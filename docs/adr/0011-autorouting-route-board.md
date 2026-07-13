# ADR-0011 — `route_board`: autorouting headless con Freerouting

**Fecha:** 2026-07-12 · **Estado:** aceptado · **Fuente:** sesión 14
(D-14.1..D-14.5, spike D-R11/sesión 13)

## Contexto

El Dogfooding Etapa 1 midió que el ruteo manual por `add_track` de un agente
LLM llega a **~22 % del ratsnest con 13 shorts** y deja el board peor
(irreversible). El spike D-R11 (sesión 13, `scratchpad/spike-autoroute/`)
demostró un camino de autorouting **headless, sin humano**: sobre una placa
real (24 fp, 64 conexiones) **Freerouting** rutea el **100 % del ratsnest con 0
errores DRC** en ~2 min y a costo de **1 llamada de herramienta** (el router no
habla con el LLM). El veredicto fue **INTEGRAR**. Esta ADR fija las decisiones
de la tool de producción `route_board`.

El motor es Freerouting (jar, subprocess java) vía round-trip **Specctra
DSN/SES** con el módulo **`pcbnew` SWIG del python del SISTEMA** (el que instala
KiCad). `kicad-cli` no hace el round-trip (no expone Specctra) y la IPC de KiCad
10 no expone el router interno — ambos descartados con evidencia en el spike.

## Decisión

### D-14.1 — split-brain: la cadena viva queda obsoleta post-route

`route_board` escribe el ruteo a **DISCO**; el board vivo de KiCad queda detrás.
El peligro no es cosmético: una mutación IPC + `save_board` posteriores
**pisarían el ruteo con cobre viejo**. Mecanismo obligatorio:

- `route_board` setea un flag de store `live_stale=True` y registra un snapshot
  de DISCO post-route.
- Con `live_stale` activo, `move_footprint`, `add_track`, `add_via`,
  `delete_track`, `delete_via` y `save_board` **FALLAN** con
  `EXTERNAL_EDIT_DETECTED` (código existente, F3 intacta: el disco cambió por
  fuera del editor vivo). Hint: "el disco tiene el ruteo y el editor vivo no;
  recargá el board en KiCad (File→Revert) y confirmá con
  `get_world_context(kind='pcb', confirm_reloaded=true)`".
- `get_world_context(kind="pcb", confirm_reloaded=true)` (parámetro nuevo,
  default `false`) limpia el flag. Con el flag activo y **sin** `confirm_reloaded`,
  la lectura viva **funciona** pero el TOON lleva una primera línea
  `[AVISO] editor vivo detras del disco (route_board)`.
- Las tools de **DISCO** (`run_drc`, `export_render`, `export_manufacturing`,
  tools `sch`) NO se bloquean: leen el estado correcto (el ruteo ya está en
  disco).

### D-14.2 — sin gate interactivo

`route_board` **no** dispara un gate interactivo (coherente con D-R8/ADR-0010:
es cobre re-ruteable; G1 + git protegen el peor caso). Obligatorio: **G1**
backup pre-route, **audit JSONL**, y confirm con conteos (≤50 tokens):
`OK route_board 64/64 nets +318 tracks +26 vias drc_err=0 [snap:N]`, donde
`X/Y` = conexiones del ratsnest resueltas / total pre-route (del `unconnected`
del DRC de disco).

### D-14.3 — superficie y pipeline

`route_board(max_passes: int | None = None, timeout_s: int = 600)`. Pipeline
interno: `save_board` implícito (live→disco, **sólo si el board abierto ES el
target** — se compara `document.project.path`/`board_filename` vía IPC; nunca se
guarda un board de otro proyecto) → DRC pre-route (ratsnest total) → export DSN
(subprocess `pcbnew` del sistema) → Freerouting jar headless (subprocess java,
timeout → `KICAD_TIMEOUT`) → import SES + SaveBoard (subprocess `pcbnew`) →
**reemplazo atómico** del `.kicad_pcb` → DRC post-route (`bridge.rules`, como G3)
para el conteo de errores → snapshot de disco → flag D-14.1 → confirm. Los
subprocesos usan el python del **SISTEMA** (`/usr/bin/python3` por default,
overridable con `KICAD_MCP_SYSTEM_PYTHON`), **NUNCA** el venv del proyecto
(`pcbnew` no es dependencia de `pyproject`, F5). El router corre como subprocess,
no por IPC: no toca la cola IPC de profundidad 1 (contención D-12.7 intacta).

A diferencia del spike, el export **NO dibuja el contorno** automáticamente: un
board sin `Edge.Cuts` FALLA con hint accionable (`draw_board_outline`) — la tool
de producción no muta el contorno en silencio.

### D-14.4 — errores tipados del pipeline (F3: cero códigos nuevos)

| Fallo | Código | Hint / `data` |
|---|---|---|
| jar ausente (`KICAD_MCP_FREEROUTING_JAR` no seteada o ruta inexistente) | `KICAD_CLI_MISSING` | export la env al freerouting.jar · `data.requirement="freerouting_jar"` |
| java ausente | `KICAD_CLI_MISSING` | instalar Java ≥17 · `data.requirement="java"` |
| `pcbnew` no importable (python del sistema) | `KICAD_CLI_MISSING` | KiCad completo trae pcbnew · `data.requirement="pcbnew"` |
| export DSN falla (típico: sin Edge.Cuts) | `KICAD_CLI_FAILED` | "dibujá el contorno con draw_board_outline" · `data.reason="no_edge_cuts"` |
| Freerouting exit≠0 / SES vacío | `KICAD_CLI_FAILED` | tail del log · `data.stage="freerouting"` |
| Freerouting timeout | `KICAD_TIMEOUT` | subí timeout_s / reducí densidad · `data.timeout_s` |
| import SES falla | `KICAD_CLI_FAILED` | stderr · `data.stage="import_ses"` |

**Argumento del mapeo:** los tres "ausentes" (jar/java/pcbnew) son la misma
clase que `KICAD_CLI_MISSING` cubre para `kicad-cli` — herramienta externa de
sistema requerida y ausente, no reintentable, con instrucción de instalación; el
`data.requirement` distingue cuál. Los fallos de subprocess (export/import/
router-exit) son `KICAD_CLI_FAILED` (herramienta externa que devolvió error),
igual que los wrappers de `kicad-cli`. El timeout del router es `KICAD_TIMEOUT`
por decisión explícita del arquitecto (reúsa el código de "operación excedió su
tiempo" sin renombrar F3). Cero códigos nuevos.

### D-14.5 — requisitos de sistema en el verificador

`scripts/verificar_entorno.py` gana tres checks **WARN-level** (no bloquean
sesiones que no rutean): `java -version` ≥17, jar en
`KICAD_MCP_FREEROUTING_JAR` existente, `python3 -c "import pcbnew"` con el python
del SISTEMA. Con los tres OK imprime "flujo de autorouting disponible". Estos
requisitos son de **sistema** (estilo `kicad-cli`), **no** de `pyproject` (F5).

## Consecuencias

- El paso 7 (rutear) del flujo end-to-end de 9 pasos queda **automatizado**:
  sólo los pasos 1 (crear/abrir proyecto) y 5 (F8 sync sch→pcb) siguen siendo
  humanos en KiCad 10 (ver `guia-paleta.md §flujo de 9 pasos`).
- `add_track`/`add_via`/`delete_track` bajan a **retoque puntual** post-ruteo;
  el autorouter es el camino primario del ruteo.
- La recarga post-route es manual (D-14.1): KiCad 10 no expone reload
  programático (D-12.4). El protocolo vive en `pruebas-gui.md §recarga
  post-route`.

## Riesgos / diferidos

- **`pcbnew` SWIG está en camino de deprecación** anunciado por KiCad a favor de
  la IPC API. Hoy (KiCad 10) sigue empaquetado y funciona (F4 nos ancla a 10).
  Si el objetivo apunta a KiCad 11+, planear la migración del round-trip fuera
  de SWIG.
- **Freerouting escala peor con densidad.** El spike validó densidad media (24
  fp). Para el rango alto (60+ fp, muchas señales cruzadas) puede no llegar al
  100 % o tardar más — punto de medición del Dogfooding 2.
- **Tuning de perfiles** (`max_passes`, `quality`) queda fuera de scope: el
  default de Freerouting alcanzó 100 %/0 errores. `max_passes` se expone como
  passthrough opcional, validado sólo el default en el test real.

## Alternativas descartadas

- **Subir la inteligencia de `add_track`** (anclaje a pads, rechazo de shorts,
  clearance-check) para ruteo LLM viable: reconstruir medio DRC dentro de la
  tool para llegar, con suerte, a lo que Freerouting da gratis en 2 min. No se
  justifica (spike §5).
- **Gate interactivo (G2-like) previo al ruteo:** es cobre re-ruteable con
  G1+git detrás; el gate reintroduce al humano en cada ciclo. Descartado por
  D-14.2.
- **Auto-dibujar el contorno** (como el spike): la tool de producción no muta el
  `Edge.Cuts` en silencio; falla con hint a `draw_board_outline` (D-14.4).
