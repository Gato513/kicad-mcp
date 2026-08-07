# Auditoría técnica — kicad-mcp

Rama auditada: `sesion/34b-license-readme-contributing` @ `b2d385e` · 2026-08-01
Método: lectura directa del repo + ejecución de la suite, linter, formatter, mypy y análisis de complejidad. Todo hallazgo cita archivo:línea o comando reproducible.

---

## 1. Resumen ejecutivo

**Qué es.** Servidor MCP sobre stdio que expone **32 tools** para que un agente LLM opere KiCad: lectura de esquemático/PCB en un formato comprimido propio (TOON), mutación atómica de cobre/zonas/footprints vía la API IPC nativa de KiCad (`kicad-python`), autorouting headless con Freerouting como subproceso, validación ERC/DRC y export de fabricación vía `kicad-cli`.

**Estado medido** (hechos, no estimaciones):

| Métrica | Valor | Comando |
|---|---|---|
| LOC producción | 11 988 en 33 archivos | `find src -name "*.py" \| xargs wc -l` |
| LOC test | 18 119 en 46 archivos (ratio 1,51:1) | ídem sobre `tests/` |
| Tests offline | **394 passed, 39 skipped, 29 deselected** en 58 s | `uv run pytest -m "not integration"` |
| Ruff (lint + format) | limpio, 82 archivos | `uv run ruff check` / `ruff format --check` |
| Mypy `strict = true` | **0 errores** en 33 archivos | `uv run mypy src/` |
| Docs | 132 `.md`, 14 ADRs, 4 specs, 7 investigaciones | `find docs -name "*.md" \| wc -l` |
| Historia | 163 commits, ~40 ramas de sesión | `git log --oneline \| wc -l` |

**Problemas que resuelve hoy** (no los planeados): el loop completo colocación → contorno → plano GND → autoruteo → refill → DRC → gerbers está cerrado y validado contra KiCad 10.0.4 real en tres placas open-hardware ajenas al proyecto (`docs/analisis/validation-suite-sintesis-A-B-C.md:16-24`): 13 fp/20 nets, 63 fp/48 nets y 437 fp/380 nets/4 capas. La tercera **no completó** — el techo de escala está medido, no supuesto.

**Madurez: Beta.** El código es de calidad claramente superior a la media de servidores MCP; lo que falta para RC es infraestructura de proyecto (CI, cobertura) y el cierre de dos P0 abiertos, uno de ellos upstream.

---

## 2. Arquitectura

### Diagrama de componentes

```
                    ┌──────────────────────────────────┐
   cliente MCP ────►│  server.py — FastMCP / stdio     │
   (LLM agent)      │  tools/__init__.py: register_all │
                    └───────────────┬──────────────────┘
                                    │ (inyecta 1 IpcBridge singleton)
        ┌───────────┬───────────┬───┴───────┬───────────┬───────────┐
        ▼           ▼           ▼           ▼           ▼           ▼
   tools/meta   tools/world  tools/pcb  tools/validate tools/export tools/sch
     (1 tool)    (2 tools)   (19 tools)   (2 tools)     (4 tools)   (4 tools)
        │           │           │            │             │           │
        │           │           │            │             │           │
        │      ┌────┴───────────┴────┐       │             │           │
        │      │  transversales      │       │             │           │
        │      │  gates/g1 (backup)  │       │             │           │
        │      │  gates/g3 (DRC gate)│◄──────┼─────────────┘           │
        │      │  audit/logger JSONL │       │                         │
        │      │  logging_config     │       │                         │
        │      │  errors.py (F3)     │       │                         │
        │      │  paths.py           │       │                         │
        │      │  snapshots/{store,  │       │                         │
        │      │   validation,delta} │       │                         │
        │      └─────────┬───────────┘       │                         │
        │                │                   │                         │
        └────────┬───────┴───────┐           │                         │
                 ▼               ▼           ▼                         ▼
        ┌─────────────────┐  ┌────────────┐ ┌──────────────┐  ┌───────────────┐
        │ bridge/ipc.py   │  │ bridge/    │ │ bridge/rules │  │ bridge/       │
        │ 2616 LOC        │  │ autoroute  │ │ rules_reader │  │ sch_positions │
        │ kicad-python    │  │ subprocess │ │ kicad_cli    │  │ netlist       │
        │ +threading.Lock │  │ java+pcbnew│ │              │  │ (kicad-skip)  │
        └────────┬────────┘  └─────┬──────┘ └──────┬───────┘  └───────┬───────┘
                 │                 │               │                  │
                 ▼                 ▼               ▼                  ▼
          KiCad IPC socket   freerouting.jar  kicad-cli        .kicad_sch en disco
          (req-reply, 2 s)   /usr/bin/python3  (subprocess)    (mutación directa)
                             (pcbnew SWIG)

        toon/{encoder,schema}  ◄── bridge/state_builder ──► NormalizedState
        (lógica pura, 3 golden)     (cache por mtime)
```

### Fortalezas de diseño

**F1 — Frontera de proceso explícita y disciplinada.** Todo lo que cruza a KiCad pasa por `bridge/`. Los tipos `Nm`/`Mm` (`bridge/ipc.py:47-56`) son distintos para que mypy atrape el bug off-by-10⁶ que CLAUDE.md identifica como el #1 histórico del dominio. No es documentación: `mypy --strict` pasa limpio sobre 33 archivos, así que la garantía es ejecutable.

**F2 — Cola IPC de profundidad 1 real.** `IpcBridge._lock` (`bridge/ipc.py:1268`) es un `threading.Lock` no reentrante que envuelve *toda* llamada IPC. Es la decisión correcta: FastMCP ejecuta tools síncronas (`grep -c "async def" src/kicad_mcp/tools/*.py` → 0 en los 7 archivos) en un thread pool, así que sin ese lock dos tool calls concurrentes pisarían el hilo de UI de KiCad. Está bien identificado y bien resuelto.

**F3 — La separación lectura/mutación es estructural, no convencional.** `_run_supervised_read` (`bridge/ipc.py:1341-1360`) aplica retry por `AS_BUSY` solo a ops en una whitelist, y el `assert op_name in _IDEMPOTENT_OPS` es —cito el docstring— "la **frontera estructural** entre lecturas y mutaciones: no existe otra vía para aplicar retry". Las mutaciones usan `_supervise` directo, que jamás reintenta. Un flag no puede aflojar esto; hay que borrar el assert. Esto es diseño defensivo de nivel senior.

**F4 — Taxonomía de errores como API pública versionada.** `errors.py` es un `StrEnum` de 27 códigos, cada uno documentado en `docs/specs/tool-catalog.md:977-998` con columnas "reintentable" y "acción del hint". El servidor jamás propaga tracebacks.

**F5 — Contratos de persistencia formalizados en ADR.** ADR-0012 (D-23.2) define "cuando `route_board` termina OK, disco == memoria == `err_post` reportado". El contrato existe porque un dogfooding lo rompió (F-D4-02), la investigación está en `docs/investigacion/23-fd4-02.md`, y hay tests canario dedicados (`tests/test_pcb_session32b_refill_silencioso_canary.py`, 470 LOC).

### Debilidades de diseño

**D1 — `tools/pcb.py` es un God module con una God function.**

```
$ uv run ruff check --select C901 --config "lint.mccabe.max-complexity=10" src/
C901 `register` is too complex (146 > 10)          # tools/pcb.py:1003
C901 `register` is too complex (24 > 10)           # tools/sch.py:839
C901 `get_footprint_neighbors` is too complex (22 > 10)
C901 `route_board` is too complex (19 > 10)
```

3 402 LOC en un archivo. `register()` ocupa las líneas 1003-3218 (**2 215 líneas de closures anidados**) porque las 19 tools se definen dentro de ella para capturar `bridge` por closure. Consecuencias medibles: complejidad ciclomática 146, imposibilidad de testear una tool sin construir el servidor entero, y un diff de cualquier tool que toca un archivo de 3 400 líneas. **Opinión arquitectónica:** el closure sobre `bridge` no justifica el costo; un objeto `PcbTools(bridge)` con métodos, o un `functools.partial`, da la misma inyección con archivos de 200-400 líneas.

**D2 — Boilerplate transversal duplicado ~19 veces sin abstracción.** Conteos en `tools/pcb.py`:

| Patrón | Ocurrencias |
|---|---|
| `_audit_error(` | 29 |
| `tool_call_timer()` / `log_tool_call(` | 19 / 19 |
| `_guard_live_stale()` | 15 |
| `audit_record(` | 15 |
| `_check_base_snap(` / `ensure_session_backup(` | 13 / 13 |
| `check_no_external_disk_edit(` | 12 |

El preámbulo de `add_track` (`tools/pcb.py:1261-1268`) —guard, check de disco, root, base_snap, resolve board— se repite casi literal en cada tool de mutación. Un decorador `@mutating_tool` centralizaría el cross-cutting concern y eliminaría la clase de bug "una tool nueva olvidó un guard". Hecho: `check_no_external_disk_edit` aparece 12 veces pero hay 19 tools con timer — la asimetría es intencional (documentada en `snapshots/validation.py:57-70`), pero es exactamente el tipo de asimetría que un decorador haría explícita en vez de implícita.

**D3 — Lógica de dominio dentro del bridge.** `IpcBridge.enforce_hole_clearance` (`bridge/ipc.py:2003-2156`, 154 líneas) calcula geometría de keepouts, lee reglas del proyecto y decide radios de exclusión. Eso es dominio EDA, no transporte. El propio docstring lo admite: "no es una tool propia, es un paso interno del pipeline de fill". Debería vivir en un módulo de dominio que *use* el bridge, no dentro de él. Mismo patrón: `_polygon_area_mm2`, `_circle_vertices_mm`, `_pad_corner_ratio` en `ipc.py:467-676`.

**D4 — Estado mutable global de módulo en tres sitios.**
- `snapshots/store.py:174` — `_default_store = SnapshotStore()`
- `gates/g1.py:29` — `_done_by_project: dict[str, str] = {}`
- `bridge/state_builder.py:27` — `_CACHE: dict[tuple[str, int], NormalizedState] = {}`

ADR-0001 (mono-usuario, stdio) lo hace defendible, y los dos primeros tienen `reset()` para tests. El tercero es un problema real, ver §8/R3.

**Acoplamiento y cohesión.** El acoplamiento entre capas es bajo y unidireccional (`tools → bridge → externo`, `tools → snapshots/gates/audit`); no encontré ciclos de import. La cohesión intra-módulo es el problema: `pcb.py` mezcla geometría computacional pura (`_dist_point_segment`, `_point_in_polygon`, `_rounded_rect_sdf`, líneas 272-900), tres encoders de formato propio, y 19 handlers de tool.

---

## 3. Inventario de herramientas MCP

32 tools, todas verificadas contra `grep -A3 "@mcp.tool" src/kicad_mcp/tools/`. Todas están documentadas en `docs/specs/tool-catalog.md` con parámetros, tipo de salida y códigos de error — **cobertura de catálogo 32/32**. Ninguna es stub; todas ejecutan contra KiCad real.

### `meta` — 1 tool

| Tool | Archivo:línea | Función | Entrada → Salida | Estado | Dependencias | Limitaciones |
|---|---|---|---|---|---|---|
| `health` | `tools/meta.py:145` | Estado del server, socket IPC, `kicad-cli`, proyecto activo | — → JSON | Completa | socket IPC (opcional), `kicad-cli` | No distingue `PROJECT_NOT_CONFIGURED` de `PROJECT_PATH_NOT_FOUND` (`docs/BACKLOG.md:515`, abierto) |

### `world` — 2 tools

| Tool | Archivo:línea | Función | Entrada → Salida | Estado | Dependencias | Limitaciones |
|---|---|---|---|---|---|---|
| `get_world_context` | `tools/world.py:171` | Estado completo en TOON v1 (sch de disco o pcb vivo) | `max_tokens?=800`, `focus_ref?`, `radius_mm?`, `kind?="sch"`, `confirm_reloaded?=false` → TOON | Completa | `kicad-cli` (sch), IPC (pcb) | Falla con `#PWR*`/`#FLG*` en `kind="sch"` (`docs/BACKLOG.md:555`, P3 abierto); multi-hoja → `UNSUPPORTED_HIERARCHY` |
| `get_context_delta` | `tools/world.py:268` | ΔTOON entre `base_snap` y estado actual | `base_snap`, `focus_ref`, `radius_mm`, `max_tokens?` → ΔTOON | Completa | idem | Retención de 10 snapshots (`snapshots/store.py:61`); más viejo → `SNAPSHOT_STALE` |

### `validate` — 2 tools

| Tool | Archivo:línea | Función | Entrada → Salida | Estado | Dependencias | Limitaciones |
|---|---|---|---|---|---|---|
| `run_erc` | `tools/validate.py:206` | ERC del esquemático | `min_severity?=warning` → JSON | Completa | `kicad-cli` | Posiciones divididas ÷100 — bug confirmado 2 veces (`docs/BACKLOG.md:514`, abierto) |
| `run_drc` | `tools/validate.py:224` | DRC presupuestado: resumen por tipo o detalle paginado | `min_severity?`, `exclude_types?`, `detail_type?`, `offset?=0`, `limit?=20` → JSON | Completa | `kicad-cli` | Lee **de disco**: si el board vivo tiene cambios sin guardar, mide estado rancio (regla 8 de CLAUDE.md) |

### `export` — 4 tools

| Tool | Archivo:línea | Función | Entrada → Salida | Estado | Dependencias | Limitaciones |
|---|---|---|---|---|---|---|
| `export_bom` | `tools/export.py:84` | BOM CSV | `output_path?` → JSON | Completa | `kicad-cli` | Sin gate |
| `export_netlist` | `tools/export.py:110` | Netlist del esquemático | `output_path?` → JSON | Completa | `kicad-cli` | Sin gate |
| `export_render` | `tools/export.py:136` | Render `sch_pdf` / `pcb_pdf` / `pcb_png` (3D) | `kind`, `output_path?` → JSON | Completa | `kicad-cli` | `pcb_png` requiere raytracer instalado |
| `export_manufacturing` | `tools/export.py:198` | Gerbers + drill | `output_dir?="fab/"` → JSON | Completa | `kicad-cli`, **Gate G3** | Bloquea con `EXPORT_BLOCKED_BY_DRC` si hay ≥1 violación `error` (`gates/g3.py:36-53`) |

### `pcb` — 19 tools

Todas dependen de KiCad **corriendo** con la API habilitada. Todas las de mutación pasan por Gate G1 (backup + commit git) y por `_guard_live_stale()`.

**Lectura (5)**

| Tool | Archivo:línea | Entrada → Salida | Estado | Limitaciones |
|---|---|---|---|---|
| `get_tracks` | `pcb.py:1845` | `net?`, `bbox?`, `layer?`, `max_tokens?` → formato `TRACKS\|v1` | Completa | IDs (KIID) se invalidan tras cualquier mutación de cobre; complejidad 11 |
| `get_zones` | `pcb.py:2554` | `layer?`, `net?`, `kind?`, `max_tokens?` → `ZONES\|v1` | Completa | Polígonos no rectangulares reportan solo `verts=N`, no coordenadas |
| `get_component_detail` | `pcb.py:2071` | `ref`, `kind?="pcb"` → `DETAIL\|...` | Completa | Posiciones a 1 decimal (deliberado, ahorro de tokens) |
| `get_footprint_neighbors` | `pcb.py:2097` | `ref`, `radius_mm?=5.0`, 5 flags `include_*`, `max_tokens?` → JSON | Completa | **Complejidad 22** |
| `reload_board_from_disk` | `pcb.py:1589` | — → JSON | Completa | Descarta cambios vivos no guardados |

**Mutación de cobre (5)**

| Tool | Archivo:línea | Entrada → Salida | Estado | Limitaciones |
|---|---|---|---|---|
| `add_track` | `pcb.py:1246` | `net`, coords y/o `from_pad`/`to_pad` (`REF.PAD`), `width_mm?=0.25`, `layer?="F.Cu"`, `base_snap?` → confirm | Completa | **No persiste a disco**; valida colisión con pads y `NET_ASSIGNMENT_MISMATCH` |
| `add_via` | `pcb.py:1424` | `x_mm`, `y_mm`, `net`, `size_mm?=0.8`, `drill_mm?=0.4` → confirm | Completa | Toma el net del cobre físico bajo la vía, no del caché |
| `delete_track` | `pcb.py:1799` | `id?` o `(net, near_x_mm, near_y_mm)` → confirm | Completa | Sin Gate G2 por decisión explícita (ADR-0010) |
| `delete_via` | `pcb.py:1822` | `id?` o `(net, x_mm, y_mm)` → confirm | Completa | idem |
| `delete_tracks_bulk` | `pcb.py:1936` | `net?`, `bbox?`, `layer?`, `include_vias?`, `dry_run?` → JSON | Completa | **Refillea en memoria pero no persiste ni re-verifica hole clearance** — `A1` en `docs/analisis/auditoria-contratos-bridge.md §5.2`, P1 agendado. Complejidad 13 |

**Zonas (4)**

| Tool | Archivo:línea | Entrada → Salida | Estado | Limitaciones |
|---|---|---|---|---|
| `add_zone` | `pcb.py:2344` | `net`, `layer`, `bbox?`/`polygon?`, `priority?=0`, `fill?=true` → JSON | Completa | **`fill=true` crashea KiCad en la 3ª-4ª llamada sobre boards grandes** — P0 abierto, causa no concluyente (`docs/BACKLOG.md:16`). Con `fill=true` cumple D-23.2 |
| `add_keepout_zone` | `pcb.py:2472` | `layer`(o `"all"`), `bbox?`/`polygon?`, 4 flags `no_*` → JSON | Completa | No recalcula fills de zonas vecinas (`A3`) |
| `fill_zones` | `pcb.py:2634` | `zone_id?`, `base_snap?` → JSON | Completa | `zone_id` solo valida existencia: kipy **no tiene fill selectivo**, refillea todo |
| `delete_zone` | `pcb.py:2733` | `id`, `base_snap?` → confirm | Completa | No recalcula fills vecinos (`A2`) |

**Colocación / estructura / persistencia (5)**

| Tool | Archivo:línea | Entrada → Salida | Estado | Limitaciones |
|---|---|---|---|---|
| `move_footprint` | `pcb.py:1009` | `ref`, `x_mm`, `y_mm`, `base_snap?` → confirm | Completa | **No dispara refill**: un DRC posterior mide fill rancio (`docs/BACKLOG.md:520`) |
| `set_footprint_ref` | `pcb.py:1118` | `ref`, `new_ref`, `kiid?`, `base_snap?` → confirm | Completa | Solo opera sobre refs duplicados (ADR-0013); sin cascada a tracks/zonas |
| `draw_board_outline` | `pcb.py:2249` | `x_mm`, `y_mm`, `width_mm`, `height_mm` → confirm | Completa | Solo rectángulos; inmutable, sin `replace=true` (`docs/BACKLOG.md:516`) |
| `save_board` | `pcb.py:1543` | `base_snap?` → confirm | Completa | Bloqueado por `live_stale` |
| `route_board` | `pcb.py:2788` | `max_passes?`, `timeout_s?=600`, `refill?=true` → JSON | Completa | Ver abajo |

`route_board` merece detalle: es la tool más compleja (**19**, 428 líneas) y la única con pipeline multi-etapa — save implícito → pre-check `DUPLICATE_REFS` → DRC pre → export DSN (`pcbnew` del python del **sistema**, no del venv) → `java -jar freerouting` → import SES → `os.replace` atómico → recarga del vivo → refill + `enforce_hole_clearance` → stitching de pads huérfanos → DRC post → save. Depende de `KICAD_MCP_FREEROUTING_JAR`, Java ≥17, `pcbnew` SWIG en `/usr/bin/python3`, y KiCad corriendo. Limitaciones: Freerouting 2.1.0 entra en crash-loop en boards grandes (P0 upstream, `docs/BACKLOG.md:83`); no respeta el plano GND como exclusión para nets ajenos (D-19.1); el sub-patrón `F-D5-01-B` de estrangulamiento lateral sigue abierto.

### `sch` — 4 tools

Arquitectura **distinta**: KiCad 10 no expone API de esquemático, así que estas mutan el `.kicad_sch` en disco vía `kicad-skip`. Todas son **puramente aditivas**.

| Tool | Archivo:línea | Entrada → Salida | Estado | Limitaciones |
|---|---|---|---|---|
| `add_symbol` | `sch.py:842` | `sheet`, `lib_id`, `ref`, `x_mm`, `y_mm`, `source?` → confirm | Completa | Clona de la hoja o de una paleta; requiere protocolo de `docs/guias/guia-paleta.md` |
| `set_value` | `sch.py:1063` | `ref`, `value` → confirm | Completa | — |
| `set_footprint` | `sch.py:1104` | `ref`, `footprint_id` → confirm | Completa | — |
| `connect_pins` | `sch.py:1153` | `pin_a`, `pin_b`, `net_name` → confirm | Completa | Conecta por labels locales homónimos, no por wires; sin `delete_wire`, un agente puede construir pero no limpiar |

**Riesgo transversal de la categoría:** escritura directa al archivo mientras el editor de KiCad lo tiene abierto → pérdida de datos. Documentado en `docs/guias/guia-paleta.md`, **no forzado por código**.

### No implementado pese a estar declarado

`gates/` contiene solo `g1.py` y `g3.py`. **G2** (borrado destructivo, interactivo) y **G4** (presupuesto de sesión) están en ADR-0003:22,24 pero no existen; `GATE_DENIED` y `BUDGET_EXCEEDED` (`errors.py:37-38`) son códigos muertos — `grep -rn` no encuentra ningún emisor. G2 tiene carve-out explícito para cobre (ADR-0010), pero no para footprints/zonas: el resultado es que `delete_zone` borra sin gate ni confirmación.

---

## 4. Capacidades actuales

- **PCB / colocación:** mover footprints, renombrar refs duplicados, contorno rectangular Edge.Cuts, detalle de footprint con pads absolutos y courtyard, vecindario en radio con distancia al borde.
- **Cobre:** crear/borrar tracks (punto↔punto, pad↔pad, mixto) y vías; borrado masivo por filtro con `dry_run`; validación de colisión pad-track por SDF de rectángulo redondeado (`pcb.py:842-930`) y verificación de net real post-creación con revert (`ipc.py:1071`).
- **Zonas:** zonas de cobre por bbox o polígono con validación de geometría (auto-intersección, `pcb.py:715-795`), keepouts con 4 flags, refill global, protección automática de agujeros ajenos (`enforce_hole_clearance`).
- **Routing:** autorouting headless completo con Freerouting; inyección de `edge_clearance` en el DSN (`autoroute.py:365`); clasificación por net del resultado desde DSN/SES en vez del DRC; stitching automático de pads GND huérfanos bajo 5 guardrails geométricos.
- **DRC/ERC:** ambos presupuestados y paginados; gate G3 automático sobre export de fabricación.
- **Exportación:** gerbers+drill, BOM CSV, netlist, PDF de sch/pcb, PNG 3D.
- **Gestión de contexto (el diferenciador real):** encoder TOON con 3 niveles de degradación por presupuesto, delta incremental, foco por ref+radio, colapso de nets de poder, estimador de tokens con factor de seguridad 0,9 (`toon/encoder.py:40-44`), y `max_tokens` en las tools de listado.
- **Integridad y trazabilidad:** snapshots monotónicos con retención 10, detección de edición externa por mtime en dos capas independientes (`validate_base_snap` + `check_no_external_disk_edit`), detección de reinicio de KiCad por `KICAD_API_TOKEN`, backup + commit git automático pre-mutación, audit JSONL de toda mutación aceptada **y rechazada**, logging JSON estructurado por tool call.
- **Agentes:** no hay orquestación de agentes en el proyecto — es un servidor, no un framework. Correcto.

---

## 5. Limitaciones

### Técnicas
- **Crítica** — `add_zone(fill=true)` crashea KiCad reproduciblemente en la 3ª-4ª llamada sobre boards grandes; causa no aislada tras la auditoría 34a (`docs/BACKLOG.md:16`). Workaround documentado: `fill_zones()` una vez al final.
- **Crítica** — Freerouting 2.1.0 crash-loop en boards grandes (437 fp): 3 600 s sin progreso. Upstream, pero es el techo funcional del producto.
- **Menor** — `run_erc` divide posiciones ÷100 (confirmado 2 veces, `docs/BACKLOG.md:514`).
- **Menor** — netclasses: `diff_pair_width`/`diff_pair_gap`/`diff_pair_via_gap` se descartan en silencio (`bridge/rules_reader.py:217`). No se puede dirigir el ruteo de un par diferencial.

### Arquitectónicas
- **Crítica** — G2 y G4 declarados en ADR-0003 (frontera F2) y sin implementar. `delete_zone` borra una zona de cobre sin gate ni confirmación; no hay techo de presupuesto de sesión.
- **Menor** — Mutación de esquemático por archivo mientras KiCad puede tenerlo abierto: hazard real mitigado solo por documentación.
- **Menor** — Esquemáticos multi-hoja fuera de alcance (`UNSUPPORTED_HIERARCHY`).

### Funcionales
- **Crítica** — Sin `delete_footprint`: asimetría deliberada (ADR-0010/0013) pero significa que un agente no puede deshacer una colocación errónea.
- **Menor** — Tools de esquemático puramente aditivas: sin `delete_wire`, `delete_symbol`.
- **Menor** — `draw_board_outline` solo rectángulos y no reemplazable.

### UX
- **Menor** — La mayoría de tools de escritura **no guardan a disco**; el agente debe saber llamar `save_board()`. Solo `route_board`, `fill_zones` y `add_zone(fill=true)` garantizan disco==memoria (ADR-0012). Documentado con honestidad en README, pero es una trampa de diseño para un LLM.
- **Menor** — Requiere 4 variables de entorno y una opción de preferencias de KiCad activada manualmente.

### Rendimiento
- **Crítica** — Un autoruteo completo excede el timeout de idle de clientes MCP (~1 818 s observados). Workaround: proceso desacoplado.
- **Menor** — Cola IPC de profundidad 1: cero paralelismo entre tool calls por diseño (correcto, pero es un techo duro).

### Seguridad
- **Menor** (contexto mono-usuario) — Tres encoders sin sanitización; ver §8/R2.
- **Menor** — Escritura fuera de la raíz del proyecto en `~/.config/freerouting/freerouting.json`; ver §8/R5.
- El vector de path traversal está bien cerrado: `canonicalize_within_project_root` (`paths.py:14-33`) resuelve y verifica contención, y el error nunca revela la ruta canónica.

### Portabilidad
- **Crítica para adopción** — Prácticamente Linux-only (ADR-0005). `_SYSTEM_PYTHON_DEFAULT = "/usr/bin/python3"` hardcodeado (`autoroute.py:57`, overridable por env), hints con `pacman` (`autoroute.py:640`), rutas de socket `/tmp/kicad`.

### Escalabilidad
- **Crítica** — Techo medido en 63 fp / 48 nets / 2 capas para el flujo completo. A 437 fp / 4 capas el autorouter no completa. Es el límite honesto del producto hoy.

---

## 6. Comparación con otros MCP

**Advertencia de verificabilidad:** no tengo acceso a la red en esta auditoría, así que la comparación se basa en conocimiento del ecosistema MCP hasta mayo de 2026, no en inspección de repos. Los números de kicad-mcp son verificados; los ajenos son de memoria y deben confirmarse antes de citarse.

**Existe al menos un `kicad-mcp` homónimo de terceros** (típicamente Python + parseo de archivos `.kicad_pcb`/`.kicad_sch` y wrappers de `kicad-cli`). La diferencia estructural es la vía de acceso: ese enfoque lee y edita archivos; este usa la **API IPC nativa de KiCad** para PCB y reserva la edición de archivos solo para esquemático, donde KiCad 10 no ofrece API. Consecuencia práctica: este proyecto opera sobre el board **vivo** que el usuario tiene abierto, con el costo de la coordinación disco/memoria que domina su ADR-0012 y su backlog.

**Qué hace mejor que lo que conozco del espacio EDA/CAD MCP:**
1. **Economía de contexto como primitiva de diseño**, no como afterthought. TOON con degradación en 3 niveles, delta incremental, foco por radio, `max_tokens` en cada listado, y un estimador de tokens con margen. La mayoría de MCP servers devuelven JSON crudo y dejan que el cliente pague.
2. **Taxonomía de errores accionable versionada como contrato.** 27 códigos, cada uno con hint accionable (sugerencias por edit-distance: `_similars`, `pcb.py:103`) y columna de "reintentable". La media del ecosistema devuelve strings.
3. **Trazabilidad de decisiones.** 14 ADRs, 7 investigaciones de causa raíz, un backlog de 700+ líneas con evidencia por hallazgo. Es raro incluso en proyectos comerciales.
4. **Validación contra ground truth real.** Tres placas open-hardware ajenas comparadas contra la PCB que su autor fabricó, con umbrales cuantitativos (±30% tracks, ±20% vías, ±25% cobre). No conozco otro MCP server con nada equivalente.
5. **Gates de seguridad automáticos** (backup + commit git antes de la primera mutación).

**Qué hace peor:**
1. **Sin CI.** No existe `.github/`. Un MCP server comparable de nivel producción tiene al menos lint+tests en PR.
2. **Sin cobertura medida.** `coverage` ni siquiera está instalado (`ModuleNotFoundError`).
3. **Sin paquete distribuible.** No hay publicación en PyPI ni imagen; la instalación es `git clone` + `uv sync` + 4 env vars + toggle manual en preferencias de KiCad.
4. **Superficie de plataforma mínima** (Linux, KiCad 10.0.4) frente a alternativas que parsean archivos y corren en cualquier lado.
5. **Idioma mixto:** código y docs internas en español, README/CONTRIBUTING en inglés. Reduce el pool de colaboradores para un proyecto que apunta a open source.

**Frente a los MCP oficiales de Anthropic** (filesystem, git, fetch): no son comparables en dominio. Sí lo son en madurez de empaquetado, donde kicad-mcp está claramente por detrás (aquellos son instalables en un comando), y en profundidad de contrato, donde kicad-mcp está por delante.

---

## 7. Calidad del código

**Stack de calidad presente:** `ruff` (lint `E,F,W,I,UP,B,SIM,RUF` + format, line-length 100), `mypy --strict`, `pytest` con 5 marcas semánticas, `uv` con `uv.lock` commiteado. Todo declarado en `pyproject.toml:32-54`.

**Stack de calidad ausente:** CI, pre-commit hooks, cobertura, security scanning, dependabot.

| Dimensión | Evaluación | Evidencia |
|---|---|---|
| Organización | Buena a nivel paquete, mala a nivel archivo | 8 subpaquetes con responsabilidad clara; `pcb.py` 3 402 LOC |
| Legibilidad | Muy alta | Nombres explícitos, funciones pequeñas fuera de `register()` |
| Documentación en código | **Excepcional** | Cada docstring explica el *porqué* y cita la sesión/ADR/investigación donde se decidió. `ipc.py:1341-1350` es el ejemplo canónico |
| Convenciones | Excelentes | ruff limpio, formatter limpio, `mypy --strict` limpio en 33 archivos |
| Type hints | Completos y semánticos | `Nm`/`Mm` distintos; `Protocol` para inyección (`gates/g3.py:23`, `autoroute.py:145`, `ipc.py:856`) |
| Complejidad | Un outlier severo, resto aceptable | 10 funciones >10; `register` de `pcb.py` = **146** |
| Duplicación | Alta en el preámbulo de tools | §2/D2 |
| Testing | Volumen alto, distribución desbalanceada | 381 `@pytest.mark.unit`, 30 `integration_gui`, 22 `integration`, 9 `integration_gui_slow`, **4 `golden`** |
| Cobertura | **No medida** | `coverage` no instalado; CLAUDE.md afirma ">90%" para `toon/` sin instrumento que lo verifique |
| Manejo de errores | **Ejemplar** | Ver abajo |

**Manejo de errores — el punto más fuerte.** `grep -rn "except Exception" src/` devuelve 5 ocurrencias; las tres de `autoroute.py:81,93,114` están **dentro de scripts Python embebidos como string** para ejecutar con el intérprete del sistema, no en el servidor. Las dos reales son deliberadas y re-lanzan:

```python
# bridge/ipc.py:1064-1069
    try:
        return list(raw_board.get_items_by_id(kiids))
    except Exception as exc:
        if _is_kipy_not_found_error(exc):
            return []
        raise                      # ← cualquier otro fallo se propaga intacto
```

```python
# bridge/ipc.py:1331-1339
        except KicadMcpError:
            raise
        except BaseException as exc:
            mapped = _map_ipc_failure(op_name, exc)
            if not _is_busy(mapped):
                self._client = None
            raise mapped from exc
```

Cero `except: pass`. Cero tracebacks al agente. Esto está por encima del estándar de la industria.

**Testing — dos observaciones.** (a) Solo **4 tests golden** sobre 3 casos (`tests/golden/00{1,2,3}_*`) para un formato declarado contrato inviolable (F1) especificado en 184 líneas. Es cobertura fina para la superficie: degradación de 3 niveles, colapso de nets de poder, foco por radio, cabecera de PCB, delta. (b) 30 tests `integration_gui` requieren un humano con KiCad abierto siguiendo `docs/guias/pruebas-gui.md` — imposible de automatizar por la API de KiCad, honestamente documentado, pero significa que **el 8% de la suite solo corre cuando alguien se acuerda**.

**Documentación de proyecto.** README de 195 líneas cuya sección *Known limitations* lidera con los fallos y enlaza la sesión donde se encontró cada uno — es el README más honesto que he revisado en este tipo de proyecto. `CONTRIBUTING.md` (235 líneas) incluye "los 4 ejes de contrato de toda write tool" y un checklist para añadir una tool nueva. `docs/BACKLOG.md` tiene calidad de issue tracker.

**Drift documental medido** (`CLAUDE.md`, el archivo que gobierna a los agentes que trabajan en el repo):
- `CLAUDE.md:11,132,170,175` apunta a `CONTEXT.md` en la raíz → **no existe**; está en `docs/CONTEXT.md` y su versión histórica en `docs/historico/CONTEXT-v7.md`.
- `CLAUDE.md:146,169` apunta a `hoja-de-ruta-v4.md` → **no existe**; la vigente es `hoja-de-ruta-v5.md` (Fase 4) y la v4 está archivada.
- `CLAUDE.md:26` describe `snapshots/` como "cache de estado + **índice espacial** + **invalidator** + mtime store". `ls src/kicad_mcp/snapshots/` → `delta.py`, `store.py`, `validation.py`. `grep -rni "spatial\|rtree\|quadtree\|invalidator" src/` no encuentra implementación. **No existe índice espacial ni invalidator.**
- `CLAUDE.md:175` fecha la fase actual el 2026-07-23 y dice "Fase 3"; el roadmap vigente arranca Fase 4 post-sesión 29.

Los enlaces del README, en cambio, resuelven todos (verificado con script sobre los 15 enlaces `.md`).

**Inconsistencia menor:** `README.es.md` tiene 94 líneas contra 195 del inglés — la traducción no cubre *Known limitations*, que es justamente la sección que el README declara prioritaria.

---

## 8. Riesgos

| # | Riesgo | Ubicación | Impacto | Prob. | Prio | Mitigación |
|---|---|---|---|---|---|---|
| R1 | **Sin CI.** Nada impide mergear con tests rojos, ruff sucio o mypy roto. La Definition of Done es una convención escrita, no un gate ejecutable. Toda la garantía depende de que un humano corra 3 comandos | ausencia de `.github/` | Alto | Alta | **P0** | GitHub Actions: `uv sync` + `ruff check` + `ruff format --check` + `mypy src/` + `pytest -m "not integration"` en push/PR. Existe `scripts/verificar_entorno.py` (804 LOC) que ya modela los checks — reutilizarlo |
| R2 | **Tres encoders emiten texto no sanitizado al LLM.** `_encode_tracks`, `_encode_zones` y `_encode_component_detail` interpolan `net_name`, `ref` y `pad.number` crudos en un formato delimitado por espacios y `\|`. El pipeline TOON sí sanitiza (`toon/encoder.py:87`, `_STRUCTURAL_CHARS` mapea `> \| :` y regex de control chars) — estos tres no. Viola la regla 6 de CLAUDE.md. **Verificado:** ninguna de las 1 032 nets distintas en las placas reales del repo contiene un delimitador, así que es latente, no observado | `tools/pcb.py:809-840`, `3263-3296`, `3314-3366` | Medio | Media | **P1** | Reusar `toon.encoder._sanitize` en los tres. ~15 líneas |
| R3 | **Fuga de memoria en el cache de estado.** `_CACHE: dict[tuple[str, int], NormalizedState]` está indexado por `(path, mtime_ns)` y **nunca evicta**. Cada guardado del esquemático crea un mtime nuevo → una entrada nueva. Un servidor de sesión larga acumula un `NormalizedState` completo por save. Contrasta con `SnapshotStore`, que sí tiene `retention=10` | `bridge/state_builder.py:27` (declaración), `:114` (inserción sin bound) | Medio | Media | **P1** | `OrderedDict` + retención, o cachear solo el último mtime por path |
| R4 | **G2 y G4 declarados y no implementados.** ADR-0003 los define bajo frontera F2 ("los gates existen para ser inviolables desde prompts"). `GATE_DENIED` y `BUDGET_EXCEEDED` no tienen emisor. `delete_zone` borra cobre sin gate ni confirmación | `gates/` (solo `g1.py`, `g3.py`); `errors.py:37-38` | Medio | Media | **P1** | Decidir explícitamente: implementar G2/G4, o emitir un ADR que los retire y marcar los códigos como reservados (como ya hace `tool-catalog.md:929` con nombres de tools futuras) |
| R5 | **Escritura silenciosa fuera de la raíz del proyecto.** `_ensure_freerouting_headless_config` reescribe `~/.config/freerouting/freerouting.json` y `/tmp/freerouting/freerouting.json` del usuario sin avisar, saltándose `canonicalize_within_project_root`. Justificado (con `gui.enabled=true` la JVM cuelga) y documentado en el docstring, pero es un side effect global no consentido. El candidato en `/tmp` añade una ventana TOCTOU menor en máquinas multiusuario | `bridge/autoroute.py:569-605` | Bajo | Alta | **P2** | Loguear una línea JSON cuando se modifique; o pasar la config por `-cfg`/system property en vez de mutar la del usuario |
| R6 | **`hint` con texto crudo de excepción/subproceso.** `errors.py:8-11` promete que un error "jamás incluye tracebacks, rutas absolutas del sistema ni texto sin sanear". Tres sitios lo incumplen: `str(exc)[:200]` de `kicad-skip` (`tools/sch.py:161`), de kipy (`bridge/ipc.py:1020`), y 600 chars de stdout+stderr de Freerouting (`autoroute.py:663`) — que rutinariamente contienen rutas absolutas. Mismo patrón en `gates/g1.py:84` con stderr de git | 4 sitios | Bajo | Alta | **P2** | Un `_scrub_paths()` compartido que reemplace prefijos absolutos por `<project>/` antes de truncar |
| R7 | **Techo de escala del autorouter.** El producto no completa el flujo sobre boards de 437 fp / 4 capas | upstream Freerouting 2.1.0 | Alto | Alta (en boards grandes) | **P2** | Ya mitigado por transparencia (README lo lidera). Abrir issue upstream; evaluar ruteo por regiones |
| R8 | **La marca `integration_gui_slow` no está en el filtro por defecto.** `addopts = "-m 'not integration and not integration_gui'"` no excluye `integration_gui_slow` (nombre distinto). Verificado: `pytest --collect-only` colecta 403/462 e incluye los 9 tests slow; el comando documentado en CLAUDE.md `pytest -m "not integration"` también. **No es explotable hoy** porque cada test tiene un guard de runtime que exige `KICAD_MCP_GUI_TEST=1` (`tests/test_route_board_gui_slow.py:72-84`) — pero el filtro de marcas y el guard dicen cosas distintas | `pyproject.toml:33` | Bajo | Baja | **P3** | `-m 'not integration and not integration_gui and not integration_gui_slow'` |
| R9 | **`CLAUDE.md` apunta a archivos inexistentes.** Es el documento que orienta a los agentes que desarrollan el repo; 3 referencias rotas y una descripción de estructura falsa (§7) | `CLAUDE.md:11,26,132,146,169,175` | Bajo | Alta | **P3** | Corregir rutas; borrar "índice espacial + invalidator" de la descripción de `snapshots/` |

---

## 9. Deuda técnica

| # | Deuda | Ubicación | Esfuerzo |
|---|---|---|---|
| DT1 | **`register()` de 2 215 líneas con complejidad 146.** 19 tools como closures anidados en una función. Bloquea el testing unitario por tool y hace ilegible cualquier diff | `tools/pcb.py:1003-3218` | **XL** |
| DT2 | **Boilerplate transversal ×19 sin decorador.** guard + check de disco + base_snap + G1 + audit + timer + log repetidos a mano en cada tool de mutación. Riesgo estructural: una tool nueva olvida un guard y nada lo detecta | `tools/pcb.py` (conteos en §2/D2) | **M** |
| DT3 | **Geometría y dominio EDA dentro del bridge.** `enforce_hole_clearance` (154 líneas), `_polygon_area_mm2`, `_circle_vertices_mm`, `_pad_corner_ratio` viven en la capa de transporte | `bridge/ipc.py:467-676`, `2003-2156` | **L** |
| DT4 | **Tres formatos de serialización ad-hoc sin spec ni golden.** `TRACKS\|v1`, `ZONES\|v1`, `DETAIL\|...` son contratos que un LLM parsea, deliberadamente fuera de F1 para no tocar el spec TOON. El costo: sin golden, sin sanitización (R2), y un cambio de formato no rompe ningún test | `tools/pcb.py:809`, `3263`, `3314` | **M** |
| DT5 | **`get_footprint_neighbors` con complejidad 22.** 149 líneas, 6 flags booleanos, presupuesto de tokens y 4 tipos de vecino en una función | `tools/pcb.py:2103-2248` | **M** |
| DT6 | **Cobertura no instrumentada.** Sin `pytest-cov`, la afirmación ">90%" de `toon/` en CLAUDE.md:19 no es verificable. Requiere aprobación F5 para la dependencia | `pyproject.toml:14-20` | **S** |
| DT7 | **`register()` de `sch.py` con complejidad 24** — mismo antipatrón que DT1 a menor escala | `tools/sch.py:839` | **M** |
| DT8 | **Drift documental de CLAUDE.md** (R9) | `CLAUDE.md` | **S** |
| DT9 | **`README.es.md` desincronizado** (94 vs 195 líneas; falta *Known limitations*) | `README.es.md` | **S** |
| DT10 | **Cuello de botella medido y aceptado:** cola IPC de profundidad 1 + timeout duro de 2 s. Correcto por diseño, pero fija el techo de throughput y hace que `route_board` (subproceso, minutos) sea la única vía para trabajo pesado | `bridge/ipc.py:1268` | — (no accionable) |

---

## 10. Funcionalidades faltantes

Medidas contra el objetivo declarado del proyecto — "un agente LLM opera KiCad autónomamente" — y contra la ambición de Fase 4, "proyecto Open Source de alta calidad" (`hoja-de-ruta-v5.md:24-27`).

**P0**
1. **CI.** Sin ella no hay "alta calidad" verificable por un colaborador externo. Es el mayor gap frente al objetivo declarado.
2. **Cierre o clasificación firme de `F-V3-ZONE-FILL-CRASH`.** Un crash reproducible de KiCad disparado por una tool es incompatible con un release público, aunque la causa sea de pcbnew.

**P1**
3. **`delete_footprint`** (o una decisión formal y definitiva de no tenerlo). Sin él, el loop de colocación no es reversible desde las tools; `docs/BACKLOG.md:517` lleva registrada la asimetría desde D-R3 sin ADR propio.
4. **Persistencia consistente entre write tools.** Hoy 3 de ~19 garantizan disco==memoria. Un agente tiene que memorizar cuáles. Generalizar D-23.2 o exponer un flag `persist` uniforme.
5. **G2 y G4, o el ADR que los retire.**
6. **Cierre de `A1`/`A2`/`A3`** (`delete_tracks_bulk`, `delete_zone`, `add_keepout_zone` no recomputan fills vecinos).

**P2**
7. **Paquete instalable** (PyPI o contenedor) — hoy la instalación es artesanal.
8. **Contorno de placa no rectangular** y `draw_board_outline(replace=true)`.
9. **Soporte de netclasses para pares diferenciales** (`rules_reader.py:217`).
10. **Fix de posiciones ÷100 en `run_erc`.**

**P3**
11. **CRUD de esquemático** (`delete_wire`, `delete_symbol`) — ya en backlog como P3.
12. **Esquemáticos jerárquicos multi-hoja.**
13. **Soporte macOS/Windows.**

---

## 11. Roadmap recomendado

### Corto plazo (0–4 semanas)

| # | Acción | Impacto | Esfuerzo | Depende de |
|---|---|---|---|---|
| C1 | **CI en GitHub Actions**: `ruff check` + `ruff format --check` + `mypy src/` + `pytest -m "not integration"` | Convierte la Definition of Done en gate ejecutable. Prerrequisito de cualquier colaboración externa | S | — |
| C2 | **Sanitizar los 3 encoders ad-hoc** reusando `toon.encoder._sanitize` + un golden por formato | Cierra R2 y arranca DT4 | S | — |
| C3 | **Acotar `_CACHE`** de `state_builder` con `OrderedDict` + retención | Cierra R3 | S | — |
| C4 | **Corregir el drift de `CLAUDE.md`** (rutas rotas + descripción falsa de `snapshots/`) y sincronizar `README.es.md` | El archivo que gobierna a los agentes deja de mentirles | S | — |
| C5 | **`_scrub_paths()` compartido** para los 4 sitios que filtran rutas absolutas en `hint` | Cierra R6, honra el contrato de `errors.py` | S | — |
| C6 | **Añadir `pytest-cov`** (requiere aprobación F5) y publicar la cobertura real | Vuelve auditable la afirmación ">90%" | S | C1 |
| C7 | **Arreglar el filtro de `integration_gui_slow`** en `addopts` | Cierra R8 | S | — |

### Mediano plazo (1–3 meses)

| # | Acción | Impacto | Esfuerzo | Depende de |
|---|---|---|---|---|
| M1 | **Extraer `@mutating_tool`** — decorador con guard + disk check + base_snap + G1 + audit + timer + log | Elimina la clase de bug "tool nueva sin guard"; recorta varios cientos de líneas | M | C1 |
| M2 | **Partir `tools/pcb.py`** en `pcb/{copper,zones,placement,routing,geometry,encoders}.py`; convertir `register()` en un despacho fino | Ataca DT1, el mayor obstáculo de mantenibilidad | L | M1 |
| M3 | **Mover `enforce_hole_clearance` y la geometría a un módulo de dominio** que consuma el bridge | Cierra DT3, restaura la separación de capas | L | M2 |
| M4 | **Cerrar `F-V3-ZONE-FILL-CRASH`** — reproducir en harness aislado o reclasificar con evidencia | Desbloquea el release público | L | — |
| M5 | **Cerrar `A1`/`A2`/`A3`** y unificar el contrato de persistencia | Un agente deja de necesitar una tabla mental de qué persiste | M | M1 |
| M6 | **Ampliar los golden de TOON** a los 3 niveles de degradación, colapso de poder, foco por radio y cabecera de PCB | El contrato F1 pasa de 3 casos a cobertura de superficie | M | — |
| M7 | **Empaquetar** (PyPI + instrucciones de registro en clientes MCP) | Baja la barrera de adopción de "artesanal" a un comando | M | C1 |

### Largo plazo (3–12 meses)

| # | Acción | Impacto | Esfuerzo | Depende de |
|---|---|---|---|---|
| L1 | **Decidir G2/G4** — implementar o retirar por ADR | Restaura la coherencia de la frontera F2 | M | M1 |
| L2 | **`delete_footprint` con G2**, o ADR definitivo que lo cierre | Cierra el loop de colocación reversible | M | L1 |
| L3 | **Estrategia frente al techo del autorouter**: ruteo por regiones, o evaluar alternativas a Freerouting | Sube el techo de 63 fp; la limitación #1 del producto | XL | M4 |
| L4 | **CRUD de esquemático + jerárquicos** | Cierra la asimetría sch/pcb | XL | L2 |
| L5 | **Portabilidad macOS/Windows** | Multiplica el mercado potencial; solo justificable con demanda real (criterio del propio roadmap) | L | M7 |
| L6 | **Automatizar parte de los 30 tests `integration_gui`** con KiCad en un display virtual | Recupera el 8% de la suite hoy dependiente de un humano | L | C1 |

---

## 12. Nivel de madurez

### **Beta**

**A favor de Beta (y no Alpha):** el flujo completo está cerrado y validado contra KiCad real en tres placas ajenas al proyecto con umbrales cuantitativos; 394 tests offline verdes; `mypy --strict` y `ruff` limpios; 32 tools documentadas 32/32 en un catálogo con taxonomía de errores; contratos formalizados en 14 ADRs; licencia Apache-2.0, NOTICE, CONTRIBUTING y README público presentes.

**En contra de Release Candidate:** dos P0 abiertos (uno de ellos un crash de KiCad disparado por una tool); sin CI; sin cobertura medida; sin paquete distribuible; el 8% de la suite requiere intervención humana; gates declarados bajo frontera "inviolable" que no existen en el código; y el techo de escala está en 63 footprints, con evidencia de que a 437 no funciona.

### Puntuación

| Dimensión | Nota | Justificación en una frase |
|---|---|---|
| Arquitectura | **7,5** | Fronteras de proceso y separación lectura/mutación excelentes, arruinadas parcialmente por un `register()` de 2 215 líneas con complejidad 146 y dominio EDA metido dentro del bridge. |
| Calidad del código | **8,5** | `mypy --strict` limpio, ruff limpio, cero `except: pass`, docstrings que explican el porqué y citan la investigación que lo motivó — descuenta solo la duplicación transversal ×19. |
| Escalabilidad | **4** | El techo está medido, no supuesto: 63 footprints funciona, 437 no completa, y la cola IPC de profundidad 1 fija el throughput por diseño. |
| Robustez | **8** | Backups automáticos, detección de edición externa en dos capas independientes, revert de nets mal asignados, reemplazo atómico del `.kicad_pcb` — con dos P0 abiertos que impiden una nota mayor. |
| Mantenibilidad | **6,5** | El sistema de ADRs e investigaciones es de primer nivel, pero un archivo de 3 402 líneas y boilerplate repetido 19 veces castigan el día a día. |
| Documentación | **9** | 132 documentos, 14 ADRs, un README que lidera con sus fallos y un backlog con calidad de issue tracker; pierde un punto por el drift de `CLAUDE.md` y la traducción a medias. |
| Innovación | **9** | TOON con degradación por presupuesto, delta incremental y hints por edit-distance son una respuesta genuinamente original al problema de economía de contexto en MCP. |
| Usabilidad | **5,5** | Requiere Linux, KiCad 10.0.4, 4 env vars, un toggle manual de preferencias y saber qué tools persisten y cuáles no. |
| Preparación para producción | **5** | El código está listo; el proyecto no: sin CI, sin cobertura, sin paquete y con dos P0 abiertos. |

**Media: 7,0**

---

## 13. Análisis crítico

### Decisiones acertadas

**Tipos distintos para nanómetros y milímetros.** `Nm`/`Mm` (`ipc.py:47-56`) con `mypy --strict` convierte el bug histórico #1 del dominio en un error de compilación. Es la clase de decisión que parece trivial y evita meses de depuración.

**El `assert` de `_IDEMPOTENT_OPS` como frontera estructural.** No es una convención ni un comentario: es imposible aplicar retry a una mutación sin borrar código explícitamente. La mayoría de los proyectos habrían usado un flag `retryable=True` y habrían acabado reintentando una escritura.

**El backlog y los ADRs como parte del repo.** `docs/BACKLOG.md` documenta cada hallazgo con la sesión, la placa, el síntoma exacto y el estado. `docs/investigacion/` guarda 7 reportes de causa raíz. Esto hace que un colaborador nuevo pueda entender no solo *qué* hace el código sino *qué se intentó y falló*. Es superior a lo que veo en la mayoría de proyectos comerciales.

**La Validation Suite.** Comparar contra la PCB que el autor original fabricó, con umbrales numéricos, y publicar que 1/4, 3/4 y 0/4 criterios se cumplieron por nivel — incluyendo el fracaso — es metodología de ingeniería, no de demo.

**El README.** Es honesto de una forma que perjudica al marketing y beneficia al usuario. La sección *Known limitations* precede a la de documentación y enlaza la sesión donde se encontró cada límite.

### Decisiones equivocadas

**El closure gigante.** Definir 19 tools dentro de `register()` para capturar `bridge` por closure fue barato al principio y hoy cuesta 2 215 líneas indivisibles con complejidad 146. Un `PcbTools(bridge)` con métodos daba la misma inyección. Esta decisión ya no es reversible barata: es el XL de la lista de deuda.

**Tres formatos de serialización nuevos para esquivar la frontera F1.** El razonamiento está escrito en `pcb.py:817` — "NO es TOON (F1 intacto: `get_tracks` es una tool separada, no una sección nueva del formato v1)". Es una lectura defendible de la regla, pero el efecto es que existen tres contratos que un LLM parsea, **sin spec, sin golden y sin sanitización** (R2/DT4). La frontera se respetó al pie de la letra y se erosionó en espíritu: el propósito de F1 es que los formatos que consume un LLM sean contratos verificados.

**Declarar G2/G4 bajo una frontera "inviolable" y no implementarlos.** F2 dice "no modificar lógica ni umbrales del sistema de gates — los gates existen para ser inviolables desde prompts". Proteger de modificación un gate que no existe es una garantía vacía, y `GATE_DENIED`/`BUDGET_EXCEEDED` en `errors.py` sugieren al lector una protección que no está.

**Confiar la Definition of Done a la disciplina humana.** `CLAUDE.md:150-163` define 6 criterios rigurosos de merge, ninguno automatizado. Que la rama actual esté verde es mérito de la disciplina del autor, no del proceso — y la disciplina no escala a colaboradores.

### Antipatrones detectados

| Antipatrón | Ubicación | Severidad |
|---|---|---|
| **God module / God function** | `tools/pcb.py` 3 402 LOC, `register()` complejidad 146 | Alta |
| **Fuga de capa (dominio en la capa de transporte)** | `enforce_hole_clearance` + geometría en `bridge/ipc.py` | Media |
| **Estado global mutable de módulo** | `store.py:174`, `g1.py:29`, `state_builder.py:27` | Media (mitigada por ADR-0001 mono-usuario; el tercero además crece sin límite) |
| **Copy-paste de cross-cutting concerns** | preámbulo de mutación ×19 en `pcb.py` | Media |
| **Side effect global no consentido** | `_ensure_freerouting_headless_config` escribe en `~/.config` | Baja |
| **Cache sin bound** | `state_builder.py:27` | Media |
| **Documentación como contrato sin verificación** | 3 formatos ad-hoc sin golden; ">90% cobertura" sin instrumento | Media |

**No detectados:** acoplamiento circular (no hay ciclos de import), side effects en constructores (`IpcBridge.__init__` solo resuelve un path y crea un lock; la conexión es perezosa en `_ensure_client`), excepciones tragadas, mutación de argumentos, ni singletons con inicialización costosa.

---

## 14. Conclusión

### Dónde está realmente el proyecto

Es un **proyecto de investigación aplicada de una sola persona, técnicamente maduro, en la puerta de convertirse en un producto open source** — y el gap que queda no es de código sino de infraestructura de proyecto. El código de dominio está resuelto a un nivel que la mayoría de los servidores MCP no alcanza: contratos formalizados, errores tipados, invariantes de persistencia verificados por tests canario, y una metodología de validación contra hardware real. Lo que le falta es lo que convierte un repo de una persona en un proyecto de varios: CI, cobertura, empaquetado, y un archivo de 3 402 líneas partido en pedazos revisables.

Hay una asimetría reveladora: el rigor del *método* (ADRs, investigaciones de causa raíz, umbrales cuantitativos, un README que lidera con los fallos) supera al rigor de la *automatización* (ningún gate ejecutable, cobertura no medida, 8% de la suite dependiente de un humano). El proyecto sabe exactamente qué está roto — lo tiene escrito con nombre, sesión y evidencia — pero nada impide mecánicamente que se rompa algo nuevo.

### Tres mayores fortalezas

1. **La disciplina de contratos y evidencia.** 14 ADRs, 7 investigaciones de causa raíz, un backlog de calidad de issue tracker, y una Validation Suite que publica sus fracasos (0/4 criterios en Nivel C) con el mismo detalle que sus éxitos.
2. **La calidad del código de frontera.** `mypy --strict` limpio en 33 archivos, tipos `Nm`/`Mm` que hacen imposible el bug histórico del dominio, cero excepciones tragadas, y el `assert` de `_IDEMPOTENT_OPS` que hace estructuralmente imposible reintentar una mutación.
3. **La economía de contexto como primitiva de diseño.** TOON con degradación en 3 niveles, delta incremental, foco por radio y `max_tokens` en cada listado — una respuesta original a un problema que la mayoría de los MCP servers ignora.

### Tres mayores debilidades

1. **`tools/pcb.py`:** 3 402 líneas con un `register()` de 2 215 y complejidad ciclomática 146, más el preámbulo de mutación duplicado 19 veces a mano.
2. **Cero automatización de calidad:** sin CI, sin cobertura instrumentada, sin pre-commit. Toda la garantía descansa en que un humano corra tres comandos antes de mergear.
3. **Techo de escala en 63 footprints,** con evidencia dura de que a 437 el flujo no completa — es el límite del producto, no un detalle.

### Las tres acciones de mayor impacto

1. **Añadir CI en GitHub Actions** con `ruff check` + `ruff format --check` + `mypy src/` + `pytest -m "not integration"` en push y PR. Esfuerzo **S**, impacto máximo: convierte 6 criterios de Definition of Done escritos en prosa en gates ejecutables, y es el prerrequisito de todo lo demás en un proyecto que declara querer colaboradores. Es la acción con mejor relación impacto/esfuerzo del repo entero.
2. **Extraer un decorador `@mutating_tool`** que centralice `_guard_live_stale` + `check_no_external_disk_edit` + `_check_base_snap` + `ensure_session_backup` + `audit_record` + `tool_call_timer` + `log_tool_call`, y usar ese punto único como paso previo a partir `tools/pcb.py` en 5-6 módulos. Esfuerzo **M**, impacto: elimina la clase de bug "una tool nueva olvidó un guard" —que hoy solo evita la memoria del autor— y desbloquea la refactorización XL.
3. **Sanitizar los tres encoders ad-hoc** (`tools/pcb.py:809`, `3263`, `3314`) reusando `toon.encoder._sanitize`, y añadir un golden por formato. Esfuerzo **S**, impacto: cierra el único hueco de la regla 6 de CLAUDE.md y convierte tres contratos hoy no verificados en contratos con test.

### Nivel de confianza para producción

**Medio-alto para el caso de uso declarado; bajo para uso general.**

Confiaría este servidor hoy para: un desarrollador que trabaja en Linux con KiCad 10.0.4, sobre placas de 2 capas y menos de ~70 footprints, con el proyecto bajo git, entendiendo que debe llamar `save_board()` explícitamente y evitar `add_zone(fill=true)` repetido. En ese perímetro las protecciones son reales y verificadas: backup automático, commit git pre-mutación, detección de edición externa en dos capas, gate G3 sobre fabricación, y audit trail completo de cada mutación aceptada y rechazada.

No lo confiaría para: placas de 4 capas o más de ~100 footprints (el autorouter no completa), operación desatendida (el crash de `add_zone(fill=true)` es un P0 abierto y G4 no existe, así que no hay techo de presupuesto), ni ningún entorno multiusuario o multiproceso (estado global de módulo, `KICAD_MCP_PROJECT` como env var de proceso, cola IPC de profundidad 1).

La razón principal de la reserva no es ninguno de los defectos técnicos individuales —todos están documentados y acotados— sino la **ausencia de CI**: en un proyecto con 163 commits, 40 ramas de sesión y una Definition of Done de 6 puntos, que nada verifique automáticamente que un merge no rompe los 394 tests es el riesgo que hace que cualquier evaluación de "listo para producción" caduque en el siguiente commit.
