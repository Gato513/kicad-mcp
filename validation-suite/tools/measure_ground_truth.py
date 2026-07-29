#!/usr/bin/env python3
"""Mide las métricas D-30.3 de un ``.kicad_pcb`` para la Validation Suite.

**Intérprete requerido: ``/usr/bin/python3`` (pcbnew del sistema), NO el
venv de ``uv``.** El venv de este proyecto no tiene ``pcbnew`` instalado
(es una dependencia del sistema operativo, vía el paquete de KiCad, no de
PyPI — ver ``scripts/verificar_entorno.py`` y ``src/kicad_mcp/bridge/
autoroute.py`` que usan el mismo patrón). Invocar así:

    /usr/bin/python3 validation-suite/tools/measure_ground_truth.py <board.kicad_pcb> [-o out.json]

Si ``import pcbnew`` falla, el script lo reporta con un mensaje explícito
en vez de un traceback crudo (regla de código #1 del proyecto, aplicada acá
aunque este script viva fuera de ``src/``).

Este script es la **herramienta reutilizable de la Validation Suite**
(sesión 31, D-30.3): produce las 4 métricas de aceptación (DRC, longitud de
tracks, número de vías, área de cobre) más un puñado de métricas auxiliares
baratas que alimentan ``validation-suite/reports/coverage-matrix.md`` y el
análisis H2. El ejecutor de sesiones 32/33 no debería necesitar preguntar
nada — cada métrica documenta acá mismo qué mide, qué asume y qué excluye.

## Métricas D-30.3

- ``drc_errors`` / ``drc_warnings``: corren ``kicad-cli pcb drc --format
  json --severity-all`` como subprocess — **mismos flags exactos que**
  ``src/kicad_mcp/bridge/rules.py::run_drc`` (sin ``--refill-zones`` ni
  ``--save-board``: medimos el estado tal cual está en disco, no lo
  mutamos). Los conteos de severidad se arman igual que
  ``rules.py::_build_report``: ``violations`` + ``unconnected_items`` se
  funden en un solo conteo por severidad (un ``unconnected_items`` sin
  severidad explícita cuenta como ``warning``, igual que el bridge).
- ``total_track_length_mm``: suma de ``GetLength()`` sobre segmentos
  (``PCB_TRACE_T``) y arcos (``PCB_ARC_T``). **Excluye vías** — una vía no
  tiene "longitud" en el sentido de un tramo de cobre (``GetLength()``
  sobre una vía devuelve 0.0, verificado empíricamente); incluirlas sería
  contar dos veces el concepto que ``via_count`` ya captura.
- ``via_count``: conteo de ``PCB_VIA_T`` en ``board.GetTracks()``.
- ``copper_area_mm2``: **unión geométrica por capa de cobre**, no suma
  aditiva de áreas individuales. Para cada capa de cobre (``CuStack()`` del
  ``LSET`` habilitado del board — típicamente ``F.Cu``/``B.Cu`` en un
  2-capas, más las internas si las hay) se construye un
  ``SHAPE_POLY_SET`` acumulando, vía ``BooleanAdd`` (unión booleana real,
  no sólo concatenación de contornos), los polígonos de:
    - tracks y arcos en esa capa (``TransformShapeToPolySet``,
      clearance=0, con la tolerancia de arco estándar de KiCad
      ``ARC_HIGH_DEF_MM``);
    - pads de footprints "flasheados" en esa capa
      (``pad.GetEffectivePolygon(layer)``);
    - zonas de cobre YA RELLENADAS en esa capa (``zone.GetFilledPolysList
      (layer)``), **excluyendo** ``zone.GetIsRuleArea()`` (keepouts no son
      cobre).
  La unión evita el doble conteo de un pad cubierto por el pour de una
  zona, o de un track que corre encima de un plano — problema real de una
  suma aditiva ingenua. Se registra también el ``total_aditivo_mm2`` (suma
  de las áreas individuales sin unir, por capa) como cross-check: por
  construcción, ``union <= aditivo`` siempre; si el script mide lo
  contrario en algún caso, es una señal de bug y se declara en
  ``method_notes``, nunca se oculta.
  **Fallback declarado**: si la API de unión (``BooleanAdd``/
  ``TransformShapeToPolySet``/``GetEffectivePolygon``) no está disponible
  en la versión de pcbnew que corre el script (versión de KiCad más vieja
  que la validada, D2/D-30.3), se cae al total aditivo y se marca
  ``"method": "aditivo_fallback"`` en el JSON — nunca en silencio.

## Métricas auxiliares (coverage-matrix + análisis H2)

``footprint_count``, ``net_count`` (``board.GetNetCount()``, incluye el
net vacío "" que KiCad siempre reserva), ``copper_layer_count``,
``board_area_mm2`` (bounding box del contorno Edge.Cuts), ``track_segment_
count`` (segmentos + arcos, sin vías), ``zone_count`` (zonas de cobre,
excluye keepouts/rule areas), ``density_pct`` (``copper_area_mm2`` de la
capa con más cobre, dividido por ``board_area_mm2`` — proxy barato de
densidad para la matriz de cobertura D-30.4, no pretende ser una métrica
de fabricación).

## Extensiones de sesión 32 (``schema_version`` 1.0 → 1.1, aditivas)

Reflexiones heredadas de sesión 31c: el ratio global de tracks/vías no
distingue "sub-ruteo uniforme" de "topología distinta en nets grandes", y
"0 errores DRC nuevos" no distingue severidad. Estas claves son **puramente
aditivas** — ninguna clave de 1.0 cambia de nombre ni de significado.

- ``track_length_by_net_mm``: igual que ``total_track_length_mm`` pero
  agrupado por ``track.GetNetname()`` — habilita el análisis por-net
  (top 5 por delta absoluto/porcentual) de sesión 32 en adelante.
- ``via_count_by_net``: igual que ``via_count`` pero agrupado por net —
  descompone el ratio de vías (diagnóstico de 31c: umbral mal calibrado
  para bases pequeñas).
- ``drc_by_rule``: ``_run_drc`` ya parseaba el JSON de ``kicad-cli`` para
  colapsar en ``errors``/``warnings`` por severidad; esta clave agrega un
  segundo conteo por ``v.get("type")`` (el rule id crudo de KiCad:
  ``solder_mask_bridge``, ``unconnected_items``, ``silk_over_copper``,
  etc.), fusionando ``violations`` + ``unconnected_items`` igual que antes.
  Es la fuente para la tabla DRC separada por severidad (eléctrico /
  estructural / cosmético) — la taxonomía de buckets vive en el reporte de
  sesión, no en este script, porque es una interpretación, no una medición.
- ``orphan_vias``: vías sin ningún ítem conectado más allá de sí mismas.
  Usa ``board.GetConnectivity().GetConnectedItems(via)`` — verificado
  empíricamente (sesión 32) que ese conjunto incluye la propia vía, así que
  una vía aislada devuelve exactamente 1 elemento (ella misma); cualquier
  cosa por encima de 1 significa que hay al menos un track o pad
  topológicamente conectado. Cross-check con
  ``TestTrackEndpointDangling(via, aIgnoreTracksInPads=False)`` — se
  registra pero no decide por sí solo (puede marcar "dangling" un extremo
  de track sano que simplemente termina en una vía intermedia). Vigilancia
  del patrón F-D5-01 / F-V1c-01 (vía o isla GND sin conectividad cerrada).

## Chequeos de cordura

- ``union_mm2 <= aditivo_mm2 + 1e-6`` por capa (tolerancia de redondeo
  flotante). Si falla, se registra en ``method_notes`` — no se corrige
  aritmética propia sobre la evidencia (D-30.1: verificar contra el motor
  real, no contra lo que "debería" dar).
- ``copper_area_mm2 <= board_area_mm2 * copper_layer_count`` (con 10% de
  margen por redondeo de arcos/curvas) — si el cobre unido excede el área
  físicamente disponible en todas las capas, algo en el cálculo está mal.

## Salida

JSON con ``schema_version``, ``board_path``, ``measured_at`` (UTC ISO8601),
``kicad_version`` (de ``pcbnew.GetBuildVersion()``), ``method`` (``"union"``
o ``"aditivo_fallback"``), las 4 métricas D-30.3, las auxiliares, y
``method_notes`` (lista de strings, vacía si no hay nada que declarar).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.1"

try:
    import pcbnew
except ImportError as exc:  # pragma: no cover - depende del intérprete del sistema
    sys.stderr.write(
        "ERROR: no se pudo importar pcbnew. Este script requiere el Python "
        "del SISTEMA que trae pcbnew instalado (ej. /usr/bin/python3), NO "
        "el venv de `uv` del proyecto (que no tiene pcbnew — es una "
        "dependencia del paquete de KiCad, no de PyPI).\n"
        f"Import original: {exc}\n"
        "Probá: /usr/bin/python3 validation-suite/tools/measure_ground_truth.py <board.kicad_pcb>\n"
    )
    sys.exit(2)


def _run_drc(pcb_path: Path) -> dict[str, Any]:
    """Corre DRC vía kicad-cli con los mismos flags que
    ``src/kicad_mcp/bridge/rules.py::run_drc`` y devuelve conteos por
    severidad, fusionando ``violations`` + ``unconnected_items`` igual que
    ``rules.py::_build_report``/``_iter_drc_violations``.

    Sesión 32 agrega ``by_rule`` (conteo por ``type`` crudo de KiCad, misma
    fusión violations+unconnected) — aditivo, no cambia ``errors``/
    ``warnings``.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=str(pcb_path.parent)
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        args = [
            "kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "-o",
            str(tmp_path),
            str(pcb_path),
        ]
        completed = subprocess.run(args, capture_output=True, text=True, timeout=120)
        if completed.returncode != 0:
            raise RuntimeError(
                f"kicad-cli pcb drc falló (returncode={completed.returncode}): "
                f"{completed.stderr.strip()[:300]}"
            )
        payload = json.loads(tmp_path.read_text(encoding="utf-8"))
    finally:
        tmp_path.unlink(missing_ok=True)

    counts: Counter[str] = Counter()
    by_rule: Counter[str] = Counter()
    for v in payload.get("violations", []):
        counts[str(v.get("severity", "warning"))] += 1
        by_rule[str(v.get("type", "unknown"))] += 1
    for v in payload.get("unconnected_items", []):
        counts[str(v.get("severity", "warning"))] += 1
        by_rule[str(v.get("type", "unconnected_items"))] += 1
    return {
        "errors": counts.get("error", 0),
        "warnings": counts.get("warning", 0),
        "by_rule": dict(by_rule),
    }


def _nm2_to_mm2(value_nm2: float) -> float:
    """``pcbnew`` reporta áreas en nm² (unidades internas al cuadrado).
    ``pcbnew.ToMM`` convierte longitud nm->mm (÷1e6); aplicarlo dos veces
    da nm²->mm² (÷1e12), que es lo que se necesita para área.
    """
    return pcbnew.ToMM(pcbnew.ToMM(value_nm2))


def _copper_layers(board: Any) -> list[tuple[int, str]]:
    layer_set = board.GetEnabledLayers()
    return [(layer_id, board.GetLayerName(layer_id)) for layer_id in layer_set.CuStack()]


def _layer_copper_area(board: Any, layer_id: int, arc_error_iu: int) -> tuple[float, float]:
    """Devuelve ``(union_mm2, aditivo_mm2)`` de cobre en una capa."""
    union = pcbnew.SHAPE_POLY_SET()
    aditivo_mm2 = 0.0

    def _accumulate(shape_poly: Any) -> None:
        nonlocal aditivo_mm2
        aditivo_mm2 += _nm2_to_mm2(shape_poly.Area())
        union.BooleanAdd(shape_poly)

    for track in board.GetTracks():
        if track.Type() == pcbnew.PCB_VIA_T:
            # Las vías se cuentan geométricamente igual que un track (tienen
            # una forma circular en la capa) — sí aportan área de cobre,
            # aunque GetLength() no las cuente en total_track_length_mm.
            if not track.IsOnLayer(layer_id):
                continue
            tmp = pcbnew.SHAPE_POLY_SET()
            track.TransformShapeToPolySet(tmp, layer_id, 0, arc_error_iu, pcbnew.ERROR_OUTSIDE)
            _accumulate(tmp)
        else:
            if not track.IsOnLayer(layer_id):
                continue
            tmp = pcbnew.SHAPE_POLY_SET()
            track.TransformShapeToPolySet(tmp, layer_id, 0, arc_error_iu, pcbnew.ERROR_OUTSIDE)
            _accumulate(tmp)

    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if not pad.IsOnLayer(layer_id):
                continue
            _accumulate(pad.GetEffectivePolygon(layer_id, pcbnew.ERROR_OUTSIDE))

    for zone in board.Zones():
        if zone.GetIsRuleArea():
            continue
        if not zone.IsOnLayer(layer_id):
            continue
        _accumulate(zone.GetFilledPolysList(layer_id))

    union.Simplify()
    return _nm2_to_mm2(union.Area()), aditivo_mm2


def _board_area_mm2(board: Any) -> float:
    """Área del bounding box del contorno Edge.Cuts, en mm².

    **NO usa** ``board.GetBoardEdgesBoundingBox()``: pese al nombre, esa API
    incluye la bbox de otros ítems del board (footprints, texto) además de
    Edge.Cuts — verificado empíricamente en sesión 31 con el working/ de
    ANAVI Dev Mic recién preparado (footprints apilados en el origen, lejos
    del contorno real): reportó un bbox ~10x más grande que el contorno
    real, extendido hasta abarcar el origen. Acá se filtran explícitamente
    los dibujos en la capa ``Edge.Cuts`` y se calcula el bbox unión de
    ÉSOS nada más — inmune a dónde estén parados los footprints.
    """
    edge_items = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    if not edge_items:
        return 0.0
    bbox = edge_items[0].GetBoundingBox()
    for item in edge_items[1:]:
        bbox.Merge(item.GetBoundingBox())
    return pcbnew.ToMM(bbox.GetWidth()) * pcbnew.ToMM(bbox.GetHeight())


def _track_length_by_net(segments_and_arcs: list[Any]) -> dict[str, float]:
    """``total_track_length_mm`` descompuesto por net (sesión 32, reflexión
    #1 de 31c). Mismo criterio de longitud (``GetLength()``, excluye vías).
    """
    by_net: dict[str, float] = {}
    for t in segments_and_arcs:
        name = t.GetNetname()
        by_net[name] = by_net.get(name, 0.0) + pcbnew.ToMM(t.GetLength())
    return {k: round(v, 4) for k, v in by_net.items()}


def _via_count_by_net(vias: list[Any]) -> dict[str, int]:
    """``via_count`` descompuesto por net (sesión 32) — descompone el ratio
    de vías para diagnosticar el sesgo de base pequeña reportado en 31c.
    """
    by_net: dict[str, int] = {}
    for v in vias:
        name = v.GetNetname()
        by_net[name] = by_net.get(name, 0) + 1
    return by_net


def _orphan_vias(board: Any, vias: list[Any]) -> list[dict[str, Any]]:
    """Vías sin ningún ítem conectado más allá de sí mismas (vigilancia
    F-D5-01 / F-V1c-01, sesión 32).

    ``CONNECTIVITY_DATA.GetConnectedItems(via)`` incluye la propia vía en el
    resultado (verificado empíricamente contra pcbnew 10.0.4 en sesión 32) —
    una vía topológicamente aislada devuelve exactamente 1 elemento (ella
    misma). ``TestTrackEndpointDangling`` se registra como cross-check
    informativo, no decide sola (puede marcar dangling un extremo sano que
    simplemente termina en una vía intermedia de un track continuo).
    """
    conn = board.GetConnectivity()
    orphans: list[dict[str, Any]] = []
    for v in vias:
        connected = conn.GetConnectedItems(v)
        if len(connected) <= 1:
            pos = v.GetPosition()
            orphans.append(
                {
                    "net": v.GetNetname(),
                    "x_mm": round(pcbnew.ToMM(pos.x), 4),
                    "y_mm": round(pcbnew.ToMM(pos.y), 4),
                    "dangling_cross_check": bool(conn.TestTrackEndpointDangling(v, False)),
                }
            )
    return orphans


def measure(pcb_path: Path) -> dict[str, Any]:
    board = pcbnew.LoadBoard(str(pcb_path))
    method_notes: list[str] = []

    tracks = list(board.GetTracks())
    segments_and_arcs = [t for t in tracks if t.Type() in (pcbnew.PCB_TRACE_T, pcbnew.PCB_ARC_T)]
    vias = [t for t in tracks if t.Type() == pcbnew.PCB_VIA_T]
    total_track_length_mm = sum(pcbnew.ToMM(t.GetLength()) for t in segments_and_arcs)

    copper_layers = _copper_layers(board)
    arc_error_iu = pcbnew.FromMM(pcbnew.ARC_HIGH_DEF_MM)

    method = "union"
    per_layer_union: dict[str, float] = {}
    per_layer_aditivo: dict[str, float] = {}
    try:
        for layer_id, layer_name in copper_layers:
            union_mm2, aditivo_mm2 = _layer_copper_area(board, layer_id, arc_error_iu)
            per_layer_union[layer_name] = union_mm2
            per_layer_aditivo[layer_name] = aditivo_mm2
            if union_mm2 > aditivo_mm2 + 1e-6:
                method_notes.append(
                    f"cordura violada en {layer_name}: unión ({union_mm2:.4f}mm2) > "
                    f"aditivo ({aditivo_mm2:.4f}mm2) — revisar el cálculo, no debería pasar."
                )
    except AttributeError as exc:
        method = "aditivo_fallback"
        method_notes.append(
            f"API de unión no disponible en esta versión de pcbnew ({exc}); "
            "se usó fallback aditivo (sobreestima si hay cobre superpuesto)."
        )
        per_layer_union = {}
        per_layer_aditivo = {}
        for layer_id, layer_name in copper_layers:
            aditivo_mm2 = 0.0
            for t in tracks:
                if not t.IsOnLayer(layer_id):
                    continue
                tmp = pcbnew.SHAPE_POLY_SET()
                t.TransformShapeToPolySet(tmp, layer_id, 0, arc_error_iu, pcbnew.ERROR_OUTSIDE)
                aditivo_mm2 += _nm2_to_mm2(tmp.Area())
            for zone in board.Zones():
                if zone.GetIsRuleArea() or not zone.IsOnLayer(layer_id):
                    continue
                aditivo_mm2 += _nm2_to_mm2(zone.GetFilledPolysList(layer_id).Area())
            per_layer_aditivo[layer_name] = aditivo_mm2

    copper_source = per_layer_union if method == "union" else per_layer_aditivo
    copper_area_mm2 = sum(copper_source.values())
    total_aditivo_mm2 = sum(per_layer_aditivo.values()) if per_layer_aditivo else copper_area_mm2

    board_area_mm2 = _board_area_mm2(board)
    n_copper_layers = len(copper_layers)
    if n_copper_layers and copper_area_mm2 > board_area_mm2 * n_copper_layers * 1.10:
        method_notes.append(
            f"cordura violada: copper_area_mm2 ({copper_area_mm2:.2f}) excede "
            f"board_area_mm2*capas ({board_area_mm2 * n_copper_layers:.2f}) en >10%."
        )

    zones_copper = [z for z in board.Zones() if not z.GetIsRuleArea()]
    density_pct = 0.0
    if copper_source and board_area_mm2 > 0:
        max_layer_area = max(copper_source.values())
        density_pct = round(100.0 * max_layer_area / board_area_mm2, 2)

    drc = _run_drc(pcb_path)

    return {
        "schema_version": SCHEMA_VERSION,
        "board_path": str(pcb_path),
        "measured_at": datetime.now(UTC).isoformat(),
        "kicad_version": pcbnew.GetBuildVersion(),
        "method": method,
        "drc_errors": drc["errors"],
        "drc_warnings": drc["warnings"],
        "drc_by_rule": drc["by_rule"],
        "total_track_length_mm": round(total_track_length_mm, 4),
        "via_count": len(vias),
        "copper_area_mm2": round(copper_area_mm2, 4),
        "copper_area_mm2_aditivo": round(total_aditivo_mm2, 4),
        "copper_area_by_layer_mm2": {k: round(v, 4) for k, v in copper_source.items()},
        "footprint_count": len(list(board.GetFootprints())),
        "net_count": board.GetNetCount(),
        "copper_layer_count": n_copper_layers,
        "board_area_mm2": round(board_area_mm2, 4),
        "track_segment_count": len(segments_and_arcs),
        "zone_count": len(zones_copper),
        "density_pct": density_pct,
        "track_length_by_net_mm": _track_length_by_net(segments_and_arcs),
        "via_count_by_net": _via_count_by_net(vias),
        "orphan_vias": _orphan_vias(board, vias),
        "method_notes": method_notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("board", type=Path, help="Path a un .kicad_pcb")
    parser.add_argument("-o", "--output", type=Path, help="Path de salida JSON (default: stdout)")
    args = parser.parse_args()

    if not args.board.exists():
        sys.stderr.write(f"ERROR: no existe {args.board}\n")
        return 1

    result = measure(args.board)
    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        args.output.write_text(output_json + "\n", encoding="utf-8")
        print(f"Métricas escritas en {args.output}")
    else:
        print(output_json)

    if result["method_notes"]:
        sys.stderr.write("AVISOS de cordura (ver method_notes en el JSON):\n")
        for note in result["method_notes"]:
            sys.stderr.write(f"  - {note}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
