"""Snapshot Store: cache de estado + índice espacial + invalidator.

MVP: no hay lógica implementada (el servidor es solo-lectura sin bridge). Se
introduce en v0.3 con delta + área local; ver arquitectura §4.3-4.4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

SnapId = int
"""Alias del identificador de snapshot; en v0.3 será monótono creciente."""


@dataclass(frozen=True)
class SnapshotHeader:
    """Metadatos mínimos de un snapshot (implementación futura en v0.3)."""

    snap_id: SnapId
    hash_state: str
    mtimes: tuple[tuple[str, float], ...]


class SnapshotStore(Protocol):
    """Interfaz del store de snapshots (implementación en v0.3)."""

    def create(self, header: SnapshotHeader) -> SnapId:
        """Registra un snapshot nuevo y retorna su id."""
        ...

    def get(self, snap_id: SnapId) -> SnapshotHeader | None:
        """Devuelve el snapshot o ``None`` si expiró/no existe."""
        ...
