# Sesión 28 — Dogfooding 6 (segundo dogfooding de Fase 3)

**Rama:** `master` (fixture regenerado, sin cambios de código).
**Tipo:** dogfooding de ratificación (no de desarrollo). Placa despertador
ATtiny85 wearable, misma variable controlada que D3/D4/D5. Objetivo
primario: ratificar la extensión del contrato D-23.2 (sesión 27) en las
tres tools + primera aplicación empírica de D-26.1 (refill obligatorio
pre-baseline).

## Resumen ejecutivo

**Nota: 9.7/10** (D2=7.5, D3=8.5, D4=4.5, D5=9.5). Segundo verde
consecutivo de Fase 3 sobre variable controlada. Placa fabricable
completa (ERC 0, colocación 23/23, ruteo con 0 errores DRC introducidos
en 3 corridas, gerbers G3 limpios, BOM exportado, fixture actualizado).
Duración real ~28 minutos — la sesión más corta de toda la serie,
reflejo de la madurez de la superficie.

**Contrato D-23.2 ratificado 9/9 en las tres tools** (`route_board`,
`fill_zones`, `add_zone(fill=True)`) sin ninguna divergencia registrada.
Combinado con las 2/2 corridas del test de regresión de sesión 27 y las
2/2 del test de sesión 24, la evidencia acumulada en producción real es
sólida: 8/8 en `route_board` (2 sesión 24 + 3 D5 + 3 D6) + 4/4 en las
dos tools nuevas (2 test regresión sesión 27 + 2 D6).

**D-27.1 ratificado en primera oportunidad** — el proyecto vivo tenía
board ruteado de D5/S27 al arrancar; restore no destructivo aplicado
con AskUserQuestion, `reload_board_from_disk()` sin reiniciar KiCad,
verificación con `get_component_detail`/`get_zones`.

**F-D5-01 no reapareció** — trigger de promoción a P2 (2 dogfoodings
independientes) no se cumple, sigue P3 vigilancia.

**Único hallazgo:** F-D6-01 (severidad info) — re-ruteo parcial de 1
net costó 110-112s en D6 vs 9-10s en D5, refutando el "modelo barato"
que D5 había sugerido con solo 2 muestras. Con N=4 total (2+2), el
rango de un re-ruteo parcial es tan amplio como el de una corrida
completa. Propuesta: 2-3 mediciones más en D7 para llegar a N=6-7 y
entender el patrón.

## Métricas comparativas

| Métrica | D2 | D3 | D4 | D5 | D6 |
|---|---|---|---|---|---|
| Nota | 7.5 | 8.5 | 4.5 | 9.5 | **9.7** |
| Duración | ~2.5h | ~2h | ~50-60min (parada) | ~2h | **~28min** |
| Contactos humanos | 5 | 2 | 0 | 0 | **1 (D-27.1)** |
| Reverts humanos | 3 | 0 | 0 | 0 | **0** |
| Fricciones bloqueantes | 0-1 | 1 externa | 1 P0 interna | 0 | **0** |
| `route_ms` corrida completa | 925s | 53s | 36.7s | 128.8s | **32.4s** |
| Errores DRC introducidos post-route | 53 (enmascarados) | 0 | 42 (obsoletos) | 1 (F-D5-01) | **0** |
| Baseline V4 pre-route (violaciones no-triviales) | N/A | N/A | N/A | 6 (fill rancio) | **0** |
| mtime cambia post-tool D-23.2 | N/A | N/A | N/A | sí (`route_board`) | **sí (3 tools)** |

## Matiz crítico: ratificación de D-26.1 no aislada

Registrado honestamente por el agente ejecutor en la pregunta 4 del
reporte: el D6 aplicó `fill_zones()` explícito entre colocación y
baseline (D-26.1 al pie de la letra), y el baseline salió con 0
violaciones no-triviales (vs 6 de D5). Pero el orden de fases del D6
fue distinto al de D5: **D6 creó el plano GND DESPUÉS de mover los 23
footprints**, mientras que **D5 creó el plano ANTES de mover**. Ese
orden por sí solo evita el fill rancio (el fill está fresco al momento
de leer el baseline sin necesidad de `fill_zones()` explícito), por lo
que la ratificación de D-26.1 en D6 es consistente con la predicción
pero **metodológicamente no aislada del confusor de orden de fases**.

Este cambio de orden respecto al brief (que prescribía plano ANTES de
colocar como D5) se hizo sin AskUserQuestion. **Origina D-28.1** —
regla operacional formalizada en la consolidación post-D6: cambios de
orden de fases del brief son cambios de metodología, no de
implementación, y requieren AskUserQuestion.

**Ratificación D-23.2:** fuerte y directa (9/9 en 3 tools, 0
divergencias).
**Ratificación D-26.1:** consistente con la predicción pero
metodológicamente débil por el confusor. D7 debe aislar correctamente
replicando el orden exacto de D5 y comparando con/sin `fill_zones()`
explícito.

## V1/V2/V3/V4/V5 consolidado

- **V1**: 4 keepouts `__kicadmcp_hc__` constantes en las 3 corridas de
  ruteo (ANT1 + 3× J1 NPTH). Sin proliferación.
- **V2 reforzado**: 3/3 por cada una de las 3 tools (9/9 total, 0
  divergencias):
  - `route_board`: `err_post = run_drc()` en 3/3, mtime cambió 3/3,
    sin `EXTERNAL_EDIT_DETECTED` espurio.
  - `fill_zones`: `run_drc()` inmediato sin `hole_clearance`/`clearance`
    espurio vs Zone GND en 3/3.
  - `add_zone(fill=True)`: idem, 3/3.
- **V3**: nunca activada en ~15 operaciones de la sesión.
- **V4 con D-26.1**: baseline 0 violaciones no-triviales (predicción
  0-1, extremo favorable). Ratifica D-26.1 con matiz metodológico
  documentado arriba.
- **V5**: F-D5-01 no apareció en 3 corridas, sigue P3 vigilancia.

## Contrato D-23.2 acumulado en producción real

Evidencia acumulada hasta cierre de D6:

| Tool | Corridas verdes | Origen |
|---|---|---|
| `route_board` | 8/8 | 2 sesión 24 (test regresión) + 3 D5 + 3 D6 |
| `fill_zones` | 4/4 | 2 sesión 27 (test regresión) + 2 D6 (V2-fill_zones + fill_zones intermedio) |
| `add_zone(fill=True)` | 3/3 | 2 sesión 27 (test regresión) + 1 D6 (V2-add_zone-1) |

Total: 15/15 corridas verdes en producción real, 0 divergencias.

## Fricciones

**F-D6-01 — Costo de re-ruteo parcial no barato** (severidad `info`,
bajo costo, no bloqueante). Re-ruteo parcial de 1 net: 110-112s en D6
vs 9-10s en D5. Con N=4 total, el rango es 9s-112s — el "modelo barato"
que D5 sugería con solo 2 muestras no se sostiene. Va a P3 vigilancia
con protocolo: 2-3 mediciones más en D7 (N=6-7 total). Si aún no muestra
patrón claro, cerrar como "variabilidad inherente de Freerouting" y
actualizar modelo mental de `route_ms` en documentación.

## Observaciones adicionales

**Drift documental detectado** (no fricción de tool). `docs/CONTEXT.md
§"Decisiones vigentes"` sigue diciendo que D-23.2 solo cubre
`route_board`, cuando el resto del propio documento y ADR-0012 ya
reflejan la extensión de sesión 27. Es error del arquitecto en los
diffs de consolidación post-27. Corregido en consolidación post-D6.
**Origina D-28.2** — deuda del arquitecto formalizada: barrido completo
de sitios al generar diffs de decisiones.

**El D6 fue réplica exacta del layout D5.** Consecuencia: la
ratificación estadística D5+D6 es más débil de lo que parece porque
las dos corridas testean literalmente la misma geometría. Cambios en
régimen de ruteo, colisiones distintas, escenarios de fill diferentes
— todo queda sin ejercitar. **D7 va a introducir variación geométrica
controlada** (mismo footprint set, mismo outline, coordenadas
distintas) para ratificar bajo condiciones no idénticas sin escalar
complejidad.

## Recomendación para sesión 29 (D7)

D7 = tercer dogfooding de ratificación, buscando el 3er verde
consecutivo del criterio de cierre de Fase 3. Tres novedades:

1. **Orden mandatorio de fases con D-28.1 vinculante:** plano GND
   ANTES de la colocación masiva (orden exacto de D5), AskUserQuestion
   obligatoria si el agente considera desviarse.
2. **Aislamiento correcto de D-26.1:** con plano fresco pre-colocación,
   leer baseline SIN `fill_zones()` primero (predicción: violaciones
   fantasma como D5) → aplicar `fill_zones()` → releer baseline
   (predicción: 0 violaciones). Separa el efecto del orden del efecto
   de D-26.1 sin confusor.
3. **Variación geométrica controlada:** mismo footprint set, mismo
   outline 44×44, mismo sch — pero coordenadas de colocación distintas
   dentro del outline (respetando D-D3.1 ≥1.5-2mm de borde). No es
   escalada de complejidad, es control de variable "layout".
4. **Protocolo F-D6-01:** 2-3 mediciones adicionales de re-ruteo parcial
   para llegar a N=6-7 total.

Si D7 sale verde con estos ajustes, el criterio de cierre de Fase 3
queda satisfecho y corresponde iniciar preparación de Fase 4.

## Artefactos

- Log completo de fricciones y 16-question report:
  `/tmp/dogfood6-fricciones.md` (635 líneas).
- Fixture actualizado: `tests/fixtures/despertador-routed/`
  (`.kicad_pcb` cambió, sch/pro/prl bit-idénticos a D5). README
  reescrito con procedencia D6, sesión 28, commit base `fba66b7`.
- Gerbers: `/tmp/gui-test-project/fab/` (26 archivos, gate G3 limpio).
- BOM: `/tmp/gui-test-project/bom.csv`.
