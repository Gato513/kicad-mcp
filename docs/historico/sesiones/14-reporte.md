# Sesión 14 — `route_board`: autorouting en producción

**Rama:** `sesion-14` · **Fecha:** 2026-07-13 · KiCad 10.0.4 (IPC + cli vivos),
Java 21, Freerouting 2.1.0, `pcbnew` del python del sistema (3.14.6).

## Resumen

Se integró `route_board`: la tool de autorouting headless con Freerouting
(ADR-0011). Envuelve el round-trip Specctra DSN/SES del spike D-R11 en un runner
tipado (`bridge/autoroute.py`), maneja el split-brain disco↔editor-vivo con un
flag `live_stale` (D-14.1), y cierra el **paso 7** del flujo end-to-end de 9
pasos. Test real end-to-end verde contra una copia del proyecto de spike (24 fp,
64 conexiones): **100 % del ratsnest ruteado, 0 errores DRC**. `unit+golden`,
`integration_gui_slow`, `mypy strict` y `ruff` limpios.

## Fase 0

Verificador: 18 OK · 3 WARN · 0 FAIL (los WARN preexistentes: IPC probe degrada
por proyecto no instalado → resuelto con `uv sync`; npx ausente). Los tres
requisitos de sistema del ruteo, **presentes**: Java 21.0.11, jar en
`KICAD_MCP_FREEROUTING_JAR`, `pcbnew` importable con `/usr/bin/python3` → 10.0.4.
Se agregaron al verificador (D-14.5): con los tres OK imprime "flujo de
autorouting disponible".

## Entregables

- **T1** `src/kicad_mcp/bridge/autoroute.py` — runner del round-trip (3
  subprocesos: export DSN / freerouting / import SES) con timeouts, captura de
  stderr para hints, tipos primitivos afuera, errores taxonomía y log JSON con
  `export_ms/route_ms/import_ms`. Scripts `pcbnew` promovidos del spike, embebidos
  como texto para `python3 -c` (evita que mypy/ruff liten código sobre un módulo
  ausente en el venv). 11 tests unit con subprocess fakeado.
- **T2** `route_board` (en `tools/pcb.py`) + flag `live_stale` en el store +
  `confirm_reloaded` en `get_world_context` + guard `EXTERNAL_EDIT_DETECTED` en
  las 6 tools afectadas. `bridge.rules` gana `RulesReport.unconnected` (ratsnest).
  `bridge.ipc` gana `get_open_board_path` (save implícito seguro). Catálogo al
  día. 14 tests unit (todas las ramas del flag + la tool con runner fakeado) + 1
  test de ciclo del flag en el store.
- **T3** `tests/test_route_board_gui_slow.py` — round-trip real (marker
  `integration_gui_slow`).
- **T4** ADR-0011, catálogo, `pruebas-gui.md §recarga post-route`,
  `guia-paleta.md §flujo de 9 pasos`, verificador (D-14.5), este reporte.

## 1. Confirm literal del `route_board` real (T3) + latencia

```
OK route_board 64/64 nets +327 tracks +26 vias drc_err=0 [snap:1]
```

Log JSON de la tool (run real, board de spike, contorno dibujado en setup):

```json
{"tool_name":"autoroute_runner","export_ms":1040.9,"route_ms":121700.8,"import_ms":1058.9,"tracks_added":327,"vias_added":26}
{"tool_name":"route_board","snap_id":1,"tokens_est":18,"latency_ms":171128.6,"export_ms":1040.9,"route_ms":121700.8,"import_ms":1058.9,"live_saved":false,"drc_err":0}
```

- **Router (`route_ms`): ~121.7 s** — domina, como anticipó el spike.
- export/import (`pcbnew` del sistema): ~1.0 s cada uno (arranque del intérprete
  + LoadBoard/Save; en el spike, con el intérprete ya caliente, eran 0.02 s).
- Diferencia `latency_ms − route_ms` (~48 s): los **dos DRC** de disco (pre-route
  para el ratsnest total, post-route para el conteo de errores) vía `kicad-cli`,
  ~20–24 s cada uno, + G1 + reemplazo atómico.
- `live_saved:false` — correcto: el board abierto en KiCad (gui-test-project) NO
  es el target (la copia de spike) → save implícito **omitido** (D-14.3, seguro).
- **100 % del ratsnest** (64/64), **0 errores DRC**. El conteo de tracks/vías
  varía por corrida (router estocástico: 318–348 en el spike, 327 acá) — el
  resultado es equivalente y limpio.

## 2. Test del flag (mutación bloqueada + destrabe)

Del test real (T3) y de los unit (`test_route_board.py`):

- Post-route, `store.is_live_stale()` es `True`.
- `move_footprint({"ref":"U1",...})` → **`EXTERNAL_EDIT_DETECTED`** con hint "el
  disco tiene el ruteo y el editor vivo no; recargá el board en KiCad
  (File→Revert) y confirmá con `get_world_context(kind='pcb',
  confirm_reloaded=true)`". Igual para `add_track`/`add_via`/`delete_track`/
  `delete_via`/`save_board` (parametrizado).
- `get_world_context(kind='pcb', confirm_reloaded=true)` → limpia el flag;
  `is_live_stale()` pasa a `False` y el TOON sale **sin** la línea `[AVISO]`.
- Con el flag activo y sin `confirm_reloaded`, la lectura viva **funciona** y el
  TOON empieza con `[AVISO] editor vivo detras del disco (route_board)`.
- Lecturas de disco/sch (`get_world_context(kind='sch')`) inmunes: ni bloqueo ni
  aviso.

## 3. Mapeo de errores D-14.4 (fallo → código → hint)

| Fallo | Código (F3, existente) | Hint / `data` |
|---|---|---|
| jar ausente (env no seteada o ruta inexistente) | `KICAD_CLI_MISSING` | exportá `KICAD_MCP_FREEROUTING_JAR` · `data.requirement="freerouting_jar"` |
| java ausente | `KICAD_CLI_MISSING` | instalar Java ≥17 · `data.requirement="java"` |
| `pcbnew` no importable (python sistema) | `KICAD_CLI_MISSING` | KiCad completo trae pcbnew · `data.requirement="pcbnew"` |
| export DSN falla (sin Edge.Cuts) | `KICAD_CLI_FAILED` | "dibujá el contorno con draw_board_outline" · `data.reason="no_edge_cuts"` |
| Freerouting exit≠0 / SES vacío | `KICAD_CLI_FAILED` | tail del log · `data.stage="freerouting"` |
| Freerouting timeout | `KICAD_TIMEOUT` | subí `timeout_s` · `data.timeout_s` |
| import SES falla | `KICAD_CLI_FAILED` | stderr · `data.stage="import_ses"` |

Argumento: los tres "ausentes" son la clase de `KICAD_CLI_MISSING` (herramienta
externa requerida y ausente, no reintentable, con instrucción de instalación);
`data.requirement` distingue cuál. Los fallos de subprocess son
`KICAD_CLI_FAILED` (herramienta externa que devolvió error, como los wrappers de
`kicad-cli`). El timeout del router es `KICAD_TIMEOUT` por decisión del
arquitecto. **Cero códigos nuevos** (F3 intacta).

## 4. Tokens del confirm y promedios

- **Confirm de `route_board`: 18 tokens** (`tokens_est`), muy por debajo del
  techo ≤50 (ADR-0004).
- Los reads (`get_world_context`) siguen bajo su presupuesto ≤400 salvo cuando
  el board abierto es grande (189 fp de gui-test-project → `CONTEXT_BUDGET_
  IMPOSSIBLE` con el default de 800; el agente sube `max_tokens` o acota con
  `focus_ref`+`radius_mm`, comportamiento preexistente, no de esta sesión).

## 5. Flujo de 9 pasos (estado)

Tabla 1.3 (`ANALISIS-ESTADO-Y-BACKLOG.md`) actualizada de facto: el **paso 7
(rutear)** pasa de "Parcial (`add_track`)" a **automatizado por `route_board`**
(100 % del ratsnest, 0 shorts). Quedan en manos humanas **sólo**:

- **Paso 1** — crear/abrir el proyecto (`KICAD_MCP_PROJECT` asume proyecto
  existente).
- **Paso 5** — sync sch→pcb (F8 Update PCB from Schematic): no automatizable en
  KiCad 10 (kicad-cli no tiene update; IPC sch es KiCad 11).

El **paso 8** gana una micro-acción humana de segundos (recargar el board tras
`route_board`, File→Revert) — no es un paso de diseño; el ruteo ya está correcto
en disco. Ver `guia-paleta.md §flujo de 9 pasos`.

## 6. Checklist de preparación del Dogfooding 2 (sesión 15)

Requisitos de **sistema** para el flujo con ruteo (verificados por D-14.5):

- [ ] **Java ≥17** en PATH (`java -version`). Presente: 21.0.11.
- [ ] **`KICAD_MCP_FREEROUTING_JAR`** exportada y apuntando a un `freerouting.jar`
      existente. Presente: 2.1.0 (del plugin de KiCad).
- [ ] **`pcbnew` del python del SISTEMA** (`/usr/bin/python3 -c "import pcbnew"`).
      Presente. Si en otra máquina vive en otro intérprete: `KICAD_MCP_SYSTEM_PYTHON`.

Preparación del proyecto y del entorno:

- [ ] El board a rutear tiene **contorno `Edge.Cuts`** — si no, `route_board`
      falla con hint a `draw_board_outline` (D-14.4). El agente debe dibujarlo
      (paso 6) antes de rutear (paso 7).
- [ ] KiCad abierto con el **PCB Editor del proyecto target** cargado si se
      quiere el `save_board` implícito (live→disco). Si el target no está abierto,
      `route_board` igual rutea la copia de disco (save implícito omitido).
- [ ] Tras `route_board`, **recargar el board** (File→Revert) + confirmar con
      `get_world_context(confirm_reloaded=true)` **antes** de retocar con
      `add_track`/`move_footprint`/`save_board` (el flag los bloquea si no).
- [ ] `KICAD_MCP_GUI_TEST=1`, `KICAD_MCP_PROJECT`, socket IPC vivo (Fase 0).

Presupuesto de tiempo: el ruteo domina (~2 min en placa media; escala peor con
densidad). Para el board grande del Dogfooding 2, medir `route_ms` y ajustar
`timeout_s` (default 600 s).

## 7. Dudas abiertas

1. **Densidad alta.** El spike/test validó densidad media (24 fp). Freerouting
   escala peor; para 60+ fp puede no llegar al 100 % o tardar más. Punto de
   medición del Dogfooding 2 — si reprueba, evaluar perfiles de Freerouting
   (`max_passes`/`quality`, hoy passthrough sin tunear) o ruteo por zonas
   (diferido).
2. **`track_dangling`.** El router deja 5–7 stubs (warnings, no bloquean G3). Si
   el Dogfooding 2 los reporta como ruido, un cleanup opcional post-route con
   `delete_track` (o exponerlos en el confirm) es barato.
3. **Deprecación de `pcbnew` SWIG.** Anclados a KiCad 10 (F4) no bloquea; si el
   objetivo salta a KiCad 11+, planear la migración del round-trip fuera de SWIG
   (la IPC de board podría ganar Specctra en versiones futuras — monitorear).
4. **`confirm_reloaded` es una aserción del agente, no una verificación.** El
   server confía en que el humano recargó. Detección automática de recarga
   (mtime del board vivo vs disco) queda fuera de scope; si el Dogfooding 2
   muestra que el agente confirma sin recargar, endurecerlo.
