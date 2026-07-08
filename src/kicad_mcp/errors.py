"""Taxonomía de errores del servidor (contrato — frontera F3).

Los códigos son literales exactos de `docs/specs/tool-catalog.md §Taxonomía`.
Los renombrados están prohibidos: son API pública consumida por otro LLM en
runtime. Añadir códigos nuevos requiere actualizar el catálogo en el mismo
commit (Definition of Done #2).

Toda respuesta de error tiene forma ``{code, message, hint}`` donde ``hint``
es accionable (p. ej. "nets similares: 3V3, 3V3_MCU"), nunca decorativo.
Un error jamás incluye tracebacks, rutas absolutas del sistema ni texto sin
sanear proveniente del proyecto.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Códigos de error del catálogo (F3). SCREAMING_SNAKE en inglés."""

    KICAD_NOT_RUNNING = "KICAD_NOT_RUNNING"
    KICAD_TIMEOUT = "KICAD_TIMEOUT"
    KICAD_RESTARTED = "KICAD_RESTARTED"
    KICAD_CLI_MISSING = "KICAD_CLI_MISSING"
    KICAD_CLI_FAILED = "KICAD_CLI_FAILED"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    COMPONENT_NOT_FOUND = "COMPONENT_NOT_FOUND"
    NET_NOT_FOUND = "NET_NOT_FOUND"
    SNAPSHOT_STALE = "SNAPSHOT_STALE"
    EXTERNAL_EDIT_DETECTED = "EXTERNAL_EDIT_DETECTED"
    CONTEXT_BUDGET_IMPOSSIBLE = "CONTEXT_BUDGET_IMPOSSIBLE"
    UNSUPPORTED_HIERARCHY = "UNSUPPORTED_HIERARCHY"
    EXPORT_BLOCKED_BY_DRC = "EXPORT_BLOCKED_BY_DRC"
    GATE_DENIED = "GATE_DENIED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    INVALID_PARAMS = "INVALID_PARAMS"
    PATH_OUTSIDE_PROJECT = "PATH_OUTSIDE_PROJECT"


class KicadMcpError(Exception):
    """Excepción base. Se serializa a ``{code, message, hint}`` para el agente."""

    def __init__(self, code: ErrorCode, message: str, hint: str) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        super().__init__(f"[{code.value}] {message}")

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": self.message, "hint": self.hint}
