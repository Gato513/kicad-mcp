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
(1/21), `S1`+`S7` (1/21). Ver `02-frecuencias-y-coocurrencias.md` §Q3 para
el desglose por grupo estructural.

## Q4 — Familias

`OBSERVACION`. 7 firmas exactas deterministas, ninguna con más de 6
miembros (ver `03-firmas-y-clusters.md`). El clustering exploratorio
adicional no aportó una partición distinta de la determinista —
`CLUSTERING_NO_CONCLUYENTE` como método independiente, pero la agrupación
determinista sí es un resultado válido y completo de Q4 (los 21 candidatos
quedan asignados sin resto).

## Q5 — Patrones documentados

`OBSERVACION`, con frecuencias citables:

- **Trío de utilidad universal** (`_audit_error`/`_resolve_board`/
  `_similars` compartidos, fuera del cluster propuesto): citado
  textualmente con esa fórmula en 6/21 fichas (1, 8, 9, 10 del original;
  14, 21 de la extensión). Estructuralmente presente también en 3
  candidatos adicionales que citan un subconjunto del trío
  (`_resolve_board` solo: fichas 3, 19, 20; `_audit_error`+`_resolve_board`:
  ficha 10 ya contada).
- **Reexports** como mecanismo de preservación de superficie (S2): citado
  explícitamente en 13/21 fichas, siempre en sentido "cumple, por debajo de
  `UMBRAL_R7_REEXPORTS=3`" — ninguna ficha reporta un caso donde S2/R7
  fallan por exceso de reexports.
- **Monkeypatches**: 0/21 fichas de candidato lo mencionan directamente (el
  término solo aparece en `enumeracion.md`/`descartados.md`, documentos de
  síntesis, no en las 21 fichas individuales).
- **Cobertura** (`COBERTURA_INFERIDA` vs. `COBERTURA_DEMOSTRADA`): presente
  en las 21 fichas sin excepción (S4), con una asimetría documentada entre
  paquetes — ver Q5.bis abajo.
- **Mezcla con deudas segregadas** (P1-2/DT3): 7/21 fichas (3, 4, 5, 9, 12
  del original) registran `REFERENCIA_EXISTENTE` con nota de "adyacencia
  temática" hacia DT3, sin escalar a `PRERREQUISITO` — ninguna ficha
  reporta relación con P1-2 más allá de compartir el bridge IPC como
  módulo externo genérico.

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
R1–R10, R12–R14), solo 4 tienen alguna activación observada en los 21
candidatos: `S8_R11` (estructural + refutación fusionadas), `S7`
(estructural), `R12` (refutación), `S1` (estructural). Las 17 restantes
—incluidas R2, R3, R4, R5, R6, R8, R9, R10, R13, R14 en su totalidad, y R1/
R7 salvo una única mención cada uno— no tienen ninguna activación
declarada en ninguna de las 21 fichas: **no fueron descartadas
explícitamente, simplemente no fueron citadas**. La distribución observada
de motivos activos está dominada por **gates estructurales** (S1, S7, y la
componente S8 de `S8_R11`) más que por **criterios de refutación**
puros (solo R12 y, dentro de la señal fusionada, R11).

`F-DT.1`, `F-DT.3` y `F-DT.4` son `NO_APLICABLE` en este universo de 21,
conforme al contrato §7.1/§8: son filtros de exclusión previos a la
materialización de fichas, no motivos observables sobre los supervivientes.
No se producen conteos ni inferencias sobre ellos.

## Q7 — Convención A

`HALLAZGO_META` + `EVIDENCIA_INSUFICIENTE`. El término "Convención A" (o
cualquier mención de "M2 cualitativo por comparación no homogénea") **no
aparece en ninguna de las fuentes autorizadas por el contrato §5.1**: no
está en `CONTRATO-AUDITADO.md` (ninguno de los dos paquetes, mismo hash
`3b16079c…1402`), no está en la fe de erratas ejecutiva
(`fe-de-erratas-ejecutiva-contrato-S47-v6.md`, custodiada fuera de los
paquetes pero citada por hash en `PACKAGE-METADATA.md`), y no está en
ninguna de las 21 fichas de candidato — se verificó por búsqueda textual
exhaustiva sobre los 21 archivos (`convenci[oó]n A`, `no homog`,
`cualitativ`), 0 coincidencias.

Columna `convencion_a` de la matriz: `no` en las 462 filas — no porque se
haya verificado activamente que ningún candidato la invoque en el sentido
formal que el contrato v6 pudiera definirle, sino porque el término no
aparece citado en ninguna fuente disponible dentro de `MODO_SOLO_PAQUETES`.

Registrado como `HALLAZGO_META` en `05-hallazgos-meta.md`
(`H-S48A-02`): el contrato S47 v6 delega varias secciones normativas en su
versión v5 ("Idéntico a v5") — ver `CONTRATO-AUDITADO.md` §§11.4/11.5 — y
v5 no forma parte de las fuentes autorizadas por §5.1 de este contrato ni
está dentro de los dos paquetes S47 congelados. Si "Convención A" se define
en v5, este análisis no tiene acceso autorizado a esa definición.
`Q7 = EVIDENCIA_INSUFICIENTE` sobre la caracterización del subconjunto; el
recuento `0/21 fichas la invocan explícitamente por ese nombre` sí es una
`OBSERVACION` firme.
