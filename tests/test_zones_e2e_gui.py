"""Test E2E del escenario canónico del Dogfooding 3 (plano GND, ruteo desde cero).

**Gate (sesión 19d, reemplaza el P4.5 original de sesión 19):** vaciar el
board de cobre, crear y fillar un plano GND en B.Cu, y re-rutear desde cero
→ Freerouting converge, DRC sin errores nuevos respecto al baseline
post-zonas, menos tracks que antes de vaciar el board (el plano absorbe
retorno de GND), y ``get_zones`` ve la zona GND con KIID estable.

**Por qué se reemplazó el escenario original:** el test P4.5 de sesión 19
re-ruteaba sólo GND sobre un board YA MAYORMENTE RUTEADO más un keepout
circular bajo ANT1, y nunca convergió en dos corridas reales (una >2h38m sin
converger, otra con ``timeout_s=1500`` sin completar). La investigación de la
sesión 19c (Bloque 1-4, ``docs/sesiones/19c-reporte.md``) aisló la causa: no
es que "Freerouting escale mal con planos densos" (conclusión original de
sesión 19) — el plano GND **solo** converge en 11.3 min sin problema
(Bloque 2, VERDE) y el escenario real del Dogfooding 3 (ruteo **desde cero**
con plano, **sin** keepout) converge en 8.5 min con 10/10 nets y DRC mejorado
(Bloque 3, VERDE). El keepout circular bajo ANT1, combinado con ruteo desde
cero (sin tracks previos que sirvan de guía parcial), bloqueó 9 de 10 nets no
GND por completo (Bloque 4, ROJO) — peor que las corridas originales de
P4.5, que al menos progresaban parcialmente. Conclusión: el keepout
autorruteado NUNCA se combina con un ruteo completo desde cero; si se
necesita proteger físicamente un área (p. ej. bajo una antena), el keepout se
aplica DESPUÉS del ruteo completo, como paso manual separado — fuera del
alcance de este test.

Este test reproduce el escenario VERDE del Bloque 3: vacía el board con
``delete_tracks_bulk`` (sesión 19d, 19d.2 — evita las 266 llamadas
individuales ``delete_track``/``delete_via`` que el Bloque 3 de 19c necesitó
por falta de esta tool), crea el plano GND, y rutea desde cero. **Sin
keepout.**

**Corre DIRECTO sobre el proyecto que ``KICAD_MCP_PROJECT`` apunta — el
mismo que debe estar YA ABIERTO en el PCB Editor de KiCad** — mismo patrón
que ``test_reload_e2e_gui.py`` (sesión 18, P3.3). **NO copia el fixture a un
tmp_path aislado**: ``delete_tracks_bulk``/``add_zone``/``fill_zones``/
``route_board`` mutan por IPC lo que sea que esté abierto en KiCad, y una
copia aislada en disco reproduciría el split-brain que la sesión 18
descubrió y corrigió — ver el docstring de ``test_reload_e2e_gui.py`` para
el hallazgo original. ``_preflight_same_board_open`` verifica la
coincidencia ANTES de mutar nada.

Para ejecutar de verdad: abrir manualmente
``tests/fixtures/despertador-routed/despertador_inteligente.kicad_pcb`` (una
COPIA de trabajo, no el fixture versionado — ver
``docs/pruebas-gui.md``/README del fixture) en KiCad, apuntar
``KICAD_MCP_PROJECT`` a esa copia, y correr con
``KICAD_MCP_GUI_TEST=1``. Si el board abierto no tiene ``ANT1`` (no es el
despertador), el test salta con un mensaje accionable en vez de mutar el
board equivocado.

Requisitos de sistema: igual a ``test_reload_e2e_gui.py`` (Java ≥17,
``KICAD_MCP_FREEROUTING_JAR``, ``pcbnew`` de sistema). El Bloque 3 de 19c
tardó 512.9s (8.5 min) con este mismo escenario contra el mismo fixture;
``timeout_s=900`` deja margen. **Muta de forma permanente y real** el board
abierto — no es descartable.
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
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store
from kicad_mcp.tools.world import _resolve_root_pcb

# bbox "atrapa-todo" para get_tracks(bbox=)/delete_tracks_bulk(bbox=) — KiCad
# no tiene boards fuera de ±10000mm (mismo límite que draw_board_outline). Es
# sólo un FILTRO de lectura/borrado, no geometría: no crea nada, a diferencia
# del bbox real del board que se usa para el plano GND (sale de
# get_world_context, más abajo).
_CATCH_ALL_BBOX = [-10_000.0, -10_000.0, 10_000.0, 10_000.0]

_ROUTE_TIMEOUT_S = 900


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


@pytest.mark.integration_gui_slow
async def test_gnd_plane_from_scratch_converges_without_new_drc_errors() -> None:
    """Bloque 3 de 19c: vaciar cobre → plano GND → rutear desde cero (sin
    keepout) → converge, DRC no empeora, menos tracks que el board original,
    zona GND con KIID estable."""
    _guard()
    pcb_path = _resolve_root_pcb()
    _preflight_same_board_open(pcb_path)
    g1.reset_session_state()
    get_default_store().reset()

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        # Precondición: el board abierto es el despertador (tiene ANT1) — si
        # no, saltar con mensaje accionable en vez de mutar el board
        # equivocado.
        detail = await client.call_tool("get_component_detail", {"ref": "ANT1"})
        if detail.isError:
            pytest.skip(
                "El board abierto no tiene ANT1 — abrí una copia de trabajo de "
                "tests/fixtures/despertador-routed/despertador_inteligente.kicad_pcb "
                "en KiCad antes de correr este test."
            )

        # max_tokens generoso: sólo necesitamos la cabecera (bbox:), pero el
        # tool arma el TOON completo antes de poder recortar — el despertador
        # (24 footprints) no entra en el default de 800 (D4).
        world_pcb = await client.call_tool("get_world_context", {"kind": "pcb", "max_tokens": 4000})
        assert not world_pcb.isError, _text(world_pcb)
        board_bbox, board_area_mm2 = _board_bbox_and_area(_text(world_pcb))

        # 1. Conteo inicial (todo el board).
        baseline_tracks = await client.call_tool(
            "get_tracks", {"bbox": _CATCH_ALL_BBOX, "max_tokens": 20000}
        )
        assert not baseline_tracks.isError, _text(baseline_tracks)
        tracks_inicial, _vias_inicial = _tracks_vias_counts(_text(baseline_tracks))

        # 2. Vaciar TODO el cobre del board en un solo round-trip (19d.2) —
        # Bloque 3 de 19c necesitó 266 llamadas individuales delete_track/
        # delete_via por falta de esta tool.
        bulk_delete = await client.call_tool(
            "delete_tracks_bulk", {"bbox": _CATCH_ALL_BBOX, "include_vias": True}
        )
        assert not bulk_delete.isError, _text(bulk_delete)
        bulk_payload = _json(bulk_delete)
        tracks_borrados = bulk_payload["tracks_deleted"]
        vias_borrados = bulk_payload["vias_deleted"]
        assert tracks_borrados > 0 or vias_borrados > 0, (
            "el despertador-routed debería tener cobre para vaciar"
        )

        # 3. Plano GND en B.Cu cubriendo el board entero (bbox REAL, no el
        # catch-all de arriba — esto sí crea geometría), sobre board sin
        # cobre (patrón validado del Bloque 3 de 19c).
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

        # 4. Fill explícito (idempotente — asegura estado consistente antes
        # del ruteo).
        fill_result = await client.call_tool("fill_zones", {})
        assert not fill_result.isError, _text(fill_result)

        # 5. Rutear DESDE CERO — Freerouting debe respetar el plano GND
        # (P4.0 §2, ``docs/investigacion/19-zonas-ipc.md``). SIN keepout: la
        # investigación 19c (Bloque 4, ROJO) confirmó que un keepout
        # autorruteado bloquea 9/10 nets cuando el ruteo parte de cero, sin
        # tracks previos que sirvan de guía parcial — si se necesita proteger
        # un área física (p. ej. bajo ANT1), el keepout se aplica DESPUÉS del
        # ruteo completo, como paso manual separado (fuera de este test).
        # timeout_s=900: el Bloque 3 de 19c (mismo escenario exacto) tardó
        # 512.9s (8.5 min); esto deja margen.
        #
        # NO se llama run_drc() manualmente antes de route_board para armar
        # un "baseline": add_zone/fill_zones/delete_tracks_bulk mutan sólo el
        # board VIVO por IPC, no el .kicad_pcb en disco — run_drc() (la tool)
        # lee de DISCO (``_resolve_pcb()``), así que un run_drc() previo a
        # route_board mediría el archivo VIEJO (el board pristino recién
        # restaurado), no el board vaciado+con plano que se acaba de armar
        # (bug real encontrado en esta sesión: comparar ese baseline
        # stale contra el DRC post-route real produce falsos positivos de
        # "regresión"). route_board SÍ mide correctamente ambos extremos —
        # hace un save_board implícito (live→disco) ANTES de su propio DRC
        # pre-route — y devuelve ambos en ``drc.err_preexistentes``/
        # ``drc.err_post`` (exactamente lo que midió 19c Bloque 3).
        route_result = await client.call_tool("route_board", {"timeout_s": _ROUTE_TIMEOUT_S})
        assert not route_result.isError, _text(route_result)
        route_payload = _json(route_result)
        assert route_payload["reloaded"] is True, (
            "route_board no pudo recargar el editor vivo — el gate de 0 "
            "contactos humanos (D-V3.1) no se cumplió"
        )
        assert route_payload["zones"]["existentes"] >= 1

        # 6. DRC: sin errores NUEVOS respecto al preexistente (medido por
        # route_board mismo, ver nota arriba).
        err_preexistentes = route_payload["drc"]["err_preexistentes"]
        err_post = route_payload["drc"]["err_post"]
        assert err_post <= err_preexistentes, (
            f"DRC post-route ({err_post} errores) > preexistentes "
            f"({err_preexistentes}) — route_board introdujo violaciones nuevas"
        )

        # 8. Verificación cuantitativa (el criterio de cierre de la sesión).
        # tracks_final < tracks_inicial es robusto: el plano absorbe cobre de
        # retorno GND (Bloque 3 de 19c: 265 < 313). vias_final NO se acota
        # contra vias_inicial a propósito — el ruteo desde cero produce un
        # conteo de vías determinado por Freerouting, no comparable al board
        # hand-routed original (Bloque 3 de 19c dio 30 vías > 21 originales);
        # sólo se verifica que el ruteo produjo algo de cobre.
        final_tracks = await client.call_tool(
            "get_tracks", {"bbox": _CATCH_ALL_BBOX, "max_tokens": 20000}
        )
        assert not final_tracks.isError, _text(final_tracks)
        tracks_final, vias_final = _tracks_vias_counts(_text(final_tracks))
        assert tracks_final < tracks_inicial, (
            f"tracks_final={tracks_final} >= tracks_inicial({tracks_inicial}) — "
            "el plano no absorbió cobre respecto al board original"
        )
        assert vias_final > 0, "el re-ruteo desde cero no agregó ninguna vía"

        # 9. get_zones ve la zona GND con KIID estable (no cambió entre su
        # creación y ahora, a pesar del re-ruteo intermedio).
        zones_b_cu = await client.call_tool("get_zones", {"layer": "B.Cu"})
        assert not zones_b_cu.isError, _text(zones_b_cu)
        assert gnd_zone_id in _text(zones_b_cu)
