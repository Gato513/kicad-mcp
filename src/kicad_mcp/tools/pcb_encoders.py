"""Encoders ad-hoc de ``tools/pcb.py`` (DT1 slice 1, sesión 41).

Extracción mecánica del cluster de encoders desde ``tools/pcb.py``
(``docs/analisis/40-dt1-caracterizacion.md`` §10): cero cambio de
comportamiento, formatos byte-exactos preservados (goldens
``tests/golden/004_pcb_tracks_canarios``, ``005_pcb_zones_canarios``,
``006_pcb_component_detail_canarios``).

Los tres formatos serializados acá (``_encode_tracks``, ``_encode_zones``,
``_encode_component_detail``) NO son TOON (F1 intacto) — ver sus docstrings.
``tools/pcb.py`` re-exporta las siete funciones de este módulo para preservar
su superficie privada previa (consumida por
``tests/test_pcb_encoders_golden.py`` y
``tests/test_pcb_session38_filter_desc.py``).
"""

from __future__ import annotations

import re
from typing import Final

from ..bridge.ipc import ComponentDetail, CopperItem, Mm, ZoneItem

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
