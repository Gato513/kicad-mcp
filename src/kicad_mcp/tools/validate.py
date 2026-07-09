"""Tools de la categoría ``validate``: ``run_erc`` y ``run_drc`` (MVP).

Ver `docs/specs/tool-catalog.md §validate`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..bridge.rules import RulesReport, filter_by_min_severity, run_drc, run_erc
from ..errors import ErrorCode, KicadMcpError
from ..logging_config import estimate_tokens, log_tool_call, tool_call_timer
from ..tools.world import _resolve_root_schematic

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _resolve_pcb() -> Path:
    """Determina el ``.kicad_pcb`` a partir del ``.kicad_sch`` activo."""
    sch = _resolve_root_schematic()
    pcb = sch.with_suffix(".kicad_pcb")
    if not pcb.is_file():
        raise KicadMcpError(
            code=ErrorCode.PROJECT_NOT_FOUND,
            message="No se encontró el .kicad_pcb del proyecto activo.",
            hint=f"Se buscaba {pcb.name} junto al esquemático.",
        )
    return pcb


def _serialize_report(report: RulesReport) -> dict[str, Any]:
    return {
        "counts": report.counts,
        "coordinate_units": report.coordinate_units,
        "kicad_version": report.kicad_version,
        "violations": [
            {
                "rule": v.rule,
                "severity": v.severity,
                "message": v.message,
                "items": [
                    {"ref": it.ref, "net": it.net, "pos": list(it.pos) if it.pos else None}
                    for it in v.items
                ],
            }
            for v in report.violations
        ],
    }


def register(mcp: FastMCP) -> None:
    """Registra ``run_erc`` y ``run_drc`` en la instancia FastMCP."""

    @mcp.tool(
        name="run_erc",
        description="ERC del esquemático, violaciones estructuradas",
    )
    def run_erc_tool(min_severity: str = "warning") -> dict[str, Any]:
        with tool_call_timer() as timer:
            sch = _resolve_root_schematic()
            report = run_erc(sch)
            filtered = filter_by_min_severity(report, min_severity)
            payload = _serialize_report(filtered)
        log_tool_call(
            tool_name="run_erc",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
            extra={"min_severity": min_severity, "total": len(filtered.violations)},
        )
        return payload

    @mcp.tool(
        name="run_drc",
        description="DRC del PCB, violaciones estructuradas",
    )
    def run_drc_tool(min_severity: str = "warning") -> dict[str, Any]:
        with tool_call_timer() as timer:
            pcb = _resolve_pcb()
            report = run_drc(pcb)
            filtered = filter_by_min_severity(report, min_severity)
            payload = _serialize_report(filtered)
        log_tool_call(
            tool_name="run_drc",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
            extra={"min_severity": min_severity, "total": len(filtered.violations)},
        )
        return payload
