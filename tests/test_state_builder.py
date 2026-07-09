"""Tests integration del constructor de estado contra fixtures reales.

- 001/002/003: el estado construido debe coincidir con ``ground_truth.json``.
- 004_real: multi-hoja → debe fallar con ``UNSUPPORTED_HIERARCHY``.

Requieren ``kicad-cli`` (Fase 0 lo verifica).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from kicad_mcp.bridge.state_builder import build_state
from kicad_mcp.errors import ErrorCode, KicadMcpError
from kicad_mcp.toon.schema import NormalizedState
from tests.conftest import mirror_fixture

FIXTURES = Path(__file__).parent / "fixtures"


def _state_to_comparable(state: NormalizedState) -> dict[str, Any]:
    components: dict[str, dict[str, Any]] = {}
    nets: dict[str, list[str]] = {}
    unconnected: list[str] = []
    for c in state.components:
        components[c.ref] = {"value": c.value, "lib": c.lib, "x": c.x, "y": c.y}
        for pin in c.pins:
            member = f"{c.ref}.{pin.p}"
            if pin.net is None:
                unconnected.append(member)
            else:
                nets.setdefault(pin.net, []).append(member)
    return {
        "components": components,
        "nets": {k: sorted(v) for k, v in nets.items()},
        "unconnected_pins": sorted(unconnected),
    }


def _ground_truth_to_comparable(gt: dict[str, Any]) -> dict[str, Any]:
    return {
        "components": {ref: {**data} for ref, data in gt["components"].items()},
        "nets": {k: sorted(v) for k, v in gt["nets"].items()},
        "unconnected_pins": sorted(gt.get("unconnected_pins", [])),
    }


@pytest.mark.integration
@pytest.mark.parametrize("fixture", ["001_basico", "002_medio", "003_grande"])
def test_state_builder_matches_ground_truth(fixture: str, tmp_path: Path) -> None:
    ground_truth = json.loads((FIXTURES / fixture / "ground_truth.json").read_text())
    project = mirror_fixture(FIXTURES / fixture, tmp_path / fixture)
    sch = project / "fixture.kicad_sch"

    state = build_state(sch.resolve(), snap=1)
    got = _state_to_comparable(state)
    expected = _ground_truth_to_comparable(ground_truth)

    assert got["components"].keys() == expected["components"].keys(), (
        f"componentes distintos: {set(got['components']) ^ set(expected['components'])}"
    )
    for ref, data in expected["components"].items():
        got_comp = got["components"][ref]
        assert got_comp["value"] == data["value"], ref
        assert got_comp["lib"] == data["lib"], ref
        assert got_comp["x"] == pytest.approx(data["x"]), ref
        assert got_comp["y"] == pytest.approx(data["y"]), ref
    assert got["nets"] == expected["nets"]
    assert got["unconnected_pins"] == expected["unconnected_pins"]


@pytest.mark.integration
def test_state_builder_refuses_hierarchical_project(tmp_path: Path) -> None:
    """El proyecto real (video / 004_real) es multi-hoja: debe fallar tipado."""
    if not (FIXTURES / "004_real" / "video.kicad_sch").exists():
        pytest.skip("fixture 004_real no disponible")
    project = mirror_fixture(FIXTURES / "004_real", tmp_path / "004")
    with pytest.raises(KicadMcpError) as excinfo:
        build_state((project / "video.kicad_sch").resolve(), snap=1)
    assert excinfo.value.code is ErrorCode.UNSUPPORTED_HIERARCHY
