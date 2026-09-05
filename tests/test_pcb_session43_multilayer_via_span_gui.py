"""Test integration_gui de sesión 43 — fix ``_copper_on_layer`` en boards
multicapa (``docs/BACKLOG.md`` "Hallazgo colateral", revisión Codex sobre
DT1 Slice 2 de sesión 42).

Antes del fix, ``_copper_on_layer`` matcheaba una via pasante sólo contra
sus dos extremos (``via_layers``): en un board con capas internas
habilitadas, ``get_tracks(layer="In1.Cu")`` omitía silenciosamente vías
pasantes que físicamente atraviesan esa capa, incumpliendo el contrato de
``docs/specs/tool-catalog.md`` ("una via pasante cuenta para cualquier capa
de su span"). El fix resuelve el span real contra el stackup habilitado del
board (``IpcBridge._via_span_layer_names``, ``bridge/ipc.py``).

**Verificado contra KiCad real (2026-09-05): 1 passed.** Corrido con
``tests/fixtures/007_pcb_multicapa`` (sesión 43-fixture) — chico y
determinístico (una vía pasante + 2 segmentos), a diferencia de ``004_real``
(también 4 capas, pero 808 vías — ``get_tracks`` no trunca, así que ese
board excede el presupuesto de tokens y el test fallaría en vez de
saltarse). Ver ``docs/guias/pruebas-gui.md``. Este test se escribió con
guard de skip explícito (precedente: sesión 32d,
``test_pcb_session32d_stitching_gui_slow.py``, "verificación end-to-end
escrita pero pendiente de ejecución humana") y no se declaró verde hasta
correr efectivamente contra ese proyecto.

Es de SOLO LECTURA (``get_tracks``, sin mutación) — no requiere una copia
descartable del fixture, pero sí requiere que ``KICAD_MCP_PROJECT`` apunte al
proyecto multicapa ya abierto en el PCB Editor (ver
``docs/guias/pruebas-gui.md``); un preflight verifica que el board abierto
coincida con ese proyecto, para no confundirse con el board de la suite
``integration_gui`` general (``004_real``).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.ipc import IpcBridge
from kicad_mcp.tools.world import _resolve_root_pcb

_MIN_COPPER_LAYERS_FOR_INTERNAL_CASE = 4


def _guard() -> None:
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/pruebas-gui.md")
    if not os.environ.get("KICAD_MCP_PROJECT"):
        pytest.skip("KICAD_MCP_PROJECT no definida; apuntar al proyecto abierto")


def _preflight_same_board_open(pcb_path: Path) -> IpcBridge:
    """Mismo patrón que ``test_pcb_session27_zone_persist_gui.py``: evita que
    este test corra en silencio contra el board equivocado si hay más de un
    proyecto GUI en juego (p. ej. ``004_real`` de la suite ``integration_gui``
    general vs. este fixture chico) — sin esto, un ``get_tracks`` contra un
    board grande falla con ``CONTEXT_BUDGET_IMPOSSIBLE`` en vez de un skip
    accionable.
    """
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


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _server():  # type: ignore[no-untyped-def]
    from kicad_mcp.server import create_server

    return create_server()


def _internal_copper_layer(raw_board: object) -> tuple[int, str] | None:
    """``(valor_enum, nombre)`` de una capa de cobre INTERNA (ni F.Cu ni
    B.Cu) habilitada del board, o ``None`` si el board no tiene ninguna
    (típicamente 2 capas).
    """
    from kipy.proto.board.board_types_pb2 import BoardLayer

    copper_values = sorted(
        v
        for v in raw_board.get_enabled_layers()  # type: ignore[attr-defined]
        if str(BoardLayer.Name(v)).endswith("_Cu")
    )
    if len(copper_values) < _MIN_COPPER_LAYERS_FOR_INTERNAL_CASE:
        return None
    # Cualquier capa que no sea el primer ni el último valor del stackup
    # ordenado es interna (F.Cu/B.Cu son siempre los extremos del enum).
    internal = copper_values[1]
    name = str(BoardLayer.Name(internal)).removeprefix("BL_").replace("_", ".")
    return internal, name


def _find_via_spanning_layer(vias: list[object], target_layer_value: int) -> str | None:
    """KIID de la primera via cuyo span (extremos normalizados del drill)
    cubre ``target_layer_value``, o ``None`` si ninguna lo hace.

    NO asume que toda via es pasante (auditoría de sesión 43, Codex: elegir
    ``vias[0]`` a ciegas rompe el test si el board tiene una via ciega/
    enterrada cuyo span no llega a la capa elegida) — el MVP de
    ``kicad-mcp`` asume pasantes por diseño (``bridge/ipc.py``), pero un
    board real preparado a mano para este fixture podría no respetarlo.
    """
    for via in vias:
        drill = via.padstack.drill  # type: ignore[attr-defined]
        lo, hi = sorted((int(drill.start_layer), int(drill.end_layer)))
        if lo <= target_layer_value <= hi:
            return str(via.id.value)  # type: ignore[attr-defined]
    return None


@pytest.mark.integration_gui
async def test_get_tracks_layer_filter_includes_through_via_on_internal_layer() -> None:
    """``get_tracks(layer=<capa interna>)`` debe incluir una via pasante
    existente cuyo span atraviesa esa capa — el caso exacto que
    ``_copper_on_layer`` no reconocía antes del fix de sesión 43.
    """
    _guard()
    pcb_path = _resolve_root_pcb()
    bridge = _preflight_same_board_open(pcb_path)
    board = bridge.get_open_board()
    assert board is not None  # _preflight_same_board_open ya lo garantizó

    raw = board.raw
    internal_layer = _internal_copper_layer(raw)
    if internal_layer is None:
        pytest.skip(
            "proyecto sin capas internas de cobre habilitadas (< "
            f"{_MIN_COPPER_LAYERS_FOR_INTERNAL_CASE}); el caso que este fix "
            "arregla no es alcanzable en un board de 2 capas. Ver "
            "docs/BACKLOG.md 'Hallazgo colateral' (sesión 42/43): el "
            "protocolo GUI de este proyecto no tiene hoy un proyecto de "
            "referencia multicapa — preparar uno para ejecutar este test."
        )
    internal_layer_value, internal_layer_name = internal_layer

    vias = list(raw.get_vias())
    if not vias:
        pytest.skip("board sin ninguna via — no hay caso para ejercitar")
    target_kiid = _find_via_spanning_layer(vias, internal_layer_value)
    if target_kiid is None:
        pytest.skip(
            f"ninguna via del board atraviesa {internal_layer_name!r} — "
            "preparar el fixture con al menos una via pasante F.Cu-B.Cu"
        )

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        listed = await client.call_tool(
            "get_tracks", {"layer": internal_layer_name, "max_tokens": 4000}
        )
    assert not listed.isError, _text(listed)
    text = _text(listed)
    assert target_kiid in text, (
        f"get_tracks(layer={internal_layer_name!r}) no incluyó la via pasante "
        f"{target_kiid} — regresión del fix de sesión 43 (_copper_on_layer)"
    )
