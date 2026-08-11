# 01 — Inventario actual (Fase 1) — `src/kicad_mcp/tools/pcb.py`

Rederivado íntegramente sobre `SHA_S47_ENTRADA = 33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b`,
sin copiar cifras de contexto (§6 del contrato). Herramienta:
`$S47_TMP/tools/inventory.py` (stdlib `ast`/`hashlib`/`json`; sin dependencias
nuevas, F5), ejecutada en modo (a). Datos crudos en `$S47_TMP/raw/inventory.json`.

## 1. Tamaño del archivo

```bash
wc -l src/kicad_mcp/tools/pcb.py   # 3161
```

`pcb.py:16` contiene `from __future__ import annotations` (PEP 563) — ver §5
(limitación metodológica sobre anotaciones).

## 2. Enumeración de V (§7.1.1 de v6)

| Categoría | Cuenta | Método |
|---|---|---|
| `@mcp.tool` de pcb.py | 19 | decorador `@mcp.tool(...)` resuelto por AST sobre closures directas de `register()` |
| Closures directas de `register()` | 20 | `FunctionDef` en el nivel inmediato del cuerpo de `register()` |
| Helpers top-level de pcb.py | 38 | `FunctionDef` a nivel de módulo, excluyendo `register` |
| Constantes top-level de pcb.py | 5 | `Assign`/`AnnAssign` a nivel de módulo |
| **`|V|` total** (unión, dedup) | **63** | 19 mcp_tools ⊆ 20 closures; 20+38+5 = 63 |

19 de las 20 closures llevan `@mcp.tool`; la excepción es `_delete_copper`
(closure interna, sin decorador MCP, consumida por `delete_track`/`delete_via`).

```
mcp_tools (19): add_keepout_zone, add_track, add_via, add_zone, delete_track,
  delete_tracks_bulk, delete_via, delete_zone, draw_board_outline, fill_zones,
  get_component_detail, get_footprint_neighbors, get_tracks, get_zones,
  move_footprint, reload_board_from_disk, route_board, save_board,
  set_footprint_ref
```

```
constantes top-level (5): _DELETE_TOLERANCE_MM (L75), _TRACKS_DEFAULT_BUDGET (L79),
  _TRACKS_BUDGET_SAFETY (L82), _STITCH_RADIUS_MM (L88), _OPPOSITE_LAYER (L89)
```

## 3. Grafo tipado E

**92 aristas** dedup por `(u, v, tipo)` entre miembros de V, de los 8 tipos de
§7.1.1 (`CALL`, `NAME_REF`, `DECORATOR`, `DEFAULT`, `ANNOTATION`,
`ATTRIBUTE_READ`, `CONSTANT_READ`, `MONKEYPATCH_TARGET`). En este archivo, las
aristas V-internas observadas se concentran en `CALL`, `CONSTANT_READ` y
`ATTRIBUTE_READ`; no se observó ningún caso de `DEFAULT` V-interno (ningún
default de parámetro referencia a otro miembro de V) ni `DECORATOR` V-interno
(los decoradores `@mcp.tool`/`@mutating_tool` son importados, no miembros de
V — contribuyen a `frontera_saliente_otras`, no al grafo interno).
`MONKEYPATCH_TARGET` no aparece como arista V-interna porque los dos símbolos
parcheados (`run_drc`, `run_autoroute`) son **importados**, no miembros de V
— ver §6.

## 4. Captura de scope de `register()` (relevante para M2 d1)

`register(mcp, *, ipc_bridge=None)` tiene un único assign propio:
`bridge = ipc_bridge or IpcBridge()` (L924). Herramienta dedicada:
`$S47_TMP/tools/captures.py` (rederivación independiente, no tomada de
`docs/analisis/40-dt1-caracterizacion.md`).

```
Las 20 closures referencian `mcp` — SOLO como blanco del decorador
  `@mcp.tool(...)`, nunca dentro del cuerpo ejecutable (verificado
  separando decorator_list del cuerpo en el AST).
18 de las 20 closures referencian además `bridge` DENTRO del cuerpo
  (uso real: IPC hacia KiCad). Las 2 excepciones son `delete_track` y
  `delete_via`, que delegan íntegramente en `_delete_copper` (quien sí
  captura `bridge`) sin pasarlo como argumento explícito.
```

Esta cifra (18/20 capturan `bridge` en el cuerpo, 20/20 vía decorador)
**coincide exactamente** con `docs/analisis/40-dt1-caracterizacion.md §6`
("las 20 capturan `mcp`; 18 capturan además `bridge`"), rederivada de forma
independiente — cross-check positivo entre S40 y S47 sobre el mismo hecho
estructural.

`register_all` en `src/kicad_mcp/tools/__init__.py` ya inyecta `mcp`+`bridge`
a seis sub-registradores (`register_meta`, `register_world`,
`register_validate`, `register_export`, `register_pcb`, `register_sch`) —
el patrón de desacople para un séptimo módulo `pcb/<familia>.py` con firma
`register_x(mcp, *, bridge)` ya existe en el repo (no se inventa nada nuevo).

## 5. Política cerrada de resolución AST (§7.1.1.bis) — aplicación y límites declarados

**Alcance operativo declarado (limitación metodológica, Regla 4 de la fe de
erratas):** la política se aplicó a referencias de identificador (`Name` en
`Load`, `Attribute` de lectura/llamada, decorador, default). Las anotaciones
de tipo (parámetros y retorno) se clasificaron **uniformemente**
`REFERENCIA_AMBIGUA` por `from __future__ import annotations` (PEP 563,
pcb.py:16) — no se resuelven individualmente símbolo a símbolo, no
contribuyen aristas `ANNOTATION` al grafo V-interno, y se cuentan aparte:

```
Total REFERENCIA_AMBIGUA por anotación aplazada: 58 ocurrencias
  (agregado por miembro de V en frontera_saliente_ambigua, con
  path:línea y descripción en raw/inventory.json).
```

**Verificación de que esta ambigüedad nunca afecta un símbolo propuesto para
extracción (evita activación espuria de R10):** los tipos anotados en las
firmas de pcb.py resuelven, en todos los casos inspeccionados, a tipos
importados de `bridge/ipc.py` (`IpcBridge`, `BoardHandle`, `FootprintData`,
`PadGeom`, `CopperItem`, …) o a tipos primitivos (`str`, `float`, `int`,
`dict[str, Any]`) — **nunca** a un símbolo de V. Por tanto, aunque la
anotación es técnicamente `REFERENCIA_AMBIGUA` por PEP 563, no dispara R10
para ninguno de los 12 candidatos con ficha (verificado nominalmente por
candidato en `02-candidatos/<nombre>.md`).

**`REFERENCIA_INEXPRESABLE`:** categoría vacía por evidencia, no por omisión.

```bash
grep -n "getattr(\|setattr(\|__dict__\|\bexec(\|\beval(\|patch(" src/kicad_mcp/tools/pcb.py
# exit 1 — sin coincidencias
```

Ninguna referencia V-interna desapareció silenciosamente: las 92 aristas +
58 ambigüedades de anotación + las resoluciones a `RESUELTA_A_MODULO_EXTERNO`
(§6) y `RESUELTA_A_STDLIB_O_BUILTIN` (no aristan, contadas y descartadas
explícitamente en el código de la herramienta) cubren exhaustivamente los
`Name`/`Attribute`/`Call` visitados.

## 6. Fronteras salientes a módulos externos

`frontera_saliente_otras` (unión sobre todo pcb.py, deduplicado por ruta
canónica de import):

```
..audit.logger        ..bridge.autoroute      ..bridge.ipc
..bridge.rules         ..bridge.rules_reader   ..bridge.state_builder
..errors                ..gates.g1              ..logging_config
..snapshots             ..tools.world           ._mutating
.pcb_encoders
```

`.pcb_encoders` confirma la frontera dejada por DT1 Slice 1 (sesión 41): los
7 re-exports (`_encode_component_detail`, `_encode_tracks`, `_encode_zones`,
`_sanitize_space_delimited`, `_tracks_filter_desc`,
`_zone_is_axis_aligned_rect`, `_zones_filter_desc`) se importan en pcb.py con
el patrón `from .pcb_encoders import X as X` (self-alias, re-export
explícito) — estos 7 símbolos **no son miembros de V** (no están definidos en
pcb.py, están importados), por diseño y consistente con CLAUDE.md regla 6.

## 7. Monkeypatches ADR-0012

```bash
grep -rn "monkeypatch.setattr(pcb_module" tests/
```

```
run_drc          -> tests/test_route_board.py, test_pcb_session31b_duplicate_refs.py,
                     test_pcb_session32b_refill_silencioso_canary.py,
                     test_pcb_session32d_orphan_pads_stitching_canary.py
run_autoroute     -> (los mismos 4 archivos)
```

Ambos símbolos son **importados** en pcb.py (`from ..bridge.rules import ...
run_drc`, `from ..bridge.autoroute import ... run_autoroute`) — no son
miembros de V. El único miembro de V que los referencia es `route_board`
(L2763, 2768, 2865, 2918) — verificado por AST, ningún otro miembro de V los
menciona. Coincide exactamente con
`docs/analisis/40-dt1-caracterizacion.md §7` ("Ambos símbolos se usan
exclusivamente dentro de `route_board`") y con el propio grep manual de esta
sesión — tres fuentes independientes convergen.

## 8. Fronteras entrantes desde `src/**` y `tests/**`

**`frontera_entrante_src(K)` — vacía para los 63 miembros de V, sin
excepción.** El único punto de acoplamiento entre `src/**` (fuera de
pcb.py) y pcb.py es `src/kicad_mcp/tools/__init__.py:35`:
`from .pcb import register as register_pcb` — referencia a `register`, que
**no es miembro de V** (es el contenedor). Consecuencia estructural:
**F-DT.4 (`|frontera_entrante_src(K)| >= 3`) no puede activarse para ningún
cluster de este archivo en su estado actual** — el máximo posible es 0.

**`frontera_entrante_tests(K)` (import/patch por path `pcb.<k>`) — no vacía
solo para:**

```
_find_duplicate_refs  <- tests/test_pcb_session31b_duplicate_refs.py
                          (from kicad_mcp.tools.pcb import _find_duplicate_refs)
```

Los demás 62 miembros de V tienen `frontera_entrante_tests` vacía bajo la
definición **literal** de §7.1.2 ("importa o patcha por path `pcb.<k>`").

**Limitación metodológica declarada:** esta definición literal **no captura**
cómo la suite realmente ejercita los 19 `@mcp.tool` — vía invocación dinámica
del registro FastMCP (`client.call_tool("<nombre>", {...})`), un mecanismo de
despacho por string, no un import/patch de path Python. Se instrumentó un
trazador complementario (`$S47_TMP/tools/coverage.py`,
`$S47_TMP/raw/coverage.json`) que localiza cada `call_tool("<nombre>", ...)`
en tests/**, resuelve el marcador pytest de la función de test contenedora
(`integration`/`integration_gui`/`integration_gui_slow`/ninguno) y detecta si
la función de test contiene al menos un `assert` sobre la variable ligada al
resultado de la llamada — proxy operativo de "la aserción depende del
camino" usado para M4 (§10-M4 de v6). Resultado íntegro: los 19 `mcp_tools`
de pcb.py tienen **al menos una** invocación `call_tool` en la suite offline
(sin marca `integration*`) con `assert` sobre el resultado — el detalle por
tool está en `raw/coverage.json` y se cita nominalmente por candidato en
`02-candidatos/<nombre>.md` (§10-M4).

## 9. Contraste con `docs/analisis/40-dt1-caracterizacion.md` (§7.2, priors S40)

La caracterización de sesión 40 (previa a DT1 Slice 1) identificó 7 clusters
exclusivos (§5 de ese documento) y evaluó 5 contra el §10 del contrato v2
(§9 de ese documento). Tres quedaron `apto`/`apto (alternativa)` además del
elegido para Slice 1 ("Encoders ad-hoc", ya cerrado):

```
"Resolución de add_track"        -> apto (alternativa)
"Vecindad geométrica"            -> apto (alternativa menor)
"Zonas (validación)"             -> apto, pero al límite del criterio
                                     "una familia funcional" de v2
"Stitching/refill (routing)"     -> VETADO por I-4 (route_board/monkeypatch)
```

Rederivados de forma independiente en esta sesión (§7 de este contrato v6),
estos cuatro clusters reaparecen exactamente como:

```
"Resolución de add_track"  -> Ficha 9 de este paquete (survivor, con ficha)
"Vecindad geométrica"      -> Ficha 3 de este paquete (survivor, con ficha)
"Zonas (validación)"       -> excluido institucional F-DT.1 (v6 amplía el
                               criterio de zonas respecto de v2; NO es una
                               refutación de S40, es una evolución del
                               contrato — ver 02-candidatos/descartados.md)
"Stitching/refill"         -> excluido institucional F-DT.1 (coincide con
                               el veto I-4 de S40 por route_board)
```

Dos priors adicionales que S40 documenta (§5/§8) sin llevarlos a tabla de
veredicto en §9 también reaparecen: "Post-mutación de move_footprint" →
Ficha 8; "Núcleo de borrado de cobre" → Ficha 1. Un séptimo prior de S40,
"Contorno" (`draw_board_outline`), reaparece como Ficha 10.

**CR1 (Priors de S40 siguen siendo los tres mejores):** `NO REFUTADA` para
los dos priors "apto" (add_track, vecindad geométrica) que sobreviven
intactos al re-cómputo; el tercero ("zonas") pasa de "apto, al límite" a
excluido institucional por el endurecimiento explícito de F-DT.1 en v6
respecto de v2 — un cambio de contrato documentado, no un hallazgo de
inconsistencia. Registro completo del criterio en `03-refutacion.md`.

**CR3 (Dependencias listadas en S40 no han cambiado):** `NO REFUTADA` — el
grafo de dependencias, capturas de scope y monkeypatches rederivados en esta
sesión coinciden byte a byte (mismos nombres, mismos consumidores) con S40
§5-§7, pese a haberse recalculado con una herramienta AST distinta y sin leer
el documento de S40 antes de rederivar (verificación honesta: el contraste
de esta sección se escribió **después** de correr las herramientas de S47).

## 10. Trazabilidad

```
$S47_TMP/tools/inventory.py    -> raw/inventory.json  (V, E, fronteras, imports)
$S47_TMP/tools/captures.py     -> raw/captures.json   (d1 por closure)
$S47_TMP/tools/coverage.py     -> raw/coverage.json   (M4, call_tool + assert)
$S47_TMP/tools/cluster.py      -> raw/clusters.json   (Fase 2, ver 02-candidatos/)
$S47_TMP/tools/m2.py           -> raw/m2.json         (M2_estado_actual, ver 02-candidatos/)
```

Ningún script escribe dentro del working tree del repo; todos leen
`/home/astra/Desktop/agent_proyect/kicad-mcp` en modo solo-lectura y
persisten en `$S47_TMP`.
