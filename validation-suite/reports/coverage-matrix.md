# Coverage Matrix — Validation Suite

Matriz viva de features ejercitadas por cada proyecto de la Validation
Suite (D-30.4 — criterio de diversidad). Primera creación: sesión 31.
Se actualiza tras cada validación admitida (no necesariamente cerrada —
un proyecto ADMITIDO en Bloque 0 ya aporta a la diversidad, aunque el
Bloque 2/3 no cierre; ver nota al pie).

| Feature | despertador (interno, Fase 1-3) | anavi-dev-mic (Nivel A-01, sesión 31→31b→31c) |
|---|---|---|
| Capas: 2 | ✓ | ✓ |
| Capas: 4+ | | |
| Plano GND: single | ✓ | ✓ (B.Cu, plano completo, ruteado y refilleado post-route) |
| Plano GND: múltiple/mixto | | |
| MCU: AVR/ATtiny | ✓ | |
| MCU: ESP8266/ESP32 | | |
| MCU: RP2040 (vía módulo XIAO) | | ✓ |
| Interfaces: I²C | ✓ | |
| Interfaces: UART | | |
| Interfaces: USB-C | | ✓ (vía módulo XIAO, no en el board directamente) |
| Interfaces: micrófono digital (PDM) | | ✓ (MP23DB01HPTR) |
| Potencia: 12V + MOSFETs | | |
| Footprints: THT | ✓ (conectores) | ✓ (J1/J2 headers, mounting holes) |
| Footprints: SMD estándar | ✓ | ✓ |
| Footprints: módulo grande (>15×15mm) | | ✓ (XIAO RP2040, 18.9×18.0mm) |
| Footprints: sin anotar / refs duplicados | | ✓ (4× `REF**` — origen de F-V1-02, resuelto sesión 31b con `set_footprint_ref`) |
| Footprints: sólo-mecánicos (sin net) | | ✓ (mounting holes) |
| Footprints: decorativos (logo, 0 pads) | | ✓ (`G***`) |
| Netclasses múltiples explícitas | | ✓ (`Default`/`usb`/`vcc`, aunque `usb`/`vcc` sin nets asignadas) |
| Contorno: rectangular | ✓ | |
| Contorno: octagonal (esquinas cortadas) | | ✓ |
| Densidad: baja (<30%) | | |
| Densidad: media (30-50%) | | |
| Densidad: alta (>50%) | ✓ (~94% B.Cu ruteado) | ✓ (93.42% B.Cu output, 70.18% B.Cu ground truth) |
| Migración de formato KiCad | | no aplicó (ground truth ya nativo KiCad 10) |
| DRC 0/0 en ground truth | n/a (fixture interno) | ✗ — admitido con excepción documentada (18 errores preexistentes al autor) |
| `route_board` end-to-end sobre board externo (2 capas, 20 nets) | ✓ (interno) | ✓ — 15/15 nets ruteables completadas, 79 tracks, 6 vías, `route_ms` 184.8s (sesión 31c) |
| Validación D-30.3 cerrada (4 criterios medidos) | n/a | ✓ — medidos los 4 (1/4 cumple umbral: cobre; ver `metrics.md` y análisis H2), sesión 31c |

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
