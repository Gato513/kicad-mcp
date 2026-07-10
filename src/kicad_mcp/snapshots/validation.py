"""Validación de ``base_snap`` contra el Snapshot Store (sesión 04 T4, 05 T2).

Compartida por ``pcb`` (``move_footprint`` / ``add_track``) y ``world``
(``get_context_delta``). La lógica es idéntica: el patrón centralizado
evita drift entre sitios y facilita cambios futuros (p. ej. mecanismo
de detección para snapshots vivos, hoy diferido — ADR-0007).
"""

from __future__ import annotations

from pathlib import Path

from ..errors import ErrorCode, KicadMcpError
from .store import SnapshotEntry, SnapshotStore, collect_project_mtimes


def validate_base_snap(store: SnapshotStore, base_snap: int, schematic: Path) -> SnapshotEntry:
    """Chequea el ``base_snap`` y devuelve la entrada del store si es válida.

    - Ausente del store → ``SNAPSHOT_STALE`` con ``data={"base_snap": ...,
      "retention": ...}`` para que el agente pueda correlacionarlo sin
      parsear el mensaje (sesión 05 T2; F3 intacta: el código no cambia).
    - Presente con ``mtimes`` dict y algún archivo cambió en disco →
      ``EXTERNAL_EDIT_DETECTED``.
    - Presente con ``mtimes=None`` (snapshot vivo, ADR-0007) → **se omite**
      el chequeo de mtime: el estado provino de una fuente in-memory y no
      hay un mtime de disco al que anclarlo. La limitación aceptada es
      que ediciones externas concurrentes no se detectan mientras el
      agente encadena mutaciones sobre snapshots vivos.
    """
    entry = store.get(base_snap)
    if entry is None:
        raise KicadMcpError(
            code=ErrorCode.SNAPSHOT_STALE,
            message=f"base_snap={base_snap} no está en el store (retención={store.retention}).",
            hint="Pedí get_world_context de nuevo antes de reintentar la operación.",
            data={"base_snap": base_snap, "retention": store.retention},
        )
    if entry.mtimes is None:
        return entry  # snapshot vivo → sin chequeo de mtime (ADR-0007)
    current_mtimes = collect_project_mtimes(schematic)
    for path, mtime in entry.mtimes.items():
        current = current_mtimes.get(path)
        if current != mtime:
            raise KicadMcpError(
                code=ErrorCode.EXTERNAL_EDIT_DETECTED,
                message="Un archivo del proyecto fue editado fuera del agente.",
                hint=(
                    "El usuario modificó el proyecto en KiCad entre el "
                    "get_world_context y esta operación; pedí contexto de "
                    "nuevo antes de continuar."
                ),
            )
    return entry
