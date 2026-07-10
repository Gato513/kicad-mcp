"""Tools de la categoría ``world``: ``get_world_context`` (MVP).

Ver `docs/specs/tool-catalog.md §world`. El MVP implementa
``get_world_context`` cableado al ``state_builder`` (netlist + posiciones)
y al ``encoder`` con presupuesto de tokens y área local.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from ..bridge.state_builder import build_state_cached, build_state_from_board
from ..errors import ErrorCode, KicadMcpError
from ..logging_config import estimate_tokens, log_tool_call, tool_call_timer
from ..snapshots import collect_project_mtimes, get_default_store, validate_base_snap
from ..snapshots.store import SnapshotEntry
from ..toon.encoder import encode, encode_delta, encode_delta_with_budget
from ..toon.schema import NormalizedState

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..bridge.ipc import IpcBridge


def _resolve_root_schematic() -> Path:
    """Resuelve el .kicad_sch raíz del proyecto activo.

    MVP: env ``KICAD_MCP_PROJECT`` apunta a la carpeta del proyecto; se
    localiza el ``.kicad_sch`` cuyo nombre coincide con el ``.kicad_pro``
    (o el único ``.kicad_sch`` presente si no hay ``.kicad_pro``).
    """
    raw = os.environ.get("KICAD_MCP_PROJECT")
    if not raw:
        raise KicadMcpError(
            code=ErrorCode.PROJECT_NOT_FOUND,
            message="No hay proyecto activo.",
            hint="Exporta KICAD_MCP_PROJECT con la ruta del proyecto.",
        )
    root = Path(raw).expanduser()
    if not root.is_dir():
        raise KicadMcpError(
            code=ErrorCode.PROJECT_NOT_FOUND,
            message="KICAD_MCP_PROJECT no apunta a un directorio.",
            hint=f"Ruta: {root.name}",
        )
    pro_files = list(root.glob("*.kicad_pro"))
    if pro_files:
        candidate = pro_files[0].with_suffix(".kicad_sch")
        if candidate.is_file():
            return candidate.resolve()
    sch_files = list(root.glob("*.kicad_sch"))
    if len(sch_files) == 1:
        return sch_files[0].resolve()
    raise KicadMcpError(
        code=ErrorCode.PROJECT_NOT_FOUND,
        message=(
            "No se pudo determinar el .kicad_sch raíz "
            f"({len(sch_files)} candidatos en el proyecto)."
        ),
        hint="Renombrar el esquemático para que coincida con el .kicad_pro.",
    )


def _resolve_root_pcb() -> Path:
    """Resuelve el .kicad_pcb raíz del proyecto activo (paralelo a _resolve_root_schematic).

    Sesión 04 T5: fixture 005_pcb_limpio es pcb-only (sin .kicad_sch). El
    export_manufacturing no necesita esquemático, así que ancla en el pcb
    directamente. Otras tools siguen requiriendo sch.
    """
    raw = os.environ.get("KICAD_MCP_PROJECT")
    if not raw:
        raise KicadMcpError(
            code=ErrorCode.PROJECT_NOT_FOUND,
            message="No hay proyecto activo.",
            hint="Exporta KICAD_MCP_PROJECT con la ruta del proyecto.",
        )
    root = Path(raw).expanduser()
    if not root.is_dir():
        raise KicadMcpError(
            code=ErrorCode.PROJECT_NOT_FOUND,
            message="KICAD_MCP_PROJECT no apunta a un directorio.",
            hint=f"Ruta: {root.name}",
        )
    pro_files = list(root.glob("*.kicad_pro"))
    if pro_files:
        candidate = pro_files[0].with_suffix(".kicad_pcb")
        if candidate.is_file():
            return candidate.resolve()
    pcb_files = list(root.glob("*.kicad_pcb"))
    if len(pcb_files) == 1:
        return pcb_files[0].resolve()
    raise KicadMcpError(
        code=ErrorCode.PROJECT_NOT_FOUND,
        message=(
            "No se pudo determinar el .kicad_pcb raíz "
            f"({len(pcb_files)} candidatos en el proyecto)."
        ),
        hint="Renombrar el PCB para que coincida con el .kicad_pro.",
    )


def _build_current_for(
    entry: SnapshotEntry, schematic: Path, ipc_bridge: IpcBridge, base_snap: int
) -> tuple[NormalizedState, int, bool]:
    """Materializa ``curr`` para ``get_context_delta`` según el kind del base.

    D-06.1v2 (sesión 06): el snapshot base gobierna cómo se construye el
    estado actual. Un base vivo (``mtimes is None``) de kind ``pcb`` viene
    de una mutación in-memory (ADR-0007) y su contraparte hoy es el board
    vivo de kipy; leer disco daría estado invertido (el disco no vio la
    mutación aún) y además compararía sch contra pcb.

    Devuelve ``(state, new_snap_id, cache_hit)``. El ``new_snap`` ya está
    registrado en el store cuando esta función retorna (con ``mtimes=None``
    para el path vivo, con mtimes de disco para el path sch).
    """
    store = get_default_store()
    if entry.mtimes is None:
        if entry.state.kind != "pcb":
            raise KicadMcpError(
                code=ErrorCode.KICAD_CLI_FAILED,
                message="Estado interno inconsistente: snapshot vivo de kind no-pcb.",
                hint=(
                    "No hay camino que registre snapshots vivos de esquemático; "
                    "reportar como bug al humano."
                ),
            )
        board = ipc_bridge.get_open_board()
        if board is None:
            raise KicadMcpError(
                code=ErrorCode.SNAPSHOT_STALE,
                message=(
                    "La cadena viva post-mutación se perdió; el board de KiCad no está disponible."
                ),
                hint=("Re-sincronizá con get_world_context antes de reintentar get_context_delta."),
                data={"base_snap": base_snap, "reason": "live_chain_lost"},
            )
        curr_raw = build_state_from_board(ipc_bridge, board)
        new_snap = store.register(curr_raw, mtimes=None)
        return curr_raw, new_snap, False
    curr_raw, cache_hit = build_state_cached(schematic, snap=0)
    mtimes = collect_project_mtimes(schematic)
    new_snap = store.register(curr_raw, mtimes)
    return curr_raw, new_snap, cache_hit


def register(mcp: FastMCP, *, ipc_bridge: IpcBridge | None = None) -> None:
    """Registra las tools de la categoría ``world``.

    ``ipc_bridge`` alimenta la rama viva de ``get_context_delta`` (D-06.1v2):
    cuando el ``base_snap`` es vivo ``kind="pcb"``, el estado actual se
    reconstruye desde el board de kipy y no desde el ``.kicad_sch`` de disco.
    En runtime lo inyecta ``tools.register_all`` (singleton por proceso).
    Los tests unit pueden pasar un fake compartido con ``pcb``.
    """
    from ..bridge.ipc import IpcBridge as _IpcBridge

    bridge = ipc_bridge if ipc_bridge is not None else _IpcBridge()

    @mcp.tool(
        name="get_world_context",
        description="Estado del proyecto en TOON v1",
    )
    def get_world_context(
        max_tokens: int = 800,
        focus_ref: str | None = None,
        radius_mm: float | None = None,
    ) -> str:
        # Devuelve el string TOON puro (sin envelope JSON). La cabecera
        # ya lleva ``snap`` y ``kind`` — reintroducir un wrapper añadía
        # ~30 % de tokens sin dato nuevo (medido en sesión 02).
        # ``snap`` se obtiene del Snapshot Store (sesión 04 T4): monótono
        # por proceso, con retención de 10.
        with tool_call_timer() as timer:
            schematic = _resolve_root_schematic()
            # Registro en el store: reconstruimos con snap=0 (placeholder) y
            # luego materializamos el snap real via model_copy.
            state_raw, cache_hit = build_state_cached(schematic, snap=0)
            mtimes = collect_project_mtimes(schematic)
            snap_id = get_default_store().register(state_raw, mtimes)
            state = state_raw.model_copy(update={"snap": snap_id})
            toon = encode(
                state,
                max_tokens=max_tokens,
                focus_ref=focus_ref,
                radius_mm=radius_mm,
            )
        log_tool_call(
            tool_name="get_world_context",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(toon),
            snap_id=snap_id,
            extra={
                "focus_ref": focus_ref,
                "radius_mm": radius_mm,
                "max_tokens": max_tokens,
                "cache_hit": cache_hit,
                "kind": state.kind,
            },
        )
        return toon

    @mcp.tool(
        name="get_context_delta",
        description="Delta TOON entre un base_snap y el estado actual",
    )
    def get_context_delta(
        base_snap: int,
        focus_ref: str,
        radius_mm: float,
        max_tokens: int | None = None,
    ) -> str:
        """Serializa el delta entre ``base_snap`` y el estado actual (spec §3).

        Errores:
        - ``PROJECT_NOT_FOUND`` si no hay proyecto activo.
        - ``SNAPSHOT_STALE`` si ``base_snap`` no está en el store.
        - ``EXTERNAL_EDIT_DETECTED`` si el snapshot base era de disco y algún
          archivo del proyecto cambió en el filesystem desde entonces. Un
          snapshot vivo (ADR-0007) omite este chequeo.
        - ``CONTEXT_BUDGET_IMPOSSIBLE`` si ni la degradación §4 hace caber
          el delta en ``max_tokens`` (D-05.5, mismo mecanismo que el estado
          completo).

        El nuevo estado se registra como un snapshot fresco antes de emitir
        el delta; su ``snap_id`` va en la cabecera ``DTOON`` como ``snap:``.
        """
        with tool_call_timer() as timer:
            schematic = _resolve_root_schematic()
            store = get_default_store()
            entry = validate_base_snap(store, base_snap, schematic)

            curr_raw, new_snap, cache_hit = _build_current_for(entry, schematic, bridge, base_snap)
            # Kinds homogéneos: si el path vivo/disco emite un kind distinto
            # al del base (no debería, cada rama es kind-específica), es un
            # bug interno. Un delta con kinds cruzados es semánticamente
            # basura — F3 respetada: usamos KICAD_CLI_FAILED como código
            # para "estado interno inconsistente" (precedente en
            # state_builder._rebuild).
            if curr_raw.kind != entry.state.kind:
                raise KicadMcpError(
                    code=ErrorCode.KICAD_CLI_FAILED,
                    message=(
                        "Estado interno inconsistente: kind del base_snap no "
                        "coincide con el estado actual."
                    ),
                    hint=(
                        f"base kind={entry.state.kind}, curr kind={curr_raw.kind}. "
                        "Reportar como bug al humano."
                    ),
                )
            curr = curr_raw.model_copy(update={"snap": new_snap})

            if max_tokens is None:
                toon = encode_delta(
                    curr,
                    base=entry.state,
                    focus_ref=focus_ref,
                    radius_mm=radius_mm,
                    base_snap=base_snap,
                )
            else:
                toon = encode_delta_with_budget(
                    curr,
                    base=entry.state,
                    focus_ref=focus_ref,
                    radius_mm=radius_mm,
                    base_snap=base_snap,
                    max_tokens=max_tokens,
                )
        log_tool_call(
            tool_name="get_context_delta",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(toon),
            snap_id=new_snap,
            extra={
                "base_snap": base_snap,
                "focus_ref": focus_ref,
                "radius_mm": radius_mm,
                "max_tokens": max_tokens,
                "cache_hit": cache_hit,
                "kind": curr.kind,
            },
        )
        return toon
