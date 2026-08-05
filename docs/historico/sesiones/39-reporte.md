# Sesión 39 — DT2: decorador `@mutating_tool` para unificar el preámbulo transversal

**Rama:** `sesion/39-mutating-tool-decorator` desde `master` (`989c505`).

**Tipo:** deuda técnica estructural (DT2 del backlog). Primera sesión del
ciclo que sale del frente de encoders ad-hoc (sesiones 36-38) y ataca el
modo de fallo transversal del proyecto: preámbulo repetido literal en las
tools mutantes sin un lugar único donde vivan las políticas de entrada.

## Resumen ejecutivo

`@mutating_tool` (`src/kicad_mcp/tools/_mutating.py`, ADR-0014) centraliza
las tres guardas de entrada — `_guard_live_stale`,
`check_no_external_disk_edit`, validación de `base_snap` — que hoy se
repetían a mano en cada tool mutante de `tools/pcb.py`. Aplicado a **12 de
las 16 tools reales** (19 tools MCP mutantes registradas, 16 sitios de
preámbulo). El análisis de anatomía (P3) refutó parcialmente H1: el
preámbulo NO es uniforme entre las 19 — hay tres familias estructurales
distintas — así que el decorador se acotó a la familia que sí lo comparte
literal, con dos exclusiones documentadas y consultadas con el arquitecto
antes de tomarlas. Resultado: `tools/pcb.py` bajó de 3507 a 3419 líneas
(-2.5%), suite offline sin un solo test viejo modificado (392 → 406,
+14 nuevos del decorador aislado), suite integration (kicad-cli) 38/38
verde.

## P3 — Verificación de premisa

1. **`master` remoto:** `989c505`, confirmado con `gh api
   repos/Gato513/kicad-mcp/commits/master` — coincide con el prompt, sin
   push directo detectado.
2. **Branch protection:** activa sobre `master`, 4 checks obligatorios
   (`ruff check`, `ruff format --check`, `mypy src/`, `pytest (offline)`),
   verificado con `gh api repos/.../branches/master/protection`.
3. **`docs/BACKLOG.md`:** `P1-1` cerrado (sesión 37+38) ✅, `P1-2` (`kiid`)
   abierto sin sesión asignada ✅. **DT2 NO tenía entrada propia** en
   `BACKLOG.md` — sólo existía en `docs/analisis/auditoria-tecnica-
   integral-2026-08.md` (documento untracked en el repo). Se creó la
   entrada esta sesión, ya marcada cerrada (ver `docs/BACKLOG.md`).
4. **Conteo real de mutantes.** Fuente triple:
   - `docs/specs/tool-catalog.md`: no contradice el código; no enumera un
     conteo total de mutantes explícito para cruzar.
   - `docs/adr/0012-route-board-persist-contract.md`: cubre la asimetría
     de persistencia de `route_board`/`fill_zones`/`add_zone`, no un
     conteo de superficie.
   - **Código real** (`grep` de `@mcp.tool(` en `tools/pcb.py` +
     `tools/sch.py`): **19 tools MCP mutantes registradas**. De ellas,
     **16 sitios de preámbulo** distintos — `_delete_copper` es el núcleo
     compartido de `delete_track`+`delete_via`, `_set_property_core` el de
     `set_value`+`set_footprint`.

   No hubo discrepancia entre las tres fuentes que ameritara nota P9 aparte
   de la ausencia de DT2 en el BACKLOG (punto 3).
5. **Anatomía real del preámbulo** (insumo directo de H1): ver tabla
   completa en `docs/adr/0014-mutating-tool-decorator.md` §Contexto. Tres
   familias:

   | Familia | Sitios | Forma |
   |---|---|---|
   | A — W-IPC de PCB | 11 | `_guard_live_stale` → `check_no_external_disk_edit` → `_project_root` → `_check_base_snap` → `_resolve_board` |
   | B — excepciones deliberadas | 2 (`route_board`, `reload_board_from_disk`) | sin guard simétrico, `root` de otra fuente, G1 en otro orden (D-14.3, ADR-0011/0012) |
   | C — W-disco de sch | 3 (`add_symbol`, `_set_property_core`, `connect_pins`) | sólo `root` + `validate_base_snap` + G1, sin guard IPC |

   El **epílogo** (`tool_call_timer`, `ensure_session_backup`,
   `audit_record`, registro del snapshot, `log_tool_call`) resultó **no
   uniforme**: mtimes reales vs `None` vs condicional (`add_zone` con
   `fill=True/False`), retorno `str` vs `dict`, contenido de `extra`
   distinto por tool. Absorberlo habría exigido invertir el control de
   cada `return` — lo opuesto de un refactor quirúrgico. Quedó fuera del
   decorador por decisión explícita (ver H1 abajo).
6. **`errors.py`:** 27 códigos de `ErrorCode`, estructura intacta, sin
   reorganización pendiente. El decorador no agrega ni renombra ninguno.

## H1 — parcialmente refutada, consulta al arquitecto

El preámbulo NO cupo en un solo decorador parametrizado sin forzar
comportamiento distinto en sitios reales. Se consultó al arquitecto con
tres preguntas (alcance del decorador, qué hacer con los sitios que no
encajan, qué hacer con la ausencia de DT2 en el BACKLOG) antes de escribir
una línea de código. Decisiones resultantes:

1. **Alcance del decorador: sólo guardas de entrada** (opción "envelope
   completo" descartada explícitamente — habría tocado los 16 `return`
   paths con alto riesgo sobre H3; "partir 39a/39b" no fue necesaria
   porque el análisis mostró que la Familia A sí cabía completa en una
   sesión).
2. **Exclusiones:** `delete_tracks_bulk` (preámbulo post early-return de
   `dry_run` — ver detalle abajo) y Familia B completa (contrato
   deliberado). Familia C (sch) no se toca esta sesión.
3. **BACKLOG:** se crea la entrada DT2, marcada cerrada por sesión 39, con
   referencia al doc de auditoría de origen.

No hizo falta partición 39a/39b: dos flags booleanos (`disk_check`,
`base_snap_check`) alcanzaron para expresar las dos asimetrías reales
encontradas — no se disparó el criterio de "varias variantes
estructurales" que habría pedido una jerarquía de decoradores.

## Superficie decidida: 12 de 16 sitios

Decoradas: `move_footprint`, `set_footprint_ref`, `add_track`, `add_via`,
`save_board`, `delete_track`, `delete_via`, `draw_board_outline`,
`add_zone`, `add_keepout_zone`, `fill_zones`, `delete_zone`.

**Excluidas, con traza al código:**

- **`delete_tracks_bulk`** (`tools/pcb.py`). Su preámbulo corre DESPUÉS
  del early-return de `dry_run=True` — la función primero calcula qué
  borraría y, sólo si `dry_run` es falso, recién ahí llama
  `_guard_live_stale()`/`check_no_external_disk_edit()`. Hoistear esas
  guardas al decorador externo habría hecho que un `dry_run=True` sobre
  un board live-stale lance `EXTERNAL_EDIT_DETECTED` en vez de listar
  candidatos — cambio de comportamiento observable, H3 refutada para ese
  caso específico. Se deja sin decorar, íntegro.
- **`route_board` / `reload_board_from_disk`** (Familia B). Desviaciones
  de contrato deliberadas y documentadas (D-14.3, ADR-0011, ADR-0012):
  `reload_board_from_disk` es el mecanismo que destraba
  `_guard_live_stale`, no puede estar detrás de esa misma guarda.
  `route_board` tiene su propio pipeline de save-implícito + recarga
  automática que no cabe en "guard antes de todo".
- **Familia C** (`add_symbol`, `set_value`/`set_footprint`,
  `connect_pins`). Estructuralmente distinta (sin guard IPC, sin
  `_resolve_board`) — fuera de alcance por definición del prompt de
  sesión 39, no por hallazgo nuevo.

**Flags que documentan asimetrías reales, no las esconden** (detalle
completo con traza al código en el ADR):

| Tool | Flag | Motivo (resumen) |
|---|---|---|
| `move_footprint` | `disk_check=False` | Única W-IPC de PCB que hoy no llama `check_no_external_disk_edit` (sí llama `_guard_live_stale`) — asimetría preexistente, ahora explícita en el sitio de registro en vez de ausencia silenciosa. |
| `delete_track`, `delete_via` | `base_snap_check=False` | `_check_base_snap` corre DENTRO de `_delete_copper`, después de la validación id-vs-coords — hoistearlo cambiaría un `INVALID_PARAMS` a `SNAPSHOT_STALE` en un caso mixto (cambio de F3). |

## Implementación

- **`src/kicad_mcp/tools/_mutating.py`** (nuevo). Decorador
  `mutating_tool(tool_name, *, live_guard=True, disk_check=True,
  base_snap_check=True)`, tipado con `TypeVar` acotado a `Callable[...,
  Any]` para que `functools.wraps` preserve la firma bajo mypy strict
  (`Callable[[F], F]`, sin `Any` de retorno). Junto al decorador se
  movieron cuatro helpers que `pcb.py` tenía a nivel de módulo y que el
  decorador necesita internamente (`_project_root`, `_guard_live_stale`,
  `_check_base_snap`, `_resolve_root_schematic_or_pcb`) — evita un ciclo
  de import `pcb.py ↔ _mutating.py`. `pcb.py` los reimporta desde
  `._mutating`; ningún call site externo (incluidos los de `pcb.py` que
  no son preámbulo, ej. `save_board` usando `_resolve_root_schematic_or_pcb`
  para `collect_project_mtimes`) cambió de comportamiento.
- **`tools/pcb.py`**: 12 sitios con diff quirúrgico — se retira el bloque
  de guardas inline (`_guard_live_stale()` + `check_no_external_disk_edit(
  ...)` + `if base_snap is not None: _check_base_snap(base_snap)`) y se
  agrega `@mutating_tool("<nombre>", ...)` entre `@mcp.tool(...)` y el
  `def`. `_delete_copper` (núcleo compartido de `delete_track`/
  `delete_via`) perdió las dos primeras guardas (ahora las aplica el
  decorador en cada wrapper) y ganó un párrafo de docstring explicando por
  qué `_check_base_snap` se queda adentro.
- **`docs/adr/0014-mutating-tool-decorator.md`**: contexto completo
  (anatomía de las tres familias, por qué el epílogo no entra), decisión,
  tabla de exclusiones con traza al código, tabla de flags, alternativas
  descartadas (envelope completo, jerarquía de decoradores, partición de
  sesión, `tools/_common.py` como ubicación) y consecuencias para DT1
  (sesión 40).
- **`tests/test_mutating_tool.py`** (nuevo, 14 tests): nivel aislado
  (spies sobre las tres guardas reales del módulo — orden, gating por
  flag, `base_snap` posicional/keyword/ausente, propagación de
  `KicadMcpError` con el mismo `code`, `functools.wraps`/firma, marca
  `__mutating_tool__`) + nivel canario (registra `tools/pcb.py` real
  contra un `FastMCP` y verifica que las 12 tools decoradas llevan la
  marca, y que las 3 excluidas explícitamente NO la llevan — protege
  contra scope creep silencioso en cualquier dirección).

## Números duros

| Métrica | Valor |
|---|---|
| Tools MCP mutantes registradas | 19 |
| Sitios de preámbulo reales | 16 |
| Sitios decorados | 12 |
| `tools/pcb.py` antes | 3507 líneas |
| `tools/pcb.py` después | 3419 líneas (**-88, -2.5%**) |
| `tools/_mutating.py` (nuevo) | 173 líneas |
| Helpers relocados (no borrados) | 4 funciones, ~49 líneas |
| Tests offline antes | 392 passed |
| Tests offline después | **406 passed** (392 intactos + 14 nuevos) |
| Tests viejos modificados | **0** |
| Tests integration (kicad-cli) | **38 passed**, 0 fallos |
| `ruff check` / `ruff format --check` / `mypy src/` | limpios |

**Desglose por tool** (líneas netas del sitio de preámbulo, decorador
incluido — no cuenta las 49 líneas de helpers relocados ni el ADR/reporte):

| Tool | Neto | Nota |
|---|---|---|
| `move_footprint` | -4 | |
| `set_footprint_ref` | -5 | |
| `add_track` | -5 | |
| `add_via` | -5 | |
| `save_board` | -5 | |
| `_delete_copper` (núcleo) | +5 | docstring nueva explicando `base_snap_check=False`, no boilerplate |
| `delete_track` | +1 | guard removido una sola vez en `_delete_copper`, no por wrapper |
| `delete_via` | +1 | ídem |
| `draw_board_outline` | -4 | |
| `add_zone` | -5 | |
| `add_keepout_zone` | -5 | |
| `fill_zones` | -5 | |
| `delete_zone` | -5 | |

## Verificación

- `python3 scripts/verificar_entorno.py`: 13 OK · 3 WARN (rama sin commit
  al inicio — resuelto creando la rama de sesión antes de tocar código;
  `KICAD_MCP_FREEROUTING_JAR` sin setear; `npx` no disponible) · 0 FAIL.
  Veredicto: listo para `integration` con kicad-cli.
- `uv run pytest -m "not integration and not integration_gui and not
  integration_gui_slow"` → **406 passed** (392 + 14), sin modificar un
  solo test existente.
- `uv run ruff check --fix && uv run ruff format` → limpio.
- `uv run mypy src/` → limpio (el primer intento marcó 12 errores
  `untyped-decorator` por un `TypeVar` mal acotado — `bound="Any"` en vez
  de `bound=Callable[..., Any]` — corregido antes de continuar).
- `uv run pytest -m integration` → **38 passed, 445 deselected** (kicad-cli
  disponible en este entorno: ERC/DRC/export). Sin fallos.
- `uv run pytest -m integration_gui_slow` (verificación de overhead de
  latencia declarada como riesgo a priori): **no corrida** — esa marca
  exige "protocolo manual" con GUI de KiCad abierta sobre un proyecto de
  prueba específico (`pyproject.toml`: `integration_gui: requiere KiCad
  GUI abierto con un proyecto de prueba (protocolo manual)`), y
  `verificar_entorno.py` reportó `MODO detectado: integration` — no
  `integration_gui`. Ejecutarla sin ese protocolo habría significado
  mutar un board real sin la preparación que el propio marcador exige.
  Se declara para CI/arquitecto, como prevé el criterio de éxito #5 del
  prompt. Riesgo de overhead evaluado como bajo por diseño
  (`functools.wraps` es prácticamente gratis, las guardas movidas son las
  mismas llamadas que antes, sólo reubicadas) pero no verificado en vivo
  esta sesión.
- CI del PR: pendiente de apertura del PR (ver Entregables).

## Hallazgo fuera de alcance — al backlog, no se tocó

`_delete_copper` (`tools/pcb.py`) llama `log_tool_call` **dentro** del
`with tool_call_timer()` en vez de después de cerrarlo (a diferencia del
resto de las tools) — `delete_track`/`delete_via` emiten `latency_ms: 0.0`
en el log estructurado porque el timer todavía no se detuvo cuando se lee
`timer["latency_ms"]`. Defecto real, preexistente, no introducido ni
tocado por esta sesión (fuera del alcance quirúrgico declarado). Anotado
para higiene menor en `docs/BACKLOG.md`.

## Propuesta para sesión 40 (DT1)

1. **Partición de `tools/pcb.py`** en varios módulos por categoría
   (footprints, tracks/vías, zonas, contorno) — DT1 hereda un `pcb.py` con
   decoradores ya aplicados pero sin partir; `_mutating.py` es transversal
   dentro de `tools/` y no resuelve el tamaño del god module por sí solo.
   Mover las 12 tools decoradas a sus módulos nuevos no debería tocar el
   decorador ni sus flags — es una buena señal temprana de que la
   separación de responsabilidades (guardas de entrada vs organización de
   archivo) está bien trazada.
2. **Integrar el fix de `P1-2` (`kiid` sin sanitizar)** en el mismo
   alcance de DT1, tal como anotó el reporte de sesión 38: el sitio de
   emisión de `kiid` vive en el mismo bloque de encoders ad-hoc que DT1 va
   a tocar de todos modos. Evaluar ahí si conviene resolverlo en el mismo
   commit o en un sub-paso claramente delimitado dentro de la sesión.
3. **Familia C (sch.py) como candidata futura** para un decorador hermano
   (`@mutating_sch_tool` o nombre equivalente) si aparece evidencia
   concreta de que el mismo modo de fallo (guard olvidado en una tool
   nueva) se repite ahí — no se fuerza sin esa evidencia.
4. El canario `test_tools_decoradas_llevan_la_marca_mutating_tool` /
   `test_tools_excluidas_no_llevan_la_marca` de
   `tests/test_mutating_tool.py` debe actualizarse junto con cualquier
   cambio de superficie que DT1 introduzca (nuevas tools, tools que
   cambian de exclusión a inclusión, etc.).

## Entregables

1. `src/kicad_mcp/tools/_mutating.py` — decorador + 4 helpers relocados.
2. `src/kicad_mcp/tools/pcb.py` — 12 sitios refactorizados, diff
   quirúrgico verificado hunk por hunk.
3. `docs/adr/0014-mutating-tool-decorator.md`.
4. `tests/test_mutating_tool.py` — 14 tests (12 aislados + 2 canarios).
5. `docs/BACKLOG.md` — DT2 cerrado, entrada nueva con traza completa.
6. Este reporte.
7. Todo en `sesion/39-mutating-tool-decorator`. Ningún commit a `master`
   — el humano abre y mergea el PR.
