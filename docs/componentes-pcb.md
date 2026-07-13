# Componentes disponibles en el PCB de prueba

**Archivo:** `docs/componentes-pcb.md`
**Propósito:** Referencia permanente de los 202 componentes únicos en el
PCB de prueba (`/tmp/gui-test-project/video.kicad_pcb`). Consultable por
el agente durante sesiones de desarrollo para validación, tests e
implementación de features.

**Generado:** sesión 07
**Última actualización:** 2026-07-10

---

## Inventario completo (202 referencias)

### Capacitores (73)
C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14, C15, C16,
C17, C18, C19, C20, C21, C22, C23, C24, C25, C26, C27, C28, C29, C30,
C31, C32, C33, C34, C35, C36, C37, C38, C39, C40, C41, C42, C43, C44,
C45, C46, C47, C48, C49, C50, C51, C52, C53, C54, C55, C56, C57, C58,
C59, C60, C61, C62, C63, C64, C65, C66, C67, C68, C69, C70, C71, C72, C73

### Resistencias (48)
R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16,
R17, R18, R19, R20, R21, R22, R23, R24, R25, R26, R27, R28, R29, R30,
R31, R32, R33, R34, R35, R36, R37, R38, R39, R40, R41, R42, R43, R44,
R45, R46, R47, R48

### Circuitos integrados (24)
U1, U2, U3, U4, U5, U6, U7, U8, U9, U10, U11, U12, U13, U14, U15, U16,
U17, U18, U19, U20, U21, U22, U23, U24

### Conectores (12)
P1, P2, P3, P4, P5, P8, P9, P10, P11, P12, J4

### Diodos (5)
D1, D2, D3, D4, D6

### Inductores (6)
L1, L2, L3, L4, L5, L6

### Transistores (3)
Q1, Q2, Q3

### Cristales/osciladores (3)
X1, X2, X3

### Jumpers (5)
W1, W2, W3, W4, W5

### Arrays de resistencias (8)
RR1, RR2, RR3, RR4, RR5, RR6, RR7, RR8

### Componentes únicos (5)
BUS1 (bus conector), CV1 (cristal), POT1 (potenciómetro)

---

## Uso recomendado

### En desarrollo de features
- **Validación de referencias:** antes de implementar operaciones que
  busquen una ref (como `move_footprint`), verificá que la ref esté en
  esta lista para evitar errores de prueba.
- **Tests de mutaciones:** usá referencias de tipos variados:
  - Pequeñas: `R5`, `C10` (footprints compactos)
  - Grandes: `U1`, `U10` (ICs de 100+ pines)
  - Especiales: `P1` (conector), `W2` (jumper), `BUS1` (bus)

### En debugging
- Si el agente reporta "ref no encontrada", verificá aquí que la ref
  existe en el board.
- Si hay colisiones inesperadas, cruzá con esta lista.

### En tests de rendimiento / stress
- Chain de mutaciones: mutar 5–10 refs en cadena y medir latencia
  acumulada. Ejemplos: `[U1, R5, C10, P1, W2]`.
- Secuencia de deltas: cambios sucesivos sobre el mismo footprint y
  capturar delta cada vez.

---

## Notas técnicas

- **Total:** 202 referencias únicas en orden alfabético.
- **Fixture:** `004_real` de KiCad (7 hojas jerárquicas, 395 símbolos
  en esquemático, 202 footprints en PCB).
- **No todas visibles al inicio:** algunos componentes pueden estar
  fuera del canvas o superpuestos. El bridge accede a todos vía
  `snapshot_footprints()` y `get_footprints()` del objeto board de
  kipy.
- **Posiciones iniciales:** varían desde (0,0) a miles de milímetros.
  Consultar el bridge para leer posición actual de una ref.

---

## Actualización

Este archivo se regenera si el fixture `004_real` cambia. Para regenerar:

```bash
grep '"Reference"' /tmp/gui-test-project/*.kicad_pcb | awk -F'"' '{print $4}' | sort | uniq
```
