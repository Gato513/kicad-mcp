"""Tests del Snapshot Store (sesión 04 T4).

Cubre:
- Monotonicidad de ``snap_id``.
- Retención de los últimos 10 (evict del más viejo).
- ``SNAPSHOT_STALE`` cuando ``base_snap`` no está en el store.
- ``EXTERNAL_EDIT_DETECTED`` cuando el mtime cambió vía ``os.utime``.
- Caso feliz: base_snap válido + mtime intacto → la mutación procede.

Los tests de integración con las tools van a `test_pcb.py`; aquí se
ejercita la unidad ``SnapshotStore`` + la ruta de ``_check_base_snap`` a
través de las tools MCP con bridge fake.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.ipc import (
    BBoxMm,
    BoardContext,
    BoardHandle,
    FootprintData,
    FootprintPadData,
    IpcBridge,
    Mm,
)
from kicad_mcp.errors import ErrorCode, KicadMcpError
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import (
    SnapshotStore,
    collect_project_mtimes,
    get_default_store,
    validate_base_snap,
)
from kicad_mcp.tools.pcb import register as register_pcb
from kicad_mcp.toon.schema import Component, NormalizedState, Pin

# --- helpers ------------------------------------------------------------------


def _state(snap: int = 0) -> NormalizedState:
    return NormalizedState(
        kind="sch",
        snap=snap,
        components=(
            Component(
                ref="U1",
                value="STM32",
                lib="MCU:STM32",
                x=100.0,
                y=50.0,
                pins=(Pin(p="1", net="3V3"),),
            ),
        ),
    )


class _FakeBridge(IpcBridge):
    """Bridge en memoria: reutiliza el patrón de ``test_pcb.py``."""

    def __init__(self, *, refs: list[str], nets: list[str], bbox: BBoxMm) -> None:
        import threading

        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._refs = list(refs)
        self._nets = list(nets)
        self._bbox = bbox
        self.moves: list[tuple[str, float, float]] = []

    def get_open_board(self) -> BoardHandle | None:
        return BoardHandle(_raw=object())

    def list_footprint_refs(self, board: BoardHandle) -> list[str]:  # type: ignore[override]
        return list(self._refs)

    def list_net_names(self, board: BoardHandle) -> list[str]:  # type: ignore[override]
        return list(self._nets)

    def board_bbox_mm(self, board: BoardHandle) -> BBoxMm:  # type: ignore[override]
        return self._bbox

    def read_board_context(self, board: BoardHandle) -> BoardContext:  # type: ignore[override]
        """D-08.1: compone en una pasada refs+bbox+footprints con KIID sintético."""
        primary_net = self._nets[0] if self._nets else None
        fps = tuple(
            FootprintData(
                ref=ref,
                value="V",
                x_mm=Mm(0.0),
                y_mm=Mm(0.0),
                pads=(FootprintPadData(number="1", net_name=primary_net),),
                kiid=f"00000000-0000-0000-0000-{i:012x}",
            )
            for i, ref in enumerate(self._refs)
        )
        return BoardContext(refs=tuple(self._refs), bbox=self._bbox, footprints=fps)

    def verify_footprint_by_kiid(  # type: ignore[override]
        self, board: BoardHandle, kiid: str
    ) -> FootprintData | None:
        """D-08.2: devuelve la posición LIVE del footprint tras la mutación.

        Como el fake registra los moves en ``self.moves`` sin propagarlos
        a ``snapshot_footprints`` (para preservar el patrón simple de
        este archivo), reflejamos la última posición pedida como la
        posición live — coincide con la derivada, sin fallback.
        """
        primary_net = self._nets[0] if self._nets else None
        for i, ref in enumerate(self._refs):
            if kiid == f"00000000-0000-0000-0000-{i:012x}":
                # Última posición pedida para esta ref, si hubo alguna.
                last = next(
                    (m for m in reversed(self.moves) if m[0] == ref),
                    None,
                )
                x_mm, y_mm = (last[1], last[2]) if last else (0.0, 0.0)
                return FootprintData(
                    ref=ref,
                    value="V",
                    x_mm=Mm(x_mm),
                    y_mm=Mm(y_mm),
                    pads=(FootprintPadData(number="1", net_name=primary_net),),
                    kiid=kiid,
                )
        return None

    def move_footprint(  # type: ignore[override]
        self,
        board: BoardHandle,
        ref: str,
        x_mm: Mm,
        y_mm: Mm,
        *,
        kiid: str | None = None,
        timings: dict[str, float] | None = None,
    ) -> None:
        self.moves.append((ref, float(x_mm), float(y_mm)))
        if timings is not None:
            timings["lookup_ms"] = 0.0

    def snapshot_footprints(  # type: ignore[override]
        self, board: BoardHandle
    ) -> tuple[FootprintData, ...]:
        primary_net = self._nets[0] if self._nets else None
        return tuple(
            FootprintData(
                ref=ref,
                value="V",
                x_mm=Mm(0.0),
                y_mm=Mm(0.0),
                pads=(FootprintPadData(number="1", net_name=primary_net),),
            )
            for ref in self._refs
        )


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "proj.kicad_sch").write_text("(kicad_sch)")
    (project / "proj.kicad_pcb").write_text("(kicad_pcb)")
    return project


def _make_server(bridge: IpcBridge) -> FastMCP:
    mcp = FastMCP(name="test-snap", instructions="test")
    register_pcb(mcp, ipc_bridge=bridge)
    return mcp


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


@pytest.fixture(autouse=True)
def _reset_g1() -> Any:
    g1.reset_session_state()
    yield
    g1.reset_session_state()


# --- unidad SnapshotStore -----------------------------------------------------


@pytest.mark.unit
def test_snap_ids_are_monotonic_per_store() -> None:
    """Cada ``register`` devuelve un ``snap_id`` estrictamente creciente."""
    store = SnapshotStore()
    ids = [store.register(_state(), mtimes={}) for _ in range(5)]
    assert ids == [1, 2, 3, 4, 5]


@pytest.mark.unit
def test_retention_evicts_oldest_beyond_10() -> None:
    """Con retención 10 y 15 registros: los primeros 5 desaparecen."""
    store = SnapshotStore()  # retention default = 10
    for _ in range(15):
        store.register(_state(), mtimes={})
    for evicted in range(1, 6):
        assert store.get(evicted) is None, f"snap_id={evicted} debía haber sido evictado"
    for kept in range(6, 16):
        assert store.get(kept) is not None, f"snap_id={kept} debería seguir en el store"


@pytest.mark.unit
def test_register_copies_mtimes_defensively() -> None:
    """Mutar el dict que pasé a ``register`` no debe afectar el snapshot guardado."""
    store = SnapshotStore()
    mtimes = {"/tmp/x.sch": 100}
    snap_id = store.register(_state(), mtimes)
    mtimes["/tmp/x.sch"] = 999
    entry = store.get(snap_id)
    assert entry is not None
    assert entry.mtimes["/tmp/x.sch"] == 100


@pytest.mark.unit
def test_live_stale_flag_lifecycle() -> None:
    """D-14.1: mark → is True; clear → is False; reset limpia el flag."""
    store = SnapshotStore()
    assert store.is_live_stale() is False
    store.mark_live_stale(42)
    assert store.is_live_stale() is True
    store.clear_live_stale()
    assert store.is_live_stale() is False
    store.mark_live_stale(7)
    store.reset()
    assert store.is_live_stale() is False


@pytest.mark.unit
def test_collect_project_mtimes_includes_both_files(tmp_path: Path) -> None:
    sch = tmp_path / "p.kicad_sch"
    pcb = tmp_path / "p.kicad_pcb"
    sch.write_text("x")
    pcb.write_text("y")
    mtimes = collect_project_mtimes(sch)
    assert set(mtimes.keys()) == {str(sch.resolve()), str(pcb.resolve())}
    assert all(v > 0 for v in mtimes.values())


@pytest.mark.unit
def test_collect_project_mtimes_ignores_missing_pcb(tmp_path: Path) -> None:
    sch = tmp_path / "only.kicad_sch"
    sch.write_text("x")
    mtimes = collect_project_mtimes(sch)
    assert list(mtimes.keys()) == [str(sch.resolve())]


# --- snapshots vivos (sesión 05 T2) ------------------------------------------


@pytest.mark.unit
def test_register_accepts_mtimes_none_as_live_snapshot() -> None:
    """``register(state, mtimes=None)`` deja el sentinel intacto en la entrada.

    Sesión 05 T2: los snapshots post-mutación se registran vivos porque el
    ``.kicad_pcb`` de disco todavía no refleja la mutación (KiCad guarda
    solo cuando el usuario lo pide).
    """
    store = SnapshotStore()
    snap_id = store.register(_state(), mtimes=None)
    entry = store.get(snap_id)
    assert entry is not None
    assert entry.mtimes is None


@pytest.mark.unit
def test_validate_base_snap_skips_mtime_check_for_live_snapshot(tmp_path: Path) -> None:
    """Un snapshot vivo NO se rechaza aunque el disco haya cambiado.

    ADR-0007: es explícito y aceptado. La regresión que este test evita es
    disparar ``EXTERNAL_EDIT_DETECTED`` como falso positivo tras el ``Save``
    que el propio agente eventualmente ejecuta.
    """
    sch = tmp_path / "proj.kicad_sch"
    pcb = tmp_path / "proj.kicad_pcb"
    sch.write_text("(kicad_sch)")
    pcb.write_text("(kicad_pcb)")

    store = SnapshotStore()
    snap_id = store.register(_state(), mtimes=None)

    # Avanzo el mtime del sch: para un snapshot de disco esto dispararía
    # EXTERNAL_EDIT_DETECTED; para uno vivo debe ser transparente.
    st = sch.stat()
    os.utime(sch, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000_000))

    entry = validate_base_snap(store, snap_id, sch)
    assert entry.snap_id == snap_id
    assert entry.mtimes is None


@pytest.mark.unit
def test_validate_base_snap_still_checks_mtime_for_disk_snapshot(tmp_path: Path) -> None:
    """Un snapshot con ``mtimes`` dict sigue disparando ``EXTERNAL_EDIT_DETECTED``.

    Verifica que la introducción del sentinel no rompió la ruta original
    (regresión potencial obvia).
    """
    sch = tmp_path / "proj.kicad_sch"
    sch.write_text("(kicad_sch)")

    store = SnapshotStore()
    snap_id = store.register(_state(), collect_project_mtimes(sch))
    st = sch.stat()
    os.utime(sch, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000_000))

    with pytest.raises(KicadMcpError) as excinfo:
        validate_base_snap(store, snap_id, sch)
    assert excinfo.value.code is ErrorCode.EXTERNAL_EDIT_DETECTED


@pytest.mark.unit
def test_snapshot_stale_exposes_structured_base_snap(tmp_path: Path) -> None:
    """``SNAPSHOT_STALE`` lleva ``base_snap`` y ``retention`` en ``data`` (T2).

    F3 intacta: el código no cambia, sólo se enriquece el payload para que
    el agente correlacione el fallo con su plan sin parsear el mensaje.
    """
    store = SnapshotStore(retention=7)
    sch = tmp_path / "proj.kicad_sch"
    sch.write_text("x")
    with pytest.raises(KicadMcpError) as excinfo:
        validate_base_snap(store, 42, sch)

    err = excinfo.value
    assert err.code is ErrorCode.SNAPSHOT_STALE
    assert err.data == {"base_snap": 42, "retention": 7}
    # to_dict expone el payload estructurado (uso interno/tests); el agente lo
    # recibe embebido como JSON en el mensaje de la excepción (sesión 16, ver
    # ``KicadMcpError.__init__``) ya que el SDK ``mcp`` colapsa toda excepción
    # a ``str(e)`` antes de llegar al cliente.
    payload = err.to_dict()
    assert "data" in str(err) and '"base_snap": 42' in str(err)
    assert payload["data"]["base_snap"] == 42
    assert payload["data"]["retention"] == 7


# --- integración con tools MCP: base_snap ------------------------------------


@pytest.mark.unit
async def test_move_footprint_snapshot_stale_when_base_snap_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``base_snap`` inexistente en el store ⇒ ``SNAPSHOT_STALE`` con hint accionable."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(refs=["U1"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(200), Mm(200)))
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "move_footprint",
            {"ref": "U1", "x_mm": 100.0, "y_mm": 100.0, "base_snap": 999},
        )
    assert result.isError
    text = _text(result)
    assert "SNAPSHOT_STALE" in text
    assert "get_world_context" in text  # hint accionable
    assert bridge.moves == []  # mutación NO procedió


@pytest.mark.unit
async def test_move_footprint_external_edit_detected_when_mtime_diverges(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``base_snap`` registrado pero mtime cambió ⇒ ``EXTERNAL_EDIT_DETECTED``."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(refs=["U1"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(200), Mm(200)))
    mcp = _make_server(bridge)

    # Registro un snap con los mtimes actuales.
    sch = project / "proj.kicad_sch"
    snap_id = get_default_store().register(_state(), collect_project_mtimes(sch))

    # Simulo edición externa avanzando el mtime del sch.
    st = sch.stat()
    os.utime(sch, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000_000))

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "move_footprint",
            {"ref": "U1", "x_mm": 100.0, "y_mm": 100.0, "base_snap": snap_id},
        )
    assert result.isError
    text = _text(result)
    assert "EXTERNAL_EDIT_DETECTED" in text
    assert "editado fuera del agente" in text
    # Hint accionable: instruye pedir contexto de nuevo antes de reintentar.
    assert "pedí contexto" in text
    assert bridge.moves == []


@pytest.mark.unit
async def test_move_footprint_happy_path_with_valid_base_snap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``base_snap`` en el store + mtime intacto ⇒ mutación procede; snap se ecoa."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(refs=["R7"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(200), Mm(200)))
    mcp = _make_server(bridge)

    sch = project / "proj.kicad_sch"
    snap_id = get_default_store().register(_state(), collect_project_mtimes(sch))

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "move_footprint",
            {"ref": "R7", "x_mm": 33.0, "y_mm": 44.0, "base_snap": snap_id},
        )
    assert not result.isError, _text(result)
    confirm = _text(result)
    # Sesión 05 T5: el confirm ecoa el snap_id post-mutación (vivo,
    # ADR-0007), no el base_snap. base_snap sigue en el audit.params.
    new_snap = snap_id + 1
    assert f"[snap:{new_snap}]" in confirm, f"esperaba el snap post-mutación: {confirm!r}"
    # Y ese nuevo snap está en el store con mtimes=None.
    entry = get_default_store().get(new_snap)
    assert entry is not None
    assert entry.mtimes is None
    assert bridge.moves == [("R7", 33.0, 44.0)]

    entries = [
        json.loads(line)
        for line in (project / ".kicad-mcp" / "audit.jsonl").read_text().splitlines()
    ]
    accepted = [e for e in entries if e["tool"] == "move_footprint" and "result" in e]
    assert accepted[-1]["params"]["base_snap"] == snap_id
    assert accepted[-1]["result"]["snap"] == new_snap
