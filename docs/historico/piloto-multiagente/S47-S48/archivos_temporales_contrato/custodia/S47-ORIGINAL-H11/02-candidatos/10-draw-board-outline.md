# Ficha 10 — `draw_board_outline`

```
K = {_outline_params, draw_board_outline}
```

## M1

```
LOC actual (suma) = 87
LOC de register() liberado = 85 (solo draw_board_outline es closure;
                                    _outline_params son 2 líneas)
LOC de pcb.py liberado = 87
Closures eliminadas = 1
```

## M2

```
d1 = 1 {bridge}
d2 = 2: draw_board_outline -> _audit_error, draw_board_outline -> _resolve_board
d3 = 8 (mismo set base que fichas 1/8/9: ..audit.logger, ..bridge.ipc,
        ..bridge.state_builder, ..errors, ..gates.g1, ..logging_config,
        ..snapshots, ._mutating)
d4 = 0
d5 = 0

M2_actual_vector = (1, 2, 8, 0, 0)
```

## S1 — **NO CUMPLE** (mismo patrón, cuarta instancia — solo 2 de los 3
miembros del "trío universal" están involucrados aquí; `_similars` no se usa
en este tool, que no reporta sugerencias de nombre)

```
Opción A: import-back de _audit_error/_resolve_board -> arista módulo
  nuevo -> pcb.py, PROHIBIDA. S1 no cumple.
Opción B: inyección explícita -> d1 pasa de 1 a 3, EMPEORA. S8 no cumple.
```

## S2 — cumple. S3 — simple-moderada (closure de 85 líneas + 1 helper
trivial de 2 líneas — el segundo más simple de reconstruir de los closure-
bearing).

## S4 — Cobertura

```
tests/test_pcb.py::test_draw_board_outline_success:892
tests/test_pcb.py::test_draw_board_outline_rejects_existing_outline:922
tests/test_pcb.py::test_draw_board_outline_rejects_nonpositive_dims:945
(5 de 6 invocaciones call_tool offline+asertadas — la proporción más alta
 offline/total de los 5 candidatos closure-bearing)
```

`test_draw_board_outline_rejects_nonpositive_dims` con aserción sobre
validación de dimensiones da evidencia directa de un camino de validación
concreto. `COBERTURA_DEMOSTRADA` razonable para la superficie del tool.

## S5 — cumple. S6 — `REFERENCIA_EXISTENTE` (`_outline_params` construye un
dict de parámetros de rectángulo; no hay cálculo de distancia/colisión, la
adyacencia geométrica con DT3 es mínima comparada con fichas 3/6/9).

## S7 — cumple **solo** por S7.a (por muy poco margen)

```
S7.a  85 >= 80    SÍ (5 líneas de margen — el más ajustado de los 5
                       candidatos closure-bearing)
S7.c  87 < 100    NO
S7.b  1 < 3       NO
```

## S8 — falla bajo Opción B; no evaluable con sentido bajo Opción A.

## R activados: R12 (Opción A) o S8 directa (Opción B). Adicionalmente,
dado que S7 se satisface por el margen más estrecho de los 5 candidatos
sustanciales (85 vs umbral 80), este es el candidato donde H4 se refuta con
**menor margen de LOC** — el candidato "más débil" de los 5 en términos de
M1 puro, y aun así comparte exactamente el mismo defecto estructural de S1.

## Veredicto individual: **NO_APTO**.
