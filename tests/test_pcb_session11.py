"""Tests unit de las tools de sesión 11 (D-11.1..D-11.5).

- ``save_board`` (D-11.1): persistencia live→disco, snapshot de disco con
  mtimes frescos, confirm con ruta absoluta, sin board → error, busy sin retry.
- ``delete_track`` / ``delete_via`` (D-11.2): borrado feliz, ambigüedad →
  INVALID_PARAMS con candidatos, net inexistente, nada dentro de tolerancia.
- ``get_component_detail`` (D-11.3): resolución REF.PAD y encoding compacto.
- ``add_track`` anclado a pads (D-11.4): resolución, ref/pad inexistente,
  mezcla de formas.

Estrategia idéntica a ``test_pcb.py``: fake bridge en memoria, sin socket ni
kipy. El fake es cómplice de la spec, no del bug.
"""

from __future__ import annotations

import json
import os
import re
import threading
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
    ComponentDetail,
    CopperItem,
    FootprintData,
    FootprintPadData,
    IpcBridge,
    Mm,
    PadGeom,
)
from kicad_mcp.errors import ErrorCode, KicadMcpError
from kicad_mcp.gates import g1
from kicad_mcp.logging_config import estimate_tokens
from kicad_mcp.snapshots import collect_project_mtimes, get_default_store
from kicad_mcp.tools.pcb import register as register_pcb


class _FakeBridge(IpcBridge):
    """Fake en memoria para las tools de sesión 11."""

    def __init__(
        self,
        *,
        refs: list[str],
        nets: list[str],
        bbox: BBoxMm,
        copper: dict[str, list[CopperItem]] | None = None,
        details: dict[str, ComponentDetail] | None = None,
        has_board: bool = True,
        save_error: KicadMcpError | None = None,
    ) -> None:
        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._refs = list(refs)
        self._nets = list(nets)
        self._bbox = bbox
        self._copper = copper or {}
        self._details = details or {}
        self._has_board = has_board
        self._save_error = save_error
        self.saved = 0
        self.removed_kiids: list[str] = []
        self.tracks: list[dict[str, Any]] = []

    def get_open_board(self) -> BoardHandle | None:
        return BoardHandle(_raw=object()) if self._has_board else None

    def list_net_names(self, board: BoardHandle) -> list[str]:  # type: ignore[override]
        return list(self._nets)

    def read_board_context(self, board: BoardHandle) -> BoardContext:  # type: ignore[override]
        primary = self._nets[0] if self._nets else None
        fps = tuple(
            FootprintData(
                ref=r,
                value="V",
                x_mm=Mm(0.0),
                y_mm=Mm(0.0),
                pads=(FootprintPadData(number="1", net_name=primary),),
                kiid=f"kiid-{r}",
            )
            for r in self._refs
        )
        return BoardContext(refs=tuple(self._refs), bbox=self._bbox, footprints=fps)

    def snapshot_footprints(  # type: ignore[override]
        self, board: BoardHandle
    ) -> tuple[FootprintData, ...]:
        return self.read_board_context(board).footprints

    def list_net_copper(  # type: ignore[override]
        self, board: BoardHandle, net: str
    ) -> tuple[CopperItem, ...]:
        return tuple(self._copper.get(net, []))

    def list_all_copper(self, board: BoardHandle) -> tuple[CopperItem, ...]:  # type: ignore[override]
        return tuple(it for items in self._copper.values() for it in items)

    def get_copper_by_kiid(  # type: ignore[override]
        self, board: BoardHandle, kiid: str
    ) -> CopperItem | None:
        for items in self._copper.values():
            for it in items:
                if it.kiid == kiid:
                    return it
        return None

    def list_all_pads(self, board: BoardHandle) -> tuple[PadGeom, ...]:  # type: ignore[override]
        # Sesión 16 D-16.4: sin pads simulados por default.
        return tuple(getattr(self, "pads", ()))

    def remove_by_kiid(self, board: BoardHandle, kiid: str) -> bool:  # type: ignore[override]
        self.removed_kiids.append(kiid)
        return True

    def save_board(self, board: BoardHandle) -> None:  # type: ignore[override]
        if self._save_error is not None:
            raise self._save_error
        self.saved += 1

    def get_component_detail(  # type: ignore[override]
        self, board: BoardHandle, ref: str
    ) -> ComponentDetail:
        if ref not in self._details:
            raise KicadMcpError(
                code=ErrorCode.COMPONENT_NOT_FOUND,
                message=f"Footprint {ref} no está en el board.",
                hint="fake: ref no registrada.",
            )
        return self._details[ref]

    def add_track(  # type: ignore[override]
        self,
        board: BoardHandle,
        net: str,
        start_mm: tuple[Mm, Mm],
        end_mm: tuple[Mm, Mm],
        width_mm: Mm,
        layer: str,
        *,
        timings: dict[str, float] | None = None,
    ) -> str:
        # Sesión 19d: add_track pasa a devolver el KIID creado (simétrico a
        # add_via) para soportar la verificación post-creación del net real.
        kiid = f"track-{len(self.tracks):012x}"
        self.tracks.append(
            {
                "net": net,
                "start": [float(start_mm[0]), float(start_mm[1])],
                "end": [float(end_mm[0]), float(end_mm[1])],
                "width_mm": float(width_mm),
                "layer": layer,
            }
        )
        if timings is not None:
            timings["lookup_ms"] = 0.0
        return kiid


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "proj.kicad_sch").write_text("(kicad_sch)")
    (project / "proj.kicad_pcb").write_text("(kicad_pcb)")
    return project


def _make_server(bridge: IpcBridge) -> FastMCP:
    mcp = FastMCP(name="test-s11", instructions="test")
    register_pcb(mcp, ipc_bridge=bridge)
    return mcp


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _track(kiid: str, net: str, sx: float, sy: float, ex: float, ey: float) -> CopperItem:
    return CopperItem(
        kind="track",
        kiid=kiid,
        net_name=net,
        layer="F.Cu",
        start_x_mm=Mm(sx),
        start_y_mm=Mm(sy),
        end_x_mm=Mm(ex),
        end_y_mm=Mm(ey),
        mid_x_mm=None,
        mid_y_mm=None,
    )


def _via(kiid: str, net: str, x: float, y: float) -> CopperItem:
    return CopperItem(
        kind="via",
        kiid=kiid,
        net_name=net,
        layer=None,
        start_x_mm=Mm(x),
        start_y_mm=Mm(y),
        end_x_mm=None,
        end_y_mm=None,
        mid_x_mm=None,
        mid_y_mm=None,
    )


def _detail(ref: str, pads: list[tuple[str, str | None, float, float]]) -> ComponentDetail:
    return ComponentDetail(
        ref=ref,
        value="V",
        x_mm=Mm(0.0),
        y_mm=Mm(0.0),
        rotation_deg=0.0,
        bbox_min_x=Mm(0.0),
        bbox_min_y=Mm(0.0),
        bbox_max_x=Mm(1.0),
        bbox_max_y=Mm(1.0),
        bbox_source="pads",
        pads=tuple(PadDetail_from(num, net, x, y) for (num, net, x, y) in pads),
    )


def PadDetail_from(num: str, net: str | None, x: float, y: float) -> Any:
    from kicad_mcp.bridge.ipc import PadDetail

    return PadDetail(
        number=num,
        net_name=net,
        x_mm=Mm(x),
        y_mm=Mm(y),
        w_mm=Mm(1.0),
        h_mm=Mm(1.0),
        layer="F.Cu",
    )


@pytest.fixture(autouse=True)
def _reset_g1() -> Any:
    g1.reset_session_state()
    yield
    g1.reset_session_state()


# --- save_board (D-11.1) ------------------------------------------------------


@pytest.mark.unit
async def test_save_board_happy_registers_disk_snapshot_with_fresh_mtimes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(refs=["U1"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)))
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("save_board", {})
    assert not result.isError, _text(result)
    confirm = _text(result)
    assert estimate_tokens(confirm) <= 50, f"{confirm!r} demasiado largo"
    assert confirm.startswith("OK save_board")
    # Ruta ABSOLUTA en el confirm (F-02 aplicado a save_board).
    assert str(project / "proj.kicad_pcb") in confirm
    assert bridge.saved == 1

    match = re.search(r"\[snap:(\d+)\]", confirm)
    assert match is not None
    snap_id = int(match.group(1))
    entry = get_default_store().get(snap_id)
    assert entry is not None
    # Snapshot de DISCO: mtimes frescos (NO None, que es el patrón vivo).
    assert entry.mtimes is not None, "save_board debe registrar snapshot de disco"
    assert str((project / "proj.kicad_pcb").resolve()) in entry.mtimes

    audit = project / ".kicad-mcp" / "audit.jsonl"
    entries = [json.loads(x) for x in audit.read_text().splitlines()]
    accepted = [e for e in entries if e["tool"] == "save_board" and "result" in e]
    assert len(accepted) == 1


@pytest.mark.unit
async def test_save_board_no_board_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        refs=["U1"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)), has_board=False
    )
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("save_board", {})
    assert result.isError
    assert "PROJECT_NOT_FOUND" in _text(result)
    assert bridge.saved == 0


@pytest.mark.unit
async def test_save_board_busy_propagates_without_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """busy en el save es escritura: se propaga tal cual, sin reintentos (D-07.1)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    busy = KicadMcpError(
        code=ErrorCode.KICAD_CLI_FAILED,
        message="KiCad está ocupado durante save_board.",
        hint="reintentá en unos segundos.",
        data={"ipc_status": "busy"},
    )
    bridge = _FakeBridge(
        refs=["U1"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)), save_error=busy
    )
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("save_board", {})
    assert result.isError
    text = _text(result)
    # El código se propaga tal cual (busy viaja en data.ipc_status, no en el
    # texto); lo que importa es que NO se reintentó ni se tragó el error.
    assert "KICAD_CLI_FAILED" in text and "ocupado" in text
    assert bridge.saved == 0


# --- guard por mtime independiente de base_snap (P3.2, sesión 18) ------------


@pytest.mark.unit
async def test_save_board_external_edit_detected_without_base_snap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """P3.2: el guard corre AUNQUE el agente no pase ``base_snap`` — cierra el
    hueco que ``tool-catalog.md`` documentaba como "sin verificación de
    coherencia" cuando ``base_snap`` está ausente. Requiere que este proceso
    ya haya registrado un snapshot de disco (el ancla); acá se simula con un
    ``get_default_store().register(...)`` directo, como haría cualquier tool
    de lectura previa (``get_world_context``, ``route_board``...)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(refs=["U1"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)))
    mcp = _make_server(bridge)

    from kicad_mcp.toon.schema import NormalizedState

    pcb = project / "proj.kicad_pcb"
    sch = project / "proj.kicad_sch"
    get_default_store().register(
        NormalizedState(kind="pcb", snap=0, components=()), collect_project_mtimes(sch)
    )

    # Edición externa silenciosa del .kicad_pcb — nadie de este proceso la
    # registró.
    st = pcb.stat()
    os.utime(pcb, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000_000))

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("save_board", {})  # SIN base_snap

    assert result.isError
    text = _text(result)
    assert "EXTERNAL_EDIT_DETECTED" in text
    assert "reload_board_from_disk" in text
    assert bridge.saved == 0  # el guard bloqueó ANTES de tocar el board


@pytest.mark.unit
async def test_save_board_proceeds_when_store_has_no_disk_anchor_yet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regresión: un store fresco (sin ningún snapshot de disco registrado
    todavía en este proceso) NO debe bloquear — no hay ancla contra la cual
    comparar (mismo criterio ya cubierto por
    ``test_save_board_happy_registers_disk_snapshot_with_fresh_mtimes``, acá
    explícito como contrato del guard P3.2)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(refs=["U1"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)))
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("save_board", {})

    assert not result.isError, _text(result)
    assert bridge.saved == 1


# --- delete_track / delete_via (D-11.2) --------------------------------------


@pytest.mark.unit
async def test_delete_track_happy_removes_by_kiid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {"GND": [_track("T1", "GND", 10.0, 10.0, 20.0, 10.0)]}
    bridge = _FakeBridge(
        refs=["U1"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)), copper=copper
    )
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "delete_track", {"net": "GND", "near_x_mm": 15.0, "near_y_mm": 10.0}
        )
    assert not result.isError, _text(result)
    confirm = _text(result)
    assert estimate_tokens(confirm) <= 50
    assert confirm.startswith("OK delete_track GND")
    assert bridge.removed_kiids == ["T1"]


@pytest.mark.unit
async def test_delete_via_happy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {"3V3": [_via("V1", "3V3", 50.0, 50.0)]}
    bridge = _FakeBridge(
        refs=["U1"], nets=["3V3"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)), copper=copper
    )
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_via", {"net": "3V3", "x_mm": 50.1, "y_mm": 50.1})
    assert not result.isError, _text(result)
    assert bridge.removed_kiids == ["V1"]


@pytest.mark.unit
async def test_delete_track_ambiguity_returns_candidates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """2 tracks dentro de tolerancia ⇒ INVALID_PARAMS con candidatos, sin borrar."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {
        "GND": [
            _track("A", "GND", 10.0, 10.0, 20.0, 10.0),
            _track("B", "GND", 10.0, 10.1, 20.0, 10.1),  # a 0.1 mm del primero
        ]
    }
    bridge = _FakeBridge(
        refs=["U1"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)), copper=copper
    )
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "delete_track", {"net": "GND", "near_x_mm": 15.0, "near_y_mm": 10.05}
        )
    assert result.isError
    text = _text(result)
    assert "INVALID_PARAMS" in text
    assert "candidatos" in text
    # NUNCA borra en ambigüedad.
    assert bridge.removed_kiids == []


@pytest.mark.unit
async def test_delete_track_net_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        refs=["U1"], nets=["GND", "3V3"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100))
    )
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "delete_track", {"net": "3v3", "near_x_mm": 15.0, "near_y_mm": 10.0}
        )
    assert result.isError
    text = _text(result)
    assert "NET_NOT_FOUND" in text
    assert "3V3" in text
    assert bridge.removed_kiids == []


@pytest.mark.unit
async def test_delete_track_nothing_in_tolerance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {"GND": [_track("T1", "GND", 10.0, 10.0, 20.0, 10.0)]}
    bridge = _FakeBridge(
        refs=["U1"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)), copper=copper
    )
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "delete_track", {"net": "GND", "near_x_mm": 80.0, "near_y_mm": 80.0}
        )
    assert result.isError
    assert "INVALID_PARAMS" in _text(result)
    assert bridge.removed_kiids == []


# --- get_component_detail (D-11.3) -------------------------------------------


@pytest.mark.unit
async def test_get_component_detail_encodes_pads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    details = {
        "R5": _detail("R5", [("1", "GND", 10.0, 20.0), ("2", "3V3", 12.0, 20.0)]),
    }
    bridge = _FakeBridge(
        refs=["R5"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)), details=details
    )
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_component_detail", {"ref": "R5"})
    assert not result.isError, _text(result)
    out = _text(result)
    assert out.startswith("DETAIL|R5|pcb|")
    assert "[PADS] 2" in out
    assert "1 GND 10.0,20.0" in out
    assert "2 3V3 12.0,20.0" in out


@pytest.mark.unit
async def test_get_component_detail_unknown_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(refs=["R5"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)))
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_component_detail", {"ref": "Q9"})
    assert result.isError
    assert "COMPONENT_NOT_FOUND" in _text(result)


@pytest.mark.unit
async def test_get_component_detail_sch_not_supported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(refs=["R5"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)))
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_component_detail", {"ref": "R5", "kind": "sch"})
    assert result.isError
    assert "INVALID_PARAMS" in _text(result)


# --- add_track anclado a pads (D-11.4) ---------------------------------------


@pytest.mark.unit
async def test_add_track_from_pad_resolves_coords(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Rotación 0/90/180/270 vive en kipy; acá probamos NUESTRA resolución
    REF.PAD → coordenada. Los pads del fake ya vienen absolutos (como kipy)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    details = {
        "U1": _detail("U1", [("8", "GND", 30.0, 40.0)]),
        "C2": _detail("C2", [("2", "GND", 55.5, 41.0)]),
    }
    bridge = _FakeBridge(
        refs=["U1", "C2"],
        nets=["GND"],
        bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)),
        details=details,
    )
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_track", {"net": "GND", "from_pad": "U1.8", "to_pad": "C2.2"}
        )
    assert not result.isError, _text(result)
    assert bridge.tracks == [
        {
            "net": "GND",
            "start": [30.0, 40.0],
            "end": [55.5, 41.0],
            "width_mm": 0.25,
            "layer": "F.Cu",
        }
    ]


@pytest.mark.unit
async def test_add_track_from_pad_unknown_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    details = {"U1": _detail("U1", [("8", "GND", 30.0, 40.0)])}
    bridge = _FakeBridge(
        refs=["U1"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)), details=details
    )
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_track", {"net": "GND", "from_pad": "U1.8", "to_pad": "Q9.1"}
        )
    assert result.isError
    assert "COMPONENT_NOT_FOUND" in _text(result)
    assert bridge.tracks == []


@pytest.mark.unit
async def test_add_track_from_pad_unknown_pad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    details = {"U1": _detail("U1", [("8", "GND", 30.0, 40.0)])}
    bridge = _FakeBridge(
        refs=["U1"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)), details=details
    )
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_track", {"net": "GND", "from_pad": "U1.8", "to_pad": "U1.99"}
        )
    assert result.isError
    text = _text(result)
    assert "INVALID_PARAMS" in text
    assert bridge.tracks == []


@pytest.mark.unit
async def test_add_track_mixing_coords_and_pads_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    details = {"U1": _detail("U1", [("8", "GND", 30.0, 40.0)])}
    bridge = _FakeBridge(
        refs=["U1"], nets=["GND"], bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)), details=details
    )
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_track",
            {"net": "GND", "from_pad": "U1.8", "start_x_mm": 1.0, "start_y_mm": 2.0},
        )
    assert result.isError
    assert "INVALID_PARAMS" in _text(result)
    assert bridge.tracks == []
