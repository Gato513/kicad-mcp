# Ficha 9 — `add_track` (resolución de endpoints de track)

```
K = {_dist_segment_to_pad, _find_track_pad_collision, _parse_pad_ref,
     _resolve_endpoint, _resolve_pad_coord, _rounded_rect_sdf, _track_params,
     add_track}
```

Prior histórico: `docs/analisis/40-dt1-caracterizacion.md §9`, "Resolución
de `add_track`" → `apto (alternativa)`. El de mayor LOC de los 12
materializados; también el de mayor `frontera_saliente_otras` (10 módulos).

## M1

```
LOC actual (suma) = 332  (el candidato más grande del universo, bajo el
                            umbral F-DT.3 de 400)
LOC de register() liberado = 167  (solo add_track es closure)
LOC de pcb.py liberado = 332
Closures eliminadas = 1
```

## M2

```
d1 = 1 {bridge}
d2 = 3: add_track -> _audit_error, add_track -> _resolve_board,
        add_track -> _similars
d3 = 10 (..audit.logger, ..bridge.ipc, ..bridge.rules_reader,
         ..bridge.state_builder, ..errors, ..gates.g1, ..logging_config,
         ..snapshots, ..tools.world, ._mutating)
d4 = 0
d5 = 0

M2_actual_vector = (1, 3, 10, 0, 0)
```

## S1 — **NO CUMPLE** (mismo patrón, tercera y más grande instancia)

```
Opción A: import-back de _audit_error/_resolve_board/_similars ->
  arista módulo nuevo -> pcb.py, PROHIBIDA. S1 no cumple.
Opción B: inyección explícita -> d1 pasa de 1 a 4, EMPEORA. S8 no cumple.
```

## S2 — cumple (0 reexports). S3 — moderada-alta: 7 helpers geométricos
(SDF de rectángulo redondeado, distancia segmento-pad, resolución de
coordenadas de pad) + 1 closure de 167 líneas — el candidato más complejo
de reconstruir mecánicamente de los 12 (más piezas móviles), aunque sin
señal concreta de "alta" irreversibilidad (todas las piezas son funciones
puras con firma explícita salvo `add_track` misma).

## S4 — Cobertura (la más fuerte de los 12 candidatos)

```
tests/test_pcb.py::test_add_track_reports_net_not_found_with_similars:409
tests/test_pcb.py::test_add_track_success_writes_audit_and_short_confirm:528
tests/test_pcb_session11.py::test_add_track_from_pad_resolves_coords:584
(13 de 28 invocaciones call_tool offline+asertadas — raw/coverage.json,
 el tool con más invocaciones call_tool en total de todo pcb.py: 28)
```

`test_add_track_from_pad_resolves_coords` asertando específicamente sobre
resolución de coordenadas de pad es evidencia directa de
`_resolve_pad_coord`/`_parse_pad_ref`/`_resolve_endpoint`.
`COBERTURA_DEMOSTRADA` razonable para el camino de resolución de pad;
`_rounded_rect_sdf`/`_find_track_pad_collision` (colisión con pads,
geometría SDF) se ejercen transitivamente sin aserción directa sobre la
fórmula — `COBERTURA_INFERIDA` para esas ramas específicas.

## S5 — cumple.

## S6 — Relación con P1-2/DT3: adyacencia geométrica notable

Este cluster es el **más intensamente geométrico** de los 12: SDF de
rectángulo redondeado, distancia segmento-a-pad, resolución de colisión
pad-track. Igual que fichas 3/4/5, DT3 está acotada textualmente a
"geometría de dominio **dentro de `bridge/`**" — este código vive en
`tools/pcb.py`, no en `bridge/`, y no comparte tipos de dominio geométrico
con `bridge/` (usa `PadGeom`/`CopperItem` como datos de entrada, no define
tipos geométricos nuevos). `REFERENCIA_EXISTENTE`, con hallazgo §14
(`DRIFT_AFECTA_CANDIDATO`) por la adyacencia temática con DT3, para que el
humano decida si vale la pena resolver DT3 antes de tocar esta familia de
helpers en una sesión futura.

## S7 — cumple por S7.a y S7.c

```
S7.a  167 >= 80    SÍ
S7.c  332 >= 100   SÍ
```

## S8 — falla bajo Opción B; no evaluable con sentido bajo Opción A.

## R activados: R12 (Opción A) o S8 directa (Opción B).

## Veredicto individual: **NO_APTO** — cuarto y más contundente
contraejemplo de H4: el candidato con la MAYOR reducción de LOC (167 en
register(), 332 en pcb.py) de todo el universo, y aun así M2 no mejora en
ninguna dimensión bajo el diseño mínimo — refuta con fuerza CR7 ("reducción
de LOC de register() es proxy suficiente de deuda").
