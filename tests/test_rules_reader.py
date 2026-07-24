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


def _write_pcb_with_setup(
    tmp_path: Path, pad_to_mask_clearance: float, *, stem: str = "proj"
) -> Path:
    """``.kicad_pcb`` con un ``(setup ...)`` real (sesión 26) — sin ``.kicad_pro``
    hermano, para aislar la lectura del segundo archivo de la del primero."""
    pcb = tmp_path / f"{stem}.kicad_pcb"
    pcb.write_text(
        f"(kicad_pcb\n\t(setup\n\t\t(pad_to_mask_clearance {pad_to_mask_clearance})\n\t)\n)",
        encoding="utf-8",
    )
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


# --- solder_mask_to_copper_clearance (.kicad_pro) + pad_to_mask_clearance
# (.kicad_pcb) — sesión 26, F-P1-solder-mask ------------------------------------


@pytest.mark.unit
def test_solder_mask_to_copper_clearance_from_design_settings_rules(tmp_path: Path) -> None:
    pcb = _write_pro(
        tmp_path,
        {"design_settings": {"rules": {"solder_mask_to_copper_clearance": 0.15}}},
    )
    rules = load_project_rules(pcb)
    assert rules.solder_mask_to_copper_clearance_mm == 0.15


@pytest.mark.unit
def test_solder_mask_to_copper_clearance_from_board_design_settings_rules(tmp_path: Path) -> None:
    pcb = _write_pro(
        tmp_path,
        {"board": {"design_settings": {"rules": {"solder_mask_to_copper_clearance": 0.1}}}},
    )
    rules = load_project_rules(pcb)
    assert rules.solder_mask_to_copper_clearance_mm == 0.1


@pytest.mark.unit
def test_solder_mask_to_copper_clearance_missing_defaults_to_zero(tmp_path: Path) -> None:
    pcb = _write_pro(tmp_path, {"design_settings": {"rules": {}}})
    rules = load_project_rules(pcb)
    assert rules.solder_mask_to_copper_clearance_mm == 0.0


@pytest.mark.unit
def test_pad_to_mask_clearance_read_from_kicad_pcb_setup(tmp_path: Path) -> None:
    """``pad_to_mask_clearance`` vive en el .kicad_pcb, NO en el .kicad_pro —
    debe leerse aunque no haya ningún .kicad_pro en el directorio."""
    pcb = _write_pcb_with_setup(tmp_path, 0.6)
    rules = load_project_rules(pcb)
    assert rules.pad_to_mask_clearance_mm == 0.6


@pytest.mark.unit
def test_pad_to_mask_clearance_missing_defaults_to_zero(tmp_path: Path) -> None:
    pcb = tmp_path / "orphan.kicad_pcb"
    pcb.write_text("(kicad_pcb)", encoding="utf-8")
    rules = load_project_rules(pcb)
    assert rules.pad_to_mask_clearance_mm == 0.0


@pytest.mark.unit
def test_pad_to_mask_clearance_and_pro_fields_both_read_together(tmp_path: Path) -> None:
    """Caso real (fixture despertador): .kicad_pro con netclasses/hole
    clearance Y .kicad_pcb con pad_to_mask_clearance, ambos aportando al
    mismo ``ProjectRules`` — no son mutuamente excluyentes."""
    pcb = _write_pro(
        tmp_path,
        {"design_settings": {"rules": {"min_hole_clearance": 0.3}}},
    )
    pcb.write_text(
        "(kicad_pcb\n\t(setup\n\t\t(pad_to_mask_clearance 0.25)\n\t)\n)", encoding="utf-8"
    )
    rules = load_project_rules(pcb)
    assert rules.min_hole_clearance_mm == 0.3
    assert rules.pad_to_mask_clearance_mm == 0.25


@pytest.mark.unit
def test_cache_reloads_when_kicad_pcb_setup_changes_only(tmp_path: Path) -> None:
    """El cache debe invalidar por cambios en el .kicad_pcb, no sólo en el
    .kicad_pro — motivación central del cache de dos archivos (sesión 26)."""
    pcb = _write_pcb_with_setup(tmp_path, 0.0)
    first = load_project_rules(pcb)
    assert first.pad_to_mask_clearance_mm == 0.0

    time.sleep(0.01)
    pcb.write_text(
        "(kicad_pcb\n\t(setup\n\t\t(pad_to_mask_clearance 0.8)\n\t)\n)", encoding="utf-8"
    )
    second = load_project_rules(pcb)
    assert second.pad_to_mask_clearance_mm == 0.8


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
