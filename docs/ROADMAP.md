# Roadmap — kicad-mcp

Generado en la reorganización documental (2026-07-24), consolidado desde
`docs/historico/CONTEXT-v7.md` (post-sesión 24). **La dirección estratégica
vigente vive en `hoja-de-ruta-v4.md`** (raíz del repo) — este documento ya no
duplica esa secuencia; queda como resumen de estado + historial de
dogfooding, que `hoja-de-ruta-v4.md` no repite.

---

## Estado en una línea

**Estado (post-sesión 29, 2026-07-25):** Fase 3 CERRADA con criterio
de convergencia cumplido (3 verdes consecutivos D5/D6/D7). Superficie
ejercitada estable: colocación, contorno, zonas/plano, ruteo autónomo,
DRC, exports. Contrato D-23.2 ratificado 25/25 en las 3 tools. Sesión
30 = planificación estratégica de Fase 4.

## Historial de dogfooding (la métrica que importa)

| Ronda | Sesión | Nota | Resultado |
|---|---|---|---|
| D1 (Etapa 1) | — | 5/10 | Primer contacto real; solo mutaciones aditivas de placement/routing. |
| D2 | 15 | 7.5/10 | Placa fabricable, DRC 0, pero con deuda eléctrica en el sch heredada. |
| D3 | 20 | 8.5/10 | Meta ≥8 alcanzada; sch corregido, plano GND, cero fricciones bloqueantes internas. |
| D4 | 22 | 4.5/10 | **Bandera roja V3**: `route_board` reportaba 51 errores DRC post-route (30 `clearance` + 16 `hole_clearance` contra zona GND), sesión detenida sin gerbers. |
| — | 23 | — | Investigación pura de F-D4-02: causa raíz = orden de medición + falta de persistencia en `route_board` (no falta de protección). |
| — | 24 | — | **Fix aplicado y validado en vivo** (ADR-0012/D-23.2): DRC se mide después de refill+enforce, y se persiste con `save_board()` explícito. Test de regresión 2/2 corridas. |
| D5 | 25 | **9.5/10** | **Primer verde de Fase 3.** Contrato D-23.2 ratificado 3/3 corridas adicionales (5/5 acumulado con sesión 24) sin ninguna divergencia. ERC 0, colocación 23/23, ruteo 10/10, DRC final 0/0, gerbers+BOM limpios. Único hallazgo: F-D5-01 (isla GND sin vía al plano, `info`, resuelta en la misma sesión). Cero contactos humanos. |
| — | 26 | — | **Investigación P1 solder mask ANT1 — cerrada sin fix.** Hipótesis de D5 refutada geométricamente (§1). Bug confirmado real (§3, umbral M≈0.22mm). Fix diseñado + verificado como insuficiente + revertido (§5). Mecanismo no aislado (§6). Kept: `rules_reader` extendido. Ver `docs/investigacion/26-solder-mask-ant1.md`. |
| — | 27 | — | **Generalización D-23.2 a `fill_zones` + `add_zone(fill=True)`.** Premisa del brief refutada en Bloque 1 (`enforce_hole_clearance` ya presente desde sesión 21). Cambio quirúrgico menor de lo anticipado. Test GUI 2/2 verde (69s por corrida). ADR-0012 extendido con sección "Extensión de alcance". `POST_ZONE_PERSIST_FAILED` compartido. Merge en `master`. |
| D6 | 28 | **9.7/10** | **Segundo verde consecutivo de Fase 3.** Contrato D-23.2 ratificado 9/9 en las tres tools (`route_board`, `fill_zones`, `add_zone(fill=True)`) en dogfooding real, sin divergencias. D-27.1 ratificado en producción (restore no destructivo del entorno GUI vivo). D-26.1 ratificado con matiz metodológico (confusor de orden de fases, corregible en D7) — origina D-28.1. Duración 28min, la más corta de la serie. F-D6-01 registrada (P3 vigilancia, re-ruteo parcial no siempre barato). F-D5-01 no reapareció. Drift documental del CONTEXT.md detectado por el propio dogfooding y corregido en consolidación — origina D-28.2. Fixture actualizado. |
| D7 | 29 | **9.8/10** | **Tercer verde consecutivo de Fase 3 — cierre de Fase 3.** D-23.2 ratificado 25/25 total en producción (route_board 12/12 + fill_zones 7/7 + add_zone 6/6). D-26.1 aislado sin confusor por primera vez (V4.a=6 exacto al patrón D5, V4.b=0 tras `fill_zones()`), replicando el orden exacto de fases de D5 (D-28.1 respetado sin desviación). F-D6-01 cerrado como variabilidad inherente Freerouting/JVM (N=7, sin patrón correlacional). F-D5-01 cerrado como incidente aislado (1/3 dogfoodings, no ratificó). Layout D7 completamente distinto de D5/D6 (clusters funcionales en anti-diagonal, ANT1 a 2mm de U4 vs 28mm). 0 fricciones de cualquier severidad. Fixture actualizado. Ver `docs/historico/sesiones/29-reporte.md`. |

La caída D3→D4 (8.5 → 4.5) fue causada por un bug estructural real
(`route_board` sobreestimaba sus propios errores y no persistía el fix), no
por regresión de calidad del ruteo — ver `docs/investigacion/23-fd4-02.md`
para el análisis completo. **D5 (sesión 25) cerró en 9.5/10** — meta ≥9
alcanzada, contrato D-23.2 ratificado 5/5 en producción; ver
`docs/historico/sesiones/25-reporte.md` para el detalle completo y
`hoja-de-ruta-v4.md` para el siguiente paso de la secuencia (sesión 26).

## Riesgos abiertos que condicionan el roadmap

Ver `docs/BACKLOG.md` para el detalle priorizado. Los que más pueden bloquear
una sesión de dogfooding futura: R12 (tools de escritura de sch puramente
aditivas), R13 (`get_world_context(kind="sch")` falla con `#PWR*`/`#FLG*`),
R9 (`Freerouting gui.enabled=true` cuelga la JVM, mitigado en código).
