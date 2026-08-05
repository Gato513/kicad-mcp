"""Decorador ``@mutating_tool`` — DT2 (deuda técnica estructural, sesión 39).

Centraliza el preámbulo de **guardas de entrada** que hoy se repite a mano en
las tools mutantes de ``tools/pcb.py``. Ver ``docs/adr/0014-mutating-tool-
decorator.md`` para el análisis completo (anatomía de las tres familias de
preámbulo encontradas, por qué el epílogo — timer/log/G1/audit/snapshot — NO
entra acá, y las exclusiones justificadas).

**Alcance deliberadamente acotado.** El decorador reemplaza SÓLO:

1. ``_guard_live_stale()`` (D-14.1) — bloquea mutar si el disco tiene un
   ruteo que el editor vivo no refleja.
2. ``check_no_external_disk_edit(...)`` (P3.2) — red de seguridad por mtime,
   independiente de ``base_snap``.
3. ``if base_snap is not None: _check_base_snap(base_snap)``.

Todo lo demás — ``tool_call_timer``, ``_resolve_board``, la lógica de
negocio, ``ensure_session_backup`` (Gate G1), ``audit_record``, el registro
del snapshot post-mutación y ``log_tool_call`` — queda tal cual en el cuerpo
de cada tool. El motivo: esas piezas NO son uniformes entre las 19 tools
mutantes (mtimes reales vs ``None`` vs condicional, retorno ``str`` vs
``dict``, contenido de ``extra`` distinto por tool); absorberlas exigiría
invertir el control de cada ``return`` — lo opuesto de un refactor
quirúrgico. Ver H3 del prompt de sesión 39.

**Orden de las guardas: idéntico al que tenían inline** (live-guard → disk-
check → base_snap). Cuando una guarda lanza, el ``tool_call_timer`` de la
tool decorada todavía no arrancó — igual que hoy, donde el preámbulo corre
antes de abrir el ``with``. Ninguna tool pierde ni gana una emisión de
``log_tool_call`` por este cambio.

**Excluidas de esta sesión** (no llevan el decorador, con justificación):

- ``delete_tracks_bulk``: su preámbulo corre DESPUÉS del early-return de
  ``dry_run`` — hoistearlo haría que un ``dry_run=True`` sobre un board
  live-stale lance ``EXTERNAL_EDIT_DETECTED`` en vez de listar candidatos,
  cambio observable (H3 refutada para ese caso).
- ``route_board`` / ``reload_board_from_disk``: desviaciones deliberadas de
  contrato (D-14.3, ADR-0011, ADR-0012) — no tienen guard de entrada
  simétrico al resto, o el orden de G1 es distinto por diseño.
- Las tres mutantes de esquemático (``add_symbol``, ``set_value``/
  ``set_footprint`` vía ``_set_property_core``, ``connect_pins``): familia
  estructuralmente distinta (sin guard IPC, sin ``_resolve_board``) — fuera
  del alcance de esta sesión.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, TypeVar, cast

from ..errors import ErrorCode, KicadMcpError
from ..snapshots import check_no_external_disk_edit, get_default_store, validate_base_snap
from .world import _resolve_root_pcb, _resolve_root_schematic

F = TypeVar("F", bound=Callable[..., Any])

_SENTINEL: Final = object()


def _project_root() -> Path:
    """Raíz del proyecto (directorio del ``.kicad_sch``). Movido desde ``pcb.py``
    (sesión 39, DT2) para que ``_mutating.py`` no dependa de ``pcb.py``."""
    return _resolve_root_schematic().parent


def _resolve_root_schematic_or_pcb() -> Path:
    """``.kicad_sch`` raíz si existe; si no, el ``.kicad_pcb`` (proyecto pcb-only).

    Movido desde ``pcb.py`` (sesión 39, DT2) — mismo motivo que
    ``_project_root``. ``collect_project_mtimes`` toma el ``.kicad_sch`` y su
    ``.kicad_pcb`` homónimo; para un proyecto pcb-only ancla en el pcb
    (fixture 005).
    """
    try:
        return _resolve_root_schematic()
    except KicadMcpError:
        return _resolve_root_pcb()


def _guard_live_stale() -> None:
    """D-14.1: bloquea mutar/guardar el board vivo si el disco tiene un ruteo
    (de ``route_board``) que el editor vivo aún no refleja.

    Movido desde ``pcb.py`` (sesión 39, DT2). Una mutación IPC + ``save_board``
    posteriores PISARÍAN el ruteo con cobre viejo. Se destraba recargando el
    board en KiCad (File→Revert) y confirmando con
    ``get_world_context(kind='pcb', confirm_reloaded=true)`` (ADR-0011). Las
    tools de DISCO (run_drc, export_*, sch) NO pasan por acá: leen el estado
    correcto y no se bloquean.
    """
    if get_default_store().is_live_stale():
        raise KicadMcpError(
            code=ErrorCode.EXTERNAL_EDIT_DETECTED,
            message="El disco tiene el ruteo de route_board y el editor vivo no.",
            hint=(
                "el disco tiene el ruteo y el editor vivo no; recargá el board en "
                "KiCad (File→Revert) y confirmá con "
                "get_world_context(kind='pcb', confirm_reloaded=true)"
            ),
        )


def _check_base_snap(base_snap: int) -> None:
    """Delega en :func:`validate_base_snap` para preservar contrato compartido.

    Movido desde ``pcb.py`` (sesión 39, DT2). Sesión 05 T2: la lógica vive en
    ``snapshots/validation.py`` para que ``get_context_delta`` (world) valide
    de la misma forma y en un único sitio. Snapshots vivos (``mtimes=None``)
    omiten el chequeo de mtime.
    """
    schematic = _resolve_root_schematic()
    validate_base_snap(get_default_store(), base_snap, schematic)


def mutating_tool(
    tool_name: str,
    *,
    live_guard: bool = True,
    disk_check: bool = True,
    base_snap_check: bool = True,
) -> Callable[[F], F]:
    """Decorador de guardas de entrada para tools mutantes W-IPC de PCB.

    ``tool_name`` es sólo para diagnóstico (no se usa hoy en las guardas,
    pero deja la marca ``__mutating_tool__`` legible y da lugar a mensajes
    de error más específicos en el futuro sin tocar los call sites).

    Flags — ``True`` reproduce el comportamiento uniforme de la Familia A;
    ``False`` documenta una asimetría real y preexistente (ver docstring del
    módulo y ADR-0014):

    - ``disk_check=False``: ``move_footprint`` es la única W-IPC de PCB que
      hoy NO llama ``check_no_external_disk_edit`` (SÍ llama
      ``_guard_live_stale``, ``live_guard`` se deja en su default ``True``) —
      asimetría real y preexistente, documentada en
      ``snapshots/validation.py:57-70``.
    - ``base_snap_check=False``: ``delete_track``/``delete_via`` validan
      ``base_snap`` DENTRO de ``_delete_copper`` — después de resolver si el
      target viene por ``id`` o por ``net``+coordenadas. Hoistear ese check
      acá cambiaría, para una llamada con ``id`` y ``net`` mezclados a la
      vez, el código de error emitido de ``INVALID_PARAMS`` a
      ``SNAPSHOT_STALE`` (cambio de F3) — se deja intacto en el núcleo
      compartido.

    ``base_snap`` se localiza por nombre en la firma decorada (posicional o
    keyword da igual) vía ``inspect.signature().bind_partial`` — no asume
    posición fija.
    """

    def decorator(func: F) -> F:
        sig = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if live_guard:
                _guard_live_stale()
            if disk_check:
                check_no_external_disk_edit(get_default_store(), _resolve_root_schematic_or_pcb())
            if base_snap_check:
                bound = sig.bind_partial(*args, **kwargs)
                base_snap = bound.arguments.get("base_snap", _SENTINEL)
                if base_snap is not _SENTINEL and base_snap is not None:
                    _check_base_snap(cast(int, base_snap))
            return func(*args, **kwargs)

        wrapper.__mutating_tool__ = tool_name  # type: ignore[attr-defined]
        return cast(F, wrapper)

    return decorator
