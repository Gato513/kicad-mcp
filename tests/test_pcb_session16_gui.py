"""Tests integration_gui de sesión 16 (P1 — visibilidad del cobre) contra KiCad real.

Requieren ``KICAD_MCP_GUI_TEST=1``, ``KICAD_MCP_PROJECT`` apuntando al proyecto
abierto y el PCB Editor cargado (ver ``docs/pruebas-gui.md``). Todas las
mutaciones se REVIERTEN en teardown (``try/finally``).

- T1 ``get_tracks(net=)``: los ids listados coinciden con los KIID reales de
  kipy (``raw.get_tracks()``/``get_vias()``).
- T2 ``get_tracks(bbox=)``: recorte correcto contra tracks reales.
- T3 ``delete_track(id=)``/``delete_via(id=)``: borrado exacto vía id
  resuelto por ``get_tracks``.
- T4 Desambiguación por coordenadas → ``data.candidates`` con ids → delete
  por id del candidato correcto.
- T5 ``add_track(from_pad=, end_x_mm=, end_y_mm=)``: segmento pad→punto, DRC
  no empeora.
- T6 ``TRACK_ID_STALE``: id vencido tras mutar el board entre list y delete.
- T7 Escenario integrado F-13: net "roto" (segmento borrado) → ``get_tracks``
  para ver el hueco → ``add_track`` pad→punto lo repara → DRC no empeora. Sin
  tocar el ``.kicad_pcb`` por fuera de las tools.
"""

from __future__ import annotations

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


def _pick_net(bridge: IpcBridge, board) -> str | None:  # type: ignore[no-untyped-def]
    for n in bridge.list_net_names(board):
        if n and n.strip():
            return n
    return None


def _pick_pad(bridge: IpcBridge, board, refs: list[str]) -> tuple[str, str] | None:  # type: ignore[no-untyped-def]
    """``(ref, pad_number)`` del primer pad numerado que encuentre, o ``None``."""
    for ref in refs:
        detail = bridge.get_component_detail(board, ref)
        for pad in detail.pads:
            if pad.number:
                return ref, pad.number
    return None


# --- T1/T2: get_tracks contra board real --------------------------------------


@pytest.mark.integration_gui
async def test_get_tracks_ids_match_kipy_kiids() -> None:
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")
    net = _pick_net(bridge, board)
    if net is None:
        pytest.skip("board sin nets con nombre")

    ctx = bridge.read_board_context(board)
    bbox = ctx.bbox
    sx = round(float(bbox.min_x) + 3.0, 3)
    sy = round(float(bbox.min_y) + 3.0, 3)
    ex = round(sx + 2.0, 3)

    raw = board.raw
    created_kiid: str | None = None
    mcp = _server()
    try:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            before = {str(t.id.value) for t in raw.get_tracks()}
            add = await client.call_tool(
                "add_track",
                {"net": net, "start_x_mm": sx, "start_y_mm": sy, "end_x_mm": ex, "end_y_mm": sy},
            )
            assert not add.isError, _text(add)
            new_ids = {str(t.id.value) for t in raw.get_tracks()} - before
            assert len(new_ids) == 1
            created_kiid = next(iter(new_ids))

            listed = await client.call_tool("get_tracks", {"net": net})
            assert not listed.isError, _text(listed)
            text = _text(listed)
            assert created_kiid in text, "el id del track creado debe aparecer en get_tracks"
    finally:
        if created_kiid is not None:
            IpcBridge().remove_by_kiid(board, created_kiid)


@pytest.mark.integration_gui
async def test_get_tracks_bbox_crops_against_real_tracks() -> None:
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")
    net = _pick_net(bridge, board)
    if net is None:
        pytest.skip("board sin nets con nombre")

    ctx = bridge.read_board_context(board)
    bbox = ctx.bbox
    inside_x = round(float(bbox.min_x) + 3.0, 3)
    inside_y = round(float(bbox.min_y) + 3.0, 3)
    # Segundo track lejos, fuera del bbox angosto que vamos a pedir.
    outside_x = round(float(bbox.max_x) - 3.0, 3)
    outside_y = round(float(bbox.max_y) - 3.0, 3)

    raw = board.raw
    created: list[str] = []
    mcp = _server()
    try:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            before = {str(t.id.value) for t in raw.get_tracks()}
            for sx, sy in ((inside_x, inside_y), (outside_x, outside_y)):
                add = await client.call_tool(
                    "add_track",
                    {
                        "net": net,
                        "start_x_mm": sx,
                        "start_y_mm": sy,
                        "end_x_mm": round(sx + 1.0, 3),
                        "end_y_mm": sy,
                    },
                )
                assert not add.isError, _text(add)
            new_ids = {str(t.id.value) for t in raw.get_tracks()} - before
            assert len(new_ids) == 2
            created = list(new_ids)

            crop = await client.call_tool(
                "get_tracks",
                {
                    "bbox": [
                        inside_x - 0.5,
                        inside_y - 0.5,
                        inside_x + 1.5,
                        inside_y + 0.5,
                    ]
                },
            )
            assert not crop.isError, _text(crop)
            text = _text(crop)
            n_inside = sum(1 for k in created if k in text)
            assert n_inside == 1, f"esperaba exactamente 1 de 2 tracks en el bbox; vi {n_inside}"
    finally:
        for kiid in created:
            IpcBridge().remove_by_kiid(board, kiid)


# --- T3/T4: borrado por id + desambiguación con candidates ------------------


@pytest.mark.integration_gui
async def test_delete_track_by_id_round_trip() -> None:
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")
    net = _pick_net(bridge, board)
    if net is None:
        pytest.skip("board sin nets con nombre")

    ctx = bridge.read_board_context(board)
    bbox = ctx.bbox
    sx = round(float(bbox.min_x) + 4.0, 3)
    sy = round(float(bbox.min_y) + 4.0, 3)
    ex = round(sx + 2.0, 3)

    raw = board.raw
    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        before = {str(t.id.value) for t in raw.get_tracks()}
        add = await client.call_tool(
            "add_track",
            {"net": net, "start_x_mm": sx, "start_y_mm": sy, "end_x_mm": ex, "end_y_mm": sy},
        )
        assert not add.isError, _text(add)
        new_ids = {str(t.id.value) for t in raw.get_tracks()} - before
        assert len(new_ids) == 1
        created_kiid = next(iter(new_ids))

        listed = await client.call_tool("get_tracks", {"net": net})
        assert not listed.isError, _text(listed)
        assert created_kiid in _text(listed)

        dele = await client.call_tool("delete_track", {"id": created_kiid})
        assert not dele.isError, _text(dele)

    after_ids = {str(t.id.value) for t in raw.get_tracks()}
    assert created_kiid not in after_ids, "el track borrado por id sigue en el board"


@pytest.mark.integration_gui
async def test_delete_track_ambiguity_candidates_resolve_by_id() -> None:
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")
    net = _pick_net(bridge, board)
    if net is None:
        pytest.skip("board sin nets con nombre")

    ctx = bridge.read_board_context(board)
    bbox = ctx.bbox
    x0 = round(float(bbox.min_x) + 5.0, 3)
    y0 = round(float(bbox.min_y) + 5.0, 3)

    raw = board.raw
    created: list[str] = []
    mcp = _server()
    try:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            before = {str(t.id.value) for t in raw.get_tracks()}
            # Dos tracks paralelos a 0.1 mm — ambiguos para la tolerancia de
            # 0.5 mm del matching geométrico (D-11.2).
            for dy in (0.0, 0.1):
                add = await client.call_tool(
                    "add_track",
                    {
                        "net": net,
                        "start_x_mm": x0,
                        "start_y_mm": round(y0 + dy, 3),
                        "end_x_mm": round(x0 + 2.0, 3),
                        "end_y_mm": round(y0 + dy, 3),
                    },
                )
                assert not add.isError, _text(add)
            new_ids = {str(t.id.value) for t in raw.get_tracks()} - before
            assert len(new_ids) == 2
            created = list(new_ids)

            ambiguous = await client.call_tool(
                "delete_track",
                {"net": net, "near_x_mm": round(x0 + 1.0, 3), "near_y_mm": round(y0 + 0.05, 3)},
            )
            assert ambiguous.isError
            text = _text(ambiguous)
            assert "data:" in text, "data.candidates debe llegar embebido en el mensaje"
            assert all(kiid in text for kiid in created)

            # Resuelve por id: borra SOLO el primero, el otro sobrevive.
            target = created[0]
            dele = await client.call_tool("delete_track", {"id": target})
            assert not dele.isError, _text(dele)
            after_ids = {str(t.id.value) for t in raw.get_tracks()}
            assert target not in after_ids
            assert created[1] in after_ids
            created = [created[1]]
    finally:
        for kiid in created:
            IpcBridge().remove_by_kiid(board, kiid)


# --- T5: add_track pad -> punto (endpoints mixtos, D-16.3) -------------------


@pytest.mark.integration_gui
async def test_add_track_pad_to_point_does_not_worsen_drc() -> None:
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")
    ctx = bridge.read_board_context(board)
    picked = _pick_pad(bridge, board, list(ctx.refs))
    if picked is None:
        pytest.skip("board sin pads numerados")
    ref, pad_number = picked
    detail = bridge.get_component_detail(board, ref)
    pad = next(p for p in detail.pads if p.number == pad_number)
    net = pad.net_name
    if not net:
        pytest.skip("el pad elegido no tiene net asignado")

    target_x = round(float(pad.x_mm) + 2.0, 3)
    target_y = round(float(pad.y_mm), 3)

    raw = board.raw
    created_kiid: str | None = None
    mcp = _server()
    try:
        from kicad_mcp.bridge.rules import run_drc

        pre_report = run_drc(_pcb_path())
        pre_err = sum(1 for v in pre_report.violations if v.severity == "error")

        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            before = {str(t.id.value) for t in raw.get_tracks()}
            add = await client.call_tool(
                "add_track",
                {
                    "net": net,
                    "from_pad": f"{ref}.{pad_number}",
                    "end_x_mm": target_x,
                    "end_y_mm": target_y,
                },
            )
            assert not add.isError, _text(add)
            new_ids = {str(t.id.value) for t in raw.get_tracks()} - before
            assert len(new_ids) == 1
            created_kiid = next(iter(new_ids))

            save = await client.call_tool("save_board", {})
            assert not save.isError, _text(save)

        post_report = run_drc(_pcb_path())
        post_err = sum(1 for v in post_report.violations if v.severity == "error")
        assert post_err <= pre_err, f"DRC empeoró: {pre_err} -> {post_err}"
    finally:
        if created_kiid is not None:
            b2 = IpcBridge().get_open_board()
            if b2 is not None:
                IpcBridge().remove_by_kiid(b2, created_kiid)
                IpcBridge().save_board(b2)


# --- T6: TRACK_ID_STALE -------------------------------------------------------


@pytest.mark.integration_gui
async def test_delete_track_id_stale_after_external_removal() -> None:
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")
    net = _pick_net(bridge, board)
    if net is None:
        pytest.skip("board sin nets con nombre")

    ctx = bridge.read_board_context(board)
    bbox = ctx.bbox
    sx = round(float(bbox.min_x) + 6.0, 3)
    sy = round(float(bbox.min_y) + 6.0, 3)

    raw = board.raw
    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        before = {str(t.id.value) for t in raw.get_tracks()}
        add = await client.call_tool(
            "add_track",
            {
                "net": net,
                "start_x_mm": sx,
                "start_y_mm": sy,
                "end_x_mm": round(sx + 1.5, 3),
                "end_y_mm": sy,
            },
        )
        assert not add.isError, _text(add)
        new_ids = {str(t.id.value) for t in raw.get_tracks()} - before
        created_kiid = next(iter(new_ids))

        listed = await client.call_tool("get_tracks", {"net": net})
        assert not listed.isError, _text(listed)
        assert created_kiid in _text(listed)

        # Mutación externa (fuera de la tool): borra el track directo por kipy,
        # simulando que el board cambió entre el list y el delete.
        bridge.remove_by_kiid(board, created_kiid)

        result = await client.call_tool("delete_track", {"id": created_kiid})
    assert result.isError
    assert "TRACK_ID_STALE" in _text(result)


# --- T7: escenario integrado F-13 --------------------------------------------


@pytest.mark.integration_gui
async def test_f13_scenario_gap_visible_and_repaired_without_external_parsing() -> None:
    """Net "roto" (segmento borrado) -> get_tracks muestra el hueco ->
    add_track pad->punto lo repara -> DRC no empeora. Sin tocar el
    ``.kicad_pcb`` por fuera de las tools (criterio de cierre de la sesión)."""
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")
    ctx = bridge.read_board_context(board)
    picked = _pick_pad(bridge, board, list(ctx.refs))
    if picked is None:
        pytest.skip("board sin pads numerados")
    ref, pad_number = picked
    detail = bridge.get_component_detail(board, ref)
    pad = next(p for p in detail.pads if p.number == pad_number)
    net = pad.net_name
    if not net:
        pytest.skip("el pad elegido no tiene net asignado")

    raw = board.raw
    mcp = _server()
    seed_kiid: str | None = None
    repair_kiid: str | None = None
    try:
        from kicad_mcp.bridge.rules import run_drc

        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # 1) Sembrar un track desde el pad (simula la net "rota": un
            #    segmento que después vamos a borrar deja el hueco).
            gap_x = round(float(pad.x_mm) + 3.0, 3)
            gap_y = round(float(pad.y_mm), 3)
            before = {str(t.id.value) for t in raw.get_tracks()}
            seed = await client.call_tool(
                "add_track",
                {
                    "net": net,
                    "from_pad": f"{ref}.{pad_number}",
                    "end_x_mm": gap_x,
                    "end_y_mm": gap_y,
                },
            )
            assert not seed.isError, _text(seed)
            new_ids = {str(t.id.value) for t in raw.get_tracks()} - before
            seed_kiid = next(iter(new_ids))

            # 2) "Rompe" la net: borra el segmento sembrado por id (única vía
            #    de mutación usada: la tool, no el archivo).
            broken = await client.call_tool("delete_track", {"id": seed_kiid})
            assert not broken.isError, _text(broken)
            seed_kiid = None

            # 3) Visibilidad del hueco: get_tracks sobre el net ya no muestra
            #    cobre entre el pad y gap_x (criterio de cierre: sin parsear
            #    el .kicad_pcb con Python externo).
            gap_view = await client.call_tool("get_tracks", {"net": net})
            assert not gap_view.isError, _text(gap_view)

            pre_report = run_drc(_pcb_path())
            pre_err = sum(1 for v in pre_report.violations if v.severity == "error")

            # 4) Reparación: add_track pad->punto (D-16.3).
            repair = await client.call_tool(
                "add_track",
                {
                    "net": net,
                    "from_pad": f"{ref}.{pad_number}",
                    "end_x_mm": gap_x,
                    "end_y_mm": gap_y,
                },
            )
            assert not repair.isError, _text(repair)
            after_ids = {str(t.id.value) for t in raw.get_tracks()}
            repair_kiid = next(iter(after_ids - before))

            save = await client.call_tool("save_board", {})
            assert not save.isError, _text(save)

        post_report = run_drc(_pcb_path())
        post_err = sum(1 for v in post_report.violations if v.severity == "error")
        assert post_err <= pre_err, f"DRC empeoró tras la reparación: {pre_err} -> {post_err}"
    finally:
        if repair_kiid is not None:
            b2 = IpcBridge().get_open_board()
            if b2 is not None:
                IpcBridge().remove_by_kiid(b2, repair_kiid)
                IpcBridge().save_board(b2)
        elif seed_kiid is not None:
            b2 = IpcBridge().get_open_board()
            if b2 is not None:
                IpcBridge().remove_by_kiid(b2, seed_kiid)
                IpcBridge().save_board(b2)
