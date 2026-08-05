"""Goldens de los tres encoders ad-hoc de ``tools/pcb.py`` (sesión 36, R2;
sesión 37 cierra el gap del espacio, ver H36.1 abajo).

``_encode_tracks``, ``_encode_zones`` y ``_encode_component_detail`` NO son
TOON (lo dicen sus propios docstrings) pero interpolan texto de KiCad
(``net_name``/``ref``/``pad.number``) — entrada no confiable por regla 6 de
CLAUDE.md. Hasta sesión 36 lo hacían sin sanitizar (R2 de la auditoría
2026-08, primera pieza de DT4). El fix reusa ``toon.encoder._sanitize`` (§5)
en los tres sitios de interpolación.

Mismo patrón que ``test_toon_encoder.py`` (comparación byte a byte contra
``tests/golden/``, marcador ``golden``), pero llamando directo a las
funciones privadas del encoder en vez de pasar por la tool MCP completa: es
la misma capa arquitectónica (serialización pura) que ``encode_state`` en el
módulo toon, sólo que acá el nombre lleva guion bajo por convención del
archivo, no porque la tool pública no exista.

**H36.1 (evaluada, refutada parcialmente en sesión 36; gap cerrado en
sesión 37):** ``_sanitize`` neutraliza los caracteres estructurales de TOON
(control chars, ``>``, ``|``, ``:``) pero NO el espacio — que es el
delimitador POSICIONAL de las tres gramáticas ad-hoc (space-delimited, a
diferencia de TOON que es ``|``-delimited). Cada golden incluye un ítem con
un ``net_name``/``number`` con espacio interno (p.ej. ``"GND EN"``); sesión
37 cierra el gap con ``_sanitize_space_delimited`` (``tools/pcb.py``), que
compone ``_sanitize`` con neutralización de whitespace en los campos
space-delimited. Ver reportes de sesión 36 y 37 en
``docs/historico/sesiones/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.bridge.ipc import ComponentDetail, CopperItem, Mm, PadDetail, ZoneItem
from kicad_mcp.tools.pcb import _encode_component_detail, _encode_tracks, _encode_zones

GOLDEN_DIR = Path(__file__).parent / "golden"


def _mm_or_none(v: float | None) -> Mm | None:
    return None if v is None else Mm(v)


def _load_tracks_items(items: list[dict]) -> tuple[CopperItem, ...]:
    return tuple(
        CopperItem(
            kind=it["kind"],
            kiid=it["kiid"],
            net_name=it["net_name"],
            layer=it["layer"],
            start_x_mm=Mm(it["start_x_mm"]),
            start_y_mm=Mm(it["start_y_mm"]),
            end_x_mm=_mm_or_none(it.get("end_x_mm")),
            end_y_mm=_mm_or_none(it.get("end_y_mm")),
            mid_x_mm=_mm_or_none(it.get("mid_x_mm")),
            mid_y_mm=_mm_or_none(it.get("mid_y_mm")),
            width_mm=_mm_or_none(it.get("width_mm")),
            size_mm=_mm_or_none(it.get("size_mm")),
            drill_mm=_mm_or_none(it.get("drill_mm")),
            via_layers=tuple(it["via_layers"]) if it.get("via_layers") else None,
        )
        for it in items
    )


def _load_zone_items(items: list[dict]) -> tuple[ZoneItem, ...]:
    zones = []
    for it in items:
        verts = it["vertices_mm"]
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        zones.append(
            ZoneItem(
                kind=it["kind"],
                kiid=it["kiid"],
                net_name=it["net_name"],
                layer=it["layer"],
                bbox_min_x=Mm(min(xs)),
                bbox_min_y=Mm(min(ys)),
                bbox_max_x=Mm(max(xs)),
                bbox_max_y=Mm(max(ys)),
                area_mm2=(max(xs) - min(xs)) * (max(ys) - min(ys)),
                filled=True,
                vertices_mm=tuple((Mm(x), Mm(y)) for x, y in verts),
            )
        )
    return tuple(zones)


def _load_component_detail(d: dict) -> ComponentDetail:
    pads = tuple(
        PadDetail(
            number=p["number"],
            net_name=p["net_name"],
            x_mm=Mm(p["x_mm"]),
            y_mm=Mm(p["y_mm"]),
            w_mm=Mm(p["w_mm"]),
            h_mm=Mm(p["h_mm"]),
            layer=p["layer"],
        )
        for p in d["pads"]
    )
    return ComponentDetail(
        ref=d["ref"],
        value=d["value"],
        x_mm=Mm(d["x_mm"]),
        y_mm=Mm(d["y_mm"]),
        rotation_deg=d["rotation_deg"],
        bbox_min_x=Mm(d["bbox_min_x"]),
        bbox_min_y=Mm(d["bbox_min_y"]),
        bbox_max_x=Mm(d["bbox_max_x"]),
        bbox_max_y=Mm(d["bbox_max_y"]),
        bbox_source=d["bbox_source"],
        pads=pads,
    )


@pytest.mark.golden
def test_golden_004_pcb_tracks_canarios_byte_por_byte() -> None:
    """Canarios: ``\\n`` (T1), ``|`` (T2), ``"`` (A1, arco), ``" "`` (T4,
    sanitizado por ``_sanitize_space_delimited`` desde sesión 37), ``""``
    (V1, gap conocido pre-existente en ``CopperItem`` — no tiene fallback
    ``or "-"`` a diferencia de zonas/pads)."""
    d = json.loads((GOLDEN_DIR / "004_pcb_tracks_canarios" / "input.json").read_text())
    expected = (GOLDEN_DIR / "004_pcb_tracks_canarios" / "expected.txt").read_bytes()
    items = _load_tracks_items(d["items"])
    got = _encode_tracks(items, d["filter_desc"]).encode("utf-8")
    assert got == expected


@pytest.mark.golden
def test_golden_005_pcb_zones_canarios_byte_por_byte() -> None:
    """Canarios: ``\\n`` (Z1), ``|`` (Z2), ``"`` (Z3, keepout), ``" "`` (Z4,
    sanitizado por ``_sanitize_space_delimited`` desde sesión 37). Z5
    (``net_name=None``) no es un canario de sanitización: es el sentinel
    ``or "-"`` pre-existente, incluido para cubrir la rama."""
    d = json.loads((GOLDEN_DIR / "005_pcb_zones_canarios" / "input.json").read_text())
    expected = (GOLDEN_DIR / "005_pcb_zones_canarios" / "expected.txt").read_bytes()
    items = _load_zone_items(d["items"])
    got = _encode_zones(items, d["filter_desc"]).encode("utf-8")
    assert got == expected


@pytest.mark.golden
def test_golden_006_pcb_component_detail_canarios_byte_por_byte() -> None:
    """``ref`` empaqueta varios canarios estructurales a la vez (``|``,
    ``:``, ``>``, ``\\n``, ``"``) en el header ``|``-delimitado, donde
    ``_sanitize`` los cierra sin excepción. Los pads cubren, uno por uno:
    ``\\n``/``|``/``"``/``" "`` en ``number``, y ``" "`` en ``net_name`` —
    ambos casos de espacio sanitizados por ``_sanitize_space_delimited``
    desde sesión 37."""
    d = json.loads((GOLDEN_DIR / "006_pcb_component_detail_canarios" / "input.json").read_text())
    expected = (GOLDEN_DIR / "006_pcb_component_detail_canarios" / "expected.txt").read_bytes()
    detail = _load_component_detail(d)
    got = _encode_component_detail(detail).encode("utf-8")
    assert got == expected
