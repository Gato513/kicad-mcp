"""Parseo de posiciones ``(at x y)`` desde el ``.kicad_sch`` raíz.

Extrae SOLO las coordenadas de instancias de componentes en la hoja raíz.
La conectividad NO se reconstruye desde aquí — la fuente de verdad es el
netlist de ``kicad-cli`` (ver `netlist.py` y `restricciones-kicad.md`).

Detección de multi-hoja: cualquier ``(sheet ...)`` en el nivel raíz dispara
``UNSUPPORTED_HIERARCHY``. El MVP no procesa proyectos jerárquicos ni parcial
ni silenciosamente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import ErrorCode, KicadMcpError

# Tokeniza el S-expression del ``.kicad_sch``:
#   - "quoted" strings (con posibles ``\"`` dentro)
#   - paréntesis
#   - atoms
_TOKEN_RE = re.compile(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+')


@dataclass(frozen=True)
class Placement:
    """Posición de una instancia de componente en la hoja raíz."""

    ref: str
    x: float
    y: float
    rot: float = 0.0


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def _parse(tokens: list[str]) -> Any:
    """Convierte una lista de tokens en un árbol de listas + atoms."""
    pos = 0

    def read() -> Any:
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        if tok == "(":
            node: list[Any] = []
            while tokens[pos] != ")":
                node.append(read())
            pos += 1
            return node
        if tok == ")":
            raise ValueError("paréntesis de cierre inesperado")
        return tok

    root = read()
    return root


def _unquote(atom: str) -> str:
    if len(atom) >= 2 and atom[0] == '"' and atom[-1] == '"':
        return atom[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return atom


def _find_child(node: Any, head: str) -> Any | None:
    """Devuelve el primer sub-nodo ``(head ...)`` dentro de ``node``, o None."""
    if not isinstance(node, list):
        return None
    for child in node:
        if isinstance(child, list) and child and child[0] == head:
            return child
    return None


def _extract_placement(symbol_node: list[Any]) -> Placement | None:
    """Extrae ``Placement`` de un ``(symbol ...)`` de instancia. None si no aplica."""
    if _find_child(symbol_node, "lib_id") is None:
        return None
    at = _find_child(symbol_node, "at")
    if at is None or len(at) < 3:
        return None
    try:
        x = float(at[1])
        y = float(at[2])
    except (TypeError, ValueError):
        return None
    rot = 0.0
    if len(at) >= 4:
        try:
            rot = float(at[3])
        except (TypeError, ValueError):
            rot = 0.0

    ref: str | None = None
    for child in symbol_node:
        if (
            isinstance(child, list)
            and len(child) >= 3
            and child[0] == "property"
            and _unquote(child[1]) == "Reference"
        ):
            ref = _unquote(child[2])
            break
    if ref is None:
        return None
    return Placement(ref=ref, x=x, y=y, rot=rot)


def parse_root_positions(sch_path: Path) -> tuple[Placement, ...]:
    """Parsea el ``.kicad_sch`` raíz. Lanza ``UNSUPPORTED_HIERARCHY`` si hay hojas.

    ``sch_path`` debe estar canonicalizada por el llamador (regla #4).
    """
    text = sch_path.read_text(encoding="utf-8", errors="replace")
    tokens = _tokenize(text)
    if not tokens:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message="El archivo .kicad_sch está vacío o ilegible.",
            hint=f"Verificar {sch_path.name}",
        )
    tree = _parse(tokens)
    if not isinstance(tree, list) or not tree or tree[0] != "kicad_sch":
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message="El archivo no comienza con (kicad_sch ...).",
            hint=f"Verificar formato de {sch_path.name}",
        )

    # Deteccion de multi-hoja: cualquier (sheet ...) en el nivel raíz.
    for child in tree[1:]:
        if isinstance(child, list) and child and child[0] == "sheet":
            raise KicadMcpError(
                code=ErrorCode.UNSUPPORTED_HIERARCHY,
                message="El esquemático raíz contiene sub-hojas (hierarchical sheets).",
                hint=(
                    "El MVP solo soporta esquemáticos plano-únicos. "
                    "Aplanar el proyecto o esperar al soporte de jerarquía."
                ),
            )

    placements: list[Placement] = []
    for child in tree[1:]:
        if isinstance(child, list) and child and child[0] == "symbol":
            p = _extract_placement(child)
            if p is not None:
                placements.append(p)
    return tuple(placements)
