# Sesión 34a — Auditoría sistemática de contratos de escritura del bridge

**Rama:** `sesion/34a-auditoria-contratos-bridge` (desde `master` — el
rename `master`→`main` que el prompt asumía no está hecho; corregido con
el arquitecto vía `AskUserQuestion` al inicio, queda como operación suya
post-sesión). Secuencia 32b→32c→32d→33 ya estaba en `master`
(`fb00a73`…`0907bfd`).
**Tipo:** investigación pura (auditoría, D-30.1/D-33.1), cumple el
compromiso formal del arquitecto post-sesión 32b.

## Resumen ejecutivo

Auditoría completa de las 19 tools de escritura del bridge (20 filas de
matriz — `add_zone` dual-mode `fill=True`/`fill=False`) contra los 4 ejes
del contrato acordados con el arquitecto (persistencia, propagación de
errores, sincronización disco↔memoria, manejo de reload). Documento
principal nuevo: `docs/analisis/auditoria-contratos-bridge.md`.

**3 correcciones de precondición** resueltas con el arquitecto antes de
arrancar (`AskUserQuestion`): rama base sin rename (`master`, no `main`),
alcance del Bloque 2 acotado a harness sintético + código (sin bajar
HackRF One a propósito), inventario tratado como "real completo" en vez
de sólo la lista de prioridad 1-4 del prompt.

**Bloque 0 refutó el inventario preliminar del prompt en 3 puntos** (tal
como D-33.1 exigía verificarlo, no asumirlo): `delete_footprint` no
existe como tool — ADR-0013 registra que fue explícitamente rechazada, el
caso real se resolvió con `set_footprint_ref` (anotación, no borrado);
`clone_symbols` tampoco es una tool registrada, sólo una mención informal
en `BACKLOG.md`; el listado omitía `add_keepout_zone`, `delete_zone`,
`save_board` y `reload_board_from_disk`.

**3 asimetrías reales confirmadas** (severidad P1/P2), 1 asimetría nueva
descubierta y fixeada in-situ, F-V3-ZONE-FILL-CRASH clasificada como no
concluyente, y D-34a.1 formaliza los 4 ejes como convención permanente.
0 rediseños arquitectónicos — ADR-0012 se ratifica correcto en su alcance
declarado.

## Correcciones de precondición (resueltas con `AskUserQuestion`)

1. **Rename `master`→`main` no hecho.** Verificado con `git branch -a`:
   no existe `main` ni local ni en `origin`. Decisión: rama desde
   `master`, sin rename — queda como operación directa del arquitecto
   antes de sesión 34b.
2. **Bloque 2 (F-V3-ZONE-FILL-CRASH):** harness sintético + análisis de
   código, explícitamente para NO tener que reabrir HackRF One (el board
   que ya crasheó 3/3 veces en sesión 33).
3. **Alcance del inventario:** auditar la superficie real completa (17→19
   tools reales tras la refutación de Bloque 0), no sólo la lista de
   prioridad 1-4 del prompt original.

## Bloque 0 — Inventario (ver §0 del documento principal)

Inspección directa de `src/kicad_mcp/tools/*.py` (31 ocurrencias de
`@mcp.tool`). Taxonomía: **W-IPC** (10 tools, mutación IPC sin save
propio), **W-COMPOSITE** (3: `route_board`, `fill_zones`,
`add_zone(fill=True)`, contrato D-23.2/ADR-0012), **W-SKIP** (4 tools de
esquemático, escritura directa vía `kicad-skip`, arquitectura distinta
por D-08.5), **infra** (`save_board`, `reload_board_from_disk`).

## Bloque 1 — Auditoría por tool (ver §3 del documento principal)

Las 19 tools completadas (no hubo timebox parcial — el checkpoint de 90
min encontró los grupos prioritarios 1-3 ya cerrados). Hallazgo relevante
por encima de lo hipotetizado en el prompt de la sesión:

- **A1 (`delete_tracks_bulk`, ya observada en 32b, confirmada P1
  esta sesión):** refilla zonas sin `enforce_hole_clearance()` ni
  `save_board()` — viola directamente el docstring de
  `enforce_hole_clearance` ("llamar SIEMPRE inmediatamente después de
  `refill_zones()`"). El test existente
  (`test_delete_tracks_bulk_refills_zones_when_copper_zone_present`) sólo
  verifica `zones_refilled == 1`, sin ninguna assertion de persistencia —
  documenta el comportamiento actual, no lo objeta.
- **A2 (`delete_zone`) y A3 (`add_keepout_zone`), nuevas:** ninguna
  recalcula fills vecinos tras mutar geometría de zonas/keepouts. Sin
  precedente empírico de impacto (a diferencia de A1) — documentadas
  como limitación, no fixeadas (D-30.1/D-32c.1: investigar antes de
  fixear).
- **A7 (`draw_board_outline`), nueva y la más severa por ausencia total
  de protección:** única tool W-IPC de PCB sin `_guard_live_stale()`
  (D-14.1) ni `check_no_external_disk_edit()` (P3.2) — verificado por
  lectura línea por línea del cuerpo completo, confirmado con `grep`
  vacío sobre el rango de la función. Mutaba el vivo aunque el disco
  tuviera un ruteo pendiente de recarga.
- **A5 refutada explícitamente:** confirmado por lectura directa que
  `fill_zones`/`add_zone` no tienen el camino silencioso de
  `route_board` (ADR-0012 §"Extensión F-V2" ya lo documentaba desde
  32b; esta auditoría lo re-verificó contra el código actual, no lo dio
  por sentado).
- **6 de las 11 W-IPC** caen en "cumple con matiz — por diseño" en Eje 1
  (D-14.3: nunca persisten, el llamador orquesta `save_board()`) — no son
  asimetrías, pero ninguna lo declara explícitamente en su respuesta
  (A6, input para CONTRIBUTING/README).

## Bloque 2 — F-V3-ZONE-FILL-CRASH: no concluyente

Al llegar al bloque, `health()` + inspección de `/proc/<pid>/environ` del
servidor MCP mostraron que el PCB Editor vivo tenía abierto exactamente
`validation-suite/level-c/hackrf-one/working` — el board que ya crasheó
3/3 veces en sesión 33 — porque `KICAD_MCP_PROJECT` quedó fijado a esa
ruta desde entonces. La superficie de tools no incluye ningún mecanismo
para abrir un proyecto distinto en el editor vivo
(`reload_board_from_disk` re-lee el mismo archivo, no cambia de
proyecto). Ejecutar el harness ahí habría significado asumir exactamente
el riesgo que la decisión "harness sintético, sin bajar HackRF One" (ver
§Correcciones) fue elegida para evitar — se optó por no hacerlo sin
consulta, en vez de forzarlo.

**Se ejecutó el análisis de código** (completo): el pipeline de
`add_zone(fill=true)` es estructuralmente el mismo que `fill_zones`
(refill interno del bridge → `enforce_hole_clearance` → `save_board`),
sin causa identificable del lado del bridge — ninguna de las dos tiene
crashes reportados. **No se ejecutó la reproducción empírica** por el
motivo de arriba. Clasificación: **no concluyente**, con nota honesta en
`docs/BACKLOG.md` de que "no funciona" acá significa "no se pudo ejecutar
sin asumir el riesgo evitado deliberadamente", no "se ejecutó y no
reprodujo". Detalle completo en el documento principal §4.

## Bloque 3 — Fix trivial aplicado: A7 (`draw_board_outline`)

**Se re-evaluó a mitad de sesión** la suposición inicial (registrada
provisoriamente en el documento principal) de que A7 requería
verificación GUI y por tanto quedaba fuera del Bloque 3. Al confirmar que
el patrón de rechazo del guard `_guard_live_stale()`/
`check_no_external_disk_edit()` **ya está testeado offline en el repo**
(`get_default_store().mark_live_stale(1)` directo sobre el store,
`tests/test_reload_board.py:103`; edición externa simulada con
`os.utime`, `tests/test_pcb_session11.py:341-374`), la suposición se
corrigió: el fix SÍ calificaba bajo los 5 criterios estrictos del Bloque
3.

**Fix:** `src/kicad_mcp/tools/pcb.py::draw_board_outline` — 2 líneas de
guard (mismo patrón que sus 9 pares W-IPC) + comentario de atribución (9
líneas efectivas totales).

**Tests:** 2 tests nuevos en `tests/test_pcb.py`
(`test_draw_board_outline_rejects_when_live_stale`,
`test_draw_board_outline_rejects_external_disk_edit`), replicando
exactamente los patrones offline ya usados para `reload_board_from_disk`
y `save_board` — sin fixtures nuevas.

**Verificación:** 5/5 tests de `draw_board_outline` en `test_pcb.py`
(3 preexistentes + 2 nuevas) pasan; suite offline completa **394 passed,
39 skipped, 0 failed**; `ruff check` limpio; `mypy src/` limpio (33
archivos). Diff total: 9 líneas en `pcb.py` + 67 líneas en `test_pcb.py`
(76 líneas, bien por debajo del precedente de 32b de <100 líneas
efectivas).

**No ejecutado, con motivo documentado:** el test `integration_gui`
específico de la tool
(`test_draw_board_outline_tool_rejects_existing_outline_on_real_board`,
protocolo manual) no es gate del DoD para este cambio (no toca el
pipeline de zonas/keepouts/route) y el único KiCad vivo disponible tenía
abierto el board de HackRF One (mismo motivo que Bloque 2) — se evitó por
el mismo criterio de no experimentar contra ese proyecto sin necesidad.
Queda pendiente de ejecución humana antes del release.

**Ningún otro candidato calificó:** A1 (no trivial, toca pipeline de
zonas, requiere extensión de ADR-0012 + gate GUI), A2/A3 (documentadas,
sin evidencia empírica que justifique un fix ciego), un candidato P3
adicional descubierto en la ficha de `move_footprint` (falta
`check_no_external_disk_edit()`, misma familia que A7 pero severidad
menor) se dejó anotado en BACKLOG sin aplicar, por foco de tiempo en A7.

## Documentación actualizada

- **`docs/analisis/auditoria-contratos-bridge.md`** (nuevo, documento
  principal) — refutación del inventario, taxonomía, matriz completa de
  20 filas, 19 fichas por tool con refutación explícita D-33.1 por eje,
  clasificación de F-V3, síntesis de asimetrías por severidad, input
  consolidado para README/CONTRIBUTING (sesiones 34b/34c).
- **`docs/BACKLOG.md`:** `F-V3-ZONE-FILL-CRASH` actualizado con la
  clasificación no concluyente; nueva entrada P1 para la asimetría de
  `delete_tracks_bulk` (promovida desde "Higiene menor", con hipótesis
  completa de `34a-fix-1`); nuevas entradas P2/P3 para A2/A3 y el
  candidato de `move_footprint`.
- **`docs/DECISIONES.md`:** `D-34a.1` (los 4 ejes como convención
  permanente, con el aprendizaje metodológico de que resultaron
  suficientes sin refinamiento) y `D-34a.2` (síntesis de las 3
  asimetrías confirmadas + ratificación de que ADR-0012 sigue correcto
  en su alcance declarado).
- **`docs/CONTEXT.md`:** entrada 5 de "Estado de la secuencia de Fase 4"
  (cierre de 34a), D-34a.1/D-34a.2 en la lista de principios
  metodológicos vigentes, próxima sesión actualizada a 34b.

## Disciplina de alcance

Sin scope creep: no se rediseñó ADR-0012 (la auditoría lo ratifica, no lo
reabre); A1/A2/A3 quedaron documentadas o agendadas, no fixeadas a
ciegas; F-V3-ZONE-FILL-CRASH no se investigó exhaustivamente (sólo lo
mínimo para intentar clasificarla, gate del Bloque 2 aplicado tal cual
ante la reproducción bloqueada); no se tocó README/CONTRIBUTING/LICENSE
(sesiones 34b/34c). El único cambio de código (`draw_board_outline`)
pasó los 5 criterios estrictos del Bloque 3 y quedó documentado con el
mismo rigor que un fix de sesión propia.

## Gates

- `pytest -m "not integration"`: **394 passed, 39 skipped, 0 failed**.
- `ruff check`: limpio.
- `mypy src/`: **Success: no issues found in 33 source files**.
- Gate GUI del DoD: no aplica (el único cambio de código no toca el
  pipeline de zonas/keepouts/route — DoD #2). Test `integration_gui`
  específico de `draw_board_outline` queda pendiente de ejecución humana
  (ver §Bloque 3).

## Próxima sesión

**34b** — LICENSE (Apache 2.0) + README público inicial + CONTRIBUTING.md.
Arranca con el input consolidado de esta sesión (§6 del documento
principal): limitaciones conocidas para README, los 4 ejes con ejemplos
para CONTRIBUTING, checklist de los 4 ejes para "how to add a write tool".

**Sin bloqueantes pendientes para mergear a `master`** (rename a `main`
sigue siendo operación directa del arquitecto, no bloquea este merge).
