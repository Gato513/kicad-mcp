"""Wrapper mínimo de ``kicad-cli`` para el MVP.

Regla de código #1: subprocess con **lista de argumentos**, timeout,
``shell=False``. Nunca ``shell=True``. Nunca interpolar strings.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Protocol

_DEFAULT_TIMEOUT_S = 5.0
_VERSION_RE = re.compile(r"(?:kicad-cli\s+)?[vV]?(\d+\.\d+\.\d+)")


class _SubprocessRunner(Protocol):
    """Firma mínima de ``subprocess.run`` que necesitamos (para inyectar fakes)."""

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        check: bool,
        shell: bool,
    ) -> subprocess.CompletedProcess[str]: ...


@dataclass(frozen=True)
class KicadCliStatus:
    """Resultado de sondear ``kicad-cli --version``."""

    available: bool
    version: str | None
    raw_output: str | None
    error: str | None


def probe_version(
    executable: str = "kicad-cli",
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    runner: _SubprocessRunner | None = None,
) -> KicadCliStatus:
    """Sondear ``kicad-cli --version``. Nunca lanza; devuelve status tipado.

    ``runner`` es opcional para inyectar un fake en tests unit; si no se pasa,
    se usa ``subprocess.run`` real.
    """
    run: _SubprocessRunner = runner if runner is not None else subprocess.run
    args = [executable, "--version"]
    try:
        completed = run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            shell=False,
        )
    except FileNotFoundError:
        return KicadCliStatus(
            available=False,
            version=None,
            raw_output=None,
            error="kicad-cli no está en PATH",
        )
    except subprocess.TimeoutExpired:
        return KicadCliStatus(
            available=False,
            version=None,
            raw_output=None,
            error=f"timeout tras {timeout_s}s",
        )

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    output = stdout or stderr
    if completed.returncode != 0:
        return KicadCliStatus(
            available=False,
            version=None,
            raw_output=output[:200],
            error=f"returncode={completed.returncode}",
        )

    match = _VERSION_RE.search(output)
    version = match.group(1) if match else None
    return KicadCliStatus(available=True, version=version, raw_output=output[:200], error=None)
