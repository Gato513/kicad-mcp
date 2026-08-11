# Ficha 1 — `_delete_copper` (núcleo de borrado de cobre)

```
K = {_DELETE_TOLERANCE_MM, _copper_candidate_dict, _delete_copper, _match_copper}
```

Semilla: S1 (0 — no es @mcp.tool), realmente originado por S2 (`_delete_copper`
es closure directa de `register()`, sin `@mcp.tool`). Expandido por C2/C3 a 4
símbolos. Prior histórico: `docs/analisis/40-dt1-caracterizacion.md §5`,
cluster "Núcleo de borrado de cobre" (~38 LOC de helpers, coincide).

## M1 — Volumen

```
LOC actual (suma miembros)     = 188  (1 constante + 2 helpers + 1 closure)
LOC de register() liberado     = 149  (_delete_copper es la única closure del
                                        cluster — mover reduce register() en 149 líneas)
LOC de pcb.py liberado (total) = 188
Closures eliminadas de register() = 1
```

## M2 — Acoplamiento

**d1 (capturas de scope actual):** `{bridge}` — `_delete_copper` referencia
`bridge` en su cuerpo (verificado en `01-inventario-actual.md §4`). **d1=1**.

**d2 (cortes hacia pcb.py, actual):** 4 aristas, TODAS hacia miembros de V
que **no** forman parte de K y **no** se proponen mover:

```
_delete_copper -> _audit_error     (helper compartido, 11 consumidores en V — ficha 2)
_delete_copper -> _resolve_board   (helper compartido, 17 consumidores en V — ficha 11)
_delete_copper -> _similars        (helper compartido, no materializado — 9 consumidores según S40 §5)
_match_copper  -> _copper_distance_mm  (helper compartido — ficha 5)
```

**d3 (módulos externos):** 8 — `..audit.logger`, `..bridge.ipc`,
`..bridge.state_builder`, `..errors`, `..gates.g1`, `..logging_config`,
`..snapshots`, `._mutating`.

**d4 (helpers de K con consumidor externo):** 0 — ningún miembro de K es
llamado desde fuera de K (`_copper_candidate_dict` y `_match_copper` solo se
usan dentro de `_delete_copper`/entre sí).

**d5 (fronteras entrantes):** 2 — `entrante_interna = {delete_track,
delete_via}` (ambos permanecen en `register()`, delegan en `_delete_copper`
vía el patrón de wrapper delgado ya usado hoy — línea 1710/1734). `entrante_src
= entrante_tests = ∅`.

```
M2_actual_vector = (d1=1, d2=4, d3=8, d4=0, d5=2)
```

## S1 — Dependency-closed y acíclico: **NO CUMPLE**

Los 4 destinos de d2 (`_audit_error`, `_resolve_board`, `_similars`,
`_copper_distance_mm`) son helpers de **fan-in alto compartido por casi
todos los closures de `register()`** (11, 17, ≥2 y ≥2 consumidores
respectivamente, según `01-inventario-actual.md` y
`docs/analisis/40-dt1-caracterizacion.md §5`) y **ninguno se propone mover**
junto con K (cada uno es, en la enumeración de esta sesión, un candidato
propio — fichas 2, 11, 5, y un no-materializado). Bajo el diseño canónico de
extracción (mover K a un módulo nuevo, dejar wrapper delgado en `register()`):

```
Opción A — el módulo nuevo importa _audit_error/_resolve_board/_similars/
  _copper_distance_mm DESDE pcb.py:
    -> arista módulo_nuevo -> pcb.py, PROHIBIDA explícitamente por S1
       ("NO puede haber arista desde el módulo nuevo a pcb.py").
    -> S1 NO CUMPLE. Activa R12 (ciclos de import).

Opción B — se inyectan los 4 símbolos como parámetros explícitos
  (S1(c), "inyecciones explícitas por parámetro"):
    -> S1 SÍ se satisface formalmente.
    -> pero d1_proyectado pasa de 1 (solo `bridge`) a 4 (bridge +
       audit_error_fn + resolve_board_fn + similars_fn), EMPEORANDO
       esa dimensión de M2 respecto de M2_actual.
    -> S8 ("ninguna dimensión del vector M2 aumenta") NO CUMPLE.
       S8 es NO dispensable (§11.7).
```

**No existe una tercera opción** dentro del alcance de un candidato aislado
(bundlear `_audit_error`/`_resolve_board`/`_similars` en la MISMA extracción
cambiaría el cluster propuesto por uno materialmente distinto — no
enumerado por el algoritmo determinista de §7.1, y afectaría a los otros 18
closures de `register()` que también los consumen; eso es una decisión de
diseño de S48, no algo que S47 pueda aprobar retroactivamente sobre este
candidato).

## S2 — Superficie-neutral: cumple (nominalmente)

El wrapper delgado en `register()` preserva firma, nombre y descripción
`@mcp.tool` de `delete_track`/`delete_via` (no son parte de K, no cambian).
Ningún código de error [F3] se renombra. Reexports: 0 nuevos necesarios
(d4=0).

## S3 — Reversibilidad preliminar: complejidad **moderada**

`_delete_copper` es una closure (no una función pura top-level como el
cluster "Encoders ad-hoc" de DT1 Slice 1) — requiere separar cuerpo +
inyectar `bridge` como parámetro explícito, más el problema de S1 sin
resolver arriba. `S3.c = moderada`, sin la mitigación de S1/S8 no hay
justificación de "alta" evitable.

## S4 — Tests suficientes: `COBERTURA_INFERIDA/DEMOSTRADA` mixta

`_delete_copper` no tiene test focal propio (ni import directo, ver
`01-inventario-actual.md §8`) — su lógica se ejerce exclusivamente a través
de `delete_track`/`delete_via`. Evidencia offline con `assert` sobre el
resultado (`raw/coverage.json`):

```
delete_track: 10 invocaciones offline con assert (ej. tests/test_pcb_session11.py
  ::test_delete_track_happy_removes_by_kiid:414, ::test_delete_track_ambiguity_
  returns_candidates:457, ::test_delete_track_net_not_found:477)
delete_via:     1 invocación offline con assert (tests/test_pcb_session11.py
  ::test_delete_via_happy:434)
```

`delete_via` con una sola invocación offline asertada es un camino delgado;
sin acceso a las aserciones específicas no se puede afirmar
`COBERTURA_DEMOSTRADA` de TODOS los caminos internos de `_delete_copper`
(p. ej. ramas de tolerancia/ambigüedad) — clasificado
**`COBERTURA_INFERIDA`** para `_match_copper`/tolerancia, **REFERENCIADA/
DEMOSTRADA parcial** para el camino feliz.

## S5 — Fuera de zonas prohibidas: cumple (F-DT.1 ya lo dejó pasar)

## S6 — Relación con P1-2/DT3: `REFERENCIA_EXISTENTE` (sin relación directa)

`_match_copper`/`_copper_candidate_dict` hacen matching de proximidad
(distancia a punto/bbox) pero **no** son la geometría segregada por DT3
(DT3 es explícitamente "geometría de dominio **dentro de `bridge/`**",
`docs/BACKLOG.md:519`) — este cluster vive en `tools/pcb.py`, no en
`bridge/`. Sin relación con P1-2 (kiid). `REFERENCIA_EXISTENTE`, admisible.

## S7 — Frontera estructural reducida: **cumple** por S7.a y S7.c

```
S7.a  149 >= UMBRAL_S7_LOC (80)        -> SÍ
S7.b  1 closure < UMBRAL_S7_CLOSURES (3) -> NO
S7.c  188 >= UMBRAL_S7_PCB_LOC (100)   -> SÍ
```

## S8 — Acoplamiento no aumenta: depende de la opción de S1

Bajo Opción A (import-back), S8 no llega a evaluarse con sentido (S1 ya
falló, R12 activo). Bajo Opción B (inyección), S8 **falla** (d1 empeora
1→4).

## R activados

```
R1   no (bridge sí es inyectable/ya lo es en el patrón register_x existente)
R12  SÍ bajo Opción A — introduce ciclos de import (S1 refutada)
R11  aplicable bajo Opción B — S7 se satisface, M2 no domina (de hecho empeora)
```

## Veredicto individual: **NO_APTO**

Por R12 (Opción A, diseño natural) o por S8 (Opción B, diseño alternativo).
Ninguna combinación del diseño de extracción mínimo satisface
simultáneamente S1 y S8. Un diseño que bundlee `_audit_error`/`_resolve_board`/
`_similars` en la misma extracción podría resolver esto, pero constituye un
candidato distinto no enumerado por el algoritmo — queda como sugerencia
para S48/H11, no como parte de este veredicto.

`excepciones_propuestas`: ninguna (S1/S8 no son dispensables por E1/E2/E3).
