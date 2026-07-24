# Backlog — kicad-mcp

**Borrador generado en la reorganización documental (2026-07-24), a revisar
por el arquitecto.** Sintetizado de `docs/historico/CONTEXT-v3.md` §"Riesgos
abiertos" y §"Deuda del arquitecto", `docs/historico/analisis/ANALISIS-ESTADO-Y-BACKLOG.md`
§Parte 2, y las fricciones registradas en sesiones 21–24. Sin orden de
prioridad estricto entre temas; dentro de cada tema, orden aproximado de
severidad.

---

## P0 — Bloqueantes de dogfooding / release

Ninguno abierto hoy. F-D4-02 (el último P0) se cerró en sesión 24
(ADR-0012). Pendiente: **confirmación en D5** de que el cierre generaliza al
board vivo, no solo al contrato JSON (ver `docs/ROADMAP.md`).

## P1 — CRUD de esquemático (R12)

Las tools de escritura de sch son puramente aditivas:
`add_symbol`, `set_value`, `set_footprint`, `connect_pins`, `clone_symbols`.
No existe `delete_wire`, `delete_label`, `add_no_connect`, `set_symbol_attr`,
`sync_symbol_from_library`. Un agente puede **diseñar** un sch desde cero
pero no **corregirlo** — cualquier defecto requiere GUI humana.

- **Origen:** F-19b-01 a 05, 08, 10 (sesión 19b). Confirmado sin ejercitar en
  D3/D4 porque el sch pre-corregido no necesitó tocarse.
- **Esfuerzo estimado:** L (varias tools, cada una con su propio patrón de
  verificación de efecto vía kicad-skip).

## P1 — `get_world_context(kind="sch")` falla con `#PWR*`/`#FLG*` (R13)

Set-difference asimétrico entre posiciones (todo símbolo) y netlist
(kicad-cli excluye pseudo-símbolos `#`-prefijados). Dispara
`KICAD_CLI_FAILED` en **cualquier** esquemático con símbolos de
alimentación/power-flag — no es un caso raro.

- **Origen:** D-19e.2, confirmado de nuevo como F-D4-01 en sesión 22.
- **Workaround vigente:** `export_netlist()` + parseo manual.
- **Esfuerzo estimado:** M.

## P2 — Correcciones puntuales con evidencia repetida

| Item | Evidencia | Estado |
|---|---|---|
| `run_erc()` posiciones ÷100 | F-03 (D2), F-19b-12 (19b) | Abierto, confirmado 2 veces. |
| `health()` no distingue `PROJECT_NOT_CONFIGURED` vs `PROJECT_PATH_NOT_FOUND` | F-02 | Abierto. |
| `draw_board_outline` inmutable (sin `replace=true`/`delete`) | F-06 | Abierto. |
| Asimetría `delete_track` sí / `delete_footprint` no | D-R3, D-R8 | Abierto, sin ADR. |
| Doc del lock no-reentrante del bridge (`self._lock` no es reentrante) | Sesión 19d | Pendiente: documentar en `bridge/README.md` o similar. |
| Issue upstream a Freerouting sobre `gui.enabled=true` colgando la JVM (R9) | Sesión 17 | Mitigado en código; issue no abierto (no urgente). |

## P3 — Ergonomía de colocación (hallazgo D4)

`get_footprint_neighbors` demostró ROI real cuando se usó en conectores con
drill mecánico (J1/J2 en D4: ahorró ~34 min vs. D3). **Pero** la directiva
que lo acotaba a "solo conectores" dejó un punto ciego: 2 `courtyards_overlap`
+ 1 `solder_mask_bridge` en pasivos/ICs que no se verificaron con la tool.

- **Propuesta:** ampliar el uso recomendado de `get_footprint_neighbors` a
  toda colocación manual, no solo conectores — es un cambio de proceso/brief,
  no de código.

## P4 — Diferidos sin urgencia (re-evaluar con evidencia nueva)

- **Eval A** (TOON vs JSON/CSV compacto): benchmark de comprensión+tokens
  pendiente desde sesión 04, diferido reiteradamente. Condiciona la
  re-evaluación de ADR-0009 (port a Rust).
- **Soporte multi-hoja** en `get_world_context`/`get_context_delta` de disco
  (`UNSUPPORTED_HIERARCHY`). Depende de si los proyectos reales del humano
  son multi-hoja (pregunta abierta, nunca respondida formalmente).
- **Rotación en `move_footprint`.**
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
