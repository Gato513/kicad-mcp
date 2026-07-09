"""Snapshot Store — arquitectura §4.3-4.4.

Sesión 04 T4: semilla v0.3. Ver ``store.py`` para la implementación.
"""

from __future__ import annotations

from .store import (
    SnapId,
    SnapshotEntry,
    SnapshotStore,
    collect_project_mtimes,
    get_default_store,
)

__all__ = [
    "SnapId",
    "SnapshotEntry",
    "SnapshotStore",
    "collect_project_mtimes",
    "get_default_store",
]
