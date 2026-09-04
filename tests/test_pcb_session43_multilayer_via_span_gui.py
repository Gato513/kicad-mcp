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

**Verificación PENDIENTE de ejecución humana.** El protocolo GUI de este
proyecto (``docs/guias/pruebas-gui.md``) no tiene, hoy, ningún proyecto de
referencia con capas internas habilitadas — todos los fixtures/proyectos de
la Validation Suite usados hasta sesión 42 son de 2 capas, donde este fix es
un no-op por construcción (ver "Costo y compatibilidad" en el reporte de
sesión 43). Este test se escribe con guard de skip explícito por esa razón
(precedente: sesión 32d, ``test_pcb_session32d_stitching_gui_slow.py``,
"verificación end-to-end escrita pero pendiente de ejecución humana") — NO
se declara verde sin haber corrido contra un proyecto real de 4+ capas de
cobre con al menos una via.

Es de SOLO LECTURA (``get_tracks``, sin mutación) — no requiere una copia
descartable del fixture, pero sí requiere que ``KICAD_MCP_PROJECT`` apunte a
un proyecto multicapa ya abierto en el PCB Editor (ver ``docs/pruebas-gui.md``).
"""

from __future__ import annotations

import os

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.ipc import IpcBridge

_MIN_COPPER_LAYERS_FOR_INTERNAL_CASE = 4


def _guard() -> None:
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/pruebas-gui.md")
    if not os.environ.get("KICAD_MCP_PROJECT"):
        pytest.skip("KICAD_MCP_PROJECT no definida; apuntar al proyecto abierto")


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _server():  # type: ignore[no-untyped-def]
    from kicad_mcp.server import create_server

    return create_server()


def _internal_copper_layer_name(raw_board: object) -> str | None:
    """Nombre de una capa de cobre INTERNA (ni F.Cu ni B.Cu) habilitada del
    board, o ``None`` si el board no tiene ninguna (típicamente 2 capas).
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
    return str(BoardLayer.Name(internal)).removeprefix("BL_").replace("_", ".")


@pytest.mark.integration_gui
async def test_get_tracks_layer_filter_includes_through_via_on_internal_layer() -> None:
    """``get_tracks(layer=<capa interna>)`` debe incluir una via pasante
    existente cuyo span atraviesa esa capa — el caso exacto que
    ``_copper_on_layer`` no reconocía antes del fix de sesión 43.
    """
    _guard()
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")

    raw = board.raw
    internal_layer_name = _internal_copper_layer_name(raw)
    if internal_layer_name is None:
        pytest.skip(
            "proyecto sin capas internas de cobre habilitadas (< "
            f"{_MIN_COPPER_LAYERS_FOR_INTERNAL_CASE}); el caso que este fix "
            "arregla no es alcanzable en un board de 2 capas. Ver "
            "docs/BACKLOG.md 'Hallazgo colateral' (sesión 42/43): el "
            "protocolo GUI de este proyecto no tiene hoy un proyecto de "
            "referencia multicapa — preparar uno para ejecutar este test."
        )

    vias = list(raw.get_vias())
    if not vias:
        pytest.skip("board sin ninguna via — no hay caso para ejercitar")
    # El MVP asume toda via pasante (bridge/ipc.py, docstring de add_via /
    # enforce_hole_clearance): cualquier via existente cruza el stackup
    # completo, así que la primera alcanza.
    target_kiid = str(vias[0].id.value)

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
