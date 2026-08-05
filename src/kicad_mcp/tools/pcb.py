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
import json
import math
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from ..audit.logger import record as audit_record
from ..bridge.autoroute import classify_net_routing, run_autoroute
from ..bridge.ipc import (
    BBoxMm,
    BoardHandle,
    ComponentDetail,
    CopperItem,
    FootprintData,
    IpcBridge,
    Mm,
    PadGeom,
    ZoneItem,
)
from ..bridge.rules import Item, diff_violations, run_drc
from ..bridge.rules_reader import load_project_rules
from ..bridge.state_builder import build_state_from_board, build_state_from_snapshot
from ..errors import ErrorCode, KicadMcpError
from ..gates.g1 import ensure_session_backup
from ..logging_config import estimate_tokens, log_tool_call, tool_call_timer
from ..snapshots import (
    check_no_external_disk_edit,
    collect_project_mtimes,
    get_default_store,
    validate_base_snap,
)
from ..tools.world import _resolve_root_pcb, _resolve_root_schematic

# Sesión 36 (R2): reuso de la sanitización §5 de TOON en los tres encoders
# ad-hoc (_encode_tracks/_encode_zones/_encode_component_detail). NO extiende
# TOON (F1 intacto): es una utilidad interna, no cambia el schema TOON.
from ..toon.encoder import _sanitize

# Sesión 37: el espacio es el delimitador POSICIONAL de las líneas de ítem de
# los tres formatos ad-hoc, pero `_sanitize` (§5 de TOON) no lo neutraliza —
# TOON es `|`-delimited y ahí un espacio es inocuo. Un `net_name` como
# "GND EN" sobrevive a `_sanitize` y desplaza todas las columnas siguientes
# (H36.1, sesión 36). Este wrapper compone las dos capas SIN tocar `toon/`:
# el núcleo no se dobla para servir a la deuda ad-hoc.
_WHITESPACE_RE: Final = re.compile(r"\s")


def _sanitize_space_delimited(raw: str) -> str:
    """``_sanitize`` + neutralización de TODO whitespace, para campos que van
    en una línea space-delimited de los formatos ad-hoc (D37.1, sesión 37):
    ``_CONTROL_RE`` de TOON ya cubre ``\\t\\n\\r\\v\\f``, pero no el espacio
    ni los separadores unicode (ej. NBSP), alcanzables vía netlists
    importadas. Devuelve sólo el texto: el flag ``suspicious`` de
    ``_sanitize`` no tiene canal en estos formatos (decisión #3, sesión 36).

    NO usar en el header ``DETAIL|<ref>|pcb|...`` de
    ``_encode_component_detail``: ahí ``|`` es el delimitador y un espacio en
    ``ref`` es inocuo (H2, sesión 37) — ese sitio sigue usando ``_sanitize``
    puro.
    """
    return _WHITESPACE_RE.sub("_", _sanitize(raw)[0])


# Tolerancia por defecto del matching geométrico del borrado dirigido (D-11.2):
# la track/via cuyo segmento pasa a ≤ este radio del punto es candidata. 0.5 mm
# = ~20 mil, holgado frente al grid de 1.27 mm pero fino para no barrer vecinas.
_DELETE_TOLERANCE_MM: float = 0.5

# Presupuesto por defecto de ``get_tracks`` (D-16.1): mismo default D4 que
# ``get_world_context`` (arquitectura.md §11 D4) — 800 tokens.
_TRACKS_DEFAULT_BUDGET: int = 800
# Mismo factor de seguridad que ``toon/encoder.py`` (_BUDGET_SAFETY_FACTOR):
# el estimador de tokens (chars/3.5) es aproximado; dejamos margen del 10%.
_TRACKS_BUDGET_SAFETY: float = 0.9

# F-D5-01 (sesión 32d, D3): radio de la región inmediata que el guardrail #5
# exige libre de cobre ajeno en la capa opuesta antes de stitchear. Único par
# de capas de cobre que este MVP modela (``ZoneItem.layer``/``PadGeom.layer``
# son de una sola capa cada uno) — sin sentido para vías ciegas/enterradas.
_STITCH_RADIUS_MM: float = 1.0
_OPPOSITE_LAYER: dict[str, str] = {"F.Cu": "B.Cu", "B.Cu": "F.Cu"}

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _project_root() -> Path:
    return _resolve_root_schematic().parent


def _guard_live_stale() -> None:
    """D-14.1: bloquea mutar/guardar el board vivo si el disco tiene un ruteo
    (de ``route_board``) que el editor vivo aún no refleja.

    Una mutación IPC + ``save_board`` posteriores PISARÍAN el ruteo con cobre
    viejo. Se destraba recargando el board en KiCad (File→Revert) y confirmando
    con ``get_world_context(kind='pcb', confirm_reloaded=true)`` (ADR-0011).
    Las tools de DISCO (run_drc, export_*, sch) NO pasan por acá: leen el estado
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


def _find_duplicate_refs(
    footprints: tuple[FootprintData, ...],
) -> list[tuple[str, list[str]]]:
    """Refs compartidos por 2+ footprints, con sus KIIDs (sesión 31b, F-V1-02).

    Ordenado por ref para salida determinista. Compartido entre la tool
    ``set_footprint_ref`` (ambigüedad — sin target, lista candidatos) y el
    pre-check de ``route_board`` (``pcbnew.ExportSpecctraDSN`` falla
    enteramente con refs duplicados en el board, sin importar su
    posición — confirmado empíricamente en sesión 31).
    """
    counts = Counter(fp.ref for fp in footprints)
    return [
        (ref, [fp.kiid for fp in footprints if fp.ref == ref])
        for ref, n in sorted(counts.items())
        if n >= 2
    ]


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


def _bbox_distance_to_point(bbox: tuple[float, float, float, float], px: float, py: float) -> float:
    """Distancia euclídea de un punto ``(px,py)`` a un rectángulo axis-aligned
    ``(min_x,min_y,max_x,max_y)`` — 0.0 si el punto cae DENTRO del bbox
    (sesión 21, ``get_footprint_neighbors`` — "distancia = mínimo entre bbox
    del footprint y el ítem vecino"). Clamp del punto al rectángulo, distancia
    del punto clampeado al original — geometría estándar punto-a-AABB.
    """
    min_x, min_y, max_x, max_y = bbox
    cx = min(max(px, min_x), max_x)
    cy = min(max(py, min_y), max_y)
    return math.hypot(px - cx, py - cy)


def _copper_distance_to_bbox(item: CopperItem, bbox: tuple[float, float, float, float]) -> float:
    """Distancia de un ``CopperItem`` (track/arc/vía) a un bbox (mm).

    ``0.0`` si el segmento cruza o toca el bbox (reusa
    ``_segment_intersects_bbox``, ya validado por ``get_tracks``). Si no,
    aproxima con el mínimo de la distancia punto-a-bbox de los EXTREMOS del
    segmento (start/end/mid) — no la distancia exacta segmento-a-rectángulo
    (que requeriría clipping contra los 4 lados), simplificación deliberada
    del mismo espíritu que otras aproximaciones ya aceptadas en el catálogo
    (p. ej. ``bloqueadas[].causa`` de ``route_board``, "mínimo honesto").
    """
    if item.kind == "via" or item.end_x_mm is None or item.end_y_mm is None:
        return _bbox_distance_to_point(bbox, float(item.start_x_mm), float(item.start_y_mm))
    sx, sy = float(item.start_x_mm), float(item.start_y_mm)
    ex, ey = float(item.end_x_mm), float(item.end_y_mm)
    if _segment_intersects_bbox(sx, sy, ex, ey, bbox):
        return 0.0
    candidates = [_bbox_distance_to_point(bbox, sx, sy), _bbox_distance_to_point(bbox, ex, ey)]
    if item.kind == "arc" and item.mid_x_mm is not None and item.mid_y_mm is not None:
        candidates.append(_bbox_distance_to_point(bbox, float(item.mid_x_mm), float(item.mid_y_mm)))
    return min(candidates)


def _closest_point_copper_bbox(
    item: CopperItem, bbox: tuple[float, float, float, float]
) -> tuple[float, float]:
    """Punto representativo de un ``CopperItem`` más cercano a ``bbox`` (sesión
    21, ``get_footprint_neighbors``) — mismo criterio de aproximación que
    ``_copper_distance_to_bbox`` (extremos del segmento, no el punto exacto
    de cruce si el segmento atraviesa el bbox)."""
    if item.kind == "via" or item.end_x_mm is None or item.end_y_mm is None:
        return (float(item.start_x_mm), float(item.start_y_mm))
    sx, sy = float(item.start_x_mm), float(item.start_y_mm)
    ex, ey = float(item.end_x_mm), float(item.end_y_mm)
    d_start = _bbox_distance_to_point(bbox, sx, sy)
    d_end = _bbox_distance_to_point(bbox, ex, ey)
    return (sx, sy) if d_start <= d_end else (ex, ey)


def _closest_board_edge(
    bbox: tuple[float, float, float, float], board_bbox: BBoxMm
) -> tuple[str, float]:
    """Lado del board (``left``/``right``/``top``/``bottom``) más cercano al
    ``bbox`` de un footprint, y la distancia (mm) — sesión 21,
    ``get_footprint_neighbors``. El board se asume rectangular (mismo
    supuesto que ``board_outline``, que sólo expone el bbox de Edge.Cuts, no
    el polígono real — ver su docstring)."""
    min_x, min_y, max_x, max_y = bbox
    gaps = {
        "left": min_x - float(board_bbox.min_x),
        "right": float(board_bbox.max_x) - max_x,
        "top": min_y - float(board_bbox.min_y),
        "bottom": float(board_bbox.max_y) - max_y,
    }
    side = min(gaps, key=lambda k: gaps[k])
    return side, max(gaps[side], 0.0)


def _segment_intersects_bbox(
    x0: float, y0: float, x1: float, y1: float, bbox: tuple[float, float, float, float]
) -> bool:
    """``True`` si el segmento ``(x0,y0)-(x1,y1)`` cruza o toca ``bbox`` (D-16.1).

    Liang-Barsky clipping: recorta el parámetro ``t`` del segmento contra
    las 4 medias-rectas del rectángulo. Usado por ``get_tracks(bbox=)`` — un
    segmento que sólo pasa POR bbox (sin tener ningún endpoint adentro) debe
    listarse igual (spec de la sesión: "segmento que cruza el bbox aparece").
    """
    min_x, min_y, max_x, max_y = bbox
    if (min_x <= x0 <= max_x and min_y <= y0 <= max_y) or (
        min_x <= x1 <= max_x and min_y <= y1 <= max_y
    ):
        return True
    dx, dy = x1 - x0, y1 - y0
    p = (-dx, dx, -dy, dy)
    q = (x0 - min_x, max_x - x0, y0 - min_y, max_y - y0)
    t0, t1 = 0.0, 1.0
    for pi, qi in zip(p, q, strict=True):
        if pi == 0:
            if qi < 0:
                return False  # paralelo al eje y fuera del rango
            continue
        t = qi / pi
        if pi < 0:
            if t > t1:
                return False
            t0 = max(t0, t)
        else:
            if t < t0:
                return False
            t1 = min(t1, t)
    return t0 <= t1


def _copper_in_bbox(item: CopperItem, bbox: tuple[float, float, float, float]) -> bool:
    """``True`` si ``item`` cae dentro/cruza ``bbox`` (D-16.1)."""
    if item.kind == "via" or item.end_x_mm is None or item.end_y_mm is None:
        min_x, min_y, max_x, max_y = bbox
        return min_x <= float(item.start_x_mm) <= max_x and min_y <= float(item.start_y_mm) <= max_y
    return _segment_intersects_bbox(
        float(item.start_x_mm),
        float(item.start_y_mm),
        float(item.end_x_mm),
        float(item.end_y_mm),
        bbox,
    )


def _copper_on_layer(item: CopperItem, layer: str) -> bool:
    """``True`` si ``item`` vive en ``layer`` (D-16.1). Una via pasante cuenta
    para cualquier capa entre su ``via_layers`` (span inicio-fin)."""
    if item.kind == "via":
        return item.via_layers is not None and layer in item.via_layers
    return item.layer == layer


def _segments_intersect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> bool:
    """``True`` si el segmento ``p1-p2`` cruza (propiamente o tocando) ``p3-p4``.

    Test de orientación estándar (Cormen et al.) — usado por
    ``_polygon_is_simple`` (P4, sesión 19) para rechazar polígonos
    auto-intersectantes en ``add_zone``/``add_keepout_zone``.
    """

    def orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> int:
        val = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(val) < 1e-9:
            return 0
        return 1 if val > 0 else 2

    def on_segment(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> bool:
        return (
            min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9
            and min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9
        )

    o1 = orientation(p1, p2, p3)
    o2 = orientation(p1, p2, p4)
    o3 = orientation(p3, p4, p1)
    o4 = orientation(p3, p4, p2)
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and on_segment(p1, p2, p3):
        return True
    if o2 == 0 and on_segment(p1, p2, p4):
        return True
    if o3 == 0 and on_segment(p3, p4, p1):
        return True
    return bool(o4 == 0 and on_segment(p3, p4, p2))


def _polygon_is_simple(vertices: list[tuple[float, float]]) -> bool:
    """``True`` si ningún par de lados NO adyacentes del polígono se cruza (P4).

    O(n²) — aceptable para el techo de 20 vértices del MVP. Lados adyacentes
    (comparten un vértice, incluido el cierre último→primero) se excluyen del
    chequeo: tocarse en el vértice compartido es la topología normal de un
    polígono, no una auto-intersección.
    """
    n = len(vertices)
    if n < 3:
        return False
    edges = [(vertices[i], vertices[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1:
                continue  # comparten vértice j (fin de i, inicio de j)
            if i == 0 and j == n - 1:
                continue  # cierre: último lado y primero comparten vértice 0
            if _segments_intersect(edges[i][0], edges[i][1], edges[j][0], edges[j][1]):
                return False
    return True


def _point_in_polygon(x: float, y: float, vertices: tuple[tuple[float, float], ...]) -> bool:
    """Ray casting estándar (F-D5-01, D3 guardrail #3, sesión 32d).

    Sobre el ``outline`` de DISEÑO de la zona (``ZoneItem.vertices_mm``), no
    el ``filled_polygon`` — permite stitchear un pad aunque el fill esté
    fracturado por el mecanismo que 32c aisló (clearance de cobre ajeno
    estrangulando el corredor local, ``docs/investigacion/32c-f-d5-01.md``).
    """
    inside = False
    x1, y1 = vertices[-1]
    for x2, y2 in vertices:
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xi:
                inside = not inside
        x1, y1 = x2, y2
    return inside


def _match_orphan_pad(
    pos: tuple[float, float], pads: tuple[PadGeom, ...], *, tolerance_mm: float = 0.01
) -> PadGeom | None:
    """Resuelve un ítem de ``unconnected_items`` a su ``PadGeom`` real, por
    POSICIÓN (F-D5-01, sesión 32d) — nunca por texto.

    El ``description`` que expone ``kicad-cli`` es dependiente del locale
    (32c lo observó en español: "Pad 3 [GND] de J5"), y las regex de
    ``bridge/rules.py`` (``_REF_RE``/``_NET_RE``) sólo matchean
    "Symbol"/"Footprint"/"Component" y ``net "..."`` — nunca el patrón
    "Pad ... of/de ..." que emite un ``unconnected_items`` real, así que
    ``Item.ref``/``Item.net`` quedan en ``None`` para estos ítems (verificado
    contra kicad-cli 10.0.4 real en el Bloque 0 de esta sesión). ``Item.pos``
    sí es fiable — viene de coordenadas, no de texto.
    """
    px, py = pos
    candidates = [
        p for p in pads if math.hypot(float(p.x_mm) - px, float(p.y_mm) - py) <= tolerance_mm
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _opposite_layer_blocked(
    x: float,
    y: float,
    layer: str,
    net: str,
    copper: tuple[CopperItem, ...],
    pads: tuple[PadGeom, ...],
) -> bool:
    """Guardrail #5 (D3): ``True`` si hay cobre AJENO (net distinto) dentro de
    ``_STITCH_RADIUS_MM`` de ``(x, y)`` en ``layer`` — la capa opuesta donde
    aterrizaría el otro extremo de la vía de stitching."""
    for item in copper:
        if item.net_name == net or not _copper_on_layer(item, layer):
            continue
        if _copper_distance_mm(item, x, y) <= _STITCH_RADIUS_MM:
            return True
    for p in pads:
        if p.net_name == net or p.layer not in (layer, "*.Cu"):
            continue
        if math.hypot(float(p.x_mm) - x, float(p.y_mm) - y) <= _STITCH_RADIUS_MM:
            return True
    return False


def _orphan_pad_dict(label: str, net: str, pad: PadGeom, reason: str) -> dict[str, Any]:
    return {
        "pad": label,
        "net": net,
        "x_mm": round(float(pad.x_mm), 4),
        "y_mm": round(float(pad.y_mm), 4),
        "reason": reason,
    }


def _stitched_via_dict(candidate: dict[str, Any], kiid: str) -> dict[str, Any]:
    return {
        "pad": candidate["label"],
        "net": candidate["net"],
        "x_mm": candidate["x_mm"],
        "y_mm": candidate["y_mm"],
        "layers": [candidate["layer"], candidate["opposite_layer"]],
        "kiid": kiid,
    }


def _evaluate_stitch_candidates(
    orphan_items: list[Item],
    pads: tuple[PadGeom, ...],
    zones: tuple[ZoneItem, ...],
    copper: tuple[CopperItem, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """D3 (sesión 32d): evalúa los 5 guardrails para cada pad huérfano
    post-refill. Devuelve ``(candidatos, rechazados)`` — un candidato pasó
    las 5 condiciones; un rechazo lleva ``reason`` explicando cuál falló.
    NUNCA es error (D-32d.2) — es dato para el payload de ``route_board``.
    """
    copper_zones = [z for z in zones if z.kind == "copper" and z.net_name]
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[float, float]] = set()
    for item in orphan_items:
        assert item.pos is not None  # el llamador ya filtró por esto
        pad = _match_orphan_pad(item.pos, pads)
        if pad is None or pad.net_name is None:
            continue  # ningún pad real en esa posición, o pad sin net asignado
        key = (round(float(pad.x_mm), 4), round(float(pad.y_mm), 4))
        if key in seen:
            continue  # un ``unconnected_items`` puede listar el mismo pad 2x
        seen.add(key)
        label = item.desc or f"pad @({pad.x_mm:.3f},{pad.y_mm:.3f})"
        net = pad.net_name
        px, py = float(pad.x_mm), float(pad.y_mm)

        own_zones = [z for z in copper_zones if z.net_name == net]
        if not own_zones:
            rejected.append(_orphan_pad_dict(label, net, pad, "sin zona de cobre propia"))
            continue

        inside = any(
            _point_in_polygon(px, py, tuple((float(vx), float(vy)) for vx, vy in z.vertices_mm))
            for z in own_zones
        )
        if not inside:
            rejected.append(_orphan_pad_dict(label, net, pad, "fuera del outline de la zona"))
            continue

        opposite = _OPPOSITE_LAYER.get(pad.layer)
        has_opposite_zone = any(z.net_name == net and z.layer == opposite for z in own_zones)
        if opposite is None or not has_opposite_zone:
            rejected.append(_orphan_pad_dict(label, net, pad, "sin zona en capa opuesta"))
            continue

        if _opposite_layer_blocked(px, py, opposite, net, copper, pads):
            rejected.append(_orphan_pad_dict(label, net, pad, "cobre ajeno en la región inmediata"))
            continue

        candidates.append(
            {
                "label": label,
                "net": net,
                "x_mm": px,
                "y_mm": py,
                "layer": pad.layer,
                "opposite_layer": opposite,
            }
        )
    return candidates, rejected


def _refill_enforce_and_save(
    bridge: IpcBridge,
    open_board: BoardHandle,
    pcb_path: Path,
    root: Path,
    route_params: dict[str, Any],
    *,
    context: str,
) -> int:
    """Refill + ``enforce_hole_clearance`` + ``save_board`` (D-23.2,
    ADR-0012) — compartido entre el bloque de refill de seguridad de
    ``route_board`` y el re-persist post-stitching (F-D5-01, sesión 32d):
    mismo pipeline, mismo manejo de fallo (``POST_ROUTE_PERSIST_FAILED``,
    D-07.1 sin reintento). ``context`` distingue el mensaje del error entre
    llamadores sin duplicar el bloque completo.

    F-D3-01/F-D3-03 (sesión 21): el refill interno de ``route_board`` es
    precisamente el disparador que el D3 reportó (zones.refilladas:1 → 53
    violaciones nuevas) — workaround post-fill obligatorio acá también.
    """
    zones_refilladas = bridge.refill_zones(open_board)
    bridge.enforce_hole_clearance(open_board, pcb_path)
    try:
        bridge.save_board(open_board)
    except KicadMcpError as exc:
        _audit_error(root, "route_board", route_params, ErrorCode.POST_ROUTE_PERSIST_FAILED)
        raise KicadMcpError(
            code=ErrorCode.POST_ROUTE_PERSIST_FAILED,
            message=(
                f"route_board completó {context} de {pcb_path.name} "
                "pero no pudo guardar el board a disco."
            ),
            hint=(
                "El board VIVO ya tiene el cambio aplicado; reintentá "
                "save_board() manual o descartá los cambios."
            ),
            data={"pcb": pcb_path.name, "live_has_fix": True},
        ) from exc
    return zones_refilladas


def _validate_zone_geometry(
    bbox: list[float] | None, polygon: list[list[float]] | None
) -> list[tuple[float, float]]:
    """Resuelve ``bbox`` XOR ``polygon`` a una lista de vértices (P4, sesión 19).

    ``INVALID_ZONE_GEOMETRY`` (código nuevo, F3: se añade, no se renombra
    nada) si: se pasan ambos o ninguno, el polígono tiene <3 o >20 vértices,
    o es auto-intersectante. Un ``bbox`` se expande a un rectángulo de 4
    vértices en sentido horario — mismo convención que
    ``docs/investigacion/19-zonas-ipc.md`` §2.3 (el rectángulo del test
    decisivo de Freerouting).
    """
    if (bbox is None) == (polygon is None):
        raise KicadMcpError(
            code=ErrorCode.INVALID_ZONE_GEOMETRY,
            message="Pasá exactamente uno de bbox o polygon, no ambos ni ninguno.",
            hint=(
                "bbox=[min_x,min_y,max_x,max_y] para rectángulos, o "
                "polygon=[[x,y],...] (3-20 vértices) para formas arbitrarias."
            ),
        )
    if bbox is not None:
        if len(bbox) != 4:
            raise KicadMcpError(
                code=ErrorCode.INVALID_ZONE_GEOMETRY,
                message=(
                    f"bbox debe tener 4 valores [min_x,min_y,max_x,max_y] (recibió {len(bbox)})."
                ),
                hint="Ejemplo: bbox=[10.0, 10.0, 50.0, 40.0].",
            )
        min_x, min_y, max_x, max_y = bbox
        if min_x > max_x or min_y > max_y:
            raise KicadMcpError(
                code=ErrorCode.INVALID_ZONE_GEOMETRY,
                message=f"bbox inválido (min > max): {bbox}.",
                hint="Formato [min_x,min_y,max_x,max_y] con min <= max en cada eje.",
            )
        return [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]

    assert polygon is not None
    if not (3 <= len(polygon) <= 20):
        raise KicadMcpError(
            code=ErrorCode.INVALID_ZONE_GEOMETRY,
            message=f"polygon debe tener entre 3 y 20 vértices (recibió {len(polygon)}).",
            hint="Usá bbox=[...] para rectángulos, o un polígono de 3-20 vértices.",
        )
    vertices: list[tuple[float, float]] = []
    for i, v in enumerate(polygon):
        if len(v) != 2:
            raise KicadMcpError(
                code=ErrorCode.INVALID_ZONE_GEOMETRY,
                message=f"Vértice {i} debe ser [x, y] (recibió {v!r}).",
                hint="Cada vértice de polygon es un par [x_mm, y_mm].",
            )
        vertices.append((float(v[0]), float(v[1])))
    if not _polygon_is_simple(vertices):
        raise KicadMcpError(
            code=ErrorCode.INVALID_ZONE_GEOMETRY,
            message="El polígono es auto-intersectante (no simple).",
            hint="Los lados no pueden cruzarse entre sí; revisá el orden de los vértices.",
        )
    return vertices


def _zone_is_axis_aligned_rect(vertices: tuple[tuple[Mm, Mm], ...]) -> bool:
    """``True`` si los 4 vértices son exactamente las esquinas de un rectángulo
    alineado a los ejes (P4) — determina si ``get_zones`` imprime ``bbox=``
    (más compacto, caso común de ``add_zone(bbox=...)``) o ``verts=N`` (conteo,
    para polígonos arbitrarios). No requiere recordar el modo de creación
    original: se detecta puramente de la geometría leída."""
    if len(vertices) != 4:
        return False
    xs = sorted({round(float(v[0]), 6) for v in vertices})
    ys = sorted({round(float(v[1]), 6) for v in vertices})
    if len(xs) != 2 or len(ys) != 2:
        return False
    expected = {(xs[0], ys[0]), (xs[1], ys[0]), (xs[1], ys[1]), (xs[0], ys[1])}
    got = {(round(float(v[0]), 6), round(float(v[1]), 6)) for v in vertices}
    return got == expected


def _zones_filter_desc(layer: str | None, net: str | None, kind: str | None) -> str:
    """Cabecera legible del filtro aplicado a ``get_zones`` (P4, espejo de
    ``_tracks_filter_desc``).

    ``layer``/``net``/``kind`` son parámetros de la tool MCP: ``kind`` está
    restringido a ``("copper","keepout")`` y ``net`` se valida contra
    ``list_net_names`` antes de llegar acá, pero ``layer`` **no se valida en
    ningún punto** — sólo se usa como filtro de igualdad. Sin sanitizar,
    un ``layer`` con ``\\n`` forja líneas adicionales dentro del bloque
    ``ZONES|v1|...`` (sesión 38, corrige el gap; no es defensa en
    profundidad, es el fix a una inyección real). Se sanitiza cada
    componente ANTES de ensamblar, con ``_sanitize`` puro (no
    ``_sanitize_space_delimited``): este header es ``|``-delimitado, un
    espacio en un valor es inocuo acá (mismo criterio que H2, sesión 37).
    Sanitizar el string ya ensamblado destruiría la propia sintaxis
    ``layer:x|net:y`` porque ``_sanitize`` neutraliza ``|`` y ``:``.
    """
    parts = []
    if layer is not None:
        parts.append(f"layer:{_sanitize(layer)[0]}")
    if net is not None:
        parts.append(f"net:{_sanitize(net)[0]}")
    if kind is not None:
        parts.append(f"kind:{_sanitize(kind)[0]}")
    return "|".join(parts)


def _encode_zones(items: tuple[ZoneItem, ...], filter_desc: str) -> str:
    """Serializa zonas a un formato compacto propio (P4, sesión 19).

    NO es TOON (F1 intacto, mismo criterio que ``_encode_tracks``). Formato
    (cabecera + una línea por zona)::

        ZONES|v1|layer:B.Cu|2
        Z <id> copper GND B.Cu bbox=10.000,10.000;50.000,40.000 area=1200.00 filled=1
        Z <id> keepout - F.Cu verts=12 area=706.86 filled=0

    ``bbox=`` para rectángulos alineados a ejes (4 vértices, el caso común de
    ``add_zone(bbox=...)``); ``verts=N`` (sólo el conteo, no las coordenadas)
    para polígonos arbitrarios — el agente que las necesite las tiene desde
    la llamada que las creó.

    ``net_name`` es entrada no confiable (CLAUDE.md regla 6): se sanitiza con
    ``_sanitize_space_delimited`` (sesión 37), que además de los caracteres
    estructurales de TOON (§5) neutraliza el espacio — delimitador posicional
    de esta línea (sesión 36, R2 + sesión 37, cierre del gap del espacio).

    ``layer`` cae a ``"-"`` si viene vacío (sesión 38): ``list_zones`` puede
    producir ``layer=""`` cuando la zona no reporta capas (``bridge/ipc.py``,
    ``layers[0] if layers else ""``) — mismo colapso de columna que tenía
    ``CopperItem.net_name`` antes de esta sesión.
    """
    header = f"ZONES|v1|{filter_desc}|{len(items)}" if filter_desc else f"ZONES|v1|{len(items)}"
    lines = [header]
    for z in items:
        # Sesión 37: net_name va en línea space-delimited (H36.1, gap del
        # espacio) — _sanitize_space_delimited neutraliza también whitespace.
        net = _sanitize_space_delimited(z.net_name) if z.net_name else "-"
        # Sesión 38: layer vacío ("") colapsa la columna igual que net_name.
        layer = z.layer or "-"
        if _zone_is_axis_aligned_rect(z.vertices_mm):
            geom = (
                f"bbox={float(z.bbox_min_x):.3f},{float(z.bbox_min_y):.3f};"
                f"{float(z.bbox_max_x):.3f},{float(z.bbox_max_y):.3f}"
            )
        else:
            geom = f"verts={len(z.vertices_mm)}"
        lines.append(
            f"Z {z.kiid} {z.kind} {net} {layer} {geom} "
            f"area={z.area_mm2:.2f} filled={1 if z.filled else 0}"
        )
    return "\n".join(lines) + "\n"


def _rounded_rect_sdf(px: float, py: float, hw: float, hh: float, r: float) -> float:
    """Distancia con signo del punto ``(px,py)`` (marco local del pad, ya
    trasladado+rotado) a un rectángulo ``hw``x``hh`` (semi-ejes) con esquinas
    redondeadas de radio ``r`` (D-16.4). Negativa adentro, positiva afuera.

    SDF estándar de "rounded box" 2D (Inigo Quilez): con ``r=0`` es la
    distancia a un rectángulo exacto; con ``r = min(hw,hh)`` degenera en
    círculo/estadio exactos — una sola fórmula cubre rect/roundrect/circle/
    oval vía ``_pad_corner_ratio``.
    """
    hw_in = hw - r
    hh_in = hh - r
    qx = abs(px) - hw_in
    qy = abs(py) - hh_in
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r


def _dist_segment_to_pad(sx: float, sy: float, ex: float, ey: float, pad: PadGeom) -> float:
    """Distancia mínima (mm) del segmento ``(sx,sy)-(ex,ey)`` al pad (D-16.4).

    Transforma el segmento al marco local del pad (traslada por su centro,
    rota por ``-rotation_deg``) y minimiza el SDF de rounded-rect a lo largo
    del segmento. El SDF de una forma convexa es una función convexa de la
    posición, y una parametrización afín (el segmento) preserva convexidad:
    ``f(t) = sdf(punto en el segmento a parámetro t)`` es convexa en
    ``t ∈ [0,1]`` → búsqueda ternaria converge al mínimo global sin
    heurísticas de muestreo.
    """
    cx, cy = float(pad.x_mm), float(pad.y_mm)
    rad = -math.radians(pad.rotation_deg)
    cos_r, sin_r = math.cos(rad), math.sin(rad)

    def _local(x: float, y: float) -> tuple[float, float]:
        dx, dy = x - cx, y - cy
        return dx * cos_r - dy * sin_r, dx * sin_r + dy * cos_r

    hw = float(pad.w_mm) / 2.0
    hh = float(pad.h_mm) / 2.0
    r = pad.corner_ratio * min(float(pad.w_mm), float(pad.h_mm))

    lsx, lsy = _local(sx, sy)
    lex, ley = _local(ex, ey)

    def _f(t: float) -> float:
        px = lsx + (lex - lsx) * t
        py = lsy + (ley - lsy) * t
        return _rounded_rect_sdf(px, py, hw, hh, r)

    lo, hi = 0.0, 1.0
    for _ in range(60):  # precisión << nm; f es convexa en [0,1]
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        if _f(m1) < _f(m2):
            hi = m2
        else:
            lo = m1
    return min(_f(lo), _f(hi), _f(0.0), _f(1.0))


def _find_track_pad_collision(
    pads: tuple[PadGeom, ...],
    *,
    net: str,
    layer: str,
    width_mm: float,
    start_x_mm: float,
    start_y_mm: float,
    end_x_mm: float,
    end_y_mm: float,
    clearance_mm: float,
) -> PadGeom | None:
    """Primer pad de OTRO net que el track invadiría, o ``None`` (D-16.4).

    Excluye pads del MISMO net (se espera que el track los toque/conecte) y
    pads en una capa de cobre distinta a la del track (salvo pasantes,
    ``layer="*.Cu"``, que aplican a cualquier capa). ``clearance_mm`` es el
    de la netclass real del track (sesión 17, P2.1 — ``rules_reader``); antes
    era un piso fijo de 0.2mm (deuda de sesión 16, D-16.4).
    """
    threshold = width_mm / 2.0 + clearance_mm
    for pad in pads:
        if pad.net_name == net:
            continue
        if pad.layer != "*.Cu" and pad.layer != layer:
            continue
        dist = _dist_segment_to_pad(start_x_mm, start_y_mm, end_x_mm, end_y_mm, pad)
        if dist < threshold:
            return pad
    return None


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


def _resolve_endpoint(
    label: str,
    bridge: IpcBridge,
    board: BoardHandle,
    *,
    pad_ref: str | None,
    x: float | None,
    y: float | None,
) -> tuple[float, float]:
    """Resuelve UN endpoint de ``add_track`` — pad O coordenadas (sesión 16, D-16.3).

    Reemplaza la exclusión mutua GLOBAL de D-11.4 (pad↔pad o punto↔punto,
    nunca mezclados) por una exclusión POR ENDPOINT: cada extremo elige su
    propia forma independientemente, así ``from_pad`` + ``end_x_mm/end_y_mm``
    (reparación real: desde un pad hasta un punto en el cobre) funciona sin
    tocar las firmas existentes — ``from_pad``/``to_pad`` siguen siendo los
    mismos parámetros, sólo se relaja qué combinaciones acepta el par.
    """
    if pad_ref is not None and (x is not None or y is not None):
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message=f"El endpoint {label} mezcla pad y coordenadas crudas.",
            hint=(
                f'Para {label} usá SOLO {label}_pad="REF.PAD" O '
                f"{label}_x_mm+{label}_y_mm, no ambos."
            ),
        )
    if pad_ref is not None:
        return _resolve_pad_coord(bridge, board, pad_ref)
    if x is None or y is None:
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message=f"Faltan coordenadas del endpoint {label}.",
            hint=f'Pasá {label}_x_mm Y {label}_y_mm, o {label}_pad="REF.PAD".',
        )
    return x, y


def register(mcp: FastMCP, *, ipc_bridge: IpcBridge | None = None) -> None:
    """Registra las tools de mutación en la instancia FastMCP."""

    bridge = ipc_bridge or IpcBridge()

    @mcp.tool(
        name="move_footprint",
        description="Mueve un footprint del PCB a (x_mm, y_mm)",
    )
    def move_footprint(ref: str, x_mm: float, y_mm: float, base_snap: int | None = None) -> str:
        with tool_call_timer() as timer:
            _guard_live_stale()  # D-14.1
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
        name="set_footprint_ref",
        description=(
            "Renombra UNA instancia de un reference designator duplicado/sin anotar "
            "(ej. 4x 'REF**') a un ref único. Sin kiid, lista las instancias candidatas."
        ),
    )
    def set_footprint_ref(
        ref: str,
        new_ref: str,
        kiid: str | None = None,
        base_snap: int | None = None,
    ) -> str:
        # Sesión 31b (F-V1-02): ExportSpecctraDSN (pcbnew) falla enteramente
        # con refs duplicados en el board, sin importar su posición
        # (confirmado en sesión 31: quitar 3 de 4 instancias de "REF**" hizo
        # pasar la exportación de ok=False,size=0 a ok=True,size=2.4MB). La
        # resolución es ANOTAR, no borrar — ADR-0013 rechaza explícitamente
        # un delete_footprint general (ADR-0010: footprints siguen detrás de
        # G2, que no existe; un footprint con ref duplicado es igual de caro
        # de reinstanciar que uno con ref único, acotar el trigger no cambia
        # ese costo). Esta tool sólo opera cuando ``ref`` YA está duplicado
        # — no puede usarse como delete_footprint disfrazado sobre un
        # footprint con ref único.
        with tool_call_timer() as timer:
            _guard_live_stale()  # D-14.1
            check_no_external_disk_edit(  # P3.2: red de seguridad, independiente de base_snap
                get_default_store(), _resolve_root_schematic_or_pcb()
            )
            root = _project_root()
            if base_snap is not None:
                _check_base_snap(base_snap)
            board = _resolve_board(bridge)

            ctx = bridge.read_board_context(board)
            matches = [fp for fp in ctx.footprints if fp.ref == ref]
            err_params: dict[str, Any] = {"ref": ref, "new_ref": new_ref, "kiid": kiid}

            if not matches:
                # sorted(set(...)): ctx.refs puede tener duplicados por
                # definición acá — sin dedupe, _similars ecoa el mismo ref
                # varias veces en las sugerencias.
                similars = _similars(ref, sorted(set(ctx.refs)))
                hint = "refs similares: " + ", ".join(similars) if similars else "sin sugerencias"
                _audit_error(root, "set_footprint_ref", err_params, ErrorCode.COMPONENT_NOT_FOUND)
                raise KicadMcpError(
                    code=ErrorCode.COMPONENT_NOT_FOUND,
                    message=f"Footprint {ref} no existe en el board.",
                    hint=hint,
                )
            if len(matches) < 2:
                _audit_error(root, "set_footprint_ref", err_params, ErrorCode.INVALID_PARAMS)
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"{ref} no está duplicado — sólo hay 1 footprint con ese ref.",
                    hint=(
                        "set_footprint_ref sólo resuelve refs compartidos por 2+ "
                        "footprints; para un ref único no hay tool de renombrado."
                    ),
                )
            match_kiids = {fp.kiid for fp in matches}
            if kiid is None or kiid not in match_kiids:
                # Ambigüedad: 2+ candidatos. NUNCA renombramos "el primero" a
                # ciegas — mismo espíritu que _delete_copper (línea ~1420).
                candidates = [
                    {
                        "kiid": fp.kiid,
                        "x_mm": float(fp.x_mm),
                        "y_mm": float(fp.y_mm),
                        "value": fp.value,
                    }
                    for fp in matches
                ]
                stale = kiid is not None
                _audit_error(root, "set_footprint_ref", err_params, ErrorCode.DUPLICATE_REFS)
                raise KicadMcpError(
                    code=ErrorCode.DUPLICATE_REFS,
                    message=(
                        f"kiid {kiid!r} no corresponde a ninguna instancia de {ref} "
                        f"(re-leer y reintentar)."
                        if stale
                        else f"{len(matches)} footprints comparten el ref {ref}."
                    ),
                    hint="Elegí un kiid de data.candidates y reintentá con ese kiid.",
                    data={"candidates": candidates},
                )

            backup_info = ensure_session_backup(root)  # Gate G1
            bridge.set_footprint_ref(board, kiid, new_ref)

            # Post-estado derivado localmente (cero IPC extra) — mismo
            # espíritu que _derive_post_state, sin el verify-by-kiid de
            # D-08.2 (esa optimización es para el hot path de move_footprint;
            # acá el rename es un evento raro, derivar-y-confiar alcanza,
            # igual que _delete_copper).
            updated: list[FootprintData] = []
            for fp in ctx.footprints:
                if fp.kiid == kiid:
                    updated.append(
                        FootprintData(
                            ref=new_ref,
                            value=fp.value,
                            x_mm=fp.x_mm,
                            y_mm=fp.y_mm,
                            pads=fp.pads,
                            kiid=fp.kiid,
                        )
                    )
                else:
                    updated.append(fp)
            new_state = build_state_from_snapshot(tuple(updated))
            snap_id = get_default_store().register(new_state, mtimes=None)
            audit_record(
                root,
                tool="set_footprint_ref",
                params={"ref": ref, "new_ref": new_ref, "kiid": kiid, "base_snap": base_snap},
                result={"snap": snap_id, "backup": backup_info.get("backup")},
            )
            confirmation = f"OK set_footprint_ref {ref} -> {new_ref} [snap:{snap_id}]"
        log_tool_call(
            tool_name="set_footprint_ref",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(confirmation),
            snap_id=snap_id,
            extra={"kiid": kiid, "base_snap": base_snap},
        )
        return confirmation

    @mcp.tool(
        name="add_track",
        description="Agrega un track entre punto/pad y punto/pad (REF.PAD), mezclables por extremo",
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
            _guard_live_stale()  # D-14.1
            check_no_external_disk_edit(  # P3.2: red de seguridad, independiente de base_snap
                get_default_store(), _resolve_root_schematic_or_pcb()
            )
            root = _project_root()
            if base_snap is not None:
                _check_base_snap(base_snap)
            board = _resolve_board(bridge)

            # D-16.3: cada endpoint elige independientemente pad O coordenadas
            # (ver ``_resolve_endpoint`` — reemplaza la exclusión mutua GLOBAL
            # de D-11.4 por una exclusión POR ENDPOINT). Habilita el caso de
            # reparación real: from_pad="U1.1" hasta un punto en el cobre.
            start_x_mm, start_y_mm = _resolve_endpoint(
                "start", bridge, board, pad_ref=from_pad, x=start_x_mm, y=start_y_mm
            )
            end_x_mm, end_y_mm = _resolve_endpoint(
                "end", bridge, board, pad_ref=to_pad, x=end_x_mm, y=end_y_mm
            )

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

            # D-16.4/P2.1 (sesión 17): colisión contra pads de OTRO net
            # (roundrect/circle/oval modelados exactos, ver
            # ``_find_track_pad_collision``). Antes de G1: un rechazo acá no
            # debe disparar backup. Clearance de la netclass REAL del net
            # (``rules_reader``, lee el ``.kicad_pro``) — ya no el piso fijo
            # 0.2mm de la sesión 16 (fallback si no hay reglas legibles).
            pads = bridge.list_all_pads(board)
            net_clearance_mm = (
                load_project_rules(_resolve_root_pcb()).class_for_net(net).clearance_mm
            )
            collision = _find_track_pad_collision(
                pads,
                net=net,
                layer=layer,
                width_mm=width_mm,
                start_x_mm=start_x_mm,
                start_y_mm=start_y_mm,
                end_x_mm=end_x_mm,
                end_y_mm=end_y_mm,
                clearance_mm=net_clearance_mm,
            )
            if collision is not None:
                _audit_error(
                    root,
                    "add_track",
                    _track_params(net, start_x_mm, start_y_mm, end_x_mm, end_y_mm, width_mm, layer),
                    ErrorCode.INVALID_PARAMS,
                )
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=(
                        f"El track invade un pad del net {collision.net_name or '(sin net)'} "
                        f"@({float(collision.x_mm):.3f},{float(collision.y_mm):.3f}) en {layer} "
                        f"(clearance mínimo {net_clearance_mm} mm)."
                    ),
                    hint=(
                        "Ajustá el trazado o el ancho; usá get_tracks/get_component_detail "
                        "para inspeccionar el área."
                    ),
                    data={
                        "pad_net": collision.net_name,
                        "pad_pos": [
                            round(float(collision.x_mm), 3),
                            round(float(collision.y_mm), 3),
                        ],
                        "clearance_mm": net_clearance_mm,
                    },
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
            _guard_live_stale()  # D-14.1
            check_no_external_disk_edit(  # P3.2: red de seguridad, independiente de base_snap
                get_default_store(), _resolve_root_schematic_or_pcb()
            )
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
            _guard_live_stale()  # D-14.1: no pisar el ruteo de disco con vivo viejo
            check_no_external_disk_edit(  # P3.2: red de seguridad, independiente de base_snap
                get_default_store(), _resolve_root_schematic_or_pcb()
            )
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

    @mcp.tool(
        name="reload_board_from_disk",
        description=(
            "Fuerza al PCB Editor vivo a re-leer el .kicad_pcb de disco "
            "(descarta el estado vivo no guardado)"
        ),
    )
    def reload_board_from_disk() -> dict[str, Any]:
        # P3.1 (sesión 18, D-V3.1): reemplaza el File→Revert manual que exigía
        # D-14.1 tras route_board. ``bridge.reload_board_from_disk`` envuelve
        # ``Board.revert()`` de kipy (verificado en vivo contra KiCad 10.0.4,
        # docs/investigacion/18-recarga-ipc.md): re-lee disco, descarta lo no
        # guardado, es idempotente. NO pasa por ``_guard_live_stale`` — esta
        # tool es precisamente el mecanismo que lo destraba.
        #
        # Nota de diseño: sólo la ausencia de editor abierto (``_resolve_board``
        # → PROJECT_NOT_FOUND) se remapea a RELOAD_FAILED aquí, tal como pide
        # el contrato ("si el editor no está abierto ... RELOAD_FAILED"). Los
        # demás fallos IPC (busy/timeout/restarted) ya tienen taxonomía propia
        # y accionable (KICAD_CLI_FAILED/KICAD_TIMEOUT/KICAD_RESTARTED) — se
        # propagan sin reenvolver para no perder esa señal.
        with tool_call_timer() as timer:
            root = _project_root()
            try:
                board = _resolve_board(bridge)
            except KicadMcpError as exc:
                if exc.code is ErrorCode.PROJECT_NOT_FOUND:
                    raise KicadMcpError(
                        code=ErrorCode.RELOAD_FAILED,
                        message="No hay PCB Editor abierto para recargar.",
                        hint=(
                            "KiCad no expuso el método esperado (no hay board abierto); "
                            "abrí el .kicad_pcb del proyecto en KiCad y reintentá, o "
                            "hacé File→Revert manualmente si ya lo tenías abierto."
                        ),
                    ) from exc
                raise
            n_tracks, n_vias = bridge.reload_board_from_disk(board)
            # Tras el revert, vivo == disco: mismo patrón de snapshot fresco
            # que save_board (mtimes reales, no ``None``).
            new_state = build_state_from_board(bridge, board)
            mtimes = collect_project_mtimes(_resolve_root_schematic_or_pcb())
            snap_id = get_default_store().register(new_state, mtimes)
            get_default_store().clear_live_stale()  # D-14.1: destraba el guard
            audit_record(
                root,
                tool="reload_board_from_disk",
                params={},
                result={"snap": snap_id, "tracks": n_tracks, "vias": n_vias},
            )
            payload: dict[str, Any] = {
                "reloaded": True,
                "snap_id": snap_id,
                "tracks": n_tracks,
                "vias": n_vias,
            }
        log_tool_call(
            tool_name="reload_board_from_disk",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
            snap_id=snap_id,
            extra={"tracks": n_tracks, "vias": n_vias},
        )
        return payload

    def _delete_copper(
        *,
        tool_name: str,
        kinds: tuple[str, ...],
        base_snap: int | None,
        timer: dict[str, float],
        track_id: str | None = None,
        net: str | None = None,
        x_mm: float | None = None,
        y_mm: float | None = None,
    ) -> str:
        """Núcleo compartido de delete_track / delete_via (D-11.2, D-16.2).

        Dos formas mutuamente excluyentes de identificar el target:
        - **por id** (``track_id``, de ``get_tracks``): resuelve directo por
          KIID, sin matching geométrico ni ambigüedad posible. Id inexistente
          o de otro ``kind`` (board mutado desde el ``get_tracks`` que lo
          emitió) → ``TRACK_ID_STALE``.
        - **por coordenadas** (``net``+``x_mm``+``y_mm``, D-11.2, compat):
          matching geométrico contra el cobre del net; ambigüedad → 2+
          candidatos con ``data.candidates`` (ahora sí llega al agente, ver
          ``KicadMcpError``).

        Ambas convergen en el mismo cierre: borrar por KIID y registrar un
        snapshot derivado del pre-estado (el borrado no altera el
        NormalizedState de footprints, patrón add_track/add_via).
        """
        _guard_live_stale()  # D-14.1
        check_no_external_disk_edit(  # P3.2: red de seguridad, independiente de base_snap
            get_default_store(), _resolve_root_schematic_or_pcb()
        )
        root = _project_root()
        uses_id = track_id is not None
        uses_coords = net is not None or x_mm is not None or y_mm is not None
        if uses_id and uses_coords:
            raise KicadMcpError(
                code=ErrorCode.INVALID_PARAMS,
                message="No se puede mezclar id con net/coordenadas.",
                hint="Usá SOLO id=... (de get_tracks) O net+coordenadas, no ambos.",
            )
        if not uses_id and not uses_coords:
            raise KicadMcpError(
                code=ErrorCode.INVALID_PARAMS,
                message="Falta el target: id, o net+coordenadas.",
                hint="Pasá id=... (de get_tracks) o net + la coordenada cercana.",
            )
        if base_snap is not None:
            _check_base_snap(base_snap)
        board = _resolve_board(bridge)

        err_params: dict[str, Any]
        target: CopperItem
        if uses_id:
            assert track_id is not None
            err_params = {"id": track_id}
            item = bridge.get_copper_by_kiid(board, track_id)
            if item is None or item.kind not in kinds:
                _audit_error(root, tool_name, err_params, ErrorCode.TRACK_ID_STALE)
                raise KicadMcpError(
                    code=ErrorCode.TRACK_ID_STALE,
                    message=f"El id {track_id} no existe o no es {kinds[0]} (board mutado).",
                    hint="Re-listá con get_tracks y usá un id vigente.",
                )
            target = item
        else:
            assert net is not None and x_mm is not None and y_mm is not None
            err_params = {"net": net, "pos": [x_mm, y_mm]}
            # Validación de net + lectura del cobre en una llamada
            # (NET_NOT_FOUND con similares lo levanta el bridge; lo
            # re-enriquecemos acá para el hint de similares).
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
            matched, candidates = _match_copper(
                items, x_mm, y_mm, kinds=kinds, tolerance_mm=_DELETE_TOLERANCE_MM
            )
            if matched is None and not candidates:
                _audit_error(root, tool_name, err_params, ErrorCode.INVALID_PARAMS)
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=(
                        f"Ningún {kinds[0]} del net {net} pasa a ≤{_DELETE_TOLERANCE_MM} mm "
                        f"de ({x_mm}, {y_mm})."
                    ),
                    hint="Ajustá el punto (usá get_tracks/get_component_detail) o el net.",
                )
            if matched is None:
                # Ambigüedad: 2+ candidatos. NUNCA borramos "el más cercano".
                cand_data = [_copper_candidate_dict(it) for it in candidates]
                _audit_error(root, tool_name, err_params, ErrorCode.INVALID_PARAMS)
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=(
                        f"{len(candidates)} candidatos del net {net} dentro de "
                        f"{_DELETE_TOLERANCE_MM} mm de ({x_mm}, {y_mm}); refiná el punto."
                    ),
                    hint=(
                        "Elegí un punto más cercano al segmento/via objetivo (ver "
                        "data.candidates), o resolvé por id con get_tracks."
                    ),
                    data={"candidates": cand_data},
                )
            target = matched

        # Snapshot pre para derivar el post (el cobre no vive en NormalizedState).
        ctx = bridge.read_board_context(board)
        backup_info = ensure_session_backup(root)  # Gate G1
        removed = bridge.remove_by_kiid(board, target.kiid)
        if not removed:
            _audit_error(root, tool_name, err_params, ErrorCode.TRACK_ID_STALE)
            raise KicadMcpError(
                code=ErrorCode.TRACK_ID_STALE,
                message="El ítem objetivo ya no está en el board (borrado concurrente).",
                hint="Re-listá con get_tracks y reintentá.",
            )
        new_state = build_state_from_snapshot(ctx.footprints)
        snap_id = get_default_store().register(new_state, mtimes=None)
        target_net = target.net_name
        target_x, target_y = float(target.start_x_mm), float(target.start_y_mm)
        audit_record(
            root,
            tool=tool_name,
            params={**err_params, "base_snap": base_snap},
            result={"snap": snap_id, "backup": backup_info.get("backup"), "kiid": target.kiid},
        )
        confirmation = (
            f"OK {tool_name} {target_net} @({target_x:.1f},{target_y:.1f}) [snap:{snap_id}]"
        )
        log_tool_call(
            tool_name=tool_name,
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(confirmation),
            snap_id=snap_id,
            extra={"net": target_net, "base_snap": base_snap, "by_id": uses_id},
        )
        return confirmation

    @mcp.tool(
        name="delete_track",
        description="Borra track/arco por id (get_tracks) o la más cercana a (net, near_x/y_mm)",
    )
    def delete_track(
        id: str | None = None,
        net: str | None = None,
        near_x_mm: float | None = None,
        near_y_mm: float | None = None,
        base_snap: int | None = None,
    ) -> str:
        with tool_call_timer() as timer:
            return _delete_copper(
                tool_name="delete_track",
                track_id=id,
                net=net,
                x_mm=near_x_mm,
                y_mm=near_y_mm,
                kinds=("track", "arc"),
                base_snap=base_snap,
                timer=timer,
            )

    @mcp.tool(
        name="delete_via",
        description="Borra una via por id (get_tracks) o la más cercana a (net, x_mm, y_mm)",
    )
    def delete_via(
        id: str | None = None,
        net: str | None = None,
        x_mm: float | None = None,
        y_mm: float | None = None,
        base_snap: int | None = None,
    ) -> str:
        with tool_call_timer() as timer:
            return _delete_copper(
                tool_name="delete_via",
                track_id=id,
                net=net,
                x_mm=x_mm,
                y_mm=y_mm,
                kinds=("via",),
                base_snap=base_snap,
                timer=timer,
            )

    @mcp.tool(
        name="get_tracks",
        description="Lista tracks/vias (net y/o bbox y/o layer) con id estable para cirugía",
    )
    def get_tracks(
        net: str | None = None,
        bbox: list[float] | None = None,
        layer: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        # D-16.1: visibilidad del cobre. Al menos un filtro es obligatorio —
        # una placa real tiene cientos/miles de segmentos (P1, dogfooding F-13).
        # No es TOON (F1 intacto): formato compacto propio, tool separada.
        with tool_call_timer() as timer:
            if net is None and bbox is None and layer is None:
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message="get_tracks requiere al menos un filtro.",
                    hint=(
                        "Pasá net, bbox=[min_x,min_y,max_x,max_y] o layer — una placa "
                        "real puede tener cientos de segmentos."
                    ),
                )
            bbox_t: tuple[float, float, float, float] | None = None
            if bbox is not None:
                if len(bbox) != 4:
                    raise KicadMcpError(
                        code=ErrorCode.INVALID_PARAMS,
                        message=(
                            "bbox debe tener 4 valores [min_x,min_y,max_x,max_y] "
                            f"(recibió {len(bbox)})."
                        ),
                        hint="Ejemplo: bbox=[10.0, 10.0, 50.0, 40.0].",
                    )
                bbox_t = (bbox[0], bbox[1], bbox[2], bbox[3])
                if bbox_t[0] > bbox_t[2] or bbox_t[1] > bbox_t[3]:
                    raise KicadMcpError(
                        code=ErrorCode.INVALID_PARAMS,
                        message=f"bbox inválido (min > max): {bbox_t}.",
                        hint="Formato [min_x,min_y,max_x,max_y] con min <= max en cada eje.",
                    )

            board = _resolve_board(bridge)
            if net is not None:
                nets = bridge.list_net_names(board)
                if net not in nets:
                    similars = _similars(net, nets)
                    hint = (
                        "nets similares: " + ", ".join(similars) if similars else "sin sugerencias"
                    )
                    raise KicadMcpError(
                        code=ErrorCode.NET_NOT_FOUND,
                        message=f"Net {net} no existe en el board.",
                        hint=hint,
                    )
                items = bridge.list_net_copper(board, net)
            else:
                items = bridge.list_all_copper(board)
            if bbox_t is not None:
                items = tuple(it for it in items if _copper_in_bbox(it, bbox_t))
            if layer is not None:
                items = tuple(it for it in items if _copper_on_layer(it, layer))

            budget = max_tokens if max_tokens is not None else _TRACKS_DEFAULT_BUDGET
            filter_desc = _tracks_filter_desc(net, bbox_t, layer)
            out = _encode_tracks(items, filter_desc)
            if estimate_tokens(out) > budget * _TRACKS_BUDGET_SAFETY:
                raise KicadMcpError(
                    code=ErrorCode.CONTEXT_BUDGET_IMPOSSIBLE,
                    message=f"El listado no cabe en {budget} tokens.",
                    hint=(
                        f"presupuesto mínimo estimado ≈ {estimate_tokens(out)} tokens; "
                        "achicá con net/bbox/layer o subí max_tokens"
                    ),
                )
            if get_default_store().is_live_stale():
                out = "[AVISO] editor vivo detras del disco (route_board)\n" + out
        log_tool_call(
            tool_name="get_tracks",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(out),
            extra={
                "net": net,
                "bbox": bbox_t,
                "layer": layer,
                "max_tokens": budget,
                "n_items": len(items),
            },
        )
        return out

    @mcp.tool(
        name="delete_tracks_bulk",
        description="Borra tracks/vías por filtro (net/bbox/layer); dry_run lista sin mutar",
    )
    def delete_tracks_bulk(
        net: str | None = None,
        bbox: list[float] | None = None,
        layer: str | None = None,
        include_vias: bool = True,
        dry_run: bool = False,
        base_snap: int | None = None,
    ) -> dict[str, Any]:
        # Sesión 19d (19d.2): el Bloque 3 de 19c necesitó 266 llamadas
        # individuales delete_track/delete_via para vaciar el cobre del board
        # antes de un route_board desde cero. Mismo pipeline de filtrado que
        # get_tracks (reutilizado tal cual: al menos 1 filtro obligatorio,
        # list_net_copper/list_all_copper + _copper_in_bbox/_copper_on_layer),
        # pero el borrado va en un solo remove_many_by_kiid (un round-trip
        # IPC) en vez de N delete_track/delete_via.
        with tool_call_timer() as timer:
            if net is None and bbox is None and layer is None:
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message="delete_tracks_bulk requiere al menos un filtro.",
                    hint=(
                        "Pasá net, bbox=[min_x,min_y,max_x,max_y] o layer — borrar "
                        "todo el cobre a ciegas es riesgoso."
                    ),
                )
            bbox_t: tuple[float, float, float, float] | None = None
            if bbox is not None:
                if len(bbox) != 4:
                    raise KicadMcpError(
                        code=ErrorCode.INVALID_PARAMS,
                        message=(
                            "bbox debe tener 4 valores [min_x,min_y,max_x,max_y] "
                            f"(recibió {len(bbox)})."
                        ),
                        hint="Ejemplo: bbox=[10.0, 10.0, 50.0, 40.0].",
                    )
                bbox_t = (bbox[0], bbox[1], bbox[2], bbox[3])
                if bbox_t[0] > bbox_t[2] or bbox_t[1] > bbox_t[3]:
                    raise KicadMcpError(
                        code=ErrorCode.INVALID_PARAMS,
                        message=f"bbox inválido (min > max): {bbox_t}.",
                        hint="Formato [min_x,min_y,max_x,max_y] con min <= max en cada eje.",
                    )

            board = _resolve_board(bridge)
            if net is not None:
                nets = bridge.list_net_names(board)
                if net not in nets:
                    similars = _similars(net, nets)
                    hint = (
                        "nets similares: " + ", ".join(similars) if similars else "sin sugerencias"
                    )
                    raise KicadMcpError(
                        code=ErrorCode.NET_NOT_FOUND,
                        message=f"Net {net} no existe en el board.",
                        hint=hint,
                    )
                items = bridge.list_net_copper(board, net)
            else:
                items = bridge.list_all_copper(board)
            if bbox_t is not None:
                items = tuple(it for it in items if _copper_in_bbox(it, bbox_t))
            if layer is not None:
                items = tuple(it for it in items if _copper_on_layer(it, layer))
            if not include_vias:
                items = tuple(it for it in items if it.kind != "via")

            tracks_matched = sum(1 for it in items if it.kind != "via")
            vias_matched = sum(1 for it in items if it.kind == "via")

            if dry_run:
                result: dict[str, Any] = {
                    "tracks_deleted": tracks_matched,
                    "vias_deleted": vias_matched,
                    "snap_id": None,
                    "zones_refilled": 0,
                }
                log_tool_call(
                    tool_name="delete_tracks_bulk",
                    latency_ms=timer["latency_ms"],
                    tokens_est=estimate_tokens(str(result)),
                    extra={"net": net, "bbox": bbox_t, "layer": layer, "dry_run": True},
                )
                return result

            _guard_live_stale()  # D-14.1
            check_no_external_disk_edit(  # P3.2: red de seguridad, independiente de base_snap
                get_default_store(), _resolve_root_schematic_or_pcb()
            )
            root = _project_root()
            if base_snap is not None:
                _check_base_snap(base_snap)

            ctx = bridge.read_board_context(board)
            backup_info = ensure_session_backup(root)  # Gate G1
            kiids = [it.kiid for it in items]
            removed = bridge.remove_many_by_kiid(board, kiids)

            zones_refilled = 0
            if any(z.kind == "copper" for z in bridge.list_zones(board)):
                zones_refilled = bridge.refill_zones(board)  # D-14.1: refill post-bulk

            new_state = build_state_from_snapshot(ctx.footprints)
            snap_id = get_default_store().register(new_state, mtimes=None)
            audit_record(
                root,
                tool="delete_tracks_bulk",
                params={
                    "net": net,
                    "bbox": bbox_t,
                    "layer": layer,
                    "include_vias": include_vias,
                    "base_snap": base_snap,
                },
                result={"snap": snap_id, "backup": backup_info.get("backup"), "removed": removed},
            )
            result = {
                "tracks_deleted": tracks_matched,
                "vias_deleted": vias_matched,
                "snap_id": snap_id,
                "zones_refilled": zones_refilled,
            }
        log_tool_call(
            tool_name="delete_tracks_bulk",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(str(result)),
            snap_id=snap_id,
            extra={"net": net, "bbox": bbox_t, "layer": layer, "dry_run": False},
        )
        return result

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
        name="get_footprint_neighbors",
        description=(
            "Vecinos de un footprint en un radio: pads/tracks/vías/holes ajenos + "
            "distancia al borde del board"
        ),
    )
    def get_footprint_neighbors(
        ref: str,
        radius_mm: float = 5.0,
        include_pads: bool = True,
        include_tracks: bool = True,
        include_vias: bool = True,
        include_holes: bool = True,
        include_edge: bool = True,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        # P1 (sesión 21, F-D3-04): D3 gastó 35 min/5 intentos rutéando a mano
        # cerca de J1 por no poder ver "qué hay alrededor" sin reconstruir el
        # mapa a mano con get_tracks(bbox=) iterativo. Read-only, reutiliza
        # get_component_detail/get_tracks/board_outline (NO reinventa
        # geometría) + list_pad_holes (nuevo, compartido con el workaround de
        # F-D3-01 — ver bridge.ipc.PadHole). Distancia = mínimo entre el bbox
        # del footprint target y el ítem vecino (no punto-a-punto).
        with tool_call_timer() as timer:
            board = _resolve_board(bridge)
            detail = bridge.get_component_detail(board, ref)
            bbox_t: tuple[float, float, float, float] = (
                float(detail.bbox_min_x),
                float(detail.bbox_min_y),
                float(detail.bbox_max_x),
                float(detail.bbox_max_y),
            )

            neighbors: dict[str, Any] = {}

            if include_pads:
                own_refs = {ref}
                pad_neighbors: list[dict[str, Any]] = []
                for other_ref in bridge.list_footprint_refs(board):
                    if other_ref in own_refs:
                        continue
                    other = bridge.get_component_detail(board, other_ref)
                    for pad in other.pads:
                        dist = _bbox_distance_to_point(bbox_t, float(pad.x_mm), float(pad.y_mm))
                        if dist <= radius_mm:
                            pad_neighbors.append(
                                {
                                    "ref": other_ref,
                                    "pad": pad.number,
                                    "at": [round(float(pad.x_mm), 3), round(float(pad.y_mm), 3)],
                                    "net": pad.net_name,
                                    "dist_mm": round(dist, 3),
                                }
                            )
                neighbors["pads"] = pad_neighbors

            if include_tracks or include_vias:
                all_copper = bridge.list_all_copper(board)
                if include_tracks:
                    track_neighbors: list[dict[str, Any]] = []
                    for it in all_copper:
                        if it.kind not in ("track", "arc"):
                            continue
                        dist = _copper_distance_to_bbox(it, bbox_t)
                        if dist <= radius_mm:
                            closest = _closest_point_copper_bbox(it, bbox_t)
                            track_neighbors.append(
                                {
                                    "id": it.kiid,
                                    "net": it.net_name,
                                    "layer": it.layer,
                                    "closest_point": [round(closest[0], 3), round(closest[1], 3)],
                                    "dist_mm": round(dist, 3),
                                }
                            )
                    neighbors["tracks"] = track_neighbors
                if include_vias:
                    via_neighbors: list[dict[str, Any]] = []
                    for it in all_copper:
                        if it.kind != "via":
                            continue
                        dist = _copper_distance_to_bbox(it, bbox_t)
                        if dist <= radius_mm:
                            via_neighbors.append(
                                {
                                    "id": it.kiid,
                                    "net": it.net_name,
                                    "at": [
                                        round(float(it.start_x_mm), 3),
                                        round(float(it.start_y_mm), 3),
                                    ],
                                    "dist_mm": round(dist, 3),
                                }
                            )
                    neighbors["vias"] = via_neighbors

            if include_holes:
                hole_neighbors: list[dict[str, Any]] = []
                for hole in bridge.list_pad_holes(board):
                    dist = _bbox_distance_to_point(bbox_t, float(hole.x_mm), float(hole.y_mm))
                    if dist <= radius_mm:
                        hole_neighbors.append(
                            {
                                "kind": hole.kind,
                                "at": [round(float(hole.x_mm), 3), round(float(hole.y_mm), 3)],
                                "diameter_mm": round(float(hole.diameter_mm), 3),
                                "belongs_to": hole.ref,
                                "dist_mm": round(dist, 3),
                            }
                        )
                neighbors["holes"] = hole_neighbors

            if include_edge:
                board_bbox, outline = bridge.board_outline(board)
                if outline == "none":
                    neighbors["edge"] = None
                else:
                    side, edge_dist = _closest_board_edge(bbox_t, board_bbox)
                    neighbors["edge"] = (
                        {"closest_edge": side, "dist_mm": round(edge_dist, 3)}
                        if edge_dist <= radius_mm
                        else None
                    )

            payload: dict[str, Any] = {
                "ref": ref,
                "center": [round(float(detail.x_mm), 3), round(float(detail.y_mm), 3)],
                "bbox": [round(v, 3) for v in bbox_t],
                "neighbors": neighbors,
            }
            budget = max_tokens if max_tokens is not None else _TRACKS_DEFAULT_BUDGET
            out_json = json.dumps(payload, ensure_ascii=False)
            if estimate_tokens(out_json) > budget * _TRACKS_BUDGET_SAFETY:
                raise KicadMcpError(
                    code=ErrorCode.CONTEXT_BUDGET_IMPOSSIBLE,
                    message=f"Los vecinos de {ref} no caben en {budget} tokens.",
                    hint=(
                        f"presupuesto mínimo estimado ≈ {estimate_tokens(out_json)} tokens; "
                        "achicá radius_mm o desactivá alguna categoría (include_*)"
                    ),
                )
            if get_default_store().is_live_stale():
                payload["aviso"] = "editor vivo detras del disco (route_board)"
        log_tool_call(
            tool_name="get_footprint_neighbors",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(out_json),
            extra={"ref": ref, "radius_mm": radius_mm, "max_tokens": budget},
        )
        return payload

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
        # Sesión 34a (auditoría de contratos, asimetría A7): esta era la única
        # tool W-IPC de PCB sin _guard_live_stale()/check_no_external_disk_edit()
        # — mutaba el vivo aunque el disco tuviera un ruteo pendiente de recarga
        # (D-14.1) o hubiera sido editado externamente (P3.2). Fix trivial:
        # mismo guard que sus 9 pares W-IPC, sin cambio de contrato.
        with tool_call_timer() as timer:
            _guard_live_stale()  # D-14.1 (sesión 34a: asimetría A7, faltaba acá)
            check_no_external_disk_edit(  # P3.2: red de seguridad, independiente de base_snap
                get_default_store(), _resolve_root_schematic_or_pcb()
            )
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

    @mcp.tool(
        name="add_zone",
        description="Crea una zona de cobre conectada a un net en una capa (bbox o polygon)",
    )
    def add_zone(
        net: str,
        layer: str,
        bbox: list[float] | None = None,
        polygon: list[list[float]] | None = None,
        priority: int = 0,
        fill: bool = True,
        base_snap: int | None = None,
    ) -> dict[str, Any]:
        # P4.1 (sesión 19): plano de cobre. Devuelve JSON estructurado (no un
        # confirm de texto) — spec explícito de la sesión, a diferencia de
        # add_track/add_via. Refill automático por defecto (fill=True): el
        # caso común es "quiero un plano GND funcional ya"; fill=false difiere
        # el costo (refill_zones() es bloqueante con polling, ver bridge).
        # D-23.2 (ADR-0012, extendido sesión 27): con fill=True, el refill +
        # enforce_hole_clearance del vivo se persiste con save_board() antes
        # de retornar — POST_ZONE_PERSIST_FAILED si la escritura falla. Con
        # fill=False no hay nada que persistir (zona sin rellenar, vivo≠disco
        # como cualquier otra mutación sin save explícito).
        with tool_call_timer() as timer:
            _guard_live_stale()  # D-14.1
            check_no_external_disk_edit(  # P3.2
                get_default_store(), _resolve_root_schematic_or_pcb()
            )
            root = _project_root()
            if base_snap is not None:
                _check_base_snap(base_snap)

            raw_params: dict[str, Any] = {
                "net": net,
                "layer": layer,
                "bbox": bbox,
                "polygon": polygon,
                "priority": priority,
                "fill": fill,
            }
            try:
                vertices = _validate_zone_geometry(bbox, polygon)
            except KicadMcpError as exc:
                _audit_error(root, "add_zone", raw_params, exc.code)
                raise

            board = _resolve_board(bridge)
            nets = bridge.list_net_names(board)
            if net not in nets:
                similars = _similars(net, nets)
                hint = "nets similares: " + ", ".join(similars) if similars else "sin sugerencias"
                _audit_error(root, "add_zone", raw_params, ErrorCode.NET_NOT_FOUND)
                raise KicadMcpError(
                    code=ErrorCode.NET_NOT_FOUND,
                    message=f"Net {net} no existe en el board.",
                    hint=hint,
                )

            # Snapshot pre para derivar el post — una zona no altera el
            # NormalizedState de footprints (patrón add_track/add_via).
            ctx = bridge.read_board_context(board)
            backup_info = ensure_session_backup(root)  # Gate G1
            zone_id, filled, area_mm2 = bridge.add_zone(
                board,
                net=net,
                layer=layer,
                vertices_mm=tuple(vertices),
                priority=priority,
                fill=fill,
            )
            if fill:
                # F-D3-01 (sesión 21): el fill de kipy puede dejar 0mm de
                # clearance contra holes PTH/NPTH/vías ajenos — workaround
                # post-fill obligatorio en TODO camino que rellene (ver
                # docstring de enforce_hole_clearance).
                bridge.enforce_hole_clearance(board, _resolve_root_pcb())
                # D-23.2 (ADR-0012, extendido sesión 27): persistir el vivo ya
                # arreglado por refill+enforce — sin esto el disco queda con
                # el clearance roto de forma indefinida (mismo bug conceptual
                # que F-D4-02, ver docs/investigacion/23-fd4-02.md Bloque 2).
                try:
                    bridge.save_board(board)
                except KicadMcpError as exc:
                    _audit_error(root, "add_zone", raw_params, ErrorCode.POST_ZONE_PERSIST_FAILED)
                    raise KicadMcpError(
                        code=ErrorCode.POST_ZONE_PERSIST_FAILED,
                        message=(
                            f"add_zone creó la zona y corrió refill+enforce en "
                            f"{_resolve_root_pcb().name} pero no pudo guardar el board a disco."
                        ),
                        hint=(
                            "El board VIVO ya tiene la zona rellenada con el clearance "
                            "arreglado; reintentá save_board() manual o descartá los cambios."
                        ),
                        data={"pcb": _resolve_root_pcb().name, "live_has_fix": True},
                    ) from exc
                new_state = build_state_from_snapshot(ctx.footprints)
                # D-23.2: mtimes recolectados POST-save (hallazgo #31 sesión
                # 24) — si se recolectaran antes, quedarían stale y el propio
                # save de add_zone dispararía un EXTERNAL_EDIT_DETECTED
                # espurio en la siguiente lectura.
                mtimes = collect_project_mtimes(_resolve_root_schematic_or_pcb())
                snap_id = get_default_store().register(new_state, mtimes)
            else:
                new_state = build_state_from_snapshot(ctx.footprints)
                snap_id = get_default_store().register(new_state, mtimes=None)
            raw_params["base_snap"] = base_snap
            audit_record(
                root,
                tool="add_zone",
                params=raw_params,
                result={"snap": snap_id, "backup": backup_info.get("backup"), "zone_id": zone_id},
            )
            payload: dict[str, Any] = {
                "zone_id": zone_id,
                "filled": filled,
                "area_mm2": round(area_mm2, 3),
                "snap_id": snap_id,
            }
        log_tool_call(
            tool_name="add_zone",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
            snap_id=snap_id,
            extra={"net": net, "layer": layer, "base_snap": base_snap, "zone_id": zone_id},
        )
        return payload

    @mcp.tool(
        name="add_keepout_zone",
        description="Crea una zona keepout (bloquea tracks/vias/pours/footprints) en una capa",
    )
    def add_keepout_zone(
        layer: str,
        bbox: list[float] | None = None,
        polygon: list[list[float]] | None = None,
        no_tracks: bool = True,
        no_vias: bool = True,
        no_pours: bool = True,
        no_footprints: bool = False,
        base_snap: int | None = None,
    ) -> dict[str, Any]:
        # P4.2 (sesión 19): keepout — estructuralmente una zona (ZT_RULE_AREA)
        # sin net. Caso de uso canónico: keepout circular ~15mm bajo ANT1 del
        # despertador (polígono de 12-16 vértices aproxima el círculo, MVP).
        with tool_call_timer() as timer:
            _guard_live_stale()  # D-14.1
            check_no_external_disk_edit(  # P3.2
                get_default_store(), _resolve_root_schematic_or_pcb()
            )
            root = _project_root()
            if base_snap is not None:
                _check_base_snap(base_snap)

            raw_params: dict[str, Any] = {
                "layer": layer,
                "bbox": bbox,
                "polygon": polygon,
                "no_tracks": no_tracks,
                "no_vias": no_vias,
                "no_pours": no_pours,
                "no_footprints": no_footprints,
            }
            try:
                vertices = _validate_zone_geometry(bbox, polygon)
            except KicadMcpError as exc:
                _audit_error(root, "add_keepout_zone", raw_params, exc.code)
                raise

            board = _resolve_board(bridge)
            ctx = bridge.read_board_context(board)
            backup_info = ensure_session_backup(root)  # Gate G1
            zone_id, area_mm2 = bridge.add_keepout_zone(
                board,
                layer=layer,
                vertices_mm=tuple(vertices),
                no_tracks=no_tracks,
                no_vias=no_vias,
                no_pours=no_pours,
                no_footprints=no_footprints,
            )
            new_state = build_state_from_snapshot(ctx.footprints)
            snap_id = get_default_store().register(new_state, mtimes=None)
            raw_params["base_snap"] = base_snap
            audit_record(
                root,
                tool="add_keepout_zone",
                params=raw_params,
                result={"snap": snap_id, "backup": backup_info.get("backup"), "zone_id": zone_id},
            )
            payload: dict[str, Any] = {
                "zone_id": zone_id,
                "keepout_flags": {
                    "no_tracks": no_tracks,
                    "no_vias": no_vias,
                    "no_pours": no_pours,
                    "no_footprints": no_footprints,
                },
                "area_mm2": round(area_mm2, 3),
                "snap_id": snap_id,
            }
        log_tool_call(
            tool_name="add_keepout_zone",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
            snap_id=snap_id,
            extra={"layer": layer, "base_snap": base_snap, "zone_id": zone_id},
        )
        return payload

    @mcp.tool(
        name="get_zones",
        description="Lista zonas de cobre y keepouts (layer y/o net y/o kind) con id estable",
    )
    def get_zones(
        layer: str | None = None,
        net: str | None = None,
        kind: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        # P4.1 (sesión 19): paralela a get_tracks (D-16.1) — al menos un
        # filtro obligatorio, mismo presupuesto de tokens (D-V3.2). Devuelve
        # copper Y keepout con kind distintivo.
        with tool_call_timer() as timer:
            if layer is None and net is None and kind is None:
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message="get_zones requiere al menos un filtro.",
                    hint=(
                        "Pasá layer, net o kind ('copper'|'keepout') — un board real "
                        "puede tener varias zonas."
                    ),
                )
            if kind is not None and kind not in ("copper", "keepout"):
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"kind={kind!r} inválido.",
                    hint="Usá kind='copper' o kind='keepout'.",
                )

            board = _resolve_board(bridge)
            if net is not None:
                nets = bridge.list_net_names(board)
                if net not in nets:
                    similars = _similars(net, nets)
                    hint = (
                        "nets similares: " + ", ".join(similars) if similars else "sin sugerencias"
                    )
                    raise KicadMcpError(
                        code=ErrorCode.NET_NOT_FOUND,
                        message=f"Net {net} no existe en el board.",
                        hint=hint,
                    )

            items = bridge.list_zones(board)
            if layer is not None:
                items = tuple(z for z in items if z.layer == layer)
            if net is not None:
                items = tuple(z for z in items if z.net_name == net)
            if kind is not None:
                items = tuple(z for z in items if z.kind == kind)

            budget = max_tokens if max_tokens is not None else _TRACKS_DEFAULT_BUDGET
            filter_desc = _zones_filter_desc(layer, net, kind)
            out = _encode_zones(items, filter_desc)
            if estimate_tokens(out) > budget * _TRACKS_BUDGET_SAFETY:
                raise KicadMcpError(
                    code=ErrorCode.CONTEXT_BUDGET_IMPOSSIBLE,
                    message=f"El listado no cabe en {budget} tokens.",
                    hint=(
                        f"presupuesto mínimo estimado ≈ {estimate_tokens(out)} tokens; "
                        "achicá con layer/net/kind o subí max_tokens"
                    ),
                )
            if get_default_store().is_live_stale():
                out = "[AVISO] editor vivo detras del disco (route_board)\n" + out
        log_tool_call(
            tool_name="get_zones",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(out),
            extra={
                "layer": layer,
                "net": net,
                "kind": kind,
                "max_tokens": budget,
                "n_items": len(items),
            },
        )
        return out

    @mcp.tool(
        name="fill_zones",
        description="Refill de todas las zonas de cobre del board (o valida zone_id si se pasa)",
    )
    def fill_zones(zone_id: str | None = None, base_snap: int | None = None) -> dict[str, Any]:
        # P4.3 (sesión 19): kipy 0.7.1 no tiene fill selectivo por zona
        # (docs/investigacion/19-zonas-ipc.md §1/§3) — refill_zones() SIEMPRE
        # recalcula TODAS las zonas de cobre del board. zone_id, si se pasa,
        # sólo VALIDA que exista (ZONE_ID_STALE si no) — no acota el refill.
        # Idempotente: llamarla dos veces seguidas no rompe nada (mismo fill).
        # D-23.2 (ADR-0012, extendido sesión 27): el refill + enforce_hole_
        # clearance del vivo se persiste incondicionalmente con save_board()
        # antes de retornar — POST_ZONE_PERSIST_FAILED si la escritura falla.
        with tool_call_timer() as timer:
            _guard_live_stale()  # D-14.1
            check_no_external_disk_edit(  # P3.2
                get_default_store(), _resolve_root_schematic_or_pcb()
            )
            root = _project_root()
            if base_snap is not None:
                _check_base_snap(base_snap)
            board = _resolve_board(bridge)

            if zone_id is not None:
                item = bridge.get_zone_by_kiid(board, zone_id)
                if item is None:
                    _audit_error(root, "fill_zones", {"zone_id": zone_id}, ErrorCode.ZONE_ID_STALE)
                    raise KicadMcpError(
                        code=ErrorCode.ZONE_ID_STALE,
                        message=f"El id {zone_id} no existe (board mutado).",
                        hint="Re-listá con get_zones y usá un id vigente.",
                    )

            ctx = bridge.read_board_context(board)
            backup_info = ensure_session_backup(root)  # Gate G1
            fill_start = time.perf_counter()
            zones_filled = bridge.refill_zones(board)
            # F-D3-01 (sesión 21): workaround post-fill obligatorio en TODO
            # camino que rellene — ver docstring de enforce_hole_clearance.
            bridge.enforce_hole_clearance(board, _resolve_root_pcb())
            # D-23.2 (ADR-0012, extendido sesión 27): persistir el vivo ya
            # arreglado por refill+enforce — sin esto el disco queda con el
            # clearance roto de forma indefinida (mismo bug conceptual que
            # F-D4-02, ver docs/investigacion/23-fd4-02.md Bloque 2).
            # Incondicional: aun con zones_filled==0 enforce_hole_clearance
            # pudo haber tocado keepouts en el vivo.
            try:
                bridge.save_board(board)
            except KicadMcpError as exc:
                _audit_error(
                    root,
                    "fill_zones",
                    {"zone_id": zone_id, "base_snap": base_snap},
                    ErrorCode.POST_ZONE_PERSIST_FAILED,
                )
                raise KicadMcpError(
                    code=ErrorCode.POST_ZONE_PERSIST_FAILED,
                    message=(
                        f"fill_zones corrió refill+enforce en {_resolve_root_pcb().name} "
                        "pero no pudo guardar el board a disco."
                    ),
                    hint=(
                        "El board VIVO ya tiene el clearance arreglado; reintentá "
                        "save_board() manual o descartá los cambios."
                    ),
                    data={"pcb": _resolve_root_pcb().name, "live_has_fix": True},
                ) from exc
            duration_ms = (time.perf_counter() - fill_start) * 1000
            new_state = build_state_from_snapshot(ctx.footprints)
            # D-23.2: mtimes recolectados POST-save (hallazgo #31 sesión 24) —
            # si se recolectaran antes, quedarían stale y el propio save de
            # fill_zones dispararía un EXTERNAL_EDIT_DETECTED espurio en la
            # siguiente lectura.
            mtimes = collect_project_mtimes(_resolve_root_schematic_or_pcb())
            snap_id = get_default_store().register(new_state, mtimes)
            audit_record(
                root,
                tool="fill_zones",
                params={"zone_id": zone_id, "base_snap": base_snap},
                result={
                    "snap": snap_id,
                    "backup": backup_info.get("backup"),
                    "zones_filled": zones_filled,
                },
            )
            payload: dict[str, Any] = {
                "zones_filled": zones_filled,
                "duration_ms": round(duration_ms, 3),
                "snap_id": snap_id,
            }
        log_tool_call(
            tool_name="fill_zones",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
            snap_id=snap_id,
            extra={"zone_id": zone_id, "base_snap": base_snap, "zones_filled": zones_filled},
        )
        return payload

    @mcp.tool(
        name="delete_zone",
        description="Borra una zona (cobre o keepout) por id (de get_zones)",
    )
    def delete_zone(id: str, base_snap: int | None = None) -> str:
        # P4.4 (sesión 19): CRUD completo, simétrico con delete_track/delete_via
        # (sesión 16) — pero sólo por id: a diferencia del cobre, una zona no
        # tiene un "punto cercano" natural para matching geométrico ambiguo.
        with tool_call_timer() as timer:
            _guard_live_stale()  # D-14.1
            check_no_external_disk_edit(  # P3.2
                get_default_store(), _resolve_root_schematic_or_pcb()
            )
            root = _project_root()
            if base_snap is not None:
                _check_base_snap(base_snap)
            board = _resolve_board(bridge)

            item = bridge.get_zone_by_kiid(board, id)
            if item is None:
                _audit_error(root, "delete_zone", {"id": id}, ErrorCode.ZONE_ID_STALE)
                raise KicadMcpError(
                    code=ErrorCode.ZONE_ID_STALE,
                    message=f"El id {id} no existe o no es una zona (board mutado).",
                    hint="Re-listá con get_zones y usá un id vigente.",
                )

            ctx = bridge.read_board_context(board)
            backup_info = ensure_session_backup(root)  # Gate G1
            removed = bridge.remove_by_kiid(board, item.kiid)
            if not removed:
                _audit_error(root, "delete_zone", {"id": id}, ErrorCode.ZONE_ID_STALE)
                raise KicadMcpError(
                    code=ErrorCode.ZONE_ID_STALE,
                    message="La zona objetivo ya no está en el board (borrado concurrente).",
                    hint="Re-listá con get_zones y reintentá.",
                )
            new_state = build_state_from_snapshot(ctx.footprints)
            snap_id = get_default_store().register(new_state, mtimes=None)
            audit_record(
                root,
                tool="delete_zone",
                params={"id": id, "base_snap": base_snap},
                result={"snap": snap_id, "backup": backup_info.get("backup"), "kiid": item.kiid},
            )
            confirmation = f"OK delete_zone {item.kind} @{item.layer} [snap:{snap_id}]"
        log_tool_call(
            tool_name="delete_zone",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(confirmation),
            snap_id=snap_id,
            extra={"kind": item.kind, "base_snap": base_snap},
        )
        return confirmation

    @mcp.tool(
        name="route_board",
        description="Autoroutea el PCB con Freerouting (headless) y escribe el ruteo a disco",
    )
    def route_board(
        max_passes: int | None = None, timeout_s: int = 600, refill: bool = True
    ) -> dict[str, Any]:
        # D-14.2/D-14.3: mutación masiva de cobre SIN gate interactivo (es cobre
        # re-ruteable; G1 + git protegen). Pipeline: save_board implícito
        # (live→disco, sólo si el board abierto ES el target) → DRC pre-route
        # (para drc.err_preexistentes) → round-trip DSN/Freerouting/SES
        # (subprocess, python del SISTEMA + java; NUNCA el venv) → reemplazo
        # atómico del .kicad_pcb → recarga del vivo → refill+enforce (si
        # corresponde) → **DRC post-route + save_board** → snapshot de DISCO +
        # flag D-14.1. El router corre como subprocess, no por IPC: no toca la
        # cola IPC (contención D-12.7 intacta).
        #
        # D-23.2 (ADR-0012, sesión 24 — cierre F-D4-02): contrato reforzado —
        # cuando ``route_board`` termina OK, disco == memoria == ``err_post``
        # reportado. El DRC que se reporta se mide DESPUÉS del bloque de
        # refill+enforce (no sobre la salida cruda de Freerouting), y ese
        # estado se persiste con ``save_board()`` antes de medirlo. Ver
        # docs/investigacion/23-fd4-02.md para la causa raíz original.
        #
        # P2.2 (sesión 17, D-V3.4): el resultado deja de ser un confirm de
        # ≤50 tok (D-14.2 original) y pasa a JSON estructurado — route_ms
        # (F-08, medido desde sesión 14 pero nunca surfaceado), denominador de
        # nets correcto desde el .dsn/.ses en vez de ``unconnected`` del DRC
        # (F-09: ese conteo mezclaba ratsnest de nets multi-pin con
        # unconnected-* de 1 pin), y causa mínima honesta por net bloqueada
        # (F-12). Trade-off de tokens documentado en tool-catalog.md: sigue
        # siendo 1 sola llamada, no contexto caliente repetido.
        with tool_call_timer() as timer:
            pcb_path = _resolve_root_pcb()
            root = pcb_path.parent
            backup_info = ensure_session_backup(root)  # Gate G1 pre-route
            store = get_default_store()
            # Sesión 32b: único punto de verdad de los params de audit/error —
            # antes duplicado literal en el raise de POST_ROUTE_PERSIST_FAILED
            # y en el audit_record final.
            route_params = {"max_passes": max_passes, "timeout_s": timeout_s, "refill": refill}

            # save_board implícito seguro (D-14.3): sólo baja live→disco si el
            # board abierto es el target y NO hay un ruteo de disco pendiente de
            # recargar (si live_stale ya está activo, el vivo está detrás del
            # disco y guardar lo PISARÍA — se salta).
            #
            # ``is_target_open`` se calcula una sola vez y sirve TAMBIÉN para
            # la recarga automática post-route (P3.1, más abajo): ambos pasos
            # necesitan saber si el board abierto en KiCad es el mismo archivo
            # que se está por rutear.
            open_board = _open_board_or_none(bridge)
            open_path: Path | None = (
                bridge.get_open_board_path(open_board) if open_board is not None else None
            )
            is_target_open = open_path is not None and open_path.resolve() == pcb_path.resolve()

            live_saved = False
            pre_footprints: tuple[FootprintData, ...] = ()
            # P4.3 (sesión 19): conteo de zonas pre-route. Sólo se puede leer
            # vía IPC (kipy), no del archivo — best-effort: 0 si el board no
            # está abierto (mismo criterio que ``pre_footprints``, ambos
            # dependen de ``is_target_open``).
            zones_existentes = 0
            if is_target_open and not store.is_live_stale():
                assert open_board is not None  # is_target_open lo implica
                bridge.save_board(open_board)  # baja live→disco
                live_saved = True
                pre_footprints = bridge.read_board_context(open_board).footprints
                zones_existentes = len(bridge.list_zones(open_board))

            # F-V1-02 (sesión 31): pcbnew.ExportSpecctraDSN falla enteramente
            # si dos o más footprints comparten reference designator, sin
            # importar su posición (confirmado en sesión 31 quitando 3 de 4
            # instancias de "REF**" en ANAVI Dev Mic: ok=False,size=0 →
            # ok=True,size=2.4MB). Lo detectamos ANTES del DRC y del
            # round-trip DSN/Freerouting (subprocess) para cambiar un
            # KICAD_CLI_FAILED opaco con stderr crudo de pcbnew por un error
            # legible y accionable (resolver con set_footprint_ref).
            # Limitación conocida: sólo corre si el board está vivo y no
            # stale — misma degradación best-effort que ``zones_existentes``
            # arriba (``pre_footprints`` es ``()`` si el board no está abierto).
            dups = _find_duplicate_refs(pre_footprints)
            if dups:
                raise KicadMcpError(
                    code=ErrorCode.DUPLICATE_REFS,
                    message=(
                        f"{len(dups)} reference designator(s) duplicados; pcbnew no "
                        "puede exportar el DSN de Freerouting en ese estado."
                    ),
                    hint=(
                        "Anotá los refs duplicados con set_footprint_ref(ref, new_ref, "
                        "kiid=...) — o en KiCad, Tools→Annotate — y reintentá route_board."
                    ),
                    data={"duplicates": [{"ref": r, "kiids": k} for r, k in dups]},
                )

            # DRC pre-route: sólo para drc.err_preexistentes (P2.2). El
            # denominador de nets YA NO sale de acá (F-09).
            pre_report = run_drc(pcb_path)
            pre_err = sum(1 for v in pre_report.violations if v.severity == "error")

            # Round-trip headless. Los errores tipados (D-14.4) se propagan.
            workdir = root / ".kicad-mcp" / "autoroute"
            result = run_autoroute(pcb_path, workdir, max_passes=max_passes, timeout_s=timeout_s)
            # Reemplazo ATÓMICO del board por el ruteado (mismo filesystem →
            # os.replace no deja el .kicad_pcb a medio escribir).
            os.replace(result.routed_pcb, pcb_path)

            # P2.2 (F-09): denominador y estado por net desde el .dsn/.ses del
            # round-trip, no del ``unconnected`` del DRC.
            pin_counts = result.nets_pin_counts
            wire_counts = result.nets_wire_counts
            nets_total = len(pin_counts)
            nets_ruteables = sum(1 for p in pin_counts.values() if p >= 2)
            routed_nets, partial_nets, blocked_nets = classify_net_routing(pin_counts, wire_counts)

            # P3.1 (sesión 18, D-V3.1): recarga automática del editor vivo
            # post-route — reemplaza el File→Revert manual de D-14.1 cuando es
            # posible. Sólo se intenta si el board abierto ES el target recién
            # ruteado (mismo chequeo que el save implícito de arriba).
            # Best-effort: si la recarga falla (busy/timeout/kipy roto), NO
            # tumba route_board — el ruteo YA está en disco y es válido; se cae
            # al viejo guard ``live_stale`` como red de seguridad (reforzada
            # por mtime en P3.2). El flag ``live_stale``/snapshot se aplican
            # más abajo (D-23.2): recién ahí existe un ``snap_id`` y el disco
            # ya está en su estado FINAL (post refill+save si corrió).
            reloaded: bool | str
            # F-V2-REFILL-SILENCIOSO (sesión 32b): la excepción de la recarga
            # ya NO se descarta acá — alimenta el diagnóstico de
            # ``POST_ROUTE_REFILL_SKIPPED`` más abajo (D-32b.1). Sigue siendo
            # best-effort en el sentido de que route_board no aborta en este
            # punto: el ruteo YA está en disco y es válido; lo que puede
            # faltar es el refill de seguridad, y eso se resuelve (o se
            # reporta) después de calcular ``zones_existentes``/el guard.
            reload_error: KicadMcpError | None = None
            if is_target_open:
                assert open_board is not None  # is_target_open lo implica
                try:
                    bridge.reload_board_from_disk(open_board)
                    reloaded = True
                except KicadMcpError as exc:
                    reloaded = False
                    reload_error = exc
            else:
                reloaded = "skipped_editor_closed" if open_board is None else False

            # P4.3 (sesión 19, D-19.1 — ver docs/investigacion/19-zonas-ipc.md
            # §2.4): el ruteo NO necesita tocar el DSN para zonas (Freerouting
            # respeta nativamente el ``(plane)`` que ``ExportSpecctraDSN``
            # emite del outline) — pero los tracks nuevos pueden requerir
            # recalcular el fill (thermal reliefs, clearance contra el cobre
            # recién agregado). Sólo se puede refillear si la recarga (arriba)
            # dejó el board vivo reflejando el archivo recién ruteado —
            # ``reload_board_from_disk`` no tiene contraparte para el caso
            # "editor cerrado" (best-effort, igual que ``pre_footprints``).
            #
            # D-19.1 v6 (sesión 23, docs/investigacion/23-fd4-02.md Bloque 3):
            # Freerouting NO respeta el plano GND como exclusión de ruteo para
            # nets ajenos — lo trata como área libre, así que tracks/vías de
            # otros nets pueden terminar geométricamente dentro del polígono
            # de la zona. El refill+enforce de acá es lo que arregla ese
            # clearance contra la zona ya ruteada; no es cosmético.
            zones_refilladas = 0
            fill_ms = 0.0
            # F-V2-REFILL-SILENCIOSO (sesión 32b): por qué el refill
            # prometido (``refill=true``) NO corrió, cuando corresponde
            # reportarlo. ``None`` = el refill corrió, ``refill=False``, o no
            # había zonas (ya lo dice ``zones.existentes: 0`` sin necesidad de
            # motivo). Los tres restantes son honestos: ``editor_closed`` y
            # ``cross_project`` son caminos de diseño legítimos (tool-catalog
            # ya los documenta vía ``reloaded``); sólo ``reload_failed`` es el
            # bug — ver el raise al final de la función.
            refill_skipped_reason: str | None = None
            if refill and zones_existentes > 0 and reloaded is True:
                assert open_board is not None  # reloaded=True lo implica
                fill_start = time.perf_counter()
                # D-23.2 (ADR-0012, sesión 24): persistir el vivo YA arreglado
                # por refill+enforce — sin esto el disco queda con el
                # clearance roto de forma indefinida (F-D4-02: el bug no era
                # protección ausente, era falta de persistencia post-fix).
                zones_refilladas = _refill_enforce_and_save(
                    bridge, open_board, pcb_path, root, route_params, context="ruteo + refill"
                )
                fill_ms = (time.perf_counter() - fill_start) * 1000
            elif refill and zones_existentes > 0:
                # El guard de arriba no corrió — el refill prometido se
                # saltó. Discriminar el motivo (D-32b.1): ``reload_error`` no
                # ``None`` es la única condición que rompe el contrato
                # D-23.2/ADR-0012 en silencio (F-V2-REFILL-SILENCIOSO).
                if reload_error is not None:
                    refill_skipped_reason = "reload_failed"
                elif open_board is None:
                    refill_skipped_reason = "editor_closed"
                else:
                    refill_skipped_reason = "cross_project"

            # DRC post-route (bridge.rules, como G3) para el conteo de
            # errores. D-23.2: se mide ACÁ, después del refill+enforce+save de
            # arriba, para que ``err_post``/``por_tipo`` reflejen el estado
            # REAL persistido — no la salida cruda de Freerouting (F-D4-02).
            post_report = run_drc(pcb_path)

            # F-D5-01 (sesión 32d, docs/investigacion/32c-f-d5-01.md):
            # Freerouting no modela el plano como conductor (D-19.1) y puede
            # rutear cobre ajeno tan cerca de un pad GND que el refill de
            # arriba —que sí recorta con clearance, correctamente— queda
            # geométricamente incapacitado para alcanzarlo. Stitching
            # automático de una vía bajo guardrails estrictos (D3), fallback
            # a exposición explícita en el payload si el guardrail rechaza —
            # nunca error (D-32d.2). Sólo se intenta con board vivo
            # sincronizado (``reloaded is True``, igual guard que el bloque
            # de refill de arriba) y si hay algo que stitchear
            # (``orphan_items`` no vacío) — H4: cero costo en el camino feliz.
            stitched_vias: list[dict[str, Any]] = []
            orphan_pads: list[dict[str, Any]] = []
            orphan_items = [
                it
                for v in post_report.violations
                if v.rule == "unconnected_items"
                for it in v.items
                if it.pos is not None
            ]
            if orphan_items and reloaded is True and zones_existentes > 0:
                assert open_board is not None  # reloaded=True lo implica
                candidates, orphan_pads = _evaluate_stitch_candidates(
                    orphan_items,
                    bridge.list_all_pads(open_board),
                    bridge.list_zones(open_board),
                    bridge.list_all_copper(open_board),
                )
                for c in candidates:
                    kiid = bridge.add_via(
                        open_board,
                        net=c["net"],
                        x_mm=Mm(c["x_mm"]),
                        y_mm=Mm(c["y_mm"]),
                        diameter_mm=Mm(0.8),
                        drill_mm=Mm(0.4),
                    )
                    stitched_vias.append(_stitched_via_dict(c, kiid))
                if stitched_vias:
                    # D-23.2/ADR-0012: las vías de stitching deben reflejarse
                    # en disco y en drc.err_post — reusa el mismo pipeline
                    # refill+enforce+save de arriba, sobre el vivo ya
                    # actualizado con las vías nuevas, y re-mide.
                    _refill_enforce_and_save(
                        bridge,
                        open_board,
                        pcb_path,
                        root,
                        route_params,
                        context="ruteo + stitching",
                    )
                    post_report = run_drc(pcb_path)

            post_err = sum(1 for v in post_report.violations if v.severity == "error")
            por_tipo: dict[str, int] = {}
            for v in post_report.violations:
                if v.severity == "error":
                    por_tipo[v.rule] = por_tipo.get(v.rule, 0) + 1

            # F-D3-03 (sesión 21): err_introducidos por IDENTIDAD de violación,
            # no por resta de totales — el D3 reportó err_introducidos:0
            # cuando en realidad 56 unconnected_items pre-route fueron
            # reemplazadas por 56 clearance/hole_clearance/copper_edge_clearance
            # post-route (mismo total, composición 100% distinta). Ver
            # bridge.rules.diff_violations.
            err_introducidos, err_resueltos, por_tipo_introducidos = diff_violations(
                pre_report.violations, post_report.violations
            )

            # Snapshot de DISCO: el ruteo no mueve footprints, se deriva de los
            # leídos pre-route (o vacío si el board no estaba abierto/coincidía;
            # el agente re-sincroniza con confirm_reloaded o reload_board_from_disk
            # tras recargar). D-23.2: los mtimes se recolectan ACÁ (no antes del
            # refill+save) — si se registraran con los mtimes previos al nuevo
            # save_board(), quedarían stale y una lectura posterior dispararía
            # un EXTERNAL_EDIT_DETECTED espurio contra el propio guardado de
            # route_board.
            new_state = build_state_from_snapshot(pre_footprints)
            mtimes = collect_project_mtimes(_resolve_root_schematic_or_pcb())
            snap_id = store.register(new_state, mtimes)

            # D-14.1: aplicar el flag de "disco adelante del vivo" ahora que
            # existe snap_id, usando el ``reloaded`` calculado arriba.
            if reloaded is True:
                store.clear_live_stale()
            else:
                store.mark_live_stale(snap_id)

            tracks_added = result.tracks_after - result.tracks_before
            vias_added = result.vias_after - result.vias_before

            payload: dict[str, Any] = {
                "route_ms": round(result.route_ms, 3),
                "nets": {
                    "total": nets_total,
                    "ruteables": nets_ruteables,
                    "ruteadas": len(routed_nets),
                    "parciales": partial_nets,
                    "bloqueadas": [
                        {
                            "net": net,
                            "code": ErrorCode.ROUTE_NET_BLOCKED.value,
                            "causa": "sin camino aparente; revisar manualmente",
                        }
                        for net in blocked_nets
                    ],
                },
                "drc": {
                    "err_preexistentes": pre_err,
                    "err_post": post_err,
                    # F-D3-03: semántica cambiada de resta de totales a
                    # identidad de conjunto (ver diff_violations) — NO se
                    # renombra el campo (F3), documentado en tool-catalog.md.
                    "err_introducidos": err_introducidos,
                    "err_resueltos": err_resueltos,
                    "por_tipo": por_tipo,
                    "por_tipo_introducidos": por_tipo_introducidos,
                },
                "tracks_added": tracks_added,
                "vias_added": vias_added,
                "snap": snap_id,
                "session_dsn": result.dsn_path,
                "session_ses": result.ses_path,
                "reloaded": reloaded,
                "zones": {
                    "existentes": zones_existentes,
                    "refilladas": zones_refilladas,
                    "fill_ms": round(fill_ms, 3),
                    **(
                        {"refill_skipped_reason": refill_skipped_reason}
                        if refill_skipped_reason is not None
                        else {}
                    ),
                },
                # F-D5-01 (sesión 32d): ausentes cuando no aplica (H4) — sin
                # pads huérfanos post-refill, ``route_board`` no agrega
                # ninguna clave nueva al payload.
                **({"stitched_vias": stitched_vias} if stitched_vias else {}),
                **({"orphan_pads": orphan_pads} if orphan_pads else {}),
            }

            audit_result: dict[str, Any] = {
                "snap": snap_id,
                "backup": backup_info.get("backup"),
                "tracks_added": tracks_added,
                "vias_added": vias_added,
                "nets_total": nets_total,
                "nets_ruteables": nets_ruteables,
                "nets_ruteadas": len(routed_nets),
                "nets_bloqueadas": len(blocked_nets),
                "drc_err_post": post_err,
                "live_saved": live_saved,
                "reloaded": reloaded,
                "zones_existentes": zones_existentes,
                "zones_refilladas": zones_refilladas,
            }
            if refill_skipped_reason is not None:
                audit_result["refill_skipped_reason"] = refill_skipped_reason
            if stitched_vias:
                audit_result["stitched_vias"] = stitched_vias
            if orphan_pads:
                audit_result["orphan_pads"] = orphan_pads

            # F-V2-REFILL-SILENCIOSO (sesión 32b, D-32b.1): sólo
            # ``reload_failed`` rompe el contrato D-23.2/ADR-0012 — el
            # refill de seguridad prometido por ``refill=true`` no corrió y
            # NO hay señal de error. El raise va ACÁ (no en el guard de
            # arriba) a propósito: recién acá ya corrieron el DRC post-route,
            # el registro del snapshot y ``store.mark_live_stale`` — abortar
            # antes dejaría el flag ``live_stale`` en ``False`` con el disco
            # adelante del vivo, y un ``fill_zones()`` posterior pasaría
            # ``_guard_live_stale()`` y pisaría el ruteo con su propio
            # ``save_board``. El audit_record se escribe SIEMPRE (con o sin
            # error) para no perder el result forense que permitió detectar
            # este bug en sesión 32.
            refill_broke_contract = refill_skipped_reason == "reload_failed"
            audit_record(
                root,
                tool="route_board",
                params=route_params,
                result=audit_result,
                error_code=(
                    ErrorCode.POST_ROUTE_REFILL_SKIPPED.value if refill_broke_contract else None
                ),
            )

            if refill_broke_contract:
                assert reload_error is not None  # "reload_failed" lo implica
                raise KicadMcpError(
                    code=ErrorCode.POST_ROUTE_REFILL_SKIPPED,
                    message=(
                        f"route_board ruteó {pcb_path.name} y lo escribió a disco, pero el "
                        f"refill de seguridad de {zones_existentes} zona(s) NO corrió: la "
                        "recarga del editor vivo falló y refillear el vivo desactualizado "
                        "pisaría el ruteo."
                    ),
                    hint=(
                        "El ruteo en disco es válido pero le falta el clearance contra la "
                        "zona (D-19.1). Corré reload_board_from_disk() y después "
                        "fill_zones() para completar el refill de seguridad."
                    ),
                    data={
                        "pcb": pcb_path.name,
                        "snap": snap_id,
                        "zones_existentes": zones_existentes,
                        "zones_refilladas": zones_refilladas,
                        "tracks_added": tracks_added,
                        "vias_added": vias_added,
                        "drc_err_post": post_err,
                        "reload_error_code": reload_error.code.value,
                    },
                ) from reload_error
        log_tool_call(
            tool_name="route_board",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
            snap_id=snap_id,
            extra={
                "export_ms": round(result.export_ms, 3),
                "route_ms": round(result.route_ms, 3),
                "import_ms": round(result.import_ms, 3),
                "live_saved": live_saved,
                "drc_err_post": post_err,
                "reloaded": reloaded,
            },
        )
        return payload


def _open_board_or_none(bridge: IpcBridge) -> BoardHandle | None:
    """Board abierto, o ``None`` si KiCad no corre / no hay board (D-14.3).

    ``route_board`` opera sobre DISCO: la ausencia del board vivo no es un error
    (el ruteo no lo necesita), sólo desactiva el ``save_board`` implícito.
    """
    try:
        return bridge.get_open_board()
    except KicadMcpError as exc:
        if exc.code is ErrorCode.KICAD_NOT_RUNNING:
            return None
        raise


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
    """Representación compacta de un candidato ambiguo para ``data.candidates``.

    Sesión 16 (D-16.2): ``id`` es el KIID del ítem — el agente resuelve la
    ambigüedad con una segunda llamada ``delete_track(id=...)``/
    ``delete_via(id=...)`` en vez de refinar coordenadas a ciegas.
    """
    d: dict[str, Any] = {"id": item.kiid, "kind": item.kind, "net": item.net_name}
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

    ``ref``/``number``/``net_name`` son entrada no confiable (CLAUDE.md regla
    6). El header (``DETAIL|<ref>|pcb|...``) es ``|``-delimitado — un espacio
    en ``ref`` es inocuo ahí, así que usa ``_sanitize`` puro (H2, sesión 37).
    Las líneas de pad son space-delimited — ``number``/``net_name`` usan
    ``_sanitize_space_delimited`` (sesión 37), que además neutraliza el
    espacio, delimitador posicional de esa línea (H36.1, sesión 36).
    """
    w = float(detail.bbox_max_x) - float(detail.bbox_min_x)
    h = float(detail.bbox_max_y) - float(detail.bbox_min_y)
    rot_f = float(detail.rotation_deg)
    rot: int | float = int(rot_f) if rot_f.is_integer() else rot_f
    # Sesión 36 (R2): ref es entrada no confiable (CLAUDE.md regla 6). Header
    # |-delimitado (H2, sesión 37): un espacio en ref no rompe el parser, no
    # se usa _sanitize_space_delimited acá.
    ref = _sanitize(detail.ref)[0]
    header = (
        f"DETAIL|{ref}|pcb|at:{float(detail.x_mm):.1f},{float(detail.y_mm):.1f}"
        f"|rot:{rot}|bbox:{w:.1f}x{h:.1f}"
        f"|box:{float(detail.bbox_min_x):.1f},{float(detail.bbox_min_y):.1f};"
        f"{float(detail.bbox_max_x):.1f},{float(detail.bbox_max_y):.1f}"
        f"|src:{detail.bbox_source}"
    )
    lines = [header, f"[PADS] {len(detail.pads)}"]
    for p in detail.pads:
        # Sesión 37: number/net_name van en línea space-delimited (H36.1).
        num = _sanitize_space_delimited(p.number) if p.number else "-"
        net = _sanitize_space_delimited(p.net_name) if p.net_name else "-"
        lines.append(
            f"{num} {net} {float(p.x_mm):.1f},{float(p.y_mm):.1f} "
            f"{float(p.w_mm):.2f}x{float(p.h_mm):.2f} {p.layer}"
        )
    return "\n".join(lines) + "\n"


def _tracks_filter_desc(
    net: str | None, bbox: tuple[float, float, float, float] | None, layer: str | None
) -> str:
    """Cabecera legible de qué filtro se aplicó (D-16.1) — el agente confirma
    qué recibió sin adivinar por el conteo de líneas.

    ``net``/``bbox``/``layer`` son parámetros de la tool MCP: ``net`` se
    valida contra ``list_net_names`` y ``bbox`` es float-formateado, pero
    ``layer`` **no se valida en ningún punto** — sólo se usa como filtro de
    igualdad. Sin sanitizar, un ``layer`` con ``\\n`` forja líneas
    adicionales dentro del bloque ``TRACKS|v1|...`` (sesión 38, corrige el
    gap; no es defensa en profundidad, es el fix a una inyección real). Se
    sanitiza cada componente ANTES de ensamblar, con ``_sanitize`` puro (no
    ``_sanitize_space_delimited``): este header es ``|``-delimitado, un
    espacio en un valor es inocuo acá (mismo criterio que H2, sesión 37).
    Sanitizar el string ya ensamblado destruiría la propia sintaxis
    ``net:x|layer:y`` porque ``_sanitize`` neutraliza ``|`` y ``:``.
    """
    parts = []
    if net is not None:
        parts.append(f"net:{_sanitize(net)[0]}")
    if bbox is not None:
        parts.append(f"bbox:{bbox[0]:.1f},{bbox[1]:.1f};{bbox[2]:.1f},{bbox[3]:.1f}")
    if layer is not None:
        parts.append(f"layer:{_sanitize(layer)[0]}")
    return "|".join(parts)


def _encode_tracks(items: tuple[CopperItem, ...], filter_desc: str) -> str:
    """Serializa segmentos/vías a un formato compacto propio (D-16.1).

    NO es TOON (F1 intacto: ``get_tracks`` es una tool separada, no una
    sección nueva del formato v1). Contrato de ID (D-16.2/D-16.3, documentado
    también en ``docs/specs/tool-catalog.md``): ``id`` es el KIID nativo de
    KiCad — estable mientras el board no cambie, se invalida tras CUALQUIER
    mutación de cobre o recarga del board. Re-listar con ``get_tracks`` tras
    mutar antes de reusar un ``id``.

    Formato (una línea de cabecera + una por ítem):

        TRACKS|v1|net:GND|3s|1v
        T <id> GND F.Cu w0.250 (10.000,10.000)->(20.000,10.000)
        A <id> GND F.Cu w0.250 (20.000,10.000)->(25.000,15.000)~(22.500,12.500)
        V <id> GND (50.000,50.000) d0.800/0.400 F.Cu-B.Cu

    ``T``=track, ``A``=arco (con punto medio ``~x,y``), ``V``=via.
    Coordenadas/anchos en mm con 3 decimales (grid de KiCad llega a 0.01 mm;
    1 decimal como en ``get_component_detail`` sería insuficiente para
    cirugía de precisión).

    ``net_name`` es entrada no confiable (CLAUDE.md regla 6): se sanitiza con
    ``_sanitize_space_delimited`` (sesión 37), que además de los caracteres
    estructurales de TOON (§5) neutraliza el espacio — delimitador posicional
    de esta línea (sesión 36, R2 + sesión 37, cierre del gap del espacio).

    ``net_name`` vacío cae a ``"-"`` (sesión 38), consistente con
    ``ZoneItem.net_name``/``PadDetail.net_name``. ``layer`` cae a ``"-"`` si
    es ``None`` (sesión 38) — defensivo: hoy sólo ``CopperItem`` de vía trae
    ``layer=None`` y esa rama no emite ``layer``, así que el caso no es
    alcanzable por el bridge en producción, pero el tipo (`str | None`)
    lo permite y el fallback cierra el flanco a costo cero.
    """
    segs = [it for it in items if it.kind in ("track", "arc")]
    vias = [it for it in items if it.kind == "via"]
    header = (
        f"TRACKS|v1|{filter_desc}|{len(segs)}s|{len(vias)}v"
        if filter_desc
        else (f"TRACKS|v1|{len(segs)}s|{len(vias)}v")
    )
    lines = [header]
    for it in segs:
        kind_letter = "A" if it.kind == "arc" else "T"
        w = f"{float(it.width_mm):.3f}" if it.width_mm is not None else "?"
        sx, sy = float(it.start_x_mm), float(it.start_y_mm)
        ex = float(it.end_x_mm) if it.end_x_mm is not None else sx
        ey = float(it.end_y_mm) if it.end_y_mm is not None else sy
        # Sesión 37: net_name va en línea space-delimited (H36.1, gap del
        # espacio) — _sanitize_space_delimited neutraliza también whitespace.
        # Sesión 38: fallback "-" para net_name vacío y layer None.
        net = _sanitize_space_delimited(it.net_name) if it.net_name else "-"
        layer = it.layer or "-"
        line = (
            f"{kind_letter} {it.kiid} {net} {layer} w{w} ({sx:.3f},{sy:.3f})->({ex:.3f},{ey:.3f})"
        )
        if it.kind == "arc" and it.mid_x_mm is not None and it.mid_y_mm is not None:
            line += f"~({float(it.mid_x_mm):.3f},{float(it.mid_y_mm):.3f})"
        lines.append(line)
    for it in vias:
        size = f"{float(it.size_mm):.3f}" if it.size_mm is not None else "?"
        drill = f"{float(it.drill_mm):.3f}" if it.drill_mm is not None else "?"
        layers = "-".join(it.via_layers) if it.via_layers else "?"
        # Sesión 37: idem, línea de vía también space-delimited.
        # Sesión 38: fallback "-" para net_name vacío (gap declarado en
        # decisión #4, sesión 36 — CopperItem.net_name no tenía guard `or "-"`
        # a diferencia de ZoneItem/PadDetail).
        net = _sanitize_space_delimited(it.net_name) if it.net_name else "-"
        lines.append(
            f"V {it.kiid} {net} "
            f"({float(it.start_x_mm):.3f},{float(it.start_y_mm):.3f}) "
            f"d{size}/{drill} {layers}"
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
