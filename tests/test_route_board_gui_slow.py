"""Test real del round-trip de ``route_board`` (T3, marker ``integration_gui_slow``).

Round-trip COMPLETO contra una COPIA del proyecto chico de spike
(``/tmp/spike-route-proyecto``, 24 fp / 64 conexiones ratsnest). NO se ruteo el
board de 189 fp de gui-test-project (demasiado lento/denso). Verifica:

- JSON estructurado (sesión 17, P2.2): ``nets.ruteadas == nets.ruteables``
  (100% del ratsnest), ``drc.err_post == 0``, ``tracks_added > 0``,
  ``route_ms`` presente (F-08).
- flag ``live_stale`` activo → una mutación (``move_footprint``) queda BLOQUEADA
  con ``EXTERNAL_EDIT_DETECTED``.
- ``get_world_context(kind='pcb', confirm_reloaded=true)`` (recarga simulada)
  destraba el flag.

Requisitos de SISTEMA (D-14.5): Java ≥17, ``KICAD_MCP_FREEROUTING_JAR`` al jar,
``pcbnew`` en el python del sistema. Corre AISLADO (~2 min; contención IPC
D-12.7). Se salta si falta cualquier requisito. La copia usa un contorno
Edge.Cuts dibujado en setup (el board de spike no lo trae y ``route_board`` de
producción NO lo dibuja solo, D-14.4).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.autoroute import _JAR_ENV, _SYSTEM_PYTHON_DEFAULT
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store

_SPIKE_SRC = Path("/tmp/spike-route-proyecto")

# Setup: dibuja un contorno rectangular Edge.Cuts (bbox+5 mm) con el pcbnew del
# SISTEMA y guarda. Es scaffolding del test (en producción lo hace
# draw_board_outline vía IPC sobre el board vivo).
_DRAW_OUTLINE = r"""
import sys, pcbnew
src = sys.argv[1]
b = pcbnew.LoadBoard(src)
FROM_MM = pcbnew.FromMM
bb = b.ComputeBoundingBox(False)
m = FROM_MM(5.0)
x0, y0 = bb.GetX() - m, bb.GetY() - m
x1, y1 = bb.GetRight() + m, bb.GetBottom() + m
pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
for i in range(4):
    seg = pcbnew.PCB_SHAPE(b)
    seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
    seg.SetLayer(pcbnew.Edge_Cuts)
    seg.SetStart(pcbnew.VECTOR2I(*pts[i]))
    seg.SetEnd(pcbnew.VECTOR2I(*pts[(i + 1) % 4]))
    seg.SetWidth(FROM_MM(0.1))
    b.Add(seg)
pcbnew.SaveBoard(src, b)
print("OUTLINE_OK")
"""


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _guard() -> None:
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/pruebas-gui.md")
    if not _SPIKE_SRC.is_dir():
        pytest.skip(f"falta {_SPIKE_SRC} (proyecto chico de spike)")
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


@pytest.mark.integration_gui_slow
async def test_route_board_real_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _guard()
    # Copia limpia (sin runs/backups/lck) del proyecto de spike.
    dst = tmp_path / "spike"
    shutil.copytree(
        _SPIKE_SRC,
        dst,
        ignore=shutil.ignore_patterns("runs", "*-backups", "*.lck", "*.dsn", "report.txt"),
    )
    pcb = next(dst.glob("*.kicad_pcb"))

    # Dibuja el contorno Edge.Cuts en la copia (setup; ver módulo).
    draw = subprocess.run(
        [_SYSTEM_PYTHON_DEFAULT, "-c", _DRAW_OUTLINE, str(pcb)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "OUTLINE_OK" in draw.stdout, draw.stderr

    monkeypatch.setenv("KICAD_MCP_PROJECT", str(dst))
    g1.reset_session_state()
    get_default_store().reset()

    server = _server()
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        # --- ruteo real (~2 min) -------------------------------------------
        res = await client.call_tool("route_board", {})
        assert not res.isError, _text(res)
        payload = json.loads(_text(res))
        ruteables = payload["nets"]["ruteables"]
        ruteadas = payload["nets"]["ruteadas"]
        assert ruteables >= 60, f"ratsnest esperado ~64, fue {ruteables}"
        assert ruteadas == ruteables, (
            f"ruteo incompleto: {ruteadas}/{ruteables} — bloqueadas: "
            f"{payload['nets']['bloqueadas']}"
        )
        assert payload["drc"]["err_post"] == 0, f"DRC con {payload['drc']} errores post-route"
        assert payload["tracks_added"] > 0
        assert payload["route_ms"] > 0  # F-08: route_ms ahora llega al agente

        # --- flag D-14.1: mutación bloqueada post-route --------------------
        assert get_default_store().is_live_stale() is True
        blocked = await client.call_tool(
            "move_footprint", {"ref": "U1", "x_mm": 10.0, "y_mm": 10.0}
        )
        assert blocked.isError
        assert "EXTERNAL_EDIT_DETECTED" in _text(blocked)

        # --- destrabe: confirm_reloaded (recarga simulada) -----------------
        # Lee el board VIVO abierto (que puede ser cualquiera / grande), así que
        # damos presupuesto holgado: sólo nos importa que la call funcione y el
        # flag quede limpio.
        reloaded = await client.call_tool(
            "get_world_context",
            {"kind": "pcb", "confirm_reloaded": True, "max_tokens": 50000},
        )
        assert not reloaded.isError, _text(reloaded)
        assert "[AVISO]" not in _text(reloaded)
        assert get_default_store().is_live_stale() is False
