"""Round-trip de autorouting headless (D-14.1..D-14.4, ADR-0011).

Envuelve los TRES subprocesos del ruteo automático, promovidos del spike
D-R11 (``scratchpad/spike-autoroute/``) al estilo del proyecto:

1. **export DSN** — ``pcbnew`` SWIG del python del **SISTEMA** (NO el venv del
   proyecto: ``pcbnew`` lo instala KiCad, no es dependencia de ``pyproject``,
   F5 intacta). Carga el ``.kicad_pcb`` de disco y exporta Specctra DSN con la
   forma de 2 args (headless, sin ``GetBoard()``/GUI).
2. **freerouting** — ``java -jar freerouting.jar -de X.dsn -do X.ses -host
   KiCad`` como subprocess (NO IPC: el router interno de KiCad no está expuesto,
   ver spike §caminos). El único paso caro (~2 min); acotado por ``timeout_s``.
3. **import SES** — ``pcbnew`` del sistema: carga el board, importa el SES y
   ``SaveBoard`` a un archivo ruteado en el workdir (el llamador decide el
   destino final; ``route_board`` lo mueve atómicamente al ``.kicad_pcb``).

**A diferencia del spike**, el export NO dibuja el contorno automáticamente: un
board sin ``Edge.Cuts`` FALLA con hint accionable (``draw_board_outline``) — la
tool de producción no muta el contorno en silencio (D-14.4).

**Invocación exacta de los subprocesos** (documentada por contrato — los
scripts ``pcbnew`` viajan como texto para ``python3 -c`` y así evitar que mypy/
ruff liten código que depende de un módulo ausente en el venv):

    /usr/bin/python3 -c <EXPORT_DSN_SCRIPT> <src.kicad_pcb> <out.dsn>
    java -jar <jar> -de <dsn> -do <ses> -host KiCad [-mp <max_passes>]
    /usr/bin/python3 -c <IMPORT_SES_SCRIPT> <src.kicad_pcb> <in.ses> <out.kicad_pcb>

Errores tipados (D-14.4, F3 — cero códigos nuevos; ver ADR-0011 §mapeo):

    java ausente / jar ausente / pcbnew no importable → KICAD_CLI_MISSING
    export DSN falla (típico: sin Edge.Cuts)          → KICAD_CLI_FAILED
    freerouting exit≠0 / SES vacío                     → KICAD_CLI_FAILED
    freerouting timeout                                → KICAD_TIMEOUT
    import SES falla                                   → KICAD_CLI_FAILED
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from ..errors import ErrorCode, KicadMcpError

_LOGGER = logging.getLogger("kicad_mcp")

# python del SISTEMA (el que trae KiCad con el módulo ``pcbnew`` SWIG). NUNCA el
# venv del proyecto — ``pcbnew`` no está en ``pyproject`` (F5). Overridable para
# entornos donde el binario no viva en la ruta canónica.
_SYSTEM_PYTHON_DEFAULT: Final = "/usr/bin/python3"
_SYSTEM_PYTHON_ENV: Final = "KICAD_MCP_SYSTEM_PYTHON"
_JAVA_EXE_DEFAULT: Final = "java"
_JAR_ENV: Final = "KICAD_MCP_FREEROUTING_JAR"

# Exit codes de los scripts ``pcbnew`` (para distinguir el mapeo de errores).
_EXIT_NO_PCBNEW: Final = 3  # ``import pcbnew`` falló → falta en el python del sistema
_EXIT_NO_OUTLINE: Final = 4  # el board no tiene contorno Edge.Cuts

# Cola del log de freerouting que se adjunta al hint / ``data`` en un fallo.
_LOG_TAIL_CHARS: Final = 600


# --- scripts ``pcbnew`` (python del SISTEMA, vía ``-c``) ----------------------
# Promovidos de ``scratchpad/spike-autoroute/{01_export_dsn,02_import_ses}.py``.
# Emiten una línea machine-readable en stdout y usan exit codes distintivos.

_EXPORT_DSN_SCRIPT: Final = r"""
import sys, os
try:
    import pcbnew
except Exception as e:
    sys.stderr.write("NO_PCBNEW: %s\n" % e)
    sys.exit(3)

src, out = sys.argv[1], sys.argv[2]

def has_outline(board):
    edge = pcbnew.Edge_Cuts
    for d in board.GetDrawings():
        try:
            if d.GetLayer() == edge:
                return True
        except Exception:
            continue
    return False

board = pcbnew.LoadBoard(src)
if not has_outline(board):
    sys.stderr.write("NO_OUTLINE\n")
    sys.exit(4)
ok = pcbnew.ExportSpecctraDSN(board, out)
size = os.path.getsize(out) if os.path.exists(out) else 0
if not (ok and size > 0):
    sys.stderr.write("EXPORT_FAILED ok=%s size=%s\n" % (ok, size))
    sys.exit(1)
sys.stdout.write("EXPORT_OK size=%d\n" % size)
sys.exit(0)
"""

_IMPORT_SES_SCRIPT: Final = r"""
import sys
try:
    import pcbnew
except Exception as e:
    sys.stderr.write("NO_PCBNEW: %s\n" % e)
    sys.exit(3)

board_path, ses, out = sys.argv[1], sys.argv[2], sys.argv[3]

def counts(board):
    t = v = 0
    for x in board.GetTracks():
        if x.Type() == pcbnew.PCB_VIA_T:
            v += 1
        else:
            t += 1
    return t, v

board = pcbnew.LoadBoard(board_path)
tb, vb = counts(board)
ok = pcbnew.ImportSpecctraSES(board, ses)
if not ok:
    sys.stderr.write("IMPORT_FAILED\n")
    sys.exit(1)
ta, va = counts(board)
pcbnew.SaveBoard(out, board)
sys.stdout.write(
    "IMPORT_OK tracks_before=%d tracks_after=%d vias_before=%d vias_after=%d\n"
    % (tb, ta, vb, va)
)
sys.exit(0)
"""


class SubprocessRunner(Protocol):
    """Firma mínima de ``subprocess.run`` (para inyectar fakes en tests)."""

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        check: bool,
    ) -> subprocess.CompletedProcess[str]: ...


@dataclass(frozen=True)
class AutorouteResult:
    """Resultado del round-trip — tipos primitivos afuera del bridge.

    Los conteos ``*_before``/``*_after`` alimentan el confirm de ``route_board``
    (``+318 tracks +26 vias``). Las latencias desglosadas (``*_ms``) son el
    instrumento de medición del RNF2 (el ``route_ms`` domina; export/import son
    <0.1 s combinados).
    """

    tracks_before: int
    tracks_after: int
    vias_before: int
    vias_after: int
    export_ms: float
    route_ms: float
    import_ms: float
    routed_pcb: str
    freerouting_log: str


def _resolve_system_python(system_python: str | None) -> str:
    return system_python or os.environ.get(_SYSTEM_PYTHON_ENV) or _SYSTEM_PYTHON_DEFAULT


def _resolve_jar(jar_path: str | None) -> str:
    """Resuelve el jar de freerouting o levanta ``KICAD_CLI_MISSING`` (D-14.4).

    Fuente: ``jar_path`` explícito o el env ``KICAD_MCP_FREEROUTING_JAR``. El
    env no seteado y la ruta inexistente son el MISMO fallo desde la óptica del
    agente (no hay router disponible) — mismo código, hint distingue la causa.
    """
    candidate = jar_path or os.environ.get(_JAR_ENV)
    if not candidate:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_MISSING,
            message="No hay jar de Freerouting configurado.",
            hint=(
                f"Exportá {_JAR_ENV} con la ruta al freerouting.jar "
                "(release en github.com/freerouting/freerouting/releases)."
            ),
            data={"requirement": "freerouting_jar", "env": _JAR_ENV},
        )
    if not Path(candidate).is_file():
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_MISSING,
            message="El jar de Freerouting no existe en la ruta configurada.",
            hint=f"{_JAR_ENV} apunta a una ruta inexistente; corregila.",
            data={"requirement": "freerouting_jar", "env": _JAR_ENV, "path": candidate},
        )
    return candidate


def _as_str(value: object) -> str:
    """Normaliza stdout/stderr a ``str`` (``TimeoutExpired`` puede traer bytes)."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _tail(text: object, chars: int = _LOG_TAIL_CHARS) -> str:
    return _as_str(text).strip()[-chars:]


def _no_pcbnew_error(stage: str, stderr: str) -> KicadMcpError:
    return KicadMcpError(
        code=ErrorCode.KICAD_CLI_MISSING,
        message=f"El python del sistema no puede importar ``pcbnew`` ({stage}).",
        hint=(
            "El round-trip necesita el ``pcbnew`` que instala KiCad en el python "
            "del SISTEMA; verificá `python3 -c 'import pcbnew'`."
        ),
        data={"requirement": "pcbnew", "detail": _tail(stderr, 200)},
    )


def _run_export_dsn(
    runner: SubprocessRunner,
    system_python: str,
    src_pcb: Path,
    dsn: Path,
    timeout_s: float,
) -> None:
    """Paso 1 — export DSN. Mapea NO_PCBNEW/NO_OUTLINE/fallo genérico (D-14.4)."""
    args = [system_python, "-c", _EXPORT_DSN_SCRIPT, str(src_pcb), str(dsn)]
    try:
        completed = runner(args, capture_output=True, text=True, timeout=timeout_s, check=False)
    except FileNotFoundError as exc:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_MISSING,
            message="El python del sistema no está disponible.",
            hint=f"Configurá {_SYSTEM_PYTHON_ENV} al python del sistema que trae KiCad.",
            data={"requirement": "system_python", "path": system_python},
        ) from exc
    if completed.returncode == _EXIT_NO_PCBNEW:
        raise _no_pcbnew_error("export DSN", completed.stderr)
    if completed.returncode == _EXIT_NO_OUTLINE:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message="El board no tiene contorno Edge.Cuts; no se puede exportar el DSN.",
            hint="Dibujá el contorno con draw_board_outline antes de rutear.",
            data={"stage": "export_dsn", "reason": "no_edge_cuts"},
        )
    if completed.returncode != 0:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message="Falló la exportación del DSN (pcbnew).",
            hint=_tail(completed.stderr, 200) or f"returncode={completed.returncode}",
            data={"stage": "export_dsn"},
        )


def _run_freerouting(
    runner: SubprocessRunner,
    java_exe: str,
    jar: str,
    dsn: Path,
    ses: Path,
    log_path: Path,
    *,
    max_passes: int | None,
    timeout_s: int,
) -> None:
    """Paso 2 — freerouting headless. Mapea java-ausente/timeout/fallo (D-14.4).

    Sigue la lógica del spike: el veredicto de éxito es la PRESENCIA de un SES
    no vacío, no el exit code (freerouting v2 puede devolver ≠0 y aun así
    producir el ruteo). El timeout SÍ es un fallo duro tipado.
    """
    args = [java_exe, "-jar", jar, "-de", str(dsn), "-do", str(ses), "-host", "KiCad"]
    if max_passes is not None:
        args += ["-mp", str(max_passes)]
    try:
        completed = runner(
            args, capture_output=True, text=True, timeout=float(timeout_s), check=False
        )
    except FileNotFoundError as exc:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_MISSING,
            message="Java no está disponible para ejecutar Freerouting.",
            hint="Instalá Java ≥ 17 (en Arch: `sudo pacman -S jre-openjdk`).",
            data={"requirement": "java"},
        ) from exc
    except subprocess.TimeoutExpired as exc:
        log_path.write_text(
            _tail(_as_str(exc.stdout) + _as_str(exc.stderr), 4000), encoding="utf-8"
        )
        raise KicadMcpError(
            code=ErrorCode.KICAD_TIMEOUT,
            message=f"El ruteo con Freerouting excedió {timeout_s} s.",
            hint=(
                "Subí timeout_s, reducí la densidad de la placa, o ruteá por zonas. "
                "El router escala peor con densidad."
            ),
            data={"stage": "freerouting", "timeout_s": timeout_s},
        ) from exc

    log_path.write_text(
        _tail((completed.stdout or "") + (completed.stderr or ""), 4000), encoding="utf-8"
    )
    if not ses.is_file() or ses.stat().st_size == 0:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message="Freerouting no produjo un SES válido.",
            hint=_tail(completed.stdout + completed.stderr) or f"returncode={completed.returncode}",
            data={"stage": "freerouting", "log_tail": _tail(completed.stdout + completed.stderr)},
        )


def _run_import_ses(
    runner: SubprocessRunner,
    system_python: str,
    src_pcb: Path,
    ses: Path,
    routed: Path,
    timeout_s: float,
) -> tuple[int, int, int, int]:
    """Paso 3 — import SES + SaveBoard. Devuelve (tb, ta, vb, va)."""
    args = [system_python, "-c", _IMPORT_SES_SCRIPT, str(src_pcb), str(ses), str(routed)]
    completed = runner(args, capture_output=True, text=True, timeout=timeout_s, check=False)
    if completed.returncode == _EXIT_NO_PCBNEW:
        raise _no_pcbnew_error("import SES", completed.stderr)
    if completed.returncode != 0:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message="Falló la importación del SES ruteado (pcbnew).",
            hint=_tail(completed.stderr, 200) or f"returncode={completed.returncode}",
            data={"stage": "import_ses"},
        )
    return _parse_counts(completed.stdout)


def _parse_counts(stdout: str) -> tuple[int, int, int, int]:
    """Extrae ``tracks_before/after`` y ``vias_before/after`` de la línea IMPORT_OK."""
    fields: dict[str, int] = {}
    for token in stdout.split():
        key, sep, value = token.partition("=")
        if sep and value.lstrip("-").isdigit():
            fields[key] = int(value)
    try:
        return (
            fields["tracks_before"],
            fields["tracks_after"],
            fields["vias_before"],
            fields["vias_after"],
        )
    except KeyError as exc:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message="No se pudo leer el conteo de tracks/vías tras el import.",
            hint="Salida inesperada del paso de import; reportar al humano.",
            data={"stage": "import_ses", "stdout": _tail(stdout, 200)},
        ) from exc


def run_autoroute(
    src_pcb: Path,
    workdir: Path,
    *,
    max_passes: int | None = None,
    timeout_s: int = 600,
    runner: SubprocessRunner | None = None,
    system_python: str | None = None,
    jar_path: str | None = None,
    java_exe: str = _JAVA_EXE_DEFAULT,
) -> AutorouteResult:
    """Ejecuta el round-trip DSN → Freerouting → SES sobre ``src_pcb`` de disco.

    ``src_pcb`` NO se modifica (el export lo lee read-only); el board ruteado se
    escribe en ``workdir/routed.kicad_pcb`` y el llamador decide su destino
    final. Cada fallo se mapea a la taxonomía (D-14.4). El ``pcbnew`` se invoca
    con el python del SISTEMA (nunca el venv). Emite una línea de log JSON con
    ``export_ms``/``route_ms``/``import_ms``.
    """
    run: SubprocessRunner = runner if runner is not None else subprocess.run
    sys_py = _resolve_system_python(system_python)
    jar = _resolve_jar(jar_path)

    workdir.mkdir(parents=True, exist_ok=True)
    dsn = workdir / "route.dsn"
    ses = workdir / "route.ses"
    routed = workdir / "routed.kicad_pcb"
    log_path = workdir / "freerouting.log"

    # Los pasos pcbnew son sub-segundo; les damos un techo generoso pero acotado
    # (no deben colgar). El router usa el ``timeout_s`` completo.
    _pcbnew_timeout = 120.0

    t0 = time.perf_counter()
    _run_export_dsn(run, sys_py, src_pcb, dsn, _pcbnew_timeout)
    export_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    _run_freerouting(
        run, java_exe, jar, dsn, ses, log_path, max_passes=max_passes, timeout_s=timeout_s
    )
    route_ms = (time.perf_counter() - t1) * 1000

    t2 = time.perf_counter()
    tb, ta, vb, va = _run_import_ses(run, sys_py, src_pcb, ses, routed, _pcbnew_timeout)
    import_ms = (time.perf_counter() - t2) * 1000

    _LOGGER.info(
        json.dumps(
            {
                "tool_name": "autoroute_runner",
                "export_ms": round(export_ms, 3),
                "route_ms": round(route_ms, 3),
                "import_ms": round(import_ms, 3),
                "tracks_added": ta - tb,
                "vias_added": va - vb,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )
    return AutorouteResult(
        tracks_before=tb,
        tracks_after=ta,
        vias_before=vb,
        vias_after=va,
        export_ms=export_ms,
        route_ms=route_ms,
        import_ms=import_ms,
        routed_pcb=str(routed),
        freerouting_log=str(log_path),
    )
