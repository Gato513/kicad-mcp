# Coverage Matrix — Validation Suite

Matriz viva de features ejercitadas por cada proyecto de la Validation
Suite (D-30.4 — criterio de diversidad). Primera creación: sesión 31.
Se actualiza tras cada validación admitida (no necesariamente cerrada —
un proyecto ADMITIDO en Bloque 0 ya aporta a la diversidad, aunque el
Bloque 2/3 no cierre; ver nota al pie).

| Feature | despertador (interno, Fase 1-3) | anavi-dev-mic (Nivel A-01, sesión 31) |
|---|---|---|
| Capas: 2 | ✓ | ✓ |
| Capas: 4+ | | |
| Plano GND: single | ✓ | ✓ (B.Cu, plano completo) |
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
| Footprints: sin anotar / refs duplicados | | ✓ (4× `REF**` — origen de F-V1-02) |
| Footprints: sólo-mecánicos (sin net) | | ✓ (mounting holes) |
| Footprints: decorativos (logo, 0 pads) | | ✓ (`G***`) |
| Netclasses múltiples explícitas | | ✓ (`Default`/`usb`/`vcc`, aunque `usb`/`vcc` sin nets asignadas) |
| Contorno: rectangular | ✓ | |
| Contorno: octagonal (esquinas cortadas) | | ✓ |
| Densidad: baja (<30%) | | |
| Densidad: media (30-50%) | | |
| Densidad: alta (>50%) | ✓ (~94% B.Cu ruteado) | ✓ (~70% B.Cu, GND plano) |
| Migración de formato KiCad | | no aplicó (ground truth ya nativo KiCad 10) |
| DRC 0/0 en ground truth | n/a (fixture interno) | ✗ — admitido con excepción documentada (18 errores preexistentes al autor) |
| Validación D-30.3 cerrada (4 criterios medidos) | n/a | ✗ — bloqueada en `route_board` (F-V1-02), ver `validation-report.md` |

## Nota sobre "admitido pero no cerrado"

`anavi-dev-mic` es el primer caso de la Suite que llega a esta matriz sin
haber cerrado una validación D-30.3 completa (sesión 31 se detuvo en
`route_board` por `F-V1-02`, P0). Se incluye igual porque:

1. Las features de su **diseño** (footprints, netclasses, contorno,
   protocolo, densidad de colocación lograda) son reales y verificadas —
   no dependen de que el ruteo haya terminado.
2. Ocultarlo de la matriz escondería la diversidad real que ya aportó
   (en particular, es el único proyecto que expuso la clase de defecto
   "refs duplicados/sin anotar" — información valiosa para sesiones
   futuras incluso sin cierre).
3. La fila "Validación D-30.3 cerrada" documenta explícitamente el estado
   pendiente, sin fingir un cierre que no ocurrió.

Cuando sesión 31 se reintente (post-fix de F-V1-02, ver
`docs/BACKLOG.md` §P0), esta fila se actualiza a ✓ y se completan las
filas de densidad con el dato medido del output real.
