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

Notas de `health` (sesión 07 D-07.3): el sub-payload `kicad_ipc` reporta tres
niveles independientes con estados discriminables — un `bool` colapsaría
"KiCad respondió que no" con "no pude preguntar", que son casos de acción
distintos para el agente.

- `socket`: `"ok"` (fichero del socket existe) | `"missing"`.
- `ipc_responde`: `"ok"` (get_version respondió) | `"error"` | `"unknown"` (nivel
  superior falló y no se evaluó).
- `pcb_editor_abierto`: `"yes"` (get_open_documents(DOCTYPE_PCB) no-vacío) |
  `"no"` (vacío o `AS_UNHANDLED`) | `"unknown"`.

El `status` de nivel superior (`"ok"`/`"missing"`/`"error"`) se preserva para
consumidores que sólo lo miren. `health` NO sondea busy: cuesta un GetItems
real (~3 s en boards medianos) y el busy es transitorio; se surfacea por
operación vía `KICAD_CLI_FAILED` con `data.ipc_status="busy"` (D-07.2).

Ejemplo con KiCad abierto sobre un PCB:

```json
"kicad_ipc": {
  "socket": "ok",
  "ipc_responde": "ok",
  "version": "10.0.4",
  "pcb_editor_abierto": "yes",
  "status": "ok"
}
```

Ejemplo con KiCad cerrado:

```json
"kicad_ipc": {
  "socket": "missing",
  "ipc_responde": "unknown",
  "pcb_editor_abierto": "unknown",
  "status": "missing",
  "code": "KICAD_NOT_RUNNING",
  "hint": "Abrí KiCad y habilitá el API server ..."
}
```

## Categoría `world`

| Tool | Descripción | Parámetros | Refresh | Errores posibles |
|---|---|---|---|---|
| `get_world_context` | Estado del proyecto (sch de disco o pcb vivo) en TOON v1 | `max_tokens?=800`, `focus_ref?`, `radius_mm?`, `kind?="sch"` | full | `KICAD_TIMEOUT`, `KICAD_NOT_RUNNING`, `KICAD_CLI_FAILED`, `PROJECT_NOT_FOUND`, `INVALID_PARAMS`, `CONTEXT_BUDGET_IMPOSSIBLE`, `UNSUPPORTED_HIERARCHY` |
| `get_context_delta` | Delta TOON entre un `base_snap` y el estado actual | `base_snap`, `focus_ref`, `radius_mm`, `max_tokens?` | delta | `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `CONTEXT_BUDGET_IMPOSSIBLE`, `PROJECT_NOT_FOUND`, `UNSUPPORTED_HIERARCHY` |

Notas de `get_world_context` (parámetro `kind`, sesión 09 D-09.1):

- `kind="sch"` (default, retrocompatible): ancla en el `.kicad_sch` raíz de
  disco (netlist vía kicad-cli + posiciones parseadas). Cabecera `SCH|…`.
  Multi-hoja → `UNSUPPORTED_HIERARCHY`. Es el path histórico.
- `kind="pcb"`: lee el **board VIVO** de KiCad en UNA pasada IPC
  (`read_board_context`), sin necesidad de haber mutado antes. Registra un
  snapshot vivo (`mtimes=None`, ADR-0007) y devuelve el TOON con `kind="pcb"`
  y el `snap_id` en la cabecera (`PCB|…|snap:N`) — el agente puede mutar o
  pedir `get_context_delta` inmediatamente con ese `snap_id` como `base_snap`.
- `focus_ref`/`radius_mm`/`max_tokens` aplican igual en ambos kinds: la
  cascada de degradación §4 es agnóstica del kind.
- **`focus_ref` sin `radius_mm` NO recorta (sesión 11, F-01).** El recorte por
  área es una palanca de degradación §4: sólo entra cuando el estado no cabe en
  `max_tokens` Y hay `focus_ref` **y** `radius_mm`. Pasar `focus_ref` solo (sin
  `radius_mm`) no recorta nada por sí mismo. Para que el agente sepa qué recibió,
  la cabecera lleva un indicador de área cuando se pidió foco: `area:full` si NO
  hubo recorte, `area:rN@ref` si sí. Sin `focus_ref` no hay token de área.
- **Cabecera pcb con geometría de board (sesión 11, F-03).** En `kind="pcb"` la
  cabecera incluye `bbox:minX,minY;maxX,maxY` (bbox del board) y
  `outline:none` | `outline:WxHmm` (contorno Edge.Cuts si existe; con contorno
  el bbox es el de Edge.Cuts, sin contorno es la envolvente tight de footprints).
  Los tokens opcionales van SIEMPRE **antes** de `snap:` (que permanece último):
  `PCB|v1|189c|588n|bbox:53.6,56.5;365.6,163.2|outline:312.0x106.7mm|area:full|snap:5`.
- Errores propios de `kind="pcb"`:
  - KiCad cerrado → `KICAD_NOT_RUNNING` (fast-fail del bridge, sin esperar
    el timeout de 2 s).
  - KiCad abierto pero **sin PCB Editor** → `KICAD_CLI_FAILED` con
    `data.ipc_status="unhandled"` (mapeo D-07.2); el hint dirige a abrir el
    PCB Editor.
  - `kind` distinto de `"sch"`/`"pcb"` → `INVALID_PARAMS`.
- Ejemplo `kind="pcb"` (board de prueba, cabecera):

  ```
  PCB|v1|202c|…|snap:5
  U19  <valor>  x… y…  1>… 2>… …
  …
  ```

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
| `run_drc` | DRC del PCB **presupuestado**: resumen por tipo (default) o detalle paginado | `min_severity?=warning`, `exclude_types?`, `detail_type?`, `offset?=0`, `limit?=20` | none | `INVALID_PARAMS`, `KICAD_CLI_FAILED`, `PROJECT_NOT_FOUND` |

**`run_erc`** — formato de violación: `{rule, severity, message,
items: [{ref?|net?|pos?}]}` — posiciones en **mm**.

**`run_drc` presupuestado (F-10, D-12.6).** La respuesta cruda medía 18 956 tok
/ 42 s (sesión 11, 47× el techo D4). Rediseño:

- **Modo default = RESUMEN.** Agrupa por tipo de violación, ordena por
  frecuencia, y por cada tipo emite `count`, `severity`, un `message`
  representativo y hasta **N=5 muestras** compactas (`pos` + `items` con los
  objetos/nets involucrados). Presupuesto verificado: **~1 491 tok con 608
  violaciones** (target ≤2 000 con 283 → cumplido con margen). Forma:
  `{mode:"summary", total, counts, coordinate_units, kicad_version, by_type:[{type,count,severity,message,samples}], hint}`.
- **`exclude_types`** (p. ej. `["unconnected_items"]`) y **`min_severity`**
  EXCLUYEN de verdad del payload (recomputan `total`/`counts`), no sólo ocultan.
- **Detalle paginado**: `detail_type=<tipo>` + `offset`/`limit` (1..100, default
  20) devuelve violaciones COMPLETAS de UN tipo por páginas
  (`{mode:"detail", type, total, offset, limit, returned, violations:[...], hint}`).
  Tipo inexistente → `total:0` + hint con los tipos disponibles.
- **Compatibilidad:** el Gate G3 (F2) **no** consume esta tool — corre
  `bridge.rules.run_drc` directo sobre el `RulesReport`, así que su semántica
  (conteo de errores) no cambia. `offset`/`limit` inválidos → `INVALID_PARAMS`.

## Categoría `export`

**Rutas absolutas en la respuesta (sesión 11, F-02).** TODAS las tools de
export devuelven la ruta ABSOLUTA final en `output_path` / `output_dir` (no el
basename relativo). El agente la lee directo sin un `ls`/`find` para ubicarla
(dogfooding F-02). Aplica también al confirm de `save_board`.

| Tool | Descripción | Parámetros | Refresh | Errores posibles |
|---|---|---|---|---|
| `export_manufacturing` | Gerbers + drill a directorio del proyecto. Gate G3 | `output_dir?=fab/` | none | `EXPORT_BLOCKED_BY_DRC`, `KICAD_CLI_FAILED`, `PATH_OUTSIDE_PROJECT`, `PROJECT_NOT_FOUND` |
| `export_bom` | BOM en CSV | `output_path?` | none | `KICAD_CLI_FAILED`, `PATH_OUTSIDE_PROJECT` |
| `export_netlist` | Netlist del esquemático | `output_path?` | none | `KICAD_CLI_FAILED`, `PATH_OUTSIDE_PROJECT` |
| `export_render` | Render del proyecto: sch_pdf, pcb_pdf o pcb_png (3D) | `kind: "sch_pdf"\|"pcb_pdf"\|"pcb_png"`, `output_path?` | none | `KICAD_CLI_FAILED`, `INVALID_PARAMS`, `PATH_OUTSIDE_PROJECT`, `PROJECT_NOT_FOUND` |

Notas de `export_render`:
- `sch_pdf` → PDF del esquemático (una hoja por página).
- `pcb_pdf` → PDF del PCB en modo single-page con capas por defecto
  `F.Cu, B.Cu, F.SilkS, B.SilkS, Edge.Cuts`. Aceptado desde v0.1.
- `pcb_png` → **render 3D REAL** del board vía `kicad-cli pcb render`
  (verificado presente en 10.0.4, sesión 09 D-09.3). **NO es un plano de
  capas** — es la vista 3D renderizada del board (propósito: feedback visual
  para el cliente MCP, que acepta imágenes, D-R5). Defaults fijos: vista
  `top`, proyección ortográfica, calidad `basic`, 1600×900. El CLI expone
  además `--perspective`, `--zoom`, `--rotate`, `--side`, etc.; su exposición
  como parámetros de la tool queda diferida (no se necesitó en el MVP). El
  formato lo fija la extensión de salida (`.png`). Respuesta: `{kind,
  output_path, bytes}` como los demás exports.

## Categoría `pcb` (v0.2 — primeras mutaciones, sesión 03)

Detrás del Gate G1 (backup + git checkpoint una vez por sesión) y con
audit line JSONL por cada mutación aceptada o rechazada.

| Tool | Descripción | Parámetros | Refresh | Errores posibles |
|---|---|---|---|---|
| `move_footprint` | Mueve un footprint del PCB a (x_mm, y_mm) | `ref`, `x_mm`, `y_mm`, `base_snap?` | confirm | `COMPONENT_NOT_FOUND`, `INVALID_PARAMS`, `KICAD_NOT_RUNNING`, `KICAD_TIMEOUT`, `KICAD_RESTARTED`, `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `PROJECT_NOT_FOUND` |
| `add_track` | Track lineal entre dos puntos **o** entre dos pads (`REF.PAD`) | `net`, `start_x_mm?`, `start_y_mm?`, `end_x_mm?`, `end_y_mm?`, `from_pad?`, `to_pad?`, `width_mm?=0.25`, `layer?="F.Cu"`, `base_snap?` | confirm | `NET_NOT_FOUND`, `COMPONENT_NOT_FOUND`, `INVALID_PARAMS`, `KICAD_NOT_RUNNING`, `KICAD_TIMEOUT`, `KICAD_RESTARTED`, `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `PROJECT_NOT_FOUND` |
| `add_via` | Via pasante en (x_mm, y_mm) asignada a un net | `x_mm`, `y_mm`, `net`, `size_mm?=0.8`, `drill_mm?=0.4`, `base_snap?` | confirm | `NET_NOT_FOUND`, `INVALID_PARAMS`, `KICAD_NOT_RUNNING`, `KICAD_TIMEOUT`, `KICAD_RESTARTED`, `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `PROJECT_NOT_FOUND` |
| `delete_track` | Borra la track/arco de un net más cercana a un punto | `net`, `near_x_mm`, `near_y_mm`, `base_snap?` | confirm | `NET_NOT_FOUND`, `INVALID_PARAMS`, `KICAD_NOT_RUNNING`, `KICAD_TIMEOUT`, `KICAD_RESTARTED`, `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `PROJECT_NOT_FOUND` |
| `delete_via` | Borra la via de un net más cercana a (x_mm, y_mm) | `net`, `x_mm`, `y_mm`, `base_snap?` | confirm | `NET_NOT_FOUND`, `INVALID_PARAMS`, `KICAD_NOT_RUNNING`, `KICAD_TIMEOUT`, `KICAD_RESTARTED`, `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `PROJECT_NOT_FOUND` |
| `save_board` | Persiste el board vivo del PCB Editor a disco | `base_snap?` | confirm | `PROJECT_NOT_FOUND`, `KICAD_NOT_RUNNING`, `KICAD_TIMEOUT`, `KICAD_RESTARTED`, `KICAD_CLI_FAILED`, `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED` |
| `get_component_detail` | Detalle de un footprint: posición, rotación, bbox/courtyard y pads absolutos | `ref`, `kind?="pcb"` | detail | `COMPONENT_NOT_FOUND`, `INVALID_PARAMS`, `PROJECT_NOT_FOUND`, `KICAD_NOT_RUNNING`, `KICAD_TIMEOUT`, `KICAD_RESTARTED` |
| `draw_board_outline` | Crea un contorno rectangular en Edge.Cuts | `x_mm`, `y_mm`, `width_mm`, `height_mm`, `base_snap?` | confirm | `INVALID_PARAMS`, `PROJECT_NOT_FOUND`, `KICAD_NOT_RUNNING`, `KICAD_TIMEOUT`, `KICAD_RESTARTED`, `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED` |

Respuestas de éxito son confirmaciones cortas (≤ 50 tokens, ADR-0004),
p. ej. `OK move_footprint R5 -> (102.5, 44.0) [snap:12]`.

Sesión 05 T5: el `snap` del confirm es el **snapshot post-mutación** que
registra la tool (vivo, ADR-0007). El agente lo usa como `base_snap` de la
próxima mutación encadenada; el `base_snap` pasado como parámetro se
preserva en `.kicad-mcp/audit.jsonl` para trazabilidad.

**Sesión 08 D-08.1/D-08.2 — pipeline rápido de mutaciones.** El pre-work
del tool (validación de refs, validación de bbox, localización del target)
se colapsa en UNA sola pasada `get_footprints()` vía la operación
compuesta interna del bridge (`read_board_context`). El post-snapshot se
DERIVA localmente aplicando la mutación conocida y se verifica por KIID
con `get_items_by_id` (filtrado del lado de KiCad, O(1) de red). Si la
verificación diverge de lo derivado (más allá de ±1 nm), la tool cae a
re-lectura completa (fallback) y loguea `post_snapshot_fallback`. El log
JSON de la tool incorpora `extra.read_ms` (pre), `extra.lookup_ms`
(escritura), `extra.verify_ms` (KIID) y `extra.post_fallback` cuando se
dispara.

Contrato de errores intacto: la superficie es la misma; solo cambia la
economía interna. Latencia medida contra el board de 202 refs: ~13.6 s
(sesión 07) → ~3.5 s (sesión 08), bajo el techo de 4 s de D-08.4.

**`add_via` (sesión 09, B3, D-09.3).** Crea una via **pasante** (through, drill
F.Cu→B.Cu) vía `kipy.board_types.Via` + `create_items` — el mismo pipeline
rápido que `add_track`. Validaciones pre-mutación: net existe
(`NET_NOT_FOUND` con similares), posición dentro del bbox (`INVALID_PARAMS`),
y `0 < drill_mm < size_mm` (`INVALID_PARAMS`: un drill ≥ diámetro es una via
imposible). Defaults sanos: `size_mm=0.8`, `drill_mm=0.4` (los clásicos de
KiCad). Post-estado: una via **no** vive en `NormalizedState` (que modela
footprints + pines), así que —igual que `add_track`— el estado post es
idéntico al pre y se DERIVA del snapshot leído (cero pasadas post, sin
verificación puntual por KIID). G1 + audit + confirm ≤50 tokens con
`snap_id`; sin retry en la escritura (D-07.1). Confirm:
`OK add_via GND @(150.0,80.0) d0.80/0.40 [snap:N]`.

**`draw_board_outline` (sesión 12, D-12.5).** Crea un contorno rectangular en
`Edge.Cuts` vía `kipy.board_types.BoardRectangle` + `create_items` — mismo
pipeline que `add_track`/`add_via` (verificado en vivo: create sube el conteo
de shapes Edge.Cuts y devuelve KIID). Superficie mínima: un rectángulo
(`x_mm, y_mm` esquina superior-izquierda + `width_mm, height_mm`); formas
complejas fuera de scope. Validaciones: dimensiones positivas
(`INVALID_PARAMS`), coords razonables (±10 000 mm), y **rechazo si ya existe
contorno** — usa la lectura `board_outline` (la cabecera `outline:` de la
sesión 11) para no apilar bordes (`INVALID_PARAMS` con hint). El contorno
**no** vive en `NormalizedState`, así que —igual que `add_track`— el post-estado
se DERIVA del snapshot vivo (mtimes=None). G1 + audit + confirm ≤50; sin retry
(D-07.1). El loop cierra con `save_board`. Confirm:
`OK draw_board_outline @(10.0,10.0) 80.0x60.0mm Edge.Cuts [snap:N]`.

**`save_board` (sesión 11, D-11.1).** Persiste el board vivo (mutado por IPC)
al `.kicad_pcb` de disco vía `Board.save()` (comando IPC `SaveDocument`).
Cierra el split-brain live/disco (dogfooding F-05): tras el save,
`export_render` / `run_drc` / `export_manufacturing` —que leen **disco** vía
kicad-cli— reflejan exactamente lo que el agente mutó. A diferencia de las
mutaciones IPC (que registran snapshots **vivos**, `mtimes=None`, ADR-0007),
`save_board` registra un snapshot de **disco** con `mtimes` frescos: disco y
vivo convergen y la cadena de snapshots lo refleja. G1 aplica. Sin retry en la
escritura (busy → se propaga). Confirm con ruta ABSOLUTA:
`OK save_board video.kicad_pcb -> /ruta/abs/video.kicad_pcb [snap:N]`.

**`delete_track` / `delete_via` (sesión 11, D-11.2, ADR-0010).** Borrado
dirigido de cobre **sin Gate G2** (el cobre es re-agregable en un call y está
protegido por G1+git; ver ADR-0010 para la asimetría con footprints). El
target se identifica por **coincidencia geométrica + net**: `delete_track`
borra la track/arco de ese net cuyo segmento pasa más cerca de
`(near_x_mm, near_y_mm)`; `delete_via` la via de ese net más cercana a
`(x_mm, y_mm)`. Tolerancia 0.5 mm. Ante **ambigüedad** (2+ candidatos dentro
de tolerancia) → `INVALID_PARAMS` con los candidatos en `data.candidates`
(posiciones/endpoints) para refinar — **nunca** se borra "el más cercano" a
ciegas. Nada dentro de tolerancia → `INVALID_PARAMS`. El borrado usa
`remove_items` sobre el KIID resuelto. Post-estado derivado del pre (el cobre
no vive en `NormalizedState`, patrón `add_track`); confirm ≤50 tok con snap.
Confirm: `OK delete_track GND @(150.0,80.0) [snap:N]`.

**`add_track` anclado a pads (sesión 11, D-11.4).** Parámetros alternativos
`from_pad` / `to_pad` con formato `"REF.PAD"` (p. ej. `"U1.8"`), **mutuamente
excluyentes** con las coordenadas crudas (`INVALID_PARAMS` si se mezclan, o si
falta uno de los dos pads). La resolución pad→coordenada absoluta usa la misma
lógica de `get_component_detail` (los pads ya vienen absolutos/rotados de
kipy). `REF` inexistente → `COMPONENT_NOT_FOUND`; `PAD` inexistente en ese
footprint → `INVALID_PARAMS` con los pads disponibles en el hint.

**`get_component_detail` (sesión 11, D-11.3).** Detalle geométrico de un
footprint **bajo demanda** (sale de reservados; ver más abajo). Devuelve, en
TOON compacto: posición y rotación del footprint, bbox (courtyard si el
footprint lo define, si no la envolvente de pads; `src:courtyard|pads`), y la
lista de pads con número, net, **posición ABSOLUTA** (ya rotada por kipy —
elimina la cuenta a mano del dogfooding F-04), tamaño y capa. Fuente: el board
vivo. `kind="pcb"` es lo soportado; `kind="sch"` → `INVALID_PARAMS` con hint
honesto (futuro). Presupuesto: un IC de ~30 pads ≈ ≤~350 tok; un conector de
75 pads (U19) ≈ ~900 tok; una R de 2 pads ≈ ~50 tok. Formato:
`DETAIL|U19|pcb|at:234.3,64.1|rot:0|bbox:115.9x8.1|box:...|src:courtyard`
seguido de `[PADS] N` y una línea `num net x,y WxH capa` por pad.

## Categoría `sch` (v0.2 — mutaciones de esquemático, sesión 08)

Superficie de mutación complementaria a `pcb`: opera sobre archivos
`.kicad_sch` con `kicad-skip`, no vía IPC. Mismo Gate G1 + audit JSONL.

| Tool | Descripción | Parámetros | Refresh | Errores posibles |
|---|---|---|---|---|
| `add_symbol` | Clona un símbolo (de la hoja, o de una paleta con `source`) y lo coloca con nueva ref | `sheet`, `lib_id`, `ref`, `x_mm`, `y_mm`, `base_snap?`, `source?` | confirm | `INVALID_PARAMS`, `PATH_OUTSIDE_PROJECT`, `PROJECT_NOT_FOUND`, `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `KICAD_CLI_FAILED` |
| `set_value` | Cambia el `Value` de un símbolo existente (localiza la hoja por ref) | `ref`, `value`, `base_snap?` | confirm | `INVALID_PARAMS`, `COMPONENT_NOT_FOUND`, `PROJECT_NOT_FOUND`, `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `KICAD_CLI_FAILED` |
| `set_footprint` | Asigna el `Footprint` (`lib:name`) de un símbolo existente | `ref`, `footprint_id`, `base_snap?` | confirm | `INVALID_PARAMS`, `COMPONENT_NOT_FOUND`, `PROJECT_NOT_FOUND`, `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `KICAD_CLI_FAILED` |
| `connect_pins` | Conecta dos pines (`REF.PIN`) por labels locales homónimos | `pin_a`, `pin_b`, `net_name`, `base_snap?` | confirm | `INVALID_PARAMS`, `COMPONENT_NOT_FOUND`, `PROJECT_NOT_FOUND`, `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `KICAD_CLI_FAILED` |

`connect_pins` — decisiones vinculantes (D-12.2):

1. **Semántica:** coloca un label LOCAL con nombre `net_name` en la posición
   absoluta de cada pin (`SymbolPin.location` de kicad-skip ya resuelve
   origen+offset+rotación). Dos labels locales homónimos netean los pines —
   práctica estándar de KiCad, verificada por netlist en el spike sesión 12.
2. **Scope de hoja:** los labels locales conectan sólo dentro de una hoja →
   `pin_a` y `pin_b` deben vivir en la MISMA hoja. Refs en hojas distintas →
   `INVALID_PARAMS` (labels globales/jerárquicos quedan fuera de scope).
3. **`net_name` obligatorio:** el agente LLM elige nombres significativos;
   autogenerar invita a basura. Vacío / mismo pin dos veces → `INVALID_PARAMS`.
   Pin inexistente en el símbolo → `INVALID_PARAMS` con los números disponibles.
4. **Caveat de prioridad:** si un pin ya carga un label global/jerárquico, el
   netlist real conserva ese nombre (prioridad global) y `connect_pins` sólo
   mergea los nets; sobre pines flotantes, el net resultante lleva `net_name`
   (con prefijo de sheet-path `/`). El snapshot derivado marca `net_name` en
   ambos pines — es una vista; el netlist es la verdad.
5. **Snapshot / G1 / audit / verificación:** idénticos a `add_symbol`. La
   verificación de efecto (D-06.3) re-lee la hoja y confirma un label
   `net_name` en cada posición.

Confirmación (≤ 50 tokens):
`OK connect_pins R1.2<->R2.2 net=I2C_SDA in fixture.kicad_sch [snap:5]`.

`set_value` / `set_footprint` — decisiones vinculantes (D-12.1):

1. **Localización por ref:** las refs son únicas por proyecto, así que ambas
   tools ubican la hoja del símbolo recorriendo todos los `.kicad_sch` del
   root (no piden `sheet`). Ref inexistente → `COMPONENT_NOT_FOUND` con
   refs similares por edit-distance.
2. **`set_footprint` valida FORMATO, no existencia:** exige `lib:name`
   (`^[A-Za-z0-9_.\-]+:[A-Za-z0-9_.\-]+$`) pero NO comprueba que la huella
   exista en las librerías del sistema (el MVP no tiene acceso). KiCad marca
   la huella faltante al asignar/actualizar el PCB. El agente elige nombres
   válidos; la responsabilidad de existencia es del humano/KiCad.
3. **Regla 6 (borde de escritura):** `value` y `footprint_id` se rechazan si
   traen caracteres de control/saltos de línea o exceden 40 chars
   (`INVALID_PARAMS`) antes de tocar disco. `value` vacío se rechaza. El
   encoder TOON re-sanitiza `value` al leerlo (§5), así que los caracteres
   estructurales no se rechazan en escritura (footprint lleva `:` legítimo).
4. **Snapshot / G1 / audit:** idénticos a `add_symbol` — G1 backup 1ª vez,
   verificación de efecto re-leyendo la hoja (D-06.3), snapshot de DISCO
   post-write con mtimes frescos (D-06.2). `set_value` deriva el post-estado
   reemplazando el `value` del Component; `set_footprint` no altera el
   `NormalizedState` (el footprint no se modela) pero registra igual un
   snapshot fresco para encadenar `base_snap`.

Confirmaciones (≤ 50 tokens):
`OK set_value R1 '10k'->'22k' in fixture.kicad_sch [snap:3]` ·
`OK set_footprint R1 ->Resistor_SMD:R_0805_2012Metric in fixture.kicad_sch [snap:4]`.

`add_symbol` — decisiones vinculantes (D-08.5, ampliadas por D-12.3):

1. **Librería**: clonado desde un símbolo/template ya instanciado. Fuente
   (`source`, D-12.3): explícito > `paleta.kicad_sch` en la raíz si existe >
   la hoja destino (clone intra-archivo, comportamiento histórico si no hay
   paleta). El clone **cross-file** copia la definición de librería (dedup si
   el destino ya la tiene) y anexa una instancia con ref/uuid/posición nuevos
   vía el árbol S-expr crudo (kicad-skip bloquea el clone entre archivos por
   sus wrappers; spike sesión 12 lo verificó a nivel de árbol). `source`
   inexistente → `PROJECT_NOT_FOUND`; `lib_id` ausente en la fuente →
   `INVALID_PARAMS` con los lib_ids disponibles. La `paleta.kicad_sch` es un
   archivo SEPARADO (no parte de la jerarquía de diseño): sus refs de template
   NO cuentan como colisión ni aparecen en hints de hojas. Ver
   `docs/guia-paleta.md`. Pick desde librerías del SISTEMA sigue fuera de scope.
2. **Cableado**: `add_symbol` **coloca**, no conecta. El símbolo nuevo
   sale con todos sus pines como `net=None` (§2 TOON: `">-"`). Conexión
   de pines en `connect_pins` (v0.5).
3. **Superficie**: toca SOLO el `.kicad_sch` indicado. No genera
   footprint ni toca el `.kicad_pcb`. La re-anotación/sync sch↔pcb la
   hace KiCad (F5 → File → Update PCB from Schematic o similar).
4. **Snapshot Store**: registra un snapshot de DISCO post-write con
   `mtimes` frescos del proyecto (D-06.2). El patrón vivo
   (`mtimes=None`) es exclusivo de mutaciones IPC. El `snap_id` del
   confirm es válido como `base_snap` de la próxima mutación.

Confirmación de éxito (≤ 50 tokens): `OK add_symbol R99 FIXLIB:R2
@(175.0,60.0) in fixture.kicad_sch [snap:1]`.

**Hazard del editor abierto (documentado, no resuelto en MVP).** Si el
usuario tiene el `.kicad_sch` abierto en KiCad al momento de la
mutación, KiCad detectará el cambio en disco cuando vuelva a la ventana
y le mostrará "El archivo cambió en disco, ¿recargar?". Cerrar el
archivo en KiCad antes de mutar es la práctica segura; sync sch↔pcb en
KiCad exige que el usuario haga la re-anotación.

Validaciones pre-mutación:

- Ref sanitizada (regla 6): `^[A-Za-z][A-Za-z0-9_]{0,14}[0-9]$`, ≤16
  chars. Refs con backticks, pipes, espacios o chars de control se
  rechazan con `INVALID_PARAMS` antes de tocar disco.
- Ref sin colisión en NINGUNA hoja del proyecto (recorre todos los
  `.kicad_sch` del root). Colisión → `INVALID_PARAMS` + hint con la hoja
  donde ya vive el ref.
- `lib_id` instanciado en la hoja destino. Si no, `INVALID_PARAMS` con
  hint listando los primeros 5 lib_ids disponibles.
- Coordenadas dentro del bbox de la hoja (bounding box de los símbolos
  existentes + 200 mm de margen). Fuera → `INVALID_PARAMS`.
- `base_snap` opcional: mismo contrato que las tools de `pcb`
  (`SNAPSHOT_STALE` / `EXTERNAL_EDIT_DETECTED`).

Verificación de efecto (D-06.3): re-lee el archivo escrito con
`kicad-skip` y confirma que el símbolo aparece con el `lib_id` y las
coordenadas pedidas (tolerancia 1e-3 mm). Divergencia → `KICAD_CLI_FAILED`
(bug interno, mutación quedó en estado inconsistente).

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

v0.2: `place_footprint`, `add_zone` (los ya implementados —`move_footprint`,
`add_track`, `add_via`, `add_symbol`, `set_value`, `set_footprint`,
`connect_pins`, `draw_board_outline`— se mueven a las secciones `pcb` y `sch`).

`reload_in_gui` — **no factible en KiCad 10 (diferido a KiCad 11).** La IPC de
esquemático (documento + `revert()`) es `versionadded 0.7.0 (KiCad 11)`; el
objeto `KiCad` de esta versión no expone reload agnóstico del editor y KiCad
10.0.4 responde `no handler available` a peticiones de documento de tipo
schematic (spike sesión 12, D-12.4). El hazard "tras mutar el sch con KiCad
abierto, el humano acepta el aviso de recarga" queda documentado
(`docs/guia-paleta.md`); no se construye nada.
v0.3: `get_session_summary`, `checkpoint` (el ya implementado
`get_context_delta` se mueve a la categoría `world`).
v0.4: `suggest_positions`, `route_with_freerouting`.

**Consultas de detalle (D-09.4 / D-R7 — reservadas, no implementadas):**
`get_net_detail`, `list_unconnected`. Se implementan **sólo** si el dogfooding
demuestra que el agente las necesita. `get_component_detail` SALIÓ de reservados
en la sesión 11 (D-11.3, D-R9): el dogfooding demostró la necesidad (F-04/F-06/
F-07 exigían parsear el `.kicad_pcb` crudo para obtener pads absolutos); ahora
vive en la categoría `pcb`.

Reservarlos ahora evita que el agente invente nombres divergentes en prompts,
docs o tests intermedios.

**Eliminada del diseño (no reservada):** `discover_tools` / router por
categorías. Resolvía "100+ schemas queman la ventana"
(`arquitectura.md §4.1`), pero este server expone ~13 tools y el roadmap
realista suma <10 más: 12-13 tools no justifican un router (D-R7,
`ADR-0009 §nota relacionada`). Nunca se escribió código; se retira del
catálogo para no prometer una superficie que no existe.

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
