# 05 — Hallazgos meta

Conforme a §3.3/§5.3 del contrato: inconsistencias internas de los paquetes
S47 se registran aquí, sin corregirlas y sin reabrir S47.

## H-S48A-01 — Ficha 6 (`_copper_in_bbox`) declarativa incompleta

**Paquete:** original. **Fuente:** `02-candidatos/06-copper-in-bbox.md`
(íntegro citado — el archivo completo son 33 líneas).

La ficha declara verdicto para solo 4 de los 8 gates S (`S1`: no cumple,
`S7`: no cumple; `S2`–`S6`, `S8` sin mención de estado) y no declara ningún
criterio R, pese a que su patrón estructural (dependencia de
`_segment_intersects_bbox` fuera de K) es idéntico al documentado con R12
explícito en las fichas 3, 8, 9, 10 del mismo paquete y 14, 18, 21 de la
extensión. Es la única de las 21 fichas con esta asimetría de cobertura
declarativa. No se corrige — la matriz respeta la ausencia literal
(`no_evaluado_o_na`, fuente "ausencia declarada" en las celdas no
declaradas). Ver `03-firmas-y-clusters.md` Grupo G.

Impacto sobre el análisis: ninguno sobre el veredicto individual de la
ficha 6 (`NO_APTO`, sin ambigüedad, doble motivo S1+S7 declarado). Impacto
posible sobre `02-frecuencias-y-coocurrencias.md`: si `R12` estuviera
declarado, la frecuencia de `R12` subiría de 8/21 (38.1 %) a 9/21 (42.9 %)
y `_copper_in_bbox` se uniría al Grupo C de `03-firmas-y-clusters.md` en
vez de permanecer aislado (Grupo G). Se documenta la magnitud del posible
impacto sin aplicarlo — el contrato prohíbe inferir desde el código.

**Precisión de ronda R1 (§10.2 del contrato, no ampliación):** revisando la
ficha para clasificar `convencion_a` (ver Q7 abajo) se detectó que la
ficha 6 sí declara S8 en línea, dentro del bloque de S1/M2 ("Opción B:
inyectarlo como parámetro -> d1 pasa de 0 a 1, EMPEORA... S8 no cumple"),
sin encabezado propio `## S8`. La frase de este hallazgo ("S2–S6, S8 sin
mención de estado") era imprecisa específicamente para S8. No se corrige la
celda de la matriz — S8 sigue condicional a la Opción B, igual que en la
ficha 1, donde el criterio de extracción del contrato también produce
`NA`; alterar la celda excede los 6 puntos autorizados en `00-preflight.md`
§8.4. Ver `01a-ontologia-y-derivaciones.md` para el detalle.

## H-S48A-02 — Q7 (Convención A): limitación redefinida en ronda R1

**Texto original de este hallazgo (superado, se conserva por trazabilidad):**
la versión previa de esta sesión buscó el rótulo literal "Convención A" en
las fuentes de §5.1, no lo encontró en ninguno de los dos paquetes S47, el
contrato v6 ni la fe de erratas, y concluyó `EVIDENCIA_INSUFICIENTE`
atribuyendo la causa a que v6 delega varias secciones en su versión v5
(`CONTRATO-AUDITADO.md` §§11.4/11.5, "Idéntico a v5"), fuente no autorizada
por §5.1 y no leída.

**Corrección de ronda R1:** esa vía era la incorrecta. El contrato §6/Q7 no
pregunta por un rótulo — pregunta "¿en cuántos candidatos se usó M2
cualitativo por comparación no homogénea?", una conducta de evaluación
descrita por la **Regla 3** de la fe de erratas ejecutiva (SHA-256
`63fe27be8ca2fa852d2f5dfef3996549edcced710b2b67275b970c19a36dcdd4`,
verificado en `00-preflight.md` §8.1) — no un término a buscar, y v5 nunca
fue la fuente relevante. Aplicando la Regla 3 como predicado de tres
estados sobre las 21 fichas (`01a-ontologia-y-derivaciones.md`), Q7 resulta
sustantivamente respondible para **15/21** candidatos (5 `aplicada` + 10
`ausencia_explicita`). La limitación real y remanente es **más estrecha**
que la declarada originalmente: se acota a **6/21** candidatos
(`no_determinable`: fichas 6, 15, 16, 17, 19, 20) donde la ficha nunca
computa `M2_proyectado` — no por ausencia de fuente autorizada, sino porque
el antecedente mismo de la Regla 3 no se pone a prueba en esas fichas
(`S7` rechaza primero bajo `C-EXT-03`, o la ficha 6 es declarativamente
incompleta, `H-S48A-01`).

`Q7 = EVIDENCIA_INSUFICIENTE`, pero acotada a esos 6/21 candidatos, no a la
pregunta completa — los 15/21 restantes quedan respondidos con evidencia
citada. Esta limitación acotada no produce `NO_GO_ENTRADA` (§9 del
contrato; `EVIDENCIA_INSUFICIENTE` es una respuesta válida para cualquier
pregunta). Ver `04-interpretacion.md` §Q7 para la tabla completa y la
evidencia citada candidato a candidato.

## Limitaciones heredadas de los paquetes S47 (no nuevas de esta sesión)

- **`H-S47EXT-01`** (paquete extensión, `04-hallazgos-fuera-de-scope-ext.md`):
  divergencia de LOC entre `enumeracion.md §6`/contrato original y la
  re-derivación de la extensión, en 8 de los 9 candidatos 13–21. Ninguna
  divergencia altera S7 (todos los valores, correcto o divergente, caen del
  mismo lado del umbral `UMBRAL_S7_LOC=80` en cada caso — verificado
  candidato a candidato en las propias fichas 13–21). Se hereda sin
  recalcular.
- **`H-S47EXT-02`** (paquete extensión, `00-preflight-ext.md §2`): archivo
  `.tmp` transitorio no reproducible durante Puerta 0. No afecta esta
  sesión (S48-A no re-ejecuta Puerta 0 de S47).
- Estado `PENDIENTE_DE_REVISION_INDEPENDIENTE_R4` citado en
  `PACKAGE-METADATA.md` del paquete de extensión: **no es un hallazgo de
  esta sesión**. El contrato S48-A §2.2 lo declara explícitamente metadato
  histórico congelado que no reabre la decisión de custodia. Se registra
  aquí únicamente para que quede constancia de que fue revisado y
  descartado como bloqueante, conforme al contrato.

## Asimetría metodológica entre paquetes (no es inconsistencia, es patrón documentado)

Ver `04-interpretacion.md` §Q5.bis: el paquete original evalúa `S1`
incondicionalmente; la extensión (corrección `C-EXT-03`) lo deja
`no_determinante` cuando `S7` decide primero. Ambos paquetes documentan la
convención explícitamente — no se trata como `HALLAZGO_META` porque no hay
inconsistencia interna no declarada, solo una diferencia de rigor entre
sesiones que ambas partes documentan.
