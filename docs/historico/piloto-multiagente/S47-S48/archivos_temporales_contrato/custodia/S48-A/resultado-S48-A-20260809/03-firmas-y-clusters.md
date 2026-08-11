# 03 — Firmas y clusters (Q4)

Método: §8.6 del contrato. Agrupación **determinista** por firma exacta
(vector completo de 21 señales canónicas, incluyendo `NA` en su posición
exacta — no solo el subconjunto de señales activas). Es el resultado
primario de Q4; el clustering exploratorio adicional se evaluó y no aportó
información no capturada ya por la agrupación determinista (ver
`CLUSTERING_NO_CONCLUYENTE` al final).

## Firmas exactas observadas (7 grupos, 21 candidatos)

### Grupo A — 6 candidatos: `{S7, S8_R11}` activas, `S1=0` explícito

`_bbox_distance_to_point`, `_copper_distance_mm + _dist_point_segment`,
`_copper_on_layer`, `_resolve_board`, `_segment_intersects_bbox`,
`_similars`.

Todos declaran `S1: cumple` explícitamente y `S4: no_determinante`
(`COBERTURA_INFERIDA`, sin test focal directo). Cinco del paquete original
(fichas 4, 5, 7, 11, 12) + una de la extensión (ficha 13, `_similars`).
Patrón: helper puro de tamaño mínimo (6–34 LOC), sin closure, sin
dependencias salientes propias, `S7` no se satisface por tamaño y `S8_R11`
tampoco (M2 no domina, cumple solo por igualdad).

### Grupo B — 5 candidatos: `{S7, S8_R11}` activas, `S1=NA`, `S4=0` explícito

`delete_track`, `delete_via`, `get_component_detail`,
`reload_board_from_disk`, `save_board`.

Distinta de Grupo A pese a compartir el mismo **conjunto** de señales
activas: aquí `S1` queda `no_determinante` (no `cumple` explícito) y `S4`
es `cumple` explícito (`COBERTURA_DEMOSTRADA`, no `no_determinante`). Las
cinco fichas de este grupo citan literalmente la misma fórmula
("`S7` rechaza primero", corrección `C-EXT-03`) para justificar por qué no
se afirma el estado de `S1` bajo extracción proyectada. Las 5 son de la
extensión corregida (fichas 15, 16, 17, 19, 20).

**OBSERVACION metodológica (Q5).** La distinción entre Grupo A y Grupo B no
es estructural sino **documental**: es una diferencia en la convención de
evaluación entre el paquete original y la extensión corregida (el paquete
original evalúa `S1` incondicionalmente incluso cuando `S7` ya decide el
veredicto; la extensión, tras la corrección `C-EXT-03`, se abstiene de
afirmar `S1` bajo extracción cuando `S7` es determinante). Ambos grupos
llegan al mismo veredicto individual `NO_APTO`.

### Grupo C — 4 candidatos: `{S1, R12}` activas

`get_footprint_neighbors`, `move_footprint`, `add_track`,
`draw_board_outline`. Los 4 restantes de los 5 candidatos con closure
sustancial del paquete original (junto con `_delete_copper`, que forma su
propio grupo E por activar una tercera señal). `S7` cumple (closure grande,
`S7.a`/`S7.c` satisfechos); `S1` no cumple por dependencia hacia el trío
`_audit_error`/`_resolve_board`/`_similars` (Ruta A); `S8_R11` queda `NA`
porque `S8` es `no_determinante` bajo Ruta A y `R11` no se declaró
explícitamente para estos 4 (solo se declaró `R12`).

### Grupo D — 3 candidatos: `{S8_R11, R12}` activas, `S1=NA`

`{_via_params, add_via}`, `get_tracks`, `set_footprint_ref`. Los tres
candidatos de la extensión que sí satisfacen `S7` cuantitativamente. Aquí
`S8` **sí** se declara `no_cumple` explícito bajo ambas rutas (a diferencia
del Grupo C), por lo que `S8_R11=1`; `S1` queda `no_determinante` por el
fraseo dual "Ruta A / Ruta B" explícito de estas tres fichas.

### Grupo E — 1 candidato: `{S1, S8_R11, R12}` — único con 3 señales activas

`_delete_copper` (núcleo de borrado de cobre, ficha 1). Único candidato de
los 21 donde `S1` es `no_cumple` explícito, `R12` está `activado`
explícito Y adicionalmente `R11` está `activado` explícito (bajo Opción B),
lo que hace `S8_R11=1` por la vía de `R11` aunque `S8` en sí quede
`no_determinante`. Es el único candidato del universo con **3** señales
canónicas activas en vez de 2.

### Grupo F — 1 candidato: `{S7, S8_R11}` + `R7=0` explícito

`_audit_error` (ficha 2). Comparte el conjunto activo con el Grupo A, pero
es el **único** candidato de los 21 con una declaración explícita de `R7`
(`no_activado`, "R7 no se activa" — ver `01a-ontologia-y-derivaciones.md`),
lo que lo separa como firma propia bajo agrupación exacta.

### Grupo G — 1 candidato: `{S1, S7}` activas, `S8_R11=NA`

`_copper_in_bbox` (ficha 6). Único candidato con esta firma: comparte el
patrón estructural de S1 con el Grupo C (dependencia hacia
`_segment_intersects_bbox` fuera de K, mismo motivo que fichas 3/8/9/10),
pero su ficha **no declara** `R12` ni ningún estado de `S8`/`R11`
explícitamente — es la ficha con cobertura declarativa más delgada del
universo (ver `01a-ontologia-y-derivaciones.md`, `05-hallazgos-meta.md`
`H-S48A-01`). `HIPOTESIS`: si la ficha 6 hubiera declarado `R12`
explícitamente con el mismo razonamiento que sus pares estructurales
(fichas 3, 8, 9, 10), este candidato probablemente se uniría al Grupo C en
vez de permanecer aislado — no verificable con la evidencia disponible, la
ficha no lo declara y este análisis no infiere desde el código.

## Resumen

| Grupo | Candidatos | Firma activa |
|---|---:|---|
| A | 6 | `S7`, `S8_R11` |
| B | 5 | `S7`, `S8_R11` (S1/S4 declarados distinto de A) |
| C | 4 | `S1`, `R12` |
| D | 3 | `S8_R11`, `R12` |
| E | 1 | `S1`, `S8_R11`, `R12` |
| F | 1 | `S7`, `S8_R11` (+ `R7` explícito) |
| G | 1 | `S1`, `S7` |

Todos los 21 candidatos caen en exactamente uno de 7 grupos deterministas;
ningún candidato queda sin firma asignada.

## Clustering exploratorio adicional

Se evaluó agrupar por distancia sobre el vector canónico completo (método
alternativo al de firma exacta). El resultado coincide exactamente con la
agrupación determinista de arriba (las mismas 7 particiones aparecen bajo
cualquier métrica de distancia razonable sobre un espacio de 21 dimensiones
binarias/NA con tan pocas señales activas por fila). No aporta información
adicional. Se declara explícitamente: el clustering exploratorio no es
concluyente como método adicional independiente — la agrupación
determinista de firma exacta ya es la partición más fina y correcta posible
sobre estos datos. `CLUSTERING_NO_CONCLUYENTE` respecto de aportar una
partición *distinta*; la partición determinista de arriba sí es el
resultado primario válido de Q4.
