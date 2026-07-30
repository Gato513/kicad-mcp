"""Canario permanente — F-V2-REFILL-SILENCIOSO (sesión 32b).

Hallazgo de sesión 32 (Validation Suite Nivel B-01, ANAVI Macro Pad 12),
reproducido también en el audit log de sesión 31c: el bloque de refill de
seguridad de ``route_board(refill=true)`` (refill + ``enforce_hole_clearance``
+ ``save_board``, D-23.2/ADR-0012) sólo corre si ``reload_board_from_disk``
tuvo éxito. Esa recarga es una **mutación sin reintento** (D-07.1): un
``AS_BUSY`` transitorio basta para que falle una sola vez, y la excepción se
descartaba en silencio (``except KicadMcpError: reloaded = False``) — sin
``POST_ROUTE_PERSIST_FAILED``, sin ningún error visible, dejando el plano GND
sin el clearance que Freerouting no respeta nativamente (D-19.1). En sesión
32 esto dejó 259 violaciones DRC reales sin resolver hasta recuperación
manual.

El fix (D-32b.1): la excepción de la recarga ya no se descarta — alimenta un
código de error nuevo, ``POST_ROUTE_REFILL_SKIPPED`` (adición pura al
``StrEnum``, F1/F3 intacta), levantado únicamente cuando el refill prometido
(``refill=true``, ``zones_existentes > 0``) no corrió por esa razón concreta
(``reload_error is not None``). Los otros dos motivos legítimos de que el
refill no corra — editor cerrado, board de otro proyecto abierto — NO son
error (ya documentados en tool-catalog.md vía el campo ``reloaded``): se
exponen como ``zones.refill_skipped_reason`` sin abortar (H4, no regresión).

El raise va DESPUÉS del DRC post-route + registro del snapshot +
``store.mark_live_stale`` (no en el guard de arriba) — abortar antes dejaría
el flag ``live_stale`` en ``False`` con el disco adelante del vivo, y un
``fill_zones()`` posterior pasaría ``_guard_live_stale()`` y pisaría el ruteo
con su propio ``save_board``.

H2 del prompt de sesión (¿el mismo bug afecta ``fill_zones``/``add_zone``?)
quedó REFUTADA por inspección: ninguna de las dos llama
``reload_board_from_disk`` — no tienen este camino silencioso, así que no
requieren cambio (ver ``docs/adr/0012-route-board-persist-contract.md``
§"Extensión F-V2 (sesión 32b)").
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

from kicad_mcp.audit.logger import audit_path
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

# --- Fake bridge (mismo espíritu que tests/test_route_board.py) -------------


class _FakeBridge(IpcBridge):
    """Bridge en memoria para route_board. No toca socket ni kipy.

    Subconjunto de ``_FakeBridge`` de ``test_route_board.py`` — no se importa
    de ahí (sin precedente de imports cross-módulo entre tests, ver
    ``test_pcb_session31b_duplicate_refs.py``) — con los knobs exactos que
    este canario necesita: ``reload_error`` y ``n_zones``.
    """

    def __init__(
        self,
        *,
        open_board_path: str | None = None,
        refs: list[str] | None = None,
        raise_not_running: bool = False,
        reload_error: Exception | None = None,
        n_zones: int = 0,
    ) -> None:
        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._open_board_path = open_board_path
        self._refs = list(refs or ["U1", "R1"])
        self._raise_not_running = raise_not_running
        self._reload_error = reload_error
        self._n_zones = n_zones
        self.saved: list[str] = []
        self.reload_calls = 0
        self.refill_calls = 0
        self.enforce_hole_clearance_calls = 0

    def get_open_board(self) -> BoardHandle | None:  # type: ignore[override]
        if self._raise_not_running:
            raise KicadMcpError(
                code=ErrorCode.KICAD_NOT_RUNNING,
                message="KiCad no corre.",
                hint="Abrí KiCad.",
            )
        if self._open_board_path is None:
            return None
        return BoardHandle(_raw=object())

    def get_open_board_path(self, board: BoardHandle) -> Path | None:  # type: ignore[override]
        return Path(self._open_board_path) if self._open_board_path else None

    def save_board(self, board: BoardHandle) -> None:  # type: ignore[override]
        self.saved.append(self._open_board_path or "")

    def reload_board_from_disk(self, board: BoardHandle) -> tuple[int, int]:  # type: ignore[override]
        self.reload_calls += 1
        if self._reload_error is not None:
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
    """Faketea run_drc (secuencia pre/post) y run_autoroute."""
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


def _reload_busy_error() -> KicadMcpError:
    return KicadMcpError(
        code=ErrorCode.KICAD_CLI_FAILED,
        message="KiCad está ocupado durante reload_board_from_disk.",
        hint="reintentá en unos segundos.",
        data={"ipc_status": "busy"},
    )


# --- H1/H3: el refill saltado por reload_error rompe el contrato ------------


@pytest.mark.unit
async def test_refill_skipped_when_reload_fails_with_zones(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Núcleo de F-V2-REFILL-SILENCIOSO: con zonas presentes, si la recarga
    falla, route_board debe levantar POST_ROUTE_REFILL_SKIPPED — no
    completar en silencio con zones.refilladas=0."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(monkeypatch, drc_sequence=[_drc(3), _drc(0)], result=_result(project))
    bridge = _FakeBridge(
        open_board_path=str(project / "proj.kicad_pcb"),
        n_zones=2,
        reload_error=_reload_busy_error(),
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert result.isError
    text = _text(result)
    assert "POST_ROUTE_REFILL_SKIPPED" in text
    # El refill de seguridad NO corrió (ni enforce, ni el save que le sigue).
    assert bridge.refill_calls == 0
    assert bridge.enforce_hole_clearance_calls == 0
    # Sólo el save implícito pre-route corrió — ninguno post-refill.
    assert bridge.saved == [str(project / "proj.kicad_pcb")]
    # El .kicad_pcb en disco sigue siendo el ruteo crudo — válido, sin pisar.
    assert (project / "proj.kicad_pcb").read_text() == "(kicad_pcb routed)"
    # data trae el forense necesario para recuperación manual.
    assert "data: " in text
    data_json = json.loads(text.split("data: ", 1)[1])
    assert data_json["zones_existentes"] == 2
    assert data_json["zones_refilladas"] == 0
    assert data_json["reload_error_code"] == "KICAD_CLI_FAILED"
    assert "snap" in data_json
    assert "tracks_added" in data_json


@pytest.mark.unit
async def test_live_stale_marcado_antes_de_levantar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """El flag D-14.1 se marca ANTES del raise (hallazgo 3): si se abortara
    en el guard de arriba, live_stale quedaría en False con el disco
    adelante del vivo — un fill_zones() posterior pisaría el ruteo."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(monkeypatch, drc_sequence=[_drc(3), _drc(0)], result=_result(project))
    bridge = _FakeBridge(
        open_board_path=str(project / "proj.kicad_pcb"),
        n_zones=1,
        reload_error=_reload_busy_error(),
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert result.isError
    assert get_default_store().is_live_stale() is True


@pytest.mark.unit
async def test_no_retry_del_reload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """D-07.1: mutaciones no se reintentan. reload_board_from_disk se llama
    UNA sola vez pese a fallar — el fix no agrega retry."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(monkeypatch, drc_sequence=[_drc(3), _drc(0)], result=_result(project))
    bridge = _FakeBridge(
        open_board_path=str(project / "proj.kicad_pcb"),
        n_zones=1,
        reload_error=_reload_busy_error(),
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert result.isError
    assert bridge.reload_calls == 1


@pytest.mark.unit
async def test_audit_conserva_forense_y_error_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """El audit log NO se sacrifica al reportar el error — conserva el
    result forense (reloaded, zones_existentes/refilladas) que fue lo que
    permitió detectar el bug original en sesión 32, más el error_code."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(monkeypatch, drc_sequence=[_drc(3), _drc(0)], result=_result(project))
    bridge = _FakeBridge(
        open_board_path=str(project / "proj.kicad_pcb"),
        n_zones=2,
        reload_error=_reload_busy_error(),
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert result.isError
    lines = audit_path(project).read_text().strip().splitlines()
    entry = json.loads(lines[-1])
    assert entry["tool"] == "route_board"
    assert entry["error_code"] == "POST_ROUTE_REFILL_SKIPPED"
    assert entry["result"]["reloaded"] is False
    assert entry["result"]["zones_existentes"] == 2
    assert entry["result"]["zones_refilladas"] == 0
    assert entry["result"]["refill_skipped_reason"] == "reload_failed"


# --- H4: caminos vecinos legítimos NO son error (no regresión) --------------


@pytest.mark.unit
async def test_sin_zonas_no_hay_falso_positivo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sin zonas preexistentes, no hay nada que refillear — la recarga
    fallida no rompe ningún contrato de seguridad. Reportado como
    diagnóstico, no como error."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(monkeypatch, drc_sequence=[_drc(3), _drc(0)], result=_result(project))
    bridge = _FakeBridge(
        open_board_path=str(project / "proj.kicad_pcb"),
        n_zones=0,
        reload_error=_reload_busy_error(),
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert not result.isError, _text(result)
    payload = _json(result)
    assert "refill_skipped_reason" not in payload["zones"]
    assert payload["zones"]["existentes"] == 0


@pytest.mark.unit
async def test_editor_cerrado_no_es_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Editor cerrado es un camino de diseño legítimo (documentado vía
    reloaded="skipped_editor_closed") — se expone la razón, sin abortar."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(
        monkeypatch, drc_sequence=[_drc(2), _drc(0)], result=_result(project, ruteables=2, routed=2)
    )
    bridge = _FakeBridge(raise_not_running=True)  # KiCad cerrado
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert not result.isError, _text(result)
    payload = _json(result)
    assert payload["reloaded"] == "skipped_editor_closed"
    # Sin board vivo no hay zonas_existentes leíbles (best-effort, ver
    # docstring de zones_existentes en route_board) — no aplica razón.
    assert payload["zones"]["existentes"] == 0
    assert "refill_skipped_reason" not in payload["zones"]


@pytest.mark.unit
async def test_cross_project_no_es_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Board de OTRO proyecto abierto: reloaded=False sin reload_calls (el
    reload ni se intenta) — no es el bug, no debe ser error."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(
        monkeypatch, drc_sequence=[_drc(2), _drc(0)], result=_result(project, ruteables=2, routed=2)
    )
    bridge = _FakeBridge(open_board_path="/tmp/otro-proyecto/otro.kicad_pcb")
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert not result.isError, _text(result)
    payload = _json(result)
    assert payload["reloaded"] is False
    assert bridge.reload_calls == 0
    assert payload["zones"]["existentes"] == 0
    assert "refill_skipped_reason" not in payload["zones"]


@pytest.mark.unit
async def test_camino_feliz_sin_razon(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Refill exitoso (H4, control): sin reload_error, la recarga y el
    refill corren normalmente — sin razón, sin error."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(monkeypatch, drc_sequence=[_drc(3), _drc(0)], result=_result(project))
    bridge = _FakeBridge(open_board_path=str(project / "proj.kicad_pcb"), n_zones=2)
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert not result.isError, _text(result)
    payload = _json(result)
    assert "refill_skipped_reason" not in payload["zones"]
    assert payload["zones"]["refilladas"] == 2
    assert bridge.refill_calls == 1
