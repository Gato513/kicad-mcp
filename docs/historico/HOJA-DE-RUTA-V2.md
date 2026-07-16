# Hoja de ruta v2.1 — kicad-mcp (post-Dogfooding Etapa 1)

**Fecha:** 2026-07-12 · **Reemplaza a:** HOJA-DE-RUTA-V2.md
**Disparador:** Dogfooding Etapa 1 (2026-07-11, `dogfood-fricciones.md`,
nota 5/10). Los objetivos rectores y las decisiones D-R1..D-R7 de la v2
siguen vigentes; cambia el orden y contenido de las sesiones.

## Qué reveló el dogfooding (resumen ejecutivo)

- **Lectura y economía: excelentes.** TOON 24comp+41nets en ~1600 tok,
  delta "la joya", confirms ~25 tok, batching paralelo, 34 llamadas /
  0 crashes, G3 inviolable. No tocar lo que funciona.
- **Escritura: el loop no cierra.** Tres gaps estructurales:
  F-05 split-brain live/disco (sin `save_board`, render/DRC/export ven
  el board viejo); F-08 sin borrado (un track malo es permanente →
  DRC limpio inalcanzable); F-04/06 sin geometría de pads (colocar y
  rutear exige parsear el archivo crudo).
- **D-R3 respondido con números:** ruteo manual completo NO viable
  (~300 tok/track de razonamiento, 13 shorts en el subconjunto fácil,
  25-40 turnos extrapolados). → La condición de re-entrada de
  autorouter SE DISPARÓ.

## Decisiones nuevas (arquitecto, 2026-07-12)

- **D-R8 (borrado de cobre sin G2):** `delete_track`/`delete_via`
  entran sin gate interactivo — el cobre es re-agregable en un call y
  está protegido por G1+git; sin borrado el loop de DRC no cierra.
  Borrar footprints/componentes SIGUE siendo territorio G2 (no existe
  aún → fuera de scope). Se documenta la asimetría en ADR.
- **D-R9 (re-entrada de `get_component_detail`):** condición D-R7
  cumplida (el dogfooding lo demostró). Se implementa con bbox/
  courtyard + pads absolutos, bajo demanda. `get_net_detail` /
  `list_unconnected` siguen reservadas (sin evidencia todavía).
- **D-R10 (sin clearance-check en add_track):** no se reconstruye el
  DRC dentro de la tool. El loop save→DRC→delete→reintentar es el
  mecanismo. Se reabre solo si el Dogfooding 2 muestra tasa de shorts
  insoportable con el loop cerrado.
- **D-R11 (autorouter al plan):** spike en sesión 13 — Freerouting
  (export DSN → route → import SES) vs router de KiCad por IPC si
  existe. `add_track`/`add_via` quedan como retoque. Sin promesa de
  integración hasta el veredicto del spike.

## Plan de sesiones (v2.1)

| Sesión | Tipo | Contenido | Cierra fricciones |
|---|---|---|---|
| **11** | Dev | **Cerrar el loop de escritura PCB:** `save_board` · `delete_track`/`delete_via` (D-R8) · `get_component_detail` (D-R9) · `add_track` anclado a pads · quick wins F-01(doc)/F-02 | F-05, F-08, F-04, F-06, F-07, F-11 |
| **12** | Dev | **Flujo sch mínimo + calidad de loop:** A1 `set_value`+`set_footprint` · A2 `connect_pins` por labels (spike+tool) · A3 doc paleta · A5 `reload_in_gui` · `draw_board_outline` (Edge.Cuts) · F-10 DRC enriquecido/paginado | F-03, F-10 + flujo sch |
| **13** | Spike | **Autorouting (D-R11):** viabilidad Freerouting vs router IPC, medición sobre la placa del dogfooding, veredicto con números. Si es viable y barato: integración mínima | D-R3 |
| **14** | **Dogfooding Etapa 2** | Flujo end-to-end real: sch desde paleta → PCB → ruteo (con el veredicto del 13 aplicado) → DRC limpio → gerbers | Criterio de éxito del objetivo 1 |
| Flexible | Lab | Eval A (sin cambios de la v2) | — |

## Diferidos (v2 sin cambios) + nuevos

Los de la v2 siguen: multi-hoja (D-R1), librerías externas (D-R4),
Rust (ADR-0009), `get_net_detail`/`list_unconnected` (evidencia
pendiente), contador post_fallback.

Nuevos diferidos con condición:
- **Clearance-check en add_track (D-R10):** si Dogfooding 2 reprueba.
- **`undo` por snap:** el borrado dirigido (D-R8) cubre el caso medido;
  undo genérico si el uso real lo pide.
- **Paginación general de tools:** solo `run_drc` mostró necesidad
  (F-10, va en la 12); el resto sin evidencia.

## Puntos de re-evaluación

Tras la sesión 13 (veredicto autorouter) y tras el Dogfooding 2. La
nota objetivo del Dogfooding 2 es ≥8/10 con el loop cerrado — si no se
alcanza, se re-prioriza con el nuevo log de fricciones.
