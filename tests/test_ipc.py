"""Tests unit del ``bridge.ipc`` (sin socket real, sin ``kipy`` real).

Estrategia: inyectar un cliente fake vía ``client_factory`` para
ejercitar la lógica del wrapper (versión, restart detection, no
propaga tipos de kipy, conversión de unidades) sin dependencias
externas.

Un test ``integration_gui`` mínimo comprueba conectividad real cuando
``KICAD_MCP_GUI_TEST=1`` y el socket está listo.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from kicad_mcp.bridge.ipc import (
    BoardHandle,
    IpcBridge,
    Mm,
    Nm,
    mm_to_nm,
    nm_to_mm,
)
from kicad_mcp.errors import ErrorCode, KicadMcpError


class _FakeVersion:
    def __init__(self, full: str, major: int, minor: int, patch: int) -> None:
        self.full_version = full
        self.major = major
        self.minor = minor
        self.patch = patch


class _FakeClient:
    """Cliente IPC en memoria — imita el subset de kipy que consumimos."""

    def __init__(
        self,
        version: _FakeVersion | None = None,
        board: object | None = None,
    ) -> None:
        self._version = version or _FakeVersion("10.0.4", 10, 0, 4)
        self._board = board
        self.calls: list[str] = []

    def get_version(self) -> _FakeVersion:
        self.calls.append("get_version")
        return self._version

    def get_board(self) -> Any:
        self.calls.append("get_board")
        return self._board


def _factory(client: _FakeClient) -> Any:
    def _f(socket_path: str | None, timeout_ms: int, kicad_token: str | None) -> _FakeClient:
        # El bridge NO debe permitir timeouts > 2 s (restricciones-kicad.md).
        assert timeout_ms == 2000, f"timeout_ms={timeout_ms} rompe la regla de 2 s"
        return client

    return _f


# --- unidades -----------------------------------------------------------------


@pytest.mark.unit
def test_nm_mm_roundtrip_exact_at_micron_grid() -> None:
    # 1 mm ↔ 1_000_000 nm.
    assert mm_to_nm(Mm(1.0)) == Nm(1_000_000)
    assert nm_to_mm(Nm(1_000_000)) == Mm(1.0)
    # 0.127 mm (50 mil grid) ↔ 127_000 nm.
    assert mm_to_nm(Mm(0.127)) == Nm(127_000)


@pytest.mark.unit
def test_mm_to_nm_uses_banker_rounding_on_half_micron() -> None:
    # 0.5 nm hacia el par ⇒ 0. Evita sesgo acumulado en operaciones repetidas.
    assert mm_to_nm(Mm(0.0000005)) == Nm(0)
    # Un cuarto de micrón sí redondea correcto.
    assert mm_to_nm(Mm(0.000001)) == Nm(1)


# --- get_version --------------------------------------------------------------


@pytest.mark.unit
def test_get_version_returns_normalized_dataclass() -> None:
    client = _FakeClient(_FakeVersion("10.0.4-a1", 10, 0, 4))
    bridge = IpcBridge(client_factory=_factory(client))

    v = bridge.get_version()

    assert v.full == "10.0.4-a1"
    assert (v.major, v.minor, v.patch) == (10, 0, 4)
    assert client.calls == ["get_version"]


# --- get_open_board -----------------------------------------------------------


@pytest.mark.unit
def test_get_open_board_returns_none_when_no_board() -> None:
    client = _FakeClient(board=None)
    bridge = IpcBridge(client_factory=_factory(client))
    assert bridge.get_open_board() is None


@pytest.mark.unit
def test_get_open_board_wraps_raw_board_in_handle() -> None:
    sentinel = object()
    client = _FakeClient(board=sentinel)
    bridge = IpcBridge(client_factory=_factory(client))

    handle = bridge.get_open_board()

    assert isinstance(handle, BoardHandle)
    # BoardHandle es la única superficie visible fuera del bridge.
    assert handle is not None
    assert handle.raw is sentinel


# --- restart detection --------------------------------------------------------


@pytest.mark.unit
def test_restart_detected_when_kicad_token_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cambio de ``KICAD_API_TOKEN`` entre dos llamadas ⇒ ``KICAD_RESTARTED``."""
    monkeypatch.setenv("KICAD_API_TOKEN", "token-A")
    client = _FakeClient()
    bridge = IpcBridge(client_factory=_factory(client))

    bridge.get_version()  # primera llamada: congela token-A
    monkeypatch.setenv("KICAD_API_TOKEN", "token-B")  # KiCad se reinició
    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()

    assert excinfo.value.code is ErrorCode.KICAD_RESTARTED


@pytest.mark.unit
def test_absent_kicad_token_is_not_treated_as_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El env sin ``KICAD_API_TOKEN`` (server standalone) no falla en cada llamada."""
    monkeypatch.delenv("KICAD_API_TOKEN", raising=False)
    client = _FakeClient()
    bridge = IpcBridge(client_factory=_factory(client))

    bridge.get_version()
    bridge.get_version()  # no debe levantar
    assert client.calls == ["get_version", "get_version"]


# --- error del factory (KICAD_NOT_RUNNING) ------------------------------------


@pytest.mark.unit
def test_factory_error_maps_to_kicad_not_running() -> None:
    def failing_factory(socket_path: str | None, timeout_ms: int, kicad_token: str | None) -> Any:
        raise KicadMcpError(
            code=ErrorCode.KICAD_NOT_RUNNING,
            message="Fake down",
            hint="Test hint",
        )

    bridge = IpcBridge(client_factory=failing_factory)

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()

    assert excinfo.value.code is ErrorCode.KICAD_NOT_RUNNING


# --- register_all singleton (sesión 04) ---------------------------------------


@pytest.mark.unit
def test_register_all_shares_injected_bridge_between_meta_and_pcb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con ``ipc_bridge=`` inyectado, ``register_all`` NO crea bridges nuevos.

    Prueba directa del contrato del singleton: una sola conexión al socket
    por proceso servidor.
    """
    from mcp.server.fastmcp import FastMCP

    from kicad_mcp.tools import register_all

    instantiations: list[IpcBridge] = []
    real_init = IpcBridge.__init__

    def counting_init(self: IpcBridge, **kwargs: Any) -> None:
        instantiations.append(self)
        real_init(self, **kwargs)

    monkeypatch.setattr(IpcBridge, "__init__", counting_init)

    shared = IpcBridge(client_factory=_factory(_FakeClient()))
    assert len(instantiations) == 1, "nuestra propia instanciación"

    mcp = FastMCP(name="test-singleton", instructions="test")
    register_all(mcp, ipc_bridge=shared)

    # Ninguna instanciación nueva: register_all reutiliza la inyectada.
    assert len(instantiations) == 1


@pytest.mark.unit
def test_register_all_creates_single_bridge_when_none_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin inyección, ``register_all`` instancia UN solo ``IpcBridge`` (no dos).

    Contra-prueba del contrato del singleton: en runtime tampoco hay dos
    clientes.
    """
    from mcp.server.fastmcp import FastMCP

    from kicad_mcp.tools import register_all

    instantiations: list[IpcBridge] = []
    real_init = IpcBridge.__init__

    def counting_init(self: IpcBridge, **kwargs: Any) -> None:
        instantiations.append(self)
        real_init(self, **kwargs)

    monkeypatch.setattr(IpcBridge, "__init__", counting_init)

    mcp = FastMCP(name="test-no-inject", instructions="test")
    register_all(mcp)

    assert len(instantiations) == 1, "register_all debe crear exactamente un IpcBridge"


# --- integration_gui (requiere KiCad abierto) ---------------------------------


@pytest.mark.integration_gui
def test_ipc_reports_real_kicad_version() -> None:
    """Con KiCad abierto y ``KICAD_MCP_GUI_TEST=1``: pide versión real vía socket.

    Sin ambos, se hace ``skip`` con mensaje claro (protocolo en
    ``docs/pruebas-gui.md``).
    """
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/pruebas-gui.md")
    socket = os.environ.get("KICAD_API_SOCKET")
    if socket and socket.startswith("ipc://"):
        socket_path = socket[len("ipc://") :]
    else:
        socket_path = "/tmp/kicad/api.sock"
    if not Path(socket_path).exists() and not (socket or "").startswith("ipc://"):
        pytest.skip(f"socket IPC no existe ({socket_path}); KiCad no está corriendo")

    bridge = IpcBridge()
    version = bridge.get_version()

    assert version.major >= 9, f"KiCad {version.full} < 9.0 (mínimo ADR-0002)"
    assert version.full  # cualquier string no vacío
