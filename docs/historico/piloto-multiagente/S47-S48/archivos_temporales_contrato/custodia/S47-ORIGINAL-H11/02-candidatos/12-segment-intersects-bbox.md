# Ficha 12 — `_segment_intersects_bbox`

```
K = {_segment_intersects_bbox}   (LOC=34, L382-415)
```

Semilla S3 (2 consumidores: `_copper_distance_to_bbox` [ficha 3],
`_copper_in_bbox` [ficha 6]).

**M2:** d1=0, d2=0 — hoja del grafo V-interno: define `orientation`/
`on_segment` como funciones anidadas LOCALES (no miembros de V, por
diseño §2 de `01-inventario-actual.md`: solo closures directas de
`register()` y helpers top-level cuentan como V; funciones anidadas dentro
de un helper top-level son detalle interno). d3=0. d4=1. d5=2
(`entrante_interna={_copper_distance_to_bbox, _copper_in_bbox}`).
`M2_actual_vector=(0,0,0,1,2)`.

**S1:** cumple (d2=0 — el candidato más "limpio" en aislamiento de los 12,
sin ninguna dependencia hacia otros miembros de V; sus dos funciones
anidadas locales viajan con él sin generar frontera).
**S2:** cumple, 1 reexport.
**S3:** simple (34 líneas, función pura autocontenida con matemática de
orientación/intersección de segmentos).
**S4:** sin test focal directo; `COBERTURA_INFERIDA` vía sus 2
consumidores (ambos igualmente sin test focal directo, cobertura transitiva
de tercer nivel — la cadena más larga sin aserción directa de los 12
candidatos).

**S5:** cumple. **S6:** `REFERENCIA_EXISTENTE`, con la misma nota de
adyacencia temática con DT3 que fichas 3/4/5/9 (geometría en `tools/`, no
en `bridge/`).

**S7:** NO cumple ninguna cuantitativa (0<80, 0<3, 34<100). S7.d no
demostrable: algoritmo de intersección de segmentos ya autocontenido y de
responsabilidad única.

**S8:** M2_proyectado = M2_actual (igualdad, diseño mínimo con 1 reexport).

**R activado:** R11.

**Veredicto individual: NO_APTO.** Nota: este es el ÚNICO de los 12
candidatos donde S1 se cumple con margen amplio (cero dependencias
salientes, incluso hacia el trío `_audit_error`/`_resolve_board`/
`_similars`) — si el criterio de selección para S48 privilegiara "menor
riesgo de romper S1" sobre "mayor LOC", este candidato (junto con fichas 2,
4, 5, 7, 11) sería preferible a los 5 candidatos más grandes, pese a no
alcanzar S7. Señal para H11/H5 (alternativa secundaria).
