"""Tests de la tool ``get_world_context``.

- ``unit``: llama la tool con un state builder mockeado (estado fake).
- ``integration``: ejerce el pipeline completo contra las fixtures 001/003.

Contrato: la tool devuelve el string TOON puro (sin envelope JSON). La
cabecera lleva ``snap`` y ``kind`` (sesión 03).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.server import create_server
from kicad_mcp.toon.schema import Component, NormalizedState, Pin
from tests.conftest import mirror_fixture

FIXTURES = Path(__file__).parent / "fixtures"


def _toon(result: CallToolResult) -> str:
    assert result.isError is False, f"error: {result}"
    assert len(result.content) == 1
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _fake_state() -> NormalizedState:
    return NormalizedState(
        kind="sch",
        snap=1,
        components=(
            Component(
                ref="U1",
                value="STM32",
                lib="MCU:STM32",
                x=100.0,
                y=50.0,
                pins=(Pin(p="1", net="3V3"), Pin(p="2", net="GND")),
            ),
            Component(
                ref="C1",
                value="100nF",
                lib="Device:C",
                x=105.0,
                y=50.0,
                pins=(Pin(p="1", net="3V3"), Pin(p="2", net="GND")),
            ),
        ),
    )


@pytest.mark.unit
async def test_world_context_with_fake_state(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_state()
    monkeypatch.setattr(
        "kicad_mcp.tools.world.build_state_cached",
        lambda *_, **__: (fake, False),
    )
    monkeypatch.setattr(
        "kicad_mcp.tools.world._resolve_root_schematic", lambda: Path("/tmp/fake.kicad_sch")
    )

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_world_context", {"max_tokens": 800})
    toon = _toon(result)
    # La cabecera lleva kind (SCH) y snap; no hace falta envelope JSON.
    assert toon.startswith("SCH|v1|2c|2n|snap:1\n")
    assert "U1  STM32" in toon
    assert "GND: C1.2 U1.2" in toon


@pytest.mark.integration
async def test_world_context_full_against_fixture_001(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_world_context", {"max_tokens": 800})
    toon = _toon(result)

    lines = toon.splitlines()
    assert lines[0] == "SCH|v1|5c|6n|snap:1"
    # Todos los refs de 001 aparecen como líneas de [C].
    assert any(line.startswith("U1  ") for line in lines)
    assert any(line.startswith("R2  ") for line in lines)
    # SDA net completa: {R1.2, U1.3, J1.3} en orden natural.
    assert "SDA: J1.3 R1.2 U1.3" in toon
    # Sin degradación.
    assert "[DEGRADADO]" not in toon


@pytest.mark.integration
async def test_world_context_with_focus_hides_far_components(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Con focus en J1 y radio pequeño en fixture 003, componentes lejanos van al summary."""
    project = mirror_fixture(FIXTURES / "003_grande", tmp_path / "003")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "get_world_context",
            {"max_tokens": 500, "focus_ref": "J1", "radius_mm": 15.0},
        )
    toon = _toon(result)
    assert "[FUERA_DE_AREA]" in toon, "el bloque de resumen debería aparecer con focus+radius"
    # Debe declarar degradación en la línea final.
    assert "[DEGRADADO]" in toon
    assert "fuera_de_area" in toon
    # J1 (el foco) sigue apareciendo con su línea [C] completa.
    lines = toon.splitlines()
    j1_lines = [line for line in lines if line.startswith("J1  ")]
    assert len(j1_lines) == 1, "J1 debe aparecer una vez como componente completo"
    # A este nivel de degradación (probablemente sin omit_pos), J1 muestra POS.
    assert " x" in j1_lines[0]
