# 03 — Fase 3: Criterios de rechazo aplicados (§8, §11.4, §11.5)

Aplicado a los 12 candidatos con ficha completa (`02-candidatos/*.md`), con
S1-S8 (AND) y R1-R14 (OR) de **v5** §§11.4/11.5 (fuente verificada por hash,
ver `00-preflight.md §6`), S8 usando la comparación M2 homogénea de **v6**
§10.

## 1. Clasificación individual (`VEREDICTO_INDIVIDUAL`)

Los 12 candidatos clasifican limpiamente en una de las 4 categorías exigidas
por §8: **ningún candidato quedó `NO_CLASIFICABLE`** — no se activó R-BL.3.a
(el baseline coincidió exactamente con el checkpoint, sin drift, ver
`00-preflight.md §5`) y ninguna `REFERENCIA_AMBIGUA` afectó a un símbolo
propuesto para extracción (`01-inventario-actual.md §5`).

```
APTO:              0
APTO_CONDICIONAL:  0
NO_APTO:           12
NO_CLASIFICABLE:   0
```

Todos los 12 son `NO_APTO`, por dos motivos estructurales distintos y
mutuamente excluyentes por candidato (ver `02-candidatos/README.md` para la
tabla completa y el razonamiento por ficha):

```
NO_APTO por S1/S8 (helpers de fan-in alto fuera del cluster):  5 candidatos
  (fichas 1, 3, 6, 8, 9, 10 — nota: 6 comparte también motivo S7)
NO_APTO por S7 sin dispensa E1 defendible:  8 candidatos
  (fichas 2, 4, 5, 6, 7, 10*, 11, 12 -- *ficha 10 satisface S7.a por
   margen mínimo, 85 vs 80; se cuenta en la columna S1/S8 como motivo
   primario)
```

(Ficha 6 se cuenta en ambas listas: falla S1 Y S7 simultáneamente, el único
caso doble.)

## 2. Verificación de la semántica formal de `APTO_CONDICIONAL` (§11.7)

No aplicable — ningún candidato alcanzó el punto de evaluar excepciones
E1/E2/E3, porque en los 5 candidatos con closure sustancial el gate que
falla es **S1 o S8**, ambos explícitamente **no dispensables**
("Criterios NO dispensables (nunca por E1, E2 ni E3): ... S1 ... S8 ...",
§11.7). En los 7 candidatos helper-only pequeños, el gate que falla es
**S7**, dispensable en principio por **E1** — pero la evidencia mínima
requerida por la tabla normativa de E1 ("qué responsabilidad se agrupa, qué
fan-in cruzado se elimina cualitativamente") no es demostrable para ninguno:
extraer una función ya cohesiva y de responsabilidad única no elimina
ninguna mezcla ni reduce fan-in (el fan-in persiste idéntico, solo cambia de
llamada intra-archivo a import cross-módulo). Se documentó explícitamente
en cada ficha por qué E1 no aplica — no es una omisión, es un juicio con
evidencia registrada (Regla 3 de la fe de erratas, aplicada aquí no porque
la comparación M2 sea sucia — es limpia — sino porque S7.d exige
"argumento estructural nominal" y ninguno de los 7 candidatos ofrece uno).

## 3. Criterios de refutación CR1-CR8 (§4 del contrato)

```
CR1  Priors de S40 siguen siendo los tres mejores.
     NO REFUTADA (parcial) — dos de los tres priors "apto"/"apto
     (alternativa)" de S40 (add_track → ficha 9, vecindad geométrica →
     ficha 3) reaparecen intactos en la enumeración v6; el tercero (zonas,
     validación) pasa a exclusión institucional F-DT.1 por endurecimiento
     explícito del contrato v6 respecto de v2 — no es un hallazgo de
     inconsistencia, es una evolución de contrato documentada. Ver
     01-inventario-actual.md §9.

CR2  Cifras de LOC reducibles del contexto siguen válidas post-Slice 1.
     NO REFUTADA — LOC totales de pcb.py (3161) y de cada candidato
     rederivados por AST de forma independiente, sin copiar cifras de
     contexto (§6 del contrato cumplido literalmente).

CR3  Dependencias listadas en S40 no han cambiado.
     NO REFUTADA — coincidencia byte a byte entre la rederivación de esta
     sesión y docs/analisis/40-dt1-caracterizacion.md §5-§7 (captura de
     scope 18/20+20/20, monkeypatches únicos run_drc/run_autoroute vía
     route_board, clusters exclusivos). Ver 01-inventario-actual.md §4/§7/§9.

CR4  Consumidores privados siguen siendo los conocidos.
     NO REFUTADA — frontera_entrante_src vacía confirmada para los 63
     miembros de V (idéntico a la ausencia de consumidores privados
     nuevos reportada implícitamente por S40 vía el patrón
     register_all/register_x). frontera_entrante_tests con un único caso
     nuevo respecto de lo citado explícitamente por S40 (_find_duplicate_refs,
     que S40 §7 SÍ lista como "Vía A" import directo) — sin discrepancia.

CR5  Monkeypatches históricos siguen siendo los únicos relevantes.
     NO REFUTADA — run_drc/run_autoroute, 4 archivos, idéntico a S40 §7 y
     a la fe de erratas/nota de invocación. Verificado por grep
     independiente en esta sesión (01-inventario-actual.md §7).

CR6  Extraer una closure es preferible a extraer helpers top-level.
     REFUTADA — de los 5 candidatos con closure sustancial (todos
     satisfacen S7 por LOC), NINGUNO alcanza APTO (los 5 fallan S1/S8). De
     los 7 candidatos helper-only, tampoco ninguno alcanza APTO (fallan
     S7). Esta sesión no encontró evidencia de que extraer closures sea
     estructuralmente preferible a extraer helpers — ambas familias fallan,
     por motivos distintos pero igualmente decisivos. Contraevidencia
     directa a CR6 tal como está formulada.

CR7  "Reducción de LOC de register()" es proxy suficiente de deuda.
     REFUTADA — 5 contraejemplos concretos (fichas 1, 3, 8, 9, 10): alta
     reducción de LOC de register() (85-167 líneas) sin ninguna mejora del
     vector M2 bajo el diseño de extracción mínimo. Ver
     02-candidatos/README.md "Consecuencia para H4".

CR8  Ausencia de fallos de tests es prueba de suficiencia de cobertura.
     NO EVALUADA DIRECTAMENTE por esta sesión — el baseline offline pasó
     406/406 sin fallos (00-preflight.md §5), pero eso no se tomó como
     prueba de suficiencia: cada ficha clasificó su M4 con las 4
     categorías del §10-M4 (DEMOSTRADA/REFERENCIADA/INFERIDA/DESCONOCIDA),
     nunca inferida solo de "los tests pasan". INSUFICIENTE_EVIDENCIA para
     pronunciarse sobre el enunciado general de CR8 más allá de lo
     observado candidato a candidato.
```

## 4. Hipótesis H1-H4 (§3 del contrato)

```
H1  El grafo de referencias tipadas admite al menos un cluster cohesivo,
    dependency-closed, superficie-neutral y reversible-preliminar.
    REFUTADA para el subconjunto evaluado (12/21 supervivientes) —
    ningún candidato con ficha completa satisface simultáneamente
    S1+S2+S3+S8 (AND completo de §11.4). No se puede afirmar refutada para
    el universo completo (21 supervivientes, 9 sin ficha) — ver
    EVIDENCIA_INSUFICIENTE en 05-veredicto.md.

H2  Al menos uno de los priors históricos sigue vigente.
    NO REFUTADA en el sentido de "sigue siendo un candidato legítimo
    dentro del universo enumerado" (add_track y vecindad geométrica
    reaparecen, CR1) pero SÍ refutada en el sentido de "apto para
    extracción ahora" (ambos NO_APTO por S1/S8, fichas 9 y 3). Distinción
    registrada explícitamente para evitar sobre-generalizar.

H3  Los tests actuales bastan sin ampliar la suite.
    NO REFUTADA para los 12 candidatos evaluados en el sentido estricto de
    §3 ("Refutable si existe al menos un camino relevante en
    COBERTURA_INFERIDA o COBERTURA_DESCONOCIDA") — de hecho SÍ existen
    caminos en COBERTURA_INFERIDA en las 12 fichas (documentados
    explícitamente candidato a candidato), por lo que, leído literalmente,
    H3 **SÍ se refuta** (el criterio de refutación de H3 se cumple: existe
    al menos un camino relevante en COBERTURA_INFERIDA en cada uno de los
    12 candidatos). Se registra como H3 REFUTADA — irrelevante para el
    veredicto global porque los 12 candidatos ya son NO_APTO por otros
    motivos, pero se deja constancia honesta del criterio.

H4  La reducción de LOC de register() es por sí sola proxy suficiente de
    deuda.
    REFUTADA — ver CR7 arriba, 5 contraejemplos concretos y documentados.
```

## 5. Verificación V0.4 (§11.2) — Fase 3 aplicada a TODOS los candidatos con ficha completa

Cumplida: las 12 fichas de `02-candidatos/` incluyen S1-S8, R aplicables,
M1-M4 y veredicto individual explícito. Ninguna quedó sin clasificar.

## 6. Consecuencia para §11.3 (aplicada formalmente en `05-veredicto.md`)

```
N_supervivientes (21) > UMBRAL_P_STOP_FICHAS (12)  -> regla 5 de §11.3
  se activa ANTES de llegar a evaluar las reglas 8-13 (GO/NO_GO/etc.) —
  el resultado de esta Fase 3 (12/12 NO_APTO) es evidencia valiosa mas
  NO determina el veredicto global por sí solo. Ver 05-veredicto.md.
```
