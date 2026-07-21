"""Test E2E del gate de cierre de sesión 18 (P3.3, D-V3.1).

**Gate:** una sesión de ruteo iterativo del despertador con CERO contactos
humanos de recarga. Ciclo por iteración: ``delete_track`` (simula edición) →
``route_board`` (re-rutea, escribe a disco, recarga el editor vivo
automáticamente — P3.1) → ``get_tracks`` inmediatamente después ve el cobre
NUEVO, sin ``[AVISO]`` de ``live_stale`` y sin ningún File→Revert humano.
Tres iteraciones. Cierre: ``save_board`` persiste el estado final.

**Corre DIRECTO sobre el proyecto que ``KICAD_MCP_PROJECT`` apunta — el
mismo que debe estar YA ABIERTO en el PCB Editor de KiCad.** NO copia el
fixture a un tmp_path aislado: ``get_tracks``/``delete_track`` mutan por IPC
lo que sea que esté abierto en KiCad (ignoran ``KICAD_MCP_PROJECT``),
mientras que ``route_board`` opera sobre el archivo que ``KICAD_MCP_PROJECT``
resuelve — si apuntaran a archivos DISTINTOS, el propio test reproduciría el
split-brain que existe para probar que no pasa (descubierto empíricamente:
la primera corrida real de este test, con ``KICAD_MCP_PROJECT`` apuntando a
una copia aislada, borró un track del board VIVO vía IPC y nunca lo
re-ruteó, porque ``route_board`` ruteó la copia — no lo que KiCad tenía
abierto). ``_preflight_same_board_open`` verifica esa coincidencia ANTES de
mutar nada; si no coincide, salta con un mensaje accionable en vez de
mutar a ciegas.

Usar `tests/fixtures/despertador-routed/` como base del proyecto que se deja
abierto en KiCad (fuera de este test — protocolo manual, ver
``docs/pruebas-gui.md``); no se lee directo al contexto del agente de
desarrollo (regla de ``CLAUDE.md``), sólo lo abre el humano en KiCad.

Requisitos de SISTEMA (D-14.5, mismos que ``test_route_board_gui_slow.py``):
``KICAD_MCP_GUI_TEST=1``, ``KICAD_MCP_PROJECT`` apuntando al proyecto
YA ABIERTO en KiCad, Java ≥17, ``KICAD_MCP_FREEROUTING_JAR`` al jar,
``pcbnew`` en el python del sistema. Se salta si falta cualquier requisito
— 3 ruteos completos contra un board denso (313+ tracks) son más lentos que
el spike de 24 fp de sesión 14: corridas reales de sesión 18 contra este
mismo board fueron de 235 s a 925 s (15.4 min) por ruteo — **el test
completo puede tardar entre 15 y 90 min**, altamente variable
(nondeterminismo de Freerouting ya documentado en sesión 17/D2); correr
AISLADO (contención IPC D-12.7). **Muta de forma permanente y real el
ruteo del proyecto abierto** — no es una copia descartable como en otros
tests GUI.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.autoroute import _JAR_ENV, _SYSTEM_PYTHON_DEFAULT
from kicad_mcp.bridge.ipc import IpcBridge
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store
from kicad_mcp.tools.world import _resolve_root_pcb

# GND es el net universal de cualquier board con alimentación — apuesta segura
# sin necesitar leer el fixture al contexto (regla de CLAUDE.md: los fixtures
# se procesan por código, nunca se leen directo). Si algún día el proyecto
# abierto cambia y GND deja de existir, el test falla con un mensaje
# explícito (no un skip silencioso) en el primer ``get_tracks``.
_NET = "GND"


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


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
    """Verifica que ``KICAD_MCP_PROJECT`` coincide con el board VIVO abierto
    en KiCad antes de mutar nada — ver docstring del módulo (hallazgo real
    de la primera corrida). Lectura pura (``get_open_board``/
    ``get_open_board_path``), sin efectos colaterales."""
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay PCB Editor abierto en KiCad")
    open_path = bridge.get_open_board_path(board)
    if open_path is None or open_path.resolve() != pcb_path.resolve():
        pytest.skip(
            f"KICAD_MCP_PROJECT ({pcb_path}) no coincide con el board abierto "
            f"en KiCad ({open_path}) — abrí ESE proyecto en KiCad antes de "
            "correr este test (evita el split-brain descubierto en la "
            "primera corrida real, ver docstring del módulo)"
        )


def _server():  # type: ignore[no-untyped-def]
    from kicad_mcp.server import create_server

    return create_server()


def _parse_track_ids(tracks_text: str) -> list[str]:
    """Extrae los KIID de las líneas ``T``/``A`` (track/arco) del formato de
    ``get_tracks`` (``docs/specs/tool-catalog.md``: ``T <id> net layer w...``).
    Ignora vías (``V``) — no aplica a este test."""
    ids = []
    for line in tracks_text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("T", "A"):
            ids.append(parts[1])
    return ids


@pytest.mark.integration_gui_slow
async def test_iterative_routing_zero_human_reload_touches() -> None:
    """3 iteraciones delete_track→route_board→get_tracks, 0 File→Revert (D-V3.1)."""
    _guard()
    pcb_path = _resolve_root_pcb()
    _preflight_same_board_open(pcb_path)
    g1.reset_session_state()
    get_default_store().reset()

    reload_flags: list[object] = []
    server = _server()
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        for iteration in range(3):
            # 1. Estado inicial del net — confirma que hay algo para simular
            # una edición real (borrar un track existente).
            before = await client.call_tool("get_tracks", {"net": _NET, "max_tokens": 8000})
            assert not before.isError, f"iteración {iteration}: {_text(before)}"
            before_ids = _parse_track_ids(_text(before))
            assert before_ids, (
                f"iteración {iteration}: sin tracks en net={_NET} para simular "
                "una edición — el fixture puede haber cambiado"
            )

            # 2. Simula una mutación de sesión: borra un track del net.
            deleted = await client.call_tool("delete_track", {"id": before_ids[0]})
            assert not deleted.isError, f"iteración {iteration}: {_text(deleted)}"

            # 3. Re-rutea. route_board escribe a disco Y recarga el editor
            # vivo automáticamente (P3.1) — CERO contactos humanos.
            # timeout_s=1800 (no el default de 600): corrida real de sesión
            # 18 contra este mismo board confirmó que Freerouting necesita
            # hasta ~925 s (15.4 min) para completar el ratsnest tras un
            # delete_track — 600 s no alcanza de forma consistente
            # (nondeterminismo ya documentado en sesión 17/D2).
            routed = await client.call_tool("route_board", {"timeout_s": 1800})
            assert not routed.isError, f"iteración {iteration}: {_text(routed)}"
            payload = json.loads(_text(routed))
            reload_flags.append(payload["reloaded"])
            assert payload["reloaded"] is True, (
                f"iteración {iteration}: reloaded={payload['reloaded']!r} — "
                "se esperaba recarga automática (editor abierto sobre el target); "
                "si esto falla, el gate D-V3.1 no se cumple sin contacto humano"
            )
            assert get_default_store().is_live_stale() is False, (
                f"iteración {iteration}: live_stale sigue activo pese a reloaded=True"
            )
            assert _NET not in payload["nets"]["bloqueadas"], (
                f"iteración {iteration}: {_NET} bloqueada tras re-rutear — "
                f"{payload['nets']['bloqueadas']}"
            )

            # 4. get_tracks INMEDIATAMENTE después ve el cobre NUEVO — sin
            # [AVISO] de live_stale, sin File→Revert. Éste es el gate.
            after = await client.call_tool("get_tracks", {"net": _NET, "max_tokens": 8000})
            assert not after.isError, f"iteración {iteration}: {_text(after)}"
            after_text = _text(after)
            assert "[AVISO]" not in after_text, (
                f"iteración {iteration}: get_tracks sigue avisando editor vivo "
                "detrás del disco — la recarga automática no sincronizó"
            )
            after_ids = _parse_track_ids(after_text)
            assert after_ids, f"iteración {iteration}: net={_NET} quedó sin tracks post-route"

        # Cierre: 0 contactos humanos en las 3 iteraciones (gate D-V3.1).
        assert reload_flags == [True, True, True]

        # Persiste el estado final a disco — no debe bloquearse por el guard
        # P3.2 (el reload de la última iteración ya sincronizó vivo==disco).
        saved = await client.call_tool("save_board", {})
        assert not saved.isError, _text(saved)

    # El .kicad_pcb en disco refleja el último route_board (contiene tracks
    # de GND — verificación mínima sin parsear el S-expression completo).
    final_bytes = pcb_path.read_bytes()
    assert b"GND" in final_bytes
