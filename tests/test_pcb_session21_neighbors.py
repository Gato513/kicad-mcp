"""Tests unit de sesión 21 — P1: ``get_footprint_neighbors`` (F-D3-04).

Motivación (``docs/dogfooding/dogfood3-fricciones.md`` F-04): 35 min / 5
intentos rutéando a mano cerca de J1 por no poder ver "qué hay alrededor"
de un footprint sin reconstruir el mapa a mano con ``get_tracks(bbox=)``
iterativo. Cubre: vecinos en cada dirección (pads/tracks/vías), holes
propios y ajenos, borde cercano, y presupuesto de tokens.

No depende de tolerancias exactas de fill de zona (eso lo cubre 21.1).
Estrategia idéntica al resto de la sesión: fake bridge en memoria, sin
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
    BoardHandle,
    ComponentDetail,
    CopperItem,
    IpcBridge,
    Mm,
    PadDetail,
    PadHole,
)
from kicad_mcp.gates import g1
from kicad_mcp.tools.pcb import register as register_pcb


class _FakeBridge(IpcBridge):
    """Bridge en memoria con soporte de footprints/cobre/holes/borde."""

    def __init__(
        self,
        *,
        refs: list[str] | None = None,
        details: dict[str, ComponentDetail] | None = None,
        copper: list[CopperItem] | None = None,
        holes: list[PadHole] | None = None,
        board_bbox: BBoxMm | None = None,
        outline: str = "44.0x44.0mm",
    ) -> None:
        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._refs = list(refs or [])
        self._details = details or {}
        self._copper = list(copper or [])
        self._holes = list(holes or [])
        self._board_bbox = board_bbox or BBoxMm(Mm(0), Mm(0), Mm(200), Mm(100))
        self._outline = outline

    def get_open_board(self) -> BoardHandle | None:
        return BoardHandle(_raw=object())

    def list_footprint_refs(self, board: BoardHandle) -> list[str]:  # type: ignore[override]
        return list(self._refs)

    def get_component_detail(  # type: ignore[override]
        self, board: BoardHandle, ref: str
    ) -> ComponentDetail:
        from kicad_mcp.errors import ErrorCode, KicadMcpError

        if ref not in self._details:
            raise KicadMcpError(
                code=ErrorCode.COMPONENT_NOT_FOUND,
                message=f"Footprint {ref} no está en el board.",
                hint="fake: ref no registrada.",
            )
        return self._details[ref]

    def list_all_copper(self, board: BoardHandle) -> tuple[CopperItem, ...]:  # type: ignore[override]
        return tuple(self._copper)

    def list_pad_holes(self, board: BoardHandle) -> tuple[PadHole, ...]:  # type: ignore[override]
        return tuple(self._holes)

    def board_outline(self, board: BoardHandle) -> tuple[BBoxMm, str]:  # type: ignore[override]
        return (self._board_bbox, self._outline)


def _detail(
    ref: str,
    x: float,
    y: float,
    *,
    bbox: tuple[float, float, float, float],
    pads: tuple[PadDetail, ...] = (),
) -> ComponentDetail:
    return ComponentDetail(
        ref=ref,
        value="V",
        x_mm=Mm(x),
        y_mm=Mm(y),
        rotation_deg=0.0,
        bbox_min_x=Mm(bbox[0]),
        bbox_min_y=Mm(bbox[1]),
        bbox_max_x=Mm(bbox[2]),
        bbox_max_y=Mm(bbox[3]),
        bbox_source="courtyard",
        pads=pads,
    )


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "proj.kicad_sch").write_text("(kicad_sch)")
    (project / "proj.kicad_pcb").write_text("(kicad_pcb)")
    return project


def _make_server(bridge: IpcBridge) -> FastMCP:
    mcp = FastMCP(name="test-s21-neighbors", instructions="test")
    register_pcb(mcp, ipc_bridge=bridge)
    return mcp


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _json(result: CallToolResult) -> dict[str, Any]:
    import json

    return json.loads(_text(result))


@pytest.fixture(autouse=True)
def _reset_g1() -> Any:
    g1.reset_session_state()
    yield
    g1.reset_session_state()


@pytest.mark.unit
async def test_get_footprint_neighbors_finds_pad_in_radius(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Un pad de otro footprint dentro del radio aparece con dist_mm correcto;
    fuera del radio, no."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    target = _detail("J1", 190.0, 48.0, bbox=(186.5, 46.0, 193.5, 50.0))
    near = _detail(
        "R3",
        196.0,
        48.0,
        bbox=(195.0, 47.0, 197.0, 49.0),
        pads=(
            PadDetail(
                number="1",
                net_name="+3V3",
                x_mm=Mm(196.0),
                y_mm=Mm(48.0),
                w_mm=Mm(1.0),
                h_mm=Mm(1.0),
                layer="F.Cu",
            ),
        ),
    )
    far = _detail(
        "R9",
        250.0,
        48.0,
        bbox=(249.0, 47.0, 251.0, 49.0),
        pads=(
            PadDetail(
                number="1",
                net_name="GND",
                x_mm=Mm(250.0),
                y_mm=Mm(48.0),
                w_mm=Mm(1.0),
                h_mm=Mm(1.0),
                layer="F.Cu",
            ),
        ),
    )
    bridge = _FakeBridge(
        refs=["J1", "R3", "R9"],
        details={"J1": target, "R3": near, "R9": far},
        board_bbox=BBoxMm(Mm(0), Mm(0), Mm(260), Mm(100)),
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_footprint_neighbors", {"ref": "J1", "radius_mm": 5.0})

    assert not result.isError
    payload = _json(result)
    assert payload["ref"] == "J1"
    pad_refs = {p["ref"] for p in payload["neighbors"]["pads"]}
    assert "R3" in pad_refs
    assert "R9" not in pad_refs
    r3 = next(p for p in payload["neighbors"]["pads"] if p["ref"] == "R3")
    assert r3["net"] == "+3V3"
    assert r3["dist_mm"] == pytest.approx(2.5, abs=0.01)  # pad en (196.0,48.0), bbox max_x=193.5


@pytest.mark.unit
async def test_get_footprint_neighbors_holes_own_and_foreign(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Los 3 agujeros NPTH PROPIOS de J1 aparecen (mismo mecanismo que el D3:
    conector con agujeros mecánicos propios), y también un hole AJENO
    (PTH de otro net) dentro del radio."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    target = _detail("J1", 190.0, 48.0, bbox=(186.5, 46.0, 193.5, 50.0))
    holes = [
        PadHole(
            ref="J1",
            pad_number="",
            net_name=None,
            x_mm=Mm(187.5),
            y_mm=Mm(48.0),
            diameter_mm=Mm(0.99),
            kind="npth",
        ),
        PadHole(
            ref="J1",
            pad_number="",
            net_name=None,
            x_mm=Mm(192.5),
            y_mm=Mm(47.0),
            diameter_mm=Mm(0.99),
            kind="npth",
        ),
        PadHole(
            ref="J1",
            pad_number="",
            net_name=None,
            x_mm=Mm(192.5),
            y_mm=Mm(49.0),
            diameter_mm=Mm(0.99),
            kind="npth",
        ),
        PadHole(
            ref="ANT1",
            pad_number="1",
            net_name="Net-(ANT1-A)",
            x_mm=Mm(191.0),
            y_mm=Mm(48.0),
            diameter_mm=Mm(2.0),
            kind="pth",
        ),
        PadHole(
            ref="FAR1",
            pad_number="1",
            net_name="GND",
            x_mm=Mm(250.0),
            y_mm=Mm(48.0),
            diameter_mm=Mm(1.0),
            kind="pth",
        ),
    ]
    bridge = _FakeBridge(
        refs=["J1"],
        details={"J1": target},
        holes=holes,
        board_bbox=BBoxMm(Mm(0), Mm(0), Mm(260), Mm(100)),
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_footprint_neighbors", {"ref": "J1", "radius_mm": 5.0})

    assert not result.isError
    payload = _json(result)
    hole_list = payload["neighbors"]["holes"]
    assert len(hole_list) == 4  # 3 NPTH propios + 1 PTH ajeno; FAR1 queda afuera
    npth = [h for h in hole_list if h["kind"] == "npth"]
    assert len(npth) == 3
    assert all(h["belongs_to"] == "J1" for h in npth)
    pth = [h for h in hole_list if h["kind"] == "pth"]
    assert len(pth) == 1
    assert pth[0]["belongs_to"] == "ANT1"


@pytest.mark.unit
async def test_get_footprint_neighbors_closest_edge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """El footprint cerca del borde derecho del board reporta closest_edge
    correcto con la distancia esperada."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    target = _detail("J1", 193.0, 48.0, bbox=(186.5, 46.0, 193.5, 50.0))
    bridge = _FakeBridge(
        refs=["J1"],
        details={"J1": target},
        board_bbox=BBoxMm(Mm(150.0), Mm(28.0), Mm(194.0), Mm(72.0)),
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_footprint_neighbors", {"ref": "J1", "radius_mm": 5.0})

    assert not result.isError
    payload = _json(result)
    edge = payload["neighbors"]["edge"]
    assert edge is not None
    assert edge["closest_edge"] == "right"
    assert edge["dist_mm"] == pytest.approx(0.5, abs=0.01)  # 194.0 - 193.5


@pytest.mark.unit
async def test_get_footprint_neighbors_edge_none_if_far(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Si el borde más cercano está más lejos que radius_mm, el campo edge
    es None (no se reporta)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    target = _detail("U1", 100.0, 50.0, bbox=(95.0, 45.0, 105.0, 55.0))
    bridge = _FakeBridge(
        refs=["U1"],
        details={"U1": target},
        board_bbox=BBoxMm(Mm(0.0), Mm(0.0), Mm(200.0), Mm(100.0)),
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_footprint_neighbors", {"ref": "U1", "radius_mm": 5.0})

    assert not result.isError
    payload = _json(result)
    assert payload["neighbors"]["edge"] is None


@pytest.mark.unit
async def test_get_footprint_neighbors_component_not_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(refs=[], details={})
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_footprint_neighbors", {"ref": "GHOST"})

    assert result.isError
    assert "COMPONENT_NOT_FOUND" in _text(result)


@pytest.mark.unit
async def test_get_footprint_neighbors_budget_impossible_with_large_radius(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Un radio grande sobre un board con muchos vecinos supera el
    presupuesto de tokens -> CONTEXT_BUDGET_IMPOSSIBLE con hint de achicar
    radius (mismo patrón que get_tracks)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    target = _detail("U1", 100.0, 50.0, bbox=(95.0, 45.0, 105.0, 55.0))
    refs = ["U1"]
    details = {"U1": target}
    for i in range(200):
        r = f"R{i}"
        refs.append(r)
        details[r] = _detail(
            r,
            100.0 + i * 0.01,
            50.0,
            bbox=(99.9 + i * 0.01, 49.9, 100.1 + i * 0.01, 50.1),
            pads=(
                PadDetail(
                    number="1",
                    net_name=f"net_{i}",
                    x_mm=Mm(100.0 + i * 0.01),
                    y_mm=Mm(50.0),
                    w_mm=Mm(0.5),
                    h_mm=Mm(0.5),
                    layer="F.Cu",
                ),
            ),
        )
    bridge = _FakeBridge(
        refs=refs, details=details, board_bbox=BBoxMm(Mm(0.0), Mm(0.0), Mm(300.0), Mm(100.0))
    )
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "get_footprint_neighbors", {"ref": "U1", "radius_mm": 1000.0, "max_tokens": 50}
        )

    assert result.isError
    assert "CONTEXT_BUDGET_IMPOSSIBLE" in _text(result)
