# Síntesis Validation Suite A+B+C — evidencia para revisión D-30.3

**Fuente:** sesiones 31→31b→31c (Nivel A, `anavi-dev-mic`), 32 (Nivel B,
`anavi-macro-pad-12`), 33 (Nivel C, `hackrf-one`). Cierra la trilogía
prevista en `hoja-de-ruta-v5.md` y aporta los 3 puntos de evidencia que
`docs/DECISIONES.md` §D-30.3 declaró como condición para revisar los
umbrales (±30% tracks / ±20% vías / ±25% cobre / DRC 0 nuevos
eléctricos+estructurales).

Este documento **no decide** la revisión de D-30.3 — es el input
formal. La decisión final es del arquitecto (`AskUserQuestion` al
cierre de sesión 33).

## Los 3 puntos, uno al lado del otro

| | Nivel A (`anavi-dev-mic`) | Nivel B (`anavi-macro-pad-12`) | Nivel C (`hackrf-one`) |
|---|---|---|---|
| Escala | 13 fp / 20 nets / 2 capas | 63 fp / 48 nets / 2 capas (~3×A) | 437 fp / 380 nets / 4 capas (~7×B, ~34×A) |
| `route_board` | Completó (184.8s) | Completó (328.9s, tras 1 timeout) | **No completó** (crash-loop interno de Freerouting, 3600s) |
| Tracks (±30%) | No cumple | **Cumple** (−4.05%) | No evaluable (sin ruteo) |
| Vías (±20%) | No cumple | **Cumple**, borde (+20.00% exacto) | No evaluable |
| Cobre (±25%) | **Cumple** | **Cumple** (+3.23%) | No evaluable |
| DRC (matizado, D-32.1) | No cumple | No cumple (F-D5-01, 4ª instancia*) | No evaluable — pero DRC terminal sin ruteo tiene 0 eléctricos/estructurales nuevos más allá de lo esperado |
| Criterios D-30.3 que cumplen | 1/4 | 3/4 | 0/4 evaluables |

*Nota: la numeración de instancias F-D5-01 en el texto original de
sesión 31c/32 contaba desde el despertador (sesión 25) como 1ª — Nivel A
es la 2ª, Nivel B la 3ª.

## Diagnósticos previos: confirmados, refutados, o no evaluables

### "Umbral de vías mal calibrado para bases pequeñas" (31c)

Formulado sobre Nivel A (2 vías en el ground truth — una base
estadísticamente insignificante donde ±20% relativo no discrimina nada
útil: 1 vía de diferencia ya es 50%).

- **Nivel B (32) — confirmación con base 15× mayor** (30 vías): el
  umbral relativo funcionó de forma más razonable (+20.00% exacto, borde
  pero interpretable), aunque "exacto en el borde" con una base de 30
  todavía deja margen de duda sobre si es coincidencia.
- **Nivel C (33) — no evaluable.** Sin ruteo, no hay vías que contar.
  El ground truth de HackRF One SÍ tiene una base grande (498 vías,
  ~17× Nivel B) que habría sido el mejor punto de la serie para probar
  el umbral relativo a gran escala — la refutación por escalabilidad de
  H1 se llevó puesta esta oportunidad.

**Veredicto de la serie:** el diagnóstico original (umbral de vías
inadecuado para bases pequeñas) **sigue sin refutar pero tampoco sin
confirmar de forma concluyente** — solo 1 de 3 puntos (Nivel B) pudo
medirlo, y con un resultado en el borde. **Recomendación: no hay
evidencia suficiente para ajustar el umbral de vías todavía** — se
necesitaría un 4º punto con ruteo exitoso sobre un board de escala
comparable a Nivel C.

### "Confirmación con base 15× mayor" (32)

Ídem — Nivel C no aporta un 3er punto por la misma razón (sin ruteo).
La tendencia observada en A→B (base más grande → umbral relativo más
interpretable) **no se puede extender a C**. Queda abierta.

### "DRC estricto no distingue severidad" (31c, formalizado D-32.1)

- **Nivel A/B:** la tabla separada por severidad (eléctrico/
  estructural/cosmético) dio lectura más útil que el conteo total crudo
  en ambos casos — confirmado 2/2.
- **Nivel C:** confirma un 3er caso, incluso en el escenario límite de
  "sin ruteo". El DRC terminal (967, sin cobre de señal) es 100%
  `unconnected_items`/pre-existente/`starved_thermal` — **0 eléctricos o
  estructurales graves nuevos** más allá de lo esperado por la ausencia
  de cobre. La tabla por severidad distinguió correctamente "esto es
  ruido esperado de un board sin rutear" de "esto es un defecto real",
  incluso en un caso que el criterio literal de D-30.3 habría marcado
  como "555 errores, fail" sin matiz.

**Veredicto de la serie: 3/3 — D-32.1 (criterio DRC por severidad) queda
confirmado con los 3 puntos completos.** Recomendación: **formalizar
D-32.1 como parte permanente del criterio DRC de D-30.3**, no como
matiz opcional.

### Dimensión nueva — descomposición por capa (propuesta de sesión 33)

No existía como pregunta antes de Nivel C (2 capas en A/B no la
necesitaban). Aportada esta sesión, con evidencia real incluso sin
poder comparar contra un output ruteado: la extensión schema 1.2 de
`measure_ground_truth.py` (`track_length_by_layer_mm`,
`track_segment_count_by_layer`, `via_count_by_type`) reveló que el
ground truth de HackRF One usa sus capas internas **casi exclusivamente
como planos** (29 y 15 segmentos de señal en `In1.Cu`/`In2.Cu` vs 2848 y
925 en `F.Cu`/`B.Cu`, pese a concentrar la mayoría del cobre total) — un
patrón de diseño RF real e informativo que un ratio global de cobre
jamás habría expuesto.

**Recomendación:** la descomposición por capa **aporta señal genuina**
y debería incorporarse a D-30.3 para boards de 3+ capas — no como un
5º criterio pass/fail (sin base numérica todavía para fijar un umbral
razonable, solo 1 punto de evidencia), sino como **métrica auxiliar
obligatoria** en el mismo espíritu que el análisis por-net (sesión 32).
Revisar de nuevo cuando haya un 2º board multi-capa en la Suite.

## Divergencia por RF vs. divergencia por umbral mal calibrado

El prompt de sesión 33 pedía distinguir explícitamente estas dos
fuentes. **No se pudo hacer la distinción prevista** — la sesión nunca
llegó a tener un output ruteado sobre el cual medir divergencia de
ningún tipo. Lo que sí se puede decir con la evidencia disponible:

- La refutación de H1 en Nivel C es por **escalabilidad del motor de
  ruteo** (Freerouting 2.1.0, crash-loop interno documentado), no por
  reglas RF no respetadas — el fallo ocurrió antes de que hubiera
  ningún track que pudiera divergir de las reglas de impedancia del
  autor.
- Esto es en sí mismo una respuesta parcial a la pregunta de fondo del
  Nivel C: el techo real del flujo automatizado en esta escala/topología
  **no es la fidelidad RF** (que sí se podría haber medido con más
  tiempo/motor más robusto), sino la **capacidad del motor de completar
  el ruteo en absoluto**. Información igual de valiosa para la
  recomendación al release OSS, aunque no la que el prompt anticipaba.

## Recomendación formal por umbral

| Umbral D-30.3 | Evidencia disponible | Recomendación |
|---|---|---|
| Tracks ±30% | 2 puntos (A: no cumple, B: cumple) | **Mantener** — insuficiente evidencia contradictoria para ajustar; el punto que no cumplió (A) tiene explicación conocida (base pequeña, topología distinta), no apunta a un umbral mal calibrado per se. |
| Vías ±20% | 2 puntos (A: no cumple, B: cumple en el borde) | **Revisar con cautela** — el patrón "borde exacto" en B es sospechoso de coincidencia; recomendado buscar un 4º punto de evidencia con ruteo exitoso en un board de base grande (Nivel C hubiera sido ideal) antes de decidir. No urgente. |
| Cobre ±25% | 2 puntos (A: cumple, B: cumple) | **Mantener** — único criterio 2/2, sin evidencia de necesitar ajuste. |
| DRC (D-32.1, por severidad) | 3 puntos (A/B/C: los 3 confirman que el criterio matizado da lectura más útil que el conteo crudo) | **Formalizar como parte permanente del criterio**, no como matiz opcional — 3/3 es la evidencia más sólida de toda la serie. |
| Descomposición por capa (nuevo) | 1 punto (C: aporta señal real) | **Incorporar como métrica auxiliar obligatoria** para boards de 3+ capas; no fijar umbral pass/fail todavía (falta evidencia comparativa). |

## Conclusión sobre el criterio 2 de convergencia Fase 4

Los 6 criterios de admisión + diversidad D-30.4 se cumplieron en los 3
niveles. La trilogía A+B+C está **cerrada** en el sentido de que las 3
sesiones se ejecutaron de punta a punta con hallazgos honestamente
documentados — pero **no en el sentido de "3 validaciones D-30.3
exitosas"**: Nivel C no llegó a medir los 4 criterios. El criterio 2 de
convergencia de Fase 4 (hoja-de-ruta-v5) debe leerse con este matiz: la
Suite cumplió su función metodológica completa (encontrar la frontera
real del flujo, no solo confirmar casos favorables), pero el resultado
cuantitativo de D-30.3 tiene solo 2 puntos completos, no 3.

**Recomendación al arquitecto:** considerar Nivel C como evidencia
válida sobre el *alcance* del flujo (dónde deja de funcionar y por qué)
aunque no aporte el 3er punto *numérico* de D-30.3. Si se quiere un 3er
punto numérico completo antes del release, evaluar un candidato de
escala intermedia entre B (63 fp) y C (437 fp) — o resolver primero
`F-V3-ZONE-FILL-CRASH`/investigar el crash-loop de Freerouting, ya que
ambos son bloqueantes reales para cualquier intento futuro a esta
escala.
