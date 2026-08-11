# CONTRATO S48-A READ-ONLY — CANDIDATO FINAL PARA APROBACIÓN
## Análisis agregado de patrones de refutación sobre S47

**Proyecto:** MCP_AUDITOR_KICAD  
**Autoridad:** Gato  
**Fecha:** 2026-08-09 (America/Asuncion)  
**Preparación documental:** ChatGPT, por instrucción expresa de Gato  
**Estado:** `PENDIENTE_DE_APROBACION_HUMANA`  
**Naturaleza:** contrato de investigación READ-ONLY; no autoriza implementación, push, PR, merge ni modificación del repositorio.

---

## 0. Regla de cierre documental

Este documento reemplaza, para fines de aprobación, la cadena de propuestas v1–v4. Es autocontenido: no incorpora cláusulas mediante expresiones como “sin cambios respecto de vN”.

Los datos que solo existen en la máquina de ejecución —rutas absolutas actuales y directorio temporal— son **parámetros de invocación**, no requisitos para aprobar el contrato. La nota humana de invocación los declarará y el preflight los verificará.

Una falta o divergencia operativa en preflight no reabre el contrato ni S47: produce un resultado puntual `NO_GO_ENTRADA` con evidencia.

---

## 1. Objetivo

Producir un diagnóstico agregado, rederivable y limitado a los 21 candidatos supervivientes evaluados en S47, respondiendo preguntas empíricas sobre la distribución y coocurrencia de los motivos documentados de refutación.

El análisis servirá exclusivamente como evidencia para que Gato decida después el destino de DT1.

No es objetivo de S48-A:

- reabrir, corregir o reinterpretar el resultado aceptado de S47;
- re-materializar candidatos ni recalcular M1/M2/M3/M4;
- evaluar los ocho candidatos excluidos institucionalmente;
- atribuir causalidad a P1-2, DT3 u otra deuda segregada;
- diseñar o implementar DT1 Slice 2;
- recomendar automáticamente las alternativas B, C, D o E;
- modificar código, documentación normativa, paquetes S47 o repositorio.

Resultado S47 que se conserva congelado:

```text
NO_GO_POR_PRESUPUESTO
ALCANCE_SUPERVIVIENTES_21
21/21 NO_APTO
```

---

## 2. Insumos identificados

### 2.1 Paquete S47 original — candidatos 1–12

Identidad lógica: `S47` original, fichas 1–12.  
Hash esperado del archivo `MANIFEST.sha256`:

```text
cb3bfee2b25f1e34f3b46a3ead35be7b4525eb9efb24499d0a9dba0cf5fcf078
```

Custodia histórica documentada:

```text
/home/astra/Desktop/agent_proyect/archivos_temporales_contrato/custodia/S47-ORIGINAL-H11/
```

La ruta es una referencia histórica, no una ruta obligatoria. La nota de invocación declarará la ruta existente en la máquina de ejecución.

### 2.2 Extensión S47 corregida — candidatos 13–21

Identidad lógica: `S47-EXT-13-21-CORREGIDO`.  
Hash esperado del archivo `MANIFEST.sha256`:

```text
d564029b1eea5e6bd3da648cbdb615c3b6cec6f5195fdbf73ea12d2261f65074
```

Ese hash corresponde al manifiesto corregido aportado a esta decisión. El manifiesto contiene, entre otras, las anclas siguientes:

```text
CORRECCIONES.md        8d4f1ed3ce660bb8ccbbe68b19fba44bfa9aa37736540beeb8ed88c72239027a
PACKAGE-METADATA.md    42349aef6a69bb46fc9cc9ba26af878c8d208150e05a3497797ffbc87d89b68b
05-RECONCILIACION.md   ca64ef89c58270655c7a40d57889af3fe1ca5ad8f7b0076c103bfc8c5e4e78a0
```

El paquete permanece congelado por decisión de Gato. Las referencias históricas internas a `PENDIENTE_DE_REVISION_INDEPENDIENTE_R4` no reabren esa decisión; se conservan como metadatos históricos.

### 2.3 Contrato S47 v6 y ancla histórica de código

```text
Contrato S47 v6, SHA-256:
3b16079cd67357b17ff2d23064c6397454b8a06e4830684c0fa60c2eaac91402

Checkpoint histórico de código:
33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
```

El código fuente es un insumo contextual opcional para localizar referencias ya citadas en las fichas. Los paquetes S47 son la evidencia primaria del análisis. Una divergencia posterior del repositorio no invalida los paquetes: activa `MODO_SOLO_PAQUETES` y se declara como limitación.

---

## 3. Nota humana de invocación

La ejecución requiere una nota posterior y separada de Gato con este contenido mínimo:

```text
NOTA DE INVOCACIÓN S48-A
Fecha:                         <ISO 8601>
Contrato aprobado SHA-256:    <hash exacto de este contrato aprobado>
S47_ORIGINAL_DIR:              <ruta absoluta existente>
S47_EXT_CORREGIDO_DIR:         <ruta absoluta existente>
REPO_DIR:                      <ruta absoluta o NO_DISPONIBLE>
Techo de ejecución:            3 horas, salvo valor explícito distinto
Ejecutor:                      Claude Code
Aprobación:                    Gato
```

La nota autoriza únicamente la ejecución READ-ONLY de este contrato. No autoriza implementación ni cambios al repositorio.

---

## 4. Preflight mínimo y vinculante

El ejecutor realiza una sola vez:

1. Verificar que la nota existe, identifica a Gato y contiene el hash exacto del contrato aprobado.
2. Resolver con `realpath` las dos rutas de paquetes declaradas.
3. Confirmar que ambas rutas están fuera del working tree del repositorio, si existe.
4. Calcular `sha256sum MANIFEST.sha256` en cada paquete y compararlo con §2.1 y §2.2.
5. Ejecutar `sha256sum -c MANIFEST.sha256` dentro de cada paquete.
6. Crear el directorio de salida con `mktemp -d --suffix=.s48a`, fuera del repositorio y de ambos paquetes.
7. Si `REPO_DIR` está disponible, registrar `git rev-parse HEAD` y `git status --porcelain=v1 --untracked-files=all` sin modificar nada. Un estado dirty se documenta y fuerza `MODO_SOLO_PAQUETES`; no bloquea por sí solo.

Producen `NO_GO_ENTRADA` únicamente:

- nota ausente, mal formada o con hash contractual distinto;
- paquete no localizable;
- hash del manifiesto distinto;
- fallo de `sha256sum -c`;
- imposibilidad de crear una salida fuera de repositorio y paquetes;
- instrucción sobrevenida que exija escribir o cruzar el scope prohibido.

No producen `NO_GO_ENTRADA`:

- repositorio no disponible, divergente o dirty;
- una ficha incompleta;
- una referencia ambigua;
- una celda no evaluada;
- clustering no concluyente;
- ausencia de patrón dominante.

Esos casos se registran como limitaciones y, cuando afecten las respuestas, conducen a `ANALISIS_PARCIAL_CON_LIMITACIONES`.

---

## 5. Scope autorizado

### 5.1 Lectura

- Paquete original S47, especialmente fichas y resúmenes de candidatos 1–12.
- Extensión corregida S47, especialmente fichas 13–21, reconciliación, correcciones y hallazgos.
- Contrato S47 v6 y fe de erratas, para semántica de S1–S8, R1–R14 y Convención A.
- Código fuente, solo en `MODO_PAQUETES_Y_CODIGO`, para localizar referencias textuales ya citadas; no para re-evaluar candidatos.

### 5.2 Escritura

Únicamente dentro del directorio temporal S48-A creado en preflight. Ninguna salida se agrega al repositorio ni modifica los paquetes S47.

### 5.3 Fuera de scope

- Toda escritura en el repositorio o los paquetes S47.
- Comandos Git que modifiquen índice, refs, configuración, worktrees o archivos.
- Ejecución de tests, KiCad, herramientas MCP, scripts de materialización o benchmarks.
- Re-cálculo de M1/M2/M3/M4 o nueva inspección causal del código.
- Re-clasificación de candidatos o evaluación de excluidos.
- Cambio de F1–F5, G1–G5, specs, ADR, presupuesto, umbrales o prioridades.
- Inferencias sobre qué ocurriría al ampliar presupuesto.

Un hallazgo fuera de scope se registra en `05-hallazgos-meta.md`; no se corrige.

---

## 6. Preguntas empíricas

**Q1. Distribución.** ¿Los 21 `NO_APTO` están dominados por pocos motivos de fallo o presentan firmas dispersas?

**Q2. Frecuencia.** ¿Qué señales normalizadas de fallo aparecen en ≥50 %, entre 25 % y <50 %, y en <25 % de los candidatos?

**Q3. Coocurrencia.** ¿Qué pares o tríos de señales primarias de fallo coocurren con mayor frecuencia? Reportar hasta cinco, sin duplicar relaciones derivadas.

**Q4. Familias.** ¿Qué candidatos comparten exactamente la misma firma de señales de fallo? Un clustering adicional es opcional y exploratorio.

**Q5. Patrones documentados.** ¿Qué patrones descriptivos aparecen expresamente en las fichas —superficie MCP, reexports, monkeypatches, acoplamiento, cobertura u otros— y con qué frecuencia? Toda causalidad propuesta se marca `HIPOTESIS`.

**Q6. Naturaleza de los motivos.** ¿Cómo se distribuyen las señales observadas entre gates estructurales S y criterios de refutación R? `F-DT.1`, `F-DT.3` y `F-DT.4` son `NO_APLICABLE` en el universo de 21 y no reciben conteos ni inferencias.

**Q7. Convención A.** ¿En cuántos candidatos se usó M2 cualitativo por comparación no homogénea y qué diferencias descriptivas presenta ese subconjunto?

`EVIDENCIA_INSUFICIENTE` es una respuesta válida para cualquier pregunta.

---

## 7. Matriz y semántica

### 7.1 Estados fuente

La matriz conserva la semántica original de cada familia:

| Familia | Estados fuente admitidos |
|---|---|
| Gates `S1–S8` | `cumple`, `no_cumple`, `no_determinante`, `no_evaluado_o_na` |
| Criterios `R1–R14` | `activado`, `no_activado`, `no_determinante`, `no_evaluado_o_na` |

No se reescribe un `R activado` como `R no_cumple`.

### 7.2 Señal normalizada para agregación

Se añade una columna `senal_fallo`:

| Estado fuente | `senal_fallo` |
|---|---:|
| `S = no_cumple` | `1` |
| `S = cumple` | `0` |
| `R = activado` | `1` |
| `R = no_activado` | `0` |
| `no_determinante` o `no_evaluado_o_na` | vacío (`NA`) |

Una celda se sustenta con: paquete, ficha, sección y cita breve de hasta 20 palabras. Si no existe declaración suficiente, se usa `no_evaluado_o_na`; no se infiere desde el código.

Columnas mínimas del CSV:

```text
candidato,origen_paquete,familia,criterio,estado_fuente,senal_fallo,
fuente_ficha,fuente_seccion,fuente_cita,convencion_a,observacion
```

### 7.3 R11 y S8

El contrato S47 v6 declara que R11 se activa cuando S8 falla por ausencia de dominancia/no-empeoramiento. Para agregación:

- ambos estados fuente se conservan por trazabilidad;
- `S8=no_cumple` y `R11=activado` representan una sola señal observacional;
- Q2–Q4 usan una señal canónica `S8_R11` y no cuentan S8 y R11 por separado;
- cualquier inconsistencia entre la ficha y esta relación se registra como `HALLAZGO_META`, sin corregir S47.

Otras relaciones derivadas pueden documentarse, pero no alteran la matriz fuente. Solo se excluyen de una agregación cuando la derivación está citada en el contrato v6 o demostrada textualmente en las fichas.

---

## 8. Método de análisis

1. Enumerar exactamente los 21 candidatos y asignar origen 1–12 o 13–21.
2. Poblar la matriz desde las fichas, sin re-evaluarlas.
3. Validar que cada candidato aparece y que toda celda tiene fuente o estado `no_evaluado_o_na`.
4. Calcular frecuencias sobre `senal_fallo=1`, con denominador 21 y número de `NA` visible.
5. Calcular coocurrencias sobre señales canónicas, excluyendo duplicados derivados.
6. Agrupar por firma exacta de señales canónicas. Esta agrupación determinista es el resultado primario de Q4.
7. Opcionalmente producir clustering exploratorio sin dependencias nuevas. Si no aporta claridad, registrar `CLUSTERING_NO_CONCLUYENTE`.
8. Separar `OBSERVACION`, `HIPOTESIS` y `EVIDENCIA_INSUFICIENTE`.

Ninguna métrica o agrupación tiene fuerza normativa sobre DT1.

---

## 9. Productos

Paquete `S48-A/`:

- `00-preflight.md`
- `01-matriz-refutacion.csv`
- `01a-ontologia-y-derivaciones.md`
- `02-frecuencias-y-coocurrencias.md`
- `03-firmas-y-clusters.md`
- `04-interpretacion.md`
- `05-hallazgos-meta.md`
- `06-cierre.md`
- `MANIFEST.sha256`

`06-cierre.md` emite exactamente uno:

```text
ANALISIS_COMPLETO
ANALISIS_PARCIAL_CON_LIMITACIONES
NO_GO_ENTRADA
```

También declara:

- universo analizado;
- preguntas respondidas y no respondidas;
- modo `PAQUETES_Y_CODIGO` o `SOLO_PAQUETES`;
- límites interpretativos;
- ausencia de modificación del repositorio y de S47.

---

## 10. Revisión e independencia proporcional

### 10.1 Contrato

Gato aprueba, rechaza o pausa el **hash exacto** de este documento. ChatGPT preparó sus bytes y no emite aprobación independiente sobre ellos. `AGENTS.md` R4 no exige una cadena recursiva de revisiones: prohíbe que el productor se presente como revisor independiente de la misma unidad.

Una vez aprobado el hash por Gato, no hay otra ronda arquitectónica ni de auditoría previa a la nota de invocación. Si los bytes cambian, Gato decide sobre el nuevo hash; no se genera automáticamente otra propuesta.

### 10.2 Paquete de ejecución

- Productor: Claude Code.
- Revisor independiente: Codex, sobre el paquete exacto y su `MANIFEST.sha256`.
- Veredictos: `APROBAR`, `APROBAR_CON_CAMBIOS` o `BLOQUEAR`.
- Si el paquete cambia tras la revisión, Codex revisa los bytes exactos modificados antes de elevarlos a Gato.
- Reportes temporales, handoffs y análisis no destinados a integración no disparan revisión recursiva.

Se permite una sola ronda de corrección material del paquete. Una segunda necesidad material se eleva a Gato con alternativas concretas; no inicia un ciclo automático.

---

## 11. Presupuesto y detención

Techo de ejecución por defecto: 3 horas. El techo limita esfuerzo; no predefine el resultado.

Al alcanzar el techo, el ejecutor conserva lo producido, completa manifiesto y cierre, y emite `ANALISIS_PARCIAL_CON_LIMITACIONES`. No extiende tiempo sin autorización de Gato.

El ejecutor no se detiene por:

- patrón inesperado;
- celdas `NA`;
- clustering no concluyente;
- hallazgos meta;
- imposibilidad de responder alguna Q;
- repositorio contextual no disponible.

---

## 12. Autoridad siguiente

1. Gato decide sobre el hash exacto de este contrato.
2. Si lo aprueba, Gato emite una nota de invocación conforme a §3.
3. Claude Code ejecuta S48-A READ-ONLY.
4. Codex revisa el paquete exacto.
5. Gato decide qué hacer con el diagnóstico.

Ningún paso posterior queda autorizado por la mera existencia de este documento.

---

## 13. Criterios binarios de aprobación del contrato

El contrato es aprobable si Gato acepta que:

- S47 permanece congelado;
- las rutas actuales se verifican en preflight, no durante la aprobación;
- los hashes de §2 son las anclas de identidad;
- los estados S y R conservan semánticas distintas y se agregan mediante `senal_fallo`;
- S8/R11 se cuentan una sola vez en agregaciones;
- evidencia incompleta produce limitación, no rediseño contractual;
- R4 se aplica a la unidad exacta producida, sin recursión sobre artefactos intermedios;
- la ejecución sigue requiriendo una nota humana posterior.

Si Gato no acepta alguno de estos puntos, la salida es `PAUSAR_O_RECHAZAR`; no se abre automáticamente una v5.

---

**Fin del contrato candidato.**
