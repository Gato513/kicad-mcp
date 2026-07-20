"""Lector de reglas del proyecto — edge clearance + netclasses (sesión 17, P2.1).

Lee el ``.kicad_pro`` en disco (no IPC): ``min_copper_edge_clearance`` y las
netclasses (``clearance``, ``track_width``, ``via_diameter``, ``via_drill``)
con su asignación net→clase. Es el plumbing que faltaba (Dogfooding 2, F-11):
el DSN que exporta ``pcbnew.ExportSpecctraDSN`` sólo ve el ``.kicad_pcb`` — sin
las reglas del proyecto, Freerouting usaba un clearance interno ~0.47mm y
violó la regla real (0.5mm) en 7 sitios. ``add_track`` (D-16.4) tenía el mismo
hueco: consumía un piso fijo 0.2mm en vez de la netclass real (sesión 16,
desviación #3). Este módulo es la única fuente para ambos consumidores —
``bridge/autoroute.py`` (inyección al DSN) y ``tools/pcb.py`` (colisión de
``add_track``) — para no duplicar el plumbing.

Ubicación del campo de edge clearance DIVERGE entre versiones del
``.kicad_pro`` (confirmado en sesión 17 comparando el despertador recién
creado contra ``tests/fixtures/004_real/video.kicad_pro``): el schema "v3"
(``meta.version=3``) lo anida en ``design_settings.rules.*``; el fixture más
viejo lo anida en ``board.design_settings.rules.*``. Se prueban ambas rutas.

Lectura pura de disco, cacheada por ``(mtime_ns, size)`` del ``.kicad_pro``
para no re-parsear en cada llamada de ``add_track``. No valida con pydantic:
regla #5 de CLAUDE.md cubre fronteras IPC/kicad-cli/MCP — esta es una lectura
de archivo del mismo tipo que ``sch_positions.py`` sobre ``.kicad_sch``, no
una de esas tres. Nunca levanta ``KicadMcpError``: es lectura best-effort para
colisión y DSN (degradación graceful con defaults documentados), no un
contrato que deba bloquear la tool si el proyecto no tiene reglas legibles.
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

# Defaults conservadores si el .kicad_pro falta, no es JSON válido, o el campo
# no está — preservan el comportamiento previo a la sesión 17 (D-16.4: piso
# fijo 0.2mm de add_track; 0.25mm es el ancho default de add_track/width_mm).
_DEFAULT_EDGE_CLEARANCE_MM: Final = 0.2
_DEFAULT_CLASS_NAME: Final = "Default"
_DEFAULT_CLEARANCE_MM: Final = 0.2
_DEFAULT_TRACK_WIDTH_MM: Final = 0.25
_DEFAULT_VIA_DIAMETER_MM: Final = 0.6
_DEFAULT_VIA_DRILL_MM: Final = 0.3

_EDGE_CLEARANCE_PATHS: Final = (
    ("design_settings", "rules", "min_copper_edge_clearance"),
    ("board", "design_settings", "rules", "min_copper_edge_clearance"),
)


@dataclass(frozen=True)
class NetClass:
    """Una netclass resuelta del ``.kicad_pro`` (o el fallback fijo)."""

    name: str
    clearance_mm: float
    track_width_mm: float
    via_diameter_mm: float
    via_drill_mm: float


_FALLBACK_CLASS: Final = NetClass(
    name=_DEFAULT_CLASS_NAME,
    clearance_mm=_DEFAULT_CLEARANCE_MM,
    track_width_mm=_DEFAULT_TRACK_WIDTH_MM,
    via_diameter_mm=_DEFAULT_VIA_DIAMETER_MM,
    via_drill_mm=_DEFAULT_VIA_DRILL_MM,
)


@dataclass(frozen=True)
class ProjectRules:
    """Reglas resueltas del ``.kicad_pro`` activo, con defaults si faltan."""

    min_copper_edge_clearance_mm: float
    classes: tuple[NetClass, ...] = ()
    # net exacto -> nombre de clase (net_settings.netclass_assignments).
    net_assignments: dict[str, str] = field(default_factory=dict)
    # (patrón glob, nombre de clase) en el orden del .kicad_pro
    # (net_settings.netclass_patterns) — primer match gana, como KiCad.
    net_patterns: tuple[tuple[str, str], ...] = ()

    def class_for_net(self, net_name: str) -> NetClass:
        """Netclass de ``net_name``.

        Orden de resolución: asignación explícita → patrón → ``Default`` →
        primera clase declarada → fallback fijo (sin clases en el archivo).
        """
        by_name = {c.name: c for c in self.classes}
        assigned = self.net_assignments.get(net_name)
        if assigned and assigned in by_name:
            return by_name[assigned]
        for pattern, cls_name in self.net_patterns:
            if fnmatch.fnmatchcase(net_name, pattern) and cls_name in by_name:
                return by_name[cls_name]
        if _DEFAULT_CLASS_NAME in by_name:
            return by_name[_DEFAULT_CLASS_NAME]
        if self.classes:
            return self.classes[0]
        return _FALLBACK_CLASS


_FALLBACK_RULES: Final = ProjectRules(min_copper_edge_clearance_mm=_DEFAULT_EDGE_CLEARANCE_MM)

# Cache por ruta resuelta del .kicad_pro: (mtime_ns, size) -> ProjectRules.
# Ambos campos (no sólo mtime) para no confundir dos escrituras rápidas en el
# mismo segundo/tick del reloj del filesystem con contenido distinto.
_cache: dict[Path, tuple[tuple[int, int], ProjectRules]] = {}


def _find_kicad_pro(pcb_path: Path) -> Path | None:
    """``.kicad_pro`` hermano de ``pcb_path`` (mismo stem), o el único del directorio."""
    sibling = pcb_path.with_suffix(".kicad_pro")
    if sibling.is_file():
        return sibling
    candidates = list(pcb_path.parent.glob("*.kicad_pro"))
    if len(candidates) == 1:
        return candidates[0]
    return None


def _dig(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    node: Any = payload
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _extract_edge_clearance(payload: dict[str, Any]) -> float | None:
    for path in _EDGE_CLEARANCE_PATHS:
        value = _dig(payload, path)
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
    return None


def _net_settings(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("net_settings")
    return raw if isinstance(raw, dict) else {}


def _extract_classes(payload: dict[str, Any]) -> tuple[NetClass, ...]:
    raw_classes = _net_settings(payload).get("classes")
    if not isinstance(raw_classes, list):
        return ()
    out: list[NetClass] = []
    for raw in raw_classes:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        out.append(
            NetClass(
                name=str(raw["name"]),
                clearance_mm=_as_float(raw.get("clearance"), _DEFAULT_CLEARANCE_MM),
                track_width_mm=_as_float(raw.get("track_width"), _DEFAULT_TRACK_WIDTH_MM),
                via_diameter_mm=_as_float(raw.get("via_diameter"), _DEFAULT_VIA_DIAMETER_MM),
                via_drill_mm=_as_float(raw.get("via_drill"), _DEFAULT_VIA_DRILL_MM),
            )
        )
    return tuple(out)


def _as_float(value: Any, default: float) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return default


def _extract_assignments(payload: dict[str, Any]) -> dict[str, str]:
    raw = _net_settings(payload).get("netclass_assignments")
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if v}


def _extract_patterns(payload: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    raw = _net_settings(payload).get("netclass_patterns")
    if not isinstance(raw, list):
        return ()
    out: list[tuple[str, str]] = []
    for item in raw:
        if isinstance(item, dict) and item.get("pattern") and item.get("netclass"):
            out.append((str(item["pattern"]), str(item["netclass"])))
    return tuple(out)


def load_project_rules(pcb_path: Path) -> ProjectRules:
    """Reglas del proyecto activo para ``pcb_path`` (edge clearance + netclasses).

    Lectura pura de disco del ``.kicad_pro`` hermano, cacheada por
    ``(mtime_ns, size)``. Degradación graceful: si el ``.kicad_pro`` no
    existe (o no se puede determinar sin ambigüedad), no es JSON válido, o
    falta un campo, se completa con los defaults documentados arriba — NUNCA
    levanta ``KicadMcpError``.
    """
    pro_path = _find_kicad_pro(pcb_path)
    if pro_path is None:
        return _FALLBACK_RULES
    try:
        st = pro_path.stat()
        cache_key = (st.st_mtime_ns, st.st_size)
    except OSError:
        return _FALLBACK_RULES
    cached = _cache.get(pro_path)
    if cached is not None and cached[0] == cache_key:
        return cached[1]
    try:
        payload = json.loads(pro_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _FALLBACK_RULES
    if not isinstance(payload, dict):
        return _FALLBACK_RULES
    rules = ProjectRules(
        min_copper_edge_clearance_mm=(
            _extract_edge_clearance(payload) or _DEFAULT_EDGE_CLEARANCE_MM
        ),
        classes=_extract_classes(payload),
        net_assignments=_extract_assignments(payload),
        net_patterns=_extract_patterns(payload),
    )
    _cache[pro_path] = (cache_key, rules)
    return rules
