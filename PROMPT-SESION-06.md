# Sesión 06 — Persistencia real de mutaciones + delta kind-aware

**Rama:** `sesion-06` (crearla desde `master` al inicio). Un commit por
tarea. No pushear.
**Novedad de esta sesión:** trabajás con **KiCad ABIERTO y vivo** como
oráculo. El humano dejó KiCad 10.0.4 corriendo con el API server
habilitado y el proyecto de prueba cargado, y lanzó esta sesión con las
variables de entorno exportadas. Podés (y debés) correr
`uv run pytest -m integration_gui` para validar contra el KiCad real.

Leé `CLAUDE.md`, `AUDITORIA-PRE-06.md` (o `docs/sesiones/` si el humano
lo movió) y `docs/sesiones/05-reporte.md` antes de tocar nada.

---

## Contexto: qué se descubrió y por qué esta sesión existe

1. **BUG CONFIRMADO contra KiCad real:** `move_footprint` vía IPC
   reporta éxito pero el footprint NO se mueve (o la lectura devuelve
   estado stale). Evidencia: `test_move_footprint_round_trip` falla con
   `x1 == x0` exacto (la posición nunca cambió en la re-lectura),
   mientras `test_ipc_reports_real_kicad_version` PASA (kipy 0.7.1 ↔
   KiCad 10.0.4 se hablan bien — la compatibilidad NO es el problema).
2. **El test a nivel tool pasó estando el bug presente**, porque solo
   verifica el formato del confirm (`snap_id > 0`), no que la mutación
   haya ocurrido. Cobertura cómplice: hay que endurecerla.
3. **Gap D-06.1v2 confirmado por auditoría** (world.py:178-179):
   `get_context_delta` construye el estado actual SIEMPRE desde el
   esquemático en disco, aunque `base_snap` sea un snapshot vivo
   `kind="pcb"`. Doble asimetría: memoria vs disco Y pcb vs sch.

---

## Decisiones vinculantes del arquitecto

- **D-06.1v2 (fuente del estado actual gobernada por el kind del base):**
  en `get_context_delta`, el snapshot base determina cómo se construye
  `curr`:
  - base `kind="pcb"` y `mtimes is None` (vivo): `curr` se construye
    desde el board vivo vía `build_state_from_board`. El snapshot nuevo
    que se registra también es vivo (`mtimes=None`).
  - base `kind="pcb"` vivo pero KiCad cerrado / board no disponible:
    `SNAPSHOT_STALE` con hint "la cadena viva se perdió; re-sincronizá
    con get_world_context". NO `KICAD_NOT_RUNNING`: el problema del
    llamador es su snapshot, no la conexión.
  - base `kind="sch"`: path actual de disco (sin cambios).
  - kinds cruzados jamás se comparan. Si por cualquier camino
    `prev.kind != curr.kind`, es un bug interno: assert/error explícito,
    nunca un delta silenciosamente basura.
- **D-06.2 (corregida): snapshots post-`add_symbol` son de DISCO, no
  vivos.** kicad-skip escribe el `.kicad_sch` directamente a disco; el
  patrón correcto es registrar un snapshot nuevo con mtimes frescos
  inmediatamente post-write y ecoar su snap_id en el confirm. El patrón
  T5 (`mtimes=None`) es exclusivo de mutaciones IPC in-memory. Además:
  detección de cambios en sch post-kicad-skip NUNCA por hash de bytes ni
  diff textual (kicad-skip reescribe el archivo entero: 23.746 → 4.344
  líneas, cero líneas sobreviven); solo por `NormalizedState`/delta.
- **D-06.3 (endurecimiento de cobertura):** ningún test de mutación
  (unit con fake o integration_gui) puede dar verde sin verificar el
  EFECTO de la mutación (posición re-leída, track presente), además del
  formato del confirm. Los fakes del bridge deben simular la semántica
  real que descubras en la Tarea 1 (si kipy exige commit explícito, el
  fake también lo exige y falla si no se llama).
- **Umbral de suite:** si `integration` supera 5:00 (hoy: 4:34), NO
  toques `pyproject.toml` (F5): reportá qué tests moverías a un marker
  `integration_slow` y el humano hace la edición.

---

## Fase 0 — Verificación del entorno vivo

1. `python3 scripts/verificar_entorno.py`.
2. Confirmar variables: `KICAD_MCP_GUI_TEST`, `KICAD_MCP_PROJECT`,
   `KICAD_MCP_GUI_REF`, `KICAD_API_SOCKET` presentes en el entorno.
3. Smoke contra KiCad real:
   `uv run pytest -m integration_gui -k version -v`
   → debe PASAR. Si falla con "no handler available", reportá y frená:
   el humano tiene que reiniciar KiCad (API server a medio arrancar).
4. Reproducir el bug:
   `uv run pytest -m integration_gui -k round_trip -v`
   → debe FALLAR con `x1 == x0`. Esta es tu línea base.

## Tarea 1 — Diagnóstico y fix de la persistencia de mutaciones

1. **Discriminar H1 vs H2** con evidencia, no intuición:
   - H1: kipy 0.7.1 requiere un paso de commit/push explícito
     (`board.update_items(...)`, context manager de commit, o similar)
     que `IpcBridge.move_footprint` no hace. Setear la posición en el
     objeto local no la empuja a KiCad.
   - H2: la mutación llega a KiCad pero `get_footprint_position` lee
     una lista de footprints cacheada localmente (estado stale).
   - Método: inspeccioná el código fuente de kipy instalado
     (`uv run python -c "import kipy; print(kipy.__file__)"` y leé el
     módulo de board) para entender la semántica real de escritura.
     Después verificá tu hipótesis contra el KiCad vivo con un script
     mínimo antes de tocar el bridge.
2. **Fix en el bridge** (`bridge/ipc.py`), manteniendo el contrato:
   tipos de kipy jamás salen del bridge, todo bajo el lock, errores
   mapeados por `_map_ipc_failure`.
3. **Auditá `add_track` por el mismo bug.** Si la semántica de commit
   aplica a toda escritura, corregilo también y agregá verificación de
   efecto (el track existe post-mutación) donde sea observable.
4. **Revisá `build_state_from_board` (T5 de sesión 05):** si H1 es
   cierta, el snapshot vivo post-mutación de la sesión 05 pudo estar
   capturando el estado local mutado que KiCad nunca vio. Verificá que
   post-fix el snapshot vivo refleje lo que KiCad efectivamente tiene.
5. DoD de la tarea: `uv run pytest -m integration_gui` → **3/3 verdes**
   contra el KiCad vivo, incluido el round-trip.

## Tarea 2 — Endurecer la cobertura de mutaciones (D-06.3)

- `test_move_footprint_tool_returns_confirm_with_positive_snap_id` pasa
  a verificar TAMBIÉN la posición re-leída vía bridge (el efecto), no
  solo el confirm.
- Fakes del bridge en unit: actualizar para simular la semántica real
  descubierta en T1 (si falta el commit, el fake NO refleja el cambio).
  Los 4+ tests de tools de mutación deben ejercitar esa semántica.
- Test nuevo unit del cruce completo con fakes:
  `move_footprint → snapshot vivo → get_context_delta(base=vivo)` →
  el delta refleja EXACTAMENTE la mutación (no vacío, no invertido).
  Este test habría atrapado tanto el bug de T1 como el gap D-06.1v2.

## Tarea 3 — Fix D-06.1v2: delta kind-aware

- Implementar el branching de D-06.1v2 en `get_context_delta`
  (probablemente extrayendo la construcción de `curr` a una función
  `_build_current_for(entry)` testeable).
- El assert de kinds homogéneos en `compute_delta` (o justo antes):
  error interno explícito, código `INVALID_PARAMS` NO — esto no es
  culpa del llamador; evaluá cuál de los 17 códigos existentes encaja
  (¿`SNAPSHOT_STALE` con hint? argumentalo) o reportá si creés que
  falta un código (F3: NO agregues códigos vos; se reporta al humano).
- Catálogo: actualizar la entrada de `get_context_delta` con el
  comportamiento por kind y el caso "cadena viva perdida".
- Tests: unit por cada rama (pcb-vivo con board, pcb-vivo sin board →
  SNAPSHOT_STALE, sch-disco intacto) + 1 integration_gui opcional que
  ejercite mutar→delta contra KiCad real si el tiempo alcanza.

## Tarea 4 — Deuda de documentación (de la auditoría)

- `docs/specs/tool-catalog.md`, sección "Taxonomía de errores": declarar
  `data: dict[str, Any] | None` como campo estándar opcional del
  envelope (qué es, cuándo se puebla, ejemplo con `SNAPSHOT_STALE`).
  Los códigos NO cambian (F3).
- `docs/pruebas-gui.md`: agregar `KICAD_MCP_GUI_REF` (y
  `KICAD_MCP_PROJECT`) a las env vars del §E2E mutaciones, con la
  checklist completa que validó el humano (está en AUDITORIA-PRE-06.md
  §Pregunta 2). Documentar también el discriminador H1/H2 aprendido.
- `tests/test_toon_encoder.py:7`: limpiar el docstring stale sobre
  xfails.
- ADR nuevo si T1 reveló semántica de commit: documentar cómo escribe
  kipy realmente y el contrato del bridge al respecto.

## Tarea 5 (OPCIONAL — solo si T1-T4 cerraron con DoD) — `add_symbol` mínimo

**Precondición dura:** el humano agregó `kicad-skip` a `pyproject.toml`
ANTES de esta sesión (F5). Verificá con
`grep -n "kicad-skip\|kicad_skip" pyproject.toml`. Si NO está, esta
tarea NO existe: no la implementes con el venv del scratchpad ni
toques el manifiesto. Reportá "T5 no habilitada" y listo.

Si está habilitada:

- `tools/sch.add_symbol(sheet, lib_id, ref, x_mm, y_mm, base_snap)`:
  clona desde template (patrón validado en el spike), valida
  `base_snap` (mismo `validate_base_snap`), escribe con kicad-skip,
  **registra snapshot de disco post-write** (D-06.2) y ecoa el snap_id
  en el confirm (≤50 tokens).
- Validaciones pre-mutación: la ref no colisiona en NINGUNA hoja,
  `lib_id` existe en el archivo, posición dentro del área de la hoja.
- G1 aplica: backup pre-mutación como en las tools PCB.
- Restricción documentada en el catálogo y en un ADR: `add_symbol`
  opera sobre el archivo en disco; si el esquemático está abierto en
  la GUI de KiCad, el usuario verá el aviso de recarga. MVP: documentar
  el hazard, no resolverlo.
- Tests: unit con copias en `tmp_path` (regla 7: fixtures jamás mutados
  in place), verificación de efecto (el símbolo existe en el archivo
  re-leído, conteo +1, sin colisiones) — D-06.3 aplica también aquí.
- Fuera de scope de la tool: cableado a nets (`connect_pins` es v0.5),
  pick desde librerías externas al archivo.

---

## Fuera de scope

- Delta para snapshots sch vivos (no existe camino que los cree;
  cuando exista `add_symbol` registra de disco, D-06.2).
- Hash del board de kipy (diferido en ADR-0007, sin novedades).
- Eval A de formato — recandidatear para sesión 07.
- Editar `pyproject.toml` bajo cualquier circunstancia (F5).
- Nuevos códigos de error (F3: se reportan, no se agregan).

## Definition of Done

```
uv run pytest -m "not integration and not integration_gui"  → verde
uv run pytest -m integration                                → verde (reportar tiempo)
uv run pytest -m integration_gui                            → 3/3 verdes contra KiCad real (+ los nuevos)
uv run mypy src/                                            → Success strict
uv run ruff check + format --check                          → clean
```

## Reporte final obligatorio

1. Veredicto H1/H2 con la evidencia (código de kipy citado + script de
   verificación) y descripción exacta del fix.
2. ¿`add_track` tenía el mismo bug? ¿`build_state_from_board` capturaba
   estado que KiCad no tenía?
3. Confirmación de que el test de cruce mutar→delta (T2) falla si se
   revierte el fix de T1 o el de T3 (mutation testing manual: probalo
   y reportá el output).
4. tokens_est de los confirms post-fix y de `get_context_delta` con
   base viva. Promedio global ≤400, confirms ≤50.
5. Tiempo de `integration`; si >5:00, lista de tests candidatos a
   `integration_slow` para que el humano edite pyproject.
6. Si corrió T5: mediciones, hazards encontrados, y qué falta para
   `connect_pins`.
7. Dudas abiertas y candidatos para sesión 07.
