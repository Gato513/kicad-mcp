# Sesión 19b — Corrección del esquemático del despertador (deuda del arquitecto)

**Tipo:** DEV sobre kicad-mcp, **nueva rama**
`sesion/19b-sch-fix-despertador` desde `master` (tras merge de sesiones 19 +
19d si ambas cierran).

**Origen:** Deuda documentada en CONTEXT v2 §Deuda del arquitecto. El sch
del despertador tiene 4 defectos eléctricos que arrastramos desde el
Dogfooding 2. El D3 requiere el sch corregido antes de arrancar.

**Criterio de cierre:** `run_erc()` sobre el sch del despertador devuelve
**0 errores, 0 warnings** (permitido: warnings de tipo
`unconnected_wire_endpoint` en pines auxiliares — se documentan explícito).
El F8 (sync sch→pcb) corre limpio. El fixture `despertador-routed` queda
invalidado y se regenera con el sch nuevo.

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4.

**Esta sesión toca ÚNICAMENTE el sch del despertador
(`/tmp/gui-test-project/despertador_inteligente.kicad_sch`).** No toca el
server, no toca tests, no toca docs salvo el reporte final y el README del
fixture.

**Si el agente detecta que alguna tool del server no puede resolver la
corrección del sch → parar, reportar, no improvisar.** El sch se puede
editar a mano si es necesario (KiCad tiene GUI), pero registrar el paso
como fricción de tool.

---

## Contexto — los 5 defectos a corregir

Del reporte del Dogfooding 2 y confirmado por el brief real (sesión 15):

### Defecto 1: pin_to_pin INT U2↔U3

- U2 (MPU-6050): pin INT es salida (interrupt output).
- U3 (MAX30102): pin INT también es salida.
- Actualmente están **atadas en la misma net** → ERC error pin_to_pin (dos
  outputs no pueden compartir net).
- **Fix:** asignar cada INT a un pin distinto del ATtiny85 (U1). U1 tiene
  pocos pines libres (SOIC-8: PB0-PB5); si no hay pines libres para 2
  interrupts, atarlas vía un wired-OR (una resistencia pull-up + ambos INT
  como open-drain al mismo pin).
- **Verificación de hoja de datos:**
  - MPU-6050 INT: open-drain configurable (registro `INT_PIN_CFG` bit 6-7).
  - MAX30102 INT: open-drain fija por diseño.
  - Ambos son open-drain → **wired-OR viable.**

### Defecto 2: pin_not_connected en U3

- Un pin de U3 (MAX30102) sin conectar y sin flag "No Connect" explícito.
- **Fix:** agregar símbolo "No Connect" (`~` en KiCad) al pin
  correspondiente, o conectarlo si el pinout lo requiere. **Verificar el
  pinout de MAX30102 LQFP-14** antes de tomar decisión.

### Defecto 3: Net /SDA fusionada con /INT_SENS

- La net del bus I2C (SDA) y la de sensor interrupt aparecen fusionadas.
- **Fix:** separar los cables en el sch. Probable causa: un cable de INT
  cruza SDA y KiCad lo interpretó como conexión. Enrutar los cables por
  caminos distintos.

### Defecto 4: Net /NSS (CS del RFM69CW) fusionada con /MOSI

- U4.3 (NSS/CS) y U4.5 (MOSI) en la misma net.
- **Fix:** separar. NSS debe ir a un pin GPIO libre de U1 (probablemente
  PB0 si no está usado); MOSI mantiene su conexión al PB1.

### Defecto 5 (limpieza): J1 debe tener `in_bom=no`

- Tag-Connect es programador, no va en BOM de producción.
- **Fix:** editar propiedad del símbolo J1 en el sch para setear
  `in_bom=no` y `on_board=yes`.

---

## Flujo de trabajo

### Paso 1 — Análisis pre-fix (obligatorio)

1. `health()` — confirmar KiCad abierto con el sch correcto.
2. `run_erc()` — capturar el listado exacto de errores y warnings.
   Reportar en el diff del reporte final.
3. `get_world_context(kind="sch", max_tokens=8000)` — inventario de pines
   de U1 (ATtiny85). Necesitamos saber qué pines están libres.
4. Confirmar decisiones de hoja de datos:
   - Ambos INT open-drain → wired-OR sobre un pin único de U1 con pull-up.

### Paso 2 — Fix del sch (usando tools del server)

El agente debe hacer los 5 fixes **en el orden que las tools permitan**.
Si una tool falla o no existe para una operación específica:
- Reportar la fricción como F-19b-NN en el reporte.
- Editar a mano en la GUI de KiCad si es necesario.
- No inventar workarounds silenciosos.

Fixes:

1. **INT wired-OR** — ambos INT (U2 y U3) al mismo pin de U1 (proponer
   PB2 o el que esté libre). Pull-up de 10kΩ (R nueva) desde ese pin a VCC.
2. **NC en U3** — marcar el pin no conectado con "No Connect" explícito.
3. **Separar SDA de /INT_SENS** — reruteo de cables.
4. **Separar NSS de /MOSI** — reasignar NSS a otro pin GPIO de U1.
5. **J1.in_bom = no** — propiedad del símbolo.

### Paso 3 — Verificación

1. `run_erc()` → debe dar 0 errores. Warnings aceptables solo si están
   documentados con justificación.
2. Guardar sch.
3. F8 humano (sync sch → pcb) — instruir al humano: "Corré Tools → Update
   PCB from Schematic (F8) y avisame".
4. `get_world_context(kind="pcb", max_tokens=4000)` → verificar que los
   footprints se actualizaron sin errores.

### Paso 4 — Invalidar y regenerar fixture (si el tiempo alcanza)

El fixture `tests/fixtures/despertador-routed/` fue generado con el sch
VIEJO. Ahora es inválido — tiene nets fusionadas que ya no existen y le
falta la nueva R del pull-up.

**Opción A (recomendada, si el tiempo permite):** regenerar el fixture con
el sch corregido usando el patrón validado del Bloque 3 de 19c:
- Board vacío + plano GND + `route_board(timeout_s=900)`.
- Si converge: copiar `.kicad_pcb/.kicad_pro/.kicad_sch/.kicad_prl` a
  `tests/fixtures/despertador-routed/` sobrescribiendo. Actualizar el
  README del fixture con el nuevo commit.

**Opción B (fallback):** dejar el fixture viejo tal cual pero marcarlo como
STALE en su README con nota "invalidado por corrección de sch — regenerar
antes de sesión 20". Actualizar los tests que lo usan para skipear con
mensaje claro.

Elegir según el tiempo disponible. Si el ruteo del fixture nuevo se
complica, Opción B es aceptable.

---

## Reporte final (`docs/sesiones/19b-reporte.md`)

- Listado exacto de errores/warnings ERC pre-fix (paso 1) y post-fix
  (paso 3).
- Diff-resumen del `.kicad_sch` (cambios netos: pines reasignados,
  componentes agregados, propiedades modificadas).
- Fricciones de tool encontradas (F-19b-NN) — cada una con hint de qué
  tool falta o falla.
- Estado del fixture: regenerado (opción A) o marcado stale (opción B).
- Confirmación de F8 limpio.

## Env vars

Las mismas de 19c:

```bash
export KICAD_MCP_GUI_TEST=1
export KICAD_MCP_PROJECT=/tmp/gui-test-project
export KICAD_MCP_GUI_REF=U1
export KICAD_MCP_FREEROUTING_JAR=/home/astra/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar
```

**KiCad reiniciado limpio**, sch del despertador abierto en el Schematic
Editor.

## Cierre esperado

Sesión 19b cerrada → ERC limpio + fixture regenerado (o marcado stale) →
sesión 20 (Dogfooding 3, meta ≥8/10) tiene el sch corregido y el fixture
confiable.
