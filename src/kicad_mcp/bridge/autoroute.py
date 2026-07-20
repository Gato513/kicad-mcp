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
import re
import subprocess
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from ..errors import ErrorCode, KicadMcpError
from .rules_reader import load_project_rules

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
    # P2.2 (sesión 17): denominador correcto + estado por net, del .dsn/.ses
    # (ver bloque "Parsers de .dsn/.ses" — reemplaza el ``unconnected`` del
    # DRC, F-09). ``{}`` si el .dsn/.ses no tenían la forma esperada.
    nets_pin_counts: dict[str, int]
    nets_wire_counts: dict[str, int]
    dsn_path: str
    ses_path: str


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


# --- Inyección de edge clearance al DSN (F-11, sesión 17 P2.1) ---------------
#
# Contexto: ``pcbnew.LoadBoard()`` SÍ carga las netclasses del ``.kicad_pro``
# hermano — el ``(class <nombre> <nets...> (rule (width..)(clearance..)))``
# que emite ``ExportSpecctraDSN`` ya refleja los valores reales del proyecto
# (verificado empíricamente sesión 17: exportando ``tests/fixtures/004_real/
# video.kicad_pcb`` el DSN trae ``(class pwr ... (rule (width 250)(clearance
# 200)))`` — 0.25mm/0.2mm, exactos a ``video.kicad_pro``). Esa parte NO
# necesita fix.
#
# Lo que SÍ falta — la causa real de F-11 (Freerouting violó
# ``min_copper_edge_clearance`` en 7 sitios) — es que Freerouting no tiene
# noción de "clearance al borde del board" en absoluto: su matriz de
# clearance sólo conoce los item-class ``TRACE/VIA/PIN/SMD/AREA``
# (``DefaultItemClearanceClasses$ItemClass``, decompilado del jar 2.1.0), y
# ``ExportSpecctraDSN`` nunca asocia el ``(boundary ...)`` a una clase de
# clearance. Mecanismo real (confirmado por bytecode con ``javap`` sobre
# ``Structure.class``/``NetClass.class`` del jar de Freerouting 2.1.0, sesión
# 17 — no está documentado en ningún lado):
#
#   1. ``Structure.read_boundary_scope`` acepta un sub-scope
#      ``(clearance_class "<nombre>")`` DENTRO de ``(boundary ...)``, que
#      guarda el string en ``BoardConstructionInfo.outline_clearance_class_name``.
#   2. Ese nombre viaja tal cual a ``BoardManager.create_board(...)`` (última
#      línea de ``Structure.read_scope``) — es decir, el contorno SÍ puede
#      tener una clearance class asociada, KiCad/pcbnew simplemente nunca la
#      emite.
#   3. ``NetClass.read_scope`` (el parser de ``(class <nombre> <nets...>
#      (rule ...))`` en ``(network ...)``) lee la lista de nets con
#      ``next_string_list()`` sin exigir que sea no vacía — una clase con
#      CERO nets asignados (sólo para registrar su ``(rule (clearance V))``
#      en la matriz) es sintácticamente válida.
#
# Por eso: post-procesamos el ``.dsn`` (texto plano) para (a) declarar
# ``(clearance_class "board_edge")`` dentro de ``(boundary ...)`` y (b)
# agregar una clase ``(class "board_edge" (rule (clearance <edge_um>)))`` sin
# nets en ``(network ...)``. Best-effort: si la forma del DSN no matchea lo
# esperado (versión de pcbnew distinta), se loguea un warning y se sigue sin
# la inyección — nunca rompe el pipeline por esto.

_EDGE_CLEARANCE_CLASS_NAME: Final = "board_edge"
_DSN_MM_TO_UNIT: Final = 1000  # "(unit um)" — 1mm = 1000um, verificado en el DSN real.


class _DsnScopeNotFound(Exception):
    """El scope buscado no está donde se esperaba — activa el fallback best-effort."""


def _find_dsn_scope_span(text: str, keyword: str) -> tuple[int, int]:
    """Índices ``[start, end)`` del scope ``(keyword ...)`` de nivel superior.

    Balanceo de paréntesis consciente de strings entre comillas dobles (el
    DSN declara ``(string_quote ")`` — ese es el carácter de quote real).
    Exige que el token que sigue a ``keyword`` sea whitespace o ``(``, para
    no matchear un keyword más largo por accidente de substring.
    """
    open_token = f"({keyword}"
    start = text.find(open_token)
    while start != -1:
        after = start + len(open_token)
        if after >= len(text) or text[after].isspace() or text[after] in "()":
            break
        start = text.find(open_token, start + 1)
    if start == -1:
        raise _DsnScopeNotFound(f"scope {keyword!r} no encontrado")
    depth = 0
    in_string = False
    i = start
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    raise _DsnScopeNotFound(f"paréntesis desbalanceados buscando el cierre de {keyword!r}")


def _inject_edge_clearance(dsn_path: Path, edge_clearance_mm: float) -> None:
    """Declara el edge clearance del proyecto en el ``.dsn`` (ver bloque arriba).

    Nunca levanta: si el DSN no tiene la forma esperada, loguea un warning y
    deja el archivo intacto (el round-trip sigue con el comportamiento
    implícito de Freerouting, igual que antes de la sesión 17).
    Tolera también un ``.dsn`` ausente (arnés de tests con runner fake que no
    materializa el archivo; en producción ``_run_export_dsn`` ya garantizó su
    existencia si llegamos hasta acá).
    """
    try:
        text = dsn_path.read_text(encoding="utf-8")
        edge_units = round(edge_clearance_mm * _DSN_MM_TO_UNIT)

        _, b_end = _find_dsn_scope_span(text, "boundary")
        boundary_addition = f'\n      (clearance_class "{_EDGE_CLEARANCE_CLASS_NAME}")\n    '
        text = text[: b_end - 1] + boundary_addition + text[b_end - 1 :]

        _, n_end = _find_dsn_scope_span(text, "network")
        class_addition = (
            f'\n    (class "{_EDGE_CLEARANCE_CLASS_NAME}"\n'
            f"      (rule\n"
            f"        (clearance {edge_units})\n"
            f"      )\n"
            f"    )\n  "
        )
        text = text[: n_end - 1] + class_addition + text[n_end - 1 :]

        dsn_path.write_text(text, encoding="utf-8")
    except (_DsnScopeNotFound, OSError) as exc:
        _LOGGER.warning(
            json.dumps(
                {
                    "tool_name": "autoroute_runner",
                    "warning": "edge_clearance_injection_skipped",
                    "reason": str(exc),
                },
                separators=(",", ":"),
                ensure_ascii=False,
            )
        )


# --- Parsers de .dsn/.ses (P2.2, sesión 17: contrato route_board) ------------
#
# Fuentes de verdad para el resultado estructurado de ``route_board``, en vez
# de derivar todo del ``unconnected`` de ``run_drc`` (F-09: ese conteo mezcla
# conexiones de ratsnest de nets multi-pin CON el ruido de las
# ``unconnected-*`` de 1 pad, de ahí el "24/64" engañoso del Dogfooding 2).
#
# ``ruteables`` (denominador correcto): nets con ≥2 pines, leído de la
# sección ``(network (net <nombre> (pins ...)) ...)`` del ``.dsn`` — excluye
# por construcción las nets de 1 pin (no aparecen como ``unconnected-*`` acá,
# aparecen con un solo pin en su lista).
#
# ``ruteadas``/``parciales``/``bloqueadas``: se comparan los pines esperados
# por net (del ``.dsn``) contra los wires que el router efectivamente generó
# por net, leídos de ``(routes (network_out (net <nombre> (wire ...) ...)))``
# en el ``.ses`` de vuelta. Heurística de conteo: una net con N pines
# necesita razonablemente N-1 wires para quedar 100% conectada en una
# topología simple (cadena); 0 wires con N≥2 pines = bloqueada, entre 1 y
# N-2 = parcial. No es un solver de conectividad real (no reconstruye el
# grafo), es la señal más barata que el propio ``.ses`` ya te da gratis.


def _iter_direct_child_scopes(text: str) -> Iterator[tuple[str, int, int]]:
    """``(keyword, start, end)`` de cada scope HIJO DIRECTO ``(keyword ...)``
    en ``text`` (el CONTENIDO ya aislado de un scope padre, sin sus propios
    paréntesis externos) — no baja a nietos. Consciente de strings entre
    comillas dobles, mismo criterio que ``_find_dsn_scope_span``.
    """
    depth = 0
    in_string = False
    child_start: int | None = None
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string:
            if ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "(":
            if depth == 0:
                child_start = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and child_start is not None:
                j = child_start + 1
                k = j
                while k < n and not text[k].isspace() and text[k] not in "()":
                    k += 1
                yield text[j:k], child_start, i + 1
                child_start = None
        i += 1


def _leading_token(text: str) -> tuple[str, int]:
    """``(nombre, offset)`` del primer token de ``text`` — quoted o bare —
    con ``offset`` = cuántos chars de ``text`` ocupó (para poder saltarlo con
    precisión, sin volver a buscarlo por substring en el resto del scope).
    """
    if text.startswith('"'):
        end_q = text.index('"', 1)
        return text[1:end_q], end_q + 1
    m = re.match(r"[^\s()]+", text)
    if m is None:
        return "", 0
    return m.group(0), m.end()


def _scope_own_name(scope_text: str, keyword: str) -> tuple[str, int]:
    """De un scope ``(keyword NOMBRE resto...)`` (con o sin comillas):
    ``(NOMBRE sin comillas, offset ABSOLUTO en scope_text donde termina
    NOMBRE)`` — el offset sirve para aislar ``resto...`` sin volver a buscar
    NOMBRE por substring (nombres cortos podrían matchear en otro lado).
    ``scope_text`` incluye los paréntesis externos.
    """
    inner_start = 1 + len(keyword)
    rest = scope_text[inner_start:].lstrip()
    pad = len(scope_text[inner_start:]) - len(rest)
    name, consumed = _leading_token(rest)
    return name, inner_start + pad + consumed


_PINS_RE: Final = re.compile(r"\(pins([\s\S]*?)\)")


def parse_dsn_net_pin_counts(dsn_text: str) -> dict[str, int]:
    """net → cantidad de pines, desde ``(network (net <nombre> (pins ...)))``.

    Denominador correcto para ``nets.ruteables`` (F-09): un net con 1 solo
    pin queda con ``pin_count=1`` acá — el llamador filtra ``>= 2``.
    """
    try:
        n_start, n_end = _find_dsn_scope_span(dsn_text, "network")
    except _DsnScopeNotFound:
        return {}
    inner = dsn_text[n_start + 1 : n_end - 1]
    counts: dict[str, int] = {}
    for keyword, start, end in _iter_direct_child_scopes(inner):
        if keyword != "net":
            continue
        scope_text = inner[start:end]
        name, _ = _scope_own_name(scope_text, "net")
        pins_match = _PINS_RE.search(scope_text)
        pin_count = len(pins_match.group(1).split()) if pins_match else 0
        counts[name] = pin_count
    return counts


def parse_ses_net_wire_counts(ses_text: str) -> dict[str, int]:
    """net → cantidad de ``(wire ...)`` generados, desde ``(network_out ...)``
    del ``.ses``. Net ausente del dict = 0 wires (net que Freerouting nunca
    tocó — típicamente bloqueada desde el vamos).
    """
    try:
        n_start, n_end = _find_dsn_scope_span(ses_text, "network_out")
    except _DsnScopeNotFound:
        return {}
    inner = ses_text[n_start + 1 : n_end - 1]
    counts: dict[str, int] = {}
    for keyword, start, end in _iter_direct_child_scopes(inner):
        if keyword != "net":
            continue
        scope_text = inner[start:end]
        name, name_end = _scope_own_name(scope_text, "net")
        # scope_text[name_end:-1] = todo lo que sigue al nombre, sin el ')' final.
        wire_count = sum(
            1 for kw, _, _ in _iter_direct_child_scopes(scope_text[name_end:-1]) if kw == "wire"
        )
        counts[name] = wire_count
    return counts


def classify_net_routing(
    pin_counts: dict[str, int], wire_counts: dict[str, int]
) -> tuple[list[str], list[dict[str, str | int]], list[str]]:
    """Clasifica nets ruteables (≥2 pines) en ruteadas/parciales/bloqueadas.

    Heurística documentada (ver bloque de arriba): net con N pines necesita
    aproximadamente N-1 wires para una cadena simple. 0 wires ⇒ bloqueada;
    ``1..N-2`` ⇒ parcial (``faltan`` = conexiones que quedan); ``>=N-1`` ⇒
    ruteada. No reconstruye el grafo de conectividad real.
    """
    routed: list[str] = []
    partial: list[dict[str, str | int]] = []
    blocked: list[str] = []
    for net, pins in pin_counts.items():
        if pins < 2:
            continue
        needed = pins - 1
        wires = wire_counts.get(net, 0)
        if wires <= 0:
            blocked.append(net)
        elif wires < needed:
            partial.append({"net": net, "faltan": needed - wires})
        else:
            routed.append(net)
    return routed, partial, blocked


_FREEROUTING_SETTINGS_CANDIDATES: Final = (
    Path(tempfile.gettempdir()) / "freerouting" / "freerouting.json",
    Path.home() / ".config" / "freerouting" / "freerouting.json",
)


def _ensure_freerouting_headless_config() -> None:
    """Fuerza ``gui.enabled=false`` en la config persistente de Freerouting
    (sesión 17, hallazgo empírico — no documentado por freerouting).

    Con ``gui.enabled=true`` (default de la instalación), el batch mode
    (``-de/-do -host KiCad``) completa el ruteo y lo loguea ("Auto-routing
    was completed"/"Optimization was completed") pero el proceso JVM se
    queda colgado DESPUÉS de eso y nunca escribe el ``.ses`` — el subprocess
    revienta por ``KICAD_TIMEOUT`` aunque Freerouting ya haya terminado
    (reproducido de forma consistente: boards que tardan más de ~1 pasada
    rápida cuelgan; el board sintético de 2 pads, que rutea en <1s, no
    llegaba a exhibirlo). Con ``gui.enabled=false`` el mismo router corre
    limpio de punta a punta y escribe el SES normalmente. Best-effort: si el
    archivo de config no existe en ninguna ubicación candidata o no es JSON
    válido, no se toca nada — el pipeline sigue con el comportamiento que
    tenga instalado (podría volver a colgar; es la config del USUARIO, no
    algo que este server pueda garantizar sin tocar estado fuera del repo).
    """
    for path in _FREEROUTING_SETTINGS_CANDIDATES:
        if not path.is_file():
            continue
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                continue
            gui = config.get("gui")
            if isinstance(gui, dict) and gui.get("enabled") is not False:
                gui["enabled"] = False
                path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            continue


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
    _ensure_freerouting_headless_config()
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
    # Inyección de reglas del proyecto (P2.1, F-11): las netclasses ya viajan
    # solas vía pcbnew.LoadBoard(); el edge clearance no tiene mecanismo
    # nativo en ExportSpecctraDSN, así que se post-procesa el .dsn — ver
    # docstring de ``_inject_edge_clearance``. Cuenta como parte de "producir
    # el DSN ruteable", de ahí que quede dentro de la ventana de ``export_ms``.
    project_rules = load_project_rules(src_pcb)
    _inject_edge_clearance(dsn, project_rules.min_copper_edge_clearance_mm)
    export_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    _run_freerouting(
        run, java_exe, jar, dsn, ses, log_path, max_passes=max_passes, timeout_s=timeout_s
    )
    route_ms = (time.perf_counter() - t1) * 1000

    t2 = time.perf_counter()
    tb, ta, vb, va = _run_import_ses(run, sys_py, src_pcb, ses, routed, _pcbnew_timeout)
    import_ms = (time.perf_counter() - t2) * 1000

    # P2.2: denominador correcto + estado por net (F-09) — best-effort, los
    # parsers ya degradan a {} solos si el .dsn/.ses no tienen la forma
    # esperada (nunca lanzan); acá además toleramos que el archivo ni
    # siquiera exista (arnés de tests con runner fake, igual que
    # ``_inject_edge_clearance``).
    try:
        nets_pin_counts = parse_dsn_net_pin_counts(dsn.read_text(encoding="utf-8"))
    except OSError:
        nets_pin_counts = {}
    try:
        nets_wire_counts = parse_ses_net_wire_counts(ses.read_text(encoding="utf-8"))
    except OSError:
        nets_wire_counts = {}

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
        nets_pin_counts=nets_pin_counts,
        nets_wire_counts=nets_wire_counts,
        dsn_path=str(dsn),
        ses_path=str(ses),
    )
