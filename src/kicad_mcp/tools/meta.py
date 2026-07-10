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
    """Snapshot fino del IPC para ``health`` (sesión 07 D-07.3).

    Tres niveles independientes con estados discriminables:

    - ``socket``: ``"ok"`` si el fichero del socket existe; ``"missing"``
      si no. Fast-fail heredado de sesión 04.
    - ``ipc_responde``: ``"ok"`` si ``get_version()`` responde;
      ``"error"`` si el bridge levanta ``KicadMcpError``; ``"unknown"``
      si el nivel superior (socket) ya falló y no lo evaluamos.
    - ``pcb_editor_abierto``: ``"yes"`` si ``get_open_documents(DOCTYPE_PCB)``
      es no-vacío; ``"no"`` si es vacío o KiCad respondió ``AS_UNHANDLED``
      (project manager sin PCB Editor); ``"unknown"`` si niveles
      superiores no lo permiten evaluar.

    Distinguir ``"no"`` (KiCad respondió "no hay PCB Editor") de
    ``"unknown"`` (no pude preguntar) evita el falso engañoso que un
    ``bool`` produciría.

    NO se prueba busy: detectar busy cuesta un ``get_items`` real (~3 s
    en el board de prueba) — demasiado caro para health. El busy es
    transitorio y se surfacea por operación vía ``_map_ipc_failure``
    (D-07.2).

    El ``status`` de nivel superior mantiene el contrato viejo
    (``"ok"``/``"missing"``/``"error"``) para no romper consumidores que
    ya lo miran; los tres niveles finos son aditivos.
    """
    payload: dict[str, Any] = {}

    # Nivel 1 — socket.
    if not bridge.socket_present():
        payload["socket"] = "missing"
        payload["ipc_responde"] = "unknown"
        payload["pcb_editor_abierto"] = "unknown"
        payload["status"] = "missing"
        payload["code"] = ErrorCode.KICAD_NOT_RUNNING.value
        payload["hint"] = (
            "Abrí KiCad y habilitá el API server en Preferences → Plugins → Enable API server."
        )
        return payload
    payload["socket"] = "ok"

    # Nivel 2 — get_version.
    try:
        v = bridge.get_version()
    except KicadMcpError as exc:
        payload["ipc_responde"] = "error"
        payload["pcb_editor_abierto"] = "unknown"
        payload["status"] = "missing" if exc.code is ErrorCode.KICAD_NOT_RUNNING else "error"
        payload["code"] = exc.code.value
        payload["message"] = exc.message
        payload["hint"] = exc.hint
        return payload
    payload["ipc_responde"] = "ok"
    payload["version"] = v.full

    # Nivel 3 — PCB Editor abierto.
    try:
        pcb_open = bridge.has_open_pcb()
    except KicadMcpError as exc:
        # ipc_responde=ok es la señal fuerte; el nivel 3 se degrada a
        # unknown sin invalidar el resto. Ejemplo: busy tras retry aquí.
        payload["pcb_editor_abierto"] = "unknown"
        payload["pcb_probe_error"] = exc.code.value
    else:
        payload["pcb_editor_abierto"] = "yes" if pcb_open else "no"

    payload["status"] = "ok"
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
