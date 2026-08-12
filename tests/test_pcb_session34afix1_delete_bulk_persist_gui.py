"""Test integration_gui_slow de 34a-fix-1 — cierra la asimetría A1 (auditoría
de contratos de escritura, sesión 34a): ``delete_tracks_bulk`` es la única
tool que rellena zonas de cobre sin aplicar el pipeline de persistencia
D-23.2 (``refill_zones`` → ``enforce_hole_clearance`` → ``save_board``) que
``add_zone(fill=True)``/``fill_zones`` (sesión 27, ver
``test_pcb_session27_zone_persist_gui.py``) y ``route_board`` (sesión 24)
sí aplican.

Reproduce, contra KiCad 10.0.4 real (kipy real, sin Freerouting — el bug
conceptual es de refill+persistencia, no de ruteo), el mismo escenario que
sesión 27 pero para ``delete_tracks_bulk``: partiendo del fixture
``despertador-routed`` (footprints + plano GND filleado + ruteo completo,
DRC 0/0 — ver ``tests/fixtures/despertador-routed/README.md``), siembra un
stub de cobre GND anclado a un pad (mismo patrón
``test_pcb_session19d_gui.py::_seed_pad_anchored_stub``, reescrito acá para
mantener este archivo autocontenido) y lo borra con ``delete_tracks_bulk``
usando un ``bbox`` acotado al stub — sin tocar el resto del ruteo real — y
SIN llamar ``save_board()`` manual. Verifica que:

1. El payload trae ``zones_refilled == 1`` (el borrado tocó la zona GND).
2. Un ``run_drc()`` independiente inmediato (oráculo primario,
   contenido/DRC — no sólo mtime) refleja el estado ya arreglado por
   refill+``enforce_hole_clearance``: 0 violaciones ``hole_clearance``, sin
   ``clearance`` contra la Zone GND.
3. Una operación D-23.2 posterior (``fill_zones()``) NO dispara
   ``EXTERNAL_EDIT_DETECTED`` espurio — evidencia de que los mtimes del
   snapshot se registraron post-save (control R2 explícito de la orden de
   ejecución 34a-fix-1: la propia escritura de la tool no se autolesiona).
4. El mtime del ``.kicad_pcb`` cambió (señal secundaria — la resolución de
   FS puede hacerla frágil, por eso no es el oráculo primario).
5. El conteo de keepouts ``__kicadmcp_hc__`` queda en el rango esperado
   (``enforce_hole_clearance`` corrió y es idempotente — mismo umbral que
   sesión 24/27, D-23.3/R16 sin tocar en este ciclo).

Deliberadamente NO reutiliza los helpers de
``test_pcb_session27_zone_persist_gui.py`` vía import — duplicación
intencional para que este archivo sea autocontenido (mismo criterio que la
orden de ejecución 34a-fix-1: "recomendado autocontenido, no mezclar con
session27").

Corre DIRECTO sobre el proyecto que ``KICAD_MCP_PROJECT`` apunta — el mismo
que debe estar YA ABIERTO en el PCB Editor de KiCad (mismo patrón que
``test_pcb_session27_zone_persist_gui.py``). **Muta de forma permanente** el
board (agrega y borra un stub de cobre GND; puede crear el plano GND si el
fixture no lo tuviera) — no es descartable. Usar SIEMPRE una copia
descartable del fixture (``docs/guias/pruebas-gui.md``
§fixture ``despertador-routed``), nunca el proyecto de trabajo real.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.ipc import IpcBridge
from kicad_mcp.bridge.rules import run_drc
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store
from kicad_mcp.tools.world import _resolve_root_pcb

# Keepouts fijos esperados (ANT1 + 3x J1 NPTH, D-D3.1/sesión 20) + margen
# generoso para no ser flakey — mismo umbral que sesión 24/27
# (D-23.3/R16 sigue sin generar keepouts por-vía, no se tocó en este ciclo).
_KEEPOUTS_MIN = 4
_KEEPOUTS_MAX = 8

_STUB_LENGTH_MM = 2.0
_STUB_DIRECTIONS = (
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (1, 1),
    (1, -1),
    (-1, 1),
    (-1, -1),
)


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _json(result: CallToolResult) -> dict[str, Any]:
    return json.loads(_text(result))


def _guard() -> None:
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/guias/pruebas-gui.md")
    if not os.environ.get("KICAD_MCP_PROJECT"):
        pytest.skip(
            "KICAD_MCP_PROJECT no seteada — debe apuntar al proyecto YA "
            "ABIERTO en el PCB Editor de KiCad"
        )


def _preflight_same_board_open(pcb_path: Path) -> IpcBridge:
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay PCB Editor abierto en KiCad")
    open_path = bridge.get_open_board_path(board)
    if open_path is None or open_path.resolve() != pcb_path.resolve():
        pytest.skip(
            f"KICAD_MCP_PROJECT ({pcb_path}) no coincide con el board abierto "
            f"en KiCad ({open_path}) — abrí ESE proyecto en KiCad antes de "
            "correr este test."
        )
    return bridge


def _server():  # type: ignore[no-untyped-def]
    from kicad_mcp.server import create_server

    return create_server()


def _gnd_clearance_violations(report: Any) -> list[Any]:
    """Violaciones ``clearance`` contra la Zone GND — mismo filtro que
    sesión 24/27."""
    return [
        v
        for v in report.violations
        if v.severity == "error"
        and v.rule == "clearance"
        and any(it.desc and "Zone" in it.desc and "GND" in it.desc for it in v.items)
    ]


def _hole_clearance_count(report: Any) -> int:
    return sum(1 for v in report.violations if v.severity == "error" and v.rule == "hole_clearance")


async def _gnd_board_bbox(client: Any) -> list[float]:
    """Bbox del board entero (``bbox:`` de ``get_world_context(kind='pcb')``,
    F-03) — mismo helper que sesión 27, para no depender de coordenadas
    hardcodeadas."""
    world_pcb = await client.call_tool("get_world_context", {"kind": "pcb", "max_tokens": 4000})
    assert not world_pcb.isError, _text(world_pcb)
    header = _text(world_pcb).splitlines()[0]
    bbox_field = next(p for p in header.split("|") if p.startswith("bbox:"))
    lo, hi = bbox_field[len("bbox:") :].split(";")
    min_x, min_y = (float(v) for v in lo.split(","))
    max_x, max_y = (float(v) for v in hi.split(","))
    return [min_x, min_y, max_x, max_y]


async def _ensure_gnd_copper_zone(client: Any, bridge: IpcBridge, board: Any) -> None:
    """Arreglo determinista: garantiza ≥1 zona de cobre GND presente antes
    de sembrar el stub — el fixture ya la trae, pero el test no depende de
    eso (robusto a una corrida aislada sobre un board sin plano)."""
    has_gnd_copper = any(
        z.kind == "copper" and z.net_name == "GND" for z in bridge.list_zones(board)
    )
    if has_gnd_copper:
        return
    board_bbox = await _gnd_board_bbox(client)
    create_result = await client.call_tool(
        "add_zone", {"net": "GND", "layer": "B.Cu", "bbox": board_bbox, "fill": True}
    )
    assert not create_result.isError, _text(create_result)


async def _seed_gnd_pad_stub(
    client: Any, bridge: IpcBridge, board: Any
) -> tuple[str, float, float, float, float]:
    """Crea, vía la tool ``add_track``, un stub de 2mm desde el primer pad
    GND que encuentre en un rumbo libre de colisión con otro cobre.

    Reescritura autocontenida de
    ``test_pcb_session19d_gui.py::_seed_pad_anchored_stub`` (mismo mecanismo,
    net fijo a GND): el stub queda aislado del resto del ruteo real, así el
    borrado que ejercita ``delete_tracks_bulk`` puede acotarse a un bbox
    mínimo sin arriesgar la topología del fixture. Devuelve
    ``(kiid, start_x, start_y, end_x, end_y)``; lanza ``AssertionError`` si
    ningún pad GND tiene un rumbo libre (fixture inadecuada).
    """
    ctx = bridge.read_board_context(board)
    for ref in ctx.refs:
        detail = bridge.get_component_detail(board, ref)
        for pad in detail.pads:
            if pad.net_name != "GND":
                continue
            px, py = float(pad.x_mm), float(pad.y_mm)
            for dx, dy in _STUB_DIRECTIONS:
                ex = round(px + dx * _STUB_LENGTH_MM, 3)
                ey = round(py + dy * _STUB_LENGTH_MM, 3)
                result = await client.call_tool(
                    "add_track",
                    {
                        "net": "GND",
                        "start_x_mm": px,
                        "start_y_mm": py,
                        "end_x_mm": ex,
                        "end_y_mm": ey,
                    },
                )
                if not result.isError:
                    new_kiids = [
                        line.split(" ")[1]
                        for line in (
                            await client.call_tool(
                                "get_tracks",
                                {
                                    "bbox": [
                                        min(px, ex) - 0.01,
                                        min(py, ey) - 0.01,
                                        max(px, ex) + 0.01,
                                        max(py, ey) + 0.01,
                                    ],
                                    "max_tokens": 4000,
                                },
                            )
                        )
                        .content[0]
                        .text.splitlines()
                        if line.startswith("T ")
                    ]
                    assert new_kiids, "el stub se creó pero get_tracks no lo encontró"
                    return new_kiids[-1], px, py, ex, ey
    raise AssertionError("ningún pad del net GND tiene un rumbo de stub libre de colisión")


@pytest.mark.integration_gui_slow
async def test_delete_tracks_bulk_zone_touch_persists_matches_independent_drc() -> None:
    """34a-fix-1 (A1/A6/P3): tras ``delete_tracks_bulk`` tocar una zona de
    cobre, disco == vivo — sin ``save_board()`` manual — gate del merge."""
    _guard()
    pcb_path = _resolve_root_pcb()
    bridge = _preflight_same_board_open(pcb_path)
    g1.reset_session_state()
    get_default_store().reset()

    board = bridge.get_open_board()
    assert board is not None  # _preflight_same_board_open ya lo garantizó

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        # --- Arreglo determinista: plano GND de cobre presente.
        await _ensure_gnd_copper_zone(client, bridge, board)

        # --- Sembrar el stub a borrar — aislado del resto del ruteo real.
        stub_kiid, sx, sy, ex, ey = await _seed_gnd_pad_stub(client, bridge, board)

        save_result = await client.call_tool("save_board", {})
        assert not save_result.isError, _text(save_result)
        mtime_before = pcb_path.stat().st_mtime

        raw = board.raw
        assert stub_kiid in {str(t.id.value) for t in raw.get_tracks()}

        # --- delete_tracks_bulk real, bbox acotado al stub — SIN
        # save_board() manual.
        margin = 0.5
        bbox = [
            min(sx, ex) - margin,
            min(sy, ey) - margin,
            max(sx, ex) + margin,
            max(sy, ey) + margin,
        ]
        delete_result = await client.call_tool("delete_tracks_bulk", {"bbox": bbox, "net": "GND"})
        assert not delete_result.isError, _text(delete_result)
        payload = _json(delete_result)
        assert payload["zones_refilled"] == 1
        assert stub_kiid not in {str(t.id.value) for t in raw.get_tracks()}

        # 1. Gate: el save_board() incondicional de 34a-fix-1 corrió.
        mtime_after = pcb_path.stat().st_mtime
        assert mtime_after > mtime_before, (
            "el mtime del .kicad_pcb no cambió tras delete_tracks_bulk — "
            "¿el save_board() de 34a-fix-1 no corrió?"
        )

        # Ground truth INDEPENDIENTE inmediata (bridge directo, no la tool).
        post_report = run_drc(pcb_path)

        # 2. Gate — corazón del contrato: el disco ya refleja el refill +
        # enforce_hole_clearance del vivo, sin que el llamador haya invocado
        # save_board() aparte.
        assert _hole_clearance_count(post_report) == 0, (
            f"run_drc() independiente trae hole_clearance espurio post-"
            f"delete_tracks_bulk: "
            f"{[v.rule for v in post_report.violations if v.severity == 'error']}"
        )
        gnd_clearance = _gnd_clearance_violations(post_report)
        assert gnd_clearance == [], (
            f"clearance vs Zone GND sobrevivió al delete_tracks_bulk: {gnd_clearance}"
        )

        # 3. Gate — control R2: una operación D-23.2 posterior (fill_zones,
        # idempotente) no dispara EXTERNAL_EDIT_DETECTED espurio — los
        # mtimes de delete_tracks_bulk se registraron post-save.
        followup = await client.call_tool("fill_zones", {})
        assert not followup.isError, _text(followup)
        assert "EXTERNAL_EDIT_DETECTED" not in _text(followup)

        # 4. Gate: keepouts fijos, sin proliferación descontrolada.
        zones_after = bridge.list_zones(board)
        keepouts_after = sum(1 for z in zones_after if z.kind == "keepout")
        assert _KEEPOUTS_MIN <= keepouts_after <= _KEEPOUTS_MAX, (
            f"conteo de keepouts fuera de rango esperado: {keepouts_after}"
        )
