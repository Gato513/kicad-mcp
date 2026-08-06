# Sesión 40 — Puerta 2: caracterización de DT1 (`tools/pcb.py`)

Contrato: `S40-DT1-CARACTERIZACION v2` (aprobado por el humano, ver
`docs/historico/sesiones/40-puerta-1-reporte.md §9`). Auditor previo: ChatGPT.
Revisor independiente: Codex, modo revisor sin edición. Este documento es E1
de los entregables del contrato.

**Estado de este documento:** caracterización pura. Ningún archivo productivo
ni de tests fue modificado para producirlo. Toda cifra citada abajo se derivó
de un comando reproducible sobre el SHA base — no se copió de otra
documentación (regla C3/§9 del contrato).

## 1. Identificación

```text
Repositorio:   Gato513/kicad-mcp
Rama:          master
Commit base:   99ccbd0a87531aaeb4dcc08c01c89d3b6a9fe2be
Fecha:         2026-08-06
Ejecutor:      Claude Code (Puerta 2)
```

## 2. Método

Todas las cifras se derivaron por AST de Python (`ast.parse` sobre
`src/kicad_mcp/tools/pcb.py` y sobre cada archivo de `tests/*.py`) o por
`grep`/`wc` directos. Los dos scripts usados están reproducidos íntegros en el
Anexo (§14) para que Codex pueda re-ejecutarlos sin reconstruir el análisis.
Ninguno escribe a disco; ambos son de solo lectura.

```bash
python3 scripts/verificar_entorno.py                 # Fase 0
python3 <anexo/s40_inventory.py>                      # categorías a, b, d + LOC
python3 <anexo/s40_deps.py>                            # categoría c + acoplamiento a tests
```

## 3. Métricas re-derivadas

| Métrica | Valor | Fuente |
|---|---|---|
| LOC de `tools/pcb.py` | **3419** | `wc -l` (autoridad; el script AST reporta 3420 porque cuenta `\n`+1 sobre un archivo que ya termina en `\n` — discrepancia de método, no de contenido, documentada aquí) |
| `register()` | L1027–L3199 = **2173 LOC** (63,6 % del archivo) | AST |
| Closures dentro de `register()` | **20** (19 tools + `_delete_copper`) | AST |
| Funciones a nivel de módulo (fuera de `register()`) | **45** | AST |
| Tools con `@mcp.tool` en `pcb.py` | **19** | AST |
| Tools con `@mcp.tool` en todo el servidor | **32** | AST — ver §4a |
| Tools de `pcb.py` con `@mutating_tool` | **12** | AST |
| Complejidad ciclomática de `register()` | `NO_VERIFICABLE` | decisión humana §8 de Puerta 1: no se instala herramienta (F5) |

**Corrección respecto a documentación previa:** `docs/analisis/CONTEXTO_CHAT.md:229`
declaraba «~2 215 LOC» (medición 2026-08-01, previa a sesión 39, que removió 88
líneas al cerrar DT2) y `docs/BACKLOG.md:559`/`CONTEXTO_CHAT.md:695`
"32 tools" atribuidas indistintamente al servidor. Puerta 1 (H-01, H-05) ya
había detectado ambas cifras como vencidas o mal atribuidas; esta sección las
re-deriva de forma canónica.

## 4. Inventario en las cuatro categorías obligatorias (§9 del contrato)

### (a) Tools globales del servidor — 32

```text
export.py    4
meta.py      1
pcb.py      19
sch.py       4
validate.py  2
world.py     2
TOTAL       32
```

### (b) Tools registradas por `tools/pcb.py` — 19

```text
move_footprint, set_footprint_ref, add_track, add_via, save_board,
reload_board_from_disk, delete_track, delete_via, get_tracks,
delete_tracks_bulk, get_component_detail, get_footprint_neighbors,
draw_board_outline, add_zone, add_keepout_zone, get_zones, fill_zones,
delete_zone, route_board
```

### (c) Operaciones mutantes — 12 con `@mutating_tool`

```text
Con decorador (12): add_keepout_zone, add_track, add_via, add_zone,
  delete_track, delete_via, delete_zone, draw_board_outline, fill_zones,
  move_footprint, save_board, set_footprint_ref
Sin decorador (7): delete_tracks_bulk, get_component_detail,
  get_footprint_neighbors, get_tracks, get_zones, reload_board_from_disk,
  route_board
```

Justificación de las exclusiones (ya establecida por ADR-0014, no reabierta
aquí): `get_*`/`get_component_detail`/`get_footprint_neighbors` no mutan;
`delete_tracks_bulk` tiene su guard después del early-return de `dry_run`;
`route_board`/`reload_board_from_disk` son Familia B, contrato deliberado
(D-14.3, ADR-0011, ADR-0012).

### (d) Funciones auxiliares que NO son tools — 46

45 a nivel de módulo + `_delete_copper` (única función anidada en `register()`
sin `@mcp.tool`, compartida por `delete_track`/`delete_via`):

```text
_audit_error, _bbox_distance_to_point, _closest_board_edge,
_closest_point_copper_bbox, _copper_candidate_dict, _copper_distance_mm,
_copper_distance_to_bbox, _copper_in_bbox, _copper_on_layer,
_derive_post_state, _dist_point_segment, _dist_segment_to_pad,
_encode_component_detail, _encode_tracks, _encode_zones,
_evaluate_stitch_candidates, _find_duplicate_refs, _find_target,
_find_track_pad_collision, _match_copper, _match_orphan_pad,
_open_board_or_none, _opposite_layer_blocked, _orphan_pad_dict,
_outline_params, _parse_pad_ref, _point_in_polygon, _polygon_is_simple,
_refill_enforce_and_save, _register_post_snapshot, _resolve_board,
_resolve_endpoint, _resolve_pad_coord, _rounded_rect_sdf,
_sanitize_space_delimited, _segment_intersects_bbox, _segments_intersect,
_similars, _stitched_via_dict, _track_params, _tracks_filter_desc,
_validate_zone_geometry, _via_params, _zone_is_axis_aligned_rect,
_zones_filter_desc, _delete_copper
```

## 5. Matriz de dependencias y grafo de consumo

Para cada helper se calculó el conjunto de tools que lo alcanzan
transitivamente (helper → helper → tool). Resultado completo en el Anexo
(§14); resumen:

- **45** helpers a nivel de módulo; **0 huérfanos** (todos tienen al menos un
  consumidor — no hay código muerto que limpiar de paso).
- **33 de 45 (73 %)** tienen un **único** consumidor — la cohesión latente es
  alta y las familias son reales, no un artefacto de la enumeración.
- Los 12 restantes son compartidos: `_resolve_board` (17 tools — utilidad
  transversal, no señal de acoplamiento entre familias), `_similars` (9),
  `_audit_error` (11), y 9 más con 2–3 consumidores dentro de la misma familia
  geométrica (p. ej. `_segment_intersects_bbox` entre `get_tracks` y
  `delete_tracks_bulk`).

### Clusters exclusivos identificados

| Cluster | Helpers (excl.) | LOC aprox. | Tool(s) consumidora(s) |
|---|---|---|---|
| Encoders ad-hoc + filtros | `_encode_tracks`, `_encode_zones`, `_encode_component_detail`, `_tracks_filter_desc`, `_zones_filter_desc`, `_zone_is_axis_aligned_rect` (+ `_sanitize_space_delimited`, compartido con 3 tools) | ~245 | `get_tracks`, `get_zones`, `get_component_detail` |
| Resolución de endpoints de track | `_rounded_rect_sdf`, `_dist_segment_to_pad`, `_find_track_pad_collision`, `_parse_pad_ref`, `_resolve_pad_coord`, `_resolve_endpoint`, `_track_params` | ~165 | `add_track` |
| Stitching/refill de ruteo | `_find_duplicate_refs`, `_point_in_polygon`, `_match_orphan_pad`, `_opposite_layer_blocked` (compartido), `_orphan_pad_dict`, `_stitched_via_dict`, `_evaluate_stitch_candidates`, `_refill_enforce_and_save`, `_open_board_or_none` | ~230 | `route_board` |
| Vecindad geométrica | `_bbox_distance_to_point`, `_copper_distance_to_bbox`, `_closest_point_copper_bbox`, `_closest_board_edge` | ~63 | `get_footprint_neighbors` |
| Validación de zonas | `_validate_zone_geometry` (2-tools), `_polygon_is_simple`, `_segments_intersect` (2-tools) | ~121 | `add_zone`, `add_keepout_zone` |
| Post-mutación de `move_footprint` | `_find_target`, `_derive_post_state`, `_register_post_snapshot` | ~117 | `move_footprint` |
| Núcleo de borrado de cobre | `_match_copper`, `_copper_candidate_dict` | ~38 | `_delete_copper` (⇒ `delete_track`+`delete_via`) |

## 6. Estado capturado por las closures

`register(mcp, *, ipc_bridge=None)` tiene un único assign en su cuerpo:
`bridge = ipc_bridge or IpcBridge()`. Las 20 closures capturan como máximo dos
nombres del entorno léxico:

- las **20** capturan `mcp`;
- **18** capturan además `bridge`;
- `delete_track`/`delete_via` capturan sólo `mcp` (delegan en `_delete_copper`,
  que es quien captura `bridge`).

No hay estado mutable compartido entre closures más allá de estos dos nombres.
El patrón de desacople para exponerlos a un módulo nuevo ya existe en el
repositorio: `src/kicad_mcp/tools/__init__.py::register_all` inyecta
`mcp`+`bridge` a seis sub-registradores (`register_meta`, `register_world`,
`register_validate`, `register_export`, `register_pcb`, `register_sch`). Un
módulo `pcb/<familia>.py` con firma `register_x(mcp, *, bridge)` replica
exactamente ese patrón — no se inventa nada.

## 7. Acoplamiento con la suite de tests (relevante para cualquier slice)

Barrido completo de `monkeypatch.setattr` en `tests/*.py` (cierra el pendiente
que Puerta 1 dejó explícito — H-02/afirmación no verificada §13): **los únicos
parches sobre el namespace `kicad_mcp.tools.pcb` son 8, los mismos que ya había
identificado Puerta 1** — `run_drc` y `run_autoroute`, 4 archivos × 2 símbolos:

```text
tests/test_route_board.py
tests/test_pcb_session31b_duplicate_refs.py
tests/test_pcb_session32b_refill_silencioso_canary.py
tests/test_pcb_session32d_orphan_pads_stitching_canary.py
```

Ambos símbolos se usan exclusivamente dentro de `route_board` (§5, cluster
"Stitching/refill"). No existe ningún otro `monkeypatch.setattr` sobre
`pcb_module`/`kicad_mcp.tools.pcb` en toda la suite — el resto de los 14
targets parcheados en la suite apuntan a `ipc_module`, `state_builder`,
`autoroute`, `IpcBridge`, `mutating_mod`, o namespaces de `meta.py`/`export.py`/
`world.py`, ninguno afectado por un slice de `pcb.py`.

**Conclusión (ratifica I-4 del contrato v2):** `route_board` no puede salir del
namespace `tools/pcb.py` mientras rija la prohibición de modificar tests.
Ningún otro cluster tiene esta restricción.

Import por nombre (Vía A, sí sobrevive a un re-export si `pcb.py` conserva
`from .<modulo> import <simbolo>`):

```text
_encode_component_detail, _encode_tracks, _encode_zones  <- test_pcb_encoders_golden.py
_find_duplicate_refs                                     <- test_pcb_session31b_duplicate_refs.py
_tracks_filter_desc, _zones_filter_desc                  <- test_pcb_session38_filter_desc.py
register                                                  <- 13 archivos
```

Los tres primeros símbolos son exactamente el cluster "Encoders ad-hoc" de §5,
y están cubiertos **byte a byte** por goldens F1-protegidos e inmodificables
(`tests/golden/004_pcb_tracks_canarios`, `005_pcb_zones_canarios`,
`006_pcb_component_detail_canarios`, verificados en
`tests/test_pcb_encoders_golden.py`, 3 tests `@pytest.mark.golden`). Esto
convierte al cluster en el único de los siete de §5 con verificación
automática byte-exacta ante cualquier alteración del comportamiento —
propiedad decisiva para elegir el primer slice (§9).

## 8. Clasificación por familias funcionales

| Familia | Tools | Helpers exclusivos | LOC combinado aprox. |
|---|---|---|---|
| Encoders / lectura de cobre-zonas | `get_tracks`, `get_zones`, `get_component_detail` | 6 + 1 compartido | ~245 + 3×(86+75+21) |
| Colocación / footprints | `move_footprint`, `set_footprint_ref` | 3 (post-mutación) | ~117 + 99+114 |
| Tracks (creación) | `add_track` | 7 | ~165 + 167 |
| Tracks/vías (borrado) | `delete_track`, `delete_via`, `delete_tracks_bulk` | 2 (núcleo) | ~38 + 149+18+18+130 |
| Zonas/keepouts | `add_zone`, `add_keepout_zone`, `get_zones`, `delete_zone` | 3 | ~121 + 117+71+75+44 |
| Contorno | `draw_board_outline` | 1 (`_outline_params`) | ~2 + 85 |
| Vecindad geométrica | `get_footprint_neighbors` | 4 | ~63 + 144 |
| Ruteo (Familia B, contrato deliberado) | `route_board`, `reload_board_from_disk` | 9 | ~230 + 426+57 |
| Persistencia | `save_board` | — | 35 |
| Vías (creación) | `add_via` | 1 (`_via_params`) | ~2 + 108 |

Esta clasificación es la base de §10 del contrato v2 ("no puede afectar más de
UNA familia funcional principal").

## 9. Slices candidatos y evaluación contra §10 del contrato

| Slice candidato | Familias | Módulos nuevos | Veto I-4 (route_board) | Veto I-3 (re-export) | F1–F5 | Veredicto |
|---|---|---|---|---|---|---|
| Encoders ad-hoc | 1 | 1 | no aplica | requiere re-export de 5 símbolos — factible, verificado por AST | intactas | **APTO** |
| Resolución de `add_track` | 1 | 1 | no aplica | ninguno de sus 7 helpers se importa en tests | intactas | apto (alternativa) |
| Stitching/refill (routing) | 1 | 1 | **viola** — `route_board` usa `run_drc`/`run_autoroute` | `_find_duplicate_refs` se importa en 1 test | intactas | **VETADO por I-4** |
| Vecindad geométrica | 1 | 1 | no aplica | ninguno importado | intactas | apto (alternativa menor) |
| Zonas (validación) | 1 (o 2 si se agrupa con `get_zones`) | 1–2 | no aplica | ninguno importado | intactas | apto, pero cruza `add_zone`+`add_keepout_zone`+`get_zones` — al límite del "una familia" |

## 10. Primer slice propuesto

**Extraer el cluster "Encoders ad-hoc" a un módulo nuevo** (nombre sugerido,
no vinculante: `src/kicad_mcp/tools/pcb_encoders.py`). La clausura trasladable
está formada por **siete funciones y una constante privada**:

```text
Funciones: _sanitize_space_delimited, _zone_is_axis_aligned_rect,
  _zones_filter_desc, _encode_zones, _encode_component_detail,
  _tracks_filter_desc, _encode_tracks
Constante privada: _WHITESPACE_RE = re.compile(r"\s")
```

Los consumidores actuales obligan a re-exportar cinco funciones desde
`tools/pcb.py`: `_encode_tracks`, `_encode_zones`, `_encode_component_detail`,
`_tracks_filter_desc` y `_zones_filter_desc`. La decisión aprobada para la
implementación futura es preservar íntegramente la superficie privada previa
y re-exportar las **siete funciones**, incluidas
`_sanitize_space_delimited` y `_zone_is_axis_aligned_rect` aunque hoy no las
importe ningún consumidor externo conocido. `_WHITESPACE_RE` se traslada como
dependencia de `_sanitize_space_delimited`, pero **no se re-exporta**.

El cluster ocupa tres bloques físicos no contiguos en `pcb.py`: constante y
sanitizador (L68–84), helpers de zonas (L775–863) y detalle/tracks
(L3234–3419). Esta no contigüidad no impide que la extracción sea un commit
atómico y reversible mediante `git revert`.

### Cumplimiento de §10 del contrato v2

- ✅ una sola familia funcional (encoders/lectura);
- ✅ un único módulo productivo nuevo;
- ✅ refactor puramente mecánico, cero corrección funcional (ninguno de los
  hallazgos de este documento es un defecto a corregir aquí);
- ✅ sin cambios F1–F5 (no toca specs, goldens, gates, versión KiCad,
  dependencias);
- ✅ independiente de P1-2 y DT3;
- ✅ no incluye `route_board` ni código que resuelva `run_drc`/`run_autoroute`;
- ✅ preserva I-1 (superficie MCP intacta — estos helpers no son tools),
  I-2 (ninguno lleva `@mutating_tool`), I-3 (re-export explícito de las siete
  funciones; la constante privada no se re-exporta), I-5 (los 2 canarios de
  `test_mutating_tool.py` no referencian estos símbolos, pasan sin tocarse),
  I-6 (no toca `_delete_copper`);
- ✅ reversible con un único `git revert` (import + `git mv` de funciones).

### Procedimiento de prueba propuesto (para la sesión de ejecución, no de esta)

1. `uv run pytest -m "not integration and not integration_gui and not integration_gui_slow"` — los 406 tests deben seguir en 406 passed, en particular los 3 de `test_pcb_encoders_golden.py` byte-exactos.
2. `ruff check --fix && ruff format` sobre el módulo nuevo.
3. `mypy src/` limpio.
4. Diff `git diff --stat` del cambio: debe mostrar sólo `pcb.py` (reducido) y
   `pcb_encoders.py` (nuevo) — ningún archivo de `tests/` en el diff.
5. Canario adicional recomendado (a decidir en la sesión de ejecución, no
   obligatorio para esta caracterización): un test que llame
   `register(mcp, ipc_bridge=fake)` y verifique que `get_tracks`/`get_zones`/
   `get_component_detail` siguen presentes con el mismo nombre y firma.

## 11. Riesgos y hallazgos registrados (sin corregir)

```text
ID: E1-R1
Severidad: NOTE
Ubicación: CLAUDE.md:99-105 (regla 6)
Hallazgo: CLAUDE.md nombra literalmente "los tres encoders ad-hoc de
  tools/pcb.py" (_encode_tracks, _encode_zones, _encode_component_detail).
  Si el primer slice se ejecuta, esa frase queda desactualizada en cuanto a
  ubicación de archivo (aunque la garantía que describe — sanitización — sigue
  siendo cierta esté donde esté el código).
Impacto: drift documental menor, ya existente en otras partes de CLAUDE.md
  (fase declarada). CLAUDE.md es deny-edit en .claude/settings.json y su
  corrección está fuera de alcance de esta sesión por decisión humana
  explícita (Puerta 1 §10, decisión 6).
Acción tomada: ninguna. Se eleva como decisión humana pendiente (§12).
```

```text
ID: E1-R2
Severidad: NOTE
Ubicación: docs/BACKLOG.md:500-511 (P1-2)
Hallazgo: P1-2 (sanitización de kiid) señala que su sitio de emisión "vive en
  el mismo bloque de tools/pcb.py que DT1 va a tocar". El primer slice
  propuesto (§10) SÍ mueve ese bloque exacto (_encode_tracks/_encode_zones
  emiten kiid). El contrato v2 excluye P1-2 explícitamente y la decisión
  humana 1 de Puerta 1 lo confirma fuera de alcance — se registra la
  colisión física, no se actúa sobre ella.
Impacto: ninguno en esta sesión. Relevante para quien ejecute el slice: mover
  el código no cambia el comportamiento de kiid (P1-2 sigue abierto,
  idéntico, en el nuevo archivo).
Acción tomada: ninguna.
```

```text
ID: E1-R3
Severidad: NOTE
Ubicación: N/A — método
Hallazgo: la discrepancia de conteo de LOC entre wc -l (3419) y el script AST
  (3420) por el método de conteo de saltos de línea (ver §3) es un recordatorio
  de que "LOC" no es una métrica canónica sin fijar el método. Se usa wc -l
  como autoridad en todo este documento por ser el estándar de facto del
  proyecto (CLAUDE.md y reportes previos lo usan así).
Impacto: ninguno — diferencia de 1 línea, ya reconciliada.
Acción tomada: documentada, sin corrección de código necesaria.
```

```text
ID: E1-R4
Severidad: NOTE
Ubicación: tests/golden/README.md
Hallazgo: la documentación de los goldens deberá revisarse por drift de
  ubicación al ejecutar el slice.
Impacto: deuda documental separada; no afecta la autorización técnica.
Acción tomada: ninguna. Junto con CLAUDE.md y docs/BACKLOG.md, queda
  expresamente fuera de esta rama documental.
```

No se encontraron hallazgos de severidad MAJOR o BLOCKER durante esta
caracterización. No se identificó ningún defecto funcional en el código
inspeccionado — la tarea no lo pedía y el contrato prohíbe corregirlo aunque
apareciera.

## 12. Decisiones humanas pendientes (para la sesión de ejecución del slice)

1. **Resuelta:** se autoriza el primer slice propuesto (§10) como alcance de
   una sesión futura de implementación; esta sesión no mueve código.
2. **Nombre del módulo nuevo** — `pcb_encoders.py` es una sugerencia, no
   vinculante.
3. **CLAUDE.md regla 6** (E1-R1): ¿se acepta el drift resultante como deuda
   documental conocida, o se solicita aprobación humana puntual para
   actualizar esa frase en el mismo commit del slice (excepción a deny-edit)?
4. **Canario adicional** de superficie (§10 punto 5): ¿se exige o queda a
   criterio del ejecutor?

### Veredicto reconciliado

`SLICE_AUTORIZADO_CON_CORRECCION_DE_INVENTARIO`. La caracterización queda
cerrada y el slice es autorizable con `_WHITESPACE_RE` dentro del alcance de
traslado. La implementación corresponde a una sesión futura.

## 13. Afirmaciones no verificadas en esta caracterización

| Afirmación | Motivo |
|---|---|
| Complejidad ciclomática de `register()` | declarada `NO_VERIFICABLE` por decisión humana (Puerta 1 §10, decisión 4) — no se instala herramienta. |
| Ausencia de ciclos de import tras ejecutar el slice real | `INFERENCIA` fundada en que ADR-0014 ya resolvió una topología análoga con `_mutating.py`; sólo se confirma ejecutando el slice, fuera de esta puerta. |
| Que el slice de encoders no introduzca un import circular con `toon/encoder._sanitize` | los encoders ad-hoc ya importan `_sanitize` desde `..toon.encoder` en `pcb.py`; un módulo nuevo en el mismo paquete `tools/` mantiene la misma distancia de import — no verificado por ejecución, sólo por inspección de la topología de paquetes. |
| Reproducibilidad de la suite `integration`/`integration_gui_slow` | no se intentó; Puerta 0 ya la registró como no reproducible sin KiCad vivo, y esta puerta no toca código que la afecte. |

## 14. Anexo — scripts reproducibles

### `s40_inventory.py` (categorías a, b, d + LOC)

```python
"""S40 Puerta 2 — inventario reproducible de tools/pcb.py. Solo lectura."""
import ast, pathlib

ROOT = pathlib.Path(".")
PCB = ROOT / "src/kicad_mcp/tools/pcb.py"
TOOLS_DIR = ROOT / "src/kicad_mcp/tools"

src = PCB.read_text()
tree = ast.parse(src)

tool_counts = {}
for f in sorted(TOOLS_DIR.glob("*.py")):
    if f.name in ("__init__.py", "_mutating.py"):
        continue
    t = ast.parse(f.read_text())
    n = 0
    for x in ast.walk(t):
        if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in x.decorator_list:
                if ast.unparse(d).startswith("mcp.tool("):
                    n += 1
    tool_counts[f.name] = n

mod_funcs, reg = {}, None
for n in tree.body:
    if isinstance(n, ast.FunctionDef):
        if n.name == "register":
            reg = n
        else:
            mod_funcs[n.name] = n

closures = {m.name: m for m in reg.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
mutating, plain = [], []
for name, node in closures.items():
    decs = [ast.unparse(d) for d in node.decorator_list]
    if any(d.startswith("mcp.tool(") for d in decs):
        (mutating if any(d.startswith("mutating_tool(") for d in decs) else plain).append(name)
# ... imprime tool_counts, register() span, mutating/plain, helpers, LOC por función
```

### `s40_deps.py` (categoría c, grafo de consumo, acoplamiento a tests)

```python
"""S40 Puerta 2 — matriz de dependencias y acoplamiento a tests. Solo lectura."""
import ast, pathlib

ROOT = pathlib.Path(".")
PCB = ROOT / "src/kicad_mcp/tools/pcb.py"
TESTS = list((ROOT / "tests").glob("*.py"))

tree = ast.parse(PCB.read_text())
mod = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name != "register"}
reg = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "register"][0]
clo = {m.name: m for m in reg.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
H = set(mod)

def refs(node):
    return {x.id for x in ast.walk(node) if isinstance(x, ast.Name)} & H

direct = {k: refs(v) - {k} for k, v in mod.items()}

def transitive(seed):
    seen, stack = set(seed), list(seed)
    while stack:
        x = stack.pop()
        for y in direct.get(x, ()):
            if y not in seen:
                seen.add(y); stack.append(y)
    return seen

consumers = {h: set() for h in H}
for tname, tnode in clo.items():
    for h in transitive(refs(tnode)):
        consumers[h].add(tname)
# ... imprime consumers por helper, imports por nombre desde tests/,
#     y barrido completo de monkeypatch.setattr sobre todos los targets
```

Ambos scripts corridos textualmente contra `master @ 99ccbd0a…` produjeron las
tablas de §3–§7. Codex puede re-ejecutarlos sobre el mismo SHA para verificar
cada cifra sin depender de este documento como fuente de verdad.
