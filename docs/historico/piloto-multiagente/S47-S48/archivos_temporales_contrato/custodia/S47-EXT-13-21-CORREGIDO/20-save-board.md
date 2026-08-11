# Ficha 20 — `save_board`

```
K = {save_board}   (LOC=35, L1446-1480, @mcp.tool closure)
```

**Nota de divergencia LOC (H-S47EXT-01):** `enumeracion.md §6`/contrato §2
anotan LOC=44. Re-derivación de esta sesión: LOC=35. Ver
`04-hallazgos-fuera-de-scope-ext.md`. No altera el veredicto (35 < 80 con
ambos valores).

## M1 — Volumen

LOC actual = 35. 1 closure eliminada de `register()`. Reducción de `pcb.py`
= 35 LOC.

## M2 — Acoplamiento

```
M2_actual_vector = (d1=1, d2=1, d3=7, d4=0, d5=0)
d1_simbolos: ['bridge']
d2_aristas: [['save_board','_resolve_board','CALL']]
d3_modulos: ['..audit.logger', '..bridge.state_builder', '..gates.g1',
             '..logging_config', '..snapshots', '..tools.world', '._mutating']
d4_simbolos: []
d5_detalle: entrante_interna=[], entrante_src=[], entrante_tests=[]
```

Dependencia hacia `_resolve_board` (ficha 11 original, NO_APTO). Mismo
dilema latente que fichas 17/19 (import-back viola S1; inyección sube d1
1→2, activa R11). No determinante — S7 falla primero. `save_board` tiene el
mayor `d3` (7 módulos externos) de los 9 candidatos que no satisfacen S7 —
señal cualitativa adicional de que, aunque S7 fuera dispensado, el diseño
de extracción tendría más superficie de importación que la mayoría de sus
pares.

## M3 — Superficie observable

`@mcp.tool(name="save_board")`, `@mutating_tool("save_board")`. Contrato
D-23.2 (ADR-0012) **no aplica directamente** a `save_board` — el contrato
D-23.2 gobierna `route_board`, `fill_zones` y `add_zone(fill=True)`
(refill+persist); `save_board` es la primitiva de persistencia simple que
esas tools invocan como parte de su propio flujo, pero por sí sola no
implementa la semántica de refill. Ningún cambio de comportamiento de
persistencia se propone en esta ficha (solo movimiento de código) — S2
cumple, y no se toca ADR-0012.

## M4 — Cobertura

`COBERTURA_DEMOSTRADA`: 5 tests offline con assert
(`tests/test_pcb_session11.py`: happy-registers-disk-snapshot-fresh-mtimes,
no-board-errors, busy-propagates-without-retry,
external-edit-detected-without-base-snap,
proceeds-when-store-has-no-disk-anchor-yet) + 1 test offline adicional en
`tests/test_route_board.py`
(`test_route_board_then_save_board_does_not_clobber_disk_when_reload_unavailable`,
relevante para D-23.2 aunque `save_board` no sea el sujeto de ese ADR) + 8
tests `integration_gui`/`integration_gui_slow`.

## Gates S1–S8

**S1:** no determinante — el estado actual cumple, pero el gate se evalúa
sobre la **extracción proyectada**, que aquí no se evalúa completamente
porque S7 rechaza primero (ver M2 y S7). No se afirma cumplimiento de S1
bajo extracción (corrección C-EXT-03).
**S2:** cumple. **S3:** simple.
**S4:** cumple, `COBERTURA_DEMOSTRADA` amplia, incluida cobertura cruzada
con `route_board`.
**S5:** cumple (no implementa refill/zonas, solo invoca `bridge.save_board`
+ registra snapshot). **S6:** `REFERENCIA_EXISTENTE` — es la primitiva de
persistencia que D-23.2 orquesta desde `route_board`/`fill_zones`, pero
`save_board` en sí no es `CAMBIO_INCIDENTAL` ni `PRERREQUISITO` de DT3;
extraerla no altera el contrato D-23.2 (que vive en la lógica de
orquestación de las otras tres tools, no en `save_board` misma).
**S7:** NO cumple ninguna cuantitativa (35 < 80; 1 closure < 3; 35 < 100).
S7.d no demostrable — responsabilidad única (persistir + snapshot fresco +
audit), ya cohesiva.
**S8:** no determinante (S7 ya falla).

**R activado:** R11 (beneficio marginal, S7 no se satisface).

## Veredicto individual: **NO_APTO** (S7 sin dispensa E1 defendible)
