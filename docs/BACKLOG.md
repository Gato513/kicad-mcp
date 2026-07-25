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
abajo. Ratificación estadística de la extensión pendiente de D6 (sesión
28). Reabrir como P0 solo si una sesión futura lo ratifica como regresión.

## P1 — Solder mask bridge en ANT1 (re-estimado M/L, próximo paso = investigación) — ⚠️ ABIERTO, sesión 26 no lo cerró

El pad de ANT1 hace bridge con la zona GND. El fix de sesión 21 (F-D3-01)
protege el *hole*, no el *pad*. **Sesión 26 confirmó el bug como real y
alcanzable, diseñó e implementó un fix con el arquitecto, pero la
verificación contra KiCad real mostró que el fix NO resuelve el bug en el
valor que su propia fórmula calcula — el mecanismo exacto de
`solder_mask_bridge` de KiCad no se pudo aislar con confianza dentro del
timebox de la sesión.** Ver `docs/investigacion/26-solder-mask-ant1.md`
(reporte completo) y `docs/historico/sesiones/26-reporte.md`.

- **Origen:** fricción de D4 (sesión 22), P1 vigente confirmado en
  `docs/historico/CONTEXT-v7.md`.
- **Estado:** vigente, no cerrado en sesión 26. Bug confirmado real y
  reproducible con evidencia sólida (investigación 26 §3): umbral entre
  `pad_to_mask_clearance=0.20mm` (no) y `0.22mm` (sí), independiente de
  `hole_clearance`.
- **Alcance del bug:** proyectos con `pad_to_mask_clearance ≥ ~0.22mm`. El
  fixture despertador usa M=0 (default KiCad) — no expuesto hoy — pero un
  proyecto real con relief de máscara mayor sí lo estaría.
- **Nota corregida (reemplaza la hipótesis de D5/sesión 25, que era
  FALSA):** en D5 corrida 1, las 3 violaciones del baseline
  (`hole_clearance`, `clearance`, `solder_mask_bridge`) se resolvieron
  post-route pero **NO** por el keepout de hole. Refutación geométrica en
  investigación 26 §1: el keepout r=1.27mm de ANT1 vive íntegramente
  DENTRO del cobre del propio pad (r=1.50mm), en B.Cu solamente — es
  geométricamente incapaz de proteger la apertura de máscara. El mecanismo
  real que resolvió el bridge en D5 fue el refill del plano post-
  `route_board` recortando la zona alrededor del pad con clearance de
  zona ordinaria (0.5mm), no protección específica de máscara. (Para J1,
  sin cobre de pad propio en sus NPTH, el mecanismo de hole SÍ sigue
  siendo el único y funciona — no confundir los dos casos.)
- **Estimación:** re-estimado de S/M a **M/L**. El fix acordado en sesión
  26 (radio keepout = max(término de hole, término de máscara)) se
  implementó, se verificó contra KiCad real, y NO resolvió el bug en su
  valor calculado (investigación 26 §5). El umbral real (§6, entre 1.82mm
  y 2.0mm) no se deriva de ninguna combinación obvia de reglas del
  proyecto vía la fórmula usada. Hay al menos una variable no
  identificada en el mecanismo de `solder_mask_bridge` de KiCad.
- **Causa raíz del baseline específico de D5** (complementaria a la nota
  corregida de arriba — explica por qué APARECIERON las 3 violaciones,
  no por qué desaparecieron): fill rancio — `add_zone(fill=true)` se
  llamó ANTES de las 23 `move_footprint` en D5, y `move_footprint` no
  dispara refill. Ver investigación 26 §2 y D-26.1
  (`docs/DECISIONES.md`). **Hallazgo de proceso transferible:**
  `fill_zones()` obligatorio tras colocación masiva, antes de leer el
  baseline DRC — anotado también en la sección de correcciones puntuales
  abajo.
- **Próximo paso:** sesión de investigación P4.0-style dedicada a aislar
  el mecanismo real antes de intentar otro fix. Alternativas de
  investigación: inspeccionar código fuente de KiCad (`pcbnew`
  específicamente), instrumentación adicional del pipeline de fill,
  reportar upstream y observar el issue tracker de KiCad. NO se agenda
  sesión de fix hasta que la investigación entregue mecanismo aislado.
  Leer investigación 26 completa (especialmente §5/§6, el barrido de
  radio de keepout que no se explica del todo) antes de re-intentar un
  fix — evita repetir el mismo diseño que ya se probó insuficiente.
- **Kept de sesión 26:** extensión de `rules_reader.py`
  (`pad_to_mask_clearance_mm`, `solder_mask_to_copper_clearance_mm`) con
  tests — el intento de fix de `enforce_hole_clearance` se implementó y
  se REVIRTIÓ en la misma sesión tras fallar la verificación, no está en
  el árbol de trabajo. Independiente del mecanismo, reutilizable por
  cualquier investigación futura sobre este tema.

### P2 — Generalización D-23.2 a fill_zones y add_zone(fill=True) [CERRADO sesión 27]

- **Estado:** cerrado 2026-07-24, mergeado a master.
- **Evidencia:** test de regresión GUI 2/2 verde contra KiCad 10.0.4
  real (`tests/test_pcb_session27_zone_persist_gui.py`, 69s por
  corrida). ADR-0012 extendido con sección "Extensión de alcance
  (sesión 27)".
- **Cambio:** `POST_ZONE_PERSIST_FAILED` compartido para las dos tools.
  Contrato D-23.2 ahora aplica a tres tools (`route_board`,
  `fill_zones`, `add_zone(fill=True)`).
- **Ratificación estadística pendiente:** D6 (sesión 28) — primera
  medición del contrato extendido en dogfooding real.
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

## P2 — Release polish (diferido hasta convergencia de Fase 3)

No bloqueante hoy — condicionado a que `hoja-de-ruta-v4.md` cierre Fase 3
(2-3 dogfoodings verdes consecutivos). Retomar recién entonces, no antes.

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

## P3 — F-D5-01: isla GND sin vía al plano tras autoroute (vigilancia)

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

- **Severidad:** `info` — una sola ocurrencia no ratifica un patrón.
- **Trigger explícito de promoción a P2 (investigación):** si **2
  dogfoodings independientes** (geometrías de colocación distintas, no la
  misma placa con el mismo layout) reproducen el mismo patrón — isla de
  ≥2 pads del mismo net conectados entre sí pero sin vía al plano — se
  promueve a P2 y se investiga si es sistemático de Freerouting con
  columnas de decoupling caps muy juntos, o un caso borde específico de la
  geometría de D5.
- **Origen:** F-D5-01, sesión 25. Ver `docs/historico/sesiones/25-reporte.md`
  §Fricciones.
- **Acción hoy:** ninguna — solo vigilar en D6/D7 (sesiones 28+).

## P3 vigilancia — F-D6-01: costo de re-ruteo parcial no barato

- **Contexto:** en D5 (sesión 25) se observaron 2 re-ruteos parciales
  con costo ~9-10s. En D6 (sesión 28) se observaron 2 re-ruteos
  parciales con costo 110-112s — con la misma placa, mismo footprint
  set, mismo Freerouting. Con N=4 total, el rango es 9s-112s, tan
  amplio como el de una corrida completa.
- **Interpretación:** el "modelo barato" que D5 había sugerido con
  solo 2 muestras no se sostiene. Hipótesis (no verificada): el costo
  de re-ruteo parcial depende del grado de interconexión del net
  borrado con el resto del board — un net con muchas conexiones a
  otros nets tiene mayor costo que un net aislado.
- **Estado:** P3 vigilancia. No bloquea uso semanal.
- **Protocolo de investigación:** D7 (sesión 29) mide 2-3 re-ruteos
  parciales adicionales para llegar a N=6-7 muestras. Si aparece patrón
  identificable (correlación con interconexión del net, o con tamaño,
  o con capas), documentar el patrón y actualizar modelo mental de
  `route_ms` en docs. Si N=6-7 aún no muestra patrón, cerrar F-D6-01
  como "variabilidad inherente de Freerouting" y documentar rango
  esperable en `docs/CONTEXT.md` o `restricciones-kicad.md`.
- **Trigger para promoción a P2 investigación:** solo si N=6-7 muestra
  costo consistentemente >60s en re-ruteos parciales (más del doble
  del techo actual de una corrida completa exitosa), lo que sería
  regresión operacional inaceptable.
- **Origen:** F-D6-01, sesión 28. Ver `docs/historico/sesiones/28-reporte.md`
  §Fricciones.

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
