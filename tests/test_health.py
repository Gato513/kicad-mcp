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
from kicad_mcp.errors import ErrorCode, KicadMcpError
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


# --- health fino (sesión 07 T3, D-07.3) --------------------------------------


class _FakeVersionForHealth:
    """Version dataclass-like para inyectar en un fake bridge."""

    def __init__(self, full: str) -> None:
        self.full = full


class _FakeBridge:
    """Bridge fake para probar ``_ipc_payload`` directo.

    Permite forzar cada combinación de los tres niveles de health sin
    montar clientes IPC. Cada método devuelve el valor configurado o
    levanta la excepción configurada.
    """

    def __init__(
        self,
        *,
        socket: bool = True,
        version_result: Any = None,
        pcb_result: Any = None,
    ) -> None:
        self._socket = socket
        self._version_result = version_result
        self._pcb_result = pcb_result

    def socket_present(self) -> bool:
        return self._socket

    def get_version(self) -> Any:
        if isinstance(self._version_result, BaseException):
            raise self._version_result
        return self._version_result

    def has_open_pcb(self) -> bool:
        if isinstance(self._pcb_result, BaseException):
            raise self._pcb_result
        assert isinstance(self._pcb_result, bool)
        return self._pcb_result


@pytest.mark.unit
def test_health_ipc_payload_all_ok_when_pcb_editor_open() -> None:
    """socket=ok, ipc_responde=ok, pcb_editor_abierto=yes, version incluido."""
    from kicad_mcp.tools.meta import _ipc_payload

    bridge = _FakeBridge(
        socket=True,
        version_result=_FakeVersionForHealth("10.0.4"),
        pcb_result=True,
    )
    payload = _ipc_payload(bridge)  # type: ignore[arg-type]

    assert payload["socket"] == "ok"
    assert payload["ipc_responde"] == "ok"
    assert payload["pcb_editor_abierto"] == "yes"
    assert payload["version"] == "10.0.4"
    assert payload["status"] == "ok"
    assert "code" not in payload


@pytest.mark.unit
def test_health_ipc_payload_pcb_no_when_no_editor_open() -> None:
    """PCB Editor cerrado (has_open_pcb=False) ⇒ ``pcb_editor_abierto="no"``,
    no ``"unknown"``: KiCad respondió que no hay editor."""
    from kicad_mcp.tools.meta import _ipc_payload

    bridge = _FakeBridge(
        socket=True,
        version_result=_FakeVersionForHealth("10.0.4"),
        pcb_result=False,
    )
    payload = _ipc_payload(bridge)  # type: ignore[arg-type]

    assert payload["pcb_editor_abierto"] == "no"
    assert payload["ipc_responde"] == "ok"


@pytest.mark.unit
def test_health_ipc_payload_socket_missing_reports_unknown_upstream() -> None:
    """Socket ausente ⇒ niveles superiores en "unknown", no false.

    Distingue "KiCad respondió que no" de "no pude preguntar" — evita
    que el agente asuma un false engañoso.
    """
    from kicad_mcp.tools.meta import _ipc_payload

    bridge = _FakeBridge(socket=False)
    payload = _ipc_payload(bridge)  # type: ignore[arg-type]

    assert payload["socket"] == "missing"
    assert payload["ipc_responde"] == "unknown"
    assert payload["pcb_editor_abierto"] == "unknown"
    assert payload["status"] == "missing"
    assert payload["code"] == "KICAD_NOT_RUNNING"


@pytest.mark.unit
def test_health_ipc_payload_ipc_error_masks_pcb_probe() -> None:
    """get_version falla ⇒ ipc_responde=error, pcb=unknown (no probamos igual)."""
    from kicad_mcp.tools.meta import _ipc_payload

    bridge = _FakeBridge(
        socket=True,
        version_result=KicadMcpError(
            code=ErrorCode.KICAD_TIMEOUT,
            message="timeout",
            hint="reintentar",
        ),
    )
    payload = _ipc_payload(bridge)  # type: ignore[arg-type]

    assert payload["socket"] == "ok"
    assert payload["ipc_responde"] == "error"
    assert payload["pcb_editor_abierto"] == "unknown"
    assert payload["code"] == "KICAD_TIMEOUT"
    assert payload["status"] == "error"


@pytest.mark.unit
def test_health_ipc_payload_pcb_probe_busy_degrades_gracefully() -> None:
    """has_open_pcb con busy tras retry ⇒ pcb_editor_abierto=unknown, ipc_responde=ok.

    Un fallo del probe de nivel 3 no invalida el nivel 2 ya OK; se
    degrada silente reportando la causa en ``pcb_probe_error``.
    """
    from kicad_mcp.tools.meta import _ipc_payload

    busy = KicadMcpError(
        code=ErrorCode.KICAD_CLI_FAILED,
        message="busy",
        hint="reintentá",
        data={"ipc_status": "busy"},
    )
    bridge = _FakeBridge(
        socket=True,
        version_result=_FakeVersionForHealth("10.0.4"),
        pcb_result=busy,
    )
    payload = _ipc_payload(bridge)  # type: ignore[arg-type]

    assert payload["ipc_responde"] == "ok"
    assert payload["pcb_editor_abierto"] == "unknown"
    assert payload["pcb_probe_error"] == "KICAD_CLI_FAILED"
    assert payload["status"] == "ok"


@pytest.mark.unit
def test_health_ipc_payload_tokens_est_under_budget() -> None:
    """El health fino sigue por debajo del techo de ~100 tokens_est.

    Presupuesto (D-07.3): el probe extra no puede empujar el health por
    encima de ~100 tokens_est (medido con el estimador de sesión 02:
    len(text)/3.5).
    """
    import json

    from kicad_mcp.logging_config import estimate_tokens
    from kicad_mcp.tools.meta import _ipc_payload

    # Caso realista de KiCad abierto con PCB Editor.
    bridge = _FakeBridge(
        socket=True,
        version_result=_FakeVersionForHealth("10.0.4"),
        pcb_result=True,
    )
    payload = _ipc_payload(bridge)  # type: ignore[arg-type]
    text = json.dumps(payload, ensure_ascii=False)
    tokens = estimate_tokens(text)
    assert tokens <= 60, (
        f"kicad_ipc solo: {tokens} tokens_est, {text!r}. "
        "El health total suma otros sub-payloads; el subtotal aquí debe quedar holgado."
    )


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
