"""Tests integration_gui de sesión 11 contra KiCad real (D-11.1..D-11.4 + T6).

Requieren ``KICAD_MCP_GUI_TEST=1``, ``KICAD_MCP_PROJECT`` apuntando al proyecto
abierto y el PCB Editor cargado. Todas las mutaciones se REVIERTEN en teardown
(``try/finally``); el board vuelve a su estado inicial y se re-guarda a disco.

- T1 ``save_board``: mover footprint → save → el .kicad_pcb en disco CAMBIÓ
  (mtime + posición nueva parseada) → restaurar + save. Cierre literal de F-05.
- T2 ``delete_track`` / ``delete_via``: add → delete → ausencia vía kipy.
- T3 ``get_component_detail``: pads absolutos de una ref rotada contra kipy.
- T4 ``add_track`` anclado a pads: endpoints contra posiciones reales (±1 nm).
- T6 loop completo sin humano: la demostración de que F-05+F-08 murieron.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.ipc import IpcBridge, Mm, mm_to_nm


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


def _parse_fp_pos(text: str, ref: str) -> tuple[float, float]:
    """Parsea la posición ``(at x y)`` del footprint ``ref`` del .kicad_pcb.

    El ``(at ...)` propio del footprint es el primero tras ``(footprint`` y
    antes de su property "Reference". Buscamos la property de la ref, luego el
    ``(footprint`` que la contiene, y el primer ``(at`` de ese bloque.
    """
    prop = text.find(f'(property "Reference" "{ref}"')
    assert prop != -1, f"ref {ref} no está en el archivo"
    fp_start = text.rfind("(footprint", 0, prop)
    assert fp_start != -1
    m = re.search(r"\(at\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)", text[fp_start:prop])
    assert m is not None, f"no se pudo parsear (at ...) de {ref}"
    return float(m.group(1)), float(m.group(2))


def _server():  # type: ignore[no-untyped-def]
    from kicad_mcp.server import create_server

    return create_server()


# --- T1: save_board (cierre de F-05) -----------------------------------------


@pytest.mark.integration_gui
async def test_save_board_persists_to_disk() -> None:
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")

    ref = os.environ.get("KICAD_MCP_GUI_REF", "U19")
    detail0 = bridge.get_component_detail(board, ref)
    orig_x, orig_y = float(detail0.x_mm), float(detail0.y_mm)
    pcb = _pcb_path()

    # Coordenada destino distintiva (no colapsa con la original).
    target_x = round(orig_x + 3.137, 3)
    target_y = round(orig_y + 2.219, 3)

    mtime_before = pcb.stat().st_mtime_ns
    pos_before = _parse_fp_pos(pcb.read_text(), ref)

    try:
        mcp = _server()
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            mv = await client.call_tool(
                "move_footprint", {"ref": ref, "x_mm": target_x, "y_mm": target_y}
            )
            assert not mv.isError, _text(mv)
            sv = await client.call_tool("save_board", {})
            assert not sv.isError, _text(sv)
            confirm = _text(sv)
            assert confirm.startswith("OK save_board")
            assert str(pcb) in confirm, confirm  # F-02: ruta absoluta

        # El .kicad_pcb en disco CAMBIÓ: mtime + posición nueva parseada.
        assert pcb.stat().st_mtime_ns != mtime_before, "el .kicad_pcb no cambió de mtime"
        pos_after = _parse_fp_pos(pcb.read_text(), ref)
        assert pos_after != pos_before, "la posición en disco no cambió"
        assert abs(pos_after[0] - target_x) <= 0.01 and abs(pos_after[1] - target_y) <= 0.01, (
            f"posición en disco {pos_after} != target ({target_x},{target_y})"
        )
        print(
            f"\n=== T1 save_board (F-05 muerto) ===\n  confirm: {confirm}"
            f"\n  disco pos {ref}: {pos_before} -> {pos_after} (target {target_x},{target_y})"
            f"\n  mtime cambió: {mtime_before} -> {pcb.stat().st_mtime_ns}\n=== fin ==="
        )
    finally:
        # Teardown: restaurar posición original + save (disco vuelve a origen).
        bridge2 = IpcBridge()
        b2 = bridge2.get_open_board()
        if b2 is not None:
            bridge2.move_footprint(b2, ref, Mm(orig_x), Mm(orig_y))
            bridge2.save_board(b2)


# --- T2: delete_track / delete_via round-trip --------------------------------


def _pick_net(bridge: IpcBridge, board) -> str | None:  # type: ignore[no-untyped-def]
    for n in bridge.list_net_names(board):
        if n and n.strip():
            return n
    return None


@pytest.mark.integration_gui
async def test_delete_track_round_trip() -> None:
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
    # Punto libre lejos del centro para minimizar ambigüedad con cobre real.
    cx = round(float(bbox.min_x) + 3.0, 3)
    cy = round(float(bbox.min_y) + 3.0, 3)
    start = (cx, cy)
    end = (round(cx + 1.5, 3), cy)
    mid = (round(cx + 0.75, 3), cy)  # punto sobre el segmento
    raw = board.raw
    before = {str(t.id.value) for t in raw.get_tracks()}

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        add = await client.call_tool(
            "add_track",
            {
                "net": net,
                "start_x_mm": start[0],
                "start_y_mm": start[1],
                "end_x_mm": end[0],
                "end_y_mm": end[1],
            },
        )
        assert not add.isError, _text(add)
        new_ids = {str(t.id.value) for t in raw.get_tracks()} - before
        assert len(new_ids) == 1, f"esperaba 1 track nuevo; {len(new_ids)}"
        created_kiid = next(iter(new_ids))

        dele = await client.call_tool(
            "delete_track", {"net": net, "near_x_mm": mid[0], "near_y_mm": mid[1]}
        )
        assert not dele.isError, _text(dele)
        assert _text(dele).startswith("OK delete_track")

    # Ausencia verificada vía kipy directo.
    after_ids = {str(t.id.value) for t in raw.get_tracks()}
    assert created_kiid not in after_ids, "el track borrado sigue en el board"
    print(f"\n=== T2 delete_track: creó y borró {created_kiid[:8]} en net {net} ===")


@pytest.mark.integration_gui
async def test_delete_via_round_trip() -> None:
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
    vx = round(float(bbox.min_x) + 6.0, 3)
    vy = round(float(bbox.min_y) + 6.0, 3)
    raw = board.raw
    before = {str(v.id.value) for v in raw.get_vias()}

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        add = await client.call_tool("add_via", {"x_mm": vx, "y_mm": vy, "net": net})
        assert not add.isError, _text(add)
        new_ids = {str(v.id.value) for v in raw.get_vias()} - before
        assert len(new_ids) == 1
        created_kiid = next(iter(new_ids))

        dele = await client.call_tool("delete_via", {"net": net, "x_mm": vx, "y_mm": vy})
        assert not dele.isError, _text(dele)

    after_ids = {str(v.id.value) for v in raw.get_vias()}
    assert created_kiid not in after_ids, "la via borrada sigue en el board"
    print(f"\n=== T2 delete_via: creó y borró {created_kiid[:8]} en net {net} ===")


# --- T3: get_component_detail contra kipy (rotación) -------------------------


@pytest.mark.integration_gui
async def test_get_component_detail_matches_kipy() -> None:
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")

    # Elegir una ref con rotación no-cero para ejercitar el caso del bug típico.
    raw = board.raw
    rotated = None
    for fp in raw.get_footprints():
        if abs(fp.orientation.degrees) > 1 and len(fp.definition.pads) >= 2:
            rotated = str(fp.reference_field.text.value)
            break
    if rotated is None:
        pytest.skip("no hay footprint rotado con ≥2 pads")

    detail = bridge.get_component_detail(board, rotated)
    # Posiciones de pad esperadas leídas de kipy directo (ya absolutas/rotadas).
    fp = next(f for f in raw.get_footprints() if str(f.reference_field.text.value) == rotated)
    expected = {str(p.number): (p.position.x, p.position.y) for p in fp.definition.pads if p.number}
    checked = 0
    for pad in detail.pads:
        if not pad.number or pad.number not in expected:
            continue
        ex, ey = expected[pad.number]
        assert abs(int(mm_to_nm(pad.x_mm)) - ex) <= 1, f"pad {pad.number} x"
        assert abs(int(mm_to_nm(pad.y_mm)) - ey) <= 1, f"pad {pad.number} y"
        checked += 1
        if checked >= 3:
            break
    assert checked >= 1, "no se verificó ningún pad"
    print(
        f"\n=== T3 get_component_detail: {rotated} rot={detail.rotation_deg} "
        f"pads={len(detail.pads)} bbox_src={detail.bbox_source} "
        f"(verificados {checked} pads vs kipy) ==="
    )


# --- T4: add_track anclado a pads --------------------------------------------


@pytest.mark.integration_gui
async def test_add_track_between_pads_by_name() -> None:
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")

    ref = os.environ.get("KICAD_MCP_GUI_REF", "U19")
    detail = bridge.get_component_detail(board, ref)
    # Dos pads del mismo net (para un track eléctricamente coherente).
    by_net: dict[str, list] = {}
    for p in detail.pads:
        if p.number and p.net_name:
            by_net.setdefault(p.net_name, []).append(p)
    pair_net = next((n for n, ps in by_net.items() if len(ps) >= 2), None)
    if pair_net is None:
        pytest.skip(f"{ref} no tiene 2 pads en un mismo net")
    p_a, p_b = by_net[pair_net][0], by_net[pair_net][1]

    raw = board.raw
    before = {str(t.id.value) for t in raw.get_tracks()}
    created = None
    try:
        mcp = _server()
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            res = await client.call_tool(
                "add_track",
                {
                    "net": pair_net,
                    "from_pad": f"{ref}.{p_a.number}",
                    "to_pad": f"{ref}.{p_b.number}",
                },
            )
            assert not res.isError, _text(res)
        new = [t for t in raw.get_tracks() if str(t.id.value) not in before]
        assert len(new) == 1, f"esperaba 1 track; {len(new)}"
        created = new[0]
        # Endpoints contra las posiciones reales de los pads (±1 nm).
        assert abs(created.start.x - int(mm_to_nm(p_a.x_mm))) <= 1
        assert abs(created.start.y - int(mm_to_nm(p_a.y_mm))) <= 1
        assert abs(created.end.x - int(mm_to_nm(p_b.x_mm))) <= 1
        assert abs(created.end.y - int(mm_to_nm(p_b.y_mm))) <= 1
        print(
            f"\n=== T4 add_track pads: {ref}.{p_a.number}->{ref}.{p_b.number} "
            f"net={pair_net} start={created.start} end={created.end} ==="
        )
    finally:
        if created is not None:
            import contextlib

            with contextlib.suppress(Exception):
                raw.remove_items(created)


# --- T6: loop completo sin humano (F-05 + F-08 muertos) ----------------------


@pytest.mark.integration_gui
async def test_full_loop_no_human() -> None:
    """El loop place→ver→rutear→save→render→DRC→delete→save→DRC, sin humano.

    Reproduce el flujo del dogfooding que F-05 (split-brain) y F-08 (sin
    borrado) hacían imposible: cada save baja el estado vivo a disco y el
    render/DRC leen exactamente lo mutado; el delete revierte cobre.
    """
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")

    ref = os.environ.get("KICAD_MCP_GUI_REF", "U19")
    detail0 = bridge.get_component_detail(board, ref)
    orig_x, orig_y = float(detail0.x_mm), float(detail0.y_mm)
    # Un net con ≥2 pads en ref para rutear por nombre.
    by_net: dict[str, list] = {}
    for p in detail0.pads:
        if p.number and p.net_name:
            by_net.setdefault(p.net_name, []).append(p)
    pair_net = next((n for n, ps in by_net.items() if len(ps) >= 2), None)
    if pair_net is None:
        pytest.skip(f"{ref} no tiene 2 pads en un mismo net")

    raw = board.raw
    render_initial = Path(os.environ["KICAD_MCP_PROJECT"]) / "s11-loop-initial.png"
    render_after = Path(os.environ["KICAD_MCP_PROJECT"]) / "s11-loop-after.png"

    added_kiid = None
    try:
        mcp = _server()
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # 0) Render inicial (disco = estado original), md5 de referencia.
            r0 = await client.call_tool(
                "export_render", {"kind": "pcb_png", "output_path": "s11-loop-initial.png"}
            )
            assert not r0.isError, _text(r0)
            md5_initial = hashlib.md5(render_initial.read_bytes()).hexdigest()

            # 1) Contexto pcb (vista local: el board es grande, foco+radio
            #    recorta a la vecindad de la ref) + detalle de la ref.
            # Budget holgado: el board es grande (588 nets) y la sección [N]
            # es global (el foco recorta componentes, no nets). El loop sólo
            # necesita que el contexto pcb se emita; 12000 lo cubre.
            ctx = await client.call_tool(
                "get_world_context",
                {"kind": "pcb", "max_tokens": 12000, "focus_ref": ref, "radius_mm": 25.0},
            )
            assert not ctx.isError, _text(ctx)
            assert _text(ctx).startswith("PCB|"), _text(ctx)
            det = await client.call_tool("get_component_detail", {"ref": ref})
            assert not det.isError, _text(det)

            # 2) Mover la ref (place) y rutear entre dos de sus pads (route).
            mv = await client.call_tool(
                "move_footprint",
                {"ref": ref, "x_mm": round(orig_x + 1.111, 3), "y_mm": round(orig_y + 0.777, 3)},
            )
            assert not mv.isError, _text(mv)
            before_tracks = {str(t.id.value) for t in raw.get_tracks()}
            # Re-leer pads tras el move (posiciones absolutas cambiaron).
            detail1 = bridge.get_component_detail(board, ref)
            ps = [p for p in detail1.pads if p.net_name == pair_net and p.number]
            at = await client.call_tool(
                "add_track",
                {
                    "net": pair_net,
                    "from_pad": f"{ref}.{ps[0].number}",
                    "to_pad": f"{ref}.{ps[1].number}",
                },
            )
            assert not at.isError, _text(at)
            new_ids = {str(t.id.value) for t in raw.get_tracks()} - before_tracks
            assert len(new_ids) == 1, f"esperaba 1 track nuevo; {len(new_ids)}"
            added_kiid = next(iter(new_ids))

            # 3) save_board → render de nuevo → md5 DEBE cambiar (F-05 muerto).
            sv1 = await client.call_tool("save_board", {})
            assert not sv1.isError, _text(sv1)
            r1 = await client.call_tool(
                "export_render", {"kind": "pcb_png", "output_path": "s11-loop-after.png"}
            )
            assert not r1.isError, _text(r1)
            md5_after = hashlib.md5(render_after.read_bytes()).hexdigest()
            assert md5_after != md5_initial, (
                "el render NO cambió tras save_board — F-05 seguiría vivo"
            )

            # 4) DRC con el board mutado (post-save).
            drc1 = await client.call_tool("run_drc", {"min_severity": "error"})
            assert not drc1.isError, _text(drc1)
            v1 = _count_violations(_text(drc1))

            # 5) delete_track (F-08 muerto) → save → DRC (≤ violaciones previas).
            mid_x = round((float(ps[0].x_mm) + float(ps[1].x_mm)) / 2, 3)
            mid_y = round((float(ps[0].y_mm) + float(ps[1].y_mm)) / 2, 3)
            dele = await client.call_tool(
                "delete_track", {"net": pair_net, "near_x_mm": mid_x, "near_y_mm": mid_y}
            )
            assert not dele.isError, _text(dele)
            added_kiid = None  # ya borrado; el teardown no debe re-borrar
            sv2 = await client.call_tool("save_board", {})
            assert not sv2.isError, _text(sv2)
            drc2 = await client.call_tool("run_drc", {"min_severity": "error"})
            assert not drc2.isError, _text(drc2)
            v2 = _count_violations(_text(drc2))
            assert v2 <= v1, f"DRC empeoró tras borrar la track: {v1} -> {v2}"

        print(
            "\n=== T6 LOOP COMPLETO SIN HUMANO (F-05 + F-08 muertos) ==="
            f"\n  render md5: inicial={md5_initial}  post-save={md5_after}  (distintos ✓)"
            f"\n  DRC errores: post-ruteo={v1}  post-borrado={v2}  (v2<=v1 ✓)"
            f"\n  save1: {_text(sv1)}\n  save2: {_text(sv2)}"
            "\n=== fin loop ==="
        )
    finally:
        # Teardown: borrar el track si quedó, restaurar footprint, re-guardar.
        import contextlib

        if added_kiid is not None:
            with contextlib.suppress(Exception):
                bridge.remove_by_kiid(board, added_kiid)
        with contextlib.suppress(Exception):
            bridge.move_footprint(board, ref, Mm(orig_x), Mm(orig_y))
        with contextlib.suppress(Exception):
            bridge.save_board(board)
        for f in (render_initial, render_after):
            with contextlib.suppress(Exception):
                f.unlink()


def _count_violations(drc_text: str) -> int:
    """Cuenta las violaciones reportadas por run_drc (heurística robusta).

    El payload es JSON con una lista de violaciones; contamos por conteo
    declarado si está, si no por ocurrencias de ``"severity"``.
    """
    import json

    try:
        data = json.loads(drc_text)
    except json.JSONDecodeError:
        return drc_text.count('"severity"')
    if isinstance(data, dict):
        if "count" in data and isinstance(data["count"], int):
            return data["count"]
        for key in ("violations", "items", "errors"):
            if isinstance(data.get(key), list):
                return len(data[key])
    if isinstance(data, list):
        return len(data)
    return 0
