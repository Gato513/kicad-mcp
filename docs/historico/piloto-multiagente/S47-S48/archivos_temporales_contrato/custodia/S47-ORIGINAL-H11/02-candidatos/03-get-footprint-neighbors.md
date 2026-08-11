# Ficha 3 — `get_footprint_neighbors` (vecindad geométrica)

```
K = {_bbox_distance_to_point, _closest_board_edge, _closest_point_copper_bbox,
     _copper_distance_to_bbox, get_footprint_neighbors}
```

Prior histórico: `docs/analisis/40-dt1-caracterizacion.md §9`, "Vecindad
geométrica" → `apto (alternativa menor)`. Reaparece intacto en esta sesión.

## M1 — Volumen

```
LOC actual (suma) = 207
LOC de register() liberado = 144 (solo get_footprint_neighbors es closure)
LOC de pcb.py liberado = 207
Closures eliminadas = 1
```

## M2 — Acoplamiento

```
d1 = 1 {bridge}
d2 = 4:
   _copper_distance_to_bbox -> _segment_intersects_bbox  (fuera de K — ficha 12)
   get_footprint_neighbors  -> _TRACKS_BUDGET_SAFETY      (constante, fuera de K)
   get_footprint_neighbors  -> _TRACKS_DEFAULT_BUDGET     (constante, fuera de K)
   get_footprint_neighbors  -> _resolve_board              (fuera de K — ficha 11)
d3 = 4 (..bridge.ipc, ..errors, ..logging_config, ..snapshots)
d4 = 0
d5 = 0 (entrante_interna = entrante_src = entrante_tests = ∅)

M2_actual_vector = (1, 4, 4, 0, 0)
```

## S1 — **NO CUMPLE**

`_copper_distance_to_bbox` llama a `_segment_intersects_bbox`, que **no**
forma parte de K (es un candidato propio, ficha 12, con otros 2
consumidores propios — `delete_tracks_bulk` [institucionalmente excluido] y
`_copper_in_bbox` [ficha 6]). Igual que en la ficha 1:

```
Opción A: importar _segment_intersects_bbox y _resolve_board DESDE pcb.py
  -> arista módulo_nuevo -> pcb.py, PROHIBIDA. S1 no cumple. R12.
Opción B: inyectar ambos como parámetros explícitos
  -> d1_proyectado pasa de 1 a 3 (bridge + segment_intersects_fn +
     resolve_board_fn), EMPEORA. S8 no cumple.
```

Las dos constantes (`_TRACKS_BUDGET_SAFETY`, `_TRACKS_DEFAULT_BUDGET`) no
generan el mismo problema — importar un valor constante desde pcb.py NO es
una arista de dependencia funcional cíclica en el sentido de S1 (no hay
lógica ni closure involucrada, es un valor). Se documenta pero no cambia el
veredicto de S1, ya dictaminado por los dos casos de función arriba.

## S2 — cumple (0 reexports nuevos, d4=0). S3 — moderada (1 closure +
4 helpers, mismo patrón que ficha 1). S5 — cumple.

## S4 — Cobertura

`get_footprint_neighbors` tiene evidencia offline sólida con `assert`:

```
tests/test_pcb_session21_neighbors.py::test_get_footprint_neighbors_finds_pad_in_radius:198
tests/test_pcb_session21_neighbors.py::test_get_footprint_neighbors_holes_own_and_foreign:277
tests/test_pcb_session21_neighbors.py::test_get_footprint_neighbors_closest_edge:308
(6 de 9 invocaciones call_tool son offline+asertadas — raw/coverage.json)
```

`test_get_footprint_neighbors_closest_edge` en particular asertando sobre
"closest edge" da evidencia directa de que el camino `_closest_board_edge`
SÍ se ejercita con una aserción que depende de él —
**`COBERTURA_DEMOSTRADA`** razonable para la superficie del tool. Los
helpers internos de distancia (`_bbox_distance_to_point`,
`_copper_distance_to_bbox`) se ejercen transitivamente —
`COBERTURA_INFERIDA` para sus ramas internas específicas (p.ej. la fórmula
exacta de distancia punto-segmento).

## S6 — Relación con P1-2/DT3

Cluster **geométrico** (distancias bbox/punto/segmento). DT3 está acotada
explícitamente a "geometría de dominio **dentro de `bridge/`**"
(`docs/BACKLOG.md:519`); este cluster vive en `tools/pcb.py`. No hay tipos
compartidos con `bridge/` más allá de `IpcBridge`/`BoardHandle` (uso normal,
no geometría de dominio). `REFERENCIA_EXISTENTE`. Se deja constancia de la
adyacencia temática (ambos tratan "geometría") como hallazgo §14
(`DRIFT_AFECTA_CANDIDATO`, ver `04-hallazgos-fuera-de-scope.md`) para que
Codex/el humano lo pondere, sin escalarlo a `PRERREQUISITO` porque la
ubicación física (bridge/ vs tools/) es un criterio objetivo y verificable
que las separa.

## S7 — cumple por S7.a y S7.c

```
S7.a  144 >= 80   SÍ
S7.c  207 >= 100  SÍ
```

## S8 — falla bajo Opción B; no evaluable con sentido bajo Opción A (S1 ya
refutada).

## R activados: **R12** (Opción A) o **S8 directa** (Opción B).

## Veredicto individual: **NO_APTO** — mismo patrón estructural que la
ficha 1: alta reducción de LOC/register() (S7 cumple limpiamente) pero
acoplamiento hacia helpers compartidos fuera del cluster impide S1+S8
simultáneos. Segundo contraejemplo de H4 (CR7 REFUTADA).
