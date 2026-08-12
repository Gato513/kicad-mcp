"""Tests unit de ``delete_tracks_bulk`` (sesión 19d, 19d.2).

Motivación: el Bloque 3 de la investigación 19c necesitó 266 llamadas
individuales ``delete_track``/``delete_via`` para vaciar el cobre del board
antes de un ``route_board`` desde cero — no existía una tool de borrado
masivo por filtro. Reutiliza el mismo pipeline de filtrado que ``get_tracks``
(``net``/``bbox``/``layer``, al menos uno obligatorio) pero borra en un solo
``remove_many_by_kiid`` en vez de N llamadas individuales, con ``dry_run``
para inspeccionar antes de comprometerse.

Estrategia idéntica al resto de la sesión 16/19: fake bridge en memoria, sin
socket ni kipy.
"""

from __future__ import annotations

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
    CopperItem,
    FootprintData,
    FootprintPadData,
    IpcBridge,
    Mm,
    ZoneItem,
)
from kicad_mcp.errors import ErrorCode, KicadMcpError
from kicad_mcp.gates import g1
from kicad_mcp.tools.pcb import register as register_pcb


class _FakeBridge(IpcBridge):
    """Bridge en memoria con soporte de cobre + zonas board-wide (19d.2)."""

    def __init__(
        self,
        *,
        nets: list[str] | None = None,
        bbox: BBoxMm | None = None,
        copper: dict[str, list[CopperItem]] | None = None,
        zones: list[ZoneItem] | None = None,
        fail_save_after: int | None = None,
    ) -> None:
        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._refs = ["U1"]
        self._nets = list(nets or ["GND"])
        self._bbox = bbox or BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100))
        self._copper = copper or {}
        self._zones = list(zones or [])
        self.removed_kiids: list[str] = []
        self.remove_many_calls: list[list[str]] = []
        self.refill_calls = 0
        self.enforce_hole_clearance_calls = 0
        self.calls: list[str] = []
        # 34a-fix-1 (patrón test_pcb_zones.py, sesión 27): a partir de la
        # llamada N+1 a save_board(), levanta KicadMcpError — simula el
        # fallo de persistencia post-refill sin tocar kipy real. ``None`` =
        # nunca falla.
        self._fail_save_after = fail_save_after
        self.saved: list[str] = []

    def get_open_board(self) -> BoardHandle | None:
        return BoardHandle(_raw=object())

    def refill_zones(self, board: BoardHandle) -> int:  # type: ignore[override]
        self.refill_calls += 1
        self.calls.append("refill")
        return sum(1 for z in self._zones if z.kind == "copper")

    def enforce_hole_clearance(self, board: BoardHandle, pcb_path: Path) -> int:  # type: ignore[override]
        # F-D3-01 (sesión 21): sin geometría real de holes en este fake (sin
        # kipy) — sólo registra que el paso corrió, mismo espíritu que
        # refill_calls.
        self.enforce_hole_clearance_calls += 1
        self.calls.append("enforce")
        return 0

    def save_board(self, board: BoardHandle) -> None:  # type: ignore[override]
        self.calls.append("save")
        self.saved.append("proj.kicad_pcb")
        if self._fail_save_after is not None and len(self.saved) > self._fail_save_after:
            raise KicadMcpError(
                code=ErrorCode.KICAD_CLI_FAILED,
                message="fake: save_board falló (test 34a-fix-1).",
                hint="test only",
            )

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

    def list_net_copper(  # type: ignore[override]
        self, board: BoardHandle, net: str
    ) -> tuple[CopperItem, ...]:
        return tuple(self._copper.get(net, []))

    def list_all_copper(self, board: BoardHandle) -> tuple[CopperItem, ...]:  # type: ignore[override]
        return tuple(it for items in self._copper.values() for it in items)

    def remove_many_by_kiid(self, board: BoardHandle, kiids: list[str]) -> int:  # type: ignore[override]
        self.remove_many_calls.append(list(kiids))
        removed = 0
        for net, items in list(self._copper.items()):
            kept = [it for it in items if it.kiid not in kiids]
            removed += len(items) - len(kept)
            self._copper[net] = kept
        self.removed_kiids.extend(kiids)
        return removed

    def list_zones(self, board: BoardHandle) -> tuple[ZoneItem, ...]:  # type: ignore[override]
        return tuple(self._zones)


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "proj.kicad_sch").write_text("(kicad_sch)")
    (project / "proj.kicad_pcb").write_text("(kicad_pcb)")
    return project


def _make_server(bridge: IpcBridge) -> FastMCP:
    mcp = FastMCP(name="test-19d-bulk", instructions="test")
    register_pcb(mcp, ipc_bridge=bridge)
    return mcp


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _json(result: CallToolResult) -> dict[str, Any]:
    import json

    return dict(json.loads(_text(result)))


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
        width_mm=Mm(0.25),
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
        size_mm=Mm(0.8),
        drill_mm=Mm(0.4),
        via_layers=("F.Cu", "B.Cu"),
    )


def _copper_zone(kiid: str, net: str) -> ZoneItem:
    return ZoneItem(
        kind="copper",
        kiid=kiid,
        net_name=net,
        layer="B.Cu",
        bbox_min_x=Mm(0.0),
        bbox_min_y=Mm(0.0),
        bbox_max_x=Mm(50.0),
        bbox_max_y=Mm(50.0),
        area_mm2=2500.0,
        filled=True,
        vertices_mm=((Mm(0.0), Mm(0.0)), (Mm(50.0), Mm(0.0)), (Mm(50.0), Mm(50.0))),
    )


@pytest.fixture(autouse=True)
def _reset_g1() -> Any:
    g1.reset_session_state()
    yield
    g1.reset_session_state()


@pytest.mark.unit
async def test_delete_tracks_bulk_requires_a_filter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge()
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_tracks_bulk", {})
    assert result.isError
    assert "INVALID_PARAMS" in _text(result)


@pytest.mark.unit
async def test_delete_tracks_bulk_net_not_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(nets=["GND"])
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_tracks_bulk", {"net": "3V3"})
    assert result.isError
    assert "NET_NOT_FOUND" in _text(result)


@pytest.mark.unit
async def test_delete_tracks_bulk_dry_run_does_not_mutate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {
        "GND": [
            _track("T1", "GND", 0.0, 0.0, 10.0, 0.0),
            _via("V1", "GND", 20.0, 20.0),
        ],
    }
    bridge = _FakeBridge(nets=["GND"], copper=copper)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_tracks_bulk", {"net": "GND", "dry_run": True})
    assert not result.isError, _text(result)
    payload = _json(result)
    assert payload == {
        "tracks_deleted": 1,
        "vias_deleted": 1,
        "snap_id": None,
        "zones_refilled": 0,
    }
    assert bridge.remove_many_calls == []
    assert len(bridge.list_all_copper(BoardHandle(_raw=object()))) == 2


@pytest.mark.unit
async def test_delete_tracks_bulk_deletes_matching_items_and_registers_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {
        "GND": [
            _track("T1", "GND", 0.0, 0.0, 10.0, 0.0),
            _via("V1", "GND", 20.0, 20.0),
        ],
        "3V3": [_track("T9", "3V3", 5.0, 5.0, 6.0, 6.0)],
    }
    bridge = _FakeBridge(nets=["GND", "3V3"], copper=copper)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_tracks_bulk", {"net": "GND"})
    assert not result.isError, _text(result)
    payload = _json(result)
    assert payload["tracks_deleted"] == 1
    assert payload["vias_deleted"] == 1
    assert isinstance(payload["snap_id"], int)
    assert payload["zones_refilled"] == 0
    assert set(bridge.remove_many_calls[0]) == {"T1", "V1"}
    # El net 3V3, fuera del filtro, no se toca.
    assert bridge.list_net_copper(BoardHandle(_raw=object()), "3V3") == (
        _track("T9", "3V3", 5.0, 5.0, 6.0, 6.0),
    )


@pytest.mark.unit
async def test_delete_tracks_bulk_include_vias_false_excludes_vias(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {
        "GND": [
            _track("T1", "GND", 0.0, 0.0, 10.0, 0.0),
            _via("V1", "GND", 20.0, 20.0),
        ],
    }
    bridge = _FakeBridge(nets=["GND"], copper=copper)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_tracks_bulk", {"net": "GND", "include_vias": False})
    assert not result.isError, _text(result)
    payload = _json(result)
    assert payload["tracks_deleted"] == 1
    assert payload["vias_deleted"] == 0
    assert bridge.remove_many_calls == [["T1"]]


@pytest.mark.unit
async def test_delete_tracks_bulk_bbox_filters_out_of_range_items(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {
        "GND": [
            _track("T1", "GND", 0.0, 0.0, 1.0, 0.0),
            _track("T2", "GND", 90.0, 90.0, 91.0, 90.0),
        ],
    }
    bridge = _FakeBridge(nets=["GND"], copper=copper)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_tracks_bulk", {"bbox": [-1.0, -1.0, 5.0, 5.0]})
    assert not result.isError, _text(result)
    payload = _json(result)
    assert payload["tracks_deleted"] == 1
    assert bridge.remove_many_calls == [["T1"]]


@pytest.mark.unit
async def test_delete_tracks_bulk_refills_zones_when_copper_zone_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {"GND": [_track("T1", "GND", 0.0, 0.0, 10.0, 0.0)]}
    zones = [_copper_zone("Z1", "GND")]
    bridge = _FakeBridge(nets=["GND"], copper=copper, zones=zones)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_tracks_bulk", {"net": "GND"})
    assert not result.isError, _text(result)
    payload = _json(result)
    assert payload["zones_refilled"] == 1
    assert bridge.refill_calls == 1


@pytest.mark.unit
async def test_delete_tracks_bulk_no_refill_without_copper_zones(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {"GND": [_track("T1", "GND", 0.0, 0.0, 10.0, 0.0)]}
    bridge = _FakeBridge(nets=["GND"], copper=copper)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_tracks_bulk", {"net": "GND"})
    assert not result.isError, _text(result)
    payload = _json(result)
    assert payload["zones_refilled"] == 0
    assert bridge.refill_calls == 0


@pytest.mark.unit
async def test_delete_tracks_bulk_zone_touch_runs_refill_enforce_save_in_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """34a-fix-1: cuando el borrado toca ≥1 zona de cobre, delete_tracks_bulk
    corre refill → enforce_hole_clearance → save_board (D-23.2, precedente
    técnico de ADR-0012 extendido a add_zone/fill_zones en sesión 27) — sin
    esto el disco queda con el clearance roto de forma indefinida (A1)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {"GND": [_track("T1", "GND", 0.0, 0.0, 10.0, 0.0)]}
    zones = [_copper_zone("Z1", "GND")]
    bridge = _FakeBridge(nets=["GND"], copper=copper, zones=zones)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_tracks_bulk", {"net": "GND"})
    assert not result.isError, _text(result)
    payload = _json(result)
    # Sin regresión respecto de test_delete_tracks_bulk_refills_zones_when_copper_zone_present.
    assert payload["tracks_deleted"] == 1
    assert payload["zones_refilled"] == 1
    assert payload["snap_id"] is not None
    # A1: orden estricto refill → enforce → save, cada uno exactamente 1 vez.
    assert bridge.refill_calls == 1
    assert bridge.enforce_hole_clearance_calls == 1
    assert len(bridge.saved) == 1
    assert bridge.calls == ["refill", "enforce", "save"]


@pytest.mark.unit
async def test_delete_tracks_bulk_zone_touch_persist_failure_is_visible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """34a-fix-1 (A2/P2): si save_board() falla tras refill+enforce,
    delete_tracks_bulk audita el fallo y re-levanta KicadMcpError con
    POST_ZONE_PERSIST_FAILED — nunca completa como éxito silencioso; el
    vivo ya tiene el fix (live_has_fix=True)."""
    import json

    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {"GND": [_track("T1", "GND", 0.0, 0.0, 10.0, 0.0)]}
    zones = [_copper_zone("Z1", "GND")]
    bridge = _FakeBridge(nets=["GND"], copper=copper, zones=zones, fail_save_after=0)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_tracks_bulk", {"net": "GND"})
    assert result.isError
    text = _text(result)
    assert "POST_ZONE_PERSIST_FAILED" in text
    assert "delete_tracks_bulk" in text
    assert "live_has_fix" in text
    # El vivo sí quedó arreglado — sólo la persistencia falló.
    assert bridge.refill_calls == 1
    assert bridge.enforce_hole_clearance_calls == 1
    assert len(bridge.saved) == 1

    audit_file = project / ".kicad-mcp" / "audit.jsonl"
    assert audit_file.is_file()
    entries = [json.loads(line) for line in audit_file.read_text().splitlines()]
    assert entries[-1]["tool"] == "delete_tracks_bulk"
    assert entries[-1]["error_code"] == "POST_ZONE_PERSIST_FAILED"
