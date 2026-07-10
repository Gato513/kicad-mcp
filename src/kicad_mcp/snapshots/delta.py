"""Diff estructural entre dos ``NormalizedState`` (ΔTOON, spec §3).

Lógica pura y determinista: dados dos estados normalizados, devuelve un
``Delta`` con las diferencias — componentes añadidos, eliminados, modificados
y nets cuya membresía cambió. **No** codifica a texto: la serialización TOON
del delta vive en ``toon/encoder.encode_delta`` (frontera F1: encoder es el
único que emite bytes contra los golden).

Determinismo:
- Todos los conjuntos se materializan a listas ordenadas por *natural key*
  (``C1, C2, C10``) antes de devolver, con lo cual `compute_delta` produce
  la misma salida para las mismas entradas independientemente del orden de
  inserción o del PYTHONHASHSEED.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..toon.schema import Component, NormalizedState

_NATURAL_SPLIT_RE = re.compile(r"(\d+)")


def _natural_key(text: str) -> tuple[object, ...]:
    return tuple(
        int(part) if part.isdigit() else part.lower()
        for part in _NATURAL_SPLIT_RE.split(text)
        if part
    )


def _nets_by_component(state: NormalizedState) -> dict[str, list[str]]:
    """``{net: [ref.pin, ...]}`` derivado de los pines. Miembros sin ordenar."""
    out: dict[str, list[str]] = {}
    for comp in state.components:
        for pin in comp.pins:
            if pin.net is None or pin.net == "":
                continue
            pin_id = pin.p if pin.p.strip() else (pin.name or "")
            out.setdefault(pin.net, []).append(f"{comp.ref}.{pin_id}")
    return out


def _component_signature(comp: Component) -> tuple[object, ...]:
    """Firma comparable de un componente: cambio en cualquier campo emitido
    en la línea TOON (value, x, y, secuencia de pines/nets) cuenta como modificación.

    ``lib`` NO participa (spec §2: no se emite en TOON, se recupera aparte).
    """
    pins = tuple(
        (pin.p, pin.name, pin.net) for pin in comp.pins
    )
    return (comp.value, comp.x, comp.y, pins)


@dataclass(frozen=True)
class Delta:
    """Cambio estructural entre dos estados normalizados.

    Los campos son *listas ordenadas* de forma determinista; no ``set`` ni
    ``dict``. El consumidor (encoder) los emite en el orden dado.
    """

    added: tuple[Component, ...] = field(default_factory=tuple)
    """Componentes presentes en ``curr`` pero no en ``prev``, orden natural
    por ``ref``."""

    removed: tuple[str, ...] = field(default_factory=tuple)
    """Refs presentes en ``prev`` pero no en ``curr``, orden natural."""

    updated: tuple[Component, ...] = field(default_factory=tuple)
    """Componentes con la misma ``ref`` cuya firma emitida cambió
    (posición, valor, secuencia de pines/nets), orden natural."""

    nets_changed: tuple[str, ...] = field(default_factory=tuple)
    """Nets cuya membresía difiere entre ``prev`` y ``curr``, con orden
    "poder primero, resto alfabético" (spec §2)."""

    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.updated or self.nets_changed)


_POWER_NET_RE = re.compile(
    r"^(GND|VSS|AGND|DGND|PGND|VCC|VDD|VBUS|[0-9]+V[0-9]*|3V3|5V|12V|-?[0-9]+V)$",
    re.IGNORECASE,
)


def _sort_nets(names: set[str]) -> tuple[str, ...]:
    return tuple(
        sorted(names, key=lambda n: (0 if _POWER_NET_RE.match(n) else 1, n))
    )


def compute_delta(prev: NormalizedState, curr: NormalizedState) -> Delta:
    """Calcula el diff estructural ``prev → curr``.

    Puro y determinista: mismos inputs ⇒ mismos outputs (ejercitado por el
    golden 003, que se corre dos veces en el mismo job para verificarlo).
    """
    prev_by_ref = {c.ref: c for c in prev.components}
    curr_by_ref = {c.ref: c for c in curr.components}

    added = tuple(
        c
        for c in sorted(curr.components, key=lambda c: _natural_key(c.ref))
        if c.ref not in prev_by_ref
    )
    removed = tuple(
        r
        for r in sorted(prev_by_ref.keys(), key=_natural_key)
        if r not in curr_by_ref
    )
    updated = tuple(
        curr_by_ref[ref]
        for ref in sorted(
            (r for r in curr_by_ref if r in prev_by_ref),
            key=_natural_key,
        )
        if _component_signature(prev_by_ref[ref]) != _component_signature(curr_by_ref[ref])
    )

    prev_nets = _nets_by_component(prev)
    curr_nets = _nets_by_component(curr)
    prev_sets = {name: frozenset(members) for name, members in prev_nets.items()}
    curr_sets = {name: frozenset(members) for name, members in curr_nets.items()}
    changed_names: set[str] = set()
    for name, members in curr_sets.items():
        if prev_sets.get(name) != members:
            changed_names.add(name)
    for name in prev_sets:
        if name not in curr_sets:
            changed_names.add(name)

    nets_changed = _sort_nets(changed_names)

    return Delta(
        added=added,
        removed=removed,
        updated=updated,
        nets_changed=nets_changed,
    )
