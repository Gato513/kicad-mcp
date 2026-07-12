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
import math
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..audit.logger import record as audit_record
from ..bridge.ipc import (
    BoardHandle,
    ComponentDetail,
    CopperItem,
    FootprintData,
    IpcBridge,
    Mm,
)
from ..bridge.state_builder import build_state_from_board, build_state_from_snapshot
from ..errors import ErrorCode, KicadMcpError
from ..gates.g1 import ensure_session_backup
from ..logging_config import estimate_tokens, log_tool_call, tool_call_timer
from ..snapshots import collect_project_mtimes, get_default_store, validate_base_snap
from ..tools.world import _resolve_root_pcb, _resolve_root_schematic

# Tolerancia por defecto del matching geométrico del borrado dirigido (D-11.2):
# la track/via cuyo segmento pasa a ≤ este radio del punto es candidata. 0.5 mm
# = ~20 mil, holgado frente al grid de 1.27 mm pero fino para no barrer vecinas.
_DELETE_TOLERANCE_MM: float = 0.5

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


def _dist_point_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Distancia euclídea del punto ``(px,py)`` al segmento ``(ax,ay)-(bx,by)``."""
    dx = bx - ax
    dy = by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0.0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _copper_distance_mm(item: CopperItem, x: float, y: float) -> float:
    """Distancia del punto ``(x,y)`` a un ``CopperItem`` (mm).

    - via: distancia al centro.
    - track: distancia al segmento start→end.
    - arc: distancia a la polilínea start→mid→end (aproximación del arco).
    """
    if item.kind == "via" or item.end_x_mm is None or item.end_y_mm is None:
        return math.hypot(x - float(item.start_x_mm), y - float(item.start_y_mm))
    sx, sy = float(item.start_x_mm), float(item.start_y_mm)
    ex, ey = float(item.end_x_mm), float(item.end_y_mm)
    if item.kind == "arc" and item.mid_x_mm is not None and item.mid_y_mm is not None:
        mx, my = float(item.mid_x_mm), float(item.mid_y_mm)
        return min(
            _dist_point_segment(x, y, sx, sy, mx, my),
            _dist_point_segment(x, y, mx, my, ex, ey),
        )
    return _dist_point_segment(x, y, sx, sy, ex, ey)


def _match_copper(
    items: tuple[CopperItem, ...],
    x: float,
    y: float,
    *,
    kinds: tuple[str, ...],
    tolerance_mm: float,
) -> tuple[CopperItem | None, list[CopperItem]]:
    """Devuelve ``(target, candidatos)`` dentro de la tolerancia (D-11.2).

    ``target`` es el ítem único dentro de tolerancia; si hay 2+ dentro de
    tolerancia, ``target`` es ``None`` y ``candidatos`` los lista (para el
    ``INVALID_PARAMS`` que pide refinar). Si ninguno cae dentro, ambos vacíos.
    NUNCA elige "el más cercano" en ambigüedad — es una decisión explícita del
    diseño (borrar el ítem equivocado es irreversible desde la sesión).
    """
    within = [
        it for it in items if it.kind in kinds and _copper_distance_mm(it, x, y) <= tolerance_mm
    ]
    if len(within) == 1:
        return within[0], within
    return None, within


def _parse_pad_ref(spec: str) -> tuple[str, str]:
    """``"U1.8"`` → ``("U1", "8")``. Levanta ``INVALID_PARAMS`` si no matchea."""
    ref, sep, pad = spec.partition(".")
    if not sep or not ref or not pad:
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message=f"Formato de pad inválido: {spec!r}.",
            hint='Usá "REF.PAD", p. ej. "U1.8".',
        )
    return ref, pad


def _resolve_pad_coord(bridge: IpcBridge, board: BoardHandle, spec: str) -> tuple[float, float]:
    """Resuelve ``"REF.PAD"`` a la coordenada ABSOLUTA del pad (D-11.4).

    Reusa ``get_component_detail`` (D-11.3): los pads ya vienen con posición
    absoluta rotada. ``COMPONENT_NOT_FOUND`` si el ref no está; ``INVALID_PARAMS``
    si el pad no está en ese footprint (con los números disponibles en el hint).
    """
    ref, pad_number = _parse_pad_ref(spec)
    detail = bridge.get_component_detail(board, ref)  # COMPONENT_NOT_FOUND si falta
    for pad in detail.pads:
        if pad.number == pad_number:
            return float(pad.x_mm), float(pad.y_mm)
    available = ", ".join(sorted({p.number for p in detail.pads if p.number})[:12])
    raise KicadMcpError(
        code=ErrorCode.INVALID_PARAMS,
        message=f"El pad {pad_number!r} no existe en {ref}.",
        hint=f"Pads de {ref}: {available or 'sin pads numerados'}.",
    )


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
        description="Agrega un track lineal entre dos puntos, o entre dos pads (REF.PAD)",
    )
    def add_track(
        net: str,
        start_x_mm: float | None = None,
        start_y_mm: float | None = None,
        end_x_mm: float | None = None,
        end_y_mm: float | None = None,
        from_pad: str | None = None,
        to_pad: str | None = None,
        width_mm: float = 0.25,
        layer: str = "F.Cu",
        base_snap: int | None = None,
    ) -> str:
        with tool_call_timer() as timer:
            root = _project_root()
            if base_snap is not None:
                _check_base_snap(base_snap)
            board = _resolve_board(bridge)

            # D-11.4: dos formas mutuamente excluyentes de dar los endpoints —
            # coordenadas crudas O anclaje a pads ("REF.PAD"). Mezclar es un
            # error de uso; resolvemos el modo ANTES de validar coords/net.
            uses_pads = from_pad is not None or to_pad is not None
            uses_coords = any(c is not None for c in (start_x_mm, start_y_mm, end_x_mm, end_y_mm))
            if uses_pads and uses_coords:
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message="No se pueden mezclar coordenadas crudas y anclaje a pads.",
                    hint="Usá (start_x_mm..end_y_mm) O (from_pad, to_pad), no ambos.",
                )
            if uses_pads:
                if from_pad is None or to_pad is None:
                    raise KicadMcpError(
                        code=ErrorCode.INVALID_PARAMS,
                        message="El anclaje a pads requiere from_pad Y to_pad.",
                        hint='Ambos con formato "REF.PAD", p. ej. from_pad="U1.8".',
                    )
                start_x_mm, start_y_mm = _resolve_pad_coord(bridge, board, from_pad)
                end_x_mm, end_y_mm = _resolve_pad_coord(bridge, board, to_pad)
            elif None in (start_x_mm, start_y_mm, end_x_mm, end_y_mm):
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message="Faltan endpoints del track.",
                    hint="Pasá start_x_mm/start_y_mm/end_x_mm/end_y_mm o from_pad/to_pad.",
                )
            # A partir de acá los cuatro son floats resueltos (mypy: narrow).
            assert start_x_mm is not None and start_y_mm is not None
            assert end_x_mm is not None and end_y_mm is not None

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

    @mcp.tool(
        name="save_board",
        description="Persiste el board vivo del PCB Editor a disco",
    )
    def save_board(base_snap: int | None = None) -> str:
        # D-11.1: baja el estado vivo (mutado por IPC) al .kicad_pcb de disco.
        # Tras el save, disco y vivo convergen: registramos un snapshot NUEVO
        # de DISCO con mtimes frescos (patrón sch de D-08.5, NO mtimes=None) y
        # ecoamos su snap_id. G1 aplica (backup 1ª vez por sesión). Sin retry
        # en la escritura (D-07.1). busy → se propaga tal cual.
        with tool_call_timer() as timer:
            root = _project_root()
            if base_snap is not None:
                _check_base_snap(base_snap)
            board = _resolve_board(bridge)
            backup_info = ensure_session_backup(root)  # Gate G1
            bridge.save_board(board)
            # Snapshot de disco: el estado vivo ya ES el de disco tras el save.
            new_state = build_state_from_board(bridge, board)
            pcb_path = _resolve_root_pcb()
            mtimes = collect_project_mtimes(_resolve_root_schematic_or_pcb())
            snap_id = get_default_store().register(new_state, mtimes)
            audit_record(
                root,
                tool="save_board",
                params={"base_snap": base_snap},
                result={
                    "snap": snap_id,
                    "backup": backup_info.get("backup"),
                    "path": str(pcb_path),
                },
            )
            confirmation = f"OK save_board {pcb_path.name} -> {pcb_path} [snap:{snap_id}]"
        log_tool_call(
            tool_name="save_board",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(confirmation),
            snap_id=snap_id,
            extra={"base_snap": base_snap, "path": str(pcb_path)},
        )
        return confirmation

    def _delete_copper(
        *,
        tool_name: str,
        net: str,
        x_mm: float,
        y_mm: float,
        kinds: tuple[str, ...],
        base_snap: int | None,
        timer: dict[str, float],
    ) -> str:
        """Núcleo compartido de delete_track / delete_via (D-11.2).

        Lee el cobre del net (get_items_by_net), hace el matching geométrico
        puro, decide target/ambigüedad/nada, borra por KIID y registra un
        snapshot derivado del pre-estado (el borrado no altera el
        NormalizedState de footprints, patrón add_track/add_via).
        """
        root = _project_root()
        err_params = {"net": net, "pos": [x_mm, y_mm]}
        if base_snap is not None:
            _check_base_snap(base_snap)
        board = _resolve_board(bridge)
        # Validación de net + lectura del cobre en una llamada (NET_NOT_FOUND
        # con similares lo levanta el bridge; lo re-enriquecemos acá para el
        # hint de similares que el bridge no computa).
        nets = bridge.list_net_names(board)
        if net not in nets:
            similars = _similars(net, nets)
            hint = "nets similares: " + ", ".join(similars) if similars else "sin sugerencias"
            _audit_error(root, tool_name, err_params, ErrorCode.NET_NOT_FOUND)
            raise KicadMcpError(
                code=ErrorCode.NET_NOT_FOUND,
                message=f"Net {net} no existe en el board.",
                hint=hint,
            )
        items = bridge.list_net_copper(board, net)
        target, candidates = _match_copper(
            items, x_mm, y_mm, kinds=kinds, tolerance_mm=_DELETE_TOLERANCE_MM
        )
        if target is None and not candidates:
            _audit_error(root, tool_name, err_params, ErrorCode.INVALID_PARAMS)
            raise KicadMcpError(
                code=ErrorCode.INVALID_PARAMS,
                message=(
                    f"Ningún {kinds[0]} del net {net} pasa a ≤{_DELETE_TOLERANCE_MM} mm "
                    f"de ({x_mm}, {y_mm})."
                ),
                hint="Ajustá el punto (usá get_component_detail o get_world_context) o el net.",
            )
        if target is None:
            # Ambigüedad: 2+ candidatos. NUNCA borramos "el más cercano".
            cand_data = [_copper_candidate_dict(it) for it in candidates]
            _audit_error(root, tool_name, err_params, ErrorCode.INVALID_PARAMS)
            raise KicadMcpError(
                code=ErrorCode.INVALID_PARAMS,
                message=(
                    f"{len(candidates)} candidatos del net {net} dentro de "
                    f"{_DELETE_TOLERANCE_MM} mm de ({x_mm}, {y_mm}); refiná el punto."
                ),
                hint="Elegí un punto más cercano al segmento/via objetivo (ver data.candidates).",
                data={"candidates": cand_data},
            )
        # Snapshot pre para derivar el post (el cobre no vive en NormalizedState).
        ctx = bridge.read_board_context(board)
        backup_info = ensure_session_backup(root)  # Gate G1
        removed = bridge.remove_by_kiid(board, target.kiid)
        if not removed:
            _audit_error(root, tool_name, err_params, ErrorCode.INVALID_PARAMS)
            raise KicadMcpError(
                code=ErrorCode.INVALID_PARAMS,
                message="El ítem objetivo ya no está en el board (borrado concurrente).",
                hint="Re-sincronizá con get_world_context(kind='pcb') y reintentá.",
            )
        new_state = build_state_from_snapshot(ctx.footprints)
        snap_id = get_default_store().register(new_state, mtimes=None)
        audit_record(
            root,
            tool=tool_name,
            params={"net": net, "pos": [x_mm, y_mm], "base_snap": base_snap},
            result={"snap": snap_id, "backup": backup_info.get("backup"), "kiid": target.kiid},
        )
        confirmation = f"OK {tool_name} {net} @({x_mm:.1f},{y_mm:.1f}) [snap:{snap_id}]"
        log_tool_call(
            tool_name=tool_name,
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(confirmation),
            snap_id=snap_id,
            extra={"net": net, "base_snap": base_snap},
        )
        return confirmation

    @mcp.tool(
        name="delete_track",
        description="Borra la track de un net más cercana a (near_x_mm, near_y_mm)",
    )
    def delete_track(
        net: str,
        near_x_mm: float,
        near_y_mm: float,
        base_snap: int | None = None,
    ) -> str:
        with tool_call_timer() as timer:
            return _delete_copper(
                tool_name="delete_track",
                net=net,
                x_mm=near_x_mm,
                y_mm=near_y_mm,
                kinds=("track", "arc"),
                base_snap=base_snap,
                timer=timer,
            )

    @mcp.tool(
        name="delete_via",
        description="Borra la via de un net más cercana a (x_mm, y_mm)",
    )
    def delete_via(
        net: str,
        x_mm: float,
        y_mm: float,
        base_snap: int | None = None,
    ) -> str:
        with tool_call_timer() as timer:
            return _delete_copper(
                tool_name="delete_via",
                net=net,
                x_mm=x_mm,
                y_mm=y_mm,
                kinds=("via",),
                base_snap=base_snap,
                timer=timer,
            )

    @mcp.tool(
        name="get_component_detail",
        description="Detalle de un footprint: posición, rotación, bbox/courtyard y pads absolutos",
    )
    def get_component_detail(ref: str, kind: str = "pcb") -> str:
        # D-11.3: detalle geométrico bajo demanda. Fuente: board vivo (los
        # pads ya viajan absolutos/rotados en kipy). kind="sch" queda para
        # el futuro (INVALID_PARAMS honesto). Salida TOON compacta.
        with tool_call_timer() as timer:
            if kind != "pcb":
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"kind={kind!r} no soportado todavía.",
                    hint="Sólo kind='pcb' por ahora; el detalle de esquemático es futuro.",
                )
            board = _resolve_board(bridge)
            detail = bridge.get_component_detail(board, ref)
            out = _encode_component_detail(detail)
        log_tool_call(
            tool_name="get_component_detail",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(out),
            extra={"ref": ref, "kind": kind, "n_pads": len(detail.pads)},
        )
        return out

    @mcp.tool(
        name="draw_board_outline",
        description="Crea un contorno rectangular en Edge.Cuts (x_mm, y_mm, width_mm, height_mm)",
    )
    def draw_board_outline(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        base_snap: int | None = None,
    ) -> str:
        # D-12.5: contorno rectangular vía IPC (BoardRectangle en Edge.Cuts,
        # verificado en vivo la sesión 12). Rechaza si YA hay contorno (no apilar
        # bordes) usando board_outline (la cabecera 'outline:' de la sesión 11 lo
        # dice barato). Snapshot vivo post-mutación (mtimes=None, patrón add_track:
        # el contorno no vive en NormalizedState). El loop cierra con save_board.
        with tool_call_timer() as timer:
            root = _project_root()
            if base_snap is not None:
                _check_base_snap(base_snap)
            board = _resolve_board(bridge)

            params = _outline_params(x_mm, y_mm, width_mm, height_mm)
            if width_mm <= 0 or height_mm <= 0:
                _audit_error(root, "draw_board_outline", params, ErrorCode.INVALID_PARAMS)
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"width/height deben ser positivos (recibido {width_mm}x{height_mm}).",
                    hint="Pasá dimensiones > 0, p. ej. width_mm=80, height_mm=60.",
                )
            # Cordura de coordenadas absolutas (el contorno puede exceder el
            # enjambre de footprints, así que NO se valida contra el bbox de
            # footprints; sólo se rechazan valores absurdos fuera de KiCad).
            for label, v in (
                ("x_mm", x_mm),
                ("y_mm", y_mm),
                ("width_mm", width_mm),
                ("height_mm", height_mm),
            ):
                if abs(v) > 10_000.0:
                    _audit_error(root, "draw_board_outline", params, ErrorCode.INVALID_PARAMS)
                    raise KicadMcpError(
                        code=ErrorCode.INVALID_PARAMS,
                        message=f"{label}={v} fuera de rango razonable (±10 000 mm).",
                        hint="Las placas de KiCad caben de sobra en ±10 000 mm.",
                    )

            # Rechazo si ya existe contorno (no apilar bordes).
            _bbox, outline = bridge.board_outline(board)
            if outline != "none":
                _audit_error(root, "draw_board_outline", params, ErrorCode.INVALID_PARAMS)
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"El board ya tiene un contorno Edge.Cuts ({outline}).",
                    hint=(
                        "No se apilan bordes. Borrá el contorno existente en KiCad si querés "
                        "redefinirlo, o mové/re-dimensioná el que hay."
                    ),
                )

            # Snapshot pre (footprints) para derivar el post — el contorno no
            # altera el NormalizedState (patrón add_track/add_via).
            ctx = bridge.read_board_context(board)
            backup_info = ensure_session_backup(root)  # Gate G1
            kiid = bridge.draw_board_outline(board, Mm(x_mm), Mm(y_mm), Mm(width_mm), Mm(height_mm))
            new_state = build_state_from_snapshot(ctx.footprints)
            snap_id = get_default_store().register(new_state, mtimes=None)
            audit_record(
                root,
                tool="draw_board_outline",
                params={**params, "base_snap": base_snap},
                result={"snap": snap_id, "backup": backup_info.get("backup"), "kiid": kiid},
            )
            confirmation = (
                f"OK draw_board_outline @({x_mm:.1f},{y_mm:.1f}) "
                f"{width_mm:.1f}x{height_mm:.1f}mm Edge.Cuts [snap:{snap_id}]"
            )
        log_tool_call(
            tool_name="draw_board_outline",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(confirmation),
            snap_id=snap_id,
            extra={"base_snap": base_snap, "width_mm": width_mm, "height_mm": height_mm},
        )
        return confirmation


def _resolve_root_schematic_or_pcb() -> Path:
    """``.kicad_sch`` raíz si existe; si no, el ``.kicad_pcb`` (proyecto pcb-only).

    ``collect_project_mtimes`` toma el ``.kicad_sch`` y su ``.kicad_pcb``
    homónimo; para un proyecto pcb-only ancla en el pcb (fixture 005).
    """
    try:
        return _resolve_root_schematic()
    except KicadMcpError:
        return _resolve_root_pcb()


def _copper_candidate_dict(item: CopperItem) -> dict[str, Any]:
    """Representación compacta de un candidato ambiguo para ``data.candidates``."""
    d: dict[str, Any] = {"kind": item.kind, "net": item.net_name}
    if item.kind == "via":
        d["pos"] = [round(float(item.start_x_mm), 3), round(float(item.start_y_mm), 3)]
    else:
        d["start"] = [round(float(item.start_x_mm), 3), round(float(item.start_y_mm), 3)]
        if item.end_x_mm is not None and item.end_y_mm is not None:
            d["end"] = [round(float(item.end_x_mm), 3), round(float(item.end_y_mm), 3)]
        d["layer"] = item.layer
    return d


def _encode_component_detail(detail: ComponentDetail) -> str:
    """Serializa ``ComponentDetail`` a TOON compacto (D-11.3, ≤~300 tok / 30 pads).

    Formato (una línea de cabecera + una por pad):

        DETAIL|U19|pcb|at:234.3,64.1|rot:0|bbox:115.9x8.1|box:176.4,59.4;292.3,67.5|src:courtyard
        [PADS] 75
        1 GND 281.9,65.4 1.14x1.14 *.Cu
        ...

    La capa se abrevia a la del pad tal cual (``F.Cu``/``B.Cu``/``*.Cu``).
    Posiciones en mm con 1 decimal (grid de KiCad ≥ 0.05 mm; 1 decimal basta
    para ubicar y es barato en tokens).
    """
    w = float(detail.bbox_max_x) - float(detail.bbox_min_x)
    h = float(detail.bbox_max_y) - float(detail.bbox_min_y)
    rot_f = float(detail.rotation_deg)
    rot: int | float = int(rot_f) if rot_f.is_integer() else rot_f
    header = (
        f"DETAIL|{detail.ref}|pcb|at:{float(detail.x_mm):.1f},{float(detail.y_mm):.1f}"
        f"|rot:{rot}|bbox:{w:.1f}x{h:.1f}"
        f"|box:{float(detail.bbox_min_x):.1f},{float(detail.bbox_min_y):.1f};"
        f"{float(detail.bbox_max_x):.1f},{float(detail.bbox_max_y):.1f}"
        f"|src:{detail.bbox_source}"
    )
    lines = [header, f"[PADS] {len(detail.pads)}"]
    for p in detail.pads:
        num = p.number or "-"
        net = p.net_name or "-"
        lines.append(
            f"{num} {net} {float(p.x_mm):.1f},{float(p.y_mm):.1f} "
            f"{float(p.w_mm):.2f}x{float(p.h_mm):.2f} {p.layer}"
        )
    return "\n".join(lines) + "\n"


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


def _outline_params(x: float, y: float, width: float, height: float) -> dict[str, Any]:
    return {"pos": [x, y], "width_mm": width, "height_mm": height}


def _audit_error(
    root: Path,
    tool: str,
    params: dict[str, Any],
    code: ErrorCode,
) -> None:
    """Registra una mutación rechazada. No suprime la excepción del llamador."""
    audit_record(root, tool=tool, params=params, error_code=code.value)
