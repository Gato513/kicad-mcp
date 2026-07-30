# Sesión 32b — Fix intermedio: refill post-route silencioso

**Rama:** `sesion/32b-fix-refill-silencioso` (desde `master`, tras
fast-forward de la cadena `sesion/31-...` → `31b` → `31c` → `32`, que
todavía no estaba mergeada al arrancar — precondición resuelta al inicio
de la sesión, `git merge --ff-only` sin conflictos).
**Tipo:** fix quirúrgico post-sesión 32, cierre de F-V2-REFILL-SILENCIOSO
(P0/P1).

## Resumen ejecutivo

**F-V2-REFILL-SILENCIOSO cerrado** con un fix de ~55 líneas efectivas en
`route_board`, siguiendo el patrón D-30.1 (hipótesis explícitas antes de
tocar código) y D-31c.1 (cross-check contra ADRs vigentes). La
investigación previa al fix (equivalente al "Bloque 0" del prompt, hecha
por inspección directa del código en vez de reproducción con mock —
suficiente porque el mecanismo es determinista una vez identificado el
punto de la excepción) refutó una de las cuatro hipótesis del prompt
(H2) y descubrió que una de las dos recomendaciones de fix del BACKLOG
era activamente peligrosa. Ambos hallazgos cambiaron el marco antes de
escribir código — se documentaron con el arquitecto vía `AskUserQuestion`
antes de proceder.

### Hallazgo 1: H2 refutada — el bug es exclusivo de `route_board`

El prompt hipotetizaba (D2) que `fill_zones()` y `add_zone(fill=true)`
podían compartir el mismo modo de falla, por compartir el contrato
D-23.2/ADR-0012 desde la extensión de sesión 27. Inspección del código
(`src/kicad_mcp/tools/pcb.py`) lo refutó: ninguna de las dos llama
`reload_board_from_disk` en absoluto. Abren con `_guard_live_stale()`
(rechazan si el disco ya está adelante del vivo) y su único modo de
falla — `save_board()` — ya levanta `POST_ZONE_PERSIST_FAILED` desde
sesión 27. No existe la llamada cuya excepción se pudiera descartar en
silencio. El fix quedó acotado a `route_board`, con el cierre del
contrato para las otras dos documentado por evidencia (no tienen el
camino silencioso), no por código simétrico nuevo — D-30.2.

### Hallazgo 2: la opción (a) del BACKLOG ("desacoplar refill de reload")
era peligrosa, no sólo descartable por preferencia

Si `reload_board_from_disk` falla, el board vivo **sigue reflejando el
estado pre-ruteo** — el `save_board()` implícito de D-14.3 bajó
live→disco *antes* de que Freerouting escribiera el ruteo. Refillear y
guardar ese vivo desactualizado habría pisado el ruteo recién persistido
en disco. El guard `refill and zones_existentes > 0 and reloaded is
True` es correcto tal como está y no se relaja — sólo la opción (b) del
BACKLOG (error explícito) era viable.

### Hallazgo 3: abortar en el guard (en vez de al final) abriría una
ventana de clobber

Levantar el error inmediatamente donde se detecta el guard (antes del
DRC post-route, el registro del snapshot y `store.mark_live_stale`)
dejaría el flag `live_stale` en `False` con el disco adelante del vivo —
un `fill_zones()` posterior pasaría `_guard_live_stale()` sin ser
rechazado y su propio `save_board()` pisaría el ruteo. El raise se
pospuso hasta después de ese bookkeeping.

### Hallazgo 4: el fixture nuevo del prompt no hacía falta

`tests/test_route_board.py::_FakeBridge` ya tenía los knobs exactos
(`reload_error`, `n_zones`) para reproducir el bug determinísticamente.
No se creó `tests/fixtures/refill-silencioso/` (entregable retirado, sin
pérdida de cobertura).

Las cuatro decisiones se presentaron al arquitecto vía `AskUserQuestion`
antes de escribir código (alcance del fix, nombre del código de error,
punto del raise, tratamiento de los casos vecinos legítimos) — las
cuatro se resolvieron con la opción recomendada.

## Evidencia por hipótesis (D-30.1)

- **H1 (detección honesta del fallo) — CONFIRMADA.** La excepción de
  `reload_board_from_disk` ya no se descarta
  (`reload_error: KicadMcpError | None` capturado en vez de perdido).
  Cuando el refill prometido no corre por esa causa concreta con ≥1
  zona existente, `route_board` levanta `POST_ROUTE_REFILL_SKIPPED` en
  vez de completar en silencio. Test `test_refill_skipped_when_reload_fails_with_zones`.
- **H2 (cobertura simétrica de las 3 tools) — REFUTADA**, ver Hallazgo 1
  arriba. Documentado en ADR-0012 y D-32b.2, no en código nuevo.
- **H3 (respeta D-07.1, sin retry) — CONFIRMADA.**
  `reload_board_from_disk` se sigue llamando una sola vez; test
  `test_no_retry_del_reload` verifica `bridge.reload_calls == 1` incluso
  cuando el reload falla.
- **H4 (sin regresión sobre el flujo canónico / casos vecinos
  legítimos) — CONFIRMADA offline; humo GUI pendiente de ejecución
  humana, ver §Gates.** Los dos motivos legítimos de que el refill no
  corra —editor cerrado, board de otro proyecto abierto— NO levantan
  error; se exponen como `zones.refill_skipped_reason` (`"editor_closed"`
  / `"cross_project"`) para diagnóstico honesto sin romper el
  comportamiento documentado en `tool-catalog.md` ni los 2 tests
  heredados de `test_route_board.py` que los cubren (`:555`, `:711` —
  ninguno se modificó). Camino feliz (`test_camino_feliz_sin_razon`):
  sin `reload_error`, el refill corre normal, sin razón, sin error.

## Fix implementado

Todo en `src/kicad_mcp/tools/pcb.py::route_board` + una línea en
`errors.py`:

1. **Captura de la excepción** (antes descartada en
   `except KicadMcpError: reloaded = False`): ahora se guarda en
   `reload_error: KicadMcpError | None`.
2. **Cálculo de `refill_skipped_reason`** junto al guard existente
   (`elif refill and zones_existentes > 0:`), con precedencia
   `reload_failed` > `editor_closed` > `cross_project`. Ausente cuando
   el refill corrió, `refill=False`, o `zones_existentes == 0` (ya lo
   dice ese campo).
3. **Raise pospuesto al final**, después de DRC post-route + snapshot +
   `store.mark_live_stale` — sólo si `refill_skipped_reason ==
   "reload_failed"`. El `audit_record` se escribe SIEMPRE (con o sin
   error), conservando el `result` forense completo
   (`reloaded`, `zones_existentes`, `zones_refilladas`,
   `refill_skipped_reason`) más el `error_code` cuando corresponde — el
   mismo result que permitió detectar el bug original en sesión 32 no
   se pierde.
4. **`route_params` extraído a un local** — antes duplicado literal en
   el raise de `POST_ROUTE_PERSIST_FAILED` y en el `audit_record` final;
   ahora un único punto de verdad, reutilizado en ambos.
5. **`POST_ROUTE_REFILL_SKIPPED`** — adición pura al `StrEnum ErrorCode`
   (F1/F3 intacta, excepción sancionada por CLAUDE.md, mismo estándar
   que `POST_ROUTE_PERSIST_FAILED` de sesión 24 y `DUPLICATE_REFS` de
   sesión 31b). Nombre elegido sobre la alternativa
   `POST_ROUTE_REFILL_FAILED` del prompt: el refill **nunca se
   intentó** — "SKIPPED" no ambigua con la semántica ya asignada a
   `POST_ROUTE_PERSIST_FAILED` (refill+enforce SÍ corrieron; falló el
   save posterior).

## Tests

`tests/test_pcb_session32b_refill_silencioso_canary.py` (canario
permanente, 8 tests, offline, `@pytest.mark.unit`), self-contenido con
un `_FakeBridge` propio (sin precedente de imports cross-módulo entre
archivos de test — ver `test_pcb_session31b_duplicate_refs.py`):

- `test_refill_skipped_when_reload_fails_with_zones` — núcleo del bug:
  `isError`, `POST_ROUTE_REFILL_SKIPPED` en el texto, `refill_calls==0`,
  `enforce_hole_clearance_calls==0`, sólo el save implícito corrió,
  disco == ruteado (no pisado), `data` trae el forense completo.
- `test_live_stale_marcado_antes_de_levantar` — cierra la ventana de
  clobber del Hallazgo 3.
- `test_no_retry_del_reload` — D-07.1, H3.
- `test_audit_conserva_forense_y_error_code` — el audit log no sacrifica
  el result forense al reportar el error.
- `test_sin_zonas_no_hay_falso_positivo`, `test_editor_cerrado_no_es_error`,
  `test_cross_project_no_es_error`, `test_camino_feliz_sin_razon` — H4,
  los 4 caminos que NO deben ser error.

Los 8 tests preexistentes de `test_route_board.py` que tocan esta zona
del código quedan **verdes sin modificarse** — verificado explícitamente:
el test que hoy documenta el fallback silencioso
(`test_route_board_reload_failure_falls_back_to_live_stale`, línea 517)
usa `n_zones=0` por default en el bridge, así que nunca activa la
condición `zones_existentes > 0` que ahora dispara el error nuevo.

## Gates

- `pytest -m "not integration"`: **384 passed, 37 skipped** (incluye los
  8 tests nuevos).
- `ruff check --fix` / `ruff format`: limpios (2 archivos reformateados,
  sin cambios de comportamiento — sólo wrapping de línea).
- `mypy src/`: **Success: no issues found in 33 source files**.
- Gate GUI del DoD + humo de no-regresión (H4 contra motor real):
  **ejecutado post-cierre de sesión, con el humano abriendo
  `tests/fixtures/despertador-routed` (copia en `/tmp/despertador-routed-test`)
  en KiCad.** `test_pcb_session21_hole_clearance_gui.py` (2/2),
  `test_pcb_session27_zone_persist_gui.py` (2/2) y
  `test_pcb_session24_route_board_persist_gui.py` (1/1, humo H4: ruteo
  real vía Freerouting headless — jar del plugin KiCad 9.0 en
  `~/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/`,
  `refill=True` default ejercitado) — **5/5 verde**. El fix no introdujo
  regresión en el camino feliz de `route_board` ni en el contrato D-23.2.

## Archivos tocados

- `src/kicad_mcp/tools/pcb.py`: captura de `reload_error`, cálculo de
  `refill_skipped_reason`, raise de `POST_ROUTE_REFILL_SKIPPED` al
  final del pipeline, `route_params` extraído (~55 líneas efectivas).
- `src/kicad_mcp/errors.py`: `POST_ROUTE_REFILL_SKIPPED` (adición pura,
  F1/F3).
- `docs/specs/tool-catalog.md`: fila de `route_board` en la tabla de
  tools, entrada de taxonomía, descripción de `reloaded` y del campo
  `zones` actualizadas.
- `docs/adr/0012-route-board-persist-contract.md`: nueva sección
  "Extensión F-V2 (sesión 32b)".
- `docs/DECISIONES.md`: `D-32b.1` (fix sin retry, raise al final) y
  `D-32b.2` (alcance acotado a `route_board`, H2 refutada).
- `docs/BACKLOG.md`: `F-V2-REFILL-SILENCIOSO` cerrado con detalle del
  fix y de H2; nota de la unificación diferida (P4) actualizada con el
  tercer código; observación nueva sobre asimetría de
  `delete_tracks_bulk` frente al contrato D-23.2 (no accionada, fuera
  de alcance).
- `docs/CONTEXT.md`: §"Estado de la secuencia de Fase 4" actualizado
  (cierre de F-V2, próxima sesión 32c), lista de principios
  metodológicos vigentes (D-32b.1/D-32b.2), caveat sobre el conteo
  "25/25" de D-23.2, fila `R17` en riesgos abiertos (cerrada).
- `tests/test_pcb_session32b_refill_silencioso_canary.py` (nuevo).

## Disciplina de alcance

Sin scope creep: no se tocó `fill_zones`/`add_zone` (H2 refutada, no
había bug que fixear); no se rediseñó D-07.1 (el fix respeta la
disciplina existente sin agregar retry); no se implementó la
unificación de códigos de error `PERSIST_CONTRACT_FAILED` (deuda P4,
sin urgencia); la asimetría real encontrada en `delete_tracks_bulk`
quedó anotada en BACKLOG, no fixeada, por estar fuera del alcance
acordado. El diff de `src/` (`pcb.py` + `errors.py`) se mantuvo bien
por debajo del umbral de 150 líneas del prompt.

## Próxima sesión

**32c** — investigación P1 Fase 4 sobre el patrón F-D5-01/F-V1c-01/
F-V2-VIA-HUERFANA (3ª instancia: sesión 25 despertador, sesión 31c
anavi-dev-mic, sesión 32 anavi-macro-pad-12). **33 (Nivel C)** arranca
sólo después de que 32c cierre.

**Gate GUI y humo H4 ya ejecutados (ver §Gates) — sin bloqueantes
pendientes para mergear a `master`.**
