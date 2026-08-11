# 02 — Enumeración de candidatos (Fase 2, §7)

Herramientas: `$S47_TMP/tools/cluster.py` (semillas S1-S4 y expansión C1-C5 de
**v5** §§7.1.3-7.1.5, fuente `~/.local/share/Trash/files/contrato_S47-DT1-SLICE2-CARACTERIZACION_v5.md`
SHA-256 `3fc56ce82ae5c7a396bd667e55228785e2073ea556373846cf0696ed6c75b7a2`;
filtros F-DT.1-F-DT.4 con la **semántica corregida de v6** §7.1.6/§7.1.7).
Entrada: `raw/inventory.json`. Salida: `raw/clusters.json`.

## 1. Semillas (v5 §7.1.3)

```
S1  19 semillas — una por cada @mcp.tool de pcb.py.
S2  20 semillas — una por cada closure directa de register() (incluye las 19
    de S1 + _delete_copper; dedup en paso 3 cuando coincide con S1).
S3   9 semillas — helpers top-level con |consumidor(H) ∩ V| >= 2:
    _audit_error, _bbox_distance_to_point, _copper_distance_mm,
    _copper_in_bbox, _copper_on_layer, _resolve_board,
    _segment_intersects_bbox, _similars, _validate_zone_geometry.
S4   0 semillas — ninguna componente conexa del grafo no dirigido inducido
    sobre V, de tamaño >= 2, está compuesta EXCLUSIVAMENTE por helpers
    top-level. Toda componente conexa de tamaño >= 2 en este archivo incluye
    al menos una closure/mcp_tool (verificado exhaustivamente: unión-find
    sobre las 92 aristas tratadas como no dirigidas, 63 nodos).
```

## 2. Expansión (v5 §7.1.4) y deduplicación (Paso 3)

Cada semilla se expande a punto fijo por C1-C5 (single-consumer absorption,
constantes de único-consumidor). Tras expandir las 48 semillas (19+20+9+0) y
deduplicar por conjunto exacto de símbolos:

```
N_universo_total = 29
```

Lista completa de los 29 clusters (clave_orden = JSON de la lista ordenada de
nombres, `sort_keys=True`), en `raw/clusters.json` campo `clusters_all`.

## 3. Filtros (v6 §7.1.6/§7.1.7, Pasos 4-6)

### F-DT.1 — EXCLUSION_CATEGORIAL_INSTITUCIONAL (no refuta)

**Regla de membresía aplicada** (documentada explícitamente para que Codex
pueda refutarla — ver §7.1.1.bis, "toda clasificación debe ser explícita"):
un cluster K "toca zonas / route_board / stitching / add_zone / add_keepout
/ delete_tracks_bulk / delete_zone" si **(a)** K contiene directamente uno de
los 7 tools institucionales (`add_zone`, `add_keepout_zone`, `get_zones`,
`fill_zones`, `delete_zone`, `delete_tracks_bulk`, `route_board`), **o (b)**
K contiene un miembro cuyo conjunto de consumidores V es un subconjunto NO
VACÍO de esos 7 tools (es decir, el miembro existe únicamente para servir a
un tool institucional, aunque el cluster que lo contiene — materializado
desde una semilla S3/helper — no haya absorbido el tool mismo por expansión
de único-consumidor).

La regla (b) se descubrió necesaria en esta sesión: la primera pasada
(solo regla (a)) dejaba sobrevivir el cluster
`{_polygon_is_simple, _segments_intersect, _validate_zone_geometry}` como
candidato NO institucional, pese a que `_validate_zone_geometry` sólo tiene
dos consumidores en V — `add_zone` y `add_keepout_zone`, ambos
institucionales — verificado explícitamente:
`consumidor(_validate_zone_geometry) = {add_zone, add_keepout_zone}`. Se
verificó exhaustivamente contra los 29 clusters que ningún otro caso análogo
existe (`raw/clusters.json` no contiene más clusters afectados por la
regla (b) además de éste).

**Verificación de que no hay contaminación cruzada:** se confirmó (lectura
manual de cada sitio de llamada, `grep -n` citado en `01-inventario-actual.md`
§9 y cross-check con `docs/analisis/40-dt1-caracterizacion.md §5/§7`) que la
familia de helpers de "stitching" (`_match_orphan_pad`,
`_opposite_layer_blocked`, `_orphan_pad_dict`, `_evaluate_stitch_candidates`,
`_stitched_via_dict`, `_refill_enforce_and_save`) tiene como **único**
consumidor a `route_board` en cada caso — ninguno de estos helpers puede
materializarse en un cluster ajeno a `route_board` por construcción del
algoritmo C2 (single-consumer absorption exige que TODOS los consumidores de
`x` estén ya en K antes de absorberlo; como el único consumidor de estos
helpers es `route_board`, `route_board` siempre precede o co-ocurre en la
misma iteración que la absorción del helper).

**Resultado — 8 clusters excluidos institucionalmente:**

```
1. {_OPPOSITE_LAYER, _STITCH_RADIUS_MM, _evaluate_stitch_candidates,
    _find_duplicate_refs, _match_orphan_pad, _open_board_or_none,
    _opposite_layer_blocked, _orphan_pad_dict, _point_in_polygon,
    _refill_enforce_and_save, _stitched_via_dict, route_board}
    -> contiene route_board directamente. Coincide con el veto I-4 de S40.
2. {_polygon_is_simple, _segments_intersect, _validate_zone_geometry}
    -> regla (b): _validate_zone_geometry sirve solo a add_zone/add_keepout_zone.
3. {add_keepout_zone}
4. {add_zone}
5. {delete_tracks_bulk}
6. {delete_zone}
7. {fill_zones}
8. {get_zones}
```

Ver `descartados.md` para el detalle nominal.

```
N_excluidos_institucional = 8
```

### F-DT.2 — CONSUMIDOR_MONKEYPATCH_OBLIGATORIO (marca, no refuta)

```
MP_REACH = {route_board}   (único miembro de V que referencia run_drc/run_autoroute,
                              los dos únicos símbolos parcheados por ADR-0012 --
                              ver 01-inventario-actual.md §7)
```

`route_board` **siempre** cae en F-DT.1 (regla (a), membresía directa) antes
de llegar a la etapa de marcado F-DT.2 (Paso 4 del §7.1.7 se aplica antes que
el Paso 5). Consecuencia: **ningún survivor de este dataset queda marcado
F-DT.2** — `N_marcados_monkeypatch = 0`. Este es un hallazgo estructural
válido, no una omisión: en el estado actual de `pcb.py`, la única vía de
alcance a un símbolo cubierto por un monkeypatch ADR-0012 pasa por
`route_board`, que ya está institucionalmente segregado por razones
independientes (zonas/stitching). La regla de prioridad de F-DT.2 ("nunca
son omitidos por presupuesto antes de un candidato no marcado") es, por
tanto, vacía en este dataset — se deja constancia expresa.

### F-DT.3 / F-DT.4 — exclusiones presupuestarias

```
UMBRAL_F_DT3_LOC (LOC del cluster) = 400  -> ningún cluster de los 21
    supervivientes de F-DT.1 lo excede (máximo observado: 332 LOC, cluster
    de add_track — ver ficha 9). N_excluidos por F-DT.3 = 0.

UMBRAL_F_DT4_MODS (|frontera_entrante_src(K)|) = 3  -> frontera_entrante_src
    es la unión vacía para los 63 miembros de V sin excepción (01-inventario-
    actual.md §8). Ningún cluster puede alcanzar >= 3. N_excluidos por
    F-DT.4 = 0.
```

```
N_excluidos_presup = 0
```

## 4. Contadores del universo (§11.2 V0.7)

```
N_universo_total          = 29
N_excluidos_institucional = 8
N_excluidos_presup        = 0
N_marcados_monkeypatch    = 0
N_supervivientes          = 21     (= 29 - 8 - 0)
N_fichas_completas        = 12     (= min(21, UMBRAL_P_STOP_FICHAS=12))
N_evaluados                = 12
```

**Consecuencia directa para el veredicto (§11.3 regla 5, evaluada antes que
cualquier clasificación de ficha):**

```
N_supervivientes (21) > UMBRAL_P_STOP_FICHAS (12)
  -> materialización presupuestariamente incompleta
  -> EVIDENCIA_INSUFICIENTE es el techo del veredicto global,
     independientemente de lo que arroje la Fase 3 sobre las 12 fichas
     materializadas.
```

Ver `05-veredicto.md` para la aplicación formal de §11.3. Las 12 fichas se
materializan igualmente (V0.4 de §11.2 lo exige como precondición de
preflight de veredicto, y son evidencia valiosa para que el humano decida
H11 — reintentar con presupuesto ampliado).

## 5. Los 12 candidatos materializados (orden por `clave_orden`)

```
 1. {_DELETE_TOLERANCE_MM, _copper_candidate_dict, _delete_copper, _match_copper}     LOC=188
 2. {_audit_error}                                                                     LOC=8
 3. {_bbox_distance_to_point, _closest_board_edge, _closest_point_copper_bbox,
     _copper_distance_to_bbox, get_footprint_neighbors}                                LOC=207
 4. {_bbox_distance_to_point}                                                          LOC=11
 5. {_copper_distance_mm, _dist_point_segment}                                         LOC=30
 6. {_copper_in_bbox}                                                                  LOC=12
 7. {_copper_on_layer}                                                                 LOC=6
 8. {_derive_post_state, _find_target, _register_post_snapshot, move_footprint}        LOC=216
 9. {_dist_segment_to_pad, _find_track_pad_collision, _parse_pad_ref, _resolve_endpoint,
     _resolve_pad_coord, _rounded_rect_sdf, _track_params, add_track}                  LOC=332
10. {_outline_params, draw_board_outline}                                              LOC=87
11. {_resolve_board}                                                                   LOC=9
12. {_segment_intersects_bbox}                                                         LOC=34
```

Fichas individuales: `01-delete-copper.md`, `02-audit-error.md`,
`03-get-footprint-neighbors.md`, `04-bbox-distance-to-point.md`,
`05-copper-distance-mm.md`, `06-copper-in-bbox.md`, `07-copper-on-layer.md`,
`08-move-footprint.md`, `09-add-track.md`, `10-draw-board-outline.md`,
`11-resolve-board.md`, `12-segment-intersects-bbox.md`.

## 6. Los 9 supervivientes SIN ficha (excluidos por presupuesto de materialización)

Orden 13-21 por `clave_orden`, no evaluados en Fase 3 por agotamiento del
`UMBRAL_P_STOP_FICHAS`. Se listan con LOC como referencia para H11 (decisión
humana de reintento con presupuesto ampliado):

```
13. {_similars}                    LOC=13
14. {_via_params, add_via}         LOC=110  (2 miembros: 1 helper + add_via, closure)
15. {delete_track}                 LOC=51
16. {delete_via}                   LOC=24
17. {get_component_detail}         LOC=30
18. {get_tracks}                   LOC=92
19. {reload_board_from_disk}       LOC=59
20. {save_board}                   LOC=44
21. {set_footprint_ref}            LOC=116
```

(LOC obtenidos de `raw/inventory.json`, mismo método que §5.) Nótese que
`{_via_params, add_via}` (110 LOC) es del mismo orden de magnitud que varios
de los 12 materializados — su exclusión es puramente por posición en
`clave_orden` (orden lexicográfico determinista, no por relevancia), tal como
exige el contrato (§7.1.5: "orden total determinista", no un ranking de
interés). Esto es señal directa para H11.
