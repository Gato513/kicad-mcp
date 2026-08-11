# CONTRATO ARQUITECTÓNICO DE SESIÓN
## `S47-H11-AMPLIACION-13-21` — v1

**Naturaleza:** READ-ONLY DE FUENTES Y ESTADO AUTORITATIVO (idéntica definición que v6 §5.1, heredada sin modificación).
**Relación con S47 v6:** este contrato NO reemplaza `contrato_S47-DT1-SLICE2-CARACTERIZACION_v6.md` (SHA-256 `3b16079cd67357b17ff2d23064c6397454b8a06e4830684c0fa60c2eaac91402`, en adelante **v6**). Lo **extiende puntualmente** bajo el mecanismo H11 de v6 §19 ("Reintentar S47 tras EVIDENCIA_INSUFICIENTE... con presupuesto ampliado"). Todo lo que v6 define y este documento no redefine explícitamente sigue vigente sin cambios: definición de READ-ONLY (§5.1), reglas de refutación S1–S8/R1–R14 (§11.4–11.5), tabla de excepciones §11.7, métricas M1–M4 (§10), tipología de hallazgos (§14), formato de paquete (§15), handoff a Codex (§16) y a ChatGPT (§17), secuencia canónica §18, puntos de decisión H1–H13 (§19). Rige también la fe de erratas ejecutiva de v6 (`fe-de-erratas-ejecutiva-contrato-S47-v6.md`, SHA-256 `63fe27be8ca2fa852d2f5dfef3996549edcced710b2b67275b970c19a36dcdd4`) y su auditoría delta (SHA-256 `55850fdfb656468fe4758c3b782b7d853ec18d39cc8153ca1d6126ee653ee04a`), en particular las Reglas 1–6.
**Autor original:** Claude Chat, Arquitecto principal. **Corrección contractual posterior:** Codex, actuando como escritor controlado por orden humana; por R4 deja de ser revisor independiente de estos bytes.
**Ejecutor previsto:** Claude Code. **Revisor independiente requerido:** una instancia/persona que no haya producido ni modificado esta unidad, designada por Gato. **Auditor:** ChatGPT. **Autoridad:** Humano (Gato).
**Plantilla:** mínima, conforme al compromiso de la fe de erratas §3 (objetivo, preflight, scope, comandos, evidencia esperada, formato, condiciones de detención, autoridad siguiente) — se evita repetir el aparato formal completo de v6 donde v6 ya lo cubre por referencia.

**Precedencia normativa cerrada:** (1) H11 prevalece para objetivo, alcance, presupuesto nuevo, invariancia, autorización y prohibiciones; (2) este contrato prevalece sobre v6 únicamente en la adaptación explícita `12 + 9` de §§4 y 8 y en la Puerta 0 adicional de §§2.1–3; (3) la fe de erratas prevalece sobre v6 en sus seis reglas interpretativas, incluida la Regla 5; (4) la auditoría delta fija la lectura conservadora de sus dos `MAJOR`; (5) v6 rige en todo lo restante. Ninguna cláusula inferior puede ampliar H11 ni convertir evidencia sobre 21 supervivientes en refutación de los 29 clusters.

---

## 0. Origen de este documento

Este contrato responde a la autorización humana **H11** (Gato, 2026-08-08 14:19:59 UTC−03:00, América/Asunción, proyecto `MCP_AUDITOR_KICAD`), que:

1. Amplía el presupuesto de S47 exclusivamente para materializar y caracterizar los 9 supervivientes pendientes (candidatos 13–21).
2. Deja invariante el resultado ya demostrado sobre los 12 candidatos originales: **0 APTO/APTO_CONDICIONAL de 12**.
3. Exige que la conclusión global sobre los 21 supervivientes se emita solo después de caracterizar los 9 pendientes, reconciliar `12 + 9`, y verificar trazabilidad e invariancia de ambos subconjuntos.
4. Exige que esta continuación se rija por un contrato nuevo, acotado y versionado (este documento) y una nota de invocación nueva (`nota-invocacion-S47-H11-AMPLIACION-13-21.md`).
5. Exige que el resultado de esta continuación sea una unidad de evidencia nueva, íntegra y manifestada, sin modificar ni sobrescribir el paquete S47 original.
6. Exige revisión independiente (Codex + ChatGPT) antes de cualquier decisión posterior.
7. Prohíbe expresamente: rediseñar o iniciar S48; implementar DT1 Slice 2; modificar los primeros 12 candidatos; ampliar el universo más allá de los 9 pendientes; alterar el resultado técnico ya validado; declarar anticipadamente un resultado global para los 21; cerrar DT1; commit, push, PR o merge.
8. Exige que Claude Code no comience la ejecución hasta que este contrato y la nota de invocación sean revisados y aceptados expresamente por la Autoridad.

**Este contrato materializa los puntos 5 y 7 de H11. No autoriza ejecución por sí solo — ver §9.**

---

## 1. Objetivo

Caracterizar, con ficha completa, los **9 candidatos supervivientes de S47 que quedaron sin evaluar por agotamiento del presupuesto original** (`UMBRAL_P_STOP_FICHAS=12` de v6), aplicando exactamente el mismo método de v6 Fase 3 (§8, §10, §11.4–11.7) que ya se aplicó a los 12 primeros. Producir después una **reconciliación formal** que combine los 12 veredictos individuales ya cerrados con los 9 nuevos y aplique la secuencia de agregación de v6 §11.3 sobre el universo completo de 21 supervivientes, para determinar si corresponde un veredicto distinto de `EVIDENCIA_INSUFICIENTE`.

**Esta sesión no autoriza S48 ni implementación.** Si la reconciliación produce `GO`, `GO_DENTRO_DEL_PRESUPUESTO` o `GO_CONDICIONAL_PROPUESTO`, la autorización de S48 sigue el mismo camino de v6 §18–19 (H2 o H2-bis), tras revisión independiente de **esta** unidad.

---

## 2. Identidad congelada de los candidatos 13–21 (hash-lock)

Fuente autoritativa: `02-candidatos/enumeracion.md §5–6` del paquete S47 original, ruta efectiva ratificada por la Autoridad (`/tmp/tmp.ZedgZwIGVl.s47/S47-CORREGIDO-2/autoridad/CONSTANCIA_AUTORIDAD_S47.md §1`): `/tmp/tmp.ZedgZwIGVl.s47/S47/`.

Anclas completas observadas y obligatorias:

```
MANIFEST.sha256 original          cb3bfee2b25f1e34f3b46a3ead35be7b4525eb9efb24499d0a9dba0cf5fcf078
CONTRACT.sha256 original          7ee91544b55916c9e92afe216c271c0b742a0e5623f0f05c9373e4c761385456
02-candidatos/enumeracion.md      93f572849a0e41a0f270649cf17a3ae83974e547bf9b3d7248dbace951b7b67c
05-veredicto.md                   ec538b9c99a45099aabe4c4cfdda17fd2ef9603971d6694931b8fbad9ac6df3a
Unidad reproducible corregida     /tmp/tmp.ZedgZwIGVl.s47/S47-CORREGIDO-2/
MANIFEST.sha256 unidad corregida  53992da2711279cbc9e0d27d48aa7c835a140acac74b5cf957015b001005c5d0
tools/inventory.py                159087703980c4ad2bb4606b4c208ef289e1679495849d1442cacc18052a81e5
tools/cluster.py                  a33a82695166399e86d64a9feb563ec35376808d48731c6e7e99d3768eed97b0
raw/inventory.json                1d6f8eb50a61fd02e07365e22e58f4a06b0d27f0af0f8167ac06fb38bc15db39
raw/clusters.json                 dd2d097dc86d20e392f2689412daf042b7c6565cd635ff0f96c93ec11408d2de
```

```
13. {_similars}                    LOC=13
14. {_via_params, add_via}         LOC=110  (helper + closure)
15. {delete_track}                 LOC=51
16. {delete_via}                   LOC=24
17. {get_component_detail}         LOC=30
18. {get_tracks}                   LOC=92
19. {reload_board_from_disk}       LOC=59
20. {save_board}                   LOC=44
21. {set_footprint_ref}            LOC=116
```

Orden por `clave_orden` (v6 §7.1.5), idéntico al del paquete original. **El universo evaluable de esta sesión es exactamente esta lista de 9 elementos — ni uno más, ni uno menos** (H11 punto 1 y prohibición "ampliar el universo más allá de los nueve pendientes").

### 2.1 Verificación de integridad de identidad (obligatoria, Puerta 0)

Antes de materializar ninguna ficha, el ejecutor debe:

1. Verificar el SHA-256 del archivo `MANIFEST.sha256` original contra el valor de §2 y luego ejecutar `sha256sum -c MANIFEST.sha256` desde `/tmp/tmp.ZedgZwIGVl.s47/S47/` (exit 0). Verificar igualmente el manifiesto de `S47-CORREGIDO-2/` contra su hash de §2 y con `sha256sum -c` (exit 0). Si falta una unidad, un hash difiere o un manifiesto falla → **NO_GO_ENTRADA**. Antes de caracterizar, preservar una copia byte-idéntica del paquete original fuera de `/tmp`, en destino nuevo autorizado, sin mover ni modificar el original, y registrar ruta y hashes.
2. Verificar por SHA-256 los cuatro archivos `tools/inventory.py`, `tools/cluster.py`, `raw/inventory.json` y `raw/clusters.json` de `S47-CORREGIDO-2/`. Re-derivar sobre `SHA_S47_ENTRADA` con estos comandos exactos, desde la raíz del repositorio y con salidas nuevas bajo `$S47_TMP`:

   ```bash
   python /tmp/tmp.ZedgZwIGVl.s47/S47-CORREGIDO-2/tools/inventory.py "$S47_TMP/inventory-ext.json"
   python /tmp/tmp.ZedgZwIGVl.s47/S47-CORREGIDO-2/tools/cluster.py "$S47_TMP/inventory-ext.json" "$S47_TMP/clusters-ext.json"
   ```

   Ambos comandos deben terminar con exit 0. `inventory-ext.json` debe ser byte-idéntico a `raw/inventory.json`; `clusters-ext.json` debe ser byte-idéntico a `raw/clusters.json`, comprobado con `cmp -s` (exit 0) y SHA-256 completo. La serialización canónica es exactamente el JSON producido por estos scripts anclados; no se admite otra herramienta, copia o normalización. Esto re-verifica Fase 2 y no materializa ni caracteriza fichas 1–12.
3. Comparar el resultado re-derivado contra los contadores y la lista congelada de §2 de este documento:
   - `N_universo_total == 29`
   - `N_excluidos_institucional == 8`
   - `N_excluidos_presup == 0`
   - `N_supervivientes == 21`
   - El array JSON `survivors` de `clusters-ext.json`, en su orden físico, debe ser byte-semánticamente idéntico al array `survivors` del `raw/clusters.json` anclado: mismas 21 listas, mismos strings y mismo orden. Además, posiciones 1–12 deben coincidir con `enumeracion.md §5` y posiciones 13–21 con §2 de este contrato. La comparación se registra mediante un script de lectura JSON conservado en `01-comparacion-identidad.py` y manifestado en la unidad nueva; exit 0 significa igualdad completa y cualquier otro exit significa drift.
4. Si CUALQUIERA de las comparaciones de (3) difiere → **NO_GO_ENTRADA** con hallazgo `DRIFT_UNIVERSO_S47` (§8 de este documento). No se improvisa una reconciliación sobre una base que cambió; se eleva al humano.
5. Si todas las comparaciones son idénticas → Puerta 0 continúa. Se registra la coincidencia exacta como evidencia en `00-preflight-ext.md`.

---

## 3. Preflight / Puerta 0

Idéntica a v6 §5, sin modificación, con el añadido de §2.1 arriba. En particular:

- `S47_TMP` nuevo, distinto del usado en S47 original, fuera del working tree, validado canónicamente (v6 §5.4).
- `GIT_OPTIONAL_LOCKS=0`, `PYTEST_ADDOPTS=''`, caches redirigidas a `$S47_TMP` (v6 §5.2).
- `SHA_S47_ENTRADA` debe coincidir con el checkpoint `33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b` (mismo checkpoint que v6 §2 — verificar que no hubo commits nuevos en `master` desde el cierre de S47 original; si los hubo, aplica R-P0.9 de v6 igual que en S47 original).
- Working tree limpio, rama `master`, HEAD no detached, `origin/master` alineado (R-P0.1–R-P0.8).
- Reglas R-P0.9–R-P0.15 de v6 aplican sin cambio, incluida R-P0.15 (`GIT_OPTIONAL_LOCKS`/`PYTEST_ADDOPTS`) conforme al `NOTE-01` de la auditoría delta.
- Baseline offline (`ruff`, `ruff format --check`, `mypy`, `pytest` no-integration) debe reproducir `BASELINE_ACTUAL_OBSERVADO` de S47 original (`passed=406, failed=0, errors=0, deselected=77`) sin drift negativo (R-BL.0–R-BL.2 de v6).

Puerta 0 de esta extensión emite **GO** solo si, además de lo anterior, §2.1 completo (1)–(5) resulta en coincidencia exacta.

Todos los comandos, stdout, stderr y exit codes de Puerta 0 se capturan sin truncamiento en `00-preflight-ext.md` y `COMANDOS-Y-EXIT-CODES.md`. No se ejecuta `uv sync` ni se accede a red: el entorno existente debe satisfacer v6; si no lo hace, corresponde `NO_GO_ENTRADA`.

---

## 4. Presupuesto de esta sesión

```
UMBRAL_P_STOP_FICHAS_EXT = 9   (fijo, no ajustable dentro de esta sesión;
                                 cualquier ampliación posterior requiere
                                 nueva H11 y nuevo contrato)
Candidatos a materializar = exactamente los 9 de §2, en el mismo orden.
UMBRAL_P_STOP_FICHAS_ACUMULADO = 21 (solo para v6 §11.3 regla 5 al
                                      reconciliar 12 congeladas + 9 nuevas;
                                      no amplía el presupuesto nuevo de 9).
Presupuesto de tiempo combinado (arquitectura+auditoría+corrección+
verificación), heredado de la fe de erratas §3: 90 minutos. Máximo dos
rondas de auditoría; una tercera solo con decisión humana explícita.
```

No se generan fichas adicionales aunque el ejecutor identifique candidatos nuevos por cualquier vía (refactor incidental, hallazgo colateral, etc.) — eso sería ampliar el universo, prohibido por H11 punto 1. Cualquier candidato nuevo detectado se registra como hallazgo §14 (`OTRO`), no se ficha.

Si la sesión se detiene antes de completar exactamente las nueve fichas nuevas, la unidad queda `INCOMPLETA`, conserva `N_fichas_completas < 21` y no puede emitir un veredicto reconciliado sobre los 21. No se reutiliza presupuesto sobrante ni se incorporan suplentes.

---

## 5. Método de caracterización (Fase 3, sin cambios respecto de v6)

Para cada uno de los 9 candidatos: mismas cuatro dimensiones M1–M4 (v6 §10), mismos gates S1–S8 (v6 §11.4) y criterios de rechazo R1–R14 (v6 §11.5), misma tabla normativa de excepciones E1–E3 (v6 §11.7), mismo tratamiento de `M2_estado_actual`/`M2_estado_proyectado` con las Reglas 3–4 de la fe de erratas (guía refutable, no gate rígido, cuando la comparación homogénea no sea limpia). Mismo esquema de ficha que las 12 originales (ver cualquiera de `01-delete-copper.md`…`12-segment-intersects-bbox.md` como plantilla de formato).

Nota estructural para el ejecutor (no vinculante, señal del riesgo residual #2 de `05-veredicto.md` de S47 original): 5 de los 12 candidatos closure-bearing fallaron por el mismo patrón (S1 vs. S8, por dependencia de `_audit_error`/`_resolve_board`/`_similars` compartidos). De los 9 pendientes, `{_via_params, add_via}` (14), `{get_tracks}` (18), `{reload_board_from_disk}` (19), `{save_board}` (20) y `{set_footprint_ref}` (21) son closures — no se presupone el resultado; la ficha debe rederivar el gate S1/S8 igual que se hizo para los 12 originales, sin copiar la conclusión por analogía.

---

## 6. Invariancia del paquete original (H11 punto 2)

**Prohibido en esta sesión:**

- Modificar, mover, renombrar o regenerar cualquiera de los 7+ artefactos del paquete S47 original (12 fichas, `enumeracion.md`, `descartados.md`, `03-refutacion.md`, `04-colisiones.md`, `05-veredicto.md`, `06-cierre.md`, `MANIFEST.sha256`, `CONTRACT.sha256`).
- Reinterpretar cualquiera de los 12 veredictos individuales ya cerrados (`NO_APTO` unánime).
- Reabrir `03-refutacion.md` de S47 original o proponer un veredicto distinto para los candidatos 1–12.

**Obligatorio:** referenciar el paquete original por los hashes completos de §2, verificados en §2.1, citándolos en todo artefacto nuevo que dependa de ellos. Las clasificaciones 1–12 se importan mecánicamente desde el `05-veredicto.md` anclado; no se copian para editarlas ni se re-derivan.

---

## 7. Artefactos obligatorios de esta sesión

Destino único: `$S47_TMP/S47-EXT-13-21/`, donde `$S47_TMP` es una ruta absoluta canónica creada para esta sesión fuera del working tree y distinta de `/tmp/tmp.ZedgZwIGVl.s47`. Antes de escribir, `realpath -m "$S47_TMP/S47-EXT-13-21"` debe quedar estrictamente bajo el `realpath` de `$S47_TMP`; el destino no debe existir ni ser enlace simbólico. Si existe, es ambiguo, escapa de `$S47_TMP` o no puede comprobarse → `NO_GO_ENTRADA`, sin borrar, mezclar ni sobrescribir nada.

```
S47-EXT-13-21/
├── PACKAGE-METADATA.md          ← referencia cruzada explícita a v6, a la
│                                   nota de invocación de esta extensión,
│                                   y a MANIFEST.sha256 del paquete S47
│                                   original (por hash, no por copia)
├── CONTRATO-AUDITADO.md          ← copia byte-a-byte de este documento
├── CONTRACT.sha256
├── 00-preflight-ext.md           ← incluye el resultado íntegro de §2.1
├── 01-comparacion-identidad.py   ← comparación JSON exacta usada en Puerta 0
├── INFORME-EJECUCION.md          ← inicio/cierre, productor, entradas, salidas,
│                                   procedencia, limitaciones y resultado
├── COMANDOS-Y-EXIT-CODES.md      ← comandos, stdout/stderr y códigos de salida
├── GIT-ANTES-DESPUES.md          ← branch, HEAD, status y worktrees antes/después
├── 13-similars.md … 21-set-footprint-ref.md   ← 9 fichas completas
├── 03-refutacion-ext.md          ← S1-S8/R1-R14/M1-M4 consolidado de los 9
├── 04-colisiones-ext.md
├── 04-hallazgos-fuera-de-scope-ext.md
├── 05-RECONCILIACION.md          ← ver §8 de este contrato
├── 06-cierre-ext.md
└── MANIFEST.sha256
```

`05-RECONCILIACION.md` es el artefacto central de esta sesión — no existía en v6, se define en §8 abajo.

---

## 8. Procedimiento de reconciliación final (12 + 9 → 21)

`05-RECONCILIACION.md` debe contener, en este orden:

1. **Identidad verificada:** referencia a §2.1 de este contrato (evidencia de que la re-derivación coincidió exactamente con el universo congelado).
2. **Tabla de los 12 veredictos originales**, citados por hash del archivo de origen (`05-veredicto.md` de S47 original), sin reinterpretación — literal `NO_APTO` × 12.
3. **Tabla de los 9 veredictos nuevos**, con la misma estructura de columnas que `02-candidatos/README.md` de S47 original (candidato, LOC, S1, S7, veredicto).
4. **Contadores del universo combinado:**
   ```
   N_universo_total           = 29   (sin cambio)
   N_excluidos_institucional  = 8    (sin cambio)
   N_excluidos_presup         = 0    (sin cambio)
   N_supervivientes           = 21   (sin cambio)
   N_fichas_completas         = 21   (12 + 9 — ahora igual a N_supervivientes)
   N_evaluados                = 21
   ```
5. **Aplicación formal de v6 §11.3**, en el mismo orden estricto de reglas 1–13, sobre el universo combinado. La única sustitución permitida es la definida en §8.6 para la regla 5; no puede inferirse ninguna otra adaptación.
6. **Veredicto único y final sobre el universo de 21 supervivientes**, con la misma disciplina de siete estados de v6 §1.1 y la adaptación cerrada siguiente:

   - para la regla 5 solamente, `UMBRAL_P_STOP_FICHAS` se sustituye por `UMBRAL_P_STOP_FICHAS_ACUMULADO=21`; por tanto, la regla 5 deja de activar solo si hay exactamente 21 fichas completas y 21 evaluados;
   - las reglas 6–13 se aplican literalmente, sin sustituir contadores;
   - como `N_excluidos_institucional=8`, un APTO produce `GO_DENTRO_DEL_PRESUPUESTO`, no `GO`; si todos los 21 evaluados son `NO_APTO`, produce `NO_GO_POR_PRESUPUESTO`, no `NO_GO`; una excepción admisible puede producir `GO_CONDICIONAL_PROPUESTO`; cualquier candidato sin clasificación o mezcla conservadora produce `EVIDENCIA_INSUFICIENTE` conforme a v6/errata;
   - el resultado se etiqueta `ALCANCE_SUPERVIVIENTES_21`; no afirma refutación o ganador sobre los ocho clusters institucionalmente excluidos.
7. **Trazabilidad explícita:** cada uno de los 21 candidatos debe aparecer exactamente una vez en la tabla combinada, con su fuente (paquete original vía hash, o esta extensión) citada.

**Ninguna sección de este contrato ni de la nota de invocación asociada predetermina el resultado de §8.6.** El veredicto se deriva mecánicamente de las 9 fichas nuevas más los 12 hechos ya cerrados — H11 prohíbe explícitamente "declarar anticipadamente un resultado global para los 21" y esta prohibición se aplica también a este contrato: no fija de antemano cuál de los siete estados corresponde.

---

## 9. Condiciones de detención (`NO_GO_ENTRADA` de esta extensión)

Mismas cuatro categorías de la fe de erratas Regla 6 (preflight fallido, mutación intentada, violación de scope, ausencia de autorización humana), aplicadas a este contrato, más:

```
NO_GO_ENTRADA adicional de esta extensión:
  - §2.1 detecta drift entre el universo re-derivado y la lista congelada
    de §2 (DRIFT_UNIVERSO_S47).
  - El paquete S47 original no verifica contra su propio MANIFEST.sha256.
  - Este contrato o la nota de invocación asociada no están, ambos,
    expresamente aceptados por la Autoridad antes de invocar Claude Code
    (H11 punto final, y §0 punto 8 de este documento).
  - Cualquier intento, durante la ejecución, de tocar, mover o regenerar
    un artefacto del paquete S47 original (§6).
  - El destino `$S47_TMP/S47-EXT-13-21/` ya existe, es enlace, es ambiguo
    o resuelve fuera de `$S47_TMP`.
  - Falta o difiere cualquier ancla completa de §2, herramienta o insumo.
```

Cualquier otra imprecisión se documenta como hallazgo §14/`04-hallazgos-fuera-de-scope-ext.md` o produce `EVIDENCIA_INSUFICIENTE` sobre el subconjunto afectado — no `NO_GO_ENTRADA` — conforme a la misma disciplina de la fe de erratas Regla 4–6.

---

## 10. Scope permitido y prohibido

Permitido: idéntico a v6 §13.1, restringido a los 9 candidatos de §2 y a la lectura del paquete S47 original (solo lectura, nunca escritura).

Prohibido: idéntico a v6 §13.2, más — textualmente, las ocho prohibiciones de H11:

```
- Rediseñar ni iniciar S48.
- Implementar DT1 Slice 2.
- Modificar los primeros 12 candidatos.
- Ampliar el universo más allá de los nueve pendientes.
- Alterar el resultado técnico ya validado (0/12 APTO).
- Declarar anticipadamente un resultado global para los 21.
- Cerrar DT1.
- Commit, push, PR o merge.
```

---

## 11. Revisión independiente obligatoria (H11 punto 7)

Antes de cualquier decisión posterior (S48, H2, H2-bis, o cualquier otra):

1. Un **revisor independiente que no haya escrito esta unidad** revisa el paquete `$S47_TMP/S47-EXT-13-21/` completo con el mismo alcance de v6 §16 (V0.1–V0.10, V1–V17), aplicado a las 9 fichas nuevas y, en particular, a `05-RECONCILIACION.md` — con foco añadido en: (a) que §2.1 se ejecutó y coincidió; (b) que ningún artefacto del paquete original fue tocado; (c) que la adaptación acotada de v6 §11.3 en §8 es correcta. Puede ser otra instancia de Codex designada por Gato, siempre que no haya producido ni modificado los bytes revisados.
2. **ChatGPT** reconcilia conforme a v6 §17, alcance restringido al delta de esta extensión (mismo patrón que la "verificación delta breve" ya usada para la fe de erratas) — no reabre la auditoría íntegra de v6.
3. Solo tras (1) y (2), la Autoridad decide sobre S48 (H2 o H2-bis) o sobre cualquier otro paso siguiente.

---

## 12. Puntos de decisión humana relevantes

Heredados de v6 §19 sin cambio, con esta sesión operacionalizando **H11**. Los siguientes permanecen exclusivamente humanos y no se activan por ningún resultado de esta extensión por sí sola: H2, H2-bis, H7, H9, H10, H12, H13.

---

## 13. Nota metodológica final

Esta extensión no reabre ninguna de las seis iteraciones de v6. Se limita a aplicar el mismo método ya validado a los 9 candidatos pendientes y a combinarlos mecánicamente con los 12 cerrados. La honestidad epistemológica de v6 §20 se preserva: si los 21 supervivientes resultan `NO_APTO`, el estado contractual es `NO_GO_POR_PRESUPUESTO` por las ocho exclusiones institucionales; si alguno califica, el estado se deriva de §8 sin atajos. Ningún estado autoriza S48 ni implementación.

---

**Fin del contrato `S47-H11-AMPLIACION-13-21` v1.** Pendiente de revisión y aceptación expresa de la Autoridad humana antes de que Claude Code comience cualquier ejecución (§0 punto 8, §9).
