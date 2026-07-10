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
import time
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


# --- get_footprint_position (sesión 04 T6) -----------------------------------


class _FakeFootprint:
    def __init__(self, ref: str, x_nm: int, y_nm: int) -> None:
        self.reference_field = type("_F", (), {"text": type("_T", (), {"value": ref})()})()
        self.position = type("_P", (), {"x": x_nm, "y": y_nm})()


class _FakeBoard:
    def __init__(self, footprints: list[_FakeFootprint]) -> None:
        self._fps = footprints

    def get_footprints(self) -> list[_FakeFootprint]:
        return list(self._fps)


@pytest.mark.unit
def test_get_footprint_position_returns_mm_from_nm() -> None:
    """Lee la posición en nm del footprint y la convierte a mm en la frontera."""
    fp = _FakeFootprint("U3", x_nm=102_500_000, y_nm=44_000_000)  # 102.5 mm, 44.0 mm
    board = BoardHandle(_raw=_FakeBoard([fp]))
    bridge = IpcBridge(client_factory=_factory(_FakeClient(board=board.raw)))

    x, y = bridge.get_footprint_position(board, "U3")

    assert x == Mm(102.5)
    assert y == Mm(44.0)


@pytest.mark.unit
def test_get_footprint_position_raises_component_not_found() -> None:
    """Ref inexistente en el board vivo ⇒ ``COMPONENT_NOT_FOUND``."""
    board = BoardHandle(_raw=_FakeBoard([_FakeFootprint("U1", 0, 0)]))
    bridge = IpcBridge(client_factory=_factory(_FakeClient(board=board.raw)))

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_footprint_position(board, "U99")
    assert excinfo.value.code is ErrorCode.COMPONENT_NOT_FOUND


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


# --- supervisión del bridge (sesión 04 T3) -----------------------------------


class _CountingFactory:
    """Factory que cuenta invocaciones y produce un cliente por llamada.

    Permite verificar que ``self._client`` se invalidó tras un fallo IPC:
    el próximo request pide un cliente nuevo (invocación #2 del factory).
    """

    def __init__(self, client_provider: Any) -> None:
        self._make_client = client_provider
        self.calls = 0

    def __call__(
        self, socket_path: str | None, timeout_ms: int, kicad_token: str | None
    ) -> _FakeClient:
        self.calls += 1
        return self._make_client()


class _RaisingClient:
    """Cliente que levanta la excepción configurada al primer ``get_version``.

    Simula un fallo mid-operación (post-``_ensure_client``): la conexión
    quedó establecida pero la request explotó.
    """

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc
        self.calls: list[str] = []
        self._version = _FakeVersion("10.0.4", 10, 0, 4)

    def get_version(self) -> _FakeVersion:
        self.calls.append("get_version")
        raise self._exc

    def get_board(self) -> Any:
        self.calls.append("get_board")
        raise self._exc


@pytest.mark.unit
def test_supervise_maps_connection_error_and_invalidates_client() -> None:
    """``ConnectionError`` mid-op ⇒ ``KICAD_NOT_RUNNING`` + próximo request reconecta."""
    ok_client = _FakeClient(_FakeVersion("10.0.4", 10, 0, 4))
    raising = _RaisingClient(ConnectionError("Connection refused"))
    # Primera llamada devuelve el raising client; segunda un cliente sano.
    clients = iter([raising, ok_client])
    factory = _CountingFactory(lambda: next(clients))
    bridge = IpcBridge(client_factory=factory)

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()
    assert excinfo.value.code is ErrorCode.KICAD_NOT_RUNNING
    assert factory.calls == 1

    # Próximo request: el cliente fue invalidado, el factory se llama de nuevo.
    v = bridge.get_version()
    assert v.major == 10
    assert factory.calls == 2, "supervisión debe forzar reconexión al siguiente request"


@pytest.mark.unit
def test_supervise_maps_timeout_to_kicad_timeout() -> None:
    """``TimeoutError`` mid-op ⇒ ``KICAD_TIMEOUT`` con hint accionable."""
    raising = _RaisingClient(TimeoutError("request took too long"))
    factory = _CountingFactory(lambda: raising)
    bridge = IpcBridge(client_factory=factory)

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()
    assert excinfo.value.code is ErrorCode.KICAD_TIMEOUT
    assert "Reintentar" in excinfo.value.hint


@pytest.mark.unit
def test_supervise_maps_generic_api_error_to_cli_failed() -> None:
    """Excepciones no clasificadas (p. ej. ``ApiError``) ⇒ ``KICAD_CLI_FAILED``."""

    class _FakeApiError(Exception):
        pass

    raising = _RaisingClient(_FakeApiError("kicad backend rejected request"))
    factory = _CountingFactory(lambda: raising)
    bridge = IpcBridge(client_factory=factory)

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()
    assert excinfo.value.code is ErrorCode.KICAD_CLI_FAILED
    assert "kicad backend rejected" in excinfo.value.hint


@pytest.mark.unit
def test_supervise_does_not_retry_silently_within_same_request() -> None:
    """La op fallida devuelve error tipado; NO se hace retry silencioso.

    Contrato del prompt sesión 04 T3: la reconexión es responsabilidad del
    request siguiente. Aquí verifico que ``get_version`` levanta y NO
    invoca ``client.get_version`` una segunda vez dentro del mismo call.
    """
    raising = _RaisingClient(ConnectionError("boom"))
    factory = _CountingFactory(lambda: raising)
    bridge = IpcBridge(client_factory=factory)

    with pytest.raises(KicadMcpError):
        bridge.get_version()
    assert raising.calls == ["get_version"]  # una sola llamada al cliente


@pytest.mark.unit
def test_supervise_distinguishes_kipy_connection_error_from_foreign_lookalike() -> None:
    """Un ``ConnectionError`` de OTRA librería NO mapea a ``KICAD_NOT_RUNNING``.

    Sesión 05 T1: si un módulo ajeno (p. ej. ``requests``) define su propio
    ``ConnectionError`` que se filtra dentro del bloque ``_supervise``, la
    identificación por sólo ``__qualname__`` lo clasificaría mal. La regla
    endurecida exige, además, que ``__module__`` empiece con ``"kipy"``.
    """

    class _ForeignConnectionError(Exception):
        pass

    _ForeignConnectionError.__qualname__ = "ConnectionError"
    _ForeignConnectionError.__module__ = "requests.exceptions"

    raising = _RaisingClient(_ForeignConnectionError("look-alike but from requests"))
    factory = _CountingFactory(lambda: raising)
    bridge = IpcBridge(client_factory=factory)

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()
    assert excinfo.value.code is ErrorCode.KICAD_CLI_FAILED, (
        "un ConnectionError ajeno a kipy debe caer al bucket genérico"
    )


@pytest.mark.unit
def test_supervise_recognizes_kipy_module_connection_error() -> None:
    """La detección positiva sigue activa para ``kipy.errors.ConnectionError``.

    Sin depender del import real de ``kipy`` (contrato del bridge: import
    perezoso), simulamos una excepción con el ``__qualname__`` y el
    ``__module__`` que ``kipy`` produce.
    """

    class _KipyConnectionError(Exception):
        pass

    _KipyConnectionError.__qualname__ = "ConnectionError"
    _KipyConnectionError.__module__ = "kipy.errors"

    raising = _RaisingClient(_KipyConnectionError("simulated kipy failure"))
    factory = _CountingFactory(lambda: raising)
    bridge = IpcBridge(client_factory=factory)

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()
    assert excinfo.value.code is ErrorCode.KICAD_NOT_RUNNING


@pytest.mark.unit
def test_supervise_maps_kipy_api_error_busy_to_ipc_status_busy() -> None:
    """``ApiError`` con ``code == AS_BUSY`` (7) ⇒ hint fijo + ``data.ipc_status='busy'``.

    Sesión 07 D-07.2: el código sigue siendo ``KICAD_CLI_FAILED`` (F3), pero
    el envelope gana ``data.ipc_status`` y un hint accionable estable, para
    que el agente correlacione sin parsear texto de KiCad.
    """

    class _KipyApiError(Exception):
        pass

    _KipyApiError.__qualname__ = "ApiError"
    _KipyApiError.__module__ = "kipy.errors"
    exc = _KipyApiError("KiCad is busy performing an operation and can't accept API commands")
    exc.code = 7  # AS_BUSY

    raising = _RaisingClient(exc)
    factory = _CountingFactory(lambda: raising)
    bridge = IpcBridge(client_factory=factory)

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()
    assert excinfo.value.code is ErrorCode.KICAD_CLI_FAILED
    assert excinfo.value.data == {"ipc_status": "busy"}
    assert "ocupado" in excinfo.value.hint.lower()


@pytest.mark.unit
def test_supervise_maps_kipy_api_error_unhandled_to_ipc_status_unhandled() -> None:
    """``ApiError`` con ``code == AS_UNHANDLED`` (5) ⇒ hint fijo + ``data.ipc_status='unhandled'``.

    Sesión 07 D-07.2. El caso "solo project manager, sin PCB Editor" viaja
    con este ``code`` desde ``kipy.KiCad.get_board`` (kipy/kicad.py:225-230).
    """

    class _KipyApiError(Exception):
        pass

    _KipyApiError.__qualname__ = "ApiError"
    _KipyApiError.__module__ = "kipy.errors"
    exc = _KipyApiError("no handler available for request of type kiapi.commands.GetOpenDocuments")
    exc.code = 5  # AS_UNHANDLED

    raising = _RaisingClient(exc)
    factory = _CountingFactory(lambda: raising)
    bridge = IpcBridge(client_factory=factory)

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()
    assert excinfo.value.code is ErrorCode.KICAD_CLI_FAILED
    assert excinfo.value.data == {"ipc_status": "unhandled"}
    assert "editor" in excinfo.value.hint.lower()


@pytest.mark.unit
def test_supervise_kipy_api_error_without_known_code_falls_through() -> None:
    """``ApiError`` con ``code`` desconocido (p. ej. AS_BAD_REQUEST=3) sigue el bucket genérico.

    No emite ``data.ipc_status``: el agente no debe asumir la clave presente
    en cualquier ``KICAD_CLI_FAILED``.
    """

    class _KipyApiError(Exception):
        pass

    _KipyApiError.__qualname__ = "ApiError"
    _KipyApiError.__module__ = "kipy.errors"
    exc = _KipyApiError("some other kicad error")
    exc.code = 3  # AS_BAD_REQUEST — no tratado especialmente

    raising = _RaisingClient(exc)
    factory = _CountingFactory(lambda: raising)
    bridge = IpcBridge(client_factory=factory)

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()
    assert excinfo.value.code is ErrorCode.KICAD_CLI_FAILED
    assert excinfo.value.data is None
    assert "some other kicad error" in excinfo.value.hint


@pytest.mark.unit
def test_supervise_kipy_connection_error_still_wins_over_api_error_path() -> None:
    """Regresión sesión 06 T1: kipy ``ConnectionError`` sigue mapeado a ``KICAD_NOT_RUNNING``.

    La rama de ``ApiError.code`` no debe robarle el mapeo a
    ``kipy.errors.ConnectionError``, que va antes.
    """

    class _KipyConnectionError(Exception):
        pass

    _KipyConnectionError.__qualname__ = "ConnectionError"
    _KipyConnectionError.__module__ = "kipy.errors"
    exc = _KipyConnectionError("simulated kipy connection failure")
    # Un ConnectionError no expone .code; forzamos una para descartar
    # ambigüedad: el flujo debe cortarse antes por qualname.
    exc.code = 7

    raising = _RaisingClient(exc)
    factory = _CountingFactory(lambda: raising)
    bridge = IpcBridge(client_factory=factory)

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()
    assert excinfo.value.code is ErrorCode.KICAD_NOT_RUNNING


@pytest.mark.unit
def test_supervise_preserves_typed_errors_unchanged() -> None:
    """``KicadMcpError`` levantado dentro de un op fluye sin remap.

    P. ej. ``move_footprint`` levanta ``COMPONENT_NOT_FOUND`` cuando la
    ref no existe post-validación; ese error no debe convertirse a
    KICAD_CLI_FAILED por la supervisión.
    """

    class _TypedRaisingClient:
        def get_version(self) -> Any:
            raise KicadMcpError(
                code=ErrorCode.KICAD_RESTARTED,
                message="fake restart",
                hint="fake hint",
            )

        def get_board(self) -> Any:
            return None

    factory = _CountingFactory(lambda: _TypedRaisingClient())
    bridge = IpcBridge(client_factory=factory)

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()
    assert excinfo.value.code is ErrorCode.KICAD_RESTARTED, "no debe remapear a CLI_FAILED"


# --- fast-fail cuando el socket no existe (sesión 04, T2) --------------------


@pytest.mark.unit
def test_default_factory_fast_fails_when_ipc_socket_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Socket ``ipc://<path>`` inexistente ⇒ ``KICAD_NOT_RUNNING`` en <100 ms.

    Sin este fast-fail, ``kipy`` deja pasar la construcción y falla al
    primer ``send()`` con costo de import + arranque (medido: ~370 ms en
    la workstation de dev, se dispararía a 2 s ante timeouts reales).
    """
    nonexistent = tmp_path / "definitely-not-there.sock"
    assert not nonexistent.exists()
    monkeypatch.setenv("KICAD_API_SOCKET", f"ipc://{nonexistent}")

    bridge = IpcBridge()  # usa el factory real; el fast-fail vive ahí

    t0 = time.monotonic()
    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()
    elapsed_ms = (time.monotonic() - t0) * 1000

    assert excinfo.value.code is ErrorCode.KICAD_NOT_RUNNING
    assert elapsed_ms < 100.0, (
        f"fast-fail tardó {elapsed_ms:.1f} ms; presupuesto 100 ms para socket ausente"
    )


@pytest.mark.unit
def test_default_factory_resolves_socket_env_over_arg(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Orden env → arg → default preservado en el fast-fail.

    Con ``KICAD_API_SOCKET`` inexistente y ``socket_path`` arg apuntando a
    un socket que sí existe, el env debe ganar y fast-failear.
    """
    env_socket = tmp_path / "env-missing.sock"
    arg_socket = tmp_path / "arg-exists.sock"
    arg_socket.touch()
    monkeypatch.setenv("KICAD_API_SOCKET", f"ipc://{env_socket}")

    bridge = IpcBridge(socket_path=f"ipc://{arg_socket}")

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()
    assert excinfo.value.code is ErrorCode.KICAD_NOT_RUNNING


@pytest.mark.unit
def test_default_factory_skips_fast_fail_for_non_ipc_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un esquema no filesystem (``tcp://``, etc.) NO dispara el fast-fail.

    La existencia del socket solo es chequeable para ``ipc://``; los demás
    esquemas los resuelve ``kipy`` (que a lo sumo tardará su timeout).
    Aquí solo verificamos que el chequeo no rechaza incorrectamente antes
    de llegar al factory.
    """
    from kicad_mcp.bridge.ipc import _socket_file_missing

    assert _socket_file_missing("tcp://localhost:12345") is False
    assert _socket_file_missing(None) is False
    assert _socket_file_missing("ipc://") is False  # sin path → deja pasar


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


@pytest.mark.integration_gui
def test_move_footprint_round_trip_against_open_board() -> None:
    """E2E de mutaciones: ``move_footprint`` persiste; ``get_footprint_position`` lee.

    Precondiciones (paso a paso en ``docs/pruebas-gui.md`` §E2E mutaciones):
    1. Copia ``tests/fixtures/004_real`` a una carpeta temporal fuera del repo.
    2. Abrir el ``.kicad_pcb`` copiado en KiCad (10.0.4 esperado).
    3. Habilitar el API server (Preferences → Plugins).
    4. Exportar ``KICAD_MCP_GUI_TEST=1`` y ``KICAD_MCP_GUI_REF=<ref>``
       (p. ej. ``KICAD_MCP_GUI_REF=U1``).
    5. Correr ``uv run pytest -m integration_gui -k round_trip``.

    El test:
    - Lee la posición inicial del footprint ``ref`` vía IPC.
    - Calcula un ``target`` desplazado 0.127 mm (grilla de 50 mil) del original.
    - Llama a ``move_footprint`` y re-lee la posición.
    - Verifica igualdad con tolerancia de redondeo banker's (±1 nm).

    NO se ejecuta en CI ni en pytest -m unit/integration: es del humano.
    """
    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/pruebas-gui.md")
    ref = os.environ.get("KICAD_MCP_GUI_REF")
    if not ref:
        pytest.skip("KICAD_MCP_GUI_REF no definida; ejemplo: KICAD_MCP_GUI_REF=U1")

    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("No hay board abierto en KiCad")

    x0, y0 = bridge.get_footprint_position(board, ref)
    # Desplazamiento en la grilla de 50 mil (0.127 mm) — el ADR de fixtures
    # dice que el grid del sch es 1.27 mm; PCB tiene grillas finas.
    target_x = Mm(round(float(x0) + 0.127, 4))
    target_y = Mm(round(float(y0) + 0.127, 4))

    bridge.move_footprint(board, ref, target_x, target_y)
    x1, y1 = bridge.get_footprint_position(board, ref)

    # Tolerancia de ±1 nm (redondeo banker's, banker_rounding_on_half_micron).
    assert abs(float(x1) - float(target_x)) < 1e-6, f"x: {x1} != {target_x}"
    assert abs(float(y1) - float(target_y)) < 1e-6, f"y: {y1} != {target_y}"


@pytest.mark.integration_gui
async def test_move_footprint_tool_returns_confirm_with_positive_snap_id() -> None:
    """E2E de la tool ``move_footprint`` contra KiCad: el confirm ecoa un snap > 0.

    Sesión 05 T5: tras la mutación exitosa, la tool registra un snapshot
    vivo (mtimes=None) y devuelve su ``snap_id`` monótono. La cadena de
    mutaciones del agente puede así usar el nuevo snap como base_snap del
    siguiente request.

    Precondiciones:
    - ``KICAD_MCP_GUI_TEST=1`` (skip si no).
    - ``KICAD_MCP_GUI_REF=<ref>`` (skip si no).
    - ``KICAD_MCP_PROJECT`` apuntando al proyecto abierto en KiCad (skip si no).
    """
    from mcp.shared.memory import create_connected_server_and_client_session
    from mcp.types import TextContent

    from kicad_mcp.server import create_server

    if os.environ.get("KICAD_MCP_GUI_TEST") != "1":
        pytest.skip("KICAD_MCP_GUI_TEST != 1; ver docs/pruebas-gui.md")
    ref = os.environ.get("KICAD_MCP_GUI_REF")
    if not ref:
        pytest.skip("KICAD_MCP_GUI_REF no definida; ejemplo: KICAD_MCP_GUI_REF=U1")
    if not os.environ.get("KICAD_MCP_PROJECT"):
        pytest.skip("KICAD_MCP_PROJECT no definida; apuntar a la carpeta del proyecto abierto")

    # Necesitamos una posición inicial válida sobre el board para no
    # depender del bounding box exacto: leemos y desplazamos 0.127 mm.
    bridge = IpcBridge()
    board = bridge.get_open_board()
    if board is None:
        pytest.skip("no hay board abierto en KiCad")
    x0, y0 = bridge.get_footprint_position(board, ref)
    target_x = Mm(round(float(x0) + 0.127, 4))
    target_y = Mm(round(float(y0) + 0.127, 4))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "move_footprint",
            {"ref": ref, "x_mm": float(target_x), "y_mm": float(target_y)},
        )
    assert not result.isError, result
    block = result.content[0]
    assert isinstance(block, TextContent)
    confirm = block.text
    assert f"OK move_footprint {ref}" in confirm

    # Regla de sesión 05 T5: el snap_id ecoado > 0 (viene del store post-mutación).
    import re

    match = re.search(r"\[snap:(\d+)\]", confirm)
    assert match is not None, f"confirm no incluye [snap:N]: {confirm!r}"
    assert int(match.group(1)) > 0, "snap_id post-mutación debe ser monótono ≥ 1"

    # D-06.3 (sesión 06): verificar el EFECTO. Un confirm con snap_id > 0
    # solo prueba que el store registró algo; la mutación real vive en el
    # board de kipy. Re-leemos via bridge — mismo camino que el round-trip
    # de bajo nivel pero encadenado a la tool MCP. Antes del fix T1 este
    # assert habría fallado con x1 == x0 (la mutación no se persistía a
    # través del proto interno de FootprintInstance).
    x_after, y_after = bridge.get_footprint_position(board, ref)
    assert abs(float(x_after) - float(target_x)) < 1e-6, (
        f"tool call OK pero la posición no se propagó: x={x_after}, target={target_x}"
    )
    assert abs(float(y_after) - float(target_y)) < 1e-6, (
        f"tool call OK pero la posición no se propagó: y={y_after}, target={target_y}"
    )
