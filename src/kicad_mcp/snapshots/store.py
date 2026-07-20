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
    """Un snapshot registrado: estado emitido + mtimes de los archivos base.

    ``mtimes`` puede ser ``None`` — "snapshot vivo" — cuando el estado se
    reconstruyó desde una fuente in-memory (p. ej. el board de kipy tras
    una mutación) y por lo tanto no hay un mtime de disco al que anclarlo.
    La consecuencia intencionada (ver ADR-0007) es que la validación de
    ``EXTERNAL_EDIT_DETECTED`` se omite para snapshots vivos: es el precio
    a pagar para no dispararla como falso positivo tras el ``Save`` que
    el propio agente eventualmente ejecute.
    """

    snap_id: SnapId
    state: NormalizedState
    mtimes: dict[str, int] | None
    """``{ruta_absoluta_canónica: mtime_ns}`` o ``None``. Cuando ``dict``,
    es copia defensiva del dict pasado a ``register`` (mutaciones externas
    no afectan al store). Cuando ``None``, marca el snapshot como vivo."""


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
        # D-14.1 (split-brain post-route): ``route_board`` escribe el ruteo a
        # DISCO y el board vivo de KiCad queda detrás. Mientras el flag esté
        # activo, las mutaciones IPC y ``save_board`` FALLAN
        # (``EXTERNAL_EDIT_DETECTED``) para no pisar el ruteo con cobre viejo;
        # se limpia con ``get_world_context(kind='pcb', confirm_reloaded=true)``
        # tras recargar el board en KiCad (File→Revert).
        self._live_stale: bool = False
        self._live_stale_snap: SnapId | None = None
        # P3.2 (sesión 18): último conjunto de mtimes de DISCO que este
        # proceso conoce, actualizado por CUALQUIER registro con mtimes reales
        # (route_board, save_board, reload_board_from_disk, get_world_context,
        # ...). Es la referencia del guard "sin external edit silencioso" —
        # independiente de ``base_snap`` (que el agente puede omitir) y del
        # flag ``live_stale`` (que sólo modela el caso conocido de
        # route_board). Ver ``snapshots/validation.py:check_no_external_disk_edit``.
        self._latest_disk_mtimes: dict[str, int] | None = None

    def register(
        self,
        state: NormalizedState,
        mtimes: dict[str, int] | None,
    ) -> SnapId:
        """Registra un nuevo snapshot y devuelve su ``snap_id`` monótono.

        ``mtimes=None`` marca el snapshot como **vivo** (ADR-0007): el estado
        proviene de una fuente in-memory (típicamente el board de kipy
        post-mutación), no hay ``mtime`` de disco al que anclarlo, y la
        validación de ``EXTERNAL_EDIT_DETECTED`` se omitirá para ese snap.

        Cuando ``mtimes`` es un dict, se copia defensivamente para desacoplar
        al store de mutaciones externas. Si al insertar se supera la
        retención, se evicta el más viejo (menor ``snap_id``); ``mtimes``
        reales (no ``None``) también actualizan ``latest_disk_mtimes``
        (P3.2), que NO se evicta con la retención — es un único puntero al
        último estado de disco conocido, no una entrada de historial.
        """
        with self._lock:
            snap_id = self._next_id
            self._next_id += 1
            stored_mtimes: dict[str, int] | None = dict(mtimes) if mtimes is not None else None
            entry = SnapshotEntry(snap_id=snap_id, state=state, mtimes=stored_mtimes)
            self._entries[snap_id] = entry
            while len(self._entries) > self._retention:
                self._entries.popitem(last=False)
            if stored_mtimes is not None:
                self._latest_disk_mtimes = stored_mtimes
            return snap_id

    @property
    def latest_disk_mtimes(self) -> dict[str, int] | None:
        """Último ``mtimes`` de DISCO registrado por cualquier tool (P3.2).

        ``None`` si este proceso todavía no registró ningún snapshot con
        mtimes reales (nada contra qué comparar todavía — mismo criterio que
        ``mtimes=None`` en ``SnapshotEntry``: sin ancla, sin falso positivo).
        Copia defensiva: el llamador no puede mutar el estado interno.
        """
        with self._lock:
            return dict(self._latest_disk_mtimes) if self._latest_disk_mtimes is not None else None

    def get(self, snap_id: SnapId) -> SnapshotEntry | None:
        """Devuelve el snapshot o ``None`` si nunca existió / fue evictado."""
        with self._lock:
            return self._entries.get(snap_id)

    @property
    def retention(self) -> int:
        return self._retention

    # --- flag D-14.1 (split-brain post-route) --------------------------------

    def mark_live_stale(self, snap_id: SnapId) -> None:
        """Marca que el DISCO tiene el ruteo y el editor vivo quedó detrás.

        ``snap_id`` es el snapshot de DISCO que ``route_board`` registró tras
        el ruteo. Con el flag activo, las tools que mutan el board vivo o lo
        guardan deben fallar con ``EXTERNAL_EDIT_DETECTED`` (ver ADR-0011).
        """
        with self._lock:
            self._live_stale = True
            self._live_stale_snap = snap_id

    def clear_live_stale(self) -> None:
        """Limpia el flag D-14.1 (el humano recargó el board en KiCad)."""
        with self._lock:
            self._live_stale = False
            self._live_stale_snap = None

    def is_live_stale(self) -> bool:
        """``True`` si hay un ruteo en disco que el editor vivo no refleja."""
        with self._lock:
            return self._live_stale

    def reset(self) -> None:
        """Test-only: limpia el store y resetea el contador. NO usar en runtime."""
        with self._lock:
            self._entries.clear()
            self._next_id = 1
            self._live_stale = False
            self._live_stale_snap = None
            self._latest_disk_mtimes = None


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
