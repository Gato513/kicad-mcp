# 02 — Frecuencias y coocurrencias (Q1, Q2, Q3)

Método: §8.4–8.5 del contrato. Denominador fijo: 21 candidatos. Señal
canónica `S8_R11` conforme a `01a-ontologia-y-derivaciones.md` (S8 y R11 no
se cuentan por separado). Fuente: `01-matriz-refutacion.csv`, rederivable
celda a celda.

## Q1 — ¿Sistemática o dispersa?

Histograma de "número de señales canónicas activas por candidato" (21
señales canónicas posibles: S1–S7, `S8_R11`, R1–R10, R12–R14):

| Nº de señales activas | Candidatos |
|---:|---:|
| 3 | 1 |
| 2 | 20 |

**OBSERVACION.** La distribución está fuertemente concentrada: 20/21
candidatos (95 %) fallan por exactamente **2** señales canónicas, y 1/21 por
3. Ningún candidato activa una señal aislada ni más de 3. En ese sentido
estricto (cardinalidad de señales por candidato), el patrón es
**sistemático por volumen** — casi todos fallan por el mismo número de
motivos — pero, como muestra Q2, **no** por el mismo motivo único: dos
señales (`S7`, `S8_R11`) concentran la enorme mayoría de la actividad, con
una tercera (`R12`) como segundo eje minoritario. Ver Q4 para la
composición exacta de qué par de señales activa cada candidato.

## Q2 — Frecuencia por señal canónica

| Señal | Activaciones/21 | % | Banda | `NA` en la señal |
|---|---:|---:|---|---:|
| `S8_R11` | 16 | 76.2 % | ≥50 % | 5 |
| `S7` | 13 | 61.9 % | ≥50 % | 0 |
| `R12` | 8 | 38.1 % | 25–<50 % | 13 |
| `S1` | 6 | 28.6 % | 25–<50 % | 8 |
| `S2` | 0 | 0.0 % | <25 % | 1 |
| `S3` | 0 | 0.0 % | <25 % | 6 |
| `S4` | 0 | 0.0 % | <25 % | 9 |
| `S5` | 0 | 0.0 % | <25 % | 1 |
| `S6` | 0 | 0.0 % | <25 % | 21 |
| `R1` | 0 | 0.0 % | <25 % | 20 |
| `R2`–`R6`, `R8`–`R10`, `R13`, `R14` | 0 cada uno | 0.0 % | <25 % | 21 cada uno |
| `R7` | 0 | 0.0 % | <25 % | 20 |

**OBSERVACION.** Dos señales dominan con ≥50 %: `S8_R11` (16/21) y `S7`
(13/21). Una tercera, `R12`, aparece en banda media (8/21, 38.1 %). `S1`
también en banda media (6/21, 28.6 %). El resto de las 21 señales
canónicas posibles tiene **0 activaciones observadas** en las 21 fichas —
no porque se hayan evaluado y descartado, sino porque, salvo las
excepciones puntuales de R1 (ficha 1) y R7 (ficha 2), **no están
declaradas** en ninguna ficha (`NA` = 20 ó 21 de 21, según el criterio; ver
`01a-ontologia-y-derivaciones.md`). Esta ausencia declarativa masiva es en
sí misma un hallazgo — ver `04-interpretacion.md` §Q6 y
`05-hallazgos-meta.md`.

Nota de transparencia sobre `S8_R11` sin fusionar (no usada para Q1–Q4,
solo diagnóstico): `S8` en estado fuente `no_cumple` en 3/21 fichas,
`no_determinante` en 10/21, `cumple` en 7/21, `no_evaluado_o_na` en 1/21
(ficha 6). `R11` declarado `activado` explícitamente en 16/21 fichas,
`no_evaluado_o_na` (no declarado) en 5/21. La señal canónica `S8_R11`
combina ambos por la regla de `01a-ontologia-y-derivaciones.md`.

## Q3 — Coocurrencias entre señales primarias (top, sin duplicar S8/R11)

Todas las coocurrencias no nulas observadas en las 21 fichas (menos de 5
pares distintos existen; se reportan todos):

| Par | Coocurrencias/21 |
|---|---:|
| `S7` + `S8_R11` | 12 |
| `R12` + `S1` | 5 |
| `R12` + `S8_R11` | 4 |
| `S1` + `S8_R11` | 1 |
| `S1` + `S7` | 1 |

**OBSERVACION.** El par dominante con amplio margen es `S7` + `S8_R11`
(12/21, 57 %): candidatos pequeños (helper-only o `S7` falla primero por
diseño de evaluación, ver `03-firmas-y-clusters.md`) que además no
satisfacen dominancia de M2. El segundo eje, `R12` + `S1` (5/21), agrupa a
los candidatos con closure sustancial del paquete original donde la Ruta A
de extracción (reexport natural) crea un ciclo de import. `R12` + `S8_R11`
(4/21) es el mismo patrón estructural pero para candidatos donde S1 quedó
`no_determinante` en vez de `no_cumple` explícito (fichas de la extensión
con el patrón dual Ruta A/B). Ningún par involucra alguna de las 17 señales
con 0 activaciones de Q2.

Fuente citable de cada celda: `01-matriz-refutacion.csv`, columnas
`fuente_ficha`/`fuente_seccion`/`fuente_cita`.
