"""Test integration_gui_slow de sesión 48 — F-V3-ZONE-FILL-CRASH: smoke test
de correctitud para el troceo de ``create_items`` en
``enforce_hole_clearance`` (``src/kicad_mcp/bridge/ipc.py``,
``_ENFORCE_HOLE_CLEARANCE_BATCH_SIZE``).

**Alcance real de este test — no confundir con carga.** El troceo en sí ya
está probado con datos duros en ``tests/test_pcb_hole_clearance.py::
test_enforce_hole_clearance_batches_create_items`` (offline, N=250 → 3
lotes de 100/100/50, mecánicamente verificado). Ese test cubre la lógica de
troceo; lo que NO cubre es un round-trip real contra KiCad. Este test SÍ lo
hace, pero sobre ``despertador-routed`` (23 fp, ~4-8 keepouts esperados por
zona — ver ``_KEEPOUTS_MIN``/``_KEEPOUTS_MAX`` de
``test_pcb_session27_zone_persist_gui.py``), que queda muy por debajo del
tamaño de lote (100): NO ejercita múltiples lotes en vivo, sólo confirma que
el camino con `pending`/flush-final no rompió el comportamiento normal.

**Laguna que este test NO cierra (declarada, no escondida):** demostrar en
vivo que el troceo evita el patrón de timeout en un board con más de 100
agujeros ajenos por zona requeriría un fixture sintético con >100 pads PTH/
NPTH reales sin zonas de cobre grandes preexistentes — construir eso exige
level bajo (``PadStack``/drill vía protobuf de kipy), evaluado como
desproporcionado para esta unidad. Queda como trabajo futuro si hace falta
demostración en vivo (ver ``docs/BACKLOG.md``, F-V3-ZONE-FILL-CRASH). La
evidencia de que 004_real (189 fp, 808 vías, zonas de cobre reales
preexistentes) YA supera el timeout de 2000ms incluso con una zona nueva de
5x5mm —medido en vivo esta sesión— es la confirmación empírica de que la
laguna es real y alcanzable, no hipotética.

Mismo patrón de round-trip que ``test_pcb_session27_zone_persist_gui.py``
(borra cualquier zona GND de cobre preexistente, la recrea con
``add_zone(fill=True)``, repite un par de veces). Corre DIRECTO sobre el
proyecto que ``KICAD_MCP_PROJECT`` apunta — debe estar YA ABIERTO en el PCB
Editor. **Muta el board** (borra/recrea el plano GND) — no es descartable
entre corridas del propio test, pero se auto-arregla.
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
from kicad_mcp.tools.world import _resolve_root_pcb

_N_REPEATS = 3
"""Repeticiones de add_zone(fill=True) — no demuestra multi-lote (ver
docstring del módulo), sólo confirma estabilidad del camino con troceo a
través de varias pasadas consecutivas, mismo espíritu que el gate de
sesión 27 (2 corridas consecutivas)."""


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _json(result: CallToolResult) -> dict[str, Any]:
    return json.loads(_text(result))


def _guard() -> None:
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/guias/pruebas-gui.md")
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


async def _gnd_board_bbox(client: Any) -> list[float]:
    world_pcb = await client.call_tool("get_world_context", {"kind": "pcb", "max_tokens": 4000})
    assert not world_pcb.isError, _text(world_pcb)
    header = _text(world_pcb).splitlines()[0]
    bbox_field = next(p for p in header.split("|") if p.startswith("bbox:"))
    lo, hi = bbox_field[len("bbox:") :].split(";")
    min_x, min_y = (float(v) for v in lo.split(","))
    max_x, max_y = (float(v) for v in hi.split(","))
    return [min_x, min_y, max_x, max_y]


async def _delete_existing_gnd_copper_zones(client: Any, bridge: IpcBridge, board: Any) -> None:
    for zone in bridge.list_zones(board):
        if zone.kind == "copper" and zone.net_name == "GND":
            delete_result = await client.call_tool("delete_zone", {"id": zone.kiid})
            assert not delete_result.isError, _text(delete_result)


@pytest.mark.integration_gui_slow
async def test_add_zone_fill_still_works_after_batching_change() -> None:
    """Sesión 48: N repeticiones de add_zone(fill=True) sobre despertador-
    routed, sin KICAD_TIMEOUT/KICAD_NOT_RUNNING, confirmando que el troceo
    de create_items no rompió el camino normal (round-trip real, no fake)."""
    _guard()
    pcb_path = _resolve_root_pcb()
    bridge = _preflight_same_board_open(pcb_path)

    board = bridge.get_open_board()
    assert board is not None  # _preflight_same_board_open ya lo garantizó

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        await _delete_existing_gnd_copper_zones(client, bridge, board)
        board_bbox = await _gnd_board_bbox(client)

        for i in range(_N_REPEATS):
            add_result = await client.call_tool(
                "add_zone", {"net": "GND", "layer": "B.Cu", "bbox": board_bbox, "fill": True}
            )
            body = _text(add_result)
            call_desc = f"pasada {i + 1}/{_N_REPEATS}: {body}"
            assert "KICAD_TIMEOUT" not in body, call_desc
            assert "KICAD_NOT_RUNNING" not in body, call_desc
            assert not add_result.isError, call_desc
            assert _json(add_result)["filled"] is True

            delete_result = await client.call_tool(
                "delete_zone", {"id": _json(add_result)["zone_id"]}
            )
            assert not delete_result.isError, _text(delete_result)

        # KiCad sigue respondiendo tras las N pasadas.
        health = await client.call_tool("health", {})
        assert not health.isError, _text(health)
        assert _json(health)["kicad_ipc"]["status"] == "ok"
