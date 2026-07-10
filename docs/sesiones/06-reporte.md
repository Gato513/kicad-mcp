# Reporte de sesión 06 — Persistencia real de mutaciones + delta kind-aware

**Fecha:** 2026-07-10 · **Rama:** `sesion-06` · **Estado:** DoD cumplido en las
cuatro tareas de núcleo (T5 no habilitada por precondición dura, F5).

---

## Fase 0 — verificación del entorno

`python3 scripts/verificar_entorno.py` → 10 OK · 1 WARN · 0 FAIL. WARN es
`npx` ausente (Inspector interactivo, no requerido para el MVP). Env vars
del prompt presentes en el shell: `KICAD_MCP_GUI_TEST=1`,
`KICAD_MCP_PROJECT=/tmp/gui-test-project`, `KICAD_MCP_GUI_REF=U19`,
`KICAD_API_SOCKET=ipc:///tmp/kicad/api.sock`.

Baseline reproducida antes de tocar código:

- Smoke `integration_gui -k version` → PASS (kipy 0.7.1 ↔ KiCad 10.0.4 se
  hablan bien).
- `integration_gui -k round_trip` → FAIL (línea base del bug T1).

---

## Veredicto del bug T1 y fix

### Discriminación H1 vs H2

- **H1 histórica ("kipy requiere `begin_commit()` explícito"): DESCARTADA**
  por doc citada de kipy 0.7.1 (`kipy/board.py:315-316`):

  > *"If you do not call begin_commit, any changes made to the board will
  > be committed immediately, which will result in multiple steps being
  > added to the undo history."*

  Sin `begin_commit` la escritura es inmediata; el batching solo agrupa
  entradas de undo.

- **H2 ("get_footprint_position lee cache local"): DESCARTADA** por
  inspección de `Board.get_footprints()` (kipy `board.py:501-506`): cada
  llamada envía un `GetItems` fresco al server IPC, sin cache local.

- **Causa real (misma dirección, mecanismo distinto): mutación de una
  copia local del proto**. Nueva evidencia citada:
  - `kipy.geometry.Vector2.__init__` (`geometry.py:38-42`) crea un proto
    NUEVO y hace `CopyFrom` del que recibe.
  - `FootprintInstance.position` getter (`board_types.py:1935-1937`)
    retorna `Vector2(self._proto.position)` — una copia del proto interno.

  Nuestro bridge hacía:

  ```python
  fp.position.x = int(mm_to_nm(x_mm))   # muta la COPIA
  fp.position.y = int(mm_to_nm(y_mm))   # muta OTRA copia
  raw_board.update_items(fp)            # envía el proto ORIGINAL sin cambio
  ```

  El proto interno del `FootprintInstance` nunca cambiaba; `update_items`
  reportaba "OK" con la posición previa. El setter correcto (`board_types.py:
  1939-1964`) escribe sobre `self._proto.position` y arrastra
  fields/pads por delta.

### Fix aplicado

`bridge/ipc.py:move_footprint` — importa perezoso `Vector2` y usa el
setter:

```python
fp.position = Vector2.from_xy(int(mm_to_nm(x_mm)), int(mm_to_nm(y_mm)))
raw_board.update_items(fp)
```

### Revalidación contra KiCad real

`uv run pytest -m integration_gui` → **3/3 verdes** (44 s):

- `test_ipc_reports_real_kicad_version` — smoke IPC.
- `test_move_footprint_round_trip_against_open_board` — round-trip
  persistente (el bug histórico) con tolerancia ±1 nm.
- `test_move_footprint_tool_returns_confirm_with_positive_snap_id` —
  cadena tool→bridge, hardened en T2 para verificar el EFECTO (posición
  re-leída), no solo el confirm.

### `add_track` auditado

`add_track` **no tiene** el mismo bug: construye `Track()` vacío y asigna
por setter de property (`track.start = Vector2.from_xy(...)`, mismo patrón
que el fix de `move_footprint`). El proto interno se escribe correctamente
y `create_items(track)` envía el proto con los datos.

### `build_state_from_board` post-fix

En sesión 05, `build_state_from_board` capturaba el estado del board de
kipy tras `move_footprint`. Con el bug T1 pendiente, la mutación local
NO afectaba el proto interno → el snapshot vivo reflejaba la POSICIÓN
INICIAL del board (que es también lo que KiCad tenía porque la mutación
nunca se propagó). El snapshot post-mutación era consistente con KiCad,
pero por la razón equivocada: ni la memoria de kipy ni KiCad vieron el
move. Post-fix, ambos ven la nueva posición y el snapshot la refleja.

---

## Mutation testing manual (§3 del prompt)

Ambos reverts se aplicaron y se corrió el test de cruce
`test_move_footprint_then_context_delta_reflects_mutation` (T2), que es el
centinela del pipeline completo. Los dos experimentos fallaron como se
esperaba; se restauraron ambos fixes antes de la suite final.

### Mutation #1 — revierto la propagación en el fake (simula bug T1 en unit)

Comenté la línea `self._positions[ref] = (float(x_mm), float(y_mm))` en
`_FakeBridge.move_footprint`. Con esto el fake registra el call pero
`snapshot_footprints` NO refleja la mutación.

Salida:

```
AssertionError: esperaba ~C por posición cambiada, obtuve:
DTOON|v1|snap:3|base:1|area:r100@U1
[AREA]
U1 ok

assert '[~C]' in 'DTOON|v1|snap:3|base:1|area:r100@U1\n[AREA]\nU1 ok\n'
```

El delta muestra `U1 ok` (sin cambios) en lugar de `[~C] U1 x50.0 y60.0`.
El test detecta el bug T1.

### Mutation #2 — revierto la rama viva en `_build_current_for` (simula bug D-06.1v2)

Reemplacé la lógica kind-aware por el path original: `curr` siempre se
construye desde disco vía `build_state_cached`.

Salida:

```
AssertionError: Error executing tool get_context_delta:
[KICAD_CLI_FAILED] kicad-cli devolvió error al exportar el netlist.
hint: Failed to load schematic
```

En el mundo unit, el `.kicad_sch` de `_make_project` es un stub
`(kicad_sch)` sin datos; el path de disco falla al parsearlo con
kicad-cli. Es una manifestación distinta del bug D-06.1v2 (el test no
tiene el fake mockeado para el path disco), pero sigue siendo evidencia
sólida: **sin la rama viva, el flujo mutar→delta se rompe**.

Ambos tests pasan al restaurar los fixes.

---

## Tarea 2 — hardening de fakes y verificaciones de efecto (D-06.3)

- `_FakeBridge` en `tests/test_pcb.py` acepta `initial_positions` y mantiene
  un `_positions[ref] -> (x, y)` que `move_footprint` actualiza y
  `snapshot_footprints` lee. Cómplice de la spec, no del bug.
- `_FakeBridge` ahora también expone `get_footprint_position` fiel a
  `_positions` — habilita la re-lectura hardened.
- `test_move_footprint_success_writes_audit_and_short_confirm` verifica el
  EFECTO (posición post-tool via `bridge.get_footprint_position`), no
  solo el confirm.
- `test_move_footprint_tool_returns_confirm_with_positive_snap_id`
  (integration_gui) también hardened: post-tool re-lee vía bridge y
  contrasta `x_after ≈ target_x` con tolerancia ±1 nm.
- Test nuevo `test_move_footprint_then_context_delta_reflects_mutation`:
  cadena `move_footprint → snapshot vivo pcb → get_context_delta(base=snap
  pre-move)` que valida que el delta refleja EXACTAMENTE la mutación.
  Este test habría atrapado tanto T1 como D-06.1v2 (mutation testing
  arriba lo demuestra).

---

## Tarea 3 — delta kind-aware (D-06.1v2)

- `_build_current_for(entry, schematic, bridge, base_snap)` en
  `tools/world.py` centraliza la construcción de `curr`:
  - Base vivo `kind="pcb"`: `build_state_from_board` (rama viva). Nuevo
    snap registrado con `mtimes=None`.
  - Base vivo `kind="pcb"` pero `bridge.get_open_board() is None`:
    `SNAPSHOT_STALE` con `data.reason="live_chain_lost"` (no
    `KICAD_NOT_RUNNING`).
  - Base de disco `kind="sch"`: `build_state_cached` (path histórico).
  - Base vivo `kind="sch"`: bug interno (no existe path que lo cree hoy) →
    `KICAD_CLI_FAILED` con hint explícito.
- Assert de kinds homogéneos post-construcción: `curr.kind != entry.state.kind`
  ⇒ `KICAD_CLI_FAILED` (código con precedente en `state_builder._rebuild`).
  F3 respetada: NO se agregaron códigos nuevos.
- `register(mcp, *, ipc_bridge)` — signature actualizada. `tools/__init__.py`
  pasa el bridge singleton igual que a `pcb`.
- Tests: 3 unit nuevos (`pcb_live_uses_board_not_disk`,
  `pcb_live_no_board_returns_snapshot_stale`,
  `sch_disk_path_still_works`) + el test de cruce arriba. El test viejo
  `skips_mtime_for_live_snapshot` se reescribió como el primero (base
  vivo pcb, no sch, que era incoherente).

---

## Tarea 4 — deuda de documentación

- `docs/specs/tool-catalog.md`:
  - Sección Taxonomía extendida con "Campo `data` del envelope (estándar
    opcional, F3 intacta)" — reglas de emisión, keys `snake_case`
    estables, emisores actuales (`SNAPSHOT_STALE` con
    `data.base_snap`/`data.retention`; y con `data.reason="live_chain_lost"`
    para la nueva rama viva).
  - Notas de `get_context_delta` extendidas con el comportamiento kind-aware
    D-06.1v2 (tres ramas + caso "cadena viva perdida").
- `docs/pruebas-gui.md`:
  - Sección "Env vars (checklist)" con tabla completa: `KICAD_MCP_GUI_TEST`,
    `KICAD_MCP_PROJECT`, `KICAD_MCP_GUI_REF`, `KICAD_API_SOCKET`.
  - Sección "Diagnóstico H1 vs H2" que documenta el aprendizaje T1
    (H1 histórica descartada por doc; causa real = property setter mal usado).
- `docs/adr/0008-kipy-write-semantics-property-setter.md`: nuevo. Registra
  el patrón `fp.position = Vector2(...)` como obligatorio y la
  regla de auditoría "grep sobre wrappers de kipy antes de emitir
  mutaciones".
- `tests/test_toon_encoder.py:7`: docstring stale limpiado (mencionaba
  xfails que ya no existían).

---

## Tarea 5 — NO habilitada

`grep -n "kicad-skip\|kicad_skip" pyproject.toml` → sin resultado. La
precondición dura del prompt (F5) NO se cumple. **T5 no se implementó.**
No se tocó `pyproject.toml` bajo ninguna circunstancia (F5), no se
levantó venv del scratchpad para hacer trampa. Queda para sesión 07 si el
humano agrega la dependencia.

---

## Definition of Done

```
uv run pytest -m "not integration and not integration_gui"  → 85 passed  ✓
uv run pytest -m integration                                → 20 passed en 3:21  ✓
uv run pytest -m integration_gui                            → 3/3 passed (KiCad real)  ✓
uv run mypy src/                                            → Success (30 files)  ✓
uv run ruff check src/ tests/ scripts/                      → All checks passed  ✓
uv run ruff format --check src/ tests/ scripts/             → clean (49 files)  ✓
```

---

## Mediciones de tokens (post-fix)

| Escenario                                                | tokens_est |
|----------------------------------------------------------|------------|
| Confirm `move_footprint` (unit, R5 → 102.5, 44.0)        | 13         |
| Confirm `move_footprint` con `base_snap` (unit, U1)      | 12         |
| `get_context_delta` con base **viva pcb**, delta [~C] U1 | **19**     |
| `add_track` confirm (sin cambios vs sesión 05)           | 18         |

**Promedio del pipeline post-mutación (T1 + T2 + T3)**: ~15 tokens/tool_call.
Confirms ≤50 tokens ✓ (ADR-0004). Promedio global ≤400 tokens ✓ (D4). El
nuevo path `get_context_delta` con base viva es EL más barato de todos
los deltas medidos: 19 tokens contra 20 (sesión 05, delta vacío sobre
001) — la rama viva no paga overhead adicional; leer del board de kipy
tiene aproximadamente el mismo costo estimado que leer un fixture de
disco.

## Tiempos de suite

| Suite                                    | Sesión 05 | Sesión 06 |
|------------------------------------------|-----------|-----------|
| `not integration and not integration_gui`| 2.8 s     | 5.0 s     |
| `integration`                            | 274 s     | 201 s     |
| `integration_gui`                        | (skip)    | 44 s      |

`integration` bajó de 4:34 a 3:21 (mejora ~1:13 sin cambios explícitos;
plausible: kicad-cli cache warm en el shell). Muy por debajo del umbral
5:00 del prompt: **no hay tests para mover a `integration_slow`**;
`pyproject.toml` NO se toca (F5).

`integration_gui` sumó 3 tests contra KiCad real; 44 s incluye el
handshake del socket, la primera lectura del board (`get_footprints` es
la más pesada) y las tres pasadas E2E.

---

## Dudas abiertas y candidatos para sesión 07

1. **KiCad "busy" al enumerar items del PCB (KiCad 10.0.4).** Durante la
   sesión, dos veces KiCad devolvió `KiCad is busy and cannot respond to
   API requests right now` para TODAS las variantes de `get_items` (footprints,
   tracks, pads, vias, zones) mientras `get_version` y `get_nets` seguían
   OK. Se destrabó cerrando y reabriendo KiCad + reabriendo el PCB
   Editor. No hay hipótesis firme sobre la causa (¿DRC realtime? ¿router
   background?). Reportable como riesgo latente del bridge — si un
   agente encadena mutaciones el humano puede toparse con el mismo
   bloqueo. Candidato de investigación: exponer un `bridge.health()`
   más fino que distinga "socket vivo" de "board editor responde a
   `GetItems`".
2. **Nuevo error del API server: `no handler available for request of
   type kiapi.common.commands.GetOpenDocuments`** cuando el PCB Editor no
   está abierto (solo project manager). Hoy se materializa como
   `KICAD_CLI_FAILED` genérico con el hint del stderr; un código o hint
   más específico "abrí el PCB Editor" ayudaría al agente.
3. **Hash del board de kipy para snapshots vivos.** Diferido en ADR-0007
   (sesión 05). Sin novedades: el gap se mide cuando aparezcan falsos
   negativos reales.
4. **Eval A (TOON vs CSV vs JSON compacto).** Sigue pendiente; el
   pipeline delta está robusto y el formato TOON validado — momento
   adecuado para la evaluación comparativa.
5. **T5 `add_symbol`.** Precondición pyproject NO habilitada; reactivable
   si el humano agrega `kicad-skip`.
6. **Ampliar el patrón `data` del envelope.** El catálogo lo declara
   estándar; considerar emitirlo desde otros errores con contexto
   estructurable (por ejemplo, `COMPONENT_NOT_FOUND` con
   `data.similar_refs`, hoy embebido en el hint).
