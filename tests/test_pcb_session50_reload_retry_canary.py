"""Canario permanente — F-RELOAD-STALE-POST-ROUTE (sesión 50).

Hallazgo de sesión 50 (Validation Suite, gate GUI 32d retomado contra
``anavi-dev-mic`` con Freerouting real): ``open_board`` (el ``BoardHandle``
que ``route_board`` usa para recargar el editor vivo post-route, D-V3.1)
se captura ANTES de arrancar el subprocess externo de Freerouting — que
puede tardar varios minutos (250-320s en las dos corridas reales de esta
sesión) sin que haya ningún tráfico IPC de por medio.
``reload_board_from_disk(open_board)`` puede fallar con
``ConnectionError`` (mapeado a ``KICAD_NOT_RUNNING`` por
``_map_ipc_failure``) — observado en 3 de 4 corridas reales, pese a que
KiCad sigue corriendo y respondiendo (confirmado por una conexión
*distinta*, activa, en el mismo instante del fallo). **Causa raíz NO
confirmada**: la hipótesis obvia ("la conexión muere por inactividad
durante esa espera") se REFUTÓ con 7 repros aislados que no lograron
reproducir el fallo (idle con pings, carga real de CPU, silencio total
ininterrumpido de 290s, subprocess.run() real, la clase IpcBridge real,
dispatch vía anyio.to_thread.run_sync, os.replace() sobre el archivo
abierto — ver ``docs/BACKLOG.md`` entrada ``F-RELOAD-STALE-POST-ROUTE``
para el detalle completo). El patrón observado (3/4 fallos, no 4/4) es
más compatible con una race condition intermitente que con inactividad
simple del socket.

Antes de este fix, eso disparaba ``POST_ROUTE_REFILL_SKIPPED``
(D-32b.1, sesión 32b) SIEMPRE que el ruteo tardara lo suficiente — el
caso NORMAL para cualquier board no trivial, no uno raro. El mecanismo
de refill automático (razón de ser de todo el pipeline post-route,
D-23.2/ADR-0012) quedaba inútil en la práctica.

El fix: un ÚNICO reintento de la recarga con un handle COMPLETAMENTE
FRESCO (``_open_board_or_none(bridge)`` de nuevo, no la ``board`` vieja)
cuando el error es específicamente ``KICAD_NOT_RUNNING`` — la firma de
una conexión perdida, no de un fallo real de KiCad. ``_supervise`` ya
invalida ``bridge._client`` tras ese error (para el PRÓXIMO request, sin
violar D-07.1 — no hay retry de la MISMA conexión), así que el reintento
usa una conexión nueva. Sólo se acepta si, tras reconectar, el editor
abierto SIGUE siendo el mismo target — si cambió o se cerró mientras
tanto, es un fallo genuino y el comportamiento de D-32b.1 (sin cambios)
sigue aplicando. Ver ``docs/adr/0012-route-board-persist-contract.md``
§"Extensión F-RELOAD-STALE (sesión 50)".

No reabre ni relaja el guard `reloaded is True` que D-32b.1 fijó
explícitamente (ADR-0012 §"Por qué el guard `reloaded is True` NO se
relaja") — el reintento SIGUE yendo por el mismo camino de éxito/fracaso
tipado, sólo le da una segunda oportunidad a la recarga en sí antes de
concluir que falló.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.autoroute import AutorouteResult
from kicad_mcp.bridge.ipc import (
    BBoxMm,
    BoardContext,
    BoardHandle,
    FootprintData,
    FootprintPadData,
    IpcBridge,
    Mm,
)
from kicad_mcp.bridge.rules import RulesReport
from kicad_mcp.errors import ErrorCode, KicadMcpError
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store
from kicad_mcp.tools import pcb as pcb_module
from kicad_mcp.tools.pcb import register as register_pcb
from kicad_mcp.tools.world import register as register_world

_UNSET = object()


class _FakeBridge(IpcBridge):
    """Bridge en memoria para route_board. No toca socket ni kipy.

    Subconjunto propio (mismo espíritu que ``test_route_board.py`` y
    ``test_pcb_session32b_refill_silencioso_canary.py`` — sin precedente de
    imports cross-módulo entre tests, ver ``test_pcb_session31b_duplicate_
    refs.py``) con los knobs exactos que este canario necesita:
    ``reload_error``/``reload_fail_times`` (cuántas llamadas consecutivas a
    ``reload_board_from_disk`` fallan antes de tener éxito) y
    ``open_board_path_on_retry`` (qué ve el SEGUNDO ``get_open_board()`` en
    adelante — simula "conexión fresca tras reconectar", posiblemente con
    un target distinto si el editor se cerró/cambió mientras tanto).
    """

    def __init__(
        self,
        *,
        open_board_path: str | None = None,
        refs: list[str] | None = None,
        reload_error: Exception | None = None,
        reload_fail_times: int = 1,
        open_board_path_on_retry: str | None | object = _UNSET,
        n_zones: int = 0,
    ) -> None:
        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._open_board_path = open_board_path
        self._open_board_path_on_retry = open_board_path_on_retry
        self._refs = list(refs or ["U1", "R1"])
        self._reload_error = reload_error
        self._reload_fail_times = reload_fail_times
        self._n_zones = n_zones
        self.saved: list[str] = []
        self.reload_calls = 0
        self.get_open_board_calls = 0
        self.refill_calls = 0
        self.enforce_hole_clearance_calls = 0

    def _current_path(self) -> str | None:
        if self.get_open_board_calls > 1 and self._open_board_path_on_retry is not _UNSET:
            path = self._open_board_path_on_retry
            assert path is None or isinstance(path, str)
            return path
        return self._open_board_path

    def get_open_board(self) -> BoardHandle | None:  # type: ignore[override]
        self.get_open_board_calls += 1
        if self._current_path() is None:
            return None
        return BoardHandle(_raw=object())

    def get_open_board_path(self, board: BoardHandle) -> Path | None:  # type: ignore[override]
        path = self._current_path()
        return Path(path) if path else None

    def save_board(self, board: BoardHandle) -> None:  # type: ignore[override]
        self.saved.append(self._open_board_path or "")

    def reload_board_from_disk(self, board: BoardHandle) -> tuple[int, int]:  # type: ignore[override]
        self.reload_calls += 1
        if self._reload_error is not None and self.reload_calls <= self._reload_fail_times:
            raise self._reload_error
        return (0, 0)

    def list_zones(self, board: BoardHandle) -> tuple[Any, ...]:  # type: ignore[override]
        return tuple(range(self._n_zones))

    def refill_zones(self, board: BoardHandle) -> int:  # type: ignore[override]
        self.refill_calls += 1
        return self._n_zones

    def enforce_hole_clearance(self, board: BoardHandle, pcb_path: Path) -> int:  # type: ignore[override]
        self.enforce_hole_clearance_calls += 1
        return 0

    def read_board_context(self, board: BoardHandle) -> BoardContext:  # type: ignore[override]
        fps = tuple(
            FootprintData(
                ref=ref,
                value="V",
                x_mm=Mm(1.0),
                y_mm=Mm(2.0),
                pads=(FootprintPadData(number="1", net_name="GND"),),
                kiid=f"kiid-{ref}",
            )
            for ref in self._refs
        )
        return BoardContext(
            refs=tuple(self._refs), bbox=BBoxMm(Mm(0), Mm(0), Mm(100), Mm(100)), footprints=fps
        )


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "proj.kicad_sch").write_text("(kicad_sch)")
    (project / "proj.kicad_pcb").write_text("(kicad_pcb original)")
    return project


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _json(result: CallToolResult) -> dict[str, Any]:
    return json.loads(_text(result))


def _drc(unconnected: int, errors: int = 0) -> RulesReport:
    from kicad_mcp.bridge.rules import Violation

    violations = tuple(
        Violation(rule="clearance", severity="error", message="err", items=())
        for _ in range(errors)
    )
    return RulesReport(
        violations=violations,
        counts={"error": errors} if errors else {},
        coordinate_units="mm",
        kicad_version="10.0.4",
        unconnected=unconnected,
    )


def _patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    drc_sequence: list[RulesReport],
    result: AutorouteResult | Exception,
) -> dict[str, Any]:
    calls: dict[str, Any] = {"drc": 0, "autoroute_args": None}

    def _fake_drc(pcb_path: Path) -> RulesReport:
        report = drc_sequence[min(calls["drc"], len(drc_sequence) - 1)]
        calls["drc"] += 1
        return report

    def _fake_autoroute(src: Path, workdir: Path, **kw: Any) -> AutorouteResult:
        calls["autoroute_args"] = {"src": src, "workdir": workdir, **kw}
        if isinstance(result, Exception):
            raise result
        routed = Path(result.routed_pcb)
        routed.parent.mkdir(parents=True, exist_ok=True)
        routed.write_text("(kicad_pcb routed)")
        return result

    monkeypatch.setattr(pcb_module, "run_drc", _fake_drc)
    monkeypatch.setattr(pcb_module, "run_autoroute", _fake_autoroute)
    return calls


def _result(workdir: Path, *, ruteables: int = 2, routed: int = 2) -> AutorouteResult:
    pin_counts = {f"NET{i}": 2 for i in range(ruteables)}
    wire_counts = {f"NET{i}": 1 for i in range(routed)}
    return AutorouteResult(
        tracks_before=0,
        tracks_after=10,
        vias_before=0,
        vias_after=2,
        export_ms=1.0,
        route_ms=2.0,
        import_ms=1.0,
        routed_pcb=str(workdir / ".kicad-mcp" / "autoroute" / "routed.kicad_pcb"),
        freerouting_log=str(workdir / "log"),
        nets_pin_counts=pin_counts,
        nets_wire_counts=wire_counts,
        dsn_path=str(workdir / ".kicad-mcp" / "autoroute" / "route.dsn"),
        ses_path=str(workdir / ".kicad-mcp" / "autoroute" / "route.ses"),
    )


def _server(bridge: IpcBridge) -> FastMCP:
    mcp = FastMCP(name="test", instructions="test")
    register_pcb(mcp, ipc_bridge=bridge)
    register_world(mcp, ipc_bridge=bridge)
    return mcp


@pytest.fixture(autouse=True)
def _reset_g1() -> Any:
    g1.reset_session_state()
    yield
    g1.reset_session_state()


def _not_running_error() -> KicadMcpError:
    return KicadMcpError(
        code=ErrorCode.KICAD_NOT_RUNNING,
        message="Conexión IPC con KiCad perdida durante la operación.",
        hint="Reintentar.",
    )


def _busy_error() -> KicadMcpError:
    return KicadMcpError(
        code=ErrorCode.KICAD_CLI_FAILED,
        message="KiCad está ocupado durante reload_board_from_disk.",
        hint="reintentá en unos segundos.",
        data={"ipc_status": "busy"},
    )


@pytest.mark.unit
async def test_reload_retry_succeeds_with_fresh_handle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Núcleo del fix: la 1ª recarga falla con KICAD_NOT_RUNNING (conexión
    vieja, capturada antes del subprocess largo); el reintento con handle
    fresco tiene éxito — el refill de seguridad SÍ corre, sin
    POST_ROUTE_REFILL_SKIPPED."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(monkeypatch, drc_sequence=[_drc(3), _drc(0)], result=_result(project))
    bridge = _FakeBridge(
        open_board_path=str(project / "proj.kicad_pcb"),
        n_zones=2,
        reload_error=_not_running_error(),
        reload_fail_times=1,  # falla la 1ª, tiene éxito la 2ª (el reintento)
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert not result.isError, _text(result)
    payload = _json(result)
    assert payload["reloaded"] is True
    assert payload["zones"]["refilladas"] == 2
    assert bridge.reload_calls == 2  # 1 falla + 1 reintento exitoso
    assert bridge.get_open_board_calls == 2  # fetch inicial + fetch del reintento
    assert bridge.refill_calls == 1
    assert bridge.enforce_hole_clearance_calls == 1
    assert get_default_store().is_live_stale() is False


@pytest.mark.unit
async def test_reload_retry_gives_up_after_second_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Si el reintento con handle fresco TAMBIÉN falla con KICAD_NOT_RUNNING,
    route_board no reintenta una segunda vez — cae a POST_ROUTE_REFILL_SKIPPED
    como antes del fix (2 llamadas totales a reload, no más)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(monkeypatch, drc_sequence=[_drc(3), _drc(0)], result=_result(project))
    bridge = _FakeBridge(
        open_board_path=str(project / "proj.kicad_pcb"),
        n_zones=2,
        reload_error=_not_running_error(),
        reload_fail_times=2,  # falla la 1ª Y el reintento
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert result.isError
    assert "POST_ROUTE_REFILL_SKIPPED" in _text(result)
    assert bridge.reload_calls == 2
    assert bridge.refill_calls == 0


@pytest.mark.unit
async def test_reload_retry_skipped_when_editor_closed_meanwhile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Si tras reconectar el editor ya NO tiene ningún board abierto (se
    cerró mientras Freerouting corría), no hay handle fresco que reintentar
    — se preserva POST_ROUTE_REFILL_SKIPPED, sin una 2ª llamada a reload."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(monkeypatch, drc_sequence=[_drc(3), _drc(0)], result=_result(project))
    bridge = _FakeBridge(
        open_board_path=str(project / "proj.kicad_pcb"),
        n_zones=2,
        reload_error=_not_running_error(),
        reload_fail_times=1,
        open_board_path_on_retry=None,  # editor cerrado en la reconexión
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert result.isError
    assert "POST_ROUTE_REFILL_SKIPPED" in _text(result)
    assert bridge.reload_calls == 1  # nunca llegó a reintentar el reload en sí
    assert bridge.get_open_board_calls == 2  # sí intentó reconectar y ver qué había


@pytest.mark.unit
async def test_reload_retry_skipped_when_different_project_open_meanwhile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Si tras reconectar hay OTRO proyecto abierto (no el target), tampoco
    se reintenta el reload — mismo espíritu que el guard ``is_target_open``
    original, sólo evaluado de nuevo con datos frescos."""
    project = _make_project(tmp_path)
    other = tmp_path / "otro.kicad_pcb"
    other.write_text("(kicad_pcb otro)")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(monkeypatch, drc_sequence=[_drc(3), _drc(0)], result=_result(project))
    bridge = _FakeBridge(
        open_board_path=str(project / "proj.kicad_pcb"),
        n_zones=2,
        reload_error=_not_running_error(),
        reload_fail_times=1,
        open_board_path_on_retry=str(other),
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert result.isError
    assert "POST_ROUTE_REFILL_SKIPPED" in _text(result)
    assert bridge.reload_calls == 1


@pytest.mark.unit
async def test_no_retry_for_non_connection_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-07.1 sigue intacto para cualquier error que NO sea la firma de
    conexión perdida (``KICAD_NOT_RUNNING``): un ``AS_BUSY`` (u otro fallo
    real de KiCad) no dispara el reintento — mismo comportamiento que antes
    del fix, ver también ``test_no_retry_del_reload`` en el canario de
    sesión 32b."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(monkeypatch, drc_sequence=[_drc(3), _drc(0)], result=_result(project))
    bridge = _FakeBridge(
        open_board_path=str(project / "proj.kicad_pcb"),
        n_zones=2,
        reload_error=_busy_error(),
        reload_fail_times=99,  # irrelevante: no debería reintentarse en absoluto
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert result.isError
    assert "POST_ROUTE_REFILL_SKIPPED" in _text(result)
    assert bridge.reload_calls == 1  # ni get_open_board_or_none se volvió a llamar
    assert bridge.get_open_board_calls == 1
