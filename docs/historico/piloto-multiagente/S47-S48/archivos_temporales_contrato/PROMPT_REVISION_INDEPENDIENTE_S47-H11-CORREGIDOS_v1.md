# INVOCACIÓN — REVISIÓN INDEPENDIENTE DE CORRECCIONES S47-H11

## 1. Rol

Actúa como **revisor contractual independiente** del proyecto `MCP_AUDITOR_KICAD`.

Debes revisar la unidad corregida formada exactamente por:

```text
/home/astra/Desktop/agent_proyect/archivos_temporales_contrato/contrato_S47-H11-AMPLIACION-13-21_v1.md
SHA-256 esperado: a2fbeee48e7304a9a957dd2b9b69d78eb290ee148cb5e66b0d90177d35ece6fc

/home/astra/Desktop/agent_proyect/archivos_temporales_contrato/nota-invocacion-S47-H11-AMPLIACION-13-21.md
SHA-256 esperado: 08e916d4dff2cb9827f3a222675a3c498dc9196599e0f9af5a0462a01cd95498
```

El Codex que realizó la revisión inicial pasó después a escritor controlado y modificó estos dos archivos. Por R4 de `AGENTS.md`, ese escritor no puede aprobar la unidad corregida. Esta revisión debe efectuarla una instancia/persona que no haya producido ni modificado los bytes anteriores.

Tu dictamen no constituye aceptación humana, no autoriza invocación o ejecución, no autoriza S48, DT1 Slice 2, implementación, commit, push, PR ni merge.

## 2. Autoridad y distribución de roles

```text
Gato: autoridad humana sobre aceptación, ejecución y pasos posteriores.
Claude Chat: arquitecto y autor original.
Codex escritor anterior: productor de las correcciones; no revisor de esta unidad.
Tú: revisor independiente READ-ONLY de los bytes finales.
Claude Code: ejecutor solamente después de aceptación e invocación humanas separadas.
ChatGPT: auditor/reconciliador documental posterior.
```

No alteres esta distribución ni atribuyas aceptación a Gato sin un acto humano auténtico.

## 3. Modo de trabajo

Trata como `READ-ONLY`:

```text
/home/astra/Desktop/agent_proyect/
/tmp/tmp.ZedgZwIGVl.s47/
```

No edites los documentos revisados, el informe anterior, el repositorio ni paquetes S47. No ejecutes caracterización, herramientas de investigación, baselines, sincronización de dependencias ni comandos Git mutantes. No accedas a red.

Puedes usar comandos locales no mutantes para leer, localizar referencias expresas, calcular hashes, validar manifiestos existentes, comparar contenido e inspeccionar Git.

El único archivo que puedes crear es:

```text
/home/astra/Desktop/agent_proyect/archivos_temporales_contrato/REVISION_INDEPENDIENTE_S47-H11-CORREGIDOS_v1.md
```

## 4. Preflight obligatorio

Antes de evaluar:

1. registra fecha, hora, zona horaria y directorio de trabajo;
2. verifica existencia, tipo, tamaño y SHA-256 completo de los dos documentos;
3. detente con `NO_AUDITABLE` si cualquier hash difiere del esperado;
4. registra `git status --short --branch` y `git rev-parse HEAD` sin modificar Git;
5. verifica que `HEAD` siga siendo `33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b`;
6. localiza únicamente dentro de las dos raíces permitidas los antecedentes citados expresamente;
7. valida los manifiestos existentes solo con `sha256sum -c`; no regeneres nada.

## 5. Antecedente de revisión vinculante

Lee íntegramente:

```text
/home/astra/Desktop/agent_proyect/archivos_temporales_contrato/REVISION_CODEX_S47-H11-CONTRATO_v1.md
SHA-256: 81ff2aa79456ebe3375fef85828d6af997daabd59f6a81f643e07288e7ff65cd
```

Ese informe auditó los bytes anteriores:

```text
Contrato anterior: 378ccfba4392a6e4f9ab502b9c477952a41952952317dba63fa98f6d8a23ad05
Nota anterior:     f03ab48c5db4ab9328a7cc422e0797ebc4375c54c350cca7fc3d86fe09a6f48c
Veredicto:         REQUIERE_CORRECCION
```

No heredes automáticamente su veredicto: comprueba la disposición de cada hallazgo sobre los bytes nuevos.

## 6. H11 vinculante

H11 autorizó preparar, no ejecutar, una ampliación acotada para materializar y caracterizar exclusivamente los nueve supervivientes pendientes, candidatos 13–21 ya enumerados.

Debe preservarse:

```text
0 APTO/APTO_CONDICIONAL entre los 12 candidatos materializados
```

No puede extrapolarse `0/12 → 0/21`. Una conclusión sobre los 21 supervivientes solo puede emitirse después de completar y reconciliar formalmente `12 + 9 = 21`.

H11 mantiene prohibido: S48, DT1 Slice 2, modificación o reclasificación de 1–12, ampliación más allá de 13–21, conclusión anticipada, cierre DT1 y operaciones Git mutantes.

## 7. Antecedentes técnicos a contrastar

Verifica, cuando existan, sus hashes completos y contenido pertinente:

- contrato S47 v6;
- fe de erratas ejecutiva de v6;
- auditoría delta de la fe de erratas;
- nota original S47;
- paquete original `/tmp/tmp.ZedgZwIGVl.s47/S47/`;
- unidad reproducible `/tmp/tmp.ZedgZwIGVl.s47/S47-CORREGIDO-2/`;
- manifiestos, `enumeracion.md`, `05-veredicto.md`, herramientas e insumos `raw/` expresamente anclados;
- auditorías S47 original y delta;
- confirmación humana anterior, distinguiendo que no es H11.

No confíes en prefijos abreviados ni reconstruyas evidencia ausente de memoria.

## 8. Disposición obligatoria de hallazgos anteriores

Para cada hallazgo `H11-CX-01` a `H11-CX-11`, emite exactamente una disposición:

```text
CERRADO
PARCIALMENTE_CERRADO
ABIERTO
REGRESION
NO_VERIFICABLE
```

Incluye evidencia literal y ubicación exacta en los bytes corregidos.

### H11-CX-01 — Reconciliación

Comprueba que:

- el presupuesto nuevo permanezca en exactamente 9;
- la regla 5 use explícitamente `UMBRAL_P_STOP_FICHAS_ACUMULADO=21` solo para reconciliación;
- reglas 6–13 permanezcan literales;
- con ocho exclusiones institucionales, un APTO produzca `GO_DENTRO_DEL_PRESUPUESTO`, y 21 `NO_APTO` produzcan `NO_GO_POR_PRESUPUESTO`;
- el resultado se limite a `ALCANCE_SUPERVIVIENTES_21`;
- no se predetermine el resultado ni se autorice implementación.

Contrasta literalmente contra v6 §11.3 y fe de erratas Regla 5.

### H11-CX-02 — Puerta 0 reproducible

Comprueba que herramientas, insumos, hashes, comandos, argumentos, salidas, serialización, comparación JSON y exit codes estén cerrados y permitan resultados iguales a dos ejecutores. Verifica físicamente los hashes citados, pero no ejecutes las herramientas.

### H11-CX-03 — Destino seguro

Comprueba que el destino sea exclusivamente `$S47_TMP/S47-EXT-13-21`, con raíz canónica fuera del working tree, inexistencia previa, rechazo de symlinks/escape/ambigüedad y `NO_GO_ENTRADA` antes de escribir.

### H11-CX-04 — Aceptación separada

Comprueba que no haya `<SUSTITUIR>`, campos de firma pendientes ni equivalencia entre invocar y aceptar. La aceptación debe ser un acto humano posterior por hashes finales y la invocación otro acto separado.

### H11-CX-05 — Precedencia

Comprueba una precedencia exhaustiva y acotada entre H11, contrato de ampliación, fe de erratas, auditoría delta y v6, sin ampliar permisos.

### H11-CX-06 — Anclas completas

Comprueba todos los hashes del paquete original, manifiesto, contrato, enumeración, veredicto, unidad corregida, herramientas y `raw/`. Confirma que la nota cite el hash final correcto del contrato corregido.

### H11-CX-07 — Unidad de evidencia

Comprueba inventario obligatorio, manifiesto, informe, comandos y exits, Git antes/después, procedencia, limitaciones, nueve fichas y reconciliación. Confirma que todos los archivos regulares salvo el manifiesto deban quedar cubiertos.

### H11-CX-08 — Procedencia H11

Comprueba que H11 se preserve sin presentarla como ejecución, que no se atribuyan declaraciones no auténticas y que la aceptación futura siga separada. Si la procedencia no puede autenticarse solo con artefactos locales, clasifica exactamente el riesgo y su impacto; no inventes un anexo.

### H11-CX-09 — Comandos de preflight

Comprueba comandos para Git, hashes, manifiestos, entorno offline, caches, Fase 2, igualdad 29→8→21, baseline y captura de exit codes. Confirma que `uv sync`, descargas y red estén prohibidos.

### H11-CX-10 — Detención anticipada

Comprueba que menos de nueve fichas deje unidad `INCOMPLETA` y prohíba reconciliación/veredicto sobre 21, sin suplentes ni reutilización.

### H11-CX-11 — Custodia temporal

Comprueba que se exija preservar copia byte-idéntica fuera de `/tmp`, en destino nuevo, sin mover ni modificar el original.

## 9. Pruebas cruzadas adicionales

Aunque los once hallazgos parezcan cerrados, busca regresiones o contradicciones nuevas. Evalúa especialmente:

- correspondencia uno a uno contrato ↔ nota;
- consistencia de todos los hashes físicos;
- comandos realmente compatibles con las interfaces de los scripts anclados;
- ausencia de rutas relativas destructivas;
- ausencia de permisos implícitos para escribir el repositorio;
- consistencia entre `READ-ONLY` de fuentes y creación de una unidad nueva fuera del working tree;
- identidad exacta y orden de candidatos 13–21 contra `enumeracion.md §6`;
- invariancia técnica/documental de 1–12;
- reserva de revisión independiente tras el cambio de rol del escritor;
- inexistencia de marcadores, hashes truncados o decisiones operativas sin resolver.

Incluye una tabla:

| Control | Contrato | Nota | Antecedente | Resultado |
|---|---|---|---|---|
| Alcance 13–21 | | | | |
| Exactamente nueve fichas | | | | |
| Invariancia 1–12 | | | | |
| Puerta 0 reproducible | | | | |
| Reconciliación 12+9 | | | | |
| Unidad nueva segura | | | | |
| Revisión independiente | | | | |
| Prohibiciones | | | | |
| Aceptación humana separada | | | | |

## 10. Clasificación

Usa `BLOCKER`, `MAJOR`, `MINOR`, `NOTE` con el mismo umbral del informe anterior. Para todo hallazgo nuevo incluye:

```text
ID
SEVERIDAD
DOCUMENTO
SECCIÓN / LÍNEA
EVIDENCIA LITERAL
NORMA AFECTADA
ANÁLISIS
IMPACTO
CORRECCIÓN MÍNIMA
RESPONSABLE
```

No corrijas directamente ni propongas rediseños amplios cuando baste un cambio localizado.

## 11. Veredictos permitidos

Emite exactamente uno:

```text
CONFORME_PARA_ACEPTACION_HUMANA
CONFORME_CON_OBSERVACIONES
REQUIERE_CORRECCION
NO_AUDITABLE
```

`CONFORME_*` solo permite presentar los bytes exactos a Gato. Nunca significa ejecución autorizada.

## 12. Entregable

Crea:

```text
/home/astra/Desktop/agent_proyect/archivos_temporales_contrato/REVISION_INDEPENDIENTE_S47-H11-CORREGIDOS_v1.md
```

Estructura mínima:

```text
1. Identificación y rol
2. Preflight y hashes
3. Unidad exacta revisada
4. Antecedentes verificados
5. Identidad 13–21
6. Disposición H11-CX-01…H11-CX-11
7. Puerta 0
8. Reconciliación 12+9
9. Invariancia 1–12
10. Unidad de evidencia y destino
11. Nota de invocación
12. Matriz de consistencia
13. Hallazgos nuevos o regresiones
14. Riesgos residuales
15. Veredicto
16. Alcance de conformidad
17. Siguiente autoridad
18. Comandos, salidas y exit codes
```

## 13. Respuesta final en chat

Responde únicamente:

```text
REVISIÓN INDEPENDIENTE S47-H11 CORREGIDA COMPLETADA

Documentos:
- Contrato: <SHA-256>
- Nota: <SHA-256>

Disposición de hallazgos anteriores:
- CERRADOS: <n>
- PARCIALMENTE_CERRADOS: <n>
- ABIERTOS: <n>
- REGRESIONES: <n>
- NO_VERIFICABLES: <n>

Hallazgos nuevos:
- BLOCKER: <n>
- MAJOR: <n>
- MINOR: <n>
- NOTE: <n>

Veredicto:
<VEREDICTO>

Entregable:
/home/astra/Desktop/agent_proyect/archivos_temporales_contrato/REVISION_INDEPENDIENTE_S47-H11-CORREGIDOS_v1.md

Estado de ejecución:
NO AUTORIZADA

Siguiente autoridad:
Gato — aceptación humana expresa de los hashes finales, si el veredicto lo permite.

S48 y DT1 Slice 2 permanecen sin autorización.
No se realizó commit, push, PR ni merge.
```
