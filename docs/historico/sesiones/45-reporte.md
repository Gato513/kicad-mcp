# Sesión 45 — cierre de un P3: `move_footprint` sin `check_no_external_disk_edit()`

## Resumen ejecutivo

`docs/BACKLOG.md` tenía abierto, como candidato trivial "para cuando haya
tiempo" (hallazgo de la auditoría 34a), que `move_footprint` era la única
tool W-IPC de PCB de Familia A con `disk_check=False` en `@mutating_tool`
(ADR-0014) — no llamaba `check_no_external_disk_edit()` (P3.2), a diferencia
de `add_track`/`add_via`/`delete_track`/`delete_via`/`add_zone`/
`add_keepout_zone`/`fill_zones`/`delete_zone`. Esta sesión investigó el
origen de la asimetría, confirmó que no había motivo de dominio detrás, y la
cerró.

## Investigación

El propio ADR-0014 (sesión 39, DT2) ya había documentado la asimetría como
"real" al introducir el decorador `@mutating_tool`, pero deliberadamente NO
la resolvió — sólo la volvió explícita (`disk_check=False` con comentario
en el sitio de registro) en vez de dejarla como ausencia silenciosa. El
docstring original de `check_no_external_disk_edit` (`snapshots/
validation.py:57-70`, P3.2, sesión 18) listaba las tools cubiertas
(`save_board`, `add_track`, `add_via`, `delete_track`, `delete_via`,
`add_zone`, `add_keepout_zone`, `fill_zones`, `delete_zone`) sin incluir
`move_footprint` ni `set_footprint_ref` desde el origen — un hueco de
scoping de cuando se introdujo el guard, nunca revisitado, no una decisión
consciente de excluir footprints del riesgo de "alguien editó el disco por
fuera del agente". Semánticamente, mover un footprint tiene el mismo riesgo
que cualquier otra mutación de Familia A: si el `.kicad_pcb` cambió en disco
sin que este proceso lo supiera (edición manual, otro proceso agente,
`route_board` en otra sesión), proceder puede pisar ese cambio en el
siguiente `save_board`.

## Cambios

- **`src/kicad_mcp/tools/pcb.py`** — `@mutating_tool("move_footprint",
  disk_check=False)` → `@mutating_tool("move_footprint")`. `move_footprint`
  pasa a ser Familia A pura (mismas tres guardas de entrada que el resto:
  `_guard_live_stale` → `check_no_external_disk_edit` → `_check_base_snap`).
- **`src/kicad_mcp/snapshots/validation.py`** — docstring de
  `check_no_external_disk_edit` actualizado: agrega `move_footprint` a la
  lista de tools cubiertas.
- **`docs/adr/0014-mutating-tool-decorator.md`** — la fila de `move_footprint`
  en la tabla de "flags que documentan asimetrías reales" se tachó y anotó
  como cerrada (no se borró: preserva el motivo histórico de por qué existía
  el flag).

## Tests

- **Nuevo** — `tests/test_pcb.py::test_move_footprint_rejects_external_disk_edit`:
  mismo patrón que `test_draw_board_outline_rejects_external_disk_edit`
  (asimetría A7, sesión 34a) — registra un snapshot, avanza el mtime del
  `.kicad_pcb` por fuera del proceso, y verifica que `move_footprint` ahora
  rechaza con `EXTERNAL_EDIT_DETECTED` antes de tocar IPC (`bridge.moves ==
  []`).
- **Corregido** — `tests/test_snapshots_store.py::
  test_move_footprint_external_edit_detected_when_mtime_diverges`: este test
  pasaba un `base_snap` con mtime divergente y esperaba el mensaje de
  `_check_base_snap` ("editado fuera del agente"/"pedí contexto"). Con el
  fix, `check_no_external_disk_edit` corre ANTES en el orden de guardas (ya
  establecido por ADR-0014 para el resto de Familia A) y dispara primero
  sobre la misma divergencia — el test consagraba, sin saberlo, el orden
  incompleto de guardas de `move_footprint`. Se actualizó la aserción de
  mensaje al de `check_no_external_disk_edit` ("cambió en disco" /
  `reload_board_from_disk`).
- **Reforzado** — `tests/test_snapshots_store.py::
  test_validate_base_snap_still_checks_mtime_for_disk_snapshot`: sólo
  verificaba el código de error; se le agregaron las aserciones de
  mensaje/hint exactos de `_check_base_snap` ("editado fuera del
  agente"/"pedí contexto") para que esa cobertura de texto no se perdiera
  al dejar de ejercitarse end-to-end vía `move_footprint`.

Suite offline: **468 passed** (467 previos + 1 nuevo). Goldens sin tocar.
`ruff`/`mypy` limpios.

## Sin ADR nuevo

Se actualizó ADR-0014 existente en vez de crear uno nuevo — mismo criterio
que sesión 31b (bbox de Edge.Cuts): cierra un gap que el propio ADR ya había
anticipado y documentado como candidato futuro, sin introducir ningún
contrato nuevo ni cambiar superficie externa (el código de error
`EXTERNAL_EDIT_DETECTED` ya estaba listado para `move_footprint` en
`docs/specs/tool-catalog.md:242`, sólo cambia CUÁNDO se dispara).

## Commit

Un commit `fix:` en `sesion/42-dt1-slice2-caracterizacion`, con los
trailers de atribución. Sin push (DoD #6).
