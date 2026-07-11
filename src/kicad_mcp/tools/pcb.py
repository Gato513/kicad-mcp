"""Tools de la categoría ``pcb``: primeras mutaciones (v0.2 semilla).

Sesión 03: ``move_footprint`` y ``add_track``. Ambas:
1. Validan parámetros contra el estado leído por IPC:
   ``COMPONENT_NOT_FOUND`` / ``NET_NOT_FOUND`` con similares (edit distance)
   e ``INVALID_PARAMS`` para coordenadas fuera del bounding box.
2. Disparan el Gate G1 (una sola vez por proyecto en la sesión del server):
   backup a ``.kicad-mcp/backups/<ts>/`` y ``git commit`` si es repo.
3. Registran la mutación en ``.kicad-mcp/audit.jsonl`` (arquitectura §4.6).
4. Devuelven confirmación **corta** (~30 tokens, ADR-0004).

El bridge IPC se instancia por default con la fábrica real; los tests
pueden pasar un fake vía ``register(mcp, ipc_bridge=fake)``.
"""

from __future__ import annotations

import difflib
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..audit.logger import record as audit_record
from ..bridge.ipc import BoardHandle, FootprintData, IpcBridge, Mm
from ..bridge.state_builder import build_state_from_board, build_state_from_snapshot
from ..errors import ErrorCode, KicadMcpError
from ..gates.g1 import ensure_session_backup
from ..logging_config import estimate_tokens, log_tool_call, tool_call_timer
from ..snapshots import get_default_store, validate_base_snap
from ..tools.world import _resolve_root_schematic

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _project_root() -> Path:
    return _resolve_root_schematic().parent


def _similars(target: str, candidates: list[str], *, limit: int = 3) -> list[str]:
    """Sugerencias por edit-distance para hints de COMPONENT/NET_NOT_FOUND."""
    return difflib.get_close_matches(target, candidates, n=limit, cutoff=0.5)


def _find_target(footprints: tuple[FootprintData, ...], ref: str) -> FootprintData:
    """Localiza el ``FootprintData`` con ``ref`` en el snapshot ya leído.

    Precondición: ``ref`` está en ``footprints`` (la validación se hizo
    antes con ``ctx.refs``). Si no lo encuentra es un bug estructural del
    llamador, no un caso a manejar en runtime.
    """
    for fp in footprints:
        if fp.ref == ref:
            return fp
    raise KicadMcpError(
        code=ErrorCode.COMPONENT_NOT_FOUND,
        message=f"Footprint {ref} no está en el snapshot leído.",
        hint="Bug interno: ref validado pero no localizado en el snapshot.",
    )


def _derive_post_state(
    pre_footprints: tuple[FootprintData, ...],
    ref: str,
    x_mm: float,
    y_mm: float,
) -> tuple[FootprintData, ...]:
    """Aplica la mutación conocida sobre el snapshot pre — cero IPC.

    D-08.2: la mutación la disparamos nosotros, así que el post-estado es
    predecible: reemplazar el footprint mutado por una copia con la
    posición nueva. La verificación puntual por KIID (D-08.2) confirma
    que KiCad aplicó exactamente lo pedido (redondeo half-even known ±1 nm);
    si diverge, el llamador cae a re-lectura completa (fallback).
    """
    updated: list[FootprintData] = []
    for fp in pre_footprints:
        if fp.ref == ref:
            updated.append(
                FootprintData(
                    ref=fp.ref,
                    value=fp.value,
                    x_mm=Mm(x_mm),
                    y_mm=Mm(y_mm),
                    pads=fp.pads,
                    kiid=fp.kiid,
                )
            )
        else:
            updated.append(fp)
    return tuple(updated)


def _register_post_snapshot(
    bridge: IpcBridge,
    board: BoardHandle,
    *,
    pre_footprints: tuple[FootprintData, ...],
    mutated_kiid: str,
    mutated_ref: str,
    target_x_mm: float,
    target_y_mm: float,
    mutation_timings: dict[str, float],
) -> Any:
    """Construye el ``NormalizedState`` post-mutación (D-08.2).

    Estrategia:
    1. Deriva localmente el post-snapshot (cero IPC) a partir de
       ``pre_footprints`` reemplazando el mutado con la posición pedida.
    2. Verifica el efecto real via ``verify_footprint_by_kiid`` (una
       única request filtrada por KiCad, no itera). Compara la posición
       leída contra la derivada con tolerancia de ±1 nm (redondeo
       banker's known).
    3. Si diverge (o no se pudo capturar KIID) → fallback a re-lectura
       completa (``snapshot_footprints``) para no cachear un estado
       incorrecto. El fallback deja huella en ``mutation_timings``
       (``post_fallback=True``) y en el log JSON de la tool.

    Retorna el ``NormalizedState`` (kind="pcb") listo para
    ``store.register(..., mtimes=None)``.
    """
    derived = _derive_post_state(pre_footprints, mutated_ref, target_x_mm, target_y_mm)
    # Sin KIID no hay verificación puntual: la única forma segura es
    # re-leer completo. Es el path que toman los tests unit con fakes
    # antiguos que no capturan KIID.
    if not mutated_kiid:
        mutation_timings["post_fallback"] = True
        return build_state_from_board(bridge, board)

    verify_start = time.perf_counter()
    live = bridge.verify_footprint_by_kiid(board, mutated_kiid)
    mutation_timings["verify_ms"] = (time.perf_counter() - verify_start) * 1000

    if live is None:
        # KIID desapareció entre la mutación y la verificación (edición
        # externa concurrente). El derivado no es fiable → re-leer.
        mutation_timings["post_fallback"] = True
        return build_state_from_board(bridge, board)

    tolerance_mm = 1e-6  # ±1 nm — banker's rounding known (docs/adr/…)
    dx = abs(float(live.x_mm) - target_x_mm)
    dy = abs(float(live.y_mm) - target_y_mm)
    if dx <= tolerance_mm and dy <= tolerance_mm:
        return build_state_from_snapshot(derived)

    # Divergencia real (KiCad clampeó/redondeó distinto del previsto):
    # log warning + fallback a re-lectura completa. Cero pérdida de
    # corrección; sólo pagamos el costo del snapshot completo esa vez.
    import logging

    logging.getLogger("kicad_mcp").warning(
        '{"tool_name":"post_snapshot_fallback","ref":"%s","kiid":"%s",'
        '"target_x":%s,"target_y":%s,"live_x":%s,"live_y":%s,'
        '"delta_x_mm":%s,"delta_y_mm":%s}',
        mutated_ref,
        mutated_kiid,
        target_x_mm,
        target_y_mm,
        float(live.x_mm),
        float(live.y_mm),
        dx,
        dy,
    )
    mutation_timings["post_fallback"] = True
    return build_state_from_board(bridge, board)


def _resolve_board(bridge: IpcBridge) -> BoardHandle:
    board = bridge.get_open_board()
    if board is None:
        raise KicadMcpError(
            code=ErrorCode.PROJECT_NOT_FOUND,
            message="No hay board abierto en KiCad.",
            hint="Abrí el .kicad_pcb del proyecto activo en KiCad.",
        )
    return board


def _check_base_snap(base_snap: int) -> None:
    """Delega en :func:`validate_base_snap` para preservar contrato compartido.

    Sesión 05 T2: la lógica vive en ``snapshots/validation.py`` para que
    ``get_context_delta`` (world) valide de la misma forma y en un único
    sitio. Snapshots vivos (``mtimes=None``) omiten el chequeo de mtime.
    """
    schematic = _resolve_root_schematic()
    validate_base_snap(get_default_store(), base_snap, schematic)


def register(mcp: FastMCP, *, ipc_bridge: IpcBridge | None = None) -> None:
    """Registra las tools de mutación en la instancia FastMCP."""

    bridge = ipc_bridge or IpcBridge()

    @mcp.tool(
        name="move_footprint",
        description="Mueve un footprint del PCB a (x_mm, y_mm)",
    )
    def move_footprint(ref: str, x_mm: float, y_mm: float, base_snap: int | None = None) -> str:
        with tool_call_timer() as timer:
            root = _project_root()
            # Validación de snap opcional (sesión 04 T4). Se hace ANTES de
            # tocar IPC para que un stale/edición externa no dispare G1.
            if base_snap is not None:
                _check_base_snap(base_snap)
            board = _resolve_board(bridge)

            # D-08.1: UNA sola pasada O(board) para el pre-work. Devuelve
            # refs (validación), bbox (validación) y footprints con KIID
            # (localización del target + snapshot pre para derivación).
            read_start = time.perf_counter()
            ctx = bridge.read_board_context(board)
            read_ms = (time.perf_counter() - read_start) * 1000
            refs = list(ctx.refs)
            bbox = ctx.bbox
            if ref not in refs:
                similars = _similars(ref, refs)
                hint = "refs similares: " + ", ".join(similars) if similars else "sin sugerencias"
                _audit_error(
                    root,
                    "move_footprint",
                    {"ref": ref, "x_mm": x_mm, "y_mm": y_mm},
                    ErrorCode.COMPONENT_NOT_FOUND,
                )
                raise KicadMcpError(
                    code=ErrorCode.COMPONENT_NOT_FOUND,
                    message=f"Footprint {ref} no existe en el board.",
                    hint=hint,
                )
            if not bbox.contains(Mm(x_mm), Mm(y_mm)):
                _audit_error(
                    root,
                    "move_footprint",
                    {"ref": ref, "x_mm": x_mm, "y_mm": y_mm},
                    ErrorCode.INVALID_PARAMS,
                )
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"Coordenadas ({x_mm}, {y_mm}) fuera del bounding box del board.",
                    hint=(
                        f"Rango permitido: x∈[{bbox.min_x:.1f}, {bbox.max_x:.1f}], "
                        f"y∈[{bbox.min_y:.1f}, {bbox.max_y:.1f}] (mm)."
                    ),
                )
            target = _find_target(ctx.footprints, ref)

            backup_info = ensure_session_backup(root)  # Gate G1
            # Sesión 07 T5 (D-07.5) / Sesión 08 D-08.1: la mutación rellena
            # ``timings["lookup_ms"]`` con la latencia del target-lookup en
            # el bridge. Con ``kiid`` resuelto, es O(1) de red — antes era
            # una pasada O(board) de ~3 s.
            mutation_timings: dict[str, float] = {}
            bridge.move_footprint(
                board,
                ref,
                Mm(x_mm),
                Mm(y_mm),
                kiid=target.kiid or None,
                timings=mutation_timings,
            )
            # T1 (D-08.1): el post-snapshot todavía re-lee el board. En T2
            # (D-08.2) se reemplaza por derivación local + verificación
            # puntual por KIID. Aislar aquí facilita el cambio incremental.
            new_state = _register_post_snapshot(
                bridge,
                board,
                pre_footprints=ctx.footprints,
                mutated_kiid=target.kiid,
                mutated_ref=ref,
                target_x_mm=x_mm,
                target_y_mm=y_mm,
                mutation_timings=mutation_timings,
            )
            snap_id = get_default_store().register(new_state, mtimes=None)
            audit_record(
                root,
                tool="move_footprint",
                params={"ref": ref, "x_mm": x_mm, "y_mm": y_mm, "base_snap": base_snap},
                result={"snap": snap_id, "backup": backup_info.get("backup")},
            )
            confirmation = f"OK move_footprint {ref} -> ({x_mm:.1f}, {y_mm:.1f}) [snap:{snap_id}]"
        extra: dict[str, Any] = {
            "ref": ref,
            "backup_already_done": backup_info.get("already_done"),
            "base_snap": base_snap,
            "read_ms": round(read_ms, 3),
        }
        if "lookup_ms" in mutation_timings:
            extra["lookup_ms"] = round(mutation_timings["lookup_ms"], 3)
        if "verify_ms" in mutation_timings:
            extra["verify_ms"] = round(mutation_timings["verify_ms"], 3)
        if mutation_timings.get("post_fallback"):
            extra["post_fallback"] = True
        log_tool_call(
            tool_name="move_footprint",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(confirmation),
            snap_id=snap_id,
            extra=extra,
        )
        return confirmation

    @mcp.tool(
        name="add_track",
        description="Agrega un track lineal entre dos puntos del PCB",
    )
    def add_track(
        net: str,
        start_x_mm: float,
        start_y_mm: float,
        end_x_mm: float,
        end_y_mm: float,
        width_mm: float = 0.25,
        layer: str = "F.Cu",
        base_snap: int | None = None,
    ) -> str:
        with tool_call_timer() as timer:
            root = _project_root()
            if base_snap is not None:
                _check_base_snap(base_snap)
            board = _resolve_board(bridge)

            # D-08.1: bbox + snapshot pre en una sola pasada. list_net_names
            # sigue aparte (es una pasada sobre get_nets, no get_footprints).
            read_start = time.perf_counter()
            ctx = bridge.read_board_context(board)
            nets = bridge.list_net_names(board)
            read_ms = (time.perf_counter() - read_start) * 1000
            if net not in nets:
                similars = _similars(net, nets)
                hint = "nets similares: " + ", ".join(similars) if similars else "sin sugerencias"
                _audit_error(
                    root,
                    "add_track",
                    _track_params(net, start_x_mm, start_y_mm, end_x_mm, end_y_mm, width_mm, layer),
                    ErrorCode.NET_NOT_FOUND,
                )
                raise KicadMcpError(
                    code=ErrorCode.NET_NOT_FOUND,
                    message=f"Net {net} no existe en el board.",
                    hint=hint,
                )
            bbox = ctx.bbox
            for label, x, y in (
                ("start", start_x_mm, start_y_mm),
                ("end", end_x_mm, end_y_mm),
            ):
                if not bbox.contains(Mm(x), Mm(y)):
                    _audit_error(
                        root,
                        "add_track",
                        _track_params(
                            net, start_x_mm, start_y_mm, end_x_mm, end_y_mm, width_mm, layer
                        ),
                        ErrorCode.INVALID_PARAMS,
                    )
                    raise KicadMcpError(
                        code=ErrorCode.INVALID_PARAMS,
                        message=f"Coordenadas de {label} fuera del bounding box del board.",
                        hint=(
                            f"Rango permitido: x∈[{bbox.min_x:.1f}, {bbox.max_x:.1f}], "
                            f"y∈[{bbox.min_y:.1f}, {bbox.max_y:.1f}] (mm)."
                        ),
                    )

            backup_info = ensure_session_backup(root)  # Gate G1
            add_track_timings: dict[str, float] = {}
            bridge.add_track(
                board,
                net=net,
                start_mm=(Mm(start_x_mm), Mm(start_y_mm)),
                end_mm=(Mm(end_x_mm), Mm(end_y_mm)),
                width_mm=Mm(width_mm),
                layer=layer,
                timings=add_track_timings,
            )
            # Sesión 08 D-08.2: ``add_track`` NO altera la lista de
            # componentes (las tracks no viven en NormalizedState). El
            # post-estado es idéntico al pre en términos de NormalizedState,
            # así que derivamos del snapshot leído sin re-iterar el board.
            # Cero pasadas post.
            new_state = build_state_from_snapshot(ctx.footprints)
            snap_id = get_default_store().register(new_state, mtimes=None)
            track_params = _track_params(
                net, start_x_mm, start_y_mm, end_x_mm, end_y_mm, width_mm, layer
            )
            track_params["base_snap"] = base_snap
            audit_record(
                root,
                tool="add_track",
                params=track_params,
                result={"snap": snap_id, "backup": backup_info.get("backup")},
            )
            confirmation = (
                f"OK add_track {net} ({start_x_mm:.1f},{start_y_mm:.1f})->"
                f"({end_x_mm:.1f},{end_y_mm:.1f}) w={width_mm:.2f} @{layer} [snap:{snap_id}]"
            )
        add_track_extra: dict[str, Any] = {
            "net": net,
            "layer": layer,
            "base_snap": base_snap,
            "read_ms": round(read_ms, 3),
        }
        if "lookup_ms" in add_track_timings:
            add_track_extra["lookup_ms"] = round(add_track_timings["lookup_ms"], 3)
        log_tool_call(
            tool_name="add_track",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(confirmation),
            snap_id=snap_id,
            extra=add_track_extra,
        )
        return confirmation

    @mcp.tool(
        name="add_via",
        description="Agrega una via pasante en (x_mm, y_mm) asignada a un net",
    )
    def add_via(
        x_mm: float,
        y_mm: float,
        net: str,
        size_mm: float = 0.8,
        drill_mm: float = 0.4,
        base_snap: int | None = None,
    ) -> str:
        # D-09.3 (B3): via pasante vía kipy Via + create_items, mismo pipeline
        # rápido que add_track (D-08.1/D-08.2). Una via NO vive en
        # NormalizedState (que modela footprints + pines), así que —igual que
        # add_track— el post-estado es idéntico al pre en términos de
        # NormalizedState: se DERIVA del snapshot leído (cero pasadas post,
        # sin re-lectura ni verificación puntual por KIID). No hay retry en la
        # escritura (D-07.1): add_via viaja por _supervise directo en el bridge.
        with tool_call_timer() as timer:
            root = _project_root()
            if base_snap is not None:
                _check_base_snap(base_snap)
            board = _resolve_board(bridge)

            read_start = time.perf_counter()
            ctx = bridge.read_board_context(board)
            nets = bridge.list_net_names(board)
            read_ms = (time.perf_counter() - read_start) * 1000
            if net not in nets:
                similars = _similars(net, nets)
                hint = "nets similares: " + ", ".join(similars) if similars else "sin sugerencias"
                _audit_error(
                    root,
                    "add_via",
                    _via_params(net, x_mm, y_mm, size_mm, drill_mm),
                    ErrorCode.NET_NOT_FOUND,
                )
                raise KicadMcpError(
                    code=ErrorCode.NET_NOT_FOUND,
                    message=f"Net {net} no existe en el board.",
                    hint=hint,
                )
            bbox = ctx.bbox
            if not bbox.contains(Mm(x_mm), Mm(y_mm)):
                _audit_error(
                    root,
                    "add_via",
                    _via_params(net, x_mm, y_mm, size_mm, drill_mm),
                    ErrorCode.INVALID_PARAMS,
                )
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"Coordenadas ({x_mm}, {y_mm}) fuera del bounding box del board.",
                    hint=(
                        f"Rango permitido: x∈[{bbox.min_x:.1f}, {bbox.max_x:.1f}], "
                        f"y∈[{bbox.min_y:.1f}, {bbox.max_y:.1f}] (mm)."
                    ),
                )
            if not (0 < drill_mm < size_mm):
                _audit_error(
                    root,
                    "add_via",
                    _via_params(net, x_mm, y_mm, size_mm, drill_mm),
                    ErrorCode.INVALID_PARAMS,
                )
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"Drill {drill_mm} mm inválido para una via de {size_mm} mm.",
                    hint="El drill debe ser positivo y estrictamente menor al diámetro.",
                )

            backup_info = ensure_session_backup(root)  # Gate G1
            add_via_timings: dict[str, float] = {}
            bridge.add_via(
                board,
                net=net,
                x_mm=Mm(x_mm),
                y_mm=Mm(y_mm),
                diameter_mm=Mm(size_mm),
                drill_mm=Mm(drill_mm),
                timings=add_via_timings,
            )
            # Post-estado: la via no altera la lista de componentes → derivamos
            # del snapshot pre (cero pasadas post, idéntico a add_track).
            new_state = build_state_from_snapshot(ctx.footprints)
            snap_id = get_default_store().register(new_state, mtimes=None)
            via_params = _via_params(net, x_mm, y_mm, size_mm, drill_mm)
            via_params["base_snap"] = base_snap
            audit_record(
                root,
                tool="add_via",
                params=via_params,
                result={"snap": snap_id, "backup": backup_info.get("backup")},
            )
            confirmation = (
                f"OK add_via {net} @({x_mm:.1f},{y_mm:.1f}) "
                f"d{size_mm:.2f}/{drill_mm:.2f} [snap:{snap_id}]"
            )
        add_via_extra: dict[str, Any] = {
            "net": net,
            "base_snap": base_snap,
            "read_ms": round(read_ms, 3),
        }
        if "lookup_ms" in add_via_timings:
            add_via_extra["lookup_ms"] = round(add_via_timings["lookup_ms"], 3)
        log_tool_call(
            tool_name="add_via",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(confirmation),
            snap_id=snap_id,
            extra=add_via_extra,
        )
        return confirmation


def _track_params(
    net: str,
    sx: float,
    sy: float,
    ex: float,
    ey: float,
    width: float,
    layer: str,
) -> dict[str, Any]:
    return {
        "net": net,
        "start": [sx, sy],
        "end": [ex, ey],
        "width_mm": width,
        "layer": layer,
    }


def _via_params(net: str, x: float, y: float, size: float, drill: float) -> dict[str, Any]:
    return {"net": net, "pos": [x, y], "size_mm": size, "drill_mm": drill}


def _audit_error(
    root: Path,
    tool: str,
    params: dict[str, Any],
    code: ErrorCode,
) -> None:
    """Registra una mutación rechazada. No suprime la excepción del llamador."""
    audit_record(root, tool=tool, params=params, error_code=code.value)
