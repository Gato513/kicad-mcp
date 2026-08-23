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

Inventariando los 30 helpers pre-`register()` por sus dependencias
externas (AST: nombres cargados que no son locales, parámetros de
funciones/lambdas anidadas, ni builtins), aparece un subconjunto de **16
funciones cuyas únicas dependencias externas son `math` y tipos de
anotación (`CopperItem`, `BBoxMm`, `PadGeom`)** — ninguna captura `bridge`,
ninguna llama al trío, ninguna usa `KicadMcpError`/`ErrorCode`/
`audit_record`. Es el único subconjunto del archivo con esa propiedad, y es
exactamente la propiedad que hizo fallar S1/S8 a 6 de los 21 candidatos
aislados.

De esas 16, tres fueron absorbidas por el clustering institucional C2 de
S47 dentro de clusters excluidos por F-DT.1 (`enumeracion.md:82-99`):

| Función | Cluster institucional que la absorbe | Vía |
|---|---|---|
| `_polygon_is_simple` (480) | #2 `{_polygon_is_simple, _segments_intersect, _validate_zone_geometry}` | `_validate_zone_geometry` → `add_zone`/`add_keepout_zone` |
| `_segments_intersect` (440) | #2 (idem) | usada por `_polygon_is_simple` |
| `_point_in_polygon` (503) | #1 (familia stitching, 456 LOC, contiene `route_board`) | usada por `_evaluate_stitch_candidates` |

Excluyéndolas queda un sub-cluster de **13 funciones / 252 LOC**, libre de
solapamiento institucional bajo cualquier lectura de F-DT.1, y que sigue
siendo dependency-closed (ninguna de las 13 depende de las 3 excluidas ni
viceversa — verificado, ver §7).

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

Verificado por grep sobre `tests/` (§7): ninguna de las 13 funciones (ni
las 3 excluidas) aparece nombrada en ningún archivo de test. Se ejercitan
indirectamente vía `get_footprint_neighbors`, `add_track`, `get_tracks` y
`delete_tracks_bulk` — las tools que las consumen.

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

Script usado (read-only, sin dependencias fuera de la stdlib):

```python
import ast
import sys

CANDIDATE = [
    "_dist_point_segment", "_copper_distance_mm", "_match_copper",
    "_bbox_distance_to_point", "_copper_distance_to_bbox",
    "_closest_point_copper_bbox", "_closest_board_edge",
    "_segment_intersects_bbox", "_copper_in_bbox", "_copper_on_layer",
    "_rounded_rect_sdf", "_dist_segment_to_pad", "_find_track_pad_collision",
]
EXCLUDED_INSTITUTIONAL = ["_polygon_is_simple", "_segments_intersect", "_point_in_polygon"]
TRIO = {"_audit_error", "_resolve_board", "_similars"}
WATCH = TRIO | {"bridge", "KicadMcpError", "ErrorCode", "audit_record", "IpcBridge"}

BUILTIN_NAMES = set(dir(__builtins__)) | {
    "float", "int", "str", "bool", "list", "dict", "tuple", "min", "max",
    "abs", "len", "range", "sorted", "any", "all", "sum", "enumerate",
    "zip", "set", "isinstance",
}


def collect_locals(fn: ast.FunctionDef) -> set[str]:
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
        elif isinstance(node, ast.FunctionDef) and node is not fn:
            local.add(node.name)
            local |= {a.arg for a in node.args.args} | {a.arg for a in node.args.kwonlyargs}
        elif isinstance(node, ast.Lambda):
            local |= {a.arg for a in node.args.args} | {a.arg for a in node.args.kwonlyargs}
    return local


def external_names(fn: ast.FunctionDef, local: set[str]) -> set[str]:
    used = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in local and node.id not in BUILTIN_NAMES:
                used.add(node.id)
    return used


def analyze(path: str) -> None:
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    top = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    def report(names: list[str], label: str) -> int:
        print(f"\n=== {label} ===")
        total = 0
        for name in names:
            fn = top.get(name)
            if fn is None:
                print(f"  {name}: NO ENCONTRADA")
                continue
            loc = fn.end_lineno - fn.lineno + 1
            total += loc
            local = collect_locals(fn)
            ext = external_names(fn, local)
            flagged = ext & WATCH
            marker = f"  <-- ARISTA A {sorted(flagged)}" if flagged else ""
            print(f"  {name:32} L{fn.lineno:<5} {loc:>3} LOC  externos={sorted(ext)}{marker}")
        print(f"  TOTAL {label}: {total} LOC, {len(names)} funciones")
        return total

    report(CANDIDATE, "Cluster propuesto (13 funciones)")
    report(EXCLUDED_INSTITUTIONAL, "Excluidas por F-DT.1")


if __name__ == "__main__":
    analyze(sys.argv[1] if len(sys.argv) > 1 else "src/kicad_mcp/tools/pcb.py")
```

Ejecución (`python3 s42_geometry_cluster.py src/kicad_mcp/tools/pcb.py`),
salida íntegra sobre el commit base:

```text
=== Cluster propuesto (13 funciones) ===
  _dist_point_segment              L253    12 LOC  externos=['math']
  _copper_distance_mm              L267    18 LOC  externos=['CopperItem', '_dist_point_segment', 'math']
  _match_copper                    L287    22 LOC  externos=['CopperItem', '_copper_distance_mm']
  _bbox_distance_to_point          L311    11 LOC  externos=['math']
  _copper_distance_to_bbox         L324    21 LOC  externos=['CopperItem', '_bbox_distance_to_point', '_segment_intersects_bbox']
  _closest_point_copper_bbox       L347    14 LOC  externos=['CopperItem', '_bbox_distance_to_point']
  _closest_board_edge              L363    17 LOC  externos=['BBoxMm']
  _segment_intersects_bbox         L382    34 LOC  externos=[]
  _copper_in_bbox                  L418    12 LOC  externos=['CopperItem', '_segment_intersects_bbox']
  _copper_on_layer                 L432     6 LOC  externos=['CopperItem']
  _rounded_rect_sdf                L760    15 LOC  externos=['math']
  _dist_segment_to_pad             L777    40 LOC  externos=['PadGeom', '_rounded_rect_sdf', 'math']
  _find_track_pad_collision        L819    30 LOC  externos=['PadGeom', '_dist_segment_to_pad']
  TOTAL Cluster propuesto (13 funciones): 252 LOC, 13 funciones

=== Excluidas por F-DT.1 ===
  _polygon_is_simple               L480    21 LOC  externos=['_segments_intersect']
  _segments_intersect              L440    38 LOC  externos=[]
  _point_in_polygon                L503    17 LOC  externos=[]
  TOTAL Excluidas por F-DT.1: 76 LOC, 3 funciones
```

Cero filas marcadas `<-- ARISTA A` — ninguna de las 13 funciones toca
`bridge`, el trío de helpers, ni la taxonomía de errores.

Cobertura de tests (grep de cada uno de los 16 nombres —13 + 3 excluidas—
contra `tests/`): cero coincidencias en los 16 casos.

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
