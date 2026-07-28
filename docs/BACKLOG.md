# Backlog — kicad-mcp

Generado en la reorganización documental (2026-07-24), repriorizado según
`docs/historico/CONTEXT-v7.md` (post-sesión 24) — la secuencia estricta de
Fase 3 sube al frente los ítems de esa secuencia (solder mask ANT1,
generalización D-23.2) y baja el CRUD de esquemático a P3, ya que v7 lo
excluye explícitamente del alcance de Fase 3. También sintetizado de
`docs/historico/analisis/ANALISIS-ESTADO-Y-BACKLOG.md` §Parte 2 y las
fricciones registradas en sesiones 21–24. Dentro de cada prioridad, orden
aproximado de severidad.

---

## P0 — Bloqueantes de dogfooding / release

Ninguno abierto hoy. **F-D4-02 cerrado y ratificado con evidencia 5/5**
(2/2 test de regresión sesión 24 + 3/3 corridas de D5, sesión 25 —
`err_post` coincidió exacto con `run_drc()` independiente, mtime cambió
post-save, cero `EXTERNAL_EDIT_DETECTED` espurio, sin ninguna excepción en
las 5 corridas). El cierre generaliza al board vivo en producción real, no
solo al contrato JSON del test controlado — ver
`docs/historico/sesiones/25-reporte.md`. **Alcance de la ratificación
ampliado en sesión 27**: el contrato D-23.2 ya cubre las tres tools
(`route_board`, `fill_zones`, `add_zone(fill=True)`) — ver P2 cerrado
abajo. **Ratificado 25/25 en producción real hasta cierre D7 (sesión 29),
sin divergencias.** Reabrir como P0 solo si una sesión futura lo ratifica
como regresión.

## P1 — Solder mask bridge en ANT1 — ✅ CERRADO sesión 30 (mecanismo aislado + fix), pendiente gate GUI

El pad de ANT1 hacía bridge con la zona GND. El fix de sesión 21 (F-D3-01)
protegía el *hole*, no el *pad*. Sesión 26 confirmó el bug como real y
alcanzable pero no logró aislar el mecanismo ni hacer efectivo un fix.
**Sesión 30 aisló el mecanismo con precisión sub-milimétrica y aterrizó el
fix.** Ver `docs/investigacion/30-solder-mask-ant1.md` (reporte completo,
continuación de `docs/investigacion/26-solder-mask-ant1.md`).

- **Origen:** fricción de D4 (sesión 22). Investigación parcial sesión 26,
  cerrada sesión 30.
- **Mecanismo:** el fill de KiCad respeta el **apotema** del keepout de
  N vértices (`r·cos(π/N)`), no un círculo ideal al radio pedido. Con
  N=16 (sesión 21-29), el déficit de apotema a los radios típicos de esta
  investigación (~1.8mm) es mayor que el margen de seguridad de 0.02mm —
  por eso el fix de sesión 26 no tuvo efecto. Sesión 26 además asumió un
  número incorrecto para la clearance natural del pad (2.00mm en vez de
  1.70mm, confundiendo `min_copper_edge_clearance` con la clearance de
  netclass), lo que hizo parecer irreconciliables sus dos experimentos.
- **Fix:** `src/kicad_mcp/bridge/ipc.py` — (1) `_circle_vertices_mm` N=16→64
  (compensa el déficit de apotema); (2) `enforce_hole_clearance` recalcula
  el radio de keepout de un pad como
  `max(hole_term, r_cobre_pad + max(pad_to_mask_clearance, solder_mask_to_copper_clearance) + margen)`
  — re-aterriza el término de máscara que sesión 26 había revertido (los
  clearances ya se leían en `rules_reader.py` desde sesión 26, sin
  consumidor hasta ahora).
- **Verificación:** unit test de la fórmula (`tests/test_pcb_hole_clearance.py`)
  + barrido `pad_to_mask_clearance` ∈ {0.0, 0.20, 0.22, 0.25, 0.30} contra
  el motor real de KiCad (`tests/test_pcb_session30_solder_mask.py`, marca
  `integration`, gate del merge) — 0 violaciones en los 5 casos, más
  control del flujo canónico sin cambio de comportamiento.
- **Gate GUI del DoD (pipeline de zonas/keepouts):** corrido contra copia
  fresca (no `/tmp/gui-test-project`, fuera de alcance de sesión 30) —
  `test_pcb_session21_hole_clearance_gui.py` 2/2 y
  `test_pcb_session27_zone_persist_gui.py` 2/2, ambos verdes. Confirma que
  el bump N=16→64 no regresiona ningún keepout auto-generado ya validado
  en D3-D7.
- **Kept de sesión 26, ahora con consumidor:** `rules_reader.py`
  (`pad_to_mask_clearance_mm`, `solder_mask_to_copper_clearance_mm`).

### P2 — Generalización D-23.2 a fill_zones y add_zone(fill=True) [CERRADO sesión 27]

- **Estado:** cerrado 2026-07-24, mergeado a master.
- **Evidencia:** test de regresión GUI 2/2 verde contra KiCad 10.0.4
  real (`tests/test_pcb_session27_zone_persist_gui.py`, 69s por
  corrida). ADR-0012 extendido con sección "Extensión de alcance
  (sesión 27)".
- **Cambio:** `POST_ZONE_PERSIST_FAILED` compartido para las dos tools.
  Contrato D-23.2 ahora aplica a tres tools (`route_board`,
  `fill_zones`, `add_zone(fill=True)`).
- **Ratificado en Fase 3** con 3 dogfoodings verdes consecutivos (D5, D6,
  D7); Fase 3 cerrada 2026-07-25.
- **Reporte:** `docs/historico/sesiones/27-reporte.md`.

## P2 — Correcciones puntuales con evidencia repetida

| Item | Evidencia | Estado |
|---|---|---|
| `run_erc()` posiciones ÷100 | F-03 (D2), F-19b-12 (19b) | Abierto, confirmado 2 veces. |
| `health()` no distingue `PROJECT_NOT_CONFIGURED` vs `PROJECT_PATH_NOT_FOUND` | F-02 | Abierto. |
| `draw_board_outline` inmutable (sin `replace=true`/`delete`) | F-06 | Abierto. |
| Asimetría `delete_track` sí / `delete_footprint` no | D-R3, D-R8 | Abierto, sin ADR. |
| Doc del lock no-reentrante del bridge (`self._lock` no es reentrante) | Sesión 19d | Pendiente: documentar en `bridge/README.md` o similar. |
| Issue upstream a Freerouting sobre `gui.enabled=true` colgando la JVM (R9) | Sesión 17 | Mitigado en código; issue no abierto (no urgente). |
| `move_footprint` no dispara refill de zonas — un DRC leído de disco tras mover pads sobre un plano mide fill rancio, no el estado real | Sesión 26, investigación 26 §2 | Nota de proceso: `fill_zones()` obligatorio tras colocación masiva, antes del baseline DRC. No es un bug de la tool (su contrato nunca prometió refill) — es un punto ciego de brief/protocolo de dogfooding. |

## P2 — Release polish (post-Fase 4, pre-release Open Source)

No bloqueante hoy — condicionado a las 3 validaciones exitosas de la
Validation Suite (sesiones 31-33 según `hoja-de-ruta-v5.md`) y al cierre
de P1 (ya cumplido, sesión 30). Retomar en sesión 34+ (preparación de
release Open Source), no antes.

- **ADR-0013 en adelante**: documentar el mecanismo indocumentado de edge
  clearance de Freerouting (hoy solo entendido por ingeniería inversa de
  bytecode, D-V3.5).
- **Docs de arquitectura para colaboradores externos.**
- **Test canario de Freerouting edge clearance.**
- **Licencia + README + CONTRIBUTING.**
- **Limpieza de código muerto** de sesiones intermedias.

## P3 — CRUD de esquemático (R12)

Las tools de escritura de sch son puramente aditivas:
`add_symbol`, `set_value`, `set_footprint`, `connect_pins`, `clone_symbols`.
No existe `delete_wire`, `delete_label`, `add_no_connect`, `set_symbol_attr`,
`sync_symbol_from_library`. Un agente puede **diseñar** un sch desde cero
pero no **corregirlo** — cualquier defecto requiere GUI humana. Bajado de P1
a P3: v7 lo excluye explícitamente del alcance de Fase 3 (que se concentra en
el ciclo de ratificación PCB), habilita autocorrección de sch pero no es
bloqueante para la consolidación en curso.

- **Origen:** F-19b-01 a 05, 08, 10 (sesión 19b). Confirmado sin ejercitar en
  D3/D4 porque el sch pre-corregido no necesitó tocarse.
- **Esfuerzo estimado:** L (varias tools, cada una con su propio patrón de
  verificación de efecto vía kicad-skip).

## P3 — `get_world_context(kind="sch")` falla con `#PWR*`/`#FLG*` (R13)

Set-difference asimétrico entre posiciones (todo símbolo) y netlist
(kicad-cli excluye pseudo-símbolos `#`-prefijados). Dispara
`KICAD_CLI_FAILED` en **cualquier** esquemático con símbolos de
alimentación/power-flag — no es un caso raro.

- **Origen:** D-19e.2, confirmado de nuevo como F-D4-01 en sesión 22.
- **Workaround vigente:** `export_netlist()` + parseo manual.
- **Esfuerzo estimado:** M.

## P3 — Loop de vías de `enforce_hole_clearance` posiblemente código muerto (R16, D-23.3)

En 3 corridas de investigación de sesión 23, el loop de vías de
`enforce_hole_clearance` (líneas 1996-2032 de `ipc.py`) nunca creó un keepout
`via_*`. Deuda técnica identificada pero **no se toca en Fase 3** salvo que
aparezca evidencia nueva de que importa — es investigación independiente.

- **Origen:** D-23.3 (sesión 23).
- **Esfuerzo estimado:** S para investigar, indeterminado para el fix.

## P3 — Ergonomía de colocación (hallazgo D4)

`get_footprint_neighbors` demostró ROI real cuando se usó en conectores con
drill mecánico (J1/J2 en D4: ahorró ~34 min vs. D3). **Pero** la directiva
que lo acotaba a "solo conectores" dejó un punto ciego: 2 `courtyards_overlap`
+ 1 `solder_mask_bridge` en pasivos/ICs que no se verificaron con la tool.

- **Propuesta:** ampliar el uso recomendado de `get_footprint_neighbors` a
  toda colocación manual, no solo conectores — es un cambio de proceso/brief,
  no de código.

### P3 → CERRADO (sesión 29 D7) — F-D5-01: isla GND sin vía al plano (incidente aislado)

En D5 (sesión 25), tras la primera corrida de `route_board`, dos caps
adyacentes (C2/C3, ambos GND) quedaron unidos entre sí por un track pero sin
vía propia al plano B.Cu — a diferencia de otros caps de la misma columna
(C4/C6), que sí recibieron vía del autorouter. 1 error DRC
(`unconnected_items`), diagnosticado con `get_tracks`+`get_footprint_neighbors`
(visibilidad completa) y resuelto con un `add_via` puntual, sin re-ruteo.

**No es señal V3** (no es clearance/hole_clearance/mismatch/persist_failed
contra la zona GND) — es un dato de comportamiento de Freerouting: el motor
puede conectar pads dentro de un net entre sí sin garantizar conectividad
global de esa isla al plano fillado.

- **Estado:** cerrado como observación puntual de D5, no patrón
  sistemático.
- **Evidencia:** trigger de promoción a P2 investigación era "2
  dogfoodings independientes reproducen el patrón". Resultado final:
  D5=1, D6=0, D7=0 → 1/3, no cumplido.
- **Sin trigger de reapertura** salvo que reaparezca en futuros
  dogfoodings.
- **Origen:** F-D5-01, sesión 25. Ver `docs/historico/sesiones/25-reporte.md`
  y `docs/historico/sesiones/29-reporte.md` §Fricciones.

### P3 → CERRADO (sesión 29 D7) — F-D6-01: variabilidad inherente Freerouting/JVM

- **Estado:** cerrado como variabilidad inherente. Sin acción de código.
- **Evidencia:** 3 mediciones D7 (`+3V3`, `/SDA`, `/NSS`) + 2 D5 + 2 D6
  = N=7 total. Sin patrón correlacional con grado de interconexión,
  tamaño del net, ni capas involucradas. Comparación directa sobre
  mismo net `/NSS`: D5=9-10s, D6=110-112s, D7=17.7s — varianza del
  proceso, no propiedad determinística.
- **Documentación pendiente de transferir a `docs/specs/restricciones-kicad.md`**
  (drift detectado en sesión 31: esta entrada afirmaba la transferencia
  hecha desde sesión 29, pero el archivo nunca se tocó — único commit en
  su historia es el de estado inicial): rango operativo esperable
  (9s-112s), advertencia "no asumir que un re-ruteo parcial es
  proporcionalmente barato al tamaño del net". Diff propuesto en sesión 31,
  pendiente de que el humano lo aplique (edición bajo F1, requiere
  levantar el deny de `.claude/settings.json` puntualmente).
- **Sin trigger de reapertura** a menos que aparezcan corridas >600s
  (timeout) o >60s consistentemente en flujos productivos.
- **Origen:** F-D6-01, sesión 28. Ver `docs/historico/sesiones/28-reporte.md`
  y `docs/historico/sesiones/29-reporte.md` §Fricciones.

## P4 — Diferidos sin urgencia (re-evaluar con evidencia nueva)

Nice-to-have, para después de convergencia de Fase 3 (Fase 4).

- **Eval A** (TOON vs JSON/CSV compacto): benchmark de comprensión+tokens
  pendiente desde sesión 04, diferido reiteradamente. Condiciona la
  re-evaluación de ADR-0009 (port a Rust).
- **Soporte multi-hoja** en `get_world_context`/`get_context_delta` de disco
  (`UNSUPPORTED_HIERARCHY`). Depende de si los proyectos reales del humano
  son multi-hoja (pregunta abierta, nunca respondida formalmente).
- **Rotación en `move_footprint`.**
- **Timeout adaptativo** (en vez de fijo) para operaciones IPC largas.
- **Limpieza de tracks huérfanos** (P2.3, sesión 17b).
- **Guard cross-proceso** (sesión 17b) — hoy el lock del bridge protege
  contra concurrencia intra-proceso, no cross-proceso.
- **`add_zone` con hueco interior** (polígono con isla).
- **Opción Y de F-D4-02** (inyectar keepout real al DSN de Freerouting en
  vez de refill+enforce post-ruteo): descartada por ahora en favor de la
  Opción X (sesión 24); reconsiderar solo si aparece evidencia de
  intermitencia real del enfoque actual.
- **A* para causas de nets bloqueadas** en `route_board` — posiblemente ya
  innecesario tras las mejoras de contrato JSON de sesiones 17/19/24.
- **Bbox de validación por Edge.Cuts real** (hoy es footprints ± 100mm) —
  deseable, no bloqueante.
- **Unificación de `POST_ROUTE_PERSIST_FAILED` y `POST_ZONE_PERSIST_FAILED`**:
  sesión 27 introdujo `POST_ZONE_PERSIST_FAILED` para `fill_zones` y
  `add_zone(fill=True)`. Semánticamente equivalente a
  `POST_ROUTE_PERSIST_FAILED` (sesión 24, `route_board`). Coexisten
  temporalmente por decisión conservadora (no tocar `route_board` en
  sesión 27). Deuda: unificar en un solo código compartido (por ejemplo
  `PERSIST_CONTRACT_FAILED` o `TOOL_PERSIST_FAILED`), deprecando los dos
  actuales. Impacto bajo — el contrato JSON de las tools no cambia (los
  códigos siguen exportándose como strings; el llamador puede aceptar
  ambos). Prioridad post-Fase 3, no bloqueante.

## Higiene menor (sin severidad, cuando haya tiempo)

- ~~Fixture `tests/fixtures/despertador-routed/` puede haber quedado stale
  tras correcciones de sch posteriores — verificar antes de reusar en D5.~~
  Resuelto: D5 (sesión 25) verificó (sch sin cambios, ERC idéntico) y
  regeneró el fixture con el ruteo nuevo.
- Contador agregado de `post_fallback` en `health()` para monitoreo pasivo de
  la derivación local (propuesto en `historico/analisis/ANALISIS-ESTADO-Y-BACKLOG.md`
  §C3, nunca implementado, 0 fallbacks observados hasta ahora).

---

## Cómo mantener este documento

Al cerrar un ítem, moverlo a una nota de una línea en el reporte de la sesión
que lo cerró (no acumular aquí "cerrados"). Al abrir uno nuevo desde una
fricción de dogfooding, añadirlo con su origen (F-NN, sesión) para que
`docs/historico/` siga siendo la fuente de evidencia completa.
