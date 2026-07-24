# Sesión 25 — Dogfooding 5 (primer dogfooding de Fase 3)

**Rama:** `master` (sin cambios de código, solo actualización de fixture).
**Tipo:** dogfooding de ratificación (no de desarrollo). Placa despertador
ATtiny85 wearable, misma variable controlada que D3/D4. Objetivo primario:
ratificar F-D4-02 / contrato D-23.2 (ADR-0012) en producción.

## Resumen ejecutivo

**Nota: 9.5/10** (D2=7.5, D3=8.5, D4=4.5). Primer verde de Fase 3 sobre
variable controlada. Placa fabricable completa (ERC 0, colocación 23/23,
ruteo 10/10, DRC 0/0, gerbers G3 limpios, BOM exportado, fixture actualizado).
Contrato D-23.2 **ratificado 3/3** sin excepción (V2 reforzado: total y
`por_tipo` coinciden, mtime cambia post-route en las 3 corridas, cero
`EXTERNAL_EDIT_DETECTED` espurio). Combinado con las 2/2 corridas del test
de regresión de sesión 24, tenemos **5/5 corridas en producción real** —
el contrato aguanta. Cero contactos humanos, cero fricciones bloqueantes,
V3 nunca activada. Único hallazgo: F-D5-01 (isla GND sin vía al plano tras
primera corrida, severidad `info`, resuelta con `add_via` puntual con
visibilidad completa vía `get_tracks`+`get_footprint_neighbors` — sin
cirugía a ciegas).

## Métricas comparativas

| Métrica | D2 | D3 | D4 | D5 |
|---|---|---|---|---|
| Nota | 7.5 | 8.5 | 4.5 | **9.5** |
| Fricciones bloqueantes | 0-1 | 1 externa | 1 P0 interna | **0** |
| `route_ms` corrida completa | 925s | 53s | 36.7s | **128.8s** |
| Contactos humanos | 5 | 2 | 0 | **0** |
| Errores DRC introducidos post-route | 53 (enmascarados) | 0 | 42 (obsoletos) | **1 (F-D5-01, resuelto)** |
| mtime cambia post-route | N/A | N/A | N/A | **sí, 3/3** |
| `EXTERNAL_EDIT_DETECTED` espurio | N/A | N/A | N/A | **no, 0/3** |

## Ratificación F-D4-02 / contrato D-23.2

V2 reforzado consolidado, 3 corridas:

| Corrida | `err_post` | `run_drc()` indep. | Coinciden | mtime cambió | `EXTERNAL_EDIT_DETECTED` |
|---|---|---|---|---|---|
| 1 | 1 (unconnected_items) | 1 (unconnected_items) | sí | sí (+221s) | no |
| 2 | 0 | 0 | sí | sí (+35s) | no |
| 3 | 0 | 0 | sí | sí (+36s) | no |

Cross-check discontinuado tras 3/3 limpio (regla del protocolo). El
workaround manual de refill que el fixture D3 documentaba como obligatorio
(F-03 sesión 20) queda **explícitamente obsoleto** — no fue necesario ni
una vez en las 3 corridas de D5. README del fixture actualizado en
consecuencia.

**Alcance de la ratificación:** contrato D-23.2 en `route_board`
solamente. `fill_zones` y `add_zone(fill=True)` no se ejercitaron con
carga significativa (solo `add_zone` inicial del plano GND, y
`add_keepout_zone` de test Fase 7). La generalización a esas dos tools
(sesión 27, backlog P2) sigue siendo trabajo real, no formalidad — la
ratificación acá no la reemplaza.

## Fricciones

**F-D5-01 — Isla GND sin vía al plano tras primer autoroute** (info,
bajo costo). Tras corrida 1, C2 y C3 (ambos GND) quedaron unidos entre
sí por un track pero sin vía propia al plano B.Cu. Diagnóstico con
`get_tracks(net=GND, bbox=...)` + `get_footprint_neighbors` (visibilidad
completa, sin adivinar). Fix con `add_via` puntual. 0 errores tras el fix.
**Interpretación arquitectónica:** dato genuino de comportamiento de
Freerouting — el motor conecta pad-a-pad dentro del net GND sin garantizar
conectividad global de la isla al plano fillado. Una sola ocurrencia no
ratifica patrón. Vale la pena vigilar en D6/D7 si el patrón se repite con
geometría similar (dos caps SMD en columna cerca del borde de zona). Va a
backlog como P3 vigilancia, no acción.

## Datos a vigilar (no fricciones)

**`route_ms` de la corrida completa (128.8s)** parece outlier respecto a
D3 (53s) y D4 (36.7s), pero está en el rango de las 2 corridas del test de
regresión de sesión 24 (186.5s y 150.2s). Con N=5 corridas históricas
(D3, D4, 2×sesión 24, D5), el techo real parece estar cerca de 200s, no
de 53s. Actualizar modelo mental de "route_ms esperado" para futuros
dogfoodings — no tomar 53s como referencia baja. Sin acción por ahora.

**Baseline V4 con cero courtyards/edge/silkscreen residuales.** El
protocolo esperaba ~5 errores residuales en el baseline pre-route (basado
en las 5 residuales que reportaba el test de regresión de sesión 24). D5
resultó en 0 courtyards + 0 edge + 0 silkscreen, atribuible a colocación
generosa con margen ≥1.5-2mm sistemático (D-D3.1 aplicado). Consecuencia:
la allowlist candidata prevista no aplica en esta sesión. No es problema
— solo actualizar expectativa. En D6 puede reaparecer si colocación es
menos cuidadosa; la allowlist queda diferida hasta que aparezcan
residuales estables.

## Ratificaciones colaterales positivas

- **D-D4.1 (`get_footprint_neighbors` inclusivo)** ratificado con impacto
  real: detectó BT1/U4 fuera del contorno ANTES de rutear (12 llamadas
  totales en la sesión). Consolida la práctica.
- **D-19c.1 (add_keepout_zone POST-route inocuo)** ratificado en Fase 7
  (test explícito): agregar keepout redundante bajo ANT1 no generó
  errores DRC nuevos, remoción limpia con `delete_zone`.
- **Snapshot mtime post-save** (hallazgo #31 sesión 24): 0
  `EXTERNAL_EDIT_DETECTED` espurio en 3 corridas + 12+ tools posteriores.
  Cierra el potencial R14' que había quedado abierto conceptualmente.
- **F-D3-03** (revocada por sesión 24) no reapareció.

## Estado del ciclo tras D5

Verde. Corresponde avanzar al siguiente paso de la secuencia Fase 3
según `hoja-de-ruta-v4.md`:

1. Sesión 26 = fix P1 solder mask bridge ANT1 (si sigue vigente).
2. Sesión 27 = generalización D-23.2 a `fill_zones` +
   `add_zone(fill=True)` con base sólida ahora.
3. Sesión 28 = D6, segundo dogfooding de ratificación.
4. Si D6 verde → tercer verde consecutivo, considerar cierre de Fase 3.

**Interpretación de resultado:** un P0 nuevo en cualquiera de las sesiones
26, 27 o 28 se sospecha regresión del fix mergeado en la sesión inmediata
anterior hasta que se pruebe lo contrario (interpretación de Fase 3,
distinta de Fase 2).

## Artefactos

- Log completo de fricciones y 14-question report:
  `/tmp/dogfood5-fricciones.md` (486 líneas).
- Fixture actualizado: `tests/fixtures/despertador-routed/` (`.kicad_pcb`
  y `.kicad_pro` cambiaron; `.kicad_sch`/`.kicad_prl` idénticos —
  esquemático no tocado). README reescrito con procedencia D5, sesión 25,
  commit base `100cb3a`, y sección explícita de ratificación D-23.2.
- Gerbers: `/tmp/gui-test-project/fab/` (26 archivos, gate G3 limpio).
- BOM: `/tmp/gui-test-project/bom.csv` (1423 bytes).
