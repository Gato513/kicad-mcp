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

``min_hole_clearance`` (sesión 21, F-D3-01) se agrega con el mismo patrón
dual-path que el edge clearance — kipy 0.7.1 no expone esta regla vía IPC
(confirmado en ``docs/investigacion/21-fill-zones-holes.md`` §2), así que
``bridge/ipc.py::enforce_hole_clearance`` la lee de acá.

``solder_mask_to_copper_clearance`` (``.kicad_pro``) y
``pad_to_mask_clearance`` (sesión 26, ``docs/investigacion/26-solder-mask-ant1.md``)
se agregan para que ``enforce_hole_clearance`` pueda proteger también la
apertura de máscara de un pad, no sólo su agujero. ``pad_to_mask_clearance``
NO vive en el ``.kicad_pro`` — vive en el ``(setup ...)`` del ``.kicad_pcb``
(otro formato, S-expression, no JSON) — así que ``load_project_rules`` ahora
lee DOS archivos: el ``.kicad_pro`` hermano (como siempre) y ``pcb_path``
mismo (regex puntual sobre el texto, no un parser S-expression completo —
sería sobre-ingeniería para un único escalar). El cache se ajusta para
invalidar por el ``(mtime_ns, size)`` de ambos archivos.

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
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

# Defaults conservadores si el .kicad_pro falta, no es JSON válido, o el campo
# no está — preservan el comportamiento previo a la sesión 17 (D-16.4: piso
# fijo 0.2mm de add_track; 0.25mm es el ancho default de add_track/width_mm).
_DEFAULT_EDGE_CLEARANCE_MM: Final = 0.2
_DEFAULT_HOLE_CLEARANCE_MM: Final = 0.25  # default real de KiCad (sesión 21)
_DEFAULT_CLASS_NAME: Final = "Default"
_DEFAULT_CLEARANCE_MM: Final = 0.2
_DEFAULT_TRACK_WIDTH_MM: Final = 0.25
_DEFAULT_VIA_DIAMETER_MM: Final = 0.6
_DEFAULT_VIA_DRILL_MM: Final = 0.3
# Defaults reales de KiCad cuando el campo falta (sesión 26): ambos 0mm.
_DEFAULT_SOLDER_MASK_TO_COPPER_CLEARANCE_MM: Final = 0.0
_DEFAULT_PAD_TO_MASK_CLEARANCE_MM: Final = 0.0

_EDGE_CLEARANCE_PATHS: Final = (
    ("design_settings", "rules", "min_copper_edge_clearance"),
    ("board", "design_settings", "rules", "min_copper_edge_clearance"),
)

_HOLE_CLEARANCE_PATHS: Final = (
    ("design_settings", "rules", "min_hole_clearance"),
    ("board", "design_settings", "rules", "min_hole_clearance"),
)

_MASK_TO_COPPER_CLEARANCE_PATHS: Final = (
    ("design_settings", "rules", "solder_mask_to_copper_clearance"),
    ("board", "design_settings", "rules", "solder_mask_to_copper_clearance"),
)

# ``pad_to_mask_clearance`` vive en el ``(setup ...)`` del .kicad_pcb, no en
# el .kicad_pro — regex puntual sobre un único escalar S-expression conocido,
# no un parser general (ver docstring del módulo).
_PAD_TO_MASK_CLEARANCE_RE: Final = re.compile(r"\(pad_to_mask_clearance\s+(-?[0-9.]+)\)")


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
    min_hole_clearance_mm: float = _DEFAULT_HOLE_CLEARANCE_MM
    solder_mask_to_copper_clearance_mm: float = _DEFAULT_SOLDER_MASK_TO_COPPER_CLEARANCE_MM
    pad_to_mask_clearance_mm: float = _DEFAULT_PAD_TO_MASK_CLEARANCE_MM
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


# Cache por pcb_path: ((mtime_ns, size) del .kicad_pro | None, (mtime_ns,
# size) del .kicad_pcb | None) -> ProjectRules. Sesión 26: dos archivos
# alimentan ProjectRules (pad_to_mask_clearance vive en el .kicad_pcb), así
# que la clave de cache ahora es el par de ambos, no sólo el .kicad_pro.
_CacheKey = tuple[tuple[int, int] | None, tuple[int, int] | None]
_cache: dict[Path, tuple[_CacheKey, ProjectRules]] = {}


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


def _extract_hole_clearance(payload: dict[str, Any]) -> float | None:
    for path in _HOLE_CLEARANCE_PATHS:
        value = _dig(payload, path)
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
    return None


def _extract_mask_to_copper_clearance(payload: dict[str, Any]) -> float | None:
    for path in _MASK_TO_COPPER_CLEARANCE_PATHS:
        value = _dig(payload, path)
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
    return None


def _extract_pad_to_mask_clearance(pcb_text: str) -> float | None:
    """``pad_to_mask_clearance`` del ``(setup ...)`` del .kicad_pcb (sesión 26).

    Regex puntual, no parser S-expression: un único escalar conocido, mismo
    criterio que el resto del módulo (lectura best-effort, degrada a
    default si no matchea).
    """
    match = _PAD_TO_MASK_CLEARANCE_RE.search(pcb_text)
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
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
    """Reglas del proyecto activo para ``pcb_path`` (edge/hole/mask clearance +
    netclasses).

    Lectura pura de disco de DOS archivos (sesión 26): el ``.kicad_pro``
    hermano (JSON, como siempre) y ``pcb_path`` mismo (texto, para
    ``pad_to_mask_clearance`` — vive en el ``(setup ...)`` del .kicad_pcb, no
    en el .kicad_pro). Cacheada por el par ``(mtime_ns, size)`` de ambos.
    Degradación graceful e independiente por archivo: si el ``.kicad_pro`` no
    existe/no es JSON válido/falta un campo, o si ``pcb_path`` no se puede
    leer/no matchea el patrón, cada campo faltante se completa con su default
    documentado arriba — NUNCA levanta ``KicadMcpError``.
    """
    pro_path = _find_kicad_pro(pcb_path)
    pro_cache_key: tuple[int, int] | None = None
    if pro_path is not None:
        try:
            st = pro_path.stat()
            pro_cache_key = (st.st_mtime_ns, st.st_size)
        except OSError:
            pro_path = None
    pcb_cache_key: tuple[int, int] | None = None
    try:
        st = pcb_path.stat()
        pcb_cache_key = (st.st_mtime_ns, st.st_size)
    except OSError:
        pass
    cache_key: _CacheKey = (pro_cache_key, pcb_cache_key)
    cached = _cache.get(pcb_path)
    if cached is not None and cached[0] == cache_key:
        return cached[1]

    edge_clearance = _DEFAULT_EDGE_CLEARANCE_MM
    hole_clearance = _DEFAULT_HOLE_CLEARANCE_MM
    mask_to_copper_clearance = _DEFAULT_SOLDER_MASK_TO_COPPER_CLEARANCE_MM
    classes: tuple[NetClass, ...] = ()
    net_assignments: dict[str, str] = {}
    net_patterns: tuple[tuple[str, str], ...] = ()
    if pro_path is not None:
        try:
            payload = json.loads(pro_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            edge_clearance = _extract_edge_clearance(payload) or _DEFAULT_EDGE_CLEARANCE_MM
            hole_clearance = _extract_hole_clearance(payload) or _DEFAULT_HOLE_CLEARANCE_MM
            extracted_mask = _extract_mask_to_copper_clearance(payload)
            mask_to_copper_clearance = (
                extracted_mask
                if extracted_mask is not None
                else _DEFAULT_SOLDER_MASK_TO_COPPER_CLEARANCE_MM
            )
            classes = _extract_classes(payload)
            net_assignments = _extract_assignments(payload)
            net_patterns = _extract_patterns(payload)

    pad_to_mask_clearance = _DEFAULT_PAD_TO_MASK_CLEARANCE_MM
    try:
        pcb_text = pcb_path.read_text(encoding="utf-8")
    except OSError:
        pcb_text = None
    if pcb_text is not None:
        extracted_pad_mask = _extract_pad_to_mask_clearance(pcb_text)
        if extracted_pad_mask is not None:
            pad_to_mask_clearance = extracted_pad_mask

    rules = ProjectRules(
        min_copper_edge_clearance_mm=edge_clearance,
        min_hole_clearance_mm=hole_clearance,
        solder_mask_to_copper_clearance_mm=mask_to_copper_clearance,
        pad_to_mask_clearance_mm=pad_to_mask_clearance,
        classes=classes,
        net_assignments=net_assignments,
        net_patterns=net_patterns,
    )
    _cache[pcb_path] = (cache_key, rules)
    return rules
