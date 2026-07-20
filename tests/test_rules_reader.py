"""Tests unit de ``bridge.rules_reader`` (sesión 17, P2.1).

Lectura pura de disco del ``.kicad_pro`` — sin IPC ni kicad-cli, todo con
archivos temporales (``tmp_path``). Cubre las dos ubicaciones divergentes del
edge clearance, la resolución de netclass por net, y la degradación graceful
ante archivo ausente/inválido/incompleto.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from kicad_mcp.bridge.rules_reader import load_project_rules


def _write_pro(tmp_path: Path, payload: dict, *, stem: str = "proj") -> Path:
    pcb = tmp_path / f"{stem}.kicad_pcb"
    pcb.write_text("(kicad_pcb)", encoding="utf-8")
    pro = tmp_path / f"{stem}.kicad_pro"
    pro.write_text(json.dumps(payload), encoding="utf-8")
    return pcb


# --- edge clearance: ambas ubicaciones -----------------------------------------


@pytest.mark.unit
def test_edge_clearance_from_design_settings_rules(tmp_path: Path) -> None:
    """Schema v3 (despertador): design_settings.rules.min_copper_edge_clearance."""
    pcb = _write_pro(
        tmp_path,
        {"design_settings": {"rules": {"min_copper_edge_clearance": 0.5}}},
    )
    rules = load_project_rules(pcb)
    assert rules.min_copper_edge_clearance_mm == 0.5


@pytest.mark.unit
def test_edge_clearance_from_board_design_settings_rules(tmp_path: Path) -> None:
    """Fixture 004_real (video): board.design_settings.rules.min_copper_edge_clearance."""
    pcb = _write_pro(
        tmp_path,
        {"board": {"design_settings": {"rules": {"min_copper_edge_clearance": 0.35}}}},
    )
    rules = load_project_rules(pcb)
    assert rules.min_copper_edge_clearance_mm == 0.35


@pytest.mark.unit
def test_edge_clearance_missing_field_falls_back_to_default(tmp_path: Path) -> None:
    pcb = _write_pro(tmp_path, {"design_settings": {"rules": {}}})
    rules = load_project_rules(pcb)
    assert rules.min_copper_edge_clearance_mm == 0.2  # default documentado


# --- netclasses + resolución por net -------------------------------------------


_TWO_CLASSES_PAYLOAD = {
    "net_settings": {
        "classes": [
            {
                "name": "Default",
                "clearance": 0.2,
                "track_width": 0.2,
                "via_diameter": 0.6,
                "via_drill": 0.3,
            },
            {
                "name": "pwr",
                "clearance": 0.3,
                "track_width": 0.4,
                "via_diameter": 0.8,
                "via_drill": 0.4,
            },
        ],
        "netclass_assignments": {"/RESET": "pwr"},
        "netclass_patterns": [{"netclass": "pwr", "pattern": "+*V"}],
    }
}


@pytest.mark.unit
def test_classes_parsed_with_all_fields(tmp_path: Path) -> None:
    pcb = _write_pro(tmp_path, _TWO_CLASSES_PAYLOAD)
    rules = load_project_rules(pcb)
    names = {c.name for c in rules.classes}
    assert names == {"Default", "pwr"}
    pwr = next(c for c in rules.classes if c.name == "pwr")
    assert (pwr.clearance_mm, pwr.track_width_mm, pwr.via_diameter_mm, pwr.via_drill_mm) == (
        0.3,
        0.4,
        0.8,
        0.4,
    )


@pytest.mark.unit
def test_class_for_net_explicit_assignment_wins(tmp_path: Path) -> None:
    pcb = _write_pro(tmp_path, _TWO_CLASSES_PAYLOAD)
    rules = load_project_rules(pcb)
    assert rules.class_for_net("/RESET").name == "pwr"


@pytest.mark.unit
def test_class_for_net_pattern_match(tmp_path: Path) -> None:
    pcb = _write_pro(tmp_path, _TWO_CLASSES_PAYLOAD)
    rules = load_project_rules(pcb)
    assert rules.class_for_net("+3.3V").name == "pwr"


@pytest.mark.unit
def test_class_for_net_falls_back_to_default_class(tmp_path: Path) -> None:
    pcb = _write_pro(tmp_path, _TWO_CLASSES_PAYLOAD)
    rules = load_project_rules(pcb)
    assert rules.class_for_net("GND").name == "Default"


@pytest.mark.unit
def test_class_for_net_no_classes_at_all_uses_fixed_fallback(tmp_path: Path) -> None:
    """Sin net_settings.classes ⇒ preserva el piso 0.2mm/0.25mm previo a la 17."""
    pcb = _write_pro(tmp_path, {})
    rules = load_project_rules(pcb)
    fallback = rules.class_for_net("anything")
    assert fallback.clearance_mm == 0.2
    assert fallback.track_width_mm == 0.25


# --- degradación graceful -------------------------------------------------------


@pytest.mark.unit
def test_missing_kicad_pro_returns_fallback(tmp_path: Path) -> None:
    pcb = tmp_path / "orphan.kicad_pcb"
    pcb.write_text("(kicad_pcb)", encoding="utf-8")
    rules = load_project_rules(pcb)
    assert rules.min_copper_edge_clearance_mm == 0.2
    assert rules.classes == ()


@pytest.mark.unit
def test_malformed_json_returns_fallback(tmp_path: Path) -> None:
    pcb = tmp_path / "bad.kicad_pcb"
    pcb.write_text("(kicad_pcb)", encoding="utf-8")
    (tmp_path / "bad.kicad_pro").write_text("{not valid json", encoding="utf-8")
    rules = load_project_rules(pcb)
    assert rules.min_copper_edge_clearance_mm == 0.2


@pytest.mark.unit
def test_ambiguous_directory_multiple_pro_files_returns_fallback(tmp_path: Path) -> None:
    """Dos .kicad_pro sin .kicad_pcb hermano exacto ⇒ no adivina, cae al fallback."""
    pcb = tmp_path / "board.kicad_pcb"
    pcb.write_text("(kicad_pcb)", encoding="utf-8")
    (tmp_path / "other_a.kicad_pro").write_text("{}", encoding="utf-8")
    (tmp_path / "other_b.kicad_pro").write_text("{}", encoding="utf-8")
    rules = load_project_rules(pcb)
    assert rules.min_copper_edge_clearance_mm == 0.2


# --- cache por mtime -------------------------------------------------------------


@pytest.mark.unit
def test_cache_reloads_when_kicad_pro_mtime_and_size_change(tmp_path: Path) -> None:
    pcb = _write_pro(tmp_path, {"design_settings": {"rules": {"min_copper_edge_clearance": 0.5}}})
    first = load_project_rules(pcb)
    assert first.min_copper_edge_clearance_mm == 0.5

    pro_path = pcb.with_suffix(".kicad_pro")
    time.sleep(0.01)
    pro_path.write_text(
        json.dumps({"design_settings": {"rules": {"min_copper_edge_clearance": 0.9999}}}),
        encoding="utf-8",
    )
    second = load_project_rules(pcb)
    assert second.min_copper_edge_clearance_mm == 0.9999
