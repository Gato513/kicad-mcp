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
from kicad_mcp.logging_config import estimate_tokens
from kicad_mcp.server import create_server
from kicad_mcp.tools.validate import (
    _filter_drc,
    paginate_drc_detail,
    summarize_drc,
)
from tests.conftest import mirror_fixture

FIXTURES = Path(__file__).parent / "fixtures"


def _viol(rule: str, severity: str, n_items: int = 2, msg: str = "") -> Violation:
    """Violación sintética con items que llevan pos + desc (como el DRC real)."""
    items = tuple(
        Item(
            ref=f"U{i}",
            net=f"/NET{i}",
            pos=(100.0 + i, 50.0 + i),
            desc=f"PTH pad {i} [/NET{i}] of U{i}",
        )
        for i in range(n_items)
    )
    return Violation(rule=rule, severity=severity, message=msg or f"{rule} violation", items=items)


def _report(violations: tuple[Violation, ...]) -> RulesReport:
    counts: dict[str, int] = {}
    for v in violations:
        counts[v.severity] = counts.get(v.severity, 0) + 1
    return RulesReport(
        violations=violations,
        counts=counts,
        coordinate_units="mm",
        kicad_version="10.0.4",
    )


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


# --- run_drc presupuestado / paginado (F-10, D-12.6) -------------------------


@pytest.mark.unit
def test_summarize_drc_groups_by_type_with_samples() -> None:
    report = _report(
        tuple(_viol("clearance", "error") for _ in range(8))
        + tuple(_viol("unconnected_items", "warning") for _ in range(3))
        + (_viol("hole_to_hole", "error"),)
    )
    summary = summarize_drc(report)
    assert summary["mode"] == "summary"
    assert summary["total"] == 12
    # Ordenado por frecuencia desc.
    assert [t["type"] for t in summary["by_type"]] == [
        "clearance",
        "unconnected_items",
        "hole_to_hole",
    ]
    clearance = summary["by_type"][0]
    assert clearance["count"] == 8
    assert clearance["severity"] == "error"
    # N=5 muestras por tipo como máximo.
    assert len(clearance["samples"]) == 5
    # Cada muestra lleva coords + objetos/nets (D-12.6).
    assert "pos" in clearance["samples"][0]
    assert "items" in clearance["samples"][0]
    assert "/NET" in clearance["samples"][0]["items"][0]


@pytest.mark.unit
def test_summarize_drc_within_token_budget() -> None:
    """El resumen con cientos de violaciones cae en ≤2 000 tok (D-12.6)."""
    viols = (
        tuple(
            _viol("clearance", "error", msg="Clearance violation (min 0.2 mm; actual 0.07 mm)")
            for _ in range(150)
        )
        + tuple(_viol("solder_mask_bridge", "warning") for _ in range(90))
        + tuple(_viol("lib_footprint_mismatch", "warning") for _ in range(60))
        + tuple(_viol("unconnected_items", "warning") for _ in range(43))
    )
    summary = summarize_drc(_report(viols))
    assert summary["total"] == 343
    tokens = estimate_tokens(json.dumps(summary, ensure_ascii=False))
    assert tokens <= 2000, f"resumen fuera de presupuesto: {tokens} tok"


@pytest.mark.unit
def test_filter_drc_exclude_types_excludes_from_payload() -> None:
    """exclude_types quita del payload y recomputa total/counts (D-12.6)."""
    report = _report(
        tuple(_viol("clearance", "error") for _ in range(5))
        + tuple(_viol("unconnected_items", "warning") for _ in range(4))
    )
    filtered = _filter_drc(report, "warning", ["unconnected_items"])
    assert all(v.rule != "unconnected_items" for v in filtered.violations)
    assert len(filtered.violations) == 5
    assert filtered.counts == {"error": 5}
    summary = summarize_drc(filtered)
    assert summary["total"] == 5
    assert [t["type"] for t in summary["by_type"]] == ["clearance"]


@pytest.mark.unit
def test_filter_drc_min_severity_excludes_warnings() -> None:
    report = _report((_viol("clearance", "error"), _viol("unconnected_items", "warning")))
    filtered = _filter_drc(report, "error", None)
    assert len(filtered.violations) == 1
    assert filtered.violations[0].severity == "error"


@pytest.mark.unit
def test_paginate_drc_detail_pages_one_type() -> None:
    report = _report(
        tuple(_viol("clearance", "error") for _ in range(25))
        + tuple(_viol("unconnected_items", "warning") for _ in range(3))
    )
    page = paginate_drc_detail(report, "clearance", offset=0, limit=20)
    assert page["mode"] == "detail"
    assert page["type"] == "clearance"
    assert page["total"] == 25
    assert page["returned"] == 20
    assert len(page["violations"]) == 20
    # Violaciones completas: items con desc/ref/net/pos.
    first_item = page["violations"][0]["items"][0]
    assert {"desc", "ref", "net", "pos"} <= set(first_item.keys())
    # Hint de próxima página.
    assert "offset=20" in page["hint"]

    page2 = paginate_drc_detail(report, "clearance", offset=20, limit=20)
    assert page2["returned"] == 5
    assert "hint" not in page2 or "offset" not in page2.get("hint", "")


@pytest.mark.unit
def test_paginate_drc_detail_unknown_type_lists_available() -> None:
    report = _report((_viol("clearance", "error"), _viol("hole_to_hole", "error")))
    page = paginate_drc_detail(report, "nonexistent", offset=0, limit=20)
    assert page["total"] == 0
    assert page["violations"] == []
    assert "clearance" in page["hint"] and "hole_to_hole" in page["hint"]


@pytest.mark.integration
@pytest.mark.parametrize("fixture", ["001_basico", "002_medio"])
async def test_run_erc_matches_erc_expected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fixture: str
) -> None:
    gt = json.loads((FIXTURES / fixture / "ground_truth.json").read_text())
    expected = gt["erc_expected"]
    project = mirror_fixture(FIXTURES / fixture, tmp_path / fixture)
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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("run_erc", {"min_severity": "error"})
    payload = _parse(result)
    assert payload["counts"].get("warning", 0) == 0
    assert payload["counts"].get("error", 0) >= 1


@pytest.mark.integration
async def test_run_drc_reports_violations_on_real_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """DRC contra el .kicad_pcb real (004_real): debe correr y devolver counts."""
    if not (FIXTURES / "004_real" / "video.kicad_pcb").is_file():
        pytest.skip("fixture 004_real no disponible")
    project = mirror_fixture(FIXTURES / "004_real", tmp_path / "004")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("run_drc", {"min_severity": "warning"})
    payload = _parse(result)
    # No asertamos números exactos: DRC contra un proyecto real varía por
    # versión de KiCad. Solo que el RESUMEN (F-10) esté bien formado y quepa
    # en el presupuesto de tokens (≤2 000, D-12.6).
    assert payload["mode"] == "summary"
    assert "counts" in payload
    assert "total" in payload
    assert isinstance(payload["by_type"], list)
    tokens = estimate_tokens(json.dumps(payload, ensure_ascii=False))
    assert tokens <= 2000, f"resumen DRC fuera de presupuesto: {tokens} tok"
    if payload["by_type"]:
        first = payload["by_type"][0]
        assert {"type", "count", "severity"} <= set(first.keys())


@pytest.mark.integration
async def test_run_drc_detail_and_exclude_on_real_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Detalle paginado + exclude_types contra el board real (F-10, D-12.6)."""
    if not (FIXTURES / "004_real" / "video.kicad_pcb").is_file():
        pytest.skip("fixture 004_real no disponible")
    project = mirror_fixture(FIXTURES / "004_real", tmp_path / "004")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        summary_res = await client.call_tool("run_drc", {"min_severity": "warning"})
        summary = _parse(summary_res)
        if not summary["by_type"]:
            pytest.skip("el board no reportó violaciones; nada que paginar")
        top_type = summary["by_type"][0]["type"]
        total_top = summary["by_type"][0]["count"]

        # exclude del tipo más frecuente reduce el total.
        excl_res = await client.call_tool(
            "run_drc", {"min_severity": "warning", "exclude_types": [top_type]}
        )
        excl = _parse(excl_res)
        assert excl["total"] == summary["total"] - total_top
        assert all(t["type"] != top_type for t in excl["by_type"])

        # detalle paginado de ese tipo.
        detail_res = await client.call_tool(
            "run_drc", {"detail_type": top_type, "offset": 0, "limit": 10}
        )
        detail = _parse(detail_res)
        assert detail["mode"] == "detail"
        assert detail["type"] == top_type
        assert detail["returned"] == min(10, total_top)
