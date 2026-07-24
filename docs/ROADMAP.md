# Roadmap — kicad-mcp

**Borrador generado en la reorganización documental (2026-07-24), a revisar
por el arquitecto.** Sintetizado de `docs/historico/sesiones/24-reporte.md`,
`docs/historico/roadmaps/hoja-de-ruta-v3.md` y
`docs/historico/dogfooding/dogfood4-fricciones.md`.

---

## Estado en una línea

Loop de escritura de PCB cerrado (esquemático → colocación → contorno →
zonas/GND → ruteo autorouter → DRC → recarga programática → gerbers),
validado contra KiCad 10.0.4 real en 4 rondas de dogfooding. El bloqueante P0
más reciente (F-D4-02: DRC post-route falso + disco no persistido) está
**cerrado** desde sesión 24 (ADR-0012, D-23.2), con evidencia en vivo (2/2
corridas reales, sin mocks). Rama vigente: `master`, todo mergeado hasta
sesión 24.

## Historial de dogfooding (la métrica que importa)

| Ronda | Sesión | Nota | Resultado |
|---|---|---|---|
| D1 (Etapa 1) | — | 5/10 | Primer contacto real; solo mutaciones aditivas de placement/routing. |
| D2 | 15 | 7.5/10 | Placa fabricable, DRC 0, pero con deuda eléctrica en el sch heredada. |
| D3 | 20 | 8.5/10 | Meta ≥8 alcanzada; sch corregido, plano GND, cero fricciones bloqueantes internas. |
| D4 | 22 | 4.5/10 | **Bandera roja V3**: `route_board` reportaba 51 errores DRC post-route (30 `clearance` + 16 `hole_clearance` contra zona GND), sesión detenida sin gerbers. |
| — | 23 | — | Investigación pura de F-D4-02: causa raíz = orden de medición + falta de persistencia en `route_board` (no falta de protección). |
| — | 24 | — | **Fix aplicado y validado en vivo** (ADR-0012/D-23.2): DRC se mide después de refill+enforce, y se persiste con `save_board()` explícito. |

La caída D3→D4 (8.5 → 4.5) fue causada por un bug estructural real
(`route_board` sobreestimaba sus propios errores y no persistía el fix), no
por regresión de calidad del ruteo — ver `docs/historico/investigacion/23-fd4-02.md`
para el análisis completo.

## Próxima etapa: D5 (sesión 25)

**Objetivo:** repetir la trilogía de verificación V1/V2/V3 de D4, con foco en
que V2 ahora cierre el círculo completo **vivo == disco == reportado** (antes
solo se validaba disco == reportado). El test de regresión de sesión 24
(`tests/test_pcb_session24_route_board_persist_gui.py`) ya ejercita esta
trilogía de forma automatizada.

**Precondiciones (mismas que D3/D4):**
1. KiCad reiniciado limpio, fixture `despertador-routed` restaurado en
   `/tmp/gui-test-project/` (ver `docs/historico/CONTEXT-v3.md` §Fixtures para
   el protocolo exacto y por qué la copia se desincroniza).
2. `health()` verde antes de arrancar.
3. Env vars del server en `~/.claude.json` (no en shell interactiva) —
   `/mcp reconnect` si se editan.

**Si D5 confirma el cierre completo del ciclo vivo/disco/reportado** →
considerar ruta a *open source* (limpieza, licencia, ADR-0012 ya está
commiteado, issue upstream a Freerouting pendiente sobre R9).

## Riesgos abiertos que condicionan el roadmap

Ver `docs/BACKLOG.md` para el detalle priorizado. Los que más pueden bloquear
una sesión de dogfooding futura:

- **R12** — tools de escritura de sch son puramente aditivas (sin CRUD).
  Cualquier defecto de sch en un dogfooding futuro requiere GUI humana.
- **R13** — `get_world_context(kind="sch")` falla con proyectos que tengan
  símbolos `#PWR*`/`#FLG*` (comunes en cualquier esquemático con alimentación).
  Workaround: `export_netlist()`.
- **R9** — `Freerouting gui.enabled=true` cuelga la JVM; mitigado en código,
  issue upstream pendiente (no urgente).

## Fuera del roadmap activo (diferido sin urgencia)

- Eval A (TOON vs JSON/CSV compacto) — sigue sin validarse empíricamente
  (ver ADR-0009, condiciona la re-evaluación del port a Rust).
- Rotación en `move_footprint`.
- Soporte multi-hoja en `get_world_context` de disco (`UNSUPPORTED_HIERARCHY`).
