"""Tests de la tool ``get_world_context``.

- ``unit``: llama la tool con un state builder mockeado (estado fake).
- ``integration``: ejerce el pipeline completo contra las fixtures 001/003.

Contrato: la tool devuelve el string TOON puro (sin envelope JSON). La
cabecera lleva ``snap`` y ``kind`` (sesión 03).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.ipc import (
    BBoxMm,
    BoardContext,
    BoardHandle,
    FootprintData,
    FootprintPadData,
    IpcBridge,
    Mm,
)
from kicad_mcp.errors import ErrorCode, KicadMcpError
from kicad_mcp.server import create_server
from kicad_mcp.toon.schema import Component, NormalizedState, Pin
from tests.conftest import mirror_fixture

FIXTURES = Path(__file__).parent / "fixtures"


def _toon(result: CallToolResult) -> str:
    assert result.isError is False, f"error: {result}"
    assert len(result.content) == 1
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _toon_error(result: CallToolResult) -> str:
    """Texto del bloque de error (result.isError True)."""
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _fake_state() -> NormalizedState:
    return NormalizedState(
        kind="sch",
        snap=1,
        components=(
            Component(
                ref="U1",
                value="STM32",
                lib="MCU:STM32",
                x=100.0,
                y=50.0,
                pins=(Pin(p="1", net="3V3"), Pin(p="2", net="GND")),
            ),
            Component(
                ref="C1",
                value="100nF",
                lib="Device:C",
                x=105.0,
                y=50.0,
                pins=(Pin(p="1", net="3V3"), Pin(p="2", net="GND")),
            ),
        ),
    )


@pytest.mark.unit
async def test_world_context_with_fake_state(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_state()
    monkeypatch.setattr(
        "kicad_mcp.tools.world.build_state_cached",
        lambda *_, **__: (fake, False),
    )
    monkeypatch.setattr(
        "kicad_mcp.tools.world._resolve_root_schematic", lambda: Path("/tmp/fake.kicad_sch")
    )

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_world_context", {"max_tokens": 800})
    toon = _toon(result)
    # La cabecera lleva kind (SCH) y snap; no hace falta envelope JSON.
    assert toon.startswith("SCH|v1|2c|2n|snap:1\n")
    assert "U1  STM32" in toon
    assert "GND: C1.2 U1.2" in toon


@pytest.mark.integration
async def test_world_context_full_against_fixture_001(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_world_context", {"max_tokens": 800})
    toon = _toon(result)

    lines = toon.splitlines()
    assert lines[0] == "SCH|v1|5c|6n|snap:1"
    # Todos los refs de 001 aparecen como líneas de [C].
    assert any(line.startswith("U1  ") for line in lines)
    assert any(line.startswith("R2  ") for line in lines)
    # SDA net completa: {R1.2, U1.3, J1.3} en orden natural.
    assert "SDA: J1.3 R1.2 U1.3" in toon
    # Sin degradación.
    assert "[DEGRADADO]" not in toon


@pytest.mark.integration
async def test_world_context_with_focus_hides_far_components(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Con focus en J1 y radio pequeño en fixture 003, componentes lejanos van al summary."""
    project = mirror_fixture(FIXTURES / "003_grande", tmp_path / "003")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            # 540 (no 500): la cabecera ahora lleva el token de área
            # (F-01, ``|area:r15@J1``, ~4 tok); con 500 la degradación caía un
            # nivel más (omit_pos) y J1 perdía su POS. El nivel objetivo del
            # test (foco con POS) sigue siendo el mismo con este budget.
            "get_world_context",
            {"max_tokens": 540, "focus_ref": "J1", "radius_mm": 15.0},
        )
    toon = _toon(result)
    assert "[FUERA_DE_AREA]" in toon, "el bloque de resumen debería aparecer con focus+radius"
    # Debe declarar degradación en la línea final.
    assert "[DEGRADADO]" in toon
    assert "fuera_de_area" in toon
    # J1 (el foco) sigue apareciendo con su línea [C] completa.
    lines = toon.splitlines()
    j1_lines = [line for line in lines if line.startswith("J1  ")]
    assert len(j1_lines) == 1, "J1 debe aparecer una vez como componente completo"
    # A este nivel de degradación (probablemente sin omit_pos), J1 muestra POS.
    assert " x" in j1_lines[0]


# --- B1: get_world_context kind="pcb" (D-09.1) --------------------------------


class _FakePcbBridge(IpcBridge):
    """IpcBridge en memoria para la rama viva ``kind="pcb"`` de get_world_context.

    Reproduce el mínimo de estado que ``tools/world.py`` consume: un
    ``get_open_board`` y un ``read_board_context`` que devuelve un
    ``BoardContext`` con footprints en posiciones arbitrarias. No toca socket
    ni kipy. Los modos ``board_mode`` simulan las fronteras de error de D-09.1.
    """

    def __init__(
        self,
        *,
        footprints: tuple[FootprintData, ...] = (),
        board_mode: str = "ok",
    ) -> None:
        import threading

        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._footprints = footprints
        self._board_mode = board_mode
        self.read_calls = 0

    def get_open_board(self) -> BoardHandle | None:  # type: ignore[override]
        if self._board_mode == "kicad_closed":
            raise KicadMcpError(
                code=ErrorCode.KICAD_NOT_RUNNING,
                message="No se pudo conectar al socket IPC de KiCad.",
                hint="Abrí KiCad y habilitá el API server.",
            )
        if self._board_mode == "editor_closed":
            # PCB Editor cerrado: get_board de kipy responde AS_UNHANDLED, que
            # el bridge mapea a KICAD_CLI_FAILED con data.ipc_status="unhandled".
            raise KicadMcpError(
                code=ErrorCode.KICAD_CLI_FAILED,
                message="KiCad no puede manejar get_open_board en el estado actual.",
                hint="El editor requerido no está abierto en KiCad (abrí el PCB Editor).",
                data={"ipc_status": "unhandled"},
            )
        if self._board_mode == "no_board":
            return None
        return BoardHandle(_raw=object())

    def read_board_context(self, board: BoardHandle) -> BoardContext:  # type: ignore[override]
        self.read_calls += 1
        xs = [float(fp.x_mm) for fp in self._footprints] or [0.0]
        ys = [float(fp.y_mm) for fp in self._footprints] or [0.0]
        margin = 100.0
        bbox = BBoxMm(
            Mm(min(xs) - margin), Mm(min(ys) - margin), Mm(max(xs) + margin), Mm(max(ys) + margin)
        )
        return BoardContext(
            refs=tuple(fp.ref for fp in self._footprints),
            bbox=bbox,
            footprints=self._footprints,
        )

    def board_outline(self, board: BoardHandle) -> tuple[BBoxMm, str]:  # type: ignore[override]
        # F-03: sin Edge.Cuts en el fake ⇒ envolvente tight de footprints y
        # outline="none" (mismo contrato que el bridge real cuando no hay borde).
        xs = [float(fp.x_mm) for fp in self._footprints] or [0.0]
        ys = [float(fp.y_mm) for fp in self._footprints] or [0.0]
        return (BBoxMm(Mm(min(xs)), Mm(min(ys)), Mm(max(xs)), Mm(max(ys))), "none")


def _pcb_server(bridge: IpcBridge) -> FastMCP:
    from kicad_mcp.tools.world import register as register_world

    mcp = FastMCP(name="test-pcb-world", instructions="test")
    register_world(mcp, ipc_bridge=bridge)
    return mcp


def _pcb_footprints(specs: list[tuple[str, float, float]]) -> tuple[FootprintData, ...]:
    return tuple(
        FootprintData(
            ref=ref,
            value="V",
            x_mm=Mm(x),
            y_mm=Mm(y),
            pads=(
                FootprintPadData(number="1", net_name="GND"),
                FootprintPadData(number="2", net_name="3V3"),
            ),
            kiid=f"00000000-0000-0000-0000-{i:012x}",
        )
        for i, (ref, x, y) in enumerate(specs)
    )


@pytest.mark.unit
async def test_world_context_pcb_happy_reads_live_board() -> None:
    """kind="pcb": lee el board vivo (1 pasada) y emite TOON pcb con snap>0."""
    bridge = _FakePcbBridge(footprints=_pcb_footprints([("U19", 100.0, 50.0), ("R5", 105.0, 55.0)]))
    mcp = _pcb_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_world_context", {"kind": "pcb"})
    toon = _toon(result)
    assert toon.startswith("PCB|v1|2c|"), toon.splitlines()[0]
    # snap_id del store, monótono > 0.
    header = toon.splitlines()[0]
    assert "snap:" in header
    snap = int(header.split("snap:")[1])
    assert snap > 0
    assert "U19" in toon and "R5" in toon
    # Exactamente 1 pasada IPC sobre el board (read_board_context).
    assert bridge.read_calls == 1


@pytest.mark.unit
async def test_world_context_pcb_editor_closed_maps_unhandled() -> None:
    """kind="pcb" con PCB Editor cerrado ⇒ KICAD_CLI_FAILED ipc_status=unhandled."""
    bridge = _FakePcbBridge(board_mode="editor_closed")
    mcp = _pcb_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_world_context", {"kind": "pcb"})
    assert result.isError
    text = _toon_error(result)
    assert "KICAD_CLI_FAILED" in text
    assert "unhandled" in text or "PCB Editor" in text


@pytest.mark.unit
async def test_world_context_pcb_kicad_closed_maps_not_running() -> None:
    """kind="pcb" con KiCad cerrado ⇒ KICAD_NOT_RUNNING."""
    bridge = _FakePcbBridge(board_mode="kicad_closed")
    mcp = _pcb_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_world_context", {"kind": "pcb"})
    assert result.isError
    assert "KICAD_NOT_RUNNING" in _toon_error(result)


@pytest.mark.unit
async def test_world_context_pcb_focus_radius_hides_far_footprints() -> None:
    """focus/radius sobre posiciones pcb: los footprints lejanos van al resumen.

    focus/radius son palancas de degradación §4: sólo entran cuando el estado
    no cabe en ``max_tokens``. Con un board grande y budget chico, el encoder
    baja hasta el nivel focus y resume los footprints fuera del radio.
    """
    # 40 footprints cerca de U19 (100,50) + un cluster lejano en (400,400).
    specs = [("U19", 100.0, 50.0)]
    specs += [(f"R{i}", 101.0 + (i % 5), 51.0 + (i % 5)) for i in range(1, 30)]
    specs += [(f"C{i}", 400.0 + i, 400.0 + i) for i in range(30, 40)]
    bridge = _FakePcbBridge(footprints=_pcb_footprints(specs))
    mcp = _pcb_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            # 300 (no 260): la cabecera pcb ahora lleva bbox+outline (F-03,
            # ~14 tok fijos); el nivel de foco sigue siendo el que cabe y el
            # cluster lejano sigue yendo al resumen. La INTENCIÓN del test
            # (esconder footprints lejanos por degradación) es idéntica.
            "get_world_context",
            {"kind": "pcb", "max_tokens": 300, "focus_ref": "U19", "radius_mm": 15.0},
        )
    toon = _toon(result)
    assert toon.startswith("PCB|")
    assert "[FUERA_DE_AREA]" in toon, toon
    # U19 (foco) presente como componente completo; el cluster lejano resumido.
    u19_lines = [ln for ln in toon.splitlines() if ln.startswith("U19  ")]
    assert len(u19_lines) == 1


@pytest.mark.unit
async def test_world_context_pcb_budget_forces_degradation() -> None:
    """max_tokens chico sobre un board grande ⇒ [DEGRADADO] (misma cascada §4)."""
    specs = [(f"C{i}", 100.0 + i, 50.0 + (i % 7)) for i in range(60)]
    bridge = _FakePcbBridge(footprints=_pcb_footprints(specs))
    mcp = _pcb_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "get_world_context",
            {"kind": "pcb", "max_tokens": 150, "focus_ref": "C0", "radius_mm": 5.0},
        )
    toon = _toon(result)
    assert toon.startswith("PCB|")
    assert "[DEGRADADO]" in toon


@pytest.mark.unit
async def test_world_context_invalid_kind_rejected() -> None:
    """kind fuera de {sch,pcb} ⇒ INVALID_PARAMS (validación explícita)."""
    bridge = _FakePcbBridge()
    mcp = _pcb_server(bridge)
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_world_context", {"kind": "gerber"})
    assert result.isError
    # Puede ser rechazo del schema (Literal) o nuestro INVALID_PARAMS.
    text = _toon_error(result)
    assert "INVALID_PARAMS" in text or "gerber" in text.lower()


# --- B1 integration_gui: board real de 202 refs -------------------------------


@pytest.mark.integration_gui
async def test_world_context_pcb_against_real_board_202_refs() -> None:
    """D-09.1 E2E: leer el board vivo de 202 refs SIN haber mutado antes.

    Verifica cabecera ``PCB|…|snap:N`` con N>0 y presencia de refs conocidas
    (docs/componentes-pcb.md). Mide tokens_est con y sin focus para el
    reporte de sesión (el board completo probablemente exige budget).

    Precondiciones: ``KICAD_MCP_GUI_TEST=1`` y el PCB Editor abierto sobre el
    proyecto de prueba (``/tmp/gui-test-project/video.kicad_pcb``).
    """
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/pruebas-gui.md")
    if not os.environ.get("KICAD_MCP_PROJECT"):
        pytest.skip("KICAD_MCP_PROJECT no definida; apuntar al proyecto abierto")

    import time

    from kicad_mcp.logging_config import estimate_tokens

    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        # (1) Completo sin budget efectivo: cuánto pide el board completo.
        t0 = time.perf_counter()
        full = await client.call_tool("get_world_context", {"kind": "pcb", "max_tokens": 1_000_000})
        full_ms = (time.perf_counter() - t0) * 1000
        assert not full.isError, full
        toon_full = _toon(full)

        # Guard (sesión 16b, Tarea 3): este test espera el fixture "video"
        # (202 refs, U19/R5/C10) — si el board abierto es otro proyecto de
        # prueba (p.ej. el despertador de la sesión 16, 24 refs sin U19), no
        # es un fallo de tool ni de test: es la precondición equivocada.
        # Chequear ANTES del focus_ref="U19" de abajo, que si no, erroraría
        # sobre un board sin esa ref antes de llegar a las aserciones.
        if "U19" not in toon_full:
            pytest.skip("board abierto no es el fixture video de 202 refs; ver docs/pruebas-gui.md")

        # (2) Con focus r=20 en una ref conocida + budget que fuerza el nivel
        #     focus de la degradación §4 (sin budget, focus no se aplica: es
        #     una palanca, no un filtro incondicional). En un board de este
        #     tamaño el focus recorta ~50 % del payload.
        focused = await client.call_tool(
            "get_world_context",
            {"kind": "pcb", "max_tokens": 14000, "focus_ref": "U19", "radius_mm": 20.0},
        )
        assert not focused.isError, focused
        toon_focus = _toon(focused)

        # (3) Con max_tokens forzando degradación SIN focus (colapso de nets
        #     de poder + omisión de posiciones). El piso lo marca el listado
        #     de nets, que en este board domina el payload.
        degraded = await client.call_tool(
            "get_world_context",
            {"kind": "pcb", "max_tokens": 16000},
        )
        # Puede caber degradado o ser IMPOSSIBLE si el piso supera 16000; ambos
        # casos son dato para el reporte, no fallo de la tool.
        toon_degraded = _toon(degraded) if not degraded.isError else None

    header = toon_full.splitlines()[0]
    assert header.startswith("PCB|v1|")
    snap = int(header.split("snap:")[1])
    assert snap > 0, f"snap debe ser > 0 sin mutar: {header}"
    # Refs conocidas del board (docs/componentes-pcb.md).
    for ref in ("U19", "R5", "C10"):
        assert f"{ref}  " in toon_full or f"{ref} " in toon_full, f"{ref} ausente del TOON"
    # El focus con budget efectivo degrada y recorta.
    assert "[DEGRADADO]" in toon_focus
    assert estimate_tokens(toon_focus) < estimate_tokens(toon_full)

    print(
        "\n=== B1 tokens_est get_world_context(kind=pcb) board real ==="
        f"\n  header:                {header}"
        f"\n  completo (sin budget): {estimate_tokens(toon_full)} tok · {full_ms:.0f} ms"
        f"\n  focus r=20 @U19 (m=14000): {estimate_tokens(toon_focus)} tok (degradado)"
        + (
            f"\n  degradado sin focus (m=16000): {estimate_tokens(toon_degraded)} tok"
            if toon_degraded is not None
            else "\n  degradado sin focus (m=16000): CONTEXT_BUDGET_IMPOSSIBLE (piso nets>16000)"
        )
        + "\n=== fin ==="
    )
