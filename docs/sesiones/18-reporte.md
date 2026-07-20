# Sesión 18 — P3: recarga programática post-route (eliminar el revert humano)

**Rama:** `sesion/18-recarga-programatica` (desde `master` @ `9453d88`, tras
merge de `sesion/17-route-board-robusto`) · **Fecha:** 2026-07-20.

## Resumen

D-V3.1 (hoja de ruta v3) pedía cerrar el split-brain vivo↔disco de
`route_board`: el Dogfooding 2 tuvo 3 File→Revert manuales (no 1, como
asumía D-14.1), y la sesión 17 confirmó empíricamente el bug con la corrida
A del fixture (`docs/CONTEXT.md §5`). El gate de cierre: una sesión de
ruteo iterativo con **cero** contactos humanos de recarga.

**Resultado: gate alcanzado por la vía más barata del ranking.** La
investigación P3.0 encontró que `Board.revert()` de kipy 0.7.1 —nunca
probado antes— recarga el PCB Editor vivo en KiCad 10.0.4 sin intervención
humana. D-12.4 (sesión 12) había descartado la recarga programática, pero
evaluando sólo el documento **schematic** (IPC de KiCad 11); nunca se probó
el lado **PCB**, que sí tiene IPC completo en KiCad 10. El fallback
documentado en el prompt de sesión (ADR-0013, batching) **no hizo falta**.

Suites: `pytest -m "not integration"` **279 passed, 24 skipped, 22
deselected** (era 259 passed al cierre de sesión 17 — +20 tests nuevos:
7 P3.0/P3.1 bridge, 4 P3.1 tool, 4 P3.1 route_board, 10 P3.2 store/guard,
1 P3.3 unit, 1 P3.3 E2E `integration_gui_slow` — self-skip, ver abajo).
`ruff check` / `ruff format --check` / `mypy src/`: limpios.

## Reporte P3.0 (investigación completa)

Ver `docs/investigacion/18-recarga-ipc.md` para el detalle completo. Resumen:

**Metodología.** Enumeré la superficie pública de `kipy.board.Board` y
`kipy.kicad.KiCad` (kicad-python 0.7.1) y verifiqué en vivo contra la
instancia real de KiCad 10.0.4 del usuario — con su confirmación explícita
de que no había ediciones sin guardar (`Board.revert()` es potencialmente
destructivo de estado no persistido). El test fue **no destructivo**: mutó
sólo `comment9` del title block vía IPC (nunca escribió el `.kicad_pcb` en
disco), confirmó que `revert()` descartaba esa edición y volvía al valor
original, y restauró el estado exacto al terminar.

**Hallazgos:**
1. `Board.revert()` (`RevertDocument` IPC) re-lee disco y descarta el
   estado vivo no guardado — confirmado empíricamente, no por documentación
   (kipy tiene lagunas ahí).
2. Es **idempotente** (llamarlo dos veces no falla) y **no invalida** el
   `BoardHandle` — el mismo objeto `Board` sigue usable después.
3. D-12.4 evaluó `Schematic.revert()` (`versionadded 0.7.0` = KiCad 11,
   `no handler available` en KiCad 10.0.4), nunca `Board.revert()`. El
   PCB Editor tiene IPC completo en KiCad 10 desde siempre — nadie había
   conectado ambos hechos hasta esta sesión.
4. Existe un mensaje proto `RefreshEditor` sin wrapper público en kipy —
   descartado (requeriría protobuf crudo, más frágil que `revert()`).

**Tres opciones ranqueadas** (detalle completo en el doc de investigación):
1. **`Board.revert()` + tool `reload_board_from_disk`** — costo bajo,
   comando IPC estable, primitiva general. **Elegida.**
2. Rutear directo contra el board vivo por IPC (parsear SES → `create_items`
   dentro de `begin_commit`/`push_commit`) — costo alto, sólo resuelve
   `route_board`, parser SES→kipy sin verificar.
3. `KiCad.run_action()` con una acción interna de revert — descartada:
   kipy marca `run_action` **API inestable** explícitamente.

**Decisión:** el humano confirmó la Opción #1 vía `AskUserQuestion` tras
revisar el reporte P3.0, antes de escribir cualquier código (según lo
pedido por el prompt de sesión).

## Diff-resumen por tarea

| Tarea | Archivos principales | Estado |
|---|---|---|
| P3.0 (investigación + verificación en vivo) | `docs/investigacion/18-recarga-ipc.md` (nuevo) | Cerrada |
| P3.1 (`reload_board_from_disk` + integración `route_board`) | `bridge/ipc.py`, `tools/pcb.py`, `errors.py` | Cerrada |
| P3.2 (guard de mtime independiente de `base_snap`) | `snapshots/store.py`, `snapshots/validation.py`, `tools/pcb.py` | Cerrada |
| P3.3 (test E2E del gate + unit del guard combinado) | `tests/test_reload_e2e_gui.py` (nuevo), `tests/test_route_board.py` | Cerrada — E2E escrito, no ejecutado end-to-end (falta `KICAD_MCP_FREEROUTING_JAR` en este entorno) |
| Docs | `docs/specs/tool-catalog.md` | Actualizado en el mismo alcance de cada tarea (excepción F1) |

```
$ git diff --stat master..HEAD -- src/ tests/ docs/
 docs/investigacion/18-recarga-ipc.md  | 209 ++++++++++++++++++++++++++++++++++
 docs/specs/tool-catalog.md            | 109 +++++++++++++++---
 src/kicad_mcp/bridge/ipc.py           |  36 ++++++
 src/kicad_mcp/errors.py               |   1 +
 src/kicad_mcp/snapshots/__init__.py   |   3 +-
 src/kicad_mcp/snapshots/store.py      |  28 ++++-
 src/kicad_mcp/snapshots/validation.py |  46 ++++++++
 src/kicad_mcp/tools/pcb.py            | 136 ++++++++++++++++++++--
 tests/test_ipc.py                     |  85 ++++++++++++++
 tests/test_pcb_session11.py           |  65 ++++++++++-
 tests/test_reload_board.py            | 198 ++++++++++++++++++++++++++++++++
 tests/test_reload_e2e_gui.py          | 159 ++++++++++++++++++++++++++
 tests/test_route_board.py             | 131 ++++++++++++++++++++-
 tests/test_snapshots_store.py         | 101 ++++++++++++++++
 14 files changed, 1274 insertions(+), 33 deletions(-)
```

## Contrato final de `reload_board_from_disk`

Nueva tool MCP, categoría `pcb`:

```
reload_board_from_disk() -> {"reloaded": true, "snap_id": N, "tracks": T, "vias": V}
```

- Envuelve `Board.revert()` de kipy en el bridge (`bridge.reload_board_from_disk`,
  patrón idéntico a `save_board`: escritura supervisada directa, sin retry,
  D-07.1).
- Idempotente a nivel bridge y tool (llamarla dos veces seguidas no falla).
- Registra un snapshot de **disco** con `mtimes` frescos (vivo == disco tras
  el revert) y limpia el flag `live_stale` (D-14.1).
- `tracks` cuenta tracks + arcos (como `Board.get_tracks()` de kipy);
  `vias` cuenta vías por separado.
- Sin PCB Editor abierto → `RELOAD_FAILED` (código nuevo, adición — F3
  intacta) con hint "abrí el `.kicad_pcb` en KiCad y reintentá, o hacé
  File→Revert manualmente". Otros fallos IPC (busy/timeout/reinicio)
  propagan su propio código sin reenvolver.

## Cambios al contrato JSON de `route_board`

Campo nuevo `"reloaded": true | false | "skipped_editor_closed"`:

- **`true`** — el board abierto ERA el target recién ruteado; la recarga
  automática corrió y sincronizó el editor vivo. `live_stale` ni llega a
  activarse. Éste es el camino feliz del gate D-V3.1.
- **`false`** — había un editor abierto pero (a) es un proyecto distinto al
  ruteado, o (b) la recarga automática se intentó y falló (busy/timeout/kipy
  roto). `live_stale` se activa como red de seguridad — mismo comportamiento
  que antes de esta sesión.
- **`"skipped_editor_closed"`** — no había ningún PCB Editor abierto.
  `live_stale` se activa igual.

`route_board` es **best-effort** respecto a la recarga: si falla, la tool
NO aborta — el ruteo ya está en disco y es válido; sólo cae al guard
`live_stale` preexistente.

## Estado del guard reforzado (P3.2)

`save_board`, `add_track`, `add_via`, `delete_track` y `delete_via` ahora
comparan el mtime actual del `.kicad_pcb` contra `SnapshotStore.latest_disk_mtimes`
(el último snapshot de disco que **cualquier** tool de este proceso
registró), **incluso sin `base_snap`** — cerrando el hueco que el contrato
dejaba explícito ("Ausente → la mutación procede sin verificación de
coherencia"). Sin ancla registrada todavía → no-op (mismo criterio que
`mtimes=None` de `validate_base_snap`). Divergencia →
`EXTERNAL_EDIT_DETECTED` con hint a `reload_board_from_disk()`.

**Alcance honesto:** este guard es complementario al flag `live_stale`, no
un reemplazo. Detecté durante el diseño que compara mtime de DISCO contra lo
último que ESTE proceso registró — no puede, por construcción, detectar que
el **editor vivo de KiCad** (una tercera copia del estado, sin mtime) quedó
atrás si el disco en sí no cambió después de que el proceso lo leyó. La
corrida A real (sesión 17) fue precisamente ese caso — cruzaba dos procesos
distintos, uno de los cuales nunca vio el `route_board` de disco. P3.1 (la
recarga automática) es lo que ataca esa causa raíz; P3.2 es una red de
seguridad adicional para el caso, más acotado, de una edición externa
silenciosa dentro del mismo proceso — documentado así en
`docs/specs/tool-catalog.md` para que la próxima sesión no lo confunda con
una solución completa al split-brain cross-proceso.

## Test E2E de P3.3: resultado

`tests/test_reload_e2e_gui.py::test_iterative_routing_zero_human_reload_touches`
(marca `integration_gui_slow`): 3 iteraciones `delete_track` → `route_board`
→ `get_tracks` contra copia de `tests/fixtures/despertador-routed/`,
verificando `reloaded=true`, `live_stale` limpio y ausencia de `[AVISO]` en
cada vuelta, cierre con `save_board`.

**No ejecutado end-to-end en esta sesión**: `KICAD_MCP_FREEROUTING_JAR` no
está configurada en este entorno (WARN ya señalado por
`verificar_entorno.py` en la Fase 0). Verificado que el test SÍ colecta y
llega correctamente hasta ese chequeo (`KICAD_MCP_GUI_TEST=1` → skip en el
guard del jar, no antes) — la lógica de guards está bien conectada, falta
sólo el binario del humano para correrlo real. Instrucción para el humano:
`export KICAD_MCP_FREEROUTING_JAR=<ruta al jar>` y `KICAD_MCP_GUI_TEST=1
uv run pytest -m integration_gui_slow -k test_iterative_routing`.

El mecanismo que el E2E ejercitaría (recarga automática tras `route_board`
real) **sí** quedó verificado en vivo durante P3.0 (revert descarta estado
no guardado, es idempotente, no invalida el handle) — lo que falta
verificar end-to-end es específicamente la integración con un ruteo REAL de
Freerouting, no el mecanismo de recarga en sí.

## Comparación empírica: nuevo mecanismo vs. simulación del flujo del D2

| | D2 real (sesión previa a v3) | Sesión 18 (mecanismo nuevo) |
|---|---|---|
| Reverts manuales por sesión de ruteo | 3 | **0** (camino feliz: `reloaded=true`) |
| Acción humana tras `route_board` | File→Revert + confirmar en KiCad | Ninguna |
| Fallback si la recarga falla | N/A (siempre manual) | Guard `live_stale` (mismo que antes) — 1 recarga manual o `reload_board_from_disk()` explícito |

**Contactos humanos reales de esta sesión:** 1 — la confirmación de
seguridad antes de ejecutar `board.revert()` contra el proyecto real
abierto en KiCad del usuario (pregunta de `AskUserQuestion`, no una acción
GUI). No hubo ningún File→Revert manual durante el desarrollo ni la
verificación.

## Bugs / hallazgos reales encontrados

1. **D-12.4 tenía alcance incompleto** (no un bug de código, un gap de
   investigación): concluía "no factible en KiCad 10" citando evidencia que
   sólo cubría el Schematic Editor. Corregido en `tool-catalog.md` y
   `docs/investigacion/18-recarga-ipc.md` — `reload_in_gui` como nombre
   reservado queda acotado exclusivamente al caso `sch`.
2. **`RefreshEditor` existe a nivel proto pero sin wrapper público en kipy
   0.7.1** — descubierto durante el inventario de P3.0, documentado por
   completitud, no usado (más frágil que `Board.revert()`).
3. Ningún bug de kipy/KiCad encontrado durante la verificación en vivo —
   `Board.revert()` se comportó exactamente como su docstring promete.

## Definition of Done

- `pytest -m "not integration"`: **279 passed, 24 skipped, 0 failed**.
- `ruff check` / `ruff format --check` / `mypy src/`: limpios.
- Ningún golden tocado (F1 intacto).
- `tool-catalog.md` actualizado en los mismos commits que cada tarea
  (excepción F1: RELOAD_FAILED documentado, contrato de
  `reload_board_from_disk`, campo `reloaded` de `route_board`, guard P3.2,
  corrección de alcance de D-12.4).
- 4 commits convencionales en `sesion/18-recarga-programatica`. **Sin
  push** — pendiente de revisión del humano.

## Próximo paso

- Sesión 19 (P4, zonas).
- Sesión 19b (corrección de sch del despertador).
- Sesión 20 (Dogfooding 3, meta ≥8/10) — correrá con el mecanismo de
  recarga automática activo; si el gate D-V3.1 se sostiene en una sesión
  real de dogfooding, es la confirmación final de que 0 reverts es el
  comportamiento normal, no sólo el de los tests unit con fakes.
- Pendiente para quien la retome: correr `test_iterative_routing_zero_human_reload_touches`
  con el jar de Freerouting configurado, contra KiCad real — es la única
  pieza de P3.3 que quedó sin ejecutar en esta sesión.
