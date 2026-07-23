"""Tests unit de sesión 21 — F-D3-01/F-D3-03: ``enforce_hole_clearance``.

Regresión del bug del Dogfooding 3: ``add_zone``/``fill_zones``/el refill
interno de ``route_board`` podían dejar 0.0000mm de clearance contra
agujeros PTH/NPTH o vías de otro net (``docs/dogfooding/dogfood3-fricciones.md``
F-01/F-03). La investigación de sesión 21
(``docs/investigacion/21-fill-zones-holes.md``) no logró aislar la causa
exacta dentro de kipy/KiCad — el humano decidió (``AskUserQuestion``) un
workaround post-fill defensivo: proteger PROACTIVAMENTE cada agujero ajeno
con un keepout de cobre (mecanismo ya confirmado correcto por el
workaround manual del D3) y refillear de nuevo.

Estos tests ejercitan ``IpcBridge.enforce_hole_clearance``/``list_pad_holes``
en aislamiento, con un ``raw_board`` fake liviano (duck-typed, sin kipy real
más que los tipos que SÍ son construibles standalone — ``Zone``,
``ZoneType``, ``PadType`` — confirmados sin conexión IPC). No toca la red
(regla #3 de CLAUDE.md); ``kipy`` en sí es una dependencia real del proyecto
(no un mock), así que estos tests validan la lógica real de
``enforce_hole_clearance`` construyendo objetos ``Zone`` reales para las
protecciones nuevas, sólo fakeando el ``raw_board`` que las recibe.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from kipy.proto.board.board_types_pb2 import PadType, ZoneType

from kicad_mcp.bridge.ipc import BoardHandle, IpcBridge


class _Vec2:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class _Net:
    def __init__(self, name: str) -> None:
        self.name = name


class _Id:
    def __init__(self, value: str) -> None:
        self.value = value


class _Drill:
    def __init__(self, dia_nm: int) -> None:
        self.diameter = _Vec2(dia_nm, dia_nm)


class _Padstack:
    def __init__(self, dia_nm: int) -> None:
        self.drill = _Drill(dia_nm)


class _Pad:
    def __init__(
        self,
        number: str,
        net_name: str | None,
        x_nm: int,
        y_nm: int,
        dia_nm: int,
        pad_type: int,
    ) -> None:
        self.number = number
        self.net = _Net(net_name) if net_name else _Net("")
        self.position = _Vec2(x_nm, y_nm)
        self.padstack = _Padstack(dia_nm)
        self.pad_type = pad_type


class _FootprintDef:
    def __init__(self, pads: list[_Pad]) -> None:
        self.pads = pads


class _Text:
    def __init__(self, value: str) -> None:
        self.value = value


class _RefField:
    def __init__(self, ref: str) -> None:
        self.text = _Text(ref)


class _Footprint:
    def __init__(self, ref: str, pads: list[_Pad]) -> None:
        self.reference_field = _RefField(ref)
        self.definition = _FootprintDef(pads)


class Via:  # nombre EXACTO "Via" — enforce_hole_clearance filtra por
    # ``type(it).__name__ == "Via"`` (mismo patrón que _is_copper_item).
    def __init__(self, net_name: str | None, x_nm: int, y_nm: int, drill_dia_nm: int, kiid: str):
        self.net = _Net(net_name) if net_name else _Net("")
        self.position = _Vec2(x_nm, y_nm)
        self.drill_diameter = drill_dia_nm
        self.id = _Id(kiid)


class _NotAVia:
    """Track no-vía en ``get_tracks()`` — debe ser ignorado por el filtro."""

    def __init__(self) -> None:
        self.net = _Net("GND")


class _FakeExistingZone:
    """Zona de cobre EXISTENTE fake — sólo los atributos que
    ``enforce_hole_clearance`` lee de una zona ya presente en el board
    (``type``/``name``/``net``/``layers``). Las zonas NUEVAS que el método
    crea sí son ``kipy.board_types.Zone`` reales (ver aserciones)."""

    def __init__(self, ztype: int, name: str, net_name: str | None, layers: list[int]) -> None:
        self.type = ztype
        self.name = name
        self.net = _Net(net_name) if net_name else _Net("")
        self.layers = layers


class _FakeRawBoard:
    def __init__(
        self,
        zones: list[object],
        footprints: list[_Footprint],
        tracks: list[object],
    ) -> None:
        self._zones = list(zones)
        self._footprints = footprints
        self._tracks = tracks
        self.refill_calls = 0

    def get_zones(self) -> list[object]:
        return list(self._zones)

    def get_footprints(self) -> list[_Footprint]:
        return list(self._footprints)

    def get_tracks(self) -> list[object]:
        return list(self._tracks)

    def create_items(self, item: object) -> list[object]:
        self._zones.append(item)
        return []

    def remove_items(self, items: object) -> None:
        to_remove = items if isinstance(items, list) else [items]
        self._zones = [z for z in self._zones if z not in to_remove]

    def refill_zones(self) -> None:
        self.refill_calls += 1


def _bridge() -> IpcBridge:
    """``IpcBridge`` sin conexión real (mismo patrón que los ``_FakeBridge``
    de otros tests): construida sin ``__init__`` real, sólo los atributos
    que ``_detect_restart``/``_supervise``/``_lock`` necesitan."""
    bridge = IpcBridge.__new__(IpcBridge)
    bridge._client = None  # type: ignore[attr-defined]
    bridge._instance_token = None  # type: ignore[attr-defined]
    bridge._lock = threading.Lock()  # type: ignore[attr-defined]
    return bridge


LAYER_B_CU = 2  # BL_B_Cu real (no importa el valor exacto para el test)


@pytest.mark.unit
def test_enforce_hole_clearance_protects_foreign_pth_and_npth() -> None:
    """Board con: zona GND existente, un pad PTH de net_a (ajeno) y un pad
    NPTH sin net (siempre ajeno, mecánico) — ambos deben quedar protegidos
    con un keepout cada uno, dimensionado por ``min_hole_clearance``."""
    zone = _FakeExistingZone(ZoneType.ZT_COPPER, "GND_plane", "GND", [LAYER_B_CU])
    pth = _Pad("1", "net_a", 20_000_000, 20_000_000, 1_000_000, PadType.PT_PTH)  # 1.0mm drill
    npth = _Pad("", None, 26_000_000, 20_000_000, 1_000_000, PadType.PT_NPTH)
    raw = _FakeRawBoard(
        zones=[zone],
        footprints=[_Footprint("P1", [pth]), _Footprint("MH1", [npth])],
        tracks=[],
    )
    bridge = _bridge()
    board = BoardHandle(_raw=raw)

    created = bridge.enforce_hole_clearance(board, Path("/nonexistent/proj.kicad_pcb"))

    assert created == 2
    assert raw.refill_calls == 1
    keepouts = [z for z in raw.get_zones() if getattr(z, "type", None) == ZoneType.ZT_RULE_AREA]
    assert len(keepouts) == 2
    names = {k.name for k in keepouts}
    assert any("P1_1" in n for n in names)
    assert any("MH1_" in n for n in names)
    for k in keepouts:
        assert k.proto.rule_area_settings.keepout_copper is True
        assert k.proto.rule_area_settings.keepout_vias is False
        assert k.proto.rule_area_settings.keepout_tracks is False


@pytest.mark.unit
def test_enforce_hole_clearance_skips_same_net_pad() -> None:
    """Un pad PTH del MISMO net que la zona no necesita protección (conexión
    legítima) — no debe crearse ningún keepout."""
    zone = _FakeExistingZone(ZoneType.ZT_COPPER, "GND_plane", "GND", [LAYER_B_CU])
    same_net_pad = _Pad("1", "GND", 20_000_000, 20_000_000, 1_000_000, PadType.PT_PTH)
    raw = _FakeRawBoard(zones=[zone], footprints=[_Footprint("P1", [same_net_pad])], tracks=[])
    bridge = _bridge()
    board = BoardHandle(_raw=raw)

    created = bridge.enforce_hole_clearance(board, Path("/nonexistent/proj.kicad_pcb"))

    assert created == 0
    assert raw.refill_calls == 0  # nada que proteger -> no hace falta refillear de nuevo
    assert all(getattr(z, "type", None) != ZoneType.ZT_RULE_AREA for z in raw.get_zones())


@pytest.mark.unit
def test_enforce_hole_clearance_protects_foreign_via() -> None:
    """Vía de net distinto al de la zona (el mecanismo exacto de F-D3-03:
    tracks/vías nuevas de route_board cerca del plano GND) — debe protegerse,
    usando el DRILL de la vía (el agujero real), no su ancho de cobre."""
    zone = _FakeExistingZone(ZoneType.ZT_COPPER, "GND_plane", "GND", [LAYER_B_CU])
    via = Via("+3V3", 166_000_000, 61_000_000, 400_000, "via-kiid-1")  # drill 0.4mm
    raw = _FakeRawBoard(zones=[zone], footprints=[], tracks=[via, _NotAVia()])
    bridge = _bridge()
    board = BoardHandle(_raw=raw)

    created = bridge.enforce_hole_clearance(board, Path("/nonexistent/proj.kicad_pcb"))

    assert created == 1
    keepouts = [z for z in raw.get_zones() if getattr(z, "type", None) == ZoneType.ZT_RULE_AREA]
    assert len(keepouts) == 1
    assert "via_via-kiid-1" in keepouts[0].name


@pytest.mark.unit
def test_enforce_hole_clearance_is_idempotent_no_duplicate_keepouts() -> None:
    """Llamar dos veces seguidas (p. ej. dos ``route_board`` consecutivos) no
    acumula keepouts duplicados — la segunda pasada borra los propios de la
    primera antes de recalcular (tag ``_AUTO_KEEPOUT_PREFIX``)."""
    zone = _FakeExistingZone(ZoneType.ZT_COPPER, "GND_plane", "GND", [LAYER_B_CU])
    npth = _Pad("", None, 26_000_000, 20_000_000, 1_000_000, PadType.PT_NPTH)
    raw = _FakeRawBoard(zones=[zone], footprints=[_Footprint("MH1", [npth])], tracks=[])
    bridge = _bridge()
    board = BoardHandle(_raw=raw)

    bridge.enforce_hole_clearance(board, Path("/nonexistent/proj.kicad_pcb"))
    bridge.enforce_hole_clearance(board, Path("/nonexistent/proj.kicad_pcb"))

    keepouts = [z for z in raw.get_zones() if getattr(z, "type", None) == ZoneType.ZT_RULE_AREA]
    assert len(keepouts) == 1  # no 2 — la 2da pasada reemplaza, no acumula


@pytest.mark.unit
def test_enforce_hole_clearance_no_copper_zones_is_noop() -> None:
    """Sin zonas de cobre en el board, no hay nada que proteger — 0 keepouts,
    0 refills adicionales (no falla ni hace trabajo de más)."""
    raw = _FakeRawBoard(zones=[], footprints=[], tracks=[])
    bridge = _bridge()
    board = BoardHandle(_raw=raw)

    created = bridge.enforce_hole_clearance(board, Path("/nonexistent/proj.kicad_pcb"))

    assert created == 0
    assert raw.refill_calls == 0


@pytest.mark.unit
def test_list_pad_holes_reports_ref_net_kind_diameter() -> None:
    """``list_pad_holes`` (compartido con 21.3) devuelve ref/net/kind/diámetro
    correctos y excluye pads sin drill (SMD/edge-connector)."""
    pth = _Pad("1", "Net-(ANT1-A)", 173_000_000, 31_000_000, 2_000_000, PadType.PT_PTH)
    npth = _Pad("", None, 192_500_000, 47_000_000, 990_600, PadType.PT_NPTH)
    smd = _Pad("2", "+3V3", 0, 0, 0, PadType.PT_SMD)  # drill 0 -> excluido
    raw = _FakeRawBoard(
        zones=[], footprints=[_Footprint("ANT1", [pth]), _Footprint("J1", [npth, smd])], tracks=[]
    )
    bridge = _bridge()
    board = BoardHandle(_raw=raw)

    holes = bridge.list_pad_holes(board)

    assert len(holes) == 2
    by_ref = {h.ref: h for h in holes}
    assert by_ref["ANT1"].net_name == "Net-(ANT1-A)"
    assert by_ref["ANT1"].kind == "pth"
    assert by_ref["ANT1"].diameter_mm == pytest.approx(2.0)
    assert by_ref["J1"].net_name is None
    assert by_ref["J1"].kind == "npth"
    assert by_ref["J1"].diameter_mm == pytest.approx(0.9906, abs=1e-4)
