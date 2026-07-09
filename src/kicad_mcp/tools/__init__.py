"""Registro de tools MCP, agrupadas por categoría (arquitectura §4.1).

Cargar por categoría en fases futuras (`discover_tools`); en el MVP se
registran las de `meta` (`health`) y quedan reservadas las categorías
`world`, `validate` y `export` (`docs/specs/tool-catalog.md`).

El ``IpcBridge`` es un **singleton por proceso servidor** (arquitectura
§10, sesión 04): una única conexión al socket IPC compartida por todas
las tools que la necesitan (`meta.health`, `pcb.*`). Se inyecta desde
``register_all`` para que los tests puedan pasar un fake sin depender
del socket real.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..bridge.ipc import IpcBridge


def register_all(mcp: FastMCP, *, ipc_bridge: IpcBridge | None = None) -> None:
    """Registra todas las tools del MVP en la instancia FastMCP.

    ``ipc_bridge``: si se pasa, se comparte entre ``meta`` y ``pcb``. Si es
    ``None`` (default en runtime), se instancia una sola vez aquí — nunca
    dos clientes al mismo socket por proceso.
    """
    from ..bridge.ipc import IpcBridge as _IpcBridge
    from .export import register as register_export
    from .meta import register as register_meta
    from .pcb import register as register_pcb
    from .validate import register as register_validate
    from .world import register as register_world

    bridge = ipc_bridge or _IpcBridge()
    register_meta(mcp, ipc_bridge=bridge)
    register_world(mcp)
    register_validate(mcp)
    register_export(mcp)
    register_pcb(mcp, ipc_bridge=bridge)
