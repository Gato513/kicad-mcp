#!/usr/bin/env python3
"""Verificación del entorno de desarrollo de kicad-mcp.

Ejecutar como Fase 0 de toda sesión de Claude Code:
    python3 scripts/verificar_entorno.py

Semántica de estados:
- OK    → listo.
- WARN  → no bloquea el MVP (solo-lectura); bloqueará fases futuras. Anotar.
- FAIL  → bloquea. Si la remediación está dentro de los permisos del agente
          (p.ej. `uv sync`), el agente la ejecuta y re-verifica. Si no
          (instalar KiCad, habilitar el API server), el agente DETIENE las
          tareas dependientes y entrega al humano la instrucción impresa.

Exit code: 0 = listo para MVP (FAILs = 0); 1 = bloqueado.
Solo stdlib. No requiere que el propio proyecto esté instalado.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS: list[tuple[str, str, str, str]] = []  # (estado, check, detalle, remediación)


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


# ------------------------------------------------------------------ checks

def check_python() -> None:
    v = sys.version_info
    if (v.major, v.minor) >= (3, 11):
        add("OK", "Python", f"{v.major}.{v.minor}.{v.micro}")
    else:
        add("FAIL", "Python", f"{v.major}.{v.minor} < 3.11",
            "Instalar Python 3.11+ (el humano; en Ubuntu: apt install python3.11)")


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
        add("FAIL", "uv", "no está en PATH",
            "El humano: instalar uv → https://docs.astral.sh/uv/getting-started/installation/")


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
        add("FAIL", "Dependencias Python", "entorno sin sincronizar",
            "El agente puede resolverlo: uv sync")


def check_kicad_cli() -> None:
    code, out, _ = run(["kicad-cli", "version"])
    if code != 0:
        add("FAIL", "kicad-cli", "no está en PATH",
            "El humano: instalar KiCad 10 → https://www.kicad.org/download/ "
            "(en Ubuntu, el PPA oficial de KiCad; el paquete de la distro puede ser viejo)")
        return
    major = int(out.split(".")[0]) if out.split(".")[0].isdigit() else 0
    if major >= 10:
        add("OK", "kicad-cli", f"v{out} (objetivo D2 cumplido)")
    elif major == 9:
        add("OK", "kicad-cli", f"v{out} (mínimo soportado; objetivo es 10)")
    elif major >= 7:
        add("WARN", "kicad-cli", f"v{out}: sirve para netlist/exports pero SIN ERC por CLI",
            "El humano: actualizar a KiCad 10 antes de la fase de validación ERC")
    else:
        add("FAIL", "kicad-cli", f"v{out} demasiado antigua",
            "El humano: instalar KiCad 10")


def check_erc() -> None:
    code, _, _ = run(["kicad-cli", "sch", "erc", "--help"])
    if code == 0:
        add("OK", "ERC por CLI", "disponible (KiCad 8+)")
    else:
        add("WARN", "ERC por CLI", "no disponible en esta versión de kicad-cli",
            "Se resuelve al actualizar a KiCad 10 (ver check kicad-cli)")


def check_ipc_socket() -> None:
    candidates = []
    if os.environ.get("KICAD_API_SOCKET"):
        candidates.append(Path(os.environ["KICAD_API_SOCKET"]))
    candidates.append(Path("/tmp/kicad/api.sock"))
    found = next((p for p in candidates if p.exists()), None)
    if found:
        add("OK", "Socket IPC de KiCad", str(found))
    else:
        add("WARN", "Socket IPC de KiCad",
            "no visible (KiCad cerrado o API deshabilitado). NO bloquea el MVP solo-lectura; "
            "imprescindible desde v0.2",
            "El humano: abrir KiCad → Preferences → Plugins → Enable API server, "
            "y dejar KiCad abierto durante sesiones que usen IPC")


def check_fixtures() -> None:
    fdir = REPO / "tests" / "fixtures"
    if not (fdir / "validate_fixtures.py").exists():
        add("FAIL", "Fixtures", "validate_fixtures.py ausente", "Verificar clone del repo")
        return
    if shutil.which("kicad-cli") is None:
        add("WARN", "Fixtures", "sin validar (kicad-cli ausente)", "Ver check kicad-cli")
        return
    code, out, err = run([sys.executable, str(fdir / "validate_fixtures.py"), str(fdir)],
                         timeout=120)
    if code == 0:
        add("OK", "Fixtures validados", out.replace("\n", " · "))
    else:
        add("FAIL", "Fixtures validados", (out + " " + err)[:300],
            "Si el fallo es de conectividad de fixtures: reportar al humano, NO editar "
            "ground_truth para hacerlo pasar (frontera F1)")


def check_fixture_004() -> None:
    d = REPO / "tests" / "fixtures" / "004_real"
    if d.exists() and any(d.glob("*.kicad_sch")):
        add("OK", "Fixture 004 (real)", "presente")
    else:
        add("WARN", "Fixture 004 (real)", "pendiente (tarea del humano)",
            "El humano: ver criterios en docs/specs/fixtures.md §004_real")


def check_settings() -> None:
    p = REPO / ".claude" / "settings.json"
    if not p.exists():
        add("FAIL", "Permisos Claude Code", ".claude/settings.json ausente",
            "Verificar clone: los permisos son parte del diseño de seguridad")
        return
    try:
        json.loads(p.read_text())
        add("OK", "Permisos Claude Code", "settings.json presente y parseable")
    except json.JSONDecodeError as e:
        add("FAIL", "Permisos Claude Code", f"settings.json inválido: {e}",
            "Reportar al humano (el agente tiene denegada la edición de .claude/)")


def check_npx() -> None:
    code, out, _ = run(["npx", "--version"])
    if code == 0:
        add("OK", "npx (MCP Inspector)", f"v{out}")
    else:
        add("WARN", "npx (MCP Inspector)", "no disponible: no habrá Inspector interactivo",
            "El humano: instalar Node.js si quiere usar el Inspector; los tests "
            "con cliente MCP in-process no lo requieren")


# ------------------------------------------------------------------ main

def main() -> int:
    for fn in (check_python, check_git, check_uv, check_deps, check_kicad_cli,
               check_erc, check_ipc_socket, check_fixtures, check_fixture_004,
               check_settings, check_npx):
        try:
            fn()
        except Exception as e:  # un check roto no debe ocultar los demás
            add("FAIL", fn.__name__, f"excepción del propio check: {e}",
                "Reportar al humano: bug del script de verificación")

    ancho = max(len(c) for _, c, _, _ in RESULTS)
    icon = {"OK": "✓", "WARN": "△", "FAIL": "✗"}
    for estado, check, detalle, fix in RESULTS:
        print(f"[{icon[estado]} {estado:4}] {check:<{ancho}}  {detalle}")
        if fix and estado != "OK":
            print(f"{'':>{ancho + 10}}→ {fix}")

    fails = sum(1 for e, *_ in RESULTS if e == "FAIL")
    warns = sum(1 for e, *_ in RESULTS if e == "WARN")
    print(f"\nResumen: {len(RESULTS) - fails - warns} OK · {warns} WARN · {fails} FAIL")
    if fails == 0:
        print("VEREDICTO: listo para el MVP (los WARN aplican a fases futuras).")
        return 0
    print("VEREDICTO: BLOQUEADO. Resolver los FAIL antes de tareas dependientes.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
