"""Audit log JSONL de mutaciones — arquitectura §4.6.

Cada mutación aceptada por el servidor escribe una línea JSON en
``<project_root>/.kicad-mcp/audit.jsonl``. Formato: timestamp UTC,
tool, params (sanitizados), resultado (dict corto) y opcionalmente
``code`` cuando la mutación falló.

Este módulo NO decide errores: solo persiste. La escritura es
best-effort en el sentido de "si el disco falla, el error debe
propagarse" — pero no reintenta ni contiene lógica de dominio.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_AUDIT_DIR = ".kicad-mcp"
_AUDIT_FILE = "audit.jsonl"


def audit_path(project_root: Path) -> Path:
    """Ruta del archivo de audit para ``project_root``. Crea el directorio."""
    directory = project_root / _AUDIT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory / _AUDIT_FILE


def record(
    project_root: Path,
    *,
    tool: str,
    params: dict[str, Any],
    result: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> None:
    """Añade una línea JSONL al audit del proyecto."""
    entry: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool": tool,
        "params": params,
    }
    if result is not None:
        entry["result"] = result
    if error_code is not None:
        entry["error_code"] = error_code
    line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
    path = audit_path(project_root)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
