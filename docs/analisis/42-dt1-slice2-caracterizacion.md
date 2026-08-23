# Sesión 42 — recaracterización de DT1 Slice 2 (`tools/pcb.py`)

**Estado de este documento:** caracterización pura, docs-only. Ningún
archivo bajo `src/` ni `tests/` fue modificado para producirlo. Toda cifra
citada abajo se derivó de un script reproducible sobre el SHA base (§7) —
no se copió de otra documentación.

**Precedente directo:** `docs/analisis/40-dt1-caracterizacion.md` (Slice 1,
cerrado sesión 41) y el paquete de evidencia de Slice 2
(`docs/historico/piloto-multiagente/S47-S48/`). Este documento no repite esa
evidencia — la asume leída y la referencia por ruta.

**Nota de proceso (AGENTS.md §15):** los procedimientos S40–S48 (contratos
formales, custodia con hash, revisión independiente Codex por unidad) **no
son precedente operativo obligatorio** para trabajo nuevo. Sus conclusiones
técnicas sí siguen vigentes y se citan como tales. Este documento se produce
con identidad Git normal, sin esa maquinaria — es una unidad integrable de
todos modos (AGENTS.md §4): quien la escribe no puede aprobarla de forma
independiente.

**Limitación heredada, no resuelta aquí:** el texto literal de los gates
S1–S8/R1–R14 (contrato v5) no está versionado en el repo — solo sus
umbrales cuantitativos y enunciados cortos, reconstruibles desde las 21
fichas de S47 (`custodia/S47-ORIGINAL-H11/02-candidatos/`). Este documento
aplica el *espíritu* de esos gates con esa base, no su texto exacto.

**Revisión independiente (Codex, `codex review --base master`) y corrección
aplicada:** la v1 de este documento afirmaba en §4 haber "inventariado los
30 helpers" cuando en realidad verificaba una lista ya curada, sin barrer
sistemáticamente las funciones pre-`register()`. Codex señaló el hallazgo
correcto —`_match_orphan_pad` (`pcb.py:522`) tiene el mismo perfil de
dependencias que el cluster propuesto y no aparecía en esa lista— y uno
incorrecto, refutado con evidencia (`grep -n "async def" pcb.py` no
devuelve nada: no hay funciones `async` en el archivo, ni top-level ni
anidadas; la afirmación de "dos helpers async omitidos" es falsa). §4 se
reescribió con un barrido exhaustivo real (script en §10, reproducible);
el resultado añade un candidato no institucional no visto antes
(`_derive_post_state`, fuera de alcance por dominio y tamaño, ver §8) y dos
del universo S47 quedan reclasificados con más precisión, pero el cluster
final propuesto —13 funciones, 252 LOC— **no cambia**.

## 1. Identificación

```text
Repositorio:   Gato513/kicad-mcp
Rama:          sesion/42-dt1-slice2-caracterizacion
Commit base:   11f49188b2c6b4153ebed0841abe6ebaab436f99
Fecha:         2026-08-23
Ejecutor:      Claude Code
```

## 2. Punto de partida — por qué el método anterior se agotó

S47 evaluó los 21 símbolos supervivientes de `register()` como candidatos
**aislados** bajo el diseño *"mover un símbolo + wrapper delgado"** (el
mismo patrón operativo de importación/re-export del Slice 1, pero aplicado
a un solo símbolo por vez en vez de a un cluster).

Resultado: **21/21 `NO_APTO`**, con dos patrones de fallo dominantes
(`custodia/S47-ORIGINAL-H11/03-refutacion.md`,
`custodia/S47-EXT-13-21-CORREGIDO/03-refutacion-ext.md`):

- **S7 (tamaño insuficiente):** 13/21 no alcanzan 80 LOC.
- **S1/S8 (fan-in a helpers compartidos):** 6/21 dependen del trío
  `_audit_error`/`_resolve_board`/`_similars`. Extraer el símbolo sin el
  trío crea una arista `módulo_nuevo → pcb.py` (prohibida por S1, activa
  R12 = ciclos de import); extraerlo inyectando el trío por parámetro
  evita el ciclo pero **empeora** el vector de acoplamiento M2, violando
  S8. La ficha 1 (`01-delete-copper.md:79-86`) lo registra sin salida
  dentro del alcance de un candidato aislado.

Veredicto formal: `NO_GO_POR_PRESUPUESTO` sobre
`ALCANCE_SUPERVIVIENTES_21`. Por regla 13 del contrato v6, ese veredicto
**no** es refutación universal (existían 8 clusters excluidos
institucionalmente, nunca evaluados) y **no** autoriza implementación
(fe de erratas, regla 2). El `BACKLOG.md` §DT1 cierra pidiendo, para
retomar: *"una unidad de extracción distinta (cluster cohesivo de varias
funciones relacionadas, no un símbolo aislado) o un diseño de extracción
distinto"*, como decisión humana.

Este documento cambia la unidad de análisis de "símbolo aislado" a
"cluster cohesivo", que es exactamente el eje que S47 dejó sin explorar
para el universo de 21 (sí lo aplicó, por diseño de su algoritmo C2, a los
8 clusters institucionales — pero esos arrastran zonas/`route_board`,
fuera de alcance aquí).

## 3. Métricas base re-derivadas

| Métrica | Valor | Fuente |
|---|---|---|
| `pcb.py` LOC total | 3206 | `wc -l` |
| `pcb_encoders.py` LOC (Slice 1) | 294 | `wc -l` |
| `register()` (`pcb.py:921-3138`) | 2218 LOC (69 % del archivo) | AST |
| Helpers top-level pre-`register()` | 824 LOC / 30 funciones (`pcb.py:95-918`) | AST |
| Helpers top-level post-`register()` | 66 LOC / 6 funciones (`pcb.py:3141-3206`) | AST |
| Tools registradas | 19 (12 con `@mutating_tool`) | AST + grep |

`pcb.py` no cambió de tamaño desde el commit base de S47 salvo por el
propio Slice 1 (que ya lo redujo). El universo de símbolos aislados sigue
agotado; no hay candidatos nuevos "por LOC" que S47 no haya visto.

## 4. Derivación del cluster de geometría pura

Barrido exhaustivo (no una lista curada — ver corrección de §Revisión
independiente arriba) de las **32 funciones top-level pre-`register()`**
(`pcb.py:95-918`) por sus dependencias externas (AST: nombres cargados que
no son locales, parámetros de funciones/lambdas anidadas, ni builtins).
Clasificación completa, script y salida íntegra en §10:

| Categoría | Funciones | Cuenta |
|---|---|---|
| Trío (obstáculo, no candidato) | `_similars`, `_resolve_board` (`_audit_error` vive post-`register()`, fuera de este barrido) | 2 |
| No dependency-closed (tocan `bridge`/errores/mcp/audit) | — | 7 |
| Dependency-closed, ya excluidas por F-DT.1 (institucional) | `_find_duplicate_refs`, `_segments_intersect`, `_polygon_is_simple`, `_point_in_polygon`, `_match_orphan_pad`, `_opposite_layer_blocked`, `_orphan_pad_dict`, `_stitched_via_dict`, `_evaluate_stitch_candidates` | 9 |
| Dependency-closed, NO institucional, fuera del cluster propuesto | `_derive_post_state` (30 LOC) | 1 |
| **Dependency-closed → cluster de geometría propuesto** | ver tabla abajo | **13** |

Total: 2 + 7 + 9 + 1 + 13 = 32. ✓ Cuadra con el total de funciones
pre-`register()`.

Las 9 excluidas por F-DT.1 caen en dos de los clusters institucionales que
enumeró el algoritmo C2 de S47 (`enumeracion.md:82-99`):

| Cluster institucional | Miembros dependency-closed relevantes aquí | Vía |
|---|---|---|
| #1 — stitching/`route_board` (456 LOC total, contiene `route_board`) | `_find_duplicate_refs`, `_point_in_polygon`, `_match_orphan_pad`, `_opposite_layer_blocked`, `_orphan_pad_dict`, `_stitched_via_dict`, `_evaluate_stitch_candidates` | consumidas exclusivamente por `_evaluate_stitch_candidates`/`route_board` |
| #2 — zonas (`{_polygon_is_simple, _segments_intersect, _validate_zone_geometry}`) | `_polygon_is_simple`, `_segments_intersect` | `_validate_zone_geometry` → `add_zone`/`add_keepout_zone` |

`_derive_post_state` (única función dependency-closed que NO cae en ningún
cluster institucional ni en el de geometría) no se propone: es dominio
distinto (diff de estado de footprint tras `move_footprint`, no geometría
de cobre/pad), su único consumidor (`_register_post_snapshot`) no es
dependency-closed, y aislada (30 LOC) reproduce el mismo fallo S7 por
tamaño que ya refutó a 13 de los 21 símbolos de S47. Queda anotada para
una eventual caracterización futura de la familia G1 (footprints), no para
este cluster.

Excluyendo el trío, las 9 institucionales y `_derive_post_state`, el
cluster de geometría propuesto es **exactamente 13 funciones / 252 LOC**,
dependency-closed de forma exhaustivamente verificada (ninguna de las 13
depende de las 9 excluidas, de `_derive_post_state`, ni del trío — ver
§10).

**Cluster propuesto — `tools/pcb_geometry.py`:**

```text
_dist_point_segment (253, 12 LOC)       _closest_board_edge (363, 17 LOC)
_copper_distance_mm (267, 18 LOC)       _segment_intersects_bbox (382, 34 LOC)
_match_copper (287, 22 LOC)             _copper_in_bbox (418, 12 LOC)
_bbox_distance_to_point (311, 11 LOC)   _copper_on_layer (432, 6 LOC)
_copper_distance_to_bbox (324, 21 LOC)  _rounded_rect_sdf (760, 15 LOC)
_closest_point_copper_bbox (347, 14 LOC) _dist_segment_to_pad (777, 40 LOC)
                                          _find_track_pad_collision (819, 30 LOC)
```

Total: **252 LOC, 13 funciones, 0 clases, 0 constantes de módulo propias.**
Ocupa dos bloques físicos no contiguos: `pcb.py:253-437` (10 funciones) y
`pcb.py:760-848` (3 funciones) — la misma no-contigüidad, y el mismo
tratamiento (commit atómico, reversible por `git revert`), que tuvo el
Slice 1 con sus tres bloques.

Patrón de extracción propuesto: **idéntico al Slice 1** — mover + import
con alias redundante + re-export explícito en `pcb.py`. Ningún consumidor
externo conocido importa hoy ninguna de estas 13 funciones por nombre
(§6), así que el re-export es defensivo, no load-bearing — pero se
mantiene por simetría con el Slice 1 y para no cerrar la puerta a un
consumidor futuro no detectado.

## 5. Aptitud contra los gates (reconstruidos, ver limitación en cabecera)

| Gate | Veredicto | Base |
|---|---|---|
| S1 — dependency-closed y acíclico | **CUMPLE** | AST (§7): 0 aristas hacia el resto de `pcb.py` |
| S2 — superficie MCP-neutral | **CUMPLE** | no mueve ninguna de las 19 tools; ninguna de las 13 lleva `@mcp.tool` ni `@mutating_tool` |
| S3 — reversibilidad preliminar | **CUMPLE** | mover + re-export, un único `git revert`, patrón ya probado |
| S5 — fuera de zonas prohibidas | **CUMPLE** | no toca `docs/specs/`, `tests/golden/`, `gates/`, `pyproject.toml` |
| S6 — relación con P1-2/DT3 | **CUMPLE** | no toca `kiid` (P1-2, vive en `pcb_encoders.py`); vive en `tools/`, no en `bridge/` (no es DT3) |
| S7 — frontera reducida | **CUMPLE** | 252 LOC ≥ 80 (umbral individual histórico); reduce `pcb.py` en 252 LOC (≥100, umbral `UMBRAL_S7_PCB_LOC`) |
| S8 — M2 no empeora | **CUMPLE** | ninguna captura `bridge`; cero inyecciones nuevas de parámetros; `d1`/`d2` proyectados = 0 |
| **S4 — testable con la suite offline actual** | **RIESGO, ver §6** | ninguna de las 13 funciones está nombrada en `tests/` hoy |

Diferencia clave con el Slice 1: los encoders tenían verificación
**byte-exacta** (goldens F1-protegidos). Este cluster no tiene ningún test
que lo nombre — se ejercita solo indirectamente.

## 6. El riesgo S4 — declarado, con mitigación propuesta

Verificado por grep sobre `tests/` (§7): ninguna de las 13 funciones del
cluster propuesto aparece nombrada en ningún archivo de test. Se ejercitan
indirectamente vía `get_footprint_neighbors`, `add_track`, `get_tracks` y
`delete_tracks_bulk` — las tools que las consumen. (Esto es específico del
cluster de geometría: no se extiende a las 9 funciones institucionalmente
excluidas de §4 — `_find_duplicate_refs`, por ejemplo, sí tiene un import
directo en `tests/test_pcb_session31b_duplicate_refs.py:60` — porque esa
cobertura es irrelevante para la propuesta de esta sesión.)

Esto no es un defecto introducido por la extracción: es el estado actual
de `pcb.py`. Pero mover código sin test directo a un módulo nuevo, sin
mitigación, deja ese módulo con cobertura estructuralmente más débil que
`pcb_encoders.py`.

**Mitigación propuesta para la sesión de ejecución (no de esta):** incluir
en el slice tests unitarios directos de las 13 funciones. Son funciones
puras (sin I/O, sin `bridge`, sin excepciones de dominio) — triviales de
testear por caso. El resultado neto convierte cobertura indirecta en
directa, lo que **mejora** la posición de verificación del archivo en vez
de degradarla. Esto encaja con la excepción E2 del contrato v6 (admite
delta *nominal* de tests; no admite eliminarlos) aunque, de nuevo, esa
maquinaria de excepciones no es precedente operativo obligatorio aquí
(AGENTS.md §15) — se cita como referencia de diseño, no como requisito
formal.

## 7. Acoplamiento externo (verificado esta sesión)

- **`register()`** — 1 consumidor en `src/` (`tools/__init__.py:35,45`) +
  13 en `tests/` (importan `register` para instanciar el servidor de
  prueba). Ninguno de estos consumidores toca las 13 funciones del cluster
  propuesto.
- **Monkeypatches sobre `pcb` como módulo** — 4 tests
  (`test_route_board.py`, `test_pcb_session31b_duplicate_refs.py`,
  `test_pcb_session32d_orphan_pads_stitching_canary.py`,
  `test_pcb_session32b_refill_silencioso_canary.py`) parchean
  `run_drc`/`run_autoroute` vía `monkeypatch.setattr(pcb_module, ...)`.
  Ninguno de los dos símbolos pertenece al cluster propuesto ni a
  `route_board` sale de `pcb.py` en esta propuesta — el veto I-4 de
  sesión 40 sigue vigente y no se toca aquí.
- **Re-exports vivos del Slice 1** (`pcb.py:64-70`) — no se tocan.
- **Import de símbolos privados desde tests**: `_find_duplicate_refs`
  (1 test), `_tracks_filter_desc`/`_zones_filter_desc`/3 encoders
  (2 tests) — ninguno pertenece al cluster propuesto.

## 8. Alternativas caracterizadas y descartadas

### Trío de helpers compartidos (`_audit_error`/`_resolve_board`/`_similars`)

Fan-in verificado esta sesión: `_audit_error` 12 llamadores / 29 call
sites; `_resolve_board` 17 llamadores / 17 call sites (el helper más
transversal del archivo); `_similars` 9 llamadores / 9 call sites. Es el
obstáculo estructural real detrás del fallo S1/S8 de 6 de los 21
candidatos, y la hipótesis Q5 de S47
(`custodia/S48-A/.../04-interpretacion.md`) predice que ninguna extracción
aislada avanzará mientras el trío permanezca en `pcb.py`.

Precedente exacto: ADR-0014 (sesión 39, DT2) movió 4 helpers
(`_project_root`, `_guard_live_stale`, `_check_base_snap`,
`_resolve_root_schematic_or_pcb`) a `tools/_mutating.py` por la misma
asimetría de ciclo (*"el decorador los necesita internamente y `pcb.py` no
puede importarlos de vuelta sin ciclo"*).

**Por qué no se propone acá:** el trío suma ~20 LOC — falla S7
cuantitativamente incluso agrupado. Y las tres funciones no comparten
responsabilidad temática entre sí (auditoría de error, resolución de
board, sugerencia de nombres similares); agruparlas en un módulo por el
solo hecho de compartir fan-in alto es el patrón de bucket genérico que
ADR-0014 rechazó explícitamente al descartar `tools/_common.py`
(*"un nombre genérico habría sido la puerta de entrada exacta para la
deriva que motivó DT2"*). Un movimiento futuro de este trío correspondería
decidirlo por responsabilidad — p. ej. `_resolve_board` junto a los
resolutores que ya viven en `_mutating.py` — no como cajón común. Fuera de
alcance de esta caracterización; queda anotado para una sesión posterior
si la Autoridad lo prioriza.

### `_derive_post_state` aislado (30 LOC)

Único hallazgo nuevo del barrido exhaustivo de §4/§10 (surgió al corregir
el hallazgo de Codex): es dependency-closed, pero no cae en ningún cluster
institucional ni en el dominio de geometría — pertenece a la familia G1
(footprints), alimenta `_register_post_snapshot` (que sí toca `bridge`, no
es dependency-closed). Aislado, reproduce el mismo fallo S7 por tamaño
insuficiente que ya refutó a 13 de los 21 símbolos de S47 (30 < 80 LOC).
Fuera de alcance de esta caracterización — es geometría de estado de
footprint, no de cobre; agruparlo con el cluster propuesto rompería
cohesión temática (S6). Candidato a anotar para una eventual
caracterización futura de la familia G1, no para ejecutar ahora.

### Los 8 clusters institucionalmente excluidos (~1060 LOC)

`enumeracion.md:82-99` — familia de zonas completa (`add_zone`,
`add_keepout_zone`, `get_zones`, `fill_zones`, `delete_zone`,
`delete_tracks_bulk`, más los helpers de validación de geometría de zona)
y la familia de stitching/`route_board`. Es la mayor masa de código sin
evaluar y **no está refutada** — está excluida por decisión institucional
(F-DT.1), no por gate. Tocarla arrastra directamente el contrato D-23.2 /
ADR-0012 (`route_board`, `fill_zones`, `add_zone(fill=True)`). Levantar
esa exclusión es decisión humana explícita, fuera de este documento.

### `route_board` aislado (426 LOC en una sola función)

Vetado desde sesión 40 (veto I-4), confirmado vigente esta sesión: 4 tests
parchean `run_drc`/`run_autoroute` como atributos del módulo donde vive
`route_board`. Moverlo rompería esos fakes **en silencio** — los tests
seguirían pasando pero ejercitando el bridge real en vez del mock, un
falso verde peor que un fallo visible.

## 9. Veredicto propuesto

**El cluster de geometría pura (`_dist_point_segment` … `_find_track_pad_collision`,
252 LOC / 13 funciones, `tools/pcb_geometry.py` sugerido) es la unidad de
extracción que el BACKLOG pide**: un cluster cohesivo, no un símbolo
aislado, que cumple S1/S2/S3/S5/S6/S7/S8 bajo los umbrales reconstruidos, y
que declara honestamente su único punto débil (S4, cobertura indirecta)
con una mitigación concreta y barata.

**Este documento NO autoriza su ejecución.** Sigue pendiente, como pide
AGENTS.md §3, la decisión humana explícita de: (a) aprobar esta unidad de
extracción en particular, (b) priorizar en su lugar el trío de helpers o
alguno de los 8 clusters institucionales, o (c) no retomar DT1 por ahora.

## 10. Reproducibilidad

**Nota de versión:** la v1 de este script (revisada por Codex, ver cabecera)
sólo reportaba una lista de nombres ya elegida a mano — no derivaba nada.
Esta v2 barre las 32 funciones pre-`register()` sin curación previa y
clasifica cada una; es la que sustenta §4.

Script usado (read-only, sin dependencias fuera de la stdlib):

```python
import ast
import sys

TRIO = {"_audit_error", "_resolve_board", "_similars"}
BRIDGE_ADJACENT = {
    "bridge", "IpcBridge", "BoardHandle", "KicadMcpError", "ErrorCode",
    "audit_record", "mcp", "FastMCP", "estimate_tokens", "log_tool_call",
    "tool_call_timer", "get_default_store", "ensure_session_backup",
    "build_state_from_snapshot", "build_state_from_board",
    "check_no_external_disk_edit", "collect_project_mtimes", "run_drc",
    "run_autoroute", "classify_net_routing", "diff_violations",
    "load_project_rules", "mutating_tool",
}

# Miembros de los clusters institucionalmente excluidos (F-DT.1), citados
# de enumeracion.md:82-99 para CLASIFICAR — este script no re-deriva esa
# exclusión, que es institucional, no de gate.
INSTITUTIONAL_CLUSTER_1_STITCHING = {
    "_OPPOSITE_LAYER", "_STITCH_RADIUS_MM", "_evaluate_stitch_candidates",
    "_find_duplicate_refs", "_match_orphan_pad", "_open_board_or_none",
    "_opposite_layer_blocked", "_orphan_pad_dict", "_point_in_polygon",
    "_refill_enforce_and_save", "_stitched_via_dict", "route_board",
}
INSTITUTIONAL_CLUSTER_2_ZONES = {
    "_polygon_is_simple", "_segments_intersect", "_validate_zone_geometry",
}
INSTITUTIONAL = INSTITUTIONAL_CLUSTER_1_STITCHING | INSTITUTIONAL_CLUSTER_2_ZONES

GEOMETRY_CLUSTER = {
    "_dist_point_segment", "_copper_distance_mm", "_match_copper",
    "_bbox_distance_to_point", "_copper_distance_to_bbox",
    "_closest_point_copper_bbox", "_closest_board_edge",
    "_segment_intersects_bbox", "_copper_in_bbox", "_copper_on_layer",
    "_rounded_rect_sdf", "_dist_segment_to_pad", "_find_track_pad_collision",
}

BUILTIN_NAMES = set(dir(__builtins__)) | {
    "float", "int", "str", "bool", "list", "dict", "tuple", "min", "max",
    "abs", "len", "range", "sorted", "any", "all", "sum", "enumerate",
    "zip", "set", "isinstance", "round",
}


def collect_locals(fn: ast.AST) -> set[str]:
    local = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
    if fn.args.vararg:
        local.add(fn.args.vararg.arg)
    if fn.args.kwarg:
        local.add(fn.args.kwarg.arg)
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        local.add(n.id)
        elif isinstance(node, (ast.For, ast.comprehension)):
            for n in ast.walk(node.target):
                if isinstance(n, ast.Name):
                    local.add(n.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not fn:
            local.add(node.name)
            local |= {a.arg for a in node.args.args} | {a.arg for a in node.args.kwonlyargs}
        elif isinstance(node, ast.Lambda):
            local |= {a.arg for a in node.args.args} | {a.arg for a in node.args.kwonlyargs}
    return local


def external_names(fn: ast.AST, local: set[str]) -> set[str]:
    used = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in local and node.id not in BUILTIN_NAMES:
                used.add(node.id)
    return used


def analyze(path: str) -> None:
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)

    top_all = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    register_line = next(n.lineno for n in top_all if n.name == "register")
    pre_register = sorted([n for n in top_all if n.lineno < register_line], key=lambda n: n.lineno)

    print(f"Total top-level def/async def en pcb.py: {len(top_all)}")
    print(f"Pre-register(): {len(pre_register)}\n")

    geometry, institutional, trio, other_extra = [], [], [], []
    not_dependency_closed = 0

    for fn in pre_register:
        local = collect_locals(fn)
        ext = external_names(fn, local)
        touches_bridge = bool(ext & BRIDGE_ADJACENT)

        if fn.name in TRIO:
            trio.append(fn.name)
        elif touches_bridge:
            not_dependency_closed += 1
        elif fn.name in INSTITUTIONAL:
            institutional.append(fn.name)
        elif fn.name in GEOMETRY_CLUSTER:
            loc = fn.end_lineno - fn.lineno + 1
            geometry.append((fn.name, loc))
        else:
            loc = fn.end_lineno - fn.lineno + 1
            other_extra.append(f"{fn.name} ({loc} LOC)")

    print(f"Dependency-closed: {len(geometry) + len(institutional) + len(other_extra)}")
    print(f"  -> cluster de geometria propuesto: {len(geometry)} funciones")
    print(f"  -> ya excluidas por F-DT.1 (institucional): {len(institutional)} funciones: {institutional}")
    print(f"  -> OTRAS dependency-closed, NO institucionales, fuera del cluster: {other_extra}")
    print(f"No dependency-closed (tocan bridge/errors/mcp/audit): {not_dependency_closed}")
    print(f"Trio (obstaculo, no candidato): {trio}")
    print(f"\nLOC total del cluster propuesto: {sum(loc for _, loc in geometry)}")
    print(f"Total contabilizado: {len(geometry)+len(institutional)+len(other_extra)+len(trio)+not_dependency_closed} "
          f"(debe igualar Pre-register()={len(pre_register)})")


if __name__ == "__main__":
    analyze(sys.argv[1] if len(sys.argv) > 1 else "src/kicad_mcp/tools/pcb.py")
```

Ejecución (`python3 s42_derivation.py src/kicad_mcp/tools/pcb.py`), salida
íntegra sobre el commit base:

```text
Total top-level def/async def en pcb.py: 39
Pre-register(): 32

Dependency-closed: 23
  -> cluster de geometria propuesto: 13 funciones
  -> ya excluidas por F-DT.1 (institucional): 9 funciones: ['_find_duplicate_refs', '_segments_intersect', '_polygon_is_simple', '_point_in_polygon', '_match_orphan_pad', '_opposite_layer_blocked', '_orphan_pad_dict', '_stitched_via_dict', '_evaluate_stitch_candidates']
  -> OTRAS dependency-closed, NO institucionales, fuera del cluster: ['_derive_post_state (30 LOC)']
No dependency-closed (tocan bridge/errors/mcp/audit): 7
Trio (obstaculo, no candidato): ['_similars', '_resolve_board']

LOC total del cluster propuesto: 252
Total contabilizado: 32 (debe igualar Pre-register()=32)
```

Contabilización cerrada: 13 + 9 + 1 + 2 + 7 = 32, sin resto. Ningún
candidato adicional queda sin clasificar.

Refutación textual de la segunda observación de Codex (helpers `async`
omitidos): `grep -n "async def" src/kicad_mcp/tools/pcb.py` no devuelve
ninguna línea — cero funciones `async` en el archivo, ni top-level ni
anidadas. `pre_register` en v1 y en v2 cuentan lo mismo (32) porque no hay
ninguna a la que `ast.FunctionDef` (sin `AsyncFunctionDef`) le faltara
capturar; v2 igual incorpora `ast.AsyncFunctionDef` por robustez futura.

Cobertura de tests del cluster propuesto (grep de las 13 funciones contra
`tests/`): cero coincidencias en las 13.

## 11. Afirmaciones no verificadas en esta caracterización

- No se corrió `mypy`/`ruff` sobre un `pcb_geometry.py` real — no existe
  todavía, esto es una propuesta docs-only. La ejecución debe repetir la
  verificación de equivalencia AST y goldens que hizo el Slice 1.
- El texto literal de S1–S8/R1–R14 (contrato v5) sigue sin recuperarse; los
  umbrales citados en §5 son los reconstruidos en S47, no una relectura
  del original.
- No se investigó si `_closest_board_edge`, `_dist_segment_to_pad` u otras
  de las 13 tienen duplicados conceptuales en otras partes del código base
  (`bridge/`, DT3) — fuera del alcance de esta caracterización.
- La clasificación de las 9 funciones excluidas por F-DT.1 (§4/§10) usa la
  membresía de cluster institucional tal como la enumeró S47
  (`enumeracion.md:82-99`), citada, no re-derivada por este documento — si
  esa enumeración tuviera un error, se propagaría acá.
- Esta v2 del documento corrigió, tras revisión independiente de Codex
  (`codex review --base master` sobre el commit `f778ab9`), el hallazgo real
  de la v1 (derivación no exhaustiva) y refutó con evidencia el hallazgo
  incorrecto de la misma revisión (helpers `async` inexistentes en el
  archivo). No hubo una segunda ronda de revisión sobre esta v2 — queda
  pendiente si la Autoridad la considera necesaria antes de decidir sobre
  el veredicto de §9.
