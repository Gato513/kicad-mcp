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

from kicad_mcp.bridge.ipc import (
    BoardHandle,
    FootprintData,
    FootprintPadData,
    IpcBridge,
    Mm,
)
from kicad_mcp.bridge.state_builder import (
    build_state,
    build_state_cached,
    build_state_from_board,
)
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


# --- build_state_from_board (sesión 05 T5) ------------------------------------


class _RecordingBridge(IpcBridge):
    """Bridge que devuelve datos preconfigurados en ``snapshot_footprints``.

    No abre socket ni instancia kipy: reproduce el mínimo estado y
    reemplaza el método consumido por ``build_state_from_board``.
    """

    def __init__(self, snapshot: tuple[FootprintData, ...]) -> None:
        import threading

        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._snapshot = snapshot
        self.calls = 0

    def snapshot_footprints(  # type: ignore[override]
        self, board: BoardHandle
    ) -> tuple[FootprintData, ...]:
        self.calls += 1
        return self._snapshot


@pytest.mark.unit
def test_build_state_from_board_produces_pcb_state_with_pins() -> None:
    """El nuevo path in-memory materializa un ``NormalizedState`` kind=pcb."""
    snapshot = (
        FootprintData(
            ref="U1",
            value="STM32",
            x_mm=Mm(100.0),
            y_mm=Mm(50.0),
            pads=(
                FootprintPadData(number="1", net_name="3V3"),
                FootprintPadData(number="8", net_name="GND"),
            ),
        ),
        FootprintData(
            ref="C1",
            value="100nF",
            x_mm=Mm(105.0),
            y_mm=Mm(80.0),
            pads=(
                FootprintPadData(number="1", net_name="3V3"),
                FootprintPadData(number="2", net_name=None),  # flotante
            ),
        ),
    )
    bridge = _RecordingBridge(snapshot)
    state = build_state_from_board(bridge, BoardHandle(_raw=object()))

    assert state.kind == "pcb"
    assert state.snap == 0  # el llamador (store.register) lo sobreescribe
    refs = {c.ref for c in state.components}
    assert refs == {"U1", "C1"}
    u1 = next(c for c in state.components if c.ref == "U1")
    assert u1.value == "STM32"
    assert u1.x == 100.0 and u1.y == 50.0
    assert [(pin.p, pin.net) for pin in u1.pins] == [("1", "3V3"), ("8", "GND")]
    c1 = next(c for c in state.components if c.ref == "C1")
    assert c1.pins[1].net is None, "pad sin net_name ⇒ Pin.net = None"
    assert bridge.calls == 1


@pytest.mark.unit
def test_build_state_from_board_handles_empty_board() -> None:
    """Board vacío ⇒ estado sin componentes (no falla)."""
    bridge = _RecordingBridge(snapshot=())
    state = build_state_from_board(bridge, BoardHandle(_raw=object()))
    assert state.kind == "pcb"
    assert state.components == ()


@pytest.mark.integration
def test_state_builder_refuses_hierarchical_project(tmp_path: Path) -> None:
    """El proyecto real (video / 004_real) es multi-hoja: debe fallar tipado."""
    if not (FIXTURES / "004_real" / "video.kicad_sch").exists():
        pytest.skip("fixture 004_real no disponible")
    project = mirror_fixture(FIXTURES / "004_real", tmp_path / "004")
    with pytest.raises(KicadMcpError) as excinfo:
        build_state((project / "video.kicad_sch").resolve(), snap=1)
    assert excinfo.value.code is ErrorCode.UNSUPPORTED_HIERARCHY


@pytest.mark.unit
def test_rebuild_ignores_pseudo_symbols_in_positions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R13: ``#PWR``/``#FLG`` están en el .kicad_sch pero no en el netlist; no
    deben disparar ``KICAD_CLI_FAILED`` (ni siquiera repetidos, p. ej. ``#PWR?``)."""
    from kicad_mcp.bridge import state_builder as sb
    from kicad_mcp.bridge.netlist import Netlist, NetlistComponent
    from kicad_mcp.bridge.sch_positions import Placement

    placements = (
        Placement(ref="R1", x=10.0, y=20.0),
        Placement(ref="#PWR01", x=1.0, y=1.0),
        Placement(ref="#PWR?", x=2.0, y=2.0),
        Placement(ref="#PWR?", x=3.0, y=3.0),
        Placement(ref="#FLG01", x=4.0, y=4.0),
    )
    netlist = Netlist(
        components=(NetlistComponent(ref="R1", value="10k", lib="Device:R", pin_ids=("1", "2")),),
        nets={"GND": (("R1", "1"),)},
    )
    monkeypatch.setattr(sb, "parse_root_positions", lambda _p: placements)
    monkeypatch.setattr(sb, "load_netlist", lambda _p: netlist)

    state = sb._rebuild(tmp_path / "x.kicad_sch", snap=1)
    assert [c.ref for c in state.components] == ["R1"]


@pytest.mark.unit
def test_rebuild_still_flags_real_ref_missing_from_netlist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """El filtro es sólo para ``#``: un ref real sin netlist sigue siendo error."""
    from kicad_mcp.bridge import state_builder as sb
    from kicad_mcp.bridge.netlist import Netlist
    from kicad_mcp.bridge.sch_positions import Placement

    monkeypatch.setattr(sb, "parse_root_positions", lambda _p: (Placement(ref="R9", x=0, y=0),))
    monkeypatch.setattr(sb, "load_netlist", lambda _p: Netlist(components=()))
    with pytest.raises(KicadMcpError) as excinfo:
        sb._rebuild(tmp_path / "x.kicad_sch", snap=1)
    assert excinfo.value.code is ErrorCode.KICAD_CLI_FAILED
    assert "R9" in excinfo.value.hint


_POWER_LIB = """(symbol "power:GND" (power) (pin_names (offset 0)) (in_bom no) (on_board no)
      (property "Reference" "#PWR" (at 0 -6.35 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "GND" (at 0 -3.81 0) (effects (font (size 1.27 1.27))))
      (symbol "GND_1_1" (pin power_in line (at 0 0 270) (length 0) hide
        (name "GND" (effects (font (size 1.27 1.27))))
        (number "1" (effects (font (size 1.27 1.27)))))))
    """
_POWER_INSTANCE = """  (symbol (lib_id "power:GND") (at 127 90 0) (unit 1)
    (in_bom no) (on_board no) (uuid 00000000-0000-0000-0000-0000000000aa)
    (property "Reference" "#PWR01" (at 127 96 0) (effects (font (size 1.27 1.27)) hide))
    (property "Value" "GND" (at 127 94 0) (effects (font (size 1.27 1.27))))
    (pin "1" (uuid 00000000-0000-0000-0000-0000000000ab)))
"""


@pytest.mark.integration
def test_build_state_accepts_power_symbol_with_real_kicad_cli(tmp_path: Path) -> None:
    """R13 end-to-end: 001_basico + un ``power:GND`` (#PWR01) construye estado."""
    project = mirror_fixture(FIXTURES / "001_basico", tmp_path / "pwr")
    sch = (project / "fixture.kicad_sch").resolve()
    text = sch.read_text(encoding="utf-8")
    text = text.replace("(lib_symbols", "(lib_symbols\n    " + _POWER_LIB, 1)
    end = text.rstrip().rfind(")")
    sch.write_text(text[:end] + _POWER_INSTANCE + text[end:], encoding="utf-8")

    state, _ = build_state_cached(sch, snap=1)
    refs = {c.ref for c in state.components}
    assert "#PWR01" not in refs
    assert {"U1", "R1", "R2", "C1", "J1"} <= refs
