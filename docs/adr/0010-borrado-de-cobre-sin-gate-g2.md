# ADR-0010 — Borrado de cobre (`delete_track`/`delete_via`) sin Gate G2

**Fecha:** 2026-07-12 · **Estado:** aceptado · **Fuente:** sesión 11 (D-R8, D-11.2)

## Contexto

El Dogfooding Etapa 1 (`docs/sesiones/dogfood-fricciones.md`, F-08) demostró
que la superficie de mutación era **solo aditiva** (`move_footprint`,
`add_track`, `add_via`, `add_symbol`): un track mal ruteado era permanente
desde las tools. Sin borrado, el loop `save → DRC → corregir` no cierra —
llegar a un DRC limpio (y por lo tanto abrir el Gate G3 de fabricación) es
**inalcanzable** por un agente autónomo. F-08 quedó, junto con F-05, como uno
de los dos gaps bloqueantes del MVP de escritura.

El sistema de Gates (`docs/adr/0003`) define **G2** como el gate interactivo
para operaciones destructivas de alto impacto (borrado de footprints /
componentes). G2 no existe todavía en el código. La pregunta de diseño es:
¿el borrado de **cobre** (tracks/vias) debe esperar a G2, o entra sin gate?

## Decisión

`delete_track` y `delete_via` entran en la categoría `pcb` **sin Gate G2**.
Quedan protegidos únicamente por:

1. **G1** — backup + checkpoint git una vez por sesión (igual que toda
   mutación). El estado pre-sesión siempre es recuperable.
2. **git** — el proyecto vive en un repo; cualquier borrado es reversible con
   un `git checkout` del `.kicad_pcb` mientras el agente no haya `save`+commit.
3. **Audit JSONL** — cada borrado (aceptado o rechazado) deja una línea con el
   KIID borrado, el net y el punto pedido.

Borrar **footprints / componentes / zonas** SIGUE siendo territorio de G2 (que
no existe aún → fuera de scope). La asimetría es deliberada.

## Justificación de la asimetría

- **El cobre es re-agregable en un call.** Un track borrado se recrea con un
  único `add_track` (idealmente `add_track(from_pad, to_pad)`, D-11.4); una via
  con `add_via`. El costo de un borrado erróneo es un re-add barato. Un
  footprint borrado, en cambio, arrastra su definición de librería, sus pads,
  su courtyard y su rol en el netlist — recrearlo no es un call, es un
  problema de re-instanciación (hoy ni siquiera existe `place_footprint`).
- **El borrado de cobre es la contraparte OBVIA de `add_*`.** Sin él, la
  superficie es un mutador manco (dogfooding, nota 5/10). Meterlo detrás de un
  gate interactivo reintroduce al humano en cada ciclo de corrección de DRC —
  exactamente la dependencia que la sesión 11 existe para eliminar.
- **La identificación es dirigida, no masiva.** El borrado es por
  coincidencia geométrica + net de UN ítem (el más cercano dentro de
  tolerancia). Ante ambigüedad (2+ candidatos dentro de tolerancia) se
  RECHAZA con `INVALID_PARAMS` y se listan los candidatos — **nunca** se borra
  "el más cercano" a ciegas. No hay borrado en lote, no hay `clear_net`, no hay
  wildcard. El radio de daño de un call es exactamente un segmento/una via.
- **G1 + git ya cubren el peor caso.** El escenario que G2 protege ("borré algo
  caro y no lo puedo deshacer") no aplica: pre-`save`, el disco está intacto;
  pre-sesión, el backup G1 lo tiene; siempre, git lo tiene.

## Consecuencias

- El loop de DRC cierra sin humano: `add_track → save → run_drc → delete_track
  → save → run_drc` es ejecutable de punta a punta por el agente (verificado en
  el test integration_gui de loop completo, sesión 11 T6).
- Si el Dogfooding Etapa 2 muestra que el agente se auto-inflige borrados
  costosos de cobre con frecuencia, se reabre la discusión de un gate más
  liviano (confirmación no interactiva / dry-run) — pero la evidencia actual
  (borrado dirigido + G1 + git) no lo justifica.
- La decisión NO crea precedente para bajar footprints/zonas de G2: la
  re-agregabilidad barata es la propiedad que habilita la excepción, y no la
  tienen los footprints.

## Alternativas descartadas

- **Esperar a G2 e implementarlo ahora.** Costo alto (gate interactivo mono-
  usuario sobre IPC) para proteger algo re-agregable en un call; retrasa el
  cierre de F-08 sin beneficio proporcional.
- **`undo` genérico por snap.** Más potente pero más complejo y con semántica
  ambigua contra el undo nativo de KiCad; el borrado dirigido cubre el caso
  medido. Queda diferido con condición (hoja de ruta v2.1).
