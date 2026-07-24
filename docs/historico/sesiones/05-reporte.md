# Reporte de sesión 05 — ΔTOON + snapshots vivos post-mutación

**Fecha:** 2026-07-10 · **Rama:** `sesion-05` · **Commits:** 6 (uno por
tarea + `.gitignore` del spike) · **Estado:** DoD cumplido en las cinco
tareas de núcleo + spike opcional entregado, sin push.

## Qué se completó

### Fase 0 — verificación del entorno

`python3 scripts/verificar_entorno.py` → 10 OK · 1 WARN · 0 FAIL. El WARN
es `npx` ausente (Inspector interactivo — no requerido para el MVP).
Suite de arranque: `pytest -m "not integration and not integration_gui"`
→ **58 passed, 1 xfailed** (el golden 003 a des-xfailear).

### Tarea 1 — Endurecimiento de `_map_ipc_failure`

- `type(exc).__module__.startswith("kipy")` complementa el chequeo por
  `__qualname__`. Contrato del import perezoso de `kipy` intacto.
- Tests unit: excepción sintética con `qualname="ConnectionError"` y
  `module="requests.exceptions"` mapea a `KICAD_CLI_FAILED` (no a
  `KICAD_NOT_RUNNING`); la variante con `module="kipy.errors"` mapea a
  `KICAD_NOT_RUNNING` (positivo preservado).

### Tarea 2 — Snapshots vivos (`mtimes=None`)

- `SnapshotEntry.mtimes: dict[str, int] | None`. `SnapshotStore.register`
  acepta el sentinel; se preserva copia defensiva cuando llega un dict.
- Lógica de validación extraída a `snapshots/validation.validate_base_snap`
  para reutilizar en `get_context_delta` (T4). Snapshots vivos omiten
  el chequeo de mtime; snapshots de disco siguen disparando
  `EXTERNAL_EDIT_DETECTED`.
- `KicadMcpError` gana un parámetro opcional `data: dict[str, Any] | None`
  que se expone en `to_dict()`. `SNAPSHOT_STALE` viaja con
  `{"base_snap": ..., "retention": ...}` — F3 intacta (código no
  renombrado), el agente correlaciona el fallo con su plan sin parsear
  el mensaje.
- **ADR-0007** documenta la decisión, el falso positivo que evita (Save
  posterior del agente sobre su propia cadena), y la limitación
  aceptada (ediciones externas concurrentes indetectables sobre un
  snapshot vivo). Alternativa (hash del board de kipy) diferida hasta
  medir el hueco (D-05.2).
- Tests unit (4): registro vivo, validación omitida para vivos,
  validación intacta para snapshots de disco, `data` estructurado en
  `SNAPSHOT_STALE`.

### Tarea 3 — `snapshots/delta.py` + des-xfail golden 003

- `compute_delta(prev, curr) -> Delta` puro y determinista. Buckets
  `added`/`removed`/`updated` con natural key, `nets_changed` con "poder
  primero, resto alfabético" (spec §2). `lib` NO cuenta como update
  (no se emite en TOON, spec §2).
- `toon/encoder.encode_delta` reemplaza el placeholder: emite
  `[+]`/`[-]`/`[~C]`/`[~N]` en ese orden y la sección `[AREA]` con el
  umbral 20 refs (spec §3).
- `toon/encoder.encode_delta_with_budget` — variante con degradación
  §4 (colapso de poder → omisión de posiciones) que consume T4.
- **Golden 003 pasó byte a byte a la primera**, sin discrepancias con
  la spec. `git log --oneline -- tests/golden/` sigue mostrando cero
  commits de esta sesión → F1 intacta.
- Tests unit (8) del `compute_delta`: identidad, add puro, remove puro,
  update de posición, cambio de net en el mismo componente, combinado
  (con test de sort natural `C10 > C2`), cambio sólo de `lib` no cuenta,
  determinismo entre dos corridas.
- Test `test_golden_003_delta_is_deterministic_across_two_runs` corre
  `encode_delta` dos veces con el mismo input y verifica igualdad de
  bytes (invariante contra `PYTHONHASHSEED`).

### Tarea 4 — Tool `get_context_delta`

- `tools/world.get_context_delta(base_snap, focus_ref, radius_mm, max_tokens?)`:
  1. `validate_base_snap` (reusa la lógica de T2) → `SNAPSHOT_STALE` con
     `data` estructurado, o `EXTERNAL_EDIT_DETECTED` cuando corresponde.
  2. Reconstruye el estado actual vía `build_state_cached` (mismo camino
     de disco que `get_world_context`).
  3. Registra el estado como snapshot fresco (mtimes de disco, no vivo
     — aquí sí sabemos si el disco cambió porque venimos de leerlo).
  4. Emite `encode_delta` o `encode_delta_with_budget` según pase
     `max_tokens`. `CONTEXT_BUDGET_IMPOSSIBLE` como fallback (D-05.5).
  5. La cabecera declara `snap:<nuevo>|base:<viejo>`.
  6. Logging JSON: `tool_name`, `snap_id=nuevo`, `extra.base_snap=viejo`,
     `tokens_est`, `latency_ms`.
- Catálogo (`docs/specs/tool-catalog.md`, DoD #2): entrada nueva en
  `world`, notas del payload estructurado, snapshots vivos, ejemplo de
  salida contra el golden 003. `get_context_delta` removida de "Nombres
  reservados" (ya implementada).
- Tests: 6 unit (SNAPSHOT_STALE sin tocar el builder, EXTERNAL_EDIT,
  snapshot vivo salta el chequeo, registro de nuevo snap con eco en
  cabecera, CONTEXT_BUDGET_IMPOSSIBLE con max_tokens=1, catálogo
  documenta la tool) + 3 integration (delta vacío contra 001, [+] contra
  base sintético recortado, logging estructurado captura ambos snaps).

### Tarea 5 — Snapshot vivo post-mutación (D-05.6 no activado)

- Nuevas dataclasses `FootprintData` / `FootprintPadData` en `bridge/ipc.py`
  — datos primitivos (nunca tipos de kipy fuera del bridge).
- `IpcBridge.snapshot_footprints(board)` recorre `fp.definition.pads`,
  extrae `pad.number` y `pad.net.name`, todo bajo el lock del bridge.
- `bridge/state_builder.build_state_from_board(bridge, board)` — camino
  paralelo al que lee de disco (`build_state_cached`). Función separada,
  no flag, como pide el prompt. Devuelve `NormalizedState(kind="pcb")`.
- `tools/pcb.move_footprint` y `tools/pcb.add_track`: tras la mutación
  exitosa, reconstruyen desde el board vivo, registran con `mtimes=None`
  y ecoan el nuevo `snap_id` en el confirm y en el audit. El `base_snap`
  del pedido se preserva en `.kicad-mcp/audit.jsonl` (params).
- **Confirms medidos (post-mutación):** `move_footprint` = 13 tokens,
  `add_track` = 18 tokens. Ambos ≤ 50 (ADR-0004).
- Tests: 2 unit para `build_state_from_board` (con pines / vacío) + 4
  tests existentes ajustados al nuevo contrato + nuevo `integration_gui`
  `test_move_footprint_tool_returns_confirm_with_positive_snap_id` que
  ejerce la tool MCP con KiCad real y verifica `[snap:N]` con `N > 0`.
- **Gate D-05.6 NO activado.** El path in-memory entró en la sesión sin
  comprometer el cierre; queda con cobertura unit + un `integration_gui`
  listo para el humano bajo las mismas envs que sesión 04.

### Tarea 6 (opcional) — Spike kicad-skip

Entregable: `scratchpad/spike-kicad-skip.md` con hallazgos concretos.
Venv descartable en `scratchpad/spike-venv/` (F5 respetada: `pyproject.toml`
intacto). Trabajo sobre `scratchpad/004_copy/`, fixture original inmune.

**Hallazgos resumidos:**

- Parse fidelity ✓: root + 7 hojas jerárquicas + 395 símbolos totales
  se cargan sin errores. Requiere ir por `sh.property` para
  `Sheetname`/`Sheetfile` (los atributos-shortcut devuelven `None` en
  esta versión).
- Write round-trip ✓: `clone()` + `at.value = [...]` + `Reference.value = ...`
  + `write()` genera un archivo re-leíble con el conteo esperado.
  Archivo `scratchpad/rams_added.kicad_sch` queda para verificación en
  GUI por el humano.
- **Recomendación preliminar sobre `add_symbol` en sesión 06:** viable
  **condicional a la validación GUI**. Bloqueadores conocidos: pick
  desde librerías externas y cableado a un net existente no cubiertos
  por el spike; interacción con el snapshot store dispararía
  `EXTERNAL_EDIT_DETECTED` sobre la propia cadena a menos que se
  extienda el patrón T5 al camino `add_symbol`.

## Definition of Done

```
uv run pytest -m "not integration and not integration_gui"  → 82 passed, 0 xfailed  ✓
uv run pytest -m integration                                → 20 passed en 2:44 s   ✓
uv run mypy src/                                            → Success (30 files)    ✓
uv run ruff check src/ tests/ scripts/                      → All checks passed     ✓
uv run ruff format --check src/ tests/ scripts/             → clean                 ✓
```

Golden 003 corrido dos veces consecutivas en el mismo job (test
dedicado `test_golden_003_delta_is_deterministic_across_two_runs`) →
bytes idénticos.

## Discrepancias con el golden 003

**Ninguna.** El encoder produjo el output esperado byte a byte en la
primera corrida. `git log --oneline -- tests/golden/` sigue mostrando
un único commit (el `chore: estado inicial` de la creación del repo).
F1 intacta.

## Mediciones de tokens

`get_context_delta` (estimador `len/3.5`):

| Escenario | tokens_est |
|---|---|
| Delta vacío contra 001 (r=200@U1) | 20 |
| Delta 002 con `-1 comp` (r=200@U1) | 106 |
| Delta 003 con `-1 comp` (r=30@J1, `max_tokens=500`) | 308 |

- `get_context_delta` sobre un mundo sin cambios cuesta ~20 tokens
  (cabecera DTOON + bloque `[AREA]` con 5 refs); frente a un
  `get_world_context` completo de 001 (~140-160 tokens según degradación)
  es ~7-8× más barato.
- Con budget forzado en 003, el mecanismo §4 aplica colapso de poder y
  degrada dentro del presupuesto (308 tokens con budget 500 → margen del
  factor de seguridad 0.9).
- Confirms de mutaciones: 13 (`move_footprint`) y 18 (`add_track`).
  Ambos ≤ 50 (ADR-0004). Promedio global de la sesión (delta vacío + 2
  deltas + 2 confirms) = **≈ 93 tokens/tool_call**, muy por debajo del
  D4 (≤ 400).

## Tiempos de suite

| Suite | Sesión 04 | Sesión 05 |
|---|---|---|
| `not integration and not integration_gui` | 2.2 s | 2.8 s |
| `integration` | 173 s (17 tests) | 164 s (20 tests) |

`integration` ejercita tres nuevos tests (`test_context_delta_*`), suma
~26 s en promedio por test (kicad-cli por invocación), y se acomoda
por debajo del umbral de 5 min del prompt. Sin necesidad de partir el
marker.

## Dudas abiertas y candidatos argumentados para sesión 06

1. **`add_symbol` con kicad-skip** (candidato principal). Requiere:
   - Verificación GUI del archivo `rams_added.kicad_sch` (paso del humano
     descrito en `scratchpad/spike-kicad-skip.md`).
   - Diseño del flujo: ¿cómo interactúa con el Snapshot Store dado que
     modifica `.kicad_sch` en disco? Alternativas: registrar un
     snapshot vivo post-write (mismo patrón T5, adaptado al camino de
     kicad-skip) o forzar re-sync explícito.
   - Definir la superficie mínima: `add_symbol(sheet, lib, ref, x, y)`
     con placement básico; el cableado (`connect_pins`) queda para v0.5.
   - Aprobación humana de la dependencia (F5).

2. **Hash del board de kipy para detectar ediciones sobre snapshots vivos**
   (diferido en D-05.2). Se activa si se mide falso negativo real; por
   ahora el análisis del scope creep quedó en el ADR-0007.

3. **Eval A (TOON vs CSV vs JSON compacto)** (mencionada como candidata
   secundaria del día 5). No se avanzó; sigue siendo el trabajo natural
   para validar la elección del formato ahora que el pipeline delta
   está cerrado.

4. **Depuración en `state_builder`**: el flag `_ = ref` de la función
   `_build_pins` es rara; podría limpiarse en sesión 06 con ownership de
   `bridge/state_builder.py`. No urgente.

5. **Fuera-de-área en deltas**: hoy `encode_delta_with_budget` no
   aplica el nivel §4.2 (`[FUERA_DE_AREA]`) porque el delta ya está
   semánticamente localizado (el foco lo define el llamador). Si un
   proyecto grande genera deltas gordos, hay que decidir si emitir un
   resumen equivalente para las nets tocadas fuera del radio. Pendiente
   de medir.
