# Catálogo de tools — MVP (v0.1)

**Estado:** CONTRATO parcial — frontera F3. Los **códigos de error existentes
no se renombran jamás** (los consume otro LLM en runtime). Añadir tools y
códigos nuevos está permitido y es responsabilidad del agente mantener este
documento actualizado en el mismo commit (Definition of Done #2).

Reglas transversales:
- Descripción de tool ≤ 15 palabras. Es lo que ve el modelo en `tools/list`.
- Toda respuesta de error tiene el formato `{code, message, hint}` donde
  `hint` es accionable ("nets similares: 3V3, 3V3_MCU"), no decorativo.
- Columna **Refresh**: qué devuelve la tool como contexto (`none` = solo
  datos solicitados; `confirm` ≈ 30 tok; `delta` ≈ 150–200; `full` = TOON).
- El MVP es solo-lectura: ninguna tool de este catálogo muta estado.

## Categoría `meta`

| Tool | Descripción | Parámetros | Refresh | Errores posibles |
|---|---|---|---|---|
| `health` | Estado del servidor, KiCad, kicad-cli y proyecto activo | — | none | `KICAD_NOT_RUNNING`, `KICAD_CLI_MISSING`, `PROJECT_NOT_FOUND` |
| `discover_tools` | Lista tools de una categoría con sus schemas | `category` | none | `INVALID_PARAMS` |

## Categoría `world`

| Tool | Descripción | Parámetros | Refresh | Errores posibles |
|---|---|---|---|---|
| `get_world_context` | Estado del proyecto en TOON v1 | `max_tokens?=800`, `focus_ref?`, `radius_mm?` | full | `KICAD_TIMEOUT`, `KICAD_NOT_RUNNING`, `PROJECT_NOT_FOUND`, `CONTEXT_BUDGET_IMPOSSIBLE`, `UNSUPPORTED_HIERARCHY` |
| `get_context_delta` | Delta TOON entre un `base_snap` y el estado actual | `base_snap`, `focus_ref`, `radius_mm`, `max_tokens?` | delta | `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `CONTEXT_BUDGET_IMPOSSIBLE`, `PROJECT_NOT_FOUND`, `UNSUPPORTED_HIERARCHY` |
| `get_component_detail` | Detalle completo de un componente: lib, pines, propiedades, footprint | `ref` | none | `COMPONENT_NOT_FOUND` |
| `get_net_detail` | Miembros y componentes de una net | `net` | none | `NET_NOT_FOUND` |
| `list_unconnected` | Pines sin net asignada en todo el proyecto | — | none | (los de lectura de estado) |

Notas de `get_context_delta` (sesión 05 T4):

- Registra el estado actual como snapshot fresco antes de emitir el delta;
  el `snap_id` nuevo va en la cabecera TOON como `snap:`. El `base_snap`
  del pedido va como `base:`. El área local sigue el formato
  `area:r{radius_mm}@{focus_ref}` (spec §3).
- `SNAPSHOT_STALE` incluye en su payload estructurado `data.base_snap` y
  `data.retention` para que el agente correlacione el fallo sin parsear
  el mensaje (F3 intacta: código no renombrado).
- Cuando el `base_snap` corresponde a un snapshot vivo (ADR-0007), el
  chequeo de `EXTERNAL_EDIT_DETECTED` se omite deliberadamente.
- **Kind-aware (sesión 06, D-06.1v2).** El kind del `base_snap` gobierna
  cómo se construye el estado actual:
  - Base vivo `kind="pcb"` (T5 sesión 05): el estado actual se reconstruye
    desde el board de kipy vía `build_state_from_board`; el snapshot nuevo
    también se registra vivo (`mtimes=None`). No se lee disco.
  - Base vivo `kind="pcb"` pero KiCad sin board disponible: `SNAPSHOT_STALE`
    con `data.reason="live_chain_lost"` (la cadena viva se perdió: cerraron
    el PCB o KiCad se reinició sin reabrir). El hint dirige a
    `get_world_context` para re-sincronizar. NO es `KICAD_NOT_RUNNING`: el
    socket puede estar OK; el problema es del snapshot del llamador.
  - Base de disco `kind="sch"` (path histórico): se sigue leyendo del
    `.kicad_sch` vía `build_state_cached` (con mtimes de disco). Kinds
    cruzados (base pcb vs curr sch o viceversa) son bug interno: la tool
    lo detecta y responde `KICAD_CLI_FAILED` con hint explícito antes de
    emitir un delta semánticamente basura.
- `max_tokens` opcional: si se pasa, se aplica la misma cascada de
  degradación §4 que en `get_world_context` (colapso de nets de poder,
  omisión de posiciones), en el mismo orden y con `CONTEXT_BUDGET_IMPOSSIBLE`
  como fallback (D-05.5).
- Ejemplo de salida (delta contra el golden 003):

  ```
  DTOON|v1|snap:8|base:7|area:r40@U1
  [+] C3  100nF  x105.0 y50.0  1>3V3 2>GND
  [~N] 3V3: C1.1 C2.1 C3.1 R1.1 U1.1
  [~N] GND: C1.2 C2.2 C3.2 U1.8
  [AREA]
  C1 ok
  C2 ok
  R1 ok
  U1 ok
  ```

## Categoría `validate`

| Tool | Descripción | Parámetros | Refresh | Errores posibles |
|---|---|---|---|---|
| `run_erc` | ERC del esquemático, violaciones estructuradas | `min_severity?=warning` | none | `KICAD_CLI_FAILED`, `PROJECT_NOT_FOUND` |
| `run_drc` | DRC del PCB, violaciones estructuradas | `min_severity?=warning` | none | `KICAD_CLI_FAILED`, `PROJECT_NOT_FOUND` |

Formato de violación (idéntico para ambos): `{rule, severity, message,
items: [{ref?|net?|pos?}]}` — posiciones en **mm**.

## Categoría `export`

| Tool | Descripción | Parámetros | Refresh | Errores posibles |
|---|---|---|---|---|
| `export_manufacturing` | Gerbers + drill a directorio del proyecto. Gate G3 | `output_dir?=fab/` | none | `EXPORT_BLOCKED_BY_DRC`, `KICAD_CLI_FAILED`, `PATH_OUTSIDE_PROJECT`, `PROJECT_NOT_FOUND` |
| `export_bom` | BOM en CSV | `output_path?` | none | `KICAD_CLI_FAILED`, `PATH_OUTSIDE_PROJECT` |
| `export_netlist` | Netlist del esquemático | `output_path?` | none | `KICAD_CLI_FAILED`, `PATH_OUTSIDE_PROJECT` |
| `export_render` | PDF del esquemático (sch_pdf) o del PCB (pcb_pdf) | `kind: "sch_pdf"\|"pcb_pdf"\|"pcb_png"`, `output_path?` | none | `KICAD_CLI_FAILED`, `INVALID_PARAMS`, `PATH_OUTSIDE_PROJECT`, `PROJECT_NOT_FOUND` |

Notas de `export_render`:
- `sch_pdf` → PDF del esquemático (una hoja por página).
- `pcb_pdf` → PDF del PCB en modo single-page con capas por defecto
  `F.Cu, B.Cu, F.SilkS, B.SilkS, Edge.Cuts`. Aceptado desde v0.1.
- `pcb_png` → **reservado**: `kicad-cli 10` no expone `pcb export png`, por
  lo que la tool devuelve `INVALID_PARAMS` con hint apuntando a `pcb_pdf`.
  Se activará sin renombrar el kind cuando kicad-cli lo soporte.

## Categoría `pcb` (v0.2 — primeras mutaciones, sesión 03)

Detrás del Gate G1 (backup + git checkpoint una vez por sesión) y con
audit line JSONL por cada mutación aceptada o rechazada.

| Tool | Descripción | Parámetros | Refresh | Errores posibles |
|---|---|---|---|---|
| `move_footprint` | Mueve un footprint del PCB a (x_mm, y_mm) | `ref`, `x_mm`, `y_mm`, `base_snap?` | confirm | `COMPONENT_NOT_FOUND`, `INVALID_PARAMS`, `KICAD_NOT_RUNNING`, `KICAD_TIMEOUT`, `KICAD_RESTARTED`, `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `PROJECT_NOT_FOUND` |
| `add_track` | Track lineal entre dos puntos, en un net y layer | `net`, `start_x_mm`, `start_y_mm`, `end_x_mm`, `end_y_mm`, `width_mm?=0.25`, `layer?="F.Cu"`, `base_snap?` | confirm | `NET_NOT_FOUND`, `INVALID_PARAMS`, `KICAD_NOT_RUNNING`, `KICAD_TIMEOUT`, `KICAD_RESTARTED`, `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `PROJECT_NOT_FOUND` |

Respuestas de éxito son confirmaciones cortas (≤ 50 tokens, ADR-0004),
p. ej. `OK move_footprint R5 -> (102.5, 44.0) [snap:12]`.

Sesión 05 T5: el `snap` del confirm es el **snapshot post-mutación** que
registra la tool (vivo, ADR-0007). El agente lo usa como `base_snap` de la
próxima mutación encadenada; el `base_snap` pasado como parámetro se
preserva en `.kicad-mcp/audit.jsonl` para trazabilidad.

Parámetro común `base_snap` (sesión 04 T4, aditivo):
- Ausente → la mutación procede sin verificación de coherencia con el
  estado que vio el agente (comportamiento pre-v0.3).
- Presente y no está en el Snapshot Store → `SNAPSHOT_STALE`; el hint
  instruye pedir `get_world_context` de nuevo (retención = 10 snapshots
  por proceso servidor).
- Presente pero el `mtime` de algún archivo del proyecto difiere del
  registrado en ese snapshot → `EXTERNAL_EDIT_DETECTED`; el usuario
  editó fuera del agente y hay que re-sync antes de mutar.
- Presente y todo coincide → la mutación procede; `snap_id` del confirm
  ecoa `base_snap`.

## Nombres reservados (fases futuras — no implementar, no renombrar)

v0.2: `add_symbol`, `set_value`, `connect_pins`, `place_footprint`,
`add_via`, `add_zone`, `reload_in_gui` (los ya implementados
—`move_footprint`, `add_track`— se mueven a la sección `pcb`).
v0.3: `get_session_summary`, `checkpoint` (el ya implementado
`get_context_delta` se mueve a la categoría `world`).
v0.4: `suggest_positions`, `route_with_freerouting`.

Reservarlos ahora evita que el agente invente nombres divergentes en prompts,
docs o tests intermedios.

## Taxonomía de errores (completa, F3)

| Código | Significado | ¿Reintentable? | Guía del hint |
|---|---|---|---|
| `KICAD_NOT_RUNNING` | No hay socket IPC disponible | Sí, tras acción del usuario | Instruir: abrir KiCad y habilitar API en Preferences→Plugins |
| `KICAD_TIMEOUT` | Request IPC excedió el timeout (2 s) | Sí, 1 reintento | Sugerir reducir alcance de la operación |
| `KICAD_RESTARTED` | `KICAD_API_TOKEN` cambió a mitad de sesión | Sí | Instruir: pedir `get_world_context` (snapshots invalidados) |
| `KICAD_CLI_MISSING` | kicad-cli no está en PATH | No | Instrucción de instalación |
| `KICAD_CLI_FAILED` | kicad-cli devolvió error | Depende | Incluir stderr resumido y saneado (≤ 200 chars) |
| `PROJECT_NOT_FOUND` | No hay proyecto activo o la ruta no existe | No | Listar qué se buscó y dónde |
| `COMPONENT_NOT_FOUND` | Ref inexistente en el snapshot vigente | No | Refs similares por distancia de edición (máx 3) |
| `NET_NOT_FOUND` | Net inexistente | No | Nets similares (máx 3) |
| `SNAPSHOT_STALE` | `base_snap` expiró o fue invalidado | No | Instruir: pedir contexto completo, no reintentar el delta |
| `EXTERNAL_EDIT_DETECTED` | El usuario editó fuera del agente (mtime) | No | Instruir: re-sync completo antes de continuar |
| `CONTEXT_BUDGET_IMPOSSIBLE` | El estado no cabe ni degradado | No | Sugerir presupuesto mínimo calculado o reducir radio |
| `UNSUPPORTED_HIERARCHY` | Esquemático multi-hoja (fuera del alcance MVP) | No | Declarar la limitación; nunca procesar parcialmente en silencio |
| `EXPORT_BLOCKED_BY_DRC` | Gate G3: hay violaciones de severidad error | Sí, tras resolver | Incluir el conteo y las 3 primeras violaciones |
| `GATE_DENIED` | Gate interactivo (G2/G4) rechazado por el usuario | No | Explicar qué gate y por qué se disparó |
| `BUDGET_EXCEEDED` | Gate G4: techo de sesión alcanzado | No | Requiere acción explícita del usuario |
| `INVALID_PARAMS` | Parámetros no validan contra el schema | No | Nombrar el campo exacto y el valor recibido |
| `PATH_OUTSIDE_PROJECT` | Ruta fuera de la raíz del proyecto | No | Mostrar la raíz permitida; jamás la ruta canónica del sistema |

Reglas de la taxonomía: los códigos son SCREAMING_SNAKE en inglés (estables
ante cambios de idioma de la UI); `message` y `hint` en el idioma de la
sesión; un error nunca incluye tracebacks, rutas absolutas del sistema ni
texto sin sanear proveniente del proyecto.

**Campo `data` del envelope (estándar opcional, F3 intacta).** El envelope
completo es `{code, message, hint, data?}`, donde `data: dict[str, Any] |
None` es un payload estructurado que enriquece el hint sin romper la
taxonomía: el código y su semántica siguen intactos, y el agente puede
correlacionar el fallo con su plan sin parsear el mensaje. Reglas:

- `data` es opcional; su ausencia equivale a `null` y se omite del envelope
  serializado. Consumidores tolerantes: nunca asumir presencia.
- Las claves de `data` son `snake_case` y estables por código de error (una
  vez publicadas no se renombran). Su semántica se documenta en la entrada
  del código o de la tool que las emite.
- Los códigos no cambian por decidir emitir `data`. Cualquier código puede
  ganar un payload estructurado en una sesión futura sin quebrar F3.

Emisores actuales:

- `SNAPSHOT_STALE` → `data.base_snap: int`, `data.retention: int`. El agente
  usa `base_snap` para saber cuál de sus snaps expiró y `retention` para
  entender cuántos hacia atrás puede cachar.
- `SNAPSHOT_STALE` con `data.reason: "live_chain_lost"` → se emite cuando el
  base es vivo pero el board de KiCad no está disponible al pedir el delta
  (sesión 06, D-06.1v2). El agente distingue esta variante del expirado por
  retención sin parsear el mensaje.
- `KICAD_CLI_FAILED` con `data.ipc_status: "busy" | "unhandled"` → clasifica
  fallos IPC de KiCad sin renombrar el código (sesión 07, D-07.2). Valores:
  - `"busy"` — KiCad devolvió `ApiStatusCode.AS_BUSY`: la UI está procesando
    otra operación (refill de zonas, DRC realtime, router auto). Hint fijo:
    "KiCad está ocupado con una operación en curso; reintentá en unos
    segundos." Reintentable por el agente; el bridge ya reintenta lecturas
    idempotentes (D-07.1) antes de propagar.
  - `"unhandled"` — KiCad devolvió `ApiStatusCode.AS_UNHANDLED`: el editor
    requerido no está abierto. Hint fijo: "El editor requerido no está
    abierto en KiCad (abrí el PCB Editor)." No reintentable sin acción del
    usuario.

  Los demás fallos IPC (incluido `ApiError` con código no distinguido) siguen
  emitiendo `KICAD_CLI_FAILED` sin `data.ipc_status`; el hint incluye el
  detalle sanitizado del mensaje original.
