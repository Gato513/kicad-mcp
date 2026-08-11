# 04 — Interpretación (Q1–Q7)

Reglas de marcado: `OBSERVACION` cita fila/columna de la matriz y fuente por
celda; `HIPOTESIS` es causal y se marca como tal, con contra-hipótesis
cuando exista; ningún hallazgo se traduce a recomendación B/C/D/E. Sin
causalidad sobre P1-2/DT3, sin contrafactuales de presupuesto, `F-DT.1`,
`F-DT.3`, `F-DT.4` `NO_APLICABLE` en Q6.

## Q1 — Distribución

`OBSERVACION`. 20/21 candidatos (95 %) fallan por exactamente 2 señales
canónicas; 1/21 (`_delete_copper`) por 3. Ninguno falla por 1 sola señal ni
por más de 3 (`01-matriz-refutacion.csv`; agregado en
`02-frecuencias-y-coocurrencias.md` §Q1). El "número" de motivos por
candidato es uniforme; el "cuál" motivo no lo es de forma pareja: 2 señales
concentran casi toda la actividad (`S8_R11` 76.2 %, `S7` 61.9 %) y una
tercera (`R12`, 38.1 %) es un eje secundario claro. El resto de las 21
señales posibles (17 de ellas) tiene 0 activaciones observadas — mayormente
por ausencia de declaración, no por evaluación negativa (ver Q6).

`HIPOTESIS` (marcada como tal, sin implicar causa sobre DT1): la
concentración en 2 señales por candidato podría reflejar que el algoritmo
de enumeración de S47 (§7.1 de v6) selecciona candidatos que ya superan la
mayoría de los gates individualmente, dejando solo 1–2 gates "de cierre"
como discriminantes — pero esta sesión no tiene evidencia para confirmar
esa hipótesis sobre el diseño del algoritmo mismo, solo sobre su resultado
observado en los 21 supervivientes.

## Q2 — Frecuencia

`OBSERVACION`. Ver tabla completa en `02-frecuencias-y-coocurrencias.md`
§Q2. Bandas: ≥50 % → `S8_R11` (16/21), `S7` (13/21). 25–<50 % → `R12`
(8/21), `S1` (6/21). <25 % → las 17 señales restantes, todas en 0/21.

## Q3 — Coocurrencia

`OBSERVACION`. Cinco pares con coocurrencia no nula, todos reportados (no
hay top-5 recortado, es el universo completo de pares observados): `S7`+
`S8_R11` (12/21), `R12`+`S1` (5/21), `R12`+`S8_R11` (4/21), `S1`+`S8_R11`
(1/21), `S1`+`S7` (1/21). Además, el único trío no nulo observado:
`{S1, S8_R11, R12} = 1` (`_delete_copper`, el único candidato de los 21 con
3 señales canónicas activas — ver Q1). El ranking del contrato §6/Q3 pide
"pares o tríos" explícitamente; se reporta el trío junto con los pares en
vez de limitar el análisis a pares, precisamente porque existe uno (n=1,
100 % del universo con 3 señales activas). Ver
`02-frecuencias-y-coocurrencias.md` §Q3 para el desglose por grupo
estructural.

## Q4 — Familias

`OBSERVACION`. Dos niveles de agregación, con cifras distintas y ambas
necesarias para no confundirlas (ver `03-firmas-y-clusters.md`):

- **7 firmas exactas** sobre el vector canónico completo (21 posiciones,
  incluyendo la posición de cada `NA`) — es el resultado primario y más
  fino de Q4, ninguna con más de 6 miembros.
- **5 conjuntos distintos de señales activas de fallo** (ignorando la
  posición de los `NA`, solo las señales con `senal_fallo=1`):
  `{S7,S8_R11}` (12 candidatos, grupos A+B+F), `{S1,R12}` (4, grupo C),
  `{S8_R11,R12}` (3, grupo D), `{S1,S8_R11,R12}` (1, grupo E), `{S1,S7}`
  (1, grupo G).

Las 7 firmas se reducen a 5 conjuntos activos porque los grupos A, B y F
comparten literalmente el mismo par de señales de fallo (`{S7,S8_R11}`) y
solo se distinguen entre sí por diferencias en celdas que **no** son
señales de fallo (declaración de `S1`/`S4` entre paquete original y
extensión; una única declaración de `R7=no_activado` en el grupo F).

El clustering exploratorio adicional no aportó una partición distinta de la
determinista de 7 firmas — `CLUSTERING_NO_CONCLUYENTE` como método
independiente, pero la agrupación determinista sí es un resultado válido y
completo de Q4 (los 21 candidatos quedan asignados sin resto). **Corrección
de ronda R1:** se retira la afirmación previa de que "las mismas 7
particiones aparecen bajo cualquier métrica de distancia razonable" — esa
generalización nunca fue verificada por cómputo real, solo por inspección
cualitativa; ver `03-firmas-y-clusters.md` para el detalle de qué sí se
sostiene sin ella.

## Q5 — Patrones documentados

`OBSERVACION`, con frecuencias citables:

- **Trío de utilidad universal** (`_audit_error`/`_resolve_board`/
  `_similars` compartidos, fuera del cluster propuesto): citado
  textualmente con esa fórmula en 6/21 fichas (1, 8, 9, 10 del original;
  14, 21 de la extensión). Estructuralmente presente también en 3
  candidatos adicionales que citan un subconjunto del trío
  (`_resolve_board` solo: fichas 3, 19, 20; `_audit_error`+`_resolve_board`:
  ficha 10 ya contada).
- **Reexports** como mecanismo de preservación de superficie (S2): la
  palabra "reexport" aparece en **14/21** fichas (corrección de ronda R1;
  el "13/21" previo no correspondía a ningún criterio verificable). De
  ellas, **11** declaran un conteo numérico de reexports asociado
  directamente al gate `S2` (0 ó 1 reexport, siempre por debajo de
  `UMBRAL_R7_REEXPORTS=3`: fichas 1, 2, 3, 4, 5, 7, 8, 9, 11, 12 del
  original + 13 de la extensión). Las **3** restantes (14, 18, 21, todas de
  la extensión) usan el término solo como rótulo de diseño — "Ruta A —
  reexport natural" — para describir la vía de extracción que crea el
  ciclo de import (`S1`/`R12`), sin declarar un conteo de `S2` distinto de
  "cumple". En ambos casos, ninguna ficha reporta `S2` ni `R7` fallando por
  exceso de reexports: confirmado en la matriz (`S2` fail=0/21, `R7`
  fail=0/21).
- **Monkeypatches**: 0/21 fichas de candidato lo mencionan directamente (el
  término solo aparece en `enumeracion.md`/`descartados.md`, documentos de
  síntesis, no en las 21 fichas individuales).
- **Cobertura** (`COBERTURA_INFERIDA` vs. `COBERTURA_DEMOSTRADA`): mencionada
  en **20/21** fichas (corrección de ronda R1 — la afirmación previa de
  "21/21 sin excepción" era incorrecta). La ficha 6 (`_copper_in_bbox`) es
  la única excepción: no declara `S4` con ninguna palabra de estado, ya
  registrado como `H-S48A-01` en `05-hallazgos-meta.md`. Esta cifra (20/21
  fichas que *mencionan* cobertura en prosa) es distinta de la cuenta de
  `S4` con estado formal en la matriz (12/21 evaluados con `cumple`, 9/21
  `no_determinante`/`NA` — ver Q6) — ambas correctas, miden cosas distintas
  (mención narrativa vs. celda estructurada), no se contradicen. Asimetría
  entre paquetes documentada en Q5.bis abajo.
- **Mezcla con deudas segregadas** (P1-2/DT3): corrección de ronda R1 —
  la cifra previa ("7/21 fichas: 3, 4, 5, 9, 12") era incorrecta en dos
  sentidos: el conteo no coincidía con la lista (5 elementos, no 7), y las
  fichas 4 y 5 no mencionan DT3 en absoluto. Reverificado por lectura
  completa de las 21 fichas:
  - **16/21** fichas mencionan `DT3`/`P1-2` en alguna forma.
  - De ellas, **4/21** (fichas 3, 9, 10, 12, todas del paquete original)
    registran una **adyacencia temática real** hacia DT3 — típicamente con
    hallazgo §14 `DRIFT_AFECTA_CANDIDATO` (fichas 3 y 9 explícitamente) o
    nota equivalente de proximidad geométrica —, siempre acotada por el
    criterio objetivo "DT3 vive en `bridge/`, este código vive en
    `tools/pcb.py`" y **sin escalar a `PRERREQUISITO`** en ningún caso.
  - Las **12/21** restantes que mencionan DT3 lo hacen para **descartar**
    explícitamente cualquier relación ("sin relación con DT3/P1-2"; la
    ficha 7 con la formulación más fuerte, "sin adyacencia siquiera
    temática con DT3").
  - **5/21** fichas (4, 5, 6 del original; 15, 16 de la extensión) no
    mencionan DT3/P1-2 en absoluto.
  16 (mencionan) + 5 (no mencionan) = 21; 4 (adyacencia) + 12 (descartan) =
  16. Ninguna ficha reporta relación con P1-2 más allá de compartir el
  bridge IPC como módulo externo genérico.

**Q5.bis — asimetría documental entre paquetes (`OBSERVACION`).** El
paquete original evalúa `S1` incondicionalmente incluso cuando `S7` ya es
determinante; la extensión corregida (corrección `C-EXT-03`, ver
`CORRECCIONES.md`) se abstiene explícitamente de afirmar `S1` bajo
extracción proyectada cuando `S7` decide primero, y lo declara
`no_determinante` en su lugar (5/9 fichas de la extensión: 15, 16, 17, 19,
20). Es una diferencia de convención metodológica entre ambas sesiones de
S47, documentada por ambos paquetes, no una inconsistencia oculta.

`HIPOTESIS` (sin atribuir causalidad sobre P1-2 ni DT3, conforme al
contrato): la recurrencia del trío `_audit_error`/`_resolve_board`/
`_similars` en 6+ candidatos distintos sugiere que **cualquier** extracción
aislada de un candidato con closure sustancial enfrentará el mismo
obstáculo estructural mientras esos tres helpers permanezcan en `pcb.py` —
esto es una observación sobre la forma del grafo de dependencias, no una
afirmación sobre si DT1 es o no viable; varias fichas (2, 11, 13) dejan
constancia explícita de que un candidato futuro que consolide el trío en un
módulo propio "queda fuera del alcance de S47" (cita literal de ficha 11).

## Q6 — Naturaleza de los motivos

`OBSERVACION`. De las 21 señales canónicas posibles (S1–S7, `S8_R11`,
R1–R10, R12–R14), solo 4 tienen alguna activación (`senal_fallo=1`)
observada en los 21 candidatos: `S8_R11` (estructural + refutación
fusionadas), `S7` (estructural), `R12` (refutación), `S1` (estructural). La
distribución observada de motivos activos está dominada por **gates
estructurales** (S1, S7, y la componente S8 de `S8_R11`) más que por
**criterios de refutación** puros (solo R12 y, dentro de la señal
fusionada, R11).

Las 17 señales restantes tienen 0 activaciones, pero **no forman una
población homogénea** — corrección de ronda R1, la formulación previa
("no fueron descartadas explícitamente, simplemente no fueron citadas")
aplicaba correctamente solo a una parte de ellas. Se dividen en dos grupos
de naturaleza distinta:

- **Evaluadas repetidamente sin ningún fallo (6 señales):** `S2` (20/21
  candidatos evaluados, 0 fallos), `S5` (20/21, 0), `S3` (15/21, 0), `S4`
  (12/21, 0), `R1` (1/21, 0), `R7` (1/21, 0). Estas señales sí fueron
  citadas y resueltas por las fichas — `S2` y `S5` en 20 de los 21
  candidatos, la inmensa mayoría del universo — y nunca resultaron en un
  fallo. Describirlas como "no citadas" es incorrecto.
- **Sin ninguna declaración, positiva o negativa (11 señales):** `S6`, `R2`,
  `R3`, `R4`, `R5`, `R6`, `R8`, `R9`, `R10`, `R13`, `R14` — `NA` (`no_
  evaluado_o_na`) en las 21 fichas. A estas sí les aplica sin matices la
  descripción "no fueron citadas".

6 + 11 = 17. La distinción importa para leer Q6 correctamente: el universo
de 21 `NO_APTO` no es un universo donde 17 de 21 criterios "no aplicaron" —
6 de ellos sí se evaluaron sistemáticamente y resultaron favorables
(`cumple`/`no_activado`); solo 11 quedan genuinamente fuera del rango
declarativo de las fichas.

`F-DT.1`, `F-DT.3` y `F-DT.4` son `NO_APLICABLE` en este universo de 21,
conforme al contrato §7.1/§8: son filtros de exclusión previos a la
materialización de fichas, no motivos observables sobre los supervivientes.
No se producen conteos ni inferencias sobre ellos.

## Q7 — Convención A (reanalizada en ronda R1)

**Corrección de metodología.** La versión previa de esta sección buscó el
rótulo literal "Convención A" en las fuentes de §5.1, no lo encontró, y
concluyó `EVIDENCIA_INSUFICIENTE` atribuyendo la laguna a que v6 delega en
v5 (fuente no autorizada). Esa vía era incorrecta por partida doble: (a) el
contrato §6/Q7 no pregunta por un rótulo, pregunta "¿en cuántos candidatos
se usó M2 cualitativo por comparación no homogénea?" — una **conducta**
observable en las fichas, no un término a buscar; y (b) la semántica que
define esa conducta está en la **Regla 3 de la fe de erratas ejecutiva**
(SHA-256 `63fe27be8ca2fa852d2f5dfef3996549edcced710b2b67275b970c19a36dcdd4`,
verificado en `00-preflight.md` §8.1), no en v5 — v5 nunca fue la fuente
correcta a buscar.

**Reanálisis.** Aplicando el predicado de tres estados de
`01a-ontologia-y-derivaciones.md` (§"Operacionalización de la Regla 3") a
las 21 fichas, con evidencia citada candidato a candidato:

| Estado | N/21 | Candidatos |
|---|---:|---|
| `aplicada` | 5 | 1, 3, 8, 9, 10 |
| `ausencia_explicita` | 10 | 2, 4, 5, 7, 11, 12, 13, 14, 18, 21 |
| `no_determinable` | 6 | 6, 15, 16, 17, 19, 20 |

`OBSERVACION`, `HIPOTESIS` marcada donde corresponde:

- `OBSERVACION`. **15/21 candidatos son clasificables sustantivamente**:
  5 aplicaron la vía cualitativa de la Regla 3 (`aplicada`), 10 no la
  necesitaron porque lograron una comparación homogénea completa
  (`ausencia_explicita`).
- `OBSERVACION`. El subconjunto `aplicada` (n=5) coincide **exactamente**
  con Grupo C + Grupo E de `03-firmas-y-clusters.md`: los 5 candidatos con
  closure sustancial del paquete original donde la Ruta A de extracción
  (reexport natural hacia `pcb.py`) activa `R12` y la Ruta B (inyección
  explícita) hace que `S8` deje de tener un veredicto único cuantificable
  ("S8 — falla bajo Opción B; no evaluable con sentido bajo Opción A").
  Todas del paquete original; ninguna de la extensión.
- `HIPOTESIS` (sin implicar viabilidad de DT1): el hecho de que las 5
  aplicaciones caigan exactamente en los candidatos de mayor fan-in del
  paquete original sugiere que la vía cualitativa de la Regla 3 se activa
  específicamente cuando el candidato depende de helpers de alto consumo
  compartido (`_audit_error`/`_resolve_board`/`_similars`, ver Q5) — no
  verificable más allá de esta correlación observada sobre 5 casos.
- `OBSERVACION`. Los **6/21 no determinables** (ficha 6 + las 5 fichas de
  extensión donde `S7` rechaza primero bajo la corrección `C-EXT-03`:
  15, 16, 17, 19, 20) nunca llegan a computar `M2_proyectado`, por lo que
  el antecedente mismo de la Regla 3 ("dos estados [...] sobre un
  candidato concreto") no se pone a prueba. La limitación es real, pero es
  **distinta** de la que declaraba la versión previa: no es ausencia de
  fuente autorizada, es ausencia de la comparación M2 en la ficha misma.

**Veredicto de Q7 (corregido):** respondida sustantivamente para 15/21
candidatos. `EVIDENCIA_INSUFICIENTE` se **retiene**, pero **acotada** a los
6/21 candidatos `no_determinable` — se elimina como fundamento del
veredicto la afirmación de que el término no aparece en ninguna fuente
autorizada; esa búsqueda era la pregunta equivocada. No se fuerza
`ANALISIS_COMPLETO`: la limitación sobre esos 6 candidatos es genuina y se
mantiene declarada en `06-cierre.md`.

Se conserva como diagnóstico secundario, no como fundamento del veredicto:
el rótulo literal "Convención A" no aparece en ninguna de las 21 fichas ni
en `CONTRATO-AUDITADO.md` — 0 coincidencias en búsqueda textual exhaustiva.
Esto ya no importa para responder Q7 (la Regla 3 nunca definió ese rótulo),
pero se documenta para que quede constancia de que la búsqueda literal
original no era, en sí misma, errónea — el error estaba en detenerse ahí en
vez de aplicar la semántica conductual de la Regla 3. Ver
`05-hallazgos-meta.md` `H-S48A-02` (reescrito en esta ronda).
