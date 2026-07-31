# Coverage Matrix — Validation Suite

Matriz viva de features ejercitadas por cada proyecto de la Validation
Suite (D-30.4 — criterio de diversidad). Primera creación: sesión 31.
Se actualiza tras cada validación admitida (no necesariamente cerrada —
un proyecto ADMITIDO en Bloque 0 ya aporta a la diversidad, aunque el
Bloque 2/3 no cierre; ver nota al pie).

| Feature | despertador (interno, Fase 1-3) | anavi-dev-mic (Nivel A-01, sesión 31→31b→31c) | anavi-macro-pad-12 (Nivel B-01, sesión 32) | hackrf-one (Nivel C-01, sesión 33) |
|---|---|---|---|---|
| Capas: 2 | ✓ | ✓ | ✓ | |
| Capas: 4+ | | | | ✓ (F/In1/In2/B, stackup RF real — NUEVO) |
| Plano GND: single | ✓ | ✓ (B.Cu, plano completo, ruteado y refilleado post-route) | ✓ (B.Cu; GT usa 2 zonas GND, flujo usa 1 — patrón heredado D-26.1) | ✓ (In1.Cu; GT usa GND+VCC+VAA+USB_SHIELD en 4 zonas/capas, flujo intentó replicar y crasheó 3× — ver F-V3-ZONE-FILL-CRASH, quedó solo GND) |
| Plano GND: múltiple/mixto | | | | ✗ intentado, no logrado (crash reproducido 3×, ver fricciones) |
| MCU: AVR/ATtiny | ✓ | | | |
| MCU: ESP8266/ESP32 | | | | |
| MCU: RP2040 (vía módulo XIAO) | | ✓ | ✓ | |
| Interfaces: I²C | ✓ | | ✓ (conector I2C dedicado) | |
| Interfaces: UART | | | | |
| Interfaces: USB-C | | ✓ (vía módulo XIAO, no en el board directamente) | ✓ (vía módulo XIAO, no en el board directamente — confirmado: sin cobre propio de USB-C) | ✓ (conector propio en el board, cobre USB_SHIELD propio — primera vez con USB nativo — NUEVO) |
| Interfaces: micrófono digital (PDM) | | ✓ (MP23DB01HPTR) | | |
| Potencia: 12V + MOSFETs | | | | |
| RF: 1MHz-6GHz, frontend de precisión, SMA | | | | ✓ (NUEVO) |
| Footprints: THT | ✓ (conectores) | ✓ (J1/J2 headers, mounting holes) | ✓ (J1-J6 conectores 3-pin, mounting holes) | ✓ |
| Footprints: SMD estándar | ✓ | ✓ | ✓ | ✓ |
| Footprints: módulo grande (>15×15mm) | | ✓ (XIAO RP2040, 18.9×18.0mm) | ✓ (XIAO RP2040, mismo módulo) | ✓ (marco de shield RF J2, 51.6×41.4mm — NUEVO, ~2.5× más grande) |
| Footprints: QFN/LQFP alta densidad | | | | ✓ (LPC4320 LQFP144, XC2C64A VQFP100 — NUEVO) |
| Footprints: sin anotar / refs duplicados | | ✓ (4× `REF**` — origen de F-V1-02, resuelto sesión 31b con `set_footprint_ref`) | ✓ (4× `REF**` mounting holes — **presentes también en el ground truth sin anotar**, resuelto con `set_footprint_ref`, ADR-0013) | ✓ (17× `TESTPOINT-30MIL-MASKONLY`, resuelto con `set_footprint_ref` ×16, ADR-0013) |
| Footprints: sólo-mecánicos (sin net) | | ✓ (mounting holes) | ✓ (mounting holes) | ✓ (test points, fiducials) |
| Footprints: decorativos (logo, 0 pads) | | ✓ (`G***`) | ✓ (`G***`) | |
| Netclasses múltiples explícitas | | ✓ (`Default`/`usb`/`vcc`, aunque `usb`/`vcc` sin nets asignadas) | ✓ (mismo patrón `Default`/`usb`/`vcc` sin asignación — confirmado en 4/4 proyectos ANAVI verificados) | ✗ — **solo `Default`**, sin asignaciones (refutado en Bloque 0, D-33.1, antes de ejecutar) |
| **Matriz de teclas con diodo por tecla** | | | ✓ (12 switches × 12 diodos, topología en malla — NUEVO) | |
| **Backlighting por tecla (LED+resistor 1:1)** | | | ✓ (12 LED + 12 resistor — NUEVO) | |
| **Footprints hot-swap (sockets)** | | | ✓ (`keyswitches:Kailh_socket_MX` — NUEVO) | |
| **Esquemático jerárquico multi-hoja** | | | | ✓ (raíz + baseband/frontend/mcu — NUEVO) |
| Contorno: rectangular | ✓ | | ✓ | ✓ (aprox, con cutouts) |
| Contorno: octagonal (esquinas cortadas) | | ✓ | | |
| Densidad: baja (<30%) | | | | |
| Densidad: media (30-50%) | | | | |
| Densidad: alta (>50%) | ✓ (~94% B.Cu ruteado) | ✓ (93.42% B.Cu output, 70.18% B.Cu ground truth) | ✓ (90.07% B.Cu output, 63.88% B.Cu ground truth) | ✓ ground truth únicamente (90.17% In1.Cu) — **output no evaluable, sin ruteo** |
| **Migración de formato KiCad (real)** | | no aplicó (ground truth ya nativo KiCad 10) | ✓ (KiCad 6→10, primera migración real de la Suite — DRC post ⊂ DRC pre, sin categorías nuevas) | ✓ (KiCad 6→10, primer sch **jerárquico** migrado — hallazgo: `sch upgrade` de la raíz no migra sub-hojas automáticamente) |
| DRC 0/0 en ground truth | n/a (fixture interno) | ✗ — admitido con excepción documentada (18 errores preexistentes al autor) | ✗ — mismo precedente (19 errores preexistentes) | ✗ — mismo precedente (22 errores preexistentes, 0 unconnected) |
| `route_board` end-to-end sobre board externo | ✓ (interno) | ✓ — 15/15 nets ruteables completadas, 79 tracks, 6 vías, `route_ms` 184.8s (sesión 31c) | ✓ — 42/42 nets ruteables completadas, 429 tracks, 36 vías, `route_ms` 328.9s (sesión 32, tras 1 intento con timeout) | ✗ — **no completó**. Freerouting 2.1.0 crash-loop interno (`NullPointerException` en `MazeSearchAlgo`, 6× repetidas, sin progreso medible) hasta el timeout duro de 3600s. `F-V3-ROUTER-TIMEOUT-HARD`. |
| Validación D-30.3 cerrada (4 criterios medidos) | n/a | ✓ — medidos los 4 (1/4 cumple umbral: cobre; ver `metrics.md` y análisis H2), sesión 31c | ✓ — medidos los 4 (**3/4 cumplen**: tracks, vías, cobre; ver `metrics.md` y análisis H2), sesión 32 | ✗ — **0/4 evaluables** (sin ruteo, ratios numéricos sin sentido diagnóstico), sesión 33. Ver hallazgo lateral: descomposición por capa del ground truth (schema 1.2) sí aportó señal nueva independiente del ruteo. |

**Escala (referencia de tamaño, no una fila de feature per se):**
despertador 23 fp/19 nets · anavi-dev-mic 13 fp/20 nets · anavi-macro-pad-12
63 fp/48 nets (~3x Nivel A) · **hackrf-one 437 fp/380 nets** (~7× Nivel B,
~34× Nivel A — salto de escala, no incremental, primera entrada en rango
"complejidad alta" real de la Suite).

## Nota sobre la historia de esta validación (sesión 31 → 31b → 31c)

`anavi-dev-mic` es el primer proyecto de la Suite en atravesar las 3
fases del ciclo de vida de una validación: admisión + bloqueo (sesión 31,
`route_board` falló por `F-V1-02`), fix intermedio (sesión 31b,
`set_footprint_ref` + pre-check `DUPLICATE_REFS`, ADR-0013), y reintento
completo (sesión 31c, flujo canónico end-to-end + comparación D-30.3
cerrada). La fila "Validación D-30.3 cerrada" pasó de ✗ a ✓ — "cerrada"
significa que los 4 criterios se **midieron** de punta a punta, no que
los 4 hayan cumplido el umbral (sólo cobre cumple; ver `metrics.md`
§Veredicto final y el análisis H2 sobre por qué los otros 3 no
necesariamente indican una placa inválida). Detalle completo en
`validation-report.md` y `docs/historico/sesiones/31c-reporte.md`.

## Nota sobre sesión 32 (Nivel B-01)

`anavi-macro-pad-12` cerró en una sola sesión (a diferencia del ciclo de
3 de Nivel A). El candidato prescrito por el prompt (ANAVI Miracle
Emitter) fue refutado en Bloque 0 por no aportar diversidad D-30.4 real
ni alcanzar escala de Nivel B — la re-selección está documentada en
`validation-suite/level-b/anavi-macro-pad-12/README.md`. 3 de 4 criterios
D-30.3 cumplen — mejor resultado que Nivel A — pero la sesión produjo un
hallazgo de robustez independiente más significativo que el resultado
cuantitativo en sí: `route_board(refill=true)` puede fallar en silencio
su paso de refill de seguridad (`F-V2-REFILL-SILENCIOSO`, P0/P1,
confirmado reproducible también en el audit log de sesión 31c — nunca
antes documentado). Detalle completo en `validation-report.md`,
`metrics.md` y `docs/historico/sesiones/32-reporte.md`.

## Nota sobre sesión 33 (Nivel C-01, cierre de la trilogía A+B+C)

`hackrf-one` cerró en una sola sesión, como Nivel B. A diferencia de A/B,
el resultado es una **refutación por escalabilidad** (escenario 6/7,
válido y de alto valor informativo por diseño de Nivel C): `route_board`
no completó — Freerouting 2.1.0 entró en un régimen de excepciones
internas repetidas (`NullPointerException`, sin progreso medible) hasta
el timeout duro de 3600s, un patrón distinto y más específico que el
"score estancado" de sesión 32. Los 4 criterios D-30.3 quedan **no
evaluables** (no "no cumplidos" — sin ruteo, un ratio numérico no tiene
sentido diagnóstico). La sesión produjo además un hallazgo de robustez
independiente reproducido 3 veces (`F-V3-ZONE-FILL-CRASH`:
`add_zone(fill=true)` crashea KiCad en la 3ª-4ª llamada consecutiva sobre
este board de 437 footprints, sin correlación con overlap geométrico —
hipótesis inicial refutada explícitamente, D-33.1). Detalle completo en
`validation-report.md`, `metrics.md` y
`docs/historico/sesiones/33-reporte.md`. Síntesis de los 3 puntos de
evidencia sobre D-30.3 en `docs/analisis/validation-suite-sintesis-A-B-C.md`.
