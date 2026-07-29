#!/usr/bin/env python3
"""Prepara el directorio ``working/`` de un proyecto de la Validation Suite.

**Mismo requisito de intérprete que ``measure_ground_truth.py``**: correr
con ``/usr/bin/python3`` (pcbnew del sistema), no con el venv de ``uv``.

    /usr/bin/python3 validation-suite/tools/prepare_working.py \\
        <ground-truth-kicad10-dir> <working-dir>

## Qué hace

1. Copia el proyecto completo (esquemático, librerías, `fp-lib-table`,
   `sym-lib-table`, `.kicad_pro`, `.kicad_prl`, imágenes, enclosures, todo)
   de ``ground-truth-kicad10-dir`` a ``working-dir`` sin tocar nada del
   esquemático — el flujo canónico rutea desde una netlist ya completa,
   nunca desde un sch a medio construir.
2. Muta **sólo** el `.kicad_pcb` de la copia, vía pcbnew:
   - borra todos los tracks/arcos/vías (`board.GetTracks()`);
   - borra todas las zonas, de cobre y rule areas/keepouts (`board.Zones()`);
   - mueve cada footprint a `(0, 0)` **sin tocar su orientación** (decisión
     explícita del arquitecto en sesión 31: estado inicial literal del
     prompt, no una grilla prolija — ejercita `get_footprint_neighbors` y
     la colocación asistida contra el caso más adversarial, courtyards
     100% solapados).
   - conserva intacto todo lo demás: Edge.Cuts, netclasses, reglas de
     diseño del autor (`pad_to_mask_clearance`, `connect_pads`, etc. viven
     en el `.kicad_pcb`/`.kicad_pro`, no se tocan).
3. Verifica el estado resultante con asserts explícitos (no en silencio):
   0 tracks, 0 vías, 0 zonas, N footprints todos en `(0,0)`, al menos un
   dibujo en Edge.Cuts. Si algún assert falla, aborta con mensaje claro —
   un `working/` mal preparado invalida toda la sesión de validación.

## Qué NO hace (deliberadamente)

- No toca el `.kicad_sch`: el esquemático completo es precondición del
  flujo canónico, no parte de lo que se "prepara".
- No re-ejecuta ERC/DRC (eso es medición, vive en `measure_ground_truth.py`
  y en las tools del propio MCP durante el Bloque 1/2).
- No copia el `.git` si `ground-truth-kicad10-dir` es un repo (se asume que
  el caller ya limpió eso, como hace sesión 31 con `ground-truth-original`).

## Hallazgo de entorno (sesión 31): segfault de pcbnew al mover footprints
en el mismo proceso que la remoción de tracks/zonas

Aislado empíricamente (D-30.1 — verificar contra el motor real, no contra
lo que "debería" andar): remover tracks+zonas y **en el mismo proceso**
Python mover un footprint con ``fp.SetPosition()`` hace segfault (SIGSEGV,
exit 139) en pcbnew 10.0.4, incluso si se hace un ``LoadBoard`` fresco del
archivo ya guardado sin cobre **dentro del mismo proceso**. Aislado con
bisección manual (remover tracks solo, remover zonas solo, mover solo —
cada uno por separado NO crashea; sólo la combinación remove-then-move en
el mismo proceso sí). La causa más probable es un caché de conectividad/
ratsnest que queda en estado inconsistente tras ``Remove()`` y que
``SetPosition()`` toca al intentar actualizar el ratsnest — el bug parece
vivir en el binding de scripting de pcbnew, no en el formato de archivo
(el archivo guardado por la etapa de remoción es perfectamente válido:
un proceso *fresco* que sólo lo carga y mueve footprints, sin haber hecho
ninguna remoción antes, funciona sin problema).

**Mitigación**: cada etapa de mutación corre en su **propio subprocess**
(``sys.executable`` = el mismo intérprete que llamó a este script, para no
perder la garantía de que sea el Python con pcbnew). Remoción y movimiento
nunca comparten proceso. Si una futura versión de pcbnew resuelve esto
limpio, este script seguiría funcionando igual (el costo extra es de unos
pocos cientos de ms por subprocess adicional en boards de este tamaño).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import pcbnew
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        "ERROR: no se pudo importar pcbnew. Correr con el Python del "
        "SISTEMA (ej. /usr/bin/python3), no con el venv de `uv`.\n"
        f"Import original: {exc}\n"
    )
    sys.exit(2)


_STAGE_REMOVE = """
import pcbnew, sys
pcb_path = sys.argv[1]
board = pcbnew.LoadBoard(pcb_path)
for track in list(board.GetTracks()):
    board.Remove(track)
for zone in list(board.Zones()):
    board.Remove(zone)
board.Save(pcb_path)
"""

_STAGE_MOVE = """
import pcbnew, sys
pcb_path = sys.argv[1]
board = pcbnew.LoadBoard(pcb_path)
origin = pcbnew.VECTOR2I(0, 0)
for fp in list(board.GetFootprints()):
    fp.SetPosition(origin)
board.Save(pcb_path)
"""


def _run_stage(script: str, pcb_path: Path, stage_name: str) -> None:
    """Corre una etapa de mutación en un subprocess NUEVO (ver hallazgo de
    segfault en el docstring del módulo — remoción y movimiento no pueden
    compartir proceso pcbnew)."""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(pcb_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Etapa '{stage_name}' de prepare_working falló "
            f"(returncode={completed.returncode}, posible segfault si es "
            f"-11/139): {completed.stderr.strip()[-500:]}"
        )


def _find_single_pcb(project_dir: Path) -> Path:
    candidates = sorted(project_dir.glob("*.kicad_pcb"))
    if len(candidates) != 1:
        raise RuntimeError(
            f"Se esperaba exactamente 1 .kicad_pcb en {project_dir}, "
            f"se encontraron {len(candidates)}: {candidates}"
        )
    return candidates[0]


def prepare(ground_truth_dir: Path, working_dir: Path) -> Path:
    if working_dir.exists():
        raise RuntimeError(
            f"{working_dir} ya existe — este script no sobrescribe un "
            "working/ existente (podría destruir colocación/ruteo ya "
            "hecho por el flujo canónico). Borralo explícitamente primero "
            "si querés regenerarlo desde cero."
        )

    shutil.copytree(ground_truth_dir, working_dir)
    pcb_path = _find_single_pcb(working_dir)

    # Conteo de footprints ANTES de mutar nada (para el assert de M3.a).
    footprints_before = len(list(pcbnew.LoadBoard(str(pcb_path)).GetFootprints()))

    _run_stage(_STAGE_REMOVE, pcb_path, "remove_tracks_and_zones")
    _run_stage(_STAGE_MOVE, pcb_path, "move_footprints_to_origin")

    # Verificación post-condición en ESTE proceso — es la única carga de
    # board que hace prepare_working.py directamente, así que no dispara
    # el bug de doble-load-en-un-proceso descrito arriba.
    reloaded = pcbnew.LoadBoard(str(pcb_path))
    origin = pcbnew.VECTOR2I(0, 0)
    n_tracks = len(list(reloaded.GetTracks()))
    n_zones = len(list(reloaded.Zones()))
    n_fp = len(list(reloaded.GetFootprints()))
    fp_positions = [fp.GetPosition() for fp in reloaded.GetFootprints()]
    n_at_origin = sum(1 for p in fp_positions if p == origin)
    edge_drawings = [d for d in reloaded.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]

    assert n_tracks == 0, f"Se esperaban 0 tracks/vías post-limpieza, hay {n_tracks}"
    assert n_zones == 0, f"Se esperaban 0 zonas post-limpieza, hay {n_zones}"
    assert n_fp == footprints_before, (
        f"El conteo de footprints cambió: {footprints_before} -> {n_fp} "
        "(corrupción — M3.a del prompt de sesión 31)"
    )
    assert n_at_origin == n_fp, (
        f"Se esperaba que los {n_fp} footprints quedaran en (0,0), sólo {n_at_origin} lo están"
    )
    assert len(edge_drawings) > 0, "Edge.Cuts vacío tras la preparación — contorno perdido"

    print(
        f"working/ preparado en {working_dir}: "
        f"{n_fp} footprints en (0,0), 0 tracks, 0 vías, 0 zonas, "
        f"{len(edge_drawings)} dibujo(s) en Edge.Cuts."
    )
    return pcb_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ground_truth_dir", type=Path)
    parser.add_argument("working_dir", type=Path)
    args = parser.parse_args()

    if not args.ground_truth_dir.is_dir():
        sys.stderr.write(f"ERROR: no existe el directorio {args.ground_truth_dir}\n")
        return 1

    try:
        prepare(args.ground_truth_dir, args.working_dir)
    except (RuntimeError, AssertionError) as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
