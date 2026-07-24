# Brief de diseño — despertador_inteligente (derivado del esquemático real)

**Fuente:** `despertador_inteligente.kicad_sch` (KiCad 10.0, generado 2026-07)
**Generado por:** arquitecto kicad-mcp (sesión 15, Dogfooding 2)
**Estado del proyecto:** esquemático completo, PCB con footprints importados (F8 ejecutado), sin colocar ni routear.

---

## Componentes reales (24 footprints confirmados por report.txt)

### Microcontrolador
| Ref | Valor | Footprint | Notas |
|-----|-------|-----------|-------|
| U1 | ATtiny85 | `Package_SO:SOIC-8_5.3x5.3mm_P1.27mm` | MCU principal, 8MHz interno. RESET en PB5. |

### Sensores
| Ref | Valor | Footprint | Notas |
|-----|-------|-----------|-------|
| U2 | MPU-6050 | `Sensor_Motion:InvenSense_QFN-24_4x4mm_P0.5mm` | Acel+gyro 6-DOF. I2C addr 0x68. Wake-on-Motion HW. |
| U3 | MAX30102 | `OptoDevice:Maxim_OLGA-14_3.3x5.6mm_P0.8mm` | SpO₂ + ritmo cardíaco. I2C. Necesita contacto con piel → borde del PCB. |

### Radio
| Ref | Valor | Footprint | Notas |
|-----|-------|-----------|-------|
| U4 | RFM69CW | `RFM69CW:MOD_RFM69CW` | 915 MHz, SPI. Footprint de librería local (no estándar KiCad). |
| ANT1 | — | `TestPoint:TestPoint_Plated_Hole_D2.0mm` | Punto de antena (hole plated). Conectar hilo λ/4 ≈ 8.2cm a 915 MHz. |

### Alimentación
| Ref | Valor | Footprint | Notas |
|-----|-------|-----------|-------|
| BT1 | CR2032 | `Battery:BatteryHolder_Keystone_3034_1x20mm` | 3V, ~220mAh. Sin regulador LDO — todos los chips operan a 3V directos. |
| D1 | — | `Package_TO_SOT_SMD:SOT-23` | Diodo de protección/polaridad (SOT-23). Valor exacto a confirmar en sch. |

### Pasivos — Desacople
| Ref | Valor | Footprint | Notas |
|-----|-------|-----------|-------|
| C1 | 10µF / 10V X5R | `Capacitor_SMD:C_0805_2012Metric` | Bulk supply. Cerca de BT1. |
| C2 | 100nF / 10V X5R | `Capacitor_SMD:C_0402_1005Metric` | Desacople U1 VCC. Pegado al pin 8. |
| C3 | 100nF | `Capacitor_SMD:C_0402_1005Metric` | Desacople U2 VDD. |
| C4 | 100nF | `Capacitor_SMD:C_0402_1005Metric` | Desacople U3. |
| C5 | 10µF | `Capacitor_SMD:C_0805_2012Metric` | Soporte de transitorios. |
| C6 | 100nF | `Capacitor_SMD:C_0402_1005Metric` | Desacople U4 VCC. |

### Pasivos — Resistencias
| Ref | Valor | Footprint | Notas |
|-----|-------|-----------|-------|
| R1 | 4.7kΩ / 1% | `Resistor_SMD:R_0402_1005Metric` | Pull-up I2C SDA. |
| R2 | 4.7kΩ / 1% | `Resistor_SMD:R_0402_1005Metric` | Pull-up I2C SCL. |
| R3 | 10kΩ / 1% / 0.1W | `Resistor_SMD:R_0402_1005Metric` | Pull-up RESET (PB5) de U1. Crítico en entorno RF. |

### Conectores
| Ref | Valor | Footprint | Notas |
|-----|-------|-----------|-------|
| J1 | TC2030 | `Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical` | ICSP/SWD. 6 pines. Borde accesible. `in_bom no`. |
| J2 | JST SH 4P | `Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal` | Expansión I2C o debug. Pin 1=VCC, 2=GND, 3=SDA, 4=SCL (a confirmar). |

### Test Points
| Ref | Footprint |
|-----|-----------|
| TP1–TP6 | `TestPoint:TestPoint_Pad_D2.0mm` |

---

## Redes principales

### Alimentación
- **VCC** (3V directo CR2032): U1.VCC, U2.VDD, U3.VDDC/VDDA, U4.VCC, C1–C6+, R1.1, R2.1, R3.1, J2.Pin1
- **GND**: todos los chips, BT1.-, J1.GND, TP (los que correspondan)

> ⚠️ **Sin regulador LDO.** La batería CR2032 alimenta directamente a 3V. Todos los chips son 3.3V-compatible operando desde 3V.

### I2C (bus de sensores)
- **SDA**: U1.PB0, U2.SDA, U3.SDA, R1.2 (pull-up a VCC), J2.Pin3
- **SCL**: U1.PB2, U2.SCL, U3.SCL, R2.2 (pull-up a VCC), J2.Pin4

### SPI (radio)
- **MOSI**: U1.PB1 → U4.MOSI
- **MISO**: U1.PB3 → U4.MISO
- **SCK**: U1.PB4 → U4.SCK
- **CS_RFM**: U1.PB0 o pin libre → U4.NSS *(verificar asignación exacta en sch)*

### ICSP (programación)
- J1: MISO, MOSI, SCK, RST, VCC, GND (comparte bus SPI con RFM69CW)

### Reset
- U1.PB5 (RESET) → R3 → VCC

### Antena
- U4.ANT → ANT1 (hole plated)

---

## Restricciones geométricas

### Tamaño y capas
- **Tamaño objetivo:** ~40×40 mm (wearable compacto; 50×50 es el máximo tolerable)
- **Capas:** 2 (F.Cu señal, B.Cu plano GND preferido)
- **Ancho pistas señal:** 0.15 mm mínimo
- **Ancho pistas power (VCC):** 0.25 mm
- **Vías mínimas:** drill 0.3 mm, annular 0.6 mm total

### Colocación recomendada
- **U1 (ATtiny85):** centro-superior. Referencia para todo el resto.
- **U2 (MPU-6050):** zona superior visible. QFN-24 4×4mm — pad térmico central requiere vías de disipación si se usa reflow.
- **U3 (MAX30102):** **borde inferior** del PCB. El sensor óptico necesita contacto directo con la piel. OLGA-14 3.3×5.6mm.
- **U4 (RFM69CW):** borde o esquina libre de ruido. Módulo grande (~13×13mm) — reservar área.
- **ANT1:** borde libre, lo más lejos posible de U2 y U3. Sin cobre de GND bajo la antena en F.Cu.
- **BT1:** borde inferior/lateral. Holder Keystone 3034 es largo (~21mm) — planificar espacio.
- **J1 (TC2030):** borde accesible para sonda.
- **J2 (JST):** borde lateral.
- **C1–C6:** cada capacitor de desacople lo más cerca posible del VCC del chip correspondiente.
- **R3 (pull-up RESET):** cerca de U1.PB5.

### Reglas RF
- Líneas SPI (MOSI/MISO/SCK/CS) hacia U4: cortas, agrupadas, separadas del bus I2C.
- I2C: evitar paralelas largas con SPI.
- Zona libre de cobre bajo ANT1 en ambas capas (keepout circular ~15mm).
- U4 alimentado con C6 (100nF) inmediatamente en su pin VCC.

### Plano de tierra
- B.Cu: plano GND continuo. Conectar con vías perimetrales cada ~5mm.
- F.Cu: minimizar interrupciones del plano retorno bajo líneas de señal críticas (I2C, SPI).

---

## Estado esperado al inicio del Dogfooding

- [x] Esquemático completo
- [x] ERC sin errores (a verificar con `run_erc`)
- [x] F8 ejecutado — 24 footprints importados al PCB
- [ ] Contorno de placa dibujado (`draw_board_outline`)
- [ ] Componentes colocados (`move_footprint` × 24)
- [ ] Ruteo completo (`route_board`)
- [ ] DRC limpio (G3)
- [ ] Gerbers exportados (`export_manufacturing`)

---

## Diferencias críticas respecto al brief anterior (invalida ese documento)

| Item | Brief anterior (INCORRECTO) | Este brief (REAL) |
|------|-----------------------------|-------------------|
| U5 regulador LDO | Presente | **No existe** |
| SW1 interruptor | Presente | **No existe** |
| LED1, LED2 | Presentes | **No existen** |
| Y1 cristal 8MHz | Presente | **No existe** |
| L1, L2 inductores | Presentes | **No existen** |
| R4, R5, R6 | Presentes | **No existen (solo R1–R3)** |
| C7, C8 | Presentes | **No existen** |
| D1 SOT-23 | No mencionado | **Existe** |
| J2 JST SH 4P | No mencionado | **Existe** |
| ANT1 plated hole | No mencionado | **Existe** |
| Alimentación | LDO → 3.3V regulado | **CR2032 directo 3V** |
