"""H1/H2 de sesión 32d contra el motor real (marker ``integration_gui_slow``).

F-D5-01 (``docs/investigacion/32c-f-d5-01.md``): stitching automático de
pads huérfanos post-refill en ``route_board`` (D1-D3, sesión 32d). Estos
dos tests ejercitan el fix END-TO-END contra los fixtures reales de la
Validation Suite — Freerouting real, refill real, DRC real — NO mocks.

**Protocolo manual, igual que ``test_route_board_gui_slow.py``** (ver
``docs/guias/pruebas-gui.md``): requieren KiCad con el API server activo Y
el proyecto copiado abierto en el PCB Editor (`KICAD_MCP_GUI_TEST=1`,
`KICAD_MCP_PROJECT` apuntando a la copia). No hay forma de automatizar
"abrir el proyecto en KiCad" (F4, MVP) — confirmado en esta sesión con un
probe directo por IPC (``get_open_board()`` devuelve ``KICAD_CLI_FAILED``
con ``ipc_status="unhandled"`` cuando ningún PCB Editor está en foco, sin
importar que KiCad esté corriendo). Por eso este archivo quedó ESCRITO pero
NO CORRIDO por el agente en sesión 32d — requiere la acción humana de abrir
cada proyecto en el PCB Editor antes de ejecutar. Ver
``docs/historico/sesiones/32d-reporte.md`` §"Verificación pendiente".

**H1 — re-baselineada a anavi-dev-mic** (sesión 32d, ver docstring del
canario unit ``test_pcb_session32d_orphan_pads_stitching_canary.py`` para
el análisis comparativo completo): ``MK1.3`` (F.Cu, zona GND sólo en B.Cu)
es la topología "capas opuestas" que el guardrail #4 fue diseñado para
aceptar. Tras ``route_board``, se espera ``stitched_vias`` con 1 entrada y
``unconnected == 0`` en un DRC de verificación posterior.

**H2 — macro-pad-12** (``J4.3``/``J5.3``): pad y única zona GND en la MISMA
capa (B.Cu) — el guardrail #4 rechaza por diseño (no hay cobre GND en F.Cu
para que la vía aterrice). Se espera ``orphan_pads`` con ambos pads,
``reason == "sin zona en capa opuesta"``, y NINGUNA vía nueva creada para
esos pads.

**Riesgo de no-determinismo, documentado honestamente:** a diferencia de la
reproducción de 32c/32d (offline, ``kicad-cli pcb drc --refill-zones``
sobre el fixture EXACTO commiteado), estos tests invocan ``route_board``
completo — Freerouting vuelve a rutear el board DESDE CERO (no incremental,
D-14.2). El mecanismo geométrico (corredor angosto estrangulado por cobre
ajeno, D-19.1) depende de POR DÓNDE decida pasar Freerouting en esta
corrida particular; no hay garantía de que reproduzca exactamente la
topología que 32c aisló. Si H1/H2 no reproducen en una corrida dada, no es
necesariamente una refutación del fix — puede ser que Freerouting,
esta vez, haya evitado el corredor angosto. Repetir antes de escalar.
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
from kicad_mcp.bridge.rules import run_drc
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store

_DEVMIC_SRC = Path("validation-suite/level-a/anavi-dev-mic/working")
_MACROPAD_SRC = Path("validation-suite/level-b/anavi-macro-pad-12/working")


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _guard(fixture_src: Path) -> None:
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/guias/pruebas-gui.md")
    if not fixture_src.is_dir():
        pytest.skip(f"falta {fixture_src}")
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
async def test_h1_devmic_stitching_resolves_mk1_3(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """H1 (re-baselineada, sesión 32d): sobre una copia de anavi-dev-mic,
    ``route_board`` debe stitchear ``MK1.3`` (GND) y dejar
    ``unconnected == 0`` en un DRC de verificación posterior.

    Protocolo previo (humano, obligatorio):
      1. ``cp -r validation-suite/level-a/anavi-dev-mic/working /tmp/f-d5-01-devmic-32d``
      2. Abrir ``/tmp/f-d5-01-devmic-32d/anavi-dev-mic.kicad_pro`` en KiCad,
         abrir también el ``.kicad_pcb`` (PCB Editor en foco).
      3. ``export KICAD_MCP_GUI_TEST=1 KICAD_MCP_PROJECT=/tmp/f-d5-01-devmic-32d
         KICAD_MCP_FREEROUTING_JAR=<jar>``
      4. ``uv run pytest -m integration_gui_slow -k h1_devmic -v``
    """
    _guard(_DEVMIC_SRC)
    project_env = os.environ.get("KICAD_MCP_PROJECT")
    assert project_env, "KICAD_MCP_PROJECT debe apuntar a la copia con el PCB Editor abierto"
    project = Path(project_env)
    pcb = next(project.glob("*.kicad_pcb"))

    g1.reset_session_state()
    get_default_store().reset()

    server = _server()
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        res = await client.call_tool("route_board", {})
        assert not res.isError, _text(res)
        payload = json.loads(_text(res))

    assert payload["reloaded"] is True, (
        "el PCB Editor no tenía este proyecto abierto/sincronizado — sin "
        "reloaded=True el stitching no puede haber corrido; revisar el paso 2 del protocolo"
    )
    stitched = payload.get("stitched_vias", [])
    assert stitched, (
        f"esperaba ≥1 vía stitcheada (MK1.3); payload.orphan_pads={payload.get('orphan_pads')}"
    )
    assert any(v["net"] == "GND" for v in stitched)

    # Verificación independiente: DRC real sobre el disco post-route.
    verify = run_drc(pcb)
    assert verify.unconnected == 0, f"sigue habiendo {verify.unconnected} unconnected_items"


@pytest.mark.integration_gui_slow
async def test_h2_macro_pad_12_guardrail_rejects_same_layer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """H2: sobre una copia de anavi-macro-pad-12, ``route_board`` NO debe
    stitchear ``J4.3``/``J5.3`` (guardrail #4: pad y zona GND en la misma
    capa B.Cu, sin cobre GND en F.Cu) — deben aparecer en ``orphan_pads``
    con la razón correcta, sin ninguna vía nueva para esos pads.

    Protocolo previo (humano, obligatorio) — igual al de H1, con:
      1. ``cp -r validation-suite/level-b/anavi-macro-pad-12/working /tmp/f-d5-01-macro-pad-32d``
      2. Abrir ``/tmp/f-d5-01-macro-pad-32d/anavi-macro-pad-12.kicad_pro`` en KiCad.
      3. ``export KICAD_MCP_GUI_TEST=1 KICAD_MCP_PROJECT=/tmp/f-d5-01-macro-pad-32d
         KICAD_MCP_FREEROUTING_JAR=<jar>``
      4. ``uv run pytest -m integration_gui_slow -k h2_macro_pad_12 -v``
    """
    _guard(_MACROPAD_SRC)
    project_env = os.environ.get("KICAD_MCP_PROJECT")
    assert project_env, "KICAD_MCP_PROJECT debe apuntar a la copia con el PCB Editor abierto"

    g1.reset_session_state()
    get_default_store().reset()

    server = _server()
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        res = await client.call_tool("route_board", {})
        assert not res.isError, _text(res)
        payload = json.loads(_text(res))

    assert payload["reloaded"] is True, (
        "el PCB Editor no tenía este proyecto abierto/sincronizado — sin "
        "reloaded=True la detección no puede haber corrido; revisar el paso 2 del protocolo"
    )
    orphans = payload.get("orphan_pads", [])
    gnd_orphans = [o for o in orphans if o["net"] == "GND"]
    if not gnd_orphans and not payload.get("stitched_vias"):
        pytest.skip(
            "esta corrida de Freerouting no reprodujo ningún pad huérfano GND — "
            "no-determinismo documentado en el docstring del módulo; reintentar"
        )
    for o in gnd_orphans:
        assert o["reason"] == "sin zona en capa opuesta", o
    # El fix NO debe stitchear nada para el net GND en este board (la única
    # zona GND está en B.Cu, sin par en F.Cu).
    stitched_gnd = [v for v in payload.get("stitched_vias", []) if v["net"] == "GND"]
    assert stitched_gnd == [], f"stitching inesperado en GND same-layer: {stitched_gnd}"
