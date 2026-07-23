"""Puente IPC con KiCad vía ``kicad-python`` (``kipy``).

Responsabilidades del bridge (arquitectura §10, restricciones-kicad.md):
- Establecer conexión al socket IPC (``KICAD_API_SOCKET`` o el default de
  la librería), reportar versión, y proveer acceso al ``Board`` abierto.
- **Timeout duro de 2 s** por request (impuesto por ``kipy``).
- **Cola de profundidad 1**: un ``threading.Lock`` alrededor de toda
  llamada IPC. KiCad procesa cada request en el hilo de UI; enviarle
  concurrencia lo bloquea.
- **Detección de reinicio**: ``KICAD_API_TOKEN`` cambia por instancia.
  Si cambia entre dos llamadas, la operación en curso falla con
  ``KICAD_RESTARTED``.
- **Unidades**: ``Nm`` (nanómetros del IPC) y ``Mm`` (milímetros de todo
  el resto del sistema) son ``NewType`` distintos. Los conversores están
  aquí; ninguna otra capa ve nanómetros jamás.

No expone envelopes ni tipos de ``kipy`` fuera del bridge: quien llama
recibe primitivos o dataclasses de este módulo. Frontera de proceso →
validación en el borde (regla #5).
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NewType, Protocol, TypeVar

from ..errors import ErrorCode, KicadMcpError
from ..logging_config import log_ipc_retry, log_socket_glob_ambiguous

_T = TypeVar("_T")

# --- Unidades del dominio -----------------------------------------------------

Nm = NewType("Nm", int)
"""Nanómetros — la unidad interna del IPC de KiCad."""

Mm = NewType("Mm", float)
"""Milímetros — la unidad que el resto del sistema (TOON, tools, agente) usa."""


def nm_to_mm(value: Nm) -> Mm:
    """Convierte nanómetros → milímetros. Único punto de conversión."""
    return Mm(value / 1_000_000)


def mm_to_nm(value: Mm) -> Nm:
    """Convierte milímetros → nanómetros. Redondeo half-even (banker)."""
    return Nm(round(value * 1_000_000))


# --- Dataclasses de retorno (nunca expone tipos de kipy) ----------------------


@dataclass(frozen=True)
class IpcVersion:
    """Versión reportada por KiCad. Formato normalizado."""

    full: str
    major: int
    minor: int
    patch: int


@dataclass(frozen=True)
class BoardHandle:
    """Handle opaco a un board abierto. Detalles internos privados al bridge."""

    _raw: Any  # ``kipy.board.Board`` — no se filtra fuera del bridge

    @property
    def raw(self) -> Any:
        """Escape controlado: acceso al ``Board`` de ``kipy`` para operaciones IPC.

        Uso restringido al mismo módulo ``bridge`` (regla implícita: los
        tipos de ``kipy`` no viajan a ``tools/`` ni al agente).
        """
        return self._raw


@dataclass(frozen=True)
class BBoxMm:
    """Bounding box del board en milímetros."""

    min_x: Mm
    min_y: Mm
    max_x: Mm
    max_y: Mm

    def contains(self, x: Mm, y: Mm) -> bool:
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y


@dataclass(frozen=True)
class FootprintPadData:
    """Pad de un footprint expuesto por el bridge para construir estado.

    Datos primitivos: el bridge nunca deja escapar tipos de kipy fuera de
    su borde (regla #5). Sesión 05 T5.
    """

    number: str
    net_name: str | None


@dataclass(frozen=True)
class FootprintData:
    """Footprint del board expuesto por el bridge para construir estado.

    Sesión 05 T5: alimenta al ``state_builder.build_state_from_board`` para
    registrar snapshots vivos tras mutaciones IPC (ADR-0007).

    Sesión 08 D-08.1/D-08.2: ``kiid`` captura el KIID de KiCad (uuid como
    string) durante la pasada única de ``read_board_context``. Habilita la
    verificación puntual post-mutación por ``get_items_by_id`` sin volver a
    iterar el board (D-08.2). Default ``""`` para retrocompat con snapshots
    reconstruidos desde disco (sin KIID accesible).
    """

    ref: str
    value: str
    x_mm: Mm
    y_mm: Mm
    pads: tuple[FootprintPadData, ...]
    kiid: str = ""


@dataclass(frozen=True)
class PadDetail:
    """Pad de un footprint con geometría ABSOLUTA (sesión 11, D-11.3).

    kipy almacena los hijos del footprint con posiciones absolutas ya
    rotadas (``FootprintInstance.position`` setter: "KiCad footprint children
    are stored with absolute positions"). Es decir, ``x_mm``/``y_mm`` son la
    posición del pad en coordenadas de board — la cuenta "origen + offset
    rotado" que el agente del dogfooding hizo a mano ya viene resuelta por
    kipy. No rotamos nada acá; sólo leemos.
    """

    number: str
    net_name: str | None
    x_mm: Mm
    y_mm: Mm
    w_mm: Mm
    h_mm: Mm
    layer: str  # "F.Cu" | "B.Cu" | "*.Cu" (through-hole)


@dataclass(frozen=True)
class ComponentDetail:
    """Detalle geométrico de un footprint del board vivo (D-11.3).

    ``bbox_*`` es el courtyard cuando el footprint lo define (layers
    ``F.CrtYd``/``B.CrtYd``); si no hay courtyard, cae a la envolvente de los
    pads. ``bbox_source`` distingue ambos casos para que el agente sepa qué
    recibió.
    """

    ref: str
    value: str
    x_mm: Mm
    y_mm: Mm
    rotation_deg: float
    bbox_min_x: Mm
    bbox_min_y: Mm
    bbox_max_x: Mm
    bbox_max_y: Mm
    bbox_source: str  # "courtyard" | "pads"
    pads: tuple[PadDetail, ...]


@dataclass(frozen=True)
class CopperItem:
    """Ítem de cobre (track / arc / via) de un net, con KIID (D-11.2).

    Superficie primitiva para el matching geométrico del borrado dirigido:
    el tool calcula la distancia punto→segmento (track/arc) o punto→centro
    (via) en unidades mm y decide el target o la ambigüedad. El bridge sólo
    lee y expone KIIDs — jamás tipos de kipy (regla 5).

    Para ``kind="via"`` los campos ``end_*`` y ``mid_*`` son ``None``.
    Para ``kind="arc"`` ``mid_*`` trae el punto medio (polilínea
    start→mid→end); para ``kind="track"`` es ``None``.
    """

    kind: str  # "track" | "arc" | "via"
    kiid: str
    net_name: str
    layer: str | None
    start_x_mm: Mm
    start_y_mm: Mm
    end_x_mm: Mm | None
    end_y_mm: Mm | None
    mid_x_mm: Mm | None
    mid_y_mm: Mm | None
    # Sesión 16 (D-16.1, ``get_tracks``): geometría adicional para la vista de
    # cobre. ``None`` cuando no aplica al ``kind`` (ancho para vías, tamaño/
    # drill/capas para tracks). Default ``None`` por retrocompat: los tests
    # existentes construyen ``CopperItem`` sin estos campos.
    width_mm: Mm | None = None  # track / arc
    size_mm: Mm | None = None  # via: diámetro
    drill_mm: Mm | None = None  # via
    via_layers: tuple[str, str] | None = None  # via: (capa_inicio, capa_fin)


@dataclass(frozen=True)
class ZoneItem:
    """Zona de cobre o keepout (rule area) de un board, con KIID (P4, sesión 19).

    Un único tipo cubre ambos ``kind`` — igual que ``kipy.board_types.Zone``,
    que modela cobre/gráfico/rule-area con la misma clase Python
    (``docs/investigacion/19-zonas-ipc.md`` §1). ``net_name`` es ``None`` para
    keepouts (no se conectan a un net). ``vertices_mm`` es el polígono del
    outline **de diseño** (no el resultado del fill — confirmado en la
    investigación que el DSN de Freerouting también usa el outline, no
    ``filled_polygons``); ``bbox_*``/``area_mm2`` se derivan de esos mismos
    vértices (fórmula shoelace), consistentes entre sí.
    """

    kind: str  # "copper" | "keepout"
    kiid: str
    net_name: str | None
    layer: str  # primera capa de cobre de la zona (MVP: una capa por zona)
    bbox_min_x: Mm
    bbox_min_y: Mm
    bbox_max_x: Mm
    bbox_max_y: Mm
    area_mm2: float
    filled: bool
    vertices_mm: tuple[tuple[Mm, Mm], ...]


@dataclass(frozen=True)
class PadGeom:
    """Geometría de un pad para la validación de colisiones de ``add_track``
    (D-16.4). Fuente: ``Board.get_pads()`` — UNA pasada IPC para todo el board
    (mismo patrón de costo que ``list_all_copper``), sin iterar footprint por
    footprint.

    ``corner_ratio`` unifica la forma del pad como un rectángulo con esquinas
    redondeadas (ver ``_pad_corner_ratio``): ``0.0`` para rect/trapezoid/custom
    (aproximación conservadora: rectángulo completo), el ``roundrect_rratio``
    real para roundrect, y ``0.5`` (máximo geométrico) para circle/oval — que
    con la misma fórmula da círculo/estadio exactos. No lleva ``ref``: el
    chequeo de colisión sólo necesita net (para excluir same-net) y geometría.
    """

    net_name: str | None
    layer: str  # "F.Cu" | "B.Cu" | "*.Cu" (pasante)
    x_mm: Mm
    y_mm: Mm
    w_mm: Mm
    h_mm: Mm
    rotation_deg: float
    corner_ratio: float  # 0..0.5


@dataclass(frozen=True)
class BoardContext:
    """Estado del board consolidado en UNA sola pasada ``get_footprints()``.

    D-08.1: los tools de mutación necesitan (1) la lista de refs para
    validar existencia, (2) el bbox para validar coordenadas, y (3) el
    snapshot completo con KIID para localizar el target y construir el
    post-estado. Antes cada uno costaba una pasada O(board) separada
    (~3 s cada una contra el board de 202 refs, sesión 07 §T5). Esta
    dataclass es el resultado consolidado: los tools consumen ``refs`` +
    ``bbox`` para validar y ``footprints`` para encontrar el target por
    ref con su KIID ya en mano (sin volver a pasar por get_footprints).

    Es una lectura idempotente → entra en la whitelist de retry (D-08.3).
    Devuelve primitivos/dataclasses del bridge, jamás tipos de kipy
    (regla 5).
    """

    refs: tuple[str, ...]
    bbox: BBoxMm
    footprints: tuple[FootprintData, ...]


# --- Helper de conversión kipy → FootprintData (única fuente de la verdad) ----


def _footprint_to_data(fp: Any, *, capture_kiid: bool) -> FootprintData:
    """Convierte un ``kipy.FootprintInstance`` en ``FootprintData`` primitivo.

    Sesión 08: unifica la conversión que antes vivía duplicada dentro de
    ``snapshot_footprints`` y ``read_board_context``. La regla 5 exige que
    ningún tipo de kipy salga del bridge; este helper es el único punto
    donde ese cruce ocurre para la superficie ``FootprintData``.

    ``capture_kiid=True`` activa la lectura del ``fp.id.value`` (uuid del
    footprint) — solo lo necesita ``read_board_context`` (D-08.1) para
    permitir la verificación puntual por KIID de D-08.2. La lectura
    aislada de ``snapshot_footprints`` la omite (aditiva y compatible).
    """
    ref = str(fp.reference_field.text.value)
    value = str(fp.value_field.text.value)
    pos = fp.position
    x = nm_to_mm(Nm(int(pos.x)))
    y = nm_to_mm(Nm(int(pos.y)))
    pads: list[FootprintPadData] = []
    for pad in fp.definition.pads:
        number = str(pad.number)
        net = pad.net
        net_name = str(net.name) if net is not None and net.name else None
        pads.append(FootprintPadData(number=number, net_name=net_name))
    kiid = str(fp.id.value) if capture_kiid else ""
    return FootprintData(
        ref=ref,
        value=value,
        x_mm=x,
        y_mm=y,
        pads=tuple(pads),
        kiid=kiid,
    )


def _layer_int_to_str(layer_value: int) -> str:
    """``BoardLayer`` enum int → nombre canónico de KiCad (``F.Cu``, ``B.Cu``…).

    Inverso exacto del mapeo que usa ``add_track`` (``BL_{layer/'.'->'_'}``):
    kipy nombra el enum ``BL_F_Cu``; quitamos el prefijo ``BL_`` y volvemos
    los ``_`` a ``.``. Importa perezoso para no forzar kipy a nivel módulo.
    """
    from kipy.proto.board.board_types_pb2 import BoardLayer

    name = str(BoardLayer.Name(layer_value))  # p. ej. "BL_F_Cu"
    return name.removeprefix("BL_").replace("_", ".")


def _pad_layer_str(pad: Any) -> str:
    """Capa de un pad: ``*.Cu`` para pasantes; la capa de cobre para SMD."""
    from kipy.proto.board.board_types_pb2 import PadType

    if pad.pad_type in (PadType.PT_PTH, PadType.PT_NPTH):
        return "*.Cu"
    copper = pad.padstack.copper_layers
    if copper:
        return _layer_int_to_str(copper[0].layer)
    return "*.Cu"


def _pad_corner_ratio(copper_layer: Any) -> float:
    """``corner_ratio`` unificado (D-16.4) para el chequeo de colisiones.

    Una única fórmula de rectángulo-con-esquinas-redondeadas cubre las formas
    reales de KiCad: ``r = ratio * min(w_mm, h_mm)``, ``ratio`` acotado a
    ``[0, 0.5]`` (el 0.5 es el máximo geométrico de KiCad — con ``w == h``
    degenera en círculo exacto; con ``w != h``, en estadio/oval exacto).

    - ``PSS_ROUNDRECT``: el ``corner_rounding_ratio`` real del padstack.
    - ``PSS_CIRCLE`` / ``PSS_OVAL``: ``0.5`` — la misma fórmula da la forma
      exacta (círculo u oval-estadio), sin código geométrico separado.
    - ``PSS_RECTANGLE`` / ``PSS_TRAPEZOID`` / ``PSS_CHAMFEREDRECT`` /
      ``PSS_CUSTOM``: ``0.0`` — aproximación conservadora (rectángulo
      completo, sin recorte de esquina). Documentado como aproximación
      deliberada (sesión 16): trapezoid/custom no tienen una forma
      rectangular-redondeada equivalente exacta, y tratarlas como rectángulo
      lleno nunca subestima el área ocupada por el pad (nunca dispara un
      falso negativo, sólo puede sobre-rechazar en el caso raro de esas
      formas — igual que antes de esta sesión, donde no había chequeo).
    """
    from kipy.proto.board.board_types_pb2 import PadStackShape as PSS

    shape = copper_layer.shape
    if shape == PSS.PSS_ROUNDRECT:
        return max(0.0, min(0.5, float(copper_layer.corner_rounding_ratio)))
    if shape in (PSS.PSS_CIRCLE, PSS.PSS_OVAL):
        return 0.5
    return 0.0


def _is_copper_item(it: Any) -> bool:
    """``True`` si ``it`` es un ``Track``/``ArcTrack``/``Via`` de kipy.

    ``get_items``/``get_items_by_id`` pueden devolver otros tipos (p. ej. un
    KIID que apunta a un footprint); el llamador filtra con esto antes de
    convertir a ``CopperItem`` (D-16.1/D-16.2).
    """
    return type(it).__name__ in ("Track", "ArcTrack", "Via")


def _kipy_copper_to_item(it: Any, net_name: str) -> CopperItem:
    """Convierte un ``Track``/``ArcTrack``/``Via`` de kipy a ``CopperItem``.

    Única fuente de la verdad de la conversión (D-16.1): la usan
    ``list_net_copper``, ``list_all_copper`` y ``get_copper_by_kiid`` por
    igual. Precondición: ``_is_copper_item(it)`` es ``True``.
    """
    tname = type(it).__name__
    if tname == "Via":
        p = it.position
        drill = it.padstack.drill
        return CopperItem(
            kind="via",
            kiid=str(it.id.value),
            net_name=net_name,
            layer=None,
            start_x_mm=nm_to_mm(Nm(int(p.x))),
            start_y_mm=nm_to_mm(Nm(int(p.y))),
            end_x_mm=None,
            end_y_mm=None,
            mid_x_mm=None,
            mid_y_mm=None,
            size_mm=nm_to_mm(Nm(int(it.diameter))),
            drill_mm=nm_to_mm(Nm(int(it.drill_diameter))),
            via_layers=(
                _layer_int_to_str(drill.start_layer),
                _layer_int_to_str(drill.end_layer),
            ),
        )
    s = it.start
    e = it.end
    is_arc = tname == "ArcTrack"
    mid = it.mid if is_arc else None
    return CopperItem(
        kind="arc" if is_arc else "track",
        kiid=str(it.id.value),
        net_name=net_name,
        layer=_layer_int_to_str(it.layer),
        start_x_mm=nm_to_mm(Nm(int(s.x))),
        start_y_mm=nm_to_mm(Nm(int(s.y))),
        end_x_mm=nm_to_mm(Nm(int(e.x))),
        end_y_mm=nm_to_mm(Nm(int(e.y))),
        mid_x_mm=nm_to_mm(Nm(int(mid.x))) if mid is not None else None,
        mid_y_mm=nm_to_mm(Nm(int(mid.y))) if mid is not None else None,
        width_mm=nm_to_mm(Nm(int(it.width))),
    )


def _polygon_area_mm2(vertices_mm: tuple[tuple[Mm, Mm], ...]) -> float:
    """Área de un polígono simple por la fórmula shoelace (P4, sesión 19).

    Se calcula sobre los vértices del ``outline`` de diseño, no sobre el
    resultado del fill (que puede encogerse por clearance) — consistente con
    el hallazgo de la investigación de que Freerouting también respeta el
    outline, no el fill. Válido para polígonos simples (no auto-intersectantes,
    ya garantizado por ``_polygon_is_simple`` en el tool antes de crear la zona).
    """
    n = len(vertices_mm)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        x0, y0 = float(vertices_mm[i][0]), float(vertices_mm[i][1])
        x1, y1 = float(vertices_mm[(i + 1) % n][0]), float(vertices_mm[(i + 1) % n][1])
        total += x0 * y1 - x1 * y0
    return abs(total) / 2.0


def _copper_layer_values(raw_board: Any) -> list[int]:
    """Todas las capas de cobre HABILITADAS del board (P4, ``add_keepout_zone``
    con ``layer="all"``). Filtra por nombre ``BL_*_Cu`` sobre las capas
    habilitadas — funciona para cualquier stackup (2 capas o N internas), sin
    asumir un conteo fijo.
    """
    from kipy.proto.board.board_types_pb2 import BoardLayer

    out = []
    for layer_value in raw_board.get_enabled_layers():
        if str(BoardLayer.Name(layer_value)).endswith("_Cu"):
            out.append(layer_value)
    return out


def _zone_layer_value(layer: str) -> int:
    """Resuelve un nombre de capa de cobre (``"F.Cu"``, ``"In1.Cu"``…) al enum
    ``BoardLayer`` de kipy. Rechaza capas no-cobre (Edge.Cuts, F.SilkS…) con
    ``INVALID_PARAMS`` — las zonas del MVP (copper o keepout) son siempre de
    cobre (P4: "layer debe ser capa de cobre válida").
    """
    from kipy.proto.board.board_types_pb2 import BoardLayer

    if not layer.endswith(".Cu"):
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message=f"Layer {layer!r} no es una capa de cobre.",
            hint="Usá F.Cu, B.Cu, o una interna (In1.Cu, …).",
        )
    try:
        return int(BoardLayer.Value(f"BL_{layer.replace('.', '_')}"))
    except ValueError as exc:
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message=f"Layer {layer!r} no reconocido por KiCad.",
            hint="Valores esperados: F.Cu, B.Cu, In1.Cu, …",
        ) from exc


def _build_zone_outline(vertices_mm: tuple[tuple[float, float], ...]) -> Any:
    """Construye el ``PolygonWithHoles`` (outline, sin huecos) de una zona a
    partir de vértices en mm (P4). Único punto de conversión mm→nm para
    geometría de zonas — espejo de ``Vector2.from_xy(mm_to_nm(...))`` que usan
    ``add_track``/``draw_board_outline``.
    """
    from kipy.geometry import PolygonWithHoles, PolyLine, PolyLineNode

    outline = PolyLine()
    outline.closed = True
    for x_mm, y_mm in vertices_mm:
        outline.append(PolyLineNode.from_xy(int(mm_to_nm(Mm(x_mm))), int(mm_to_nm(Mm(y_mm)))))
    poly = PolygonWithHoles()
    poly.outline = outline
    return poly


def _kipy_zone_to_item(z: Any) -> ZoneItem:
    """Convierte un ``kipy.board_types.Zone`` a ``ZoneItem`` (P4, D-16.1-like).

    Única fuente de la verdad de la conversión — la usan ``list_zones`` y
    ``get_zone_by_kiid`` por igual (mismo patrón que ``_kipy_copper_to_item``).
    Sólo soporta outlines de vértices rectos (sin arcos) — precondición
    garantizada porque el MVP sólo CREA zonas así; una zona con arcos en su
    outline (creada a mano en KiCad, fuera del control del agente) sale con
    los nodos-arco simplemente omitidos del cálculo de vértices/área/bbox
    (aproximación honesta, no falla).
    """
    from kipy.proto.board.board_types_pb2 import ZoneType

    is_keepout = z.type == ZoneType.ZT_RULE_AREA
    net_name: str | None = None
    if not is_keepout:
        net_obj = z.net
        net_name = str(net_obj.name) if net_obj is not None and net_obj.name else None
    layers = [_layer_int_to_str(layer_value) for layer_value in z.layers]
    layer_str = layers[0] if layers else ""

    vertices_mm: list[tuple[Mm, Mm]] = []
    for node in z.outline.outline:
        if node.has_point:
            vertices_mm.append(
                (
                    nm_to_mm(Nm(int(node.point.x))),
                    nm_to_mm(Nm(int(node.point.y))),
                )
            )
    if vertices_mm:
        xs = [float(v[0]) for v in vertices_mm]
        ys = [float(v[1]) for v in vertices_mm]
        bbox = (min(xs), min(ys), max(xs), max(ys))
    else:
        bbox = (0.0, 0.0, 0.0, 0.0)
    area_mm2 = _polygon_area_mm2(tuple(vertices_mm))

    return ZoneItem(
        kind="keepout" if is_keepout else "copper",
        kiid=str(z.id.value),
        net_name=net_name,
        layer=layer_str,
        bbox_min_x=Mm(bbox[0]),
        bbox_min_y=Mm(bbox[1]),
        bbox_max_x=Mm(bbox[2]),
        bbox_max_y=Mm(bbox[3]),
        area_mm2=area_mm2,
        filled=bool(z.filled),
        vertices_mm=tuple(vertices_mm),
    )


def _pad_to_detail(pad: Any) -> PadDetail:
    """Convierte un ``kipy.Pad`` (leído del board) en ``PadDetail`` absoluto."""
    pos = pad.position
    copper = pad.padstack.copper_layers
    if copper:
        size = copper[0].size
        w = nm_to_mm(Nm(int(size.x)))
        h = nm_to_mm(Nm(int(size.y)))
    else:
        w = Mm(0.0)
        h = Mm(0.0)
    net = pad.net
    net_name = str(net.name) if net is not None and net.name else None
    return PadDetail(
        number=str(pad.number),
        net_name=net_name,
        x_mm=nm_to_mm(Nm(int(pos.x))),
        y_mm=nm_to_mm(Nm(int(pos.y))),
        w_mm=w,
        h_mm=h,
        layer=_pad_layer_str(pad),
    )


def _footprint_bbox_mm(fp: Any) -> tuple[BBoxMm, str]:
    """Bbox absoluto del footprint: courtyard si existe, si no envolvente de pads.

    Devuelve ``(bbox, source)`` con ``source`` ∈ {"courtyard", "pads"}. El
    courtyard sale de los shapes en ``F.CrtYd``/``B.CrtYd`` (concretizados por
    ``definition.shapes``); su ``bounding_box()`` ya está en coordenadas
    absolutas. Sin courtyard, se usa la unión de extents de pad (lado mayor
    como radio para ser conservador ante rotación).
    """
    xs: list[float] = []
    ys: list[float] = []
    for shape in fp.definition.shapes:
        if _layer_int_to_str(getattr(shape, "layer", 0)) in ("F.CrtYd", "B.CrtYd"):
            bb = shape.bounding_box()
            xs.extend([float(bb.pos.x), float(bb.pos.x + bb.size.x)])
            ys.extend([float(bb.pos.y), float(bb.pos.y + bb.size.y)])
    if xs and ys:
        return (
            BBoxMm(
                nm_to_mm(Nm(int(min(xs)))),
                nm_to_mm(Nm(int(min(ys)))),
                nm_to_mm(Nm(int(max(xs)))),
                nm_to_mm(Nm(int(max(ys)))),
            ),
            "courtyard",
        )
    for pad in fp.definition.pads:
        copper = pad.padstack.copper_layers
        half = max(float(copper[0].size.x), float(copper[0].size.y)) / 2 if copper else 0.0
        pos = pad.position
        xs.extend([float(pos.x) - half, float(pos.x) + half])
        ys.extend([float(pos.y) - half, float(pos.y) + half])
    if not xs:
        pos = fp.position
        return (
            BBoxMm(
                nm_to_mm(Nm(int(pos.x))),
                nm_to_mm(Nm(int(pos.y))),
                nm_to_mm(Nm(int(pos.x))),
                nm_to_mm(Nm(int(pos.y))),
            ),
            "pads",
        )
    return (
        BBoxMm(
            nm_to_mm(Nm(int(min(xs)))),
            nm_to_mm(Nm(int(min(ys)))),
            nm_to_mm(Nm(int(max(xs)))),
            nm_to_mm(Nm(int(max(ys)))),
        ),
        "pads",
    )


# --- Protocolo del cliente (para inyección en tests) --------------------------


class KiCadClientLike(Protocol):
    """Subset del API de ``kipy.KiCad`` que consume el bridge.

    Permite reemplazar el cliente real por un fake en tests unit sin
    montar ni ``pynng`` ni un socket real.
    """

    def get_version(self) -> Any: ...

    def get_board(self) -> Any: ...

    def get_open_documents(self, doc_type: Any) -> Any: ...


class _ClientFactory(Protocol):
    """Fábrica de clientes IPC — inyectable por tests."""

    def __call__(
        self, socket_path: str | None, timeout_ms: int, kicad_token: str | None
    ) -> KiCadClientLike: ...


def _socket_file_missing(socket_uri: str | None) -> bool:
    """``True`` si ``socket_uri`` es un ``ipc://`` con path filesystem inexistente.

    El check habilita el **fast-fail** (sesión 04): sin este, un ``KiCad(...)``
    con KiCad cerrado espera 2 s de timeout en cada llamada. Para esquemas no
    filesystem (``tcp://``, etc.) devuelve ``False`` — que resuelva el factory.
    """
    if not socket_uri or not socket_uri.startswith("ipc://"):
        return False
    fs_path = socket_uri[len("ipc://") :]
    if not fs_path:
        return False
    return not Path(fs_path).exists()


def _socket_uri(path: Path) -> str:
    """Envuelve un path filesystem como URI ``ipc://<path>`` (esquema de kipy)."""
    return f"ipc://{path}"


def _default_client_factory(
    socket_path: str | None, timeout_ms: int, kicad_token: str | None
) -> KiCadClientLike:
    """Fábrica real: instancia ``kipy.KiCad``.

    Import perezoso: no se resuelve ``kipy`` hasta que un llamador lo
    necesita (mantiene el server arrancable si el paquete falla al
    importar por razones ambientales).

    **Fast-fail (sesión 04)**: si el socket es un ``ipc://<path>`` y ese
    ``<path>`` no existe, se levanta ``KICAD_NOT_RUNNING`` inmediatamente
    en vez de esperar los 2 s del timeout IPC. Reduce la latencia de
    ``health`` con KiCad cerrado de 2 s a milisegundos.
    """
    if _socket_file_missing(socket_path):
        raise KicadMcpError(
            code=ErrorCode.KICAD_NOT_RUNNING,
            message="No se pudo conectar al socket IPC de KiCad.",
            hint=(
                "Abrí KiCad y habilitá el API server en Preferences → Plugins → Enable API server."
            ),
        )

    from kipy import KiCad
    from kipy.errors import ConnectionError as _KConn

    try:
        return KiCad(
            socket_path=socket_path,
            timeout_ms=timeout_ms,
            kicad_token=kicad_token,
        )
    except _KConn as exc:
        raise KicadMcpError(
            code=ErrorCode.KICAD_NOT_RUNNING,
            message="No se pudo conectar al socket IPC de KiCad.",
            hint=(
                "Abrí KiCad y habilitá el API server en Preferences → Plugins → Enable API server."
            ),
        ) from exc


# --- Clasificación de fallos IPC (supervisión, sesión 04 T3) ------------------

# Constantes ``ApiStatusCode`` del proto de kipy (envelope_pb2.pyi:70-77).
# Se copian como int para preservar el contrato perezoso del bridge (nada de
# kipy importado a nivel de módulo, sesión 04). Son estables por proto y el
# atributo ``ApiError.code`` se compara por igualdad de int (kipy
# ``client.py:89-91`` lo asigna desde ``reply.status.status``).
_AS_UNHANDLED = 5
_AS_BUSY = 7


def _map_ipc_failure(op_name: str, exc: BaseException) -> KicadMcpError:
    """Traduce excepciones que atraviesan una operación IPC a errores del catálogo.

    Regla:
    - ``TimeoutError`` (builtin, socket, kipy) → ``KICAD_TIMEOUT``.
    - ``ConnectionError`` (builtin) o ``kipy.errors.ConnectionError`` →
      ``KICAD_NOT_RUNNING``.
    - ``kipy.errors.ApiError`` con ``code == AS_BUSY`` (7) → ``KICAD_CLI_FAILED``
      con hint fijo accionable y ``data.ipc_status = "busy"`` (D-07.2). Estado
      protocolar de KiCad (envelope_pb2.pyi:74-75): la UI está ocupada
      procesando otro trabajo (refill zones, DRC realtime, router).
    - ``kipy.errors.ApiError`` con ``code == AS_UNHANDLED`` (5) →
      ``KICAD_CLI_FAILED`` con hint apuntando a abrir el editor requerido y
      ``data.ipc_status = "unhandled"`` (D-07.2). Es el error que emite
      KiCad cuando el request no tiene handler para el estado actual (p. ej.
      pedir el board sin PCB Editor abierto — ver ``kipy/kicad.py:225-230``).
    - Cualquier otra excepción (incluyendo ``ApiError`` con code no
      distinguido) → ``KICAD_CLI_FAILED`` con el detalle sanitizado en el
      hint.

    Se identifica ``kipy.errors.ConnectionError`` y ``kipy.errors.ApiError``
    por ``__qualname__`` **más** ``__module__.startswith("kipy")``, para no
    forzar el import de ``kipy`` en un ciclo perezoso y a la vez no confundir
    homónimos definidos por otra librería que corra dentro del bloque
    supervisado (sesión 05 T1).
    """
    if isinstance(exc, TimeoutError):
        return KicadMcpError(
            code=ErrorCode.KICAD_TIMEOUT,
            message=f"IPC excedió el timeout durante {op_name}.",
            hint="Reintentar o reducir el alcance de la operación.",
        )
    exc_type = type(exc)
    exc_module = exc_type.__module__ or ""
    is_from_kipy = exc_module.startswith("kipy")
    is_kipy_conn_error = exc_type.__qualname__ == "ConnectionError" and is_from_kipy
    if isinstance(exc, ConnectionError) or is_kipy_conn_error:
        return KicadMcpError(
            code=ErrorCode.KICAD_NOT_RUNNING,
            message="Conexión IPC con KiCad perdida durante la operación.",
            hint="Abrí KiCad y habilitá el API server; el próximo request reconectará.",
        )
    # ApiError con ``code`` reconocido: F3 intacta, el código sigue siendo
    # ``KICAD_CLI_FAILED``; sólo cambian el hint (accionable, fijo) y el
    # ``data.ipc_status`` (canal estructurado, documentado en el catálogo).
    if is_from_kipy and exc_type.__qualname__ == "ApiError":
        api_code = getattr(exc, "code", None)
        # ``ApiStatusCode`` en el proto es un int-enum; la igualdad por int
        # cubre tanto el enum como cualquier alias plano.
        if isinstance(api_code, int) and not isinstance(api_code, bool):
            if api_code == _AS_BUSY:
                return KicadMcpError(
                    code=ErrorCode.KICAD_CLI_FAILED,
                    message=f"KiCad está ocupado durante {op_name}.",
                    hint=(
                        "KiCad está ocupado con una operación en curso; reintentá en unos segundos."
                    ),
                    data={"ipc_status": "busy"},
                )
            if api_code == _AS_UNHANDLED:
                return KicadMcpError(
                    code=ErrorCode.KICAD_CLI_FAILED,
                    message=f"KiCad no puede manejar {op_name} en el estado actual.",
                    hint="El editor requerido no está abierto en KiCad (abrí el PCB Editor).",
                    data={"ipc_status": "unhandled"},
                )
    return KicadMcpError(
        code=ErrorCode.KICAD_CLI_FAILED,
        message=f"Fallo IPC en {op_name}.",
        hint=(str(exc)[:200] or "sin detalle disponible"),
    )


def _is_busy(exc: KicadMcpError) -> bool:
    """``True`` si el envelope trae ``data.ipc_status == "busy"`` (D-07.2)."""
    return (
        exc.code is ErrorCode.KICAD_CLI_FAILED
        and exc.data is not None
        and exc.data.get("ipc_status") == "busy"
    )


def _is_kipy_not_found_error(exc: BaseException) -> bool:
    """``True`` si ``exc`` es la ``ApiError`` que kipy lanza por KIID(s) inexistentes.

    Bug descubierto en sesión 16b (``docs/sesiones/16b-reporte.md``): el
    contrato asumido por los 4 consumidores de ``get_items_by_id`` (lista
    vacía si el id no existe) no coincide con kipy, que lanza
    ``ApiError("... none of the requested IDs were found or valid")`` en vez
    de devolver ``[]``. Esta ``ApiError`` no trae un ``code`` de status
    reconocido (no es AS_BUSY ni AS_UNHANDLED, ver ``_map_ipc_failure``) — la
    única señal disponible es el mensaje, así que se distingue por substring
    además de la detección estructural (qualname + módulo) ya usada arriba.
    """
    exc_type = type(exc)
    is_from_kipy = (exc_type.__module__ or "").startswith("kipy")
    if not (is_from_kipy and exc_type.__qualname__ == "ApiError"):
        return False
    return "were found or valid" in str(exc)


def _get_items_by_id_or_empty(raw_board: Any, kiids: list[Any]) -> list[Any]:
    """``raw_board.get_items_by_id(kiids)`` tolerante a KIID(s) inexistentes.

    Envuelve la llamada para los 4 consumidores (``verify_footprint_by_kiid``,
    ``get_copper_by_kiid``, ``remove_by_kiid``, ``move_footprint``) que ya
    asumían — y siguen asumiendo, sin cambios — el contrato "lista vacía en
    not-found". Sólo absorbe la ``ApiError`` puntual de
    ``_is_kipy_not_found_error``; cualquier otro fallo (busy, unhandled,
    desconexión, etc.) se re-lanza intacto para que ``_supervise``/
    ``_run_supervised_read`` lo mapeen como siempre.
    """
    try:
        return list(raw_board.get_items_by_id(kiids))
    except Exception as exc:
        if _is_kipy_not_found_error(exc):
            return []
        raise


def _verify_created_net_or_revert(
    raw_board: Any,
    kiid_protos: list[Any],
    created_item: Any,
    requested_net: str,
    at_mm: list[float],
) -> None:
    """Releé el net real de un ítem de cobre recién creado y revierte si KiCad
    lo reasignó (sesión 19d, ``NET_ASSIGNMENT_MISMATCH``).

    Causa raíz confirmada en vivo (19c Bloque 1 para ``add_via``, 19d.0 para
    ``add_track``): KiCad reasigna un track/via al net del cobre físico bajo
    su geometría al crearlo, sin relación con el net pedido por el caller —
    el objeto ``created_item`` en memoria sigue mostrando el net pedido, así
    que la verificación exige una relectura fresca vía ``get_items_by_id``.

    No toma ``self._lock`` (no es un método de instancia): se invoca desde
    dentro del bloque ``with self._lock`` ya adquirido por ``add_via``/
    ``add_track`` — ``self._lock`` es un ``threading.Lock`` NO reentrante,
    así que releer con ``get_copper_by_kiid`` (que sí toma el lock) causaría
    deadlock. Por eso esta función es kipy-agnóstica: recibe ``raw_board``
    y los ``KIID`` proto ya construidos, no importa ``kipy`` — testeable con
    un ``raw_board`` fake en unit tests (kipy no es importable offline).

    Si el ítem ya no está (borrado concurrente), no hay nada que verificar.
    Si el net coincide (o no se pudo leer un net con nombre), no hace nada.
    Si difiere, borra el ítem recién creado (``remove_items``) y lanza
    ``NET_ASSIGNMENT_MISMATCH`` con ``data.requested_net``/``data.actual_net``/
    ``data.at``.
    """
    reread = _get_items_by_id_or_empty(raw_board, kiid_protos)
    if not reread:
        return
    net = reread[0].net
    actual_net = str(net.name) if net is not None and net.name else ""
    if actual_net and actual_net != requested_net:
        raw_board.remove_items(created_item)
        raise KicadMcpError(
            code=ErrorCode.NET_ASSIGNMENT_MISMATCH,
            message=(
                f"KiCad asignó el net {actual_net!r} en vez del {requested_net!r} "
                "pedido: el punto/trazado pisa cobre de otro net."
            ),
            hint=(
                "el punto solicitado pisa cobre de otro net; verificá "
                "coordenadas con get_tracks(bbox=...) o borrá cobre ajeno "
                "primero"
            ),
            data={
                "requested_net": requested_net,
                "actual_net": actual_net,
                "at": at_mm,
            },
        )


# --- Retry acotado para lecturas idempotentes (D-07.1) ------------------------

# Whitelist EXPLÍCITA de operaciones a las que se les puede aplicar retry ante
# ``AS_BUSY``. Todas son solo-lectura y no tienen efectos colaterales en KiCad.
# Añadir una entrada requiere leer D-07.1 y verificar que reintentar sea
# semánticamente seguro (el request puede haber sido aceptado y la mutación
# duplicaría). Las mutaciones NO viajan por este camino: usan ``_supervise``
# directamente, así que este set NO es un flag encendible por accidente.
_IDEMPOTENT_OPS: frozenset[str] = frozenset(
    {
        "get_version",
        "get_open_board",
        "get_open_documents_pcb",  # sesión 07 T3 — probe del health fino
        "list_footprint_refs",
        "list_net_names",
        "board_bbox_mm",
        "snapshot_footprints",
        "get_footprint_position",
        # Sesión 08 D-08.1/D-08.3: lectura compuesta que colapsa 3 iteraciones
        # O(board) en una. Se aplica antes de cualquier escritura, por lo que
        # es semánticamente segura de reintentar ante AS_BUSY.
        "read_board_context",
        # D-08.2: verificación puntual por KIID tras la mutación. Filtra en
        # KiCad (get_items_by_id), no itera el board del lado del bridge.
        # Es una lectura pura del estado post-mutación — retry-elegible.
        "verify_footprint_by_kiid",
        # Sesión 11 (D-11.2/D-11.3/D-11.4): lecturas puras del board vivo.
        # ``get_component_detail`` alimenta el detalle y la resolución
        # REF.PAD; ``list_net_copper`` alimenta el matching geométrico del
        # borrado dirigido (get_items_by_net, filtrado del lado de KiCad).
        "get_component_detail",
        "list_net_copper",
        # F-03: bbox del board + contorno Edge.Cuts para la cabecera TOON pcb.
        "board_outline",
        # Sesión 16 (D-16.1/D-16.2/D-16.4): lecturas puras para ``get_tracks``,
        # el borrado dirigido por id y la validación de colisiones de
        # ``add_track``. Ninguna tiene efecto colateral en KiCad.
        "list_all_copper",
        "get_copper_by_kiid",
        "list_all_pads",
        # P4 (sesión 19): lecturas puras de zonas para ``get_zones`` y la
        # resolución por KIID de ``delete_zone``/``fill_zones(zone_id=)`` —
        # mismo criterio que ``list_all_copper``/``get_copper_by_kiid``.
        "list_zones",
        "get_zone_by_kiid",
    }
)

# Backoff exponencial acotado (< 1 s total adicional). D-07.1: máximo 2
# reintentos, para no propagar en cascada un busy que persiste (KiCad
# probablemente está genuinamente ocupado con router/DRC/refill y no
# terminará en el próximo cuarto de segundo).
_BUSY_RETRY_BACKOFFS_MS: tuple[int, ...] = (250, 500)


# --- Bridge -------------------------------------------------------------------


_DEFAULT_TIMEOUT_MS = 2000
_DEFAULT_SOCKET_LINUX = "ipc:///tmp/kicad/api.sock"

# --- Descubrimiento del socket en cascada (sesión 19e, F-19b-09) --------------
#
# KiCad 10.0.4 crea el socket como ``/tmp/kicad/api-<PID>.sock`` (sufijo de
# PID), no el path canónico sin sufijo. Constantes separadas (en vez de
# derivarlas de ``_DEFAULT_SOCKET_LINUX``) para que los tests las
# ``monkeypatch.setattr`` y redirijan el descubrimiento a un ``tmp_path``
# sin tocar el ``/tmp/kicad`` real del dev.
_KICAD_SOCKET_DIR = Path("/tmp/kicad")
_LEGACY_SOCKET_NAME = "api.sock"
_PID_SOCKET_GLOB = "api-*.sock"


def _resolve_kicad_socket(explicit_arg: str | None = None) -> str | None:
    """Resuelve el socket IPC de KiCad en Linux por cascada (F-19b-09).

    Orden: ``KICAD_API_SOCKET`` (si el path existe) → ``explicit_arg`` (si
    el path existe) → path legacy ``/tmp/kicad/api.sock`` (si existe) →
    glob per-PID ``/tmp/kicad/api-<PID>.sock`` (1 match, o el más reciente
    por ``mtime`` si hay varios — con warning) → último recurso: el
    override explícito (env o arg) aunque su path no exista, para que el
    fast-fail de ``_default_client_factory`` siga funcionando → ``None`` si
    no hay ningún candidato.

    Función pura salvo el log warning en el caso ambiguo (múltiples
    sockets per-PID). En plataformas no-Linux el caller mantiene el path
    canónico — esta cascada es específica de Linux (RNF6).
    """
    env = os.environ.get("KICAD_API_SOCKET")
    if env and not _socket_file_missing(env):
        return env
    if explicit_arg and not _socket_file_missing(explicit_arg):
        return explicit_arg
    legacy = _socket_uri(_KICAD_SOCKET_DIR / _LEGACY_SOCKET_NAME)
    if not _socket_file_missing(legacy):
        return legacy
    matches = sorted(
        _KICAD_SOCKET_DIR.glob(_PID_SOCKET_GLOB),
        key=lambda p: p.stat().st_mtime,
    )
    if matches:
        if len(matches) > 1:
            log_socket_glob_ambiguous(chosen=str(matches[-1]), count=len(matches))
        return _socket_uri(matches[-1])  # más reciente por mtime
    return env or explicit_arg or None  # último recurso: fast-fail en el factory


class IpcBridge:
    """Cliente IPC serializado con detección de reinicio de KiCad.

    Estado interno mínimo: el ``KiCadClientLike`` conectado y el último
    ``KICAD_API_TOKEN`` visto. No mantiene caches de dominio (eso lo
    hace el Snapshot Store).
    """

    def __init__(
        self,
        *,
        socket_path: str | None = None,
        client_factory: _ClientFactory = _default_client_factory,
        timeout_ms: int = _DEFAULT_TIMEOUT_MS,
    ) -> None:
        # El arg explícito se conserva para re-resolver en cada chequeo
        # (F-19b-09 / R11): KiCad puede reiniciarse a mitad de la vida del
        # server con un socket distinto (PID nuevo, o incluso sin sufijo de
        # PID — observado en vivo, sesión 19e), y una resolución congelada
        # en el constructor dejaría a ``socket_present()``/``_ensure_client``
        # apuntando a un socket muerto indefinidamente.
        self._socket_path_arg = socket_path
        self._socket_path: str | None = _resolve_kicad_socket(socket_path)
        self._timeout_ms = timeout_ms
        self._client_factory = client_factory
        self._client: KiCadClientLike | None = None
        # Token de la instancia — se congela al primer contacto y se
        # compara contra el env de cada llamada para detectar reinicios.
        self._instance_token: str | None = None
        # Cola de profundidad 1 sobre TODA llamada IPC (thread-safe).
        self._lock = threading.Lock()

    # -- ciclo de vida --------------------------------------------------------

    def _current_env_token(self) -> str | None:
        raw = os.environ.get("KICAD_API_TOKEN")
        return raw or None

    def socket_present(self) -> bool:
        """``True`` si el fichero del socket IPC existe (fast-fail, sesión 04).

        Cheap check para el nivel más bajo de ``health`` (sesión 07 D-07.3):
        KiCad crea el socket al arrancar y lo borra al salir, así que su
        presencia distingue "KiCad no está corriendo" (missing) de "KiCad
        corriendo pero el server IPC puede estar ocupado o cerrado". No
        toca red ni el hilo UI.

        Re-resuelve la cascada en cada llamada (sesión 19e, F-19b-09/R11):
        si KiCad se reinició con un socket distinto desde la última vez,
        este check debe reflejarlo sin requerir reconstruir el bridge.

        ``None`` (nada descubrible: sin env, sin arg, sin socket en
        ``/tmp/kicad``) es explícitamente "ausente" — ``_socket_file_missing``
        devuelve ``False`` para ``None``/esquemas no ``ipc://`` porque ese
        caso lo delega al factory (deja pasar), pero aquí no hay factory al
        que delegar: sin candidato, no hay socket.
        """
        self._socket_path = _resolve_kicad_socket(self._socket_path_arg)
        if self._socket_path is None:
            return False
        return not _socket_file_missing(self._socket_path)

    def _ensure_client(self) -> KiCadClientLike:
        resolved = _resolve_kicad_socket(self._socket_path_arg)
        if resolved != self._socket_path:
            # El socket cambió (KiCad se reinició) desde la última conexión:
            # el cliente viejo apunta a un path muerto, descartarlo.
            self._client = None
            self._socket_path = resolved
        if self._client is None:
            token = self._current_env_token()
            self._client = self._client_factory(self._socket_path, self._timeout_ms, token)
            self._instance_token = token
        return self._client

    @contextmanager
    def _supervise(self, op_name: str) -> Iterator[None]:
        """Supervisa un bloque de operación IPC (sesión 04 T3).

        Si el bloque levanta una excepción no tipada (``ApiError``,
        ``ConnectionError``, ``TimeoutError``, o cualquier otra fuera de
        ``KicadMcpError``), mapea a error tipado del catálogo y —salvo por
        ``AS_BUSY`` (D-07.1)— invalida ``self._client`` para forzar reconexión
        en el próximo request. ``_supervise`` **no** hace retry: eso vive en
        ``_run_supervised_read`` para lecturas idempotentes en whitelist. Las
        mutaciones se supervisan directamente y jamás se reintentan.

        AS_BUSY es un rechazo transitorio de KiCad (la UI está ocupada);
        la conexión IPC sigue viva. Preservar el cliente evita que el
        wrapper de retry pague una reconexión al socket a cambio de nada.
        """
        try:
            yield
        except KicadMcpError:
            raise
        except BaseException as exc:
            mapped = _map_ipc_failure(op_name, exc)
            if not _is_busy(mapped):
                # Cliente sospechoso → descartar para que el próximo request
                # reconstruya la conexión. Busy no afecta la conexión.
                self._client = None
            raise mapped from exc

    def _run_supervised_read(self, op_name: str, do: Callable[[], _T]) -> _T:
        """Ejecuta ``do()`` dentro de ``_supervise(op_name)`` con retry acotado
        para ``AS_BUSY`` (D-07.1).

        ``op_name`` DEBE estar en ``_IDEMPOTENT_OPS`` — el ``assert`` es la
        **frontera estructural** entre lecturas y mutaciones: no existe otra
        vía para aplicar retry, así que ninguna mutación puede reintentarse
        por accidente ni por un flag encendible. Añadir un op a la whitelist
        exige leer D-07.1 y auditar el determinismo del request.

        Retorna el resultado de ``do()`` a la primera respuesta OK. Backoff
        exponencial 250 → 500 ms entre intentos (< 1 s total adicional). Si
        el busy persiste, propaga el ``KICAD_CLI_FAILED`` (``data.ipc_status
        = "busy"``) del último intento. Cualquier otro fallo del catálogo se
        propaga sin retry en el primer intento.
        """
        if op_name not in _IDEMPOTENT_OPS:
            raise AssertionError(f"{op_name!r} no está en la whitelist idempotente (D-07.1)")
        attempt_i = 0
        max_retries = len(_BUSY_RETRY_BACKOFFS_MS)
        while True:
            try:
                with self._supervise(op_name):
                    return do()
            except KicadMcpError as exc:
                if attempt_i >= max_retries or not _is_busy(exc):
                    raise
                backoff_ms = _BUSY_RETRY_BACKOFFS_MS[attempt_i]
                attempt_i += 1
                log_ipc_retry(op_name=op_name, attempt=attempt_i, backoff_ms=backoff_ms)
                time.sleep(backoff_ms / 1000.0)

    def _detect_restart(self) -> None:
        """Compara el token actual con el guardado; lanza ``KICAD_RESTARTED`` si cambió.

        El caso "ambos None" no es reinicio: puede que el server no reciba
        el env de KiCad (por ejemplo, arrancado fuera de un plugin) y aún
        así el socket sea válido.
        """
        current = self._current_env_token()
        if self._instance_token is None:
            self._instance_token = current
            return
        if current is None:
            return  # falta de env no cuenta como reinicio
        if current != self._instance_token:
            # Descarta el cliente: el próximo request reconectará.
            self._client = None
            self._instance_token = current
            raise KicadMcpError(
                code=ErrorCode.KICAD_RESTARTED,
                message="KiCad se reinició durante la sesión (token de instancia distinto).",
                hint="Pedí get_world_context: los snapshots previos quedaron inválidos.",
            )

    # -- operaciones ----------------------------------------------------------

    def get_version(self) -> IpcVersion:
        """Versión de KiCad reportada por IPC. Puede levantar ``KICAD_NOT_RUNNING``."""
        with self._lock:
            self._detect_restart()
            client = self._ensure_client()

            def _do() -> IpcVersion:
                proto = client.get_version()
                return IpcVersion(
                    full=str(getattr(proto, "full_version", "")) or "unknown",
                    major=int(getattr(proto, "major", 0)),
                    minor=int(getattr(proto, "minor", 0)),
                    patch=int(getattr(proto, "patch", 0)),
                )

            return self._run_supervised_read("get_version", _do)

    def get_open_board(self) -> BoardHandle | None:
        """Devuelve un handle al ``Board`` abierto, o ``None`` si no hay board.

        Nunca expone tipos de ``kipy`` fuera del bridge: se envuelve en
        ``BoardHandle`` (frontera de proceso, regla #5).
        """
        with self._lock:
            self._detect_restart()
            client = self._ensure_client()

            def _do() -> BoardHandle | None:
                raw = client.get_board()
                return BoardHandle(_raw=raw) if raw is not None else None

            return self._run_supervised_read("get_open_board", _do)

    def has_open_pcb(self) -> bool:
        """``True`` si KiCad tiene un PCB Editor abierto (sesión 07 T3).

        Consulta ``get_open_documents(DOCTYPE_PCB)`` en lugar de intentar
        ``get_board()`` para no traer el proto del board completo. Distingue:

        - Lista no-vacía → PCB Editor abierto (``True``).
        - Excepción ``AS_UNHANDLED`` (mapeada por ``_map_ipc_failure`` a
          ``KICAD_CLI_FAILED`` con ``data.ipc_status="unhandled"``) → sólo
          project manager sin PCB Editor abierto (``False``).

        Cualquier otro error IPC (busy tras retry, timeout, socket muerto)
        se propaga: ``health`` decide qué reportar en cada nivel del
        payload sin engañar al agente con un ``False`` que en realidad es
        "no lo sé".
        """
        from kipy.proto.common.types import DocumentType

        with self._lock:
            self._detect_restart()
            client = self._ensure_client()

            def _do() -> bool:
                docs = client.get_open_documents(DocumentType.DOCTYPE_PCB)
                return len(docs) > 0

            try:
                return self._run_supervised_read("get_open_documents_pcb", _do)
            except KicadMcpError as exc:
                if (
                    exc.code is ErrorCode.KICAD_CLI_FAILED
                    and exc.data is not None
                    and (exc.data.get("ipc_status") == "unhandled")
                ):
                    return False
                raise

    def get_open_board_path(self, board: BoardHandle) -> Path | None:
        """Ruta en disco del board abierto, o ``None`` si no es determinable.

        Lee ``document.project.path`` + ``document.board_filename`` del proto
        que kipy cachea en el ``Board`` (atributo local — sin IPC). D-14.3 lo
        usa para decidir el ``save_board`` implícito de ``route_board`` de forma
        SEGURA: sólo baja live→disco si el board abierto ES el que se va a
        rutear; si difiere (o no se puede determinar), no toca el board vivo.
        """
        doc = getattr(board.raw, "document", None)
        if doc is None:
            return None
        filename = str(getattr(doc, "board_filename", "") or "")
        project = getattr(doc, "project", None)
        project_path = str(getattr(project, "path", "") or "") if project is not None else ""
        if not filename or not project_path:
            return None
        return Path(project_path) / filename

    # -- consultas del board (para validación previa a mutaciones) ------------

    def list_footprint_refs(self, board: BoardHandle) -> list[str]:
        """Refs (``U1``, ``R42``…) de todos los footprints del board."""
        with self._lock:
            self._detect_restart()

            def _do() -> list[str]:
                return [str(fp.reference_field.text.value) for fp in board.raw.get_footprints()]

            return self._run_supervised_read("list_footprint_refs", _do)

    def list_net_names(self, board: BoardHandle) -> list[str]:
        """Nombres de los nets del board."""
        with self._lock:
            self._detect_restart()

            def _do() -> list[str]:
                return [str(n.name) for n in board.raw.get_nets()]

            return self._run_supervised_read("list_net_names", _do)

    def board_bbox_mm(self, board: BoardHandle) -> BBoxMm:
        """Bounding box del board en milímetros.

        Preferencia: usar la superficie declarada del board (Edge.Cuts).
        Fallback: unión de bounding boxes de todos los footprints. En el
        MVP nos apoyamos en un bbox amplio: el objetivo del check es
        rechazar coordenadas absurdas, no ser pixel-perfect.
        """
        with self._lock:
            self._detect_restart()

            def _do() -> BBoxMm:
                items = list(board.raw.get_footprints())
                if not items:
                    # Board vacío: no hay bbox útil; devolvemos un rango grande
                    # que no rechaza nada razonable (1e6 mm es el borde
                    # razonable de KiCad).
                    return BBoxMm(Mm(-1e6), Mm(-1e6), Mm(1e6), Mm(1e6))
                xs: list[float] = []
                ys: list[float] = []
                for fp in items:
                    pos = fp.position
                    xs.append(nm_to_mm(Nm(int(pos.x))))
                    ys.append(nm_to_mm(Nm(int(pos.y))))
                # Margen de 100 mm alrededor del enjambre de footprints.
                margin = 100.0
                return BBoxMm(
                    Mm(min(xs) - margin),
                    Mm(min(ys) - margin),
                    Mm(max(xs) + margin),
                    Mm(max(ys) + margin),
                )

            return self._run_supervised_read("board_bbox_mm", _do)

    def snapshot_footprints(self, board: BoardHandle) -> tuple[FootprintData, ...]:
        """Datos primitivos de todos los footprints — para el snapshot post-mutación.

        Sesión 05 T5. Se ejecuta bajo el lock del bridge; devuelve dataclasses
        propias (nunca tipos de kipy) para que ``state_builder.build_state_from_board``
        materialice un ``NormalizedState`` sin volver a IPC.

        Sesión 08: sigue disponible como fallback aislado; el pre-work de los
        tools de mutación viaja por ``read_board_context`` (una pasada, con
        bbox + refs + KIIDs). Aquí NO se captura el KIID para no cambiar el
        contrato de retorno de la lectura aislada — quien necesite KIID pide
        ``read_board_context``.
        """
        with self._lock:
            self._detect_restart()

            def _do() -> tuple[FootprintData, ...]:
                items: list[FootprintData] = []
                for fp in board.raw.get_footprints():
                    items.append(_footprint_to_data(fp, capture_kiid=False))
                return tuple(items)

            return self._run_supervised_read("snapshot_footprints", _do)

    def read_board_context(self, board: BoardHandle) -> BoardContext:
        """Lectura compuesta del board — UNA sola pasada por ``get_footprints()``.

        Sesión 08 D-08.1. Reemplaza el trío
        ``list_footprint_refs`` + ``board_bbox_mm`` + ``snapshot_footprints``
        que los tools de mutación disparaban en secuencia (~9 s en el board de
        202 refs, sesión 07 §T5). En una sola iteración construye:

        - ``refs``: refs para la validación ``COMPONENT_NOT_FOUND`` + similares.
        - ``bbox``: bounding box con margen (misma semántica de
          ``board_bbox_mm`` — ver docstring de ese método).
        - ``footprints``: snapshot completo con ``kiid`` capturado (habilita
          ``bridge.move_footprint(..., kiid=...)`` y la verificación puntual
          por KIID de D-08.2).

        Retry-elegible (D-08.3): es lectura idempotente y corre siempre antes
        de cualquier escritura, por construcción — es imposible que reintentar
        duplique una mutación.
        """
        with self._lock:
            self._detect_restart()

            def _do() -> BoardContext:
                refs: list[str] = []
                xs: list[float] = []
                ys: list[float] = []
                fps_data: list[FootprintData] = []
                for fp in board.raw.get_footprints():
                    data = _footprint_to_data(fp, capture_kiid=True)
                    refs.append(data.ref)
                    xs.append(float(data.x_mm))
                    ys.append(float(data.y_mm))
                    fps_data.append(data)
                if not fps_data:
                    bbox = BBoxMm(Mm(-1e6), Mm(-1e6), Mm(1e6), Mm(1e6))
                else:
                    margin = 100.0
                    bbox = BBoxMm(
                        Mm(min(xs) - margin),
                        Mm(min(ys) - margin),
                        Mm(max(xs) + margin),
                        Mm(max(ys) + margin),
                    )
                return BoardContext(
                    refs=tuple(refs),
                    bbox=bbox,
                    footprints=tuple(fps_data),
                )

            return self._run_supervised_read("read_board_context", _do)

    def verify_footprint_by_kiid(self, board: BoardHandle, kiid: str) -> FootprintData | None:
        """Re-lee un único footprint por KIID (D-08.2, verificación puntual).

        Usa ``get_items_by_id`` de kipy (``kipy/board.py:384-399``): filtra en
        el lado de KiCad, sin iterar el board del lado del bridge. Costo de
        red equivalente a una request; O(1) frente al ~3 s de una pasada
        completa. Habilita comparar la posición derivada localmente contra
        la que KiCad realmente aplicó (con redondeos y clamps propios).

        Devuelve ``None`` si el KIID no está en el board (edge case: alguien
        eliminó el ítem por fuera entre la mutación y la verificación).
        """
        from kipy.proto.common.types.base_types_pb2 import KIID

        with self._lock:
            self._detect_restart()

            def _do() -> FootprintData | None:
                kiid_proto = KIID()
                kiid_proto.value = kiid
                items = _get_items_by_id_or_empty(board.raw, [kiid_proto])
                if not items:
                    return None
                return _footprint_to_data(items[0], capture_kiid=True)

            return self._run_supervised_read("verify_footprint_by_kiid", _do)

    def get_footprint_position(self, board: BoardHandle, ref: str) -> tuple[Mm, Mm]:
        """Posición ``(x_mm, y_mm)`` del footprint ``ref`` según el board vivo.

        Interno del bridge (sesión 04 T6): lo consume el test integration_gui
        para verificar que ``move_footprint`` persistió las coordenadas.
        No se expone como tool MCP; el catálogo permanece igual.

        Levanta ``COMPONENT_NOT_FOUND`` si el ref no está.
        """
        with self._lock:
            self._detect_restart()

            def _do() -> tuple[Mm, Mm]:
                for fp in board.raw.get_footprints():
                    if str(fp.reference_field.text.value) == ref:
                        pos = fp.position
                        return (
                            nm_to_mm(Nm(int(pos.x))),
                            nm_to_mm(Nm(int(pos.y))),
                        )
                raise KicadMcpError(
                    code=ErrorCode.COMPONENT_NOT_FOUND,
                    message=f"Footprint {ref} no está en el board.",
                    hint="Verificá que el ref exista y que el board correcto esté abierto.",
                )

            return self._run_supervised_read("get_footprint_position", _do)

    def get_component_detail(self, board: BoardHandle, ref: str) -> ComponentDetail:
        """Detalle geométrico del footprint ``ref`` del board vivo (D-11.3).

        Una pasada ``get_footprints()`` para localizar el ref; de él se leen
        origen, rotación, bbox (courtyard o pads) y la lista de pads con
        posición ABSOLUTA (ya rotada por kipy), tamaño, capa y net. Levanta
        ``COMPONENT_NOT_FOUND`` si el ref no está en el board.
        """
        with self._lock:
            self._detect_restart()

            def _do() -> ComponentDetail:
                target: Any = None
                for fp in board.raw.get_footprints():
                    if str(fp.reference_field.text.value) == ref:
                        target = fp
                        break
                if target is None:
                    raise KicadMcpError(
                        code=ErrorCode.COMPONENT_NOT_FOUND,
                        message=f"Footprint {ref} no está en el board.",
                        hint="Verificá el ref con get_world_context(kind='pcb').",
                    )
                pos = target.position
                bbox, source = _footprint_bbox_mm(target)
                pads = tuple(_pad_to_detail(pad) for pad in target.definition.pads)
                return ComponentDetail(
                    ref=ref,
                    value=str(target.value_field.text.value),
                    x_mm=nm_to_mm(Nm(int(pos.x))),
                    y_mm=nm_to_mm(Nm(int(pos.y))),
                    rotation_deg=float(target.orientation.degrees),
                    bbox_min_x=bbox.min_x,
                    bbox_min_y=bbox.min_y,
                    bbox_max_x=bbox.max_x,
                    bbox_max_y=bbox.max_y,
                    bbox_source=source,
                    pads=pads,
                )

            return self._run_supervised_read("get_component_detail", _do)

    def list_net_copper(self, board: BoardHandle, net: str) -> tuple[CopperItem, ...]:
        """Tracks/arcs/vias del ``net`` con KIID y geometría (D-11.2).

        Usa ``get_items_by_net`` (KiCad 10.0.1+, filtrado del lado de KiCad):
        ~10x más barato que iterar los miles de tracks del board. Devuelve
        primitivos ``CopperItem``; el matching geométrico y la decisión de
        ambigüedad viven en el tool (lógica pura, testeable con fakes).

        Levanta ``NET_NOT_FOUND`` si el net no existe.
        """
        from kipy.proto.common.types import KiCadObjectType as OT

        with self._lock:
            self._detect_restart()

            def _do() -> tuple[CopperItem, ...]:
                raw_board = board.raw
                net_obj = next((n for n in raw_board.get_nets() if str(n.name) == net), None)
                if net_obj is None:
                    raise KicadMcpError(
                        code=ErrorCode.NET_NOT_FOUND,
                        message=f"Net {net} no existe en el board.",
                        hint="Verificá el net con get_world_context(kind='pcb').",
                    )
                items = raw_board.get_items_by_net(
                    net_obj, [OT.KOT_PCB_TRACE, OT.KOT_PCB_ARC, OT.KOT_PCB_VIA]
                )
                return tuple(_kipy_copper_to_item(it, net) for it in items if _is_copper_item(it))

            return self._run_supervised_read("list_net_copper", _do)

    def list_all_copper(self, board: BoardHandle) -> tuple[CopperItem, ...]:
        """Todos los tracks/arcs/vias del board, sin filtrar por net (D-16.1).

        Alimenta ``get_tracks(bbox=|layer=)`` sin ``net``: una única pasada
        ``get_items`` (tipos TRACE/ARC/VIA) — mismo costo de un
        ``list_net_copper`` sin el filtro server-side por net. El ``net_name``
        de cada ítem sale de ``it.net.name`` (no lo tenemos de antemano, a
        diferencia de ``list_net_copper``).
        """
        from kipy.proto.common.types import KiCadObjectType as OT

        with self._lock:
            self._detect_restart()

            def _do() -> tuple[CopperItem, ...]:
                raw_board = board.raw
                items = raw_board.get_items(
                    types=[OT.KOT_PCB_TRACE, OT.KOT_PCB_ARC, OT.KOT_PCB_VIA]
                )
                out: list[CopperItem] = []
                for it in items:
                    if not _is_copper_item(it):
                        continue
                    net = it.net
                    net_name = str(net.name) if net is not None and net.name else ""
                    out.append(_kipy_copper_to_item(it, net_name))
                return tuple(out)

            return self._run_supervised_read("list_all_copper", _do)

    def get_copper_by_kiid(self, board: BoardHandle, kiid: str) -> CopperItem | None:
        """Resuelve un ``CopperItem`` por KIID (D-16.2, borrado dirigido por id).

        ``None`` si el KIID no existe (board mutado desde el ``get_tracks``
        que lo emitió) o si existe pero no es cobre (p. ej. apunta a un
        footprint). El llamador mapea ambos casos a ``TRACK_ID_STALE``.
        """
        from kipy.proto.common.types.base_types_pb2 import KIID as _KIID_proto

        with self._lock:
            self._detect_restart()

            def _do() -> CopperItem | None:
                raw_board = board.raw
                kiid_proto = _KIID_proto()
                kiid_proto.value = kiid
                items = _get_items_by_id_or_empty(raw_board, [kiid_proto])
                if not items or not _is_copper_item(items[0]):
                    return None
                it = items[0]
                net = it.net
                net_name = str(net.name) if net is not None and net.name else ""
                return _kipy_copper_to_item(it, net_name)

            return self._run_supervised_read("get_copper_by_kiid", _do)

    def list_all_pads(self, board: BoardHandle) -> tuple[PadGeom, ...]:
        """Geometría de todos los pads del board, para colisiones de ``add_track``
        (D-16.4). Una pasada ``Board.get_pads()`` — sin iterar footprint por
        footprint (mismo espíritu de costo que ``list_all_copper``).
        """
        with self._lock:
            self._detect_restart()

            def _do() -> tuple[PadGeom, ...]:
                raw_board = board.raw
                out: list[PadGeom] = []
                for pad in raw_board.get_pads():
                    copper = pad.padstack.copper_layers
                    if not copper:
                        continue
                    size = copper[0].size
                    net = pad.net
                    net_name = str(net.name) if net is not None and net.name else None
                    pos = pad.position
                    out.append(
                        PadGeom(
                            net_name=net_name,
                            layer=_pad_layer_str(pad),
                            x_mm=nm_to_mm(Nm(int(pos.x))),
                            y_mm=nm_to_mm(Nm(int(pos.y))),
                            w_mm=nm_to_mm(Nm(int(size.x))),
                            h_mm=nm_to_mm(Nm(int(size.y))),
                            rotation_deg=float(pad.padstack.angle.degrees),
                            corner_ratio=_pad_corner_ratio(copper[0]),
                        )
                    )
                return tuple(out)

            return self._run_supervised_read("list_all_pads", _do)

    def list_zones(self, board: BoardHandle) -> tuple[ZoneItem, ...]:
        """Todas las zonas (cobre + keepout) del board (P4, ``get_zones``).

        ``Board.get_zones()`` de kipy — verificado en vivo contra KiCad
        10.0.4 (``docs/investigacion/19-zonas-ipc.md`` §1): round-trips por
        IPC, una sola pasada, sin filtro server-side por capa/net/kind (el
        tool filtra en Python, mismo patrón que ``list_all_copper``).
        """
        with self._lock:
            self._detect_restart()

            def _do() -> tuple[ZoneItem, ...]:
                raw_board = board.raw
                return tuple(_kipy_zone_to_item(z) for z in raw_board.get_zones())

            return self._run_supervised_read("list_zones", _do)

    def get_zone_by_kiid(self, board: BoardHandle, kiid: str) -> ZoneItem | None:
        """Resuelve una ``ZoneItem`` por KIID (P4, espejo de ``get_copper_by_kiid``).

        ``None`` si el KIID no existe o si existe pero no es una zona. El
        llamador (``delete_zone``/``fill_zones``) mapea ambos casos a
        ``ZONE_ID_STALE``.
        """
        from kipy.proto.common.types.base_types_pb2 import KIID as _KIID_proto

        with self._lock:
            self._detect_restart()

            def _do() -> ZoneItem | None:
                raw_board = board.raw
                kiid_proto = _KIID_proto()
                kiid_proto.value = kiid
                items = _get_items_by_id_or_empty(raw_board, [kiid_proto])
                if not items or type(items[0]).__name__ != "Zone":
                    return None
                return _kipy_zone_to_item(items[0])

            return self._run_supervised_read("get_zone_by_kiid", _do)

    def add_zone(
        self,
        board: BoardHandle,
        *,
        net: str,
        layer: str,
        vertices_mm: tuple[tuple[float, float], ...],
        priority: int = 0,
        fill: bool = True,
    ) -> tuple[str, bool, float]:
        """Crea una zona de cobre conectada a ``net`` en ``layer`` (P4, ``add_zone``).

        Precondición: el llamador ya validó que ``net`` existe y que el
        polígono es simple con 3-20 vértices (``INVALID_ZONE_GEOMETRY`` se
        levanta ahí, no acá — mismo reparto de responsabilidades que
        ``add_track``: el tool valida con hints ricos, el bridge re-chequea
        ``net`` por las dudas de una carrera entre validación y mutación).

        Si ``fill``, llama ``Board.refill_zones()`` tras crear la zona — es
        **bloqueante con polling** (``docs/investigacion/19-zonas-ipc.md``
        §1/§3), no hay fill selectivo por zona en kipy 0.7.1: refilla TODAS
        las zonas del board (idempotente, sin efecto adverso si ya estaban
        rellenas). Devuelve ``(kiid, filled, area_mm2)``.
        """
        from kipy.board_types import Zone

        with self._lock:
            self._detect_restart()
            with self._supervise("add_zone"):
                raw_board = board.raw
                net_obj = next(
                    (n for n in raw_board.get_nets() if str(n.name) == net),
                    None,
                )
                if net_obj is None:
                    raise KicadMcpError(
                        code=ErrorCode.NET_NOT_FOUND,
                        message=f"Net {net} no está en el board (post-validación).",
                        hint="Snapshot del board cambió entre la validación y la mutación.",
                    )
                layer_value = _zone_layer_value(layer)
                zone = Zone()  # nace ZT_COPPER por default (kipy)
                zone.layers = [layer_value]  # type: ignore[list-item]
                zone.outline = _build_zone_outline(vertices_mm)
                zone.net = net_obj
                zone.priority = priority
                created = raw_board.create_items(zone)
                kiid = str(created[0].id.value) if created else ""
                if fill:
                    raw_board.refill_zones()
                area_mm2 = _polygon_area_mm2(tuple((Mm(x), Mm(y)) for x, y in vertices_mm))
                return kiid, fill, area_mm2

    def add_keepout_zone(
        self,
        board: BoardHandle,
        *,
        layer: str,
        vertices_mm: tuple[tuple[float, float], ...],
        no_tracks: bool,
        no_vias: bool,
        no_pours: bool,
        no_footprints: bool,
    ) -> tuple[str, float]:
        """Crea una zona keepout (rule area) sin net (P4, ``add_keepout_zone``).

        ``layer="all"`` resuelve a TODAS las capas de cobre habilitadas
        (``_copper_layer_values``); si no, una sola capa de cobre específica.
        Los flags ``keepout_*`` viven en ``rule_area_settings`` del proto — la
        wrapper ``Zone`` de kipy no los expone como propiedades Python
        (``docs/investigacion/19-zonas-ipc.md`` §1), así que se escriben
        directo sobre ``zone.proto.rule_area_settings`` (``Wrapper.proto``
        devuelve la misma instancia interna, sin copia — la escritura es
        efectiva antes de ``create_items``). No requiere fill (una keepout no
        tiene cobre). Devuelve ``(kiid, area_mm2)``.
        """
        from kipy.board_types import Zone
        from kipy.proto.board.board_types_pb2 import ZoneType

        with self._lock:
            self._detect_restart()
            with self._supervise("add_keepout_zone"):
                raw_board = board.raw
                layer_values = (
                    _copper_layer_values(raw_board)
                    if layer == "all"
                    else [_zone_layer_value(layer)]
                )
                zone = Zone()
                zone.type = ZoneType.ZT_RULE_AREA
                zone.layers = layer_values  # type: ignore[assignment]
                zone.outline = _build_zone_outline(vertices_mm)
                zone.proto.rule_area_settings.keepout_tracks = no_tracks
                zone.proto.rule_area_settings.keepout_vias = no_vias
                zone.proto.rule_area_settings.keepout_copper = no_pours
                zone.proto.rule_area_settings.keepout_footprints = no_footprints
                created = raw_board.create_items(zone)
                kiid = str(created[0].id.value) if created else ""
                area_mm2 = _polygon_area_mm2(tuple((Mm(x), Mm(y)) for x, y in vertices_mm))
                return kiid, area_mm2

    def refill_zones(self, board: BoardHandle) -> int:
        """Refill de TODAS las zonas de cobre del board (P4, ``fill_zones``).

        kipy 0.7.1 no expone fill selectivo por zona (``Board.refill_zones()``
        no toma una lista de KIIDs — verificado en la investigación P4.0):
        esta llamada SIEMPRE recalcula el fill de todas las zonas de cobre,
        sin importar si el tool pidió un ``zone_id`` específico. Bloqueante
        con polling (hasta 30s default de kipy). Idempotente. Devuelve la
        cantidad de zonas de COBRE del board (las keepout no tienen fill).
        """
        from kipy.proto.board.board_types_pb2 import ZoneType

        with self._lock:
            self._detect_restart()
            with self._supervise("refill_zones"):
                raw_board = board.raw
                raw_board.refill_zones()
                zones = raw_board.get_zones()
                return sum(1 for z in zones if z.type != ZoneType.ZT_RULE_AREA)

    def board_outline(self, board: BoardHandle) -> tuple[BBoxMm, str]:
        """Bbox del board y estado del contorno Edge.Cuts (F-03).

        Devuelve ``(bbox, outline)`` donde ``outline`` es ``"none"`` (sin
        Edge.Cuts) o ``"WxHmm"`` (dimensiones del contorno). Con contorno, el
        bbox es el de las líneas Edge.Cuts (dimensión real de fabricación);
        sin contorno, cae a la envolvente TIGHT del enjambre de footprints
        (sin el margen de validación de ``board_bbox_mm``) para que el agente
        vea el área ocupada por la colocación.
        """
        from kipy.proto.board.board_types_pb2 import BoardLayer

        with self._lock:
            self._detect_restart()

            def _do() -> tuple[BBoxMm, str]:
                raw_board = board.raw
                xs: list[float] = []
                ys: list[float] = []
                for shape in raw_board.get_shapes():
                    if getattr(shape, "layer", None) == BoardLayer.BL_Edge_Cuts:
                        bb = shape.bounding_box()
                        xs.extend([float(bb.pos.x), float(bb.pos.x + bb.size.x)])
                        ys.extend([float(bb.pos.y), float(bb.pos.y + bb.size.y)])
                if xs and ys:
                    min_x, min_y, max_x, max_y = min(xs), min(ys), max(xs), max(ys)
                    w_mm = (max_x - min_x) / 1_000_000
                    h_mm = (max_y - min_y) / 1_000_000
                    return (
                        BBoxMm(
                            nm_to_mm(Nm(int(min_x))),
                            nm_to_mm(Nm(int(min_y))),
                            nm_to_mm(Nm(int(max_x))),
                            nm_to_mm(Nm(int(max_y))),
                        ),
                        f"{w_mm:.1f}x{h_mm:.1f}mm",
                    )
                # Sin Edge.Cuts: envolvente tight de footprints (sin margen).
                fxs: list[float] = []
                fys: list[float] = []
                for fp in raw_board.get_footprints():
                    pos = fp.position
                    fxs.append(float(pos.x))
                    fys.append(float(pos.y))
                if not fxs:
                    return (BBoxMm(Mm(0.0), Mm(0.0), Mm(0.0), Mm(0.0)), "none")
                return (
                    BBoxMm(
                        nm_to_mm(Nm(int(min(fxs)))),
                        nm_to_mm(Nm(int(min(fys)))),
                        nm_to_mm(Nm(int(max(fxs)))),
                        nm_to_mm(Nm(int(max(fys)))),
                    ),
                    "none",
                )

            return self._run_supervised_read("board_outline", _do)

    # -- mutaciones -----------------------------------------------------------

    def save_board(self, board: BoardHandle) -> None:
        """Persiste el board vivo a disco vía IPC (D-11.1).

        kipy expone el save del documento como ``Board.save()``
        (``kipy/board.py:285-288``): envía el comando ``SaveDocument`` sobre
        el mismo socket IPC. Es una ESCRITURA: se supervisa directo (sin
        retry, D-07.1) — un ``AS_BUSY`` se propaga tal cual. Cierra el
        split-brain live/disco (F-05): tras el save, render/DRC/export vía
        kicad-cli leen exactamente lo que el agente mutó.
        """
        with self._lock:
            self._detect_restart()
            with self._supervise("save_board"):
                board.raw.save()

    def reload_board_from_disk(self, board: BoardHandle) -> tuple[int, int]:
        """Recarga el board vivo desde el ``.kicad_pcb`` de disco (P3.1, sesión 18).

        kipy expone la recarga como ``Board.revert()`` (``kipy/board.py:304-308``):
        envía ``RevertDocument`` sobre el mismo socket IPC que ``save()``.
        D-12.4 (sesión 12) había descartado la recarga programática evaluando
        sólo el documento **schematic** (IPC de KiCad 11, ``no handler
        available`` en KiCad 10.0.4); nunca se probó ``Board.revert()`` del
        PCB Editor, que sí tiene IPC completo en KiCad 10.

        Verificado en vivo contra KiCad 10.0.4 (sesión 18,
        ``docs/investigacion/18-recarga-ipc.md``): descarta el estado vivo no
        persistido y re-lee exactamente los bytes actuales del disco —
        agnóstico del origen del diff (edición IPC no guardada o reemplazo
        externo del archivo como hace ``route_board`` con ``os.replace``,
        ``pcb.py``). Es idempotente (llamarlo dos veces no falla ni cambia el
        resultado) y NO invalida el ``BoardHandle``: el mismo objeto ``Board``
        de kipy sigue usable después.

        ESCRITURA: supervisada directa, sin retry (D-07.1) — un ``AS_BUSY``
        se propaga tal cual, igual que ``save_board``.

        Devuelve ``(n_tracks, n_vias)`` releídos tras la recarga (incluye
        arcos en el conteo de tracks, como ``Board.get_tracks()`` de kipy) —
        el llamador los usa para el contrato JSON de
        ``reload_board_from_disk`` (tool).
        """
        with self._lock:
            self._detect_restart()
            with self._supervise("reload_board_from_disk"):
                raw_board = board.raw
                raw_board.revert()
                n_tracks = len(list(raw_board.get_tracks()))
                n_vias = len(list(raw_board.get_vias()))
                return (n_tracks, n_vias)

    def draw_board_outline(
        self,
        board: BoardHandle,
        x_mm: Mm,
        y_mm: Mm,
        width_mm: Mm,
        height_mm: Mm,
    ) -> str:
        """Crea un contorno rectangular en ``Edge.Cuts`` (D-12.5).

        Precondición: el llamador validó dimensiones positivas y que el board
        NO tiene contorno todavía (no apilar bordes). Usa ``BoardRectangle``
        (top_left/bottom_right en nm) sobre ``BL_Edge_Cuts`` y lo crea con
        ``create_items`` — mismo camino que ``add_track``/``add_via``. Verificado
        en vivo (sesión 12): create sube el conteo de Edge.Cuts y devuelve KIID.
        ESCRITURA: supervisada directa, sin retry (D-07.1). Devuelve el KIID del
        rectángulo creado, o ``""`` si KiCad no lo reporta.
        """
        from kipy.board_types import BoardRectangle
        from kipy.geometry import Vector2
        from kipy.proto.board.board_types_pb2 import BoardLayer

        with self._lock:
            self._detect_restart()
            with self._supervise("draw_board_outline"):
                raw_board = board.raw
                rect = BoardRectangle()
                rect.layer = BoardLayer.BL_Edge_Cuts
                x0 = int(mm_to_nm(x_mm))
                y0 = int(mm_to_nm(y_mm))
                rect.top_left = Vector2.from_xy(x0, y0)
                rect.bottom_right = Vector2.from_xy(
                    x0 + int(mm_to_nm(width_mm)), y0 + int(mm_to_nm(height_mm))
                )
                created = raw_board.create_items(rect)
                if created:
                    return str(created[0].id.value)
                return ""

    def remove_by_kiid(self, board: BoardHandle, kiid: str) -> bool:
        """Borra el ítem de board identificado por ``kiid`` (D-11.2).

        Localiza el ítem con ``get_items_by_id`` y lo borra con
        ``remove_items`` (el mismo camino validado en los teardowns de los
        tests integration_gui de sesión 09). Devuelve ``True`` si borró algo,
        ``False`` si el KIID ya no estaba (borrado concurrente). ESCRITURA:
        supervisada directa, sin retry.
        """
        from kipy.proto.common.types.base_types_pb2 import KIID as _KIID_proto

        with self._lock:
            self._detect_restart()
            with self._supervise("remove_by_kiid"):
                raw_board = board.raw
                kiid_proto = _KIID_proto()
                kiid_proto.value = kiid
                items = _get_items_by_id_or_empty(raw_board, [kiid_proto])
                if not items:
                    return False
                raw_board.remove_items(items[0])
                return True

    def remove_many_by_kiid(self, board: BoardHandle, kiids: list[str]) -> int:
        """Borra varios ítems de board por KIID en un solo round-trip IPC
        (sesión 19d, ``delete_tracks_bulk``).

        Un ``get_items_by_id`` batch + un ``remove_items`` en bloque — evita
        el costo de N round-trips que tenía ``delete_track``/``delete_via``
        llamado en loop (266 llamadas en 19c Bloque 3 para vaciar el cobre
        del board). KIIDs stale (borrado concurrente entre el ``get_tracks``
        que los emitió y esta llamada) se ignoran silenciosamente — el
        conteo devuelto refleja lo que efectivamente se borró, no lo pedido.
        """
        from kipy.proto.common.types.base_types_pb2 import KIID as _KIID_proto

        with self._lock:
            self._detect_restart()
            with self._supervise("remove_many_by_kiid"):
                raw_board = board.raw
                kiid_protos = []
                for kiid in kiids:
                    kiid_proto = _KIID_proto()
                    kiid_proto.value = kiid
                    kiid_protos.append(kiid_proto)
                items = _get_items_by_id_or_empty(raw_board, kiid_protos)
                if not items:
                    return 0
                raw_board.remove_items(items)
                return len(items)

    def move_footprint(
        self,
        board: BoardHandle,
        ref: str,
        x_mm: Mm,
        y_mm: Mm,
        *,
        kiid: str | None = None,
        timings: dict[str, float] | None = None,
    ) -> None:
        """Mueve el footprint ``ref`` a ``(x_mm, y_mm)`` y persiste el commit.

        Precondición: el llamador ya validó existencia de ``ref`` y que
        las coordenadas están dentro del bounding box. La validación se
        hace afuera para poder emitir errores tipados con hints ricos.

        Sesión 08 D-08.1: si ``kiid`` viene resuelto (típicamente porque
        el tool ya lo capturó vía ``read_board_context``), la búsqueda del
        target usa ``get_items_by_id`` — O(1) de red — en lugar de iterar
        ``get_footprints`` O(board). Colapsa ~3 s de lookup contra el
        board de 202 refs. Sin ``kiid``, se preserva el camino iterativo
        histórico (integration_gui tests y llamadas ad-hoc del bridge).

        Si ``timings`` es un dict, se rellena ``timings["lookup_ms"]`` con
        la latencia de la búsqueda del target (sesión 07 T5, D-07.5).
        """
        # ``fp.position`` es un getter que devuelve ``Vector2(self._proto.position)``
        # (kipy geometry.py:38-42: Vector2 hace CopyFrom del proto). Escribir
        # ``fp.position.x = …`` muta una copia local y update_items envía el
        # proto original sin cambios → mutación silenciosamente perdida
        # (sesión 06 T1). El setter ``fp.position = Vector2(...)`` sí escribe
        # sobre el proto interno del FootprintInstance y además arrastra
        # fields/pads por delta (board_types.py:1939-1964).
        from kipy.geometry import Vector2
        from kipy.proto.common.types.base_types_pb2 import KIID as _KIID_proto

        with self._lock:
            self._detect_restart()
            with self._supervise("move_footprint"):
                raw_board = board.raw
                lookup_start = time.perf_counter()
                target_fp: Any = None
                if kiid:
                    kiid_proto = _KIID_proto()
                    kiid_proto.value = kiid
                    items = _get_items_by_id_or_empty(raw_board, [kiid_proto])
                    target_fp = items[0] if items else None
                else:
                    for fp in raw_board.get_footprints():
                        if str(fp.reference_field.text.value) == ref:
                            target_fp = fp
                            break
                if timings is not None:
                    timings["lookup_ms"] = (time.perf_counter() - lookup_start) * 1000
                if target_fp is not None:
                    target_fp.position = Vector2.from_xy(int(mm_to_nm(x_mm)), int(mm_to_nm(y_mm)))
                    raw_board.update_items(target_fp)
                    return
                # Consistencia: si no lo encontramos, es un bug del llamador.
                raise KicadMcpError(
                    code=ErrorCode.COMPONENT_NOT_FOUND,
                    message=f"Footprint {ref} no está en el board (post-validación).",
                    hint="Snapshot del board cambió entre la validación y la mutación.",
                )

    def add_track(
        self,
        board: BoardHandle,
        net: str,
        start_mm: tuple[Mm, Mm],
        end_mm: tuple[Mm, Mm],
        width_mm: Mm,
        layer: str,
        *,
        timings: dict[str, float] | None = None,
    ) -> str:
        """Agrega un track lineal entre ``start`` y ``end`` en ``layer``.

        Precondición: net y layer válidos, coordenadas dentro del bbox.
        Segmentos múltiples (points_mm en la spec) se representan como
        múltiples add_track por la simplicidad del MVP.

        Si ``timings`` es un dict, se rellena ``timings["lookup_ms"]`` con
        la latencia de la búsqueda O(nets) del net por nombre (sesión 07
        T5, D-07.5).

        Sesión 19d (19d.0): confirmado en vivo que este método tiene el
        mismo comportamiento de reasignación de net que ``add_via`` (H2 de
        19c) — KiCad reasigna el track ENTERO al net del cobre que cruza,
        no sólo el punto de intersección. Verificamos el net real
        post-creación y revertimos en mismatch (``NET_ASSIGNMENT_MISMATCH``).
        Por eso ahora devuelve el KIID del track creado, simétrico a
        ``add_via`` (antes descartaba el retorno de ``create_items``).
        """
        # Import perezoso de tipos de kipy: mantiene el bridge testable
        # con fakes sin pagar el costo cuando kipy no se usa.
        from kipy.board_types import Track
        from kipy.geometry import Vector2
        from kipy.proto.board.board_types_pb2 import BoardLayer
        from kipy.proto.common.types.base_types_pb2 import KIID as _KIID_proto

        with self._lock:
            self._detect_restart()
            with self._supervise("add_track"):
                raw_board = board.raw
                lookup_start = time.perf_counter()
                net_obj = next(
                    (n for n in raw_board.get_nets() if str(n.name) == net),
                    None,
                )
                if timings is not None:
                    timings["lookup_ms"] = (time.perf_counter() - lookup_start) * 1000
                if net_obj is None:
                    raise KicadMcpError(
                        code=ErrorCode.NET_NOT_FOUND,
                        message=f"Net {net} no está en el board (post-validación).",
                        hint="Snapshot del board cambió entre la validación y la mutación.",
                    )
                # Layer string ("F.Cu", "B.Cu", "F.SilkS") → enum BoardLayer (BL_F_Cu,…).
                try:
                    layer_value = BoardLayer.Value(f"BL_{layer.replace('.', '_')}")
                except ValueError as exc:
                    raise KicadMcpError(
                        code=ErrorCode.INVALID_PARAMS,
                        message=f"Layer {layer!r} no reconocido por KiCad.",
                        hint="Valores esperados: F.Cu, B.Cu, F.SilkS, B.SilkS, Edge.Cuts, …",
                    ) from exc
                track = Track()
                track.start = Vector2.from_xy(
                    int(mm_to_nm(start_mm[0])), int(mm_to_nm(start_mm[1]))
                )
                track.end = Vector2.from_xy(int(mm_to_nm(end_mm[0])), int(mm_to_nm(end_mm[1])))
                track.width = int(mm_to_nm(width_mm))
                track.layer = layer_value
                track.net = net_obj
                created = raw_board.create_items(track)
                if not created:
                    return ""
                kiid_proto = _KIID_proto()
                kiid_proto.value = str(created[0].id.value)
                _verify_created_net_or_revert(
                    raw_board,
                    [kiid_proto],
                    created[0],
                    net,
                    [float(start_mm[0]), float(start_mm[1]), float(end_mm[0]), float(end_mm[1])],
                )
                return str(created[0].id.value)

    def add_via(
        self,
        board: BoardHandle,
        net: str,
        x_mm: Mm,
        y_mm: Mm,
        diameter_mm: Mm,
        drill_mm: Mm,
        *,
        timings: dict[str, float] | None = None,
    ) -> str:
        """Crea una via pasante (through) en ``(x_mm, y_mm)`` asignada a ``net``.

        Precondición: net válido, coordenadas dentro del bbox, drill < diámetro
        (el llamador valida antes para emitir errores tipados con hints ricos).

        La ``Via`` de kipy nace pasante (``VT_THROUGH``, drill F.Cu→B.Cu) por
        default (``board_types.py:1606-1608``); fijamos posición, diámetro,
        drill y net. Se crea con ``create_items`` — el mismo camino que
        ``add_track``. Devuelve el KIID de la via creada (para la verificación
        puntual del round-trip E2E), o ``""`` si KiCad no lo reporta.

        Si ``timings`` es un dict, se rellena ``timings["lookup_ms"]`` con la
        latencia de la búsqueda O(nets) del net por nombre (paralelo a
        ``add_track``).

        Sesión 19c (Bloque 1, H2) confirmó en vivo que KiCad reasigna la via
        al net del cobre físico bajo el punto de colocación, sin relación con
        lo pedido — la confirmación de texto de la tool seguía mostrando el
        net pedido pese a la reasignación silenciosa. Sesión 19d cierra ese
        hueco: verificamos el net real post-creación y revertimos en
        mismatch (``NET_ASSIGNMENT_MISMATCH``).
        """
        from kipy.board_types import Via
        from kipy.geometry import Vector2
        from kipy.proto.common.types.base_types_pb2 import KIID as _KIID_proto

        with self._lock:
            self._detect_restart()
            with self._supervise("add_via"):
                raw_board = board.raw
                lookup_start = time.perf_counter()
                net_obj = next(
                    (n for n in raw_board.get_nets() if str(n.name) == net),
                    None,
                )
                if timings is not None:
                    timings["lookup_ms"] = (time.perf_counter() - lookup_start) * 1000
                if net_obj is None:
                    raise KicadMcpError(
                        code=ErrorCode.NET_NOT_FOUND,
                        message=f"Net {net} no está en el board (post-validación).",
                        hint="Snapshot del board cambió entre la validación y la mutación.",
                    )
                via = Via()
                via.position = Vector2.from_xy(int(mm_to_nm(x_mm)), int(mm_to_nm(y_mm)))
                via.diameter = int(mm_to_nm(diameter_mm))
                via.drill_diameter = int(mm_to_nm(drill_mm))
                via.net = net_obj
                created = raw_board.create_items(via)
                if not created:
                    return ""
                kiid_proto = _KIID_proto()
                kiid_proto.value = str(created[0].id.value)
                _verify_created_net_or_revert(
                    raw_board,
                    [kiid_proto],
                    created[0],
                    net,
                    [float(x_mm), float(y_mm)],
                )
                return str(created[0].id.value)
