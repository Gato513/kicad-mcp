"""Punto de entrada del servidor MCP por stdio.

Arquitectura §3.2 (Tool Router) + §4.1. Usa ``FastMCP`` del SDK oficial
(``mcp``). Registra las tools del MVP (`meta`) y arranca por stdio.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .tools import register_all


def create_server() -> FastMCP:
    """Fabrica una instancia lista con todas las tools del MVP registradas."""
    mcp = FastMCP(
        name="kicad-mcp",
        instructions=(
            "Servidor MCP de KiCad (MVP solo-lectura). Contexto en formato "
            "TOON v1. Errores tipados con {code, message, hint}."
        ),
    )
    register_all(mcp)
    return mcp


def main() -> None:
    """Entry-point declarado en ``pyproject.toml`` (``kicad-mcp``)."""
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
