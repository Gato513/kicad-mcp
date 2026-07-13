"""Cruce netlist x posiciones -> ``NormalizedState``.

Fuentes:
- **Conectividad**: ``bridge/netlist.py`` (kicad-cli sch export netlist).
- **Posiciones**: ``bridge/sch_positions.py`` (parseo local del .kicad_sch).

Una ref presente en una fuente y ausente en la otra ⇒ estado inconsistente,
error tipado (jamás adivinar). Ver `restricciones-kicad.md`.

Cachea el ``NormalizedState`` por ``(ruta_canonica, mtime_ns)`` del
``.kicad_sch``. El invalidator del Snapshot Store (arquitectura §4.4)
usará este mismo criterio; aquí es su semilla. Cambiar el ``snap`` no
invalida: el estado cacheado se copia con el nuevo ``snap`` sin
reconstruir.
"""

from __future__ import annotations

from pathlib import Path

from ..errors import ErrorCode, KicadMcpError
from ..toon.schema import Component, NormalizedState, Pin
from .ipc import BoardHandle, FootprintData, IpcBridge
from .netlist import Netlist, load_netlist
from .sch_positions import Placement, parse_root_positions

_CACHE: dict[tuple[str, int], NormalizedState] = {}


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

    Wrapper de ``build_state_cached`` que descarta el flag ``cache_hit``.
    """
    state, _ = build_state_cached(schematic, snap=snap)
    return state


def build_state_cached(schematic: Path, *, snap: int) -> tuple[NormalizedState, bool]:
    """Como ``build_state`` pero además reporta si vino de cache.

    Precondiciones: ``schematic`` es una ruta absoluta canonicalizada por el
    llamador. Lanza:
    - ``UNSUPPORTED_HIERARCHY`` si el ``.kicad_sch`` es multi-hoja.
    - ``KICAD_CLI_FAILED`` si kicad-cli falla o hay estado inconsistente.

    El cache está indexado por ``(str(schematic.resolve()), mtime_ns)``: si
    el ``.kicad_sch`` cambió su mtime desde la última llamada, se
    reconstruye. Los ``snap`` distintos no invalidan; se reusan copiando
    el estado con el nuevo ``snap``.
    """
    resolved = schematic.resolve()
    try:
        mtime_ns = resolved.stat().st_mtime_ns
    except FileNotFoundError:
        # Sin mtime no hay cache; que el pipeline levante el error tipado
        # que corresponda río abajo. No decidimos aquí sobre errores.
        return _rebuild(schematic, snap=snap), False
    key = (str(resolved), mtime_ns)
    cached = _CACHE.get(key)
    if cached is not None:
        if cached.snap == snap:
            return cached, True
        return cached.model_copy(update={"snap": snap}), True
    state = _rebuild(schematic, snap=snap)
    _CACHE[key] = state
    return state, False


def clear_cache() -> None:
    """Vacía el cache. Útil en tests que necesitan aislar mtime hits."""
    _CACHE.clear()


def build_state_from_snapshot(footprints: tuple[FootprintData, ...]) -> NormalizedState:
    """Materializa ``NormalizedState`` (kind="pcb") desde un snapshot ya leído.

    Sesión 08 D-08.1: los tools de mutación traen los footprints en un
    único pasaje de ``read_board_context`` y, tras la mutación, aplican
    la derivación local (D-08.2) sobre esa misma tupla. Este helper es
    la conversión pura ``FootprintData → NormalizedState`` — sin tocar
    IPC, sin volver a iterar el board.

    Mantiene el contrato de ``build_state_from_board`` (kind="pcb",
    ``snap=0``; el llamador sobrescribe con el ``snap_id`` del store).
    """
    components: list[Component] = []
    for fp in footprints:
        pins = tuple(Pin(p=pad.number, net=pad.net_name) for pad in fp.pads)
        components.append(
            Component(
                ref=fp.ref,
                value=fp.value,
                lib=None,  # kipy no expone lib acá; recuperable por get_component_detail.
                x=float(fp.x_mm),
                y=float(fp.y_mm),
                pins=pins,
            )
        )
    return NormalizedState(kind="pcb", snap=0, components=tuple(components))


def build_state_from_board(bridge: IpcBridge, board: BoardHandle) -> NormalizedState:
    """Reconstruye ``NormalizedState`` (kind="pcb") desde el board vivo de kipy.

    Sesión 05 T5. Camino paralelo a ``build_state_cached`` — este NO lee de
    disco: consulta el board via ``bridge.snapshot_footprints`` (lock-safe)
    y materializa el estado tal como kipy lo tiene tras la mutación. El
    ``.kicad_pcb`` de disco todavía no lo refleja (KiCad sólo guarda con
    ``Save``), por eso el llamador registra este snapshot con ``mtimes=None``
    (snapshot vivo, ADR-0007).

    Sesión 08: el pipeline eficiente ya no pasa por acá — los tools usan
    ``read_board_context`` (una pasada) y ``build_state_from_snapshot``
    para armar el pre-estado, y derivan el post-estado localmente
    (D-08.2). Esta función queda como fallback (rama de divergencia) y
    para call-sites histórics (state_builder tests). Es una pasada
    O(board) más una en total.
    """
    footprints = bridge.snapshot_footprints(board)
    return build_state_from_snapshot(footprints)


def _rebuild(schematic: Path, *, snap: int) -> NormalizedState:
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
            c.pin_ids,
            connections.get(c.ref, {}),
            unconnected_by_ref.get(c.ref, set()),
        )
        components.append(Component(ref=c.ref, value=c.value, lib=c.lib, x=p.x, y=p.y, pins=pins))
    return NormalizedState(kind="sch", snap=snap, components=tuple(components))
