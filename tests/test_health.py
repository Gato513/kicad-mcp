"""Tests de la tool `health` — MVP.

- `unit`: cliente MCP in-process contra el servidor con `kicad-cli` mockeado.
- `integration`: cliente MCP in-process contra `kicad-cli` real (requiere que
  esté instalado; Fase 0 lo verifica).

Ambos ejercitan la capa MCP (list_tools + call_tool) sobre streams en memoria.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.kicad_cli import KicadCliStatus
from kicad_mcp.server import create_server


def _parse_health(result: CallToolResult) -> dict[str, Any]:
    """Extrae el dict JSON del resultado de la tool."""
    assert result.isError is False, f"tool devolvió error: {result}"
    assert len(result.content) == 1
    block = result.content[0]
    assert isinstance(block, TextContent)
    return json.loads(block.text)


def _stub_ipc_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutraliza el probe IPC en tests que no lo ejercen (evita el timeout real de 2 s)."""
    monkeypatch.setattr(
        "kicad_mcp.tools.meta._ipc_payload",
        lambda _bridge: {"status": "ok", "version": "test-stub"},
    )


@pytest.mark.unit
async def test_health_reports_ok_when_kicad_cli_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = KicadCliStatus(
        available=True, version="10.0.4", raw_output="kicad-cli v10.0.4", error=None
    )
    monkeypatch.setattr("kicad_mcp.tools.meta.probe_version", lambda **_: fake)
    _stub_ipc_ok(monkeypatch)
    monkeypatch.delenv("KICAD_MCP_PROJECT", raising=False)

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        tools = await client.list_tools()
        assert "health" in [t.name for t in tools.tools]
        result = await client.call_tool("health", {})

    payload = _parse_health(result)
    assert payload["server"]["status"] == "ok"
    assert payload["kicad_cli"] == {"status": "ok", "version": "10.0.4"}
    assert payload["kicad_ipc"] == {"status": "ok", "version": "test-stub"}
    assert payload["project"]["status"] == "not_configured"
    assert payload["project"]["code"] == "PROJECT_NOT_FOUND"


@pytest.mark.unit
async def test_health_reports_kicad_ipc_missing_when_socket_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IPC no disponible ⇒ ``status=missing`` con ``KICAD_NOT_RUNNING``.

    No usa el bridge real (esperaría 2 s por el timeout). Inyecta un
    payload directamente para probar el contrato.
    """
    fake = KicadCliStatus(available=True, version="10.0.4", raw_output="", error=None)
    monkeypatch.setattr("kicad_mcp.tools.meta.probe_version", lambda **_: fake)
    monkeypatch.setattr(
        "kicad_mcp.tools.meta._ipc_payload",
        lambda _bridge: {
            "status": "missing",
            "code": "KICAD_NOT_RUNNING",
            "message": "No se pudo conectar al socket IPC de KiCad.",
            "hint": "Abrí KiCad y habilitá el API server en Preferences → Plugins.",
        },
    )
    monkeypatch.delenv("KICAD_MCP_PROJECT", raising=False)

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("health", {})

    payload = _parse_health(result)
    assert payload["kicad_ipc"]["status"] == "missing"
    assert payload["kicad_ipc"]["code"] == "KICAD_NOT_RUNNING"
    assert "API server" in payload["kicad_ipc"]["hint"]


@pytest.mark.unit
async def test_health_reports_missing_when_kicad_cli_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = KicadCliStatus(
        available=False, version=None, raw_output=None, error="kicad-cli no está en PATH"
    )
    monkeypatch.setattr("kicad_mcp.tools.meta.probe_version", lambda **_: fake)
    _stub_ipc_ok(monkeypatch)
    monkeypatch.delenv("KICAD_MCP_PROJECT", raising=False)

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("health", {})

    payload = _parse_health(result)
    assert payload["kicad_cli"]["status"] == "missing"
    assert payload["kicad_cli"]["code"] == "KICAD_CLI_MISSING"
    assert "PATH" in payload["kicad_cli"]["hint"]


@pytest.mark.unit
async def test_health_reports_project_when_env_var_points_to_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    project_dir = tmp_path / "proyecto_de_prueba"
    project_dir.mkdir()
    fake = KicadCliStatus(available=True, version="10.0.4", raw_output="", error=None)
    monkeypatch.setattr("kicad_mcp.tools.meta.probe_version", lambda **_: fake)
    _stub_ipc_ok(monkeypatch)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project_dir))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("health", {})

    payload = _parse_health(result)
    assert payload["project"] == {"status": "ok", "name": "proyecto_de_prueba"}


@pytest.mark.integration
async def test_health_against_real_kicad_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ejerce el binario real de kicad-cli. Requiere KiCad ≥ 9.0 en PATH (ADR-0002)."""
    monkeypatch.delenv("KICAD_MCP_PROJECT", raising=False)
    _stub_ipc_ok(monkeypatch)  # el IPC no está en Fase 0 (WARN); se cubre en integration_gui

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("health", {})

    payload = _parse_health(result)
    assert payload["kicad_cli"]["status"] == "ok"
    version = payload["kicad_cli"]["version"]
    assert version is not None, "kicad-cli --version no imprimió una versión reconocible"
    major = int(version.split(".", 1)[0])
    assert major >= 9, f"KiCad {version} < 9.0 (mínimo del ADR-0002)"
