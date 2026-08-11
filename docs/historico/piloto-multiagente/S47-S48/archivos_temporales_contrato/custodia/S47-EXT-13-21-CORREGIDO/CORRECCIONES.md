# CORRECCIONES — S47-EXT-13-21-CORREGIDO

```
Unidad origen:          /tmp/tmp.mCEghuAEtW.s47ext/S47-EXT-13-21/
MANIFEST.sha256 origen:  ea4aab540e1d8b7849baf5e3e4d8b4c89f7a3851c2f45845b9ada153b04a07d8
Revisor independiente:   Codex, read-only
Veredicto de revisión:   APROBAR_CON_CAMBIOS
Reconciliador:           Codex (auditor/reconciliador), ajustes de verificación aceptados
Autorización de ejecución: Gato, autoridad humana del proyecto MCP_AUDITOR_KICAD
Productor de esta corrección: Claude Code
```

**R4 (`AGENTS.md`):** Claude Code produjo estos bytes → no puede emitir la
aprobación independiente de esta unidad corregida. Esta unidad queda en
estado `PENDIENTE_DE_REVISION_INDEPENDIENTE_R4`: requiere revisión por una
instancia que no haya producido ni modificado sus bytes (no Codex, que ya
actuó como escritor controlado sobre bytes de esta línea de trabajo en
sesiones previas; no Claude Code, productor de esta corrección).

Ningún hallazgo altera la cadena de veredictos: `NO_GO_POR_PRESUPUESTO`,
`ALCANCE_SUPERVIVIENTES_21`, 21/21 `NO_APTO` permanecen sin cambio.

## C-EXT-01 — MINOR — `15-delete-track.md` §M4

**Antes:**
```
`COBERTURA_DEMOSTRADA`: 6 tests offline con assert (`tests/test_pcb_session11.py`
×4: happy/ambigüedad/net-not-found/nothing-in-tolerance;
`tests/test_pcb_session16.py` ×6 adicionales: by-id, ambigüedad con ids,
id-stale, mixing-id-and-coords) + 5 tests `integration_gui`/
`integration_gui_slow`.
```

**Después:**
```
`COBERTURA_DEMOSTRADA`: 9 tests offline con assert (`tests/test_pcb_session11.py`
×4: happy/ambigüedad/net-not-found/nothing-in-tolerance;
`tests/test_pcb_session16.py` ×5 adicionales: by-id, ambigüedad con ids,
id-stale, by-id-wrong-kind→track-id-stale, mixing-id-and-coords) + 5 tests
`integration_gui`/`integration_gui_slow`.
```
(+ párrafo de corrección explicando el delta, ver el archivo).

**Evidencia de verificación:**
```bash
$ grep -n "^def test_" tests/test_pcb_session11.py | grep -ci delete_track
# 4 tests: happy/ambigüedad/net-not-found/nothing-in-tolerance
$ grep -n "def test_delete_track" tests/test_pcb_session16.py
380:async def test_delete_track_by_id_removes_exact_segment(
403:async def test_delete_track_ambiguity_carries_candidates_with_ids(
443:async def test_delete_track_id_stale_when_board_mutated(
469:async def test_delete_track_by_id_wrong_kind_is_track_id_stale(
486:async def test_delete_track_mixing_id_and_coords_rejected(
# 5 tests, no 6. El original omitía "by_id_wrong_kind_is_track_id_stale".
```

**Impacto en veredicto:** ninguno. `18 < 80` con 9 o con 6 tests declarados;
S7 falla igual de claro.

## C-EXT-02 — MINOR — `19-reload-board-from-disk.md` §M4

**Antes:**
```
`COBERTURA_DEMOSTRADA`: 5 tests offline con assert
(`tests/test_reload_board.py`: happy-registers-disk-snapshot,
is-idempotent-at-tool-level ×2, no-board-open-raises-reload-failed,
busy-propagates-without-rewrapping).
```

**Después:**
```
`COBERTURA_DEMOSTRADA`: 4 tests offline tool-level con assert
(`tests/test_reload_board.py`: happy-registers-disk-snapshot-and-clears-
live-stale, is-idempotent-at-tool-level, no-board-open-raises-reload-failed,
busy-propagates-without-rewrapping), más 3 tests bridge-level en
`tests/test_ipc.py` (calls-revert-and-counts-tracks-vias,
is-idempotent-at-bridge-level, does-not-retry-on-busy) — evidencia adicional
distinta, no sustituye la cobertura tool-level.
```

**Evidencia de verificación:**
```bash
$ grep -n "^async def test_" tests/test_reload_board.py
98:async def test_reload_happy_registers_disk_snapshot_and_clears_live_stale(
135:async def test_reload_is_idempotent_at_tool_level(
154:async def test_reload_no_board_open_raises_reload_failed(
174:async def test_reload_busy_propagates_without_rewrapping(
# 4 tests, una sola prueba de idempotencia (no ×2).
$ grep -n "def test_reload_board_from_disk" tests/test_ipc.py
1127:def test_reload_board_from_disk_calls_revert_and_counts_tracks_vias
1141:def test_reload_board_from_disk_is_idempotent_at_bridge_level
1160:def test_reload_board_from_disk_does_not_retry_on_busy
# 3 tests bridge-level, evidencia adicional y distinta.
```

**Impacto en veredicto:** ninguno. `57 < 80` con 4, 5 o 7 tests declarados;
S7 falla igual de claro.

## C-EXT-03 — NOTE — fichas 15, 16, 17, 19, 20 + tablas resumen

**Antes (idéntico en 16/17/19/20, con paréntesis extra en 15):**
```
**S1:** cumple trivialmente en el estado actual.
```

**Después (las cinco fichas):**
```
**S1:** no determinante — el estado actual cumple, pero el gate se evalúa
sobre la **extracción proyectada**, que aquí no se evalúa completamente
porque S7 rechaza primero (ver M2 y S7). No se afirma cumplimiento de S1
bajo extracción (corrección C-EXT-03).
```

Ficha 13 (`13-similars.md`) **no se tocó**: su S1 está justificado con
evidencia propia (`d2=0, sin dependencias hacia pcb.py`), no con la fórmula
genérica "en el estado actual" — no es instancia del mismo hallazgo.

**Tablas resumen** (`03-refutacion-ext.md §4`, `05-RECONCILIACION.md §3`):
se añadió una nota al pie idéntica en ambas explicando el alcance de
"cumple" en la columna S1 para los candidatos rechazados por S7. Las celdas
de la tabla no se modificaron (mantiene comparabilidad con la tabla de los
12 originales, que usa la misma convención para candidatos en situación
idéntica).

**Impacto en veredicto:** ninguno. S1 nunca fue el gate determinante para
estos 5 candidatos — S7 rechaza primero en los 5 casos.

## C-EXT-04 — NOTE — `03-refutacion-ext.md` encabezado

**Antes:**
```
... con S1-S8 (AND) y R1-R14 (OR) de **v5** §§11.4/11.5 (fuente verificada
por hash, `00-preflight-ext.md §3`), S8 usando la comparación M2 homogénea
de **v6** §10, ...
```

**Después:**
```
... con S1-S8 (AND) y R1-R14 (OR) de **v6** §§11.4-11.5 —instrumento
normativo primario, verificado por hash (`00-preflight-ext.md §3`), cuyos
apartados declaran su contenido "idéntico a v5"—, S8 usando la comparación
M2 homogénea de **v6** §10, ...
```

**Evidencia de verificación:** `00-preflight-ext.md §3` ancla por SHA-256 a
`contrato_S47-DT1-SLICE2-CARACTERIZACION_v6.md`
(`3b16079cd67357b17ff2d23064c6397454b8a06e4830684c0fa60c2eaac91402`); v5 no
forma parte del conjunto de instrumentos anclados por hash en esta unidad.
`contrato_S47-DT1-SLICE2-CARACTERIZACION_v6.md` §11.4 y §11.5 dicen
literalmente "Idéntico a v5" — no hay contradicción de contenido, solo de
qué documento es la referencia primaria verificable.

**Impacto en veredicto:** ninguno. El contenido normativo de S1-S8/R1-R14
es el mismo en v5 y v6 por declaración explícita de v6.

## Resumen de impacto

Los 21 candidatos permanecen `NO_APTO`. La regla 13 de v6 §11.3 sigue siendo
la primera aplicable. `NO_GO_POR_PRESUPUESTO` / `ALCANCE_SUPERVIVIENTES_21`
sin cambio.
