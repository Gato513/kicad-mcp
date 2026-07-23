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
    _resolve_kicad_socket,
    _verify_created_net_or_revert,
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


# --- get_items_by_id: bug del not-found (sesión 17, P2.0) ---------------------
#
# Bug descubierto en sesión 16b (docs/sesiones/16b-reporte.md): los 4
# consumidores de ``get_items_by_id`` (``verify_footprint_by_kiid``,
# ``get_copper_by_kiid``, ``remove_by_kiid``, ``move_footprint``) asumen que
# kipy devuelve ``[]`` para un KIID inexistente. En la práctica kipy lanza
# ``ApiError("... none of the requested IDs were found or valid")``. El
# helper ``_get_items_by_id_or_empty`` (ipc.py) debe absorber ESA excepción
# puntual y devolver ``[]`` — sin tocar ningún otro fallo IPC.


class _KipyApiErrorNotFound(Exception):
    """Simula ``kipy.errors.ApiError`` del caso not-found (mensaje real observado)."""


_KipyApiErrorNotFound.__qualname__ = "ApiError"
_KipyApiErrorNotFound.__module__ = "kipy.errors"


class _KipyApiErrorOther(Exception):
    """``ApiError`` de kipy con un mensaje NO relacionado a not-found — debe propagar."""


_KipyApiErrorOther.__qualname__ = "ApiError"
_KipyApiErrorOther.__module__ = "kipy.errors"


class _NotFoundRawBoard:
    """``raw`` fake cuyo ``get_items_by_id`` siempre lanza la ApiError not-found."""

    def get_items_by_id(self, kiids: list[Any]) -> list[Any]:
        raise _KipyApiErrorNotFound(
            "none of the requested IDs were found or valid on the current document"
        )


class _OtherErrorRawBoard:
    """``raw`` fake cuyo ``get_items_by_id`` lanza una ApiError distinta (no absorbible)."""

    def get_items_by_id(self, kiids: list[Any]) -> list[Any]:
        raise _KipyApiErrorOther("some unrelated kicad error")


@pytest.mark.unit
def test_get_copper_by_kiid_returns_none_on_kipy_not_found_error() -> None:
    """El KIID stale debe resolver a ``None`` (→ ``TRACK_ID_STALE`` en la tool), no reventar."""
    board = BoardHandle(_raw=_NotFoundRawBoard())
    bridge = IpcBridge()

    assert bridge.get_copper_by_kiid(board, "stale-kiid") is None


@pytest.mark.unit
def test_get_copper_by_kiid_propagates_unrelated_api_error() -> None:
    """Una ``ApiError`` que NO es el caso not-found sigue mapeándose como siempre."""
    board = BoardHandle(_raw=_OtherErrorRawBoard())
    bridge = IpcBridge()

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.get_copper_by_kiid(board, "any-kiid")
    assert excinfo.value.code is ErrorCode.KICAD_CLI_FAILED
    assert "unrelated kicad error" in excinfo.value.hint


@pytest.mark.unit
def test_verify_footprint_by_kiid_returns_none_on_kipy_not_found_error() -> None:
    board = BoardHandle(_raw=_NotFoundRawBoard())
    bridge = IpcBridge()

    assert bridge.verify_footprint_by_kiid(board, "stale-kiid") is None


@pytest.mark.unit
def test_remove_by_kiid_returns_false_on_kipy_not_found_error() -> None:
    """Borrado concurrente (id ya no está) ⇒ ``False``, no una excepción cruda."""
    board = BoardHandle(_raw=_NotFoundRawBoard())
    bridge = IpcBridge()

    assert bridge.remove_by_kiid(board, "stale-kiid") is False


class _RecordingRemoveManyRawBoard:
    """``raw`` fake que imita la firma real de ``kipy.Board.remove_items``:
    UN solo parámetro ``items: BoardItem | Sequence[BoardItem]`` — NO
    variádico. Detectó en vivo (19d.2, corrida GUI real) que
    ``remove_many_by_kiid`` llamaba ``remove_items(*items)`` (desempaquetado),
    lo que kipy rechaza con ``TypeError: remove_items() takes 2 positional
    arguments but N were given`` en cuanto ``items`` tiene más de un
    elemento — un fake que sólo simulara la llamada sin replicar esta forma
    de la firma real no lo hubiera atrapado."""

    def __init__(self, found: list[Any]) -> None:
        self._found = found
        self.remove_items_calls: list[Any] = []

    def get_items_by_id(self, kiids: list[Any]) -> list[Any]:
        return self._found

    def remove_items(self, items: Any) -> None:
        self.remove_items_calls.append(items)


@pytest.mark.unit
def test_remove_many_by_kiid_calls_remove_items_with_a_single_sequence_arg() -> None:
    """Regresión del bug de 19d.2: ``remove_items`` recibe UNA lista, no
    ``*items`` desempaquetado — kipy real rechaza más de un posicional."""
    found_items = [object(), object(), object()]
    raw_board = _RecordingRemoveManyRawBoard(found_items)
    board = BoardHandle(_raw=raw_board)
    bridge = IpcBridge()

    removed = bridge.remove_many_by_kiid(board, ["k1", "k2", "k3"])

    assert removed == 3
    assert raw_board.remove_items_calls == [found_items]


@pytest.mark.unit
def test_remove_many_by_kiid_returns_zero_when_nothing_found() -> None:
    raw_board = _RecordingRemoveManyRawBoard([])
    board = BoardHandle(_raw=raw_board)
    bridge = IpcBridge()

    assert bridge.remove_many_by_kiid(board, ["stale-1", "stale-2"]) == 0
    assert raw_board.remove_items_calls == []


@pytest.mark.unit
def test_move_footprint_by_kiid_raises_component_not_found_on_kipy_not_found_error() -> None:
    """El fast-path por kiid, con KIID stale, cae al mismo ``COMPONENT_NOT_FOUND``
    de consistencia que el camino sin kiid — no un ``KICAD_CLI_FAILED`` crudo."""
    board = BoardHandle(_raw=_NotFoundRawBoard())
    bridge = IpcBridge()

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.move_footprint(board, "U1", Mm(1.0), Mm(1.0), kiid="stale-kiid")
    assert excinfo.value.code is ErrorCode.COMPONENT_NOT_FOUND


# --- Sesión 19d: _verify_created_net_or_revert (add_via/add_track hijacking) --


class _FakeNet:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeCopperItem:
    def __init__(self, net_name: str) -> None:
        self.net = _FakeNet(net_name) if net_name else None


class _RerereadRawBoard:
    """``raw`` fake cuyo ``get_items_by_id`` devuelve un net fijo — simula la
    relectura post-creación de ``add_via``/``add_track`` (sesión 19d)."""

    def __init__(self, reread_net_name: str) -> None:
        self._reread_net_name = reread_net_name
        self.removed: list[Any] = []

    def get_items_by_id(self, kiids: list[Any]) -> list[Any]:
        return [_FakeCopperItem(self._reread_net_name)]

    def remove_items(self, item: Any) -> None:
        self.removed.append(item)


class _EmptyRerereadRawBoard:
    """El ítem ya no está (borrado concurrente) — nada que verificar."""

    def get_items_by_id(self, kiids: list[Any]) -> list[Any]:
        return []

    def remove_items(self, item: Any) -> None:
        raise AssertionError("no debería revertir si el ítem ya no está")


@pytest.mark.unit
def test_verify_created_net_or_revert_ok_when_net_matches() -> None:
    """Caso feliz: el net releído coincide con el pedido — no revierte, no lanza."""
    raw_board = _RerereadRawBoard(reread_net_name="GND")
    created_item = object()

    _verify_created_net_or_revert(raw_board, ["kiid-proto"], created_item, "GND", [1.0, 2.0])

    assert raw_board.removed == []


@pytest.mark.unit
def test_verify_created_net_or_revert_raises_and_reverts_on_mismatch() -> None:
    """El net releído difiere del pedido (KiCad reasignó al cobre físico bajo el
    punto, H2 de 19c/19d.0): revierte creando y lanza NET_ASSIGNMENT_MISMATCH
    con el ``data`` estructurado que necesita el agente para diagnosticar."""
    raw_board = _RerereadRawBoard(reread_net_name="/MOSI")
    created_item = object()

    with pytest.raises(KicadMcpError) as excinfo:
        _verify_created_net_or_revert(
            raw_board, ["kiid-proto"], created_item, "+3V3", [170.775, 57.225]
        )

    assert excinfo.value.code is ErrorCode.NET_ASSIGNMENT_MISMATCH
    assert excinfo.value.data == {
        "requested_net": "+3V3",
        "actual_net": "/MOSI",
        "at": [170.775, 57.225],
    }
    assert raw_board.removed == [created_item]


@pytest.mark.unit
def test_verify_created_net_or_revert_noop_when_item_disappeared() -> None:
    """Borrado concurrente entre la creación y la relectura: nada que verificar,
    no revierte (no hay nada que revertir) ni lanza."""
    raw_board = _EmptyRerereadRawBoard()
    created_item = object()

    _verify_created_net_or_revert(raw_board, ["kiid-proto"], created_item, "GND", [1.0, 2.0])


@pytest.mark.unit
def test_verify_created_net_or_revert_noop_when_reread_net_unnamed() -> None:
    """Si la relectura no trae un net con nombre (net None o vacío), no hay
    señal de hijacking confiable — no revierte ni lanza."""
    raw_board = _RerereadRawBoard(reread_net_name="")
    created_item = object()

    _verify_created_net_or_revert(raw_board, ["kiid-proto"], created_item, "GND", [1.0, 2.0])

    assert raw_board.removed == []


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


class _KipyApiErrorBase(Exception):
    """Base para simular ``kipy.errors.ApiError`` sin depender del import real."""


_KipyApiErrorBase.__qualname__ = "ApiError"
_KipyApiErrorBase.__module__ = "kipy.errors"


def _kipy_busy(msg: str = "KiCad is busy") -> Exception:
    exc = _KipyApiErrorBase(msg)
    exc.code = 7  # AS_BUSY
    return exc


class _BusyThenOkClient:
    """Cliente fake que devuelve AS_BUSY las primeras ``busy_before_ok`` veces
    y luego responde correctamente. Simula el patrón real de KiCad procesando
    una operación background que termina tras un momento.
    """

    def __init__(self, busy_before_ok: int) -> None:
        self.busy_before_ok = busy_before_ok
        self.get_version_calls = 0
        self._version = _FakeVersion("10.0.4", 10, 0, 4)

    def get_version(self) -> _FakeVersion:
        self.get_version_calls += 1
        if self.get_version_calls <= self.busy_before_ok:
            raise _kipy_busy()
        return self._version

    def get_board(self) -> Any:
        return None

    def get_open_documents(self, doc_type: Any) -> Any:
        return []


@pytest.mark.unit
def test_retry_recovers_after_transient_busy(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """AS_BUSY una vez → segundo intento OK, con 1 línea de retry registrada.

    Sesión 07 T2 (D-07.1): el bridge reintenta lecturas idempotentes ante
    AS_BUSY con backoff 250 → 500 ms. Aquí forzamos backoff cero para no
    dilatar la suite.
    """
    from kicad_mcp.bridge import ipc as ipc_module

    monkeypatch.setattr(ipc_module, "_BUSY_RETRY_BACKOFFS_MS", (0, 0))

    client = _BusyThenOkClient(busy_before_ok=1)
    bridge = IpcBridge(client_factory=_factory(client))

    with caplog.at_level("INFO", logger="kicad_mcp"):
        v = bridge.get_version()

    assert v.major == 10
    assert client.get_version_calls == 2, (
        f"esperaba 1 busy + 1 retry OK; hubo {client.get_version_calls} llamadas"
    )
    retry_lines = [r for r in caplog.records if '"ipc_retry"' in r.message]
    assert len(retry_lines) == 1
    assert '"op_name":"get_version"' in retry_lines[0].message
    assert '"attempt":1' in retry_lines[0].message


@pytest.mark.unit
def test_retry_persistent_busy_after_max_retries_returns_typed_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """AS_BUSY persistente → error tipado tras 2 reintentos con ``data.ipc_status='busy'``.

    Prueba de "mutation testing" del retry: forzamos el fake a nunca ceder
    (busy_before_ok muy alto) y verificamos que:
    - El bridge propaga ``KICAD_CLI_FAILED`` con ``data.ipc_status='busy'``.
    - El fake fue invocado exactamente 3 veces (1 intento inicial + 2 retries).
    - Se emiten exactamente 2 líneas de retry (attempts 1 y 2).
    """
    from kicad_mcp.bridge import ipc as ipc_module

    monkeypatch.setattr(ipc_module, "_BUSY_RETRY_BACKOFFS_MS", (0, 0))

    client = _BusyThenOkClient(busy_before_ok=99)
    bridge = IpcBridge(client_factory=_factory(client))

    with caplog.at_level("INFO", logger="kicad_mcp"), pytest.raises(KicadMcpError) as excinfo:
        bridge.get_version()

    assert excinfo.value.code is ErrorCode.KICAD_CLI_FAILED
    assert excinfo.value.data == {"ipc_status": "busy"}
    assert client.get_version_calls == 3, "1 inicial + 2 retries = 3 invocaciones al cliente"
    retry_lines = [r for r in caplog.records if '"ipc_retry"' in r.message]
    assert len(retry_lines) == 2, f"esperaba 2 retries logueados; hubo {len(retry_lines)}"
    assert '"attempt":1' in retry_lines[0].message
    assert '"attempt":2' in retry_lines[1].message


@pytest.mark.unit
def test_mutation_move_footprint_does_not_retry_on_busy() -> None:
    """AS_BUSY en una mutación ⇒ error INMEDIATO, exactamente 1 llamada IPC.

    D-07.1 no reintenta mutaciones bajo NINGUNA circunstancia (KiCad podría
    haber aceptado la primera y el retry duplicaría). Este test verifica la
    frontera estructural: ``move_footprint`` NO viaja por
    ``_run_supervised_read``, así que aunque el rechazo sea busy, no hay
    retry.
    """

    class _BusyBoard:
        def __init__(self) -> None:
            self.get_footprints_calls = 0

        def get_footprints(self) -> Any:
            self.get_footprints_calls += 1
            raise _kipy_busy()

    busy_board = _BusyBoard()
    board = BoardHandle(_raw=busy_board)
    bridge = IpcBridge(client_factory=_factory(_FakeClient(board=busy_board)))

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.move_footprint(board, "U1", Mm(10.0), Mm(20.0))

    assert excinfo.value.code is ErrorCode.KICAD_CLI_FAILED
    assert excinfo.value.data == {"ipc_status": "busy"}
    assert busy_board.get_footprints_calls == 1, (
        "una mutación NO se reintenta ante AS_BUSY (D-07.1); "
        f"hubo {busy_board.get_footprints_calls} invocaciones"
    )


@pytest.mark.unit
def test_mutation_add_via_does_not_retry_on_busy() -> None:
    """AS_BUSY en ``add_via`` ⇒ error INMEDIATO, exactamente 1 llamada IPC.

    B3 (D-09.3): como toda mutación (D-07.1), ``add_via`` viaja por
    ``_supervise`` directo, NO por ``_run_supervised_read``: un busy no se
    reintenta (KiCad podría haber aceptado la primera y el retry duplicaría
    la via). El busy se dispara en la búsqueda del net (``get_nets``).
    """

    class _BusyNetsBoard:
        def __init__(self) -> None:
            self.get_nets_calls = 0

        def get_nets(self) -> Any:
            self.get_nets_calls += 1
            raise _kipy_busy()

    busy_board = _BusyNetsBoard()
    board = BoardHandle(_raw=busy_board)
    bridge = IpcBridge(client_factory=_factory(_FakeClient(board=busy_board)))

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.add_via(board, "GND", Mm(50.0), Mm(50.0), Mm(0.8), Mm(0.4))

    assert excinfo.value.code is ErrorCode.KICAD_CLI_FAILED
    assert excinfo.value.data == {"ipc_status": "busy"}
    assert busy_board.get_nets_calls == 1, (
        "una mutación NO se reintenta ante AS_BUSY (D-07.1); "
        f"hubo {busy_board.get_nets_calls} invocaciones"
    )


class _FakeRevertBoard:
    """Board fake para ``reload_board_from_disk`` (P3.1, sesión 18).

    Imita el subset de ``kipy.Board`` que el método consume: ``revert()``
    (sin retorno, como ``Board.revert()`` real) + ``get_tracks()``/
    ``get_vias()`` para el conteo post-recarga.
    """

    def __init__(self, tracks: list[Any], vias: list[Any]) -> None:
        self._tracks = tracks
        self._vias = vias
        self.revert_calls = 0

    def revert(self) -> None:
        self.revert_calls += 1

    def get_tracks(self) -> list[Any]:
        return self._tracks

    def get_vias(self) -> list[Any]:
        return self._vias


@pytest.mark.unit
def test_reload_board_from_disk_calls_revert_and_counts_tracks_vias() -> None:
    """``reload_board_from_disk`` envuelve ``Board.revert()`` y devuelve
    ``(n_tracks, n_vias)`` releídos tras la recarga (P3.1, D-V3.1)."""
    raw = _FakeRevertBoard(tracks=[object(), object(), object()], vias=[object()])
    board = BoardHandle(_raw=raw)
    bridge = IpcBridge(client_factory=_factory(_FakeClient(board=raw)))

    n_tracks, n_vias = bridge.reload_board_from_disk(board)

    assert raw.revert_calls == 1
    assert (n_tracks, n_vias) == (3, 1)


@pytest.mark.unit
def test_reload_board_from_disk_is_idempotent_at_bridge_level() -> None:
    """Llamar ``reload_board_from_disk`` dos veces seguidas no falla (P3.1).

    Verificado también en vivo contra KiCad 10.0.4
    (``docs/investigacion/18-recarga-ipc.md``): ``Board.revert()`` es
    idempotente y no invalida el handle.
    """
    raw = _FakeRevertBoard(tracks=[], vias=[])
    board = BoardHandle(_raw=raw)
    bridge = IpcBridge(client_factory=_factory(_FakeClient(board=raw)))

    bridge.reload_board_from_disk(board)
    n_tracks, n_vias = bridge.reload_board_from_disk(board)

    assert raw.revert_calls == 2
    assert (n_tracks, n_vias) == (0, 0)


@pytest.mark.unit
def test_reload_board_from_disk_does_not_retry_on_busy() -> None:
    """AS_BUSY en la recarga ⇒ error INMEDIATO, exactamente 1 llamada a
    ``revert()``. Es ESCRITURA (D-07.1): no viaja por ``_run_supervised_read``,
    mismo patrón que ``move_footprint``/``add_via``."""

    class _BusyRevertBoard:
        def __init__(self) -> None:
            self.revert_calls = 0

        def revert(self) -> None:
            self.revert_calls += 1
            raise _kipy_busy()

    busy_board = _BusyRevertBoard()
    board = BoardHandle(_raw=busy_board)
    bridge = IpcBridge(client_factory=_factory(_FakeClient(board=busy_board)))

    with pytest.raises(KicadMcpError) as excinfo:
        bridge.reload_board_from_disk(board)

    assert excinfo.value.code is ErrorCode.KICAD_CLI_FAILED
    assert excinfo.value.data == {"ipc_status": "busy"}
    assert busy_board.revert_calls == 1, (
        "una mutación NO se reintenta ante AS_BUSY (D-07.1); "
        f"hubo {busy_board.revert_calls} invocaciones"
    )


@pytest.mark.unit
def test_run_supervised_read_rejects_non_idempotent_op_name() -> None:
    """``_run_supervised_read`` con un op fuera de la whitelist ⇒ AssertionError.

    La whitelist ``_IDEMPOTENT_OPS`` es la frontera estructural entre
    lecturas y mutaciones (D-07.1). No es un flag encendible: pasar un
    nombre no listado es un bug del código que llama, y explota loudly.
    """
    bridge = IpcBridge(client_factory=_factory(_FakeClient()))
    with pytest.raises(AssertionError, match="whitelist idempotente"):
        bridge._run_supervised_read("move_footprint", lambda: None)


@pytest.mark.unit
def test_supervise_preserves_client_on_busy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un AS_BUSY NO invalida ``self._client`` (D-07.1).

    Complemento de la sesión 04 T3: un fallo genérico invalida el cliente
    para forzar reconexión, pero AS_BUSY es transitorio y la conexión IPC
    sigue viva. Preservar el cliente evita reconexiones innecesarias
    cuando el wrapper de retry reintenta.
    """
    from kicad_mcp.bridge import ipc as ipc_module

    monkeypatch.setattr(ipc_module, "_BUSY_RETRY_BACKOFFS_MS", (0, 0))

    client = _BusyThenOkClient(busy_before_ok=99)
    factory = _CountingFactory(lambda: client)
    bridge = IpcBridge(client_factory=factory)

    with pytest.raises(KicadMcpError):
        bridge.get_version()

    # El factory fue invocado UNA sola vez: el bridge preservó el cliente
    # a través de los 3 intentos porque cada fallo era busy.
    assert factory.calls == 1, f"esperaba 1 conexión (busy preserva); hubo {factory.calls}"


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
    """Socket ``ipc://<path>`` inexistente y nada descubrible ⇒ ``KICAD_NOT_RUNNING``
    en <100 ms.

    Sin este fast-fail, ``kipy`` deja pasar la construcción y falla al
    primer ``send()`` con costo de import + arranque (medido: ~370 ms en
    la workstation de dev, se dispararía a 2 s ante timeouts reales).

    Sesión 19e: se hermetiza redirigiendo ``_KICAD_SOCKET_DIR`` (el dir de
    descubrimiento) a un ``tmp_path`` vacío, para que la cascada no
    encuentre nada más y caiga al último recurso (el env inexistente).
    """
    import kicad_mcp.bridge.ipc as ipc_module

    monkeypatch.setattr(ipc_module, "_KICAD_SOCKET_DIR", tmp_path / "discovery-empty")
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
def test_default_factory_resolves_arg_when_env_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sesión 19e — contrato *existence-aware*: env inexistente cede al arg.

    Con ``KICAD_API_SOCKET`` apuntando a un path que NO existe, la cascada
    ya no lo usa incondicionalmente (contrato pre-19e); sigue a
    ``socket_path`` (el arg del constructor), que sí existe, y se conecta
    con éxito. Reemplaza al test de sesión 04 que afirmaba lo contrario.
    """
    import kicad_mcp.bridge.ipc as ipc_module

    monkeypatch.setattr(ipc_module, "_KICAD_SOCKET_DIR", tmp_path / "discovery-empty")
    env_socket = tmp_path / "env-missing.sock"
    arg_socket = tmp_path / "arg-exists.sock"
    arg_socket.touch()
    monkeypatch.setenv("KICAD_API_SOCKET", f"ipc://{env_socket}")

    bridge = IpcBridge(socket_path=f"ipc://{arg_socket}")

    assert bridge._socket_path == f"ipc://{arg_socket}"


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


# --- resolución cascada del socket (sesión 19e, F-19b-09) --------------------


@pytest.mark.unit
def test_resolve_socket_env_var_wins_when_path_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``KICAD_API_SOCKET`` con path existente gana sobre todo lo demás."""
    import kicad_mcp.bridge.ipc as ipc_module

    monkeypatch.setattr(ipc_module, "_KICAD_SOCKET_DIR", tmp_path / "discovery")
    env_socket = tmp_path / "env.sock"
    env_socket.touch()
    monkeypatch.setenv("KICAD_API_SOCKET", f"ipc://{env_socket}")

    assert _resolve_kicad_socket() == f"ipc://{env_socket}"


@pytest.mark.unit
def test_resolve_socket_env_var_missing_falls_through_to_last_resort(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``KICAD_API_SOCKET`` con path inexistente y nada más descubrible ⇒ se
    devuelve igual como último recurso (para que el caller fast-failee)."""
    import kicad_mcp.bridge.ipc as ipc_module

    monkeypatch.setattr(ipc_module, "_KICAD_SOCKET_DIR", tmp_path / "discovery-empty")
    env_socket = tmp_path / "env-missing.sock"
    monkeypatch.setenv("KICAD_API_SOCKET", f"ipc://{env_socket}")

    assert _resolve_kicad_socket() == f"ipc://{env_socket}"


@pytest.mark.unit
def test_resolve_socket_legacy_path_used_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Solo existe el path legacy ``api.sock`` (sin PID) ⇒ se usa ese."""
    import kicad_mcp.bridge.ipc as ipc_module

    monkeypatch.delenv("KICAD_API_SOCKET", raising=False)
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir()
    monkeypatch.setattr(ipc_module, "_KICAD_SOCKET_DIR", discovery_dir)
    legacy = discovery_dir / "api.sock"
    legacy.touch()

    assert _resolve_kicad_socket() == f"ipc://{legacy}"


@pytest.mark.unit
def test_resolve_socket_single_pid_glob_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Solo existe ``api-<PID>.sock`` (KiCad 10.0.4) ⇒ se descubre por glob."""
    import kicad_mcp.bridge.ipc as ipc_module

    monkeypatch.delenv("KICAD_API_SOCKET", raising=False)
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir()
    monkeypatch.setattr(ipc_module, "_KICAD_SOCKET_DIR", discovery_dir)
    pid_socket = discovery_dir / "api-1234.sock"
    pid_socket.touch()

    assert _resolve_kicad_socket() == f"ipc://{pid_socket}"


@pytest.mark.unit
def test_resolve_socket_multiple_pid_globs_picks_newest_and_warns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Múltiples ``api-<PID>.sock`` ⇒ se elige el más reciente por ``mtime`` y
    se loguea un warning (sockets de instancias previas de KiCad no limpiadas)."""
    import logging

    import kicad_mcp.bridge.ipc as ipc_module

    monkeypatch.delenv("KICAD_API_SOCKET", raising=False)
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir()
    monkeypatch.setattr(ipc_module, "_KICAD_SOCKET_DIR", discovery_dir)

    older = discovery_dir / "api-1234.sock"
    newer = discovery_dir / "api-5678.sock"
    older.touch()
    newer.touch()
    now = time.time()
    os.utime(older, (now - 100, now - 100))
    os.utime(newer, (now, now))

    with caplog.at_level(logging.WARNING, logger="kicad_mcp"):
        result = _resolve_kicad_socket()

    assert result == f"ipc://{newer}"
    assert any("socket_discovery" in record.message for record in caplog.records)


@pytest.mark.unit
def test_resolve_socket_nothing_found_returns_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sin env, sin arg, sin ningún socket en el dir de descubrimiento ⇒ ``None``."""
    import kicad_mcp.bridge.ipc as ipc_module

    monkeypatch.delenv("KICAD_API_SOCKET", raising=False)
    monkeypatch.setattr(ipc_module, "_KICAD_SOCKET_DIR", tmp_path / "discovery-empty")

    assert _resolve_kicad_socket() is None


@pytest.mark.unit
def test_socket_present_reflects_live_filesystem_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``socket_present()`` re-resuelve en cada llamada, no cachea del ``__init__``.

    Sesión 19e / R11: verificado en vivo que el proceso ``kicad-mcp`` vive
    más que una sesión de KiCad — si el socket resuelto se congelara en el
    constructor, un reinicio de KiCad a mitad de vida del bridge dejaría
    ``socket_present()`` reportando ``False`` para siempre aunque KiCad
    vuelva a estar arriba con un socket nuevo.
    """
    import kicad_mcp.bridge.ipc as ipc_module

    monkeypatch.delenv("KICAD_API_SOCKET", raising=False)
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir()
    monkeypatch.setattr(ipc_module, "_KICAD_SOCKET_DIR", discovery_dir)

    bridge = IpcBridge()
    assert bridge.socket_present() is False  # nada en el dir todavía

    pid_socket = discovery_dir / "api-9999.sock"
    pid_socket.touch()
    assert bridge.socket_present() is True  # mismo bridge, sin reconstruir

    pid_socket.unlink()
    assert bridge.socket_present() is False  # KiCad se cerró de nuevo


@pytest.mark.unit
def test_bridge_reconnects_when_socket_changes_after_kicad_restart(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R11 — KiCad se reinicia con un socket distinto a mitad de vida del
    bridge (PID nuevo, o incluso sin sufijo de PID — observado en vivo,
    sesión 19e) ⇒ el próximo request re-resuelve y reconecta solo, sin
    reconstruir el ``IpcBridge`` ni intervención humana.
    """
    import kicad_mcp.bridge.ipc as ipc_module

    monkeypatch.delenv("KICAD_API_SOCKET", raising=False)
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir()
    monkeypatch.setattr(ipc_module, "_KICAD_SOCKET_DIR", discovery_dir)

    first_socket = discovery_dir / "api-1111.sock"
    first_socket.touch()

    seen_paths: list[str | None] = []

    class _RecordingFactory:
        def __call__(
            self, socket_path: str | None, timeout_ms: int, kicad_token: str | None
        ) -> _FakeClient:
            seen_paths.append(socket_path)
            return _FakeClient(_FakeVersion("10.0.4", 10, 0, 4))

    bridge = IpcBridge(client_factory=_RecordingFactory())
    bridge.get_version()
    assert seen_paths == [f"ipc://{first_socket}"]

    # KiCad se reinicia: el socket viejo desaparece, aparece uno nuevo con
    # otro nombre — sin symlink ni intervención manual (visto en vivo: la
    # segunda instancia usó ``api.sock`` sin PID, no ``api-<PID>.sock``).
    first_socket.unlink()
    second_socket = discovery_dir / "api.sock"
    second_socket.touch()

    bridge.get_version()
    assert seen_paths == [f"ipc://{first_socket}", f"ipc://{second_socket}"]


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
