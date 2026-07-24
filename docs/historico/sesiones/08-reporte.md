# Reporte de sesión 08 — Mutaciones rápidas (≤4 s) + `add_symbol`

**Fecha:** 2026-07-10 · **Rama:** `sesion-08` (sin push)
**Base:** `master @ 28f081b` (post-merge sesión 07 + prompt sesión 08).
**Entorno vivo:** KiCad 10.0.4 con PCB Editor abierto sobre
`/tmp/gui-test-project/video.kicad_pcb`, API server habilitado. Env vars
`KICAD_MCP_GUI_TEST=1`, `KICAD_MCP_PROJECT=/tmp/gui-test-project`,
`KICAD_MCP_GUI_REF=U19`, `KICAD_API_SOCKET=ipc:///tmp/kicad/api.sock`.

## Fase 0 — verificación

`python3 scripts/verificar_entorno.py` → 10 OK · 1 WARN · 0 FAIL (`npx`
para el Inspector, no requerido). Suite de arranque `pytest -m "not
integration and not integration_gui"` → 101 passed. Línea base de
latencia con la telemetría de la sesión 07 (`scratchpad/baseline_08.py`):

| # | latency_ms (total tool) | lookup_ms | resto |
|---|---|---|---|
| 0 | 15956.8 | 3058.6 | 12898.2 |
| 1 | 14845.5 | 2615.7 | 12229.8 |

μ ≈ **15.4 s**, coherente con la ~13.6 s reportada en la 07 (variación
por primer G1 backup y JIT).

## Estado por tarea

| Tarea | Estado | Commit |
|---|---|---|
| T1 `read_board_context` compuesta (D-08.1) | ✅ | siguiente |
| T2 Post-estado derivado + verificación puntual (D-08.2) | ✅ | siguiente |
| T3 Medición final ≤4 s (D-08.4) | ✅ | (mismo) |
| T4 `add_symbol` (D-08.5) | ✅ | siguiente |
| T5 Hint health cerrado (D-08.6) + catálogo | ✅ | siguiente |
| T6 (OPCIONAL) Eval A: TOON vs alternativas | ⏭ diferida | — |

Los cambios se agrupan en dos commits: bridge/tools/pcb (T1+T2+T3) y
sch/T4+T5. El humano puede reordenar antes del push.

### T1 + T2 — `read_board_context` + post-estado derivado (D-08.1/D-08.2)

**Bridge — nueva superficie.**

- `BoardContext` dataclass: `(refs, bbox, footprints)` — resultado de
  UNA sola pasada por `get_footprints()`.
- `FootprintData.kiid: str = ""` (aditivo, default retrocompat): captura
  el UUID de KiCad durante la pasada compuesta. Fuente única de la
  conversión kipy → primitivos en `_footprint_to_data(...)` (evita la
  duplicación previa entre `snapshot_footprints` y la nueva lectura).
- `IpcBridge.read_board_context(board) -> BoardContext`: whitelist
  `_IDEMPOTENT_OPS` (retry-elegible ante `AS_BUSY`, D-08.3). Cero
  cambios estructurales al retry existente.
- `IpcBridge.verify_footprint_by_kiid(board, kiid) -> FootprintData |
  None`: usa `get_items_by_id([kiid_proto])` (kipy `board.py:384-399`).
  Filtro del lado de KiCad; O(1) de red. Whitelisted.
- `IpcBridge.move_footprint(..., kiid: str | None = None, ...)`: con
  KIID resuelto, salta la iteración O(board). Sin KIID, mantiene el
  path histórico (para tests unit legacy y llamadas ad-hoc).

**Tools — pipeline nuevo.**

`tools/pcb.move_footprint`:

1. `ctx = bridge.read_board_context(board)` — UNA pasada O(board).
2. Validaciones (`refs`, `bbox`) + `_find_target(ctx.footprints, ref)`.
3. G1 backup.
4. `bridge.move_footprint(..., kiid=target.kiid)` — cero iteraciones
   nuevas (usa `get_items_by_id`).
5. `_register_post_snapshot(...)`:
   - Deriva el post-estado localmente
     (`_derive_post_state(ctx.footprints, ref, x, y)`).
   - Verifica por KIID (`verify_footprint_by_kiid`), tolerancia ±1 nm.
   - Match → registra el snapshot derivado (`build_state_from_snapshot`).
   - Divergencia o KIID desaparecido → warning `post_snapshot_fallback`
     + re-lectura completa vía `snapshot_footprints` (fallback).
6. Log JSON con `extra.read_ms`, `extra.lookup_ms`, `extra.verify_ms` y
   `extra.post_fallback` cuando corresponde.

`tools/pcb.add_track`: mismo `read_board_context` para bbox; el
`list_net_names` sigue aparte (pasada sobre `get_nets`, no
`get_footprints`). Post-snapshot ahora se DERIVA del pre — como
`add_track` no altera la lista de componentes, `build_state_from_snapshot(ctx.footprints)`
es equivalente sin re-lectura.

**`state_builder`.** Nuevo helper `build_state_from_snapshot(footprints:
tuple[FootprintData, ...]) -> NormalizedState`. `build_state_from_board`
queda como delegado (`snapshot_footprints` + helper) — fallback path y
tests legacy.

### T3 — Medición final (D-08.4)

`scratchpad/measure_mutation_latency.py` (5 mutaciones U19 contra KiCad
real):

| # | latency_ms (total tool) | read_ms | lookup_ms (KIID) | verify_ms | resto |
|---|---|---|---|---|---|
| 0 | 4281.7 | 3553.7 | 67.2 | 156.7 | 504.1 |
| 1 | 3265.2 | 2740.9 | 43.4 | 114.3 | 366.6 |
| 2 | 3113.5 | 2628.9 | 42.8 | 147.6 | 294.2 |
| 3 | 3253.6 | 2551.6 | 55.0 | 271.3 | 375.7 |
| 4 | 3500.8 | 2960.9 | 57.4 | 163.8 | 318.7 |
| μ | **3483.0** | **2887.2** | **53.2** | **170.7** | **371.9** |

**Comparativa sesión 07 vs sesión 08 (μ):**

| Métrica | Sesión 07 | Sesión 08 | Δ |
|---|---|---|---|
| Total por mutación vía tool | 13645.7 ms | 3483.0 ms | **-74 %** |
| Pasadas O(board) por mutación | 4 | 1 | -3 |
| Lookup del target | 3133.6 ms (iterar) | 53.2 ms (KIID) | -98 % |
| Snapshot post | ~3.1 s (re-lectura) | 170.7 ms (KIID) | -95 % |

**Objetivo D-08.4 (≤4 s) cumplido**: μ 3.5 s por debajo del techo, con la
única excepción de la primera medición (4.28 s por warmup + G1 backup).
Las 4 siguientes están entre 3.1 y 3.5 s.

Sobre los scripts de la 07 en `scratchpad/`:

- `measure_mutation_latency.py`: sigue vigente, muestra `lookup_ms` y
  el desglose. Los nuevos canales `read_ms`, `verify_ms` viajan en el
  log JSON pero no se muestran en la tabla del script (para no cambiar
  el formato del reporte). Candidato a extensión menor si otra sesión
  quiere granularidad total en la salida cruda.
- `measure_health.py`: sigue vigente sin cambios (mide el token count
  de payload health cerrado y abierto).
- `baseline_08.py`: nuevo, usado para la Fase 0 de esta sesión. Puede
  archivarse tras el push.

### T2b — Mini-verificación empírica D-08.2

`scratchpad/verify_derivation.py` (3 moves U19, comparando pedido vs
leído por KIID):

| # | target_x | target_y | live_x | live_y | dx_nm | dy_nm |
|---|---|---|---|---|---|---|
| 0 | 235.458 | 65.278 | 235.458 | 65.278 | 0.0 | 0.0 |
| 1 | 235.585 | 65.405 | 235.585 | 65.405 | 0.0 | 0.0 |
| 2 | 235.712 | 65.532 | 235.712 | 65.532 | 0.0 | 0.0 |

**KiCad NO redondea**: 3/3 exactos al nm. La derivación local es
correcta. El fallback a re-lectura completa **no disparó ninguna vez**
en los tests integration_gui ni en la medición T3 sobre el board real.

### Test contador (D-08.1/D-08.2 requerido)

`tests/test_pcb.py::test_move_footprint_makes_exactly_one_pre_pass_zero_post_pass`:

```
assert bridge.get_footprints_calls == 1  # 1 pasada pre, 0 post
assert bridge.get_footprints_by_id_calls == 1  # verificación puntual
```

Passing. Refuerzos:

- `test_move_footprint_registers_derived_post_snapshot`: verifica que
  el snapshot registrado refleja la mutación aunque no haya re-lectura.
- `test_move_footprint_falls_back_to_full_read_on_divergence`: simula
  divergencia +5 mm → contador reporta 2 pasadas (1 pre + 1 fallback),
  el snapshot registra la posición live (no la derivada).

### T4 — `add_symbol` (D-08.5)

`src/kicad_mcp/tools/sch.py` — nueva categoría `sch`, registrada en
`tools/__init__.py::register_all`.

Superficie: `add_symbol(sheet, lib_id, ref, x_mm, y_mm, base_snap?) -> str`.

**Pipeline.**

1. Sanitizar `ref` (regla 6): regex
   `^[A-Za-z][A-Za-z0-9_]{0,14}[0-9]$`. Refs con backticks, pipes,
   espacios, chars de control → `INVALID_PARAMS`.
2. Canonicalizar `sheet` bajo el project root (regla 4);
   `PATH_OUTSIDE_PROJECT` si escapa.
3. Recolectar refs de TODAS las hojas (`_collect_all_refs`). Colisión →
   `INVALID_PARAMS` + hint con la hoja donde ya vive el ref.
4. Bbox de la hoja (símbolos existentes + 200 mm de margen). Coord fuera
   → `INVALID_PARAMS`.
5. Localizar template por `lib_id` en la hoja. Ausente → `INVALID_PARAMS`
   + hint con lib_ids disponibles.
6. Snapshot pre-mutación del proyecto vía `build_state_cached`.
7. G1 backup.
8. Write con kicad-skip: `template.clone()` + `Reference` + `at`.
9. Verificación de efecto (D-06.3): re-lee el sch, chequea presencia +
   `lib_id` + coordenadas (tolerancia 1e-3 mm).
10. **Post-estado derivado localmente** (motivo detallado abajo).
11. Registro en el Snapshot Store con **mtimes frescos del disco**
    (D-06.2 / D-08.5 #4).
12. Confirm + audit JSONL + log JSON.

**Motivo de la derivación (importante).** `kicad-cli sch export netlist`
NO incluye el símbolo recién añadido: KiCad re-anota jerarquía al abrir
el sch, hasta entonces el netlist devuelve solo los "componentes" con
Reference ya bindeada por su `sheet_instances`. Reconstruir el
post-estado con `build_state_cached` explota con
"posición sin netlist: <ref>". La derivación local es fiel al
contrato de D-08.5 #2 (`add_symbol` no conecta): el componente nuevo
aparece con todos sus pines `net=None`, y KiCad los re-conectará
cuando el usuario abra el sch. Los pines los saco del `lib_symbols`
del archivo (`_pin_ids_of_lib_id`, ya presente en el sch por
kicad-skip).

**Confirm literal** (medido en test unit sobre 001_basico):

```
OK add_symbol R99 FIXLIB:R2 @(175.0,60.0) in fixture.kicad_sch [snap:1]
```

`tokens_est` = **20** (bajo el techo ≤ 50 de ADR-0004).

**Verificación de efecto (D-06.3), output del test unit:**

```
{"tool_name":"add_symbol","snap_id":1,"tokens_est":20,"latency_ms":1002.119,
 "ref":"R99","lib_id":"FIXLIB:R2","sheet":"fixture.kicad_sch",
 "base_snap":null,"backup_already_done":false,"sheet_total":6}
```

`sheet_total: 6` = 5 (originales de 001_basico) + 1 (R99 nuevo).
El símbolo se localiza por Reference, se valida su `lib_id`, y su
posición se compara con lo pedido — sin divergencia.

**Archivo generado para inspección visual del humano:**

- Ruta: `/tmp/add-symbol-demo/fixture.kicad_sch`.
- Generador: `scratchpad/add_symbol_demo.py`.
- Abrir en KiCad 10 con:
  ```bash
  xdg-open /tmp/add-symbol-demo/fixture.kicad_sch
  ```
- Esperado: 5 símbolos originales + R99 (FIXLIB:R2) en (175, 60).

**Tests unit** (`tests/test_sch.py`, 8 casos, todos pass):

- Happy path sobre 001_basico (`FIXLIB:R2 → R99`).
- Snapshot post-write con `mtimes != None` (D-06.2 / D-08.5 #4).
- Colisión ref en la MISMA hoja (`R1` ya existe).
- Colisión ref CROSS-SHEET sobre 004_real (multi-hoja, `U1`).
- `lib_id` ausente en la hoja → hint con los disponibles.
- Coordenada absurda → hint con rango permitido.
- Ref con caracteres inválidos → regla 6.
- `sheet` fuera del root → regla 4.

**Hazard del editor abierto**: documentado en catálogo (§ `sch`) y
docstring de `tools/sch.py`. El usuario con el sch abierto en KiCad ve
un aviso "cambió en disco, ¿recargar?" — MVP documenta, no resuelve.

### T5 — Hint del health cerrado (D-08.6) + docs

`tools/meta._ipc_payload`: hint del socket ausente pasa de

```
"Abrí KiCad y habilitá el API server en Preferences → Plugins → Enable API server."
```

a

```
"Abrí KiCad y habilitá el API server (Preferences → Plugins)."
```

**tokens_est del health cerrado**: **107** (era 113 en la 07). El techo
del prompt era ~100; quedamos 7 % arriba, ~6 tokens ganados. Acortar
más pierde accionabilidad — la parte "Preferences → Plugins" es el
handoff concreto. Trade-off aceptable.

Catálogo `docs/specs/tool-catalog.md`:

- Nueva subsección `pcb` §"Sesión 08 D-08.1/D-08.2 — pipeline rápido"
  con la explicación de la operación compuesta, derivación y
  telemetría (`read_ms`, `verify_ms`, `post_fallback`).
- Nueva categoría `sch` con la entrada completa de `add_symbol`
  (parámetros, errores posibles, decisiones vinculantes D-08.5,
  validaciones pre-mutación, verificación de efecto, hazard del editor
  abierto).
- Sección "Nombres reservados" actualizada: `add_symbol` sale de v0.2
  reservado y entra en `sch` implementada.

F3 intacta: no se renombró ningún código; se documentaron canales
`data.*` existentes y aditivos.

## Definition of Done

```
uv run pytest -m "not integration and not integration_gui"  → 112 passed
uv run pytest -m integration                                → 20 passed en 4:xx (< 5:00)
uv run pytest -m integration_gui                            → 4 passed
uv run mypy src/                                            → Success (31 files, strict)
uv run ruff check src/ tests/                               → clean
uv run ruff format --check src/ tests/                      → clean
```

- **112 unit tests**: 101 base + 3 nuevos T1/T2 (`test_pcb.py`, contador
  de pasadas + derivación + fallback) + 8 nuevos T4 (`test_sch.py`).
- **20 integration**: sin cambios.
- **4 integration_gui**: incluye el T4.2 de la sesión 07 (delta pcb/pcb
  tras `move_footprint`); pasa sin cambios de semántica.
- **mypy strict**: `# type: ignore[import-untyped]` una única vez en el
  primer `from skip import Schematic` (kicad-skip 0.2 no publica
  py.typed).

## Promedios de tokens (post-08)

| Métrica | Valor | Presupuesto | Estado |
|---|---|---|---|
| Confirm `move_footprint` (unit) | 13 | ≤ 50 (ADR-0004) | ✓ |
| Confirm `add_track` (unit) | 18 | ≤ 50 | ✓ |
| Confirm `add_symbol` (unit, 001_basico) | 20 | ≤ 50 | ✓ |
| `health` KiCad abierto | 78 | ≤ ~100 (D-07.3) | ✓ |
| `health` KiCad cerrado | 107 | ≤ ~100 (D-08.6) | ⚠ (7 %) |
| `get_context_delta` pcb/pcb (72 pads) | 332 | ≤ 400 promedio global | ✓ |

Confirms promedio: 17 (todos ≤ 20, techo 50 muy holgado). Global ≤ 400
mantenido. Único overrun: health cerrado 107 vs 100 (mejorado desde
113, ver §T5).

## Dudas abiertas y candidatos argumentados para sesión 09

1. **Fallback empírico jamás disparado.** En 5 mutaciones reales (T3) +
   3 mini-verificaciones (T2b) + integration_gui: 0 fallbacks. La
   derivación local es correcta al nm en el board de 202 refs. Si en la
   09 aparece un caso donde KiCad clampea (fuera del bbox del board,
   snap grid del PCB Editor, etc.), la telemetría `post_fallback` en el
   log JSON permite detectarlo sin cambiar código. Candidato: sumar el
   contador de fallbacks en un metric agregado a `health` para
   monitoreo pasivo.

2. **Cache ref → KIID (Propuesta B de la sesión 07).** No se implementó
   en la 08 porque `get_items_by_id` sobre un único KIID capturado en la
   misma request compuesta ya rinde ~53 ms (contra los ~3 s originales
   del lookup iterativo). El cache ganaría milisegundos, no segundos.
   Candidato: descartar la Propuesta B hasta que una medición futura
   muestre que la lectura compuesta (2.8 s) es el nuevo cuello.

3. **`connect_pins` (v0.5).** El terreno está listo: `add_symbol`
   coloca símbolos sin conexiones (Pin(p=..., net=None)); el próximo
   paso natural es cablear a un net existente. Requiere abrir la
   pregunta "¿escribimos un wire en el `.kicad_sch` con kicad-skip, o
   asignamos la net del pin del sym instance directamente?" —
   Investigación de sesión 09.

4. **Sync sch↔pcb tras `add_symbol`.** MVP documenta el hazard pero no
   lo resuelve. El agente que coloque un símbolo en el sch y quiera
   verlo en el pcb debe pedirle al humano correr "Update PCB from
   Schematic" en KiCad. Candidato: introducir una tool sin efecto
   (`reload_in_gui`, ya reservada) que le dé al agente lenguaje para
   pedir eso explícitamente.

5. **Aceptación pragmática del bbox del board.** Sigue basado en
   footprints + margen 100 mm. Para el board de 202 refs y su Edge.Cuts
   presente, sería más correcto leer `board.edge_cuts` de kipy. Sesión
   05 lo dejó anotado como "MVP acepta bbox amplio". Sigue vigente.
   Candidato menor.

6. **Eval A (TOON vs alternativas).** Diferida por 3ª sesión. Sesión 08
   no la corrió: prioridad fue exprimir la latencia (D-08.4) y
   `add_symbol`. Si la 09 baja el pulso (retry acotado + operación
   compuesta + derivación son piezas estables), la eval podría entrar
   como investigación en paralelo a `connect_pins`.

7. **`base_snap` en `add_symbol`.** Soportado (chequeo de
   `SNAPSHOT_STALE` / `EXTERNAL_EDIT_DETECTED` con el sch raíz), pero
   NO cubierto por test unit. En la 09, si `connect_pins` continúa la
   cadena de mutaciones sch, agregar un test unit del happy path con
   `base_snap` sería el equivalente de lo que `test_snapshots_store.py`
   hace para `move_footprint`.

8. **Refactor menor del script `measure_mutation_latency.py`.** La
   tabla que produce muestra `latency`, `lookup`, `resto`. Los canales
   nuevos `read_ms` y `verify_ms` viajan en el JSON pero no en la
   tabla; extender el script mostraría el desglose completo sin
   perder retrocompat de la 07. Trivial pero no vino con la 08.
