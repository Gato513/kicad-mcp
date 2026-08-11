# Ficha 13 — `_similars`

```
K = {_similars}   (LOC=3, L95-97 de src/kicad_mcp/tools/pcb.py)
```

**Nota de divergencia LOC (H-S47EXT-01):** `enumeracion.md §6` y contrato §2
anotan LOC=13 para este cluster. La re-derivación de esta sesión
(`inventory-ext.json`, byte-idéntico a `raw/inventory.json` anclado) da
LOC=3, confirmado contra el código fuente real:

```python
def _similars(target: str, candidates: list[str], *, limit: int = 3) -> list[str]:
    """Sugerencias por edit-distance para hints de COMPONENT/NET_NOT_FOUND."""
    return difflib.get_close_matches(target, candidates, n=limit, cutoff=0.5)
```

Se usa el valor re-derivado (3) para M1/S7 de esta ficha; ver
`04-hallazgos-fuera-de-scope-ext.md` para el detalle completo del hallazgo.
La divergencia no altera el veredicto (con LOC=3 o LOC=13, ambos muy por
debajo de `UMBRAL_S7_LOC=80`).

## M1 — Volumen

LOC actual = 3. Closure eliminada de `register()` si se extrae: 0 (es helper
top-level, no closure — no vive dentro de `register()`). Reducción de
`pcb.py` = 3 LOC. `pcb_py_loc_total=3161`.

## M2 — Acoplamiento

```
M2_actual_vector = (d1=0, d2=0, d3=0, d4=1, d5=9)
d1_simbolos: []
d2_aristas: []
d3_modulos: []
d4_simbolos: ['_similars']  (helper con consumidor externo — trivial, es el
                              propio símbolo, único miembro de K)
d5_detalle:
  entrante_interna: ['_delete_copper', 'add_track', 'add_via', 'add_zone',
                      'delete_tracks_bulk', 'get_tracks', 'get_zones',
                      'move_footprint', 'set_footprint_ref']  (9 consumidores)
  entrante_src: []
  entrante_tests: []
```

Función pura (`d2=0`, `d3=0`): usa únicamente `difflib` (stdlib, no cuenta
como módulo externo — `RESUELTA_A_STDLIB`), sin dependencias hacia `pcb.py`
ni hacia `bridge/`. Bajo diseño de extracción mínimo (mover a módulo nuevo +
1 reexport desde `pcb.py`), `M2_proyectado = (0,0,0,1,9)`: **igual** al
actual — 1 reexport preserva los 9 accesos sin cambio de conteo. `S8`
cumple por igualdad, no por dominancia.

## M3 — Superficie observable

Sin `@mcp.tool` (helper interno). Ningún código de error [F3] asociado
directamente. Sin reexports actuales; 1 reexport necesario post-extracción
(`UMBRAL_R7_REEXPORTS=3`, dentro de margen).

## M4 — Cobertura

Sin test focal directo (ningún test importa/parchea `pcb._similars`
explícitamente). `COBERTURA_INFERIDA` por transitividad extrema: 9 caminos
independientes lo ejercen (todos los consumidores listados en `d5_detalle`
tienen tests con `assert` sobre el hint de `NET_NOT_FOUND`/
`COMPONENT_NOT_FOUND` que depende de su salida — p. ej.
`test_add_via_reports_net_not_found_with_similars`,
`test_set_footprint_ref_ambiguous_without_kiid_lists_candidates`). Ningún
test asigna una aserción al comportamiento de `_similars` en sí (p. ej. sobre
el umbral `cutoff=0.5` o el límite `limit=3`).

## Gates S1–S8

**S1:** cumple (d2=0, sin dependencias hacia `pcb.py` ni módulos inestables).
**S2:** cumple, 1 reexport (< `UMBRAL_R7_REEXPORTS=3`).
**S3:** simple (3 líneas, función pura sin estado).
**S4:** sin `COBERTURA_DEMOSTRADA` directa; `COBERTURA_INFERIDA` fuerte, sin
delta de test nominal propuesto en esta ficha (fuera de scope de S47:
propuesta de test queda para S48 si se autoriza).
**S5:** cumple. **S6:** `REFERENCIA_EXISTENTE` (utilidad de UX de error, sin
relación con DT3/P1-2).
**S7:** NO cumple ninguna cuantitativa (LOC=3 << 80; 1 closure eliminada < 3;
reducción `pcb.py`=3 << 100). S7.d no demostrable: función de una expresión,
responsabilidad ya mínima y única (idéntico patrón a `_audit_error` ficha 2 y
`_resolve_board` ficha 11 del paquete original).
**S8:** M2_proyectado = M2_actual (cumple por igualdad).

**R activado:** R11 (beneficio marginal — S7 no se satisface y no hay base
para E1).

## Veredicto individual: **NO_APTO** (S7 sin dispensa E1 defendible)

Tercer ejemplar de la familia "helper puro de fan-in alto, tamaño mínimo"
junto a `_audit_error` (ficha 2, LOC=8) y `_resolve_board` (ficha 11, LOC=9)
del paquete original — mismo patrón estructural, mismo motivo de rechazo, sin
copiar la conclusión: se rederivó S1/S7/S8 de forma independiente sobre el
código actual y el resultado coincide.
