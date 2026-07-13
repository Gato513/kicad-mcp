"""Snapshot Store — arquitectura §4.3-4.4.

Sesión 04 T4: semilla v0.3. Ver ``store.py`` para la implementación.
"""

from __future__ import annotations

from .delta import Delta, compute_delta
from .store import (
    SnapId,
    SnapshotEntry,
    SnapshotStore,
    collect_project_mtimes,
    get_default_store,
)
from .validation import validate_base_snap

__all__ = [
    "Delta",
    "SnapId",
    "SnapshotEntry",
    "SnapshotStore",
    "collect_project_mtimes",
    "compute_delta",
    "get_default_store",
    "validate_base_snap",
]
