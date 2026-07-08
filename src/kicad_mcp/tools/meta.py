"""Tools de la categoría ``meta``: ``health`` (MVP), ``discover_tools`` (futuro).

Ver `docs/specs/tool-catalog.md` §meta.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import __version__
from ..bridge.kicad_cli import KicadCliStatus, probe_version
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


def register(mcp: FastMCP) -> None:
    """Registra las tools ``meta`` en la instancia FastMCP."""

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
                "kicad_ipc": {
                    "status": "not_checked",
                    "note": "Bridge IPC llega en v0.2 (arquitectura §10)",
                },
                "project": _project_payload(project_root),
            }
        log_tool_call(
            tool_name="health",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
        )
        return payload
