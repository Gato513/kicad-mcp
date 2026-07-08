# Fixtures de prueba

**Estado:** los fixtures 001–003 fueron **validados contra el motor de
conectividad real de KiCad** (kicad-cli 7.0.11: netlist exportada y comparada
miembro a miembro contra `ground_truth.json`). Pendiente del humano: re-validar
con kicad-cli de KiCad 10 en la máquina de desarrollo (mismo comando, §5) y
correr ERC (no disponible en kicad-cli 7).

## Principios

1. **Sintéticos y deterministas.** Generados por `generate_fixtures.py` con
   UUIDs `uuid5` → regenerar produce bytes idénticos. El generador es la
   fuente; los archivos generados se commitean igualmente (los tests no deben
   depender de regenerar).
2. **Ground truth independiente del archivo.** `ground_truth.json` lo calcula
   el generador desde su propia estructura de datos, NO parseando el archivo.
   El validador compara netlist real vs. ground truth: si el generador tuviera
   un bug de coordenadas, la netlist divergiría y el validador fallaría (así
   se detectó y corrigió un bug de layout en 003 durante su creación).
3. **Símbolos embebidos (FIXLIB).** Sin dependencia de librerías instaladas.
   Conectividad por global labels colocados exactamente en el endpoint de cada
   pin — sin wires ni junctions, eliminando la clase de error más frágil.
4. **Rasgos plantados.** Cada fixture contiene características deliberadas con
   valores exactos conocidos, para que los tests afirmen igualdad, no
   plausibilidad.
5. **Formato KiCad 7** (`version 20230121`): legible por KiCad 9/10. Si el
   humano los re-guarda desde KiCad 10, el formato se normaliza hacia arriba —
   permitido, pero entonces `generate_fixtures.py` deja de ser la fuente y
   debe marcarse como histórico.

## Inventario

### 001_basico — 5 componentes
MCU de 8 pines + pullups I2C + desacoplo + conector. Para tests unitarios
rápidos del encoder TOON y del parser.

Rasgos plantados: `U1.5` **sin conectar** (test de `list_unconnected`); net
`GND2X` con 2 miembros del mismo componente (U1.7–U1.8: test de nets
intra-componente); 6 nets, 1 pin suelto.

### 002_medio — 30 componentes
MCU48 + 8 desacoplos + bus I2C + 8 canales LED (R serie + LED) + 3 conectores.
El fixture de trabajo por defecto para tests de integración del encoder.

Rasgos plantados: `GND` con **42 miembros** (>8 → debe disparar el colapso de
nets de poder de TOON §4.1); exactamente **2 pines sin conectar** (`U1.33`,
`U1.34`); 30 nets totales; cadenas LED→LEDK→GND para tests de traversal de
netlist a 2 saltos.

### 003_grande — 150 componentes
10 bloques idénticos (1 conector + 14 resistencias) en grilla de 5×2. Prueba
de escala: presupuesto TOON, degradación por bloques, índice espacial.

Rasgos plantados (geometría exacta): bloques separados 76,2 mm; **un radio de
30 mm alrededor de cualquier `Jn` contiene exactamente los 15 componentes de
su bloque** (verificado: max distancia interna ≈ 24 mm, vecino más cercano a
76,2 mm). Es el ground truth de `focus_ref + radius_mm`. `GND` global con 150
miembros: el caso extremo de colapso.

### 004_real — proyecto del mundo real (TAREA DEL HUMANO)
Un proyecto KiCad real, open source, **multi-hoja**, de complejidad media.
Propósito: (a) verificar que el detector de jerarquía dispara
`UNSUPPORTED_HIERARCHY` limpiamente; (b) cuando el soporte multi-hoja llegue,
convertirse en el fixture de realismo (símbolos multi-unidad, pines
alternativos, campos sucios).

Criterios de selección: licencia libre (CERN-OHL/MIT/CC-BY), formato KiCad
7+, 2–5 hojas, 50–200 componentes. Candidatos donde buscar: proyectos de
placas de desarrollo publicados en GitHub con su hardware completo. Se
commitea con su archivo LICENSE y la URL de origen en `SOURCE.md`.

## Reglas para el agente

- Los fixtures son **datos de solo lectura** para los tests. Modificarlos =
  frontera F1 extendida: prohibido sin aprobación.
- Un test que necesita otro escenario **añade un fixture nuevo** al generador
  (función `build_00X`) con su ground truth; no muta los existentes.
- Prohibido cargar `fixture.kicad_sch` al contexto del agente (CLAUDE.md):
  se procesan con código.

## Validación

```bash
cd tests/fixtures
python3 generate_fixtures.py .      # regenerar (debe ser no-op en git)
python3 validate_fixtures.py .      # netlist real vs ground truth
# Con KiCad 10 (pendiente, máquina del humano):
kicad-cli sch erc --format json -o /tmp/erc.json 002_medio/fixture.kicad_sch
```

ERC esperado en 001/002: violaciones de tipo "input pin not driven" y "pin no
conectado" en los pines plantados — son deliberadas y forman parte del ground
truth de `run_erc` (los conteos exactos se fijarán al correr KiCad 10 por
primera vez y se añadirán a `ground_truth.json` como `erc_expected`).
