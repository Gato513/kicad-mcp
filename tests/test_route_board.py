"""Tests unit de ``route_board`` + flag ``live_stale`` (T2, D-14.1..D-14.3).

Dos bloques:
1. **Flag D-14.1** — cada rama: mutación bloqueada, save bloqueado, delete
   bloqueado, lectura viva con aviso, ``confirm_reloaded`` limpia, disco/sch
   inmunes.
2. **Tool ``route_board``** — con ``run_autoroute``/``run_drc`` fakeados: confirm
   con conteos, flag activo, snapshot, save implícito seguro (sólo si el board
   abierto ES el target), y propagación de errores tipados sin dejar el flag.
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
from kicad_mcp.errors import ErrorCode
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store
from kicad_mcp.tools import pcb as pcb_module
from kicad_mcp.tools.pcb import register as register_pcb
from kicad_mcp.tools.world import register as register_world


class _FakeBridge(IpcBridge):
    """Bridge en memoria para route_board / flag. No toca socket ni kipy."""

    def __init__(
        self,
        *,
        open_board_path: str | None = None,
        refs: list[str] | None = None,
        raise_not_running: bool = False,
    ) -> None:
        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._open_board_path = open_board_path
        self._refs = list(refs or ["U1", "R1"])
        self._raise_not_running = raise_not_running
        self.saved: list[str] = []

    def get_open_board(self) -> BoardHandle | None:  # type: ignore[override]
        if self._raise_not_running:
            from kicad_mcp.errors import KicadMcpError

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
    """``route_board`` devuelve JSON estructurado (P2.2, sesión 17) — no un
    confirm de texto plano."""
    return json.loads(_text(result))


@pytest.fixture(autouse=True)
def _reset_g1() -> Any:
    g1.reset_session_state()
    yield
    g1.reset_session_state()


def _server(bridge: IpcBridge) -> FastMCP:
    mcp = FastMCP(name="test", instructions="test")
    register_pcb(mcp, ipc_bridge=bridge)
    register_world(mcp, ipc_bridge=bridge)
    return mcp


# --- Bloque 1: flag D-14.1 ----------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("move_footprint", {"ref": "U1", "x_mm": 10.0, "y_mm": 10.0}),
        (
            "add_track",
            {"net": "GND", "start_x_mm": 1.0, "start_y_mm": 1.0, "end_x_mm": 2.0, "end_y_mm": 2.0},
        ),
        ("add_via", {"x_mm": 5.0, "y_mm": 5.0, "net": "GND"}),
        ("delete_track", {"net": "GND", "near_x_mm": 1.0, "near_y_mm": 1.0}),
        ("delete_via", {"net": "GND", "x_mm": 1.0, "y_mm": 1.0}),
        ("save_board", {}),
    ],
)
async def test_mutation_blocked_when_live_stale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tool: str, args: dict[str, Any]
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    get_default_store().mark_live_stale(7)
    mcp = _server(_FakeBridge())

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(tool, args)

    assert result.isError
    text = _text(result)
    assert "EXTERNAL_EDIT_DETECTED" in text
    assert "File→Revert" in text or "confirm_reloaded" in text


@pytest.mark.unit
async def test_live_read_works_with_notice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    get_default_store().mark_live_stale(7)
    bridge = _FakeBridge(open_board_path=str(project / "proj.kicad_pcb"))

    # board_outline lo consume get_world_context(kind='pcb'); lo fakeamos.
    def _board_outline(board: BoardHandle) -> tuple[BBoxMm, str]:
        return (BBoxMm(Mm(0), Mm(0), Mm(50), Mm(50)), "none")

    monkeypatch.setattr(bridge, "board_outline", _board_outline)
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_world_context", {"kind": "pcb"})

    assert not result.isError
    text = _text(result)
    assert text.startswith("[AVISO] editor vivo detras del disco (route_board)")
    # La lectura sigue funcionando (no se bloquea) y el flag NO se limpió.
    assert get_default_store().is_live_stale() is True


@pytest.mark.unit
async def test_confirm_reloaded_clears_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    get_default_store().mark_live_stale(7)
    bridge = _FakeBridge(open_board_path=str(project / "proj.kicad_pcb"))
    monkeypatch.setattr(
        bridge, "board_outline", lambda board: (BBoxMm(Mm(0), Mm(0), Mm(50), Mm(50)), "none")
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "get_world_context", {"kind": "pcb", "confirm_reloaded": True}
        )

    assert not result.isError
    text = _text(result)
    assert "[AVISO]" not in text
    assert get_default_store().is_live_stale() is False


@pytest.mark.unit
async def test_sch_read_immune_to_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Las lecturas de DISCO (sch) no se bloquean ni llevan aviso (D-14.1)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    get_default_store().mark_live_stale(7)
    # sch de disco mínimo válido para el state_builder no aplica: fake el builder.
    from kicad_mcp.toon.schema import NormalizedState

    monkeypatch.setattr(
        "kicad_mcp.tools.world.build_state_cached",
        lambda schematic, snap: (NormalizedState(kind="sch", snap=snap, components=()), False),
    )
    mcp = _server(_FakeBridge())

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("get_world_context", {"kind": "sch"})

    assert not result.isError
    assert "[AVISO]" not in _text(result)


# --- Bloque 2: tool route_board ----------------------------------------------


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
    """Faketea run_drc (secuencia pre/post) y run_autoroute. Registra llamadas."""
    calls: dict[str, Any] = {"drc": 0, "autoroute_args": None}

    def _fake_drc(pcb_path: Path) -> RulesReport:
        report = drc_sequence[min(calls["drc"], len(drc_sequence) - 1)]
        calls["drc"] += 1
        return report

    def _fake_autoroute(src: Path, workdir: Path, **kw: Any) -> AutorouteResult:
        calls["autoroute_args"] = {"src": src, "workdir": workdir, **kw}
        if isinstance(result, Exception):
            raise result
        # Materializa el routed board para que os.replace funcione.
        routed = Path(result.routed_pcb)
        routed.parent.mkdir(parents=True, exist_ok=True)
        routed.write_text("(kicad_pcb routed)")
        return result

    monkeypatch.setattr(pcb_module, "run_drc", _fake_drc)
    monkeypatch.setattr(pcb_module, "run_autoroute", _fake_autoroute)
    return calls


def _result(
    workdir: Path,
    *,
    ruteables: int = 64,
    routed: int = 64,
    blocked: int = 0,
) -> AutorouteResult:
    """AutorouteResult fake con N nets ruteables de 2 pines c/u; ``routed``
    de ellas con 1 wire (ruteadas), el resto (``ruteables - routed``, hasta
    ``blocked``) con 0 wires (bloqueadas) — el resto queda sin entrada en
    ``nets_wire_counts`` (mismo caso: 0 wires, bloqueada)."""
    pin_counts = {f"NET{i}": 2 for i in range(ruteables)}
    wire_counts = {f"NET{i}": 1 for i in range(routed)}
    return AutorouteResult(
        tracks_before=0,
        tracks_after=318,
        vias_before=0,
        vias_after=26,
        export_ms=20.0,
        route_ms=101800.0,
        import_ms=15.0,
        routed_pcb=str(workdir / ".kicad-mcp" / "autoroute" / "routed.kicad_pcb"),
        freerouting_log=str(workdir / "log"),
        nets_pin_counts=pin_counts,
        nets_wire_counts=wire_counts,
        dsn_path=str(workdir / ".kicad-mcp" / "autoroute" / "route.dsn"),
        ses_path=str(workdir / ".kicad-mcp" / "autoroute" / "route.ses"),
    )


@pytest.mark.unit
async def test_route_board_confirm_flag_and_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    calls = _patch_pipeline(
        monkeypatch,
        drc_sequence=[_drc(64), _drc(0, errors=0)],
        result=_result(project),
    )
    bridge = _FakeBridge(open_board_path=str(project / "proj.kicad_pcb"))
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert not result.isError
    payload = _json(result)
    # P2.2: JSON estructurado — route_ms (F-08), denominador de nets desde
    # el .dsn/.ses (F-09, no del DRC), DRC pre/post + por_tipo, session paths.
    assert payload["route_ms"] == 101800.0
    assert payload["nets"] == {
        "total": 64,
        "ruteables": 64,
        "ruteadas": 64,
        "parciales": [],
        "bloqueadas": [],
    }
    assert payload["drc"] == {
        "err_preexistentes": 0,
        "err_post": 0,
        "err_introducidos": 0,
        "por_tipo": {},
    }
    assert payload["tracks_added"] == 318
    assert payload["vias_added"] == 26
    assert isinstance(payload["snap"], int)
    assert payload["session_dsn"].endswith("route.dsn")
    assert payload["session_ses"].endswith("route.ses")
    # Flag activo tras el ruteo.
    assert get_default_store().is_live_stale() is True
    # save_board implícito corrió (board abierto == target).
    assert bridge.saved == [str(project / "proj.kicad_pcb")]
    # El .kicad_pcb fue reemplazado por el ruteado.
    assert (project / "proj.kicad_pcb").read_text() == "(kicad_pcb routed)"
    assert calls["drc"] == 2


@pytest.mark.unit
async def test_route_board_reports_blocked_nets_with_cause(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """F-12: net bloqueada (0 wires) reporta causa honesta, code
    ROUTE_NET_BLOCKED — sin A* de bloqueador concreto (decisión de sesión 17)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(
        monkeypatch,
        drc_sequence=[_drc(3), _drc(0)],
        result=_result(project, ruteables=3, routed=2),  # NET2 queda con 0 wires
    )
    bridge = _FakeBridge(open_board_path=str(project / "proj.kicad_pcb"))
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert not result.isError
    payload = _json(result)
    assert payload["nets"]["ruteables"] == 3
    assert payload["nets"]["ruteadas"] == 2
    assert payload["nets"]["bloqueadas"] == [
        {
            "net": "NET2",
            "code": "ROUTE_NET_BLOCKED",
            "causa": "sin camino aparente; revisar manualmente",
        }
    ]


@pytest.mark.unit
async def test_route_board_reports_drc_error_breakdown_by_type(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """P2.1/gate de sesión 17: el desglose por_tipo debe permitir verificar
    "0 violaciones sistemáticas de copper_edge_clearance" sin parsear texto."""
    from kicad_mcp.bridge.rules import RulesReport, Violation

    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    post_drc = RulesReport(
        violations=(
            Violation(rule="copper_edge_clearance", severity="error", message="e", items=()),
            Violation(rule="copper_edge_clearance", severity="error", message="e", items=()),
            Violation(rule="silk_overlap", severity="warning", message="w", items=()),
        ),
        counts={"error": 2, "warning": 1},
        coordinate_units="mm",
        kicad_version="10.0.4",
        unconnected=0,
    )
    _patch_pipeline(
        monkeypatch,
        drc_sequence=[_drc(2), post_drc],
        result=_result(project, ruteables=2, routed=2),
    )
    bridge = _FakeBridge(open_board_path=str(project / "proj.kicad_pcb"))
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert not result.isError
    payload = _json(result)
    assert payload["drc"]["err_post"] == 2
    assert payload["drc"]["err_introducidos"] == 2  # pre_err=0 (drc_sequence[0])
    assert payload["drc"]["por_tipo"] == {"copper_edge_clearance": 2}  # warnings no cuentan acá


@pytest.mark.unit
async def test_route_board_skips_save_cross_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(
        monkeypatch,
        drc_sequence=[_drc(10), _drc(0)],
        result=_result(project, ruteables=10, routed=10),
    )
    # El board abierto es OTRO proyecto → no se debe guardar.
    bridge = _FakeBridge(open_board_path="/tmp/otro-proyecto/otro.kicad_pcb")
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert not result.isError
    payload = _json(result)
    assert payload["nets"]["total"] == 10
    assert bridge.saved == []  # no se tocó el board vivo de otro proyecto
    assert get_default_store().is_live_stale() is True


@pytest.mark.unit
async def test_route_board_works_without_kicad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(
        monkeypatch,
        drc_sequence=[_drc(5), _drc(0)],
        result=_result(project, ruteables=5, routed=5),
    )
    bridge = _FakeBridge(raise_not_running=True)  # KiCad cerrado
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert not result.isError
    payload = _json(result)
    assert payload["nets"]["total"] == 5
    assert payload["nets"]["ruteadas"] == 5
    assert bridge.saved == []


@pytest.mark.unit
async def test_route_board_propagates_error_without_setting_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from kicad_mcp.errors import KicadMcpError

    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    _patch_pipeline(
        monkeypatch,
        drc_sequence=[_drc(64)],
        result=KicadMcpError(
            code=ErrorCode.KICAD_CLI_MISSING,
            message="jar ausente",
            hint="seteá KICAD_MCP_FREEROUTING_JAR",
        ),
    )
    bridge = _FakeBridge(open_board_path=str(project / "proj.kicad_pcb"))
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert result.isError
    assert "KICAD_CLI_MISSING" in _text(result)
    # El pipeline abortó antes de tocar el flag y sin pisar el .kicad_pcb.
    assert get_default_store().is_live_stale() is False
    assert (project / "proj.kicad_pcb").read_text() == "(kicad_pcb original)"
