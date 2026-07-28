#!/usr/bin/env python3
"""Harness de barrido y MEDICIÓN para la investigación P1 solder_mask_bridge
(sesión 30, continuación de docs/investigacion/26-solder-mask-ant1.md).

Sesión 26 solo observó DRC pass/fail (señal binaria). Este harness mide la
geometría real: tras `kicad-cli pcb drc --refill-zones --save-board`, parsea
el `filled_polygon` de la zona GND en B.Cu del board resultante y calcula la
distancia mínima del centro de ANT1 al borde del fill (`d_fill`). Eso permite
contrastar directamente contra el modelo:

    r_mask  = r_cobre_pad + max(pad_to_mask_clearance, mask_to_copper_clearance)
    d_fill  = max(r_cobre_pad + clearance_netclass, r_keepout * cos(pi/N))
    viola  <=>  r_mask > d_fill

Uso:
    python3 sweep.py <fixture_dir> <workdir> --M 0.22 [--keepout-r 1.82] [--keepout-n 16]

No modifica el fixture in-place (siempre copia). No requiere pcbnew ni IPC —
100% offline vía kicad-cli, reproducible sin KiCad corriendo.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ANT1_CENTER_MM = (144.5, 89.0)  # fixture actual (post sesión 29); ver nota abajo
ANT1_COPPER_RADIUS_MM = 1.5  # (size 3 3) -> r = 1.5
KEEPOUT_ZONE_NAME = "__kicadmcp_hc__pad_ANT1_1"

_PAD_TO_MASK_RE = re.compile(r"\(pad_to_mask_clearance\s+(-?[0-9.]+)\)")


@dataclass
class SweepResult:
    m_pad_to_mask: float
    keepout_r_mm: float | None
    keepout_n: int | None
    d_fill_mm: float | None
    violation_ant1_vs_gnd: bool
    total_violations: int


def _circle_pts(cx: float, cy: float, r: float, n: int) -> str:
    pts = []
    for i in range(n):
        theta = 2 * math.pi * i / n
        x = round(cx + r * math.cos(theta), 6)
        y = round(cy + r * math.sin(theta), 6)
        pts.append(f"(xy {x} {y})")
    return " ".join(pts)


def prepare_board(
    fixture_dir: Path,
    workdir: Path,
    *,
    m_pad_to_mask: float,
    keepout_r_mm: float | None,
    keepout_n: int = 16,
    label: str,
) -> Path:
    """Copia el fixture a workdir/label, ajusta pad_to_mask_clearance y
    opcionalmente reemplaza el polígono del keepout B.Cu de ANT1."""
    dst = workdir / label
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(fixture_dir, dst)

    pcb_path = next(dst.glob("*.kicad_pcb"))
    text = pcb_path.read_text()

    text, n_sub = _PAD_TO_MASK_RE.subn(f"(pad_to_mask_clearance {m_pad_to_mask})", text)
    if n_sub != 1:
        raise RuntimeError(f"esperaba 1 match de pad_to_mask_clearance, encontré {n_sub}")

    if keepout_r_mm is not None:
        text = _replace_keepout_polygon(
            text,
            layer="B.Cu",
            cx=ANT1_CENTER_MM[0],
            cy=ANT1_CENTER_MM[1],
            r=keepout_r_mm,
            n=keepout_n,
        )

    pcb_path.write_text(text)
    return pcb_path


def _replace_keepout_polygon(
    text: str, *, layer: str, cx: float, cy: float, r: float, n: int
) -> str:
    """Reemplaza el bloque (pts ...) del primer (polygon) que sigue al bloque
    (zone ... (layer "<layer>") (name "__kicadmcp_hc__pad_ANT1_1") ...)."""
    marker = f'(name "{KEEPOUT_ZONE_NAME}")'
    search_from = 0
    while True:
        name_idx = text.find(marker, search_from)
        if name_idx == -1:
            raise RuntimeError(f"no encontré zona {KEEPOUT_ZONE_NAME!r}")
        # el (layer "...") vive ANTES del (name ...) en el orden real del
        # S-expr de KiCad (layer, uuid, name, ...) -> buscar hacia atrás
        zone_start = text.rfind("(zone", 0, name_idx)
        layer_match = re.search(r'\(layer "([^"]+)"\)', text[zone_start:name_idx])
        if layer_match and layer_match.group(1) == layer:
            break
        search_from = name_idx + len(marker)

    poly_idx = text.find("(polygon", name_idx)
    pts_start = text.find("(pts", poly_idx)
    pts_end = text.find(")", text.find(")", pts_start) + 1) + 1
    # (pts ... ) puede tener varias líneas de (xy ..); buscamos el cierre real
    # contando paréntesis desde pts_start.
    depth = 0
    i = pts_start
    for i in range(pts_start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                break
    pts_end = i + 1

    new_pts_block = f"(pts\n\t\t\t\t{_circle_pts(cx, cy, r, n)}\n\t\t\t)"
    return text[:pts_start] + new_pts_block + text[pts_end:]


def run_drc(pcb_path: Path) -> dict:
    out_json = pcb_path.with_suffix(".drc.json")
    cmd = [
        "kicad-cli",
        "pcb",
        "drc",
        "--format",
        "json",
        "--severity-all",
        "--refill-zones",
        "--save-board",
        "-o",
        str(out_json),
        str(pcb_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"kicad-cli falló ({proc.returncode}): {proc.stderr}")
    return json.loads(out_json.read_text())


def _point_segment_distance(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    """Distancia de (px,py) al segmento [A,B] (no a la recta infinita)."""
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    cx_, cy_ = ax + t * dx, ay + t * dy
    return math.hypot(px - cx_, py - cy_)


def measure_d_fill(pcb_path: Path, *, center: tuple[float, float] = ANT1_CENTER_MM) -> float | None:
    """Distancia mínima del centro de ANT1 al borde del filled_polygon de la
    zona GND en B.Cu, tras el refill+save de run_drc.

    IMPORTANTE: mide distancia a los SEGMENTOS del polígono (perpendicular,
    clippeada), no solo a sus vértices. Para un polígono de lados rectos la
    distancia mínima real desde un punto interior ocurre típicamente en el
    punto medio de una arista (el apotema), no en un vértice — medir solo
    vértices sobreestima sistemáticamente d_fill cuando el keepout domina.
    """
    text = pcb_path.read_text()
    idx = text.find('(net "GND")')
    while idx != -1:
        window = text[idx : idx + 200]
        if '(layer "B.Cu")' in window:
            break
        idx = text.find('(net "GND")', idx + 1)
    if idx == -1:
        return None

    fp_idx = text.find("(filled_polygon", idx)
    if fp_idx == -1 or fp_idx - idx > 5000:
        return None
    # el filled_polygon puede tener varios (pts) si hay islas; tomamos hasta
    # 8000 chars, suficiente para el polígono relevante en este fixture.
    seg = text[fp_idx : fp_idx + 8000]
    pts = [(float(x), float(y)) for x, y in re.findall(r"\(xy ([\-0-9.]+) ([\-0-9.]+)\)", seg)]
    cx, cy = center

    # sub-lista de puntos cercanos a ANT1, preservando su orden de aparición
    # (son consecutivos en el contorno) para poder reconstruir los segmentos
    # que realmente rodean el cutout, incluyendo el segmento de "entrada" y
    # "salida" del cutout (que conecta con puntos lejanos).
    near_idx = [i for i, (x, y) in enumerate(pts) if math.hypot(x - cx, y - cy) < 3.0]
    if not near_idx:
        return None
    lo, hi = min(near_idx), max(near_idx)
    # incluir un punto extra a cada lado para cerrar los segmentos de borde
    lo = max(0, lo - 1)
    hi = min(len(pts) - 1, hi + 1)
    window_pts = pts[lo : hi + 1]

    best = min(
        _point_segment_distance(cx, cy, ax, ay, bx, by)
        for (ax, ay), (bx, by) in itertools.pairwise(window_pts)
    )
    return best


def check_violation(drc_payload: dict) -> tuple[bool, int]:
    violations = drc_payload.get("violations", [])
    total = len(violations)
    hit = False
    for v in violations:
        if v.get("type") != "solder_mask_bridge":
            continue
        descs = " ".join(it.get("description", "") for it in v.get("items", []))
        if "ANT1" in descs and "GND" in descs:
            hit = True
    return hit, total


def run_one(
    fixture_dir: Path,
    workdir: Path,
    *,
    m_pad_to_mask: float,
    keepout_r_mm: float | None,
    keepout_n: int,
    label: str,
) -> SweepResult:
    pcb_path = prepare_board(
        fixture_dir,
        workdir,
        m_pad_to_mask=m_pad_to_mask,
        keepout_r_mm=keepout_r_mm,
        keepout_n=keepout_n,
        label=label,
    )
    payload = run_drc(pcb_path)
    hit, total = check_violation(payload)
    d_fill = measure_d_fill(pcb_path)
    return SweepResult(
        m_pad_to_mask=m_pad_to_mask,
        keepout_r_mm=keepout_r_mm,
        keepout_n=keepout_n if keepout_r_mm is not None else None,
        d_fill_mm=d_fill,
        violation_ant1_vs_gnd=hit,
        total_violations=total,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fixture_dir", type=Path)
    ap.add_argument("workdir", type=Path)
    ap.add_argument("--M", type=float, action="append", dest="m_values", required=True)
    ap.add_argument("--keepout-r", type=float, default=None)
    ap.add_argument("--keepout-n", type=int, default=16)
    args = ap.parse_args()

    args.workdir.mkdir(parents=True, exist_ok=True)
    results = []
    for m in args.m_values:
        label = f"m{m}_r{args.keepout_r}_n{args.keepout_n}".replace(".", "p").replace(
            "None", "stock"
        )
        r = run_one(
            args.fixture_dir,
            args.workdir,
            m_pad_to_mask=m,
            keepout_r_mm=args.keepout_r,
            keepout_n=args.keepout_n,
            label=label,
        )
        results.append(r)
        print(
            f"M={r.m_pad_to_mask:.3f} r_keepout={r.keepout_r_mm} N={r.keepout_n} "
            f"d_fill={r.d_fill_mm} violation_ANT1_vs_GND={r.violation_ant1_vs_gnd} "
            f"total_violations={r.total_violations}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
