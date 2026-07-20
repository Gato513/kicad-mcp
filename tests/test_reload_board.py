"""Tests unit de la tool ``reload_board_from_disk`` (P3.1, sesión 18, D-V3.1).

Estrategia idéntica a ``test_pcb_session11.py``: fake bridge en memoria, sin
socket ni kipy. Cubre:

- Camino feliz: registra snapshot de DISCO (mtimes frescos, no ``None``),
  limpia el flag ``live_stale``, devuelve el JSON del contrato.
- Idempotencia a nivel tool: llamarla dos veces seguidas no falla.
- Sin board abierto → ``RELOAD_FAILED`` (no el genérico ``PROJECT_NOT_FOUND``
  que usan las demás tools de ``pcb``).
- Otros fallos IPC (busy) propagan su código propio, sin reenvolver.
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

from kicad_mcp.bridge.ipc import BoardHandle, IpcBridge
from kicad_mcp.errors import ErrorCode, KicadMcpError
from kicad_mcp.gates import g1
from kicad_mcp.snapshots import get_default_store
from kicad_mcp.tools.pcb import register as register_pcb


class _FakeBridge(IpcBridge):
    """Fake en memoria para ``reload_board_from_disk``."""

    def __init__(
        self,
        *,
        has_board: bool = True,
        reload_error: KicadMcpError | None = None,
        n_tracks: int = 5,
        n_vias: int = 2,
    ) -> None:
        self._client = None  # type: ignore[assignment]
        self._instance_token = None
        self._lock = threading.Lock()
        self._has_board = has_board
        self._reload_error = reload_error
        self._n_tracks = n_tracks
        self._n_vias = n_vias
        self.reload_calls = 0

    def get_open_board(self) -> BoardHandle | None:
        return BoardHandle(_raw=object()) if self._has_board else None

    def snapshot_footprints(self, board: BoardHandle) -> tuple[Any, ...]:  # type: ignore[override]
        return ()

    def reload_board_from_disk(self, board: BoardHandle) -> tuple[int, int]:  # type: ignore[override]
        self.reload_calls += 1
        if self._reload_error is not None:
            raise self._reload_error
        return (self._n_tracks, self._n_vias)


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "proj.kicad_sch").write_text("(kicad_sch)")
    (project / "proj.kicad_pcb").write_text("(kicad_pcb)")
    return project


def _make_server(bridge: IpcBridge) -> FastMCP:
    mcp = FastMCP(name="test-reload", instructions="test")
    register_pcb(mcp, ipc_bridge=bridge)
    return mcp


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


@pytest.mark.unit
async def test_reload_happy_registers_disk_snapshot_and_clears_live_stale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    get_default_store().mark_live_stale(1)  # simula el estado post-route_board
    bridge = _FakeBridge(n_tracks=42, n_vias=7)
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("reload_board_from_disk", {})

    assert not result.isError, _text(result)
    payload = _json(result)
    assert payload["reloaded"] is True
    assert payload["tracks"] == 42
    assert payload["vias"] == 7
    assert isinstance(payload["snap_id"], int)
    assert bridge.reload_calls == 1

    # D-14.1: el flag se destraba — es exactamente lo que esta tool reemplaza
    # (File→Revert manual).
    assert get_default_store().is_live_stale() is False

    # Snapshot de DISCO: mtimes frescos (no None, que es el patrón vivo) —
    # mismo contrato que save_board (vivo == disco tras la recarga).
    entry = get_default_store().get(payload["snap_id"])
    assert entry is not None
    assert entry.mtimes is not None, "reload_board_from_disk debe registrar snapshot de disco"

    audit = project / ".kicad-mcp" / "audit.jsonl"
    entries = [json.loads(x) for x in audit.read_text().splitlines()]
    accepted = [e for e in entries if e["tool"] == "reload_board_from_disk" and "result" in e]
    assert len(accepted) == 1


@pytest.mark.unit
async def test_reload_is_idempotent_at_tool_level(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Llamarla dos veces seguidas no falla (contrato P3.1)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge()
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        first = await client.call_tool("reload_board_from_disk", {})
        second = await client.call_tool("reload_board_from_disk", {})

    assert not first.isError
    assert not second.isError
    assert bridge.reload_calls == 2


@pytest.mark.unit
async def test_reload_no_board_open_raises_reload_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sin PCB Editor abierto → RELOAD_FAILED (no el PROJECT_NOT_FOUND genérico)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    bridge = _FakeBridge(has_board=False)
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("reload_board_from_disk", {})

    assert result.isError
    text = _text(result)
    assert "RELOAD_FAILED" in text
    assert "File" in text or "Revert" in text  # hint accionable
    assert bridge.reload_calls == 0


@pytest.mark.unit
async def test_reload_busy_propagates_without_rewrapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Un fallo IPC ya tipado (busy) NO se reenvuelve en RELOAD_FAILED — ya
    trae su propia taxonomía accionable (KICAD_CLI_FAILED/data.ipc_status)."""
    project = _make_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    busy = KicadMcpError(
        code=ErrorCode.KICAD_CLI_FAILED,
        message="KiCad está ocupado durante reload_board_from_disk.",
        hint="reintentá en unos segundos.",
        data={"ipc_status": "busy"},
    )
    bridge = _FakeBridge(reload_error=busy)
    mcp = _make_server(bridge)

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("reload_board_from_disk", {})

    assert result.isError
    text = _text(result)
    assert "KICAD_CLI_FAILED" in text
    assert "RELOAD_FAILED" not in text
    # El flag no se toca en un fallo (el tool no llegó a limpiar nada).
    assert get_default_store().is_live_stale() is False
