"""Wrappers de ``kicad-cli sch erc`` / ``pcb drc`` con salida normalizada.

Formato normalizado por violación (catálogo, `docs/specs/tool-catalog.md`):
``{rule, severity, message, items: [{ref?, net?, pos?}]}``.

Reglas:
- Nunca ``--exit-code-violations``: violaciones NO son error de la herramienta.
  Exit code ≠ 0 significa que kicad-cli falló.
- Subprocess con lista de argumentos, ``shell=False``, timeout duro.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from ..errors import ErrorCode, KicadMcpError

_TIMEOUT_S: Final = 90.0
_SEVERITY_ORDER: Final = {"error": 3, "warning": 2, "info": 1, "exclusion": 0}

_REF_RE: Final = re.compile(r"(?:Symbol|Footprint|Component)\s+([A-Za-z_]+\d+)")
_NET_RE: Final = re.compile(r'[Nn]et\s+"([^"]+)"')


@dataclass(frozen=True)
class Item:
    ref: str | None
    net: str | None
    pos: tuple[float, float] | None


@dataclass(frozen=True)
class Violation:
    rule: str
    severity: str
    message: str
    items: tuple[Item, ...]


@dataclass(frozen=True)
class RulesReport:
    violations: tuple[Violation, ...]
    counts: dict[str, int]
    coordinate_units: str
    kicad_version: str


def _extract_item(raw: dict[str, Any]) -> Item:
    desc = str(raw.get("description", ""))
    ref_match = _REF_RE.search(desc)
    net_match = _NET_RE.search(desc)
    pos_raw = raw.get("pos")
    pos: tuple[float, float] | None = None
    if isinstance(pos_raw, dict):
        try:
            pos = (float(pos_raw.get("x", 0)), float(pos_raw.get("y", 0)))
        except (TypeError, ValueError):
            pos = None
    return Item(
        ref=ref_match.group(1) if ref_match else None,
        net=net_match.group(1) if net_match else None,
        pos=pos,
    )


def _iter_erc_violations(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for sheet in payload.get("sheets", []):
        yield from sheet.get("violations", [])


def _iter_drc_violations(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for v in payload.get("violations", []):
        yield v
    for v in payload.get("unconnected_items", []):
        # Los ítems desconectados son un tipo especial de violación de DRC.
        yield {**v, "severity": v.get("severity", "warning")}


def _build_report(payload: dict[str, Any], iterator: Iterable[dict[str, Any]]) -> RulesReport:
    violations: list[Violation] = []
    counts: dict[str, int] = {}
    for v in iterator:
        severity = str(v.get("severity", "warning"))
        counts[severity] = counts.get(severity, 0) + 1
        items = tuple(_extract_item(i) for i in v.get("items", []))
        violations.append(
            Violation(
                rule=str(v.get("type", "unknown")),
                severity=severity,
                message=str(v.get("description", "")),
                items=items,
            )
        )
    return RulesReport(
        violations=tuple(violations),
        counts=counts,
        coordinate_units=str(payload.get("coordinate_units", "mm")),
        kicad_version=str(payload.get("kicad_version", "")),
    )


def _run_kicad_cli(
    args: list[str], *, action: str
) -> tuple[dict[str, Any], subprocess.CompletedProcess[str]]:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_MISSING,
            message="kicad-cli no está en PATH.",
            hint="Instala KiCad ≥ 9.0 o exporta PATH con kicad-cli.",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message=f"kicad-cli {action} excedió {_TIMEOUT_S:.0f}s.",
            hint="Reintentar; reducir alcance del proyecto si persiste.",
        ) from exc
    return {}, completed


def run_erc(sch_path: Path) -> RulesReport:
    """Corre ERC con salida ``json`` y devuelve el reporte normalizado."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=str(sch_path.parent)
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        args = [
            "kicad-cli",
            "sch",
            "erc",
            "--format",
            "json",
            "--severity-all",
            "-o",
            str(tmp_path),
            str(sch_path),
        ]
        _, completed = _run_kicad_cli(args, action="ERC")
        if completed.returncode != 0:
            raise KicadMcpError(
                code=ErrorCode.KICAD_CLI_FAILED,
                message="kicad-cli devolvió error al correr ERC.",
                hint=(completed.stderr or "").strip()[:200]
                or f"returncode={completed.returncode}",
            )
        payload = json.loads(tmp_path.read_text(encoding="utf-8"))
    finally:
        tmp_path.unlink(missing_ok=True)
    return _build_report(payload, _iter_erc_violations(payload))


def run_drc(pcb_path: Path) -> RulesReport:
    """Corre DRC con salida ``json`` y devuelve el reporte normalizado."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=str(pcb_path.parent)
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        args = [
            "kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "-o",
            str(tmp_path),
            str(pcb_path),
        ]
        _, completed = _run_kicad_cli(args, action="DRC")
        if completed.returncode != 0:
            raise KicadMcpError(
                code=ErrorCode.KICAD_CLI_FAILED,
                message="kicad-cli devolvió error al correr DRC.",
                hint=(completed.stderr or "").strip()[:200]
                or f"returncode={completed.returncode}",
            )
        payload = json.loads(tmp_path.read_text(encoding="utf-8"))
    finally:
        tmp_path.unlink(missing_ok=True)
    return _build_report(payload, _iter_drc_violations(payload))


def filter_by_min_severity(report: RulesReport, min_severity: str) -> RulesReport:
    """Filtra las violaciones cuya severidad sea ≥ ``min_severity``."""
    threshold = _SEVERITY_ORDER.get(min_severity, 0)
    kept = tuple(
        v for v in report.violations if _SEVERITY_ORDER.get(v.severity, 0) >= threshold
    )
    counts = {s: 0 for s in report.counts}
    for v in kept:
        counts[v.severity] = counts.get(v.severity, 0) + 1
    return RulesReport(
        violations=kept,
        counts=counts,
        coordinate_units=report.coordinate_units,
        kicad_version=report.kicad_version,
    )
