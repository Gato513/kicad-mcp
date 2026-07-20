# CONTEXT.md v2 — kicad-mcp (post-sesión 17, 2026-07-20)

**Handoff destilado. Reemplaza a CONTEXT.md v1.** 17 sesiones de desarrollo,
2 dogfoodings, 1 hoja de ruta v3 en ejecución. Este documento es la conversación:
si alguien abre un nuevo chat, esto es todo lo que necesita para tomar el rol.

---

## Estado en una línea

Servidor MCP para operar KiCad autónomamente desde Claude Code. 17+ tools productivas,
loop de escritura PCB cerrado (esquemático → colocación → contorno → ruteo → DRC →
gerbers), autorouter Freerouting integrado con reglas del proyecto que ahora SÍ
viajan al DSN. Última sesión de dogfooding real (D2, 24 componentes, ATtiny85 wearable):
7.5/10 con placa fabricable. Objetivo v3: Dogfooding 3 con nota ≥8 tras cerrar P3
(recarga programática) y P4 (zonas).

**Rama vigente:** `sesion/17-route-board-robusto` (6 commits, listo para rebase sobre
master y merge). `sesion/16-get-tracks` pendiente de merge previo.

**Estás por arrancar:** sesión 18 (P3, recarga programática post-route).

---

## Rol

Arquitecto senior + revisor técnico crítico. NO escribo código. Diseño, decido,
audito, genero prompts de sesión. Vinculante en decisiones, no en implementación.
Los prompts los ejecuta un agente de Claude Code sobre el repo.

Reglas de operación (heredadas del v1, vigentes):
1. Respetar decisiones del CONTEXT o cuestionarlas con evidencia nueva.
2. Mantener el nivel de profundidad técnica.
3. Nueva evidencia > decisiones previas cuando hay contradicción.
4. Cronología importante: algunas decisiones fueron revocadas/ampliadas.

**Nueva regla vinculante para mí (D-V3.6, ver abajo):** los briefs de dogfooding
se generan con las tools del propio server, nunca se redactan desde texto. Tres
fricciones del D2 (F-01, F-04, F-07) fueron mías porque violé esto.

---

## Cronología condensada

| Sesión | Contenido | Cierre |
|---|---|---|
| 1–10 | Bootstrap del server, tools básicas, TOON encoder, primer dogfooding (D1 → 5/10) | Ver v1 |
| 11 | Tools de PCB v1 (add_track, delete_track por coords, add_via) | Merge |
| 12 | Cirugía escrituras, guards live_stale/EXTERNAL_EDIT_DETECTED, split-brain descubierto (D-12.4: reload_in_gui imposible en KiCad 10) | Merge |
| 13 | Spike Freerouting (24 componentes, 100%, ~2min) | Merge |
| 14 | Integración `route_board` productiva, D-14.1 (flag `live_stale`), D-14.2 (confirm ≤50 tok) | Merge |
| **15** | **Dogfooding 2**: despertador_inteligente ATtiny85 wearable, 24 fp | **7.5/10** |
| **16** | P1: `get_tracks` + `delete_track(id=)` + `add_track` mixed endpoints + collision SDF | Merge pendiente |
| **16b** | Fix tests integration_gui + descubierto bug real de `get_copper_by_kiid` | Rama misma que 16 |
| **17** | P2.0 fix bug + P2.1 reglas al DSN + P2.2 route_board contrato JSON + P2.5 DRC pos + fixture | Listo para merge |
| 18 | **Siguiente**: P3 recarga programática post-route | Prompt pendiente |
| 19 | P4 zonas / plano GND | — |
| 20 | Dogfooding 3 con sch corregido | Objetivo ≥8/10 |

---

## Decisiones de arquitectura vigentes

Las que están **modificadas** o **revocadas** por evidencia posterior lo dicen
explícito. En caso de conflicto entre CONTEXT v1 y este, gana este.

### Modificadas por evidencia del Dogfooding 2 (hoja de ruta v3)

- **D-V3.1** (revoca parte de D-R2/D-14.1): el revert humano post-route deja de
  ser aceptable como costo fijo. El D2 tuvo 3 reverts, no 1. Recarga programática
  vía IPC es la meta de la sesión 18.
- **D-V3.2**: TOON no crece; `get_tracks` es la nueva vista de cobre (implementada
  en sesión 16, funciona).
- **D-V3.3**: selección por KIID reemplaza desambiguación por radio en delete_track
  (sesión 16, funciona).
- **D-V3.4**: `route_board` deja de ser caja negra. Contrato JSON con `route_ms`,
  denominador correcto, causas de nets bloqueadas, DRC pre/post (sesión 17, cerrado
  parcialmente: F-12 quedó con causa mínima honesta, A* diferido a 17b).
- **D-V3.5**: reglas del board viajan al DSN de Freerouting. **Descubrimiento
  no anticipado**: netclasses ya viajaban automáticamente vía `pcbnew.LoadBoard`;
  edge clearance necesitó ingeniería inversa de bytecode (ver §Hallazgos técnicos).
- **D-V3.6** (proceso, vinculante para el arquitecto): los briefs se generan con
  tools, no se redactan. Dimensiones vía `get_component_detail`, estado ERC vía
  `run_erc` real, paths verificados con `ls`.

### Vigentes sin cambios desde v1

- D-08 (persistencia IPC como bug conocido — sigue igual, workaround estable)
- D-09.1 (TOON `snap:N`)
- D-12.3 (clone cross-file con pendiente conocido del bloque `(instances)`)
- D-12.4 (reload_in_gui imposible en KiCad 10 vía IPC; ver también D-V3.1)
- D-14.1 (flag `live_stale` funciona — validado en sesión 16, evitó pisar cobre)
- D-14.2 (confirm ≤50 tok) — **excepción documentada**: `route_board` rompe este
  contrato con su JSON estructurado, decisión explícita en tool-catalog.md
- D-R3 (autorouting > ruteo manual por LLM)
- D-R8 (asimetría delete_track sí / delete_footprint no — sigue abierta)

### Nuevas de sesión 16-17

- **D-16.1**: `id` en tools de cobre = KIID nativo de KiCad, no hash. Invalidado
  tras cualquier mutación de cobre o recarga. Agente debe re-listar.
- **D-16.2**: `add_track` acepta pad y coordenada por endpoint independiente. La
  exclusión pad↔coord es por endpoint, no global.
- **D-16.3**: validación de colisión con pads modela roundrect/circle/oval exacto
  vía SDF. NO valida contra tracks — el DRC es el oráculo para tracks.
- **D-16.4** (superseded por P2.1): `add_track` collision con clearance piso 0.2mm.
  **Ya obsoleta**: desde sesión 17 usa el clearance real de la netclass del track.
- **D-17.1**: `route_board` devuelve JSON estructurado (rompe D-14.2 conscientemente).
- **D-17.2**: causa de nets bloqueadas es heurística mínima honesta ("sin camino
  aparente"), no A* de bloqueador concreto. A* diferido a 17b si un dogfooding
  ejercita la ruta.

---

## Tools productivas (inventario actualizado)

**Lectura de mundo:**
- `health()` — estado del server, IPC, proyecto (sigue con la limitación de no
  distinguir "no configurado" de "path no existe" — F-02 abierta)
- `get_world_context(kind, focus, budget)` — TOON, sin tracks (por D-V3.2)
- `get_component_detail(ref)` — pads, courtyard, absolutos
- `get_tracks(net=|bbox=|layer=, max_tokens=)` — **sesión 16**, con KIIDs
- `run_erc()` — sigue con bug F-03 (posiciones ÷100) abierto

**Escritura de esquemático (paleta):**
- `add_symbol`, `set_value`, `set_footprint`, `connect_pins`, `clone_symbols`

**Escritura de PCB:**
- `draw_board_outline` — sigue inmutable (F-06 abierta)
- `move_footprint` — sin rotación aún; bbox ahora considera Edge.Cuts (fix sesión 16)
- `add_track` — endpoints mixed (D-16.2), collision SDF (D-16.3), clearance real (P2.1)
- `add_via`, `delete_track(id=|coords)`, `delete_via(id=|coords)` — con KIIDs
- `save_board`
- `route_board` — **JSON estructurado desde sesión 17** (route_ms, nets, drc)

**Validación y export:**
- `run_drc(min_severity=)` — con fix de pos para edge clearance (P2.5)
- `export_render`, `export_manufacturing` (G3), `export_bom`

**17+ códigos de error** en catálogo (`docs/specs/tool-catalog.md`):
- Existentes: `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `KICAD_CLI_FAILED`,
  `CONTEXT_BUDGET_IMPOSSIBLE`, `PATH_OUTSIDE_PROJECT`, `KICAD_NOT_RUNNING`, etc.
- **Nuevos desde sesión 16**: `TRACK_ID_STALE`
- **Nuevos desde sesión 17**: `ROUTE_NET_BLOCKED` (informativo, embebido en payload)

**Fix estructural de `data` (sesión 16, más grande de lo esperado):** el SDK MCP
vendorizado colapsaba TODA excepción a `str(e)`. Antes del fix, `data` estructurado
en cualquier error nunca llegaba al agente. El agente del Dogfooding 2 operó sin
NINGÚN `data.*` que el catálogo prometía. Fix en `errors.py` (una función), sin
tocar el SDK (F5 intacta). Beneficia a todos los emisores retroactivamente.

---

## Fronteras inviolables (F1–F5)

Sin cambios desde v1:

- **F1**: no editar `toon-v1.md` (spec del encoder). Nuevas vistas de datos van a
  tools nuevas, no a TOON. Ejemplo canónico: `get_tracks` no es sección de TOON.
- **F2**: no cambiar semántica de gates G0–G3.
- **F3**: no renombrar códigos de error existentes. Códigos nuevos permitidos con
  hint accionable.
- **F4**: no asumir KiCad 11 (el codebase asume KiCad 10.x). El reporte 17 confirma
  10.0.4 en el ambiente de desarrollo del humano.
- **F5**: no tocar `pyproject.toml` sin aprobación. Extiende a: no modificar el SDK
  MCP vendorizado (workaround en el codebase, no en el vendor).

---

## Fixtures y proyectos de prueba

**Vivos, importantes para tests:**

- `/tmp/gui-test-project/` (proyecto del humano) — despertador_inteligente. **Estado
  al cierre de sesión 17**: puede quedar en estado inconsistente tras corridas de
  test (la corrida A del fixture guardó estado vacío por IPC pisando el ruteo). No
  es fuente de verdad. Los tests e/f ahora usan el fixture del repo.
- `tests/fixtures/despertador-routed/` — **sesión 17**. Board ruteado real, 313
  tracks, 21 vías, 1 error DRC (`unconnected_items`, ratsnest residual), 0
  `copper_edge_clearance`. `min_copper_edge_clearance=0.5`. **NO es eléctricamente
  correcto** — el sch tiene nets fusionadas (SCL↔INT_SENS, NSS↔MOSI), pin_to_pin
  INT U2↔U3, pin_not_connected U3. Fixture para tests de colisión y regresión de
  `route_board` únicamente. Documentado en README dentro de la carpeta.
- `tests/fixtures/004_real/` — proyecto `video.kicad_pcb` (202 refs, U19, R5, C10).
  Usado por el test viejo de sesión 11 hardcodeado (con guard skip agregado en 16b
  cuando el board abierto no coincide).

**Path del humano en shell:** `/home/astra/Desktop/agent_proyect/kicad-mcp` (repo),
`/home/astra/Desktop/Electronig_Proyects/despertador_inteligente/` (proyecto real).
En el reporte del D2 usó `/tmp/gui-test-project` como scratch.

**Env vars para GUI tests (ver `docs/pruebas-gui.md`):**
```
KICAD_MCP_GUI_TEST=1
KICAD_MCP_PROJECT=/tmp/gui-test-project
KICAD_MCP_GUI_REF=U1
```
Y KiCad abierto con PCB Editor activo.

---

## Riesgos abiertos y estado

| # | Riesgo | Estado tras 17 |
|---|---|---|
| R1 | Freerouting no escala más allá de 24 componentes | Sin evidencia nueva. Dogfooding 3 con sch corregido (~24 fp) tampoco lo va a probar; queda pendiente para un proyecto más grande |
| R2 | Tracks danglings post-route | Sin evidencia de ocurrencia real |
| R3 | `confirm_reloaded` es aserción no verificación | Sigue así; P3 en sesión 18 lo puede reemplazar por recarga programática real |
| R4 | pcbnew SWIG deprecación | Sin cambios |
| R6 | `kicad-skip` reescribe archivo completo | Sin cambios |
| R7 | Clone cross-file bloque `(instances)` hereda de paleta | Sin cambios |
| **R8** | **Mismatch brief/proyecto** | **CERRADO por D-V3.6** — proceso vinculante impide redactar briefs a mano. Ocurrió 3 veces (D1, D2 setup, brief inicial del D2). No debe volver a ocurrir |
| **R9** (nuevo, sesión 17) | Freerouting `gui.enabled=true` cuelga JVM sin escribir `.ses` | **Mitigado**: `_ensure_freerouting_headless_config()` fuerza `gui.enabled=false` antes de cada invocación. Reportar upstream al repo Freerouting antes de open-source (pendiente humano) |
| **R10** (nuevo, sesión 17) | Discrepancia DRC 1 vs 16 tras `save_board` desde GUI | Investigación diferida a 17b — si aparece en Dogfooding 3, escalar |

---

## Hallazgos técnicos críticos (sesiones 16-17)

### 1. Bug estructural: `data` nunca llegaba al agente (sesión 16)

**Impacto retroactivo:** los payloads de error estructurados prometidos por el
catálogo (`SNAPSHOT_STALE.base_snap`, `data.candidates` de delete_track, los 8
emisores de route_board) NUNCA llegaron durante el Dogfooding 2. Agente operó
7.5/10 sin ellos. Fix en `errors.py`, beneficia a todo el sistema.

### 2. Mecanismo indocumentado de edge clearance en Freerouting (sesión 17)

**El descubrimiento más valioso técnicamente del proyecto.** Freerouting 2.1.0
NO tiene concepto público de "clearance al borde del board" — su matriz de
clearance sólo conoce TRACE/VIA/PIN/SMD/AREA. Vía ingeniería inversa de bytecode
(`javap` sobre `freerouting-2.1.0.jar`) se descubrió que:
- `Structure.read_boundary_scope` acepta `(clearance_class "nombre")` dentro de
  `(boundary ...)`
- `NetClass.read_scope` acepta una `(class "nombre" (rule (clearance V)))` sin nets
- Ese nombre viaja a `BoardManager.create_board(...)` como restricción real

Implementado en `bridge/autoroute.py::_inject_edge_clearance`. Validado
empíricamente con boards sintéticos.

**Deuda pendiente (nueva):** ADR-0012 documentando el mecanismo (cita textual de
bytecode + warning de fragilidad si Freerouting cambia entre versiones) + test
canario que rutee con pads a distancia crítica y verifique DRC. Si Freerouting
2.2+ cambia el parser, el canario debe gritar.

### 3. Bug de `get_copper_by_kiid` (16b, corregido en 17)

`kipy.get_items_by_id([kiid])` lanza `ApiError` en not-found, no devuelve `[]`.
El catch-all de `_supervise` mapeaba genéricamente a `KICAD_CLI_FAILED`. Fix
puntual: capturar la excepción por estructura (`__module__`/`__qualname__` +
substring del mensaje) en un helper `_get_items_by_id_or_empty`, aplicado a los
4 consumidores del método (`verify_footprint_by_kiid`, `get_copper_by_kiid`,
`remove_by_kiid`, `move_footprint`).

### 4. Freerouting cuelga con `gui.enabled=true` (R9)

Con la config default de instalación (`$TMPDIR/freerouting/freerouting.json`),
batch mode completa el ruteo pero el proceso JVM se cuelga sin escribir el
`.ses`. Reproducido consistentemente. Mitigado en código; pendiente issue upstream.

### 5. Split-brain confirmado empíricamente (sesión 17)

La corrida A del fixture demostró el split-brain vivo↔disco en la práctica:
`route_board` escribió el ruteo a disco correctamente, pero el board vivo en KiCad
siguió mostrando 0 tracks por IPC hasta que el humano hizo File→Revert. Cualquier
tool que corrió contra el vivo entre route y revert veía el estado pre-ruteo. Un
`save_board` en ese estado sobrescribió el ruteo real.

**Corolario:** D-V3.1 (P3 sesión 18) no es lujo, es necesidad. Sin recarga
programática, cualquier iteración `route → mutar → save` es peligrosa por defecto.

---

## Métricas del Dogfooding 2 (referencia)

Duración ~2.5h · 118 llamadas MCP · Nota 7.5/10 (D1 fue 5/10).

Distribución de llamadas: 32 move_footprint (6 errores de rango), 21 add_track
(2 errores), 13 delete_track (4 errores de desambiguación — los que P1/sesión 16
cerró), 8 run_drc, 8 get_world_context (3 errores de presupuesto), 6
get_component_detail, 6 add/delete_via, 5 route_board (1 timeout), 5 save_board,
4 export_render (1 error de path), 2 health, 2 draw_board_outline (1 error), 1
run_erc, 1 export_manufacturing, 1 export_bom.

Contactos humanos: 3 File→Revert + 1 aprobación de regla + 1 pista `/RESET` en GUI = 5.

Fricciones registradas: F-01 a F-13. Estado tras sesiones 16-17:

| F-NN | Descripción | Estado |
|---|---|---|
| F-01 | Path proyecto sin subdirectorio (arquitecto) | Cerrada por D-V3.6 |
| F-02 | `health()` no distingue estados | Abierta (P5 hoja de ruta) |
| F-03 | ERC posiciones ÷100 | Abierta (P5) |
| F-04 | ERC "limpio" falso (arquitecto) | Cerrada por D-V3.6 |
| F-05 | move_footprint ignora Edge.Cuts | Cerrada sesión 16 |
| F-06 | Contorno inmutable | Abierta (P5) |
| F-07 | Dimensiones erradas en brief (arquitecto) | Cerrada por D-V3.6 |
| F-08 | `route_ms` ausente | Cerrada sesión 17 (con excepción en ruta de fallo — 17b) |
| F-09 | Denominador engañoso de route_board | Cerrada sesión 17 |
| F-10 | Re-route incremental timeout | Sin acción (P2.3 diferido) |
| F-11 | Reglas no viajan al DSN, DRC pos=[0,0] | Cerrada sesión 17 |
| F-12 | Nets bloqueadas silenciosas | Parcialmente cerrada (causa mínima honesta; A* diferido a 17b) |
| F-13 | Cobre invisible / cirugía a ciegas | Cerrada sesión 16 |

---

## Deuda del arquitecto (yo — mantener visible)

Registro honesto de fricciones que YO causé y las salvaguardas aplicadas:

1. **Riesgo 8 ocurrió 3 veces** (D1, setup D2, brief inicial D2). D-V3.6 lo cerró.
   Todo brief nuevo se genera con tools verificadas, nunca redactado desde texto.
2. **Deuda eléctrica del sch del despertador**: nets fusionadas SCL↔INT_SENS,
   NSS↔MOSI + pin_to_pin INT U2↔U3 + pin_not_connected U3. La placa fabricable
   del D2 hereda esos defectos. **Decisión vigente**: no fabricar esos gerbers.
   Sesión 20 (Dogfooding 3) empieza corrigiendo el sch. **Este es MI trabajo
   pendiente antes de la 20.**
3. J1 marcado `in_bom no` en brief pero no en sch. Corregir junto con lo anterior.

---

## Hoja de ruta v3 vigente

| Sesión | Contenido | Gate |
|---|---|---|
| 18 | **P3**: recarga programática post-route (D-V3.1) | Sesión de ruteo con 0 contactos humanos (o 1 si batch) |
| 19 | **P4**: zonas mínimas (`add_zone`) | Plano GND rectangular + keepout expresable |
| 17b (opcional) | A* bloqueador, `route_ms` en fallos, DRC discrepancia R10, ADR-0012 | Solo si D3 lo pide |
| 20 | **Dogfooding 3**: sch corregido + re-route con todo lo nuevo | **Nota ≥8/10** |

**Post-D3 con ≥8**: ruta a open source (limpieza, docs, ADR-0012, issue upstream
a Freerouting sobre R9, licencia).

---

## Instrucciones de handoff (para un nuevo chat)

Pegá este documento como primer mensaje con este preámbulo:

> Sos el arquitecto de software senior y revisor técnico crítico del proyecto
> kicad-mcp. El CONTEXT.md v2 adjunto contiene el estado completo del proyecto
> tras 17 sesiones. No vas a ver la conversación anterior — ese archivo ES la
> conversación destilada.
>
> Reglas de operación:
> 1. Respetá decisiones del CONTEXT o cuestionalas con evidencia nueva.
> 2. Mantené el mismo nivel de profundidad técnica.
> 3. Nueva evidencia > decisiones previas cuando hay contradicción.
> 4. Tu rol es arquitectura, no código. Generás prompts de sesión.
> 5. Conservá la cronología: algunas decisiones fueron revocadas/ampliadas.
>
> **Estado crítico al arrancar:** sesión 17 lista para merge, sesión 18 (P3
> recarga programática) es el siguiente prompt a generar. La deuda eléctrica del
> sch del despertador (SCL↔INT_SENS, NSS↔MOSI) es MI trabajo pendiente antes de
> la sesión 20.
