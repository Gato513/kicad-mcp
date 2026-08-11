# Ficha 19 — `reload_board_from_disk`

```
K = {reload_board_from_disk}   (LOC=57, L1489-1545, @mcp.tool closure, no
                                 mutante — no lleva @mutating_tool: revierte
                                 estado vivo, no lo muta hacia adelante)
```

**Nota de divergencia LOC (H-S47EXT-01):** `enumeracion.md §6`/contrato §2
anotan LOC=59. Re-derivación de esta sesión: LOC=57. Ver
`04-hallazgos-fuera-de-scope-ext.md`. No altera el veredicto (57 < 80 con
ambos valores).

## M1 — Volumen

LOC actual = 57. 1 closure eliminada de `register()`. Reducción de `pcb.py`
= 57 LOC.

## M2 — Acoplamiento

```
M2_actual_vector = (d1=1, d2=1, d3=6, d4=0, d5=0)
d1_simbolos: ['bridge']
d2_aristas: [['reload_board_from_disk','_resolve_board','CALL']]
d3_modulos: ['..audit.logger', '..bridge.state_builder', '..errors',
             '..logging_config', '..snapshots', '._mutating']
d4_simbolos: []
d5_detalle: entrante_interna=[], entrante_src=[], entrante_tests=[]
```

Dependencia hacia `_resolve_board` (ficha 11 original, NO_APTO). Mismo
dilema latente (import-back viola S1; inyección sube d1 1→2, activa R11).
No determinante — S7 falla primero.

## M3 — Superficie observable

`@mcp.tool(name="reload_board_from_disk")`. Contrato de mapeo de error
propio y documentado: `PROJECT_NOT_FOUND` de `_resolve_board` se remapea
explícitamente a `ErrorCode.RELOAD_FAILED` (único remapeo de código entre
los 9 candidatos — es comportamiento observable ya existente, no una
propuesta de cambio; preservarlo intacto es parte de S2). Interactúa con
`get_default_store().clear_live_stale()` (D-14.1) — efecto de
sincronización con el guard de staleness usado por otras 9+ tools.

## M4 — Cobertura

`COBERTURA_DEMOSTRADA`: 4 tests offline tool-level con assert
(`tests/test_reload_board.py`: happy-registers-disk-snapshot-and-clears-
live-stale, is-idempotent-at-tool-level, no-board-open-raises-reload-failed,
busy-propagates-without-rewrapping), más 3 tests bridge-level en
`tests/test_ipc.py` (calls-revert-and-counts-tracks-vias,
is-idempotent-at-bridge-level, does-not-retry-on-busy) — evidencia adicional
**distinta**: ejercitan `bridge.reload_board_from_disk`, no la closure de la
tool, y por tanto no sustituyen la cobertura tool-level.

**Corrección C-EXT-02 (hallazgo MINOR de revisión independiente):** la
versión original declaraba "5 tests" contando
`is-idempotent-at-tool-level ×2`; en `tests/test_reload_board.py` hay una
sola prueba de idempotencia y 4 tests en total. El veredicto no cambia.

Sin tests `integration_gui` propios
listados en `coverage.json` (el flujo GUI se ejercita indirectamente vía
`test_reload_e2e_gui.py::test_iterative_routing_zero_human_reload_touches`,
que no aparece en la entrada `reload_board_from_disk` de `coverage.json`
pero sí en las de `get_tracks`/`save_board` — limitación metodológica
heredada de `05-veredicto.md §6`, misma vía de invocación dinámica
`call_tool(...)` no siempre trazada por path literal).

## Gates S1–S8

**S1:** no determinante — el estado actual cumple, pero el gate se evalúa
sobre la **extracción proyectada**, que aquí no se evalúa completamente
porque S7 rechaza primero (ver M2 y S7). No se afirma cumplimiento de S1
bajo extracción (corrección C-EXT-03).
**S2:** cumple, incluido el remapeo de error documentado arriba.
**S3:** simple.
**S4:** cumple, `COBERTURA_DEMOSTRADA`.
**S5:** cumple. **S6:** `REFERENCIA_EXISTENTE` (mecanismo de sincronización
disco↔vivo, sin relación con DT3/P1-2; interactúa con el guard de staleness
pero no con geometría de zona).
**S7:** NO cumple ninguna cuantitativa (57 < 80; 1 closure < 3; 57 < 100).
S7.d no demostrable — función ya de responsabilidad única (revertir +
snapshot + destrabar guard, las tres partes de UNA operación atómica de
sincronización, no una mezcla de responsabilidades separables).
**S8:** no determinante (S7 ya falla).

**R activado:** R11 (beneficio marginal, S7 no se satisface).

## Veredicto individual: **NO_APTO** (S7 sin dispensa E1 defendible)
