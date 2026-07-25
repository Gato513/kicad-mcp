"""Test integration_gui de sesión 27 — extensión de D-23.2 (ADR-0012) a
``fill_zones`` y ``add_zone(fill=True)``: gate del merge.

Reproduce, contra KiCad 10.0.4 real (kipy real, sin Freerouting — no hace
falta re-rutear para blindar el bug conceptual de refill+persistencia), el
mismo escenario que ``test_pcb_session24_route_board_persist_gui.py`` pero
para las dos tools nuevas: partiendo del fixture ``despertador-routed``
(footprints + plano GND filleado + ruteo completo, DRC 0/0 — ver
``tests/fixtures/despertador-routed/README.md``), se borra y se vuelve a
crear el plano GND con ``add_zone(fill=True)``, y por separado se re-filla
con ``fill_zones()`` — en ambos casos SIN llamar ``save_board()`` manual — y
se verifica que:

1. El mtime del ``.kicad_pcb`` cambia (evidencia de que el ``save_board()``
   incondicional de D-23.2 corrió).
2. Un ``run_drc()`` independiente inmediato refleja el estado ya arreglado
   por refill+``enforce_hole_clearance`` (0 ``hole_clearance``, sin
   ``clearance`` contra la Zone GND) — el corazón del contrato: el disco NO
   miente sobre lo que el board vivo tiene.
3. Una operación D-23.2 posterior (``fill_zones()`` de nuevo) NO dispara
   ``EXTERNAL_EDIT_DETECTED`` espurio — evidencia de que los mtimes del
   snapshot se registraron post-save (hallazgo #31 de sesión 24).
4. El conteo de keepouts ``__kicadmcp_hc__`` queda en el rango esperado
   (``enforce_hole_clearance`` corrió y es idempotente — D-23.3/R16 sin
   tocar en esta sesión).

Cada test se auto-arregla al inicio (borra cualquier zona GND de cobre
preexistente y la vuelve a crear con ``add_zone``/``fill_zones``) para ser
robusto a 2 corridas consecutivas sin depender del orden de ejecución ni de
qué corrida previa dejó el board.

Corre DIRECTO sobre el proyecto que ``KICAD_MCP_PROJECT`` apunta — el mismo
que debe estar YA ABIERTO en el PCB Editor de KiCad (mismo patrón que
``test_reload_e2e_gui.py`` / ``test_zones_e2e_gui.py``). **Muta de forma
permanente** el board (borra y recrea el plano GND, re-rellena zonas) — no
es descartable; si se necesita un estado limpio para otra cosa, restaurar el
fixture antes de la siguiente corrida.

A diferencia de ``test_pcb_session24_route_board_persist_gui.py``, este test
**no requiere Freerouting** (Java/jar/pcbnew de sistema) — el bug conceptual
que blinda es el de refill+persistencia, no el de ruteo — así que corre en
segundos, no en minutos, lo que hace trivial exigir las 2 corridas
consecutivas del gate del merge.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.ipc import IpcBridge
from kicad_mcp.bridge.rules import run_drc
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store
from kicad_mcp.tools.world import _resolve_root_pcb

# Keepouts fijos esperados (ANT1 + 3x J1 NPTH, D-D3.1/sesión 20) + margen
# generoso para no ser flakey — mismo umbral que sesión 24
# (D-23.3/R16 sigue sin generar keepouts por-vía, no se tocó en esta sesión).
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


def _gnd_clearance_violations(report: Any) -> list[Any]:
    """Violaciones ``clearance`` contra la Zone GND — mismo filtro que el
    test de sesión 24 (``test_pcb_session24_route_board_persist_gui.py``)."""
    return [
        v
        for v in report.violations
        if v.severity == "error"
        and v.rule == "clearance"
        and any(it.desc and "Zone" in it.desc and "GND" in it.desc for it in v.items)
    ]


def _hole_clearance_count(report: Any) -> int:
    return sum(1 for v in report.violations if v.severity == "error" and v.rule == "hole_clearance")


async def _gnd_board_bbox(client: Any) -> list[float]:
    """Bbox del board entero (``bbox:`` de ``get_world_context(kind='pcb')``,
    F-03) — mismo helper que ``test_zones_e2e_gui.py``, para no depender de
    coordenadas hardcodeadas ni de una zona GND que puede haber sido borrada
    por el propio test."""
    world_pcb = await client.call_tool("get_world_context", {"kind": "pcb", "max_tokens": 4000})
    assert not world_pcb.isError, _text(world_pcb)
    header = _text(world_pcb).splitlines()[0]
    bbox_field = next(p for p in header.split("|") if p.startswith("bbox:"))
    lo, hi = bbox_field[len("bbox:") :].split(";")
    min_x, min_y = (float(v) for v in lo.split(","))
    max_x, max_y = (float(v) for v in hi.split(","))
    return [min_x, min_y, max_x, max_y]


async def _delete_existing_gnd_copper_zones(client: Any, bridge: IpcBridge, board: Any) -> None:
    """Auto-arreglo (idempotencia entre corridas): borra cualquier zona de
    cobre GND preexistente antes de que el test cree la suya — así cada
    corrida arranca del mismo punto sin importar qué dejó la corrida
    anterior."""
    for zone in bridge.list_zones(board):
        if zone.kind == "copper" and zone.net_name == "GND":
            delete_result = await client.call_tool("delete_zone", {"id": zone.kiid})
            assert not delete_result.isError, _text(delete_result)


@pytest.mark.integration_gui_slow
async def test_add_zone_fill_persists_matches_independent_drc() -> None:
    """D-23.2 (ADR-0012, extendido sesión 27): tras ``add_zone(fill=True)``,
    disco == vivo — sin ``save_board()`` manual — gate del merge."""
    _guard()
    pcb_path = _resolve_root_pcb()
    bridge = _preflight_same_board_open(pcb_path)
    g1.reset_session_state()
    get_default_store().reset()

    board = bridge.get_open_board()
    assert board is not None  # _preflight_same_board_open ya lo garantizó

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        # --- Arreglo determinista: sin plano GND en disco (borra + save).
        await _delete_existing_gnd_copper_zones(client, bridge, board)
        save_result = await client.call_tool("save_board", {})
        assert not save_result.isError, _text(save_result)
        mtime_before = pcb_path.stat().st_mtime

        board_bbox = await _gnd_board_bbox(client)

        # --- add_zone(fill=True) real — SIN save_board() manual.
        add_result = await client.call_tool(
            "add_zone", {"net": "GND", "layer": "B.Cu", "bbox": board_bbox, "fill": True}
        )
        assert not add_result.isError, _text(add_result)
        payload = _json(add_result)
        assert payload["filled"] is True

        # 1. Gate: el save_board() incondicional de D-23.2 corrió.
        mtime_after = pcb_path.stat().st_mtime
        assert mtime_after > mtime_before, (
            "el mtime del .kicad_pcb no cambió tras add_zone(fill=True) — "
            "¿el save_board() de D-23.2 no corrió?"
        )

        # Ground truth INDEPENDIENTE inmediata (bridge directo, no la tool).
        post_report = run_drc(pcb_path)

        # 2. Gate — corazón del contrato: el disco ya refleja el refill +
        # enforce_hole_clearance del vivo, sin que el llamador haya invocado
        # save_board() aparte.
        assert _hole_clearance_count(post_report) == 0, (
            f"run_drc() independiente trae hole_clearance espurio post-add_zone: "
            f"{[v.rule for v in post_report.violations if v.severity == 'error']}"
        )
        gnd_clearance = _gnd_clearance_violations(post_report)
        assert gnd_clearance == [], (
            f"clearance vs Zone GND sobrevivió al add_zone(fill=True): {gnd_clearance}"
        )

        # 3. Gate: una operación D-23.2 posterior (fill_zones, idempotente)
        # no dispara EXTERNAL_EDIT_DETECTED espurio — los mtimes de
        # add_zone se registraron post-save (hallazgo #31 sesión 24).
        followup = await client.call_tool("fill_zones", {})
        assert not followup.isError, _text(followup)
        assert "EXTERNAL_EDIT_DETECTED" not in _text(followup)

        # 4. Gate: keepouts fijos, sin proliferación descontrolada.
        zones_after = bridge.list_zones(board)
        keepouts_after = sum(1 for z in zones_after if z.kind == "keepout")
        assert _KEEPOUTS_MIN <= keepouts_after <= _KEEPOUTS_MAX, (
            f"conteo de keepouts fuera de rango esperado: {keepouts_after}"
        )


@pytest.mark.integration_gui_slow
async def test_fill_zones_persists_matches_independent_drc() -> None:
    """D-23.2 (ADR-0012, extendido sesión 27): tras ``fill_zones()``, disco
    == vivo — sin ``save_board()`` manual — gate del merge."""
    _guard()
    pcb_path = _resolve_root_pcb()
    bridge = _preflight_same_board_open(pcb_path)
    g1.reset_session_state()
    get_default_store().reset()

    board = bridge.get_open_board()
    assert board is not None

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        # --- Arreglo determinista: asegurar que existe un plano GND para
        # refillar (el fixture ya lo trae; defensivo por si esta corrida
        # arranca de un estado sin plano — p. ej. corrida aislada de este
        # test sin la anterior).
        zones_before = bridge.list_zones(board)
        has_gnd_copper = any(z.kind == "copper" and z.net_name == "GND" for z in zones_before)
        if not has_gnd_copper:
            board_bbox = await _gnd_board_bbox(client)
            create_result = await client.call_tool(
                "add_zone", {"net": "GND", "layer": "B.Cu", "bbox": board_bbox, "fill": True}
            )
            assert not create_result.isError, _text(create_result)

        save_result = await client.call_tool("save_board", {})
        assert not save_result.isError, _text(save_result)
        mtime_before = pcb_path.stat().st_mtime

        # --- fill_zones() real — SIN save_board() manual.
        fill_result = await client.call_tool("fill_zones", {})
        assert not fill_result.isError, _text(fill_result)
        fill_payload = _json(fill_result)
        assert fill_payload["zones_filled"] >= 1

        # 1. Gate: el save_board() incondicional de D-23.2 corrió.
        mtime_after = pcb_path.stat().st_mtime
        assert mtime_after > mtime_before, (
            "el mtime del .kicad_pcb no cambió tras fill_zones() — "
            "¿el save_board() de D-23.2 no corrió?"
        )

        # Ground truth INDEPENDIENTE inmediata.
        post_report = run_drc(pcb_path)

        # 2. Gate — corazón del contrato.
        assert _hole_clearance_count(post_report) == 0, (
            f"run_drc() independiente trae hole_clearance espurio post-fill_zones: "
            f"{[v.rule for v in post_report.violations if v.severity == 'error']}"
        )
        gnd_clearance = _gnd_clearance_violations(post_report)
        assert gnd_clearance == [], (
            f"clearance vs Zone GND sobrevivió al fill_zones(): {gnd_clearance}"
        )

        # 3. Gate: llamar fill_zones() de nuevo (idempotente) no dispara
        # EXTERNAL_EDIT_DETECTED — prueba que la PRIMERA llamada registró
        # mtimes post-save correctamente (si hubiera quedado stale, esta
        # segunda llamada lo detectaría contra sí misma).
        followup = await client.call_tool("fill_zones", {})
        assert not followup.isError, _text(followup)
        assert "EXTERNAL_EDIT_DETECTED" not in _text(followup)

        # 4. Gate: keepouts fijos, sin proliferación descontrolada.
        zones_after = bridge.list_zones(board)
        keepouts_after = sum(1 for z in zones_after if z.kind == "keepout")
        assert _KEEPOUTS_MIN <= keepouts_after <= _KEEPOUTS_MAX, (
            f"conteo de keepouts fuera de rango esperado: {keepouts_after}"
        )
