# Roadmap — kicad-mcp

Generado en la reorganización documental (2026-07-24), consolidado desde
`docs/historico/CONTEXT-v7.md` (post-sesión 24). **La dirección estratégica
vigente vive en `hoja-de-ruta-v4.md`** (raíz del repo) — este documento ya no
duplica esa secuencia; queda como resumen de estado + historial de
dogfooding, que `hoja-de-ruta-v4.md` no repite.

---

## Estado en una línea

Loop de escritura de PCB cerrado (esquemático → colocación → contorno →
zonas/GND → ruteo autorouter → DRC → recarga programática → gerbers),
validado contra KiCad 10.0.4 real en 4 rondas de dogfooding. El bloqueante P0
más reciente (F-D4-02: DRC post-route falso + disco no persistido) está
**cerrado** desde sesión 24 (ADR-0012, D-23.2), con evidencia en vivo (2/2
corridas reales, sin mocks). Rama vigente: `master`, todo mergeado hasta
sesión 24. **El proyecto pasó de Fase 2 (descubrimiento acelerado) a Fase 3
(consolidación)** — ver `docs/CONTEXT.md` §"Estado actual" para el modelo de
fases, y `hoja-de-ruta-v4.md` para la secuencia estricta vigente (D5 → fix P1
→ generalización D-23.2 → D6 → convergencia).

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
por regresión de calidad del ruteo — ver `docs/investigacion/23-fd4-02.md`
para el análisis completo. **D5 (sesión 25, objetivo ≥9) todavía no corrió**
— agregará la próxima fila; ver `hoja-de-ruta-v4.md` para precondiciones,
gates de salida y el resto de la secuencia.

## Riesgos abiertos que condicionan el roadmap

Ver `docs/BACKLOG.md` para el detalle priorizado. Los que más pueden bloquear
una sesión de dogfooding futura: R12 (tools de escritura de sch puramente
aditivas), R13 (`get_world_context(kind="sch")` falla con `#PWR*`/`#FLG*`),
R9 (`Freerouting gui.enabled=true` cuelga la JVM, mitigado en código).
