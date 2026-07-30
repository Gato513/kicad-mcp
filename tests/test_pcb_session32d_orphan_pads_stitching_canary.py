"""Canario permanente — F-D5-01 stitching automático de pads huérfanos
(sesión 32d).

F-D5-01 se manifestó 3 veces en regímenes distintos (sesión 25 despertador,
31c dev-mic ``MK1.3``, 32 macro-pad-12 ``J4.3``/``J5.3``) y se promovió a P1.
Sesión 32c aisló el mecanismo causalmente
(``docs/investigacion/32c-f-d5-01.md``): Freerouting no modela el plano GND
como conductor (D-19.1), y puede rutear cobre ajeno tan cerca de un pad GND
que el refill posterior de KiCad —que sí recorta con clearance,
correctamente— queda geométricamente incapacitado para alcanzar ese pad.

Este canario cubre el fix de sesión 32d: tras el refill final de
``route_board`` (bloque D-23.2/ADR-0012), se detectan pads huérfanos
(``unconnected_items`` post-refill) sobre nets con zona de cobre propia y se
intenta stitchear una vía bajo 5 guardrails estrictos (D3). Cualquier
guardrail que rechace NO es error (D-32d.2) — el pad se expone en el
payload como ``orphan_pads`` con la razón del rechazo. Si se stitchea
≥1 vía, ``route_board`` re-refillea/re-guarda/re-mide (D-23.2: el
``err_post`` reportado debe seguir describiendo el estado REAL persistido).

**Hallazgo de esta sesión que corrige la premisa del prompt original**: las
3 manifestaciones NO son el mismo caso geométrico. En macro-pad-12
(``J4.3``/``J5.3``), el pad huérfano y la única zona GND del board están en
la MISMA capa (B.Cu) — no existe cobre GND en la capa opuesta (F.Cu), así
que el guardrail #4 ("capa opuesta con zona del mismo net") rechaza por
diseño: una vía ahí uniría B.Cu (relleno retraído) con F.Cu (sin cobre
GND), sin conectar nada. macro-pad-12 pasa a ser el caso canónico de
RECHAZO por guardrail (evidencia de H2); H1 (stitching que sí cierra el
síntoma) se re-baselinea a anavi-dev-mic (``MK1.3``, F.Cu, con zona GND
únicamente en B.Cu — exactamente la topología "capas opuestas" que el
guardrail #4 fue diseñado para aceptar). Ver
``docs/historico/sesiones/32d-reporte.md`` para el análisis comparativo.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.autoroute import AutorouteResult
from kicad_mcp.bridge.ipc import (
    BBoxMm,
    BoardContext,
    BoardHandle,
    CopperItem,
    FootprintData,
    FootprintPadData,
    IpcBridge,
    Mm,
    PadGeom,
    ZoneItem,
)
from kicad_mcp.bridge.rules import Item, RulesReport, Violation
from kicad_mcp.gates import g1
from kicad_mcp.tools import pcb as pcb_module
from kicad_mcp.tools.pcb import register as register_pcb
from kicad_mcp.tools.world import register as register_world

# --- Geometría sintética común a los tests -----------------------------------
# Réplica simplificada de la topología "capas opuestas" (dev-mic real):
# pad huérfano GND en F.Cu, zona de cobre GND sólo en B.Cu, cubriendo el pad.

_PAD_X, _PAD_Y = 10.0, 10.0
_ZONE_OUTLINE_NEAR = ((0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0))
_ZONE_OUTLINE_FAR = ((100.0, 100.0), (120.0, 100.0), (120.0, 120.0), (100.0, 120.0))


def _pad(net: str = "GND", layer: str = "F.Cu", x: float = _PAD_X, y: float = _PAD_Y) -> PadGeom:
    return PadGeom(
        net_name=net,
        layer=layer,
        x_mm=Mm(x),
        y_mm=Mm(y),
        w_mm=Mm(0.5),
        h_mm=Mm(0.5),
        rotation_deg=0.0,
        corner_ratio=0.0,
    )


def _zone(
    net: str = "GND",
    layer: str = "B.Cu",
    vertices: tuple[tuple[float, float], ...] = _ZONE_OUTLINE_NEAR,
) -> ZoneItem:
    return ZoneItem(
        kind="copper",
        kiid="zone-1",
        net_name=net,
        layer=layer,
        bbox_min_x=Mm(vertices[0][0]),
        bbox_min_y=Mm(vertices[0][1]),
        bbox_max_x=Mm(vertices[2][0]),
        bbox_max_y=Mm(vertices[2][1]),
        area_mm2=100.0,
        filled=True,
        vertices_mm=tuple((Mm(x), Mm(y)) for x, y in vertices),
    )


def _blocker(
    net: str = "+5V", layer: str = "B.Cu", x: float = _PAD_X, y: float = _PAD_Y
) -> CopperItem:
    return CopperItem(
        kind="via",
        kiid="blocker-1",
        net_name=net,
        layer=layer,
        start_x_mm=Mm(x),
        start_y_mm=Mm(y),
        end_x_mm=None,
        end_y_mm=None,
        mid_x_mm=None,
        mid_y_mm=None,
        via_layers=(layer, layer),
    )


# --- Fake bridge --------------------------------------------------------------


class _FakeBridge(IpcBridge):
    """Bridge en memoria para route_board (mismo espíritu que
    ``test_route_board.py``/``test_pcb_session32b_refill_silencioso_canary.py``),
    extendido con los métodos que el stitching de sesión 32d necesita:
    ``list_all_pads``/``list_zones``/``list_all_copper`` (lectura de
    geometría para los guardrails) y ``add_via`` (la mutación en sí,
    instrumentada para registrar cada llamada)."""

    def __init__(
        self,
        *,
        open_board_path: str,
        n_zones: int = 1,
        pads: tuple[PadGeom, ...] = (),
        zones: tuple[ZoneItem, ...] = (),
        copper: tuple[CopperItem, ...] = (),
        add_via_error: Exception | None = None,
    ) -> None:
        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._open_board_path = open_board_path
        self._n_zones = n_zones
        self._pads = pads
        self._zones = zones
        self._copper = copper
        self._add_via_error = add_via_error
        self.saved: list[str] = []
        self.refill_calls = 0
        self.enforce_hole_clearance_calls = 0
        self.add_via_calls: list[dict[str, Any]] = []
        self.list_all_pads_calls = 0
        self.list_zones_calls = 0
        self.list_all_copper_calls = 0

    def get_open_board(self) -> BoardHandle | None:  # type: ignore[override]
        return BoardHandle(_raw=object())

    def get_open_board_path(self, board: BoardHandle) -> Path | None:  # type: ignore[override]
        return Path(self._open_board_path)

    def save_board(self, board: BoardHandle) -> None:  # type: ignore[override]
        self.saved.append(self._open_board_path)

    def reload_board_from_disk(self, board: BoardHandle) -> tuple[int, int]:  # type: ignore[override]
        return (0, 0)

    def list_zones(self, board: BoardHandle) -> tuple[ZoneItem, ...]:  # type: ignore[override]
        self.list_zones_calls += 1
        return self._zones

    def list_all_pads(self, board: BoardHandle) -> tuple[PadGeom, ...]:  # type: ignore[override]
        self.list_all_pads_calls += 1
        return self._pads

    def list_all_copper(self, board: BoardHandle) -> tuple[CopperItem, ...]:  # type: ignore[override]
        self.list_all_copper_calls += 1
        return self._copper

    def refill_zones(self, board: BoardHandle) -> int:  # type: ignore[override]
        self.refill_calls += 1
        return self._n_zones

    def enforce_hole_clearance(self, board: BoardHandle, pcb_path: Path) -> int:  # type: ignore[override]
        self.enforce_hole_clearance_calls += 1
        return 0

    def add_via(  # type: ignore[override]
        self,
        board: BoardHandle,
        net: str,
        x_mm: Mm,
        y_mm: Mm,
        diameter_mm: Mm,
        drill_mm: Mm,
        *,
        timings: dict[str, float] | None = None,
    ) -> str:
        if self._add_via_error is not None:
            raise self._add_via_error
        self.add_via_calls.append({"net": net, "x_mm": float(x_mm), "y_mm": float(y_mm)})
        return f"kiid-via-{len(self.add_via_calls)}"

    def read_board_context(self, board: BoardHandle) -> BoardContext:  # type: ignore[override]
        fps = (
            FootprintData(
                ref="J1",
                value="V",
                x_mm=Mm(1.0),
                y_mm=Mm(2.0),
                pads=(FootprintPadData(number="1", net_name="GND"),),
                kiid="kiid-J1",
            ),
        )
        return BoardContext(
            refs=("J1",), bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)), footprints=fps
        )


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "proj.kicad_sch").write_text("(kicad_sch)")
    (project / "proj.kicad_pcb").write_text("(kicad_pcb original)")
    return project


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _json(result: CallToolResult) -> dict[str, Any]:
    return json.loads(_text(result))


def _drc(*, errors: int = 0, orphans: tuple[tuple[float, float], ...] = ()) -> RulesReport:
    """DRC sintético (F-D5-01, sesión 32d): ``errors`` violaciones genéricas
    + una violación ``unconnected_items`` real por cada posición en
    ``orphans`` — misma forma que kicad-cli 10.0.4 real (severity="error",
    un único ``Item`` con ``pos``, verificado en el Bloque 0 de esta sesión).
    """
    violations = [
        Violation(rule="clearance", severity="error", message="err", items=())
        for _ in range(errors)
    ]
    for pos in orphans:
        violations.append(
            Violation(
                rule="unconnected_items",
                severity="error",
                message="Missing connection between items",
                items=(Item(ref=None, net=None, pos=pos, desc=f"Pad [GND] @{pos}"),),
            )
        )
    total_errors = errors + len(orphans)
    return RulesReport(
        violations=tuple(violations),
        counts={"error": total_errors} if total_errors else {},
        coordinate_units="mm",
        kicad_version="10.0.4",
        unconnected=len(orphans),
    )


def _patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    drc_sequence: list[RulesReport],
    result: AutorouteResult,
) -> dict[str, Any]:
    calls: dict[str, Any] = {"drc": 0}

    def _fake_drc(pcb_path: Path) -> RulesReport:
        report = drc_sequence[min(calls["drc"], len(drc_sequence) - 1)]
        calls["drc"] += 1
        return report

    def _fake_autoroute(src: Path, workdir: Path, **kw: Any) -> AutorouteResult:
        routed = Path(result.routed_pcb)
        routed.parent.mkdir(parents=True, exist_ok=True)
        routed.write_text("(kicad_pcb routed)")
        return result

    monkeypatch.setattr(pcb_module, "run_drc", _fake_drc)
    monkeypatch.setattr(pcb_module, "run_autoroute", _fake_autoroute)
    return calls


def _result(workdir: Path) -> AutorouteResult:
    return AutorouteResult(
        tracks_before=0,
        tracks_after=10,
        vias_before=0,
        vias_after=2,
        export_ms=1.0,
        route_ms=2.0,
        import_ms=1.0,
        routed_pcb=str(workdir / ".kicad-mcp" / "autoroute" / "routed.kicad_pcb"),
        freerouting_log=str(workdir / "log"),
        nets_pin_counts={"GND": 2},
        nets_wire_counts={"GND": 1},
        dsn_path=str(workdir / ".kicad-mcp" / "autoroute" / "route.dsn"),
        ses_path=str(workdir / ".kicad-mcp" / "autoroute" / "route.ses"),
    )


def _server(bridge: IpcBridge) -> FastMCP:
    mcp = FastMCP(name="test", instructions="test")
    register_pcb(mcp, ipc_bridge=bridge)
    register_world(mcp, ipc_bridge=bridge)
    return mcp


@pytest.fixture(autouse=True)
def _reset_g1() -> Any:
    g1.reset_session_state()
    yield
    g1.reset_session_state()


async def _route(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: _FakeBridge
) -> CallToolResult:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge._open_board_path = str(project / "proj.kicad_pcb")
    mcp = _server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        return await client.call_tool("route_board", {})


# --- H1 (re-baselineada a la topología "capas opuestas", dev-mic real) ------


@pytest.mark.unit
async def test_orphan_pad_stitched_when_guardrails_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Las 5 condiciones de D3 se cumplen (topología dev-mic: pad en F.Cu,
    zona GND sólo en B.Cu cubriéndolo, sin cobre ajeno cerca) — se stitchea
    la vía y el payload la expone."""
    project = tmp_path / "proj"
    _patch_pipeline(
        monkeypatch,
        drc_sequence=[_drc(), _drc(orphans=((_PAD_X, _PAD_Y),)), _drc()],
        result=_result(project),
    )
    bridge = _FakeBridge(
        open_board_path="",
        n_zones=1,
        pads=(_pad(),),
        zones=(_zone(),),
        copper=(),
    )
    result = await _route(monkeypatch, tmp_path, bridge)

    assert not result.isError, _text(result)
    payload = _json(result)
    assert len(bridge.add_via_calls) == 1
    assert bridge.add_via_calls[0] == {"net": "GND", "x_mm": _PAD_X, "y_mm": _PAD_Y}
    assert payload["stitched_vias"] == [
        {
            "pad": f"Pad [GND] @({_PAD_X}, {_PAD_Y})",
            "net": "GND",
            "x_mm": _PAD_X,
            "y_mm": _PAD_Y,
            "layers": ["F.Cu", "B.Cu"],
            "kiid": "kiid-via-1",
        }
    ]
    assert "orphan_pads" not in payload
    # Re-persist tras el stitching (D-23.2): refill/enforce corren una
    # SEGUNDA vez (la primera es el bloque de seguridad D-23.2 existente).
    assert bridge.refill_calls == 2
    assert bridge.enforce_hole_clearance_calls == 2
    # saved: 1 implícito pre-route (D-14.3) + 1 refill de seguridad + 1
    # re-persist del stitching.
    assert len(bridge.saved) == 3


@pytest.mark.unit
async def test_err_post_remeasured_after_stitching(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-23.2: ``drc.err_post`` sale del DRC FINAL (post-stitching), no del
    intermedio — el JSON no debe volver a mentir (precedente F-D4-02)."""
    project = tmp_path / "proj"
    calls = _patch_pipeline(
        monkeypatch,
        drc_sequence=[
            _drc(),  # pre-route
            _drc(errors=1, orphans=((_PAD_X, _PAD_Y),)),  # post-refill: 1 unconnected
            _drc(),  # post-stitching: resuelto
        ],
        result=_result(project),
    )
    bridge = _FakeBridge(open_board_path="", n_zones=1, pads=(_pad(),), zones=(_zone(),), copper=())
    result = await _route(monkeypatch, tmp_path, bridge)

    assert not result.isError, _text(result)
    payload = _json(result)
    assert calls["drc"] == 3
    assert payload["drc"]["err_post"] == 0


# --- H2 (macro-pad-12 real: rechazo de guardrail, no error) -----------------


@pytest.mark.unit
async def test_no_stitching_when_net_has_no_zone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Guardrail #2: el board SÍ tiene zonas (el refill de seguridad D-23.2
    corre normalmente), pero ninguna es del net del pad huérfano — sin zona
    propia, no se stitchea."""
    project = tmp_path / "proj"
    _patch_pipeline(
        monkeypatch,
        drc_sequence=[_drc(), _drc(orphans=((_PAD_X, _PAD_Y),))],
        result=_result(project),
    )
    bridge = _FakeBridge(
        open_board_path="",
        n_zones=1,
        pads=(_pad(),),  # net GND
        zones=(_zone(net="+3V3"),),  # única zona del board, de OTRO net
        copper=(),
    )
    result = await _route(monkeypatch, tmp_path, bridge)

    assert not result.isError, _text(result)
    payload = _json(result)
    assert bridge.add_via_calls == []
    assert "stitched_vias" not in payload
    assert payload["orphan_pads"] == [
        {
            "pad": f"Pad [GND] @({_PAD_X}, {_PAD_Y})",
            "net": "GND",
            "x_mm": _PAD_X,
            "y_mm": _PAD_Y,
            "reason": "sin zona de cobre propia",
        }
    ]
    # Rechazo de guardrail = sin candidatos = sin re-persist extra: sólo el
    # refill de seguridad D-23.2 estándar corrió (no una segunda vez).
    assert bridge.refill_calls == 1
    assert len(bridge.saved) == 2  # 1 implícito pre-route + 1 refill de seguridad


@pytest.mark.unit
async def test_no_stitching_when_pad_outside_zone_outline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Guardrail #3: el pad no cae dentro del outline de la zona de su net."""
    project = tmp_path / "proj"
    _patch_pipeline(
        monkeypatch,
        drc_sequence=[_drc(), _drc(orphans=((_PAD_X, _PAD_Y),))],
        result=_result(project),
    )
    bridge = _FakeBridge(
        open_board_path="",
        n_zones=1,
        pads=(_pad(),),
        zones=(_zone(vertices=_ZONE_OUTLINE_FAR),),
        copper=(),
    )
    result = await _route(monkeypatch, tmp_path, bridge)

    assert not result.isError, _text(result)
    payload = _json(result)
    assert bridge.add_via_calls == []
    assert payload["orphan_pads"][0]["reason"] == "fuera del outline de la zona"
    assert bridge.refill_calls == 1  # sin re-persist extra: rechazo de guardrail


@pytest.mark.unit
async def test_no_stitching_when_no_opposite_layer_zone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Guardrail #4 — LA GEOMETRÍA REAL DE MACRO-PAD-12 (J4.3/J5.3, sesión
    32): pad y única zona GND en la MISMA capa (B.Cu), sin cobre GND en la
    capa opuesta (F.Cu). El guardrail rechaza por diseño — una vía ahí
    uniría B.Cu (relleno retraído por el clearance de +5V que 32c aisló) con
    F.Cu (sin cobre GND): no conectaría nada."""
    project = tmp_path / "proj"
    pad_same_layer = _pad(layer="B.Cu")
    _patch_pipeline(
        monkeypatch,
        drc_sequence=[_drc(), _drc(orphans=((_PAD_X, _PAD_Y),))],
        result=_result(project),
    )
    bridge = _FakeBridge(
        open_board_path="",
        n_zones=1,
        pads=(pad_same_layer,),
        zones=(_zone(layer="B.Cu"),),  # misma capa que el pad — no "opuesta"
        copper=(),
    )
    result = await _route(monkeypatch, tmp_path, bridge)

    assert not result.isError, _text(result)
    payload = _json(result)
    assert bridge.add_via_calls == []
    assert payload["orphan_pads"][0]["reason"] == "sin zona en capa opuesta"
    assert bridge.refill_calls == 1  # sin re-persist extra: rechazo de guardrail


@pytest.mark.unit
async def test_no_stitching_when_area_not_free(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Guardrail #5: cobre ajeno (otro net) dentro de 1mm del punto de
    stitching en la capa opuesta — no se stitchea para no arriesgar
    colisión."""
    project = tmp_path / "proj"
    _patch_pipeline(
        monkeypatch,
        drc_sequence=[_drc(), _drc(orphans=((_PAD_X, _PAD_Y),))],
        result=_result(project),
    )
    bridge = _FakeBridge(
        open_board_path="",
        n_zones=1,
        pads=(_pad(),),
        zones=(_zone(),),
        copper=(_blocker(net="+5V", layer="B.Cu", x=_PAD_X, y=_PAD_Y),),
    )
    result = await _route(monkeypatch, tmp_path, bridge)

    assert not result.isError, _text(result)
    payload = _json(result)
    assert bridge.add_via_calls == []
    assert payload["orphan_pads"][0]["reason"] == "cobre ajeno en la región inmediata"
    assert bridge.refill_calls == 1  # sin re-persist extra: rechazo de guardrail


# --- Exposición mixta y H4 (0 huérfanos, cero costo) -------------------------


@pytest.mark.unit
async def test_payload_lists_stitched_and_orphan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Un pad stitcheable y uno rechazado en la misma corrida — ambas claves
    del payload conviven, cada una con su propio contenido."""
    project = tmp_path / "proj"
    other_x, other_y = 50.0, 50.0
    _patch_pipeline(
        monkeypatch,
        drc_sequence=[
            _drc(),
            _drc(orphans=((_PAD_X, _PAD_Y), (other_x, other_y))),
            _drc(),
        ],
        result=_result(project),
    )
    bridge = _FakeBridge(
        open_board_path="",
        n_zones=1,
        pads=(_pad(), _pad(net="+3V3", x=other_x, y=other_y)),  # +3V3 sin zona propia
        zones=(_zone(),),
        copper=(),
    )
    result = await _route(monkeypatch, tmp_path, bridge)

    assert not result.isError, _text(result)
    payload = _json(result)
    assert len(payload["stitched_vias"]) == 1
    assert payload["stitched_vias"][0]["net"] == "GND"
    assert len(payload["orphan_pads"]) == 1
    assert payload["orphan_pads"][0]["net"] == "+3V3"
    assert payload["orphan_pads"][0]["reason"] == "sin zona de cobre propia"


@pytest.mark.unit
async def test_no_effect_when_zero_orphans(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """H4: sin pads huérfanos post-refill, el fix no hace NADA adicional —
    ni IPC de geometría propia (``list_all_pads``/``list_all_copper``), ni
    re-persist extra, ni claves nuevas en el payload. El board SÍ tiene una
    zona (el refill de seguridad D-23.2 estándar corre igual que siempre;
    ``list_zones`` se llama UNA vez para eso, no por el stitching)."""
    project = tmp_path / "proj"
    calls = _patch_pipeline(monkeypatch, drc_sequence=[_drc(), _drc()], result=_result(project))
    bridge = _FakeBridge(open_board_path="", n_zones=1, pads=(), zones=(_zone(),), copper=())
    result = await _route(monkeypatch, tmp_path, bridge)

    assert not result.isError, _text(result)
    payload = _json(result)
    assert "stitched_vias" not in payload
    assert "orphan_pads" not in payload
    assert bridge.add_via_calls == []
    assert bridge.list_all_pads_calls == 0
    assert bridge.list_all_copper_calls == 0
    assert bridge.list_zones_calls == 1  # sólo el cómputo pre-route de zones_existentes
    assert calls["drc"] == 2  # pre-route + post-refill; sin 3er DRC
    assert bridge.refill_calls == 1  # sólo el bloque de seguridad D-23.2 existente
    assert len(bridge.saved) == 2  # 1 implícito pre-route + 1 refill de seguridad
