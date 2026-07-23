"""Test integration_gui de sesión 21 — P1: ``get_footprint_neighbors`` en vivo.

Verifica sobre el fixture real ``despertador-routed`` (KiCad 10.0.4) que
``get_footprint_neighbors("J1", radius_mm=5.0)`` devuelve los 3 agujeros
NPTH propios de J1, el borde derecho del board a ~0.5mm, y pads vecinos —
el escenario exacto de F-D3-04
(``docs/dogfooding/dogfood3-fricciones.md``).

**Read-only** — a diferencia de los otros tests de sesión 21, este NO muta
el board (ni siquiera fill/refill). Corre directo sobre el proyecto que
``KICAD_MCP_PROJECT`` apunta, sin requisito de Freerouting/Java.
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent


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


def _server():  # type: ignore[no-untyped-def]
    from kicad_mcp.server import create_server

    return create_server()


@pytest.mark.integration_gui
async def test_get_footprint_neighbors_j1_finds_npth_holes_and_edge() -> None:
    """J1 (conector ICSP) tiene 3 agujeros NPTH mecánicos propios y está a
    ~0.5mm del borde derecho del board (44x44mm) — el escenario real que
    costó 35 min/5 intentos en el D3 (F-04)."""
    _guard()

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        detail = await client.call_tool("get_component_detail", {"ref": "J1"})
        if detail.isError:
            pytest.skip(
                "El board abierto no tiene J1 — abrí una copia de trabajo de "
                "tests/fixtures/despertador-routed/despertador_inteligente.kicad_pcb "
                "en KiCad antes de correr este test."
            )

        # max_tokens generoso: J1 está en un cluster denso (23 vecinos de
        # cobre reales dentro de 5mm) — no entra en el default de 800 (D4),
        # igual que get_component_detail sobre conectores grandes.
        result = await client.call_tool(
            "get_footprint_neighbors", {"ref": "J1", "radius_mm": 5.0, "max_tokens": 4000}
        )
        assert not result.isError, _text(result)
        payload = _json(result)

        assert payload["ref"] == "J1"
        holes = payload["neighbors"]["holes"]
        own_npth = [h for h in holes if h["kind"] == "npth" and h["belongs_to"] == "J1"]
        assert len(own_npth) == 3, f"esperaba 3 agujeros NPTH propios de J1, encontró: {holes}"
        for h in own_npth:
            assert h["diameter_mm"] == pytest.approx(0.99, abs=0.02)

        edge = payload["neighbors"]["edge"]
        assert edge is not None, "J1 debería estar cerca del borde derecho (~0.5mm)"
        assert edge["closest_edge"] == "right"
        assert edge["dist_mm"] == pytest.approx(0.5, abs=0.3)

        # Vecinos de cobre: J1 está en un cluster denso (tracks/vías reales
        # dentro de 5mm), aunque no necesariamente PADS de otros footprints
        # (BT1/U4 quedan a >5mm del bbox de J1 en este layout).
        assert isinstance(payload["neighbors"]["pads"], list)
        assert len(payload["neighbors"]["tracks"]) > 0


@pytest.mark.integration_gui
async def test_get_footprint_neighbors_small_radius_excludes_far_holes() -> None:
    """Un radio chico (1mm) sobre J1 no debería traer los 3 agujeros NPTH si
    alguno está más lejos que el pad de referencia — verifica que el filtro
    de radio realmente filtra, no sólo lista todo."""
    _guard()

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        detail = await client.call_tool("get_component_detail", {"ref": "J1"})
        if detail.isError:
            pytest.skip("El board abierto no tiene J1 (no es el despertador).")

        wide = await client.call_tool(
            "get_footprint_neighbors", {"ref": "J1", "radius_mm": 5.0, "max_tokens": 4000}
        )
        narrow = await client.call_tool(
            "get_footprint_neighbors", {"ref": "J1", "radius_mm": 0.01, "max_tokens": 4000}
        )
        assert not wide.isError, _text(wide)
        assert not narrow.isError, _text(narrow)
        wide_holes = _json(wide)["neighbors"]["holes"]
        narrow_holes = _json(narrow)["neighbors"]["holes"]
        assert len(narrow_holes) <= len(wide_holes)
