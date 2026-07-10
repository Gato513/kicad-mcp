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


def _fake_state(added_c3: bool = False, snap: int = 0) -> NormalizedState:
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
    return NormalizedState(kind="sch", snap=snap, components=tuple(comps))


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
async def test_context_delta_skips_mtime_for_live_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Snapshot vivo (mtimes=None) ⇒ el chequeo se omite (ADR-0007)."""
    project = tmp_path / "proj"
    project.mkdir()
    sch = project / "proj.kicad_sch"
    sch.write_text("(kicad_sch)")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    base = _fake_state(added_c3=False)
    snap_id = get_default_store().register(base, mtimes=None)
    # Aunque el disco haya avanzado (o incluso desaparecido), un snapshot
    # vivo no chequea mtimes: la operación debe proceder.
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
    assert not result.isError, _text(result)
    toon = _text(result)
    # Cabecera DTOON con base y snap frescos.
    assert toon.startswith(f"DTOON|v1|snap:{snap_id + 1}|base:{snap_id}|area:r40@U1\n")
    assert "[+] C3" in toon  # el componente añadido está


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


@pytest.mark.unit
def test_context_delta_documented_in_tool_catalog() -> None:
    """DoD #2: la tool nueva vive en el catálogo con sus errores tipados."""
    catalog = (Path(__file__).parent.parent / "docs" / "specs" / "tool-catalog.md").read_text()
    assert "get_context_delta" in catalog
    assert "SNAPSHOT_STALE" in catalog
    assert "EXTERNAL_EDIT_DETECTED" in catalog
    _ = json
