# 04 — Colisiones con riesgos fuera de scope (extensión 13-21)

Conforme a v6 §9 (Fase 4). Ninguna de las 9 fichas cruza zonas prohibidas
(S5 cumple en las 9: sin tocar `route_board`/`fill_zones`/`add_zone`/
`add_keepout_zone`/`delete_zone`/`delete_tracks_bulk`/stitching).

## Colisiones temáticas registradas

| # | Candidato | Colisión | Categoría S6 |
|---|---|---|---|
| 13 | `_similars` | Ninguna — utilidad de UX de error, sin geometría | `REFERENCIA_EXISTENTE` |
| 14 | `{_via_params, add_via}` | Comparte `bridge.ipc`/`gates.g1` con familia de mutación de cobre (add_track, delete_track/via) | `REFERENCIA_EXISTENTE` |
| 15 | `delete_track` | Comparte `_delete_copper` con ficha 1 (original, NO_APTO) | `REFERENCIA_EXISTENTE` |
| 16 | `delete_via` | Comparte `_delete_copper` con ficha 1 (original, NO_APTO) y con ficha 15 de esta extensión | `REFERENCIA_EXISTENTE` |
| 17 | `get_component_detail` | Consumido incidentalmente por tests GUI de zonas (H-S47EXT-01 §Colisión DT3) | `REFERENCIA_EXISTENTE` |
| 18 | `get_tracks` | Consumido incidentalmente por tests GUI de zonas/rerouting; mayor `d2` de los 9 (6 aristas) | `REFERENCIA_EXISTENTE` |
| 19 | `reload_board_from_disk` | Interactúa con `get_default_store().clear_live_stale()`, guard compartido con `route_board`/D-14.1 | `REFERENCIA_EXISTENTE` |
| 20 | `save_board` | Primitiva de persistencia invocada por `route_board`/`fill_zones` bajo D-23.2 (ADR-0012); no implementa refill por sí misma | `REFERENCIA_EXISTENTE` |
| 21 | `set_footprint_ref` | Ninguna — resolución de refs duplicados, ADR-0013/ADR-0010 | `REFERENCIA_EXISTENTE` |

Ninguna asciende a `CAMBIO_INCIDENTAL` ni `PRERREQUISITO` (S6 cumple en las
9, igual que en 6/12 del paquete original que también citaron
`REFERENCIA_EXISTENTE`). Ningún hallazgo nuevo de colisión más allá de lo ya
registrado en `04-hallazgos-fuera-de-scope-ext.md`.

## Nota sobre D-23.2 / ADR-0012 (save_board, ficha 20)

`save_board` es la primitiva que `route_board`, `fill_zones` y
`add_zone(fill=True)` invocan como parte de su contrato de persistencia
(regla de código 7 de CLAUDE.md, ADR-0012). Esta ficha **no propone ningún
cambio de comportamiento de persistencia** — solo evalúa la viabilidad
estructural de mover el código de `save_board` a un módulo nuevo,
preservando su contrato exacto. El veredicto `NO_APTO` (S7 insuficiente) no
tiene relación con D-23.2; se documenta la adyacencia por transparencia, no
porque constituya un riesgo de colisión real.
