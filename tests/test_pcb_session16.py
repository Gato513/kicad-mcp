"""Tests unit de sesión 16 (P1 — visibilidad del cobre).

- ``get_tracks`` (D-16.1): filtro obligatorio, net/bbox/layer, ids estables,
  presupuesto de tokens.
- ``delete_track``/``delete_via`` por ``id`` (D-16.2): resolución directa por
  KIID, ``TRACK_ID_STALE`` si el id no resuelve, y el bug de ``data.candidates``
  ausente en la desambiguación por coordenadas (ahora sí llega, ver errors.py).
- ``add_track`` con endpoints mixtos pad+coordenada (D-16.3).
- Validación de colisiones contra pads de otro net, roundrect incluido (D-16.4).

Estrategia idéntica al resto de la sesión 11/14: fake bridge en memoria, sin
socket ni kipy.
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
    ComponentDetail,
    CopperItem,
    FootprintData,
    FootprintPadData,
    IpcBridge,
    Mm,
    PadDetail,
    PadGeom,
)
from kicad_mcp.gates import g1
from kicad_mcp.tools.pcb import register as register_pcb


class _FakeBridge(IpcBridge):
    """Bridge en memoria con soporte de cobre board-wide + pads (D-16.x)."""

    def __init__(
        self,
        *,
        refs: list[str] | None = None,
        nets: list[str] | None = None,
        bbox: BBoxMm | None = None,
        copper: dict[str, list[CopperItem]] | None = None,
        pads: list[PadGeom] | None = None,
        details: dict[str, ComponentDetail] | None = None,
    ) -> None:
        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._refs = list(refs or ["U1"])
        self._nets = list(nets or ["GND"])
        self._bbox = bbox or BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100))
        self._copper = copper or {}
        self._pads = list(pads or [])
        self._details = details or {}
        self.removed_kiids: list[str] = []
        self.tracks: list[dict[str, Any]] = []

    def get_open_board(self) -> BoardHandle | None:
        return BoardHandle(_raw=object())

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

    def get_copper_by_kiid(  # type: ignore[override]
        self, board: BoardHandle, kiid: str
    ) -> CopperItem | None:
        for items in self._copper.values():
            for it in items:
                if it.kiid == kiid:
                    return it
        return None

    def list_all_pads(self, board: BoardHandle) -> tuple[PadGeom, ...]:  # type: ignore[override]
        return tuple(self._pads)

    def remove_by_kiid(self, board: BoardHandle, kiid: str) -> bool:  # type: ignore[override]
        self.removed_kiids.append(kiid)
        found = False
        for net, items in list(self._copper.items()):
            kept = [it for it in items if it.kiid != kiid]
            if len(kept) != len(items):
                found = True
            self._copper[net] = kept
        return found

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


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "proj.kicad_sch").write_text("(kicad_sch)")
    (project / "proj.kicad_pcb").write_text("(kicad_pcb)")
    return project


def _make_server(bridge: IpcBridge) -> FastMCP:
    mcp = FastMCP(name="test-s16", instructions="test")
    register_pcb(mcp, ipc_bridge=bridge)
    return mcp


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _track(
    kiid: str,
    net: str,
    sx: float,
    sy: float,
    ex: float,
    ey: float,
    layer: str = "F.Cu",
    width: float = 0.25,
) -> CopperItem:
    return CopperItem(
        kind="track",
        kiid=kiid,
        net_name=net,
        layer=layer,
        start_x_mm=Mm(sx),
        start_y_mm=Mm(sy),
        end_x_mm=Mm(ex),
        end_y_mm=Mm(ey),
        mid_x_mm=None,
        mid_y_mm=None,
        width_mm=Mm(width),
    )


def _via(
    kiid: str, net: str, x: float, y: float, size: float = 0.8, drill: float = 0.4
) -> CopperItem:
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
        size_mm=Mm(size),
        drill_mm=Mm(drill),
        via_layers=("F.Cu", "B.Cu"),
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
        pads=tuple(
            PadDetail(
                number=num,
                net_name=net,
                x_mm=Mm(x),
                y_mm=Mm(y),
                w_mm=Mm(1.0),
                h_mm=Mm(1.0),
                layer="F.Cu",
            )
            for (num, net, x, y) in pads
        ),
    )


@pytest.fixture(autouse=True)
def _reset_g1() -> Any:
    g1.reset_session_state()
    yield
    g1.reset_session_state()


# --- get_tracks ----------------------------------------------------------


@pytest.mark.unit
async def test_get_tracks_requires_a_filter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge()
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_tracks", {})
    assert result.isError
    assert "INVALID_PARAMS" in _text(result)


@pytest.mark.unit
async def test_get_tracks_by_net_lists_segments_and_vias_with_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """(a) get_tracks(net=) lista todos los segmentos+vías de ese net con ids."""
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
        result = await client.call_tool("get_tracks", {"net": "GND"})
    assert not result.isError, _text(result)
    text = _text(result)
    assert "T1" in text and "GND" in text
    assert "V1" in text
    assert "T9" not in text  # otro net, no debe aparecer
    assert text.startswith("TRACKS|v1|net:GND|1s|1v")


@pytest.mark.unit
async def test_get_tracks_net_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(nets=["GND", "3V3"])
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_tracks", {"net": "3v3"})
    assert result.isError
    text = _text(result)
    assert "NET_NOT_FOUND" in text
    assert "3V3" in text


@pytest.mark.unit
async def test_get_tracks_bbox_crops_crossing_segment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """(b) get_tracks(bbox=) recorta: el segmento que CRUZA el bbox aparece
    (sin tener ningún endpoint adentro); el de afuera no."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {
        "GND": [
            _track("CROSS", "GND", -5.0, 5.0, 25.0, 5.0),  # cruza x=[0,20] horizontal
            _track("OUTSIDE", "GND", 100.0, 100.0, 110.0, 100.0),
        ]
    }
    bridge = _FakeBridge(nets=["GND"], copper=copper)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_tracks", {"bbox": [0.0, 0.0, 20.0, 20.0]})
    assert not result.isError, _text(result)
    text = _text(result)
    assert "CROSS" in text
    assert "OUTSIDE" not in text


@pytest.mark.unit
async def test_get_tracks_layer_filter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {
        "GND": [
            _track("FRONT", "GND", 0.0, 0.0, 10.0, 0.0, layer="F.Cu"),
            _track("BACK", "GND", 0.0, 0.0, 10.0, 0.0, layer="B.Cu"),
        ]
    }
    bridge = _FakeBridge(nets=["GND"], copper=copper)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_tracks", {"layer": "F.Cu"})
    assert not result.isError, _text(result)
    text = _text(result)
    assert "FRONT" in text
    assert "BACK" not in text


@pytest.mark.unit
async def test_get_tracks_context_budget_impossible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {"GND": [_track(f"T{i}", "GND", float(i), 0.0, float(i) + 1, 0.0) for i in range(50)]}
    bridge = _FakeBridge(nets=["GND"], copper=copper)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_tracks", {"net": "GND", "max_tokens": 10})
    assert result.isError
    assert "CONTEXT_BUDGET_IMPOSSIBLE" in _text(result)


# --- delete_track / delete_via por id -------------------------------------


@pytest.mark.unit
async def test_delete_track_by_id_removes_exact_segment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """(c) delete por id borra exactamente ese segmento."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {
        "GND": [
            _track("KEEP", "GND", 0.0, 0.0, 10.0, 0.0),
            _track("DROP", "GND", 0.0, 1.0, 10.0, 1.0),
        ]
    }
    bridge = _FakeBridge(nets=["GND"], copper=copper)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_track", {"id": "DROP"})
    assert not result.isError, _text(result)
    assert bridge.removed_kiids == ["DROP"]
    remaining = [it.kiid for it in bridge._copper["GND"]]
    assert remaining == ["KEEP"]


@pytest.mark.unit
async def test_delete_track_ambiguity_carries_candidates_with_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """(d) desambiguación por coordenadas -> error CON candidates+ids (bug
    corregido: antes ``data`` se perdía en la frontera MCP) -> delete por id
    del candidate correcto."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {
        "GND": [
            _track("A", "GND", 10.0, 10.0, 20.0, 10.0),
            _track("B", "GND", 10.0, 10.1, 20.0, 10.1),  # a 0.1 mm de A
        ]
    }
    bridge = _FakeBridge(nets=["GND"], copper=copper)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        ambiguous = await client.call_tool(
            "delete_track", {"net": "GND", "near_x_mm": 15.0, "near_y_mm": 10.05}
        )
        assert ambiguous.isError
        text = _text(ambiguous)
        assert "INVALID_PARAMS" in text
        assert "candidatos" in text
        # El bug de sesión 15: ``data.candidates`` se prometía en el hint y
        # nunca llegaba. Ahora viaja embebido como JSON parseable.
        assert "data:" in text
        data_json = text.split("data: ", 1)[1]
        data = json.loads(data_json)
        candidate_ids = [c["id"] for c in data["candidates"]]
        assert set(candidate_ids) == {"A", "B"}
        assert bridge.removed_kiids == []

        target_id = next(c["id"] for c in data["candidates"] if c["net"] == "GND")
        resolved = await client.call_tool("delete_track", {"id": target_id})
    assert not resolved.isError, _text(resolved)
    assert bridge.removed_kiids == [target_id]


@pytest.mark.unit
async def test_delete_track_id_stale_when_board_mutated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """(g) id de un get_tracks anterior, board mutado entre medio -> error correcto."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {"GND": [_track("T1", "GND", 0.0, 0.0, 10.0, 0.0)]}
    bridge = _FakeBridge(nets=["GND"], copper=copper)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        listed = await client.call_tool("get_tracks", {"net": "GND"})
        assert not listed.isError, _text(listed)
        assert "T1" in _text(listed)

        # El board muta entre el list y el delete (p. ej. otra herramienta
        # borró/movió el track): el id ya no resuelve.
        bridge._copper["GND"] = []

        result = await client.call_tool("delete_track", {"id": "T1"})
    assert result.isError
    text = _text(result)
    assert "TRACK_ID_STALE" in text
    assert bridge.removed_kiids == []


@pytest.mark.unit
async def test_delete_track_by_id_wrong_kind_is_track_id_stale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Un id de VIA pasado a ``delete_track`` no debe borrar nada (kind mismatch)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    copper = {"GND": [_via("V1", "GND", 10.0, 10.0)]}
    bridge = _FakeBridge(nets=["GND"], copper=copper)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("delete_track", {"id": "V1"})
    assert result.isError
    assert "TRACK_ID_STALE" in _text(result)
    assert bridge.removed_kiids == []


@pytest.mark.unit
async def test_delete_track_mixing_id_and_coords_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(nets=["GND"])
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "delete_track", {"id": "T1", "net": "GND", "near_x_mm": 1.0, "near_y_mm": 1.0}
        )
    assert result.isError
    assert "INVALID_PARAMS" in _text(result)


# --- add_track: endpoints mixtos pad + coordenada (D-16.3) ----------------


@pytest.mark.unit
async def test_add_track_from_pad_to_point(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """(e) add_track(from_pad=, to=[x,y]) crea el segmento — caso de
    reparación real: desde un pad hasta un punto en el cobre."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    details = {"U1": _detail("U1", [("1", "GND", 30.0, 40.0)])}
    bridge = _FakeBridge(refs=["U1"], nets=["GND"], details=details)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_track",
            {"net": "GND", "from_pad": "U1.1", "end_x_mm": 50.0, "end_y_mm": 40.0},
        )
    assert not result.isError, _text(result)
    assert bridge.tracks == [
        {
            "net": "GND",
            "start": [30.0, 40.0],
            "end": [50.0, 40.0],
            "width_mm": 0.25,
            "layer": "F.Cu",
        }
    ]


@pytest.mark.unit
async def test_add_track_point_to_pad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """El caso simétrico: punto -> pad."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    details = {"U1": _detail("U1", [("1", "GND", 30.0, 40.0)])}
    bridge = _FakeBridge(refs=["U1"], nets=["GND"], details=details)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_track",
            {"net": "GND", "start_x_mm": 10.0, "start_y_mm": 40.0, "to_pad": "U1.1"},
        )
    assert not result.isError, _text(result)
    assert bridge.tracks == [
        {
            "net": "GND",
            "start": [10.0, 40.0],
            "end": [30.0, 40.0],
            "width_mm": 0.25,
            "layer": "F.Cu",
        }
    ]


@pytest.mark.unit
async def test_add_track_same_endpoint_mixing_still_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Mezclar pad Y coords en el MISMO extremo sigue siendo error (D-16.3
    sólo relaja la exclusión GLOBAL, no la de un único endpoint)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    details = {"U1": _detail("U1", [("1", "GND", 30.0, 40.0)])}
    bridge = _FakeBridge(refs=["U1"], nets=["GND"], details=details)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_track",
            {
                "net": "GND",
                "from_pad": "U1.1",
                "start_x_mm": 1.0,
                "start_y_mm": 2.0,
                "end_x_mm": 5.0,
                "end_y_mm": 5.0,
            },
        )
    assert result.isError
    assert "INVALID_PARAMS" in _text(result)
    assert bridge.tracks == []


# --- add_track: colisión contra pads de otro net (D-16.4) -----------------


@pytest.mark.unit
async def test_add_track_rejects_collision_with_other_net_pad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    # Pad rectangular 1x1mm de 3V3 centrado en (5,0): el track GND horizontal
    # por y=0 lo atraviesa de lleno.
    pads = [
        PadGeom(
            net_name="3V3",
            layer="F.Cu",
            x_mm=Mm(5.0),
            y_mm=Mm(0.0),
            w_mm=Mm(1.0),
            h_mm=Mm(1.0),
            rotation_deg=0.0,
            corner_ratio=0.0,
        )
    ]
    bridge = _FakeBridge(nets=["GND", "3V3"], pads=pads)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_track",
            {"net": "GND", "start_x_mm": 0.0, "start_y_mm": 0.0, "end_x_mm": 10.0, "end_y_mm": 0.0},
        )
    assert result.isError
    text = _text(result)
    assert "INVALID_PARAMS" in text
    assert "3V3" in text
    assert bridge.tracks == []


@pytest.mark.unit
async def test_add_track_ignores_same_net_pad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Un pad del MISMO net que el track no debe disparar colisión (se espera
    que el track lo toque — son los pads que conecta)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    pads = [
        PadGeom(
            net_name="GND",
            layer="F.Cu",
            x_mm=Mm(5.0),
            y_mm=Mm(0.0),
            w_mm=Mm(1.0),
            h_mm=Mm(1.0),
            rotation_deg=0.0,
            corner_ratio=0.0,
        )
    ]
    bridge = _FakeBridge(nets=["GND"], pads=pads)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_track",
            {"net": "GND", "start_x_mm": 0.0, "start_y_mm": 0.0, "end_x_mm": 10.0, "end_y_mm": 0.0},
        )
    assert not result.isError, _text(result)
    assert len(bridge.tracks) == 1


@pytest.mark.unit
async def test_add_track_ignores_pad_on_other_layer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Un pad SMD de otro net en B.Cu no bloquea un track en F.Cu."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    pads = [
        PadGeom(
            net_name="3V3",
            layer="B.Cu",
            x_mm=Mm(5.0),
            y_mm=Mm(0.0),
            w_mm=Mm(1.0),
            h_mm=Mm(1.0),
            rotation_deg=0.0,
            corner_ratio=0.0,
        )
    ]
    bridge = _FakeBridge(nets=["GND", "3V3"], pads=pads)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_track",
            {
                "net": "GND",
                "layer": "F.Cu",
                "start_x_mm": 0.0,
                "start_y_mm": 0.0,
                "end_x_mm": 10.0,
                "end_y_mm": 0.0,
            },
        )
    assert not result.isError, _text(result)


@pytest.mark.unit
async def test_add_track_roundrect_corner_not_falsely_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """La fricción original (dogfooding F-13): un checker que trata un pad
    roundrect como rectángulo completo sobre-rechaza cerca de la esquina
    recortada (2 iteraciones DRC perdidas). Con el radio modelado, un track
    que sólo pasa por la cuña recortada de un roundrect (dentro de la bbox
    cuadrada del pad, fuera de la forma real) debe pasar.

    Pad roundrect 2x2mm, ratio 0.5 (máximo -> radio 1.0mm = círculo exacto
    inscripto en el cuadrado 2x2 centrado en origen). Segmento diagonal corto
    cerca de la esquina (1,1): a 0.329mm del círculo real (sin colisión con
    clearance 0.25mm) pero a -0.06mm de un rectángulo completo (colisión
    profunda si el pad se modelara como rect sin redondeo — verificado con
    la misma fórmula SDF en r=0, ver sesión 16 T4).
    """
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    pads = [
        PadGeom(
            net_name="3V3",
            layer="F.Cu",
            x_mm=Mm(0.0),
            y_mm=Mm(0.0),
            w_mm=Mm(2.0),
            h_mm=Mm(2.0),
            rotation_deg=0.0,
            corner_ratio=0.5,
        )
    ]
    bridge = _FakeBridge(nets=["GND", "3V3"], pads=pads)
    mcp = _make_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_track",
            {
                "net": "GND",
                "width_mm": 0.1,
                "start_x_mm": 0.9,
                "start_y_mm": 0.98,
                "end_x_mm": 0.98,
                "end_y_mm": 0.9,
            },
        )
    assert not result.isError, _text(result)
