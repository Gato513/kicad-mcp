# Reporte de sesión 04 — bridge IPC persistente + semilla del Snapshot Store

**Fecha:** 2026-07-09 · **Rama:** `sesion-04` · **Commits:** 6 (uno por
tarea) · **Estado:** DoD cumplido en las seis tareas, sin push.

## Qué se completó

### Fase 0 — verificación del entorno

`python3 scripts/verificar_entorno.py` → 9 OK · 2 WARN · 0 FAIL. Los
WARN esperados (socket IPC no visible y `npx` ausente) no bloquean el
alcance de esta sesión. El fixture `005_pcb_limpio` estaba presente al
inicio (dos commits del humano en master antes de arrancar).

### Tarea 1 — `IpcBridge` singleton compartido

- `register_all(mcp, *, ipc_bridge=None)` en `tools/__init__.py`
  instancia UN `IpcBridge` (o acepta el inyectado) y lo pasa a
  `meta.health` y `pcb.*`. Una sola conexión al socket por proceso
  servidor.
- `tools/meta.register(mcp, *, ipc_bridge=None)` acepta el bridge; usa
  fallback local si falta (camino defensivo para llamadas directas).
- Tests unit (2): `__init__` counter sobre `IpcBridge`. Con inyección,
  `register_all` no crea bridges extra; sin inyección, crea
  exactamente uno.

### Tarea 2 — health fast-fail

- `_socket_file_missing(socket_uri)` + guardia en `_default_client_factory`.
  Si el URI es `ipc://<path>` y el archivo no existe, se levanta
  `KICAD_NOT_RUNNING` antes del import perezoso de `kipy`. Esquemas no
  filesystem (`tcp://…`) los resuelve el factory de siempre.
- Preserva el orden `env → arg → default` de la resolución del socket
  (verificado por test explícito).
- **Latencia de `health` con KiCad cerrado (workstation dev):**
  | Escenario | Antes T2 | Después T2 |
  |---|---|---|
  | Socket path inexistente (fixture) | 365.9 ms | 0.2 ms |
  Nota: la medición SIN fast-fail salió por debajo de 2 s porque en la
  workstation el `Connection refused` del kernel es inmediato (no hay
  listener); el peor caso descrito en el reporte 03 (2 s de timeout
  real de `kipy`) requiere un socket que acepta la conexión pero no
  responde. El fast-fail cubre ambos: si el file no existe, corta al
  millisegundo.
- Tests unit (3): fast-fail <100 ms, orden env→arg, y `tcp://` no
  falso-positivo.

### Tarea 3 — supervisión del bridge

- `_map_ipc_failure(op_name, exc)` module-level: mapea
  `TimeoutError → KICAD_TIMEOUT`, `ConnectionError` (builtin o
  `kipy.errors.ConnectionError` por `__qualname__`) `→ KICAD_NOT_RUNNING`,
  cualquier otra excepción → `KICAD_CLI_FAILED` con el detalle
  sanitizado (≤ 200 chars) en el hint.
- `IpcBridge._supervise(op_name)` context manager: cubre cada
  operación IPC (`get_version`, `get_open_board`, `list_footprint_refs`,
  `list_net_names`, `board_bbox_mm`, `move_footprint`, `add_track`).
  Ante fallo no-tipado: invalida `self._client` y remapea. **No hay
  retry silencioso** — la operación fallida responde su error tipado;
  la reconexión es responsabilidad del request siguiente.
- **Bug del reporte 03 cerrado**: `kipy` conecta lazily y su
  `ConnectionError` se levantaba en el primer `send()`, no en el
  constructor. La supervisión antes vivía solo en `_ensure_client`
  → el error se filtraba desde `bridge.get_version()` sin envolver
  (visible en el benchmark de T2). Ahora se atrapa y se mapea.
- Tests unit (5): ConnectionError, TimeoutError, ApiError-like
  genérico, sin retry silencioso, y typed passthrough
  (`KicadMcpError` no se remapea a `KICAD_CLI_FAILED`).

### Tarea 4 — Snapshot Store (semilla v0.3)

- `snapshots/store.py`:
  - `SnapshotEntry(snap_id, state, mtimes)`.
  - `SnapshotStore`: `register(state, mtimes) -> snap_id` monotónico
    por proceso, `get(snap_id) -> SnapshotEntry | None`, retención
    default = 10 (FIFO por `snap_id`), thread-safe con
    `threading.Lock`, `reset()` para tests.
  - `get_default_store()`: singleton module-level.
  - `collect_project_mtimes(schematic)`: `{ruta_canónica: mtime_ns}` de
    `.kicad_sch` + `.kicad_pcb` (si existe).
- `get_world_context` (`tools/world.py`) registra cada estado emitido
  y usa el `snap_id` real en la cabecera TOON — adiós `snap:1` fijo.
- `move_footprint` / `add_track` incorporan `base_snap: int | None = None`
  (aditivo al catálogo):
  - Ausente → comportamiento pre-v0.3.
  - No presente en el store → `SNAPSHOT_STALE` con hint accionable.
  - Presente pero algún `mtime_ns` cambió → `EXTERNAL_EDIT_DETECTED`
    (verificado con `os.utime`).
  - Válido → mutación procede; `snap_id` ecoa `base_snap` en el
    confirm y el audit.
- Cambio de semantics: `snap` en confirm/audit sin `base_snap` ahora
  es `0` (señal "operación no vinculada"). Rompe la aserción hard-coded
  del test 03 (`snap == 1`), actualizado a `snap == 0` en el mismo
  commit. Test integrado migra `params` para incluir `base_snap: None`.
- `docs/adr/0004`: techo formal `≤ 50 tokens_est` por confirmación +
  el hallazgo corregido de la sesión 03 sobre la palanca real de
  tokens (la degradación §4, no el envelope).
- Catálogo (`docs/specs/tool-catalog.md`): actualizado en el mismo
  commit — `base_snap?` en params, `SNAPSHOT_STALE` y
  `EXTERNAL_EDIT_DETECTED` en la lista de errores posibles de las
  tools `pcb.*`. F3 respetada (códigos existentes, sin renombrar).
- Tests unit (8): monotonicidad, retención 10 evicta 1..5 con 15
  registros, copia defensiva de `mtimes`,
  `collect_project_mtimes` con/sin pcb, `SNAPSHOT_STALE`,
  `EXTERNAL_EDIT_DETECTED`, y happy-path con audit.

### Tarea 5 — cierre pendientes DRC/export

- `tests/test_export.py::test_export_manufacturing_happy_path_against_clean_fixture`
  (integration): copia `005_pcb_limpio` a tmp → G3 pasa → gerbers +
  drill escritos. Verifica `count > 0` y extensiones `.gbr` / `.drl|.txt`.
- `tests/data/strict_severities.kicad_pro`: minimal (5 keys, ~200
  bytes). Sube `min_copper_edge_clearance` a 0.5 mm y mantiene severidad
  `error`. Segundo test integration (`test_export_manufacturing_blocks_with_strict_kicad_pro`)
  documenta como test ejecutable el hallazgo de la sesión 03 (el
  `.kicad_pro` original de 004 baja el umbral a 0.01 mm; las 27
  violaciones vuelven con el nuestro y el gate bloquea).
- El fixture 005 es pcb-only (limpieza intencional del humano en
  `1d0b835`). Agrego `_resolve_root_pcb()` paralelo a
  `_resolve_root_schematic()` en `tools/world.py` y
  `export_manufacturing` ancla en el pcb directamente.
  `_project_root()` de `export.py` cae al pcb cuando no hay sch para
  canonicalizar la carpeta `fab/`.

### Tarea 6 — E2E manual (integration_gui) de mutaciones

- `IpcBridge.get_footprint_position(board, ref) -> (Mm, Mm)`: lectura
  por IPC, supervisada, `COMPONENT_NOT_FOUND` si el ref falta. Interno
  del bridge — **no** se expone como tool MCP (catálogo intacto).
- Tests unit (2): conversión nm→mm en la frontera y raise en ref
  inexistente.
- `tests/test_ipc.py::test_move_footprint_round_trip_against_open_board`
  (integration_gui): lee posición inicial → desplaza 0.127 mm →
  llama `move_footprint` → re-lee → verifica igualdad con tolerancia
  ±1 nm (redondeo banker's). No lo ejecuto: skip si `KICAD_MCP_GUI_TEST != 1`
  o si falta `KICAD_MCP_GUI_REF`.
- `docs/pruebas-gui.md` §E2E mutaciones: paso a paso exacto.

## Definition of Done

```
uv run pytest -m "not integration and not integration_gui"
  → 58 passed, 19 deselected, 1 xfailed en 2.2 s
uv run pytest -m integration
  → 17 passed, 61 deselected en 173 s (DRC real 004 + 005)
uv run pytest -m "not integration_gui"
  → 75 passed, 2 deselected, 1 xfailed
uv run mypy src/                     → Success (strict, 28 files)
uv run ruff check src/ tests/        → All checks passed
uv run ruff format --check ...       → clean
```

## Estado del Snapshot Store al final de la sesión

- Singleton por proceso (`snapshots.store._default_store`).
- Retención = 10. Contador arranca en 1 y crece monótonamente.
- Cada entrada: `snap_id`, `state: NormalizedState`, `mtimes: {ruta: mtime_ns}`.
- `mtimes` incluye `.kicad_sch` + `.kicad_pcb` (si existen). Multi-hoja
  no soportado (F4 respeta lo del MVP).
- Uso actual:
  - `get_world_context` → registra en cada llamada. La cabecera TOON
    ya lleva el `snap_id` real.
  - `move_footprint` / `add_track` → validan `base_snap` con
    `SNAPSHOT_STALE` (no en el store) o `EXTERNAL_EDIT_DETECTED`
    (mtime cambió).
- **No implementado todavía**: registro post-mutación de un snapshot
  "resultante". Cuando el agente muta, el mundo real cambió pero
  ningún nuevo `snap_id` se emite; el siguiente `get_world_context`
  registra el estado nuevo. La cadena `mutación → nuevo snap` la
  desbloquea el delta v0.3 (fuente de continuidad).
- Reset entre tests: `tests/conftest.py::_reset_snapshot_store`
  autouse; garantiza que cada test arranque con `snap:1`.

## Decisiones tomadas dentro del margen permitido

1. **Fast-fail vive en `_default_client_factory`, no en `_ensure_client`.**
   Motivo: los tests con `client_factory` inyectado usan sockets ficticios
   (p. ej. `ipc:///tmp/kicad/api.sock` que no existe en CI). Si el check
   viviese en `_ensure_client`, TODOS los tests unit fallarían. Con la
   guardia en el factory real, solo la ruta real la ejerce.
2. **`_supervise` como context manager**, no decorador. Motivo:
   permite envolver solo el bloque IPC (dejando fuera cómputos puros
   como el `raw_board = board.raw`) y no cambia la signatura de los
   métodos públicos. El overhead por método es una línea de indent
   extra.
3. **`_map_ipc_failure` identifica `kipy.errors.ConnectionError` por
   `__qualname__`.** Alternativa considerada: importar
   `kipy.errors` en el módulo del bridge y usar `isinstance`. Descartada:
   el import perezoso de kipy es un contrato (server arrancable sin él,
   ADR — regla de arquitectura §10). Ir por qualname mantiene ese
   contrato.
4. **`snap` en confirm/audit sin `base_snap` = 0**, no 1. Motivo:
   `1` era un placeholder engañoso — sugería "yo pertenezco al snapshot
   1", que era falso. `0` es sentinel explícito "no vinculado". Rompo
   la aserción del test 03 y lo actualizo en el mismo commit.
5. **`get_footprint_position` queda interno del bridge, no se expone
   como tool MCP.** El prompt lo autoriza. Motivo: es una lectura
   auxiliar del test integration_gui, no un servicio del agente. Si el
   agente algún día lo necesita (para verificar mutaciones aplicadas
   antes de encadenar), se promueve a tool y se agrega al catálogo.
6. **`_resolve_root_pcb` en `tools/world.py`** (junto a
   `_resolve_root_schematic`), no en `tools/export.py`. Motivo:
   agrupar los resolvers evita duplicación futura si otra tool también
   quiere anclar en pcb (p. ej. `run_drc` como tool independiente).
7. **`_project_root()` de `export.py` cae del sch al pcb** cuando no
   hay sch. Motivo: el fixture 005 es pcb-only por decisión del humano
   (`1d0b835`), y la canonicalización de `fab/` se rompía. Alternativa
   considerada: forzar sch obligatorio y pedir al humano que
   restaure. Descartada: el humano fue explícito sobre eliminar sch;
   respeto esa señal.
8. **Reset del store como autouse fixture en `conftest.py`**, no
   como decorator por-test. Motivo: el store es un singleton global;
   olvidarlo en un test crea test-order dependencies invisibles. El
   autouse los previene.

## Pendientes

1. **Registro post-mutación en el store**: hoy solo `get_world_context`
   registra. Un mutación → nuevo `snap_id` requiere reconstruir el
   estado (releer .kicad_pcb o .kicad_sch). Costo latente que el
   delta v0.3 sí paga, pero el store por sí solo no.
2. **Golden 003 aún xfailed** (sin cambios en esta sesión). Su cierre
   forma parte natural del delta v0.3.
3. **`add_track` con `points_mm`** (múltiples segmentos) sigue no
   implementado. Idem sesión 03.
4. **`_socket_file_missing` no cubre `tcp://` timeouts**. Si el humano
   monta un backend IPC remoto que hace timeout, el peor caso vuelve
   a ser 2 s. Fuera de scope MVP (Linux + socket local).
5. **`SNAPSHOT_STALE` incluye el nombre `base_snap=N` en el message
   pero no en el hint estructurado**. Menor: si algún día el agente
   quiere reintentar programáticamente, el `N` está en `message`, no
   en un campo dedicado. `to_dict()` de KicadMcpError sí lo expone en
   el message string.

## Dudas abiertas para sesión 05

1. **¿Delta v0.3 completo o spike kicad-skip primero?**
   Recomendación mía: el delta primero (semilla del store ya
   registra `snap → state` y `mtimes`; queda calcular la diferencia
   canónica entre dos states y emitir el TOON delta). El spike de
   kicad-skip es de investigación pura; puede meterse en paralelo
   como día parcial. Ver §Propuesta.
2. **¿Registrar snapshot post-mutación en `move_footprint`/`add_track`?**
   Si la respuesta es sí, la cadena `mutar → obtener nuevo snap →
   confirmar contra ese snap` funciona sin volver a llamar
   `get_world_context`. Costo: re-leer el pcb tras la mutación (kipy
   ya lo tiene en memoria, pero necesitamos convertirlo a
   `NormalizedState`). El delta v0.3 necesita esta capacidad
   igualmente.
3. **`snap = 0` como sentinel**: ¿aceptable a largo plazo? Alternativas:
   `snap = None` en el catálogo (rompe el contrato de string
   `[snap:X]`) o eliminar el prefijo cuando no hay snap. Prefiero
   `0` porque el matching regex `\[snap:\d+\]` sigue funcionando.
4. **`_ipc_payload` en `health`**: hoy paga la latencia de
   `bridge.get_version()` incluso con fast-fail (0.2 ms). Aceptable.
   Pero con KiCad **abierto** y responsive, cada `health` paga ~1-2 ms
   de IPC round-trip. ¿Vale cachear la última versión N segundos?
   Preferencia mía: no cachear en v0.3; medir primero si es problema.

## Propuesta concreta para la sesión 05

**Argumento del orden:** el store ya está; la palanca de mayor valor
inmediato es el **delta v0.3 completo** — desbloquea el des-xfail del
golden 003 y materializa la razón de ser del store (que las mutaciones
sean baratas contra el mismo mundo). El spike de kicad-skip y la Eval A
son investigación (aprendizaje sin código de producción); pueden
correr en paralelo si el humano quiere invertir un día extra.

**Núcleo (días 1-4): delta v0.3**
1. `snapshots/delta.py`: `compute_delta(prev: NormalizedState, curr:
   NormalizedState) -> Delta` con adds/removes/updates de componentes,
   nets y pines. Determinista, sorted, unit-tested contra golden
   003 (des-xfail en el mismo commit).
2. `tools/world.get_context_delta(base_snap: int, max_tokens?: int) -> str`:
   levanta `SNAPSHOT_STALE` si `base_snap` no está en el store,
   `EXTERNAL_EDIT_DETECTED` si mtime cambió, sino computa y devuelve
   TOON delta.
3. Registro post-mutación en `move_footprint`/`add_track`: tras
   mutar, el bridge reconstruye `NormalizedState` del pcb en memoria
   (no re-lee disco), registra un nuevo `snap_id` en el store, y el
   confirm ecoa ese snap. Cierra la cadena "mutar → confirmar contra
   snap fresco".

**Paralelo opcional (día 4-5): spike de kicad-skip (readonly)**
4. Explorar `kicad-skip` contra copias del fixture 004_real:
   - ¿Parseo del `.kicad_sch` es fiel?
   - ¿Detecta componentes, nets, jerarquía?
   - ¿Manipulación (agregar símbolo) genera un archivo válido para KiCad?
   Sin código de producción — un notebook o un script en
   `scratchpad/`. Entregable: informe con evidencia (`.kicad_sch`
   generado abre en KiCad sí/no) para decidir sobre `add_symbol` en
   sesión 06.

**Fuera de scope de sesión 05**:
- `add_symbol` real (bloqueado por el spike de arriba).
- Freerouting / `suggest_positions` (v0.4).
- Eval A (formato TOON vs CSV vs JSON compacto): tiene ya los
  datos disponibles (world.get_world_context genera TOON hoy; falta
  medir el mismo estado en CSV y JSON compacto y comparar tokens_est
  + comprensión del modelo). Es una tarde de laboratorio; puede ser
  parte del día 5 si el spike se acorta.

**Riesgo declarado**: el registro post-mutación en el store requiere
reconstruir `NormalizedState` desde el board vivo de kipy, sin
re-leer el `.kicad_pcb` en disco (que no está mutado hasta que el
usuario guarde). Esto obliga a un nuevo path en `state_builder`
paralelo al actual (que lee del disco vía kicad-cli). Puede ser el
mayor consumidor de tiempo de la sesión — si peligra la finalización,
priorizar delta contra dos snapshots existentes (uno pre-mutación,
uno post-mutación forzando un re-lectura tras `Save`) y dejar la
reconstrucción in-memory para sesión 06.
