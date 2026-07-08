"""Canonicalización de rutas — regla de código #4 de CLAUDE.md.

Mitigación de path traversal: toda ruta de archivo pasa por
``canonicalize_within_project_root()``. Sin excepciones.
"""

from __future__ import annotations

from pathlib import Path

from .errors import ErrorCode, KicadMcpError


def canonicalize_within_project_root(candidate: str | Path, project_root: Path) -> Path:
    """Devuelve la ruta canónica si está dentro de ``project_root``; ``PATH_OUTSIDE_PROJECT`` si no.

    El error nunca revela la ruta canónica del sistema (regla F3 §Taxonomía).
    """
    root = project_root.resolve()
    resolved = (
        (root / candidate).resolve()
        if not Path(candidate).is_absolute()
        else Path(candidate).resolve()
    )
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise KicadMcpError(
            code=ErrorCode.PATH_OUTSIDE_PROJECT,
            message="La ruta solicitada queda fuera de la raíz del proyecto.",
            hint=f"Raíz permitida: {root.name}/",
        ) from exc
    return resolved
