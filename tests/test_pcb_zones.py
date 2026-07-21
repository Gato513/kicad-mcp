"""Tests unit de sesión 19 (P4 — zonas: plano GND + keepouts).

Cubre las 5 tools nuevas con un fake bridge en memoria (sin socket ni kipy),
mismo patrón que ``test_pcb_session16.py``/``test_reload_board.py``:

- ``add_zone``/``add_keepout_zone`` (P4.1/P4.2): geometría bbox/polygon,
  ``INVALID_ZONE_GEOMETRY`` (ambos/ninguno, <3/>20 vértices, auto-intersección),
  ``NET_NOT_FOUND``, JSON estructurado de retorno.
- ``get_zones`` (P4.1): filtro obligatorio, layer/net/kind, formato compacto.
- ``fill_zones`` (P4.3): idempotente, ``ZONE_ID_STALE`` con ``zone_id`` inválido.
- ``delete_zone`` (P4.4): borrado por id, ``ZONE_ID_STALE``.
- ``route_board`` (P4.3): campo ``zones`` nuevo del contrato JSON.
"""

from __future__ import annotations

import json
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
    FootprintData,
    FootprintPadData,
    IpcBridge,
    Mm,
    ZoneItem,
)
from kicad_mcp.gates import g1
from kicad_mcp.tools.pcb import register as register_pcb


class _FakeBridge(IpcBridge):
    """Bridge en memoria con soporte de zonas (P4, sesión 19)."""

    def __init__(
        self,
        *,
        nets: list[str] | None = None,
        zones: list[ZoneItem] | None = None,
    ) -> None:
        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._nets = list(nets or ["GND", "3V3"])
        self._zones: list[ZoneItem] = list(zones or [])
        self.removed_kiids: list[str] = []
        self.added_zones: list[dict[str, Any]] = []
        self.added_keepouts: list[dict[str, Any]] = []
        self.refill_calls = 0
        self._next_kiid = 1000

    def get_open_board(self) -> BoardHandle | None:
        return BoardHandle(_raw=object())

    def list_net_names(self, board: BoardHandle) -> list[str]:  # type: ignore[override]
        return list(self._nets)

    def read_board_context(self, board: BoardHandle) -> BoardContext:  # type: ignore[override]
        fps = (
            FootprintData(
                ref="U1",
                value="V",
                x_mm=Mm(0.0),
                y_mm=Mm(0.0),
                pads=(FootprintPadData(number="1", net_name="GND"),),
                kiid="kiid-U1",
            ),
        )
        return BoardContext(
            refs=("U1",), bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)), footprints=fps
        )

    def list_zones(self, board: BoardHandle) -> tuple[ZoneItem, ...]:  # type: ignore[override]
        return tuple(self._zones)

    def get_zone_by_kiid(self, board: BoardHandle, kiid: str) -> ZoneItem | None:  # type: ignore[override]
        for z in self._zones:
            if z.kiid == kiid:
                return z
        return None

    def add_zone(  # type: ignore[override]
        self,
        board: BoardHandle,
        *,
        net: str,
        layer: str,
        vertices_mm: tuple[tuple[float, float], ...],
        priority: int = 0,
        fill: bool = True,
    ) -> tuple[str, bool, float]:
        kiid = f"zone-{self._next_kiid}"
        self._next_kiid += 1
        self.added_zones.append(
            {
                "net": net,
                "layer": layer,
                "vertices": vertices_mm,
                "priority": priority,
                "fill": fill,
            }
        )
        xs = [v[0] for v in vertices_mm]
        ys = [v[1] for v in vertices_mm]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        item = ZoneItem(
            kind="copper",
            kiid=kiid,
            net_name=net,
            layer=layer,
            bbox_min_x=Mm(min(xs)),
            bbox_min_y=Mm(min(ys)),
            bbox_max_x=Mm(max(xs)),
            bbox_max_y=Mm(max(ys)),
            area_mm2=area,
            filled=fill,
            vertices_mm=tuple((Mm(x), Mm(y)) for x, y in vertices_mm),
        )
        self._zones.append(item)
        return kiid, fill, area

    def add_keepout_zone(  # type: ignore[override]
        self,
        board: BoardHandle,
        *,
        layer: str,
        vertices_mm: tuple[tuple[float, float], ...],
        no_tracks: bool,
        no_vias: bool,
        no_pours: bool,
        no_footprints: bool,
    ) -> tuple[str, float]:
        kiid = f"keepout-{self._next_kiid}"
        self._next_kiid += 1
        self.added_keepouts.append(
            {
                "layer": layer,
                "vertices": vertices_mm,
                "no_tracks": no_tracks,
                "no_vias": no_vias,
                "no_pours": no_pours,
                "no_footprints": no_footprints,
            }
        )
        xs = [v[0] for v in vertices_mm]
        ys = [v[1] for v in vertices_mm]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        item = ZoneItem(
            kind="keepout",
            kiid=kiid,
            net_name=None,
            layer=layer,
            bbox_min_x=Mm(min(xs)),
            bbox_min_y=Mm(min(ys)),
            bbox_max_x=Mm(max(xs)),
            bbox_max_y=Mm(max(ys)),
            area_mm2=area,
            filled=False,
            vertices_mm=tuple((Mm(x), Mm(y)) for x, y in vertices_mm),
        )
        self._zones.append(item)
        return kiid, area

    def refill_zones(self, board: BoardHandle) -> int:  # type: ignore[override]
        self.refill_calls += 1
        return sum(1 for z in self._zones if z.kind == "copper")

    def remove_by_kiid(self, board: BoardHandle, kiid: str) -> bool:  # type: ignore[override]
        self.removed_kiids.append(kiid)
        before = len(self._zones)
        self._zones = [z for z in self._zones if z.kiid != kiid]
        return len(self._zones) != before


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "proj.kicad_sch").write_text("(kicad_sch)")
    (project / "proj.kicad_pcb").write_text("(kicad_pcb)")
    return project


def _make_server(bridge: IpcBridge) -> FastMCP:
    mcp = FastMCP(name="test-s19", instructions="test")
    register_pcb(mcp, ipc_bridge=bridge)
    return mcp


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _json(result: CallToolResult) -> dict[str, Any]:
    return json.loads(_text(result))


def _zone(
    kiid: str,
    kind: str,
    net: str | None,
    layer: str,
    vertices: list[tuple[float, float]],
    filled: bool = True,
) -> ZoneItem:
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    area = (max(xs) - min(xs)) * (max(ys) - min(ys))
    return ZoneItem(
        kind=kind,
        kiid=kiid,
        net_name=net,
        layer=layer,
        bbox_min_x=Mm(min(xs)),
        bbox_min_y=Mm(min(ys)),
        bbox_max_x=Mm(max(xs)),
        bbox_max_y=Mm(max(ys)),
        area_mm2=area,
        filled=filled,
        vertices_mm=tuple((Mm(x), Mm(y)) for x, y in vertices),
    )


@pytest.fixture(autouse=True)
def _reset_g1() -> Any:
    g1.reset_session_state()
    yield
    g1.reset_session_state()


# --- add_zone --------------------------------------------------------------


@pytest.mark.unit
async def test_add_zone_bbox_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge()
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_zone", {"net": "GND", "layer": "B.Cu", "bbox": [0.0, 0.0, 50.0, 40.0]}
        )
    assert not result.isError, _text(result)
    payload = _json(result)
    assert payload["zone_id"] == "zone-1000"
    assert payload["filled"] is True
    assert payload["area_mm2"] == pytest.approx(2000.0)
    assert isinstance(payload["snap_id"], int)
    assert bridge.added_zones[0]["net"] == "GND"
    assert bridge.added_zones[0]["layer"] == "B.Cu"

    audit = project / ".kicad-mcp" / "audit.jsonl"
    entries = [json.loads(x) for x in audit.read_text().splitlines()]
    accepted = [e for e in entries if e["tool"] == "add_zone" and "result" in e]
    assert len(accepted) == 1
    assert accepted[0]["result"]["zone_id"] == "zone-1000"


@pytest.mark.unit
async def test_add_zone_polygon_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge()
    mcp = _make_server(bridge)
    triangle = [[0.0, 0.0], [10.0, 0.0], [5.0, 10.0]]
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_zone", {"net": "GND", "layer": "F.Cu", "polygon": triangle, "fill": False}
        )
    assert not result.isError, _text(result)
    payload = _json(result)
    assert payload["filled"] is False
    assert bridge.added_zones[0]["fill"] is False


@pytest.mark.unit
async def test_add_zone_net_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(nets=["GND", "3V3"])
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_zone", {"net": "3v3", "layer": "B.Cu", "bbox": [0.0, 0.0, 10.0, 10.0]}
        )
    assert result.isError
    text = _text(result)
    assert "NET_NOT_FOUND" in text
    assert "3V3" in text
    assert not bridge.added_zones


@pytest.mark.unit
@pytest.mark.parametrize(
    "params",
    [
        {"net": "GND", "layer": "B.Cu"},  # ni bbox ni polygon
        {
            "net": "GND",
            "layer": "B.Cu",
            "bbox": [0.0, 0.0, 10.0, 10.0],
            "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]],
        },  # ambos
        {"net": "GND", "layer": "B.Cu", "bbox": [0.0, 0.0, 5.0]},  # bbox con 3 valores
        {"net": "GND", "layer": "B.Cu", "polygon": [[0.0, 0.0], [1.0, 1.0]]},  # <3 vértices
        {
            "net": "GND",
            "layer": "B.Cu",
            "polygon": [[float(i), 0.0] for i in range(21)],
        },  # >20 vértices
    ],
)
async def test_add_zone_invalid_geometry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, params: dict[str, Any]
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge()
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("add_zone", params)
    assert result.isError
    assert "INVALID_ZONE_GEOMETRY" in _text(result)
    assert not bridge.added_zones


@pytest.mark.unit
async def test_add_zone_self_intersecting_polygon_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Un "bowtie" (4 vértices que se cruzan en el medio) es no-simple."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge()
    mcp = _make_server(bridge)
    bowtie = [[0.0, 0.0], [10.0, 10.0], [10.0, 0.0], [0.0, 10.0]]
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_zone", {"net": "GND", "layer": "B.Cu", "polygon": bowtie}
        )
    assert result.isError
    assert "INVALID_ZONE_GEOMETRY" in _text(result)


# --- add_keepout_zone -------------------------------------------------------


@pytest.mark.unit
async def test_add_keepout_zone_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge()
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_keepout_zone",
            {
                "layer": "F.Cu",
                "bbox": [10.0, 10.0, 20.0, 25.0],
                "no_footprints": True,
            },
        )
    assert not result.isError, _text(result)
    payload = _json(result)
    assert payload["keepout_flags"] == {
        "no_tracks": True,
        "no_vias": True,
        "no_pours": True,
        "no_footprints": True,
    }
    assert payload["area_mm2"] == pytest.approx(150.0)
    assert bridge.added_keepouts[0]["layer"] == "F.Cu"


@pytest.mark.unit
async def test_add_keepout_zone_invalid_geometry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge()
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("add_keepout_zone", {"layer": "all"})
    assert result.isError
    assert "INVALID_ZONE_GEOMETRY" in _text(result)


# --- get_zones ---------------------------------------------------------------


@pytest.mark.unit
async def test_get_zones_requires_a_filter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge()
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_zones", {})
    assert result.isError
    assert "INVALID_PARAMS" in _text(result)


@pytest.mark.unit
async def test_get_zones_by_layer_lists_copper_and_keepout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    zones = [
        _zone("Z1", "copper", "GND", "B.Cu", [(0.0, 0.0), (50.0, 0.0), (50.0, 40.0), (0.0, 40.0)]),
        _zone(
            "Z2", "keepout", None, "B.Cu", [(10.0, 10.0), (20.0, 10.0), (20.0, 20.0), (10.0, 20.0)]
        ),
        _zone("Z3", "copper", "3V3", "F.Cu", [(0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0)]),
    ]
    bridge = _FakeBridge(zones=zones)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_zones", {"layer": "B.Cu"})
    assert not result.isError, _text(result)
    text = _text(result)
    assert text.startswith("ZONES|v1|layer:B.Cu|2")
    assert "Z1" in text and "copper" in text and "GND" in text
    assert "Z2" in text and "keepout" in text
    assert "Z3" not in text  # otra capa, no debe aparecer
    assert "bbox=" in text  # rectángulos alineados a ejes


@pytest.mark.unit
async def test_get_zones_by_kind_filters(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    zones = [
        _zone("Z1", "copper", "GND", "B.Cu", [(0.0, 0.0), (50.0, 0.0), (50.0, 40.0), (0.0, 40.0)]),
        _zone(
            "Z2", "keepout", None, "B.Cu", [(10.0, 10.0), (20.0, 10.0), (20.0, 20.0), (10.0, 20.0)]
        ),
    ]
    bridge = _FakeBridge(zones=zones)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_zones", {"kind": "keepout"})
    assert not result.isError, _text(result)
    text = _text(result)
    assert "Z2" in text
    assert "Z1" not in text


@pytest.mark.unit
async def test_get_zones_invalid_kind(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge()
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_zones", {"kind": "bogus"})
    assert result.isError
    assert "INVALID_PARAMS" in _text(result)


@pytest.mark.unit
async def test_get_zones_polygon_shows_vertex_count_not_bbox(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    circle_verts = [(15.0 * (1 + 0.1 * i), 15.0) for i in range(12)]  # no forman un rect
    zones = [_zone("Z9", "keepout", None, "F.Cu", circle_verts)]
    bridge = _FakeBridge(zones=zones)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_zones", {"kind": "keepout"})
    assert not result.isError, _text(result)
    text = _text(result)
    assert "verts=12" in text
    assert "bbox=" not in text


# --- fill_zones --------------------------------------------------------------


@pytest.mark.unit
async def test_fill_zones_refills_all_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    zones = [
        _zone("Z1", "copper", "GND", "B.Cu", [(0.0, 0.0), (50.0, 0.0), (50.0, 40.0), (0.0, 40.0)]),
        _zone(
            "Z2", "keepout", None, "B.Cu", [(10.0, 10.0), (20.0, 10.0), (20.0, 20.0), (10.0, 20.0)]
        ),
    ]
    bridge = _FakeBridge(zones=zones)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        first = await client.call_tool("fill_zones", {})
        second = await client.call_tool("fill_zones", {})
    assert not first.isError, _text(first)
    assert not second.isError, _text(second)
    payload1 = _json(first)
    payload2 = _json(second)
    assert payload1["zones_filled"] == 1  # sólo la de cobre, no la keepout
    assert payload2["zones_filled"] == 1
    assert bridge.refill_calls == 2


@pytest.mark.unit
async def test_fill_zones_stale_zone_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge()
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("fill_zones", {"zone_id": "nope"})
    assert result.isError
    assert "ZONE_ID_STALE" in _text(result)
    assert bridge.refill_calls == 0


# --- delete_zone ---------------------------------------------------------------


@pytest.mark.unit
async def test_delete_zone_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    zones = [
        _zone("Z1", "copper", "GND", "B.Cu", [(0.0, 0.0), (50.0, 0.0), (50.0, 40.0), (0.0, 40.0)])
    ]
    bridge = _FakeBridge(zones=zones)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_zone", {"id": "Z1"})
    assert not result.isError, _text(result)
    text = _text(result)
    assert text.startswith("OK delete_zone copper")
    assert bridge.removed_kiids == ["Z1"]
    assert not bridge.list_zones(BoardHandle(_raw=object()))


@pytest.mark.unit
async def test_delete_zone_stale_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge()
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_zone", {"id": "ghost"})
    assert result.isError
    assert "ZONE_ID_STALE" in _text(result)
