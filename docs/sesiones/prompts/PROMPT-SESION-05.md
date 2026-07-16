# Sesión 05 — Delta v0.3 + registro post-mutación

**Rama de trabajo:** `sesion-05` (crearla desde `master` al inicio).
**Duración estimada:** 4 días de núcleo + 1 día opcional de spike.
**Un commit por tarea.** No pushear.

Sos un agente autónomo trabajando sobre el repo `kicad-mcp`. Leé `CLAUDE.md`
antes de tocar nada. Las decisiones de esta sesión ya fueron tomadas por el
arquitecto; tu trabajo es ejecutarlas con fidelidad, no reinterpretarlas.

---

## ⚠️ ADVERTENCIA CRÍTICA — F1 Y EL GOLDEN 003

Esta sesión des-xfailea `tests/golden/003_delta/`. El delta se implementa
**contra la spec** (`docs/specs/toon-v1.md`, sección delta) y debe pasar el
golden **byte a byte**.

Si tu implementación produce un output que NO coincide con el golden:

1. **NO edites el golden.** `tests/golden/**` es frontera F1, denegada en
   `.claude/settings.json` y en tu contrato.
2. **NO "reinterpretes" la spec** para justificar tu output.
3. Detené la tarea y escribí en el reporte la discrepancia exacta:
   bytes esperados vs producidos, sección de la spec involucrada, y tu
   hipótesis de la causa. El humano decide.

Un golden que falla es un reporte, no una edición. Esto aplica también si
la spec te parece ambigua: la ambigüedad se reporta, no se resuelve
unilateralmente.

---

## Decisiones vinculantes del arquitecto (contexto de esta sesión)

- **D-05.1:** Delta primero, spike kicad-skip después (opcional). El delta
  materializa el valor del Snapshot Store y cierra el golden 003.
- **D-05.2:** `SnapshotEntry.mtimes` pasa a `dict[str, int] | None`. Un
  snapshot registrado tras una mutación in-memory (el disco no cambió) se
  registra con `mtimes=None` = "snapshot vivo". La validación de mtime
  **se omite** para snapshots vivos. Motivo: si un snapshot post-mutación
  llevara mtimes de disco, el `Save` legítimo posterior dispararía
  `EXTERNAL_EDIT_DETECTED` falso positivo sobre la propia cadena del
  agente. La limitación resultante (un snapshot vivo no detecta ediciones
  externas concurrentes) se documenta en un ADR nuevo. La alternativa de
  hashear el board de kipy queda diferida hasta que se mida que el hueco
  importa.
- **D-05.3:** `snap = 0` como sentinel "no vinculado" queda ratificado a
  largo plazo. Sin cambios.
- **D-05.4:** No se cachea la versión en `health`. YAGNI hasta perfil real.
- **D-05.5:** `get_context_delta` con `max_tokens` usa el **mismo mecanismo
  de degradación §4** que el estado completo. No inventes un segundo
  comportamiento de budget. Si ni degradado entra en el presupuesto →
  `CONTEXT_BUDGET_IMPOSSIBLE`, igual que hoy.
- **D-05.6 (gate de contingencia, fin del día 3):** si la reconstrucción de
  `NormalizedState` desde el board vivo de kipy (Tarea 5) peligra el cierre
  de la sesión, se degrada el alcance: delta entre dos snapshots de disco
  únicamente, y la reconstrucción in-memory se difiere a sesión 06 con
  reporte explícito. Preferimos una sesión cerrada y honesta a una
  sobre-extendida.

---

## Fase 0 — Verificación del entorno

- Confirmar que estás en `master` actualizado (el humano ya mergeó
  `sesion-04`) y crear la rama `sesion-05`.
- `python3 scripts/verificar_entorno.py` — reportar OK/WARN/FAIL.
- Correr la suite rápida y confirmar el punto de partida:
  `uv run pytest -m "not integration and not integration_gui"`
  → esperado: 58 passed, 1 xfailed.

---

## Tarea 1 — Endurecimiento de `_map_ipc_failure`

Además del match por `__qualname__`, verificar
`type(exc).__module__.startswith("kipy")` para identificar
`kipy.errors.ConnectionError`. El builtin `ConnectionError` sigue por
`isinstance`. Motivo: evitar que un `ConnectionError` propio de otra
librería dentro del bloque supervisado se mapee a `KICAD_NOT_RUNNING`.
El contrato de import perezoso de kipy se mantiene intacto (nada de
`import kipy` a nivel de módulo).

Tests unit: un fake exception con qualname `ConnectionError` pero módulo
ajeno debe mapear a `KICAD_CLI_FAILED`, no a `KICAD_NOT_RUNNING`.

---

## Tarea 2 — Snapshots vivos (`mtimes=None`)

Implementar D-05.2:

- `SnapshotEntry.mtimes: dict[str, int] | None`.
- `SnapshotStore.register(state, mtimes=None)` acepta el sentinel.
- La validación de `base_snap` en `move_footprint` / `add_track` (y en
  `get_context_delta` de la Tarea 4):
  - snap no está en el store → `SNAPSHOT_STALE` (sin cambios).
  - snap con `mtimes` dict y algún mtime cambió → `EXTERNAL_EDIT_DETECTED`
    (sin cambios).
  - snap con `mtimes=None` (vivo) → **se omite** el chequeo de mtime.
- ADR nuevo (`docs/adr/0007` o el siguiente número libre): documentar la
  decisión, el falso positivo que evita, y la limitación aceptada.
- Aprovechá para cerrar el pendiente 5 del reporte 04: `SNAPSHOT_STALE`
  expone el `base_snap` recibido en un campo estructurado del hint,
  además del message. F3 intacta: el código no cambia, solo se enriquece
  el payload.

Tests unit: registro con `mtimes=None`, validación omitida para vivos,
validación intacta para snapshots de disco, campo estructurado en
`SNAPSHOT_STALE`.

---

## Tarea 3 — `snapshots/delta.py` + des-xfail golden 003

- `compute_delta(prev: NormalizedState, curr: NormalizedState) -> Delta`
  con adds/removes/updates de componentes, nets y pines.
- **Determinista**: orden sorted estable, sin dependencia de orden de
  inserción ni de hash seed. Correr el test del golden dos veces en el
  mismo job para verificarlo.
- Encoder del delta a TOON según la spec (§delta de `toon-v1.md`).
- Des-xfail de `tests/golden/003_delta/` **en el mismo commit** que lo
  hace pasar. Releé la advertencia F1 de arriba antes de empezar.
- Tests unit del `compute_delta` puro: estado idéntico → delta vacío,
  add puro, remove puro, update de posición, update de nets, combinado.

---

## Tarea 4 — Tool `get_context_delta`

- `tools/world.get_context_delta(base_snap: int, max_tokens: int | None = None) -> str`:
  - `base_snap` no está en el store → `SNAPSHOT_STALE` (con el campo
    estructurado de la Tarea 2).
  - snapshot de disco con mtime cambiado → `EXTERNAL_EDIT_DETECTED`.
  - snapshot vivo → sin chequeo de mtime (D-05.2).
  - Caso válido: construir el estado actual, computar delta contra el
    snapshot base, emitir TOON delta. **Registrar el estado actual como
    snapshot nuevo** y llevar su `snap_id` en la cabecera del delta
    (el delta dice "de snap A a snap B").
  - Budget: mecanismo §4 idéntico al estado completo (D-05.5).
- Catálogo (`docs/specs/tool-catalog.md`): entrada nueva con params,
  errores posibles (`SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`,
  `CONTEXT_BUDGET_IMPOSSIBLE`, `PROJECT_NOT_FOUND`) y ejemplo de output.
  El catálogo es editable por vos; la spec TOON no.
- Logging JSON por tool call como siempre (`tool_name`, `snap_id`,
  `tokens_est`, `latency_ms`).

Tests: unit con store poblado por fixture, integration contra
`001_basico` (mundo sin cambios → delta vacío; mover algo con `os` no —
usar dos builds del estado con una copia mutada del fixture en `tmp_path`,
regla 7 de CLAUDE.md: los fixtures jamás se mutan in place).

---

## Tarea 5 — Registro post-mutación (con gate D-05.6)

- Tras `move_footprint` / `add_track` exitosos: reconstruir
  `NormalizedState` desde el board vivo de kipy (sin re-leer el
  `.kicad_pcb` de disco, que todavía no refleja la mutación), registrar
  en el store con `mtimes=None` (snapshot vivo, D-05.2), y ecoar el
  `snap_id` nuevo en el confirm y el audit. El confirm sigue ≤ 50
  tokens_est (ADR-0004).
- Esto requiere un path nuevo en `state_builder` paralelo al actual
  (que hoy lee de disco vía kicad-cli). Diseñalo como función separada
  que recibe el board de kipy, no como flag del path existente.
- **Gate de contingencia (fin del día 3):** si este path in-memory está
  consumiendo la sesión, aplicá D-05.6: dejá el registro post-mutación
  como no-implementado, documentalo en el reporte con el estado exacto
  del avance, y asegurá que las Tareas 1-4 cierran con DoD completo.
  Un `xfail` explícito con razón es aceptable; scope creep no.

Tests: unit con bridge fake que devuelve un board sintético; el test
`integration_gui` de round-trip de sesión 04 se extiende para verificar
que el confirm trae un `snap_id` > 0 tras la mutación (skip bajo las
mismas variables de entorno que hoy).

---

## Tarea 6 (OPCIONAL, días 4-5) — Spike kicad-skip (readonly)

Solo si las Tareas 1-5 cerraron con DoD. Sin código de producción:
todo en `scratchpad/` (crear el directorio, agregarlo a `.gitignore`
si no está).

- Instalar kicad-skip **en un venv descartable dentro de scratchpad/**,
  NO en el `pyproject.toml` del proyecto (F5: dependencias las aprueba
  el humano; un spike no justifica tocar el manifiesto).
- Contra **copias** del fixture `004_real`:
  1. ¿El parseo del `.kicad_sch` es fiel? (componentes, nets, jerarquía
     de 7 hojas)
  2. ¿La manipulación (agregar un símbolo) genera un archivo que KiCad
     10.0.4 abre sin quejarse? Dejá el archivo generado en
     `scratchpad/` para que el humano lo verifique en GUI.
- Entregable: informe en `scratchpad/spike-kicad-skip.md` con evidencia
  concreta, para decidir sobre `add_symbol` en sesión 06.

---

## Fuera de scope de esta sesión

- `add_symbol` real (bloqueado por el spike).
- Eval A (TOON vs CSV vs JSON compacto) — solo si sobra tiempo del día 5
  y el spike se acortó; prioridad menor que el spike.
- Freerouting / `suggest_positions` (v0.4).
- Multi-hoja jerárquica, KiCad 11, HTTP remoto (F4, D1, D2 — de siempre).
- Cachear versión en `health` (D-05.4).
- Hash del board de kipy para detectar ediciones sobre snapshots vivos
  (diferido explícitamente en D-05.2).

---

## Definition of Done

```
uv run pytest -m "not integration and not integration_gui"  → verde, golden 003 SIN xfail
uv run pytest -m integration                                → verde
uv run mypy src/                                            → Success strict
uv run ruff check src/ tests/ scripts/                      → clean
uv run ruff format --check src/ tests/ scripts/             → clean
```

El test del golden 003 corrido dos veces consecutivas en el mismo job
(determinismo). Si `integration` supera los ~5 minutos, reportalo — el
arquitecto evaluará partir el marker.

---

## Reporte final obligatorio

1. Estado de cada tarea (incluido si se activó el gate D-05.6 y en qué
   estado quedó el path in-memory).
2. Si hubo CUALQUIER discrepancia con el golden 003 durante el
   desarrollo: qué era, cómo se resolvió, y confirmación explícita de
   que el golden no fue tocado (`git log --oneline -- tests/golden/`
   debe mostrar cero commits tuyos).
3. tokens_est medidos: `get_context_delta` contra 001 (delta vacío),
   contra 002 con un cambio, y contra 003 con budget. Confirmar
   promedio global ≤ 400 (D4) y confirms ≤ 50.
4. Tiempo de la suite integration antes/después.
5. Si corriste el spike: resumen de hallazgos y tu recomendación
   preliminar sobre `add_symbol` (kicad-skip sí/no/insuficiente).
6. Dudas abiertas y candidatos argumentados para sesión 06.
