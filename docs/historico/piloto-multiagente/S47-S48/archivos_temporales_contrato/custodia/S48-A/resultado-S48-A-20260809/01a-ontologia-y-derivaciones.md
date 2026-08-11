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
