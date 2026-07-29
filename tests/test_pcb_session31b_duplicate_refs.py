"""Tests de sesión 31b — F-V1-02: refs de footprint duplicados/sin anotar.

Hallazgo de sesión 31 (Validation Suite, ANAVI Dev Mic): 4 mounting holes
comparten el reference designator literal ``"REF**"`` (nunca anotados por
el autor). ``pcbnew.ExportSpecctraDSN`` — que ``route_board`` necesita
para generar el ``.dsn`` de Freerouting — falla enteramente
(``ok=False, size=0``) con refs duplicados en el board, sin importar su
posición. Confirmado quitando 3 de las 4 instancias en una copia de
prueba: la exportación pasó a ``ok=True, size=2.4MB``.

ADR-0013 rechaza un ``delete_footprint`` general (ADR-0010: footprints
siguen detrás de Gate G2, que no existe; un footprint con ref duplicado
es igual de caro de reinstanciar que uno con ref único). La resolución es
**anotar**, no borrar: ``set_footprint_ref(ref, new_ref, kiid=...)``.

Cuatro piezas cubiertas acá:
1. `_find_duplicate_refs` — helper puro, compartido por la tool y el
   pre-check de `route_board`.
2. El pre-check `DUPLICATE_REFS` en `route_board` — falla ANTES del
   subprocess de exportación DSN/Freerouting.
3. La tool `set_footprint_ref` — resolución explícita, nunca a ciegas
   (mismo espíritu que la ambigüedad de `_delete_copper`).
4. Reproducción del fallo real de `pcbnew.ExportSpecctraDSN` (motor real,
   marca `integration`, requiere el python del SISTEMA con pcbnew — NO
   el venv, ver `_resolve_system_python`) contra
   `tests/fixtures/006_pcb_refs_duplicados/`: congela el experimento
   controlado de sesión 31 (quitar/renombrar refs duplicados hace pasar
   la exportación de `ok=False,size=0` a `ok=True`) como test de
   regresión permanente.
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.autoroute import AutorouteResult, _resolve_system_python, _run_export_dsn
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
from kicad_mcp.tools.pcb import _find_duplicate_refs
from kicad_mcp.tools.pcb import register as register_pcb
from kicad_mcp.tools.world import register as register_world
from tests.conftest import mirror_fixture

# --- _find_duplicate_refs: helper puro -----------------------------------


def _fp(ref: str, kiid: str) -> FootprintData:
    return FootprintData(ref=ref, value="V", x_mm=Mm(0.0), y_mm=Mm(0.0), pads=(), kiid=kiid)


@pytest.mark.unit
def test_find_duplicate_refs_none() -> None:
    fps = (_fp("U1", "k1"), _fp("R1", "k2"))
    assert _find_duplicate_refs(fps) == []


@pytest.mark.unit
def test_find_duplicate_refs_one_group() -> None:
    fps = (_fp("REF**", "k1"), _fp("REF**", "k2"), _fp("U1", "k3"))
    assert _find_duplicate_refs(fps) == [("REF**", ["k1", "k2"])]


@pytest.mark.unit
def test_find_duplicate_refs_multiple_groups_sorted_by_ref() -> None:
    fps = (
        _fp("Z1", "k1"),
        _fp("Z1", "k2"),
        _fp("A1", "k3"),
        _fp("A1", "k4"),
        _fp("A1", "k5"),
        _fp("U1", "k6"),
    )
    assert _find_duplicate_refs(fps) == [
        ("A1", ["k3", "k4", "k5"]),
        ("Z1", ["k1", "k2"]),
    ]


@pytest.mark.unit
def test_find_duplicate_refs_preserves_kiid_order() -> None:
    fps = (_fp("REF**", "kA"), _fp("REF**", "kB"), _fp("REF**", "kC"))
    assert _find_duplicate_refs(fps) == [("REF**", ["kA", "kB", "kC"])]


# --- fake bridge compartido: route_board + set_footprint_ref -------------


class _FakeBridge(IpcBridge):
    """Bridge en memoria para route_board / set_footprint_ref, con soporte
    de refs duplicados (kiid único por INDICE, no por ref — a diferencia
    del fake de ``test_route_board.py``, que deriva el kiid del ref y por
    lo tanto no puede representar duplicados)."""

    def __init__(
        self,
        *,
        open_board_path: str | None = None,
        refs: list[str] | None = None,
        n_zones: int = 0,
    ) -> None:
        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._open_board_path = open_board_path
        self._refs = list(refs or ["U1", "R1"])
        self._n_zones = n_zones
        self.saved: list[str] = []
        self.reload_calls = 0
        self.refill_calls = 0
        self.enforce_hole_clearance_calls = 0
        self.set_footprint_ref_calls: list[tuple[str, str]] = []

    def get_open_board(self) -> BoardHandle | None:  # type: ignore[override]
        if self._open_board_path is None:
            return None
        return BoardHandle(_raw=object())

    def get_open_board_path(self, board: BoardHandle) -> Path | None:  # type: ignore[override]
        return Path(self._open_board_path) if self._open_board_path else None

    def save_board(self, board: BoardHandle) -> None:  # type: ignore[override]
        self.saved.append(self._open_board_path or "")

    def reload_board_from_disk(self, board: BoardHandle) -> tuple[int, int]:  # type: ignore[override]
        self.reload_calls += 1
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
                value=f"V{i}",
                x_mm=Mm(float(i)),
                y_mm=Mm(float(i) * 2.0),
                pads=(FootprintPadData(number="1", net_name="GND"),),
                kiid=f"kiid-{i}",
            )
            for i, ref in enumerate(self._refs)
        )
        return BoardContext(
            refs=tuple(self._refs),
            bbox=BBoxMm(Mm(-100), Mm(-100), Mm(100), Mm(100)),
            footprints=fps,
        )

    def set_footprint_ref(self, board: BoardHandle, kiid: str, new_ref: str) -> None:  # type: ignore[override]
        self.set_footprint_ref_calls.append((kiid, new_ref))


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


@pytest.fixture(autouse=True)
def _reset_g1() -> Any:
    g1.reset_session_state()
    yield
    g1.reset_session_state()


@pytest.fixture(autouse=True)
def _reset_store() -> Any:
    get_default_store().reset()
    yield
    get_default_store().reset()


def _server(bridge: IpcBridge) -> FastMCP:
    mcp = FastMCP(name="test", instructions="test")
    register_pcb(mcp, ipc_bridge=bridge)
    register_world(mcp, ipc_bridge=bridge)
    return mcp


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
    """Faketea run_drc/run_autoroute — igual patrón que test_route_board.py.
    ``calls["autoroute_args"]`` queda ``None`` si nunca se invocó: es la
    aserción central de que el pre-check corta ANTES del subprocess."""
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


def _result(workdir: Path) -> AutorouteResult:
    return AutorouteResult(
        tracks_before=0,
        tracks_after=10,
        vias_before=0,
        vias_after=1,
        export_ms=5.0,
        route_ms=100.0,
        import_ms=5.0,
        routed_pcb=str(workdir / ".kicad-mcp" / "autoroute" / "routed.kicad_pcb"),
        freerouting_log=str(workdir / "log"),
        nets_pin_counts={"NET0": 2},
        nets_wire_counts={"NET0": 1},
        dsn_path=str(workdir / ".kicad-mcp" / "autoroute" / "route.dsn"),
        ses_path=str(workdir / ".kicad-mcp" / "autoroute" / "route.ses"),
    )


# --- route_board: pre-check DUPLICATE_REFS --------------------------------


@pytest.mark.unit
async def test_route_board_rejects_duplicate_refs_before_subprocess(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    calls = _patch_pipeline(monkeypatch, drc_sequence=[_drc(0)], result=_result(project))
    bridge = _FakeBridge(
        open_board_path=str(project / "proj.kicad_pcb"),
        refs=["REF**", "REF**", "REF**", "REF**", "U1"],
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert result.isError
    text = _text(result)
    assert "DUPLICATE_REFS" in text
    assert "REF**" in text
    # La aserción de comportamiento real: nunca llegó al subprocess de
    # exportación DSN/Freerouting, ni siquiera al DRC pre-route.
    assert calls["autoroute_args"] is None
    assert calls["drc"] == 0


@pytest.mark.unit
async def test_route_board_unique_refs_unaffected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No regresión: refs únicos, el flujo normal de route_board procede
    sin cambios."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    calls = _patch_pipeline(monkeypatch, drc_sequence=[_drc(0), _drc(0)], result=_result(project))
    bridge = _FakeBridge(open_board_path=str(project / "proj.kicad_pcb"), refs=["U1", "R1", "C1"])
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert not result.isError
    assert calls["autoroute_args"] is not None


@pytest.mark.unit
async def test_route_board_skips_check_when_board_not_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Degradación documentada: sin board vivo, ``pre_footprints`` es
    ``()`` y el pre-check no tiene nada que chequear — mismo criterio
    best-effort que ``zones_existentes``."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    calls = _patch_pipeline(monkeypatch, drc_sequence=[_drc(0), _drc(0)], result=_result(project))
    bridge = _FakeBridge(open_board_path=None, refs=["REF**", "REF**"])
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("route_board", {})

    assert not result.isError
    assert calls["autoroute_args"] is not None


# --- set_footprint_ref: tool --------------------------------------------


@pytest.mark.unit
async def test_set_footprint_ref_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(open_board_path=str(project / "proj.kicad_pcb"), refs=["U1"])
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("set_footprint_ref", {"ref": "REF**", "new_ref": "MH1"})

    assert result.isError
    assert "COMPONENT_NOT_FOUND" in _text(result)
    assert bridge.set_footprint_ref_calls == []


@pytest.mark.unit
async def test_set_footprint_ref_unique_ref_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No puede usarse como delete_footprint disfrazado: un ref único no
    es un caso válido para esta tool (ADR-0013)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(open_board_path=str(project / "proj.kicad_pcb"), refs=["U1", "R1"])
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("set_footprint_ref", {"ref": "U1", "new_ref": "U2"})

    assert result.isError
    assert "INVALID_PARAMS" in _text(result)
    assert bridge.set_footprint_ref_calls == []


@pytest.mark.unit
async def test_set_footprint_ref_ambiguous_without_kiid_lists_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        open_board_path=str(project / "proj.kicad_pcb"), refs=["REF**", "REF**", "REF**", "U1"]
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("set_footprint_ref", {"ref": "REF**", "new_ref": "MH1"})

    assert result.isError
    text = _text(result)
    assert "DUPLICATE_REFS" in text
    # Los 3 kiids candidatos (índices 0,1,2 — REF** es el ref de esas 3
    # primeras instancias) deben estar en el payload de error.
    assert "kiid-0" in text and "kiid-1" in text and "kiid-2" in text
    # Nunca se resolvió a ciegas: sin mutación.
    assert bridge.set_footprint_ref_calls == []
    assert bridge.saved == []


@pytest.mark.unit
async def test_set_footprint_ref_stale_kiid_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(open_board_path=str(project / "proj.kicad_pcb"), refs=["REF**", "REF**"])
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "set_footprint_ref",
            {"ref": "REF**", "new_ref": "MH1", "kiid": "kiid-nonexistent"},
        )

    assert result.isError
    assert "DUPLICATE_REFS" in _text(result)
    assert bridge.set_footprint_ref_calls == []


@pytest.mark.unit
async def test_set_footprint_ref_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(
        open_board_path=str(project / "proj.kicad_pcb"), refs=["REF**", "REF**", "REF**", "REF**"]
    )
    mcp = _server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "set_footprint_ref",
            {"ref": "REF**", "new_ref": "MH1", "kiid": "kiid-0"},
        )

    assert not result.isError
    text = _text(result)
    assert text.startswith("OK set_footprint_ref REF** -> MH1")
    assert "[snap:" in text
    assert bridge.set_footprint_ref_calls == [("kiid-0", "MH1")]
    # Gate G1 disparado.
    assert (project / ".kicad-mcp" / "backups").is_dir()
    # Línea en audit.jsonl.
    audit_path = project / ".kicad-mcp" / "audit.jsonl"
    assert audit_path.exists()
    lines = audit_path.read_text().strip().splitlines()
    assert any(
        json.loads(line).get("tool") == "set_footprint_ref"
        and json.loads(line).get("result", {}).get("snap") is not None
        for line in lines
    )


# --- reproducción real: pcbnew.ExportSpecctraDSN con refs duplicados -----
#
# Motor real (kicad-cli/pcbnew del SISTEMA vía subprocess, NO el venv de
# `uv` — mismo patrón que `run_autoroute`/`_run_export_dsn`). Sin GUI, sin
# socket IPC — 100% offline, mismo espíritu que
# `test_pcb_session30_solder_mask.py`. Congela el experimento controlado
# de sesión 31 como regresión permanente contra F-V1-02.

_FIXTURE_006 = Path(__file__).parent / "fixtures" / "006_pcb_refs_duplicados"

_RENAME_DUPLICATES_SCRIPT = """
import sys
import pcbnew
board = pcbnew.LoadBoard(sys.argv[1])
dups = [fp for fp in board.GetFootprints() if fp.GetReference() == "REF**"]
assert len(dups) == 2, dups
dups[0].SetReference("MH1")
dups[1].SetReference("MH2")
board.Save(sys.argv[1])
"""


@pytest.mark.integration
def test_export_dsn_fails_with_duplicate_refs_and_succeeds_after_rename(
    tmp_path: Path,
) -> None:
    project = tmp_path / "proj"
    mirror_fixture(_FIXTURE_006, project)  # regla de sesión 03: nunca in-place
    pcb_path = project / "dup_refs.kicad_pcb"
    dsn_path = tmp_path / "out.dsn"
    system_python = _resolve_system_python(None)

    # 1. CON refs duplicados: falla enteramente, mismo síntoma que
    #    `route_board` reportaba como `KICAD_CLI_FAILED` opaco antes del
    #    pre-check `DUPLICATE_REFS` (sesión 31, ANAVI Dev Mic).
    with pytest.raises(KicadMcpError) as excinfo:
        _run_export_dsn(subprocess.run, system_python, pcb_path, dsn_path, 60.0)
    assert excinfo.value.code is ErrorCode.KICAD_CLI_FAILED
    assert not dsn_path.exists() or dsn_path.stat().st_size == 0

    # 2. Renombrar los 2 duplicados a refs únicas (equivalente a 2
    #    llamadas a `set_footprint_ref` — acá vía pcbnew directo, sin IPC,
    #    porque este test es 100% offline).
    renamed = subprocess.run(
        [system_python, "-c", _RENAME_DUPLICATES_SCRIPT, str(pcb_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert renamed.returncode == 0, renamed.stderr

    # 3. SIN duplicados: la exportación debe pasar — no debe lanzar.
    _run_export_dsn(subprocess.run, system_python, pcb_path, dsn_path, 60.0)
    assert dsn_path.exists()
    assert dsn_path.stat().st_size > 0
