# Ficha 14 — `{_via_params, add_via}`

```
K = {_via_params, add_via}   (LOC=110: _via_params L3146-3147 [2 LOC] +
                               add_via L1332-1439 [108 LOC], @mcp.tool closure)
```

LOC re-derivado (110) **coincide** con `enumeracion.md §6`/contrato §2 — el
único de los 9 sin divergencia (ver `04-hallazgos-fuera-de-scope-ext.md`).

## M1 — Volumen

LOC actual = 110. 1 closure `@mcp.tool` eliminada de `register()` si se
extrae (`add_via`; `_via_params` es helper top-level, no closure). Reducción
de `pcb.py` = 110 LOC (`pcb_py_loc_total=3161` → 3051 proyectado).

## M2 — Acoplamiento

```
M2_actual_vector = (d1=1, d2=3, d3=8, d4=0, d5=0)
d1_simbolos: ['bridge']
d2_aristas: [['add_via','_audit_error','CALL'],
             ['add_via','_resolve_board','CALL'],
             ['add_via','_similars','CALL']]
d3_modulos: ['..audit.logger', '..bridge.ipc', '..bridge.state_builder',
             '..errors', '..gates.g1', '..logging_config', '..snapshots',
             '._mutating']
d4_simbolos: []
d5_detalle: entrante_interna=[], entrante_src=[], entrante_tests=[]
```

Bajo diseño de extracción mínimo (mover `{_via_params, add_via}` a módulo
nuevo, reexport delgado en `register()`), los tres símbolos de `d2`
(`_audit_error`, ficha 2 del original NO_APTO; `_resolve_board`, ficha 11
del original NO_APTO; `_similars`, ficha 13 de esta extensión, NO_APTO)
permanecen en `pcb.py` — ninguno se propone mover junto con este cluster.
Dos rutas de diseño, ambas evaluadas:

**Ruta A — reexport natural (importar los 3 símbolos desde `pcb.py`):**
crea 3 aristas módulo-nuevo → `pcb.py`. **S1 falla** literalmente
("NO puede haber arista desde el módulo nuevo a pcb.py"). Activa **R12**
(ciclo de import).

**Ruta B — inyección explícita por parámetro (S1.c):** `_audit_error`,
`_resolve_board`, `_similars` pasan a ser parámetros de la función movida,
vinculados en `register()` al momento de construir el wrapper. Preserva S1
(sin arista de vuelta), pero:
```
M2_proyectado(Ruta B) = (d1=4, d2=0, d3=8, d4=0, d5=0)
```
`d1` empeora 1→4 (los 3 símbolos que antes eran referencias de módulo pasan
a ser capturas de scope inyectadas). `M2_nuevo NO_EMPEORA` es **FALSO**
(∃i: d1_proy > d1_actual). **S8 falla.** Activa **R11** (beneficio
marginal — S7 se satisface solo por LOC/closures, sin que M2 domine).

Ninguna de las dos rutas satisface simultáneamente S1 y S8 — idéntico al
patrón formal de las fichas 1, 3, 8, 9, 10 del paquete original (`03-refutacion.md
§1`, "no existe ninguna combinación que satisfaga simultáneamente S1 y S8").

## M3 — Superficie observable

`@mcp.tool(name="add_via")`, decorador `@mutating_tool("add_via")` (flags
por defecto: `live_guard=True, disk_check=True, base_snap_check=True`).
Códigos de error [F3] usados: `NET_NOT_FOUND`, `INVALID_PARAMS`. Bajo
cualquiera de las dos rutas de extracción, `register()` reexporta `add_via`
sin cambiar firma ni comportamiento observable — M3 no se ve afectada por sí
sola (S2 cumple independientemente del resultado de S1/S8).

## M4 — Cobertura

`COBERTURA_DEMOSTRADA`: 5 tests offline con assert en `tests/test_pcb.py`
(`test_add_via_success_writes_audit_and_short_confirm`,
`test_add_via_uses_default_sizes`,
`test_add_via_reports_net_not_found_with_similars`,
`test_add_via_rejects_out_of_bounds`,
`test_add_via_rejects_drill_ge_diameter`) + 4 tests `integration_gui`
(round-trip, mismatch de net ajeno, preservación de net solicitado).

## Gates S1–S8

**S1:** NO cumple (Ruta A) / cumple con degradación S8 (Ruta B) — ver M2.
**S2:** cumple (firma `@mcp.tool` preservada).
**S3:** simple (mover 2 símbolos + wrapper delgado).
**S4:** cumple, `COBERTURA_DEMOSTRADA`.
**S5:** cumple (no toca zonas/route_board/stitching).
**S6:** `REFERENCIA_EXISTENTE` (mutación de cobre puntual, sin relación con
DT3/P1-2 más allá de compartir el bridge IPC).
**S7:** cumple por S7.a (110 ≥ `UMBRAL_S7_LOC=80`) y S7.c (proyección de
reducción de `pcb.py`, 110 < 100 en sentido estricto no aplica — ver nota:
S7.c mide reducción de `pcb.py`, no de `register()`; 110 ≥ 100 si se cuenta
la extracción completa del cluster, incluido `_via_params`). Al menos S7.a
se satisface con margen claro.
**S8:** NO cumple en ninguna de las dos rutas (ver M2).

**R activado:** R12 (Ruta A, ciclo de import) o R11 (Ruta B, beneficio
marginal sin dominancia M2). Ambos criterios no dispensables por E1/E2/E3
(§11.7: S1 y S8 nunca dispensables).

## Veredicto individual: **NO_APTO** (S1 o S8, según ruta de diseño, ninguna dispensable)

Rederivado independientemente, sin copiar la conclusión de las fichas 1/3/8/9/10
del paquete original por analogía — el conflicto estructural (dependencia de
`_audit_error`/`_resolve_board`/`_similars` compartidos) es el mismo,
verificado directamente sobre el código actual de `add_via`.
