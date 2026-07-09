"""Gate G3 — bloquea exports de fabricación cuando el DRC no está limpio.

Contrato F2 (ADR-0003): el gate corre DRC sobre el ``.kicad_pcb``. Si hay
al menos una violación con severidad ``error``, la exportación se
detiene con ``EXPORT_BLOCKED_BY_DRC``; el hint incluye el conteo total y
un resumen de las **3 primeras violaciones** (formato del catálogo,
tool-catalog.md §Taxonomía).

No modifica lógica ni umbrales sin aprobación humana (F2). Este archivo
es solo la ligadura del check a la tool ``export_manufacturing``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..bridge.rules import RulesReport
from ..bridge.rules import run_drc as _run_drc_real
from ..errors import ErrorCode, KicadMcpError


class _DrcRunner(Protocol):
    def __call__(self, pcb_path: Path) -> RulesReport: ...


def _summarize_first_errors(report: RulesReport, limit: int = 3) -> str:
    errors = [v for v in report.violations if v.severity == "error"]
    parts: list[str] = []
    for v in errors[:limit]:
        head = v.message.strip().splitlines()[0][:120] if v.message else v.rule
        parts.append(f"{v.rule}: {head}")
    return " | ".join(parts) if parts else "(sin detalle)"


def check_drc_clean(pcb_path: Path, *, drc_runner: _DrcRunner | None = None) -> None:
    """Corre DRC y bloquea si hay violaciones ``error``.

    ``pcb_path`` debe estar canonicalizada por el llamador. ``drc_runner``
    permite inyectar un fake en tests unit — por default usa
    ``bridge.rules.run_drc``.
    """
    runner = drc_runner or _run_drc_real
    report = runner(pcb_path)
    error_count = sum(1 for v in report.violations if v.severity == "error")
    if error_count == 0:
        return
    hint = f"{error_count} errores DRC. {_summarize_first_errors(report)}"
    raise KicadMcpError(
        code=ErrorCode.EXPORT_BLOCKED_BY_DRC,
        message="Exportación bloqueada: el PCB tiene violaciones DRC de severidad error.",
        hint=hint,
    )
