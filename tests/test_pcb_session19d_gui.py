"""Tests integration_gui de sesión 19d contra KiCad real.

``NET_ASSIGNMENT_MISMATCH`` (``add_via``/``add_track``) y ``delete_tracks_bulk``.

Requieren ``KICAD_MCP_GUI_TEST=1`` y ``KICAD_MCP_PROJECT`` apuntando al proyecto
abierto con el PCB Editor cargado (ver ``docs/pruebas-gui.md``). Todas las
mutaciones se REVIERTEN en teardown (``try/finally``).

Reproduce en vivo el hallazgo de 19c (Bloque 1, H2, para ``add_via``) y de
19d.0 (mismo comportamiento confirmado para ``add_track``): KiCad reasigna un
track/via recién creado al net del cobre físico que pisa/cruza, sin relación
con el net pedido por el caller. Antes de esta sesión la tool reportaba éxito
con el net pedido pese a la reasignación silenciosa (divergencia real,
detectada por 19c pero no corregida por timebox). Ahora ``add_via``/
``add_track`` verifican el net real post-creación contra lo pedido y, en
mismatch, revierten la creación y lanzan ``NET_ASSIGNMENT_MISMATCH`` — estos
tests confirman ambas mitades (detección + revert) contra un board real.

**Nota de diseño (19d, verificado en vivo):** la reasignación de net de una
VIA requiere que el cobre ajeno esté indexado en el grafo de conectividad de
KiCad — un segmento flotante ad-hoc (dos puntos vacíos sin pad) NO alcanza
para que una vía lo herede, aunque SÍ alcanza para que otro TRACK que lo cruce
sea reasignado (asimetría real, confirmada experimentalmente). Por eso el
cobre "ajeno" de T1/T2 se ancla a un pad real (stub desde un pad con net
conocido) — igual que el segmento real de /MOSI que usó 19c Bloque 1.

- T1 ``add_via``: via sobre un stub de cobre anclado a un pad de un net ajeno
  → ``NET_ASSIGNMENT_MISMATCH``, sin via nueva persistente en el board.
- T2 ``add_track``: track que cruza ese mismo stub → mismo error, sin track
  nueva persistente.
- T3 Caso feliz: ``add_via``/``add_track`` en zona vacía preservan el net
  pedido tal cual (sin falso positivo del fix).
- T4 ``delete_tracks_bulk``: borra TODO el cobre de un net real en un solo
  round-trip (Bloque 3 de 19c necesitó 266 llamadas individuales
  delete_track/delete_via por falta de esta tool) — ``dry_run`` no muta,
  el borrado real deja 0 ítems del net.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.ipc import IpcBridge


def _guard() -> None:
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/pruebas-gui.md")
    if not os.environ.get("KICAD_MCP_PROJECT"):
        pytest.skip("KICAD_MCP_PROJECT no definida; apuntar al proyecto abierto")


def _pcb_path() -> Path:
    root = Path(os.environ["KICAD_MCP_PROJECT"])
    pcbs = list(root.glob("*.kicad_pcb"))
    pro = list(root.glob("*.kicad_pro"))
    if pro:
        cand = pro[0].with_suffix(".kicad_pcb")
        if cand.is_file():
            return cand.resolve()
    return pcbs[0].resolve()


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _server():  # type: ignore[no-untyped-def]
    from kicad_mcp.server import create_server

    return create_server()


def _pick_two_distinct_nets(bridge: IpcBridge, board) -> tuple[str, str] | None:  # type: ignore[no-untyped-def]
    """Dos nets con nombre, distintos entre sí — necesarios para forzar el
    cruce de cobre ajeno sin hardcodear nombres de net del fixture."""
    named = [n for n in bridge.list_net_names(board) if n and n.strip()]
    for i, a in enumerate(named):
        for b in named[i + 1 :]:
            if a != b:
                return a, b
    return None


_STUB_LENGTH_MM = 2.0
_STUB_DIRECTIONS = (
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (1, 1),
    (1, -1),
    (-1, 1),
    (-1, -1),
)


async def _seed_pad_anchored_stub(  # type: ignore[no-untyped-def]
    client, bridge: IpcBridge, board, refs: list[str], net: str
) -> tuple[str, float, float, float, float]:
    """Crea, vía la tool ``add_track``, un stub de 2mm desde el primer pad de
    ``net`` que encuentre en un rumbo libre de colisión con otros pads.

    Necesario para T1/T2: la reasignación de net de una vía sólo dispara
    sobre cobre indexado en la conectividad real de KiCad (ver nota de
    diseño del módulo) — un pad es la forma más simple de anclar el stub a
    esa conectividad. Intentos que fallan por colisión de pad
    (``INVALID_PARAMS``) no mutan el board — se descartan sin cleanup.
    Devuelve ``(kiid, start_x, start_y, end_x, end_y)``; lanza
    ``AssertionError`` si ningún pad/rumbo de ``net`` está libre (fixture
    inadecuada para este escenario).
    """
    for ref in refs:
        detail = bridge.get_component_detail(board, ref)
        for pad in detail.pads:
            if pad.net_name != net:
                continue
            px, py = float(pad.x_mm), float(pad.y_mm)
            for dx, dy in _STUB_DIRECTIONS:
                ex = round(px + dx * _STUB_LENGTH_MM, 3)
                ey = round(py + dy * _STUB_LENGTH_MM, 3)
                result = await client.call_tool(
                    "add_track",
                    {
                        "net": net,
                        "start_x_mm": px,
                        "start_y_mm": py,
                        "end_x_mm": ex,
                        "end_y_mm": ey,
                    },
                )
                if not result.isError:
                    new_kiids = [
                        line.split(" ")[1]
                        for line in (
                            await client.call_tool(
                                "get_tracks",
                                {
                                    "bbox": [
                                        min(px, ex) - 0.01,
                                        min(py, ey) - 0.01,
                                        max(px, ex) + 0.01,
                                        max(py, ey) + 0.01,
                                    ],
                                    "max_tokens": 4000,
                                },
                            )
                        )
                        .content[0]
                        .text.splitlines()
                        if line.startswith("T ")
                    ]
                    assert new_kiids, "el stub se creó pero get_tracks no lo encontró"
                    return new_kiids[-1], px, py, ex, ey
    raise AssertionError(f"ningún pad del net {net!r} tiene un rumbo de stub libre de colisión")


# --- T1: add_via sobre cobre ajeno --------------------------------------------


@pytest.mark.integration_gui
async def test_add_via_on_foreign_copper_reverts_and_raises_mismatch() -> None:
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")
    nets = _pick_two_distinct_nets(bridge, board)
    if nets is None:
        pytest.skip("board sin al menos 2 nets con nombre")
    net_a, net_b = nets
    ctx = bridge.read_board_context(board)

    raw = board.raw
    foreign_kiid: str | None = None
    try:
        mcp = _server()
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            foreign_kiid, sx, sy, ex, ey = await _seed_pad_anchored_stub(
                client, bridge, board, list(ctx.refs), net_b
            )
            mid_x = round((sx + ex) / 2, 3)
            mid_y = round((sy + ey) / 2, 3)

            vias_before = {str(v.id.value) for v in raw.get_vias()}
            result = await client.call_tool("add_via", {"x_mm": mid_x, "y_mm": mid_y, "net": net_a})
            assert result.isError, _text(result)
            assert "NET_ASSIGNMENT_MISMATCH" in _text(result)

            vias_after = {str(v.id.value) for v in raw.get_vias()}
            assert vias_after == vias_before, (
                "la vía en mismatch debió revertirse — no debe quedar ninguna nueva"
            )
    finally:
        if foreign_kiid is not None:
            bridge.remove_by_kiid(board, foreign_kiid)


# --- T2: add_track cruzando cobre ajeno ---------------------------------------


@pytest.mark.integration_gui
async def test_add_track_crossing_foreign_copper_reverts_and_raises_mismatch() -> None:
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")
    nets = _pick_two_distinct_nets(bridge, board)
    if nets is None:
        pytest.skip("board sin al menos 2 nets con nombre")
    net_a, net_b = nets
    ctx = bridge.read_board_context(board)

    raw = board.raw
    foreign_kiid: str | None = None
    try:
        mcp = _server()
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            foreign_kiid, sx, sy, ex, ey = await _seed_pad_anchored_stub(
                client, bridge, board, list(ctx.refs), net_b
            )
            mid_x = round((sx + ex) / 2, 3)
            mid_y = round((sy + ey) / 2, 3)
            # Perpendicular al stub, centrado en su punto medio — cruza el
            # stub sin importar su orientación exacta.
            perp_dx, perp_dy = -(ey - sy), (ex - sx)
            norm = max((perp_dx**2 + perp_dy**2) ** 0.5, 1e-6)
            perp_dx, perp_dy = perp_dx / norm, perp_dy / norm

            tracks_before = {str(t.id.value) for t in raw.get_tracks()}
            result = await client.call_tool(
                "add_track",
                {
                    "net": net_a,
                    "start_x_mm": round(mid_x - perp_dx, 3),
                    "start_y_mm": round(mid_y - perp_dy, 3),
                    "end_x_mm": round(mid_x + perp_dx, 3),
                    "end_y_mm": round(mid_y + perp_dy, 3),
                },
            )
            assert result.isError, _text(result)
            assert "NET_ASSIGNMENT_MISMATCH" in _text(result)

            tracks_after = {str(t.id.value) for t in raw.get_tracks()}
            assert tracks_after == tracks_before, (
                "el track en mismatch debió revertirse — no debe quedar ninguno nuevo"
            )
    finally:
        if foreign_kiid is not None:
            bridge.remove_by_kiid(board, foreign_kiid)


# --- T3: caso feliz, zona vacía — sin falso positivo --------------------------


@pytest.mark.integration_gui
async def test_add_via_and_add_track_in_empty_area_preserve_requested_net() -> None:
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")
    nets = _pick_two_distinct_nets(bridge, board)
    if nets is None:
        pytest.skip("board sin al menos 2 nets con nombre")
    net_a, _ = nets

    ctx = bridge.read_board_context(board)
    bbox = ctx.bbox
    sx = round(float(bbox.min_x) + 1.0, 3)
    sy = round(float(bbox.min_y) + 1.0, 3)
    ex = round(sx + 2.0, 3)
    vx = round(sx + 6.0, 3)
    vy = round(sy + 6.0, 3)

    raw = board.raw
    track_kiid: str | None = None
    via_kiid: str | None = None
    try:
        mcp = _server()
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            tracks_before = {str(t.id.value) for t in raw.get_tracks()}
            add_track = await client.call_tool(
                "add_track",
                {
                    "net": net_a,
                    "start_x_mm": sx,
                    "start_y_mm": sy,
                    "end_x_mm": ex,
                    "end_y_mm": sy,
                },
            )
            assert not add_track.isError, _text(add_track)
            new_tracks = {str(t.id.value) for t in raw.get_tracks()} - tracks_before
            assert len(new_tracks) == 1
            track_kiid = next(iter(new_tracks))
            created_track = next(t for t in raw.get_tracks() if str(t.id.value) == track_kiid)
            assert str(created_track.net.name) == net_a

            vias_before = {str(v.id.value) for v in raw.get_vias()}
            add_via = await client.call_tool("add_via", {"x_mm": vx, "y_mm": vy, "net": net_a})
            assert not add_via.isError, _text(add_via)
            new_vias = {str(v.id.value) for v in raw.get_vias()} - vias_before
            assert len(new_vias) == 1
            via_kiid = next(iter(new_vias))
            created_via = next(v for v in raw.get_vias() if str(v.id.value) == via_kiid)
            assert str(created_via.net.name) == net_a
    finally:
        if track_kiid is not None:
            bridge.remove_by_kiid(board, track_kiid)
        if via_kiid is not None:
            bridge.remove_by_kiid(board, via_kiid)


# --- T4: delete_tracks_bulk ----------------------------------------------------


@pytest.mark.integration_gui
async def test_delete_tracks_bulk_removes_all_copper_of_a_net() -> None:
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")
    net = next((n for n in bridge.list_net_names(board) if n and n.strip()), None)
    if net is None:
        pytest.skip("board sin nets con nombre")
    ctx = bridge.read_board_context(board)

    raw = board.raw

    def _net_tracks_and_vias() -> tuple[list[object], list[object]]:
        tracks = [t for t in raw.get_tracks() if str(t.net.name) == net]
        vias = [v for v in raw.get_vias() if str(v.net.name) == net]
        return tracks, vias

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        # Sembramos un stub propio (anclado a pad) para garantizar ≥1 ítem a
        # borrar, sin depender de que el board ya tenga cobre residual de ese
        # net (assert trivial si tracks_before ya fuera 0).
        seeded_kiid, _sx, _sy, _ex, _ey = await _seed_pad_anchored_stub(
            client, bridge, board, list(ctx.refs), net
        )
        tracks_before, vias_before = _net_tracks_and_vias()
        assert seeded_kiid in {str(t.id.value) for t in raw.get_tracks()}
        assert len(tracks_before) >= 1

        dry = await client.call_tool("delete_tracks_bulk", {"net": net, "dry_run": True})
        assert not dry.isError, _text(dry)
        dry_payload = json.loads(_text(dry))
        assert dry_payload["tracks_deleted"] == len(tracks_before)
        assert dry_payload["vias_deleted"] == len(vias_before)
        assert dry_payload["snap_id"] is None

        # dry_run no debe haber mutado nada.
        tracks_after_dry, vias_after_dry = _net_tracks_and_vias()
        assert len(tracks_after_dry) == len(tracks_before)
        assert len(vias_after_dry) == len(vias_before)

        result = await client.call_tool("delete_tracks_bulk", {"net": net})
        assert not result.isError, _text(result)
        payload = json.loads(_text(result))
        assert payload["tracks_deleted"] == len(tracks_before)
        assert payload["vias_deleted"] == len(vias_before)

    tracks_after, vias_after = _net_tracks_and_vias()
    assert tracks_after == []
    assert vias_after == []
