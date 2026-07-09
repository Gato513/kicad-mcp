"""Gate G1 — checkpoint de seguridad antes de la primera mutación.

Contrato F2 / ADR-0003: en la PRIMERA mutación de la sesión del server
(por proyecto), G1 copia ``.kicad_sch`` y ``.kicad_pcb`` a
``<project>/.kicad-mcp/backups/<timestamp>/``. Si el proyecto es un
repo git, además ejecuta ``git add -A && git commit`` con mensaje
``checkpoint: pre-mutación kicad-mcp`` (solo dentro del proyecto,
NUNCA push).

Si el backup falla, la mutación NO procede: el hint indica qué falló.
El estado del gate por proyecto se mantiene en memoria del proceso;
se resetea entre reinicios del server (lo cual es lo correcto: cada
sesión merece su checkpoint fresco).
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from ..errors import ErrorCode, KicadMcpError

_BACKUP_DIR: Final = ".kicad-mcp/backups"
_CHECKPOINT_MESSAGE: Final = "checkpoint: pre-mutación kicad-mcp"

_done_by_project: dict[str, str] = {}
"""Proyectos que ya pasaron G1 en esta sesión → timestamp del backup."""


def _copy_docs(project_root: Path, dst: Path) -> list[str]:
    """Copia ``.kicad_sch`` y ``.kicad_pcb`` presentes en la raíz al backup.

    Devuelve la lista de nombres copiados. NO recurre a subdirectorios
    (jerárquicos: ADR-fuera-de-alcance en el MVP).
    """
    dst.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for pattern in ("*.kicad_sch", "*.kicad_pcb"):
        for src in project_root.glob(pattern):
            if src.is_file():
                shutil.copy2(src, dst / src.name)
                copied.append(src.name)
    return copied


def _try_git_checkpoint(project_root: Path) -> bool:
    """Si ``project_root/.git`` existe: ``git add -A && git commit``.

    Devuelve ``True`` si se hizo commit, ``False`` si no había git repo
    o no había cambios que commitear. Los errores del subprocess se
    propagan como excepciones (no se silencian).
    """
    if not (project_root / ".git").exists():
        return False
    subprocess.run(
        ["git", "-C", str(project_root), "add", "-A"],
        check=True,
        capture_output=True,
    )
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(project_root),
            "commit",
            "-m",
            _CHECKPOINT_MESSAGE,
            "--allow-empty",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    # returncode != 0 con "nothing to commit" es normal (si no hay cambios).
    if completed.returncode != 0 and "nothing to commit" not in (
        completed.stdout + completed.stderr
    ):
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,  # gen. genérico: no rompemos F3
            message="git commit del checkpoint falló.",
            hint=(completed.stderr or completed.stdout or "returncode nonzero").strip()[:200],
        )
    return True


def ensure_session_backup(project_root: Path) -> dict[str, object]:
    """Ejecuta G1 si no se hizo en esta sesión para ``project_root``.

    Devuelve un dict con la ruta relativa del backup y flag ``git`` si
    se comiteó. Idempotente por proyecto: la segunda llamada devuelve
    ``already_done`` sin volver a copiar.

    Errores del backup NO se silencian: si copiar falla, la mutación
    debe abortar (llamador es responsable).
    """
    key = str(project_root.resolve())
    if key in _done_by_project:
        return {"backup": _done_by_project[key], "already_done": True}

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dst = project_root / _BACKUP_DIR / ts
    copied = _copy_docs(project_root, dst)
    if not copied:
        raise KicadMcpError(
            code=ErrorCode.PROJECT_NOT_FOUND,
            message="G1: no hay .kicad_sch ni .kicad_pcb para respaldar.",
            hint=f"Se buscaron *.kicad_sch/*.kicad_pcb en {project_root.name}/",
        )
    git_committed = _try_git_checkpoint(project_root)
    _done_by_project[key] = str(dst.relative_to(project_root))
    return {
        "backup": str(dst.relative_to(project_root)),
        "files": copied,
        "git": git_committed,
        "already_done": False,
    }


def reset_session_state() -> None:
    """Resetea el gate (solo para tests). NO usar en runtime."""
    _done_by_project.clear()
