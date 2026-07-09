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
| `get_component_detail` | Detalle completo de un componente: lib, pines, propiedades, footprint | `ref` | none | `COMPONENT_NOT_FOUND` |
| `get_net_detail` | Miembros y componentes de una net | `net` | none | `NET_NOT_FOUND` |
| `list_unconnected` | Pines sin net asignada en todo el proyecto | — | none | (los de lectura de estado) |

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
v0.3: `get_context_delta`, `get_session_summary`, `checkpoint`.
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
