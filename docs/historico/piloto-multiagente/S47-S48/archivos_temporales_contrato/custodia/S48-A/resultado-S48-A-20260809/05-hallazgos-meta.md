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

## H-S48A-02 — Q7 (Convención A) sin fuente autorizada

Ver `04-interpretacion.md` §Q7 para el detalle completo. Resumen: el
término no aparece en ninguna fuente dentro del alcance de §5.1 (ambos
paquetes S47, contrato v6, fe de erratas). v6 delega en v5 para varias
secciones normativas (§§11.4/11.5 de `CONTRATO-AUDITADO.md`: "Idéntico a
v5"), y v5 no es un insumo autorizado ni está dentro de los paquetes
congelados. No se leyó v5. Produce `EVIDENCIA_INSUFICIENTE` en Q7, no
`NO_GO_ENTRADA` (una pregunta sin poder responderse no detiene el análisis,
§9 del contrato).

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
