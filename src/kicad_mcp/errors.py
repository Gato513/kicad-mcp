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
    """Excepción base. Se serializa a ``{code, message, hint, data?}`` para el agente.

    ``data`` es un payload estructurado opcional que enriquece el hint sin
    romper F3 (el código y su semántica siguen intactos). Uso típico: emitir
    el ``base_snap`` que causó un ``SNAPSHOT_STALE`` para que el agente lo
    correlacione con su plan sin parsear el mensaje.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        hint: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.data: dict[str, Any] | None = dict(data) if data else None
        # El texto propaga a través de FastMCP; incluir hint para que el
        # agente reciba la parte accionable sin depender de contenido
        # estructurado (que MVP no expone).
        super().__init__(f"[{code.value}] {message} hint: {hint}")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
            "hint": self.hint,
        }
        if self.data is not None:
            payload["data"] = self.data
        return payload
