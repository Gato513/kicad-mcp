# 05 — Reconciliación final (12 + 9 → 21)

Artefacto central de `S47-H11-AMPLIACION-13-21` (contrato §8). Orden literal
exigido por contrato §8(1)-(7).

## 1. Identidad verificada

`00-preflight-ext.md §6-7` documenta la re-derivación completa de Fase 2
(`inventory-ext.json`/`clusters-ext.json`, byte-idénticos a los anclados,
`cmp -s` exit 0) y la comparación de identidad
(`01-comparacion-identidad.py`, exit 0, `IDENTIDAD_CONFORME`):
`N_universo_total=29`, `N_excluidos_institucional=8`,
`N_excluidos_presup=0`, `N_supervivientes=21`, con el array `survivors`
byte-semánticamente idéntico al anclado, posiciones 1-12 coincidentes con
`enumeracion.md §5` y posiciones 13-21 coincidentes con contrato §2, mismo
orden. Sin `DRIFT_UNIVERSO_S47`.

## 2. Tabla de los 12 veredictos originales (literal, sin reinterpretación)

Fuente: `05-veredicto.md` del paquete S47 original, hash
`ec538b9c99a45099aabe4c4cfdda17fd2ef9603971d6694931b8fbad9ac6df3a`
(verificado, `00-preflight-ext.md §5`). Importados mecánicamente, no
re-derivados:

| # | Candidato | LOC | S1 | S7 | Veredicto |
|---|---|---:|---|---|---|
| 1 | `_delete_copper` (núcleo borrado cobre) | 188 | NO cumple | cumple (a,c) | **NO_APTO** |
| 2 | `_audit_error` | 8 | cumple | NO cumple | **NO_APTO** |
| 3 | `get_footprint_neighbors` | 207 | NO cumple | cumple (a,c) | **NO_APTO** |
| 4 | `_bbox_distance_to_point` | 11 | cumple | NO cumple | **NO_APTO** |
| 5 | `_copper_distance_mm`+`_dist_point_segment` | 30 | cumple | NO cumple | **NO_APTO** |
| 6 | `_copper_in_bbox` | 12 | NO cumple | NO cumple | **NO_APTO** |
| 7 | `_copper_on_layer` | 6 | cumple | NO cumple | **NO_APTO** |
| 8 | `move_footprint` | 216 | NO cumple | cumple (a,c) | **NO_APTO** |
| 9 | `add_track` | 332 | NO cumple | cumple (a,c) | **NO_APTO** |
| 10 | `draw_board_outline` | 87 | NO cumple | cumple (a, margen mínimo) | **NO_APTO** |
| 11 | `_resolve_board` | 9 | cumple | NO cumple | **NO_APTO** |
| 12 | `_segment_intersects_bbox` | 34 | cumple | NO cumple | **NO_APTO** |

**12/12 `NO_APTO`. 0 `APTO`/`APTO_CONDICIONAL`.** Sin reinterpretación —
literal de `02-candidatos/README.md` del paquete original.

## 3. Tabla de los 9 veredictos nuevos

Misma estructura de columnas que `02-candidatos/README.md` del paquete
original. Fuente: fichas `13-similars.md` … `21-set-footprint-ref.md` de
esta extensión, derivadas independientemente (§5 del contrato: sin copiar
conclusiones por analogía). LOC = valor re-derivado (`inventory-ext.json`),
no el de `enumeracion.md §6` — ver `04-hallazgos-fuera-de-scope-ext.md`
H-S47EXT-01.

| # | Candidato | LOC | S1 | S7 | Veredicto |
|---|---|---:|---|---|---|
| 13 | `_similars` | 3 | cumple | NO cumple | **NO_APTO** |
| 14 | `{_via_params, add_via}` | 110 | NO cumple | cumple (a) | **NO_APTO** |
| 15 | `delete_track` | 18 | cumple | NO cumple | **NO_APTO** |
| 16 | `delete_via` | 18 | cumple | NO cumple | **NO_APTO** |
| 17 | `get_component_detail` | 21 | cumple | NO cumple | **NO_APTO** |
| 18 | `get_tracks` | 86 | NO cumple | cumple (a) | **NO_APTO** |
| 19 | `reload_board_from_disk` | 57 | cumple | NO cumple | **NO_APTO** |
| 20 | `save_board` | 35 | cumple | NO cumple | **NO_APTO** |
| 21 | `set_footprint_ref` | 114 | NO cumple | cumple (a,c) | **NO_APTO** |

**9/9 `NO_APTO`. 0 `APTO`/`APTO_CONDICIONAL`.**

**Nota sobre la columna S1 (C-EXT-03):** para los candidatos rechazados por
S7, "cumple" en la columna S1 describe el **estado actual** del símbolo, no
una evaluación completa de la extracción proyectada —que es lo que el gate
evalúa. En esos casos S1 no es determinante: el veredicto lo fija S7. La
columna conserva la convención de la tabla de los 12 originales para
mantener comparabilidad entre ambas.

## 4. Contadores del universo combinado

```
N_universo_total           = 29   (sin cambio)
N_excluidos_institucional  = 8    (sin cambio)
N_excluidos_presup         = 0    (sin cambio)
N_supervivientes           = 21   (sin cambio)
N_fichas_completas         = 21   (12 + 9 — ahora igual a N_supervivientes)
N_evaluados                = 21
```

## 5. Aplicación formal de v6 §11.3 (orden estricto, universo combinado)

```
1. Puerta 0 falló?                              NO -> continuar
2. R-BL.2 activada?                              NO -> continuar
3. R-BL.3.b activa insuficiencia global?         NO -> continuar
4. Alguna V0.2-V0.7 no cumplida?                 NO -> continuar
5. N_supervivientes(21) > UMBRAL_P_STOP_FICHAS_ACUMULADO(21)?
   (única sustitución permitida, contrato §8.6)  NO (21 > 21 es FALSO)
                                                  -> continuar
6. Algún candidato con ficha sin clasificar
   entre APTO/APTO_CONDICIONAL/NO_APTO/
   NO_CLASIFICABLE?                              NO (los 21 clasifican
                                                  limpiamente NO_APTO)
                                                  -> continuar
7. N_evaluados == 0?                             NO (21) -> continuar
8. >=1 APTO Y N_excluidos_presup==0 Y
   N_excluidos_institucional==0?                 NO (0 APTO)
                                                  -> continuar
9. >=1 APTO Y (N_excluidos_presup>0 O
   N_excluidos_institucional>0)?                 NO (0 APTO)
                                                  -> continuar
10. NO existe APTO y existe >=1
    APTO_CONDICIONAL con excepción §11.7?        NO (0 APTO_CONDICIONAL)
                                                  -> continuar
11. NO existe APTO ni APTO_CONDICIONAL
    y existe >=1 NO_CLASIFICABLE?                NO (0 NO_CLASIFICABLE)
                                                  -> continuar
12. TODOS NO_APTO Y N_excluidos_presup==0 Y
    N_excluidos_institucional==0?                NO (N_excluidos_
                                                  institucional=8>0)
                                                  -> continuar
13. TODOS NO_APTO Y (N_excluidos_presup>0 O
    N_excluidos_institucional>0)?                SÍ (21/21 NO_APTO,
                                                  N_excluidos_institucional=8)
                                                  -> NO_GO_POR_PRESUPUESTO
```

**La regla 13 se activa y es la primera regla aplicable de la secuencia
ordenada.** Reglas 6-13 se aplicaron literalmente, sin sustituir ningún otro
contador — la única sustitución fue el operando de la regla 5 (`21` en vez
de `12`), exactamente como fija contrato §8.6, y esa regla **dejó de
activarse** (a diferencia del veredicto original, donde la regla 5 SÍ se
activaba con el umbral de 12 y detenía la evaluación antes de llegar a la
constatación de unanimidad `NO_APTO`).

## 6. Veredicto único sobre el universo de 21 supervivientes

```
╔═════════════════════════════════════════╗
║  VEREDICTO:  NO_GO_POR_PRESUPUESTO        ║
║  ALCANCE:    ALCANCE_SUPERVIVIENTES_21    ║
╚═════════════════════════════════════════╝
```

Con `N_excluidos_institucional=8`, la consecuencia formal correcta de "todos
los 21 evaluados son `NO_APTO`" es `NO_GO_POR_PRESUPUESTO`, **no** `NO_GO`
estricto (contrato §8.6, tercer punto; regla 13 vs. regla 12 de v6 §11.3).
El etiquetado `ALCANCE_SUPERVIVIENTES_21` es obligatorio: este veredicto
**no** afirma haber refutado los 8 clusters excluidos institucionalmente —
esos nunca se evaluaron y siguen fuera del universo evaluado, exactamente
como excluye la fe de erratas Regla 5 y como exige contrato §8.6, cuarto
punto.

**Esta conclusión no estaba predeterminada** por ningún documento previo:
se deriva mecánicamente de que los 21 veredictos individuales (12 originales
importados por hash + 9 nuevos rederivados de forma independiente en esta
sesión) resultaron unánimemente `NO_APTO`, sin que ningún criterio de
extracción propuesto — bajo el diseño mínimo evaluado (mover + wrapper
delgado) — supere simultáneamente los 8 gates AND de §11.4 para ninguno de
los 21 candidatos del universo evaluado.

## 7. Trazabilidad explícita — los 21 candidatos, una vez cada uno

| # | Candidato | Fuente |
|---|---|---|
| 1 | `_delete_copper` | paquete original, hash `05-veredicto.md` §2 |
| 2 | `_audit_error` | paquete original |
| 3 | `get_footprint_neighbors` | paquete original |
| 4 | `_bbox_distance_to_point` | paquete original |
| 5 | `_copper_distance_mm`+`_dist_point_segment` | paquete original |
| 6 | `_copper_in_bbox` | paquete original |
| 7 | `_copper_on_layer` | paquete original |
| 8 | `move_footprint` | paquete original |
| 9 | `add_track` | paquete original |
| 10 | `draw_board_outline` | paquete original |
| 11 | `_resolve_board` | paquete original |
| 12 | `_segment_intersects_bbox` | paquete original |
| 13 | `_similars` | esta extensión, `13-similars.md` |
| 14 | `{_via_params, add_via}` | esta extensión, `14-via-params-add-via.md` |
| 15 | `delete_track` | esta extensión, `15-delete-track.md` |
| 16 | `delete_via` | esta extensión, `16-delete-via.md` |
| 17 | `get_component_detail` | esta extensión, `17-get-component-detail.md` |
| 18 | `get_tracks` | esta extensión, `18-get-tracks.md` |
| 19 | `reload_board_from_disk` | esta extensión, `19-reload-board-from-disk.md` |
| 20 | `save_board` | esta extensión, `20-save-board.md` |
| 21 | `set_footprint_ref` | esta extensión, `21-set-footprint-ref.md` |

Los 21 aparecen exactamente una vez. Ninguno se cuenta dos veces, ninguno
falta.

## 8. Lo que este veredicto NO autoriza (recordatorio, contrato §1/§10)

`NO_GO_POR_PRESUPUESTO` sobre `ALCANCE_SUPERVIVIENTES_21` **no** autoriza
S48, DT1 Slice 2, ni ningún paso de implementación (Regla 2 de la fe de
erratas, contrato §1 último párrafo). No cierra DT1. No declara refutados
los 8 clusters excluidos institucionalmente. La vía de continuación, si el
humano la ejerce, requeriría una nueva autorización explícita (nuevo H,
fuera del alcance de esta sesión) — esta reconciliación no la presupone ni
la recomienda.
