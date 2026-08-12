#!/usr/bin/env python3
"""
Comparación JSON exacta de identidad, exigida por contrato
S47-H11-AMPLIACION-13-21_v1 §2.1(3).

Compara clusters-ext.json (re-derivado en esta sesión) contra:
  - los contadores congelados del universo (29 / 8 / 0 / 21),
  - el array `survivors` anclado en S47-CORREGIDO-2/raw/clusters.json,
  - posiciones 1-12 contra enumeracion.md §5 (paquete S47 original),
  - posiciones 13-21 contra contrato §2 (candidatos de esta extensión).

Exit 0 = igualdad completa. Cualquier otro exit = drift (DRIFT_UNIVERSO_S47).
No escribe nada; solo lee. No modifica ningún archivo de entrada.
"""

import json
import sys
from pathlib import Path

CLUSTERS_EXT = Path(sys.argv[1])
CLUSTERS_ANCLADO = Path(sys.argv[2])

EXPECTED_COUNTS = {
    "N_universo_total": 29,
    "N_excluidos_institucional": 8,
    "N_excluidos_presup": 0,
    "N_supervivientes": 21,
}

# Posiciones 1-12, literal de enumeracion.md §5 del paquete S47 original.
EXPECTED_1_12 = [
    ["_DELETE_TOLERANCE_MM", "_copper_candidate_dict", "_delete_copper", "_match_copper"],
    ["_audit_error"],
    [
        "_bbox_distance_to_point",
        "_closest_board_edge",
        "_closest_point_copper_bbox",
        "_copper_distance_to_bbox",
        "get_footprint_neighbors",
    ],
    ["_bbox_distance_to_point"],
    ["_copper_distance_mm", "_dist_point_segment"],
    ["_copper_in_bbox"],
    ["_copper_on_layer"],
    ["_derive_post_state", "_find_target", "_register_post_snapshot", "move_footprint"],
    [
        "_dist_segment_to_pad",
        "_find_track_pad_collision",
        "_parse_pad_ref",
        "_resolve_endpoint",
        "_resolve_pad_coord",
        "_rounded_rect_sdf",
        "_track_params",
        "add_track",
    ],
    ["_outline_params", "draw_board_outline"],
    ["_resolve_board"],
    ["_segment_intersects_bbox"],
]

# Posiciones 13-21, literal de contrato_S47-H11-AMPLIACION-13-21_v1.md §2.
EXPECTED_13_21 = [
    ["_similars"],
    ["_via_params", "add_via"],
    ["delete_track"],
    ["delete_via"],
    ["get_component_detail"],
    ["get_tracks"],
    ["reload_board_from_disk"],
    ["save_board"],
    ["set_footprint_ref"],
]

EXPECTED_SURVIVORS = [sorted(k) for k in (EXPECTED_1_12 + EXPECTED_13_21)]

errors: list[str] = []

ext = json.loads(CLUSTERS_EXT.read_text())
anclado = json.loads(CLUSTERS_ANCLADO.read_text())

for key, expected in EXPECTED_COUNTS.items():
    got = ext.get(key)
    if got != expected:
        errors.append(f"{key}: esperado {expected}, obtenido {got}")
    got_anchor = anclado.get(key)
    if got_anchor != expected:
        errors.append(f"{key} (anclado): esperado {expected}, obtenido {got_anchor}")

survivors_ext = ext.get("survivors")
survivors_anclado = anclado.get("survivors")

if survivors_ext != survivors_anclado:
    errors.append("survivors: array re-derivado difiere del array anclado (orden o contenido)")

if survivors_ext != EXPECTED_SURVIVORS:
    for i, (got, exp) in enumerate(zip(survivors_ext, EXPECTED_SURVIVORS, strict=True), 1):
        if got != exp:
            errors.append(f"survivors[{i}]: esperado {exp}, obtenido {got}")
    if len(survivors_ext) != len(EXPECTED_SURVIVORS):
        errors.append(
            f"survivors: longitud esperada {len(EXPECTED_SURVIVORS)}, obtenida {len(survivors_ext)}"
        )

if errors:
    print("DRIFT_UNIVERSO_S47")
    for e in errors:
        print(" -", e)
    sys.exit(1)

print("IDENTIDAD_CONFORME")
print(
    f"N_universo_total={ext['N_universo_total']} "
    f"N_excluidos_institucional={ext['N_excluidos_institucional']} "
    f"N_excluidos_presup={ext['N_excluidos_presup']} "
    f"N_supervivientes={ext['N_supervivientes']}"
)
print(
    "Posiciones 1-21 del array survivors coinciden exactamente con "
    "enumeracion.md §5 (1-12) y contrato §2 (13-21), mismo orden."
)
sys.exit(0)
