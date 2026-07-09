"""Tests unit de los parsers del bridge.

- ``sch_positions.parse_root_positions`` sobre snippets sintéticos.
- Detección de ``UNSUPPORTED_HIERARCHY`` cuando hay ``(sheet ...)`` en el
  nivel raíz.
- ``netlist._parse_netlist_xml`` sobre un XML mínimo commiteado en
  ``tests/data/`` (dato de test, no golden).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.bridge.netlist import _parse_netlist_xml
from kicad_mcp.bridge.sch_positions import parse_root_positions
from kicad_mcp.errors import ErrorCode, KicadMcpError

DATA_DIR = Path(__file__).parent / "data"


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


@pytest.mark.unit
def test_parse_positions_extracts_ref_and_at(tmp_path: Path) -> None:
    sch = _write(
        tmp_path,
        "sample.kicad_sch",
        """
(kicad_sch (version 20230121) (generator test)
  (symbol (lib_id "Device:R") (at 100.5 60.0 90) (unit 1)
    (property "Reference" "R1" (at 0 0 0))
    (property "Value" "10k" (at 0 0 0)))
  (symbol (lib_id "Device:C") (at 120 80) (unit 1)
    (property "Reference" "C1" (at 0 0 0))
    (property "Value" "100nF" (at 0 0 0))))
""",
    )
    placements = parse_root_positions(sch)
    by_ref = {p.ref: p for p in placements}
    assert set(by_ref) == {"R1", "C1"}
    assert by_ref["R1"].x == pytest.approx(100.5)
    assert by_ref["R1"].y == pytest.approx(60.0)
    assert by_ref["R1"].rot == pytest.approx(90.0)
    assert by_ref["C1"].rot == pytest.approx(0.0)


@pytest.mark.unit
def test_parse_positions_rejects_hierarchical_sheet(tmp_path: Path) -> None:
    sch = _write(
        tmp_path,
        "hier.kicad_sch",
        """
(kicad_sch (version 20230121) (generator test)
  (symbol (lib_id "Device:R") (at 100 60 0) (unit 1)
    (property "Reference" "R1" (at 0 0 0)))
  (sheet (at 200 100) (size 40 40)
    (property "Sheetname" "sub" (at 0 0 0))
    (property "Sheetfile" "sub.kicad_sch" (at 0 0 0))))
""",
    )
    with pytest.raises(KicadMcpError) as excinfo:
        parse_root_positions(sch)
    assert excinfo.value.code is ErrorCode.UNSUPPORTED_HIERARCHY


@pytest.mark.unit
def test_parse_positions_ignores_lib_symbols_nested_symbols(tmp_path: Path) -> None:
    """Los ``(symbol "LIB:X" ...)`` dentro de ``(lib_symbols ...)`` no son placements."""
    sch = _write(
        tmp_path,
        "libnest.kicad_sch",
        """
(kicad_sch (version 20230121) (generator test)
  (lib_symbols
    (symbol "Device:R" (pin_names (offset 0)) (in_bom yes) (on_board yes)
      (property "Reference" "R" (at 0 0 0))))
  (symbol (lib_id "Device:R") (at 50 50 0) (unit 1)
    (property "Reference" "R1" (at 0 0 0))
    (property "Value" "1k" (at 0 0 0))))
""",
    )
    placements = parse_root_positions(sch)
    assert [p.ref for p in placements] == ["R1"]


@pytest.mark.unit
def test_parse_netlist_xml_minimal() -> None:
    """Parseo del XML mínimo commiteado en tests/data/."""
    netlist = _parse_netlist_xml(DATA_DIR / "minimal_netlist.xml")
    refs = {c.ref for c in netlist.components}
    assert refs == {"R1", "C1", "U1"}
    r1 = next(c for c in netlist.components if c.ref == "R1")
    assert r1.value == "10k"
    assert r1.lib == "Device:R"
    assert r1.pin_ids == ("1", "2")
    assert set(netlist.nets["VCC"]) == {("R1", "1"), ("U1", "1")}
    assert set(netlist.nets["GND"]) == {("C1", "2"), ("U1", "2")}
    # El pin sin conectar aparece como red 'unconnected-*' → mapa unconnected.
    assert ("U1", "3") in netlist.unconnected_pins
    assert not any(name.startswith("unconnected-") for name in netlist.nets)
