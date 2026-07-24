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

Ninguno abierto hoy. F-D4-02 (el último P0) se cerró en sesión 24
(ADR-0012). Pendiente: **confirmación en D5** de que el cierre generaliza al
board vivo, no solo al contrato JSON (ver `hoja-de-ruta-v4.md`). Reabrir
como P0 solo si D5 lo ratifica como regresión.

## P1 — Solder mask bridge en ANT1 (Fase 3, paso 2 de la secuencia)

El pad de ANT1 hace bridge con la zona GND. El fix de sesión 21 (F-D3-01)
protege el *hole*, no el *pad* — puede necesitar un keepout de máscara
separado. Próxima sesión de fix inmediatamente después de D5, salvo que D5
abra algo más urgente.

- **Origen:** friccion de D4 (sesión 22), P1 vigente confirmado en
  `docs/historico/CONTEXT-v7.md`.
- **Esfuerzo estimado:** por investigar (probablemente S/M — keepout de
  máscara puntual).

## P2 — Generalización D-23.2 a `fill_zones` / `add_zone(fill=True)` (Fase 3, paso 3)

Aplicar a `fill_zones` y `add_zone(fill=True)` el mismo patrón de
reordenamiento de medición + persistencia incondicional confirmado en
`route_board` (ADR-0012). Ambas tools sufren hoy el mismo patrón de "no
persiste el refill" que tenía `route_board` antes de sesión 24 (R14
residual).

- **Condición:** solo si D5 ratifica que el patrón de `route_board` es
  correcto en producción — no iniciar antes.
- **Origen:** D-23.2, nota de sesión 24 sobre `add_zone`/`fill_zones`.
- **Esfuerzo estimado:** M (sesión dedicada + tests de regresión, siguiendo
  el patrón ya probado en `route_board`).

## P2 — Correcciones puntuales con evidencia repetida

| Item | Evidencia | Estado |
|---|---|---|
| `run_erc()` posiciones ÷100 | F-03 (D2), F-19b-12 (19b) | Abierto, confirmado 2 veces. |
| `health()` no distingue `PROJECT_NOT_CONFIGURED` vs `PROJECT_PATH_NOT_FOUND` | F-02 | Abierto. |
| `draw_board_outline` inmutable (sin `replace=true`/`delete`) | F-06 | Abierto. |
| Asimetría `delete_track` sí / `delete_footprint` no | D-R3, D-R8 | Abierto, sin ADR. |
| Doc del lock no-reentrante del bridge (`self._lock` no es reentrante) | Sesión 19d | Pendiente: documentar en `bridge/README.md` o similar. |
| Issue upstream a Freerouting sobre `gui.enabled=true` colgando la JVM (R9) | Sesión 17 | Mitigado en código; issue no abierto (no urgente). |

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

## Higiene menor (sin severidad, cuando haya tiempo)

- Fixture `tests/fixtures/despertador-routed/` puede haber quedado stale tras
  correcciones de sch posteriores — verificar antes de reusar en D5.
- Contador agregado de `post_fallback` en `health()` para monitoreo pasivo de
  la derivación local (propuesto en `historico/analisis/ANALISIS-ESTADO-Y-BACKLOG.md`
  §C3, nunca implementado, 0 fallbacks observados hasta ahora).

---

## Cómo mantener este documento

Al cerrar un ítem, moverlo a una nota de una línea en el reporte de la sesión
que lo cerró (no acumular aquí "cerrados"). Al abrir uno nuevo desde una
fricción de dogfooding, añadirlo con su origen (F-NN, sesión) para que
`docs/historico/` siga siendo la fuente de evidencia completa.
