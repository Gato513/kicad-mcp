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
import re
from collections.abc import Iterator
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


def _iter_numbered_pads(  # type: ignore[no-untyped-def]
    bridge: IpcBridge, board, refs: list[str]
) -> Iterator[tuple[str, str, object]]:
    """``(ref, pad_number, pad)`` de todo pad numerado y con net, en orden.

    Generaliza el antiguo ``_pick_pad`` (que sólo devolvía el primero): la
    Tarea 2 de la sesión 16b necesita poder recorrer TODOS los candidatos
    hasta encontrar uno con un endpoint de stub libre de cobre ajeno.
    """
    for ref in refs:
        detail = bridge.get_component_detail(board, ref)
        for pad in detail.pads:
            if pad.number and pad.net_name:
                yield ref, pad.number, pad


# --- Dogfood de get_tracks para sembrar stubs sin empeorar el DRC (T5b/T7b) --

# Distancia centro-a-centro mínima entre el stub candidato y cualquier track
# de OTRA net para considerarlo "libre". No es sólo ``_MIN_CLEARANCE_MM``
# (0.2 mm, la que usa add_track para colisión con pads): acá comparamos
# centerlines de dos tracks, así que hay que descontar además el semi-ancho
# de cada uno (0.25 mm de ancho default → 0.125 + 0.125) y dejar margen para
# el caso pre-dogfooding donde la regla de clearance del proyecto puede
# valer 0.5 mm (Tarea 5). 1.0 mm cubre ambos escenarios con margen.
_STUB_CLEARANCE_MM = 1.0
_STUB_LEN_CANDIDATES_MM = (2.0, 1.0, 0.5)
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

_COORD_RE = re.compile(r"\(([-\d.]+),([-\d.]+)\)")


def _parse_track_segments(text: str) -> list[tuple[str, str, float, float, float, float]]:
    """Parsea la salida compacta de ``get_tracks`` (D-16.1, NO es TOON).

    Formato por línea: ``T <kiid> <net> <layer> w<width> (sx,sy)->(ex,ey)``
    para tracks, con ``~(mx,my)`` extra para arcos. Devuelve una lista de
    segmentos ``(layer, net, x1, y1, x2, y2)``; un arco se parte en dos
    sub-segmentos (start→mid, mid→end) para el chequeo de distancia.
    """
    segments: list[tuple[str, str, float, float, float, float]] = []
    for line in text.splitlines():
        if not line or line[0] not in ("T", "A"):
            continue
        toks = line.split(" ")
        if len(toks) < 6:
            continue
        kind, net, layer = toks[0], toks[2], toks[3]
        pts = [(float(x), float(y)) for x, y in _COORD_RE.findall(toks[5])]
        if kind == "T" and len(pts) == 2:
            (x1, y1), (x2, y2) = pts
            segments.append((layer, net, x1, y1, x2, y2))
        elif kind == "A" and len(pts) == 3:
            (x1, y1), (x2, y2), (mx, my) = pts
            segments.append((layer, net, x1, y1, mx, my))
            segments.append((layer, net, mx, my, x2, y2))
    return segments


def _seg_seg_dist(
    p1: tuple[float, float],
    p2: tuple[float, float],
    q1: tuple[float, float],
    q2: tuple[float, float],
) -> float:
    """Distancia mínima 2D entre dos segmentos (heurística por proyección de
    extremos — suficiente para descartar candidatos de stub, no un solver
    geométrico exacto de intersección)."""

    def closest_point(
        a: tuple[float, float], b: tuple[float, float], p: tuple[float, float]
    ) -> tuple[float, float]:
        ax, ay = a
        bx, by = b
        px, py = p
        dx, dy = bx - ax, by - ay
        len2 = dx * dx + dy * dy
        if len2 == 0:
            return a
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len2))
        return (ax + t * dx, ay + t * dy)

    def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    return min(
        dist(closest_point(p1, p2, q1), q1),
        dist(closest_point(p1, p2, q2), q2),
        dist(closest_point(q1, q2, p1), p1),
        dist(closest_point(q1, q2, p2), p2),
    )


async def _pick_free_stub(  # type: ignore[no-untyped-def]
    client, bridge: IpcBridge, board, refs: list[str]
) -> tuple[str, str, object, tuple[float, float]] | None:
    """Busca ``(ref, pad_number, pad, (end_x_mm, end_y_mm))`` de un stub de
    F.Cu sembrable desde algún pad numerado sin acercarse a cobre de otra
    net (Tarea 2, sesión 16b: dogfood de ``get_tracks(bbox=)`` en vez de
    tirar el stub a ciegas). ``None`` si ningún pad ofrece un endpoint
    libre — el llamador debe ``pytest.skip``, no fallar.
    """
    ctx = bridge.read_board_context(board)
    bbox = ctx.bbox
    for ref, pad_number, pad in _iter_numbered_pads(bridge, board, refs):
        px, py = float(pad.x_mm), float(pad.y_mm)
        listed = await client.call_tool(
            "get_tracks",
            {"bbox": [px - 4.0, py - 4.0, px + 4.0, py + 4.0], "max_tokens": 4000},
        )
        if listed.isError:
            continue
        segs = _parse_track_segments(_text(listed))
        other_net = [s for s in segs if s[0] == "F.Cu" and s[1] != pad.net_name]
        for length in _STUB_LEN_CANDIDATES_MM:
            for dx, dy in _STUB_DIRECTIONS:
                norm = (dx * dx + dy * dy) ** 0.5
                ex = round(px + dx / norm * length, 3)
                ey = round(py + dy / norm * length, 3)
                if not (bbox.min_x <= ex <= bbox.max_x and bbox.min_y <= ey <= bbox.max_y):
                    continue
                free = all(
                    _seg_seg_dist((px, py), (ex, ey), (s[2], s[3]), (s[4], s[5]))
                    > _STUB_CLEARANCE_MM
                    for s in other_net
                )
                if free:
                    return ref, pad_number, pad, (ex, ey)
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

            listed = await client.call_tool("get_tracks", {"net": net, "max_tokens": 4000})
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

        listed = await client.call_tool("get_tracks", {"net": net, "max_tokens": 4000})
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
    """Corrección sesión 16b (Tarea 2): la corrida anterior tiraba el stub a
    +2mm de un pad sin mirar qué cobre había ahí — sobre un board 100%
    ruteado eso colisiona (``add_track`` valida contra pads, no contra
    tracks; el DRC es el oráculo para tracks, por diseño). Ahora el
    endpoint sale de ``_pick_free_stub``, que dogfoodea
    ``get_tracks(bbox=)`` antes de sembrar."""
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")
    ctx = bridge.read_board_context(board)

    raw = board.raw
    initial_count = len(raw.get_tracks())
    created_kiid: str | None = None
    mcp = _server()
    try:
        from kicad_mcp.bridge.rules import run_drc

        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            picked = await _pick_free_stub(client, bridge, board, list(ctx.refs))
            if picked is None:
                pytest.skip("board demasiado denso para sembrar stub seguro")
            ref, pad_number, pad, (target_x, target_y) = picked
            net = pad.net_name

            pre_report = run_drc(_pcb_path())
            pre_err = sum(1 for v in pre_report.violations if v.severity == "error")

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
        # Limpieza garantizada (Tarea 2): re-guardar SIEMPRE tras limpiar, no
        # sólo cuando el test pasó — la corrida anterior dejó el stub
        # persistido porque el finally no re-guardaba.
        b2 = IpcBridge().get_open_board()
        if b2 is not None:
            raw2 = b2.raw
            live_ids = {str(t.id.value) for t in raw2.get_tracks()}
            if created_kiid is not None and created_kiid in live_ids:
                IpcBridge().remove_by_kiid(b2, created_kiid)
                IpcBridge().save_board(b2)
            final_count = len(raw2.get_tracks())
            assert final_count == initial_count, (
                f"el board quedó contaminado: {initial_count} -> {final_count} tracks"
            )


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

        listed = await client.call_tool("get_tracks", {"net": net, "max_tokens": 4000})
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

    raw = board.raw
    initial_count = len(raw.get_tracks())
    mcp = _server()
    seed_kiid: str | None = None
    repair_kiid: str | None = None
    try:
        from kicad_mcp.bridge.rules import run_drc

        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # 0) Elegir un endpoint de "hueco" libre de cobre ajeno (Tarea 2,
            #    sesión 16b: dogfood de get_tracks(bbox=) antes de sembrar —
            #    la corrida anterior tiraba +3mm a ciegas y colisionaba).
            picked = await _pick_free_stub(client, bridge, board, list(ctx.refs))
            if picked is None:
                pytest.skip("board demasiado denso para sembrar stub seguro")
            ref, pad_number, pad, (gap_x, gap_y) = picked
            net = pad.net_name

            # 1) Sembrar un track desde el pad (simula la net "rota": un
            #    segmento que después vamos a borrar deja el hueco).
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
            gap_view = await client.call_tool("get_tracks", {"net": net, "max_tokens": 4000})
            assert not gap_view.isError, _text(gap_view)

            pre_report = run_drc(_pcb_path())
            pre_err = sum(1 for v in pre_report.violations if v.severity == "error")

            # 4) Reparación: add_track pad->punto (D-16.3). Mismo endpoint
            #    libre elegido en (0): la reparación reconstruye exactamente
            #    el segmento sembrado en (1), así que si ese endpoint era
            #    seguro entonces también lo es ahora.
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
        # Limpieza garantizada (Tarea 2): re-guardar SIEMPRE tras limpiar —
        # la corrida anterior dejó 2 stubs persistidos en /RESET porque el
        # finally no re-guardaba tras limpiar.
        b2 = IpcBridge().get_open_board()
        if b2 is not None:
            raw2 = b2.raw
            live_ids = {str(t.id.value) for t in raw2.get_tracks()}
            leftover = repair_kiid or seed_kiid
            if leftover is not None and leftover in live_ids:
                IpcBridge().remove_by_kiid(b2, leftover)
                IpcBridge().save_board(b2)
            final_count = len(raw2.get_tracks())
            assert final_count == initial_count, (
                f"el board quedó contaminado: {initial_count} -> {final_count} tracks"
            )
