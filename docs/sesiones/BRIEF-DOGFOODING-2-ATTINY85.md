# Brief de diseño — ATtiny85 Wearable Sensor Node

## Descripción general
Nodo wearable de bajo consumo para monitoreo de signos vitales y movimiento. Microcontrolador ATtiny85 con sensor IMU (MPU-6050), monitor cardíaco/SpO₂ (MAX30102), radio LoRa (RFM69CW), batería CR2032, e interfaces ICSP para programación. Diseño optimizado para portabilidad y bajo consumo de energía.

## Lista de componentes

### Microcontrolador y programa
- **U1**: ATtiny85 (SOIC-8, microcontrolador principal)
- **J1**: Conector ICSP (SPI Programming, 6 pines: MISO, MOSI, SCK, RST, VCC, GND)
- **Y1**: Cristal 8 MHz (si se usa reloj externo, footprint SMD 2016)

### Sensores
- **U2**: MPU-6050 (QFN-24, acelerómetro + giroscopio 6-DOF, I2C)
- **U3**: MAX30102 (LQFP-14, sensor de SpO₂ y ritmo cardíaco, I2C)

### Radio LoRa
- **U4**: RFM69CW (DFM-16, transceptor LoRa 915 MHz, SPI)
- **L1, L2**: Inductores RF/filtrado (SMD 0603)

### Regulación de potencia
- **U5**: Regulador 3.3V LDO (SOT-23-5, entrada 5V/batería)
- **CR2032**: Batería de botón (3V)
- **SW1**: Interruptor de encendido (pulsador SMD)

### Desacople y filtrado
- **C1, C2, C3, C4**: 100nF capacitores desacople (SMD 0603, en VCC de U1, U2, U3, U4)
- **C5, C6**: 10µF capacitores soporte transitorios (SMD 1206)
- **C7, C8**: Capacitores resonancia cristal (si aplica, 20pF típico)

### Pull-ups y resistencias
- **R1, R2**: 4.7kΩ pull-ups I2C SDA/SCL (SMD 0603)
- **R3, R4**: 10kΩ resistencias de configuración/reset (SMD 0603)
- **R5, R6**: Resistencias de termistor/sensor (valores a definir)

### Indicadores y prueba
- **LED1**: LED rojo SMD (indicador de encendido/estado, footprint 0603)
- **LED2**: LED verde SMD (indicador de transmisión, footprint 0603)
- **TP1-TP6**: Test points para depuración y medición (pads SMD)

## Redes principales (Nets)

### Alimentación
- **VCC_3V3**: Red de 3.3V regulado
  - Conecta: U1.VCC, U2.VDD, U3.VDDC/VDDA, U4.VCC, C1-C6.+, LED1.anode, LED2.anode, R1.1, R2.1, R3.1, R4.1, U5.OUT
- **VCC_RAW**: Entrada de batería/USB (5V si viene de regulador, o directo CR2032 en algunos casos)
  - Conecta: SW1, U5.IN (si se usa regulador)
- **GND**: Plano común de tierra
  - Conecta: U1.GND, U2.GND/DGND, U3.AGND/DGND, U4.GND, C1-C8.-, LED1.cathode, LED2.cathode, J1.GND, TP.GND, SW1.pad2

### I2C (Sensor bus)
- **SDA**: Línea de datos I2C
  - Conecta: U1.GPIO0, U2.SDA, U3.SDA, R1.2 (pull-up)
- **SCL**: Línea de reloj I2C
  - Conecta: U1.GPIO2, U2.SCL, U3.SCL, R2.2 (pull-up)

### SPI (Radio)
- **MOSI**: Master-Out-Slave-In
  - Conecta: U1.GPIO1, U4.MOSI
- **MISO**: Master-In-Slave-Out
  - Conecta: U1.GPIO3, U4.MISO
- **SCK**: Serial Clock
  - Conecta: U1.GPIO4, U4.SCK
- **CS_RFM**: Chip Select para RFM69CW
  - Conecta: U1.GPIO5, U4.NSS

### Cristal (si se usa)
- **XTAL_P**: Entrada cristal positiva
  - Conecta: U1.GPIO6, Y1.pad1, C7.1
- **XTAL_N**: Entrada cristal negativa
  - Conecta: U1.GPIO7, Y1.pad2, C8.1

### LEDs e indicadores
- **LED_PWR**: Control de LED de encendido
  - Conecta: U1.GPIO8 (via R5 limitador de corriente), LED1.cathode
- **LED_TX**: Control de LED de transmisión
  - Conecta: U1.GPIO9 (via R6 limitador), LED2.cathode

### Pines sin usar / Test Points
- **TP1-TP6**: Puntos de prueba para debugging, medir VCC, GND, y señales críticas

## Restricciones geométricas y notas de diseño

### Colocación
- **ATtiny85 (U1)**: Colocar en zona central o borde accesible (es pequeño, SOIC-8)
- **MPU-6050 (U2)**: Colocar en zona visible/superior del PCB (acelerómetro debe estar orientado)
- **MAX30102 (U3)**: Colocar en borde accesible (sensor óptico, necesita contacto con piel)
- **RFM69CW (U4)**: Colocar lejos de componentes de alto ruido; antenna (L2) cerca de borde
- **Batería CR2032**: Si se usa holder, colocar en borde inferior para facilidad de cambio
- **Conector ICSP (J1)**: Colocar en zona accesible para programación (típicamente borde)
- **LEDs (LED1, LED2)**: Colocar en zona visible del PCB

### Distancias y ruido
- Líneas I2C: evitar rotas rápidas digitales paralelas
- SPI: mantener las líneas del RFM69CW juntas y separadas de I2C si es posible
- Cristal (si existe): colocar cerca de U1 con capacitores de resonancia en paralelo; zona relativamente libre de EMI
- Capacitores desacople: lo más cerca posible de los VCC de cada chip (U1, U2, U3, U4)

### Topología del PCB
- Tamaño estimado: ~50x50 mm (compacto, wearable)
- Capas: 2 (F.Cu y B.Cu)
- Ancho mínimo de pistas: 0.15mm (señal), 0.25mm (power)
- Distancia mínima entre pistas: 0.15mm
- Vías mínimas: 0.3mm

### Rutas esperadas
- Tierra: plano continuo en B.Cu si es posible (facilita retorno de corrientes)
- Alimentación VCC_3V3: distribución radial desde U5 hacia chips
- I2C: líneas controladas en impedancia si el circuito requiere velocidades altas
- SPI: líneas cortas y directas hacia RFM69CW

## Estado actual del proyecto
- **Esquemático**: completo, ERC debe estar validado (todos los componentes presentes y conectados)
- **PCB**: proyecto vacío o con componentes sin colocar; F8 sincronización pendiente
- **Objetivo final**: placa completamente ruteada con DRC limpio, lista para fabricación (Gerbers exportados)

## Capacidades esperadas post-diseño
- Sensor de movimiento 6-DOF (acel + gyro) cada 100ms
- Monitoreo de ritmo cardíaco y SpO₂ vía MAX30102 cada 1s
- Transmisión LoRa a 915 MHz (modulable)
- Autonomía: ~48-72 horas con CR2032 (según consumo de muestreo)
- Bajo consumo en modo sleep (<10µA)

## Notas técnicas finales
- ATtiny85 opera a 8 MHz interno (puede subir a 16 MHz vía PLL si es necesario)
- MPU-6050 y MAX30102 requieren I2C; direcciones I2C: MPU=0x68, MAX=0x57 (típicas)
- RFM69CW: modulación GFSK, ancho de banda 61–250 kHz, potencia 5–20 dBm
- CR2032: capacidad ~220 mAh, ideal para bajo consumo
- ICSP: necesario para cargar firmware inicial en ATtiny85 (bootloader o direct programming)
