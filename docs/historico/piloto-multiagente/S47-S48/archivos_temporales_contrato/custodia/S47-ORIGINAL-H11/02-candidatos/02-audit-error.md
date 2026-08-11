# Ficha 2 — `_audit_error`

```
K = {_audit_error}
```

Semilla: S3 (helper con ≥2 consumidores en V — en realidad 11, ver d5).

## M1 — Volumen

```
LOC actual = 8 (L3154-3161). Helper top-level, fuera de register() ->
LOC de register() liberado = 0.
LOC de pcb.py liberado = 8.
Closures eliminadas = 0.
```

## M2 — Acoplamiento

```
d1 = 0 (función pura top-level, sin captura de scope de register()).
d2 = 0 (no llama a ningún otro miembro de V — es un builder de dict, hoja del grafo).
d3 = 2 (..audit.logger, ..errors).
d4 = 1 (_audit_error mismo: consumidores fuera de K = todos los que lo llaman).
d5 = 11: entrante_interna = {_delete_copper, _refill_enforce_and_save,
      add_keepout_zone, add_track, add_via, add_zone, delete_zone,
      draw_board_outline, fill_zones, move_footprint, set_footprint_ref}.
      entrante_src = entrante_tests = ∅.

M2_actual_vector = (0, 0, 2, 1, 11)
```

## S1 — cumple

d2=0: no hay ninguna arista saliente de K hacia V\K. Sus únicas dependencias
son módulos externos estables (`..audit.logger`, `..errors`) — S1(b). No hay
riesgo de ciclo de import.

## S2 — cumple (con 1 reexport)

Con d4=1 y 11 consumidores restantes en pcb.py, se necesita **1 reexport**
(`from .pcb_audit import _audit_error as _audit_error`) — muy por debajo de
`UMBRAL_R7_REEXPORTS=3`. R7 no se activa.

## S3 — reversibilidad simple

Función pura top-level, patrón idéntico al de DT1 Slice 1 (mover +
reexportar). `S3.c = simple`.

## S4 — cobertura

Sin test focal directo (no aparece en `frontera_entrante_tests`). Se ejerce
transitivamente vía los 11 closures que lo llaman — `COBERTURA_INFERIDA`
para la lógica propia de `_audit_error` (nunca se asertan sus campos
directamente en un test dedicado, según inspección de
`raw/coverage.json`/`01-inventario-actual.md §8`; los tests aserten sobre el
mensaje de error final del tool, no sobre la estructura intermedia que
`_audit_error` construye).

## S5 — cumple. S6 — `REFERENCIA_EXISTENTE` (sin relación con P1-2/DT3; es
formateo de auditoría, no geometría ni kiid).

## S7 — **NO cumple ninguna cuantitativa**

```
S7.a  0 < 80    NO
S7.b  0 < 3     NO
S7.c  8 < 100   NO
S7.d  sin demostración de "eliminación de responsabilidad mezclada":
      _audit_error ya tiene responsabilidad única y estrecha (formatear un
      dict de error de auditoría); extraerlo no separa ninguna mezcla
      existente, solo relocaliza 8 líneas ya cohesivas.
```

Sin S7.d demostrable, no hay base para E1 (la tabla normativa exige
"argumento estructural nominal: qué responsabilidad se agrupa, qué fan-in
cruzado se elimina cualitativamente" — aquí no se elimina fan-in, el fan-in
de 11 consumidores **persiste igual** tras la extracción, solo cambia de
"llamada intra-archivo" a "import cross-módulo").

## S8 — M2 no empeora (bajo diseño mínimo): cumple trivialmente por
igualdad (d1..d5 sin cambio bajo reexport), pero **no domina** (ningún
dimensión mejora) — H4 se refuta con este candidato también (alta pureza
S7.a-style no aplica aquí, pero sirve como contraejemplo adicional de "mover
código reduce acoplamiento por sí solo").

## R activados: **R11** (beneficio marginal — S7 no se satisface por
ninguna vía cuantitativa, y S7.d no es demostrable; extraer 8 líneas sin
reducir el fan-in de 11 consumidores no es una reducción de deuda
estructural, es una relocalización).

## Veredicto individual: **NO_APTO** (por S7, sin dispensa E1 defendible)
