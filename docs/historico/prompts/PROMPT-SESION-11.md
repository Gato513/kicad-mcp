# Sesión 11 — Cerrar el loop de escritura PCB

**Rama:** `sesion-11` (desde `master`). Un commit por tarea. No pushear.
**Entorno vivo:** KiCad 10.0.4 con el PCB Editor cargado sobre
`/tmp/gui-test-project/video.kicad_pcb` (el proyecto de PRUEBA, no el del
dogfooding), env vars exportadas, `verificar_entorno.py` en verde modo
`integration_gui`.

Leé antes de empezar: `CLAUDE.md`, `docs/HOJA-DE-RUTA-V2.1.md` (nueva —
decisiones D-R8..D-R11), y **`docs/sesiones/dogfood-fricciones.md`**
completo — esta sesión existe para cerrar F-05, F-08, F-04/F-06/F-07/F-11.
El log describe con precisión qué necesitaba el agente usuario; ese es
el contrato de esta sesión.

---

## Decisiones vinculantes del arquitecto

- **D-11.1 (`save_board`):** tool que persiste el board vivo a disco
  vía IPC (kipy expone el save de documento — verificá el método real
  en el código instalado; si kipy 0.7.1 no lo expone, reportá ANTES de
  buscar alternativas exóticas). Semántica con el Snapshot Store: tras
  el save exitoso, registrar un snapshot NUEVO de disco (mtimes
  frescos) y ecoar su snap_id en el confirm — el estado vivo y el disco
  convergen y la cadena de snapshots lo refleja. G1 aplica (backup
  pre-write la primera vez por sesión, como las demás mutaciones).
  Confirm ≤50 tokens. Errores: sin board abierto → el mapeo D-07.2;
  busy → sin retry (es escritura, D-07.1).
- **D-11.2 (borrado de cobre, D-R8):** `delete_track` y `delete_via`.
  SIN Gate G2 (decisión D-R8: el cobre es re-agregable y está protegido
  por G1+git; la asimetría con footprints se documenta en ADR nuevo).
  Identificación del target: por **coincidencia geométrica + net** —
  `delete_track(net, near_x, near_y)` borra la track de esa net cuyo
  segmento pasa más cerca del punto (tolerancia documentada, p. ej.
  0.5 mm); `delete_via(net, x, y)` ídem por posición. Para resolverlo,
  el bridge necesita leer tracks/vias con sus KIIDs (extendé
  `read_board_context` o una lectura específica — argumentá el costo).
  Si hay ambigüedad (2+ candidatos dentro de la tolerancia) →
  `INVALID_PARAMS` con los candidatos en `data` (posiciones/endpoints)
  para que el agente refine — NUNCA borrar "el más cercano" en
  ambigüedad. Borrado usa `remove_items` (ya validado en teardowns).
  Confirm ≤50 tok con snap nuevo (derivado del pre-estado, patrón
  D-08.2). Verificación de efecto en tests: el ítem ya no está
  (integration_gui round-trip: add → delete → verificar ausencia).
- **D-11.3 (`get_component_detail`, D-R9):** tool nueva (el nombre sale
  de reservados — F3 permite, estaba reservado para esto).
  `get_component_detail(ref, kind="pcb")` → posición y rotación del
  footprint, bbox/courtyard (WxH y esquinas absolutas), y lista de pads
  con: número, net, posición ABSOLUTA (origen + offset rotado — la
  cuenta que el agente del dogfooding hizo a mano en 40 líneas de
  Python), tamaño y capa. Presupuesto: un IC de ~30 pads debe caber en
  ≤~300 tokens — formato compacto tipo TOON, no JSON verboso. Fuente:
  el board vivo si está abierto (los datos ya viajan en
  `FootprintData` — extendela con lo que falte); sin board → error
  tipado con hint. `kind="sch"` queda para el futuro
  (INVALID_PARAMS con hint honesto por ahora).
- **D-11.4 (`add_track` anclado a pads):** parámetros alternativos
  `from_pad`/`to_pad` con formato `"REF.PAD"` (p. ej. `"U1.8"`).
  Mutuamente excluyentes con las coordenadas crudas (una u otra forma,
  INVALID_PARAMS si mezcla). La resolución pad→coordenada absoluta usa
  la misma lógica de D-11.3. `add_via` puede ganar `at_pad` si sale
  gratis; no lo fuerces.
- **D-11.5 (quick wins):**
  - F-02: TODOS los exports devuelven ruta ABSOLUTA final en el
    confirm/respuesta.
  - F-01: documentar en el catálogo que `focus_ref` sin `radius_mm`
    no recorta, y agregar al header TOON un indicador cuando NO hubo
    recorte (p. ej. `area:full`) para que el agente sepa qué recibió.
  - F-03 (parcial, barato): el header TOON de `kind="pcb"` incluye el
    bbox del board y si existe contorno Edge.Cuts (`outline:none` |
    `outline:WxHmm`). Dibujar el contorno es de la sesión 12; saberlo
    es de esta.

---

## Fase 0

`verificar_entorno.py` verde en `integration_gui`; smoke `-k version`;
suite de arranque (123 unit esperados).

## Tarea 1 — `save_board` (D-11.1)

Implementación + catálogo + tests: unit con fakes (save feliz, sin
board, busy sin retry, snapshot de disco registrado con mtimes frescos)
+ integration_gui: mover un footprint → `save_board` → verificar que el
`.kicad_pcb` en disco CAMBIÓ (mtime + posición nueva parseada del
archivo) → restaurar posición + save de teardown. Este test es el
cierre literal de F-05: mutación visible en disco sin humano.

## Tarea 2 — `delete_track` / `delete_via` (D-11.2)

Implementación + ADR de la asimetría D-R8 + catálogo + tests: unit
(borrado feliz, ambigüedad → INVALID_PARAMS con candidatos, net
inexistente, nada dentro de tolerancia) + integration_gui round-trip:
`add_track` → `delete_track` → verificar ausencia vía kipy → ídem via.

## Tarea 3 — `get_component_detail` (D-11.3)

Implementación + catálogo (sale de reservados) + tests: unit con fake
(pads absolutos con rotación 0/90/180/270 — la rotación es donde vive
el bug típico; verificá contra posiciones conocidas del fixture) +
integration_gui contra el board real: pedir detail de una ref con
rotación no-cero y contrastar 2-3 pads contra lo que reporta kipy
directamente. Medí tokens de un IC grande (U19, 72 pads) y de una R
de 2 pads.

## Tarea 4 — `add_track` anclado a pads (D-11.4)

Implementación + catálogo + tests: unit (resolución REF.PAD, ref
inexistente, pad inexistente, mezcla de formas → INVALID_PARAMS) +
integration_gui: rutear entre dos pads reales por nombre y verificar
endpoints contra las posiciones de esos pads (±1 nm).

## Tarea 5 — Quick wins (D-11.5)

Los tres puntos, cada uno con su test. Actualización de catálogo donde
aplique.

## Tarea 6 — El test que faltó: loop completo sin humano

Un integration_gui de integración TOTAL que reproduce el flujo del
dogfooding SIN humano (la demostración de que F-05+F-08 murieron):

```
get_world_context(pcb) → get_component_detail(ref) →
move_footprint → add_track(from_pad→to_pad) → save_board →
export_render (verificar que el PNG CAMBIÓ respecto del inicial: md5
distinto — el test literal que falló en F-05) → run_drc →
delete_track → save_board → run_drc (una violación menos o igual)
```

Con teardown que restaura. Este test es el DoD conceptual de la sesión.

---

## Fuera de scope

- `delete_footprint` o borrado de cualquier cosa que no sea cobre
  (G2, D-R8).
- Clearance-check en add_track (D-R10).
- `undo` genérico por snap.
- Edge.Cuts como tool de dibujo, DRC paginado, flujo sch → sesión 12.
- Autorouter → sesión 13 (D-R11).

## Definition of Done

```
uv run pytest -m "not integration and not integration_gui"  → verde
uv run pytest -m integration                                → verde (< 5:00)
uv run pytest -m integration_gui                            → verde, incluido el loop completo de T6
uv run mypy src/                                            → Success strict
uv run ruff check + format --check                          → clean
```

## Reporte final obligatorio

1. Estado por tarea. Para T1: cómo expone kipy el save (cita de código).
2. Output literal del test de loop completo (T6) — es la prueba de que
   F-05 y F-08 están muertos.
3. tokens_est de `get_component_detail` (IC de 72 pads vs R de 2 pads)
   y de los confirms nuevos (save/delete). Promedios: global ≤400,
   confirms ≤50.
4. Mapa fricción→estado: para cada F-01..F-11 del dogfooding, una
   línea: CERRADA (por qué tarea) / PARCIAL (qué falta) / DIFERIDA
   (dónde vive en la hoja de ruta). Este mapa abre el prompt del
   Dogfooding 2.
5. Tiempos de suites.
6. Dudas abiertas y lo que la sesión 12 debería saber.
