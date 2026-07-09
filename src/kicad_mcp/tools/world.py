"""Tools de la categoría ``world``: ``get_world_context`` (MVP).

Ver `docs/specs/tool-catalog.md §world`. El MVP implementa
``get_world_context`` cableado al ``state_builder`` (netlist + posiciones)
y al ``encoder`` con presupuesto de tokens y área local.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from ..bridge.state_builder import build_state_cached
from ..errors import ErrorCode, KicadMcpError
from ..logging_config import estimate_tokens, log_tool_call, tool_call_timer
from ..toon.encoder import encode

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _resolve_root_schematic() -> Path:
    """Resuelve el .kicad_sch raíz del proyecto activo.

    MVP: env ``KICAD_MCP_PROJECT`` apunta a la carpeta del proyecto; se
    localiza el ``.kicad_sch`` cuyo nombre coincide con el ``.kicad_pro``
    (o el único ``.kicad_sch`` presente si no hay ``.kicad_pro``).
    """
    raw = os.environ.get("KICAD_MCP_PROJECT")
    if not raw:
        raise KicadMcpError(
            code=ErrorCode.PROJECT_NOT_FOUND,
            message="No hay proyecto activo.",
            hint="Exporta KICAD_MCP_PROJECT con la ruta del proyecto.",
        )
    root = Path(raw).expanduser()
    if not root.is_dir():
        raise KicadMcpError(
            code=ErrorCode.PROJECT_NOT_FOUND,
            message="KICAD_MCP_PROJECT no apunta a un directorio.",
            hint=f"Ruta: {root.name}",
        )
    pro_files = list(root.glob("*.kicad_pro"))
    if pro_files:
        candidate = pro_files[0].with_suffix(".kicad_sch")
        if candidate.is_file():
            return candidate.resolve()
    sch_files = list(root.glob("*.kicad_sch"))
    if len(sch_files) == 1:
        return sch_files[0].resolve()
    raise KicadMcpError(
        code=ErrorCode.PROJECT_NOT_FOUND,
        message=(
            "No se pudo determinar el .kicad_sch raíz "
            f"({len(sch_files)} candidatos en el proyecto)."
        ),
        hint="Renombrar el esquemático para que coincida con el .kicad_pro.",
    )


def register(mcp: FastMCP) -> None:
    """Registra las tools de la categoría ``world``."""

    @mcp.tool(
        name="get_world_context",
        description="Estado del proyecto en TOON v1",
    )
    def get_world_context(
        max_tokens: int = 800,
        focus_ref: str | None = None,
        radius_mm: float | None = None,
    ) -> str:
        # Devuelve el string TOON puro (sin envelope JSON). La cabecera
        # ya lleva ``snap`` y ``kind`` — reintroducir un wrapper añadía
        # ~30 % de tokens sin dato nuevo (medido en sesión 02).
        snap_id = 1  # MVP sin Snapshot Store: siempre 1. v0.3 usará el store.
        with tool_call_timer() as timer:
            schematic = _resolve_root_schematic()
            state, cache_hit = build_state_cached(schematic, snap=snap_id)
            toon = encode(
                state,
                max_tokens=max_tokens,
                focus_ref=focus_ref,
                radius_mm=radius_mm,
            )
        log_tool_call(
            tool_name="get_world_context",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(toon),
            snap_id=snap_id,
            extra={
                "focus_ref": focus_ref,
                "radius_mm": radius_mm,
                "max_tokens": max_tokens,
                "cache_hit": cache_hit,
                "kind": state.kind,
            },
        )
        return toon
