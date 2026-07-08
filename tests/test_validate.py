"""Tests de las tools ``run_erc`` y ``run_drc``.

- ``unit``: filtro por severidad sobre un ``RulesReport`` sintético.
- ``integration``: ERC contra 001/002 (esperado en ``erc_expected`` del
  ground_truth) y DRC contra el proyecto real 004.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.rules import Item, RulesReport, Violation, filter_by_min_severity
from kicad_mcp.server import create_server

FIXTURES = Path(__file__).parent / "fixtures"


def _parse(result: CallToolResult) -> dict[str, Any]:
    assert result.isError is False, f"error: {result}"
    assert len(result.content) == 1
    block = result.content[0]
    assert isinstance(block, TextContent)
    return json.loads(block.text)


@pytest.mark.unit
def test_filter_by_min_severity_drops_lower() -> None:
    report = RulesReport(
        violations=(
            Violation(rule="a", severity="error", message="e", items=(Item(None, None, None),)),
            Violation(rule="b", severity="warning", message="w", items=()),
            Violation(rule="c", severity="info", message="i", items=()),
        ),
        counts={"error": 1, "warning": 1, "info": 1},
        coordinate_units="mm",
        kicad_version="10.0.4",
    )
    filtered = filter_by_min_severity(report, "warning")
    assert [v.severity for v in filtered.violations] == ["error", "warning"]
    assert filtered.counts == {"error": 1, "warning": 1, "info": 0}


@pytest.mark.integration
@pytest.mark.parametrize("fixture", ["001_basico", "002_medio"])
async def test_run_erc_matches_erc_expected(
    monkeypatch: pytest.MonkeyPatch, fixture: str
) -> None:
    project = FIXTURES / fixture
    gt = json.loads((project / "ground_truth.json").read_text())
    expected = gt["erc_expected"]
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("run_erc", {"min_severity": "warning"})
    payload = _parse(result)

    assert payload["counts"].get("error", 0) == expected["error"], fixture
    assert payload["counts"].get("warning", 0) == expected["warning"], fixture
    assert payload["kicad_version"].startswith("10."), payload["kicad_version"]


@pytest.mark.integration
async def test_run_erc_min_severity_error_filters_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = FIXTURES / "001_basico"
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("run_erc", {"min_severity": "error"})
    payload = _parse(result)
    assert payload["counts"].get("warning", 0) == 0
    assert payload["counts"].get("error", 0) >= 1


@pytest.mark.integration
async def test_run_drc_reports_violations_on_real_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DRC contra el .kicad_pcb real (004_real): debe correr y devolver counts."""
    project = FIXTURES / "004_real"
    if not (project / "video.kicad_pcb").is_file():
        pytest.skip("fixture 004_real no disponible")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("run_drc", {"min_severity": "warning"})
    payload = _parse(result)
    # No asertamos números exactos: DRC contra un proyecto real varía por
    # versión de KiCad. Solo que el reporte esté bien formado.
    assert "counts" in payload
    assert "violations" in payload
    assert isinstance(payload["violations"], list)
    if payload["violations"]:
        first = payload["violations"][0]
        assert {"rule", "severity", "message", "items"} <= set(first.keys())
