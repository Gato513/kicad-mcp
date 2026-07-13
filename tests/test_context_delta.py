"""Tests de la tool ``get_context_delta`` (sesión 05 T4).

Estructura análoga a ``test_world_context.py``:
- ``unit``: con state builder mockeado, ejercita los caminos de error
  (SNAPSHOT_STALE, EXTERNAL_EDIT_DETECTED) y el happy path.
- ``integration``: contra fixture 001_basico (mundo sin cambios ⇒
  delta con [+]/[-]/[~C] vacíos). Mutaciones sintéticas se hacen sobre
  COPIAS en tmp_path — regla 7 de CLAUDE.md: fixtures jamás in place.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.server import create_server
from kicad_mcp.snapshots import collect_project_mtimes, get_default_store
from kicad_mcp.toon.schema import Component, NormalizedState, Pin
from tests.conftest import mirror_fixture

FIXTURES = Path(__file__).parent / "fixtures"


def _text(result: CallToolResult) -> str:
    assert len(result.content) == 1
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _fake_state(added_c3: bool = False, snap: int = 0, kind: str = "sch") -> NormalizedState:
    comps = [
        Component(
            ref="U1",
            value="STM32",
            lib=None,
            x=100.0,
            y=50.0,
            pins=(Pin(p="1", net="3V3"), Pin(p="2", net="GND")),
        ),
        Component(
            ref="C1",
            value="100nF",
            lib=None,
            x=105.0,
            y=50.0,
            pins=(Pin(p="1", net="3V3"), Pin(p="2", net="GND")),
        ),
    ]
    if added_c3:
        comps.append(
            Component(
                ref="C3",
                value="100nF",
                lib=None,
                x=110.0,
                y=50.0,
                pins=(Pin(p="1", net="3V3"), Pin(p="2", net="GND")),
            )
        )
    return NormalizedState(kind=kind, snap=snap, components=tuple(comps))


@pytest.mark.unit
async def test_context_delta_snapshot_stale_when_base_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """base_snap fuera del store ⇒ ``SNAPSHOT_STALE`` sin tocar el builder."""
    project = tmp_path / "proj"
    project.mkdir()
    sch = project / "proj.kicad_sch"
    sch.write_text("(kicad_sch)")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    called = {"builder": False}

    def _fail_builder(*_: object, **__: object) -> tuple[NormalizedState, bool]:
        called["builder"] = True
        raise AssertionError("builder no debería llamarse antes de validar el snap")

    monkeypatch.setattr("kicad_mcp.tools.world.build_state_cached", _fail_builder)

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "get_context_delta",
            {"base_snap": 999, "focus_ref": "U1", "radius_mm": 40.0},
        )
    assert result.isError
    text = _text(result)
    assert "SNAPSHOT_STALE" in text
    assert called["builder"] is False


@pytest.mark.unit
async def test_context_delta_external_edit_when_mtime_diverges(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """base_snap presente pero disco cambió ⇒ ``EXTERNAL_EDIT_DETECTED``."""
    project = tmp_path / "proj"
    project.mkdir()
    sch = project / "proj.kicad_sch"
    sch.write_text("(kicad_sch)")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    base = _fake_state(added_c3=False)
    snap_id = get_default_store().register(base, collect_project_mtimes(sch))
    # Simulo edición externa: avanzo el mtime.
    st = sch.stat()
    os.utime(sch, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000_000))

    monkeypatch.setattr(
        "kicad_mcp.tools.world.build_state_cached",
        lambda *_, **__: (_fake_state(added_c3=True), False),
    )

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "get_context_delta",
            {"base_snap": snap_id, "focus_ref": "U1", "radius_mm": 40.0},
        )
    assert result.isError
    assert "EXTERNAL_EDIT_DETECTED" in _text(result)


@pytest.mark.unit
async def test_context_delta_pcb_live_uses_board_not_disk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-06.1v2: base vivo pcb ⇒ curr desde board, NO desde disco.

    Fixture 1: registra un snapshot vivo ``kind="pcb"`` (patrón T5 sesión 05).
    Mockea ``build_state_from_board`` (rama viva) para devolver el estado con
    C3 añadido, y ``build_state_cached`` (rama disco) para FALLAR si es
    llamada. Verifica que el delta refleja la mutación pcb-a-pcb sin cruzar
    a disco ni comparar sch vs pcb (el bug que existía antes del fix).
    """
    project = tmp_path / "proj"
    project.mkdir()
    sch = project / "proj.kicad_sch"
    sch.write_text("(kicad_sch)")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    base = _fake_state(added_c3=False, kind="pcb")
    snap_id = get_default_store().register(base, mtimes=None)
    # Avanzo el mtime: si el path incorrectamente cae a disco, chequearía
    # mtimes y lanzaría EXTERNAL_EDIT — el test lo detecta.
    st = sch.stat()
    os.utime(sch, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000_000))

    def _fail_disk_builder(*_: object, **__: object) -> tuple[NormalizedState, bool]:
        raise AssertionError(
            "build_state_cached NO debe llamarse cuando el base es vivo pcb (D-06.1v2)"
        )

    monkeypatch.setattr("kicad_mcp.tools.world.build_state_cached", _fail_disk_builder)
    monkeypatch.setattr(
        "kicad_mcp.tools.world.build_state_from_board",
        lambda *_, **__: _fake_state(added_c3=True, kind="pcb"),
    )
    # El bridge tiene que devolver un board "no None" — cualquier objeto sirve
    # porque build_state_from_board está mockeado.
    monkeypatch.setattr(
        "kicad_mcp.bridge.ipc.IpcBridge.get_open_board",
        lambda self: object(),
    )

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "get_context_delta",
            {"base_snap": snap_id, "focus_ref": "U1", "radius_mm": 40.0},
        )
    assert not result.isError, _text(result)
    toon = _text(result)
    assert toon.startswith(f"DTOON|v1|snap:{snap_id + 1}|base:{snap_id}|area:r40@U1\n")
    assert "[+] C3" in toon  # la mutación pcb se refleja, no invertida


@pytest.mark.unit
async def test_context_delta_pcb_live_wins_over_divergent_disk_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sesión 07 T4.1 (D-07.4): centinela dura de la invariante "disco jamás
    para bases vivas pcb/pcb", asertada por CONTENIDO del delta.

    Este test **ata la invariante** ``el path de disco jamás debe usarse
    para bases vivas``. Si alguien en el futuro accidentalmente elimina la
    rama viva de ``_build_current_for``, el pipeline caería a
    ``build_state_cached`` y (con este mock) devolvería U1@0,0 — la
    "mutación invertida" del bug: el board vivo dice U1@50,60 (la mutación
    real) pero el delta reportaría U1@0,0 (contenido semánticamente basura).
    Este test lo atrapa asertando la POSICIÓN dentro del ``[~C] U1``, no
    solo la ausencia de crash o kind cruzado.

    Complementa ``test_context_delta_pcb_live_uses_board_not_disk``, que
    protege sólo contra "cayó a disco" (build_state_cached lanza
    AssertionError). Aquí el disco devuelve un estado PLAUSIBLE de kind
    ``pcb`` (imposible con el ``_rebuild`` actual, que sólo emite ``sch``,
    pero simulamos un futuro cambio que rompiera invariantes).
    """
    project = tmp_path / "proj"
    project.mkdir()
    sch = project / "proj.kicad_sch"
    sch.write_text("(kicad_sch)")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    # Base: kind=pcb, mtimes=None (vivo), U1 en (100, 50).
    base = NormalizedState(
        kind="pcb",
        snap=0,
        components=(
            Component(
                ref="U1",
                value="STM32",
                lib=None,
                x=100.0,
                y=50.0,
                pins=(Pin(p="1", net="3V3"), Pin(p="2", net="GND")),
            ),
        ),
    )
    snap_id = get_default_store().register(base, mtimes=None)

    # Mock rama viva: U1 movido a (50, 60) — la mutación REAL que hizo el
    # agente antes de pedir el delta.
    live_state = NormalizedState(
        kind="pcb",
        snap=0,
        components=(
            Component(
                ref="U1",
                value="STM32",
                lib=None,
                x=50.0,
                y=60.0,
                pins=(Pin(p="1", net="3V3"), Pin(p="2", net="GND")),
            ),
        ),
    )
    monkeypatch.setattr(
        "kicad_mcp.tools.world.build_state_from_board",
        lambda *_, **__: live_state,
    )
    monkeypatch.setattr(
        "kicad_mcp.bridge.ipc.IpcBridge.get_open_board",
        lambda self: object(),
    )

    # Mock rama disco: U1 en (0, 0), kind=pcb (imposible hoy, simula
    # ruptura de invariante futura). Si el pipeline cae aquí por error,
    # el delta va a mostrar (0, 0) — la "mutación invertida".
    divergent_disk_state = NormalizedState(
        kind="pcb",
        snap=0,
        components=(
            Component(
                ref="U1",
                value="STM32",
                lib=None,
                x=0.0,
                y=0.0,
                pins=(Pin(p="1", net="3V3"), Pin(p="2", net="GND")),
            ),
        ),
    )
    monkeypatch.setattr(
        "kicad_mcp.tools.world.build_state_cached",
        lambda *_, **__: (divergent_disk_state, False),
    )

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "get_context_delta",
            {"base_snap": snap_id, "focus_ref": "U1", "radius_mm": 40.0},
        )
    assert not result.isError, _text(result)
    toon = _text(result)
    # El delta debe contener la mutación REAL (del board vivo), NO la del
    # mock de disco. Si esta assert falla con x0.0/y0.0, es porque el
    # pipeline cayó a la rama de disco — la invariante D-06.1v2 se rompió.
    changed_lines = [line for line in toon.splitlines() if line.startswith("[~C] U1")]
    assert len(changed_lines) == 1, f"esperaba 1 línea [~C] U1; TOON:\n{toon}"
    assert "x50.0 y60.0" in changed_lines[0], (
        f"delta muestra posición inesperada; probablemente cayó a disco.\nlínea: {changed_lines[0]}"
    )
    assert "x0.0 y0.0" not in changed_lines[0], (
        "delta contiene la posición divergente del mock de disco — invariante rota"
    )


@pytest.mark.unit
async def test_context_delta_pcb_live_no_board_returns_snapshot_stale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-06.1v2: base vivo pcb + KiCad sin board ⇒ ``SNAPSHOT_STALE``.

    La cadena viva se perdió (el usuario cerró el PCB, KiCad se reinició sin
    reabrir, etc.). El código es SNAPSHOT_STALE — no KICAD_NOT_RUNNING: el
    socket puede estar OK y la operación fallida es del llamador (su snapshot
    ya no tiene contraparte). ``data.reason="live_chain_lost"`` permite al
    agente correlacionar sin parsear el hint (F3 intacta).
    """
    project = tmp_path / "proj"
    project.mkdir()
    (project / "proj.kicad_sch").write_text("(kicad_sch)")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    base = _fake_state(added_c3=False, kind="pcb")
    snap_id = get_default_store().register(base, mtimes=None)

    monkeypatch.setattr(
        "kicad_mcp.bridge.ipc.IpcBridge.get_open_board",
        lambda self: None,
    )

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "get_context_delta",
            {"base_snap": snap_id, "focus_ref": "U1", "radius_mm": 40.0},
        )
    assert result.isError
    text = _text(result)
    assert "SNAPSHOT_STALE" in text
    assert "cadena viva" in text  # el hint menciona la cadena viva


@pytest.mark.unit
async def test_context_delta_sch_disk_path_still_works(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-06.1v2: base sch de disco ⇒ path histórico intacto (rama disco).

    Verifica que la rama sch (mtimes dict, kind="sch") sigue leyendo desde
    disco vía ``build_state_cached`` — cero regresión al agregar la rama
    viva pcb.
    """
    project = tmp_path / "proj"
    project.mkdir()
    sch = project / "proj.kicad_sch"
    sch.write_text("(kicad_sch)")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    base = _fake_state(added_c3=False)
    snap_id = get_default_store().register(base, collect_project_mtimes(sch))

    def _fail_board_builder(*_: object, **__: object) -> NormalizedState:
        raise AssertionError(
            "build_state_from_board NO debe llamarse en la rama sch/disco (D-06.1v2)"
        )

    monkeypatch.setattr("kicad_mcp.tools.world.build_state_from_board", _fail_board_builder)
    monkeypatch.setattr(
        "kicad_mcp.tools.world.build_state_cached",
        lambda *_, **__: (_fake_state(added_c3=True), False),
    )

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "get_context_delta",
            {"base_snap": snap_id, "focus_ref": "U1", "radius_mm": 40.0},
        )
    assert not result.isError, _text(result)
    toon = _text(result)
    assert toon.startswith(f"DTOON|v1|snap:{snap_id + 1}|base:{snap_id}|area:r40@U1\n")
    assert "[+] C3" in toon


@pytest.mark.unit
async def test_context_delta_registers_fresh_snap_and_echoes_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """El delta abre un snapshot nuevo; su snap_id va en la cabecera y en el log."""
    project = tmp_path / "proj"
    project.mkdir()
    sch = project / "proj.kicad_sch"
    sch.write_text("(kicad_sch)")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    base = _fake_state(added_c3=False)
    base_snap = get_default_store().register(base, collect_project_mtimes(sch))

    monkeypatch.setattr(
        "kicad_mcp.tools.world.build_state_cached",
        lambda *_, **__: (_fake_state(added_c3=True), False),
    )

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "get_context_delta",
            {"base_snap": base_snap, "focus_ref": "U1", "radius_mm": 40.0},
        )
    assert not result.isError, _text(result)
    toon = _text(result)
    assert f"|base:{base_snap}|" in toon
    # El estado nuevo se registró en el store con snap_id = base_snap + 1.
    entry = get_default_store().get(base_snap + 1)
    assert entry is not None
    assert entry.snap_id == base_snap + 1


@pytest.mark.unit
async def test_context_delta_budget_impossible_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``max_tokens=1`` con delta no vacío ⇒ ``CONTEXT_BUDGET_IMPOSSIBLE`` (D-05.5)."""
    project = tmp_path / "proj"
    project.mkdir()
    sch = project / "proj.kicad_sch"
    sch.write_text("(kicad_sch)")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    base = _fake_state(added_c3=False)
    base_snap = get_default_store().register(base, collect_project_mtimes(sch))
    monkeypatch.setattr(
        "kicad_mcp.tools.world.build_state_cached",
        lambda *_, **__: (_fake_state(added_c3=True), False),
    )

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "get_context_delta",
            {
                "base_snap": base_snap,
                "focus_ref": "U1",
                "radius_mm": 40.0,
                "max_tokens": 1,
            },
        )
    assert result.isError
    text = _text(result)
    assert "CONTEXT_BUDGET_IMPOSSIBLE" in text
    assert "presupuesto mínimo" in text


@pytest.mark.integration
async def test_context_delta_empty_when_world_unchanged_against_fixture_001(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Mundo sin cambios (mismo fixture, un solo build) ⇒ delta sin cambios.

    Registro el snapshot base con el estado real de 001, luego pido el
    delta contra el mismo estado. El [AREA] contiene los refs del entorno
    (o el summary de >20). No hay [+], [-], [~C], [~N].
    """
    project = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        # Primero pido contexto normal para establecer el snap base.
        world = await client.call_tool("get_world_context", {"max_tokens": 800})
        assert not world.isError
        base_snap_line = _text(world).splitlines()[0]
        # Cabecera formato: SCH|v1|Nc|Nn|snap:X
        base_snap = int(base_snap_line.rsplit(":", 1)[1])

        # Ahora pido el delta contra ese mismo estado.
        result = await client.call_tool(
            "get_context_delta",
            {"base_snap": base_snap, "focus_ref": "U1", "radius_mm": 50.0},
        )
    assert not result.isError, _text(result)
    toon = _text(result)
    lines = toon.splitlines()
    assert lines[0].startswith(f"DTOON|v1|snap:{base_snap + 1}|base:{base_snap}|")
    # Sin cambios estructurales.
    assert not any(line.startswith("[+] ") for line in lines)
    assert not any(line.startswith("[-] ") for line in lines)
    assert not any(line.startswith("[~C] ") for line in lines)
    assert not any(line.startswith("[~N] ") for line in lines)


@pytest.mark.integration
async def test_context_delta_reports_added_component_against_synthetic_base(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Base sintético con un componente menos ⇒ el delta reporta [+] contra el mundo real.

    Ejerce el pipeline completo (kicad-cli + parser + delta) sin mutar el
    fixture (regla 7 de CLAUDE.md): registro un base "recortado" del
    estado real y verifico que get_context_delta detecta la diferencia.
    """
    project = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        world = await client.call_tool("get_world_context", {"max_tokens": 800})
        assert not world.isError
        real_snap = int(_text(world).splitlines()[0].rsplit(":", 1)[1])

        # Construyo un base sintético: mismo mundo menos el primer componente.
        real_entry = get_default_store().get(real_snap)
        assert real_entry is not None
        trimmed = real_entry.state.model_copy(
            update={"components": real_entry.state.components[1:]}
        )
        sch = next(project.glob("*.kicad_sch"))
        synthetic_base = get_default_store().register(trimmed, collect_project_mtimes(sch))

        result = await client.call_tool(
            "get_context_delta",
            {"base_snap": synthetic_base, "focus_ref": "U1", "radius_mm": 200.0},
        )
    assert not result.isError, _text(result)
    toon = _text(result)
    added_lines = [line for line in toon.splitlines() if line.startswith("[+] ")]
    assert len(added_lines) == 1, f"esperaba 1 [+], vi:\n{toon}"


@pytest.mark.integration
async def test_context_delta_log_emits_snap_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """log_tool_call recibe snap_id=nuevo y extra.base_snap=viejo."""
    project = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        "kicad_mcp.tools.world.log_tool_call",
        lambda **kwargs: captured.append(kwargs),
    )

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        world = await client.call_tool("get_world_context", {"max_tokens": 800})
        assert not world.isError
        base_snap = int(_text(world).splitlines()[0].rsplit(":", 1)[1])
        await client.call_tool(
            "get_context_delta",
            {"base_snap": base_snap, "focus_ref": "U1", "radius_mm": 50.0},
        )

    delta_calls = [c for c in captured if c.get("tool_name") == "get_context_delta"]
    assert len(delta_calls) == 1
    assert delta_calls[0]["snap_id"] == base_snap + 1
    extra = delta_calls[0]["extra"]
    assert isinstance(extra, dict)
    assert extra["base_snap"] == base_snap


@pytest.mark.integration_gui
async def test_context_delta_pcb_pcb_pipeline_after_move_footprint() -> None:
    """Sesión 07 T4.2 (D-07.4): pipeline delta pcb/pcb realista contra KiCad.

    Registra un snapshot vivo pre-mutación desde el board de kipy, muta ``ref``
    vía la tool ``move_footprint``, pide ``get_context_delta`` con el snap
    inicial como base y verifica que el TOON contiene ``[~C] <ref>`` con la
    NUEVA posición (la mutación se refleja correctamente). Cierra el hueco
    identificado en la auditoría pre-07 (P1): ningún integration cubría el
    round-trip completo delta pcb/pcb hasta ahora.

    Teardown en ``finally``: restaura la posición inicial vía bridge para
    dejar el entorno estable entre corridas (regla 7 no aplica al board de
    /tmp, es copia descartable, pero el teardown evita drift acumulado).
    """
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/pruebas-gui.md")
    ref = os.environ.get("KICAD_MCP_GUI_REF")
    if not ref:
        pytest.skip("KICAD_MCP_GUI_REF no definida; ejemplo: KICAD_MCP_GUI_REF=U19")
    if not os.environ.get("KICAD_MCP_PROJECT"):
        pytest.skip("KICAD_MCP_PROJECT no definida; apuntar al proyecto abierto")

    from kicad_mcp.bridge.ipc import IpcBridge, Mm
    from kicad_mcp.bridge.state_builder import build_state_from_board

    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")

    x0, y0 = bridge.get_footprint_position(board, ref)
    try:
        # Snapshot vivo del board pre-mutación → base_snap del delta.
        state_pre = build_state_from_board(bridge, board)
        base_snap = get_default_store().register(state_pre, mtimes=None)

        # Target: desplazamiento 0.254 mm (grid 100 mil clásico de PCB).
        target_x = Mm(round(float(x0) + 0.254, 4))
        target_y = Mm(round(float(y0) + 0.254, 4))

        mcp = create_server()
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            mut = await client.call_tool(
                "move_footprint",
                {"ref": ref, "x_mm": float(target_x), "y_mm": float(target_y)},
            )
            assert not mut.isError, _text(mut)

            delta = await client.call_tool(
                "get_context_delta",
                {"base_snap": base_snap, "focus_ref": ref, "radius_mm": 20.0},
            )
        assert not delta.isError, _text(delta)
        toon = _text(delta)

        # El delta debe reportar [~C] <ref> con la NUEVA posición.
        changed_lines = [line for line in toon.splitlines() if line.startswith(f"[~C] {ref}")]
        assert len(changed_lines) == 1, f"esperaba 1 [~C] {ref}; TOON:\n{toon}"
        expected_pos = f"x{float(target_x):.1f} y{float(target_y):.1f}"
        assert expected_pos in changed_lines[0], (
            f"delta muestra posición inesperada.\n"
            f"esperaba: {expected_pos}\nrecibí: {changed_lines[0]}"
        )
        # Reporta el TOON completo para el reporte final de sesión.
        print(f"\n=== T4.2 TOON delta pcb/pcb ===\n{toon}\n=== fin TOON ===")
    finally:
        # Teardown: restauro U19 aunque falle el assert (try/finally).
        # ``suppress`` no enmascara el error original y evita el noqa.
        import contextlib

        with contextlib.suppress(Exception):
            bridge.move_footprint(board, ref, x0, y0)


@pytest.mark.unit
def test_context_delta_documented_in_tool_catalog() -> None:
    """DoD #2: la tool nueva vive en el catálogo con sus errores tipados."""
    catalog = (Path(__file__).parent.parent / "docs" / "specs" / "tool-catalog.md").read_text()
    assert "get_context_delta" in catalog
    assert "SNAPSHOT_STALE" in catalog
    assert "EXTERNAL_EDIT_DETECTED" in catalog
    _ = json
