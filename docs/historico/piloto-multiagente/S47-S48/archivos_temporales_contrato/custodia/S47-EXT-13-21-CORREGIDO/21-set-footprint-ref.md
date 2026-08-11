# Ficha 21 — `set_footprint_ref`

```
K = {set_footprint_ref}   (LOC=114, L1039-1152, @mcp.tool closure)
```

**Nota de divergencia LOC (H-S47EXT-01):** `enumeracion.md §6`/contrato §2
anotan LOC=116. Re-derivación de esta sesión: LOC=114 — la divergencia más
pequeña de los 9 (2 líneas). Ver `04-hallazgos-fuera-de-scope-ext.md`. No
altera el veredicto: S7.a se satisface con ambos valores (114 y 116, ambos
≥ 80).

## M1 — Volumen

LOC actual = 114. 1 closure eliminada de `register()`. Reducción de
`pcb.py` = 114 LOC.

## M2 — Acoplamiento

```
M2_actual_vector = (d1=1, d2=3, d3=8, d4=0, d5=0)
d1_simbolos: ['bridge']
d2_aristas: [['set_footprint_ref','_audit_error','CALL'],
             ['set_footprint_ref','_resolve_board','CALL'],
             ['set_footprint_ref','_similars','CALL']]
d3_modulos: ['..audit.logger', '..bridge.ipc', '..bridge.state_builder',
             '..errors', '..gates.g1', '..logging_config', '..snapshots',
             '._mutating']
d4_simbolos: []
d5_detalle: entrante_interna=[], entrante_src=[], entrante_tests=[]
```

`M2_actual_vector` **idéntico** al de `add_via` (ficha 14): mismo trío de
dependencias (`_audit_error`, `_resolve_board`, `_similars`), mismo `d3`.
Análisis estructural igual:

**Ruta A — reexport natural:** 3 aristas módulo-nuevo → `pcb.py`. **S1
falla.** Activa **R12**.

**Ruta B — inyección explícita por parámetro:**
```
M2_proyectado(Ruta B) = (d1=4, d2=0, d3=8, d4=0, d5=0)
```
`d1` empeora 1→4. **S8 falla.** Activa **R11**.

Ninguna ruta satisface S1 y S8 simultáneamente.

## M3 — Superficie observable

`@mcp.tool(name="set_footprint_ref")`, `@mutating_tool("set_footprint_ref")`.
Códigos de error [F3]: `COMPONENT_NOT_FOUND`, `INVALID_PARAMS`,
`DUPLICATE_REFS` (con `data={"candidates": [...]}`, contrato de
desambiguación por `kiid` documentado en sesión 31b, F-V1-02). Bajo
cualquiera de las dos rutas de extracción, firma y códigos se preservan —
S2 cumple independientemente del resultado de S1/S8.

## M4 — Cobertura

`COBERTURA_DEMOSTRADA`: 5 tests offline con assert, todos en
`tests/test_pcb_session31b_duplicate_refs.py` (not-found, unique-ref-rejected,
ambiguous-without-kiid-lists-candidates, stale-kiid-rejected, happy-path).
Sin tests `integration_gui` propios en `coverage.json` — cobertura
concentrada en la capa offline, sin corroboración GUI directa registrada
para esta tool específica (limitación declarada, no bloqueante: S4 exige
`COBERTURA_DEMOSTRADA` en los caminos relevantes, que sí está presente
offline).

## Gates S1–S8

**S1:** NO cumple (Ruta A) / cumple con degradación S8 (Ruta B).
**S2:** cumple.
**S3:** simple (mover 1 función, wrapper delgado).
**S4:** cumple, `COBERTURA_DEMOSTRADA` (offline).
**S5:** cumple (renombra ref, no toca zonas/route_board).
**S6:** `REFERENCIA_EXISTENTE` (ADR-0013/ADR-0010 citados en el propio
docstring: resolución de refs duplicados, explícitamente NO un
`delete_footprint` disfrazado; sin relación con DT3/P1-2).
**S7:** cumple por S7.a (114 ≥ 80) y S7.c (114 ≥ 100).
**S8:** NO cumple en ninguna ruta — idéntico patrón a `add_via` (ficha 14).

**R activado:** R12 (Ruta A) o R11 (Ruta B). No dispensables.

## Veredicto individual: **NO_APTO** (S1 o S8, ninguna dispensable)

Tercer y último de los tres candidatos de esta extensión que satisface S7
cuantitativamente (junto a 14 y 18) — y, como ellos, cae por el mismo
conflicto estructural S1-vs-S8 rederivado independientemente sobre sus
propias 3 dependencias reales (`_audit_error`, `_resolve_board`,
`_similars`), no por analogía.
