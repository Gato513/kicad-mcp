"""Tests de las tools ``export_bom``, ``export_netlist``, ``export_render``.

- ``unit``: valida ``PATH_OUTSIDE_PROJECT`` y ``INVALID_PARAMS`` con state
  builder mockeado.
- ``integration``: exporta contra fixture 001; verifica que el archivo se
  crea dentro de la raíz del proyecto y tiene bytes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.server import create_server
from tests.conftest import mirror_fixture

FIXTURES = Path(__file__).parent / "fixtures"


def _parse(result: CallToolResult) -> dict[str, Any]:
    return json.loads(result.content[0].text) if not result.isError else {"error": result}


def _error_text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


@pytest.mark.unit
async def test_export_render_rejects_invalid_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(FIXTURES / "001_basico"))
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_render", {"kind": "dxf"})
    assert result.isError
    assert "INVALID_PARAMS" in _error_text(result)


@pytest.mark.unit
async def test_export_render_pcb_png_returns_invalid_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(FIXTURES / "001_basico"))
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_render", {"kind": "pcb_png"})
    assert result.isError
    text = _error_text(result)
    assert "INVALID_PARAMS" in text
    assert "pcb_pdf" in text


@pytest.mark.unit
async def test_export_bom_rejects_output_outside_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(FIXTURES / "001_basico"))
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_bom", {"output_path": "/etc/passwd_bom.csv"})
    assert result.isError
    assert "PATH_OUTSIDE_PROJECT" in _error_text(result)


@pytest.mark.integration
async def test_export_bom_writes_csv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_copy = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project_copy))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_bom", {"output_path": "out/bom.csv"})
    payload = _parse(result)
    assert not result.isError, payload
    bom = project_copy / "out" / "bom.csv"
    assert bom.is_file()
    assert bom.stat().st_size > 0
    assert payload["bytes"] == bom.stat().st_size


@pytest.mark.integration
async def test_export_netlist_writes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_copy = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project_copy))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_netlist", {"output_path": "out/net.net"})
    payload = _parse(result)
    assert not result.isError, payload
    assert (project_copy / "out" / "net.net").is_file()
    assert payload["bytes"] > 0


@pytest.mark.integration
async def test_export_render_sch_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_copy = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project_copy))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "export_render", {"kind": "sch_pdf", "output_path": "renders/sch.pdf"}
        )
    payload = _parse(result)
    assert not result.isError, payload
    pdf = project_copy / "renders" / "sch.pdf"
    assert pdf.is_file()
    with pdf.open("rb") as f:
        assert f.read(4) == b"%PDF"
