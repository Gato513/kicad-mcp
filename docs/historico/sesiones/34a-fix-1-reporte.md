# Sesión 34a-fix-1 — Fix: `delete_tracks_bulk` aplica el pipeline D-23.2

**Rama:** `sesion/34a-fix-1-delete-tracks-bulk-persist` (desde `master` @
`a42f45d`). **Tipo:** fix quirúrgico de la asimetría A1 confirmada en la
auditoría de sesión 34a (`docs/historico/sesiones/34a-reporte.md`).
**Primer ciclo ejecutado de punta a punta bajo el flujo híbrido
multiagente v2** (`docs/proceso/FLUJO-HIBRIDO-MULTIAGENTE-v2.md`):
propuesta → auditoría previa → ejecución continua de Claude Code →
revisión posterior única de Codex → retorno.

## Resumen ejecutivo

`delete_tracks_bulk` era la única tool mutante de zonas de cobre que
refilleaba sin aplicar `enforce_hole_clearance()` ni `save_board()`
posteriores — a diferencia de `route_board`, `fill_zones` y
`add_zone(fill=True)`, que sí aplican el pipeline D-23.2/ADR-0012. La
asimetría (A1) fue observada en sesión 32b, confirmada con severidad P1 en
la auditoría sistemática de sesión 34a y agendada como `34a-fix-1`.

Cerrada en esta sesión: cuando el borrado toca ≥1 zona de cobre,
`delete_tracks_bulk` ahora corre `refill_zones` → `enforce_hole_clearance`
→ `save_board`, con fallo de persistencia visible
(`POST_ZONE_PERSIST_FAILED`, auditado, `live_has_fix=True`) y mtimes
registrados post-save (mismo patrón que `add_zone`/`fill_zones`, sesión
27). Sin zona tocada, comportamiento sin cambios (`mtimes=None`, W-IPC).

**Revisión independiente de Codex: APROBAR, 0 hallazgos** (BLOCKER/MAJOR/
MINOR) — `OBJETIVO_CUMPLIDO`.

## Riesgo y control (R2)

Ciclo clasificado R2 por decisión del arquitecto (2026-08-12): controles
autorizados y suficientes — commit local único como unidad revisable,
gates mecánicos completos, gate GUI con oráculo determinista, verificación
de no-autolesión (`EXTERNAL_EDIT_DETECTED`) y revisión semántica
independiente de Codex. **No autorizaba** F1-F5, ADR-0012, roadmap,
BACKLOG, DECISIONES, publicación, push, PR ni merge durante la ejecución
del fix — esos quedaron reservados y se cierran en un commit `docs:`
separado, posterior a la aprobación de Codex, sin reabrir ni modificar el
commit de código ya revisado.

## Rama elegida: R-A (patrón inline)

El BACKLOG hipotetizaba reusar `_refill_enforce_and_save` (el helper que
ya usa `route_board`). Se descartó tras inspección: el helper está
acoplado a `route_board` (interpola `"route_board completó …"` en el
mensaje de error, levanta `POST_ROUTE_PERSIST_FAILED`, y sus dos únicos
call-sites son ambos de `route_board`). Los dos callers semánticamente
hermanos del caso nuevo — `add_zone`/`fill_zones` — ya son inline con
`POST_ZONE_PERSIST_FAILED`. Parametrizar el helper (rama R-B) no ofrecía
reutilización material y ampliaba el blast radius sin necesidad. Se eligió
**R-A**: bloque inline en `delete_tracks_bulk`, paralelo a
`add_zone`/`fill_zones`, sin tocar `route_board`, `add_zone`, `fill_zones`
ni `_refill_enforce_and_save`.

`enforce_hole_clearance` se confirmó aplicable (no se optó por R-C,
aborto): borrar vías elimina agujeros del board, y el método ya es
idempotente (limpia sus propios keepouts `__kicadmcp_hc__` de la pasada
previa antes de recalcular) — la pasada post-borrado limpia keepouts
huérfanos y protege el cobre re-expandido por el refill.

## Fix implementado

`src/kicad_mcp/tools/pcb.py::delete_tracks_bulk` (post early-return de
`dry_run` — la tool sigue excluida de `@mutating_tool`, ADR-0014, sin
cambio de ese layout):

1. Guard existente (`any(z.kind == "copper" for z in bridge.list_zones(board))`)
   nombrado (`touched_copper_zone`) — se consulta dos veces (persistencia
   + snapshot).
2. Con zona tocada: `refill_zones` → `enforce_hole_clearance(board,
   pcb_path)` → `try: save_board(board) except KicadMcpError`. En el
   except: `_audit_error(root, "delete_tracks_bulk", raw_params,
   POST_ZONE_PERSIST_FAILED)` + `raise KicadMcpError(...) from exc` con
   `code=POST_ZONE_PERSIST_FAILED`, mensaje que nombra la tool, hint
   accionable, `data={"pcb": ..., "live_has_fix": True}`.
3. Snapshot: con zona, `mtimes = collect_project_mtimes(...)`
   **post-save** (patrón `add_zone`, hallazgo #31 sesión 24 — mtimes
   pre-save harían que el propio `save_board()` dispare
   `EXTERNAL_EDIT_DETECTED` espurio en la siguiente lectura). Sin zona,
   `mtimes=None` sin cambio. La tool pasa a ser **W-COMPOSITE** con zona,
   **W-IPC** sin zona (taxonomía de la auditoría 34a).
4. `raw_params` extraído a un local compartido entre `_audit_error` y
   `audit_record` (mismo patrón que `add_zone`), sin cambio de contenido.

Diff: 63 líneas en `pcb.py` (`+50/-13`).

## Documentación previa ausente

`docs/analisis/auditoria-previa-34a-fix-1.md`, citada en la orden de
ejecución como la auditoría previa única del ciclo (autoridad ChatGPT,
veredicto `EJECUTABLE_CON_AJUSTES`), **no existe en el repo** en `a42f45d`
(`docs/analisis/` tiene 8 archivos, ninguno con ese nombre). Se ejecutó
igual, con los ajustes 1-7 ya integrados en el texto de la orden —
registrado como hallazgo, no bloqueante, no corregido.

## Tests

**Unit (`tests/test_pcb_delete_bulk.py`, 2 nuevos, 8 preexistentes sin
editar):**

- `test_delete_tracks_bulk_zone_touch_runs_refill_enforce_save_in_order` —
  orden estricto `refill → enforce → save` (spy `bridge.calls`), cada uno
  exactamente 1 vez, payload sin regresión respecto del test preexistente
  de refill.
- `test_delete_tracks_bulk_zone_touch_persist_failure_is_visible` — fallo
  de `save_board()` visible: `POST_ZONE_PERSIST_FAILED` en el texto,
  `live_has_fix`, refill/enforce sí corrieron (vivo arreglado), entrada de
  `.kicad-mcp/audit.jsonl` con `tool="delete_tracks_bulk"` y el código —
  sin swallow, sin payload normal.

El `_FakeBridge` compartido por los 10 tests se extendió con
`enforce_hole_clearance`/`save_board`/`fail_save_after` (mismo dialecto
que `tests/test_pcb_zones.py`, sesión 27) — necesario porque, sin esos
métodos, el test preexistente de refill atravesaría el path nuevo contra
la implementación base de `IpcBridge` (`board.raw.save()` sobre un
`object()`). Ningún cuerpo de test preexistente se editó.

**GUI (`tests/test_pcb_session34afix1_delete_bulk_persist_gui.py`, nuevo,
`integration_gui_slow`, autocontenido — no importa helpers de
`test_pcb_session27_zone_persist_gui.py` por diseño):** sobre el fixture
`despertador-routed` (footprints + plano GND filleado + ruteo real, DRC
0/0), siembra un stub de cobre GND anclado a un pad (patrón
`test_pcb_session19d_gui.py::_seed_pad_anchored_stub`, reescrito acá) y lo
borra con `delete_tracks_bulk` (bbox acotado al stub, sin tocar el resto
del ruteo real) **sin** `save_board()` manual. Verifica:

1. Payload `zones_refilled == 1`.
2. **Oráculo primario** (contenido/DRC, no sólo mtime): `run_drc()`
   independiente inmediato → `hole_clearance == 0`, sin `clearance` contra
   la Zone GND.
3. **Control R2 explícito:** operación posterior (`fill_zones()`) no
   dispara `EXTERNAL_EDIT_DETECTED` — los mtimes se registraron post-save.
4. Señal secundaria: mtime del `.kicad_pcb` avanzó.
5. Keepouts `__kicadmcp_hc__` en el rango `[4, 8]` (mismo umbral que
   sesión 24/27) — `enforce_hole_clearance` corrió y es idempotente.

## Gates

- `pytest -m "not integration and not integration_gui and not
  integration_gui_slow"`: **408 passed** (incluye los 10 de
  `test_pcb_delete_bulk.py`).
- `ruff check` / `ruff format --check` (archivos tocados): limpio.
- `mypy src/`: **Success: no issues found in 35 source files**.
- **Gate GUI del DoD (pipeline de zonas, gate de merge):** 1/1 verde
  contra KiCad 10.0.4 real, proyecto disponible en
  `/tmp/despertador-routed-test` (ya abierto en el PCB Editor —
  reutilizado tal cual, no recreado desde cero en esta sesión).
  Adicionalmente verificado sin regresión:
  `test_pcb_session19d_gui.py::test_delete_tracks_bulk_removes_all_copper_of_a_net`
  (preexistente, marca `integration_gui`) sigue verde con el fix aplicado.

## Revisión de Codex

Revisión independiente, read-only, del commit exacto `d174361` (base
`a42f45d`). Veredicto: **APROBAR**, 0 hallazgos BLOCKER/MAJOR/MINOR.
Evidencia verificada por Codex: suite focal 10/10, suite offline 408
passed/78 deselected, `ruff check` limpio, `ruff format` 3 archivos
conformes, `mypy` 35 archivos sin errores, `git diff --check` limpio; gate
GUI aceptado por evidencia aportada (no re-ejecutado — requiere KiCad
vivo). Estado: `OBJETIVO_CUMPLIDO`.

## Disciplina de alcance

Sin scope creep: no se tocó `route_board`, `add_zone`, `fill_zones`,
`_refill_enforce_and_save`, `delete_zone`, `add_keepout_zone`, ADR-0012 ni
ninguna otra ADR, `F-V3-ZONE-FILL-CRASH`, `F-V3-ROUTER-TIMEOUT-HARD`,
DT1/S49. Sin código de error nuevo (`POST_ZONE_PERSIST_FAILED` reusado tal
cual de sesión 27) ni tool nueva. `ruff format` sin scope reformateó de
rebote 2 archivos históricos ajenos al ciclo
(`docs/historico/piloto-multiagente/S47-S48/...`) — revertidos antes de
comitear; el commit de código quedó acotado a los 3 archivos autorizados
(`pcb.py`, `test_pcb_delete_bulk.py`, el nuevo test GUI). Sin push, sin
PR, sin merge.

## Documentación actualizada (este commit, posterior a la aprobación de Codex)

- **`docs/historico/sesiones/34a-fix-1-reporte.md`** (este documento).
- **`docs/BACKLOG.md`:** entrada P1 de `delete_tracks_bulk`/A1 cerrada,
  con la implementación real (R-A) en vez de la hipótesis original
  (reuso de `_refill_enforce_and_save`).
- **`docs/DECISIONES.md`:** `D-34a-fix-1.1` — R-A sobre R-B/hipótesis del
  BACKLOG, y cierre de A1 como primer ciclo completo bajo el flujo
  híbrido v2.
- **`docs/CONTEXT.md`:** ítem 7 de "Estado de la secuencia de Fase 4"
  (cierre de 34a-fix-1), puntero de próxima sesión movido a `34c`.
- **`docs/specs/tool-catalog.md`:** fila de `delete_tracks_bulk`
  actualizada (descripción del pipeline D-23.2 condicional + código
  `POST_ZONE_PERSIST_FAILED` agregado a la lista de errores) — excepción
  sancionada de F1 (DoD §3: catálogo actualizado por el agente, sin
  renombrar códigos existentes).

## Próxima sesión

**34c** — documentación de arquitectura para colaboradores externos,
ahora con la asimetría A1 ya resuelta (según el puntero fijado en sesión
34b, `docs/CONTEXT.md:371-376`). `delete_zone`/`add_keepout_zone` (A2/A3,
P2, sin precedente empírico) y `F-V3-ZONE-FILL-CRASH`/router timeout hard
siguen abiertos en `BACKLOG.md`, sin cambio de estado en este ciclo.

**Sin bloqueantes pendientes para mergear a `master`** (push/PR/merge
reservados al arquitecto).
