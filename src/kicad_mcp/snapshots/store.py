"""Snapshot Store — semilla v0.3 (arquitectura §4.3-4.4, sesión 04 T4).

Objetivo del MVP-semilla:
1. ``snap_id`` monotónico por proceso (adiós ``snap:1`` fijo).
2. Retención de los últimos 10 snapshots (FIFO por ``snap_id``).
3. Cada snapshot registra el conjunto de ``mtime_ns`` de los archivos del
   proyecto que participaron del estado (``.kicad_sch``, ``.kicad_pcb``).
4. Los llamadores (pcb tools) validan ``base_snap`` contra el store:
   - Ausente en el store → ``SNAPSHOT_STALE``.
   - Presente pero mtime cambió en disco → ``EXTERNAL_EDIT_DETECTED``.

No hay TTL temporal; la retención es puramente por cantidad. La cache de
``bridge.state_builder`` sigue siendo la vía rápida para reconstruir el
mismo estado sin releer archivos — el store es una capa DIFERENTE: guarda
el estado emitido al agente en cada turno, para permitir mutaciones
seguras contra un mundo específico.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from ..toon.schema import NormalizedState

SnapId = int
"""Identificador de snapshot; monótono creciente por proceso servidor."""


@dataclass(frozen=True)
class SnapshotEntry:
    """Un snapshot registrado: estado emitido + mtimes de los archivos base."""

    snap_id: SnapId
    state: NormalizedState
    mtimes: dict[str, int]
    """``{ruta_absoluta_canónica: mtime_ns}``. Copia defensiva del dict pasado
    a ``register``: mutaciones externas no afectan al store."""


class SnapshotStore:
    """Store en memoria con retención por cantidad. Thread-safe.

    Un solo store por proceso servidor. La retención (default 10) coincide
    con ``re_sync_interval`` del ADR-0004: si el agente pide un ``base_snap``
    más viejo, el diseño supone que ya toca hacer full re-sync.
    """

    def __init__(self, *, retention: int = 10) -> None:
        if retention < 1:
            raise ValueError("retention debe ser ≥ 1")
        self._retention = retention
        self._entries: OrderedDict[SnapId, SnapshotEntry] = OrderedDict()
        self._next_id: SnapId = 1
        self._lock = threading.Lock()

    def register(self, state: NormalizedState, mtimes: dict[str, int]) -> SnapId:
        """Registra un nuevo snapshot y devuelve su ``snap_id`` monótono.

        Copia ``mtimes`` para desacoplar al store de mutaciones externas del
        dict. Si al insertar se supera la retención, evicta el más viejo
        (menor ``snap_id``).
        """
        with self._lock:
            snap_id = self._next_id
            self._next_id += 1
            entry = SnapshotEntry(snap_id=snap_id, state=state, mtimes=dict(mtimes))
            self._entries[snap_id] = entry
            while len(self._entries) > self._retention:
                self._entries.popitem(last=False)
            return snap_id

    def get(self, snap_id: SnapId) -> SnapshotEntry | None:
        """Devuelve el snapshot o ``None`` si nunca existió / fue evictado."""
        with self._lock:
            return self._entries.get(snap_id)

    @property
    def retention(self) -> int:
        return self._retention

    def reset(self) -> None:
        """Test-only: limpia el store y resetea el contador. NO usar en runtime."""
        with self._lock:
            self._entries.clear()
            self._next_id = 1


# --- singleton por proceso servidor ------------------------------------------


_default_store = SnapshotStore()


def get_default_store() -> SnapshotStore:
    """Store compartido por meta/world/pcb dentro del mismo proceso servidor."""
    return _default_store


# --- utilidades compartidas ---------------------------------------------------


def collect_project_mtimes(schematic: Path) -> dict[str, int]:
    """``{ruta_canónica: mtime_ns}`` de los archivos que forman el snapshot.

    MVP: incluye ``.kicad_sch`` y, si existe, el ``.kicad_pcb`` homónimo.
    Las rutas se resuelven con ``resolve()`` para que el matching contra
    el disco sea estable ante symlinks o cwd relativos.
    """
    out: dict[str, int] = {}
    sch = schematic.resolve()
    if sch.is_file():
        out[str(sch)] = sch.stat().st_mtime_ns
    pcb = sch.with_suffix(".kicad_pcb")
    if pcb.is_file():
        out[str(pcb)] = pcb.stat().st_mtime_ns
    return out
