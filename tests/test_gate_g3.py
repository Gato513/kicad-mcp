"""Tests unit del Gate G3 (bloqueo por DRC sucio).

- Caso limpio: 0 violaciones ``error`` ⇒ ``check_drc_clean`` no lanza.
- Caso sucio: N violaciones ``error`` ⇒ ``EXPORT_BLOCKED_BY_DRC`` con
  conteo y las 3 primeras violaciones en el hint (contrato del catálogo).

Sin dependencia de kicad-cli: DRC mockeado.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.bridge.rules import RulesReport, Violation
from kicad_mcp.errors import ErrorCode, KicadMcpError
from kicad_mcp.gates.g3 import check_drc_clean


def _report(*violations: Violation) -> RulesReport:
    counts: dict[str, int] = {}
    for v in violations:
        counts[v.severity] = counts.get(v.severity, 0) + 1
    return RulesReport(
        violations=violations,
        counts=counts,
        coordinate_units="mm",
        kicad_version="10.0.4",
    )


def _err(rule: str, message: str) -> Violation:
    return Violation(rule=rule, severity="error", message=message, items=())


def _warn(rule: str, message: str) -> Violation:
    return Violation(rule=rule, severity="warning", message=message, items=())


@pytest.mark.unit
def test_g3_passes_on_clean_report() -> None:
    report = _report(_warn("clearance", "warning_only"))

    def runner(_: Path) -> RulesReport:
        return report

    # No lanza. Ese es todo el contrato del caso limpio.
    check_drc_clean(Path("/fake.kicad_pcb"), drc_runner=runner)


@pytest.mark.unit
def test_g3_blocks_when_any_error_present() -> None:
    report = _report(
        _err("clearance", "Silk over pad — pin U1.5 vs F.SilkS"),
        _err("track_width", "Track width 0.15 mm below minimum 0.20 mm"),
        _err("copper_edge_clearance", "Copper too close to Edge.Cuts (0.12 mm < 0.30 mm)"),
        _err("hole_clearance", "Drill hole overlap between vias V3 and V4"),
        _warn("silk_clip", "silk clipped"),
    )

    def runner(_: Path) -> RulesReport:
        return report

    with pytest.raises(KicadMcpError) as excinfo:
        check_drc_clean(Path("/fake.kicad_pcb"), drc_runner=runner)

    assert excinfo.value.code is ErrorCode.EXPORT_BLOCKED_BY_DRC
    hint = excinfo.value.hint
    assert "4 errores DRC" in hint  # conteo total de errores (no warnings)
    # Las 3 primeras violaciones ``error``.
    assert "clearance" in hint
    assert "track_width" in hint
    assert "copper_edge_clearance" in hint
    # La 4ta NO debe entrar (límite del catálogo: 3).
    assert "hole_clearance" not in hint
