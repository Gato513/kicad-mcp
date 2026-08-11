# Ficha 8 — `move_footprint` (post-mutación)

```
K = {_derive_post_state, _find_target, _register_post_snapshot, move_footprint}
```

Prior histórico: `docs/analisis/40-dt1-caracterizacion.md §5/§8`, cluster
"Post-mutación de move_footprint" (~117 LOC de helpers + 99 de la tool,
coincide casi exactamente con esta ficha: 216 LOC totales aquí).

## M1

```
LOC actual (suma) = 216
LOC de register() liberado = 99  (solo move_footprint es closure)
LOC de pcb.py liberado = 216
Closures eliminadas = 1
```

## M2

```
d1 = 1 {bridge}
d2 = 3: move_footprint -> _audit_error, move_footprint -> _resolve_board,
        move_footprint -> _similars   (los tres fuera de K)
d3 = 8 (..audit.logger, ..bridge.ipc, ..bridge.state_builder, ..errors,
        ..gates.g1, ..logging_config, ..snapshots, ._mutating)
d4 = 0
d5 = 0

M2_actual_vector = (1, 3, 8, 0, 0)
```

## S1 — **NO CUMPLE**

Mismo patrón que fichas 1/3: los 3 destinos de d2 son la "trío de utilidad
universal" (`_audit_error` 11 consumidores, `_resolve_board` 17
consumidores, `_similars` ≥9 consumidores) que ningún candidato individual
puede absorber sin afectar a los otros ~18 closures que también los
consumen.

```
Opción A: import-back -> arista módulo nuevo -> pcb.py, PROHIBIDA. S1 no cumple.
Opción B: inyección explícita -> d1 pasa de 1 a 4, EMPEORA. S8 no cumple.
```

## S2 — cumple (0 reexports, d4=0). S3 — moderada (closure + 3 helpers
propios, patrón `_derive_post_state`/`_register_post_snapshot` de
diff pre/post estado — más elaborado que un simple builder, pero sin
señales de complejidad "alta").

## S4 — Cobertura

Evidencia offline sólida:

```
tests/test_pcb.py::test_move_footprint_reports_component_not_found_with_similars:353
tests/test_pcb.py::test_move_footprint_rejects_out_of_bounds:385
tests/test_pcb.py::test_gate_g1_fires_once_per_session:443
(12 de 17 invocaciones call_tool offline+asertadas — raw/coverage.json)
```

`test_move_footprint_reports_component_not_found_with_similars` asertando
sobre el mensaje de "similars" es evidencia directa del camino que usa
`_similars`/`_find_target`. `COBERTURA_DEMOSTRADA` razonable para la
superficie observable del tool; `_derive_post_state`/`_register_post_snapshot`
(diff de estado pre/post) se ejercen transitivamente en el camino feliz —
`COBERTURA_INFERIDA` para sus ramas internas de diffing.

## S5 — cumple. S6 — `REFERENCIA_EXISTENTE` (bookkeeping de snapshot
pre/post, no geometría ni kiid — sin relación con DT3/P1-2).

## S7 — cumple por S7.a y S7.c

```
S7.a  99 >= 80    SÍ (por muy poco margen: 19 líneas sobre el umbral)
S7.c  216 >= 100  SÍ
```

## S8 — falla bajo Opción B; no evaluable con sentido bajo Opción A.

## R activados: R12 (Opción A) o S8 directa (Opción B).

## Veredicto individual: **NO_APTO** — tercer contraejemplo de H4 (CR7
REFUTADA: S7.a se cumple por apenas 19 líneas de margen, y aun así M2 no
mejora en ninguna dimensión bajo el diseño mínimo).
