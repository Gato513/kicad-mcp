"""Encoder TOON v1.

Contrato en `docs/specs/toon-v1.md`. MVP: encoder sin degradación (§2).
La degradación por presupuesto (§4) y el delta (§3) llegan en v0.3.

Frontera F1: los golden files bajo `tests/golden/` son la definición
ejecutable. Ante discrepancia entre este código y el golden, el golden manda.
"""

from __future__ import annotations

import re
from typing import Final

from .schema import Component, NormalizedState, Pin

_STRUCTURAL_CHARS: Final = str.maketrans({">": "_", "|": "_", ":": "_"})
_CONTROL_RE: Final = re.compile(r"[\x00-\x1f\x7f]")
_MAX_FIELD_LEN: Final = 40
_NATURAL_SPLIT_RE: Final = re.compile(r"(\d+)")

# `docs/specs/toon-v1.md §4`: regex de nets de poder. En §2 la usamos también
# para ordenar (poder primero, resto alfabético).
_POWER_NET_RE: Final = re.compile(
    r"^(GND|VSS|AGND|DGND|PGND|VCC|VDD|VBUS|[0-9]+V[0-9]*|3V3|5V|12V|-?[0-9]+V)$",
    re.IGNORECASE,
)

# Heurística de inyección (§5.4): estos términos disparan el aviso final.
_SUSPICIOUS_RE: Final = re.compile(r"(?i)(ignore|system|instruction|prompt|you are)")


def _sanitize(raw: str) -> tuple[str, bool]:
    """Sanea un string de entrada no confiable (§5). Devuelve ``(saneado, sospechoso)``."""
    cleaned = _CONTROL_RE.sub("_", raw)
    cleaned = cleaned.translate(_STRUCTURAL_CHARS)
    if len(cleaned) > _MAX_FIELD_LEN:
        cleaned = cleaned[: _MAX_FIELD_LEN - 1] + "…"
    suspicious = bool(_SUSPICIOUS_RE.search(cleaned))
    return cleaned, suspicious


def _natural_key(text: str) -> tuple[object, ...]:
    """Orden natural (`C1, C2, C10` en vez de `C1, C10, C2`)."""
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


def _encode_component_line(comp: Component, warnings: list[str]) -> str:
    ref, ref_flag = _sanitize(comp.ref)
    value, value_flag = _sanitize(comp.value)
    if ref_flag:
        warnings.append(f"{ref}.ref")
    if value_flag:
        warnings.append(f"{ref}.value")

    pin_tokens: list[str] = []
    for pin in sorted(comp.pins, key=lambda p: _natural_key(_format_pin_ref(p))):
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

    pos = f"x{_format_num(comp.x)} y{_format_num(comp.y)}"
    return f"{ref}  {value}  {pos}  {' '.join(pin_tokens)}"


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


def _encode_net_line(net: str, members: list[str]) -> str:
    members_sorted = sorted(members, key=_natural_key)
    return f"{net}: {' '.join(members_sorted)}"


def encode_state(state: NormalizedState) -> str:
    """Serializa un estado completo a TOON v1 sin degradación.

    Salida terminada en ``\\n`` (una sola línea final, spec §6).
    """
    components_sorted = tuple(sorted(state.components, key=lambda c: _natural_key(c.ref)))
    warnings: list[str] = []
    comp_lines = [_encode_component_line(c, warnings) for c in components_sorted]

    nets = _collect_nets(components_sorted)
    net_names = _sort_nets(nets)
    net_lines = [_encode_net_line(n, nets[n]) for n in net_names]

    kind = state.kind.upper()
    header = f"{kind}|v1|{len(components_sorted)}c|{len(nets)}n|snap:{state.snap}"

    lines = [header, "[C]", *comp_lines, "[N]", *net_lines]
    if warnings:
        # De-duplica preservando el primer orden en que apareció cada campo.
        seen: dict[str, None] = {}
        for w in warnings:
            seen.setdefault(w, None)
        lines.append(f"[AVISO] campos con texto sospechoso: {', '.join(seen)}")
    return "\n".join(lines) + "\n"


def encode(
    state: NormalizedState,
    *,
    max_tokens: int = 800,
    focus_ref: str | None = None,
    radius_mm: float | None = None,
) -> str:
    """API pública futura: encoder con presupuesto y área local.

    MVP: si el estado cabe sin degradar, devuelve la versión completa. En
    cuanto haga falta degradar (§4) o filtrar por foco/radio, se lanza
    ``NotImplementedError`` — se resuelve en v0.3.
    """
    _ = (focus_ref, radius_mm)  # aún no aplicados
    full = encode_state(state)
    from ..logging_config import estimate_tokens

    if estimate_tokens(full) > max_tokens:
        raise NotImplementedError(
            "Degradación por presupuesto no implementada (docs/specs/toon-v1.md §4, v0.3)."
        )
    return full


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
