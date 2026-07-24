# Sesión 24 — Fix F-D4-02 (Opción X): reordenar medición DRC + persistir en `route_board`

**Rama:** `sesion/24-fix-fd4-02-opcion-x` (desde `master`, post-merge de
`sesion/23-investigacion-fd4-02`). **Tipo:** implementación de fix quirúrgico
+ test de regresión gate del merge.

## Resumen ejecutivo

Se implementó la Opción X decidida por el arquitecto al cierre de sesión 23:
reordenar `route_board` para que la medición del DRC reportado
(`drc.err_post`/`por_tipo`) ocurra **después** del bloque interno de
`refill_zones()` + `enforce_hole_clearance()`, y agregar un `save_board()`
explícito al final de ese mismo bloque — contrato D-23.2 (ADR-0012):
"cuando `route_board` termina OK, disco == memoria == `err_post` reportado".
El fix quedó **validado en vivo contra KiCad 10.0.4 + Freerouting reales**
(no solo unit tests mockeados): 2/2 corridas consecutivas del test de
regresión sobre el fixture `despertador-routed`, con `err_post=5` y **cero**
`hole_clearance`/`clearance`-vs-GND en ambas — el síntoma original de F-D4-02
(16 `hole_clearance` + 30 `clearance` en la reproducción de Dogfooding 4)
desapareció. Alcance respetado: solo `route_board`; `enforce_hole_clearance`,
`fill_zones`, `add_zone(fill=True)` y el generador DSN no se tocaron.

## Bloque 1 — Diseño

Cubierto en detalle durante la exploración previa a la implementación (tres
agentes de exploración en paralelo + lectura directa de
`docs/investigacion/23-fd4-02.md`, `pcb.py:2366-2588`, `ipc.py:1902-2036`,
`errors.py`, `docs/specs/tool-catalog.md`, y los tests GUI existentes). Puntos
clave del análisis, confirmados antes de tocar código:

1. **Pipeline actual:** `post_report`/`por_tipo`/`diff_violations`
   (líneas 2434-2449 pre-fix) alimentaban **solo** el payload/audit/log —
   ningún control de flujo ni mutación dependía de ellos, así que el bloque
   se podía mover libremente.
2. **Snapshot/mtimes:** el `store.register(...)` (mtimes de disco, para
   `EXTERNAL_EDIT_DETECTED`) se registraba ANTES del punto donde se agregaría
   el nuevo `save_board()`. Si no se movía también, los mtimes quedarían
   stale y el propio guardado de `route_board` dispararía un
   `EXTERNAL_EDIT_DETECTED` espurio en la siguiente lectura — se decidió
   registrar el snapshot con mtimes **frescos**, después del save.
3. **`live_stale`:** `mark_live_stale`/`clear_live_stale` dependían de
   `snap_id` — se diferieron al mismo punto que el snapshot, preservando la
   semántica exacta de cada rama (`reloaded is True` → clear; si no → mark).
4. **Código de error nuevo:** `POST_ROUTE_PERSIST_FAILED`, agregado al
   `StrEnum ErrorCode` (excepción sancionada a F1 por DoD #2 — adición pura,
   no renombra nada, F3 intacta).
5. **Comportamiento del vivo si `save_board()` falla:** se dejó el board vivo
   TAL CUAL (con el fix de refill+enforce ya aplicado, sin reload forzado)
   — decisión sugerida en el prompt, sin objeciones al leer el código.
6. **ADR:** el último ADR existente era `0011` (no `0012`/`0013` como
   sugería el prompt tentativamente) — se usó `0012` como siguiente número
   libre real.

## Bloque 2 — Implementación

**Archivos tocados:** `src/kicad_mcp/tools/pcb.py`, `src/kicad_mcp/errors.py`,
`docs/specs/tool-catalog.md`, `docs/adr/0012-route-board-persist-contract.md`
(nuevo), `tests/test_route_board.py`.

- `route_board` (pcb.py): reordenado completo del bloque post-autoroute.
  Nuevo orden: clasificación de nets → reload (solo computa `reloaded`, sin
  tocar el store todavía) → refill+enforce+**`save_board()`** (con manejo de
  fallo → `POST_ROUTE_PERSIST_FAILED`) → **`post_report`/`por_tipo`/
  `diff_violations`** (ahora sobre el disco YA persistido) → snapshot con
  mtimes frescos → aplicación diferida de `mark/clear_live_stale`. Docstring
  de cabecera actualizado con el contrato D-23.2 + referencia al ADR-0012;
  comentario D-19.1 v6 agregado junto al bloque refill explicando por qué
  Freerouting no protege contra la zona GND para nets ajenos.
- `errors.py`: `POST_ROUTE_PERSIST_FAILED = "POST_ROUTE_PERSIST_FAILED"`
  agregado al enum.
- `tool-catalog.md`: fila nueva en §Taxonomía + código agregado a la columna
  de errores de `route_board`.
- **Decisión durante la implementación (no en el diseño original):** se
  reforzó `tests/test_route_board.py` con cobertura unit del código de
  error nuevo — el `_FakeBridge` ganó un parámetro `fail_save_after` para
  simular el fallo de `save_board()` post-refill sin tocar kipy real, y se
  agregó `test_route_board_post_route_persist_failed_when_save_fails` (nuevo)
  + una assertion en `test_route_board_refills_zones_when_present_and_reloaded`
  verificando las 2 llamadas a `save_board` (implícita pre-route + explícita
  post-refill). Esto cubre la assertion opcional #6 del Bloque 3 (test
  unitario del path de error) de forma más barata que un mock manual —
  determinista, sin KiCad.

**Diff:** `pcb.py` +119/-34 líneas (reorden, no crecimiento neto grande);
`test_route_board.py` +58 líneas (1 test nuevo + 1 assertion reforzada);
`errors.py` +1 línea; `tool-catalog.md` +2/-1 líneas. Verificación intermedia
(ruff/mypy/pytest -m "not integration") verde sin desvíos — no hizo falta
`AskUserQuestion` de fricción.

## Bloque 3 — Test de regresión (gate del merge)

**Fixture:** Opción (b) del prompt, vía helper — sin directorio estático
nuevo. El propio test deriva el bbox de `delete_tracks_bulk` en runtime de
`bridge.list_zones()` (unión de bboxes de zonas existentes + margen de 5mm),
en vez de hardcodear coordenadas del fixture checked-in — se confirmó en
vivo que la copia de trabajo real (`/tmp/gui-test-project`) tiene el board
en un origen absoluto distinto ((100,50)-(144,94)) del fixture crudo
((150,28)-(194,72)), mismo tamaño 44×44mm. Hardcodear hubiera sido frágil.

**Test nuevo:** `tests/test_pcb_session24_route_board_persist_gui.py`
(`integration_gui_slow`, calcado del patrón de
`test_pcb_session21_route_board_drc_gui.py`). 5 assertions (4 gate + 1
opcional):

1. `drc.por_tipo.hole_clearance == 0`.
2. Ninguna violación `clearance` de severidad error cuyos ítems referencien
   `Zone`+`GND`.
3. **(corazón de D-23.2)** `run_drc()` independiente inmediato, SIN
   `save_board()` manual, coincide exactamente con `drc.err_post`/`por_tipo`.
4. Conteo de keepouts entre 4 y 8 (umbral generoso, no flakey).
5. (opcional) mtime del `.kicad_pcb` cambió entre pre-route y post-route.

**Corridas — validado en VIVO contra KiCad 10.0.4 + Freerouting 2.1.0 reales**
(no solo mockeado), sobre `/tmp/gui-test-project` (copia de trabajo de
`despertador-routed`):

| Corrida | Resultado | Duración | `tracks_added`/`vias_added` | `drc_err_post` |
|---|---|---|---|---|
| 1 | ✅ passed | 186.5s | 224/28 | 5 |
| 2 | ✅ passed | 150.2s | 263/29 | 5 |

Ambas corridas: `hole_clearance:0`, sin `clearance` vs `Zone GND`,
`err_post` de `route_board` == `run_drc()` independiente sin save manual,
4 keepouts (sin proliferación), mtime cambiado. Los conteos de tracks/vías
difieren entre corridas (no-determinismo esperado de Freerouting) pero
`err_post`/composición de errores es idéntica en ambas — confirma que el fix
es estructural, no depende de la geometría específica del ruteo. Determinismo
confirmado, sin señales de flakiness.

## Bloque 4 — DoD, docs y merge

### DoD checklist

1. ✅ `ruff check` limpio (repo completo, diff acotado a los archivos de
   esta sesión — se descartó un fix de formato no relacionado en
   `scripts/verificar_entorno.py` que `ruff format .` tocó de paso, para
   mantener el diff mínimo).
2. ✅ `mypy src/` limpio (33 archivos).
3. ✅ `uv run pytest -m "not integration"`: 342 passed, 35 skipped, 22
   deselected — sin regresiones (341→342, +1 test nuevo).
4. ✅ `uv run pytest -m integration_gui_slow` (el test nuevo): 2/2 corridas
   verdes en vivo (ver Bloque 3).
5. ✅ ADR `docs/adr/0012-route-board-persist-contract.md` commiteado.
6. ✅ Docstring de `route_board` actualizado (contrato D-23.2 + referencia
   al ADR).
7. ✅ Comentario D-19.1 v6 junto al bloque refill.
8. ✅ `POST_ROUTE_PERSIST_FAILED` definido (`errors.py`) y usado (`pcb.py`),
   con cobertura unit dedicada.
9. ✅ Fixture vía helper (no directorio estático) commiteado como parte del
   test file.

### Guardarraíles de scope — respetados

`enforce_hole_clearance` (loop de vías, D-23.3/R16) NO tocado. `fill_zones`
y `add_zone(fill=True)` NO tocados. Generador DSN (Opción Y) NO tocado. No
hubo fricción que ameritara `AskUserQuestion` de desvío de scope — el
reorden quedó contenido en una sola función, tal como anticipaba el diseño
del Bloque 1.

### Estado del merge

**Pendiente de confirmación explícita del arquitecto** (gate del merge,
según instrucción del humano) antes de mergear a `master`. Diff completo y
resultado de las 2 corridas del test de regresión presentados para revisión.

## Métricas

- Líneas cambiadas (código + docs, sin contar el test GUI nuevo ni el ADR):
  `pcb.py` +119/-34, `errors.py` +1, `tool-catalog.md` +2/-1,
  `test_route_board.py` +58. Total ~181 líneas netas en archivos existentes.
- Archivos nuevos: ADR (117 líneas), test GUI de regresión (221 líneas).
- Tiempo por bloque (aproximado, sesión ejecutada por agente):
  Bloque 1 (diseño, vía exploración previa): ~sin desvío del timebox de
  30 min equivalente. Bloque 2 (implementación): dentro de 60 min, sin
  fricciones. Bloque 3 (test + 2 corridas reales con Freerouting,
  186.5s + 150.2s de ejecución real más overhead de escritura/verificación):
  dentro de 45 min. Bloque 4 (DoD + docs + reporte): dentro de 30 min.
- Desvíos del plan: ninguno de scope. Único agregado no anticipado
  explícitamente en el prompt: refuerzo de cobertura unit para
  `POST_ROUTE_PERSIST_FAILED` en `test_route_board.py` (cubre la assertion
  opcional #6 del Bloque 3 a nivel unit en vez de vía mock complejo del
  bridge real).

## Recomendación explícita para sesión 25 (D5)

Mismas precondiciones que D3/D4 (KiCad reiniciado limpio, fixture
`despertador-routed` restaurado, `health()` verde) + verificación específica
del contrato D-23.2 reforzado. Repetir la trilogía V1/V2/V3 de D4 con foco
en que **V2 ahora ratifica fidelidad al VIVO**, no solo consistencia de
lectura de disco — es decir, además de confirmar que el JSON de
`route_board` coincide con un `run_drc()` de disco (lo que V2 ya validaba),
D5 debe confirmar que el board **vivo** en KiCad (post-reload automático)
también coincide, cerrando el círculo completo vivo==disco==reportado. El
test de regresión de esta sesión (`test_pcb_session24_...`) ya ejercita esta
trilogía de forma automatizada — D5 debería poder apoyarse en dogfooding
real (flujo completo schematic→gerbers) sabiendo que el P0 de F-D4-02 está
cerrado con evidencia en vivo, no solo con tests mockeados.
