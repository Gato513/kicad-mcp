"""Test integration_gui de sesión 21 — F-D3-01: verificación en vivo del
workaround ``enforce_hole_clearance`` contra KiCad 10.0.4 real.

Reproduce el escenario del Dogfooding 3 (``docs/dogfooding/dogfood3-fricciones.md``
F-01): un plano GND simple (`bbox`, SIN las muescas manuales que el agente
del D3 tuvo que tallar a mano) sobre un board con el pad PTH real de ANT1 y
los 3 agujeros NPTH reales de J1. Antes del fix (sesión 20), esto dejaba
0.0000mm de clearance contra esos agujeros — 6 violaciones DRC reales
(4xhole_clearance + 1xclearance + 1xsolder_mask_bridge). Con el workaround
post-fill de sesión 21 (``docs/investigacion/21-fill-zones-holes.md``,
decisión humana), `add_zone`/`fill_zones` deben quedar en 0 errores.

Corre DIRECTO sobre el proyecto que ``KICAD_MCP_PROJECT`` apunta — mismo
patrón que ``test_zones_e2e_gui.py``/``test_reload_e2e_gui.py``. **Muta de
forma permanente** el board abierto (borra y recrea la zona GND) — no es
descartable; regenerar desde el fixture si hace falta el estado original.

No requiere Freerouting (no rutea) — sólo Java/jar de
``test_zones_e2e_gui.py`` NO son requisito acá.
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
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store
from kicad_mcp.tools.world import _resolve_root_pcb


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


def _preflight_same_board_open(pcb_path: Path) -> None:
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


@pytest.mark.integration_gui
async def test_add_zone_bbox_respects_pth_npth_hole_clearance() -> None:
    """Repro exacta del D3 F-01: plano GND simple (bbox, sin muescas) sobre
    ANT1 (PTH) + J1 (3x NPTH) -> 0 errores DRC (antes del fix: 6)."""
    _guard()
    pcb_path = _resolve_root_pcb()
    _preflight_same_board_open(pcb_path)
    g1.reset_session_state()
    get_default_store().reset()

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        ant1 = await client.call_tool("get_component_detail", {"ref": "ANT1"})
        if ant1.isError:
            pytest.skip(
                "El board abierto no tiene ANT1 — abrí una copia de trabajo de "
                "tests/fixtures/despertador-routed/despertador_inteligente.kicad_pcb "
                "en KiCad antes de correr este test."
            )
        j1 = await client.call_tool("get_component_detail", {"ref": "J1"})
        assert not j1.isError, _text(j1)

        world_pcb = await client.call_tool(
            "get_world_context", {"kind": "pcb", "max_tokens": 4000}
        )
        assert not world_pcb.isError, _text(world_pcb)
        header = _text(world_pcb).splitlines()[0]
        bbox_field = next(p for p in header.split("|") if p.startswith("bbox:"))
        lo, hi = bbox_field[len("bbox:") :].split(";")
        min_x, min_y = (float(v) for v in lo.split(","))
        max_x, max_y = (float(v) for v in hi.split(","))
        board_bbox = [min_x, min_y, max_x, max_y]

        # Zona GND EXISTENTE (fixture regenerado = ya con muescas manuales
        # del D3) — se borra para reproducir la geometría ORIGINAL simple.
        existing = await client.call_tool("get_zones", {"net": "GND"})
        assert not existing.isError, _text(existing)
        for line in _text(existing).splitlines()[1:]:
            zone_id = line.split()[1]
            deleted = await client.call_tool("delete_zone", {"id": zone_id})
            assert not deleted.isError, _text(deleted)

        # Plano GND simple (bbox, SIN muescas) — el patrón EXACTO que produjo
        # F-01 en el D3.
        add_zone_result = await client.call_tool(
            "add_zone", {"net": "GND", "layer": "B.Cu", "bbox": board_bbox, "fill": True}
        )
        assert not add_zone_result.isError, _text(add_zone_result)

        drc = await client.call_tool("run_drc", {"min_severity": "error"})
        assert not drc.isError, _text(drc)
        drc_payload = _json(drc)
        assert drc_payload["total"] == 0, (
            f"DRC post add_zone(bbox) mostró {drc_payload['total']} errores "
            f"(esperado 0 con enforce_hole_clearance activo): {drc_payload}"
        )


@pytest.mark.integration_gui
async def test_fill_zones_refill_keeps_hole_clearance() -> None:
    """Refill explícito (no recrear) también debe mantener 0 errores —
    ejercita el mismo workaround vía ``fill_zones()`` en vez de ``add_zone``."""
    _guard()
    pcb_path = _resolve_root_pcb()
    _preflight_same_board_open(pcb_path)
    g1.reset_session_state()
    get_default_store().reset()

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        ant1 = await client.call_tool("get_component_detail", {"ref": "ANT1"})
        if ant1.isError:
            pytest.skip("El board abierto no tiene ANT1 (no es el despertador).")

        fill_result = await client.call_tool("fill_zones", {})
        assert not fill_result.isError, _text(fill_result)

        drc = await client.call_tool("run_drc", {"min_severity": "error"})
        assert not drc.isError, _text(drc)
        assert _json(drc)["total"] == 0
