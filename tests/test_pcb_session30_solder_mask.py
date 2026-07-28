"""Test integration de sesión 30 — P1 ``solder_mask_bridge`` en ANT1
(``docs/investigacion/30-solder-mask-ant1.md``, continuación de
``docs/investigacion/26-solder-mask-ant1.md``).

Gate del merge para el fix de ``enforce_hole_clearance``
(``src/kicad_mcp/bridge/ipc.py``): bump de ``_circle_vertices_mm`` de N=16 a
N=64 (compensación de apotema) + término de máscara (``max(hole_term,
mask_term)``). ``enforce_hole_clearance`` en sí requiere una conexión IPC
viva (kipy) y no puede exhibirse offline — este test valida la geometría
que el fix produce, corriendo el motor REAL de KiCad (``kicad-cli pcb drc
--refill-zones --save-board``) contra un keepout con la geometría exacta
que el código fijo calcularía. La lógica de selección de fórmula
(``max(hole_term, mask_term)``) tiene su propio unit test en
``tests/test_pcb_hole_clearance.py::test_enforce_hole_clearance_mask_term_dominates_when_larger``.

100% offline: no requiere KiCad GUI ni ``pcbnew`` — mismo patrón que
``tests/test_export.py::test_export_manufacturing_blocks_on_real_dirty_pcb``.
Nunca muta ``tests/fixtures/`` (regla de sesión 03, ``mirror_fixture``).
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

import pytest

from kicad_mcp.bridge.ipc import _HOLE_CLEARANCE_MARGIN_MM, _circle_vertices_mm
from tests.conftest import mirror_fixture

FIXTURES = Path(__file__).parent / "fixtures"
ANT1_CENTER_MM = (144.5, 89.0)
ANT1_COPPER_RADIUS_MM = 1.5  # (size 3 3) en el fixture
KEEPOUT_ZONE_NAME = "__kicadmcp_hc__pad_ANT1_1"

_PAD_TO_MASK_RE = re.compile(r"\(pad_to_mask_clearance\s+(-?[0-9.]+)\)")


def _set_pad_to_mask_clearance(pcb_path: Path, m_mm: float) -> None:
    text = pcb_path.read_text()
    text, n_sub = _PAD_TO_MASK_RE.subn(f"(pad_to_mask_clearance {m_mm})", text)
    assert n_sub == 1, f"esperaba 1 match de pad_to_mask_clearance, encontré {n_sub}"
    pcb_path.write_text(text)


def _replace_keepout_polygon(pcb_path: Path, *, layer: str, radius_mm: float) -> None:
    """Reemplaza el keepout B.Cu de ANT1 por el polígono que produciría el
    ``enforce_hole_clearance`` fijo: mismos vértices que ``_circle_vertices_mm``
    (N=64 default, sesión 30) al radio pedido."""
    text = pcb_path.read_text()
    marker = f'(name "{KEEPOUT_ZONE_NAME}")'
    search_from = 0
    while True:
        name_idx = text.find(marker, search_from)
        assert name_idx != -1, f"no encontré zona {KEEPOUT_ZONE_NAME!r}"
        zone_start = text.rfind("(zone", 0, name_idx)
        layer_match = re.search(r'\(layer "([^"]+)"\)', text[zone_start:name_idx])
        if layer_match and layer_match.group(1) == layer:
            break
        search_from = name_idx + len(marker)

    poly_idx = text.find("(polygon", name_idx)
    pts_start = text.find("(pts", poly_idx)
    depth = 0
    pts_end = pts_start
    for i in range(pts_start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                pts_end = i + 1
                break

    vertices = _circle_vertices_mm(ANT1_CENTER_MM[0], ANT1_CENTER_MM[1], radius_mm)
    pts_str = " ".join(f"(xy {round(x, 6)} {round(y, 6)})" for x, y in vertices)
    new_block = f"(pts\n\t\t\t\t{pts_str}\n\t\t\t)"
    text = text[:pts_start] + new_block + text[pts_end:]
    pcb_path.write_text(text)


def _run_drc_refill_save(pcb_path: Path) -> dict:
    out_json = pcb_path.with_suffix(".drc.json")
    cmd = [
        "kicad-cli",
        "pcb",
        "drc",
        "--format",
        "json",
        "--severity-all",
        "--refill-zones",
        "--save-board",
        "-o",
        str(out_json),
        str(pcb_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    assert proc.returncode == 0, f"kicad-cli falló: {proc.stderr}"
    return json.loads(out_json.read_text())


def _ant1_vs_gnd_solder_mask_bridge(payload: dict) -> bool:
    for v in payload.get("violations", []):
        if v.get("type") != "solder_mask_bridge":
            continue
        descs = " ".join(it.get("description", "") for it in v.get("items", []))
        if "ANT1" in descs and "GND" in descs:
            return True
    return False


@pytest.mark.integration
@pytest.mark.parametrize("m_mm", [0.0, 0.20, 0.22, 0.25, 0.30])
def test_fixed_keepout_geometry_resolves_solder_mask_bridge(tmp_path: Path, m_mm: float) -> None:
    """Barrido de ``pad_to_mask_clearance`` (D-30.1, protección contra
    regresiones): con el keepout dimensionado por la fórmula fija
    (``max(hole_term, mask_term)`` + N=64), 0 violaciones ``solder_mask_bridge``
    de ANT1 contra ``Zone [GND]`` en todo el rango 0.0-0.30mm.

    ``min_hole_clearance``=0.25 (fixture) -> hole_term = 1.0+0.25+0.02=1.27mm.
    mask_term = 1.5 + m_mm + 0.02. El máximo se inyecta directamente (no
    pasa por ``load_project_rules``/IPC — eso lo cubre el unit test de
    ``enforce_hole_clearance``); acá se valida que ESA geometría resuelve
    el bug contra el motor real de KiCad.
    """
    project = mirror_fixture(FIXTURES / "despertador-routed", tmp_path / f"m{m_mm}")
    pcb_path = project / "despertador_inteligente.kicad_pcb"

    _set_pad_to_mask_clearance(pcb_path, m_mm)

    hole_term_mm = 1.0 + 0.25 + _HOLE_CLEARANCE_MARGIN_MM
    mask_term_mm = ANT1_COPPER_RADIUS_MM + m_mm + _HOLE_CLEARANCE_MARGIN_MM
    radius_mm = max(hole_term_mm, mask_term_mm)
    _replace_keepout_polygon(pcb_path, layer="B.Cu", radius_mm=radius_mm)

    payload = _run_drc_refill_save(pcb_path)

    assert not _ant1_vs_gnd_solder_mask_bridge(payload), (
        f"m_mm={m_mm} radius_mm={radius_mm} apotema="
        f"{radius_mm * math.cos(math.pi / 64)} — violación no resuelta"
    )


@pytest.mark.integration
def test_stock_fixture_pad_to_mask_zero_unaffected(tmp_path: Path) -> None:
    """Control D-30.1: el flujo canónico (fixture con ``pad_to_mask_clearance``
    default 0, keepout SIN modificar) sigue sin violación — el fix no
    introduce regresión en el caso que ya funcionaba (D6/D7)."""
    project = mirror_fixture(FIXTURES / "despertador-routed", tmp_path / "control")
    pcb_path = project / "despertador_inteligente.kicad_pcb"

    payload = _run_drc_refill_save(pcb_path)

    assert not _ant1_vs_gnd_solder_mask_bridge(payload)
