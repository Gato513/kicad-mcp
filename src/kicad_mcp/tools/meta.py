"""Tools de la categoría ``meta``: ``health`` (MVP), ``discover_tools`` (futuro).

Ver `docs/specs/tool-catalog.md` §meta.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import __version__
from ..bridge.ipc import IpcBridge
from ..bridge.kicad_cli import KicadCliStatus, probe_version
from ..errors import ErrorCode, KicadMcpError
from ..logging_config import estimate_tokens, log_tool_call, tool_call_timer

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _resolve_project_root() -> Path | None:
    """Devuelve la raíz del proyecto activo o ``None``.

    MVP: se toma de la env var ``KICAD_MCP_PROJECT`` si existe y apunta a un
    directorio; en fases futuras vendrá del cliente MCP (roots).
    """
    raw = os.environ.get("KICAD_MCP_PROJECT")
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_dir() else None


def _cli_payload(status: KicadCliStatus) -> dict[str, Any]:
    if status.available:
        return {"status": "ok", "version": status.version}
    # No level a KicadMcpError: `health` reporta subsistemas, no falla.
    return {
        "status": "missing",
        "code": "KICAD_CLI_MISSING",
        "message": "kicad-cli no está disponible.",
        "hint": "Instala KiCad ≥ 9.0 o exporta PATH con kicad-cli.",
        "error": status.error,
    }


def _project_payload(root: Path | None) -> dict[str, Any]:
    if root is None:
        return {
            "status": "not_configured",
            "code": "PROJECT_NOT_FOUND",
            "hint": "Exporta KICAD_MCP_PROJECT con la ruta del proyecto activo.",
        }
    return {"status": "ok", "name": root.name}


def _ipc_payload(bridge: IpcBridge) -> dict[str, Any]:
    """Snapshot del IPC para ``health``.

    Deliberadamente breve: solo estado y versión. Un fallo del bridge
    (KICAD_NOT_RUNNING, timeout) se reporta como subsistema sin
    interrumpir el resto del ``health`` — igual criterio que
    ``kicad-cli``.
    """
    try:
        v = bridge.get_version()
        return {"status": "ok", "version": v.full}
    except KicadMcpError as exc:
        payload: dict[str, Any] = {
            "status": "missing" if exc.code is ErrorCode.KICAD_NOT_RUNNING else "error",
            "code": exc.code.value,
            "message": exc.message,
            "hint": exc.hint,
        }
        return payload


def register(mcp: FastMCP, *, ipc_bridge: IpcBridge | None = None) -> None:
    """Registra las tools ``meta`` en la instancia FastMCP.

    ``ipc_bridge`` es inyectado desde ``register_all`` como singleton por
    proceso (sesión 04). Si es ``None`` — camino defensivo para llamadas
    directas — se instancia local; los tests pasan un fake.
    """

    bridge = ipc_bridge or IpcBridge()

    @mcp.tool(
        name="health",
        description="Estado del servidor, KiCad, kicad-cli y proyecto activo",
    )
    def health() -> dict[str, Any]:
        with tool_call_timer() as timer:
            cli_status = probe_version()
            project_root = _resolve_project_root()
            payload: dict[str, Any] = {
                "server": {"status": "ok", "version": __version__},
                "kicad_cli": _cli_payload(cli_status),
                "kicad_ipc": _ipc_payload(bridge),
                "project": _project_payload(project_root),
            }
        log_tool_call(
            tool_name="health",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
        )
        return payload
