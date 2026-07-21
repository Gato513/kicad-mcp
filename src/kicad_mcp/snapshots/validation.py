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


def check_no_external_disk_edit(store: SnapshotStore, schematic: Path) -> None:
    """Red de seguridad por mtime, independiente de ``base_snap`` (P3.2, sesión 18).

    ``validate_base_snap`` sólo corre cuando el agente PASA ``base_snap`` —
    ausente, "la mutación procede sin verificación de coherencia" (contrato
    documentado en ``tool-catalog.md``). Ese hueco es justo el que este guard
    cierra para las tools de mayor riesgo de pisar disco: ``save_board``,
    ``add_track``, ``add_via``, ``delete_track``, ``delete_via`` y, desde la
    sesión 19 (P4), ``add_zone``, ``add_keepout_zone``, ``fill_zones``,
    ``delete_zone`` — compara el mtime ACTUAL de los archivos del proyecto
    contra
    ``store.latest_disk_mtimes`` (el último snapshot de DISCO que *cualquier*
    tool de este proceso registró: ``route_board``, ``save_board``,
    ``reload_board_from_disk``, ``get_world_context``...).

    Si el store nunca registró un snapshot de disco en este proceso
    (``latest_disk_mtimes is None``), no hay ancla contra la cual comparar —
    se omite, mismo criterio que ``mtimes=None`` en ``validate_base_snap``
    (sin ancla, no hay falso positivo posible).

    **Complementario, NO sustituto, del flag ``live_stale`` (D-14.1).** Ese
    flag modela "sé que el editor vivo quedó atrás de un ``route_board``
    concreto" — vive en memoria y se pierde entre procesos/reinicios del
    server. Este guard modela algo distinto: "el ``.kicad_pcb`` cambió en
    disco sin que ninguna tool de ESTE proceso lo registrara" — cubre
    ediciones externas silenciosas (humano editando el archivo a mano, otro
    proceso agente concurrente, un ``route_board`` corrido en otro proceso)
    que el flag, por vivir sólo en memoria de un proceso, no puede ver. Es
    red de seguridad: si la recarga automática de P3.1 algún día se rompe
    (bug de kipy, versión distinta de KiCad), este guard sigue evitando que
    un ``save_board`` pise disco en silencio.
    """
    latest = store.latest_disk_mtimes
    if latest is None:
        return  # sin ancla en este proceso todavía — nada que comparar
    current = collect_project_mtimes(schematic)
    for path, mtime in latest.items():
        if current.get(path) != mtime:
            raise KicadMcpError(
                code=ErrorCode.EXTERNAL_EDIT_DETECTED,
                message="El .kicad_pcb cambió en disco fuera de esta sesión del agente.",
                hint=(
                    "el archivo cambió en disco; recargá el board vivo con "
                    "reload_board_from_disk() (o File→Revert) y reintentá"
                ),
            )
