"""Cruce netlist x posiciones -> ``NormalizedState``.

Fuentes:
- **Conectividad**: ``bridge/netlist.py`` (kicad-cli sch export netlist).
- **Posiciones**: ``bridge/sch_positions.py`` (parseo local del .kicad_sch).

Una ref presente en una fuente y ausente en la otra ⇒ estado inconsistente,
error tipado (jamás adivinar). Ver `restricciones-kicad.md`.
"""

from __future__ import annotations

from pathlib import Path

from ..errors import ErrorCode, KicadMcpError
from ..toon.schema import Component, NormalizedState, Pin
from .netlist import Netlist, load_netlist
from .sch_positions import Placement, parse_root_positions


def _index_placements(placements: tuple[Placement, ...]) -> dict[str, Placement]:
    seen: dict[str, Placement] = {}
    for p in placements:
        if p.ref in seen:
            raise KicadMcpError(
                code=ErrorCode.KICAD_CLI_FAILED,
                message=f"Referencia duplicada en el .kicad_sch: {p.ref}.",
                hint="Verificar el esquemático: dos símbolos con la misma Reference.",
            )
        seen[p.ref] = p
    return seen


def _build_pins(
    ref: str,
    all_pin_ids: tuple[str, ...],
    connections: dict[str, str],
    unconnected: set[str],
) -> tuple[Pin, ...]:
    pins: list[Pin] = []
    for pin_id in all_pin_ids:
        if pin_id in connections:
            pins.append(Pin(p=pin_id, net=connections[pin_id]))
        elif pin_id in unconnected:
            pins.append(Pin(p=pin_id, net=None))
        else:
            # Pin en <units> del netlist pero sin net y sin marca de unconnected:
            # KiCad lo trataría como flotante. Lo emitimos como sin conectar
            # para no perder el pin (spec §2: pin sin conectar → ">-").
            pins.append(Pin(p=pin_id, net=None))
        _ = ref  # firma consistente si alguien quiere depurar por ref
    return tuple(pins)


def _connections_per_ref(netlist: Netlist) -> dict[str, dict[str, str]]:
    """``{ref: {pin_id: net_name}}`` para los nets no unconnected."""
    per_ref: dict[str, dict[str, str]] = {}
    for net_name, members in netlist.nets.items():
        for ref, pin_id in members:
            per_ref.setdefault(ref, {})[pin_id] = net_name
    return per_ref


def _unconnected_per_ref(netlist: Netlist) -> dict[str, set[str]]:
    per_ref: dict[str, set[str]] = {}
    for ref, pin_id in netlist.unconnected_pins:
        per_ref.setdefault(ref, set()).add(pin_id)
    return per_ref


def build_state(schematic: Path, *, snap: int) -> NormalizedState:
    """Construye ``NormalizedState`` desde el esquemático dado.

    Precondiciones: ``schematic`` es una ruta absoluta canonicalizada por el
    llamador. Lanza:
    - ``UNSUPPORTED_HIERARCHY`` si el ``.kicad_sch`` es multi-hoja.
    - ``KICAD_CLI_FAILED`` si kicad-cli falla o hay estado inconsistente.
    """
    # Chequear jerarquía ANTES de invocar kicad-cli: falla rápido en proyectos
    # multi-hoja sin gastar el subprocess (que sí procesa jerarquía).
    placements = parse_root_positions(schematic)
    netlist = load_netlist(schematic)
    placements_by_ref = _index_placements(placements)
    connections = _connections_per_ref(netlist)
    unconnected_by_ref = _unconnected_per_ref(netlist)

    refs_netlist = {c.ref for c in netlist.components}
    refs_positions = set(placements_by_ref.keys())
    only_in_netlist = sorted(refs_netlist - refs_positions)
    only_in_positions = sorted(refs_positions - refs_netlist)
    if only_in_netlist or only_in_positions:
        detail = []
        if only_in_netlist:
            detail.append(f"netlist sin posición: {', '.join(only_in_netlist[:3])}")
        if only_in_positions:
            detail.append(f"posición sin netlist: {', '.join(only_in_positions[:3])}")
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message="Estado inconsistente entre netlist y posiciones.",
            hint="; ".join(detail),
        )

    components: list[Component] = []
    for c in netlist.components:
        p = placements_by_ref[c.ref]
        pins = _build_pins(
            c.ref,
            c.pin_ids,
            connections.get(c.ref, {}),
            unconnected_by_ref.get(c.ref, set()),
        )
        components.append(Component(ref=c.ref, value=c.value, lib=c.lib, x=p.x, y=p.y, pins=pins))
    return NormalizedState(kind="sch", snap=snap, components=tuple(components))
