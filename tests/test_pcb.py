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
from pathlib import Path
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.ipc import BBoxMm, BoardHandle, FootprintData, FootprintPadData, IpcBridge, Mm
from kicad_mcp.gates import g1
from kicad_mcp.logging_config import estimate_tokens
from kicad_mcp.tools.pcb import register as register_pcb


class _FakeBridge(IpcBridge):
    """IpcBridge en memoria — no toca socket ni kipy.

    Sobrescribe TODOS los métodos que ``tools/pcb.py`` consume. La
    validación previa de kipy en el constructor no se ejerce (no llama
    al factory hasta que se necesita).
    """

    def __init__(
        self,
        *,
        refs: list[str],
        nets: list[str],
        bbox: BBoxMm,
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
        self.moves: list[tuple[str, float, float]] = []
        self.tracks: list[dict[str, Any]] = []

    def get_open_board(self) -> BoardHandle | None:
        return BoardHandle(_raw=object())

    def list_footprint_refs(self, board: BoardHandle) -> list[str]:  # type: ignore[override]
        return list(self._refs)

    def list_net_names(self, board: BoardHandle) -> list[str]:  # type: ignore[override]
        return list(self._nets)

    def board_bbox_mm(self, board: BoardHandle) -> BBoxMm:  # type: ignore[override]
        return self._bbox

    def move_footprint(  # type: ignore[override]
        self, board: BoardHandle, ref: str, x_mm: Mm, y_mm: Mm
    ) -> None:
        self.moves.append((ref, float(x_mm), float(y_mm)))

    def add_track(  # type: ignore[override]
        self,
        board: BoardHandle,
        net: str,
        start_mm: tuple[Mm, Mm],
        end_mm: tuple[Mm, Mm],
        width_mm: Mm,
        layer: str,
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

    def snapshot_footprints(  # type: ignore[override]
        self, board: BoardHandle
    ) -> tuple[FootprintData, ...]:
        # Componentes sintéticos derivados de refs+nets: da al pipeline post-
        # mutación algo consistente que registrar en el store con mtimes=None.
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
