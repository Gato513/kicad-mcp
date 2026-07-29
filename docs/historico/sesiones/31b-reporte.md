# Sesión 31b — Fix intermedio: refs duplicados/sin anotar + bbox de Edge.Cuts

**Rama:** `sesion/31b-fix-delete-footprint-y-bbox` (branch desde
`sesion/31-validation-A-anavi-light-controller`, ya que sesión 31 aún no
estaba mergeada a `master` al arrancar — precondición verificada y
resuelta al inicio, sin bloquear la sesión).
**Tipo:** fix quirúrgico post-sesión 31, cierre de F-V1-01 (P1) y F-V1-02
(P0).

## Resumen ejecutivo

**Ambos hallazgos de sesión 31 cerrados**, con un pivote de diseño
importante respecto al plan original: el fix de F-V1-02 se resolvió por
**anotación** (`set_footprint_ref`), no por **borrado**
(`delete_footprint`/`resolve_duplicate_ref`) — descubierto durante la
investigación previa al fix, antes de escribir código.

### Hallazgo central: el diseño original habría violado ADR-0010

La investigación previa (2 agentes Explore + 1 agente Plan, todo
verificado contra el código real) encontró que el diseño de
`resolve_duplicate_ref` (borrar todas las instancias de un ref duplicado
excepto una) tenía dos problemas serios, no cubiertos por las decisiones
D1-D4 del prompt original:

1. **Chocaba con ADR-0010** — borrar footprints sigue siendo territorio
   de Gate G2 (que no existe en código), y esa asimetría con
   `delete_track`/`delete_via` es **deliberada**: acotar el trigger a
   "ref duplicado" no cambia el argumento de costo de re-instanciación.
2. **Habría destruido datos reales** — las 4 `REF**` de ANAVI Dev Mic
   (el caso que motivó todo esto) son mounting holes legítimas, no
   basura duplicada. Borrar 3 habría invalidado el ground truth de 13
   footprints que sesión 31 ya midió y admitió en la Validation Suite.

Presentado al arquitecto vía `AskUserQuestion` con la alternativa
encontrada por el agente Plan (verificada en el código vendored de
kipy): `fp.reference_field.text.value` usa semántica de escritura en
vivo (a diferencia de `fp.position`, la trampa de ADR-0008) — **renombrar
es técnicamente viable**. Decisión: pivotar a renombrar, con un spike
GUI de confirmación como Paso 0 de la ejecución.

### Paso 0 — spike confirmado (GO)

Contra KiCad 10.0.4 real (fixture despertador): `fp.reference_field.
text.value = "SPIKE_TEST_REF"` + `board.update_items(fp)` → el cambio
persistió en una relectura fresca. Restaurado sin incidentes. Camino de
renombrado confirmado antes de escribir ninguna línea de `src/`.

## Fixes implementados

### F-V1-01 (P1) — bbox de Edge.Cuts

**Corrección durante la investigación:** `board_bbox_mm` resultó ser
código muerto en `src/` (sin consumidores) — el bug real vivía en una
copia inline **independiente** dentro de `read_board_context` (el método
que `move_footprint`/`add_track`/`add_via` realmente usan). La entrada
original del backlog nombraba la función equivocada por la misma razón
estructural que causó el bug.

Fix: helper lock-free `_edge_cuts_bbox_nm` extraído de `board_outline`
(evita reentrar `self._lock`, no reentrante — hallazgo de diseño
verificado directamente contra el código: `read_board_context` mantiene
el lock durante TODO su cuerpo), consumido por los tres métodos
(`board_outline`, `board_bbox_mm`, `read_board_context`) vía el helper
puro `_bbox_with_margin`. Semántica final: **unión** de Edge.Cuts (±10mm)
y enjambre de footprints (±100mm) — estrictamente no regresivo.

Sin ADR (implementa comportamiento ya documentado, sin contrato externo
nuevo). 12 tests unit nuevos en `tests/test_ipc.py`, incluyendo un
canario de deadlock (reemplaza `self._lock` por un wrapper que lanza en
re-entrada).

### F-V1-02 (P0) — refs duplicados/sin anotar

Tool nueva `set_footprint_ref(ref, new_ref, kiid=None, base_snap=None)`:
sólo opera sobre refs YA duplicados (no puede usarse como
`delete_footprint` disfrazado — la precondición lo excluye
estructuralmente), lista candidatos con `data.candidates` si `kiid` no
se especifica (nunca resuelve a ciegas, mismo espíritu que la ambigüedad
de `_delete_copper`). Sin cascada.

Companion: pre-check `DUPLICATE_REFS` en `route_board`, insertado antes
del DRC pre-route y del subprocess de exportación DSN — usa
`pre_footprints` ya en memoria (cero IPC extra), reemplaza el
`KICAD_CLI_FAILED` opaco anterior por un error legible.

**ADR-0013** documenta el contrato completo, incluyendo el hallazgo
arquitectónico de la semántica `proto_ref=` de `reference_field`
(contraparte de ADR-0008).

Verificación: 12 tests unit (`_find_duplicate_refs`, pre-check de
`route_board` — incluye assert de que `run_autoroute`/`run_drc` nunca se
invocan si hay duplicados —, tool `set_footprint_ref` completa) + 1 test
`integration` contra pcbnew real
(`tests/fixtures/006_pcb_refs_duplicados/`, construida sobre
`005_pcb_limpio` con pcbnew scripting) que congela el experimento
controlado de sesión 31 como regresión permanente: `ok=False,size=0` con
duplicados → `ok=True` tras renombrar.

## Gates

- `pytest -m "not integration"`: verde (incluye los 24 tests nuevos).
- `pytest -m integration`: verde (incluye el test de reproducción real
  contra `dup_refs.kicad_pcb`).
- `ruff check`/`ruff format`/`mypy src/`: limpios en todos los archivos
  tocados.
- Gate GUI del DoD contra `/tmp/kicad-mcp-sesion31b-gui/` (copia fresca
  del fixture despertador): `test_pcb_session21_hole_clearance_gui.py`
  2/2, `test_pcb_session27_zone_persist_gui.py` 2/2.

## Archivos tocados

- `src/kicad_mcp/bridge/ipc.py`: helpers `_edge_cuts_bbox_nm`,
  `_bbox_with_margin`, constantes `_BBOX_OUTLINE_MARGIN_MM`/
  `_BBOX_SWARM_MARGIN_MM`; `board_outline`/`board_bbox_mm`/
  `read_board_context` actualizados; `set_footprint_ref` nuevo.
- `src/kicad_mcp/tools/pcb.py`: `_find_duplicate_refs`, tool
  `set_footprint_ref`, pre-check en `route_board`.
- `src/kicad_mcp/errors.py`: `DUPLICATE_REFS` (adición pura, F1).
- `docs/specs/tool-catalog.md`: fila `set_footprint_ref`, columna de
  errores de `route_board`, entrada de taxonomía `DUPLICATE_REFS`,
  bullets de `data`, enumeraciones de `live_stale`/P3.2 — todo en el
  mismo commit (DoD, excepción F1 sancionada).
- `docs/adr/0013-refs-duplicados-por-anotacion-no-borrado.md`: nueva.
- `docs/BACKLOG.md`: F-V1-01 y F-V1-02 cerrados; asimetría
  `delete_track`/`delete_footprint` anotada como "sigue así
  deliberadamente".
- `docs/DECISIONES.md`, `docs/CONTEXT.md`: actualizados.
- `tests/test_ipc.py`, `tests/test_pcb_session31b_duplicate_refs.py`
  (nuevo), `tests/fixtures/006_pcb_refs_duplicados/` (nuevo).

## Disciplina de alcance

Sin scope creep: no se implementó Gate G2, no se tocó
`validation-suite/level-a/anavi-dev-mic/` (el ground truth de ANAVI Dev
Mic sigue válido — el fix preserva las 4 mounting holes, sólo las
renombra), no se expandió el pre-check a otras validaciones
estructurales (queda anotado en ADR-0013 como hallazgo adicional —
`snapshots/delta.py:99-100` colapsa refs duplicados en
`get_context_delta` — sin tocar, fuera de alcance).

## Próxima sesión

Reintento de sesión 31: arranca desde Bloque 2 (colocación/zona ya
hechas en la corrida anterior, o repetible en minutos) sobre el
`working/` de ANAVI Dev Mic ya preparado, con `route_board` ahora
capaz de completar tras `set_footprint_ref` sobre las 4 instancias
`REF**`. Sesión 32 (Nivel B) arranca sólo cuando el reintento de 31
cierre con conclusión clara.
