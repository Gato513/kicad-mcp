# Dogfooding Etapa 2 — Una placa real, de la nada a los gerbers

**QUÉ ES:** sesión de USO, no de desarrollo (mismas reglas que la Etapa
1: prohibido editar el repo de kicad-mcp; toda falla se REGISTRA en el
log de fricciones, no se arregla). Es la prueba de fuego del objetivo 1
de la hoja de ruta: diseñar una placa real completa con las tools,
apuntando a superar la nota 5/10 de la Etapa 1 — **objetivo ≥8/10**.

**ENTREGABLES:**
1. `/tmp/dogfood2-fricciones.md` — mismo formato F-NN de la Etapa 1
   (qué pasó / qué esperaba / workaround / costo / severidad), escrito
   EN EL MOMENTO. Sección final de Aciertos.
2. La placa: PCB colocado, contorneado, ruteado al 100% con DRC sin
   errores → render final → gerbers (G3).
3. Resumen final con la nota /10 y la comparación contra la Etapa 1.

---

## ⚠️ ESTADO REAL DEL PROYECTO AL INICIO DE ESTA SESIÓN

**El esquemático ya existe y está completo. El F8 ya fue ejecutado.**
No construyas el sch desde la paleta — ya existe en disco.

Estado verificado:
- [x] Esquemático completo (`despertador_inteligente.kicad_sch`)
- [x] ERC sin errores (confirmar con `run_erc` al inicio)
- [x] F8 ejecutado — 24 footprints importados al PCB (confirmado por report.txt)
- [ ] Contorno de placa — FALTA (`draw_board_outline`)
- [ ] Componentes colocados — FALTA (`move_footprint` × 24)
- [ ] Ruteo — FALTA (`route_board`)
- [ ] DRC limpio — FALTA (G3)
- [ ] Gerbers — FALTA (`export_manufacturing`)

**Tu trabajo empieza en el paso 3 del flujo (PCB).** Arrancá con:
1. `health()` — verificar que KiCad está corriendo con el proyecto correcto
2. `run_erc()` — confirmar ERC limpio
3. `get_world_context(kind="pcb", max_tokens=4000)` — ver los 24 footprints sin colocar
4. `draw_board_outline(...)` — antes de cualquier otra cosa en el PCB

---

## El proyecto

**Proyecto en disco:** `/tmp/gui-test-project/despertador_inteligente/`
**Nombre:** despertador_inteligente (nodo wearable ATtiny85)

---

## Brief de diseño — despertador_inteligente (REAL, derivado del esquemático)

> ⚠️ Este brief fue generado desde el esquemático real. Existe un brief
> anterior incorrecto que el arquitecto ya invalidó. Usar SOLO este.

### Componentes (24 footprints confirmados)

#### Microcontrolador
| Ref | Valor | Footprint | Notas |
|-----|-------|-----------|-------|
| U1 | ATtiny85 | `Package_SO:SOIC-8_5.3x5.3mm_P1.27mm` | MCU principal, 8MHz interno. RESET en PB5. |

#### Sensores
| Ref | Valor | Footprint | Notas |
|-----|-------|-----------|-------|
| U2 | MPU-6050 | `Sensor_Motion:InvenSense_QFN-24_4x4mm_P0.5mm` | Acel+gyro 6-DOF. I2C addr 0x68. |
| U3 | MAX30102 | `OptoDevice:Maxim_OLGA-14_3.3x5.6mm_P0.8mm` | SpO₂ + ritmo cardíaco. I2C. Sensor óptico → borde del PCB. |

#### Radio
| Ref | Valor | Footprint | Notas |
|-----|-------|-----------|-------|
| U4 | RFM69CW | `RFM69CW:MOD_RFM69CW` | 915 MHz, SPI. Módulo ~13×13mm. Librería local. |
| ANT1 | — | `TestPoint:TestPoint_Plated_Hole_D2.0mm` | Hole plated para antena. λ/4 ≈ 8.2cm. |

#### Alimentación
| Ref | Valor | Footprint | Notas |
|-----|-------|-----------|-------|
| BT1 | CR2032 | `Battery:BatteryHolder_Keystone_3034_1x20mm` | 3V directo. Sin LDO. Holder ~21mm de largo. |
| D1 | SOT-23 | `Package_TO_SOT_SMD:SOT-23` | Diodo protección. Confirmar valor con `get_world_context(kind="sch")`. |

#### Pasivos — Desacople
| Ref | Valor | Footprint |
|-----|-------|-----------|
| C1 | 10µF / 10V X5R | `Capacitor_SMD:C_0805_2012Metric` |
| C2 | 100nF / 10V X5R | `Capacitor_SMD:C_0402_1005Metric` |
| C3 | 100nF | `Capacitor_SMD:C_0402_1005Metric` |
| C4 | 100nF | `Capacitor_SMD:C_0402_1005Metric` |
| C5 | 10µF | `Capacitor_SMD:C_0805_2012Metric` |
| C6 | 100nF | `Capacitor_SMD:C_0402_1005Metric` |

#### Pasivos — Resistencias
| Ref | Valor | Footprint | Notas |
|-----|-------|-----------|-------|
| R1 | 4.7kΩ / 1% | `Resistor_SMD:R_0402_1005Metric` | Pull-up I2C SDA |
| R2 | 4.7kΩ / 1% | `Resistor_SMD:R_0402_1005Metric` | Pull-up I2C SCL |
| R3 | 10kΩ / 1% | `Resistor_SMD:R_0402_1005Metric` | Pull-up RESET (PB5). Crítico en entorno RF. |

#### Conectores
| Ref | Valor | Footprint | Notas |
|-----|-------|-----------|-------|
| J1 | TC2030 | `Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical` | ICSP 6 pines. `in_bom no`. |
| J2 | JST SH 4P | `Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal` | I2C externo: VCC/GND/SDA/SCL. |

#### Test Points
| Refs | Footprint |
|------|-----------|
| TP1–TP6 | `TestPoint:TestPoint_Pad_D2.0mm` |

### Redes principales

**Alimentación:**
- VCC (3V, CR2032 directo — SIN LDO): U1.VCC, U2.VDD, U3.VDDC/VDDA, U4.VCC, C1–C6+, R1.1, R2.1, R3.1, J2.1
- GND: todos los chips, BT1.-, J1.GND

**I2C:**
- SDA: U1.PB0 → U2.SDA, U3.SDA, R1.2, J2.3
- SCL: U1.PB2 → U2.SCL, U3.SCL, R2.2, J2.4

**SPI (radio):**
- MOSI: U1.PB1 → U4.MOSI
- MISO: U1.PB3 → U4.MISO
- SCK: U1.PB4 → U4.SCK
- CS_RFM: U1.PB0 → U4.NSS *(verificar en sch — posible conflicto con SDA)*

**Otros:**
- RESET: U1.PB5 → R3.1; R3.2 → VCC
- ANT: U4.ANT → ANT1

---

## Restricciones geométricas

**Tamaño:** ~40×40mm (máx 50×50mm). **Capas:** 2 (F.Cu + B.Cu).

**Colocación:**
- U1 (ATtiny85 SOIC-8): zona central
- U2 (MPU-6050 QFN-24): zona superior — orientación importa para acelerómetro
- U3 (MAX30102 OLGA-14): **borde inferior** — contacto con piel
- U4 (RFM69CW): esquina, lejos de U2/U3. Módulo grande, reservar ~14×14mm
- ANT1: borde libre. **Keepout de cobre ~15mm alrededor** (ambas capas)
- BT1: borde lateral. Ocupa ~21×10mm
- J1, J2: bordes accesibles
- C_desacople: inmediatamente junto al VCC de su chip
- R3: junto a U1.PB5

**Reglas:**
- Señal: 0.15mm mín. Power (VCC): 0.25mm mín. Vías: drill 0.3mm.
- SPI lines hacia U4: cortas, agrupadas, separadas de I2C.
- B.Cu: plano GND continuo preferido.

---

## Puntos de contacto humano

Solo estos (ya ocurrió H1 y H2):

- **H1 ✅ (ya hecho):** proyecto en disco + F8 ejecutado.
- **H2 ✅ (ya hecho):** F8 confirmado por report.txt (24 footprints importados).
- **H3 (tras route_board):** "File → Revert en el PCB Editor y avisame" → luego `get_world_context(kind='pcb', confirm_reloaded=true)`.
- **H4 (opcional):** validación visual de render intermedio.

---

## Flujo desde donde estás

Saltás directamente al paso 3:

```
health()
run_erc()                                    # confirmar sch limpio
get_world_context(kind="pcb", max_tokens=4000)  # ver los 24 fps sin colocar
draw_board_outline(x=0, y=0, width=40, height=40)
# → plan de colocación (breve, en el chat)
move_footprint(ref, x, y) × 24              # con deltas para verificar
save_board()
export_render()                              # render de control pre-route
route_board()                               # reportar route_ms
# → H3: humano recarga → confirm_reloaded=true
run_drc()                                   # diagnóstico
export_render()                             # render final
export_manufacturing()                      # G3 → gerbers
export_bom()
```

---

## Disciplina de contexto

Delta > mundo con focus > mundo completo. Renders con criterio (~11s c/u).
Reportar al final: llamadas por tool, tokens totales estimados, tiempo de sesión.

---

## Log de fricciones

Crear `/tmp/dogfood2-fricciones.md` al inicio. Formato:

```
## F-NN — Título
- **Qué pasó:** ...
- **Qué esperaba:** ...
- **Workaround:** ...
- **Costo:** [bajo/medio/alto]
- **Severidad:** [info/warn/bloqueante]
```

Escribirlo EN EL MOMENTO, no al final.

---

## Resumen final (última sección del log)

1. ¿Placa completa? (ERC ✓, colocado %, ruteado %, DRC, gerbers ✓/✗)
2. Tabla comparativa Etapa 1 vs Etapa 2.
3. Estado de las fricciones F-01..F-11 de la Etapa 1 desde tu experiencia de HOY.
4. Las 3 fricciones nuevas más caras (si las hay) con propuesta.
5. `route_ms` y calidad del ruteo (% completado, shorts, dangling tracks).
6. **Nota /10 con justificación** — objetivo ≥8.
7. ¿Qué falta para usar esto todas las semanas?
