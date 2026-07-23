"""Test integration_gui de sesión 21 — F-D3-03: ``route_board.drc`` en vivo
contra KiCad 10.0.4 real (kicad-cli real, no mockeado).

El escenario EXACTO del D3 (mismo total DRC pre/post, composición distinta)
ya está cubierto de forma determinística por el test unit
(``tests/test_route_board.py::test_route_board_err_introducidos_by_identity_not_totales``)
— forzarlo de forma reproducible contra un round-trip REAL de Freerouting
(no determinístico en el detalle exacto de qué traza dónde) no es práctico.
Este test valida en cambio el camino real end-to-end que el fix toca:
``bridge.rules.run_drc`` (kicad-cli real) → ``diff_violations`` (identidad,
no resta) → contrato JSON de ``route_board`` — con dos chequeos honestos:

1. El contrato trae los 3 campos nuevos (``err_resueltos``,
   ``por_tipo_introducidos``) con los tipos esperados, coexistiendo con los
   campos viejos (F3: nada se renombra).
2. Consistencia interna: ``err_introducidos`` de ``route_board`` coincide con
   lo que un ``run_drc()`` independiente post-route mediría por identidad
   contra el ``run_drc()`` pre-route — es decir, el campo no miente respecto
   al ground truth (el problema original de F-03).

Requiere Freerouting real (Java + jar) — mismo requisito que
``test_zones_e2e_gui.py``. Corre DIRECTO sobre el proyecto que
``KICAD_MCP_PROJECT`` apunta. **Muta de forma permanente** el board (rutea
de nuevo) — no es descartable.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.autoroute import _JAR_ENV, _SYSTEM_PYTHON_DEFAULT
from kicad_mcp.bridge.ipc import IpcBridge
from kicad_mcp.bridge.rules import diff_violations, run_drc
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store
from kicad_mcp.tools.world import _resolve_root_pcb

_ROUTE_TIMEOUT_S = 900


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _json(result: CallToolResult) -> dict[str, Any]:
    return json.loads(_text(result))


def _guard() -> None:
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/pruebas-gui.md")
    if not os.environ.get("KICAD_MCP_PROJECT"):
        pytest.skip(
            "KICAD_MCP_PROJECT no seteada — debe apuntar al proyecto YA "
            "ABIERTO en el PCB Editor de KiCad"
        )
    jar = os.environ.get(_JAR_ENV)
    if not jar or not Path(jar).is_file():
        pytest.skip(f"{_JAR_ENV} no seteada o inexistente (requisito de ruteo)")
    if shutil.which("java") is None:
        pytest.skip("java no está en PATH (requisito de ruteo)")
    if not Path(_SYSTEM_PYTHON_DEFAULT).exists():
        pytest.skip(f"{_SYSTEM_PYTHON_DEFAULT} ausente (pcbnew del sistema)")


def _preflight_same_board_open(pcb_path: Path) -> None:
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


def _server():  # type: ignore[no-untyped-def]
    from kicad_mcp.server import create_server

    return create_server()


@pytest.mark.integration_gui_slow
async def test_route_board_drc_contract_matches_independent_run_drc() -> None:
    """``route_board.drc`` (identidad, F-D3-03) no miente respecto a un
    ``run_drc()`` independiente pre/post — validación end-to-end contra
    kicad-cli real, no mockeado."""
    _guard()
    pcb_path = _resolve_root_pcb()
    _preflight_same_board_open(pcb_path)
    g1.reset_session_state()
    get_default_store().reset()

    # Ground truth INDEPENDIENTE: run_drc real ANTES de rutear (bridge
    # directo, no la tool — mismo mecanismo que route_board usa internamente
    # para su propio pre_report, permite comparar aparte).
    pre_report_independiente = run_drc(pcb_path)

    mcp = _server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        route_result = await client.call_tool("route_board", {"timeout_s": _ROUTE_TIMEOUT_S})
        assert not route_result.isError, _text(route_result)
        payload = _json(route_result)
        drc = payload["drc"]

        # 1. Contrato: los 3 campos nuevos coexisten con los viejos (F3).
        assert set(drc.keys()) >= {
            "err_preexistentes",
            "err_post",
            "err_introducidos",
            "err_resueltos",
            "por_tipo",
            "por_tipo_introducidos",
        }
        assert isinstance(drc["err_resueltos"], int)
        assert isinstance(drc["por_tipo_introducidos"], dict)

        # 2. Consistencia: ground truth POST independiente (run_drc real
        # sobre el .kicad_pcb que route_board acaba de escribir a disco).
        post_report_independiente = run_drc(pcb_path)
        introducidas_gt, resueltas_gt, por_tipo_gt = diff_violations(
            pre_report_independiente.violations, post_report_independiente.violations
        )
        assert drc["err_introducidos"] == introducidas_gt, (
            f"route_board.drc.err_introducidos ({drc['err_introducidos']}) no "
            f"coincide con el ground truth independiente ({introducidas_gt}) — "
            "el contrato miente (el bug original de F-03)"
        )
        assert drc["err_resueltos"] == resueltas_gt
        assert drc["por_tipo_introducidos"] == por_tipo_gt
