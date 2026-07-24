"""Test integration_gui de sesión 24 — D-23.2 (ADR-0012): gate del merge del
fix de F-D4-02.

Reproduce, contra KiCad 10.0.4 real (kicad-cli + kipy reales, Freerouting
real), el escenario EXACTO del Bloque 1 de la investigación de sesión 23
(``docs/investigacion/23-fd4-02.md``): partiendo del fixture
``despertador-routed`` (footprints + plano GND filleado + 4 keepouts fijos —
ANT1 + 3x J1 NPTH), se borra TODO el cobre existente (``delete_tracks_bulk``)
para simular un ``route_board`` "desde cero", y se verifica que el fix
(Opción X — reordenar medición DRC + persistir) cierra el bug real:
``route_board`` ya NO sobreestima ``hole_clearance``/``clearance`` contra la
zona GND, y el disco queda sincronizado con lo reportado SIN que el llamador
tenga que invocar ``save_board()`` aparte.

El bbox de ``delete_tracks_bulk`` se deriva en runtime de
``bridge.list_zones()`` (unión de bboxes + margen) — NO se hardcodean las
coordenadas del fixture checked-in, porque la copia de trabajo en
``KICAD_MCP_PROJECT`` puede vivir en un origen absoluto distinto (confirmado:
el fixture crudo tiene el board en (150,28)-(194,72), la copia de trabajo
real usada en sesión 24 lo tiene en (100,50)-(144,94) — mismo tamaño
44x44mm, origen distinto).

Requiere Freerouting real (Java + jar) — mismo requisito que
``test_zones_e2e_gui.py`` / ``test_pcb_session21_route_board_drc_gui.py``.
Corre DIRECTO sobre el proyecto que ``KICAD_MCP_PROJECT`` apunta. **Muta de
forma permanente** el board (borra el cobre y rutea de nuevo) — no es
descartable; requiere restaurar el fixture antes de la siguiente corrida si
se necesita un estado limpio para otra cosa.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.autoroute import _JAR_ENV, _SYSTEM_PYTHON_DEFAULT
from kicad_mcp.bridge.ipc import IpcBridge
from kicad_mcp.bridge.rules import run_drc
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store
from kicad_mcp.tools.world import _resolve_root_pcb

_ROUTE_TIMEOUT_S = 900
# Margen alrededor de la unión de bboxes de zonas (mm) — generoso para
# capturar cualquier track/vía cerca del borde del board sin depender de
# coordenadas hardcodeadas del fixture.
_BBOX_MARGIN_MM = 5.0
# Keepouts fijos esperados (ANT1 + 3x J1 NPTH, D-D3.1/sesión 20) + margen
# generoso para no ser flakey si el pipeline agrega alguno por-vía a futuro
# (D-23.3/R16, deuda técnica NO tocada en esta sesión).
_KEEPOUTS_MIN = 4
_KEEPOUTS_MAX = 8


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _json(result: CallToolResult) -> dict[str, Any]:
    return json.loads(_text(result))


def _guard() -> None:
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/pruebas-gui.md")
    if not os.environ.get("KICAD_MCP_PROJECT"):
        pytest.skip(
            "KICAD_MCP_PROJECT no seteada — debe apuntar al proyecto YA "
            "ABIERTO en el PCB Editor de KiCad"
        )
    jar = os.environ.get(_JAR_ENV)
    if not jar or not Path(jar).is_file():
        pytest.skip(f"{_JAR_ENV} no seteada o inexistente (requisito de ruteo)")
    if shutil.which("java") is None:
        pytest.skip("java no está en PATH (requisito de ruteo)")
    if not Path(_SYSTEM_PYTHON_DEFAULT).exists():
        pytest.skip(f"{_SYSTEM_PYTHON_DEFAULT} ausente (pcbnew del sistema)")


def _preflight_same_board_open(pcb_path: Path) -> IpcBridge:
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay PCB Editor abierto en KiCad")
    open_path = bridge.get_open_board_path(board)
    if open_path is None or open_path.resolve() != pcb_path.resolve():
        pytest.skip(
            f"KICAD_MCP_PROJECT ({pcb_path}) no coincide con el board abierto "
            f"en KiCad ({open_path}) — abrí ESE proyecto en KiCad antes de "
            "correr este test."
        )
    return bridge


def _server():  # type: ignore[no-untyped-def]
    from kicad_mcp.server import create_server

    return create_server()


@pytest.mark.integration_gui_slow
async def test_route_board_persists_fix_matches_independent_drc() -> None:
    """D-23.2 (ADR-0012): tras ``route_board``, disco == memoria ==
    ``err_post`` reportado — gate del merge del fix de F-D4-02 (sesión 24)."""
    _guard()
    pcb_path = _resolve_root_pcb()
    bridge = _preflight_same_board_open(pcb_path)
    g1.reset_session_state()
    get_default_store().reset()

    board = bridge.get_open_board()
    assert board is not None  # _preflight_same_board_open ya lo garantizó
    zones_before = bridge.list_zones(board)
    copper_zones = [z for z in zones_before if z.kind == "copper"]
    assert copper_zones, (
        "el fixture despertador-routed debería tener el plano GND ya "
        "presente — ¿se restauró correctamente KICAD_MCP_PROJECT?"
    )

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        # --- Setup determinista (Opción b, docs/sesiones/24-reporte.md):
        # parte del fixture YA abierto (footprints + plano GND filleado + 4
        # keepouts fijos) y borra TODO el cobre existente (tracks+vías) para
        # reproducir el estado "recién ruteado desde cero" del Bloque 1 de
        # sesión 23 — bbox derivado de la unión de zonas + margen, no
        # hardcodeado.
        min_x = min(z.bbox_min_x for z in zones_before) - _BBOX_MARGIN_MM
        min_y = min(z.bbox_min_y for z in zones_before) - _BBOX_MARGIN_MM
        max_x = max(z.bbox_max_x for z in zones_before) + _BBOX_MARGIN_MM
        max_y = max(z.bbox_max_y for z in zones_before) + _BBOX_MARGIN_MM

        delete_result = await client.call_tool(
            "delete_tracks_bulk",
            {"bbox": [min_x, min_y, max_x, max_y], "include_vias": True},
        )
        assert not delete_result.isError, _text(delete_result)
        save_result = await client.call_tool("save_board", {})
        assert not save_result.isError, _text(save_result)
        mtime_before_route = pcb_path.stat().st_mtime

        # --- route_board real (Freerouting headless real, no mockeado).
        route_result = await client.call_tool("route_board", {"timeout_s": _ROUTE_TIMEOUT_S})
        assert not route_result.isError, _text(route_result)
        payload = _json(route_result)
        drc = payload["drc"]

        # 1. Gate: 0 hole_clearance en el reporte — el síntoma original de
        # F-D4-02 (16 hole_clearance + 30 clearance en la reproducción de
        # Dogfooding 4).
        assert drc["por_tipo"].get("hole_clearance", 0) == 0, (
            f"drc.por_tipo trae hole_clearance espurio post-fix: {drc['por_tipo']}"
        )

        # Ground truth INDEPENDIENTE post-route (bridge directo, no la tool) —
        # se mide UNA sola vez y se reutiliza para las assertions 2 y 3, para
        # no correr kicad-cli dos veces sobre el mismo instante de disco.
        post_report_independiente = run_drc(pcb_path)

        # 2. Gate: ninguna violación clearance contra la zona GND sobrevive
        # (otras clearance por causas distintas — p. ej. courtyards del
        # proceso — SÍ pueden seguir existiendo; el patrón eliminado es
        # específicamente "net ajeno vs Zone GND").
        gnd_clearance = [
            v
            for v in post_report_independiente.violations
            if v.severity == "error"
            and v.rule == "clearance"
            and any(it.desc and "Zone" in it.desc and "GND" in it.desc for it in v.items)
        ]
        assert gnd_clearance == [], (
            f"clearance vs Zone GND sobrevivió al fix (D-23.2 no cerrado): {gnd_clearance}"
        )

        # 3. Gate — CORAZÓN del contrato D-23.2: un run_drc() independiente
        # inmediato, SIN llamar save_board() manual, coincide con lo que
        # route_board reportó. Si esto falla, el fix no cerró F-D4-02: el
        # disco seguiría desincronizado del reporte.
        post_err_independiente = sum(
            1 for v in post_report_independiente.violations if v.severity == "error"
        )
        por_tipo_independiente: dict[str, int] = {}
        for v in post_report_independiente.violations:
            if v.severity == "error":
                por_tipo_independiente[v.rule] = por_tipo_independiente.get(v.rule, 0) + 1
        assert drc["err_post"] == post_err_independiente, (
            f"route_board.drc.err_post ({drc['err_post']}) no coincide con el "
            f"run_drc() independiente inmediato ({post_err_independiente}) — "
            "el disco no está sincronizado con lo reportado (F-D4-02 no cerrado)."
        )
        assert drc["por_tipo"] == por_tipo_independiente, (
            f"drc.por_tipo ({drc['por_tipo']}) no coincide con el desglose "
            f"independiente ({por_tipo_independiente})."
        )

        # 4. Gate: keepouts fijos, sin proliferación descontrolada (umbral
        # generoso — D-23.3/R16 sigue sin generar keepouts por-vía en este
        # pipeline, no se tocó en esta sesión).
        zones_after = bridge.list_zones(board)
        keepouts_after = sum(1 for z in zones_after if z.kind == "keepout")
        assert _KEEPOUTS_MIN <= keepouts_after <= _KEEPOUTS_MAX, (
            f"conteo de keepouts fuera de rango esperado: {keepouts_after}"
        )

        # 5. Opcional (evidencia adicional, no gate): el mtime del
        # .kicad_pcb cambió entre el save post-delete y el post-route — el
        # save_board() de D-23.2 sí corrió.
        mtime_after_route = pcb_path.stat().st_mtime
        assert mtime_after_route > mtime_before_route, (
            "el mtime del .kicad_pcb no cambió tras route_board — "
            "¿save_board() post-refill no corrió?"
        )
