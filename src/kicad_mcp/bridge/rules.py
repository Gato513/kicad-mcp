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
from collections import Counter
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
    # Descripción cruda del ítem tal como la emite kicad-cli (p. ej.
    # "PTH pad 22 [/TVRAM5] of U19"). Lleva net + objeto inline — es la vía
    # más barata de exponer "nets/objetos involucrados" (F-10, D-12.6) sin
    # re-parsear formatos que varían por tipo de violación.
    desc: str | None = None


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
    # Ítems del ratsnest sin conectar (``unconnected_items`` del DRC json).
    # 0 para ERC. ``route_board`` (D-14.2) lo usa como total del ratsnest:
    # pre-route = conexiones a rutear, post-route = restantes (idealmente 0).
    unconnected: int = 0


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
        desc=desc or None,
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


# Ítems cuyo ``desc`` contiene esto describen el borde del board (el gráfico
# Edge.Cuts), no el cobre ofensor — ver ``_reorder_edge_clearance_items``.
_EDGE_CUTS_MARKER: Final = "Edge.Cuts"


def _reorder_edge_clearance_items(rule: str, items: tuple[Item, ...]) -> tuple[Item, ...]:
    """En ``copper_edge_clearance``, KiCad siempre reporta el ítem Edge.Cuts
    PRIMERO (sesión 17, P2.5 — verificado con ``kicad-cli pcb drc`` real: el
    primer ítem es ``"Segment on Edge.Cuts"`` con la posición de un punto del
    borde — NO necesariamente ``[0,0]``, pero siempre inútil para ubicar el
    cobre real; el segundo ítem, ``"Track [...] on F.Cu"``/``"Pad ... of
    U1"``, sí trae la posición del ofensor). Los consumidores (p. ej.
    ``tools/validate.py::_sample_of``) toman ``items[0].pos`` como
    representativo de la violación, así que reordenamos acá — en el origen —
    para que el primer ítem sea siempre el cobre real, no el borde.
    """
    if rule != "copper_edge_clearance":
        return items
    non_edge = [it for it in items if not (it.desc and _EDGE_CUTS_MARKER in it.desc)]
    if not non_edge:
        return items
    edge = [it for it in items if it.desc and _EDGE_CUTS_MARKER in it.desc]
    return tuple(non_edge + edge)


def _build_report(
    payload: dict[str, Any], iterator: Iterable[dict[str, Any]], *, unconnected: int = 0
) -> RulesReport:
    violations: list[Violation] = []
    counts: dict[str, int] = {}
    for v in iterator:
        severity = str(v.get("severity", "warning"))
        counts[severity] = counts.get(severity, 0) + 1
        rule = str(v.get("type", "unknown"))
        items = tuple(_extract_item(i) for i in v.get("items", []))
        items = _reorder_edge_clearance_items(rule, items)
        violations.append(
            Violation(
                rule=rule,
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
        unconnected=unconnected,
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
                hint=(completed.stderr or "").strip()[:200] or f"returncode={completed.returncode}",
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
                hint=(completed.stderr or "").strip()[:200] or f"returncode={completed.returncode}",
            )
        payload = json.loads(tmp_path.read_text(encoding="utf-8"))
    finally:
        tmp_path.unlink(missing_ok=True)
    unconnected = len(payload.get("unconnected_items", []))
    return _build_report(payload, _iter_drc_violations(payload), unconnected=unconnected)


_POS_ROUND_MM: Final = 1  # ndigits para round() -> tolerancia de 0.1mm


def _violation_identity(v: Violation) -> tuple[str, tuple[float, float] | None, tuple[str, ...]]:
    """Identidad de una violación DRC (F-D3-03, sesión 21 — fix de
    ``route_board.drc.err_introducidos``, que comparaba conteos totales en
    vez de identidad: ``docs/dogfooding/dogfood3-fricciones.md`` F-03, donde
    56 ``unconnected_items`` pre-ruteo y 56 ``clearance``/``hole_clearance``/
    ``copper_edge_clearance`` post-ruteo daban ``err_introducidos:0`` por
    coincidencia numérica de totales, con composición 100% distinta).

    ``(rule, pos_redondeada_0.1mm, items_ordenados)``. La posición se
    redondea a 0.1mm: un track ofensor que se re-rutea puede desplazarse
    levemente sin ser, en la práctica, una violación "distinta" — tolerancia
    elegida por ser el mismo orden de magnitud que la resolución típica de
    grid de KiCad (no una medición exacta de "misma violación", sino un
    balance documentado entre falsos positivos por ruido geométrico y falsos
    negativos por colapsar violaciones realmente distintas). ``items`` usa
    ``Item.desc`` (ya trae ref+net inline, ver ``_extract_item``), ordenado
    para que el orden de reporte de ``kicad-cli`` no afecte la igualdad.
    """
    pos = v.items[0].pos if v.items else None
    pos_rounded = (round(pos[0], _POS_ROUND_MM), round(pos[1], _POS_ROUND_MM)) if pos else None
    item_keys = tuple(sorted(it.desc or "" for it in v.items))
    return (v.rule, pos_rounded, item_keys)


def diff_violations(
    pre: tuple[Violation, ...], post: tuple[Violation, ...]
) -> tuple[int, int, dict[str, int]]:
    """Compara violaciones DRC pre/post-route por IDENTIDAD, no por resta de
    totales (fix F-D3-03). Sólo severidad ``error`` — mismo criterio que
    ``err_preexistentes``/``err_post`` en ``route_board``.

    Devuelve ``(introducidas, resueltas, por_tipo_introducidos)``:
    - ``introducidas``: violaciones en ``post`` cuya identidad no estaba (o
      estaba menos veces) en ``pre``.
    - ``resueltas``: violaciones en ``pre`` cuya identidad ya no está (o está
      menos veces) en ``post`` — bonus: cuántas violaciones pre-route se
      resolvieron con el ruteo.
    - ``por_tipo_introducidos``: desglose de "introducidas" por ``rule``.

    Multiset (``collections.Counter``), no ``set``: preserva duplicados
    genuinos — dos violaciones distintas con la misma identidad cuentan dos
    veces, no colapsan en una.
    """
    pre_ids = Counter(_violation_identity(v) for v in pre if v.severity == "error")
    post_ids = Counter(_violation_identity(v) for v in post if v.severity == "error")
    introduced = post_ids - pre_ids
    resolved = pre_ids - post_ids
    por_tipo: dict[str, int] = {}
    for identity, count in introduced.items():
        por_tipo[identity[0]] = por_tipo.get(identity[0], 0) + count
    return sum(introduced.values()), sum(resolved.values()), por_tipo


def filter_by_min_severity(report: RulesReport, min_severity: str) -> RulesReport:
    """Filtra las violaciones cuya severidad sea ≥ ``min_severity``."""
    threshold = _SEVERITY_ORDER.get(min_severity, 0)
    kept = tuple(v for v in report.violations if _SEVERITY_ORDER.get(v.severity, 0) >= threshold)
    counts = {s: 0 for s in report.counts}
    for v in kept:
        counts[v.severity] = counts.get(v.severity, 0) + 1
    return RulesReport(
        violations=kept,
        counts=counts,
        coordinate_units=report.coordinate_units,
        kicad_version=report.kicad_version,
        unconnected=report.unconnected,
    )
