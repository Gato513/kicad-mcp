# CONTEXT.md v7 — kicad-mcp (post-Sesión 24, 2026-07-23)

**Handoff destilado. Reemplaza a CONTEXT.md v6.** 26 sesiones (14 base +
4 dogfoodings + 6 sesiones hoja de ruta v3 + sesión 21 hardening +
sesión 23 investigación + sesión 24 fix Opción X mergeada).
**Transición explícita: el proyecto pasa de Fase 2 (descubrimiento
acelerado) a Fase 3 (consolidación y aumento progresivo de confianza).**
Este documento es la conversación destilada: si abrís un nuevo chat,
esto es todo lo que necesitás para tomar el rol.

---

## Estado en una línea

Servidor MCP para operar KiCad autónomamente desde Claude Code. 20+
tools productivas, loop de escritura PCB cerrado sin reverts humanos,
autorouter Freerouting, zonas + keepouts, socket dinámico. **F-D4-02
cerrado técnicamente en sesión 24** (Opción X: reordenar medición DRC +
persistir + fallo visible), mergeado a `master` (commit 972fa80, sin
push), con test de regresión en vivo 2/2 contra KiCad 10.0.4 +
Freerouting real. **Proyecto entra en Fase 3 de consolidación.**
Próximo trabajo: sesión 25 = D5 con baseline dinámico + verificación
reforzada V1/V2/V3.

---

## Rol

Arquitecto senior + revisor técnico crítico. NO escribo código. Diseño,
decido, audito, genero prompts de sesión. Vinculante en decisiones, no
en implementación.

Reglas de operación:
1. Respetar decisiones del CONTEXT o cuestionarlas con evidencia nueva.
2. Mantener el nivel de profundidad técnica.
3. Nueva evidencia > decisiones previas cuando hay contradicción.
4. Cronología importante: algunas decisiones fueron revocadas/ampliadas.

**Regla vinculante para mí (D-V3.6 con extensiones acumuladas):**
briefs generados con tools + calcular márgenes geométricos + resolver
netlist post-separación + consejos operacionales inclusivos por
defecto + hipótesis no ancladas en marco único (considerar que el
reporte puede engañar, no solo la mecánica del fix).

**Nota específica de Fase 3 (cambio de disposición del arquitecto):**
en Fase 2 el instinto era buscar hallazgos activamente y valorar que
un dogfooding encontrara bugs. En Fase 3 eso se invierte: un
dogfooding verde es **evidencia positiva de convergencia**, no
aburrimiento. Resistir la tentación de forzar hallazgos donde no los
hay, o de escalar complejidad prematuramente para "hacer que la
sesión valga la pena". La disciplina de variable controlada y
validación estadística importa más que la novedad.

---

## Fases del proyecto

Reconstrucción explícita del arco, incorporada en v7:

- **Fase 1 — Construcción de capabilities** (sesiones 1-19e): tools
  MCP, arquitectura básica, primeros loops de escritura. Terminó con
  el stack lo suficientemente maduro para dogfoodings intensivos.
- **Fase 2 — Descubrimiento acelerado** (sesiones 20-24): ciclo
  intensivo fix → dogfooding → nuevo bug. Cada dogfooding tenía
  probabilidad alta de encontrar P0/P1 nuevos. D3=8.5, D4=4.5 (V3
  activada). Cierre de Fase 2: sesión 24 merge de Opción X con
  evidencia en vivo. **F-D4-02 fue el último P0 conocido.**
- **Fase 3 — Consolidación y aumento progresivo de confianza**
  (arranca con D5, sesión 25): el objetivo pasa de "encontrar causa
  raíz" a "ganar confianza estadística en que las causas raíz
  eliminadas realmente no vuelven". Ciclo:
  1. Ratificar en dogfooding sobre variable controlada.
  2. Resolver pendientes conocidos (P1, generalizaciones).
  3. Nueva ratificación.
  4. Solo cuando la superficie actual esté estabilizada, escalar
     complejidad.
- **Fase 4 — Expansión funcional** (futuro): release, features
  nuevos, escenarios de complejidad ampliada. Sin fecha. Requiere
  convergencia en Fase 3.

---

## Ruta estratégica vigente (Fase 3)

**Objetivo del proyecto:** herramienta de calidad de referencia. NO
release rápido. Publicar solo cuando la Fase 3 haya cerrado con
estabilidad estadística demostrada.

**Secuencia estricta de Fase 3** (confirmada por el arquitecto,
prioridad orden):

1. **Ratificar cierre de F-D4-02** en dogfooding sobre placa
   despertador (sesión 25 = D5). Objetivo nota ≥9.
2. **Resolver P1 pendiente**: solder mask bridge en ANT1 (sesión de
   fix + test, probablemente sesión 26).
3. **Generalizar D-23.2** a `fill_zones` y `add_zone(fill=True)` — SI
   D5 confirma que el patrón de reordenamiento + persistencia es
   correcto. Sesión dedicada.
4. **Nueva ratificación** en dogfooding (D6, misma placa despertador).
5. Solo cuando esa superficie esté estabilizada con 2-3 verdes
   consecutivos → considerar escalada de complejidad.

**Criterio operacional de convergencia (Fase 3):**
- ≥2-3 dogfoodings consecutivos verdes (nota ≥9) sobre misma placa.
- P1 conocido resuelto.
- Generalización D-23.2 completada y ratificada.
- Sin P0 nuevos en la superficie ratificada.
- Estabilidad sostenida.

Solo con esas condiciones se puede pensar en Fase 4 (release / nuevas
capabilities / escenarios más complejos).

**Interpretación de resultados en Fase 3:**
- **Verde (nota ≥9, 0 P0/P1 nuevos):** evidencia positiva. Avanzar
  a siguiente paso de la secuencia.
- **Amarillo (nota 8-8.9, 1-2 P1):** ciclo continúa, sesión de fix +
  próximo dogfooding.
- **Rojo (V3 activada, P0 nuevo, nota <8):** señal fuerte de que
  algo no cerró como pensábamos. Investigación mandatoria antes de
  continuar. Cualquier P0 nuevo en Fase 3 se trata como potencial
  regresión del último fix mergeado hasta que se pruebe lo
  contrario.

---

## Cronología condensada

| Sesión | Contenido | Cierre |
|---|---|---|
| 1–14 | Bootstrap, D1, TOON, tools PCB v1, Freerouting | Ver v1-v4 |
| 15 | **Dogfooding 2**: despertador ATtiny85, 24 fp | **7.5/10** |
| 16 | P1: `get_tracks` + `delete_track(id=)` + `add_track` mixed | Merge |
| 16b | Fix tests integration_gui + bug `get_copper_by_kiid` | Merge |
| 17 | P2.0 + P2.1 (reglas DSN) + P2.2 (route_board JSON) + P2.5 + fixture | Merge |
| 18 | P3: `Board.revert()` — D-V3.1 cerrado | Merge |
| 19 | P4: 5 tools de zonas | Merge |
| 19c | Investigación bloqueantes pre-D3 (4 bloques) | Merge |
| 19d | NET_ASSIGNMENT_MISMATCH + delete_tracks_bulk + test P4.5 | Merge |
| 19b | Corrección sch del despertador | Merge |
| 19e | Fix socket path (F-19b-09) | Merge |
| **20** | **Dogfooding 3**: sch corregido, plano GND | **8.5/10** |
| 21 | Fix P0 (F-D3-03) + mitigación P0 (F-D3-01) + P1 (`get_footprint_neighbors`) | Merge |
| **22** | **Dogfooding 4**: variable controlada | **4.5/10, V3 activada** |
| 23 | Investigación P4.0 F-D4-02: causa raíz = orden de medición + persistencia | Merge (solo docs) |
| **24** | **Fix Opción X**: reordenar medición + persistir + `POST_ROUTE_PERSIST_FAILED` + test regresión gate | **Merge 972fa80** |
| **25** | **Siguiente**: **Dogfooding 5** con baseline dinámico + V1/V2/V3 reforzadas | — |
| 26 | Fix solder mask bridge ANT1 (P1) | — |
| 27 | Generalización D-23.2 a `fill_zones` / `add_zone(fill=True)` — si D5 confirma | — |
| 28 | Dogfooding 6, ratifica todo el bloque | — |
| ... | Escalada solo tras 2-3 verdes consecutivos | — |

---

## Decisiones de arquitectura vigentes

Las modificadas o revocadas por evidencia lo dicen explícito.

### Nuevas de sesión 24

**D-24.1 (patrón operacional para fixtures con coordenadas):**
preferir helpers que deriven bboxes en runtime desde el estado real
del board (`bridge.list_zones()`, `get_world_context()`, etc.) sobre
directorios estáticos con coordenadas hardcodeadas. Sesión 24
descubrió que `/tmp/gui-test-project` tiene el board en origen
absoluto distinto del fixture crudo (mismo tamaño 44×44mm, desplazado
(150,28) → (100,50)) — hardcodear hubiera generado tests flakey a
mediano plazo. El agente lo detectó al implementar el fixture del
test de regresión y resolvió con helper runtime.

**D-24.2 (técnica de baseline dinámico):** para verificar que un
cambio no introduce errores nuevos en placas con errores DRC
preexistentes (ej. courtyards, edge clearance del outline), preferir
"baseline dinámico + delta" sobre "allowlist estática escrita a
mano". Metodología: `run_drc()` inicial → registrar `por_tipo` +
lista de violaciones individuales → mediciones posteriores comparan
solo los deltas contra ese baseline. Ventaja: robusto ante drift del
fixture. Convertir en allowlist estática solo cuando N corridas
consecutivas ratifican estabilidad del residual. Aplicar en D5 para
los ~5 errores residuales que quedan post-route en placa despertador.

### Reformuladas por sesión 23 (siguen vigentes en v7)

**D-D3.2 v6** — La coincidencia `route_board.drc.err_post =
run_drc()` no ratifica fidelidad al vivo por sí sola, solo
consistencia de lectura de disco. **Post-sesión 24** el contrato
D-23.2 refuerza esto al garantizar disco == memoria == err_post en
`route_board`, pero D-D3.2 sigue siendo advertencia útil para futuras
tools que no adopten el patrón todavía (ej. `fill_zones`,
`add_zone(fill=True)`).

**D-17.1 v6** — `route_board` con contrato JSON fiel. Post-sesión 24
el matiz de v6 queda superado en `route_board`: el JSON refleja el
estado real persistido. En las otras tools sigue vigente el matiz de
v6 hasta que se generalice el patrón (paso 3 de la secuencia Fase 3).

**D-19.1 v6** — Freerouting respeta `(plane)` como conectividad para
el net dueño, NO como exclusión para otros nets. Sin cambios en v7,
documentado en ADR-0012 al lado del contrato D-23.2 (contexto de por
qué el refill+enforce es imprescindible).

### De sesión 23 (siguen vigentes)

**D-23.1** — Causa raíz F-D4-02 confirmada empíricamente: bug de
orden de medición + falta de persistencia. **CERRADO por sesión 24.**

**D-23.2 (implementada en sesión 24)** — Contrato reforzado de
`route_board`: cuando termina OK, disco == memoria == `err_post`. Se
implementa reordenando `post_report` para medirse DESPUÉS del bloque
refill+enforce, y agregando `save_board()` incondicional al final de
ese bloque (dentro del branch `if refill and zones_existentes>0 and
reloaded is True`). Fallo del save → `POST_ROUTE_PERSIST_FAILED`
explícito, board vivo se preserva TAL CUAL (no forzar reload).
**Documentado en `docs/adr/0012-route-board-persist-contract.md`.**

**D-23.3 (deuda técnica separada)** — Loop de vías de
`enforce_hole_clearance` (líneas 1996-2032 de `ipc.py`) posiblemente
código muerto — nunca creó keepout `via_*` en 3 corridas de sesión
23. NO se toca en Fase 3 salvo que aparezca evidencia de que
importa. Investigación independiente cuando corresponda. Riesgo R16
abierto.

### Ratificadas por evidencia (sin cambios estructurales)

- **D-V3.1** (revoca D-R2/D-14.1): revert humano post-route
  eliminado. `Board.revert()` funciona nativo. D-12.4 corregida:
  `revert()` imposible en Schematic Editor pero funciona en PCB.
- **D-V3.2**: TOON no crece; `get_tracks` es la vista de cobre.
- **D-V3.3**: KIID reemplaza desambiguación por radio.
- **D-V3.4**: `route_board` con contrato JSON. Reforzado por D-23.2.
- **D-V3.5**: reglas del board viajan al DSN. Edge clearance vía
  ingeniería inversa de bytecode.
- **D-V3.6 + extensiones acumuladas** (proceso, vinculante).
- **D-D3.1**: margen conectores densos ≥1.5-2mm. Ratificado en D4.
- **D-D4.1**: uso amplio de `get_footprint_neighbors`. Ratificado.
- **D-19c.1, D-19c.2, D-19d.1, D-19b.1, D-19b.2, D-19e.1, D-19e.2**
  sin cambios.

### Vigentes desde v3-v4

D-08, D-09.1, D-12.3, D-14.1, D-14.2 (con excepciones D-17.1 v6,
D-19.x). D-R3, D-R8. D-16.1 (KIID), D-16.2 (endpoints mixed), D-16.3
(SDF collision). D-17.2 (causa mínima honesta).

---

## Tools productivas (inventario con estado bugs post-sesión 24)

### Lectura de mundo
- `health()` — 19e cascada dinámica de socket.
- `get_world_context(kind, focus, budget)` — kind="sch" no soporta
  `#PWR*/#FLG*` (R13, ratificado en D4). Workaround `export_netlist()`.
- `get_component_detail(ref)` — estrella del D3, ratificado en D4.
- `get_tracks(net=|bbox=|layer=, max_tokens=)` — con KIIDs.
- `get_zones(layer=|net=|max_tokens=)` — con KIIDs.
- `get_footprint_neighbors(ref, radius_mm=, ...)` — P1 sesión 21,
  ratificado en D4. Default recomendado `max_tokens=3000`.
- `run_erc()` — F-03 (÷100 posiciones) sigue abierta.

### Escritura de esquemático — LIMITACIÓN R12
Tools puramente aditivas. NO CRUD. Diferido a P3.

### Escritura de PCB
- `draw_board_outline` — F-06 inmutable.
- `move_footprint` — sin rotación.
- `add_track`, `add_via` — verificación post-creación (19d), bridges
  devuelven KIID.
- `delete_track(id=|coords)`, `delete_via(id=|coords)`,
  `delete_tracks_bulk(net=|bbox=|layer=, include_vias, dry_run)`.
- `save_board` — guard mtime.
- `add_zone(net, layer, bbox=|polygon=, fill=true)` — dispara
  `enforce_hole_clearance` correctamente para puntos fijos
  preexistentes. **Nota post-sesión 24**: sufre el mismo patrón de
  "no persiste el refill" identificado en `route_board`. Pendiente
  generalización D-23.2 (paso 3 de secuencia Fase 3).
- `add_keepout_zone` — no ejercitado en D4.
- `fill_zones(zone_id=)` — mismo patrón que `add_zone`. Idem
  generalización.
- `route_board(timeout_s=)` — **contrato D-23.2 implementado
  (sesión 24, ADR-0012).** Cuando termina OK: disco == memoria ==
  `err_post`. Fallo del save → `POST_ROUTE_PERSIST_FAILED` visible.
  Test de regresión `test_pcb_session24_route_board_persist_gui.py`
  gate del merge, 2/2 corridas verdes en vivo.
- `reload_board_from_disk()`.

### Validación y export
- `run_drc(min_severity=)` — mide sobre disco vía kicad-cli.
- `export_render`, `export_manufacturing` (G3), `export_bom`.

### Códigos de error (F3 respetada, F1 excepción sancionada por DoD sesión 24)
- Base: `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `KICAD_CLI_FAILED`,
  `CONTEXT_BUDGET_IMPOSSIBLE`, `PATH_OUTSIDE_PROJECT`, `KICAD_NOT_RUNNING`,
  `KICAD_TIMEOUT`, `KICAD_RESTARTED`, `INVALID_PARAMS`, `NET_NOT_FOUND`.
- 16: `TRACK_ID_STALE`.
- 17: `ROUTE_NET_BLOCKED`.
- 18: `RELOAD_FAILED`.
- 19: `INVALID_ZONE_GEOMETRY`, `ZONE_ID_STALE`.
- 19d: `NET_ASSIGNMENT_MISMATCH`.
- **24: `POST_ROUTE_PERSIST_FAILED`** (contrato D-23.2 no cumplible).

---

## Fronteras inviolables (F1–F5)

Sin cambios estructurales. Nota: F1 (no modificar contratos existentes
de tools) tuvo excepción sancionada en sesión 24 (adición pura
`POST_ROUTE_PERSIST_FAILED` al `StrEnum ErrorCode`, no renombra nada,
F3 intacta). Excepciones futuras del mismo tipo son admisibles si
respetan el mismo estándar (adición sin renombrar).

---

## Fixtures y proyectos de prueba

- `/tmp/gui-test-project/` — STALE por defecto. Restaurar antes de
  cada sesión GUI.
- `tests/fixtures/despertador-routed/` — regenerado en D3. Sigue
  siendo baseline válido. **NO se actualizó en D4, sesión 23, ni
  sesión 24**. Sigue viviendo en origen absoluto (150,28)-(194,72)
  vs `/tmp/gui-test-project` (100,50)-(144,94) — D-24.1 explica por
  qué esto no fue problema.
- **Patrón helper runtime (D-24.1)**: para tests que requieren
  coordenadas del board (bbox de zonas, posiciones de footprints),
  derivar en runtime desde `bridge.list_zones()` /
  `get_world_context()` en el propio helper del test. Ejemplo vivo:
  `tests/test_pcb_session24_route_board_persist_gui.py`.
- `tests/fixtures/004_real/` — proyecto `video`, sin cambios.

**Path del humano:** `/home/astra/Desktop/agent_proyect/kicad-mcp`
(repo), `/home/astra/Desktop/Electronig_Proyects/despertador_inteligente/`
(proyecto físico).

**Env vars del server MCP en `~/.claude.json`**:
`.projects["/home/astra/Desktop/agent_proyect/kicad-mcp"].mcpServers["kicad-mcp"].env`.

Cambio de env → `/mcp reconnect` en Claude Code.

---

## Riesgos abiertos (post-sesión 24)

| # | Riesgo | Estado |
|---|---|---|
| R1 | Freerouting > 24 componentes | Sin evidencia. No prioritario en Fase 3 |
| R2 | Tracks danglings | Sin evidencia |
| R3 | `confirm_reloaded` | Superado por D-V3.1 |
| R4 | pcbnew SWIG | Sin cambios |
| R6, R7 | kicad-skip, clone cross-file | Sin cambios |
| R8 | Mismatch brief/proyecto | Cerrado por D-V3.6 |
| R9 | Freerouting `gui.enabled=true` | Mitigado en 17 |
| R10 | Discrepancia DRC tras `save_board` GUI | Sin evidencia nueva |
| R11 | Crash de KiCad bajo mutaciones rápidas | No re-ejercitado |
| R12 | Tools de sch aditivas | No ejercitado en D3/D4/24 |
| R13 | `get_world_context(kind="sch")` con `#PWR*/#FLG*` | Ratificado en D4 (F-D4-01), pendiente |
| R14 | `fill_zones` no respeta hole clearance PTH/NPTH | **Cerrado en `route_board`** post-sesión 24. Residual abierto en `fill_zones` / `add_zone(fill=True)` hasta generalización D-23.2 (paso 3 de secuencia Fase 3) |
| R15 | `route_board.drc.err_introducidos` falso | **Cerrado técnicamente** por sesión 24 (test regresión en vivo 2/2). Ratificación final pendiente en D5 |
| R16 | Loop de vías de `enforce_hole_clearance` posiblemente código muerto | D-23.3, deuda técnica. NO tocar en Fase 3 salvo evidencia nueva |

---

## Hallazgos técnicos críticos (v3-v4-D4-sesión 23 + sesión 24)

Manteniendo 29 items previos + agregando lo de sesión 24:

### 30. Determinismo estructural del fix Opción X confirmado (sesión 24)

Test de regresión 2/2 corridas contra Freerouting real: `tracks_added`
difirió entre corridas (224 vs 263) y `vias_added` también (28 vs 29),
pero `err_post` fue idéntico en ambas (5 errores, mismo `por_tipo`).
Esto confirma que el fix es estructural — no depende de la geometría
específica del ruteo. La eliminación del patrón "net ajeno vs Zone
GND" es robusta a la no-determinación de Freerouting. Contraste con
D4: donde antes había 16 `hole_clearance` + 30 `clearance`-vs-GND
espurios reportados en el JSON, ahora hay 0 y 0 respectivamente.

### 31. Snapshot mtime + `live_stale` como dependencia oculta del reorden (sesión 24)

Hallazgo del Bloque 1 que no anticipé en el prompt: `store.register()`
mantenía mtimes de disco **pre-save**, por lo que el propio guardado
de `route_board` disparaba `EXTERNAL_EDIT_DETECTED` espurio en la
siguiente lectura. El agente detectó la dependencia moviendo el
registro para usar mtimes frescos post-save, y difiriendo también
`mark/clear_live_stale`. Este es el tipo de dependencia entre pasos
que la exploración del Bloque 1 estaba diseñada para forzar a
descubrir — funcionó según diseño. Aprendizaje reforzado para futuros
prompts de fix quirúrgico: mantener el Bloque 1 de diseño obligatorio
aunque el cambio parezca "3 líneas".

### 32. Patrón "fixture helper runtime" superior a directorio estático (sesión 24)

D-24.1 documenta esto. La copia de trabajo real vs el fixture crudo
tenían origen absoluto distinto (mismo tamaño). El bbox del
`delete_tracks_bulk` derivado en runtime de `bridge.list_zones()` +
margen 5mm es robusto a este drift. Convención vigente para
próximas sesiones de test de regresión.

### 33. Baseline dinámico + delta como técnica de verificación (sesión 24 → D5)

D-24.2 documenta la técnica. En placas con errores DRC preexistentes
(courtyards, edge clearance del outline, etc.), la comparación
"total antes vs total después" es engañosa. La técnica correcta:
enumerar `por_tipo` inicial + violaciones individuales, y tratar solo
los deltas como hallazgos nuevos. Solo cuando el residual es estable
en N corridas consecutivas, convertir a allowlist documentada. D5
va a usar esta técnica por primera vez sobre placa despertador para
los ~5 errores residuales que quedan post-route.

---

## Reglas operacionales para sesiones GUI

Sin cambios respecto a v6 (restauración proyecto, KiCad limpio, env
vars, editar código, socket, backups G1).

### D-D3.1 vigente — margen conectores densos ≥1.5-2mm.
### D-D3.2 v6 — cross-check ya no interesante como verificación en `route_board` post-sesión 24 (trivialmente cierto).
### D-D4.1 — uso amplio de `get_footprint_neighbors`.
### D-24.1 — helper runtime sobre fixture estático cuando hay coords.
### D-24.2 — baseline dinámico + delta sobre allowlist estática.

---

## Métricas comparativas D1/D2/D3/D4

| Métrica | D1 | D2 | D3 | D4 |
|---|---|---|---|---|
| Nota | 5/10 | 7.5/10 | 8.5/10 | 4.5/10 |
| Duración | ~2h | ~2.5h | ~2h | ~50-60min (parada) |
| Contactos humanos | 5+ | 5 | 2 | 0 |
| Reverts humanos | 3 | 3 | 0 | 0 |
| Fricciones bloqueantes | 3 | 0-1 | 1 externa | 1 P0 interna |
| `route_ms` | N/A | 925s | 53s | 36.7s |
| Errores DRC introducidos (reportados) | ? | 53 (enmascarados) | 0 | 42 (obsoletos, D-23.1) |

D5 va a agregar una fila. Objetivo Fase 3: nota ≥9.

### Fricciones del D4 (estado post-sesión 24)

| F-NN | Descripción | Estado |
|---|---|---|
| F-D4-01 | `get_world_context(kind="sch")` con `#PWR*/#FLG*` (R13) | P3, pendiente |
| F-D4-02 | Bug de orden de medición + persistencia en `route_board` | **Cerrado en sesión 24, ratificación final pendiente D5** |
| courtyards_overlap × 2 | Proceso del brief D4 (D-V3.6) | Cerrado por D-D4.1 |
| solder_mask_bridge en ANT1 | Pad no protegido por hole keepout | **P1 vigente, próximo objetivo de sesión de fix post-D5** |
| 23 vs 24 footprints | Discrepancia menor probable artefacto de 19b | Nota |

---

## Deuda del arquitecto (mantener visible)

Sin cambios estructurales respecto a v6, más la reflexión de v7:

1. **Riesgo 8** cerrado por D-V3.6 (ocurrió 3 veces).
2. **Sch del despertador** (5 defectos corregidos en 19b, 3
   subestimaciones mías del diseño).
3. **Deuda física del proyecto real** (fuera de scope kicad-mcp):
   ICSP en circuito perdido, VLED+ flotante, INT eliminado.
4. Regla arquitectónica reforzada: antes de aceptar "X escala mal" o
   "X no funciona", exigir prueba de X aislado.
5. De D4: consejos operacionales inclusivos por defecto.
6. De sesión 23: al formular hipótesis, incluir marco "el reporte
   puede engañar".
7. **De sesión 24 (nueva):** criterio ADR-vs-docstring debe ser por
   naturaleza (contrato arquitectónico) no por longitud. Corregí un
   umbral cuantitativo mío que hubiera invitado a exprimir
   docstrings para evitar ADR. Regla aplicada en el prompt sesión 24
   y de acá en más.
8. **De transición Fase 2 → Fase 3 (nueva):** el arquitecto tiene
   que resistir la tentación de "hacer que cada sesión valga la
   pena" mediante hallazgos forzados o escaladas prematuras.
   Convergencia estadística es evidencia positiva incluso cuando se
   siente aburrida. Contar el aburrimiento como señal, no como
   problema.

---

## Backlog priorizado v7

Reorganización post-sesión 24, refleja secuencia estricta de Fase 3.

### P0 (bloqueante para calidad de referencia)

**Vacío.** F-D4-02 sale del P0 tras sesión 24. Reabrir solo si D5
lo ratifica como regresión.

### P1 (mejora crítica no bloqueante — prioridad Fase 3 paso 2)

1. **Solder mask bridge en ANT1**: pad de ANT1 hace bridge con zona
   GND. El fix de 21.1 protege el hole, no el pad. Investigar si
   necesita keepout de máscara separado. Próxima sesión de fix
   después de D5, salvo que D5 abra algo más urgente.

### P2 (Fase 3 paso 3 — generalización)

2. **Generalización D-23.2 a `fill_zones` y `add_zone(fill=True)`**:
   aplicar el mismo patrón de reordenamiento + persistencia
   confirmado en `route_board`. Sesión dedicada. Condicionado a que
   D5 ratifique el patrón. Segundo objetivo tras el P1 solder mask.

### P2 (release polish — diferido hasta convergencia Fase 3)

3. ADR-0013 en adelante: mecanismo indocumentado edge clearance
   Freerouting.
4. Docs de arquitectura para colaboradores externos.
5. Test canario Freerouting edge clearance.
6. Issue upstream Freerouting sobre R9.
7. Licencia + README + CONTRIBUTING.
8. Limpieza código muerto sesiones intermedias.
9. Doc política de locking del bridge (constraint no-reentrante).

### P3 (calidad durante ciclo)

10. **CRUD de sch (R12)**: sesión dedicada. Habilita autocorrección
    sch.
11. F-03 D2 / F-19b-12: `run_erc` posiciones ÷100.
12. F-19b-10: `get_pin_net_membership`.
13. F-19b-06 / D-19e.2 / F-D4-01: `#PWR/#FLG` filter (R13).
14. F-D3-05: `delete_track` cosmético.
15. A* de bloqueador concreto (17b).
16. `route_ms` en ruta de fallo (17b).
17. Documentar `__kicadmcp_hc__*` como convención.
18. Default `max_tokens` en `get_footprint_neighbors` a 1500-2000.
19. Discrepancia 23 vs 24 footprints (nota D4).
20. **Investigación del loop de vías de `enforce_hole_clearance`
    (D-23.3, R16)**: por qué nunca creó keepouts `via_*` en las 3
    corridas de sesión 23. Independiente. NO tocar en Fase 3 salvo
    evidencia nueva.

### P4 (nice-to-have — post-convergencia Fase 3, para Fase 4)

21. Rotación en `move_footprint`.
22. Timeout adaptativo.
23. P2.3: limpieza tracks huérfanos.
24. Guard cross-proceso (17b).
25. `add_zone` con hueco interior.
26. Opción Y de F-D4-02 (inyectar keepout real al DSN). Descartada
    por ahora. Solo si aparece intermitencia real futura.

---

## Ciclo de consolidación (Fase 3)

Reemplaza al "Ciclo de hardening" de v6, refleja la nueva disposición.

**Ritmo esperado en Fase 3:**
```
[Dogfooding ratificación] → [Sesión de fix pequeña si corresponde] →
[Nuevo dogfooding] → [Repetir hasta 2-3 verdes consecutivos]
```

**Secuencia acordada:**
1. Sesión 25 = **D5** con placa despertador. Baseline dinámico +
   V1/V2/V3 reforzada.
2. Sesión 26 = **fix P1** (solder mask bridge ANT1) + test de
   regresión.
3. Sesión 27 = **generalización D-23.2** a `fill_zones` +
   `add_zone(fill=True)` + tests.
4. Sesión 28 = **D6** con placa despertador. Ratifica todo el bloque.
5. Si D6 verde → considerar D7 o iniciar preparación Fase 4.
6. Si D6 abre P0 → tratar como potencial regresión de sesión 27,
   investigación inmediata.

**Reglas del ciclo Fase 3:**
1. Cada bug nuevo → registrar F-DN-XX.
2. Un P0 nuevo en Fase 3 se sospecha regresión hasta que se pruebe
   lo contrario (interpretación distinta de Fase 2, donde se
   sospechaba gap nuevo).
3. P1 conocido → fix quirúrgico + test + próximo dogfooding.
4. Generalizaciones → sesión dedicada + tests + próximo dogfooding.
5. NO regresiones: cada fix trae test de regresión.
6. Cada dogfooding actualiza el fixture cuando corresponde.
7. **NO escalar complejidad hasta 2-3 verdes consecutivos.**

---

## Preparación específica para sesión 25 (Dogfooding 5)

**Ver `PROMPT-SESION-25.md` (documento hermano).**

Precondiciones:
1. `master` con sesión 24 mergeada (972fa80).
2. `/tmp/gui-test-project/` restaurado desde fixture
   `despertador-routed` del D3.
3. KiCad reiniciado limpio.
4. Env vars completas en `~/.claude.json`.
5. **NO editar el repo de kicad-mcp** — mismas prohibiciones que
   D2/D3/D4.

**Objetivo:** nota ≥9. D3=8.5, D4=4.5, D5 esperado ≥9 con contrato
D-23.2 aguantando en producción.

**Estructura tentativa** (detalle en el prompt):
- Fase 1 con **baseline dinámico** (`run_drc()` inicial completo
  registrado).
- V1/V2/V3 reforzadas: V2 ahora ratifica fidelidad al vivo (no solo
  al disco), V3 es más severo si aparece (potencial regresión de
  sesión 24).
- Verificación específica de contrato D-23.2: mtime cambia
  post-route, no aparece `EXTERNAL_EDIT_DETECTED` espurio.
- Delta vs baseline como criterio de "hallazgo nuevo".

**Fuera de alcance:**
- Solder mask bridge ANT1 (P1, próxima sesión).
- Generalización a `fill_zones`/`add_zone` (post-D5).
- Cualquier feature nuevo.
- Escalada de complejidad.

---

## Instrucciones de handoff (para un nuevo chat)

Pegá este documento como primer mensaje con este preámbulo:

> Sos el arquitecto de software senior y revisor técnico crítico del
> proyecto kicad-mcp. El CONTEXT.md v7 adjunto contiene el estado
> completo tras 26 sesiones. No vas a ver la conversación anterior
> — ese archivo ES la conversación destilada.
>
> Reglas de operación:
> 1. Respetá decisiones del CONTEXT o cuestionalas con evidencia
>    nueva.
> 2. Mantené el nivel de profundidad técnica.
> 3. Nueva evidencia > decisiones previas cuando hay contradicción.
> 4. Tu rol es arquitectura, no código. Generás prompts de sesión.
> 5. Conservá la cronología: algunas decisiones fueron
>    revocadas/ampliadas.
>
> Estilo con Astra: directo, técnico, sin adornos. No preámbulos, no
> felicitaciones. Estructura de respuesta: veredicto claro +
> análisis técnico + próximo paso. Los consejos operacionales que
> generes deben ser inclusivos por defecto, no restrictivos.
>
> **Estado crítico al arrancar:** proyecto entra en Fase 3
> (consolidación / aumento progresivo de confianza). F-D4-02
> cerrado técnicamente en sesión 24 con test de regresión en vivo
> 2/2. Secuencia estricta Fase 3: D5 ratificación → fix P1 (solder
> mask ANT1) → generalización D-23.2 a `fill_zones`/`add_zone` →
> D6 ratificación. Solo tras 2-3 verdes consecutivos considerar
> escalada de complejidad. Interpretación de resultados invertida
> respecto a Fase 2: un verde es evidencia positiva, no
> aburrimiento; un P0 nuevo se sospecha regresión hasta prueba en
> contrario. NO forzar hallazgos ni escalar prematuramente.
