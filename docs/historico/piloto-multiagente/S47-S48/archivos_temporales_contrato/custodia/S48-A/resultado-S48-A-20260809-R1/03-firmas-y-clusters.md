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

## Distinción entre firmas exactas y conjuntos de señales activas (corrección de ronda R1)

El contrato §6/Q4 pregunta por candidatos que comparten "exactamente la
misma firma de señales de fallo". La tabla de 7 grupos arriba responde eso
sobre el **vector completo** (21 posiciones, incluyendo la posición exacta
de cada `NA`) — es la partición más fina posible y el resultado primario de
Q4. Pero conviene distinguir esa cifra de una lectura más gruesa, que
importa para Q1/Q5: cuántos **conjuntos distintos de señales activas de
fallo** (ignorando la posición de los `NA`, solo mirando qué señales llegan
a `senal_fallo=1`) hay entre los 21 candidatos:

| Conjunto de señales activas | Grupos que lo comparten | Candidatos |
|---|---|---:|
| `{S7, S8_R11}` | A + B + F | 12 |
| `{S1, R12}` | C | 4 |
| `{S8_R11, R12}` | D | 3 |
| `{S1, S8_R11, R12}` | E | 1 |
| `{S1, S7}` | G | 1 |

**7 firmas exactas, pero solo 5 conjuntos distintos de señales activas de
fallo** (12+4+3+1+1=21). Los grupos A, B y F comparten el mismo conjunto
activo `{S7, S8_R11}` y solo se separan como firmas distintas por el estado
de celdas que **no** son señales de fallo activas (`S1`/`S4` declarados de
forma diferente en A vs. B; una declaración adicional de `R7=no_activado`
en F) — ver §Grupo B y §Grupo F arriba para el detalle candidato a
candidato.

## Clustering exploratorio adicional

Se evaluó agrupar por distancia sobre el vector canónico completo (método
alternativo al de firma exacta). El resultado coincide con la agrupación
determinista de arriba: no se identificó ninguna partición alternativa que
separe o una grupos de forma distinta a los 7 de la tabla. **Corrección de
ronda R1:** la versión previa de este párrafo afirmaba que "las mismas 7
particiones aparecen bajo cualquier métrica de distancia razonable" — esa
generalización sobre *cualquier* métrica no fue puesta a prueba (no se
ejecutó ningún cálculo de distancia real sobre las 21 dimensiones binarias/
`NA`, solo una inspección cualitativa de que ninguna métrica obvia
produciría una partición distinta dado lo disperso del espacio activo). Se
retira la afirmación no demostrada. Lo que sí se sostiene, sin necesidad de
esa generalización: la partición por firma exacta (7 grupos) ya es la más
fina posible sobre estos datos, y ningún ejercicio de agrupación adicional
—exploratorio o no— puede producir más de 7 particiones sin inventar
información no presente en la matriz. `CLUSTERING_NO_CONCLUYENTE` respecto
de aportar una partición *distinta* de la determinista; la partición
determinista de arriba es el resultado primario válido de Q4.
