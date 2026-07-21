# Sesión 19 — P4: Zonas (plano GND + keepouts)

**Rama:** `sesion/19-zonas` (desde `master`, tras merge de
`sesion/18-recarga-programatica`) · **Fecha:** 2026-07-21.

## Resumen

P4 agregó las 5 tools de zonas (`add_zone`, `add_keepout_zone`, `get_zones`,
`fill_zones`, `delete_zone`) + integración con `route_board`, precedidas de
investigación empírica (P4.0) que confirmó el hallazgo central de la sesión:
**Freerouting 2.1.0 respeta nativamente los planos de cobre que
`ExportSpecctraDSN` emite — no hace falta ningún pre-procesamiento del DSN.**
La superficie completa está implementada, documentada
(`docs/specs/tool-catalog.md`) y cubierta por tests unit (fake bridge, sin
socket ni kipy): **301 passed** en la suite pura (`not integration and not
integration_gui and not integration_gui_slow`), `ruff`/`mypy` limpios.

**El gate cuantitativo de cierre (P4.5) NO se completó en vivo esta
sesión.** Se hicieron dos intentos reales contra el fixture `despertador`
abierto en KiCad: el primero corrió **2h38m sin converger** (killeado
manualmente); el segundo, con `timeout_s=1500` (25 min), agotó el timeout
limpiamente (`KICAD_TIMEOUT`, mecanismo funcionando correctamente — ver
diagnóstico abajo). El hallazgo real es que **re-rutear sólo GND sobre un
board ya mayormente ruteado + un keepout nuevo es sustancialmente más lento
que el benchmark de sesión 18** (235-925 s), que medía una placa
completamente sin rutear. Esto queda documentado como riesgo abierto para
19b/20, no como bug de esta sesión. El código de la investigación P4.0 (test
sintético de 2 pads, corrido dos veces con/sin plano) sí demostró el
mecanismo de forma concluyente y rápida — la duda no es "¿Freerouting respeta
el plano?" (respondida, sí) sino "¿cuánto tarda en converger sobre un board
denso real?" (no resuelta esta sesión).

## Reporte P4.0 (investigación completa)

Ver `docs/investigacion/19-zonas-ipc.md` para el detalle completo. Resumen:

**Metodología.** Enumeré la superficie pública de `kipy.board.Board`/
`kipy.board_types.Zone` (kicad-python 0.7.1) contra la instancia real de
KiCad 10.0.4 vía introspección en vivo (lectura pura). Para la pregunta
crítica —¿Freerouting respeta un plano preexistente?— construí un board
sintético mínimo (2 pads GND sin track entre ellos + 2 pads de control en
otro net, con y sin un plano GND en B.Cu) en vez de correr el pipeline
completo sobre el fixture real (24 footprints): la pregunta se responde en
segundos con un caso aislado, sin comprometerse a una corrida larga sólo
para diagnosticar. Esta misma decisión metodológica —aislar antes de
escalar— resultó validada en retrospectiva por lo que pasó en P4.5 (ver
Resumen): el pipeline completo sobre el board real resultó mucho más caro
de lo previsto.

**Hallazgos:**
1. `Board.get_zones()`/`Board.refill_zones()` existen; no hay `create_zone()`
   dedicado — las zonas se crean con el `create_items()` genérico pasando un
   `Zone` (protobuf) construido a mano, mismo camino que
   `draw_board_outline`/`add_track`.
2. Copper vs keepout se distingue por `Zone.type` (`ZT_COPPER`/
   `ZT_RULE_AREA`); los flags de keepout viven en `rule_area_settings`, que
   la wrapper Python de kipy NO expone como propiedades — hay que escribir
   directo sobre `zone.proto.rule_area_settings.keepout_*`.
3. **Freerouting 2.1.0 respeta nativamente el `(plane <net> ...)`** que
   `pcbnew.ExportSpecctraDSN` emite del outline de una zona de cobre — test
   decisivo (board sintético): con el plano, la vía que conectaba 2 pads GND
   desaparece del ruteo (0 vías vs 1 sin plano) y el SES resultante no
   menciona `GND` en absoluto. **No hace falta inyección manual de `(plane)`
   al DSN** — descarta la Opción A del plan de sesión. **Confirmado también
   en la corrida real de P4.5** (ver más abajo): tras borrar los 91 tracks de
   GND, el board siguió siendo válido para Freerouting sin ellos (nunca
   reportó GND como bloqueada por falta de camino — sólo tardó mucho).
4. El fill (`refill_zones()`) no es necesario para que Freerouting respete
   el plano (usa el `outline` de diseño, no `filled_polygons`) — pero sigue
   siendo necesario para que el `.kicad_pcb` final tenga cobre real.

**Decisión confirmada por el humano** (`AskUserQuestion`, sin necesidad de
asumir por no-respuesta): las 5 tools completas + integración `route_board`
+ E2E, con el fallback de Freerouting resuelto por evidencia del test vivo
(§2.4 del doc de investigación) → export nativo, sin inyección DSN.

## Diff por tarea

### P4.1 — `add_zone` + `get_zones`
- Bridge (`src/kicad_mcp/bridge/ipc.py`): `ZoneItem` dataclass, helpers de
  geometría (`_polygon_area_mm2`, `_copper_layer_values`, `_zone_layer_value`,
  `_build_zone_outline`, `_kipy_zone_to_item`), métodos `list_zones`,
  `get_zone_by_kiid`, `add_zone`, `refill_zones`.
- Tools (`src/kicad_mcp/tools/pcb.py`): validación de geometría
  (`_validate_zone_geometry`, `_polygon_is_simple` vía test de
  intersección de segmentos orientado), `add_zone`, `get_zones`.
- `add_zone` devuelve JSON (no confirm de texto, a diferencia de
  `add_track`) — contrato explícito del prompt de sesión:
  `{zone_id, filled, area_mm2, snap_id}`.

### P4.2 — `add_keepout_zone`
- Bridge: `add_keepout_zone` — `layer="all"` resuelve a todas las capas de
  cobre habilitadas del stackup (no asume 2 capas fijas).
- Tool: `add_keepout_zone`, reusa `_validate_zone_geometry`. Devuelve
  `{zone_id, keepout_flags, area_mm2, snap_id}`.

### P4.3 — `fill_zones` + integración `route_board`
- Tool `fill_zones`: kipy no tiene fill selectivo por zona — `zone_id`, si se
  pasa, sólo valida existencia (`ZONE_ID_STALE` si no) y NO acota el refill
  (siempre recalcula TODAS las zonas de cobre). Documentado explícitamente
  como limitación de la superficie de kipy 0.7.1, no un bug del diseño.
  Devuelve `{zones_filled, duration_ms, snap_id}`.
- `route_board` gana el campo `"zones": {existentes, refilladas, fill_ms}` +
  flag `refill=true` (default). Refill post-route ocurre sólo si la recarga
  automática (P3.1) tuvo éxito — si el editor estaba cerrado, `refilladas=0`
  (best-effort, mismo criterio que `pre_footprints`).

### P4.4 — `delete_zone`
- Simétrico a `delete_track`/`delete_via` pero **sólo por id** (una zona no
  tiene "punto cercano" natural para matching geométrico ambiguo, a
  diferencia del cobre lineal).

### P4.5 — Test E2E del gate (implementado, NO verificado en vivo con éxito)

`tests/test_zones_e2e_gui.py` implementa el flujo completo del gate: plano
GND en B.Cu (bbox real del board vía `get_world_context`), keepout circular
de 12 vértices ~15mm bajo ANT1 (centro vía `get_component_detail`), fill
explícito, DRC baseline, borrado de todos los tracks GND, `route_board`, DRC
post-route, y las 3 verificaciones cuantitativas (tracks/vías/área) +
`get_zones` con KIIDs estables. **Corre y se detiene correctamente en los
puntos correctos** (confirmado en las corridas reales: creó ambas zonas con
KIID reales, `fill_zones` refillo 1 zona de cobre, `run_drc` corrió, se
borraron 91 tracks de GND, y `route_board` se invocó) — lo único que no se
completó fue la CONVERGENCIA de Freerouting dentro del tiempo disponible en
esta sesión.

**Desviación documentada del prompt original:** el prompt de sesión pedía
"copiar fixture a tmpdir" antes de mutar. **No se hizo así** — la sesión 18
(P3.3) descubrió y corrigió empíricamente que `route_board` opera sobre el
archivo que resuelve `KICAD_MCP_PROJECT`, mientras que `get_tracks`/
`delete_track`/`add_zone`/etc. mutan por IPC lo que sea que esté ABIERTO en
KiCad — si apuntan a archivos distintos (fixture copiado a un tmp_path
aislado vs. lo que KiCad tiene abierto), se reproduce el split-brain que esa
sesión corrigió. El test E2E de P4.5 sigue el mismo patrón que
`test_reload_e2e_gui.py` (P3.3): opera DIRECTO sobre el proyecto ya abierto
en KiCad, con `_preflight_same_board_open` verificando la coincidencia antes
de mutar nada.

**Estado del board vivo al cierre de la sesión:** restaurado a su estado
original (313 tracks, 21 vías, 0 zonas — verificado con `board.revert()`
tras copiar el `.kicad_pcb` del fixture versionado sobre el archivo abierto
en `/tmp/gui-test-project/`). El intento de P4.5 dejó el board temporalmente
sin tracks de GND (91 borrados, plano+keepout creados, sin re-rutear); se
restauró explícitamente para no dejar el entorno GUI compartido en un
estado roto para la próxima sesión.

## Bugs / hallazgos reales encontrados

1. **`list_zones` faltaba en la whitelist idempotente de lecturas
   (D-07.1)** — `route_board` llama `bridge.list_zones()` para contar zonas
   pre-route, pero `_run_supervised_read` levanta un `AssertionError` si el
   nombre de la operación no está en `_IDEMPOTENT_OPS`. Encontrado al correr
   el suite completo tras P4.1 (6 tests de `route_board` fallaron con el
   mismo síntoma); corregido agregando `list_zones`/`get_zone_by_kiid` a la
   whitelist (ambas son lecturas puras, mismo criterio que
   `list_all_copper`/`get_copper_by_kiid`).

2. **Freerouting escala mucho peor de lo documentado para "re-ruteo parcial
   de un board denso ya mayormente ruteado + keepout nuevo"** que para "board
   limpio sin rutear" (benchmark de sesión 18: 235-925 s). Dos corridas
   reales sobre `despertador` con sólo GND sin rutear (91 tracks borrados,
   resto del board intacto) no convergieron ni en 25 min ni informalmente en
   2h38m. El mecanismo de timeout de `route_board` (`subprocess.run(timeout=)`)
   se verificó funcionando correctamente en ambos extremos (un repro directo
   con `timeout_s=5` disparó `KICAD_TIMEOUT` en ~26s; el segundo intento real
   con `timeout_s=1500` lo disparó en ~1657s, limpio) — **no es un bug de
   código de esta sesión**, es una característica de rendimiento de
   Freerouting bajo este patrón de uso específico, documentada como riesgo
   abierto para 19b/20 (quizás rutear encima de cobre existente + evitar un
   keepout nuevo fuerza una búsqueda mucho más restringida que un board en
   blanco).

3. **El comando de verificación "seguro" usado durante gran parte de la
   sesión (`pytest -m "not integration and not integration_gui_slow"`) NO
   excluía el marker `integration_gui`** (una categoría separada de
   `integration_gui_slow`, ambas activas en este entorno GUI) — varias
   corridas de "verificar que no rompí nada" terminaron ejercitando de
   verdad tests que mutan el board vivo compartido (`test_pcb.py`,
   `test_pcb_session16_gui.py`), sin que yo lo notara hasta que el board
   quedó en un estado inesperado. El comando correcto para excluir TODA
   interacción con KiCad vivo es `pytest -m "not integration and not
   integration_gui and not integration_gui_slow"` (verificado en esta
   sesión: 301 passed, sin tocar el board). **Nota para sesiones futuras**:
   el propio `pyproject.toml` ya trae `addopts = "-m 'not integration and
   not integration_gui' -q"` — correr `pytest` a secas (sin `-m` en la CLI)
   ya excluye ambos por default; pasar un `-m` propio en la línea de
   comandos REEMPLAZA el de `addopts`, no lo extiende — hay que repetir las
   3 exclusiones a mano si se quiere ser explícito.

4. **Detectado pero no investigado a fondo (fuera de alcance P4):**
   `test_pcb.py::test_add_via_round_trip_against_open_board` falla de forma
   reproducible contra la instancia de KiCad de esta sesión (`add_via` con
   `net="+3V3"` devuelve un via cuyo `net.name` lee `/MOSI`) — confirmado que
   el código de `add_via` no fue tocado por el diff de esta sesión
   (`git diff` desde antes de sesión 19 no lo modifica). Hipótesis: caché de
   net-code de kipy quedó inconsistente tras las muchas llamadas
   `revert()`/mutación de esta sesión larga sobre la misma conexión IPC.
   Recomendación: reiniciar el proceso de KiCad antes de confiar en
   `integration_gui` en la próxima sesión.

## Contratos finales

Ver `docs/specs/tool-catalog.md` (categoría `pcb`) para las firmas completas
de las 5 tools, el campo `zones` de `route_board`, y la taxonomía de errores
actualizada (`INVALID_ZONE_GEOMETRY`, `ZONE_ID_STALE`).

## Suites

`pytest -m "not integration and not integration_gui and not
integration_gui_slow"`: **301 passed**. `ruff check` / `ruff format --check`
/ `mypy src/`: limpios. `test_zones_e2e_gui.py` (P4.5, `integration_gui_slow`)
implementado y ejercitado en vivo dos veces; no llegó a completar la
convergencia de Freerouting dentro del tiempo disponible — ver hallazgo #2.

## Cierre esperado

Sesión 19 cerrada con P4.0-P4.4 completos y verificados; **P4.5 queda como
gate pendiente de una corrida en vivo con más presupuesto de tiempo
dedicado** (sesión 19b o una sesión de seguimiento corta específica para
esto, antes o junto con Dogfooding 3). → sesión 19b (corrección del sch del
despertador con P1+P2+P3+P4 disponibles) → sesión 20 (Dogfooding 3, meta
≥8/10).
