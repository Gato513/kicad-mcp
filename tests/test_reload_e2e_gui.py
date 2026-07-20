"""Test E2E del gate de cierre de sesión 18 (P3.3, D-V3.1).

**Gate:** una sesión de ruteo iterativo del despertador con CERO contactos
humanos de recarga. Ciclo por iteración: ``delete_track`` (simula edición) →
``route_board`` (re-rutea, escribe a disco, recarga el editor vivo
automáticamente — P3.1) → ``get_tracks`` inmediatamente después ve el cobre
NUEVO, sin ``[AVISO]`` de ``live_stale`` y sin ningún File→Revert humano.
Tres iteraciones. Cierre: ``save_board`` persiste el estado final.

Corre contra una COPIA de ``tests/fixtures/despertador-routed/`` (313 tracks,
21 vías, fixture ya ruteado de sesión 17 — no se lee directamente al
contexto del agente de desarrollo, sólo se copia y se procesa por código,
regla de ``CLAUDE.md``).

Requisitos de SISTEMA (D-14.5, mismos que ``test_route_board_gui_slow.py``):
``KICAD_MCP_GUI_TEST=1``, Java ≥17, ``KICAD_MCP_FREEROUTING_JAR`` al jar,
``pcbnew`` en el python del sistema, KiCad con el PCB Editor abierto sobre
la copia. Se salta si falta cualquier requisito — 3 ruteos completos contra
un board denso (313 tracks) son más lentos que el spike de 24 fp de sesión
14; correr AISLADO (contención IPC D-12.7).
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
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store

_FIXTURE_SRC = Path(__file__).parent / "fixtures" / "despertador-routed"

# GND es el net universal de cualquier board con alimentación — apuesta segura
# sin necesitar leer el fixture al contexto (regla de CLAUDE.md: los fixtures
# se procesan por código, nunca se leen directo). Si algún día el fixture
# cambia y GND deja de existir, el test falla con un mensaje explícito (no
# un skip silencioso) en el primer ``get_tracks``.
_NET = "GND"


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _guard() -> None:
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/pruebas-gui.md")
    if not _FIXTURE_SRC.is_dir():
        pytest.skip(f"falta {_FIXTURE_SRC} (fixture despertador-routed)")
    jar = os.environ.get(_JAR_ENV)
    if not jar or not Path(jar).is_file():
        pytest.skip(f"{_JAR_ENV} no seteada o inexistente (requisito de ruteo)")
    if shutil.which("java") is None:
        pytest.skip("java no está en PATH (requisito de ruteo)")
    if not Path(_SYSTEM_PYTHON_DEFAULT).exists():
        pytest.skip(f"{_SYSTEM_PYTHON_DEFAULT} ausente (pcbnew del sistema)")


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
async def test_iterative_routing_zero_human_reload_touches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """3 iteraciones delete_track→route_board→get_tracks, 0 File→Revert (D-V3.1)."""
    _guard()
    dst = tmp_path / "despertador"
    shutil.copytree(_FIXTURE_SRC, dst)
    pcb_path = next(dst.glob("*.kicad_pcb"))
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(dst))
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
            routed = await client.call_tool("route_board", {})
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
