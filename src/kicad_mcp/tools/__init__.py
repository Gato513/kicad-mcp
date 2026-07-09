"""Registro de tools MCP, agrupadas por categoría (arquitectura §4.1).

Cargar por categoría en fases futuras (`discover_tools`); en el MVP se
registran las de `meta` (`health`) y quedan reservadas las categorías
`world`, `validate` y `export` (`docs/specs/tool-catalog.md`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_all(mcp: FastMCP) -> None:
    """Registra todas las tools del MVP en la instancia FastMCP."""
    from .export import register as register_export
    from .meta import register as register_meta
    from .pcb import register as register_pcb
    from .validate import register as register_validate
    from .world import register as register_world

    register_meta(mcp)
    register_world(mcp)
    register_validate(mcp)
    register_export(mcp)
    register_pcb(mcp)
