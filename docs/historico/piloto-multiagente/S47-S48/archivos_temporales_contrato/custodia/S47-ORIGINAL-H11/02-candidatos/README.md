# 02 — Candidatos

- `enumeracion.md` — trazabilidad completa del algoritmo §7.1 (semillas
  S1-S4, expansión C1-C5, filtros F-DT.1-F-DT.4, contadores del universo).
- `descartados.md` — los 8 clusters excluidos institucionalmente (F-DT.1) y
  el registro de que F-DT.3/F-DT.4 no excluyeron ninguno.
- `01-*.md` … `12-*.md` — las 12 fichas completas materializadas dentro del
  presupuesto `UMBRAL_P_STOP_FICHAS=12`, en el mismo orden de `clave_orden`
  en que se enumeraron.

## Resumen de veredictos individuales

| # | Candidato | LOC | S1 | S7 | Veredicto |
|---|---|---|---|---|---|
| 1 | `_delete_copper` (núcleo borrado cobre) | 188 | NO cumple | cumple (a,c) | **NO_APTO** |
| 2 | `_audit_error` | 8 | cumple | NO cumple | **NO_APTO** |
| 3 | `get_footprint_neighbors` (vecindad geométrica) | 207 | NO cumple | cumple (a,c) | **NO_APTO** |
| 4 | `_bbox_distance_to_point` | 11 | cumple | NO cumple | **NO_APTO** |
| 5 | `_copper_distance_mm`+`_dist_point_segment` | 30 | cumple | NO cumple | **NO_APTO** |
| 6 | `_copper_in_bbox` | 12 | NO cumple | NO cumple | **NO_APTO** |
| 7 | `_copper_on_layer` | 6 | cumple | NO cumple | **NO_APTO** |
| 8 | `move_footprint` (post-mutación) | 216 | NO cumple | cumple (a,c) | **NO_APTO** |
| 9 | `add_track` (resolución endpoints) | 332 | NO cumple | cumple (a,c) | **NO_APTO** |
| 10 | `draw_board_outline` | 87 | NO cumple | cumple (a, margen mínimo) | **NO_APTO** |
| 11 | `_resolve_board` | 9 | cumple | NO cumple | **NO_APTO** |
| 12 | `_segment_intersects_bbox` | 34 | cumple | NO cumple | **NO_APTO** |

**0 de 12 candidatos materializados alcanzan `APTO` o `APTO_CONDICIONAL`.**

## Patrón estructural dominante (ver `03-refutacion.md` para el análisis
formal completo)

Dos familias de motivo de rechazo, ninguna arbitraria:

1. **Candidatos con closure (`@mcp.tool`) de tamaño sustancial** (fichas 1,
   3, 8, 9, 10 — los 5 únicos que satisfacen S7 cuantitativamente):
   todos dependen de un trío de helpers de fan-in muy alto que permanece en
   `pcb.py` (`_audit_error` 11 consumidores, `_resolve_board` 17,
   `_similars` ≥9) y/o de `_segment_intersects_bbox`. Bajo el diseño de
   extracción mínimo (mover + wrapper delgado en `register()`), **no existe
   ninguna combinación que satisfaga simultáneamente S1 (sin arista de
   vuelta al módulo pcb.py) y S8 (M2 no empeora)** — importar de vuelta
   viola S1; inyectar como parámetro explícito preserva S1 pero empeora d1,
   violando S8. Ambos gates son no dispensables por E1/E2/E3 (§11.7).

2. **Candidatos helper-only pequeños** (fichas 2, 4, 5, 6, 7, 11, 12 — LOC
   entre 6 y 34): ninguno alcanza los umbrales cuantitativos de S7
   (`UMBRAL_S7_LOC=80`, `UMBRAL_S7_CLOSURES=3`, `UMBRAL_S7_PCB_LOC=100` —
   los tres muy por encima de cualquiera de estos candidatos) y S7.d
   ("eliminación demostrable de responsabilidad mezclada") no es
   argumentable: son funciones ya cohesivas y de responsabilidad única —
   extraerlas relocaliza código limpio sin eliminar ninguna mezcla. Sin
   base para E1.

**Consecuencia para H4** (§3 del contrato: "La reducción de LOC de
`register()` es por sí sola proxy suficiente de deuda"): **REFUTADA**, con
cinco contraejemplos concretos (fichas 1, 3, 8, 9, 10) donde una reducción
sustancial de LOC (85 a 167 líneas de `register()`, 87 a 332 de `pcb.py`) no
viene acompañada de ninguna mejora en el vector M2 bajo el diseño de
extracción mínimo — la mejora de M1 es, en los cinco casos, cosmética
(relocalización de líneas) sin reducción de acoplamiento estructural. CR7
(§4 del contrato) → **REFUTADA** con la misma evidencia.

Ver `03-refutacion.md` para CR1-CR8, H1-H4 y el detalle formal S1-S8/R1-R14
consolidado.
