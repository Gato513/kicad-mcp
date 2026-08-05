# ADR-0014 — `@mutating_tool`: decorador de guardas de entrada para tools mutantes

**Fecha:** 2026-08-05 · **Estado:** aceptado · **Fuente:** sesión 39 (DT2 del
backlog, `docs/analisis/auditoria-tecnica-integral-2026-08.md` M1)

## Contexto

`docs/analisis/auditoria-tecnica-integral-2026-08.md` (DT2) registró que el
preámbulo transversal de las tools mutantes de `tools/pcb.py` está repetido
a mano en cada una. El costo no es el LOC: sin un lugar único donde vivan
esas políticas, cada una se aplica o se olvida por memoria del autor. La
sesión 34a ya encontró una instancia real de ese modo de fallo —
`draw_board_outline` era la única tool W-IPC de PCB sin
`_guard_live_stale()`/`check_no_external_disk_edit()`, mutaba el vivo aunque
el disco tuviera un ruteo pendiente de recarga o hubiera sido editado
externamente (asimetría A7, fix trivial pero sólo detectado por auditoría
manual).

Sesión 40 (DT1) va a partir `tools/pcb.py` en varios módulos. Si el
preámbulo sigue repetido literal, DT1 fija la deuda en más archivos en vez
de reducirla — de ahí que DT2 preceda a DT1 en la secuencia del roadmap.

### Anatomía real del preámbulo (P3 de la sesión, previa al diseño)

Inspección de las 19 tools MCP mutantes registradas en el código (17 sitios
de preámbulo — `_delete_copper` sirve a `delete_track`+`delete_via`,
`_set_property_core` a `set_value`+`set_footprint`) encontró **tres
familias estructurales**, no una uniforme:

| Familia | Sitios | Forma del preámbulo |
|---|---|---|
| **A — W-IPC de PCB** | 12 | `_guard_live_stale` → `check_no_external_disk_edit` → `_project_root` → `_check_base_snap` → `_resolve_board` |
| **B — excepciones deliberadas** | 2 (`route_board`, `reload_board_from_disk`) | sin guard de entrada simétrico, `root` de otra fuente, orden de Gate G1 distinto (D-14.3, ADR-0011, ADR-0012) |
| **C — W-disco de esquemático** | 3 (`add_symbol`, `set_value`/`set_footprint` vía `_set_property_core`, `connect_pins`) | sólo `root` + `validate_base_snap` + G1 — sin guard IPC, sin `_resolve_board` |

**Corrección (errata post-merge, 2026-08-05):** la versión original de esta
tabla contaba 11 sitios en la Familia A y 16 en el total — error aritmético:
`delete_tracks_bulk` es estructuralmente Familia A (mismo guard, sólo
desplazado tras el early-return de `dry_run`, ver más abajo) pero había
quedado fuera de la suma de la fila. Familia A son en realidad **13 tools**
(`move_footprint`, `set_footprint_ref`, `add_track`, `add_via`,
`save_board`, `delete_track`, `delete_via`, `delete_tracks_bulk`,
`draw_board_outline`, `add_zone`, `add_keepout_zone`, `fill_zones`,
`delete_zone`) que colapsan a **12 sitios** por la fusión
`delete_track`+`delete_via` → `_delete_copper`. 12+2+3 = **17** sitios
totales, no 16. El conteo de tools decoradas (12) y el análisis de
exclusiones no cambian — sólo la aritmética del total de sitios.

Además, el **epílogo** (`tool_call_timer`, `ensure_session_backup`,
`audit_record`, registro del snapshot post-mutación, `log_tool_call`) **no
es uniforme entre las 19 tools**: mtimes reales vs `None` vs condicional
(`add_zone` con `fill=True/False`), retorno `str` vs `dict` estructurado,
contenido de `extra` distinto por tool. Absorber el epílogo en un decorador
exigiría invertir el control de cada `return` — el equivalente de reescribir
las 19 tools, no un refactor quirúrgico.

## Decisión

**`@mutating_tool` cubre exclusivamente las guardas de ENTRADA de la
Familia A** — nada del epílogo:

1. `_guard_live_stale()` (D-14.1).
2. `check_no_external_disk_edit(...)` (P3.2).
3. `if base_snap is not None: _check_base_snap(base_snap)`.

Vive en `src/kicad_mcp/tools/_mutating.py`, un módulo nuevo (no
`tools/_common.py`: no hay hoy ninguna otra utilidad transversal fuera de
las guardas mismas, y un nombre genérico invitaría a acumular ahí lo que
sesión 39 explícitamente descarta — cache, retry, logging de "yapa"). Junto
al decorador se movieron cuatro helpers que antes vivían en `tools/pcb.py`
(`_project_root`, `_guard_live_stale`, `_check_base_snap`,
`_resolve_root_schematic_or_pcb`) porque el decorador los necesita
internamente y `pcb.py` no puede importarlos de vuelta sin ciclo. `pcb.py`
los reimporta desde `_mutating` — ningún call site externo cambia.

```python
def mutating_tool(
    tool_name: str,
    *,
    live_guard: bool = True,
    disk_check: bool = True,
    base_snap_check: bool = True,
) -> Callable[[F], F]: ...
```

Aplicación:

```python
@mcp.tool(name="add_track", description="...")
@mutating_tool("add_track")
def add_track(net, ..., base_snap: int | None = None) -> str:
    with tool_call_timer() as timer:
        root = _project_root()
        board = _resolve_board(bridge)
        ...                      # cuerpo sin cambios
    log_tool_call(...)           # epílogo sin cambios
    return confirmation
```

`@mcp.tool` queda por FUERA (decorador exterior); `@mutating_tool` decora
la función directamente. `functools.wraps` preserva `__name__`, `__doc__` y
la firma vía `__wrapped__`, así que `inspect.signature` (que FastMCP usa
para construir el JSON schema del tool) sigue viendo la firma original —
API observable por el LLM cliente intacta.

`base_snap` se localiza en la firma decorada por **nombre**, vía
`inspect.signature(func).bind_partial(*args, **kwargs)`, no por posición
fija — indiferente a si la tool lo recibe posicional o por keyword.

### Superficie decidida: 12 tools de 17 sitios

De los 17 sitios de preámbulo, **12 tools llevan el decorador**
(11 sitios de código distintos, ya que `delete_track`/`delete_via`
comparten `_delete_copper`): `move_footprint`, `set_footprint_ref`,
`add_track`, `add_via`, `save_board`, `delete_track`, `delete_via`,
`draw_board_outline`, `add_zone`, `add_keepout_zone`, `fill_zones`,
`delete_zone`.

**Excluidas, con justificación:**

- **`delete_tracks_bulk`.** Su preámbulo corre DESPUÉS del early-return de
  `dry_run` (`tools/pcb.py`), no al entrar a la función. Hoistearlo al
  decorador externo haría que un `dry_run=True` sobre un board live-stale
  lance `EXTERNAL_EDIT_DETECTED` en vez de listar candidatos — cambio de
  comportamiento observable (H3 del prompt de sesión 39, refutada para este
  caso). Se deja sin decorar.
- **Familia B completa** (`route_board`, `reload_board_from_disk`).
  Desviaciones deliberadas de contrato (D-14.3, ADR-0011, ADR-0012):
  `reload_board_from_disk` es precisamente el mecanismo que destraba
  `_guard_live_stale`, y `route_board` tiene su propio pipeline de
  save-implícito + recarga que no cabe en el modelo "guard antes de todo".
- **Familia C completa** (`add_symbol`, `set_value`/`set_footprint`,
  `connect_pins`). Estructuralmente distinta — sin guard IPC, sin
  `_resolve_board` — fuera del alcance de esta sesión. Candidata natural
  para un decorador hermano (`@mutating_sch_tool` o similar) en una sesión
  futura si aparece la misma señal de deuda ahí.

### Flags que documentan asimetrías reales (no las esconden)

| Tool | Flag | Motivo |
|---|---|---|
| `move_footprint` | `disk_check=False` | Única W-IPC de PCB que hoy NO llama `check_no_external_disk_edit` (SÍ llama `_guard_live_stale`). Asimetría preexistente, documentada en `snapshots/validation.py:57-70`. El flag la vuelve explícita en el sitio de registro — el objetivo declarado de DT2 — en vez de "ausencia silenciosa" como hasta ahora. |
| `delete_track`, `delete_via` | `base_snap_check=False` | En `_delete_copper` (núcleo compartido) la validación `INVALID_PARAMS` de id-vs-coords corre ANTES de `_check_base_snap`. Hoistear el check al decorador externo cambiaría, para una llamada que mezcla `id` con `net`/coordenadas y además pasa un `base_snap` vencido, el código de error emitido de `INVALID_PARAMS` a `SNAPSHOT_STALE` — cambio de F3, prohibido sin ADR aparte. `_check_base_snap` se queda dentro de `_delete_copper`, después de la validación de forma. |

En `add_zone`/`add_keepout_zone`/`fill_zones`/`delete_zone` el orden
relativo entre las tres guardas y el resto del cuerpo se preserva sin
flags — son Familia A pura.

### Latencia y logging — sin cambio observable

Las guardas ahora corren ANTES de que `tool_call_timer` abra su `with`
(el decorador envuelve la función completa, y el `with` vive dentro de
ella). Es el mismo orden que tenían inline: cuando una guarda lanza, ya
hoy no se llega a abrir el `with` ni a emitir `log_tool_call`. Ninguna tool
gana ni pierde una línea de log por este cambio.

## Alternativas descartadas

- **Un solo decorador que también cubra el epílogo** (timer + log +
  snapshot + audit), con las tools devolviendo un `MutationResult`
  estructurado. Descartado: el epílogo no es uniforme (ver Contexto);
  forzarlo exige invertir el control de cada `return`, tocando los 17
  sitios de forma no quirúrgica y con alto riesgo sobre el criterio de
  "cero cambio observable" (H3). Evaluado y rechazado explícitamente por
  el arquitecto en la consulta de diseño de esta sesión.
- **Jerarquía de 2-3 decoradores especializados** (uno por familia). Con
  sólo 12 tools cubiertas y dos flags booleanos alcanzando para expresar
  las asimetrías reales, una jerarquía habría sido complejidad sin
  beneficio — el criterio del prompt ("mejor jerarquía pequeña que
  decorador todopoderoso, PERO sólo si el análisis lo pide") no se
  disparó: dos flags booleanos, no variantes estructurales, bastaron.
- **Partición 39a/39b** (análisis+ADR en una sesión, implementación en
  otra). Evaluada como salida válida si la varianza real superaba lo
  manejable en una sesión; el análisis de P3 mostró que sí cabía completo
  (superficie acotada a 12 tools de forma casi idéntica, 2 asimetrías
  expresables en flags) — no se activó.
- **`tools/_common.py`** como ubicación. Descartado a favor de
  `tools/_mutating.py`: un nombre genérico habría sido la puerta de
  entrada exacta para la deriva que motivó DT2 en primer lugar (agregar
  "una ayuda más" sin que quede claro qué pertenece ahí).

## Consecuencias

- 12 sitios de preámbulo colapsan a una línea de decorador + (a lo sumo)
  1-2 kwargs. El resto del cuerpo (timer, lógica de negocio, G1, audit,
  snapshot, log) no cambia una línea — diff quirúrgico, verificable célula
  por célula contra el `git diff`.
- Los 4 sitios sin decorar (`delete_tracks_bulk`, `route_board`,
  `reload_board_from_disk`, y las 3 de Familia C que no suman como "sitio
  de preámbulo A") quedan documentados acá y en el docstring de
  `_mutating.py` como exclusiones activas, no como deuda pendiente sin
  registrar.
- Toda tool mutante NUEVA que se agregue a la Familia A (W-IPC de PCB) debe
  nacer con `@mutating_tool`; si no aplica, la justificación va en este
  ADR (nueva fila de la tabla de exclusiones) o en uno nuevo si el patrón
  es sustancialmente distinto. El canario de `tests/test_mutating_tool.py`
  (`test_tools_decoradas_llevan_la_marca_mutating_tool`) es el mecanismo
  que hace cumplir esto en CI: una mutante nueva sin el decorador no rompe
  ningún test existente por sí sola, así que ese canario es la única red
  — se actualiza junto con cualquier cambio de superficie.
- Sesión 40 (DT1, partición de `tools/pcb.py`) hereda un `pcb.py` con
  decoradores aplicados pero SIN partir — `_mutating.py` es transversal
  dentro de `tools/`, no resuelve el tamaño del god module por sí solo.
  DT1 puede mover las tools decoradas a sus módulos nuevos sin tocar el
  decorador ni sus flags.
- Familia C (sch.py) queda con su preámbulo intacto — candidata explícita
  para una sesión futura si el mismo modo de fallo (guard olvidado en una
  tool nueva) aparece ahí con evidencia concreta.
