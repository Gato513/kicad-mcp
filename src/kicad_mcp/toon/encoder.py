"""Encoder TOON v1.

Contrato en ``docs/specs/toon-v1.md``. Cubre:
- §2 (formato completo, sin degradación) — MVP sesión 01.
- §4 (degradación por presupuesto, 3 niveles + fallback) — MVP sesión 02.
- §3 (ΔTOON) — v0.3.

Frontera F1: los golden files bajo ``tests/golden/`` son la definición
ejecutable. Ante discrepancia entre este código y el golden, el golden manda.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Final

from ..errors import ErrorCode, KicadMcpError
from ..logging_config import estimate_tokens
from .schema import Component, NormalizedState, Pin

_STRUCTURAL_CHARS: Final = str.maketrans({">": "_", "|": "_", ":": "_"})
_CONTROL_RE: Final = re.compile(r"[\x00-\x1f\x7f]")
_MAX_FIELD_LEN: Final = 40
_NATURAL_SPLIT_RE: Final = re.compile(r"(\d+)")
_REF_PREFIX_RE: Final = re.compile(r"^([A-Za-z_]+)(\d+)$")

# ``docs/specs/toon-v1.md §4``: regex de nets de poder. En §2 la usamos también
# para ordenar (poder primero, resto alfabético).
_POWER_NET_RE: Final = re.compile(
    r"^(GND|VSS|AGND|DGND|PGND|VCC|VDD|VBUS|[0-9]+V[0-9]*|3V3|5V|12V|-?[0-9]+V)$",
    re.IGNORECASE,
)
_POWER_COLLAPSE_THRESHOLD: Final = 8  # spec §4 nivel 1: >8 miembros
_AREA_OK_THRESHOLD: Final = 20  # spec §3: umbral del bloque [AREA]

# Factor de seguridad sobre el estimador ``len/3.5`` (ADR-0004). El estimador
# es aproximado; sin margen, documentos que apenas caben terminan cortados en
# el tokenizador real. El golden 002 asume este margen (F1). Ver "Notas de
# implementación" de ADR-0004.
_BUDGET_SAFETY_FACTOR: Final = 0.9

# Heurística de inyección (§5.4): estos términos disparan el aviso final.
_SUSPICIOUS_RE: Final = re.compile(r"(?i)(ignore|system|instruction|prompt|you are)")

_CATEGORY_MAP: Final[dict[str, str]] = {
    "R": "resistencias",
    "C": "caps",
    "L": "inductores",
    "D": "diodos",
    "Q": "transistores",
    "Y": "cristales",
    "U": "ICs",
    "J": "conectores",
    "SW": "switches",
    "TP": "test_points",
    "K": "reles",
    "FB": "ferrites",
    "F": "fusibles",
    "BT": "baterias",
}


@dataclass(frozen=True)
class _Options:
    """Configuración interna del encoder (nunca expuesta al llamador)."""

    collapse_power: bool = False
    focus_ref: str | None = None
    radius_mm: float | None = None
    omit_pos: bool = False
    degrade_labels: tuple[str, ...] = field(default_factory=tuple)


def _sanitize(raw: str) -> tuple[str, bool]:
    """Sanea un string de entrada no confiable (§5). Devuelve ``(saneado, sospechoso)``."""
    cleaned = _CONTROL_RE.sub("_", raw)
    cleaned = cleaned.translate(_STRUCTURAL_CHARS)
    if len(cleaned) > _MAX_FIELD_LEN:
        cleaned = cleaned[: _MAX_FIELD_LEN - 1] + "…"
    suspicious = bool(_SUSPICIOUS_RE.search(cleaned))
    return cleaned, suspicious


def _natural_key(text: str) -> tuple[object, ...]:
    """Orden natural (``C1, C2, C10`` en vez de ``C1, C10, C2``)."""
    return tuple(
        int(part) if part.isdigit() else part.lower()
        for part in _NATURAL_SPLIT_RE.split(text)
        if part
    )


def _format_num(value: float) -> str:
    """``NUM`` del §2: mm con 1 decimal, sin ceros a la izquierda."""
    return f"{value:.1f}"


def _format_pin_ref(pin: Pin) -> str:
    """PIN_ID: número si existe; nombre solo si el símbolo no numera."""
    if pin.p.strip():
        return pin.p
    return pin.name or ""


def _encode_component_line(comp: Component, warnings: list[str], omit_pos: bool) -> str:
    ref, ref_flag = _sanitize(comp.ref)
    value, value_flag = _sanitize(comp.value)
    if ref_flag:
        warnings.append(f"{ref}.ref")
    if value_flag:
        warnings.append(f"{ref}.value")

    pin_tokens: list[str] = []
    # Orden de emisión = orden de entrada (los goldens 001/002 lo requieren).
    for pin in comp.pins:
        pin_id, pin_flag = _sanitize(_format_pin_ref(pin))
        if pin_flag:
            warnings.append(f"{ref}.pin[{pin_id}]")
        if pin.net is None or pin.net == "":
            pin_tokens.append(f"{pin_id}>-")
        else:
            net, net_flag = _sanitize(pin.net)
            if net_flag:
                warnings.append(f"{ref}.pin[{pin_id}].net")
            pin_tokens.append(f"{pin_id}>{net}")

    body = " ".join(pin_tokens)
    if omit_pos:
        return f"{ref}  {value}  {body}"
    pos = f"x{_format_num(comp.x)} y{_format_num(comp.y)}"
    return f"{ref}  {value}  {pos}  {body}"


def _collect_nets(components: tuple[Component, ...]) -> dict[str, list[str]]:
    """Construye la sección [N] a partir de los pines de los componentes."""
    nets: dict[str, list[str]] = {}
    for comp in components:
        for pin in comp.pins:
            if pin.net is None or pin.net == "":
                continue
            net_name, _ = _sanitize(pin.net)
            pin_id, _ = _sanitize(_format_pin_ref(pin))
            ref, _ = _sanitize(comp.ref)
            nets.setdefault(net_name, []).append(f"{ref}.{pin_id}")
    return nets


def _sort_nets(nets: dict[str, list[str]]) -> list[str]:
    """Poder primero (regex §4), resto alfabético (§2)."""

    def key(name: str) -> tuple[int, str]:
        return (0 if _POWER_NET_RE.match(name) else 1, name)

    return sorted(nets.keys(), key=key)


def _encode_net_line(net: str, members: list[str], *, collapse_power: bool) -> str:
    if collapse_power and _POWER_NET_RE.match(net) and len(members) > _POWER_COLLAPSE_THRESHOLD:
        return f"{net}: {len(members)} pines (colapsada)"
    members_sorted = sorted(members, key=_natural_key)
    return f"{net}: {' '.join(members_sorted)}"


def _in_area_refs(components: tuple[Component, ...], focus_ref: str, radius_mm: float) -> set[str]:
    focus = next((c for c in components if c.ref == focus_ref), None)
    if focus is None:
        raise KicadMcpError(
            code=ErrorCode.COMPONENT_NOT_FOUND,
            message=f"El foco ``{focus_ref}`` no existe en el snapshot vigente.",
            hint="Verificar la referencia; usar get_world_context sin foco.",
        )
    result = {focus.ref}
    for c in components:
        if math.hypot(c.x - focus.x, c.y - focus.y) <= radius_mm:
            result.add(c.ref)
    return result


def _compact_ref_group(refs: list[str]) -> str:
    """Colapsa una lista de refs con mismo prefijo a rangos ``R1-R3`` o ``R1,R3``."""
    numbered: list[tuple[str, int, str]] = []
    unparsed: list[str] = []
    for r in refs:
        m = _REF_PREFIX_RE.match(r)
        if m:
            numbered.append((m.group(1), int(m.group(2)), r))
        else:
            unparsed.append(r)
    numbered.sort(key=lambda t: (t[0], t[1]))
    pieces: list[str] = []
    i = 0
    while i < len(numbered):
        prefix, start_n, start_ref = numbered[i]
        end_n = start_n
        end_ref = start_ref
        j = i + 1
        while j < len(numbered) and numbered[j][0] == prefix and numbered[j][1] == end_n + 1:
            end_n = numbered[j][1]
            end_ref = numbered[j][2]
            j += 1
        pieces.append(start_ref if end_n == start_n else f"{start_ref}-{end_ref}")
        i = j
    pieces.extend(sorted(unparsed, key=_natural_key))
    return ",".join(pieces)


def _format_far_summary(far: tuple[Component, ...]) -> str:
    """``[FUERA_DE_AREA] N comp: R1-R3(resistencias) …`` — spec §4 nivel 2."""
    groups: dict[str, list[str]] = {}
    for c in far:
        m = _REF_PREFIX_RE.match(c.ref)
        prefix = m.group(1).upper() if m else c.ref.upper()
        groups.setdefault(prefix, []).append(c.ref)
    parts: list[str] = []
    for prefix in sorted(groups.keys()):
        category = _CATEGORY_MAP.get(prefix, f"{prefix.lower()}s")
        parts.append(f"{_compact_ref_group(groups[prefix])}({category})")
    return f"[FUERA_DE_AREA] {len(far)} comp: {' '.join(parts)}"


def _encode_impl(state: NormalizedState, opts: _Options) -> str:
    components_sorted = tuple(sorted(state.components, key=lambda c: _natural_key(c.ref)))
    total_components = len(components_sorted)
    if opts.focus_ref is not None and opts.radius_mm is not None:
        in_area = _in_area_refs(components_sorted, opts.focus_ref, opts.radius_mm)
    else:
        in_area = {c.ref for c in components_sorted}

    warnings: list[str] = []
    comp_lines: list[str] = []
    far_components: list[Component] = []
    for c in components_sorted:
        if c.ref in in_area:
            comp_lines.append(_encode_component_line(c, warnings, opts.omit_pos))
        else:
            far_components.append(c)
    if far_components:
        comp_lines.append(_format_far_summary(tuple(far_components)))

    nets = _collect_nets(components_sorted)
    net_names = _sort_nets(nets)
    net_lines = [
        _encode_net_line(n, nets[n], collapse_power=opts.collapse_power) for n in net_names
    ]

    kind = state.kind.upper()
    header = f"{kind}|v1|{total_components}c|{len(nets)}n|snap:{state.snap}"

    lines: list[str] = [header, "[C]", *comp_lines, "[N]", *net_lines]
    if warnings:
        seen: dict[str, None] = {}
        for w in warnings:
            seen.setdefault(w, None)
        lines.append(f"[AVISO] campos con texto sospechoso: {', '.join(seen)}")
    if opts.degrade_labels:
        lines.append(f"[DEGRADADO] {' '.join(opts.degrade_labels)}")
    return "\n".join(lines) + "\n"


def encode_state(state: NormalizedState) -> str:
    """Serializa un estado completo a TOON v1 sin degradación (§2).

    Salida terminada en ``\\n`` (una sola línea final, spec §6).
    """
    return _encode_impl(state, _Options())


def _try_options_sequence(
    state: NormalizedState, sequence: list[_Options], max_tokens: int
) -> tuple[str, _Options] | None:
    """Devuelve el primer encoding que cabe en ``max_tokens`` (o None si ninguno).

    Usa un umbral ``max_tokens * _BUDGET_SAFETY_FACTOR`` para dejar margen al
    tokenizador real (ver constante).
    """
    threshold = math.floor(max_tokens * _BUDGET_SAFETY_FACTOR)
    for opts in sequence:
        encoded = _encode_impl(state, opts)
        if estimate_tokens(encoded) <= threshold:
            return encoded, opts
    return None


def encode(
    state: NormalizedState,
    *,
    max_tokens: int = 800,
    focus_ref: str | None = None,
    radius_mm: float | None = None,
) -> str:
    """Encoder con presupuesto de tokens y área local (spec §4).

    Aplica los tres niveles de degradación en orden aditivo hasta caber en
    ``max_tokens``; si ni siquiera con todo aplicado cabe, lanza
    ``CONTEXT_BUDGET_IMPOSSIBLE`` con hint del presupuesto mínimo calculado.
    """
    can_focus = focus_ref is not None and radius_mm is not None

    sequence: list[_Options] = [_Options()]
    sequence.append(_Options(collapse_power=True, degrade_labels=("poder_colapsado",)))
    if can_focus:
        sequence.append(
            _Options(
                collapse_power=True,
                focus_ref=focus_ref,
                radius_mm=radius_mm,
                degrade_labels=("poder_colapsado", "fuera_de_area"),
            )
        )
    last_labels = [*sequence[-1].degrade_labels, "posiciones_omitidas"]
    sequence.append(
        _Options(
            collapse_power=True,
            focus_ref=focus_ref if can_focus else None,
            radius_mm=radius_mm if can_focus else None,
            omit_pos=True,
            degrade_labels=tuple(last_labels),
        )
    )

    found = _try_options_sequence(state, sequence, max_tokens)
    if found is not None:
        return found[0]

    # Ni el nivel máximo cabe. Calculamos el presupuesto mínimo con lo más
    # degradado que sabemos hacer y lo comunicamos como hint accionable.
    min_encoding = _encode_impl(state, sequence[-1])
    min_budget = estimate_tokens(min_encoding)
    hint = (
        f"presupuesto mínimo estimado ≈ {min_budget} tokens; "
        "subir max_tokens o reducir el foco/radio"
    )
    raise KicadMcpError(
        code=ErrorCode.CONTEXT_BUDGET_IMPOSSIBLE,
        message=(
            f"El estado no cabe en {max_tokens} tokens ni aplicando todos los "
            "niveles de degradación (spec §4)."
        ),
        hint=hint,
    )


def encode_delta(
    state: NormalizedState,
    *,
    base: NormalizedState,
    focus_ref: str,
    radius_mm: float,
    base_snap: int,
) -> str:
    """Placeholder del delta (§3). Se implementa en v0.3."""
    _ = (state, base, focus_ref, radius_mm, base_snap)
    raise NotImplementedError("ΔTOON no implementado (docs/specs/toon-v1.md §3, v0.3).")
