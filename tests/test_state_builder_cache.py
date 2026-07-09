"""Tests del cache mtime de ``bridge.state_builder`` (unit, sin kicad-cli).

- Segundo llamado con mismo mtime ⇒ ``cache_hit=True`` y no reconstruye.
- ``os.utime`` cambia mtime ⇒ ``cache_hit=False`` y reconstruye.
- Cambio de ``snap`` sobre mtime idéntico ⇒ ``cache_hit=True`` y ``snap``
  refrescado (no reconstruye).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from kicad_mcp.bridge import state_builder
from kicad_mcp.bridge.netlist import Netlist, NetlistComponent
from kicad_mcp.bridge.sch_positions import Placement


class _RebuildCounter:
    """Reemplaza los I/O de state_builder por objetos deterministas y cuenta llamadas."""

    def __init__(self) -> None:
        self.netlist_calls = 0
        self.positions_calls = 0

    def netlist(self, schematic: Path) -> Netlist:
        self.netlist_calls += 1
        comp = NetlistComponent(ref="R1", value="10k", lib="Device:R", pin_ids=("1", "2"))
        return Netlist(
            components=(comp,),
            nets={"NET1": (("R1", "1"),)},
            unconnected_pins=(("R1", "2"),),
        )

    def positions(self, schematic: Path) -> tuple[Placement, ...]:
        self.positions_calls += 1
        return (Placement(ref="R1", x=1.0, y=2.0),)


@pytest.fixture
def sch_file(tmp_path: Path) -> Path:
    """Un ``.kicad_sch`` vacío en tmp; el contenido no importa (todo mockeado)."""
    sch = tmp_path / "fake.kicad_sch"
    sch.write_text("(kicad_sch)")
    return sch


@pytest.fixture(autouse=True)
def clear_state_cache() -> Any:
    """Aísla cada test del cache de sesiones previas."""
    state_builder.clear_cache()
    yield
    state_builder.clear_cache()


@pytest.mark.unit
def test_second_call_same_mtime_hits_cache(
    monkeypatch: pytest.MonkeyPatch, sch_file: Path
) -> None:
    counter = _RebuildCounter()
    monkeypatch.setattr(state_builder, "load_netlist", counter.netlist)
    monkeypatch.setattr(state_builder, "parse_root_positions", counter.positions)

    s1, hit1 = state_builder.build_state_cached(sch_file, snap=1)
    s2, hit2 = state_builder.build_state_cached(sch_file, snap=1)

    assert hit1 is False and hit2 is True
    assert counter.netlist_calls == 1
    assert counter.positions_calls == 1
    assert s1 == s2


@pytest.mark.unit
def test_mtime_change_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch, sch_file: Path
) -> None:
    counter = _RebuildCounter()
    monkeypatch.setattr(state_builder, "load_netlist", counter.netlist)
    monkeypatch.setattr(state_builder, "parse_root_positions", counter.positions)

    state_builder.build_state_cached(sch_file, snap=1)
    # Toca el mtime hacia adelante 2 s (evita colisión con la resolución del FS).
    stat = sch_file.stat()
    os.utime(sch_file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
    _, hit_after_touch = state_builder.build_state_cached(sch_file, snap=1)

    assert hit_after_touch is False
    assert counter.netlist_calls == 2
    assert counter.positions_calls == 2


@pytest.mark.unit
def test_snap_change_reuses_cache(
    monkeypatch: pytest.MonkeyPatch, sch_file: Path
) -> None:
    counter = _RebuildCounter()
    monkeypatch.setattr(state_builder, "load_netlist", counter.netlist)
    monkeypatch.setattr(state_builder, "parse_root_positions", counter.positions)

    s1, hit1 = state_builder.build_state_cached(sch_file, snap=1)
    s2, hit2 = state_builder.build_state_cached(sch_file, snap=7)

    assert hit1 is False and hit2 is True
    assert counter.netlist_calls == 1  # no rebuild
    assert s1.snap == 1
    assert s2.snap == 7
    assert s1.components == s2.components  # mismo estado, solo cambió snap
