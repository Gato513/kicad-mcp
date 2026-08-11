# Ficha 18 — `get_tracks`

```
K = {get_tracks}   (LOC=86, L1749-1834, @mcp.tool closure, no mutante)
```

**Nota de divergencia LOC (H-S47EXT-01):** `enumeracion.md §6`/contrato §2
anotan LOC=92. Re-derivación de esta sesión: LOC=86. Ver
`04-hallazgos-fuera-de-scope-ext.md`. **No altera el veredicto** — con
ambos valores S7.a se satisface (86 ≥ 80 y 92 ≥ 80); el gate determinante
sigue siendo S1/S8, evaluado abajo con evidencia real.

## M1 — Volumen

LOC actual = 86. 1 closure eliminada de `register()`. Reducción de `pcb.py`
= 86 LOC.

## M2 — Acoplamiento

```
M2_actual_vector = (d1=1, d2=6, d3=4, d4=0, d5=0)
d1_simbolos: ['bridge']
d2_aristas: [
  ['get_tracks','_TRACKS_BUDGET_SAFETY','CONSTANT_READ'],
  ['get_tracks','_TRACKS_DEFAULT_BUDGET','CONSTANT_READ'],
  ['get_tracks','_copper_in_bbox','CALL'],
  ['get_tracks','_copper_on_layer','CALL'],
  ['get_tracks','_resolve_board','CALL'],
  ['get_tracks','_similars','CALL']
]
d3_modulos: ['..errors', '..logging_config', '..snapshots', '.pcb_encoders']
d4_simbolos: []
d5_detalle: entrante_interna=[], entrante_src=[], entrante_tests=[]
```

`get_tracks` es el candidato con **mayor `d2`** de los 9 (6 cortes hacia
`pcb.py`): 2 constantes de módulo (`_TRACKS_BUDGET_SAFETY`,
`_TRACKS_DEFAULT_BUDGET`) + 4 llamadas (`_copper_in_bbox` ficha 6 original
NO_APTO, `_copper_on_layer` ficha 7 original NO_APTO, `_resolve_board`
ficha 11 original NO_APTO, `_similars` ficha 13 esta extensión NO_APTO).
Ninguno de los cuatro helpers ni las dos constantes se propone mover junto
con este cluster.

**Ruta A — reexport natural:** 6 aristas módulo-nuevo → `pcb.py`. **S1
falla** con el margen más amplio de los 9 candidatos (6 aristas, vs. 3 en
add_via/set_footprint_ref). Activa **R12**.

**Ruta B — inyección explícita por parámetro:**
```
M2_proyectado(Ruta B) = (d1=7, d2=0, d3=4, d4=0, d5=0)
```
`d1` empeora 1→7 (el peor deterioro de M2 entre los 9 candidatos). **S8
falla** con claridad. Activa **R11**.

Ninguna ruta satisface S1 y S8 simultáneamente. Con 6 dependencias
cruzadas, `get_tracks` es el ejemplo más nítido de los 9 del mismo patrón
ya documentado para las fichas 1, 3, 8, 9, 10 del paquete original.

## M3 — Superficie observable

`@mcp.tool(name="get_tracks")`, no mutante. Códigos de error [F3]:
`INVALID_PARAMS` (sin filtro, bbox malformado), `NET_NOT_FOUND`,
`CONTEXT_BUDGET_IMPOSSIBLE`. Usa `_encode_tracks` de `pcb_encoders.py`
(sanitiza `net_name`/`pad.number` incl. `_sanitize_space_delimited`, regla
de código 6). Bajo cualquier ruta de extracción, la firma `@mcp.tool` y los
códigos de error se preservan — S2 cumple independientemente del resultado
de S1/S8.

## M4 — Cobertura

`COBERTURA_DEMOSTRADA`: 6 tests offline con assert
(`tests/test_pcb_session16.py`: requires-a-filter, by-net, net-not-found,
bbox-crops-crossing-segment, layer-filter, context-budget-impossible) + 1
test offline sin assert directo (`_pick_free_stub`, helper de fixture, no
cuenta) + 8 tests `integration_gui`/`integration_gui_slow`.

## Gates S1–S8

**S1:** NO cumple (Ruta A) / cumple con degradación S8 (Ruta B).
**S2:** cumple.
**S3:** simple (mover 1 función, wrapper delgado).
**S4:** cumple, `COBERTURA_DEMOSTRADA`.
**S5:** cumple (lectura de cobre, no toca zonas ni route_board).
**S6:** `REFERENCIA_EXISTENTE` (lectura de tracks/vías, sin relación con
DT3/P1-2 — aparece en tests GUI de zonas/rerouting solo como consumidor de
verificación, no como implementación de geometría de zona).
**S7:** cumple por S7.a (86 ≥ 80).
**S8:** NO cumple en ninguna ruta (peor caso de los 9: d2=6 / Δd1=+6).

**R activado:** R12 (Ruta A) o R11 (Ruta B, el deterioro de M2 más grande
de los 9 candidatos evaluados en esta extensión). No dispensables.

## Veredicto individual: **NO_APTO** (S1 o S8, ninguna dispensable)

Rederivado de forma independiente sobre las 6 dependencias reales de
`get_tracks` — no se copió la conclusión de ningún candidato del paquete
original; el patrón coincide porque la causa estructural (helpers
compartidos de fan-in alto sin mover) es la misma en todo `pcb.py`.
