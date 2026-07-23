# CONTEXT.md v3 — kicad-mcp (post-sesión 19e, 2026-07-22)

**Handoff destilado. Reemplaza a CONTEXT.md v2.** 22 sesiones de desarrollo
(1-14 base, 15 Dogfooding 2, 16-19e nuevas), 2 dogfoodings completos, 1
hoja de ruta v3 en última fase antes del Dogfooding 3. Este documento es la
conversación: si alguien abre un nuevo chat, esto es todo lo que necesita
para tomar el rol.

---

## Estado en una línea

Servidor MCP para operar KiCad autónomamente desde Claude Code. 20+ tools
productivas, loop de escritura PCB cerrado (esquemático → colocación →
contorno → ruteo → DRC → gerbers) con recarga programática (no más
File→Revert humano), autorouter Freerouting integrado con reglas del
proyecto que viajan al DSN, zonas de cobre y keepouts implementados,
resolución de socket dinámica robusta ante crashes de KiCad. Último
dogfooding real (D2, 2026-07-16): 7.5/10 con placa fabricable. **Estás por
arrancar sesión 20: Dogfooding 3, meta ≥8/10.**

**Rama vigente:** `master`, con todas las sesiones 19-19e mergeadas.

---

## Rol

Arquitecto senior + revisor técnico crítico. NO escribo código. Diseño,
decido, audito, genero prompts de sesión. Vinculante en decisiones, no en
implementación. Los prompts los ejecuta un agente de Claude Code sobre el
repo.

Reglas de operación:
1. Respetar decisiones del CONTEXT o cuestionarlas con evidencia nueva.
2. Mantener el nivel de profundidad técnica.
3. Nueva evidencia > decisiones previas cuando hay contradicción.
4. Cronología importante: algunas decisiones fueron revocadas/ampliadas.

**Regla vinculante para mí (D-V3.6):** los briefs de dogfooding se generan
con las tools del propio server, nunca se redactan desde texto. Tres
fricciones del D2 (F-01, F-04, F-07) fueron mías por violar esto. Y en
19b, tres correcciones adicionales a mis diseños: mapa de pines mal
derivado del netlist fusionado, worklist con "Update Symbols" destructivo,
déficit de pines subestimado. **Antes de proponer diseños de sch, resolver
el netlist post-separación explícitamente.**

---

## Cronología condensada

| Sesión | Contenido | Cierre |
|---|---|---|
| 1–14 | Bootstrap del server, D1, TOON, tools PCB v1, Freerouting integration | Ver v1/v2 |
| 15 | **Dogfooding 2**: despertador ATtiny85, 24 fp | **7.5/10** |
| 16 | P1: `get_tracks` + `delete_track(id=)` + `add_track` mixed | Merge |
| 16b | Fix tests integration_gui + descubierto bug `get_copper_by_kiid` | Merge |
| 17 | P2.0 fix + P2.1 reglas al DSN + P2.2 route_board JSON + P2.5 DRC pos + fixture | Merge |
| 18 | P3: recarga programática vía `Board.revert()` — D-V3.1 cerrado | Merge |
| **19** | **P4**: 5 tools de zonas (add_zone, add_keepout_zone, get_zones, fill_zones, delete_zone) | Merge |
| **19c** | Investigación bloqueantes pre-D3: 4 bloques ejecutados | Sin merge (investigación) |
| **19d** | Fixes puntuales: NET_ASSIGNMENT_MISMATCH + delete_tracks_bulk + test P4.5 reescrito | Merge |
| **19b** | Corrección sch del despertador (deuda del arquitecto) | Merge |
| **19e** | Fix socket path (blocker F-19b-09) + investigación F-19b-06 | Merge |
| **20** | **Siguiente**: Dogfooding 3 con meta ≥8/10 | — |

---

## Decisiones de arquitectura vigentes

Las modificadas o revocadas por evidencia posterior lo dicen explícito. En
caso de conflicto entre CONTEXT v2 y este, gana este.

### Modificadas por evidencia (hoja de ruta v3 y sesiones posteriores)

- **D-V3.1** (revoca parte de D-R2/D-14.1): revert humano post-route
  eliminado. `Board.revert()` en KiCad 10.0.4 funciona nativo (sesión 18).
  **D-12.4 corregida retroactivamente**: `revert()` es imposible en
  Schematic Editor (KiCad 11 IPC) pero funciona perfecto en PCB Editor.
- **D-V3.2**: TOON no crece; `get_tracks` es la vista de cobre con KIIDs
  (sesión 16).
- **D-V3.3**: selección por KIID reemplaza desambiguación por radio en
  delete_track/delete_via (sesión 16).
- **D-V3.4**: `route_board` con contrato JSON (route_ms, denominador,
  causas de nets bloqueadas, DRC pre/post, campo `zones`) — sesión 17 + 19.
- **D-V3.5**: reglas del board viajan al DSN. Descubrimiento: netclasses
  ya viajan por `pcbnew.LoadBoard`; edge clearance necesitó ingeniería
  inversa de bytecode (ver §Hallazgos técnicos).
- **D-V3.6** (proceso, vinculante para el arquitecto): briefs generados
  con tools, no redactados. Extendido en sesión 19b: **antes de proponer
  reasignaciones de pin, resolver el netlist post-separación explícitamente.**

### Nuevas de sesión 19-19e

- **D-19.1**: Freerouting 2.1.0 respeta nativamente `(plane <net> ...)`
  que `pcbnew.ExportSpecctraDSN` emite. NO se inyecta manualmente al DSN.
  Descubrimiento del Bloque P4.0 de sesión 19.
- **D-19c.1** (heurística del keepout): NO aplicar `add_keepout_zone`
  antes de un `route_board` autorruteado desde cero. El keepout bloquea
  nets sistemáticamente cuando corta corredores de ruteo del board. Se
  aplica DESPUÉS del ruteo, resolviendo manualmente lo que quede bajo la
  zona. Confirmado empíricamente en el Bloque 4 de sesión 19c.
- **D-19c.2** (net-hijacking en add_via/add_track): KiCad reasigna el net
  del ítem creado al net del cobre físico bajo/que cruza. NO es bug de
  caché ni de código; es dominio de KiCad. Confirmado en Bloques 1 de 19c
  y 19d.0. **Cerrado en tool** por sesión 19d con verificación post-creación
  + `NET_ASSIGNMENT_MISMATCH`.
- **D-19d.1**: `add_track` bridge devuelve KIID (antes `None`). Simetría
  con `add_via`. La tool MCP mantiene el confirm de texto.
- **D-19b.1**: `lib_symbol_mismatch` warnings aceptados y documentados si
  el símbolo local diverge intencionalmente. NO ejecutar "Update Symbols
  from Library" — es destructivo cuando los símbolos son customizaciones
  funcionales (rompió 6 pines en 19b, revertido con Ctrl+Z).
- **D-19b.2**: neteo de sch es por coincidencia de texto de label, no por
  proximidad ni wire físico. Cualquier tool de mutación de sch debe
  respetar esto. No-Connect no severa una red si el pin conserva su label.
- **D-19e.1**: resolución de socket es cascada **dinámica** (re-resolución
  en cada `_ensure_client()`), no snapshot en `__init__`. Sobrevive a
  crashes/reinicios de KiCad. Constantes de descubrimiento separadas del
  `_DEFAULT_SOCKET_LINUX` para monkeypatch en tests.
- **D-19e.2**: `get_world_context(kind="sch")` NO soporta proyectos con
  símbolos `#PWR*`/`#FLG*`. Causa: filtro asimétrico entre posiciones
  (todo símbolo) y netlist (kicad-cli excluye pseudo-símbolos). Workaround
  vigente: `export_netlist()` + parseo. Fix diferido a 20b.

### Vigentes sin cambios desde v2

- D-08, D-09.1, D-12.3, D-14.1, D-14.2 (con excepciones documentadas por
  D-17.1 y D-19.x que rompen el confirm ≤50 tok).
- D-R3, D-R8 (asimetría delete_track sí / delete_footprint no — sigue
  abierta).
- D-16.1 (KIID), D-16.2 (endpoints mixed), D-16.3 (SDF collision con
  netclass real desde P2.1).
- D-17.1 (route_board JSON), D-17.2 (causa mínima honesta, A* diferido).

---

## Tools productivas (inventario actualizado)

### Lectura de mundo
- `health()` — estado del server, IPC, proyecto. **19e**: cascada de
  socket resolution robusta. F-02 (no distingue estados) sigue abierta.
- `get_world_context(kind, focus, budget)` — TOON, sin tracks (D-V3.2).
  **19e**: NO soporta `kind="sch"` con proyectos que tengan `#PWR*`/`#FLG*`
  (workaround: `export_netlist()`).
- `get_component_detail(ref)` — pads, courtyard, absolutos.
- `get_tracks(net=|bbox=|layer=, max_tokens=)` — con KIIDs.
- `get_zones(layer=|net=|max_tokens=)` — **sesión 19**, con KIIDs. Devuelve
  copper + keepouts distinguibles por `kind`.
- `run_erc()` — F-03 (÷100 en posiciones) y F-19b-12 (mismo bug con más
  detalle) siguen abiertos.

### Escritura de esquemático (paleta) — **LIMITACIÓN CRÍTICA**
Las 4 tools existentes son **puramente aditivas**:
- `add_symbol`, `set_value`, `set_footprint`, `connect_pins`, `clone_symbols`

**NO existe CRUD**: no hay `delete_wire`, `delete_label`, `add_no_connect`,
`set_symbol_attr`, `sync_symbol_from_library` (F-19b-01 a F-19b-05, F-19b-08,
F-19b-10). El agente puede DISEÑAR un sch desde cero pero NO CORREGIRLO.
Cualquier defecto de sch en el D3 requiere intervención GUI humana.

### Escritura de PCB
- `draw_board_outline` — F-06 (inmutable) sigue abierta.
- `move_footprint` — sin rotación aún; bbox considera Edge.Cuts.
- `add_track` — endpoints mixed (D-16.2), collision SDF con netclass real
  (P2.1), **19d**: verificación post-creación + `NET_ASSIGNMENT_MISMATCH`.
  Bridge devuelve KIID.
- `add_via` — **19d**: idem `NET_ASSIGNMENT_MISMATCH`.
- `delete_track(id=|coords)`, `delete_via(id=|coords)` — con KIIDs.
- **`delete_tracks_bulk(net=|bbox=|layer=, include_vias=, dry_run=)`** —
  **nueva 19d**. Al menos un filtro obligatorio. `dry_run=True` como buena
  práctica para primera invocación.
- `save_board` — con guard reforzado mtime (P3.2).
- `add_zone(net, layer, bbox=|polygon=, fill=true)` — **nueva 19**.
- `add_keepout_zone(layer, bbox=|polygon=, no_tracks, no_vias, no_pours)` —
  **nueva 19**. VER D-19c.1: no aplicar antes de `route_board` desde cero.
- `fill_zones(zone_id=)` — **nueva 19**. `zone_id` valida existencia pero
  no acota el refill (limitación de kipy 0.7.1, siempre refilla todas).
- `delete_zone(id=)` — **nueva 19**. Solo por KIID.
- `route_board(timeout_s=)` — **JSON estructurado desde sesión 17**
  (route_ms, nets con causas, drc pre/post, zones existentes/refilladas,
  reloaded). Post-route hace `Board.revert()` automático.
- `reload_board_from_disk()` — **nueva 18**. `Board.revert()` de kipy.

### Validación y export
- `run_drc(min_severity=)` — con fix de pos para edge clearance (P2.5).
- `export_render`, `export_manufacturing` (G3), `export_bom`.

### Códigos de error (F3 respetada, siempre agregar nunca renombrar)
- Existentes: `SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, `KICAD_CLI_FAILED`,
  `CONTEXT_BUDGET_IMPOSSIBLE`, `PATH_OUTSIDE_PROJECT`, `KICAD_NOT_RUNNING`,
  `KICAD_TIMEOUT`, `KICAD_RESTARTED`, `INVALID_PARAMS`, `NET_NOT_FOUND`.
- Sesión 16: `TRACK_ID_STALE`.
- Sesión 17: `ROUTE_NET_BLOCKED` (informativo, embebido en payload).
- Sesión 18: `RELOAD_FAILED`.
- Sesión 19: `INVALID_ZONE_GEOMETRY`, `ZONE_ID_STALE`.
- **Sesión 19d: `NET_ASSIGNMENT_MISMATCH`** — con `data.requested_net`,
  `data.actual_net`, `data.at`.

**Fix estructural de `data` (sesión 16):** el SDK MCP vendorizado
colapsaba TODA excepción a `str(e)`. Antes del fix, `data` estructurado
nunca llegaba al agente. Fix en `errors.py`, sin tocar el SDK (F5 intacta).
Beneficia a todos los emisores retroactivamente.

---

## Fronteras inviolables (F1–F5)

Sin cambios desde v2:

- **F1**: no editar `toon-v1.md`. Nuevas vistas → tools nuevas, no
  secciones TOON.
- **F2**: no cambiar semántica de gates G0–G3.
- **F3**: no renombrar códigos de error existentes. Nuevos con hint
  accionable.
- **F4**: **asume KiCad 10.0.4 exclusivamente**; no asumir KiCad 11 hasta
  decisión formal de migración.
- **F5**: no tocar `pyproject.toml` sin aprobación. Extiende: no modificar
  el SDK MCP vendorizado.

---

## Fixtures y proyectos de prueba

- `/tmp/gui-test-project/` (proyecto del humano) — **STALE por defecto**.
  La copia se rompe/desincroniza con frecuencia (crashes, sesiones largas,
  save_board sobre estado inconsistente). **Protocolo obligatorio antes de
  cada sesión GUI**: restaurar copia desde el fixture versionado del repo
  o desde `/home/astra/Desktop/Electronig_Proyects/despertador_inteligente/`.

- `tests/fixtures/despertador-routed/` — **STALE tras sesión 19b**. El sch
  del despertador cambió (5 defectos corregidos). El fixture del repo aún
  refleja el sch VIEJO. **Regeneración prevista para sesión 20 (Dogfooding
  3)** como subproducto natural del ruteo desde cero con sch corregido.
  Los 2 tests que lo consumen (`test_zones_e2e_gui.py`,
  `test_reload_e2e_gui.py`) no assertean sobre nets específicas — siguen
  siendo válidos para colisión de cobre denso. NO requieren skip.

- `tests/fixtures/004_real/` — proyecto `video.kicad_pcb` (202 refs).
  Guard skip agregado en 16b si el board abierto no coincide.

**Path del humano en shell:** `/home/astra/Desktop/agent_proyect/kicad-mcp`
(repo), `/home/astra/Desktop/Electronig_Proyects/despertador_inteligente/`
(proyecto físico canónico). `/tmp/gui-test-project` como scratch.

**Env vars para sesiones GUI:**
```
KICAD_MCP_GUI_TEST=1
KICAD_MCP_PROJECT=/tmp/gui-test-project
KICAD_MCP_GUI_REF=U1
KICAD_MCP_FREEROUTING_JAR=/home/astra/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar
```

Y KiCad abierto con PCB Editor activo. Ver §Reglas operacionales sobre
dónde vivan estas env vars realmente para el server MCP.

---

## Riesgos abiertos y estado

| # | Riesgo | Estado |
|---|---|---|
| R1 | Freerouting no escala > 24 componentes | Sin evidencia. D3 (~24 fp) tampoco lo va a probar |
| R2 | Tracks danglings post-route | Sin evidencia de ocurrencia real |
| R3 | `confirm_reloaded` es aserción no verificación | Superado por D-V3.1 (P3.1 recarga programática) |
| R4 | pcbnew SWIG deprecación | Sin cambios |
| R6 | kicad-skip reescribe archivo completo | Sin cambios |
| R7 | Clone cross-file bloque `(instances)` | Sin cambios |
| R8 | Mismatch brief/proyecto | Cerrado por D-V3.6 |
| R9 | Freerouting `gui.enabled=true` cuelga JVM | Mitigado en 17. Pendiente issue upstream (humano, no urgente) |
| R10 | Discrepancia DRC tras `save_board` desde GUI | Sin evidencia nueva |
| **R11** | Crash de KiCad bajo mutaciones IPC rápidas | **Reportado en 19d**. Server sobrevive gracias a cascada dinámica de socket (19e). Mitigación: `save_board` frecuente + backups G1 automáticos |
| **R12** (nuevo) | Tools de sch son puramente aditivas — sin CRUD | **Confirmado en 19b**. Cualquier defecto de sch en D3 requiere GUI humana. CRUD diferido a 20b |
| **R13** (nuevo) | `get_world_context(kind="sch")` falla con `#PWR*`/`#FLG*` | **Confirmado en 19e**. Workaround: `export_netlist()`. Fix diferido a 20b |

---

## Hallazgos técnicos críticos (sesiones 15-19e)

### 1. Bug estructural: `data` nunca llegaba al agente (sesión 16)
Ver v2 §Hallazgos. Fix en `errors.py` beneficia a todo el sistema
retroactivamente.

### 2. Mecanismo indocumentado de edge clearance en Freerouting (sesión 17)
Ingeniería inversa de bytecode con `javap`. `Structure.read_boundary_scope`
+ `NetClass.read_scope` con `clearance_class` sintética. ADR-0012 pendiente
+ test canario propuesto (17b/20b).

### 3. Bug de `get_copper_by_kiid` (16b, corregido en 17)
kipy lanza `ApiError` en not-found en vez de devolver `[]`. Helper
`_get_items_by_id_or_empty` captura la excepción.

### 4. Bug de Freerouting `gui.enabled=true` (17)
JVM cuelga sin escribir `.ses`. Mitigado en código
(`_ensure_freerouting_headless_config()`). Pendiente issue upstream.

### 5. Split-brain confirmado empíricamente (17)
Motivó P3.1 (sesión 18). Cerrado con `Board.revert()` post-route
automático.

### 6. Freerouting respeta `(plane)` nativo (sesión 19 P4.0)
No hace falta inyección DSN manual. Test decisivo con board sintético:
plano GND → 0 vías vs 1 sin plano.

### 7. Net-hijacking en add_via/add_track (sesiones 19c, 19d)
KiCad reasigna el net del ítem creado al del cobre físico bajo/cruzado.
Comportamiento de dominio, no bug. **Cerrado en tool** con
`NET_ASSIGNMENT_MISMATCH` que verifica post-creación y revierte. Asimetría
observada: `add_via` solo con cobre indexado en grafo de conectividad
(anclado a pad); `add_track` reasigna todo el segmento (no solo el punto
de cruce).

### 8. Keepout como causa del no-convergence de P4.5 (sesión 19c Bloque 2)
La conclusión de sesión 19 ("Freerouting escala mal con planos densos")
era incorrecta. Ruteo con plano solo converge en 11.3 min; con plano +
keepout no converge. **Regla arquitectónica nueva**: antes de aceptar "X
escala mal", exigir prueba de que X aislado sin Y también escala mal.
Segunda vez que una hipótesis mía o de reporte anterior era menos
completa que la evidencia real (la primera fue D-12.4).

### 9. Freerouting con keepout desde cero declara nets bloqueadas (19c Bloque 4)
Diferente al comportamiento con cobre parcial (progresa parcial). Sin
tracks previos que actúen de guía, el router declara bloqueo temprano.
Consecuencia D-19c.1: keepout SIEMPRE post-route en D3+.

### 10. Neteo del sch es por texto de label (sesión 19b Hallazgo 1)
Las dos fusiones de red del despertador eran dos wires de 1.27mm puenteando
label stubs adyacentes. El diseño netea mayormente por coincidencia de
texto. Consecuencia: No-Connect no severa red si el pin conserva su label
(Hallazgo 3).

### 11. "Update Symbols from Library" es destructivo (sesión 19b Hallazgo 4)
Los símbolos locales pueden divergir intencionalmente de la librería del
sistema. Sincronizar rompió 6 pines. **Regla nueva**: `lib_symbol_mismatch`
NO es cosmético por defecto. Investigar antes de "arreglar".

### 12. Socket de KiCad no tiene naming predecible (sesión 19e)
Misma versión, mismo binario: instancia 1 creó `api-5640.sock`; instancia 2
`api.sock` (sin sufijo). Justifica la cascada completa, no solo el glob.

### 13. Bug `get_world_context(kind="sch")` con pseudo-símbolos (F-19b-06, 19e)
Set-difference estricto entre posiciones (todo símbolo) y netlist
(kicad-cli excluye `#`-prefijados). 26 pseudo-símbolos en el despertador
disparan siempre `KICAD_CLI_FAILED`. Workaround estable: `export_netlist()`.

### 14. Bug `remove_items` firma no variádica (sesión 19d)
kipy expone `remove_items(items: Sequence[BoardItem])`, no variádica. Test
de regresión con fake que replica la firma exacta agregado.

### 15. Constraint del lock no-reentrante (sesión 19d)
`self._lock` del bridge es `threading.Lock` NO reentrante. Funciones bajo
`with self._lock` NO pueden llamar a otras funciones que retomen el lock.
Documentar en `bridge/README.md` o similar es item para 20b.

---

## Reglas operacionales para sesiones GUI (nueva sección desde v2)

Estas reglas surgieron de fricciones reales en 18-19e y son mandatorias
para el D3.

### Restauración de proyecto
Antes de cada sesión GUI, restaurar la copia de trabajo:
```
cp -r /home/astra/Desktop/Electronig_Proyects/despertador_inteligente /tmp/gui-test-project
```
(o desde el fixture versionado según lo que la sesión necesite). `/tmp` es
efímero y las sesiones anteriores pueden haber dejado estado inconsistente.

### KiCad limpio
Reiniciar KiCad desde cero antes de arrancar. Sesiones largas o crashes
previos pueden dejar caché IPC stale.

### Env vars del server
**Las env vars del server MCP están en `~/.claude.json`**, no en la shell
interactiva. Ruta exacta:
`projects.<repo>.mcpServers.kicad-mcp.env`.

`export FOO=bar` en la terminal del humano **no llega al proceso del
server**. Verificar con `/proc/<pid>/environ` si hay dudas. Cambiar env
del server requiere editar el JSON + `/mcp reconnect`.

### Editar código del server durante una sesión
Editar `bridge/` o `tools/` con el server MCP activo NO tiene auto-reload.
Protocolo:
1. Editar el código.
2. `kill <pid del server>`.
3. Humano ejecuta `/mcp reconnect` en Claude Code.
4. Continuar.

Sesión 19e experimentó esto 3 veces en una sesión corta.

### Socket path
Ya NO requiere symlink manual (cerrado en 19e). Cascada dinámica: env var
→ path legacy → glob per-PID. Sobrevive a reinicios de KiCad.

### Backups automáticos G1
Cada primera mutación de una sesión dispara un backup automático del sch/pcb
en `<proyecto>-backups/`. Restaurar desde ahí si algo se rompe.

---

## Métricas del Dogfooding 2 (referencia histórica)

Duración ~2.5h · 118 llamadas MCP · Nota **7.5/10** (D1 fue 5/10).

Fricciones registradas F-01 a F-13. Estado tras sesiones 16-19e:

| F-NN | Estado |
|---|---|
| F-01, F-04, F-07 (mías) | Cerradas por D-V3.6 |
| F-02 (health estados) | Abierta (P5 20b) |
| F-03 (ERC ÷100) | Abierta (P5 20b). Confirmada de nuevo en 19b como F-19b-12 |
| F-05, F-08, F-09, F-11 | Cerradas sesiones 16-17 |
| F-06 (contorno inmutable) | Abierta (P5 20b) |
| F-10 (re-route incremental) | Sin acción (P2.3 diferido) |
| F-12 (nets bloqueadas) | Parcialmente cerrada. A* diferido a 17b (posiblemente innecesario tras 19c-19d) |
| F-13 (cobre invisible) | Cerrada sesión 16 |

## Métricas de la sesión 19b (para diseñar el D3)

12 fricciones nuevas F-19b-01 a F-19b-12. Estado:

- F-19b-01 a 05, 08, 10: CRUD de sch faltante — **R12 abierta**, diferida a 20b.
- F-19b-06: `get_world_context(kind="sch")` con `#PWR*`/`#FLG*` — **cerrada
  como documentar en 19e**, workaround: `export_netlist()`.
- F-19b-07: `health()` reporta KICAD_NOT_RUNNING — causa F-19b-09.
- F-19b-09: socket path hardcodeado — **cerrada por 19e** (D-19e.1).
- F-19b-11: "Update Symbols" destructivo — **cerrada por D-19b.1**.
- F-19b-12: `run_erc` posiciones ÷100 — abierta, mismo bug que F-03.

---

## Deuda del arquitecto (yo — mantener visible)

Registro honesto y actualizado:

1. **Riesgo 8** ocurrió 3 veces (D1, setup D2, brief inicial D2). D-V3.6
   lo cerró.
2. **Sch del despertador tenía 5 defectos** que arrastramos desde D2.
   Corregido en 19b, pero con 3 subestimaciones mías durante el diseño:
   - Mapa de pines mal derivado del netlist fusionado.
   - Worklist con "Update Symbols" que resultó destructivo.
   - Déficit de pines U1 subestimado (2, no 1). Compromiso aceptado:
     ICSP en circuito perdido.
3. **Deuda física del proyecto real** (fuera del scope de kicad-mcp pero
   consecuencia del sch actual):
   - Programar U1 en banco antes de soldar (no ICSP en circuito).
   - **VLED+ (U3.pin10) flotante = MAX30102 no medirá SpO₂**. Diseñar
     alimentación LED antes de fabricar.
   - INT por hardware eliminado; firmware pollea por I2C.
4. **Regla arquitectónica reforzada** (después de dos fallos, D-12.4 y
   sesión 19): antes de aceptar "X escala mal" o "X no funciona",
   **exigir prueba de que X aislado también falla**.

---

## Hoja de ruta vigente

| Sesión | Contenido | Meta |
|---|---|---|
| **20** | **Dogfooding 3**: despertador con sch corregido, plano GND + ruteo desde cero (D-19c.1) | **Nota ≥8/10** |
| **20b** (post-D3) | Backlog: CRUD sch (R12), F-19b-12 (÷100), F-19b-10 (`get_pin_net_membership`), F-19b-06/D-19e.2 (`#PWR/#FLG` filter), ADR-0012 (edge clearance), A* bloqueador (17b), guard cross-proceso, doc de lock no-reentrante, issue upstream Freerouting | — |

Post-D3 con ≥8 → ruta a open source (limpieza, docs, ADR-0012, licencia,
issue upstream a Freerouting sobre R9).

---

## Preparación específica para el Dogfooding 3 (sesión 20)

Precondiciones antes de arrancar:

1. **Todo mergeado a master**: 19+19d+19b+19e. Confirmado en cronología.
2. **KiCad reiniciado limpio** con `/tmp/gui-test-project/` restaurado
   desde Desktop.
3. **Env vars en `~/.claude.json`** (no en shell), `/mcp reconnect` si se
   editan.
4. **Sin symlink en `/tmp/kicad/`** — la cascada de 19e resuelve
   automáticamente.
5. **Sch del despertador corregido** (0 errores, 4 warnings
   `lib_symbol_mismatch` aceptados). Fixture del repo STALE hasta que D3
   lo regenere.

Caveats operacionales del D3 (validados en 19c):

1. **No `add_keepout_zone` antes de `route_board` autorruteado** (D-19c.1).
2. **Patrón validado**: crear/fillar plano GND ANTES de `route_board`, sobre
   board sin cobre. `timeout_s ≥ 900`.
3. **`delete_tracks_bulk` con `dry_run=True` la primera vez** de cada
   iteración.
4. **`add_track`/`add_via` con `NET_ASSIGNMENT_MISMATCH` esperable** en
   colocación cercana a cobre existente — no es fallo del agente, es
   señal a re-planificar coordenadas.

---

## Instrucciones de handoff (para un nuevo chat)

Pegá este documento como primer mensaje con este preámbulo:

> Sos el arquitecto de software senior y revisor técnico crítico del
> proyecto kicad-mcp. El CONTEXT.md v3 adjunto contiene el estado
> completo del proyecto tras 22 sesiones (14 base + Dogfooding 2 + 6
> sesiones de hoja de ruta v3). No vas a ver la conversación anterior —
> ese archivo ES la conversación destilada.
>
> Reglas de operación:
> 1. Respetá decisiones del CONTEXT o cuestionalas con evidencia nueva.
> 2. Mantené el mismo nivel de profundidad técnica.
> 3. Nueva evidencia > decisiones previas cuando hay contradicción.
> 4. Tu rol es arquitectura, no código. Generás prompts de sesión.
> 5. Conservá la cronología: algunas decisiones fueron revocadas o
>    ampliadas.
>
> **Estado crítico al arrancar:** todas las sesiones 19-19e mergeadas a
> master. Próximo trabajo: prompt del Dogfooding 3 (sesión 20), meta
> ≥8/10. Precondiciones y caveats operacionales están en §Preparación
> específica para el Dogfooding 3.
