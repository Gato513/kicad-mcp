# 02 — Candidatos descartados (F-DT.1 institucional + F-DT.3/F-DT.4 presupuestario)

Por diseño de v6 §7.1.7 Paso 5, los candidatos marcados F-DT.2 **no**
aparecen aquí (reciben ficha completa). En este dataset `N_marcados_monkeypatch
= 0` de todas formas (ver `enumeracion.md` §3).

## F-DT.1 — EXCLUSION_CATEGORIAL_INSTITUCIONAL (8 clusters)

No se refutan por criterio R; se excluyen por decisión institucional del
contrato (§13.2, zonas prohibidas de S47). Motivo uniforme: "frontera
segregada institucional" (zonas/route_board/stitching).

| # | Cluster | LOC | Motivo específico |
|---|---|---|---|
| 1 | `{_OPPOSITE_LAYER, _STITCH_RADIUS_MM, _evaluate_stitch_candidates, _find_duplicate_refs, _match_orphan_pad, _open_board_or_none, _opposite_layer_blocked, _orphan_pad_dict, _point_in_polygon, _refill_enforce_and_save, _stitched_via_dict, route_board}` | 456 | Contiene `route_board` directamente. Familia "stitching/refill" completa. Coincide con el veto histórico I-4 de `docs/analisis/40-dt1-caracterizacion.md §9` (route_board usa `run_drc`/`run_autoroute`, monkeypatcheados por 4 archivos de test — ver `01-inventario-actual.md §7`). |
| 2 | `{_polygon_is_simple, _segments_intersect, _validate_zone_geometry}` | 71 | `_validate_zone_geometry` sirve exclusivamente a `add_zone` y `add_keepout_zone` (regla (b) de `enumeracion.md §3`) — "toca zonas" aunque no incluya el nombre del tool. |
| 3 | `{add_keepout_zone}` | 76 | Tool institucional directo (zonas/keepouts). |
| 4 | `{add_zone}` | 118 | Tool institucional directo (zonas). |
| 5 | `{delete_tracks_bulk}` | 130 | Tool institucional directo (nombrado explícitamente en F-DT.1). |
| 6 | `{delete_zone}` | 44 | Tool institucional directo (nombrado explícitamente en F-DT.1). |
| 7 | `{fill_zones}` | 89 | Tool institucional directo (zonas, contrato D-23.2/ADR-0012). |
| 8 | `{get_zones}` | 76 | Tool institucional directo (familia de zonas). |

LOC obtenidos de `raw/inventory.json` (suma de LOC por miembro).

## F-DT.3 (`EXCLUSION_PRESUPUESTARIA_TAMAÑO`, LOC > 400)

**Ninguno.** El cluster superviviente de mayor LOC es el de `add_track`
(332 LOC, ficha 9), bajo el umbral de 400.

## F-DT.4 (`EXCLUSION_PRESUPUESTARIA_ACOPLAMIENTO`, `|frontera_entrante_src| >= 3`)

**Ninguno.** `frontera_entrante_src(K) = ∅` para los 63 miembros de V sin
excepción (`01-inventario-actual.md §8`) — el máximo alcanzable por
cualquier K es 0, muy por debajo del umbral 3.

## Totales

```
N_excluidos_institucional = 8
N_excluidos_presup        = 0
```
