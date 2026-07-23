"""Tests unit de ``bridge.rules`` — parseo del DRC/ERC JSON (sesión 17, P2.5).

Estrategia: ``_build_report``/``_iter_drc_violations`` sobre payloads
sintéticos, sin invocar ``kicad-cli`` (eso lo cubre ``test_export.py`` /
``integration``). El payload de ``copper_edge_clearance`` de abajo es la
forma REAL capturada corriendo ``kicad-cli pcb drc --format json`` sobre un
board sintético con un track a 0.2mm de un borde con
``min_copper_edge_clearance=0.5`` (sesión 17): el primer ítem SIEMPRE es el
gráfico Edge.Cuts (posición del borde, no necesariamente ``[0,0]`` pero
siempre inútil para ubicar el cobre ofensor) y el segundo es el track/pad
real.
"""

from __future__ import annotations

from typing import Any

import pytest

from kicad_mcp.bridge.rules import (
    Item,
    Violation,
    _build_report,
    _iter_drc_violations,
    diff_violations,
)

# Payload real (recortado a lo relevante) capturado con kicad-cli 10.0.4.
_EDGE_CLEARANCE_PAYLOAD: dict[str, Any] = {
    "coordinate_units": "mm",
    "kicad_version": "10.0.4",
    "unconnected_items": [],
    "violations": [
        {
            "type": "copper_edge_clearance",
            "severity": "error",
            "description": (
                "Board edge clearance violation (board setup constraints "
                "edge clearance 0.5000 mm; actual 0.2000 mm)"
            ),
            "items": [
                {
                    "description": "Segment on Edge.Cuts",
                    "pos": {"x": 20.0, "y": 20.0},
                    "uuid": "4e25dd2c-d30d-47d8-865d-764072377d39",
                },
                {
                    "description": "Track [NET1] on F.Cu, length 16.0000 mm",
                    "pos": {"x": 2.0, "y": 19.7},
                    "uuid": "4e3b055d-1660-4922-b037-68a8e9b43068",
                },
            ],
        },
        {
            "type": "copper_edge_clearance",
            "severity": "error",
            "description": (
                "Board edge clearance violation (board setup constraints "
                "edge clearance 0.5000 mm; actual 0.0000 mm)"
            ),
            "items": [
                {
                    "description": "Segment on Edge.Cuts",
                    "pos": {"x": 20.0, "y": 20.0},
                    "uuid": "4e25dd2c-d30d-47d8-865d-764072377d39",
                },
                {
                    "description": "Pad 1 [NET1] of U1 on F.Cu",
                    "pos": {"x": 2.0, "y": 19.7},
                    "uuid": "d66ea6b1-df54-4532-8925-4fdbb1ef4d2d",
                },
            ],
        },
    ],
}


@pytest.mark.unit
def test_copper_edge_clearance_first_item_is_the_offending_copper_not_the_edge() -> None:
    """El bug P2.5: antes, ``items[0].pos`` era el del gráfico Edge.Cuts
    (inútil para ubicar el cobre); ahora el primer ítem es siempre el
    track/pad real."""
    report = _build_report(_EDGE_CLEARANCE_PAYLOAD, _iter_drc_violations(_EDGE_CLEARANCE_PAYLOAD))
    assert len(report.violations) == 2

    track_violation = report.violations[0]
    assert track_violation.items[0].pos == (2.0, 19.7)
    assert track_violation.items[0].desc is not None
    assert "Edge.Cuts" not in track_violation.items[0].desc
    assert track_violation.items[1].desc is not None
    assert "Edge.Cuts" in track_violation.items[1].desc

    pad_violation = report.violations[1]
    assert pad_violation.items[0].pos == (2.0, 19.7)
    assert pad_violation.items[0].desc == "Pad 1 [NET1] of U1 on F.Cu"


@pytest.mark.unit
def test_non_edge_clearance_violations_keep_original_item_order() -> None:
    """El reordenamiento es específico de ``copper_edge_clearance`` — otros
    tipos de violación (p. ej. clearance track-a-track) no se tocan."""
    payload: dict[str, Any] = {
        "coordinate_units": "mm",
        "kicad_version": "10.0.4",
        "unconnected_items": [],
        "violations": [
            {
                "type": "clearance",
                "severity": "error",
                "description": "Clearance violation",
                "items": [
                    {"description": "Track [NET1] on F.Cu", "pos": {"x": 5.0, "y": 5.0}},
                    {"description": "Track [NET2] on F.Cu", "pos": {"x": 5.1, "y": 5.0}},
                ],
            }
        ],
    }
    report = _build_report(payload, _iter_drc_violations(payload))
    v = report.violations[0]
    assert v.items[0].pos == (5.0, 5.0)
    assert v.items[1].pos == (5.1, 5.0)


@pytest.mark.unit
def test_copper_edge_clearance_all_edge_items_no_reorder_no_crash() -> None:
    """Caso degenerado: si TODOS los ítems son Edge.Cuts (no debería pasar en
    la práctica), no hay a qué reordenar — se preserva el orden original sin
    lanzar."""
    payload: dict[str, Any] = {
        "coordinate_units": "mm",
        "kicad_version": "10.0.4",
        "unconnected_items": [],
        "violations": [
            {
                "type": "copper_edge_clearance",
                "severity": "error",
                "description": "edge",
                "items": [
                    {"description": "Segment on Edge.Cuts", "pos": {"x": 0.0, "y": 0.0}},
                    {"description": "Arc on Edge.Cuts", "pos": {"x": 1.0, "y": 1.0}},
                ],
            }
        ],
    }
    report = _build_report(payload, _iter_drc_violations(payload))
    v = report.violations[0]
    assert v.items[0].pos == (0.0, 0.0)
    assert v.items[1].pos == (1.0, 1.0)


@pytest.mark.unit
def test_copper_edge_clearance_items_without_desc_are_not_misclassified_as_edge() -> None:
    """Un ítem sin ``description`` (desc=None) no debe crashear el filtro
    ``"Edge.Cuts" in it.desc`` — y no se lo trata como el ítem Edge.Cuts."""
    payload: dict[str, Any] = {
        "coordinate_units": "mm",
        "kicad_version": "10.0.4",
        "unconnected_items": [],
        "violations": [
            {
                "type": "copper_edge_clearance",
                "severity": "error",
                "description": "edge",
                "items": [
                    {"description": "Segment on Edge.Cuts", "pos": {"x": 0.0, "y": 0.0}},
                    {"pos": {"x": 3.0, "y": 3.0}},  # sin "description"
                ],
            }
        ],
    }
    report = _build_report(payload, _iter_drc_violations(payload))
    v = report.violations[0]
    assert v.items[0].pos == (3.0, 3.0)


# --- diff_violations (F-D3-03, sesión 21) -------------------------------------


@pytest.mark.unit
def test_diff_violations_same_total_different_composition_is_not_zero() -> None:
    """El escenario EXACTO del D3: 3 violaciones tipo A pre-route + 3 tipo B
    post-route (mismo total, composición 100% distinta). La resta de totales
    vieja daría ``err_introducidos=0``; ``diff_violations`` debe detectar las
    3 introducidas y las 3 resueltas."""
    pre = tuple(
        Violation(rule="unconnected_items", severity="error", message="e", items=())
        for _ in range(3)
    )
    post = tuple(
        Violation(rule="hole_clearance", severity="error", message="e", items=()) for _ in range(3)
    )
    introducidas, resueltas, por_tipo = diff_violations(pre, post)
    assert introducidas == 3
    assert resueltas == 3
    assert por_tipo == {"hole_clearance": 3}


@pytest.mark.unit
def test_diff_violations_identical_violations_are_zero_introduced() -> None:
    """Las mismas violaciones (misma rule/pos/items) pre y post no cuentan
    como introducidas ni resueltas — persisten sin cambio."""
    v = Violation(
        rule="clearance",
        severity="error",
        message="e",
        items=(Item(ref="U1", net="GND", pos=(10.0, 20.0)),),
    )
    introducidas, resueltas, por_tipo = diff_violations((v,), (v,))
    assert introducidas == 0
    assert resueltas == 0
    assert por_tipo == {}


@pytest.mark.unit
def test_diff_violations_position_tolerance_0_1mm() -> None:
    """Un track ofensor que se desplaza <0.1mm al re-rutear no cuenta como
    una violación "nueva" — tolerancia de redondeo documentada en
    ``_violation_identity``."""
    pre = (
        Violation(
            rule="clearance",
            severity="error",
            message="e",
            items=(Item(ref="U1", net="GND", pos=(10.02, 20.04)),),
        ),
    )
    post = (
        Violation(
            rule="clearance",
            severity="error",
            message="e",
            items=(Item(ref="U1", net="GND", pos=(10.04, 20.02)),),
        ),
    )
    introducidas, resueltas, _ = diff_violations(pre, post)
    assert introducidas == 0
    assert resueltas == 0


@pytest.mark.unit
def test_diff_violations_ignores_warnings() -> None:
    """Sólo severidad ``error`` cuenta — mismo criterio que
    ``err_preexistentes``/``err_post`` en ``route_board``."""
    pre = ()
    post = (Violation(rule="silk_overlap", severity="warning", message="w", items=()),)
    introducidas, resueltas, por_tipo = diff_violations(pre, post)
    assert introducidas == 0
    assert resueltas == 0
    assert por_tipo == {}


@pytest.mark.unit
def test_diff_violations_duplicate_identities_use_multiset_not_set() -> None:
    """2 violaciones NUEVAS con la misma identidad deben contar 2, no
    colapsar en 1 (multiset, no set)."""
    pre = ()
    post = tuple(
        Violation(rule="clearance", severity="error", message="e", items=()) for _ in range(2)
    )
    introducidas, resueltas, por_tipo = diff_violations(pre, post)
    assert introducidas == 2
    assert resueltas == 0
    assert por_tipo == {"clearance": 2}
