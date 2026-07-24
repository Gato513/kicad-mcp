# Sesión 17 — P2: route_board robusto

**Rama:** `sesion/17-route-board-robusto` (desde `sesion/16-get-tracks` @ `3e758b0`
— sesión 16 no estaba mergeada a master) · **Fecha:** 2026-07-20.

## Resumen

Se cerraron las 4 fricciones de F-08/F-09/F-11/F-12 del Dogfooding 2 sobre
`route_board`, se corrigió el bug real de `get_copper_by_kiid` descubierto en
16b (P2.0), y se generó por dogfood real un fixture ruteado
(`tests/fixtures/despertador-routed/`) contra el que los tests e/f de sesión
16 corrieron — **validados dos veces**: una contra un board vacío (inválido,
descubierto a mitad de sesión) y una segunda vez, real, contra 313
tracks/21 vías de cobre denso tras que el humano recargara el board en KiCad.

**Hallazgo no anticipado por el plan:** la inyección de edge clearance al DSN
(P2.1) resultó ser un mecanismo de Freerouting **completamente indocumentado**
— se confirmó por ingeniería inversa de bytecode (`javap`, con JDK instalado
por el humano a mitad de sesión) y validación empírica con Freerouting real,
no por lectura de spec. Además se encontró y corrigió un bug de entorno real:
Freerouting con `gui.enabled=true` (default de instalación) completa el ruteo
pero el proceso se cuelga sin escribir el `.ses` — invisible hasta que se
corrió el round-trip real por primera vez en la sesión.

`unit+golden`: **259 passed, 1 skipped** (desde 214 al inicio — +45 tests
nuevos de esta sesión). `integration` (kicad-cli offline): **22 passed, 0
failed**. `integration_gui`: **18 passed, 4 skipped, 0 failed**, incluyendo
e/f validados contra cobre real. `ruff`/`ruff format`/`mypy --strict` limpios.

## Diff-resumen por tarea

| Tarea | Archivos principales | Estado |
|---|---|---|
| P2.0 (fix bug `get_copper_by_kiid`) | `bridge/ipc.py`, `tests/test_ipc.py` | Cerrada — verificada en vivo |
| P2.1 (`rules_reader.py` + inyección DSN + `add_track`) | `bridge/rules_reader.py` (nuevo), `bridge/autoroute.py`, `tools/pcb.py` | Cerrada — gate empírico cumplido |
| P2.5 (fix DRC pos Edge.Cuts) | `bridge/rules.py`, `tests/test_rules.py` (nuevo) | Cerrada |
| P2.2 (contrato JSON de `route_board`) | `tools/pcb.py`, `bridge/autoroute.py`, `errors.py` | Cerrada |
| Fixture `despertador-routed` | `tests/fixtures/despertador-routed/` (nuevo) | Cerrada — validada en vivo dos veces |
| Docs | `docs/specs/tool-catalog.md`, `docs/pruebas-gui.md` | Actualizados en el mismo alcance |

```
$ git diff --stat
 docs/pruebas-gui.md                |  65 ++++-
 docs/specs/tool-catalog.md         | 100 +++++--
 src/kicad_mcp/bridge/autoroute.py  | 365 +++++++++++++++++++++
 src/kicad_mcp/bridge/ipc.py        |  46 ++-
 src/kicad_mcp/bridge/rules.py      |  29 +-
 src/kicad_mcp/errors.py            |   1 +
 src/kicad_mcp/tools/pcb.py         | 128 ++++---
 tests/test_autoroute.py            | 381 ++++++++++++++++++++
 tests/test_ipc.py                  |  93 ++++++
 tests/test_route_board.py          | 140 +++++++-
 tests/test_route_board_gui_slow.py |  27 +-
 11 files changed, 1286 insertions(+), 89 deletions(-)
```
Más `src/kicad_mcp/bridge/rules_reader.py` (nuevo), `tests/test_rules.py`
(nuevo), `tests/test_rules_reader.py` (nuevo), `tests/fixtures/despertador-routed/`
(nuevo) — sin trackear todavía, no comiteados (a la espera de confirmación).

## P2.0 — Fix `get_copper_by_kiid` (prerrequisito)

Causa raíz confirmada (ver `docs/sesiones/16b-reporte.md`): el código asumía
`get_items_by_id([kiid])` → `[]` en not-found; kipy en realidad lanza
`ApiError("... none of the requested IDs were found or valid")`, que
`_supervise` mapeaba genéricamente a `KICAD_CLI_FAILED` antes de que el guard
`if not items` corriera. Fix: helper `_get_items_by_id_or_empty` en
`bridge/ipc.py` que absorbe SOLO esa excepción puntual (detección estructural
por `__module__`/`__qualname__` + substring del mensaje) y devuelve `[]`;
enruta los 4 consumidores (`verify_footprint_by_kiid`, `get_copper_by_kiid`,
`remove_by_kiid`, `move_footprint`).

**Verificado en vivo:** `test_delete_track_id_stale_after_external_removal`
(el que fallaba en 16b con `KICAD_CLI_FAILED`) pasa limpio contra KiCad real;
`integration_gui` completo: 17 passed / 5 skipped / **0 failed** tras el fix
(antes: 1 failed).

## P2.1 — Reglas del proyecto al DSN + `add_track`

**Hallazgo que revirtió la premisa del plan:** el ancho/clearance por
netclass YA viajaba al DSN sin fix — `pcbnew.LoadBoard()` carga
automáticamente las netclasses del `.kicad_pro` hermano (verificado
exportando `tests/fixtures/004_real/video.kicad_pcb`: el DSN trae
`(class pwr ... (rule (width 250)(clearance 200)))` = 0.25mm/0.2mm, exacto a
`video.kicad_pro`). Lo que faltaba de verdad (causa real de F-11) es el
**edge clearance** — Freerouting no tiene NINGÚN concepto de "clearance al
borde del board": su matriz de clearance sólo conoce item-classes
`TRACE/VIA/PIN/SMD/AREA` (`DefaultItemClearanceClasses`, decompilado del jar
2.1.0), y `ExportSpecctraDSN` nunca asocia el `(boundary ...)` a una clase.

**Mecanismo real (confirmado por bytecode con `javap`, sesión 17 — el humano
instaló el JDK a mitad de sesión para esto, no documentado en ningún lado):**
`Structure.read_boundary_scope` acepta `(clearance_class "nombre")` DENTRO de
`(boundary ...)`; ese nombre viaja a `BoardManager.create_board(...)`.
`NetClass.read_scope` acepta una `(class "nombre" (rule (clearance V)))` SIN
nets asignados (sintácticamente válido). Implementado en
`bridge/autoroute.py::_inject_edge_clearance`: post-procesa el `.dsn` de
texto (parser de scopes S-expr consciente de comillas,
`_find_dsn_scope_span`/`_iter_direct_child_scopes`) para inyectar
`(clearance_class "board_edge")` en el boundary + `(class "board_edge" (rule
(clearance <edge_mm*1000>)))` en network. Validado empíricamente corriendo
Freerouting real sobre un board sintético con pads a 0.3mm del borde: la
inyección parsea sin error y rutea normalmente (score 987.50, 0.73s).

`rules_reader.py` (nuevo): lee `min_copper_edge_clearance` (dos ubicaciones
divergentes del `.kicad_pro` según versión — `design_settings.rules.*` vs
`board.design_settings.rules.*`, ambas probadas), netclasses, asignación
net→clase (`netclass_assignments`/`netclass_patterns`), cacheado por
`(mtime_ns, size)`. `add_track`'s `_find_track_pad_collision` ahora usa el
clearance real de la netclass del track (antes: piso fijo 0.2mm, deuda D-16.4
de sesión 16).

**Gate empírico cumplido:** `route_board` sobre el despertador con
`min_copper_edge_clearance=0.5` (regla REAL, no bajada como en el D2) →
`drc.por_tipo` **sin `copper_edge_clearance`** en ambas corridas reales (ver
§route_board JSON).

## P2.5 — Fix DRC pos Edge.Cuts (`bridge/rules.py`)

Confirmado con JSON real de `kicad-cli pcb drc` (board sintético, track a
0.2mm de un borde con regla 0.5mm): el primer ítem de una violación
`copper_edge_clearance` es SIEMPRE `"... on Edge.Cuts"` con la posición de un
punto del borde (no necesariamente `[0,0]` literal, pero siempre inútil para
ubicar el cobre ofensor); el segundo ítem trae la posición real. Fix:
`_reorder_edge_clearance_items` en `_build_report` reordena para que el
ofensor real quede primero — arregla `tools/validate.py::_sample_of` (que
toma `items[0].pos`) sin tocar ese archivo.

## P2.2 — Contrato JSON de `route_board`

`route_board` devuelve JSON estructurado (rompe el `confirm ≤50 tok` de
D-14.2 original — trade-off documentado en tool-catalog.md: sigue siendo 1
sola llamada). Nuevos parsers en `autoroute.py`: `parse_dsn_net_pin_counts`
(denominador correcto desde `(network (net <n> (pins ...)))`, excluye
`unconnected-*` de 1 pin por construcción — arregla F-09), 
`parse_ses_net_wire_counts` (estado por net desde `(network_out (net <n>
(wire ...)))`), `classify_net_routing` (heurística N-1 wires por net,
documentada como aproximación — no reconstruye el grafo). `route_ms` ya se
medía desde sesión 14 pero nunca llegaba al agente (F-08) — ahora siempre
presente en éxito. `ROUTE_NET_BLOCKED` (código nuevo, F3) viaja embebido en
`nets.bloqueadas[].code`, nunca como excepción — causa mínima honesta ("sin
camino aparente; revisar manualmente"), sin A* de bloqueador concreto
(decisión explícita del humano esta sesión, diferido a 17b).

## `route_board` sobre el despertador — JSON literal (dogfood real)

Dos corridas completas contra KiCad vivo (24 fp, outline 55×55mm, regla de
clearance 0.5mm real):

**Corrida 1** (route_ms 60.4s, sin errores):
```json
{
  "route_ms": 60386.406,
  "nets": {"total": 41, "ruteables": 10, "ruteadas": 10, "parciales": [], "bloqueadas": []},
  "drc": {"err_preexistentes": 64, "err_post": 0, "err_introducidos": -64, "por_tipo": {}},
  "tracks_added": 324, "vias_added": 23
}
```

**Corrida 2** (route_ms 87.4s — mismo board, nueva corrida; nondeterminismo
esperado del router):
```json
{
  "route_ms": 87390.048,
  "nets": {"total": 41, "ruteables": 10, "ruteadas": 10, "parciales": [], "bloqueadas": []},
  "drc": {"err_preexistentes": 64, "err_post": 1, "err_introducidos": -63,
          "por_tipo": {"unconnected_items": 1}},
  "tracks_added": 313, "vias_added": 21
}
```
Esta segunda corrida es la que se copió al fixture (313 tracks, 21 vías, 1
error `unconnected_items`, **0 `copper_edge_clearance`**).

### ¿Qué fricciones del Dogfooding 2 cierran?

| Fricción | Estado | Evidencia |
|---|---|---|
| F-08 (`route_ms` ausente) | **Cerrada** | `route_ms` presente en ambas corridas (60386/87390 ms). En fallos del pipeline (timeout, jar ausente) sigue sin viajar — diferido a 17b, `KICAD_TIMEOUT` ya trae `data.timeout_s` como proxy |
| F-09 (denominador engañoso) | **Cerrada** | `nets.total=41` / `ruteables=10` desde el `.dsn`, no desde `unconnected` del DRC — ya no mezcla ratsnest con nets de 1 pin |
| F-11 (reglas no viajan, edge clearance violado) | **Cerrada** | 0 `copper_edge_clearance` en `por_tipo` con la regla REAL 0.5mm, ambas corridas |
| F-12 (nets bloqueadas sin mensaje) | **Parcialmente cerrada** | `bloqueadas[].causa` existe y se testeó a nivel unit; en el dogfood real `bloqueadas=[]` (nada que reportar) — el mínimo honesto no se ejerció con un caso real bloqueado. A* de bloqueador concreto diferido a 17b (decisión explícita) |

## Fixture `tests/fixtures/despertador-routed/`

- Path: `tests/fixtures/despertador-routed/` (despertador_inteligente.kicad_pcb/
  .kicad_pro/.kicad_sch/.kicad_prl + README.md).
- Tamaño: `.kicad_pcb` 172 KB (vs 119 KB pre-ruteo).
- Estado: 313 tracks, 21 vías, 41 nets (10 ruteables, 10/10 ruteadas), DRC: 1
  error (`unconnected_items`), 0 `copper_edge_clearance`.
- `min_copper_edge_clearance`: 0.5mm (regla real, confirmado en el `.kicad_pro`
  copiado).
- No comiteado todavía (a la espera de confirmación del humano, igual que el
  resto de los archivos nuevos) — sin commit hash propio aún.

### Validación en vivo de los tests e/f (dos corridas, una inválida)

**Corrida A (inválida, descubierta a mitad de sesión):** tras rutear por
subprocess (`route_board` opera sobre DISCO, D-14.1) y copiar el fixture, corrí
`integration_gui` completo contra el proyecto — 18 passed/4 skipped incluyendo
e/f. Pero el board VIVO en KiCad nunca se recargó (`File→Revert`): la sesión
GUI seguía viendo el estado PRE-ruteo por IPC (`raw.get_tracks()` = 0,
confirmado). Es decir, e/f pasaron pero contra un board vacío por IPC — no
ejercitaron colisión real. Uno de los tests (e) llama `save_board`, que
persistió el estado vivo (vacío) sobre el archivo, pisando momentáneamente el
ruteo en disco (sólo en `/tmp/gui-test-project`, el fixture del repo ya estaba
copiado y a salvo).

**Corrida B (válida):** restaurado el disco desde el fixture, el humano hizo
`File→Revert` en KiCad. Confirmado por IPC: `raw.get_tracks()` = 313,
`raw.get_vias()` = 21 — el editor vivo ahora sí ve el cobre real. Re-corrida
`integration_gui`: **18 passed, 4 skipped, 0 failed** — e/f pasaron con
`_pick_free_stub` navegando alrededor de cobre denso real. Post-corrida:
conteo de tracks/vías restaurado (313/21, sin leftovers), confirmando que el
teardown de e/f limpia correctamente incluso con cobre denso alrededor.

**Nota de higiene:** el DRC del archivo vivo en `/tmp/gui-test-project`
subió a 16 errores tras el `save_board` de los tests (vs 1 en el fixture del
repo) — probablemente KiCad recalcula geometría derivada (zonas, courtyard)
al guardar desde la GUI, distinto al archivo escrito por el round-trip
subprocess. Es un artefacto del entorno de scratch, no afecta el fixture del
repo (verificado sin tocar: sigue en 1 error). No investigado más a fondo por
alcance/tiempo.

## Bug real de tool descubierto: Freerouting se cuelga con `gui.enabled=true`

**No es un bug del código de kicad-mcp — es un hallazgo de entorno de
Freerouting 2.1.0**, pero afecta directamente la confiabilidad de
`route_board`, así que se corrigió a nivel de código (no sólo se reportó).

Con la config persistente de Freerouting (`$TMPDIR/freerouting/freerouting.json`,
default de instalación) en `gui.enabled=true`: el batch mode (`-de/-do -host
KiCad`) completa el ruteo (el log dice "Auto-routing was
completed"/"Optimization was completed") pero el proceso JVM se cuelga
DESPUÉS sin escribir el `.ses` — revienta por `KICAD_TIMEOUT` aunque el
router ya terminó. Reproducido de forma consistente (3 corridas seguidas,
descartada la hipótesis de telemetría/red primero). Con `gui.enabled=false`
el mismo router corre limpio de punta a punta.

**Fix:** `_ensure_freerouting_headless_config()` en `autoroute.py` fuerza
`gui.enabled=false` en la config de Freerouting antes de cada invocación
(best-effort: si el archivo no existe en ninguna ubicación candidata, no
toca nada). Verificado: reseteando `gui.enabled=true` a mano y volviendo a
correr `route_board`, el código lo corrigió solo (confirmado leyendo el
archivo después). 6 tests unit nuevos en `test_autoroute.py`.

## Suites

- `unit+golden`: **259 passed, 1 skipped, 44 deselected** (era 214 al cierre
  de 16b; +45 tests de esta sesión: 6 P2.0, 12 rules_reader, ~19 autoroute
  P2.1/P2.2/headless-config, 4 rules P2.5, 4 route_board).
- `integration` (kicad-cli offline, sin KiCad vivo): **22 passed, 0 failed**.
- `integration_gui`: **18 passed, 4 skipped, 0 failed** (corrida B, válida,
  contra cobre real).
- `ruff check` / `ruff format --check` / `mypy --strict src/`: limpios.

## Próximo paso (17b, fuera de alcance de esta sesión)

- A* de bloqueador concreto para `nets.bloqueadas[].causa` (F-12 completo).
- `route_ms` en la ruta de fallo del pipeline (timeout/jar ausente).
- P2.3 (limpieza de tracks huérfanos en re-route incremental), P2.4 (timeout
  adaptativo) — sin caso real todavía.
- Investigar la discrepancia de DRC post-`save_board` desde la GUI (nota de
  higiene arriba) si vuelve a aparecer.
- Merge de `sesion/16-get-tracks` a master sigue pendiente (paso del humano).
