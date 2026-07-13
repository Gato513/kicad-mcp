"""Tests del diff estructural (``snapshots.delta.compute_delta``).

Cubre estado idéntico, add puro, remove puro, update de posición, update
de nets y combinado. Los tests son puros (sin fixtures de disco, sin
KiCad): la lógica de `compute_delta` es determinista sobre `NormalizedState`.

El golden 003 sigue siendo el contrato de la codificación TOON del delta;
estos tests protegen la capa de diff estructural.
"""

from __future__ import annotations

import pytest

from kicad_mcp.snapshots import Delta, compute_delta
from kicad_mcp.toon.schema import Component, NormalizedState, Pin


def _s(components: tuple[Component, ...], snap: int = 1) -> NormalizedState:
    return NormalizedState(kind="sch", snap=snap, components=components)


def _c(ref: str, x: float, y: float, pins: tuple[Pin, ...] = (), value: str = "V") -> Component:
    return Component(ref=ref, value=value, lib=None, x=x, y=y, pins=pins)


@pytest.mark.unit
def test_identical_states_produce_empty_delta() -> None:
    """Snapshot idéntico ⇒ delta vacío (regresión del "delta sobre delta")."""
    state = _s(
        (
            _c("U1", 0.0, 0.0, (Pin(p="1", net="GND"),)),
            _c("R1", 10.0, 0.0, (Pin(p="1", net="3V3"),)),
        )
    )
    delta = compute_delta(state, state)
    assert isinstance(delta, Delta)
    assert delta.is_empty()
    assert delta.added == ()
    assert delta.removed == ()
    assert delta.updated == ()
    assert delta.nets_changed == ()


@pytest.mark.unit
def test_pure_add_reports_added_and_net_growth() -> None:
    """Añadir un componente que engancha nets existentes: [+] y sus nets [~N]."""
    base = _s((_c("R1", 0.0, 0.0, (Pin(p="1", net="GND"),)),))
    curr = _s(
        (
            _c("R1", 0.0, 0.0, (Pin(p="1", net="GND"),)),
            _c("C1", 10.0, 0.0, (Pin(p="1", net="GND"),)),
        )
    )
    delta = compute_delta(base, curr)
    assert [c.ref for c in delta.added] == ["C1"]
    assert delta.removed == ()
    assert delta.updated == ()
    assert delta.nets_changed == ("GND",)


@pytest.mark.unit
def test_pure_remove_reports_removed_and_net_shrink() -> None:
    """Quitar un componente: [-] REF + [~N] de las nets que pierden miembros."""
    base = _s(
        (
            _c("R1", 0.0, 0.0, (Pin(p="1", net="GND"),)),
            _c("C1", 10.0, 0.0, (Pin(p="1", net="GND"),)),
        )
    )
    curr = _s((_c("R1", 0.0, 0.0, (Pin(p="1", net="GND"),)),))
    delta = compute_delta(base, curr)
    assert delta.added == ()
    assert delta.removed == ("C1",)
    assert delta.updated == ()
    assert delta.nets_changed == ("GND",)


@pytest.mark.unit
def test_position_change_reports_updated_only() -> None:
    """Cambio de posición ⇒ [~C]; nets no cambian ⇒ no [~N]."""
    base = _s((_c("R1", 0.0, 0.0, (Pin(p="1", net="GND"),)),))
    curr = _s((_c("R1", 5.0, 0.0, (Pin(p="1", net="GND"),)),))
    delta = compute_delta(base, curr)
    assert delta.added == ()
    assert delta.removed == ()
    assert [c.ref for c in delta.updated] == ["R1"]
    assert delta.nets_changed == ()


@pytest.mark.unit
def test_net_change_on_same_component_reports_updated_and_net() -> None:
    """Repunetar un pin del mismo componente ⇒ [~C] y [~N] de ambas nets."""
    base = _s((_c("R1", 0.0, 0.0, (Pin(p="1", net="GND"),)),))
    curr = _s((_c("R1", 0.0, 0.0, (Pin(p="1", net="3V3"),)),))
    delta = compute_delta(base, curr)
    assert delta.added == ()
    assert delta.removed == ()
    assert [c.ref for c in delta.updated] == ["R1"]
    # Poder primero (3V3 y GND ambos son poder → orden alfabético).
    assert delta.nets_changed == ("3V3", "GND")


@pytest.mark.unit
def test_combined_add_remove_update_is_natural_sorted() -> None:
    """Sortings estables: los tres buckets ordenan por natural key.

    C10 debe salir DESPUÉS de C2 (no antes) — regresión del sort lexicográfico.
    """
    base = _s(
        (
            _c("R1", 0.0, 0.0),
            _c("R10", 0.0, 0.0),
            _c("C2", 5.0, 0.0, (Pin(p="1", net="A"),)),
        )
    )
    curr = _s(
        (
            _c("R1", 9.0, 0.0),  # updated (moved)
            _c("C2", 5.0, 0.0, (Pin(p="1", net="A"),)),  # unchanged
            _c("C10", 0.0, 0.0, (Pin(p="1", net="A"),)),  # added
            _c("R2", 0.0, 0.0),  # added
            # R10 removed
        )
    )
    delta = compute_delta(base, curr)
    assert [c.ref for c in delta.added] == ["C10", "R2"]  # C10 después de C1 no de C1
    assert delta.removed == ("R10",)
    assert [c.ref for c in delta.updated] == ["R1"]
    assert delta.nets_changed == ("A",)  # C10.1 añadido a la net A


@pytest.mark.unit
def test_lib_change_does_not_count_as_update() -> None:
    """Cambiar sólo ``lib`` no es un update: no se emite en TOON (spec §2)."""
    base = _s((Component(ref="U1", value="V", lib="OldLib:U", x=0.0, y=0.0, pins=()),))
    curr = _s((Component(ref="U1", value="V", lib="NewLib:U", x=0.0, y=0.0, pins=()),))
    delta = compute_delta(base, curr)
    assert delta.is_empty()


@pytest.mark.unit
def test_delta_is_deterministic_across_repeated_calls() -> None:
    """Mismos inputs ⇒ mismo output (invariante contra PYTHONHASHSEED)."""
    base = _s(
        (
            _c("C2", 0.0, 0.0, (Pin(p="1", net="B"),)),
            _c("C1", 0.0, 0.0, (Pin(p="1", net="A"),)),
        )
    )
    curr = _s(
        (
            _c("C3", 0.0, 0.0, (Pin(p="1", net="A"),)),  # added
            _c("C2", 0.0, 0.0, (Pin(p="1", net="B"),)),
            _c("C1", 0.0, 0.0, (Pin(p="1", net="A"),)),
        )
    )
    d1 = compute_delta(base, curr)
    d2 = compute_delta(base, curr)
    assert d1 == d2
