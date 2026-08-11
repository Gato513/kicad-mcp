# 03 — Fase 3 extendida: criterios de rechazo aplicados a candidatos 13-21

Aplicado a los 9 candidatos con ficha completa (`13-similars.md` …
`21-set-footprint-ref.md`), con S1-S8 (AND) y R1-R14 (OR) de **v6**
§§11.4-11.5 —instrumento normativo primario, verificado por hash
(`00-preflight-ext.md §3`), cuyos apartados declaran su contenido "idéntico
a v5"—, S8 usando la comparación M2 homogénea de **v6** §10, sobre
`raw/m2-ext.json` (derivado en
Fase B, validado por control de sanidad byte-idéntico contra el
`raw/m2.json` anclado para los 12 originales — `00-preflight-ext.md` y
`raw/m2-check-1-12-sanity.json`).

## 1. Clasificación individual

```
APTO:              0
APTO_CONDICIONAL:  0
NO_APTO:           9
NO_CLASIFICABLE:   0
```

Ningún candidato quedó `NO_CLASIFICABLE`: R-BL.3.a no se activó (baseline
sin drift, checkpoint exacto, `00-preflight-ext.md §9`), y ninguna
`REFERENCIA_AMBIGUA` afectó a un símbolo de los 9.

```
NO_APTO por S1/S8 (dependencia de helpers compartidos de fan-in alto,
fuera del cluster propuesto):  3 candidatos
  (fichas 14, 18, 21 — los únicos 3 que satisfacen S7 cuantitativamente)
NO_APTO por S7 sin dispensa E1 defendible:  6 candidatos
  (fichas 13, 15, 16, 17, 19, 20)
```

Ningún candidato de esta extensión falla ambos motivos simultáneamente (a
diferencia de la ficha 6 del paquete original) — la partición es limpia.

## 2. Patrón estructural — confirma, no asume, el riesgo residual #2 de `05-veredicto.md`

`05-veredicto.md §16` (paquete original) señaló como **riesgo no
verificado, señal para H11**: "el patrón S1-vs-S8 encontrado en los 5
candidatos closure-bearing... incluye, muy probablemente, a varios de los 9
supervivientes sin ficha... get_tracks, reload_board_from_disk, save_board,
set_footprint_ref, delete_track, delete_via, add_via". Esta extensión
**rederivó** S1/S7/S8 de forma independiente para cada uno de los 9 (no
copió la conclusión por analogía, conforme exige contrato §5) y el
resultado confirma la sospecha solo parcialmente y con precisión mayor:

- **Confirmado exactamente para 3 de los 7 nombrados**: `add_via` (14),
  `get_tracks` (18), `set_footprint_ref` (21) — los únicos que además
  satisfacen S7 cuantitativamente, y por tanto los únicos donde S1/S8 es el
  motivo de rechazo *determinante*.
- **Refutado para los otros 4 nombrados**: `delete_track` (15), `delete_via`
  (16), `reload_board_from_disk` (19), `save_board` (20) sí dependen de
  helpers compartidos (`_delete_copper` o `_resolve_board`) y **también**
  fallarían S1/S8 si se llegara a evaluar esa ruta — pero **no llegan a ese
  punto**: los cuatro fallan primero por S7 (tamaño insuficiente,
  ninguno alcanza 80 LOC ni siquiera con el LOC erróneo de
  `enumeracion.md §6`). El riesgo residual #2 sobre-estimó cuántos
  candidatos serían bloqueados específicamente por S1/S8 — el motivo
  primario para 4 de los 7 es, en cambio, el mismo patrón "helper-only
  pequeño" (S7) que ya dominaba 7 de los 12 originales.
- **Nuevo dato no anticipado por el riesgo residual #2**: `_similars` (13,
  no nombrado explícitamente en esa lista, pero de la misma familia que
  `_audit_error`/`_resolve_board`) y `get_component_detail` (17) también
  fallan por S7, no por S1/S8 — ninguno de los dos depende de un trío
  amplio de helpers compartidos.

## 3. Verificación de `APTO_CONDICIONAL` (§11.7)

No aplicable en ninguno de los 9. En 14/18/21: el gate que falla es S1 o S8,
ambos no dispensables. En 13/15/16/17/19/20: el gate que falla es S7,
dispensable en principio por E1 — pero ninguna de las 6 fichas ofrece
evidencia mínima defendible de eliminación de responsabilidad mezclada
(S7.d): todas son ya funciones de responsabilidad única (delegar, resolver
+ delegar, o ejecutar una operación atómica de sincronización) cuya
extracción solo reubica código limpio, sin eliminar mezcla, siguiendo el
mismo criterio ya aplicado en `03-refutacion.md §2` del paquete original.

## 4. Tabla resumen S1-S8/R1-R14 por candidato

| # | Candidato | LOC (real) | S1 | S7 | S8 | R activado | Veredicto |
|---|---|---:|---|---|---|---|---|
| 13 | `_similars` | 3 | cumple | NO cumple | cumple (igualdad) | R11 | **NO_APTO** |
| 14 | `{_via_params, add_via}` | 110 | NO cumple / degrada S8 | cumple (a) | NO cumple | R12/R11 | **NO_APTO** |
| 15 | `delete_track` | 18 | cumple | NO cumple | n/a | R11 | **NO_APTO** |
| 16 | `delete_via` | 18 | cumple | NO cumple | n/a | R11 | **NO_APTO** |
| 17 | `get_component_detail` | 21 | cumple | NO cumple | n/a | R11 | **NO_APTO** |
| 18 | `get_tracks` | 86 | NO cumple / degrada S8 | cumple (a) | NO cumple | R12/R11 | **NO_APTO** |
| 19 | `reload_board_from_disk` | 57 | cumple | NO cumple | n/a | R11 | **NO_APTO** |
| 20 | `save_board` | 35 | cumple | NO cumple | n/a | R11 | **NO_APTO** |
| 21 | `set_footprint_ref` | 114 | NO cumple / degrada S8 | cumple (a,c) | NO cumple | R12/R11 | **NO_APTO** |

**0 de 9 candidatos materializados en esta extensión alcanzan `APTO` o
`APTO_CONDICIONAL`.**

**Nota sobre la columna S1 (C-EXT-03):** para los candidatos rechazados por
S7, "cumple" en la columna S1 describe el **estado actual** del símbolo, no
una evaluación completa de la extracción proyectada —que es lo que el gate
evalúa. En esos casos S1 no es determinante: el veredicto lo fija S7. La
columna conserva la convención de la tabla de los 12 originales para
mantener comparabilidad entre ambas.

## 5. Consecuencia para H4/CR7 (contrato v6 §3/§4) — no reabierta, extendida

`03-refutacion.md §-final` del paquete original refutó H4/CR7 con 5
contraejemplos. Esta extensión aporta 3 contraejemplos adicionales del
mismo patrón (14, 18, 21: reducción sustancial de LOC de `register()` sin
mejora de M2 bajo diseño de extracción mínimo) — no reabre la refutación
original, la corrobora con evidencia independiente sobre candidatos
distintos.
