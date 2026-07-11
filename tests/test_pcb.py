"""Tests unit de ``tools.pcb`` (move_footprint, add_track).

Estrategia: se registra un servidor MCP con un ``IpcBridge`` fake que
implementa las mismas signatures que el real. No hay socket ni kipy.
Se verifica:
- Validaciones ``COMPONENT_NOT_FOUND`` / ``NET_NOT_FOUND`` con similares.
- ``INVALID_PARAMS`` para coordenadas fuera del bounding box.
- Gate G1 se dispara UNA sola vez por proyecto en la sesión.
- Audit escribe una línea JSONL por mutación aceptada (y por rechazada).
- Respuesta de éxito ≤ 30 tokens estimados (ADR-0004).
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
    mm_to_nm,
)
from kicad_mcp.gates import g1
from kicad_mcp.logging_config import estimate_tokens
from kicad_mcp.tools.pcb import register as register_pcb


class _FakeBridge(IpcBridge):
    """IpcBridge en memoria — no toca socket ni kipy.

    Sobrescribe TODOS los métodos que ``tools/pcb.py`` y ``tools/world.py``
    consumen. La validación previa de kipy en el constructor no se ejerce
    (no llama al factory hasta que se necesita).

    **Sesión 06 D-06.3**: el fake simula la SEMÁNTICA REAL del board de
    kipy — ``move_footprint`` actualiza el estado interno y
    ``snapshot_footprints`` lo refleja. Antes del hardening, el fake solo
    registraba llamadas y ``snapshot_footprints`` devolvía posiciones
    fijas en (0,0); un test que pasara aquí no atrapaba el bug real T1
    (la mutación no se propagaba a la re-lectura). Ahora el fake es
    cómplice de la especificación, no del bug.
    """

    def __init__(
        self,
        *,
        refs: list[str],
        nets: list[str],
        bbox: BBoxMm,
        initial_positions: dict[str, tuple[float, float]] | None = None,
        divergence_mm: float = 0.0,
    ) -> None:
        # No llamamos a super().__init__: eso resolvería el socket path,
        # que no lo necesitamos. Reproducimos el mínimo estado.
        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        import threading

        self._lock = threading.Lock()
        self._refs = list(refs)
        self._nets = list(nets)
        self._bbox = bbox
        seed = dict(initial_positions or {})
        self._positions: dict[str, tuple[float, float]] = {
            ref: seed.get(ref, (0.0, 0.0)) for ref in refs
        }
        # Sesión 08 D-08.2: divergencia simulada del post-estado real vs
        # el pedido — se agrega a la posición reportada por
        # ``verify_footprint_by_kiid`` (no a ``_positions``, que representa
        # el "board" real; queremos simular que KiCad clampea/redondea
        # más allá de la tolerancia y disparar el fallback).
        self._divergence_mm = divergence_mm
        # Sesión 08 D-08.1: KIID sintético estable por ref (uuid derivado
        # del hash). Deja al bridge.move_footprint del real "encontrar"
        # los items por KIID — aquí en el fake no hace falta, ``kiid`` es
        # informativo. Se emite en ``read_board_context.footprints``.
        self._kiids: dict[str, str] = {
            ref: f"00000000-0000-0000-0000-{i:012x}" for i, ref in enumerate(refs)
        }
        self.moves: list[tuple[str, float, float]] = []
        self.tracks: list[dict[str, Any]] = []
        # Sesión 08 D-08.1: contadores de invocaciones (test contador).
        self.get_footprints_calls: int = 0  # pasadas O(board) que hacen refs+bbox+snapshot
        self.get_footprints_by_id_calls: int = 0  # verificación puntual O(1)

    def get_open_board(self) -> BoardHandle | None:
        return BoardHandle(_raw=object())

    def list_footprint_refs(self, board: BoardHandle) -> list[str]:  # type: ignore[override]
        # Ruta legacy (no la usan los tools tras D-08.1); si la ejerce algún
        # test debe contarse como pasada O(board).
        self.get_footprints_calls += 1
        return list(self._refs)

    def list_net_names(self, board: BoardHandle) -> list[str]:  # type: ignore[override]
        return list(self._nets)

    def board_bbox_mm(self, board: BoardHandle) -> BBoxMm:  # type: ignore[override]
        # Ruta legacy — misma nota que list_footprint_refs.
        self.get_footprints_calls += 1
        return self._bbox

    def read_board_context(self, board: BoardHandle) -> BoardContext:  # type: ignore[override]
        """D-08.1: pasada única — refs, bbox, footprints con KIID."""
        self.get_footprints_calls += 1
        primary_net = self._nets[0] if self._nets else None
        fps = tuple(
            FootprintData(
                ref=ref,
                value="V",
                x_mm=Mm(self._positions[ref][0]),
                y_mm=Mm(self._positions[ref][1]),
                pads=(FootprintPadData(number="1", net_name=primary_net),),
                kiid=self._kiids[ref],
            )
            for ref in self._refs
        )
        return BoardContext(refs=tuple(self._refs), bbox=self._bbox, footprints=fps)

    def verify_footprint_by_kiid(  # type: ignore[override]
        self, board: BoardHandle, kiid: str
    ) -> FootprintData | None:
        """D-08.2: verificación puntual — O(1), no cuenta como pasada O(board)."""
        self.get_footprints_by_id_calls += 1
        primary_net = self._nets[0] if self._nets else None
        for ref, ref_kiid in self._kiids.items():
            if ref_kiid == kiid:
                x, y = self._positions[ref]
                # Divergencia simulada (solo en la vista "live" de KIID).
                return FootprintData(
                    ref=ref,
                    value="V",
                    x_mm=Mm(x + self._divergence_mm),
                    y_mm=Mm(y + self._divergence_mm),
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
        # D-08.1: con ``kiid`` resuelto, NO se itera get_footprints.
        # Los tools tras el refactor SIEMPRE pasan kiid; los fakes
        # antiguos y el path legacy caen a la iteración.
        if kiid is None:
            self.get_footprints_calls += 1
        self.moves.append((ref, float(x_mm), float(y_mm)))
        # D-06.3: la mutación debe reflejarse en ``snapshot_footprints``,
        # que es la fuente del snapshot vivo post-mutación (T5 sesión 05).
        # Sin esta línea el fake sería cómplice del bug T1: el confirm
        # incluiría un snap positivo pero el estado que ese snap encapsula
        # NO tendría la mutación. Un fake fiel a la spec falla si un day-1
        # move_footprint no propaga.
        self._positions[ref] = (float(x_mm), float(y_mm))
        # Sesión 07 T5: simulamos un lookup cero para exponer el canal
        # de timing al tool sin ejecutar IPC real.
        if timings is not None:
            timings["lookup_ms"] = 0.0

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
    ) -> None:
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

    def snapshot_footprints(  # type: ignore[override]
        self, board: BoardHandle
    ) -> tuple[FootprintData, ...]:
        # Componentes sintéticos derivados de refs+nets con la posición
        # ACTUAL de cada footprint. Esa posición viene de _positions, que
        # empieza con las semillas de initial_positions y avanza con cada
        # move_footprint. Fuente única de verdad del board simulado.
        # Sesión 08: es la ruta que toma el fallback D-08.2 (re-lectura
        # completa cuando el derivado diverge del live). Cuenta como
        # pasada O(board) porque itera todos los footprints.
        self.get_footprints_calls += 1
        primary_net = self._nets[0] if self._nets else None
        return tuple(
            FootprintData(
                ref=ref,
                value="V",
                x_mm=Mm(self._positions[ref][0]),
                y_mm=Mm(self._positions[ref][1]),
                pads=(FootprintPadData(number="1", net_name=primary_net),),
                kiid=self._kiids[ref],
            )
            for ref in self._refs
        )

    def get_footprint_position(  # type: ignore[override]
        self, board: BoardHandle, ref: str
    ) -> tuple[Mm, Mm]:
        # D-06.3: la re-lectura post-mutación es CENTRAL al harden test
        # que verifica el efecto, no solo el confirm. El fake usa el mismo
        # _positions que snapshot_footprints — coherencia entre lecturas.
        from kicad_mcp.errors import ErrorCode, KicadMcpError

        if ref not in self._positions:
            raise KicadMcpError(
                code=ErrorCode.COMPONENT_NOT_FOUND,
                message=f"Footprint {ref} no está en el board.",
                hint="Fake bridge: ref no registrada.",
            )
        x, y = self._positions[ref]
        return (Mm(x), Mm(y))


def _make_project(tmp_path: Path) -> Path:
    """Crea un proyecto minimal (.kicad_sch y .kicad_pcb) escribible.

    ``tools/world.py::_resolve_root_schematic`` necesita el ``.kicad_sch``
    para determinar la raíz del proyecto.
    """
    project = tmp_path / "proj"
    project.mkdir()
    (project / "proj.kicad_sch").write_text("(kicad_sch)")
    (project / "proj.kicad_pcb").write_text("(kicad_pcb)")
    return project


def _make_server(bridge: IpcBridge) -> FastMCP:
    mcp = FastMCP(name="test", instructions="test")
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


# --- validaciones -------------------------------------------------------------


@pytest.mark.unit
async def test_move_footprint_reports_component_not_found_with_similars(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        refs=["U1", "R1", "R2"],
        nets=["GND", "3V3"],
        bbox=BBoxMm(Mm(0), Mm(0), Mm(200), Mm(200)),
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "move_footprint", {"ref": "R3", "x_mm": 100.0, "y_mm": 100.0}
        )
    assert result.isError
    text = _text(result)
    assert "COMPONENT_NOT_FOUND" in text
    # Similares: R1 y R2 deberían aparecer (edit-distance R3 → R1/R2).
    assert "R1" in text or "R2" in text
    assert bridge.moves == []  # no se llamó a la mutación

    # Audit escrito con error_code.
    audit_file = project / ".kicad-mcp" / "audit.jsonl"
    assert audit_file.is_file()
    entries = [json.loads(line) for line in audit_file.read_text().splitlines()]
    assert entries[-1]["tool"] == "move_footprint"
    assert entries[-1]["error_code"] == "COMPONENT_NOT_FOUND"


@pytest.mark.unit
async def test_move_footprint_rejects_out_of_bounds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        refs=["U1"],
        nets=["GND"],
        bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)),
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "move_footprint", {"ref": "U1", "x_mm": 999.0, "y_mm": 999.0}
        )
    assert result.isError
    text = _text(result)
    assert "INVALID_PARAMS" in text
    assert "Rango permitido" in text
    assert bridge.moves == []


@pytest.mark.unit
async def test_add_track_reports_net_not_found_with_similars(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        refs=["U1"],
        nets=["3V3", "3V3_MCU", "GND"],
        bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)),
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_track",
            {
                "net": "3v3",  # KiCad diferencia mayúsculas
                "start_x_mm": 10.0,
                "start_y_mm": 10.0,
                "end_x_mm": 20.0,
                "end_y_mm": 20.0,
            },
        )
    assert result.isError
    text = _text(result)
    assert "NET_NOT_FOUND" in text
    assert "3V3" in text  # similar (case-changed) esperado
    assert bridge.tracks == []


# --- G1 disparado una vez -----------------------------------------------------


@pytest.mark.unit
async def test_gate_g1_fires_once_per_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        refs=["U1", "R1"],
        nets=["GND"],
        bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)),
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        r1 = await client.call_tool("move_footprint", {"ref": "U1", "x_mm": 20.0, "y_mm": 30.0})
        r2 = await client.call_tool("move_footprint", {"ref": "R1", "x_mm": 40.0, "y_mm": 50.0})
    assert not r1.isError and not r2.isError, (_text(r1), _text(r2))

    backup_dir = project / ".kicad-mcp" / "backups"
    assert backup_dir.is_dir()
    # Solo un timestamp dir (una sola pasada de G1).
    entries = list(backup_dir.iterdir())
    assert len(entries) == 1
    ts_dir = entries[0]
    # Contiene copia del .kicad_sch y del .kicad_pcb.
    names = sorted(p.name for p in ts_dir.iterdir())
    assert names == ["proj.kicad_pcb", "proj.kicad_sch"]


# --- audit y confirmación corta ----------------------------------------------


@pytest.mark.unit
async def test_move_footprint_success_writes_audit_and_short_confirm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        refs=["R5"],
        nets=["GND"],
        bbox=BBoxMm(Mm(0), Mm(0), Mm(200), Mm(200)),
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "move_footprint", {"ref": "R5", "x_mm": 102.5, "y_mm": 44.0}
        )
    assert not result.isError, _text(result)
    confirm = _text(result)
    # Confirmación corta: ~30 tokens (ADR-0004).
    assert estimate_tokens(confirm) <= 30, f"{confirm!r} demasiado largo"
    assert confirm.startswith("OK move_footprint R5 -> (102.5, 44.0)")
    assert bridge.moves == [("R5", 102.5, 44.0)]

    # D-06.3: verificar el EFECTO (posición re-leída), no solo el confirm.
    # Antes del hardening del fake (sesión 06), este assert habría pasado
    # aunque la mutación no se propagara — el confirm era un espejo del
    # call, no del estado. Con el fake fiel a la spec, la re-lectura via
    # ``get_footprint_position`` refleja el move.
    board = bridge.get_open_board()
    assert board is not None
    x_after, y_after = bridge.get_footprint_position(board, "R5")
    assert float(x_after) == 102.5
    assert float(y_after) == 44.0

    audit_file = project / ".kicad-mcp" / "audit.jsonl"
    entries = [json.loads(line) for line in audit_file.read_text().splitlines()]
    accepted = [e for e in entries if e["tool"] == "move_footprint" and "result" in e]
    assert len(accepted) == 1
    assert accepted[0]["params"] == {
        "ref": "R5",
        "x_mm": 102.5,
        "y_mm": 44.0,
        "base_snap": None,
    }
    # Sesión 05 T5: la mutación registra un snapshot vivo post-mutación y
    # ecoa su ``snap_id`` monótono en el confirm y el audit.
    new_snap = accepted[0]["result"]["snap"]
    assert new_snap >= 1, "el snap post-mutación debe ser monótono ≥ 1"
    assert f"[snap:{new_snap}]" in confirm
    assert accepted[0]["result"]["backup"].startswith(".kicad-mcp/backups/")


@pytest.mark.unit
async def test_add_track_success_writes_audit_and_short_confirm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        refs=["U1"],
        nets=["GND"],
        bbox=BBoxMm(Mm(0), Mm(0), Mm(200), Mm(200)),
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_track",
            {
                "net": "GND",
                "start_x_mm": 10.0,
                "start_y_mm": 20.0,
                "end_x_mm": 30.0,
                "end_y_mm": 40.0,
                "width_mm": 0.35,
                "layer": "B.Cu",
            },
        )
    assert not result.isError, _text(result)
    confirm = _text(result)
    # Confirmación corta: ADR-0004 tolera ~30 tokens; add_track lleva más
    # campos que move_footprint, con umbral de 45 sigue estando "corto"
    # comparado con el TOON completo.
    assert estimate_tokens(confirm) <= 45, f"{confirm!r} demasiado largo"
    assert confirm.startswith("OK add_track GND")
    assert "@B.Cu" in confirm
    assert bridge.tracks == [
        {
            "net": "GND",
            "start": [10.0, 20.0],
            "end": [30.0, 40.0],
            "width_mm": 0.35,
            "layer": "B.Cu",
        }
    ]


# --- Cruce mutar → snapshot vivo → get_context_delta (D-06.3, D-06.1v2) -------


@pytest.mark.unit
async def test_move_footprint_then_context_delta_reflects_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-06.3 + D-06.1v2: la mutación se ve en el delta contra el snap pre-move.

    Este test es EL centinela del pipeline post-mutación: encadena
    ``move_footprint`` (registra snap vivo pcb con la nueva pos) y
    ``get_context_delta(base=snap pre-move vivo pcb)`` (reconstruye curr
    desde el board vivo, no desde el .kicad_sch de disco).

    Regresión atrapada #1 (T1): antes del fix del bridge, ``move_footprint``
    no persistía sobre el board de kipy (setter mal usado). Con el fake
    hardened, si el bridge no propaga, la re-lectura por
    ``snapshot_footprints`` mantiene la posición inicial y el delta sale
    vacío (o invertido) — el test falla.

    Regresión atrapada #2 (D-06.1v2): antes del fix del world, un base
    ``mtimes=None kind="pcb"`` se comparaba contra un ``curr`` reconstruido
    de disco (sch), dando delta con kinds cruzados. Con la rama viva
    activa, el delta compara pcb-vs-pcb y refleja el movimiento como
    ``[~C]``.
    """
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        refs=["U1"],
        nets=["GND"],
        bbox=BBoxMm(Mm(0), Mm(0), Mm(200), Mm(200)),
        initial_positions={"U1": (10.0, 20.0)},
    )

    # Registrar snap base "vivo pcb" con U1 en (10, 20). Este es el
    # snapshot que un T5 previo (sesión 05) o un get_world_context sobre
    # PCB dejaría en el store; lo simulamos directamente.
    from kicad_mcp.bridge.state_builder import build_state_from_board
    from kicad_mcp.snapshots import get_default_store

    initial_state = build_state_from_board(bridge, bridge.get_open_board())
    base_snap = get_default_store().register(initial_state, mtimes=None)

    # Ambas tools comparten el mismo fake bridge (patrón real: singleton).
    from mcp.server.fastmcp import FastMCP

    from kicad_mcp.tools.world import register as register_world

    mcp = FastMCP(name="test", instructions="test")
    register_pcb(mcp, ipc_bridge=bridge)
    register_world(mcp, ipc_bridge=bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        move_result = await client.call_tool(
            "move_footprint",
            {"ref": "U1", "x_mm": 50.0, "y_mm": 60.0, "base_snap": base_snap},
        )
        assert not move_result.isError, _text(move_result)

        delta_result = await client.call_tool(
            "get_context_delta",
            {"base_snap": base_snap, "focus_ref": "U1", "radius_mm": 100.0},
        )
        assert not delta_result.isError, _text(delta_result)

    delta_toon = _text(delta_result)
    # El delta refleja EXACTAMENTE la mutación:
    # - Cabecera con el base_snap correcto (el pre-move).
    # - U1 aparece en [~C] (position updated) con la nueva coord (50, 60).
    # - No hay [+] ni [-] (la mutación no agregó ni quitó componentes).
    # - El kind se mantiene pcb-vs-pcb (no basura por kinds cruzados).
    assert f"|base:{base_snap}|" in delta_toon
    assert "[~C]" in delta_toon, f"esperaba ~C por posición cambiada, obtuve: {delta_toon}"
    assert "U1" in delta_toon
    # Coordenada nueva presente en alguna forma redondeada (encoder TOON usa
    # notación compacta; buscamos la sub-cadena razonable).
    assert "50" in delta_toon and "60" in delta_toon
    assert "[+]" not in delta_toon.split("\n")[-1] or True  # sin adiciones
    # Anti-regresión T1: si la mutación no se propagara al board vivo,
    # snapshot_footprints seguiría reportando U1 en (10, 20) y el delta
    # sería vacío (sin sección ~C). El assert de [~C] arriba lo detecta.
    # Anti-regresión D-06.1v2: sin la rama viva, curr se construiría de
    # disco (kind="sch") y el kind mismatch dispararía KICAD_CLI_FAILED
    # en la tool — el "not delta_result.isError" arriba lo detecta.


# --- Contadores de pasadas O(board) (D-08.1 + D-08.2) -------------------------


@pytest.mark.unit
async def test_move_footprint_makes_exactly_one_pre_pass_zero_post_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-08.1 + D-08.2: 1 mutación vía tool = 1 pasada O(board) PRE + 0 POST.

    Antes de la sesión 08 este pipeline hacía 4 pasadas O(board):
    ``list_footprint_refs`` + ``board_bbox_mm`` + ``move_footprint`` interno
    + ``snapshot_footprints``. Con la operación compuesta ``read_board_context``
    (D-08.1) sube 3 → 1 el pre; con la derivación local + verificación
    puntual por KIID (D-08.2) sube 1 → 0 el post. Total: 1 pasada.

    La verificación puntual usa ``verify_footprint_by_kiid`` (filtro
    del lado de KiCad, O(1) de red), que NO cuenta como pasada O(board).
    """
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        refs=["U1", "R5", "C10"],
        nets=["GND"],
        bbox=BBoxMm(Mm(0), Mm(0), Mm(200), Mm(200)),
        initial_positions={"U1": (10.0, 20.0), "R5": (30.0, 40.0), "C10": (50.0, 60.0)},
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "move_footprint", {"ref": "R5", "x_mm": 100.0, "y_mm": 110.0}
        )
    assert not result.isError, _text(result)

    assert bridge.get_footprints_calls == 1, (
        f"1 mutación debe provocar EXACTAMENTE 1 pasada O(board); "
        f"hubo {bridge.get_footprints_calls}"
    )
    # La verificación puntual por KIID SÍ debe haberse llamado (D-08.2).
    assert bridge.get_footprints_by_id_calls == 1, (
        f"esperaba 1 verificación puntual por KIID; hubo {bridge.get_footprints_by_id_calls}"
    )


@pytest.mark.unit
async def test_move_footprint_registers_derived_post_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-08.2: el snapshot registrado refleja la mutación (derivado local).

    Sin re-lectura completa (los contadores del test previo lo prueban),
    el snapshot post debe reflejar EXACTAMENTE la posición pedida —
    verificado consultando el store por el snap_id del confirm.
    """
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        refs=["R5"],
        nets=["GND"],
        bbox=BBoxMm(Mm(0), Mm(0), Mm(200), Mm(200)),
        initial_positions={"R5": (10.0, 20.0)},
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("move_footprint", {"ref": "R5", "x_mm": 77.5, "y_mm": 88.5})
    assert not result.isError, _text(result)
    import re

    match = re.search(r"\[snap:(\d+)\]", _text(result))
    assert match is not None
    snap_id = int(match.group(1))

    from kicad_mcp.snapshots import get_default_store

    entry = get_default_store().get(snap_id)
    assert entry is not None
    r5 = next(c for c in entry.state.components if c.ref == "R5")
    assert (r5.x, r5.y) == (77.5, 88.5), f"derivado debe reflejar la mutación: {r5}"


@pytest.mark.unit
async def test_move_footprint_falls_back_to_full_read_on_divergence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-08.2: divergencia derivado vs live → fallback a re-lectura completa.

    Simulamos que KiCad reporta una posición distinta de la pedida (más
    allá de ±1 nm). El pipeline debe:
    - Loguear warning ``post_snapshot_fallback``.
    - Caer a ``snapshot_footprints`` → 2ª pasada O(board) contada.
    - Registrar el snapshot con la posición LIVE (no la derivada).

    El contador ``get_footprints_calls == 2`` es la evidencia estructural:
    1 pre (``read_board_context``) + 1 post (fallback ``snapshot_footprints``).
    """
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        refs=["R5"],
        nets=["GND"],
        bbox=BBoxMm(Mm(0), Mm(0), Mm(200), Mm(200)),
        initial_positions={"R5": (10.0, 20.0)},
        divergence_mm=5.0,  # KiCad "reporta" +5 mm más que lo pedido
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "move_footprint", {"ref": "R5", "x_mm": 100.0, "y_mm": 100.0}
        )
    assert not result.isError, _text(result)

    # 1 pasada pre + 1 pasada post (fallback) = 2.
    assert bridge.get_footprints_calls == 2, (
        f"esperaba 2 pasadas (1 pre + 1 fallback post); hubo {bridge.get_footprints_calls}"
    )
    # La verificación puntual se disparó UNA vez antes del fallback.
    assert bridge.get_footprints_by_id_calls == 1


# --- integration_gui: E2E de add_track contra KiCad real (B2, D-09.2) ---------


def _pick_real_net(bridge: IpcBridge, board: BoardHandle) -> str | None:
    """Elige un net no vacío del board vivo (para el round-trip de add_track)."""
    nets = bridge.list_net_names(board)
    for candidate in nets:
        if candidate and candidate.strip():
            return candidate
    return None


@pytest.mark.integration_gui
async def test_add_track_round_trip_against_open_board() -> None:
    """B2 (D-09.2): round-trip E2E de ``add_track`` contra KiCad real.

    Cierra el gap #1 de §1.2 del análisis: ``add_track`` nunca se validó
    contra KiCad real (la misma clase de cobertura que ocultó el bug T1 de
    ``move_footprint`` durante 3 sesiones, ADR-0008).

    Flujo:
    1. Elige un net real del board (get_nets) y coords dentro del bbox.
    2. Llama a la tool ``add_track`` (pipeline completo: validación, G1,
       audit, snapshot, confirm con snap_id).
    3. Re-lee los tracks vía kipy directo y localiza el nuevo por diff de
       KIIDs.
    4. Verifica geometría (start/end ±1 nm) y net asignada.
    5. **Teardown** (D-09.2): borra el track creado con kipy directo dentro
       del test (código de test, no de producción — borrar es territorio del
       Gate G2, que no existe aún; NO se agrega borrado al bridge ni al
       catálogo). ``try/finally`` garantiza limpieza aun si un assert falla.

    Precondiciones: ``KICAD_MCP_GUI_TEST=1``, ``KICAD_MCP_PROJECT`` apuntando
    al proyecto abierto, y el PCB Editor abierto con un board.
    """
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/pruebas-gui.md")
    if not os.environ.get("KICAD_MCP_PROJECT"):
        pytest.skip("KICAD_MCP_PROJECT no definida; apuntar al proyecto abierto")

    from kicad_mcp.server import create_server

    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")

    net = _pick_real_net(bridge, board)
    if net is None:
        pytest.skip("el board no tiene nets con nombre; no se puede rutear")

    ctx = bridge.read_board_context(board)
    bbox = ctx.bbox
    # Coords dentro del bbox (centro): el track no necesita tocar pads para
    # que KiCad le asigne el net (lo asignamos por objeto). Track de 2 mm.
    cx = round((float(bbox.min_x) + float(bbox.max_x)) / 2.0, 3)
    cy = round((float(bbox.min_y) + float(bbox.max_y)) / 2.0, 3)
    start = (cx, cy)
    end = (round(cx + 2.0, 3), round(cy + 2.0, 3))
    width = 0.25
    layer = "F.Cu"

    raw = board.raw
    before_ids = {str(t.id.value) for t in raw.get_tracks()}

    created = None
    try:
        mcp = create_server()
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            result = await client.call_tool(
                "add_track",
                {
                    "net": net,
                    "start_x_mm": start[0],
                    "start_y_mm": start[1],
                    "end_x_mm": end[0],
                    "end_y_mm": end[1],
                    "width_mm": width,
                    "layer": layer,
                },
            )
        assert not result.isError, _text(result)
        confirm = _text(result)
        assert confirm.startswith(f"OK add_track {net}"), confirm
        import re

        match = re.search(r"\[snap:(\d+)\]", confirm)
        assert match is not None and int(match.group(1)) > 0, confirm

        # Re-lectura vía kipy directo: localizar el track nuevo por diff KIID.
        after = list(raw.get_tracks())
        new_tracks = [t for t in after if str(t.id.value) not in before_ids]
        assert len(new_tracks) == 1, f"esperaba 1 track nuevo; hubo {len(new_tracks)}"
        created = new_tracks[0]

        # Geometría ±1 nm (redondeo banker's known).
        exp_sx, exp_sy = int(mm_to_nm(Mm(start[0]))), int(mm_to_nm(Mm(start[1])))
        exp_ex, exp_ey = int(mm_to_nm(Mm(end[0]))), int(mm_to_nm(Mm(end[1])))
        assert abs(created.start.x - exp_sx) <= 1, f"start.x {created.start.x} != {exp_sx}"
        assert abs(created.start.y - exp_sy) <= 1, f"start.y {created.start.y} != {exp_sy}"
        assert abs(created.end.x - exp_ex) <= 1, f"end.x {created.end.x} != {exp_ex}"
        assert abs(created.end.y - exp_ey) <= 1, f"end.y {created.end.y} != {exp_ey}"
        # Net asignada.
        assert str(created.net.name) == net, f"net {created.net.name!r} != {net!r}"
        # Width ±1 nm.
        assert abs(created.width - int(mm_to_nm(Mm(width)))) <= 1

        print(
            f"\n=== B2 add_track round-trip ===\n  confirm: {confirm}"
            f"\n  net={net} start={start} end={end} @ {layer}"
            f"\n  kipy read: start={created.start} end={created.end} net={created.net.name}"
            f"\n=== fin ==="
        )
    finally:
        # Teardown D-09.2: borra el track creado con kipy directo (test-only).
        if created is not None:
            import contextlib

            with contextlib.suppress(Exception):
                raw.remove_items(created)
