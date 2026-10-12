"""Geometría pura de ``tools/pcb.py`` (DT1 slice 2, sesión 42).

Extracción mecánica del cluster de geometría desde ``tools/pcb.py``
(``docs/analisis/42-dt1-slice2-caracterizacion.md`` §4/§10): cero cambio de
comportamiento, mismo criterio de cero I/O y cero acoplamiento *funcional*
hacia ``bridge``/errores/mcp/audit que motivó la selección de este cluster
(§5, gates S1/S8). El único vínculo con ``bridge`` es el import de tipos de
anotación (``BBoxMm``/``CopperItem``/``PadGeom``, dataclasses puras) — nunca
una llamada IPC ni un símbolo de ``IpcBridge``/``BoardHandle``.

``tools/pcb.py`` re-exporta las trece funciones de este módulo para
preservar su superficie privada previa. Ningún consumidor externo conocido
las importa por nombre hoy (§7 de la caracterización) — el re-export es
defensivo, por simetría con el Slice 1 (``pcb_encoders.py``).
"""

from __future__ import annotations

import math

from ..bridge.ipc import BBoxMm, CopperItem, PadGeom


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
    para cualquier capa de su span (``tool-catalog.md``), no sólo sus dos
    extremos: ``via_span_layers`` trae ese span real cuando el bridge pudo
    resolver el stackup; si no (``None`` — degradación en KiCad 9.0-9.0.4,
    ver ``_safe_copper_layer_values``), cae a matchear sólo los extremos de
    ``via_layers``.
    """
    if item.kind == "via":
        if item.via_span_layers is not None:
            return layer in item.via_span_layers
        return item.via_layers is not None and layer in item.via_layers
    return item.layer == layer


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
