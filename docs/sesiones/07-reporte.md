# Reporte de sesión 07 — Resiliencia IPC: busy, estados distinguibles, health fino

**Fecha:** 2026-07-10 · **Rama:** `sesion-07` (5 commits, sin push)
**Base:** `master @ b73d2d7` (post-merge de sesión 06 + `kicad-skip>=0.1` ya
declarado en pyproject por el humano).
**Entorno vivo:** KiCad 10.0.4 con PCB Editor abierto sobre
`/tmp/gui-test-project/video.kicad_pcb`, API server habilitado. Env vars
`KICAD_MCP_GUI_TEST=1`, `KICAD_MCP_PROJECT`, `KICAD_MCP_GUI_REF=U19`,
`KICAD_API_SOCKET` presentes durante toda la sesión.

## Fase 0 — verificación

`python3 scripts/verificar_entorno.py` → 10 OK · 1 WARN · 0 FAIL (el WARN
es `npx` para el Inspector, no requerido). Smoke `integration_gui -k version`
→ PASS. Suite de arranque `pytest -m "not integration and not integration_gui"`
→ 85 passed (línea base sesión 06).

## Estado por tarea

| Tarea | Estado | Commit |
|---|---|---|
| T1 `_map_ipc_failure` reconoce ApiStatusCode | ✅ | `6a8c480` |
| T2 Retry acotado AS_BUSY | ✅ | `8f914f7` |
| T3 Health fino (3 niveles IPC) | ✅ | `a7a7d69` |
| T4 Tests delta pcb/pcb (unit + integration_gui) | ✅ | `8a55ed2` |
| T5 Instrumentación `lookup_ms` en mutaciones | ✅ | `ca7c096` |
| T6 (OPCIONAL) `add_symbol` | ⏭ diferida | — |

### T1 — `_map_ipc_failure` reconoce `ApiStatusCode` (D-07.2)

Constantes locales `_AS_UNHANDLED = 5` y `_AS_BUSY = 7` copiadas del proto
(`envelope_pb2.pyi:70-77`) para preservar el contrato perezoso (nada de
`kipy` a nivel de módulo). Discriminación por `type(exc).__qualname__ ==
"ApiError"` **más** `__module__.startswith("kipy")` — mismo patrón que la
detección de `ConnectionError` de sesión 05 T1.

Comportamiento:

- `ApiError.code == AS_BUSY` (7) → `KICAD_CLI_FAILED` + hint fijo "KiCad
  está ocupado con una operación en curso; reintentá en unos segundos" +
  `data.ipc_status="busy"`.
- `ApiError.code == AS_UNHANDLED` (5) → `KICAD_CLI_FAILED` + hint "El
  editor requerido no está abierto en KiCad (abrí el PCB Editor)" +
  `data.ipc_status="unhandled"`.
- `ApiError` con code desconocido → bucket genérico sin `data.ipc_status`.
- Cualquier otra excepción → comportamiento previo intacto.

**F3 intacta**: el código sigue siendo `KICAD_CLI_FAILED`. La clave
nueva `data.ipc_status` se documenta en la sección estándar de `data` del
catálogo (aditiva al canal introducido en sesión 06 T4).

Tests unit añadidos (4):
`test_supervise_maps_kipy_api_error_busy_to_ipc_status_busy`,
`test_supervise_maps_kipy_api_error_unhandled_to_ipc_status_unhandled`,
`test_supervise_kipy_api_error_without_known_code_falls_through`,
`test_supervise_kipy_connection_error_still_wins_over_api_error_path`.

### T2 — Retry acotado para lecturas idempotentes (D-07.1)

Wrapper `IpcBridge._run_supervised_read(op_name, do)` con whitelist
`_IDEMPOTENT_OPS`:

```
{get_version, get_open_board, get_open_documents_pcb,
 list_footprint_refs, list_net_names, board_bbox_mm,
 snapshot_footprints, get_footprint_position}
```

- Backoff exponencial acotado: 250 → 500 ms, máximo 2 reintentos
  (< 1 s adicional).
- Si `op_name` NO está en la whitelist → `AssertionError`. Es la frontera
  estructural, no un flag encendible: `move_footprint`/`add_track` usan
  `_supervise` directamente, no pasan por este wrapper.
- `_supervise` modificado: NO invalida `self._client` cuando el fallo
  mapeado es busy (la conexión IPC sigue viva). Cualquier otro fallo
  mid-op sigue invalidando.
- Cada retry emite una línea JSON: `{"tool_name":"ipc_retry","op_name":
  "get_version","attempt":1,"backoff_ms":250}` para observabilidad.

Tests unit añadidos (5):
`test_retry_recovers_after_transient_busy`,
`test_retry_persistent_busy_after_max_retries_returns_typed_error`,
`test_mutation_move_footprint_does_not_retry_on_busy`,
`test_run_supervised_read_rejects_non_idempotent_op_name`,
`test_supervise_preserves_client_on_busy`.

**Mutation testing del retry** (T2 requerida). Fake `_BusyThenOkClient`
con `busy_before_ok=99` (busy persistente):

- Cliente invocado exactamente **3 veces** (1 intento inicial + 2 retries):
  ```
  test_retry_persistent_busy_after_max_retries_returns_typed_error PASSED
  assert client.get_version_calls == 3, "1 inicial + 2 retries = 3 invocaciones al cliente"
  ```
- Error final: `KICAD_CLI_FAILED` con `data == {"ipc_status": "busy"}`.
- Log JSON con 2 líneas de retry (`attempt:1`, `attempt:2`).

**Mutación con AS_BUSY = cero retry** (T2 requerida). Fake `_BusyBoard`
que siempre levanta busy en `get_footprints`, `move_footprint` llamado:
```
test_mutation_move_footprint_does_not_retry_on_busy PASSED
assert busy_board.get_footprints_calls == 1, (
    "una mutación NO se reintenta ante AS_BUSY (D-07.1); "
    f"hubo {busy_board.get_footprints_calls} invocaciones"
)
```
El fake registra exactamente 1 invocación → error inmediato con
`data.ipc_status="busy"`.

### T3 — Health fino (D-07.3)

`tools/meta._ipc_payload` reporta tres niveles independientes con estados
discriminables:

- `socket`: `"ok"` (fichero del socket existe) | `"missing"`.
- `ipc_responde`: `"ok"` (get_version respondió) | `"error"` | `"unknown"`
  (nivel superior falló, no se evaluó).
- `pcb_editor_abierto`: `"yes"` (get_open_documents(DOCTYPE_PCB) no-vacío)
  | `"no"` (vacío o `AS_UNHANDLED`) | `"unknown"`.

`"no"` vs `"unknown"` evita el false engañoso que un `bool` colapsaría —
"KiCad respondió que no" es semánticamente distinto de "no pude
preguntar", y ameritan acciones distintas del agente.

`bridge.has_open_pcb()` implementa el probe: `get_open_documents(DOCTYPE_PCB)`
con captura del `AS_UNHANDLED` (mapeado por D-07.2) para devolver `False`
sin propagar el error. `bridge.socket_present()` expone el fast-fail.

**Health NO sondea busy** (D-07.3): probar busy costaría un `GetItems`
real (~3 s), demasiado caro para un health check. El busy es transitorio
y se surfacea por operación vía D-07.2.

Tests unit añadidos (6):
`test_health_ipc_payload_all_ok_when_pcb_editor_open`,
`test_health_ipc_payload_pcb_no_when_no_editor_open`,
`test_health_ipc_payload_socket_missing_reports_unknown_upstream`,
`test_health_ipc_payload_ipc_error_masks_pcb_probe`,
`test_health_ipc_payload_pcb_probe_busy_degrades_gracefully`,
`test_health_ipc_payload_tokens_est_under_budget`.

**Mediciones tokens_est / latencia del health** (T3 requerida, `scratchpad/measure_health.py`):

| Escenario | `kicad_ipc` | latency_ms | tokens_est (payload completo) |
|---|---|---|---|
| KiCad ABIERTO (PCB Editor open) | `socket=ok, ipc_responde=ok, version=10.0.4, pcb_editor_abierto=yes, status=ok` | **732 ms** | **78** |
| KiCad CERRADO (socket ausente) | `socket=missing, ipc_responde=unknown, pcb_editor_abierto=unknown, status=missing, code=KICAD_NOT_RUNNING, hint=…` | **327 ms** | **113** |

- Abierto: **732 ms** total (get_version + has_open_pcb + kicad-cli
  --version + project resolution). El probe extra `has_open_pcb`
  (`get_open_documents`) es liviano; el grueso lo llevan las dos rondas
  IPC anteriores. **< 1 s budget del prompt ✓**.
- Cerrado: **327 ms**, todos los niveles cortan por el fast-fail de
  socket. Comportamiento sesión 04 intacto.
- Tokens abierto: **78** — bajo el techo de ~100 del prompt ✓.
- Tokens cerrado: **113** — 13 % arriba del techo de ~100. La contribución
  proviene del hint largo ("Abrí KiCad y habilitá el API server en
  Preferences → Plugins → Enable API server"). Trade-off aceptable: en
  la ruta cerrada el objetivo es orientar al humano, no comprimir. Si
  entra en presupuesto en la 08, cambiar el hint a "Abrí KiCad y habilitá
  el API server (Preferences → Plugins)." baja ~10 tokens.

### T4 — Cierre del gap de tests delta pcb/pcb (D-07.4)

**T4.1 unit** (`test_context_delta_pcb_live_wins_over_divergent_disk_state`).
Registra base kind=`pcb` mtimes=`None` con U1@100,50; mockea
`build_state_from_board` para devolver U1@50,60 (mutación real); mockea
`build_state_cached` para devolver U1@0,0 (divergente pero mismo kind).
Verifica que el TOON delta contiene `[~C] U1  ... x50.0 y60.0`, NO `x0.0
y0.0`. **Documenta la invariante** que ata: si alguien elimina la rama
viva de `_build_current_for`, el pipeline caería a disco y el delta
saldría con la "mutación invertida" — el test lo atrapa por CONTENIDO,
no solo por crash o kind cruzado (que era lo que atrapaba el centinela
previo).

**T4.2 integration_gui** (`test_context_delta_pcb_pcb_pipeline_after_move_footprint`).
Pipeline completo realista contra KiCad vivo: snapshot pre-mutación via
`build_state_from_board`, mutación U19 vía tool `move_footprint`,
`get_context_delta(base=snap_pre)`, verifica `[~C] U19` con la nueva
posición. Teardown con `contextlib.suppress` restaura U19 (try/finally).

**Salida TOON literal del delta pcb/pcb** (T4.2, corrida real):

```
DTOON|v1|snap:3|base:1|area:r20@U19
[~C] U19  SIM4X32  x235.3 y65.2  >- >- >- 1>GND 2>/TVRAM0 3>/TVRAM16 4>/TVRAM1 5>/TVRAM17 6>/TVRAM2 7>/TVRAM18 8>/TVRAM3 9>/TVRAM19 10>+5V 11>unconnected-(U19-NC-Pad11) 12>/MXA0 13>/MXA1 14>/MXA2 15>/MXA3 16>/MXA4 17>/MXA5 18>/MXA6 19>/MXA10 20>/TVRAM4 21>/TVRAM20 22>/TVRAM5 23>/TVRAM21 24>/TVRAM6 25>/TVRAM22 26>/TVRAM7 27>/TVRAM23 28>/MXA7 29>unconnected-(U19-NC-Pad29) 30>+5V 31>/MXA8 32>/MXA9 33>unconnected-(U19-NC-Pad33) 34>/RAS0- 35>unconnected-(U19-NC-Pad35) 36>unconnected-(U19-NC-Pad36) 37>unconnected-(U19-NC-Pad37) 38>unconnected-(U19-NC-Pad38) 39>GND 40>/CAS0- 41>/CAS1- 42>/CAS2- 43>/CAS3- 44>/RAS0- 45>unconnected-(U19-NC-Pad45) 46>unconnected-(U19-NC-Pad46) 47>/WRAM- 48>unconnected-(U19-NC-Pad48) 49>/TVRAM8 50>/TVRAM24 51>/TVRAM9 52>/TVRAM25 53>/TVRAM10 54>/TVRAM26 55>/TVRAM11 56>/TVRAM27 57>/TVRAM12 58>/TVRAM28 59>+5V 60>/TVRAM29 61>/TVRAM13 62>/TVRAM30 63>/TVRAM14 64>/TVRAM31 65>/TVRAM15 66>unconnected-(U19-NC-Pad65) 67>unconnected-(U19-PRD0-Pad67) 68>unconnected-(U19-PRD1-Pad68) 69>unconnected-(U19-PRD2-Pad69) 70>unconnected-(U19-PRD3-Pad70) 71>unconnected-(U19-NC-Pad71) 72>GND
[AREA]
U17 ok
U18 ok
```

**tokens_est del delta pcb/pcb**: **332** (según log del test). Alto por
la lista completa de pines del SIM4X32 de 72 pads. Está dentro del
presupuesto por defecto de `get_context_delta` (sin `max_tokens`, no aplica
degradación). Si se pidiera con `max_tokens=200` la cascada §4 colapsaría
posiciones y powers, o devolvería `CONTEXT_BUDGET_IMPOSSIBLE` con un hint
del mínimo estimado.

### T5 — Instrumentación de latencia de mutaciones (D-07.5)

Bridge y tools instrumentados:
- `bridge.move_footprint(..., timings=None)` — si `timings` es un dict,
  rellena `timings["lookup_ms"]` con la latencia de la búsqueda O(board)
  por ref.
- `bridge.add_track(..., timings=None)` — mismo canal para la búsqueda
  O(nets) por nombre.
- `tools.pcb.move_footprint` / `add_track` crean el dict, lo pasan al
  bridge, y lo emiten como `extra.lookup_ms` en el log JSON.

Logging aditivo, F3 intacta.

**Tabla de latencias** — 5 mutaciones consecutivas U19 vía tool
`move_footprint` contra KiCad real (`scratchpad/measure_mutation_latency.py`):

| # | latency_ms (total tool) | extra.lookup_ms (bridge) | resto (tool - lookup) |
|---|---|---|---|
| 0 | 14188.8 | 3326.4 | 10862.4 |
| 1 | 13514.5 | 3238.2 | 10276.3 |
| 2 | 13402.6 | 2901.0 | 10501.6 |
| 3 | 13466.7 | 3102.6 | 10364.1 |
| 4 | 13655.8 | 3099.7 | 10556.1 |
| μ | **13645.7** | **3133.6** | **10512.1** |

Observaciones sobre el desglose:

- El **lookup** (~3.1 s) es exactamente lo que la auditoría pre-07 midió
  para `snapshot_footprints` en idle: es el costo de una iteración
  `board.raw.get_footprints()` sobre las 189 footprints del board. La
  `move_footprint` real vía IPC (update_items) es un tail insignificante
  frente a esa iteración.
- El **resto** (~10.5 s) NO son overhead de la MCP layer: son las **otras
  tres iteraciones O(board)** que hace el tool antes y después del
  bridge.move_footprint:
  1. `bridge.list_footprint_refs(board)` (validación de existencia).
  2. `bridge.board_bbox_mm(board)` (validación de bbox).
  3. `build_state_from_board(bridge, board)` → `snapshot_footprints`
     (snapshot post-mutación para la cadena viva).
  Cada una itera 189 fps → cada una cuesta ~3 s. Sumadas: ~9 s. Con la
  búsqueda del propio move_footprint (~3 s) y el update_items, la cuenta
  cierra en ~13.5 s.
- La auditoría pre-07 midió ~3.2 s para `move_footprint` **directo sobre
  el bridge** — coherente con la iteración interna aislada. El costo vía
  tool es ~4x porque el tool hace **4 iteraciones full** por mutación.

**Propuestas de optimización para sesión 08 (no implementar en la 07):**

**Propuesta A — Consolidar iteraciones en una `snapshot_and_find(board, ref)`.**
El tool hoy hace `list_footprint_refs` + `board_bbox_mm` + move + `snapshot_footprints`
= 4 iteraciones O(board). Una operación combinada del bridge que devuelva
`(target_fp, refs_list, bbox, footprint_data_tuple)` en una sola pasada
lo colapsaría a **una** iteración (~3 s). Ahorro estimado: ~10 s por
mutación (del 74 % al 22 % del tiempo total). Costo: complica la superficie
del bridge (una única operación sirve para múltiples propósitos, viola el
principio de responsabilidad simple); requiere que la tool acepte tipos
del bridge distintos a los actuales. Compatible con la frontera regla #5
(sigue devolviendo primitivos/dataclasses). No depende de nuevas features
de kipy. **Recomendada como primer paso**: es un puro refactor de
composición, testeable sin KiCad.

**Propuesta B — Cache ref→KIID por sesión, invalidado por
`KICAD_RESTARTED`.**  kipy expone `board.get_items_by_id(ids)` que va por
GetItemsById filtrado (`kipy/board.py:384-399`). Si el bridge mantiene un
`Dict[str, KIID]` (ref → KIID) poblado en la primera lectura, y usa
`get_items_by_id([kiid])` en `move_footprint`, la búsqueda cae a O(1) por
la red (KiCad hace el filter). Ahorro estimado: ~3 s por mutación (los
otros ~10 s del resto siguen). Costos y riesgos:
- Cache stale ante mutaciones que agregan/eliminan símbolos (KiCad usa
  KIID estable por ítem, así que la ref cambia poco pero el mapeo puede
  quedar desincronizado si otro cliente muta el board por fuera).
- Invalidación en `KICAD_RESTARTED` es cheap (`self._client = None`
  también invalida el cache).
- `add_symbol` (T6, futuro) generaría nuevas KIID que el cache no conoce
  → hay que actualizarlas al momento de emitir el mutation.
- La `list_footprint_refs` que ya se ejecuta al validar puede poblar el
  cache "for free" — pero no ayuda si Propuesta A ya la consolidó.
- Sólo optimiza el **lookup** de `move_footprint`; las otras iteraciones
  (bbox, snapshot post) no cambian.

**Recomendación de orden**: A primero (baja el 74 % del tiempo con un
refactor local), B después si la 08 sigue midiendo el 22 % restante
relevante. Aisladas no se pisan; combinadas mueven el pipeline por debajo
de 1 s por mutación, según proyección lineal.

### T6 — `add_symbol` (OPCIONAL, precondición `kicad-skip` cumplida)

`grep -n "kicad-skip" pyproject.toml` → `11:    "kicad-skip>=0.1"` **✓**.

**Diferida en esta sesión.** Racional: T6 requiere implementar el diseño
completo de sesión 06 T5 (clone de template, resolución de sheet,
validaciones pre-mutación, snapshot de DISCO post-write per D-06.2, G1
backup, hazard del editor abierto documentado, verificación de efecto per
D-06.3, confirm ≤ 50 tokens) sobre un spike (spike-kicad-skip.md) que
explícitamente marca lagunas: pick de librería no probado, conexión de
pines no probada, interacción con el board no probada, colisión con el
Snapshot Store no resuelta. Priorizar el DoD completo de T1–T5 (retry,
health, delta test, instrumentación) y su reporte es el trade-off correcto
dado el scope. Se recomienda para la 08 con el spike como punto de partida
y decisiones explícitas del arquitecto sobre las 4 lagunas del spike.

## Definition of Done

```
uv run pytest -m "not integration and not integration_gui"  → 101 passed
uv run pytest -m integration                                → 20 passed en 4:16 (< 5:00)
uv run pytest -m integration_gui                            → 4 passed en 1:02 (incluye nuevo T4.2)
uv run mypy src/                                            → Success (30 files)
uv run ruff check src/ tests/                               → All checks passed
uv run ruff format --check src/ tests/                      → clean (48 files)
```

- **101 unit tests** (85 base + 4 T1 + 5 T2 + 6 T3 + 1 T4.1) — sin
  regresiones.
- **20 integration** — 4:16 (256 s). Bajo el techo 5:00 del DoD. Varianza
  con la auditoría (3:41–3:50) dentro del rango observado histórico
  (201–256 s). No hay candidatos a `integration_slow`.
- **4 integration_gui** — 1:02, incluye el nuevo `test_context_delta_
  pcb_pcb_pipeline_after_move_footprint` (T4.2).
- **mypy** — 30 files, sin errores, strict.
- **ruff** — check + format, clean.

## Promedios de tokens (post-07)

| Métrica | Valor | Presupuesto | Estado |
|---|---|---|---|
| Confirm `move_footprint` (unit) | 13 | ≤ 50 (ADR-0004) | ✓ |
| Confirm `add_track` (unit) | 18 | ≤ 50 (ADR-0004) | ✓ |
| `health` KiCad abierto | 78 | ≤ ~100 (D-07.3) | ✓ |
| `health` KiCad cerrado | 113 | ≤ ~100 (D-07.3) | ⚠ (13 %) |
| `get_context_delta` pcb/pcb (72 pads) | 332 | ≤ 400 promedio global (D4) | ✓ |

**Promedios D4/ADR-0004 cumplidos**: confirms ≤ 50 (máximo observado 18),
global ≤ 400 (delta pcb/pcb con muchos pines llega a 332). El único
overrun es health cerrado en 113 vs ~100 — trade-off del hint accionable
sobre compresión (ver §T3).

## Dudas abiertas y candidatos para sesión 08

1. **Optimización de mutaciones (D-07.5, decisión pendiente).** Propuestas
   A y B en §T5. La 07 midió y propuso; la 08 decide y ejecuta. Con la
   telemetría `extra.lookup_ms` ahora en producción, el arquitecto tiene
   datos para elegir cuánto invertir.
2. **`add_symbol` (T6, diferido).** kicad-skip presente en pyproject;
   spike sesión 05 marcó 4 lagunas de diseño. Prompt de la 08 tendría
   que decidir explícitamente sobre cada laguna antes de codificar:
   - Librería fija o pick por parámetro.
   - Conexión de pines: manual con `connect_pins` (v0.3) o parte de
     `add_symbol`.
   - Interacción con `.kicad_pcb`: `add_symbol` toca solo sch por ahora.
   - Colisión con el Snapshot Store: ¿snapshot vivo desde disco
     recién escrito, o snapshot que fuerza re-sync?
3. **Eval A (TOON vs alternativas).** Sigue pendiente desde sesión 06.
   Sesión de dev calma para hacerlo (0 flakes en 90 tests integration +
   100 lecturas IPC en la auditoría; suite verde estable en la 07).
4. **Retry para `add_track`.** El wrapper de retry no aplica hoy porque
   `add_track` es mutación. Pero la mutación tiene una lectura previa
   (net lookup) — si esa lectura sufre busy, se propaga inmediatamente.
   La 08 podría considerar si conviene un retry sólo para la parte de
   lookup, con la clara semántica de que el `create_items` posterior sí
   es no-idempotente.
5. **Hint largo del health cerrado.** Ver §T3, presupuesto de ~100 tokens.
   Fácil de arreglar en 1 línea si la 08 quiere ajustarlo.
6. **Anchor point de `has_open_pcb` en el catálogo.** La tool `health`
   documenta el output, pero la tool no expone `has_open_pcb` como MCP
   tool separada — está usada solo dentro de `_ipc_payload`. Si la 08
   quisiera exponerla como probe estable (útil para agentes que
   pre-flighteen antes de mutar), sería aditivo, F3 intacta.
