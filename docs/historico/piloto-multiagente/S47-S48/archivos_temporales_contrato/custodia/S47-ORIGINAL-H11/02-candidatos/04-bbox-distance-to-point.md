# Ficha 4 — `_bbox_distance_to_point`

```
K = {_bbox_distance_to_point}   (LOC=11, L311-321)
```

Semilla S3 (3 consumidores: `_closest_point_copper_bbox`,
`_copper_distance_to_bbox`, `get_footprint_neighbors` — todos fuera de K,
parte de la ficha 3).

**M2:** d1=0, d2=0 (hoja, sin llamadas salientes a V), d3=0 (sin imports
externos propios más allá de tipos), d4=1, d5=3
(`entrante_interna={_closest_point_copper_bbox, _copper_distance_to_bbox,
get_footprint_neighbors}`). `M2_actual_vector=(0,0,0,1,3)`.

**S1:** cumple (d2=0, sin riesgo de ciclo).
**S2:** cumple con 1 reexport (d4=1, bien bajo `UMBRAL_R7_REEXPORTS=3`).
**S3:** simple (función pura de 11 líneas).
**S4:** sin test focal directo; `COBERTURA_INFERIDA` vía los 3 consumidores
(uno de ellos, `get_footprint_neighbors`, con evidencia offline+assert —
ficha 3 §S4).
**S5:** cumple. **S6:** `REFERENCIA_EXISTENTE` (geometría en `tools/`, no en
`bridge/`, mismo razonamiento que ficha 3).

**S7:** NO cumple ninguna cuantitativa (0<80, 0<3, 11<100) — no es closure,
LOC trivial. S7.d no demostrable: función de una sola expresión matemática
(distancia punto-bbox), sin mezcla de responsabilidad que eliminar.

**M2_proyectado = M2_actual** (extracción pura sin cambio de ninguna
dimensión bajo el diseño mínimo con 1 reexport) → S8 cumple por igualdad,
no domina.

**R activado:** R11 (beneficio marginal — S7 no se satisface, extraer 11
líneas con 3 consumidores compartidos no reduce deuda estructural
medible).

**Veredicto individual: NO_APTO** (S7 sin dispensa E1 defendible; la
"responsabilidad" ya es única y estrecha).
