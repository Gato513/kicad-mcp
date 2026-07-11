#!/usr/bin/env python3
"""Verificación del entorno de desarrollo de kicad-mcp (v2).

Ejecutar como Fase 0 de toda sesión de Claude Code:
    python3 scripts/verificar_entorno.py

Detección automática de modo (sin flags manuales):
    unit             → ni socket IPC ni ``KICAD_MCP_GUI_TEST=1``.
    integration      → hay socket o ``kicad-cli`` pero ``KICAD_MCP_GUI_TEST != "1"``.
    integration_gui  → ``KICAD_MCP_GUI_TEST == "1"`` (el humano habilitó GUI).

Cada modo tiene su conjunto de checks. En ``integration_gui`` los checks
de KiCad/GUI son **FAIL** (no WARN): sin ellos la sesión se rompe.

Semántica de estados:
- OK    → listo.
- WARN  → no bloquea el modo actual; puede bloquear fases futuras. Anotar
          en el reporte.
- FAIL  → bloquea. Si la remediación está dentro de los permisos del agente
          (``uv sync``, ``git init``), el agente la ejecuta y re-verifica.
          Si no (instalar KiCad, abrir el PCB Editor, exportar env vars),
          el agente DETIENE las tareas dependientes y entrega al humano
          la instrucción exacta que imprime el script.

Exit code: 0 = listo para el modo detectado (FAILs = 0); 1 = bloqueado.

Restricciones:
- Solo stdlib para los checks de entorno básico. El bloque
  ``integration_gui`` importa perezosamente ``kicad_mcp.bridge.ipc`` (el
  bridge del propio proyecto) para la prueba IPC — si el proyecto no está
  instalado, ese check degrada a WARN con hint de ``uv sync``.
- Cada check IPC usa el timeout de 2 s del bridge; el script termina en
  <15 s en cualquier modo.
- No muta estado del board ni del proyecto: solo lee (``get_version``,
  ``get_open_board``).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

REPO = Path(__file__).resolve().parent.parent
RESULTS: list[tuple[str, str, str, str]] = []  # (estado, check, detalle, remediación)

Mode = Literal["unit", "integration", "integration_gui"]


def add(estado: str, check: str, detalle: str, fix: str = "") -> None:
    RESULTS.append((estado, check, detalle, fix))


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return 127, "", "no encontrado"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


# ------------------------------------------------------------------ modo


def _default_socket_uri() -> str:
    return os.environ.get("KICAD_API_SOCKET") or "ipc:///tmp/kicad/api.sock"


def _socket_fs_path(uri: str) -> Path | None:
    """Devuelve el path filesystem del socket si es un ``ipc://<path>``, si no ``None``."""
    if not uri.startswith("ipc://"):
        return None
    fs = uri[len("ipc://") :]
    return Path(fs) if fs else None


def _socket_present() -> bool:
    p = _socket_fs_path(_default_socket_uri())
    return p is not None and p.exists()


def detect_mode() -> Mode:
    """Detecta el modo de sesión según env vars y presencia de KiCad.

    Prioridad:
    1. ``KICAD_MCP_GUI_TEST == "1"`` → ``integration_gui`` (el humano ya
       autorizó ejercitar el socket).
    2. Hay socket IPC o ``kicad-cli`` en PATH → ``integration``.
    3. Nada de lo anterior → ``unit``.
    """
    if os.environ.get("KICAD_MCP_GUI_TEST") == "1":
        return "integration_gui"
    if _socket_present() or shutil.which("kicad-cli") is not None:
        return "integration"
    return "unit"


# ------------------------------------------------------------------ checks


def check_git_branch() -> None:
    """Imprime la rama actual y WARNea si estás en master con cambios."""
    code, branch, _ = run(["git", "-C", str(REPO), "branch", "--show-current"])
    if code != 0:
        # El status del repo lo cubre check_git; acá solo salimos silenciosos.
        return
    branch = branch or "(detached HEAD)"
    code2, changes, _ = run(["git", "-C", str(REPO), "status", "--porcelain"])
    dirty = bool(changes.strip()) if code2 == 0 else False
    detalle = f"rama actual: {branch}" + (" · con cambios sin commit" if dirty else "")
    if branch == "master" and dirty:
        add(
            "WARN",
            "Rama git",
            detalle,
            "Estás en master con cambios — considerá crear rama de sesión: "
            "`git switch -c sesion/<nombre>` antes de continuar",
        )
    else:
        add("OK", "Rama git", detalle)


def check_python() -> None:
    v = sys.version_info
    if (v.major, v.minor) >= (3, 11):
        add("OK", "Python", f"{v.major}.{v.minor}.{v.micro}")
    else:
        add(
            "FAIL",
            "Python",
            f"{v.major}.{v.minor} < 3.11",
            "Instalar Python 3.11+ (el humano; en Ubuntu: apt install python3.11)",
        )


def check_git() -> None:
    code, out, _ = run(["git", "-C", str(REPO), "rev-parse", "--is-inside-work-tree"])
    if code == 0 and out == "true":
        add("OK", "Repositorio git", "inicializado")
    else:
        add(
            "FAIL",
            "Repositorio git",
            "no inicializado",
            "El agente puede resolverlo: "
            "git init && git add -A && git commit -m 'chore: estado inicial'",
        )


def check_uv() -> None:
    code, out, _ = run(["uv", "--version"])
    if code == 0:
        add("OK", "uv", out)
    else:
        add(
            "FAIL",
            "uv",
            "no está en PATH",
            "El humano: instalar uv → https://docs.astral.sh/uv/getting-started/installation/",
        )


def check_deps() -> None:
    if not (REPO / "pyproject.toml").exists():
        add(
            "FAIL",
            "pyproject.toml",
            "ausente",
            "No debería pasar: está versionado. Verificar clone.",
        )
        return
    code, _, _ = run(["uv", "run", "python", "-c", "import mcp, pydantic"], timeout=120)
    if code == 0:
        add("OK", "Dependencias Python", "mcp + pydantic importables vía uv")
    else:
        add(
            "FAIL",
            "Dependencias Python",
            "entorno sin sincronizar",
            "El agente puede resolverlo: uv sync",
        )


def check_kicad_cli() -> None:
    code, out, _ = run(["kicad-cli", "version"])
    if code != 0:
        add(
            "FAIL",
            "kicad-cli",
            "no está en PATH",
            "El humano: instalar KiCad 10 → https://www.kicad.org/download/ "
            "(en Ubuntu, el PPA oficial de KiCad; el paquete de la distro puede ser viejo)",
        )
        return
    major = int(out.split(".")[0]) if out.split(".")[0].isdigit() else 0
    if major >= 10:
        add("OK", "kicad-cli", f"v{out} (objetivo D2 cumplido)")
    elif major == 9:
        add("OK", "kicad-cli", f"v{out} (mínimo soportado; objetivo es 10)")
    elif major >= 7:
        add(
            "WARN",
            "kicad-cli",
            f"v{out}: sirve para netlist/exports pero SIN ERC por CLI",
            "El humano: actualizar a KiCad 10 antes de la fase de validación ERC",
        )
    else:
        add("FAIL", "kicad-cli", f"v{out} demasiado antigua", "El humano: instalar KiCad 10")


def check_erc() -> None:
    code, _, _ = run(["kicad-cli", "sch", "erc", "--help"])
    if code == 0:
        add("OK", "ERC por CLI", "disponible (KiCad 8+)")
    else:
        add(
            "WARN",
            "ERC por CLI",
            "no disponible en esta versión de kicad-cli",
            "Se resuelve al actualizar a KiCad 10 (ver check kicad-cli)",
        )


def check_pcb_render() -> None:
    """Verifica que ``kicad-cli pcb render`` exista (sesión 09: existía pero
    el catálogo lo negaba)."""
    code, _, _ = run(["kicad-cli", "pcb", "render", "--help"])
    if code == 0:
        add("OK", "kicad-cli pcb render", "subcomando presente en esta versión")
    else:
        add(
            "WARN",
            "kicad-cli pcb render",
            "no disponible en esta versión de kicad-cli",
            "El humano: actualizar a KiCad 10 si vas a usar renders programáticos "
            "(no bloquea el MVP)",
        )


def check_ipc_socket() -> None:
    """Presencia del socket IPC. Mantiene la semántica original: WARN si falta."""
    candidates = []
    if os.environ.get("KICAD_API_SOCKET"):
        env_uri = os.environ["KICAD_API_SOCKET"]
        env_fs = _socket_fs_path(env_uri)
        if env_fs is not None:
            candidates.append(env_fs)
    candidates.append(Path("/tmp/kicad/api.sock"))
    found = next((p for p in candidates if p.exists()), None)
    if found:
        add("OK", "Socket IPC de KiCad", str(found))
    else:
        add(
            "WARN",
            "Socket IPC de KiCad",
            "no visible (KiCad cerrado o API deshabilitado). NO bloquea el MVP solo-lectura; "
            "imprescindible desde v0.2",
            "El humano: abrir KiCad → Preferences → Plugins → Enable API server, "
            "y dejar KiCad abierto durante sesiones que usen IPC",
        )


def check_fixtures() -> None:
    fdir = REPO / "tests" / "fixtures"
    if not (fdir / "validate_fixtures.py").exists():
        add("FAIL", "Fixtures", "validate_fixtures.py ausente", "Verificar clone del repo")
        return
    if shutil.which("kicad-cli") is None:
        add("WARN", "Fixtures", "sin validar (kicad-cli ausente)", "Ver check kicad-cli")
        return
    code, out, err = run(
        [sys.executable, str(fdir / "validate_fixtures.py"), str(fdir)], timeout=120
    )
    if code == 0:
        add("OK", "Fixtures validados", out.replace("\n", " · "))
    else:
        add(
            "FAIL",
            "Fixtures validados",
            (out + " " + err)[:300],
            "Si el fallo es de conectividad de fixtures: reportar al humano, NO editar "
            "ground_truth para hacerlo pasar (frontera F1)",
        )


def check_fixture_004() -> None:
    d = REPO / "tests" / "fixtures" / "004_real"
    if d.exists() and any(d.glob("*.kicad_sch")):
        add("OK", "Fixture 004 (real)", "presente")
    else:
        add(
            "WARN",
            "Fixture 004 (real)",
            "pendiente (tarea del humano)",
            "El humano: ver criterios en docs/specs/fixtures.md §004_real",
        )


def check_settings() -> None:
    p = REPO / ".claude" / "settings.json"
    if not p.exists():
        add(
            "FAIL",
            "Permisos Claude Code",
            ".claude/settings.json ausente",
            "Verificar clone: los permisos son parte del diseño de seguridad",
        )
        return
    try:
        json.loads(p.read_text())
        add("OK", "Permisos Claude Code", "settings.json presente y parseable")
    except json.JSONDecodeError as e:
        add(
            "FAIL",
            "Permisos Claude Code",
            f"settings.json inválido: {e}",
            "Reportar al humano (el agente tiene denegada la edición de .claude/)",
        )


def check_npx() -> None:
    code, out, _ = run(["npx", "--version"])
    if code == 0:
        add("OK", "npx (MCP Inspector)", f"v{out}")
    else:
        add(
            "WARN",
            "npx (MCP Inspector)",
            "no disponible: no habrá Inspector interactivo",
            "El humano: instalar Node.js si quiere usar el Inspector; los tests "
            "con cliente MCP in-process no lo requieren",
        )


# ------------------------------------------------------- checks integration_gui


def check_gui_env_vars() -> None:
    """Env vars requeridas por sesiones ``integration_gui`` (ver docs/pruebas-gui.md)."""
    # KICAD_MCP_GUI_TEST — ya sabemos que es "1" (por eso estamos en este modo).
    add("OK", "env KICAD_MCP_GUI_TEST", "=1 (autoriza ejercitar el socket IPC)")

    proj = os.environ.get("KICAD_MCP_PROJECT")
    if not proj:
        add(
            "FAIL",
            "env KICAD_MCP_PROJECT",
            "no definida — los tests que registran audit/snapshots la exigen",
            "El humano: `export KICAD_MCP_PROJECT=/tmp/gui-test-project`",
        )
    elif not Path(proj).is_dir():
        add(
            "FAIL",
            "env KICAD_MCP_PROJECT",
            f"={proj} pero el directorio no existe",
            "El humano: crear/copiar el proyecto de prueba y re-exportar la variable. "
            "Ver el check 'Proyecto de prueba /tmp/gui-test-project' abajo.",
        )
    else:
        add("OK", "env KICAD_MCP_PROJECT", f"={proj}")

    ref = os.environ.get("KICAD_MCP_GUI_REF")
    if not ref:
        add(
            "WARN",
            "env KICAD_MCP_GUI_REF",
            "no definida — sólo el test round-trip la exige (skip si falta)",
            "El humano: `export KICAD_MCP_GUI_REF=U19` (o cualquier ref existente del board)",
        )
    else:
        add("OK", "env KICAD_MCP_GUI_REF", f"={ref}")

    sock_uri = os.environ.get("KICAD_API_SOCKET")
    if not sock_uri:
        add(
            "FAIL",
            "env KICAD_API_SOCKET",
            "no definida — el bridge caerá al default pero conviene fijarla",
            'El humano: `export KICAD_API_SOCKET="ipc:///tmp/kicad/api.sock"`',
        )
        return
    fs = _socket_fs_path(sock_uri)
    if fs is None:
        add("OK", "env KICAD_API_SOCKET", f"={sock_uri} (esquema no filesystem)")
        return
    if fs.exists():
        add("OK", "env KICAD_API_SOCKET", f"={sock_uri} (socket file presente)")
    else:
        add(
            "FAIL",
            "env KICAD_API_SOCKET",
            f"={sock_uri} pero el path {fs} no existe",
            "El humano: abrir KiCad y verificar Preferences → Plugins → Enable API server",
        )


def _kicad_process_alive() -> bool | None:
    """``True`` si hay un proceso ``kicad`` corriendo; ``None`` si no se puede saber.

    Escanea ``/proc`` en Linux (evita depender de ``psutil``). En sistemas sin
    ``/proc`` o cuando la lectura falla completa, devuelve ``None`` para no
    afirmar algo que no se pudo verificar.
    """
    proc_dir = Path("/proc")
    if not proc_dir.is_dir():
        return None
    scanned_any = False
    for entry in proc_dir.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            comm = (entry / "comm").read_text().strip()
        except OSError:
            continue
        scanned_any = True
        if comm == "kicad":
            return True
    return False if scanned_any else None


def check_socket_alive() -> None:
    """Detecta socket muerto (remanente de una sesión anterior de KiCad).

    Si el path del socket existe pero no hay proceso ``kicad`` vivo, el
    archivo es un remanente y ``connect`` colgará hasta el timeout. FAIL con
    hint de reinicio.
    """
    sock_uri = _default_socket_uri()
    fs = _socket_fs_path(sock_uri)
    if fs is None:
        add(
            "OK",
            "Socket IPC vivo",
            f"esquema no filesystem ({sock_uri}); la liveness se resuelve al conectar",
        )
        return
    if not fs.exists():
        add(
            "FAIL",
            "Socket IPC vivo",
            f"no existe: {fs}",
            "El humano: abrir KiCad → Preferences → Plugins → Enable API server "
            "(y reiniciar KiCad tras el cambio)",
        )
        return
    alive = _kicad_process_alive()
    if alive is True:
        add("OK", "Socket IPC vivo", f"{fs} presente y proceso kicad corriendo")
    elif alive is False:
        add(
            "FAIL",
            "Socket IPC vivo",
            f"{fs} existe pero NO hay proceso kicad — el socket es un remanente muerto",
            "El humano: reiniciar KiCad. Si el socket persiste tras cerrar KiCad, borrarlo "
            f"manualmente: `rm {fs}`",
        )
    else:
        add(
            "WARN",
            "Socket IPC vivo",
            f"{fs} presente; no pude verificar si hay proceso kicad corriendo (sin /proc)",
            "Verificalo a mano: `pgrep -x kicad`",
        )


def _run_ipc_probe(
    op_name: str,
    action: Callable[[Any], tuple[str, str, str, str]],
) -> tuple[str, str, str, str]:
    """Runner común para los probes IPC.

    Importa perezosamente el bridge (regla: solo el propio proyecto además
    de stdlib). Si el proyecto no está instalado degrada a WARN con
    remediación de ``uv sync``. Instancia un ``IpcBridge`` fresco y llama
    ``action(bridge)`` que devuelve el tuple ``(estado, check, detalle, fix)``.

    Traduce ``KicadMcpError`` a mensajes accionables según el código.
    """
    try:
        from kicad_mcp.bridge.ipc import IpcBridge
        from kicad_mcp.errors import ErrorCode, KicadMcpError
    except ImportError as exc:
        return (
            "WARN",
            op_name,
            f"proyecto no instalado ({exc}); el check IPC degrada",
            "El agente puede resolverlo: uv sync",
        )
    try:
        bridge = IpcBridge(timeout_ms=2000)
        return action(bridge)
    except KicadMcpError as e:
        code = e.code
        data = e.data or {}
        ipc_status = data.get("ipc_status") if isinstance(data, dict) else None
        if code is ErrorCode.KICAD_NOT_RUNNING:
            return (
                "FAIL",
                op_name,
                f"KiCad no está corriendo o el API server está deshabilitado: {e.message}",
                "El humano: abrir KiCad y habilitar Preferences → Plugins → Enable API server; "
                "reiniciar KiCad tras el cambio",
            )
        if code is ErrorCode.KICAD_TIMEOUT:
            return (
                "FAIL",
                op_name,
                "IPC excedió el timeout de 2 s",
                "El humano: KiCad puede estar bloqueado por un diálogo modal o una operación "
                "larga (router/DRC). Cerrar el diálogo y reintentar",
            )
        if code is ErrorCode.KICAD_CLI_FAILED and ipc_status == "busy":
            return (
                "WARN",
                op_name,
                "KiCad respondió pero está ocupado con otra operación",
                "El humano: esperar a que termine la operación en curso (router/DRC/refill) "
                "y re-ejecutar el script",
            )
        # AS_UNHANDLED que llega hasta acá es el fallback: el probe específico
        # (check_pcb_editor) ya lo intercepta con hint accionable.
        return (
            "FAIL",
            op_name,
            f"{code}: {e.hint or e.message}",
            "Revisar el estado de KiCad; ver detalle arriba",
        )
    except Exception as e:
        return (
            "FAIL",
            op_name,
            f"excepción no mapeada: {type(e).__name__}: {e}",
            "Reportar al humano: bug potencial del bridge o del script",
        )


def check_ipc_probe() -> None:
    """``get_version`` contra KiCad vía ``IpcBridge`` del proyecto."""

    def _probe(bridge: Any) -> tuple[str, str, str, str]:
        version = bridge.get_version()
        return (
            "OK",
            "IPC probe (get_version)",
            f"KiCad {version.full} (major={version.major})",
            "",
        )

    add(*_run_ipc_probe("IPC probe (get_version)", _probe))


def check_pcb_editor() -> None:
    """``get_open_board`` para verificar que el PCB Editor tiene un board cargado."""

    def _probe(bridge: Any) -> tuple[str, str, str, str]:
        try:
            board = bridge.get_open_board()
        except Exception as exc:
            # El importe perezoso se resolvió (estamos dentro de _run_ipc_probe).
            from kicad_mcp.errors import ErrorCode, KicadMcpError

            if isinstance(exc, KicadMcpError):
                data = exc.data or {}
                ipc_status = data.get("ipc_status") if isinstance(data, dict) else None
                if exc.code is ErrorCode.KICAD_CLI_FAILED and ipc_status == "unhandled":
                    return (
                        "FAIL",
                        "PCB Editor cargado",
                        "KiCad está abierto pero el PCB Editor no tiene ningún board cargado "
                        "(AS_UNHANDLED)",
                        "El humano: en KiCad, File → Open Project… → seleccionar el .kicad_pro; "
                        "o desde el Project Manager, doble-clic sobre el .kicad_pcb",
                    )
            raise
        if board is None:
            return (
                "FAIL",
                "PCB Editor cargado",
                "get_open_board() devolvió None — el PCB Editor no tiene board cargado",
                "El humano: en KiCad, abrir el .kicad_pcb desde el Project Manager (doble-clic)",
            )
        return ("OK", "PCB Editor cargado", "board abierto y accesible por IPC", "")

    add(*_run_ipc_probe("PCB Editor cargado", _probe))


def check_gui_test_project() -> None:
    """``/tmp/gui-test-project`` existe, tiene los archivos KiCad y está actualizado."""
    d = Path("/tmp/gui-test-project")
    fixture = REPO / "tests" / "fixtures" / "004_real"
    recopy_cmd = (
        "rm -rf /tmp/gui-test-project && "
        "cp -r tests/fixtures/004_real /tmp/gui-test-project"
    )
    if not d.is_dir():
        add(
            "FAIL",
            "Proyecto de prueba /tmp/gui-test-project",
            "no existe",
            f"El humano o el agente: `{recopy_cmd}`",
        )
        return
    pcb_files = list(d.glob("*.kicad_pcb"))
    sch_files = list(d.glob("*.kicad_sch"))
    if not pcb_files or not sch_files:
        add(
            "FAIL",
            "Proyecto de prueba /tmp/gui-test-project",
            f"faltan archivos KiCad ({len(pcb_files)} pcb, {len(sch_files)} sch)",
            f"El humano o el agente: `{recopy_cmd}`",
        )
        return
    fixture_pcb = fixture / "video.kicad_pcb"
    if fixture_pcb.exists():
        fx_mtime = fixture_pcb.stat().st_mtime
        tmp_mtime = pcb_files[0].stat().st_mtime
        # Tolerancia de 1 s para evitar warnings por copia reciente.
        if fx_mtime > tmp_mtime + 1:
            add(
                "WARN",
                "Proyecto de prueba /tmp/gui-test-project",
                "fixture 004_real más nuevo que la copia en /tmp — puede estar desactualizada",
                f"El agente puede resolverlo: `{recopy_cmd}` "
                "(y volver a abrir el .kicad_pcb en KiCad)",
            )
            return
    add(
        "OK",
        "Proyecto de prueba /tmp/gui-test-project",
        f"presente ({len(pcb_files)} pcb, {len(sch_files)} sch) y no anterior al fixture",
    )


# ------------------------------------------------------------------ main


def _run(fn: Callable[[], None]) -> None:
    try:
        fn()
    except Exception as e:  # un check roto no debe ocultar los demás
        add(
            "FAIL",
            fn.__name__,
            f"excepción del propio check: {e}",
            "Reportar al humano: bug del script de verificación",
        )


def main() -> int:
    mode = detect_mode()
    print(f"[MODO: {mode}]\n")

    # Rama git primero: es contexto de sesión.
    _run(check_git_branch)

    # Bloque base (todos los modos).
    for fn in (
        check_python,
        check_git,
        check_uv,
        check_deps,
        check_kicad_cli,
        check_erc,
    ):
        _run(fn)

    # Bloque de integración (integration + integration_gui).
    if mode in ("integration", "integration_gui"):
        _run(check_pcb_render)

    # Bloque comunes de fondo.
    _run(check_ipc_socket)

    # Bloque específico de integration_gui: env vars + estado real de KiCad
    # + proyecto de prueba. Todos son FAIL cuando corresponde (no WARN):
    # sin ellos la sesión GUI se rompe.
    if mode == "integration_gui":
        _run(check_gui_env_vars)
        _run(check_socket_alive)
        _run(check_ipc_probe)
        _run(check_pcb_editor)
        _run(check_gui_test_project)

    # Fixtures y misceláneos (todos los modos).
    for fn in (
        check_fixtures,
        check_fixture_004,
        check_settings,
        check_npx,
    ):
        _run(fn)

    ancho = max(len(c) for _, c, _, _ in RESULTS)
    icon = {"OK": "✓", "WARN": "△", "FAIL": "✗"}
    for estado, check, detalle, fix in RESULTS:
        print(f"[{icon[estado]} {estado:4}] {check:<{ancho}}  {detalle}")
        if fix and estado != "OK":
            print(f"{'':>{ancho + 10}}→ {fix}")

    fails = sum(1 for e, *_ in RESULTS if e == "FAIL")
    warns = sum(1 for e, *_ in RESULTS if e == "WARN")
    print(f"\nMODO detectado: {mode}")
    print(f"Resumen: {len(RESULTS) - fails - warns} OK · {warns} WARN · {fails} FAIL")

    if fails == 0:
        if mode == "unit":
            print("VEREDICTO: listo para tests unitarios (sin KiCad).")
        elif mode == "integration":
            print("VEREDICTO: listo para integration con kicad-cli (sin GUI).")
        else:
            print("VEREDICTO: listo para sesión completa con KiCad real.")
        return 0

    if mode == "integration_gui":
        print("VEREDICTO: BLOQUEADO — corregir los FAIL antes de iniciar la sesión GUI.")
    else:
        print("VEREDICTO: BLOQUEADO. Resolver los FAIL antes de tareas dependientes.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
