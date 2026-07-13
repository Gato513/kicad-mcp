"""Tools de la categoría ``validate``: ``run_erc`` y ``run_drc`` (MVP).

Ver `docs/specs/tool-catalog.md §validate`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..bridge.rules import RulesReport, Violation, filter_by_min_severity, run_drc, run_erc
from ..errors import ErrorCode, KicadMcpError
from ..logging_config import estimate_tokens, log_tool_call, tool_call_timer
from ..tools.world import _resolve_root_schematic

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# Presupuesto de tokens del DRC (F-10, D-12.6). El modo default RESUMEN debe
# caber en ≤2 000 tok con cientos de violaciones: agrupamos por tipo, contamos,
# y damos N muestras compactas por tipo. El detalle completo se pide por páginas.
_DRC_SAMPLES_PER_TYPE = 5
_DRC_ITEM_DESC_MAX = 56
_DRC_MSG_MAX = 100
_DRC_SAMPLE_ITEMS_MAX = 2
_DRC_DETAIL_LIMIT_MAX = 100
_SEVERITY_ORDER: dict[str, int] = {"error": 3, "warning": 2, "info": 1, "exclusion": 0}


def _trunc(text: str, limit: int) -> str:
    """Primera línea de ``text`` recortada a ``limit`` chars con ``…`` si excede."""
    head = text.strip().splitlines()[0] if text.strip() else ""
    return head if len(head) <= limit else head[: limit - 1] + "…"


def _filter_drc(
    report: RulesReport, min_severity: str, exclude_types: list[str] | None
) -> RulesReport:
    """Aplica severidad mínima + ``exclude_types``, EXCLUYENDO de verdad del payload.

    ``exclude_types`` quita las violaciones de esos tipos y recomputa los
    conteos, de modo que ``total`` y ``counts`` reflejan lo que el agente ve
    (D-12.6: el filtro debe excluir del payload, no sólo ocultar).
    """
    filtered = filter_by_min_severity(report, min_severity)
    if not exclude_types:
        return filtered
    excluded = set(exclude_types)
    kept = tuple(v for v in filtered.violations if v.rule not in excluded)
    counts: dict[str, int] = {}
    for v in kept:
        counts[v.severity] = counts.get(v.severity, 0) + 1
    return RulesReport(
        violations=kept,
        counts=counts,
        coordinate_units=filtered.coordinate_units,
        kicad_version=filtered.kicad_version,
    )


def _max_severity(violations: list[Violation]) -> str:
    """Severidad más alta presente en un grupo (para la cabecera por tipo)."""
    if not violations:
        return "warning"
    return max(violations, key=lambda v: _SEVERITY_ORDER.get(v.severity, 0)).severity


def _sample_of(violation: Violation) -> dict[str, Any]:
    """Muestra compacta de una violación: coords + objetos/nets involucrados (D-12.6)."""
    sample: dict[str, Any] = {}
    first_pos = next((it.pos for it in violation.items if it.pos), None)
    if first_pos is not None:
        sample["pos"] = [round(first_pos[0], 3), round(first_pos[1], 3)]
    items = [
        _trunc(it.desc, _DRC_ITEM_DESC_MAX)
        for it in violation.items[:_DRC_SAMPLE_ITEMS_MAX]
        if it.desc
    ]
    if items:
        sample["items"] = items
    return sample


def summarize_drc(report: RulesReport) -> dict[str, Any]:
    """Resumen presupuestado del DRC (F-10, D-12.6, modo default).

    Agrupa por tipo de violación, ordena por frecuencia, y por cada tipo emite
    conteo, severidad, un mensaje representativo y hasta N muestras compactas
    (coords + objetos/nets). ``total``/``counts`` ya vienen filtrados.
    """
    groups: dict[str, list[Violation]] = {}
    for v in report.violations:
        groups.setdefault(v.rule, []).append(v)
    by_type: list[dict[str, Any]] = []
    for rule, vs in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        entry: dict[str, Any] = {
            "type": rule,
            "count": len(vs),
            "severity": _max_severity(vs),
        }
        rep_msg = next((v.message for v in vs if v.message), "")
        if rep_msg:
            entry["message"] = _trunc(rep_msg, _DRC_MSG_MAX)
        samples = [s for s in (_sample_of(v) for v in vs[:_DRC_SAMPLES_PER_TYPE]) if s]
        if samples:
            entry["samples"] = samples
        by_type.append(entry)
    return {
        "mode": "summary",
        "total": len(report.violations),
        "counts": report.counts,
        "coordinate_units": report.coordinate_units,
        "kicad_version": report.kicad_version,
        "by_type": by_type,
        "hint": (
            "detalle completo por páginas: run_drc(detail_type=<tipo>, offset=0, limit=20). "
            "Filtrá con exclude_types=[...] o min_severity='error'."
        ),
    }


def _full_violation(violation: Violation) -> dict[str, Any]:
    """Violación completa (sin recortes agresivos) para el modo detalle paginado."""
    return {
        "type": violation.rule,
        "severity": violation.severity,
        "message": violation.message,
        "items": [
            {
                "desc": it.desc,
                "ref": it.ref,
                "net": it.net,
                "pos": [round(it.pos[0], 3), round(it.pos[1], 3)] if it.pos else None,
            }
            for it in violation.items
        ],
    }


def paginate_drc_detail(
    report: RulesReport, detail_type: str, offset: int, limit: int
) -> dict[str, Any]:
    """Página de violaciones COMPLETAS de UN tipo (F-10, D-12.6, modo detalle)."""
    vs = [v for v in report.violations if v.rule == detail_type]
    total = len(vs)
    page = vs[offset : offset + limit]
    payload: dict[str, Any] = {
        "mode": "detail",
        "type": detail_type,
        "total": total,
        "offset": offset,
        "limit": limit,
        "returned": len(page),
        "coordinate_units": report.coordinate_units,
        "kicad_version": report.kicad_version,
        "violations": [_full_violation(v) for v in page],
    }
    if total == 0:
        available = sorted({v.rule for v in report.violations})
        payload["hint"] = (
            f"No hay violaciones de tipo {detail_type!r} (tras filtros). "
            f"Tipos disponibles: {', '.join(available) or 'ninguno'}."
        )
    elif offset + limit < total:
        payload["hint"] = f"hay más: pedí offset={offset + limit} para la próxima página."
    return payload


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
        description=(
            "DRC del PCB presupuestado: resumen por tipo (default) o detalle "
            "paginado de un tipo (detail_type + offset/limit)"
        ),
    )
    def run_drc_tool(
        min_severity: str = "warning",
        exclude_types: list[str] | None = None,
        detail_type: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        # F-10 (D-12.6): la respuesta cruda medía 18 956 tok / 42 s (sesión 11).
        # Rediseño: modo default = RESUMEN por tipo (≤2 000 tok); modo detalle
        # = una página de violaciones completas de UN tipo. exclude_types y
        # min_severity excluyen de verdad del payload. G3 NO consume esta tool
        # (usa bridge.rules.run_drc directo) — F2 intacto.
        with tool_call_timer() as timer:
            if offset < 0:
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"offset debe ser ≥ 0 (recibido {offset}).",
                    hint="Empezá en offset=0 y avanzá por páginas.",
                )
            if not (1 <= limit <= _DRC_DETAIL_LIMIT_MAX):
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"limit debe estar en [1, {_DRC_DETAIL_LIMIT_MAX}] (recibido {limit}).",
                    hint=f"Usá un limit razonable, p. ej. 20 (máx {_DRC_DETAIL_LIMIT_MAX}).",
                )
            pcb = _resolve_pcb()
            report = run_drc(pcb)
            filtered = _filter_drc(report, min_severity, exclude_types)
            if detail_type is not None:
                payload = paginate_drc_detail(filtered, detail_type, offset, limit)
                mode = "detail"
            else:
                payload = summarize_drc(filtered)
                mode = "summary"
        log_tool_call(
            tool_name="run_drc",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
            extra={
                "min_severity": min_severity,
                "mode": mode,
                "total": len(filtered.violations),
                "excluded": exclude_types or [],
                "detail_type": detail_type,
            },
        )
        return payload
