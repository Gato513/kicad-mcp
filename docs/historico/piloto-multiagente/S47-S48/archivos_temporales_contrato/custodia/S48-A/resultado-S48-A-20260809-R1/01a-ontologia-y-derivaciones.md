# 01a — Ontología y derivaciones

## Derivación normativa (contrato §7.3): `S8_R11`

El contrato S48-A declara textualmente (§7.3): "El contrato S47 v6 declara que
R11 se activa cuando S8 falla por ausencia de dominancia/no-empeoramiento
[...] `S8=no_cumple` y `R11=activado` representan una sola señal
observacional [...] Q2–Q4 usan una señal canónica `S8_R11` y no cuentan S8 y
R11 por separado."

Fuente en v6 (`CONTRATO-AUDITADO.md`, ambos paquetes, hash `3b16079c…1402`,
coincide con contrato §2.3):

> "R11 activada por S8 sin dominancia." — `CONTRATO-AUDITADO.md §11.5`

Regla de construcción de la señal canónica `S8_R11` para un candidato dado:

```text
S8_R11 = 1 (activada) si S8.estado_fuente == "no_cumple"
                      O R11.estado_fuente == "activado"
S8_R11 = 0 si S8.estado_fuente == "cumple" Y R11 no está declarado activado
S8_R11 = NA en cualquier otro caso (ambos no_determinante/no_evaluado_o_na)
```

En las agregaciones de §8.4–§8.6 (`02-frecuencias-y-coocurrencias.md`,
`03-firmas-y-clusters.md`) se usa exclusivamente `S8_R11`; `S8` y `R11`
individuales **no** se cuentan por separado como señales independientes,
conforme al mandato de §7.3. La matriz base (`01-matriz-refutacion.csv`)
conserva ambos estados fuente por separado, por transparencia — el filtro se
aplica solo en la agregación, no en la extracción, tal como exige el
contrato.

## Otras derivaciones consideradas

El contrato (§7.3) autoriza documentar derivaciones adicionales "solo cuando
la derivación está citada en el contrato v6 o demostrada textualmente en las
fichas". Se revisaron las 21 fichas buscando pares R↔R o S↔R citados
explícitamente con ese carácter (no solo co-ocurrencia estructural). No se
encontró ninguna declaración textual de derivación adicional en las 21
fichas ni en `CONTRATO-AUDITADO.md §§11.4/11.5/11.7` más allá de `R11↔S8`.

En particular, **no** se trata como derivación el patrón recurrente
"R12 (Ruta A) o R11 (Ruta B)" que aparece en 8 candidatos (fichas 1, 3, 8, 9,
10, 14, 18, 21): ambos criterios se activan bajo rutas de diseño mutuamente
excluyentes documentadas explícitamente en cada ficha, no son el mismo evento
observacional visto desde dos ángulos (a diferencia de `S8_R11`, que sí lo
es por declaración expresa de v6). Se preservan como señales independientes
en la matriz y en `02-frecuencias-y-coocurrencias.md` §Q3, con la
observación `"condicionado a Ruta A"` / `"condicionado a Ruta B"` en la
columna `observacion` de cada celda correspondiente.

## Criterios sin ninguna declaración en las 21 fichas

R2, R3, R4, R5, R6, R8, R9, R10, R13, R14 no aparecen declarados
explícitamente en ninguna de las 21 fichas (ni como activados ni como
descartados) ni en las secciones de síntesis (`03-refutacion.md`,
`03-refutacion-ext.md`). Quedan `no_evaluado_o_na` en la matriz, fuente
`"ausencia declarada"`, en las 21 filas correspondientes. No se infiere su
estado desde el patrón estructural de la ficha ni desde el código —
conforme a la regla de §7.2 ("no se infiere desde el código").

R1 tiene una única declaración explícita, en la ficha 1 (`no_activado`,
"bridge sí es inyectable/ya lo es en el patrón register_x existente"); en
las 20 fichas restantes no hay declaración de R1 y queda
`no_evaluado_o_na`.

R7 tiene una única declaración explícita, en la ficha 2 ("R7 no se activa",
sección S2); en las 20 fichas restantes no hay declaración de R7 y queda
`no_evaluado_o_na`. Nota: la mención recurrente de `UMBRAL_R7_REEXPORTS` en
otras fichas (p. ej. 4, 11, 13) es una cita del umbral numérico, no una
declaración del estado del criterio R7 — no se cuenta como tal (distinción
verificada línea por línea sobre las 21 fichas).

## Ficha con cobertura declarativa incompleta

La ficha 6 (`_copper_in_bbox`, paquete original) declara explícitamente solo
4 de los 8 gates S (S1, S7 con verdicto; menciona el M2 pero no cierra S2–S6
ni S8 con una palabra de estado) y **ningún** criterio R, pese a que su
patrón estructural (S1 no cumple por dependencia hacia
`_segment_intersects_bbox` fuera de K) es idéntico al de las fichas 1, 3, 8,
9, 10 y 14/18/21, todas las cuales sí declaran R12 explícitamente para ese
mismo patrón. La matriz respeta la ausencia literal: las celdas no
declaradas de la ficha 6 quedan `no_evaluado_o_na`, sin inferir R12 por
analogía estructural. Ver `05-hallazgos-meta.md` `H-S48A-01`.

**Precisión de ronda R1:** la ficha 6 sí contiene una declaración textual de
S8 ("Opción B: inyectarlo como parámetro -> d1 pasa de 0 a 1, EMPEORA esa
dimensión ... S8 no cumple"), inline dentro de su bloque de S1/M2, sin
encabezado propio `## S8`. La caracterización de este mismo párrafo ("no
cierra S2–S6 ni S8 con una palabra de estado") era imprecisa para S8
específicamente. Esta precisión **no cambia ninguna celda de la matriz**: el
criterio de extracción de `01-matriz-refutacion.csv` exige un encabezado o
declaración formal por gate, y S8 en la ficha 6 es condicional a la Opción B
(igual que en la ficha 1, donde también queda `NA` porque el estado depende
de la ruta de diseño, no de un veredicto único). El estado
`no_evaluado_o_na` de S8 en la fila de la ficha 6 se conserva sin
alteración — corregir la celda excede el alcance autorizado de esta ronda
(§10.2 del contrato, solo los 6 puntos listados en `00-preflight.md` §8.4).

## Operacionalización de la Regla 3 de la fe de erratas (ronda R1, columna `convencion_a`)

Fuente: fe de erratas ejecutiva, contrato S47 v6, SHA-256
`63fe27be8ca2fa852d2f5dfef3996549edcced710b2b67275b970c19a36dcdd4`
(verificado en `00-preflight.md` §8.1), Regla 3 (§2):

> "Si el ejecutor encuentra que dos estados no admiten una comparación
> homogénea limpia sobre un candidato concreto, el candidato se documenta
> cualitativamente con las dimensiones que sí son comparables, se declara
> la limitación en la ficha, y S8/R11 se evalúan según el juicio del
> ejecutor con evidencia registrada."

La Regla 3 no introduce un rótulo nuevo ("Convención A" tampoco aparece en
la fe de erratas); describe una **conducta** de evaluación. Para clasificar
los 21 candidatos según si esa conducta ocurrió, se define un predicado de
tres estados sobre cada ficha, aplicado por lectura directa de su sección
M2/S8, sin inferencia desde el código:

```text
aplicada            la ficha declara explícitamente que la comparación
                     M2_actual vs. M2_proyectado no es homogénea/limpia bajo
                     al menos una ruta de diseño (p. ej. "S8 no llega a
                     evaluarse con sentido bajo Opción A"), documenta la
                     dimensión que sí resulta comparable bajo la otra ruta
                     (p. ej. d1 empeora bajo Opción B), y resuelve S8/R11/R12
                     por ese juicio cualitativo con la evidencia citada.

ausencia_explicita  la ficha SÍ completa una comparación homogénea de
                     M2_actual vs. M2_proyectado (igualdad exacta, o vector
                     proyectado completo bajo cada ruta con veredicto
                     definitivo) y no declara ninguna limitación de
                     comparabilidad — la vía cualitativa de la Regla 3
                     simplemente no fue necesaria en este candidato.

no_determinable      la ficha nunca computa M2_proyectado (S7 decide el
                     veredicto primero, corrección de diseño C-EXT-03, o la
                     ficha no llega a esa sección) — el antecedente de la
                     Regla 3 ("dos estados [...] sobre un candidato
                     concreto") no llega a ponerse a prueba, y no hay base
                     textual para clasificar en ninguno de los dos estados
                     anteriores.
```

### Clasificación resultante (21/21, evidencia citada por candidato)

| # | Candidato | `convencion_a` | Anclaje textual |
|---:|---|---|---|
| 1 | `_delete_copper` | `aplicada` | "Bajo Opción A ... S8 no llega a evaluarse con sentido (S1 ya falló, R12 activo). Bajo Opción B ... S8 falla (d1 empeora)" |
| 2 | `_audit_error` | `ausencia_explicita` | "cumple trivialmente por igualdad ... pero no domina" — comparación única resuelta, sin declarar no-homogeneidad ni ruta dual |
| 3 | `get_footprint_neighbors` | `aplicada` | "S8 — falla bajo Opción B; no evaluable con sentido bajo Opción A (S1 ya falló)" |
| 4 | `_bbox_distance_to_point` | `ausencia_explicita` | "M2_proyectado = M2_actual (extracción pura sin cambio) → S8 cumple por igualdad" |
| 5 | `_copper_distance_mm` | `ausencia_explicita` | "M2_proyectado = M2_actual bajo diseño mínimo (1 reexport) — cumple por igualdad" |
| 6 | `_copper_in_bbox` | `no_determinable` | Ficha declarativamente incompleta (`H-S48A-01`); sin sección M2_proyectado dual explícita — sin base para clasificar con la misma solidez que 1/3/8/9/10 |
| 7 | `_copper_on_layer` | `ausencia_explicita` | "S8: M2_proyectado = M2_actual (igualdad)" |
| 8 | `move_footprint` | `aplicada` | "S8 — falla bajo Opción B; no evaluable con sentido bajo Opción A" |
| 9 | `add_track` | `aplicada` | "S8 — falla bajo Opción B; no evaluable con sentido bajo Opción A" |
| 10 | `draw_board_outline` | `aplicada` | "S8 — falla bajo Opción B; no evaluable con sentido bajo Opción A" |
| 11 | `_resolve_board` | `ausencia_explicita` | "S8: M2_proyectado = M2_actual bajo diseño mínimo (1 reexport preserva ...)" |
| 12 | `_segment_intersects_bbox` | `ausencia_explicita` | "S8: M2_proyectado = M2_actual (igualdad, diseño mínimo con 1 reexport)" |
| 13 | `_similars` | `ausencia_explicita` | "M2_proyectado = (0,0,0,1,9): igual al actual ... S8 cumple por igualdad, no por dominancia" |
| 14 | `add_via`/`_via_params` | `ausencia_explicita` | Ambas rutas computadas y cerradas con veredicto definitivo: "S8: NO cumple en ninguna de las dos rutas", sin declarar limitación de comparabilidad |
| 15 | `delete_track` | `no_determinable` | "S7 rechaza primero ... S8: no determinante (S7 ya falla)" — M2_proyectado nunca se computa (C-EXT-03) |
| 16 | `delete_via` | `no_determinable` | ídem patrón C-EXT-03 |
| 17 | `get_component_detail` | `no_determinable` | ídem patrón C-EXT-03 |
| 18 | `get_tracks` | `ausencia_explicita` | "S8: NO cumple en ninguna ruta (peor caso de los 9)" — ambas rutas computadas y cerradas |
| 19 | `reload_board_from_disk` | `no_determinable` | ídem patrón C-EXT-03 |
| 20 | `save_board` | `no_determinable` | ídem patrón C-EXT-03 |
| 21 | `set_footprint_ref` | `ausencia_explicita` | "S8 falla" bajo Ruta B con `d1` cuantificado, Ruta A resuelta por S1/R12, sin declarar no-homogeneidad |

**Distribución:** `aplicada` = 5 (fichas 1, 3, 8, 9, 10 — coinciden
exactamente con Grupo C + Grupo E de `03-firmas-y-clusters.md`);
`ausencia_explicita` = 10 (fichas 2, 4, 5, 7, 11, 12, 13, 14, 18, 21);
`no_determinable` = 6 (fichas 6, 15, 16, 17, 19, 20). 5+10+6=21.

Nota de límite del juicio: la distinción entre `aplicada` (5) y las fichas
de ruta dual sin declaración de no-homogeneidad (14, 18, 21) es la más fina
del corpus — estas tres también evalúan Opción A/Ruta A y Opción B/Ruta B,
pero a diferencia de 1/3/8/9/10 sí logran cerrar S8 con un veredicto
cuantificado bajo cada ruta ("NO cumple en ninguna ruta", con `d1` numérico
citado), sin declarar la comparación como no-homogénea. Esta clasificación
es un juicio del ejecutor con evidencia registrada, tal como la Regla 3 lo
prevé explícitamente ("Codex puede refutar el juicio; el humano decide") —
no una medición mecánica.
