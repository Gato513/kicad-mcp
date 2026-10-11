# Backlog — kicad-mcp

Generado en la reorganización documental (2026-07-24), repriorizado según
`docs/historico/CONTEXT-v7.md` (post-sesión 24) — la secuencia estricta de
Fase 3 sube al frente los ítems de esa secuencia (solder mask ANT1,
generalización D-23.2) y baja el CRUD de esquemático a P3, ya que v7 lo
excluye explícitamente del alcance de Fase 3. También sintetizado de
`docs/historico/analisis/ANALISIS-ESTADO-Y-BACKLOG.md` §Parte 2 y las
fricciones registradas en sesiones 21–24. Dentro de cada prioridad, orden
aproximado de severidad.

---

## P0 — Bloqueantes de dogfooding / release

### F-V3-ZONE-FILL-CRASH — `add_zone(fill=true)` crashea KiCad de forma reproducible en la 3ª-4ª llamada sobre boards grandes — defecto real corregido y commiteado (sesión 48, commit 047ba2e), pendiente de revisión/push humana (DoD #6), causa exacta del crash de HackRF sin confirmar

**Origen:** sesión 33, Validation Suite Nivel C (HackRF One, 437
footprints / 380 nets / 4 capas). Reproducido 3 veces, siempre con el
mismo resultado: KiCad se cae (2 veces) o queda colgado transitoriamente
(1 vez), disco con **710 zonas** (3 reales + 707 fragmentos sin net) tras
cada intento fallido. Sesión 34a lo clasificó "no concluyente", orientado
hacia fragmentación interna de pcbnew — **esa clasificación queda
superada por la investigación de sesión 48** (abajo). Detalle forense
histórico: `validation-suite/level-c/hackrf-one/validation-report.md`
§Fricciones; análisis de contratos original en
`docs/analisis/auditoria-contratos-bridge.md` §4.

**Sesión 48 — tres diagnósticos evaluados y auditados por Codex, dos
refutados con evidencia dura:**

1. **v1 (bug de limpieza de keepouts stale) — REFUTADO.** Comparando UUID
   (no sólo nombres) de los keepouts entre pasadas de los backups de
   sesión 33: 0 UUID en común entre pasadas, con nombres idénticos — el
   borrado funciona. Los "707 fragmentos sin net" son recómputo legítimo
   de `enforce_hole_clearance` para *todas* las zonas de cobre reales del
   board en cada pasada (crecen porque sesión 33 agregaba una zona real
   nueva por llamada), no basura acumulada.
2. **v2 (subir el timeout IPC de 2000ms a 30000ms) — BLOQUEADO.**
   `docs/specs/restricciones-kicad.md:23-27` fija timeout duro de 2000ms
   por request como restricción normativa (F1) — "operaciones grandes se
   trocean o se rechazan", no se esperan más. El "techo de 30s de kipy"
   usado para justificar el valor no existe (`sleeps` nunca se incrementa
   en el busy-loop de `kipy/board.py`).
3. **v3 (clasificar el timeout de refill como `KICAD_TIMEOUT` vs
   `KICAD_NOT_RUNNING` según presencia del archivo de socket) —
   BLOQUEADO.** Un socket Unix puede quedar huérfano tras un crash
   abrupto (SIGKILL/segfault) sin limpiarse — "socket presente" no
   implica "KiCad viva". Clasificar así habría reportado un crash real
   como "sólo ocupado, reintentá", peor que el estado actual.

**v4 — implementado, verificado localmente, commiteado (047ba2e),
pendiente de revisión humana (nunca push, DoD #6).** Único cambio: `create_items` en
`enforce_hole_clearance` (`src/kicad_mcp/bridge/ipc.py`) trocea en lotes
de `_ENFORCE_HOLE_CLEARANCE_BATCH_SIZE=100` en vez de 1 request por ítem.
Medido en vivo contra `tests/fixtures/004_real` (189 fp, 808 vías) con el
timeout real de producción: N=100 → 0.93s avg/1.14s max, N=200 → 1.40s
avg/1.56s max — ambos bajo 2000ms; un único request con 707 ítems (sin
trocear) tardaba 8.40s, muy por encima. Test offline
(`tests/test_pcb_hole_clearance.py::test_enforce_hole_clearance_batches_create_items`)
verifica N=250 → 3 lotes de `[100, 100, 50]`. Test GUI
(`tests/test_pcb_session48_zone_fill_batching_gui_slow.py`) confirma el
round-trip real contra KiCad sobre `despertador-routed` (smoke de
correctitud, no de carga — ver limitación siguiente). Aprobado por Codex
(auditoría previa del plan, 4ª ronda) sin hallazgos.

**Laguna declarada, confirmada empíricamente, no cerrada por este fix:**
`refill_zones()` es una operación atómica — kipy 0.7.1 no expone fill
parcial/selectivo (`docs/investigacion/19-zonas-ipc.md`), no se puede
trocear. **Probe manual ad hoc de esta sesión, no versionado como test**
(evidencia de sesión, no artefacto reproducible en CI): sobre
`tests/fixtures/004_real` con sus 2 zonas de cobre reales preexistentes,
crear una zona nueva de apenas 5×5mm con net real (`+3.3V`) superó igual
los 2000ms (`ConnectionError` tras 2.74s). Esa única medición acredita el
timeout observado en ese momento; no prueba por sí sola, de forma
concluyente, que la población de zonas preexistente domine el costo en
general — es la lectura más consistente con los datos (el troceo de
`create_items`, que corre *después* del refill dentro de
`enforce_hole_clearance`, no llegó a ejecutarse porque el timeout saltó
antes), pero queda como inferencia razonable, no medición repetida.
**No confirmado que este fix, por sí solo, elimine el crash de HackRF**
— sólo que corrige el defecto que sí estaba mal (troceo de
`create_items`) y dejó honesta la laguna que sigue sin solución dentro de
las restricciones normativas actuales (timeout duro de 2000ms +
`refill_zones()` no-troceable).

**Construir un GUI test que demuestre multi-lote en vivo con pad holes
reales** (no keepouts ni vías sintéticas — ver hallazgo colateral abajo)
requeriría sintetizar >100 pads PTH/NPTH vía protobuf de kipy
(`PadStack`/drill/capas de cobre) sin zonas de cobre grandes
preexistentes — evaluado como desproporcionado para esta unidad, queda
como trabajo futuro si se necesita demostración en vivo.

**Próximo paso, si reaparece:** repro fiel contra HackRF One (riesgo
deliberado, decisión humana) o rediseño de `_supervise` para no
reconectar mientras un comando previo puede seguir vivo en KiCad
(candidato a ADR propio, fuera de alcance de sesión 48 — ver hallazgo de
carrera timeout→reconexión, reproducido 4 veces seguidas sobre
`004_real` sin llegar a crash: produce cuelgue transitorio de ~22s, no
corrupción).

**Fuente:** sesión 33 (hallazgo), sesión 34a (clasificación superada),
sesión 48 (dos hipótesis refutadas, defecto real corregido — timeout
insuficiente para `create_items` sin trocear —, mecanismo de timeout de
`refill_zones()` confirmado como alcanzable en boards de densidad media,
causa exacta del crash de HackRF sin confirmar, fix commiteado en 047ba2e,
pendiente de revisión/push humana).

---

### F-VIAS-CLEARANCE-DEAD-CODE — protección de vías ajenas en `enforce_hole_clearance` nunca se ejecuta en producción — es D-23.3/R16, ver entrada canónica

**Es el mismo hallazgo que D-23.3/R16 (sesión 23, `docs/DECISIONES.md`),
no uno nuevo** — sesión 48 lo redescubrió acá, como hallazgo colateral de
F-V3-ZONE-FILL-CRASH (arriba), sin cruzar referencia con la deuda técnica
ya documentada. Causa raíz confirmada sesión 48, juicio cruzado con
Codex en sesión 49 (veredicto: BLOQUEAR, fix diferido). Detalle completo,
evidencia y trigger explícito de reapertura: **§"P3 — Loop de vías de
`enforce_hole_clearance` posiblemente código muerto (R16, D-23.3)"** más
abajo en este mismo documento — esa es la entrada canónica de severidad,
ésta queda sólo como puntero para quien la encuentre por orden histórico
de descubrimiento.

### F-V3-ROUTER-TIMEOUT-HARD — Freerouting 2.1.0 entra en crash-loop interno sobre boards grandes (HackRF One) — investigado sesión 49: bug upstream ya corregido en 2.2.3+, pendiente confirmar completitud

**Origen:** sesión 33, Validation Suite Nivel C (HackRF One).

`route_board(timeout_s=3600)` no completó. El log interno de
Freerouting (33 líneas totales en ~55 min de corrida) no registra
**ninguna** línea de score/progreso — solo 6 `NullPointerException`
repetidas en `MazeSearchAlgo.expand_to_target_doors` (`target_shape`
null), distribuidas de forma intermitente a lo largo de toda la
corrida. Diagnóstico distinto al de sesión 32 (score estancado cerca de
completar, con progreso real hasta ahí): acá el motor no avanza,
crashea internamente en loop sin indicio de por qué esta topología
específica (4 capas, 380 nets, plano GND parcial) dispara la excepción.

**Investigación sesión 49 (repro standalone, sin KiCad vivo).** El
`route.dsn` exacto de la corrida de sesión 33 seguía en
`validation-suite/level-c/hackrf-one/working/.kicad-mcp/autoroute/route.dsn`
(4 capas, 379 nets — coincide). Repro aislado: `java -jar
freerouting-X.jar -de route.dsn -do route.ses -host KiCad` (mismo
invocation que `bridge/autoroute.py:_run_freerouting`), sin tocar
KiCad ni el repo.

- **Búsqueda upstream:** `gh api search/issues -f q='repo:freerouting/freerouting
  MazeSearchAlgo NullPointerException'` encontró PR #658 ("Fix NPE in
  combine_traces and AIOOBE in BatchAutorouter for >2-layer boards",
  cerrado sin mergear pero con análisis de causa raíz aceptado por el
  maintainer). El **changelog oficial de v2.2.3** confirma el fix:
  *"Fixed routing failures on boards with more than 2 copper layers
  (PR #671) — `RouterSettings` incorrectly hardcoded 2-layer defaults
  for all per-layer arrays... Any board with more layers could crash
  with `ArrayIndexOutOfBoundsException` [o NPE aguas abajo]"* — con
  crédito explícito a los reportes de #657/#658. HackRF One es
  exactamente ese caso (4 capas, >2).
- **Repro con 2.1.0 (el mismo log de sesión 33):** 6 `NullPointerException`
  en `MazeSearchAlgo.expand_to_target_doors`, 0 líneas de progreso, en
  33 líneas totales de log.
- **Repro con 2.2.3 (Java 26, `/usr/lib/jvm/java-26-openjdk` — 2.2.3+
  requiere JDK ≥21 con class-file version 69, no corre con Java 21):
  25 minutos de corrida sobre el mismo `route.dsn`, 2045 líneas de log,
  0 líneas `ERROR`, 0 `NullPointerException`. Actividad normal de
  pass 1 (fallos de inserción de traza puntuales, esperables en un
  board denso — no crashes) hasta que el timeout externo (1500s) cortó
  el proceso; el propio Freerouting había registrado
  `PullTightAlgo.is_stop_requested: time limit exceeded` segundos antes,
  sin abortar.

**Veredicto: el bug de crash-loop está corregido upstream desde v2.2.3
(2026-05-08), casi un año de desarrollo por delante de la 2.1.0 usada en
sesión 33 (releases intermedios: 2.2.0-2.2.4, 2.3.0, hoy 2.4.1).** Lo
que esta sesión NO confirma: si el ruteo **completa** en un timeout
razonable — el proceso de prueba no terminó el pass 1 en 25 min de un
solo hilo antes de que el timeout externo lo cortara (sin señal de
estancamiento; podría necesitar más tiempo, o beneficiarse de
multi-hilo/tuning que 2.2.3+ expone). Eso es un problema de
tiempo/calidad, no el crash P0 original.

**Severidad revisada:** ya no bloquea `route_board` end-to-end por un
bug interno de Freerouting sin salida — hay un camino de mitigación
conocido (subir de versión). Sigue siendo **fuera del control de
`kicad-mcp`** arreglar el motor en sí; lo accionable acá es actualizar
la versión de Freerouting recomendada/probada en la documentación de
entorno (`scripts/verificar_entorno.py` no pinea versión hoy, sólo
apunta a la página de releases genérica).

**Trigger para cerrar del todo:** correr `route_board` real (vía
`route_board` de kicad-mcp, no el repro standalone) con Freerouting
≥2.2.3 contra HackRF One con un timeout largo (≥3600s, como sesión 33)
y confirmar que produce un `.ses`/ruteo válido — no sólo que no
crashea. Requiere KiCad abierto + `KICAD_MCP_FREEROUTING_JAR` seteada
(no disponibles en esta sesión, ver `verificar_entorno.py`). Candidato
natural para retomar la Validation Suite Nivel C.

**Hallazgo colateral cerrado (sesión 50):** el repro standalone de
sesión 49 sólo pudo correr Freerouting 2.2.3+ invocando Java 26
manualmente (`/usr/lib/jvm/java-26-openjdk/bin/java`) — Freerouting
≥2.2.3 exige class file version 69 (**Java 25**), y el `java` del PATH
de esta máquina resuelve a 21. `bridge/autoroute.py` **no** tenía forma
de overridear el ejecutable de java en producción (`route_board`
siempre invocaba el literal `"java"`, a diferencia de `system_python`/
`jar_path` que sí resuelven contra env vars) — sin este fix, "seteá el
jar a ≥2.2.3" era **insuficiente** para cerrar este hallazgo vía
`route_board` real, sólo servía para el repro standalone. Cerrado
agregando `KICAD_MCP_JAVA_EXE` (mismo patrón que
`KICAD_MCP_SYSTEM_PYTHON`/`KICAD_MCP_FREEROUTING_JAR`, ver ADR-0011).
El trigger de arriba ahora sí es alcanzable con KiCad abierto + jar
≥2.2.3 + `KICAD_MCP_JAVA_EXE` apuntando a un JDK ≥25.

**Confirmación en vivo (sesión 50), vía `route_board` real, no repro
standalone:** con KiCad 10.0.6 abierto (PCB Editor de
`hackrf-one/working` en foco), jar 2.4.1 + `KICAD_MCP_JAVA_EXE=java-26`,
dos corridas reales de `route_board()` contra el board completo (437 fp
/ 380 nets / 4 capas, 1018 ítems sin rutear reportados por Freerouting):
`timeout_s=600` y `timeout_s=1800`. **Ninguna de las dos crasheó ni
produjo `NullPointerException`/`ERROR`** — ambas arrancaron limpio
(`Auto-routing stage started ... for 1018 unrouted items`) y terminaron
en `KICAD_TIMEOUT` typed error (D-14.4), con D-23.2 intacto (backup G1
en `.kicad-mcp/backups/`, board de disco sin tocar, servidor MCP
responsivo tras el timeout en ambos casos). **Sigue sin confirmarse que
complete** — ninguna corrida pasó de la línea de arranque en el log
capturado (8 líneas ambas veces, 10 min y 30 min), lo que probablemente
sea un artefacto de buffering de stdout de la JVM perdido al matar el
proceso en el timeout (`_run_freerouting` sólo lee `exc.stdout`/
`exc.stderr` de `TimeoutExpired`, que no garantiza haber drenado el pipe)
y no evidencia de que el router esté trabado — pero no se puede
distinguir una cosa de la otra con la instrumentación actual. **El
crash-loop P0 queda confirmado resuelto con evidencia real, no sólo
standalone; "completa en tiempo razonable" sigue abierto como ítem de
calidad/tiempo, no bloqueante.**

**Instrumentación del log (sesión 52):** `_run_freerouting` ya no captura
la salida por pipe; la escribe directo a `.kicad-mcp/autoroute/freerouting.log`
mientras corre (seguible con `tail -f`) y el log completo sobrevive al
`KICAD_TIMEOUT` (el error ahora trae `data.log_path` y la cola en el hint).
Con esto la corrida larga del trigger de arriba deja evidencia que distingue
"router trabado" de "router progresando". La corrida real (≥3600 s, KiCad
abierto, jar ≥2.2.3 + `KICAD_MCP_JAVA_EXE`) sigue pendiente.

**Fuente:** sesión 33 (hallazgo original), sesión 49 (causa raíz +
repro standalone, sin cambios de código en el repo), sesión 50 (fix de
`KICAD_MCP_JAVA_EXE` + confirmación real vía `route_board` contra KiCad
vivo). Log de 2.1.0 en
`validation-suite/level-c/hackrf-one/working/.kicad-mcp/autoroute/freerouting.log`
(no versionado — archivo de trabajo); repro de 2.2.3 hecho en
scratchpad, no versionado.

### F-C4-01 — Freerouting se traba en re-ruteo incremental sobre cluster denso ya mayormente ruteado (`anavi-dev-mic`) — investigado sesión 49: mismo fix upstream que F-V3-ROUTER-TIMEOUT-HARD lo resuelve

**Origen:** Ciclo C4, intento de ejecutar el gate GUI pendiente desde
sesión 32d para el fix de stitching (ver entrada P1 "CERRADO
PARCIALMENTE sesión 32d" más abajo). H1
(`tests/test_pcb_session32d_stitching_gui_slow.py`) terminó en
`KICAD_TIMEOUT` a los 638.91s contra KiCad 10.0.5 real.

**Síntoma:** el fixture de H1 (copia de la salida ya ruteada de sesión
31c con la conexión GND de `MK1.3` removida a propósito, para forzar el
escenario "capas opuestas" que el fix de stitching debe resolver);
`route_board()` sin argumentos entró en un estado sin progreso: score
fijo en 969.16–969.19 con "2 unrouted" durante los 73 passes registrados
(~10 min), motor de geometría fallando internamente en cada pass (`the
maze search algorithm could not be created`,
`ShapeSearchTree45Degree.complete_shape: cannot convert Simplex to
IntOctagon`) sobre un net VECINO (`Net-(MK1-Pad2)`), no el pad huérfano
que el test ejercita a propósito.

**Diagnóstico parcial, no concluyente** (investigación completa:
`docs/investigacion/c4-gate-gui-32d-h1-devmic-timeout.md`):
- Descartado: segmento de 0.02mm "degenerado" en ese net — existe
  idéntico, en coordenadas prácticamente iguales, en la corrida exitosa
  de 31c (refutación por comparación directa contra el historial git).
- Paradoja no resuelta: la MISMA geometría final, ruteada por 31c desde
  0 tracks, completó en 184.82s sin errores (15/15 nets). El mismo
  resultado, precargado como estado inicial con solo 1 conexión GND
  faltante, se traba usando el presupuesto completo de 600s.
- Hipótesis más plausible sin confirmación causal: `route_board`/
  Freerouting trataría TODO el cobre preexistente (no solo el del net
  dueño) como obstáculo fijo cuando el board llega ya mayormente
  ruteado, lo que puede volver el remanente de un cluster denso
  (`MK1`/`R1`/`R2`/`C1`/`C2`, ~10mm², 3 nets superpuestos) más difícil
  de resolver que rutear todo junto desde cero con libertad completa.

**Relación con F-V3-ROUTER-TIMEOUT-HARD (arriba):** misma familia de
síntoma (motor de geometría interno de Freerouting 2.1.0 fallando/
trabado sin converger, fuera del control de `kicad-mcp`), pero mecanismo
y escala distintos — acá es un board CHICO (10 footprints) en modo de
re-ruteo incremental sobre un board mayormente ya ruteado, no un board
grande desde cero. Sugiere que la fragilidad del motor de geometría de
Freerouting 2.1.0 no está acotada a "boards grandes" — el disparador
real podría ser densidad de cobre preexistente en el corredor de
búsqueda, independiente de la escala total del board.

**Severidad:** no bloquea el flujo de ruteo-desde-cero (evidencia: mismo
board, misma geometría final, exitoso en 31c). Bloquea específicamente:
(a) el gate GUI 32d — la verificación end-to-end del fix de stitching
H1/H2 sigue sin poder ejecutarse contra el motor real; (b) cualquier
flujo futuro de "completar ruteo sobre un board ya mayormente ruteado"
con clusters densos, patrón no cubierto hoy por ninguna validación de la
Validation Suite.

**Estado:** C4 permanece DETENIDO. No se reintentó H1 con `timeout_s`
mayor — la falla interna del motor se repitió sin variación en los 73
passes con el presupuesto completo ya consumido, sin evidencia a favor
de que más tiempo lo resuelva. No se corrió H2. No se tocó el fixture ni
`route_board`; contrato D-23.2 intacto (timeout ocurre antes de
cualquier persist).

**Investigación sesión 49 (repro standalone, sin KiCad vivo, mismo
método que F-V3-ROUTER-TIMEOUT-HARD).** El fixture actual
(`validation-suite/level-a/anavi-dev-mic/working/anavi-dev-mic.kicad_pcb`,
sin tocar) **ya es** el escenario H1 tal cual está commiteado — no hace
falta reconstruirlo: `MK1` pad 3 (net `GND`) sólo tiene cobre en `F.Cu`,
la zona GND está sólo en `B.Cu`, y `board.GetConnectivity()` confirma que
el pad no tiene ningún ítem físico conectado (huérfano real, verificado
vía API de conectividad de `pcbnew`, no inferido).

- **Export DSN** (`pcbnew.ExportSpecctraDSN`, mismo script que
  `bridge/autoroute.py:_EXPORT_DSN_SCRIPT`) desde ese fixture: 19 nets, 2
  capas. **Hallazgo colateral necesario para poder exportar — ver entrada
  nueva `F-PCBNEW-SWIG-PY314` más abajo**: en esta máquina,
  `board.GetDrawings()`/`GetTracks()` (usados por el export/import real
  de `route_board`) fallan con `AttributeError` bajo Python 3.14 — se
  parcheó sólo en el script standalone de esta investigación
  (`pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__`), NO en
  el repo.
- **Repro con 2.1.0** sobre ese DSN real: score congelado en **969.31,
  "2 unrouted"**, sin mejora durante 52+ passes (300s), 0 `.ses`
  producido — mismo patrón de estancamiento que documentó Ciclo C4 (la
  cifra exacta de score difiere levemente de los "969.16–969.19"
  originales — esperable, Freerouting no es determinista pass a pass,
  ver docstring de `test_pcb_session32d_stitching_gui_slow.py` sobre este
  riesgo — pero el patrón de "congelado, 2 unrouted, sin salida" es
  idéntico).
- **Repro con 2.4.1** sobre el MISMO DSN: **completó limpio en 3m33s**.
  El detector de estancamiento de Freerouting (`PR #634`, en el motor
  desde v2.2.0 — ver evidencia en F-V3-ROUTER-TIMEOUT-HARD arriba) paró
  el autorouter solo tras 10 passes sin mejora ("score 680.00 no mejoró
  más de 0.5 puntos en las últimas 10 passes"), y emitió un **reporte
  legible de las 8 conexiones sin rutear** (incluida `via -> MK1-3`, el
  pad huérfano exacto que el fix de stitching de `route_board` debe
  resolver DESPUÉS vía inserción manual de vía, no vía Freerouting).
  Generó un `.ses` válido (15331 bytes) — resultado parcial utilizable,
  no un cuelgue sin salida.

**Lectura del resultado:** que Freerouting 2.4.1 deje `via -> MK1-3` sin
rutear NO es una regresión — es el comportamiento esperado y necesario:
el mecanismo de stitching de `route_board` (F-D5-01, `enforce_hole_clearance`
+ inserción de vía post-refill) existe precisamente para resolver esos
huérfanos que el autorouter no toca. Lo que cambia es que Freerouting ya
no se cuelga/traba indefinidamente antes de llegar a esa etapa — termina,
reporta, y le entrega el control de vuelta al pipeline de `kicad-mcp`.

**Relación con F-V3-ROUTER-TIMEOUT-HARD:** confirmado que es la misma
causa raíz de familia (motor de Freerouting 2.1.0, sin las mejoras de
estabilidad/detección de estancamiento de v2.2.0+) aplicada a una escala
y mecanismo distintos (re-ruteo incremental sobre cluster denso vs. board
grande desde cero) — la hipótesis de sesión "Ciclo C4" sobre densidad de
cobre preexistente en el corredor de búsqueda queda parcialmente
corroborada (ahí es donde Freerouting 2.1.0 se atasca), pero la causa de
fondo (versión de motor desactualizada) es la misma en ambos hallazgos.

**Severidad revisada:** igual que F-V3-ROUTER-TIMEOUT-HARD — ya no es un
callejón sin salida upstream; hay mitigación conocida (subir de versión).
El gate GUI 32d sigue sin poder correrse en ESTA sesión (requiere KiCad
abierto), pero el bloqueo de fondo (Freerouting colgándose sin dar
señales) tiene camino de resolución confirmado.

**Trigger para cerrar del todo:** correr H1/H2
(`tests/test_pcb_session32d_stitching_gui_slow.py`) reales con
`KICAD_MCP_FREEROUTING_JAR` apuntando a ≥2.2.3 (idealmente 2.4.1) y KiCad
abierto, y confirmar que `route_board` completa con `stitched_vias` conteniendo
la entrada de `MK1.3` como esperaba H1 originalmente. `F-PCBNEW-SWIG-PY314`
(abajo, bloqueante del export DSN real en esta máquina) ya está cerrado
— el gate sólo necesita ahora KiCad abierto + el jar configurado + (ver
hallazgo colateral en `F-V3-ROUTER-TIMEOUT-HARD` arriba) `KICAD_MCP_JAVA_EXE`
apuntando a un JDK ≥25, ya que el `java` del PATH de esta máquina no alcanza
para ningún jar ≥2.2.3.

**Fuente:** Ciclo C4 (hallazgo original, diagnóstico parcial),
`docs/investigacion/c4-gate-gui-32d-h1-devmic-timeout.md`; sesión 49
(causa raíz + repro standalone confirmado, sin cambios de código en el
repo — jars/DSN/SES de prueba en scratchpad, no versionados).

**Actualización sesión 50 — F-C4-01 resuelto, pero el gate GUI 32d
descubre un hallazgo P0 NUEVO y distinto: ver `F-RELOAD-STALE-POST-ROUTE`
justo abajo.** Con jar 2.4.1 + `KICAD_MCP_JAVA_EXE`, `route_board()` real
contra `anavi-dev-mic` **completó el ruteo dos veces seguidas** (317.6s y
246.0s, 19/-1 tracks — el conteo negativo de la 2ª corrida es ruido
esperable de re-rutear sobre un board que la 1ª corrida ya había dejado
parcialmente ruteado en disco, no investigado más) — el motor de
Freerouting ya no es el bloqueante. H1/H2 en sí **no pudieron ejecutarse
hasta el final** (2/2) por el hallazgo nuevo, no por F-C4-01.

### F-RELOAD-STALE-POST-ROUTE — el refill de seguridad post-route puede
fallar con `POST_ROUTE_REFILL_SKIPPED`/`KICAD_NOT_RUNNING` cuando el
ruteo tarda varios minutos — **mitigación (retry) implementada y
verificada por unit, causa raíz NO confirmada pese a investigación
extensiva (parece intermitente, no 100% reproducible)**

**Origen:** sesión 50, al fin conseguir que el gate GUI 32d (H1,
`anavi-dev-mic`) corriera con Freerouting real tras cerrar F-C4-01
(arriba). Reproducido **2 de 2 veces**, ambas contra KiCad 10.0.6 real,
PCB Editor en foco, socket IPC verificado responsivo (por una conexión
*distinta* y activa en paralelo, ver abajo) en el mismo instante del
fallo — descarta que KiCad se haya cerrado o colgado de verdad.

**Síntoma exacto:** `route_board()` corre el round-trip completo
(export DSN → Freerouting subprocess ~250-320s → import SES →
reemplazo atómico de disco, D-23.2 respetado: el .kicad_pcb en disco
queda válido). Al llegar al paso "recargar el editor vivo" (necesario
para poder refillear zonas contra el cobre nuevo, D-19.1), la llamada
`bridge.reload_board_from_disk(open_board)` (`tools/pcb.py:2588`) falla
con `ConnectionError`, mapeado por `_map_ipc_failure`
(`bridge/ipc.py:1061-1064`) a `KICAD_NOT_RUNNING`. `route_board` respeta
el contrato (D-23.2/D-32b.1): no fuerza el refill sobre un vivo
desincronizado, reporta `POST_ROUTE_REFILL_SKIPPED` con el estado
completo (`zones_refilladas=0`, `drc_err_post=18`) y un hint accionable
(`reload_board_from_disk()` + `fill_zones()` manuales). **No hay
corrupción ni violación de contrato — el fallo es honesto y
recuperable** — pero el mecanismo de refill automático, la razón de ser
de todo el pipeline post-route, no corre solo cuando más falta hace
(boards que tardan lo suficiente en rutear como para que esto dispare).

**Hipótesis de causa raíz original (REFUTADA por instrumentación
directa, misma sesión):** se sospechó que `open_board`
(`tools/pcb.py:2500`, vía `_open_board_or_none(bridge)`), capturado
**ANTES** de arrancar el subprocess externo de Freerouting, perdía la
conexión IPC subyacente por **inactividad prolongada** durante los
~250-320s sin tráfico IPC del round-trip. **Refutada con 7 repros
aislados, ninguno reprodujo el fallo:** (1) conexión idle 300s con
pings periódicos — sobrevive; (2) conexión bajo la carga REAL de
Freerouting (JVM a 123% CPU, ~190s) con pings cada 10s — sobrevive; (3)
conexión con **silencio TOTAL e ininterrumpido de 290s** (sin ningún
ping, replicando exactamente la ausencia de tráfico IPC de
`run_autoroute`) usando el MISMO handle viejo — sobrevive,
`get_board()`/`revert()` OK; (4) ídem pero con `subprocess.run(["sleep",
"290"])` real en vez de `time.sleep()` — sobrevive; (5) ídem usando la
clase `IpcBridge` real (no `kipy` crudo) — sobrevive, `reload_board_
from_disk()` con el handle viejo funciona tras el subprocess; (6) ídem
despachado dentro de `anyio.to_thread.run_sync()` (la forma exacta en
que FastMCP corre `route_board`, que es `def` sync, no `async def`) —
sobrevive; (7) `os.replace()` sobre el `.kicad_pcb` abierto (nuevo
inodo, mismo path, el mecanismo exacto de D-14.3) seguido de `revert()`
inmediato — sobrevive. **Ninguna de las variables mecánicas
identificables (inactividad, carga de CPU, spawn de subprocess, thread
del dispatch, reemplazo de inodo) rompe la conexión en aislamiento.**

**Evidencia de que el fallo real es intermitente, no determinístico:**
de 4 corridas reales de `route_board()` completas contra KiCad (misma
máquina, mismo proyecto, ~250-330s de ruteo real cada vez), **3
fallaron** con `KICAD_NOT_RUNNING` en el reload y **1 tuvo éxito a la
primera** (sin necesitar ningún retry) — la 4ª corrida, con logging de
debug temporal en `_supervise()` para capturar el traceback crudo antes
de la clasificación, simplemente no generó ninguna excepción que
capturar. Esto es inconsistente con una causa 100% mecánica y
reproducible; más compatible con una race condition rara (máquina de
2 núcleos con uso pesado de swap, ver `free -h` de esta sesión —
2.8GiB/3.8GiB de swap en uso — candidato a variable de confusión no
controlada entre corridas) que ninguno de los 7 experimentos aislados
logró disparar deliberadamente.

**Fix implementado de todos modos (commiteado en bf54747/bcc13f0/901a475,
pendiente de revisión/push humana):** aunque la causa raíz exacta no se
confirmó, el retry único con handle
fresco (`tools/pcb.py`, gateado a `exc.code is ErrorCode.KICAD_NOT_RUNNING`
+ re-verificación de `is_target_open`) es una mitigación de costo/riesgo
bajo — no reintenta la MISMA conexión (D-07.1 intacto), no relaja el
guard `reloaded is True` (D-32b.1 intacto), y en el peor caso (ambos
intentos fallan) se comporta IDÉNTICO a antes del fix. Verificado con 5
tests unit (`tests/test_pcb_session50_reload_retry_canary.py`): éxito
del reintento, agotamiento tras 2 fallos, editor cerrado/cambiado
mientras tanto, no-retry para códigos que no son `KICAD_NOT_RUNNING`.
Documentado en ADR-0012 §"Extensión F-RELOAD-STALE (sesión 50)".

**Por qué esto sigue siendo prioritario pese a ser intermitente:** el
escenario que lo dispara —Freerouting tardando varios minutos— es el
caso NORMAL para cualquier board no trivial (ver F-V3-ROUTER-TIMEOUT-HARD
arriba). Con 3/4 de fallo observado en esta sesión, la tasa real puede
ser alta; el fix mitiga sin poder garantizar cierre total mientras la
causa exacta no se identifique.

**No cerrado — no confirmado que el fix por sí solo alcance.** El
único intento real POST-fix con `route_board` completo (la corrida que
tuvo éxito) no permite distinguir si el éxito vino del reintento o de
que el primer intento ya funcionó — no hubo excepción que capturar. H1
tampoco pudo verificarse limpio esa corrida: el reload funcionó pero el
guardrail de stitching rechazó `MK1.3` por razón geométrica distinta
("cobre ajeno en la región inmediata", no "capas opuestas") — la
fixture de `/tmp` ya lleva 4 re-ruteos acumulados y la geometría cerca
de `MK1.3` derivó del escenario original que H1 espera (no-determinismo
YA documentado en el docstring del test, sesión 32d) — probar H1 limpio
requiere una copia fresca del fixture original, no reintentado en esta
sesión por costo de tiempo.

**Actualización (misma sesión, copia fresca del fixture):** repetido
con `/tmp/f-d5-01-devmic-32d-fresh` (fixture pristino, no el reruteado
4 veces) — **reload exitoso a la primera de nuevo** (`"reloaded":true`,
sin necesitar el retry). Acumulado: **2 de 5** corridas reales de
`route_board()` con éxito de reload a la primera, **3 de 5** con fallo
`KICAD_NOT_RUNNING`. Confirma el patrón intermitente, ratio
aproximadamente 40/60 con esta muestra chica — no concluyente sobre si
el fix ayuda en los casos que SÍ fallan (ninguna corrida post-fix llegó
a necesitar el retry para tener éxito; las que fallan, fallan derecho,
sin dato de si el retry las hubiera salvado).

**H1 sigue sin cerrar limpio, pero por una razón DISTINTA y ya
documentada** (no bloqueada por este hallazgo): con el fixture fresco,
Freerouting rechazó el guardrail de stitching por
`"cobre ajeno en la región inmediata"` (guardrail #5) en vez del
escenario "capas opuestas" que H1 espera — el no-determinismo de POR
DÓNDE rutea Freerouting en cada corrida, ya documentado explícitamente
en el docstring del módulo de test desde sesión 32d ("no hay garantía
de que reproduzca exactamente la topología que 32c aisló"). Esto es
esperable y no indica una regresión de este fix.

**Trigger para cerrar del todo:** seguir acumulando corridas reales
(¿cuántas de N fallan/tienen éxito con el fix puesto?) para una
muestra estadísticamente más sólida; considerar instrumentar con
logging permanente condicionado a un env var de debug (no temporal
como en esta sesión) para capturar el traceback crudo la próxima vez
que ocurra en producción sin tener que re-parchear código. H1 (el
escenario de stitching específico) necesita además una corrida donde
Freerouting reproduzca la topología "capas opuestas" — independiente de
este hallazgo.

**Fuente:** sesión 50, descubierto en vivo intentando cerrar el gate GUI
32d tras resolver F-C4-01; extendido con la investigación de causa raíz
(7 repros aislados, todos refutando la hipótesis de inactividad) y el
fix + su verificación unit. Logs/scripts de la investigación no
versionados (`/tmp/f-d5-01-devmic-32d`, `/tmp/probe_*.py`,
`/tmp/h1_debug.log`).

### F-PCBNEW-SWIG-PY314 — `pcbnew.py` (SWIG, del paquete `kicad`) rompe bajo Python 3.14 del sistema: `GetTracks()`/`GetDrawings()` fallan — ✅ CERRADO sesión 49, fix aplicado

**Origen:** hallazgo colateral durante la investigación de F-C4-01
(arriba), al intentar exportar un DSN real vía
`pcbnew.ExportSpecctraDSN` (el mismo script que usa
`bridge/autoroute.py:_EXPORT_DSN_SCRIPT`) con `/usr/bin/python3` (el
python del SISTEMA que `kicad-mcp` usa explícitamente, F5 — no es el venv
del proyecto).

**Síntoma:** `board.GetDrawings()` y `board.GetTracks()` (entre otros —
no se auditó la lista completa) fallan con
`AttributeError: 'SwigPyIterator' object has no attribute 'next'`.
`GetFootprints()` SÍ funciona (probado, 13 footprints OK). Causa exacta:
`/usr/lib/python3.14/site-packages/pcbnew.py` (generado por SWIG,
empaquetado por `kicad`, no es código de `kicad-mcp`) define su propio
`__iter__` que llama manualmente `it.next()` sobre un
`pcbnew.SwigPyIterator` — ese objeto expone `__next__` (protocolo Python
3 estándar, confirmado con `hasattr`) pero NO el alias `next` de
compatibilidad Python 2 que versiones anteriores de las bindings SWIG sí
incluían.

**Impacto en `kicad-mcp`:** `bridge/autoroute.py` usa exactamente este
patrón en `_EXPORT_DSN_SCRIPT` (`has_outline()` itera `GetDrawings()`) e
`_IMPORT_SES_SCRIPT` (`counts()` itera `GetTracks()`) — el pipeline real
de `route_board`/`fill_zones` sobre disco (paso 1 y 3 del round-trip de
autoroute, ver docstring del módulo) probablemente falla en esta máquina
tal como está, con una excepción Python cruda en el subprocess (no un
`NO_OUTLINE` limpio) — no confirmado end-to-end contra `route_board` real
en esta sesión (no había KiCad abierto), pero sí confirmado el fallo
puntual de los dos iteradores que esos scripts usan.

**Fix aplicado (sesión 49, `bridge/autoroute.py`):** monkeypatch de una
línea, guardado (sólo aplica si falta, no toca builds de `pcbnew` donde
`next` ya funciona), agregado al inicio de `_EXPORT_DSN_SCRIPT` e
`_IMPORT_SES_SCRIPT`:

```python
if not hasattr(pcbnew.SwigPyIterator, "next"):
    pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__
```

**Confirmado end-to-end contra el código real (no un script aparte):**
llamando directamente `kicad_mcp.bridge.autoroute._run_export_dsn` y
`_run_import_ses` (las funciones exactas que usa `route_board`) contra
`validation-suite/level-a/anavi-dev-mic/working/anavi-dev-mic.kicad_pcb`
— **antes** del fix ambas fallaban con `KicadMcpError(KICAD_CLI_FAILED)`
cuyo hint traía el traceback de `SwigPyIterator`; **después**, ambas
completan (`EXPORT SUCCEEDED: 2463044 bytes`,
`IMPORT SUCCEEDED: (79, 98, 6, 6)`). Confirma que esto SÍ bloqueaba
`route_board` real en esta máquina, no sólo el script standalone de la
investigación original.

**Cobertura de test (sesión 49, `tests/test_autoroute.py`):**
- `test_export_and_import_scripts_carry_the_swig_iterator_guard`
  (`unit`): el guard sigue presente como texto en ambos scripts — corre
  siempre, sin pcbnew real.
- `test_export_dsn_survives_py314_swig_iterator_bug` /
  `test_import_ses_counts_survives_py314_swig_iterator_bug`
  (`integration`, motor real): regresión directa contra
  `tests/fixtures/005_pcb_limpio`. Verificado manualmente (revirtiendo el
  fix temporalmente) que los 3 tests detectan la regresión si el guard se
  borra.

**Hallazgo colateral de esta confirmación, NO cerrado — ver entrada
nueva `F-DUPREFS-SILENT-NETLIST` más abajo:** al correr la suite
`integration` completa tras el fix, `test_pcb_session31b_duplicate_refs.py`
pasó a fallar — no por el fix en sí, sino porque destapó que su premisa
("pcbnew falla enteramente con refs duplicados") ya no es cierta en esta
versión de KiCad. Test dejado tal cual, sin tocar — es evidencia real de
un hallazgo nuevo, no una regresión de este fix.

**No investigado en esta sesión:** si el bug de `SwigPyIterator` ya
rompía antes de sesión 49 (regresión reciente del sistema, p. ej. un
`pacman -Syu` que subió Python a 3.14) o si es la primera vez que se
ejercita este código exacto en esta máquina; alcance completo (qué otras
llamadas `Get*()` de `pcbnew` en el resto del código de `kicad-mcp`
podrían compartir el mismo patrón, aunque ninguna otra fue encontrada al
grepear `import pcbnew` en `src/`).

**Fuente:** sesión 49. Fix en `src/kicad_mcp/bridge/autoroute.py`, tests
en `tests/test_autoroute.py`.

### F-DUPREFS-SILENT-NETLIST — `pcbnew.ExportSpecctraDSN` ya no falla con refs duplicados en esta versión de KiCad — **el riesgo de "pérdida silenciosa de conectividad" quedó REFUTADO (sesión 50) para el caso con net real; producción no afectada por ninguna vía**

**Origen:** hallazgo colateral al arreglar F-PCBNEW-SWIG-PY314 (arriba) y
correr la suite `integration` completa para verificar que no rompía
nada. `test_pcb_session31b_duplicate_refs.py` (sesión 31b, F-V1-02) pasó
de verde a rojo — no por el fix en sí, sino porque el fix destapó el
comportamiento real de `pcbnew.ExportSpecctraDSN` por primera vez en
esta máquina (antes, cualquier llamada a `_run_export_dsn` crasheaba por
`SwigPyIterator` sin importar los refs duplicados — el test "pasaba" por
el motivo equivocado, mismo patrón de falso verde que `_copper_on_layer`
en sesión 43).

**Lo que documentan `ADR-0013` y el comentario de
`tools/pcb.py:_find_duplicate_refs`** (textual): *"pcbnew no puede
exportar el DSN... `pcbnew.ExportSpecctraDSN` falla enteramente si dos o
más footprints comparten reference designator, sin importar su
posición (confirmado en sesión 31... `ok=False,size=0` →
`ok=True,size=2.4MB`)"*.

**Lo que pasa en esta máquina (KiCad 10.0.6), verificado llamando
`_run_export_dsn` directo contra `tests/fixtures/006_pcb_refs_duplicados/
dup_refs.kicad_pcb` (2 footprints con ref literal `REF**` compartida,
más `R1`/`R2` únicos):** la exportación **NO falla** — `ok=True`, DSN de
2474 bytes (chico pero bien formado, no un `size=0` truncado a medias).
`pcbnew` **renombra solo** el segundo duplicado a `REF**_1` en el bloque
`(placement...)`. Pero la sección `(network (net NET1 (pins ...)))` del
DSN sólo lista los pines de `R1`/`R2` — **los pines de `REF**`/`REF**_1`
quedan completamente ausentes del netlist**, sin ningún error ni warning
en el DSN ni en el `returncode`. Si Freerouting corriera sobre este DSN,
esos 2 componentes simplemente no tendrían ninguna conexión que rutear
— indistinguible de "no tiene nets", no de "el exportador los perdió".

**Por qué esto NO es un riesgo de producción hoy:** `route_board`
(`tools/pcb.py:2531`, precheck `DUPLICATE_REFS`) usa
`_find_duplicate_refs(pre_footprints)`, que lee refs del snapshot IPC en
vivo — **no depende de `ExportSpecctraDSN` en absoluto**. El precheck
sigue bloqueando este escenario ANTES de llegar al subprocess de export,
exactamente igual que antes de este hallazgo. Verificado leyendo el
código, no sólo asumido.

**Por qué se pensó que importaba igual (sesión 49, REFUTADO parcialmente
en sesión 50):** (1) la justificación documentada en `ADR-0013` y en el
propio código ya no describe la realidad de esta versión de KiCad —
sigue siendo cierto, el ADR sigue desactualizado en ese punto puntual;
(2) se temió que el modo de falla real, si el precheck alguna vez se
bypasea, fuera **peor** que lo que el ADR asume: pérdida silenciosa de
conectividad. **Esto último es lo que sesión 50 investigó a fondo y
refutó** — ver abajo.

**Investigación de sesión 50 — 3 experimentos controlados contra una
copia de `tests/fixtures/006_pcb_refs_duplicados/dup_refs.kicad_pcb`
(scripts en `/tmp/f-duprefs-investigation/`, no versionados; el
regresivo permanente sí quedó versionado, ver "Estado del test"
abajo):**

1. **Refs duplicados CON conectividad real (el escenario que de verdad
   importaría en producción):** el fixture 006 commiteado tiene los 2
   `REF**` **sin net asignado por diseño** (heredados de 005 como
   filler, ver su propio `SOURCE.md`) — la evidencia original de sesión
   49 ("los pines de REF**/REF**_1 ausentes del netlist") es exactamente
   la ausencia esperable de CUALQUIER pad sin net, duplicado o no, no
   evidencia de pérdida causada por el renombrado. Asignando `NET1` (el
   net real que ya conecta `R1`/`R2`) a los 4 pads de los 2 `REF**` y
   re-exportando: **los 8 pines aparecen correctamente en
   `(net NET1 (pins ...))`**, repartidos entre `REF**-N` y `REF**_1-N` —
   **sin pérdida**. El riesgo (2) de arriba NO se materializa en este
   escenario.
2. **Ref vacía (`""`)**: KiCad la trata como si fuera literalmente
   `"REF**"` — un footprint con ref vacía colisiona con la MISMA bolsa
   de duplicados que `"REF**"` y termina renombrado a `REF**_N` en el
   DSN (sorprendente para inspección humana del placement, pero sin
   pérdida de conectividad: sus pines siguen apareciendo correctamente
   bajo su net real).
3. **Footprint sin pads**: exporta sin error, sin crash; el footprint
   simplemente no aporta pines a ningún net (nada que perder, ya que no
   tenía pines).

**Conclusión revisada:** el riesgo de "pérdida silenciosa de
conectividad" que motivaba tratar esto como hallazgo activo no se
materializa en ninguno de los 3 escenarios probados. Sigue habiendo
valor real en el precheck `DUPLICATE_REFS` (independiente de este
hallazgo): un DSN con refs `REF**`/`REF**_1` autogenerados es menos
legible para debugging, y `set_footprint_ref` sigue siendo la vía
correcta de resolución (ADR-0013) — pero no por pérdida de datos
demostrada. El ADR-0013 y el comentario de
`tools/pcb.py:_find_duplicate_refs` siguen desactualizados en describir
un crash limpio (`ok=False,size=0`) que ya no ocurre en esta versión de
KiCad — corrección de esos textos queda como higiene menor, no P0/P1.

**Estado del test:** el xfail original (`test_export_dsn_fails_with_
duplicate_refs_and_succeeds_after_rename`, sesión 49) se mantiene —
su premisa de sesión 31b (que la exportación falla enteramente) sigue
sin cumplirse en KiCad 10.0.6, motivo no investigado (¿cambio de
versión? sigue abierto). **Test permanente nuevo** (sesión 50,
`test_export_dsn_preserves_connectivity_of_duplicate_refs_with_real_net`,
mismo archivo): fija como regresión que refs duplicados CON conectividad
real exportan sus 8 pines sin pérdida — la evidencia positiva que
refuta el riesgo (2).

**Fuente:** sesión 49 (hallazgo original, sin investigación dedicada);
sesión 50 (3 experimentos controlados + test de regresión permanente).

### F-V2-REFILL-SILENCIOSO — `route_board(refill=true)` puede no persistir el refill sin ningún error visible — ✅ CERRADO sesión 32b

**Origen:** sesión 32, segunda Validation Suite (Nivel B, ANAVI Macro Pad 12).

**Mecanismo confirmado** (`src/kicad_mcp/tools/pcb.py`): el bloque
post-ruteo de refill+`enforce_hole_clearance`+`save_board`
(`pcb.py:2728-2733`, activado por `refill=true`) sólo se ejecuta si
`reloaded is True`. `reloaded` depende de que
`bridge.reload_board_from_disk(open_board)` no lance `KicadMcpError`
(`pcb.py:2701-2710`) — una operación de **mutación**, deliberadamente
**sin reintento** ante `AS_BUSY` transitorio (D-07.1). Si falla una sola
vez, la excepción se descarta en silencio
(`except KicadMcpError: reloaded = False`) y **todo** el paso de
seguridad que corrige que "Freerouting NO respeta el plano GND como
zona de exclusión" (D-19.1) se salta — sin `POST_ROUTE_PERSIST_FAILED`,
sin ningún error, `route_board` devuelve un payload de éxito normal con
`refill: true` solicitado pero silenciosamente no honrado.

**Reproducible en 2 sesiones independientes, no un fluke:** el audit log
de `/tmp/gui-test-project` conserva la llamada `route_board` original de
**sesión 31c** (`2026-07-29T11:13:58`) mostrando el mismo patrón exacto:
`"reloaded": false, "zones_refilladas": 0`. Sesión 31c ejecutó su propio
"Refill final" explícito pocos minutos después sin cruzar estos campos
contra la promesa de `refill=true` — el hallazgo nunca se documentó
porque el paso ya prescripto en el flujo canónico (D-23.2) lo
enmascaraba. En sesión 32, esto dejó 259 violaciones DRC reales (236
`clearance` + 23 `hole_clearance`, 100% contra la zona GND) sin resolver
hasta recuperación manual (`reload_board_from_disk()` + `fill_zones()`
explícitos).

**Por qué es P0 y no sólo P2:** rompe la garantía D-23.2/ADR-0012
("disco == memoria == err_post reportado") — el caso exacto que ese
contrato existe para prevenir — sin ninguna señal de error. Cualquier
uso de `route_board(refill=true)` que confíe en esa promesa sin un paso
de refill explícito adicional recibiría un board con clearance real
contra el plano GND sin saberlo.

**Recomendación de fix original** (sesión intermedia, patrón 31b, antes de
sesión 33): (a) desacoplar el refill+persistencia en disco de
`reload_board_from_disk` — son operaciones lógicamente independientes
(una sincroniza el editor vivo, la otra corrige y persiste el archivo);
(b) si se mantiene la dependencia, surfacear un código de error
explícito (ej. `POST_ROUTE_REFILL_SKIPPED`) en vez de éxito silencioso;
(c) evaluar si esta mutación en particular (re-sincronizar estado, no
aplicar un cambio de diseño) amerita excepción documentada al criterio
general de D-07.1 de no reintentar mutaciones.

**Cierre (sesión 32b):** la opción (a) resultó ser PELIGROSA, no sólo
descartable por preferencia — investigación previa al fix (Bloque 0)
encontró que si la recarga falló, el board vivo todavía refleja el
estado **pre-ruteo** (el `save_board` implícito bajó live→disco antes de
que Freerouting escribiera); refillear y guardar ese vivo desactualizado
pisaría el ruteo recién persistido en disco. Se aplicó la opción (b): la
excepción de `reload_board_from_disk` ya no se descarta
(`src/kicad_mcp/tools/pcb.py`, bloque de recarga automática post-route),
y cuando el refill prometido (`refill=true`, `zones_existentes > 0`) no
corre por esa razón concreta, `route_board` levanta
`POST_ROUTE_REFILL_SKIPPED` (adición pura al `StrEnum`, F1/F3 intacta) en
vez de completar en silencio. El raise se pospone hasta después del DRC
post-route + snapshot + `store.mark_live_stale` (no en el guard), para no
abrir una ventana donde un `fill_zones()` posterior pisara el ruteo. La
opción (c) NO se tomó — D-07.1 (mutación sin reintento) queda intacta,
`reload_board_from_disk` se sigue llamando una sola vez.

**H2 refutada (alcance del fix):** el prompt de sesión 32b hipotetizaba
que `fill_zones()`/`add_zone(fill=true)` podían compartir el mismo bug
(cobertura simétrica D2). Inspección del código lo refutó: ninguna de las
dos llama `reload_board_from_disk` — no tienen este camino silencioso, su
único modo de falla (`save_board()`) ya levanta `POST_ZONE_PERSIST_FAILED`
desde sesión 27. El fix quedó acotado a `route_board`.

**Ver:** `docs/adr/0012-route-board-persist-contract.md`
§"Extensión F-V2 (sesión 32b)", `docs/DECISIONES.md` D-32b.1/D-32b.2,
`docs/historico/sesiones/32b-reporte.md`,
`tests/test_pcb_session32b_refill_silencioso_canary.py` (canario
permanente), y `validation-suite/level-b/anavi-macro-pad-12/validation-report.md`
§Fricciones para el hallazgo original.

### F-V1-02 — `route_board` falla enteramente con refs de footprint duplicados/sin anotar — ✅ CERRADO sesión 31b

**Origen:** sesión 31, primera Validation Suite (Nivel A, ANAVI Dev Mic).
El diseño del autor trae 4 mounting holes con el reference designator
literal `REF**` compartido (footprints sólo-mecánicos, sin símbolo de
esquemático — nunca fueron anotados; patrón real y no infrecuente en
proyectos KiCad externos).

- **Síntoma 1 (ya conocido, P2 histórico — ver abajo, ahora resuelto):**
  `move_footprint(ref="REF**", ...)` resolvía por `fp.ref == ref` (primer
  match) — sólo podía mover UNA de las 4 instancias.
- **Síntoma 2 (root cause aislado con experimento controlado en sesión
  31):** `pcbnew.ExportSpecctraDSN()` — invocada por `_run_export_dsn`,
  paso 1 de `route_board` — **devuelve `ok=False, size=0` cuando el
  board tiene refs de footprint duplicados**, sin importar la posición
  de esos footprints. Confirmado quitando 3 de las 4 instancias `REF**`
  en una copia de prueba: la exportación pasó de fallar a `ok=True,
  size=2.4MB`. Bloqueaba `route_board` **por completo**.
- **Decisión de diseño (sesión 31b, investigación previa al fix):** el
  fix obvio (`delete_footprint(ref, kiid)` general) se descartó — ADR-0010
  dice explícitamente que borrar footprints sigue detrás de Gate G2 (que
  no existe en código), y esa asimetría con `delete_track`/`delete_via`
  es **deliberada**, no un vacío. Acotar el trigger a "ref duplicado" NO
  cambia el argumento de ADR-0010: un footprint con ref duplicado es
  igual de caro de reinstanciar que uno con ref único. Además, en el
  caso real de ANAVI Dev Mic, las 4 `REF**` son mounting holes
  **legítimas**, no basura — borrar 3 habría destruido el ground truth
  de 13 footprints que sesión 31 ya midió.
- **Fix real: anotar, no borrar.** Verificado con un spike GUI contra
  KiCad 10.0.4 real (sesión 31b, Paso 0) que `fp.reference_field.text.value`
  usa semántica de escritura en vivo en kipy (`proto_ref=`, sin
  `CopyFrom` — a diferencia de `fp.position`, la trampa de ADR-0008).
  Tool nueva: `set_footprint_ref(ref, new_ref, kiid=None)` — sólo opera
  sobre refs YA duplicados (no puede usarse como delete_footprint
  disfrazado), lista candidatos con `data.candidates` si `kiid` no se
  especifica (nunca resuelve a ciegas, mismo espíritu que la ambigüedad
  de `_delete_copper`). Complementado con un pre-check `DUPLICATE_REFS`
  en `route_board` (falla ANTES del subprocess de exportación DSN, con
  mensaje legible en vez del `KICAD_CLI_FAILED` opaco anterior).
- **Ver ADR-0013** para el contrato completo (incluye el hallazgo
  arquitectónico de la semántica `proto_ref=` de `reference_field`,
  contraparte de ADR-0008).
- **Verificación:** 12 tests unit (`_find_duplicate_refs`, pre-check de
  `route_board`, tool `set_footprint_ref` — ambigüedad, kiid stale, ref
  único rechazado, happy path) + 1 test `integration` contra pcbnew real
  (`tests/fixtures/006_pcb_refs_duplicados/`) que congela el experimento
  controlado de sesión 31 como regresión permanente.
- **Impacto en sesión 31:** H1a (estabilidad del flujo canónico) fue
  refutada honestamente en su momento — la validación Nivel A (ANAVI Dev
  Mic) cerró SIN completar el ruteo. Con este fix, el reintento de
  sesión 31 queda desbloqueado sobre el mismo `working/` ya preparado.
  Ver `validation-suite/level-a/anavi-dev-mic/validation-report.md` y
  `docs/historico/sesiones/31-reporte.md`.

Ningún P0 abierto hoy (F-V1-02 arriba cerrado en sesión 31b). **F-D4-02
cerrado y ratificado con evidencia 5/5**
(2/2 test de regresión sesión 24 + 3/3 corridas de D5, sesión 25 —
`err_post` coincidió exacto con `run_drc()` independiente, mtime cambió
post-save, cero `EXTERNAL_EDIT_DETECTED` espurio, sin ninguna excepción en
las 5 corridas). El cierre generaliza al board vivo en producción real, no
solo al contrato JSON del test controlado — ver
`docs/historico/sesiones/25-reporte.md`. **Alcance de la ratificación
ampliado en sesión 27**: el contrato D-23.2 ya cubre las tres tools
(`route_board`, `fill_zones`, `add_zone(fill=True)`) — ver P2 cerrado
abajo. **Ratificado 25/25 en producción real hasta cierre D7 (sesión 29),
sin divergencias.** Reabrir como P0 solo si una sesión futura lo ratifica
como regresión.

## P1 — `delete_tracks_bulk` no respeta D-23.2/ADR-0012 sobre zonas tocadas — ✅ CERRADO sesión 34a-fix-1

**Origen:** observado en sesión 32b (`docs/BACKLOG.md` §Higiene menor,
histórico), no accionado por estar fuera del alcance quirúrgico de esa
sesión. **Confirmado con severidad P1** (no P3/higiene) en la auditoría
sistemática de contratos de escritura de sesión 34a.

`delete_tracks_bulk` (`src/kicad_mcp/tools/pcb.py:2039`) llamaba
`bridge.refill_zones(board)` cuando el borrado tocaba tracks de una zona
de cobre, pero **sin** `enforce_hole_clearance()` ni `save_board()`
posteriores — a diferencia de `route_board`, `fill_zones` y
`add_zone(fill=True)`, que corren las tres juntas (contrato D-23.2/
ADR-0012). Dos consecuencias concretas: (1) el clearance contra holes
podía quedar roto (mismo bug conceptual que F-D3-01, sin su workaround
acá); (2) el refill vivía sólo en memoria — el payload reportaba
`zones_refilled: 1` pero el disco nunca se actualizaba, así que un
`run_drc()` inmediato medía el estado viejo. El propio docstring de
`enforce_hole_clearance` (`ipc.py:2016`) exige llamarlo **siempre**
inmediatamente después de `refill_zones()` — esta tool violaba esa
invariante directamente.

**No fixeado en sesión 34a** (fuera de alcance: la sesión es auditoría
pura, fixes triviales <20 líneas únicamente). Fix agendado como
`34a-fix-1` y cerrado en esa sesión.

**Fix (sesión 34a-fix-1, rama R-A):** cuando el borrado toca ≥1 zona de
cobre, `delete_tracks_bulk` corre `refill_zones` → `enforce_hole_clearance`
→ `save_board`, con fallo de persistencia visible
(`POST_ZONE_PERSIST_FAILED` reusado tal cual de sesión 27, sin código
nuevo) y mtimes registrados post-save (patrón `add_zone`, hallazgo #31
sesión 24). La hipótesis original del BACKLOG (reusar
`_refill_enforce_and_save`, el helper de `route_board`) se descartó por
inspección: el helper está acoplado a `route_board` en su mensaje de
error y en `POST_ROUTE_PERSIST_FAILED`; se implementó inline, paralelo a
`add_zone`/`fill_zones` (sus hermanos semánticos, también inline).

**Evidencia:** 2 tests unit nuevos (orden estricto `refill → enforce →
save`; fallo de `save_board()` visible y auditado) en
`tests/test_pcb_delete_bulk.py`, sin editar los 8 preexistentes; 1 test
GUI nuevo (`tests/test_pcb_session34afix1_delete_bulk_persist_gui.py`,
`integration_gui_slow`, gate del merge), 1/1 verde contra KiCad 10.0.4
real: `zones_refilled == 1`, `run_drc()` independiente sin
`hole_clearance` ni `clearance` contra Zone GND, sin
`EXTERNAL_EDIT_DETECTED` espurio post-save, keepouts en rango esperado.
Suite offline 408 passed, `ruff`/`mypy` limpios. Revisión independiente de
Codex: **APROBAR, 0 hallazgos**. Detalle completo:
`docs/historico/sesiones/34a-fix-1-reporte.md`,
`docs/analisis/auditoria-contratos-bridge.md` §3 (ficha
`delete_tracks_bulk`) y §5.3.

## P1 — Solder mask bridge en ANT1 — ✅ CERRADO sesión 30 (mecanismo aislado + fix), pendiente gate GUI

El pad de ANT1 hacía bridge con la zona GND. El fix de sesión 21 (F-D3-01)
protegía el *hole*, no el *pad*. Sesión 26 confirmó el bug como real y
alcanzable pero no logró aislar el mecanismo ni hacer efectivo un fix.
**Sesión 30 aisló el mecanismo con precisión sub-milimétrica y aterrizó el
fix.** Ver `docs/investigacion/30-solder-mask-ant1.md` (reporte completo,
continuación de `docs/investigacion/26-solder-mask-ant1.md`).

- **Origen:** fricción de D4 (sesión 22). Investigación parcial sesión 26,
  cerrada sesión 30.
- **Mecanismo:** el fill de KiCad respeta el **apotema** del keepout de
  N vértices (`r·cos(π/N)`), no un círculo ideal al radio pedido. Con
  N=16 (sesión 21-29), el déficit de apotema a los radios típicos de esta
  investigación (~1.8mm) es mayor que el margen de seguridad de 0.02mm —
  por eso el fix de sesión 26 no tuvo efecto. Sesión 26 además asumió un
  número incorrecto para la clearance natural del pad (2.00mm en vez de
  1.70mm, confundiendo `min_copper_edge_clearance` con la clearance de
  netclass), lo que hizo parecer irreconciliables sus dos experimentos.
- **Fix:** `src/kicad_mcp/bridge/ipc.py` — (1) `_circle_vertices_mm` N=16→64
  (compensa el déficit de apotema); (2) `enforce_hole_clearance` recalcula
  el radio de keepout de un pad como
  `max(hole_term, r_cobre_pad + max(pad_to_mask_clearance, solder_mask_to_copper_clearance) + margen)`
  — re-aterriza el término de máscara que sesión 26 había revertido (los
  clearances ya se leían en `rules_reader.py` desde sesión 26, sin
  consumidor hasta ahora).
- **Verificación:** unit test de la fórmula (`tests/test_pcb_hole_clearance.py`)
  + barrido `pad_to_mask_clearance` ∈ {0.0, 0.20, 0.22, 0.25, 0.30} contra
  el motor real de KiCad (`tests/test_pcb_session30_solder_mask.py`, marca
  `integration`, gate del merge) — 0 violaciones en los 5 casos, más
  control del flujo canónico sin cambio de comportamiento.
- **Gate GUI del DoD (pipeline de zonas/keepouts):** corrido contra copia
  fresca (no `/tmp/gui-test-project`, fuera de alcance de sesión 30) —
  `test_pcb_session21_hole_clearance_gui.py` 2/2 y
  `test_pcb_session27_zone_persist_gui.py` 2/2, ambos verdes. Confirma que
  el bump N=16→64 no regresiona ningún keepout auto-generado ya validado
  en D3-D7.
- **Kept de sesión 26, ahora con consumidor:** `rules_reader.py`
  (`pad_to_mask_clearance_mm`, `solder_mask_to_copper_clearance_mm`).

### P2 — Generalización D-23.2 a fill_zones y add_zone(fill=True) [CERRADO sesión 27]

- **Estado:** cerrado 2026-07-24, mergeado a master.
- **Evidencia:** test de regresión GUI 2/2 verde contra KiCad 10.0.4
  real (`tests/test_pcb_session27_zone_persist_gui.py`, 69s por
  corrida). ADR-0012 extendido con sección "Extensión de alcance
  (sesión 27)".
- **Cambio:** `POST_ZONE_PERSIST_FAILED` compartido para las dos tools.
  Contrato D-23.2 ahora aplica a tres tools (`route_board`,
  `fill_zones`, `add_zone(fill=True)`).
- **Ratificado en Fase 3** con 3 dogfoodings verdes consecutivos (D5, D6,
  D7); Fase 3 cerrada 2026-07-25.
- **Reporte:** `docs/historico/sesiones/27-reporte.md`.

## P1 — bbox de validación no leía Edge.Cuts — ✅ CERRADO sesión 31b

**Origen:** sesión 31, Bloque 2 (colocación sobre ANAVI Dev Mic).
`board_bbox_mm` (`src/kicad_mcp/bridge/ipc.py`) tenía un docstring que
decía *"Preferencia: usar la superficie declarada del board (Edge.Cuts).
Fallback: unión de bounding boxes de todos los footprints"* — pero el
código **nunca leía Edge.Cuts**, iba directo al fallback (margen de
±100mm alrededor del enjambre de posiciones de footprints).

- **Corrección de sesión 31b (investigación previa al fix):**
  `board_bbox_mm` **no tiene ningún consumidor en `src/`** — el bug real
  que sesión 31 pisó vivía en una copia inline **independiente** del
  mismo cálculo dentro de `read_board_context` (el método que
  `move_footprint`/`add_track`/`add_via` realmente usan vía
  `ctx.bbox`). La entrada original de este ítem nombraba la función
  equivocada por la misma razón estructural que causó el bug: dos
  copias divergentes de la misma lógica.
- **Cuándo importaba:** si todos los footprints están agrupados lejos
  del contorno real (ej. todos en `(0,0)`, la convención de estado
  inicial de `working/` en la Validation Suite —
  `validation-suite/tools/prepare_working.py`), el bbox calculado
  (`swarm ± 100mm`) podía no cubrir el contorno Edge.Cuts real, y
  `move_footprint`/`add_track` rechazaban con `INVALID_PARAMS` cualquier
  coordenada dentro del board real. Sesión 31 lo confirmó con ANAVI Dev
  Mic: contorno en x∈[109,144], bbox aceptado x∈[-100,100] — sin
  intersección.
- **Fix (sesión 31b):** helper lock-free `_edge_cuts_bbox_nm` extraído
  de `board_outline` (evita re-adquirir `self._lock`, no reentrante —
  `ipc.py:999-1003`), consumido por `board_outline`, `board_bbox_mm` Y
  `read_board_context` vía el helper puro `_bbox_with_margin`. Semántica
  final: **unión** de Edge.Cuts (±10mm) y enjambre de footprints
  (±100mm), no "preferir uno u otro" — estrictamente no regresivo, nunca
  devuelve un rango más chico que el código anterior.
- **Verificación:** 12 tests unit nuevos en `tests/test_ipc.py`
  (incluye un canario de deadlock que reemplaza `self._lock` por un
  wrapper que lanza en re-entrada) + suite offline completa sin
  regresiones.
- **Sin ADR** — implementa comportamiento ya documentado, sin cambiar
  contrato externo (DoD #4, "aclaración de comportamiento").

## P1-1 — Sanitización de los tres encoders ad hoc — ✅ CERRADO sesión 37, gaps derivados cerrados/delegados sesión 38

**Origen:** R2 de `docs/analisis/auditoria-tecnica-integral-2026-08.md:367`
(plan de acción C2 en `:429`, deuda técnica DT4 en `:385`). `_encode_tracks`,
`_encode_zones` y `_encode_component_detail` (hoy en
`tools/pcb_encoders.py`, con re-exports desde `tools/pcb.py`) interpolan
`net_name`/`ref`/`pad.number` de KiCad — entrada no confiable por CLAUDE.md
regla 6 — en formatos delimitados por espacios/`|` propios (NO TOON, F1
intacto por diseño).

- **Sesión 36 (parcial):** aplicó `toon.encoder._sanitize` en los tres
  puntos de interpolación (cierra caracteres estructurales `\n`/`|`/`:`/`>`
  y control-chars) + 3 goldens byte-exactos nuevos
  (`tests/golden/004_pcb_tracks_canarios/`, `005_pcb_zones_canarios/`,
  `006_pcb_component_detail_canarios/`, `tests/test_pcb_encoders_golden.py`).
  Evaluando H36.1 activamente (no asumida), descubrió que `_sanitize` **no**
  neutraliza el espacio — el delimitador posicional real de las tres
  gramáticas ad-hoc (a diferencia de TOON, `|`-delimited). Documentado como
  golden de caracterización (líneas `T4`/`Z4`/pads 4-5) y escalado a sesión
  37 en vez de fixearlo apurado.
- **Sesión 37 (cierre):** mini-sanitizador local `_sanitize_space_delimited`
  (hoy en `tools/pcb_encoders.py`, junto al import de `_sanitize`) — compone `_sanitize` +
  `re.sub(r"\s", "_", ...)` (D37.1: whitespace unicode completo, no sólo
  `U+0020`, alcanzable vía netlists importadas; `_CONTROL_RE` de TOON ya
  cubre `\t\n\r\v\f` pero no el espacio). Aplicado en los 5 sitios
  space-delimited: `net_name` en `_encode_tracks` (segmentos y vías) y
  `_encode_zones`, `number`/`net_name` de pad en `_encode_component_detail`.
  El header `DETAIL|<ref>|pcb|...` de `_encode_component_detail` (`|`-delimitado)
  **no** se toca — H2 confirmada, un espacio ahí es inocuo.
  `toon/` no se tocó (ruta (a) del ADR propuesto en 36; la ruta (b), extender
  `_sanitize`, fue descartada explícitamente por el arquitecto para no
  invertir la dependencia núcleo↔deuda ad-hoc).
- **Goldens actualizados exactamente en las 4 líneas anticipadas** (`T4` en
  004, `Z4` en 005, pads 4-5 en 006) — H3 confirmada, regenerar con el código
  nuevo y diffear contra el golden previo no tocó ninguna otra línea.
- **Riesgo real, no sólo teórico:** hay consumidores posicionales activos que
  `.split(" ")`/`.split()` estas líneas — `tests/test_pcb_session16_gui.py:126`,
  `tests/test_pcb_session19d_gui.py:142`,
  `tests/test_pcb_session21_hole_clearance_gui.py:115`,
  `tests/test_reload_e2e_gui.py:122`. Un `net_name="GND EN"` sin el fix
  leería `net="GND"`, `layer="EN"` — corrupción silenciosa.
- **Campos fuera de alcance, quedan como candidatos futuros** (ya listados
  en la decisión #4 de sesión 36, sin sesión asignada): `filter_desc`
  (headers de `_encode_tracks`/`_encode_zones`), `it.kiid`/`z.kiid`,
  `it.layer`/`z.layer`/`p.layer` (`CopperItem.layer: str | None` renderiza
  el literal `None` cuando falta), `z.kind`, `it.via_layers`,
  `detail.bbox_source`, y `CopperItem.net_name` vacío sin fallback `or "-"`
  (a diferencia de `ZoneItem.net_name`/`PadDetail.number`/`net_name`, que sí
  lo tienen). Ver `docs/historico/sesiones/37-reporte.md`.
- **Verificación:** `pytest tests/test_pcb_encoders_golden.py` → 3 passed;
  suite offline completa → 388 passed (mismo baseline que sesión 36); `ruff
  check`/`ruff format --check`/`mypy src/` limpios.
- **Sesión 38 — cierre de 4 de los 7 campos listados arriba, veredicto
  explícito en los 7:**
  - `CopperItem.net_name` vacío → fallback `"-"` (`_encode_tracks`), ya
    consistente con `ZoneItem`/`PadDetail`. **Cerrado.**
  - `CopperItem.layer` (`str | None` renderizando `None`) → fallback `"-"`.
    Defensivo, no correctivo: hoy sólo las vías traen `layer=None` y esa
    rama no emite `layer` — inalcanzable en producción, pero el tipo lo
    permite y el fix cierra el flanco a costo cero. **Cerrado.**
  - `z.layer` (no estaba en los 4 candidatos originales del prompt de la
    sesión, pero sí en el desglose `it.layer`/`z.layer`/`p.layer` de esta
    misma entrada) → puede ser `""` (`bridge/ipc.py`, `layers[0] if layers
    else ""`), mismo colapso de columna que tenía `CopperItem.net_name`.
    Fallback `"-"`. **Cerrado** (correctivo, caso alcanzable).
  - `filter_desc` → sanitiza cada componente (`net`/`layer`/`kind`) antes de
    ensamblar, en `_tracks_filter_desc`/`_zones_filter_desc`. **Correctivo,
    no defensivo:** `layer` de `get_tracks`/`get_zones` no se valida en
    ningún punto (a diferencia de `net`/`kind`/`bbox`) y llegaba crudo al
    header — un `layer` con `\n` forjaba líneas dentro del bloque
    `TRACKS|v1|...`/`ZONES|v1|...`. **Cerrado.**
  - `kiid` → **NO cerrado, abre `P1-2`** (ver abajo): es identificador de
    round-trip (`delete_track(id=...)`, `get_copper_by_kiid`), sanitizarlo
    rompe la resolución del id — requiere discusión de diseño, no es un fix
    mecánico.
  - `bbox_source`, `kind`, `p.layer` → **refutados**, no son gaps reales:
    conjuntos cerrados de literales hard-codeados internos
    (`{"courtyard","pads"}` para `bbox_source`; `"via"/"arc"/"track"`/bool
    `is_keepout` para `kind`) o siempre no-vacíos (`_pad_layer_str` —
    `"*.Cu"` o nombre de enum en toda rama), nunca texto de archivo KiCad.
  - Canarios nuevos: `T5` en `004_pcb_tracks_canarios` (`net_name=""` +
    `layer=null`), `Z6` en `005_pcb_zones_canarios` (`layer=""`). `006` sin
    cambios (los dos candidatos que la tocaban quedaron refutados).
    `filter_desc` sin cobertura golden posible (el arnés recibe el string ya
    ensamblado) — cubierto en `tests/test_pcb_session38_filter_desc.py`.
  - Ver `docs/historico/sesiones/38-reporte.md` para el detalle con traza al
    código de cada veredicto.

## P1-2 — `kiid` sin sanitizar en los encoders ad hoc — ✅ CERRADO sesión 44, REFUTADO CON EVIDENCIA

**Origen:** decisión #4 de sesión 36, verificado y promovido a entrada propia
en sesión 38 (el resto de esa decisión se cerró en la misma sesión, ver
`P1-1` arriba).

**Ubicación auditada:** `it.kiid` en `_encode_tracks` y `z.kiid` en
`_encode_zones`, ambos en `tools/pcb_encoders.py` y re-exportados desde
`tools/pcb.py`. Ambos vienen de
`str(it.id.value)`/`str(z.id.value)` (`bridge/ipc.py`) — el KIID nativo de
KiCad, no texto arbitrario de archivo.

**Veredicto: refutado, no requiere sanitización.** Dos piezas de evidencia
independientes, la segunda ejecutada porque una garantía documental sola no
alcanza cuando el origen es un archivo editable a mano:

1. **Contrato de kipy (upstream, no de este repo):** `base_types_pb2.pyi`
   (`kipy/proto/common/types/base_types_pb2.pyi:276-290`) declara el tipo
   `KIID` — usado uniformemente para tracks, vías, zonas, footprints y pads,
   no sólo para las dos superficies auditadas — con el comentario textual
   *"The KIID's value in standard UUID format, stored as a string for easy
   portability"*. Un UUID estándar sólo usa `[0-9a-fA-F-]`: nunca un espacio
   ni `|`, los dos delimitadores de las tres gramáticas ad hoc.
2. **Verificación empírica propia (offline, vía `pcbnew`, mismo motor de
   carga que usa el IPC):** se tomó `tests/fixtures/007_pcb_multicapa` en
   `/tmp` (nunca se tocó el fixture commiteado) y se reemplazó el `(uuid
   ...)` de la vía por una cadena maliciosa con espacio, `|` y tab. Al
   cargar con `pcbnew.LoadBoard()`, el uuid inyectado **no sobrevive**: KiCad
   lo descarta al parsear y genera uno nuevo, válido, al azar
   (`cc200f04-593b-4f1c-a25e-c62b244a64f8`). Control: el mismo experimento
   con un uuid bien formado (el original del fixture,
   `5e4b1000-0000-4000-8000-000000000004`) sí se preserva exacto — confirma
   que el comportamiento es rechazo de formato inválido, no reemplazo
   incondicional. Conclusión: ni siquiera un `.kicad_pcb` editado a mano de
   forma adversarial puede lograr que un `kiid` con caracteres estructurales
   llegue al object model en memoria que expone el IPC — el string
   malicioso muere en el parser de KiCad, antes de que `kicad-mcp` lo vea.

Para un ítem creado por `kicad-mcp` (`add_via`, `add_track`, `add_zone`) el
argumento es aún más directo: el KIID lo genera KiCad internamente
(`KIID()` por defecto), nunca se deriva de texto de archivo.

**Por qué no aplicaba un fix mecánico (razonamiento original, preservado):**
`kiid` es un identificador de round-trip — el agente lo recibe de
`get_tracks`/`get_zones` y lo devuelve tal cual a `delete_track(id=...)`,
`get_copper_by_kiid`, etc. `_sanitize`/`_sanitize_space_delimited` (truncan a
40 chars, reemplazan caracteres) lo habrían mutilado, rompiendo esa
resolución sin necesidad — la evidencia de arriba confirma que nunca hacía
falta.

**Sin cambio de código.** DT1 Slice 1 (sesión 41) trasladó `kiid` mecánicamente
sin sanitizarlo; esta sesión confirma que esa decisión era correcta y cierra
el candidato. Detalle completo del experimento en
`docs/historico/sesiones/44-reporte.md`.

## DT1 — Partición de `tools/pcb.py` — ✅ CERRADA sesión 48 (estado actual), reapertura condicional

La caracterización de sesión 40 (`docs/analisis/40-dt1-caracterizacion.md`)
autorizó un primer slice mecánico y reversible. **DT1 Slice 1 — encoders ad
hoc: CERRADA en sesión 41**, mediante PR #13 y merge
`8d3696b890b4719ef19a96db26735b25da0214b5`. El cluster vive en el nuevo
módulo `src/kicad_mcp/tools/pcb_encoders.py`; `tools/pcb.py` conserva siete
re-exports explícitos. Ver `docs/historico/sesiones/41-reporte.md`.

**Siguiente paso:** recaracterizar `tools/pcb.py` después del Slice 1 y
seleccionar el segundo cluster mediante cohesión, dependencias, consumidores,
monkeypatches, ciclos, re-exports, cobertura y reversibilidad. No seleccionar
únicamente por LOC. La sesión concreta requiere decisión humana.

**Caracterización DT1 Slice 2 (S47 v6 + extensión H11) — CERRADA,
`NO_GO_POR_PRESUPUESTO`, `ALCANCE_SUPERVIVIENTES_21`:** aplicando gates
S1-S8 (AND) / R1-R14 (OR) (contrato `S47-DT1-SLICE2-CARACTERIZACION_v6.md`)
a los 12 candidatos originales y, tras `EVIDENCIA_INSUFICIENTE`, a los 9
pendientes (contrato `S47-H11-AMPLIACION-13-21_v1.md`), el universo completo
de 21 símbolos supervivientes de `register()` en `tools/pcb.py` resultó
**21/21 `NO_APTO`** bajo el diseño de extracción mínimo evaluado (mover +
wrapper delgado). Patrón dominante: los símbolos pequeños fallan S7 (tamaño
insuficiente, <80 LOC); los pocos con tamaño suficiente (`add_via`,
`get_tracks`, `set_footprint_ref`) fallan S1/S8 por fan-in alto hacia
helpers compartidos (`_delete_copper`/`_resolve_board`/`_via_params`).
Revisado independientemente (Codex, `APROBAR_CON_CAMBIOS` → 4 hallazgos
documentales sin impacto en veredicto, reconciliados) y aprobado por la
Autoridad (`APROBAR`, 2026-08-08). Unidad final `S47-EXT-13-21-CORREGIDO`,
manifiesto
`d564029b1eea5e6bd3da648cbdb615c3b6cec6f5195fdbf73ea12d2261f65074`, en
custodia histórica versionada
(`docs/historico/piloto-multiagente/S47-S48/archivos_temporales_contrato/custodia/S47-EXT-13-21-CORREGIDO/`).
`NO_GO_POR_PRESUPUESTO` **no** autoriza S48 ni ningún paso
de implementación (contrato §1/§8.6); tampoco refuta los 8 clusters
excluidos institucionalmente, que nunca se evaluaron.

**Consecuencia para el siguiente paso arriba:** el universo de símbolos
individuales de `tools/pcb.py` evaluable bajo extracción mínima
(mover + wrapper delgado) está agotado — no queda ningún candidato "por LOC"
ni por cohesión de símbolo único pendiente de caracterizar con este método.
Retomar DT1 Slice 2 requiere una unidad de extracción distinta (cluster
cohesivo de varias funciones relacionadas, no un símbolo aislado) o un
diseño de extracción distinto al evaluado. Decisión de diseño, exclusivamente
humana.

**Recaracterización sesión 42 (docs-only) — cluster propuesto:**
`docs/analisis/42-dt1-slice2-caracterizacion.md` cambió la unidad de
análisis de "símbolo aislado" a "cluster cohesivo", tal como pedía el
párrafo anterior. Identificó por AST un subconjunto de **13 funciones de
geometría pura / 252 LOC** (`_dist_point_segment` … `_find_track_pad_collision`,
`pcb.py:253-437` + `pcb.py:760-848`) cuyas únicas dependencias externas son
`math` y tipos de anotación — cero aristas hacia `bridge`, hacia el trío
`_audit_error`/`_resolve_board`/`_similars`, ni hacia la taxonomía de
errores. Excluyó deliberadamente 3 funciones adyacentes
(`_polygon_is_simple`, `_segments_intersect`, `_point_in_polygon`) por
solapamiento con clusters institucionalmente excluidos (F-DT.1, familia de
zonas y stitching). Cumple los gates S1/S2/S3/S5/S6/S7/S8 reconstruidos;
declaró un único punto débil real (S4 — ninguna de las 13 funciones estaba
nombrada en `tests/`) con mitigación propuesta (tests unitarios directos).
También caracterizó y descartó, con motivo, el trío de helpers compartidos
(fan-in demasiado alto para extraer solo, LOC insuficiente para extraer
agrupado — el bucket genérico que ADR-0014 ya rechazó) y los 8 clusters
institucionales (~1060 LOC, no refutados, arrastran ADR-0012/D-23.2).

**DT1 Slice 2 — geometría pura: ✅ CERRADA en sesión 42**, misma sesión que
la recaracterización (Autoridad aprobó el cluster propuesto sin cambios).
Las 13 funciones viven ahora en `src/kicad_mcp/tools/pcb_geometry.py`;
`tools/pcb.py` conserva trece re-exports explícitos con alias redundante
(mismo patrón que el Slice 1). Equivalencia AST verificada función por
función contra el commit base (`11f4918`) — cero cambio de comportamiento.
Mitigación del riesgo S4 aplicada: `tests/test_pcb_geometry_unit.py` cubre
las 13 funciones con casos directos (32 tests). Suite offline completa
verde, `ruff`/`mypy` limpios. Ver `docs/historico/sesiones/42-reporte.md`.

**Hallazgo colateral (revisión Codex sobre el slice, no de esta
caracterización): `_copper_on_layer` no reconoce capas internas de una vía
pasante — ✅ CERRADO sesión 43.** `CopperItem.via_layers` sólo guarda
`(capa_inicio, capa_fin)` — para un board multicapa, una vía pasante real
conecta también las capas internas entre esos dos extremos, pero
`_copper_on_layer(via, "In1.Cu")` devolvía `False` aunque
`docs/specs/tool-catalog.md:437` promete "una via pasante cuenta para
cualquier capa de su span". Bug preexistente (AST idéntico desde antes de
sesión 42, no introducido por el slice).

**Decisión de diseño tomada:** poblar el span real desde el bridge, dejar
el filtro puro. `pcb_geometry.py` (geometría pura, sin acoplamiento a
`bridge` desde el Slice 2) no debía ganar ese acoplamiento — así que el
stackup del board se resuelve donde ya vive (`bridge/ipc.py`) y viaja como
dato nuevo en `CopperItem.via_span_layers: tuple[str, ...] | None` (default
`None`). `via_layers` queda intacto (sigue siendo el par de extremos que
el encoder renderiza en la línea `V ... F.Cu-B.Cu`, formato F1). Helper
puro nuevo `_via_span_layer_names` (slice ordenado del stackup habilitado
entre los dos extremos, reusando `_copper_layer_values` ya existente para
`add_keepout_zone`); `_kipy_copper_to_item` y los tres productores
(`list_net_copper`/`list_all_copper`/`get_copper_by_kiid`) lo pueblan **una
vez por llamada, sólo si el resultado contiene al menos una vía**.
`_copper_on_layer` prioriza `via_span_layers` si está disponible y cae al
comportamiento de extremos (`via_layers`) si no — en un board de 2 capas
ambos caminos dan el mismo resultado (selección y encoding idénticos), así
que D3-D7/Validation Suite A-B/goldens no cambian.

**Semántica uniforme en los tres call sites** (`get_tracks`,
`delete_tracks_bulk`, el guardrail #5 de stitching): los tres comparten
`_copper_on_layer`, así que corregirla una vez alcanza para los tres. Decisión
explícita del humano dado que `delete_tracks_bulk(layer=<capa interna>)` pasa
de borrar 0 vías a borrarlas por defecto (`include_vias=True`,
`dry_run=False` son los defaults — no hay red automática, sólo las válvulas
*opt-in* ya existentes).

**Compatibilidad KiCad 9.0-9.0.4 (riesgo no anticipado en la caracterización
original, hallado durante el fix):** `Board.get_enabled_layers()` es
`versionadded 0.5.0` (KiCad 9.0.5+), y F4 declara mínimo compatible 9.0.
`_safe_copper_layer_values` degrada con log estructurado ante cualquier
fallo de esa lectura (no `except Exception: pass` — CLAUDE.md regla 1) en
vez de romper una lectura de `get_tracks`/`delete_tracks_bulk` que hoy
funciona en esas versiones.

**Sin ADR** — mismo criterio que el fix de bbox Edge.Cuts de sesión 31b:
implementa un contrato ya documentado (`tool-catalog.md:437`) sin cambiar
ninguna superficie externa. Auditado por Codex DOS VECES: antes de
implementar (`APROBAR_CON_CAMBIOS`, 3 hallazgos MAJOR sobre el plan
corregidos antes de escribir código: la tesis de "no-op estricto" era
falsa —el fix agrega un request IPC nuevo—, `delete_tracks_bulk` no estaba
protegido por `dry_run`/`include_vias` por defecto como decía el plan
original, y la cobertura de tests propuesta inicialmente era
insuficiente); y de nuevo sobre el CÓDIGO YA IMPLEMENTADO
(`APROBAR_CON_CAMBIOS`, 3 hallazgos reales que el plan no podía haber
anticipado, los tres corregidos): (1) MAJOR — el log de degradación
interpolaba `str(exc)` en un JSON armado a mano en vez de usar
`json.dumps` (ya establecido en `logging_config.py` para casos idénticos:
`log_socket_glob_ambiguous`/`log_ipc_retry`), produciendo JSON inválido
con mensajes de excepción hostiles (comillas/saltos de línea) — corregido
con `log_copper_layer_stackup_unavailable` nuevo, mismo patrón que sus
hermanos; (2) MINOR — el invariante documentado de `via_span_layers`
afirmaba coincidencia posicional con `via_layers`, falsa si
`drill.start_layer > drill.end_layer` (kipy no garantiza el orden) —
corregido a igualdad de conjunto; (3) MINOR — faltaba el canario de "cero
IPC sin vía" para `list_all_copper`, el test `include_vias=False` de
`delete_tracks_bulk` pasaba igual con el bug sin corregir (no
discriminaba), y el test GUI elegía una vía a ciegas asumiendo pasante —
los tres corregidos.

**Verificación:** 26 tests unit nuevos en total (`test_ipc.py` +17: helper
puro + degradación con test de JSON válido ante mensaje hostil + plumbing
de `_kipy_copper_to_item` + canarios de conteo de IPC en los tres
productores; `test_pcb_geometry_unit.py` +5: filtro con/sin span +
invariante extremos como conjunto; `test_pcb_delete_bulk.py` +3, uno
reescrito para ser autocontenido: los tres modos del sitio destructivo),
sin editar ninguno de los tests preexistentes de antes de esta sesión.
Suite offline **468 passed** (443 previos + 26 nuevos de estos tres
archivos + 1 archivo GUI nuevo deseleccionado por marker). Goldens sin
tocar y verdes. `ruff`/`mypy` limpios. Test `integration_gui`
(`tests/test_pcb_session43_multilayer_via_span_gui.py`) **escrito, pendiente
de ejecución humana** — el protocolo GUI de este proyecto no tiene hoy
ningún proyecto de referencia con capas internas habilitadas (mismo
precedente que sesión 32d); hace `skip` explícito con esa razón si el
board abierto tiene menos de 4 capas de cobre.

**Auditoría Codex #3 (sobre-ingeniería, sobre el código ya implementado y
verificado, no sobre el plan) — APROBAR_CON_CAMBIOS, verificado hallazgo por
hallazgo antes de aplicar nada:**
- Aplicado: la rama defensiva de `_via_span_layer_names` para un extremo
  ausente de `copper_values` era inalcanzable en producción (el drill de una
  vía real siempre referencia capas del mismo board que produjo el
  stackup) — eliminada junto a su test dedicado.
- Aplicado: el default `copper_values: Sequence[int] = ()` de
  `_kipy_copper_to_item` no lo usaba ningún llamador productivo (los tres
  productores siempre pasan el valor resuelto) — ahora es obligatorio; el
  test que sólo consagraba el default fue renombrado para pasar `()`
  explícito (esa rama sí es real: resultado sin vías o stackup degradado).
- Aplicado: se recortaron los docstrings más verbosos (`via_span_layers`,
  `_safe_copper_layer_values`, `_via_span_layer_names`,
  `log_copper_layer_stackup_unavailable`, `_copper_on_layer`) al nivel de
  densidad de sus pares existentes en el archivo (`log_socket_glob_ambiguous`/
  `log_ipc_retry`), y se corrigió una afirmación imprecisa en
  `_copper_on_layer` ("board de 2 capas donde nunca se calculó" — en
  realidad los tres productores sí resuelven el stackup en 2 capas cuando
  hay una vía; `None` sólo ocurre por degradación o construcción manual).
- **Rechazado, con razón explícita:** la recomendación principal de fusionar
  `via_layers`/`via_span_layers` en un único campo. Auditoría #1 ya había
  evaluado esta misma distinción como legítima (no redundancia): son datos
  con disponibilidad distinta (`via_layers` siempre viene del drill de la
  vía, sin costo extra; `via_span_layers` requiere una lectura de stackup
  del board que puede degradar) y longitud distinta (2 vs N elementos).
  Fusionarlos exige sobrecargar la semántica del campo único y tocar de
  nuevo el encoder (`pcb_encoders.py:283`, formato F1) — riesgo de churn no
  justificado por ahorrar un campo, en una función que ya pasó dos rondas
  de auditoría previas sobre esta misma superficie.
- **Rechazado:** la mayoría de los tests señalados como "redundantes"
  (`test_via_with_span_still_matches_both_extremes`,
  `test_kipy_copper_to_item_track_never_populates_via_span_layers`, el test
  de interacción `include_vias=False` en el sitio destructivo) verifican
  ramas de dispatch o interacciones con flags preexistentes que no son
  mecánicamente idénticas a otro test ya existente — se mantienen.
- Soporte de vías ciegas/enterradas en `_via_span_layer_names`, la
  degradación KiCad 9.0-9.0.4, y el test `integration_gui` diferido: los
  tres marcados **JUSTIFICADO** por la propia auditoría (frontera IPC real
  con boards externos, riesgo de compat confirmado por versión de API, y
  precedente de sesión 32d respectivamente) — sin cambios.

Tras estos recortes: suite offline **467 passed** (-1 test eliminado, sin
reemplazo, por ser el único que cubría la rama defensiva quitada). Goldens
sin tocar y verdes. `ruff`/`mypy` limpios.

**Fixture `007_pcb_multicapa` preparado — corrección de una premisa falsa.**
Esta misma entrada afirmaba que "el protocolo GUI de este proyecto no tiene
hoy ningún proyecto de referencia con capas internas habilitadas". **Es
falso:** `tests/fixtures/004_real/video.kicad_pcb` —el proyecto de
referencia que el protocolo GUI ya usa— es de 4 capas de cobre con 808 vías
pasantes; `validation-suite/level-c/hackrf-one/` también. El bloqueo real
era otro: `get_tracks` no trunca (`src/kicad_mcp/tools/pcb.py:1551-1559`,
`CONTEXT_BUDGET_IMPOSSIBLE`), así que contra un board con 808 vías el test
fallaría con error en vez de saltarse. Se creó
`tests/fixtures/007_pcb_multicapa/` (PCB sintética mínima escrita a mano:
4 capas, 1 vía pasante F.Cu-B.Cu, 2 segmentos — 128 líneas, 4KB, contra los
159822/5,5MB de `004_real`), validada con `kicad-cli pcb drc` (0 errores,
0 unconnected items) y cargada con el módulo `pcbnew` de KiCad 10
(`GetCopperLayerCount()==4`, capas y vía correctas). El test
(`tests/test_pcb_session43_multilayer_via_span_gui.py`) ganó un preflight
(`_preflight_same_board_open`, mismo patrón que
`test_pcb_session27_zone_persist_gui.py`) para hacer `skip` accionable si el
board abierto no coincide con `KICAD_MCP_PROJECT`, en vez de fallar
confuso contra el board equivocado. Protocolo documentado en
`docs/guias/pruebas-gui.md` §Fixture `007_pcb_multicapa`. **Ejecutado
(2026-09-05) contra KiCad real con el fixture abierto: 1 passed** — el fix
de `_copper_on_layer` de sesión 43 queda verificado end-to-end, no sólo en
unit tests.

**2ª auditoría Codex sobre el test ya ejecutado — hallazgo MAJOR real,
corregido.** El test original sólo aserteaba *inclusión* de la vía al
filtrar por la capa interna, nunca *exclusión* de cobre de otra capa —
verificado con evidencia propia que el filtro de `get_tracks`
(`src/kicad_mcp/tools/pcb.py:1546`/`:1643`) es una comprehension simple
sobre `_copper_on_layer`; una regresión que la rompiera (p. ej. devolver
todo sin filtrar) habría pasado el test igual. Se agregó la aserción
negativa (segmento F.Cu ausente de `get_tracks(layer="In1.Cu")`) y se
convirtieron los `skip` post-preflight en `fail` (son invariantes del
fixture dedicado, no casos de "board genérico"). Re-ejecutado: **1
passed**. Detalle completo en `docs/historico/sesiones/43-reporte.md`.

**Estado de DT1 tras Slice 2:** ambos slices mecánicos identificados hasta
ahora (encoders, geometría) están cerrados. Lo que resta en `tools/pcb.py`
es el trío de helpers compartidos (no extraíble solo por LOC insuficiente,
ver arriba) y los 8 clusters institucionales de zonas/stitching (excluidos
por F-DT.1, arrastran ADR-0012/D-23.2). Retomar DT1 más allá de este punto
requiere decisión humana explícita sobre si levantar la exclusión de
F-DT.1 o cerrar DT1 con el estado actual.

**Decisión (sesión 48): DT1 CERRADA con el estado actual (Slice 1 + Slice
2, ~500 LOC extraídas de forma mecánica y reversible). No se levanta
F-DT.1.**

Motivo: los 8 clusters institucionales que F-DT.1 protege cargan
directamente el contrato ADR-0012/D-23.2 (persistencia disco==memoria==
`err_post` de `route_board`/`fill_zones`/`add_zone`), y `route_board` en
particular ya tiene veto vigente desde sesión 40 (I-4) por fragilidad de
mocks (4 tests parchean `run_drc`/`run_autoroute` como atributos del
módulo — moverlo los rompe en silencio, verde falso). Además, ahora mismo
hay un P0 abierto y no resuelto en exactamente esa superficie
(`F-V3-ZONE-FILL-CRASH`, ver P0 arriba — causa raíz aún no encontrada).
Refactorizar código bajo investigación activa de un crash reproducible en
el contrato de persistencia más crítico del proyecto viola el mismo
criterio de bajo-riesgo/reversibilidad que ya limitó los slices ejecutados
a geometría pura y encoders sin acoplamiento a `bridge`. `hoja-de-ruta-v5.md`
tampoco habilita preparación de release (y con ella, limpieza estructural)
hasta cerrar las 3 validaciones de la Validation Suite — abrir este frente
ahora está mal secuenciado.

**Condición de reapertura explícita:** revisar F-DT.1 sólo después de que
`F-V3-ZONE-FILL-CRASH` (P0) tenga causa raíz y esté cerrado. Aun entonces,
tratar el levantamiento de F-DT.1 como decisión de ADR explícita —no como
slice mecánico— dado el acoplamiento a D-23.2.

## DT3 — Geometría de dominio dentro de `bridge/` — ABIERTA

**Estado:** abierta; no modificada por las sesiones 40–41.

**Descripción:** existen tipos o lógica geométrica de dominio dentro de
`bridge/` cuya ubicación arquitectónica debe reevaluarse antes de una
extracción.

**Fuente histórica:** `docs/analisis/CONTEXTO_CHAT.md`, sección DT3, y
`docs/analisis/40-dt1-caracterizacion.md`.

**Próximo paso:** caracterización independiente. No mezclar con el siguiente
slice de DT1 sin decisión humana.

## DT2 — Boilerplate transversal ×19 sin decorador — ✅ CERRADO sesión 39

**Origen:** `docs/analisis/auditoria-tecnica-integral-2026-08.md` (fila DT2
de la tabla de deuda técnica en `:383`, plan de acción M1 en `:440`; el doc
en sí no está trackeado en el repo — esta entrada es la primera referencia
a DT2 en `BACKLOG.md`). Prerrequisito declarado de `DT1` (sesión 40,
partición de `tools/pcb.py`): sin un lugar único para el preámbulo
transversal, DT1 fijaría la deuda en más archivos en vez de reducirla.

**Conteo real (P3 de la sesión):** 19 tools MCP mutantes registradas, **17**
sitios de preámbulo (`_delete_copper` sirve a `delete_track`+`delete_via`,
`_set_property_core` a `set_value`+`set_footprint`). Anatomía real: **tres
familias estructurales**, no una uniforme (H1 del prompt, parcialmente
refutada) — Familia A (13 tools W-IPC de PCB → 12 sitios, preámbulo casi
literal), Familia B (`route_board`/`reload_board_from_disk`, desviaciones
deliberadas de contrato D-14.3/ADR-0011/ADR-0012), Familia C (3 mutantes
de esquemático, sin guard IPC). El epílogo (timer/G1/audit/snapshot/log)
resultó NO uniforme entre las 19 — fuera de alcance del decorador.

*(Errata post-merge, 2026-08-05: la versión original de esta entrada decía
"16 sitios" / "11 tools" en la Familia A — error aritmético, `delete_tracks_bulk`
es Familia A pero había quedado fuera de la suma. Corregido acá y en
`docs/adr/0014-mutating-tool-decorator.md`; el reporte de sesión
`docs/historico/sesiones/39-reporte.md` preserva el conteo original, sin
tocar, por convención de bitácora.)*

**Decisión:** `@mutating_tool` (`src/kicad_mcp/tools/_mutating.py`) cubre
sólo las guardas de ENTRADA (`_guard_live_stale` + `check_no_external_disk_edit`
+ `_check_base_snap`) de la Familia A. Aplicado a **12 tools de los 17
sitios reales** (`move_footprint`, `set_footprint_ref`, `add_track`,
`add_via`, `save_board`, `delete_track`, `delete_via`,
`draw_board_outline`, `add_zone`, `add_keepout_zone`, `fill_zones`,
`delete_zone`).
**Excluidas con justificación** (ver `docs/adr/0014-mutating-tool-decorator.md`):
`delete_tracks_bulk` (preámbulo post early-return de `dry_run` — hoistearlo
cambiaría comportamiento observable), Familia B completa (contrato
deliberado), Familia C completa (estructuralmente distinta, candidata a
decorador hermano en sesión futura).

- **Reducción medida:** `tools/pcb.py` 3507 → 3419 líneas (-88, -2.5%).
  4 helpers movidos a `_mutating.py` (~49 líneas relocadas, no borradas).
  12 tools con preámbulo colapsado a 1 línea de decorador cada una (10
  con reducción neta de -4/-5 líneas; `delete_track`/`delete_via`
  netean +1 cada uno porque su guard vivía una sola vez en el núcleo
  compartido `_delete_copper`, que además ganó un párrafo de docstring
  explicando por qué `base_snap_check=False`).
- **Verificación:** suite offline **392 → 406 passed** (392 baseline
  intacto sin modificar un solo test existente + 14 tests nuevos de
  `tests/test_mutating_tool.py`, aislados con spies + 2 canarios de
  registro contra `tools/pcb.py` real). `ruff check`/`ruff format
  --check`/`mypy src/` limpios.
- **Sin cambio observable:** mismos códigos de error, misma taxonomía F3,
  mismas firmas de tool (FastMCP ve la firma original vía
  `functools.wraps`/`__wrapped__`).
- Ver `docs/historico/sesiones/39-reporte.md` para el detalle completo y
  la propuesta de sesión 40 (DT1).

## P1 (investigación Fase 4) — Conectividad GND no cierra tras refill (F-D5-01 / F-V1c-01 / F-V2-VIA-HUERFANA) — CERRADO PARCIALMENTE sesión 32d, ver sub-patrón abierto abajo

**3ª instancia confirmada del patrón → cumple el trigger de promoción
explícito** ("2 dogfoodings/validaciones independientes reproducen el
patrón" para F-D5-01 original; el criterio análogo de sesión 32 exigía
específicamente una 3ª instancia en régimen distinto, ahora cumplido).

| # | Sesión | Board | Síntoma exacto |
|---|---|---|---|
| 1 | 25 (dogfooding D5) | despertador | isla GND sin vía al plano |
| 2 | 31c (Nivel A) | anavi-dev-mic | 1 vía GND (F.Cu-B.Cu) no conectada a un pad de 0.30×0.30mm (MK1) |
| 3 | 32 (Nivel B) | anavi-macro-pad-12 | 2 pads GND (J4/J5 pad 3) no conectados al plano/track tras refill |

**Origen sesión 32:** DRC de cierre post-`route_board`+refill de
recuperación (ver F-V2-REFILL-SILENCIOSO arriba — este hallazgo apareció
*después* de la recuperación manual, no es un artefacto del refill
fallido): 20 errores totales, de los cuales 2 `unconnected_items` nuevos
vs los 19 del ground truth. `_orphan_vias` (script extendido,
`measure_ground_truth.py` schema 1.1) confirmó **0 vías huérfanas** — el
mecanismo de esta 3ª instancia es a nivel de *pad* (conectividad
pad-a-zona/track), distinto del mecanismo de 31c (vía aislada), pero el
síndrome de fondo (conectividad GND que sobrevive al refill sin cerrar)
es el mismo.

- **Severidad:** el trigger de promoción elevó esto a **P1 investigación
  Fase 4** (patrón sesión 23/26, P4.0-style). No bloquea sesión 32 ni 33
  en sí (14/15 → 42/42 nets ruteables completaron en ambos casos).
- **MECANISMO AISLADO Y CONFIRMADO CAUSALMENTE (sesión 32c).** Freerouting
  rutea tracks de otros nets sin reservar corredor para que el flood-fill
  del plano GND alcance pads específicos (refinamiento medido de D-19.1).
  Cuando ese track ajeno corre en paralelo al borde de la zona en el
  mismo rango Y que un pad GND situado en un corredor angosto, su
  clearance obligatorio consume el corredor por completo — el pad se
  queda sin conexión al plano. Confirmado con 2 experimentos de borrado
  dirigido + re-fillado real (`kicad-cli pcb drc --refill-zones
  --save-board`) sobre copias desechables en anavi-macro-pad-12: borrar
  solo el track troncal `+5V` (rango Y que cubre `J4.3`/`J5.3` pero no al
  `J1.3` sano) resuelve `J5.3` (backbone real, solo faltaba el contacto
  local); `J4.3` necesita además borrar el track serpenteante de su
  propio pin 2 (no tiene ningún track/vía GND propio, patrón original de
  sesión 25). Generalización confirmada por correlación fuerte en
  anavi-dev-mic (`MK1.3` rodeado por sus propios 4 pines hermanos a
  0.85–2.94mm). 3 hipótesis alternativas refutadas con experimentos
  causales: `island_removal_mode`, keepouts de `enforce_hole_clearance`
  (9.3mm de distancia, sin relación), fill totalmente despojado.
- **Fix diferido a sesión 32d** — vive en el pipeline de refill/zonas de
  `route_board`, fuera del "SI Y SÓLO SI" de alcance quirúrgico de 32c.
  Hipótesis completa: tras el bloque D-23.2 + DRC post-route, detectar
  `unconnected_items` sobre nets con zona de cobre propia; stitching
  automático con `add_via` (ya existe la tool) solo si el pad cae dentro
  del outline de una zona de su mismo net; si no es seguro automatizar,
  exponer el conteo en clave explícita del payload en vez de diluirlo en
  `por_tipo`.
- **Hallazgo lateral, sin acción:** `L9.1` en anavi-macro-pad-12 comparte
  la misma dependencia estructural 100%-de-la-zona que `J4.3` (grafo de
  conectividad sin nodos ZONE), sin generar `unconnected_items` hoy —
  candidato de vigilancia.
- **Ver** `docs/investigacion/32c-f-d5-01.md` (reporte completo de
  investigación), `docs/historico/sesiones/32c-reporte.md` (ejecutivo),
  `validation-suite/level-a/anavi-dev-mic/metrics.md` (instancia 2) y
  `validation-suite/level-b/anavi-macro-pad-12/metrics.md` (instancia 3).

### CERRADO PARCIALMENTE (sesión 32d) — stitching automático, topología "capas opuestas"

Fix implementado en `route_board` (D-32d.1/D-32d.2,
`docs/adr/0012-route-board-persist-contract.md` §"F-D5-01 stitching"):
tras el refill final, `route_board` stitchea automáticamente una vía para
cada pad huérfano cuyo net tenga zona propia en la capa OPUESTA a la del
pad (5 guardrails geométricos estrictos, D3). Es la primera respuesta
arquitectónica del proyecto a D-19.1 (Freerouting no ve el plano como
conductor) — mitiga el síntoma, D-19.1 sigue vigente como restricción del
motor externo.

**Hallazgo de sesión 32d: las 3 manifestaciones NO comparten topología.**
Instancia 1 (despertador) e instancia 2 (`anavi-dev-mic`, `MK1.3`) son la
topología "capas opuestas" — el pad huérfano está en una capa y la(s)
zona(s) del net en la OTRA; una vía pasante conecta ambas correctamente.
**Cierra con este fix.** Instancia 3 (`anavi-macro-pad-12`, `J4.3`/`J5.3`)
es una topología DISTINTA — pad y única zona GND en la MISMA capa (B.Cu),
sin cobre GND en F.Cu. Una vía ahí uniría B.Cu (relleno retraído por el
clearance del track ajeno) con F.Cu (sin cobre GND): no conectaría nada.
El guardrail #4 rechaza correctamente (verificado con la geometría real
del fixture, no sólo por diseño teórico) — **queda abierta**, ver entrada
siguiente.

- **Verificación:** canario unit permanente (8 tests, guardrails 1-5 +
  exposición mixta + H4 + re-medición de `err_post`) + suite
  offline/integration completas verdes. Verificación end-to-end contra el
  motor real (`anavi-dev-mic` cerrando, `anavi-macro-pad-12` rechazando)
  **escrita pero pendiente de ejecución humana**
  (`tests/test_pcb_session32d_stitching_gui_slow.py`) — requiere abrir
  cada proyecto en el PCB Editor de KiCad (protocolo manual, sin
  automatización posible en este MVP). Ver
  `docs/historico/sesiones/32d-reporte.md` §"Verificación pendiente".
  **Intento Ciclo C4:** H1 detenido por `KICAD_TIMEOUT` — causa raíz NO
  es el fix de stitching, sino el motor de Freerouting trabándose en el
  net vecino al pad huérfano. Ver `F-C4-01` arriba en §P0. Gate GUI 32d
  sigue pendiente de ejecución exitosa.

### Abierto — F-D5-01-B: estrangulamiento lateral en la misma capa (`anavi-macro-pad-12`)

**Origen:** sub-patrón descubierto en sesión 32d al intentar aplicar el
fix de stitching a `anavi-macro-pad-12`. El pad huérfano (`J4.3`/`J5.3`,
B.Cu) y la única zona GND del board (también B.Cu) están en la misma
capa; el track ajeno (`+5V`) que 32c aisló como causal también corre en
B.Cu — es un estrangulamiento lateral del corredor, no un problema de
capas opuestas. Ninguna vía puede remediarlo: conectaría cobre real
(B.Cu, del lado del pad) con la nada (F.Cu, sin cobre GND).

**Candidatos de mitigación NO evaluados** (fuera del alcance quirúrgico
de sesión 32d): ensanchar el corredor disponible (mover el pad o rediseñar
la zona, fuera de lo que `route_board` puede decidir autónomamente); un
keepout que empuje a Freerouting lejos del corredor angosto ANTES de
rutear (viable en principio — `add_keepout_zone` ya existe — pero
requeriría identificar el corredor angosto ANTES del ruteo, no después,
cambio de orden de pipeline no trivial); aceptar el patrón como límite
conocido del autoruteo y documentarlo en `docs/glosario.md`/
`restricciones-kicad.md` para que el agente lo anticipe en vez de
descubrirlo por DRC.

**Severidad:** no bloquea flujos existentes (evidencia: `J4.3`/`J5.3` no
impidieron que macro-pad-12 completara 15/15 nets ruteables en sesión 32).
Candidato a investigación P4.0-style si aparece una 2ª instancia
confirmada de este sub-patrón específico (capas iguales, no opuestas).

## P2 — Correcciones puntuales con evidencia repetida

| Item | Evidencia | Estado |
|---|---|---|
| `run_erc()` posiciones ÷100 | F-03 (D2), F-19b-12 (19b) | ✅ Cerrado (sesión 51) — causa en `kicad-cli` 10.0.6 (JSON crudo ÷100, verificado contra `.kicad_sch`), no en el bridge. `run_erc` compensa ×100 sólo en la serie 10.0.x (`bridge/rules.py::_erc_pos_scale`); otras versiones pasan crudas. Re-evaluar el rango al soportar 10.1+/9.x. |
| `health()` no distingue `PROJECT_NOT_CONFIGURED` vs `PROJECT_PATH_NOT_FOUND` | F-02 | ✅ Cerrado — `health()`/`project` ahora emite `PROJECT_NOT_CONFIGURED` (env var ausente) o `PROJECT_PATH_NOT_FOUND` (env var apuntando a un path inexistente) con hints distintos; adición pura al `StrEnum ErrorCode` (F1/F3 intacta). Ver `docs/specs/tool-catalog.md` §meta y §Taxonomía. |
| `draw_board_outline` inmutable (sin `replace=true`/`delete`) | F-06 | Abierto. |
| Asimetría `delete_track` sí / `delete_footprint` no | D-R3, D-R8 | Abierto, sin ADR — **sigue así deliberadamente**. Escaló a P0 en sesión 31 (F-V1-02: refs duplicados bloqueaban `route_board`), pero sesión 31b cerró ese caso sin tocar la asimetría — resolvió por anotación (`set_footprint_ref`), no por borrado. Ver ADR-0013: un `delete_footprint` general sigue rechazado, ADR-0010 vigente sin excepción. |
| Doc del lock no-reentrante del bridge (`self._lock` no es reentrante) | Sesión 19d | ✅ Cerrado (sesión 51) — regla central en el docstring de módulo de `bridge/ipc.py` (lock no reentrante → deadlock silencioso; helpers bajo el lock no lo toman). |
| Issue upstream a Freerouting sobre `gui.enabled=true` colgando la JVM (R9) | Sesión 17 | Mitigado en código; issue no abierto (no urgente). |
| `move_footprint` no dispara refill de zonas — un DRC leído de disco tras mover pads sobre un plano mide fill rancio, no el estado real | Sesión 26, investigación 26 §2 | Nota de proceso: `fill_zones()` obligatorio tras colocación masiva, antes del baseline DRC. No es un bug de la tool (su contrato nunca prometió refill) — es un punto ciego de brief/protocolo de dogfooding. |
| `route_board`/netclasses descartan silenciosamente `diff_pair_width`/`diff_pair_gap`/`diff_pair_via_gap` (`bridge/rules_reader.py:217`) — el flujo no puede dirigir el ruteo de un par diferencial por netclass, aunque el `.kicad_pro` lo declare | Sesión 32 (hallazgo estructural, H1b reformulada) | Abierto. Verificado además que **ningún** proyecto ANAVI del catálogo (dev-mic, miracle-emitter, word-clock, macro-pad-12) asigna netclasses en la práctica (`"nets": []` en todos) — la brecha de código nunca fue ejercitada por ningún candidato real hasta ahora. Candidato a Nivel C/D si aparece un board con asignación real. |

## P2 — Release polish (post-Fase 4, pre-release Open Source)

No bloqueante hoy — condicionado a las 3 validaciones exitosas de la
Validation Suite (sesiones 31-33 según `hoja-de-ruta-v5.md`) y al cierre
de P1 (ya cumplido, sesión 30). Retomar en sesión 34+ (preparación de
release Open Source), no antes.

- **ADR-0014 en adelante** (drift corregido sesión 31c — el número 0013
  ya lo consumió sesión 31b, ver `docs/adr/0013-refs-duplicados-por-anotacion-no-borrado.md`):
  documentar el mecanismo indocumentado de edge clearance de Freerouting
  (hoy solo entendido por ingeniería inversa de bytecode, D-V3.5).
- **Docs de arquitectura para colaboradores externos.**
- **Test canario de Freerouting edge clearance.**
- **Licencia + README + CONTRIBUTING.**
- **Limpieza de código muerto** de sesiones intermedias.

## P3 — CRUD de esquemático (R12)

Las tools de escritura de sch son puramente aditivas:
`add_symbol`, `set_value`, `set_footprint`, `connect_pins`, `clone_symbols`.
No existe `delete_wire`, `delete_label`, `add_no_connect`, `set_symbol_attr`,
`sync_symbol_from_library`. Un agente puede **diseñar** un sch desde cero
pero no **corregirlo** — cualquier defecto requiere GUI humana. Bajado de P1
a P3: v7 lo excluye explícitamente del alcance de Fase 3 (que se concentra en
el ciclo de ratificación PCB), habilita autocorrección de sch pero no es
bloqueante para la consolidación en curso.

- **Origen:** F-19b-01 a 05, 08, 10 (sesión 19b). Confirmado sin ejercitar en
  D3/D4 porque el sch pre-corregido no necesitó tocarse.
- **Esfuerzo estimado:** L (varias tools, cada una con su propio patrón de
  verificación de efecto vía kicad-skip).

## P3 — `get_world_context(kind="sch")` falla con `#PWR*`/`#FLG*` (R13) — ✅ CERRADO sesión 51

Set-difference asimétrico entre posiciones (todo símbolo) y netlist
(kicad-cli excluye pseudo-símbolos `#`-prefijados). Dispara
`KICAD_CLI_FAILED` en **cualquier** esquemático con símbolos de
alimentación/power-flag — no es un caso raro.

- **Origen:** D-19e.2, confirmado de nuevo como F-D4-01 en sesión 22.
- **Cierre (sesión 51):** reproducido con `kicad-cli` real (001_basico + `power:GND`
  `#PWR01` → `posición sin netlist: #PWR01`). Fix en `bridge/state_builder.py::_rebuild`:
  se descartan de las posiciones los refs `#`-prefijados antes de indexar/cruzar con el
  netlist (cubre también `#PWR?` repetidos). Un ref real sin netlist sigue siendo error.
  Tests: 2 unit + 1 `integration` en `tests/test_state_builder.py`.
- **Pendiente de verificación (cierre sesión 51):** `-m integration` no se re-ejecutó
  al cierre (KiCad cerrado); lo mismo aplica al fix de F-03. Correrlo antes de mergear.
  Auditoría de Codex sobre los commits de sesión 51: sin hallazgos (ver `51-reporte.md`).

## P3 — Loop de vías de `enforce_hole_clearance` posiblemente código muerto (R16, D-23.3) — causa raíz confirmada sesión 48/49, fix diferido

En 3 corridas de investigación de sesión 23, el loop de vías de
`enforce_hole_clearance` (`ipc.py`, keepouts `via_*`) nunca creó un
keepout. Deuda técnica identificada pero **no se toca** salvo que aparezca
evidencia nueva de que importa — es investigación independiente. Ver
`docs/DECISIONES.md` D-23.3 para el texto completo de la decisión y
`docs/historico/sesiones/23-reporte.md` para el porqué (el bug real que
motivó la investigación de sesión 23 se resolvió con un mecanismo
distinto, ADR-0012/D-23.2, no con este loop).

**Causa raíz confirmada (sesión 48, re-hallada sin cruzar referencia con
esta entrada — hallazgo colateral de F-V3-ZONE-FILL-CRASH):**
`enforce_hole_clearance` (`ipc.py:2170`) filtra vías con `vias = [it for
it in raw_board.get_tracks() if type(it).__name__ == "Via"]`.
`Board.get_tracks()` de kipy 0.7.1 (`Sequence[Union[Track, ArcTrack]]`)
**nunca devuelve `Via`** — hay un `get_vias()` separado. Verificado en
vivo: 256 vías creadas, `get_tracks()` reportó 0; `get_vias()` reportó
las 257. Explica el mecanismo exacto de por qué nunca dispara, algo que
sesión 23 no había podido determinar.

**Sesión 49 — juicio cruzado con Codex sobre si esta causa raíz cumple el
umbral de D-23.3 ("evidencia de que importa"). Veredicto: BLOQUEAR, no
alcanza.** La causa raíz es evidencia de *mecanismo*, no de *impacto* —
ningún dogfooding detectó jamás un `hole_clearance` real contra vía que
el loop hubiera evitado. Fix candidato escrito y descartado (no
commiteado) por 3 razones verificadas: (1) rompería el gate calibrado
`tests/test_pcb_session27_zone_persist_gui.py`
(`_KEEPOUTS_MIN=4`/`_KEEPOUTS_MAX=8`) — medido sobre `despertador-routed`:
22 vías, 7 ajenas a GND, produciría ≥11 keepouts; (2) los keepouts que
crea el método son globales por capa sin filtro de net — con varias
zonas de cobre de nets distintos en la misma capa, proteger la zona A
contra una vía ajena podría bloquear que la zona B (dueña legítima de esa
vía) se conecte a ella, riesgo nunca evaluado porque el caso de
referencia (D3/ANT1) es de una sola zona; (3) riesgo de duplicación de
keepouts por combinación zona×vía en boards con muchas zonas (mismo
territorio que F-V3-ZONE-FILL-CRASH). Detalle completo en
`docs/BACKLOG.md` §F-VIAS-CLEARANCE-DEAD-CODE (sección P0, arriba —
queda ahí por orden histórico de descubrimiento, esta entrada es la
canónica de severidad).

**Trigger de reapertura (reemplaza al genérico de sesión 23):** (a) un
`hole_clearance` real contra vía que sobreviva al refill en un
dogfooding/validación; o (b) decisión arquitectónica que reemplace
D-23.3, con fix de keepouts filtrados por net (no globales por capa) +
validación GUI multi-zona/multi-net + medición de proliferación de
keepouts.

- **Origen:** D-23.3 (sesión 23); causa raíz sesión 48; diferido tras
  juicio cruzado sesión 49.
- **Esfuerzo estimado:** hecho (causa raíz). Fix en sí: indeterminado,
  condicionado al trigger de reapertura de arriba.

## P3 — Ergonomía de colocación (hallazgo D4)

`get_footprint_neighbors` demostró ROI real cuando se usó en conectores con
drill mecánico (J1/J2 en D4: ahorró ~34 min vs. D3). **Pero** la directiva
que lo acotaba a "solo conectores" dejó un punto ciego: 2 `courtyards_overlap`
+ 1 `solder_mask_bridge` en pasivos/ICs que no se verificaron con la tool.

- **Propuesta:** ampliar el uso recomendado de `get_footprint_neighbors` a
  toda colocación manual, no solo conectores — es un cambio de proceso/brief,
  no de código.

### P3 → CERRADO (sesión 29 D7) — F-D5-01: isla GND sin vía al plano (incidente aislado)

En D5 (sesión 25), tras la primera corrida de `route_board`, dos caps
adyacentes (C2/C3, ambos GND) quedaron unidos entre sí por un track pero sin
vía propia al plano B.Cu — a diferencia de otros caps de la misma columna
(C4/C6), que sí recibieron vía del autorouter. 1 error DRC
(`unconnected_items`), diagnosticado con `get_tracks`+`get_footprint_neighbors`
(visibilidad completa) y resuelto con un `add_via` puntual, sin re-ruteo.

**No es señal V3** (no es clearance/hole_clearance/mismatch/persist_failed
contra la zona GND) — es un dato de comportamiento de Freerouting: el motor
puede conectar pads dentro de un net entre sí sin garantizar conectividad
global de esa isla al plano fillado.

- **Estado:** cerrado como observación puntual de D5, no patrón
  sistemático.
- **Evidencia:** trigger de promoción a P2 investigación era "2
  dogfoodings independientes reproducen el patrón". Resultado final:
  D5=1, D6=0, D7=0 → 1/3, no cumplido.
- **Sin trigger de reapertura** salvo que reaparezca en futuros
  dogfoodings.
- **Origen:** F-D5-01, sesión 25. Ver `docs/historico/sesiones/25-reporte.md`
  y `docs/historico/sesiones/29-reporte.md` §Fricciones.

### P3 → CERRADO (sesión 29 D7) — F-D6-01: variabilidad inherente Freerouting/JVM

- **Estado:** cerrado como variabilidad inherente. Sin acción de código.
- **Evidencia:** 3 mediciones D7 (`+3V3`, `/SDA`, `/NSS`) + 2 D5 + 2 D6
  = N=7 total. Sin patrón correlacional con grado de interconexión,
  tamaño del net, ni capas involucradas. Comparación directa sobre
  mismo net `/NSS`: D5=9-10s, D6=110-112s, D7=17.7s — varianza del
  proceso, no propiedad determinística.
- **Documentación pendiente de transferir a `docs/specs/restricciones-kicad.md`**
  (drift detectado en sesión 31: esta entrada afirmaba la transferencia
  hecha desde sesión 29, pero el archivo nunca se tocó — único commit en
  su historia es el de estado inicial): rango operativo esperable
  (9s-112s), advertencia "no asumir que un re-ruteo parcial es
  proporcionalmente barato al tamaño del net". Diff propuesto en sesión 31,
  pendiente de que el humano lo aplique (edición bajo F1, requiere
  levantar el deny de `.claude/settings.json` puntualmente).
- **Sin trigger de reapertura** a menos que aparezcan corridas >600s
  (timeout) o >60s consistentemente en flujos productivos.
- **Origen:** F-D6-01, sesión 28. Ver `docs/historico/sesiones/28-reporte.md`
  y `docs/historico/sesiones/29-reporte.md` §Fricciones.

## P4 — Diferidos sin urgencia (re-evaluar con evidencia nueva)

Nice-to-have, para después de convergencia de Fase 3 (Fase 4).

- **Eval A** (TOON vs JSON/CSV compacto): benchmark de comprensión+tokens
  pendiente desde sesión 04, diferido reiteradamente. Condiciona la
  re-evaluación de ADR-0009 (port a Rust).
- **Soporte multi-hoja** en `get_world_context`/`get_context_delta` de disco
  (`UNSUPPORTED_HIERARCHY`). Depende de si los proyectos reales del humano
  son multi-hoja (pregunta abierta, nunca respondida formalmente).
- **Rotación en `move_footprint`.**
- **Timeout adaptativo** (en vez de fijo) para operaciones IPC largas.
- **Limpieza de tracks huérfanos** (P2.3, sesión 17b).
- **Guard cross-proceso** (sesión 17b) — hoy el lock del bridge protege
  contra concurrencia intra-proceso, no cross-proceso.
- **`add_zone` con hueco interior** (polígono con isla).
- **Opción Y de F-D4-02** (inyectar keepout real al DSN de Freerouting en
  vez de refill+enforce post-ruteo): descartada por ahora en favor de la
  Opción X (sesión 24); reconsiderar solo si aparece evidencia de
  intermitencia real del enfoque actual.
- **A* para causas de nets bloqueadas** en `route_board` — posiblemente ya
  innecesario tras las mejoras de contrato JSON de sesiones 17/19/24.
- ~~**Bbox de validación por Edge.Cuts real** (hoy es footprints ± 100mm)~~ —
  **cerrado sesión 31b** (drift corregido sesión 31c): implementado como
  unión de Edge.Cuts (±10mm) y enjambre de footprints (±100mm) en
  `board_outline`/`board_bbox_mm`/`read_board_context`. Ver F-V1-01 en
  §P1 arriba y ADR-0013 (contexto del fix compañero).
- **Unificación de `POST_ROUTE_PERSIST_FAILED`, `POST_ZONE_PERSIST_FAILED`
  y `POST_ROUTE_REFILL_SKIPPED`**: sesión 27 introdujo
  `POST_ZONE_PERSIST_FAILED` para `fill_zones` y `add_zone(fill=True)`.
  Semánticamente equivalente a `POST_ROUTE_PERSIST_FAILED` (sesión 24,
  `route_board`). Coexisten temporalmente por decisión conservadora (no
  tocar `route_board` en sesión 27). Sesión 32b sumó un tercer código,
  `POST_ROUTE_REFILL_SKIPPED` (cierre de F-V2-REFILL-SILENCIOSO) —
  semánticamente distinto de los otros dos (el refill NO se intentó, vs.
  "se intentó y no se pudo persistir"), pero la misma familia de
  "algo del contrato D-23.2/ADR-0012 no se cumplió". Refuerza la deuda,
  no la resuelve. Deuda: unificar en un solo código compartido (por
  ejemplo `PERSIST_CONTRACT_FAILED` o `TOOL_PERSIST_FAILED`), deprecando
  los tres actuales — o mantener `POST_ROUTE_REFILL_SKIPPED` separado si
  la distinción semántica (intentado-y-fallido vs. no-intentado) se
  considera valiosa al momento de unificar. Impacto bajo — el contrato
  JSON de las tools no cambia (los códigos siguen exportándose como
  strings; el llamador puede aceptar todos). Prioridad post-Fase 3, no
  bloqueante.

## Higiene menor (sin severidad, cuando haya tiempo)

- ~~Fixture `tests/fixtures/despertador-routed/` puede haber quedado stale
  tras correcciones de sch posteriores — verificar antes de reusar en D5.~~
  Resuelto: D5 (sesión 25) verificó (sch sin cambios, ERC idéntico) y
  regeneró el fixture con el ruteo nuevo.
- Contador agregado de `post_fallback` en `health()` para monitoreo pasivo de
  la derivación local (propuesto en `historico/analisis/ANALISIS-ESTADO-Y-BACKLOG.md`
  §C3, nunca implementado, 0 fallbacks observados hasta ahora).
- ~~**P3 — `move_footprint` sin `check_no_external_disk_edit()`**~~ — ✅
  CERRADO sesión 45 (quitado `disk_check=False` de `@mutating_tool`, sin
  motivo de dominio que lo justificara). Detalle:
  `docs/historico/sesiones/45-reporte.md`.
- **P2 — `delete_zone`/`add_keepout_zone` no recalculan fills vecinos**
  (hallazgos A2/A3, auditoría 34a, nuevos — sin precedente previo en
  BACKLOG): ninguna de las dos corre `refill_zones()` tras mutar geometría
  que puede interactuar con zonas de cobre existentes (borrar una zona de
  cobre con vecinas solapadas; crear un keepout `no_pours` sobre un fill
  ya existente). Sin evidencia empírica de impacto real (a diferencia de
  A1, que sí tiene precedente F-D3-01) — documentado como limitación
  conocida, no como fix ciego (D-30.1/D-32c.1: investigar antes de
  fixear). Promover a investigación si la Validation Suite lo evidencia.
  Detalle: `docs/analisis/auditoria-contratos-bridge.md` §3 (fichas
  `delete_zone`, `add_keepout_zone`).

---

## Cómo mantener este documento

Al cerrar un ítem, moverlo a una nota de una línea en el reporte de la sesión
que lo cerró (no acumular aquí "cerrados"). Al abrir uno nuevo desde una
fricción de dogfooding, añadirlo con su origen (F-NN, sesión) para que
`docs/historico/` siga siendo la fuente de evidencia completa.
