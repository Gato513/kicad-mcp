"""Test E2E del gate de cierre de sesión 19 (P4.5, plano GND + keepout).

**Gate:** re-rutear el fixture ``despertador-routed`` con un plano GND en
B.Cu y un keepout circular bajo ANT1 → Freerouting respeta la zona y el
keepout (investigación P4.0, ``docs/investigacion/19-zonas-ipc.md`` §2) →
DRC sin errores nuevos respecto al baseline post-zonas → verificación
cuantitativa: menos tracks/vías que antes de borrar el cobre GND dedicado
(el plano absorbió parte del retorno), y ``get_zones`` ve las 2 zonas con
KIID estables.

**Corre DIRECTO sobre el proyecto que ``KICAD_MCP_PROJECT`` apunta — el
mismo que debe estar YA ABIERTO en el PCB Editor de KiCad** — mismo patrón
que ``test_reload_e2e_gui.py`` (sesión 18, P3.3). **NO copia el fixture a un
tmp_path aislado**, a pesar de que el prompt original de la sesión lo pedía
así: ``add_zone``/``add_keepout_zone``/``fill_zones``/``delete_track``
mutan por IPC lo que sea que esté abierto en KiCad, y una copia aislada en
disco reproduciría exactamente el split-brain que la sesión 18 descubrió y
corrigió (``route_board`` rutearía la copia, no el board vivo que
``get_tracks``/``delete_track`` tocan) — ver el docstring de
``test_reload_e2e_gui.py`` para el hallazgo original. ``_preflight_same_board_open``
verifica la coincidencia ANTES de mutar nada.

Para ejecutar de verdad: abrir manualmente
``tests/fixtures/despertador-routed/despertador_inteligente.kicad_pcb`` (una
COPIA de trabajo, no el fixture versionado — ver
``docs/pruebas-gui.md``/README del fixture) en KiCad, apuntar
``KICAD_MCP_PROJECT`` a esa copia, y correr con
``KICAD_MCP_GUI_TEST=1``. Si el board abierto no tiene ``ANT1`` (no es el
despertador), el test salta con un mensaje accionable en vez de mutar el
board equivocado.

Requisitos de sistema: igual a ``test_reload_e2e_gui.py`` (Java ≥17,
``KICAD_MCP_FREEROUTING_JAR``, ``pcbnew`` de sistema). **Corrida real: el
benchmark de sesión 18 (235-925 s) es para un board recién exportado a
Freerouting sin cobre previo relevante para el solver; ESTE escenario —
borrar sólo GND de un board YA MAYORMENTE RUTEADO y dejar el resto intacto
más un keepout nuevo— demostró en sesión 19 (P4.5, dos corridas reales) ser
sustancialmente más lento: un intento corrió >2h38m sin converger (killeado
manualmente) y un segundo intento con ``timeout_s=1500`` (25 min) NO
completó — Freerouting seguía activo al cierre del timeout, sin error, sólo
más lento de lo esperado. **No se pudo completar una corrida en vivo exitosa
en sesión 19** dentro de un presupuesto de tiempo razonable; ``timeout_s``
por defecto de este test se dejó generoso (ver la llamada a ``route_board``
más abajo) a la espera de que una sesión futura, con más presupuesto de
tiempo dedicado, complete el gate. **Muta de forma permanente y real** el
board abierto — no es descartable.
"""

from __future__ import annotations

import json
import math
import os
import shutil
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.autoroute import _JAR_ENV, _SYSTEM_PYTHON_DEFAULT
from kicad_mcp.bridge.ipc import IpcBridge
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store
from kicad_mcp.tools.world import _resolve_root_pcb

# bbox "atrapa-todo" para get_tracks(bbox=) — KiCad no tiene boards fuera de
# ±10000mm (mismo límite que la validación de draw_board_outline). Es sólo un
# FILTRO de lectura, no geometría: no crea nada, a diferencia del bbox real
# del board que se usa para el plano GND (ver más abajo, sale de
# get_world_context).
_CATCH_ALL_BBOX = [-10_000.0, -10_000.0, 10_000.0, 10_000.0]

_KEEPOUT_RADIUS_MM = 15.0
_KEEPOUT_VERTICES = 12


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


def _preflight_same_board_open(pcb_path: Path) -> None:
    """Idéntico a ``test_reload_e2e_gui.py`` — evita el split-brain (P3.3)."""
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


def _server():  # type: ignore[no-untyped-def]
    from kicad_mcp.server import create_server

    return create_server()


def _parse_track_ids(tracks_text: str) -> list[str]:
    """Espejo de la misma función en ``test_reload_e2e_gui.py``: KIID de las
    líneas ``T``/``A`` (track/arco) de ``get_tracks``. Ignora vías."""
    ids = []
    for line in tracks_text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("T", "A"):
            ids.append(parts[1])
    return ids


def _tracks_vias_counts(tracks_text: str) -> tuple[int, int]:
    """Cuenta tracks+arcos y vías desde la cabecera de ``get_tracks``
    (``TRACKS|v1|<filtro>|Ns|Nv``) — más barato que contar líneas a mano."""
    header = tracks_text.splitlines()[0]
    parts = header.split("|")
    n_segs = int(parts[-2].rstrip("s"))
    n_vias = int(parts[-1].rstrip("v"))
    return n_segs, n_vias


def _board_bbox_and_area(world_pcb_text: str) -> tuple[list[float], float]:
    """Extrae ``bbox:min_x,min_y;max_x,max_y`` de la cabecera de
    ``get_world_context(kind='pcb')`` (F-03,
    ``src/kicad_mcp/toon/encoder.py:266``) y calcula el área real del board.
    """
    header = world_pcb_text.splitlines()[0]
    bbox_field = next(p for p in header.split("|") if p.startswith("bbox:"))
    lo, hi = bbox_field[len("bbox:") :].split(";")
    min_x, min_y = (float(v) for v in lo.split(","))
    max_x, max_y = (float(v) for v in hi.split(","))
    area = (max_x - min_x) * (max_y - min_y)
    return [min_x, min_y, max_x, max_y], area


def _drc_error_count(payload: dict[str, Any]) -> int:
    return int(payload.get("counts", {}).get("error", 0))


@pytest.mark.integration_gui_slow
async def test_gnd_plane_and_ant1_keepout_reduce_vias_without_new_drc_errors() -> None:
    """P4.5: plano GND + keepout ANT1 → re-ruteo → menos vías, DRC sin
    errores nuevos, 2 zonas con KIID estables."""
    _guard()
    pcb_path = _resolve_root_pcb()
    _preflight_same_board_open(pcb_path)
    g1.reset_session_state()
    get_default_store().reset()

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        # Precondición: el board abierto tiene ANT1 (es el despertador) — si
        # no, saltar con mensaje accionable en vez de mutar el board
        # equivocado (mismo espíritu que _preflight_same_board_open).
        detail = await client.call_tool("get_component_detail", {"ref": "ANT1"})
        if detail.isError:
            pytest.skip(
                "El board abierto no tiene ANT1 — abrí una copia de trabajo de "
                "tests/fixtures/despertador-routed/despertador_inteligente.kicad_pcb "
                "en KiCad antes de correr este test."
            )
        detail_header = _text(detail).splitlines()[0]
        at_field = next(p for p in detail_header.split("|") if p.startswith("at:"))
        ant1_x, ant1_y = (float(v) for v in at_field[len("at:") :].split(","))

        # max_tokens generoso: sólo necesitamos la cabecera (bbox:), pero el
        # tool arma el TOON completo antes de poder recortar — el despertador
        # (24 footprints) no entra en el default de 800 (D4).
        world_pcb = await client.call_tool("get_world_context", {"kind": "pcb", "max_tokens": 4000})
        assert not world_pcb.isError, _text(world_pcb)
        board_bbox, board_area_mm2 = _board_bbox_and_area(_text(world_pcb))

        # 2. Conteo inicial (todo el board, no sólo GND).
        baseline_tracks = await client.call_tool(
            "get_tracks", {"bbox": _CATCH_ALL_BBOX, "max_tokens": 20000}
        )
        assert not baseline_tracks.isError, _text(baseline_tracks)
        tracks_inicial, vias_inicial = _tracks_vias_counts(_text(baseline_tracks))

        # 3. Plano GND en B.Cu cubriendo el board entero (bbox REAL, no el
        # catch-all de arriba — esto sí crea geometría).
        add_zone_result = await client.call_tool(
            "add_zone", {"net": "GND", "layer": "B.Cu", "bbox": board_bbox}
        )
        assert not add_zone_result.isError, _text(add_zone_result)
        zone_payload = _json(add_zone_result)
        gnd_zone_id = zone_payload["zone_id"]
        assert zone_payload["area_mm2"] >= 0.6 * board_area_mm2, (
            f"área del plano GND ({zone_payload['area_mm2']} mm2) < 60% del "
            f"board ({board_area_mm2} mm2) — el fill no funcionó como se esperaba"
        )

        # 4. Keepout circular ~15mm bajo ANT1, ambas capas.
        circle = [
            [
                round(
                    ant1_x + _KEEPOUT_RADIUS_MM * math.cos(2 * math.pi * i / _KEEPOUT_VERTICES), 3
                ),
                round(
                    ant1_y + _KEEPOUT_RADIUS_MM * math.sin(2 * math.pi * i / _KEEPOUT_VERTICES), 3
                ),
            ]
            for i in range(_KEEPOUT_VERTICES)
        ]
        keepout_result = await client.call_tool(
            "add_keepout_zone", {"layer": "all", "polygon": circle}
        )
        assert not keepout_result.isError, _text(keepout_result)
        keepout_zone_id = _json(keepout_result)["zone_id"]

        # 5. Fill explícito (idempotente — asegura estado consistente antes
        # del DRC baseline).
        fill_result = await client.call_tool("fill_zones", {})
        assert not fill_result.isError, _text(fill_result)

        # 6. DRC baseline post-zonas.
        drc_baseline = await client.call_tool("run_drc", {})
        assert not drc_baseline.isError, _text(drc_baseline)
        err_baseline = _drc_error_count(_json(drc_baseline))

        # 7. Borrar TODOS los tracks de GND — el plano debería absorberlos.
        gnd_tracks = await client.call_tool("get_tracks", {"net": "GND", "max_tokens": 20000})
        assert not gnd_tracks.isError, _text(gnd_tracks)
        gnd_ids = _parse_track_ids(_text(gnd_tracks))
        tracks_gnd_borrados = len(gnd_ids)
        assert tracks_gnd_borrados > 0, "el despertador-routed debería tener tracks de GND"
        for kiid in gnd_ids:
            delr = await client.call_tool("delete_track", {"id": kiid})
            assert not delr.isError, _text(delr)

        # 8. Re-rutear — Freerouting debe respetar el plano GND (P4.0 §2) y
        # el keepout (no meter cobre bajo ANT1). timeout_s generoso (ver
        # docstring del módulo): re-rutear sólo GND sobre un board YA
        # MAYORMENTE RUTEADO + keepout nuevo demostró en sesión 19 ser mucho
        # más lento que el benchmark de board limpio de sesión 18 (dos
        # corridas reales no convergieron ni con 1500s ni informalmente con
        # >2h38m) — no se decidió un valor "seguro" definitivo, sólo se subió
        # el piso frente al default de 1800s que resultó insuficiente.
        route_result = await client.call_tool("route_board", {"timeout_s": 5400})
        assert not route_result.isError, _text(route_result)
        route_payload = _json(route_result)
        assert route_payload["reloaded"] is True, (
            "route_board no pudo recargar el editor vivo — el gate de 0 "
            "contactos humanos (D-V3.1) no se cumplió"
        )
        assert route_payload["zones"]["existentes"] >= 2

        # 9. DRC post-route — sin errores NUEVOS respecto al baseline post-zonas.
        drc_post = await client.call_tool("run_drc", {})
        assert not drc_post.isError, _text(drc_post)
        err_post = _drc_error_count(_json(drc_post))
        assert err_post <= err_baseline, (
            f"DRC post-route ({err_post} errores) > baseline post-zonas "
            f"({err_baseline}) — route_board introdujo violaciones nuevas"
        )

        # 10. Verificación cuantitativa (el criterio de cierre de la sesión).
        final_tracks = await client.call_tool(
            "get_tracks", {"bbox": _CATCH_ALL_BBOX, "max_tokens": 20000}
        )
        assert not final_tracks.isError, _text(final_tracks)
        tracks_final, vias_final = _tracks_vias_counts(_text(final_tracks))
        assert tracks_final <= tracks_inicial - tracks_gnd_borrados, (
            f"tracks_final={tracks_final} > tracks_inicial({tracks_inicial}) - "
            f"tracks_gnd_borrados({tracks_gnd_borrados}) — el plano no absorbió cobre"
        )
        assert vias_final <= vias_inicial, (
            f"vias_final={vias_final} > vias_inicial={vias_inicial} — el plano no "
            "redujo el ruteo dedicado de retorno de GND"
        )

        # 11. get_zones ve las 2 zonas con KIID estables (no cambiaron entre
        # su creación y ahora, a pesar del re-ruteo intermedio).
        zones_b_cu = await client.call_tool("get_zones", {"layer": "B.Cu"})
        assert not zones_b_cu.isError, _text(zones_b_cu)
        zones_text = _text(zones_b_cu)
        assert gnd_zone_id in zones_text
        assert keepout_zone_id in zones_text
