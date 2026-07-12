"""Tests del encoder TOON v1.

- ``golden``: comparación byte-a-byte contra ``tests/golden/`` (frontera F1).
- ``unit``: transformación de una fixture (``tests/fixtures/001_basico``) al
  schema de entrada y verificación de la cabecera contra ``counts``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from kicad_mcp.errors import ErrorCode, KicadMcpError
from kicad_mcp.toon.encoder import encode, encode_delta, encode_state
from kicad_mcp.toon.schema import Component, NormalizedState, Pin

GOLDEN_DIR = Path(__file__).parent / "golden"
FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_state(path: Path) -> NormalizedState:
    """Carga un JSON con el schema de entrada del encoder (spec §1)."""
    with path.open() as f:
        return NormalizedState.model_validate(json.load(f))


@pytest.mark.golden
def test_golden_001_minimo_byte_por_byte() -> None:
    state = _load_state(GOLDEN_DIR / "001_minimo" / "input.json")
    expected = (GOLDEN_DIR / "001_minimo" / "expected.toon").read_bytes()
    got = encode_state(state).encode("utf-8")
    assert got == expected


@pytest.mark.golden
def test_golden_002_degradacion_byte_por_byte() -> None:
    state = _load_state(GOLDEN_DIR / "002_degradacion" / "input.json")
    params = json.loads((GOLDEN_DIR / "002_degradacion" / "params.json").read_text())
    expected = (GOLDEN_DIR / "002_degradacion" / "expected.toon").read_bytes()
    got = encode(state, max_tokens=params["max_tokens"]).encode("utf-8")
    assert got == expected


@pytest.mark.golden
def test_golden_003_delta_byte_por_byte() -> None:
    state = _load_state(GOLDEN_DIR / "003_delta" / "input.json")
    base = _load_state(GOLDEN_DIR / "003_delta" / "base.json")
    params = json.loads((GOLDEN_DIR / "003_delta" / "params.json").read_text())
    expected = (GOLDEN_DIR / "003_delta" / "expected.toon").read_bytes()
    got = encode_delta(
        state,
        base=base,
        focus_ref=params["focus_ref"],
        radius_mm=params["radius_mm"],
        base_snap=params["base_snap"],
    ).encode("utf-8")
    assert got == expected


@pytest.mark.golden
def test_golden_003_delta_is_deterministic_across_two_runs() -> None:
    """Sesión 05 T3: dos corridas seguidas del mismo golden ⇒ bytes idénticos.

    Verifica determinismo (sin dependencia de orden de inserción ni hash seed).
    """
    state = _load_state(GOLDEN_DIR / "003_delta" / "input.json")
    base = _load_state(GOLDEN_DIR / "003_delta" / "base.json")
    params = json.loads((GOLDEN_DIR / "003_delta" / "params.json").read_text())
    kwargs = {
        "base": base,
        "focus_ref": params["focus_ref"],
        "radius_mm": params["radius_mm"],
        "base_snap": params["base_snap"],
    }
    first = encode_delta(state, **kwargs)
    second = encode_delta(state, **kwargs)
    assert first == second


def _fixture_ground_truth_to_state(gt: dict[str, Any]) -> NormalizedState:
    """Transforma un ``ground_truth.json`` de fixtures al schema del encoder.

    El ground_truth expresa componentes y nets externamente (mapa net → refs);
    el schema del encoder pide pines por componente. Aquí invertimos el mapa.
    Los ``.kicad_sch`` de las fixtures no se cargan (regla del CLAUDE.md:
    procesar con código, no leerlos al contexto).
    """
    comp_pins: dict[str, list[Pin]] = {ref: [] for ref in gt["components"]}
    for net_name, members in gt["nets"].items():
        for member in members:
            ref, pin_id = member.split(".", 1)
            comp_pins[ref].append(Pin(p=pin_id, net=net_name))
    for member in gt.get("unconnected_pins", []):
        ref, pin_id = member.split(".", 1)
        comp_pins[ref].append(Pin(p=pin_id, net=None))
    components = tuple(
        Component(
            ref=ref,
            value=data["value"],
            lib=data["lib"],
            x=float(data["x"]),
            y=float(data["y"]),
            pins=tuple(comp_pins[ref]),
        )
        for ref, data in gt["components"].items()
    )
    return NormalizedState(kind="sch", snap=1, components=components)


@pytest.mark.unit
def test_encoder_raises_context_budget_impossible_when_no_level_fits() -> None:
    """Un estado modesto con ``max_tokens`` absurdamente bajo debe fallar tipado."""
    state = _load_state(GOLDEN_DIR / "002_degradacion" / "input.json")
    with pytest.raises(KicadMcpError) as excinfo:
        encode(state, max_tokens=1, focus_ref="U1", radius_mm=10.0)
    assert excinfo.value.code is ErrorCode.CONTEXT_BUDGET_IMPOSSIBLE
    assert "presupuesto mínimo" in excinfo.value.hint


@pytest.mark.unit
def test_encoder_header_matches_fixture_counts() -> None:
    """La cabecera del encoder respeta ``counts`` del ground_truth de la fixture 001."""
    gt_path = FIXTURE_DIR / "001_basico" / "ground_truth.json"
    gt = json.loads(gt_path.read_text())

    state = _fixture_ground_truth_to_state(gt)
    result = encode_state(state)

    header = result.splitlines()[0]
    expected_c = gt["counts"]["components"]
    expected_n = gt["counts"]["nets"]
    assert header == f"SCH|v1|{expected_c}c|{expected_n}n|snap:1", f"header inesperado: {header!r}"


# --- Sesión 11: cabecera enriquecida (F-01 área, F-03 bbox/outline pcb) -------


def _pcb_state(*refs_pos: tuple[str, float, float]) -> NormalizedState:
    comps = tuple(
        Component(ref=r, value="V", x=x, y=y, pins=(Pin(p="1", net="GND"),))
        for (r, x, y) in refs_pos
    )
    return NormalizedState(kind="pcb", snap=3, components=comps)


@pytest.mark.unit
def test_header_area_full_when_focus_requested_but_not_cropped() -> None:
    """F-01: focus sin recorte ⇒ ``area:full`` en la cabecera; snap sigue último."""
    state = _pcb_state(("U1", 0.0, 0.0), ("R1", 1.0, 1.0))
    out = encode(state, max_tokens=100000, focus_ref="U1")  # sin radius: no recorta
    header = out.splitlines()[0]
    assert "|area:full|snap:3" in header, header
    assert header.endswith("snap:3")


@pytest.mark.unit
def test_header_area_local_when_cropped() -> None:
    """F-01: focus+radius que recorta ⇒ ``area:rN@ref``.

    Un cluster lejano grande hace que sólo el nivel de foco (que resume lo
    de fuera del radio) quepa en el budget — ahí sí hay recorte.
    """
    specs = [("U1", 0.0, 0.0)]
    specs += [(f"C{i}", 400.0 + i, 400.0 + i) for i in range(1, 40)]
    state = _pcb_state(*specs)
    out = encode(state, max_tokens=260, focus_ref="U1", radius_mm=10.0)
    header = out.splitlines()[0]
    assert "area:r10@U1" in header, header
    assert "[FUERA_DE_AREA]" in out
    assert header.endswith("snap:3")


@pytest.mark.unit
def test_header_no_area_token_without_focus() -> None:
    """Sin foco pedido no hay token de área (invariante que preserva goldens)."""
    state = _pcb_state(("U1", 0.0, 0.0))
    header = encode(state, max_tokens=100000).splitlines()[0]
    assert "area:" not in header


@pytest.mark.unit
def test_header_pcb_bbox_and_outline() -> None:
    """F-03: bbox del board + outline en la cabecera pcb, antes de snap."""
    state = _pcb_state(("U1", 0.0, 0.0))
    out = encode(
        state,
        max_tokens=100000,
        board_bbox=(53.6, 56.5, 365.6, 163.2),
        outline="312.0x106.7mm",
    )
    header = out.splitlines()[0]
    assert "bbox:53.6,56.5;365.6,163.2" in header
    assert "outline:312.0x106.7mm" in header
    assert header.endswith("snap:3")  # snap SIEMPRE último


@pytest.mark.unit
def test_header_outline_none() -> None:
    state = _pcb_state(("U1", 0.0, 0.0))
    header = encode(state, max_tokens=100000, outline="none").splitlines()[0]
    assert "outline:none" in header
