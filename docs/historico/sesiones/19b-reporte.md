# Sesión 19b — Corrección del esquemático del despertador

**Rama:** `sesion/19b-sch-fix-despertador` · **Fecha:** 2026-07-22.

## Resumen

Corrección de los 5 defectos eléctricos documentados en
`docs/sesiones/prompts/PROMPT-SESION-19B.md` sobre
`/tmp/gui-test-project/despertador_inteligente.kicad_sch` (proyecto GUI
recreado desde cero copiando `despertador_inteligente/` del Desktop tras un
apagado entre sesiones — estado limpio confirmado por `health()`).

**Hallazgo central: ninguno de los 5 defectos es corregible con las tools del
server.** Las cuatro tools que mutan el `.kicad_sch`
(`add_symbol`, `set_value`, `set_footprint`, `connect_pins`, en
`src/kicad_mcp/tools/sch.py`) son puramente aditivas. Cada defecto requiere
**borrar/reenrutar un wire, agregar un flag No-Connect, o togglear un
atributo de símbolo (`in_bom`/`on_board`)** — ninguna operación existe en el
server. `connect_pins` sólo agrega labels locales; no puede *quitar* la
fusión de redes que ES el defecto. Siguiendo el fallback explícito del
prompt, **la corrección se hizo a mano en la GUI de KiCad**, con el agente
haciendo el análisis exacto, produciendo el worklist ordenado, y verificando
con `run_erc`.

Durante el análisis pre-fix además aparecieron **tres hallazgos que el
prompt original no anticipaba** y que cambiaron el alcance real de la
sesión — documentados abajo y resueltos con decisión explícita del humano
(no inventados por el agente).

## ERC — baseline pre-fix

`run_erc(min_severity="warning")`, capturado antes de cualquier edición:
**2 errores, 8 warnings.**

| Regla | Severidad | Refs | Mapea a |
|---|---|---|---|
| `pin_not_connected` | error | U3 pin10 (VLED+) | Defecto 2 |
| `pin_to_pin` (Output↔Output) | error | U2.INT ↔ U3.~INT | Defecto 1 |
| `multiple_net_names` (INT_SENS/SCL) | warning | — | Defecto 3 |
| `multiple_net_names` (MOSI/NSS) | warning | — | Defecto 4 |
| `lib_symbol_mismatch` ×4 | warning | U1, U2, U3, U4 | extra (fuera de los 5) |
| `no_connect_dangling` ×2 | warning | — | extra (fuera de los 5) |

Defecto 5 (J1 `in_bom=no`) no es un item de ERC — es limpieza de BOM.

## Hallazgos más allá del prompt original (análisis vía `export_netlist`)

`get_world_context(kind="sch")` falló (`KICAD_CLI_FAILED` — estado
inconsistente entre netlist y posiciones, `#FLG01/#FLG02/#PWR01`), así que el
mapa de pines de U1 se derivó parseando `export_netlist()` directamente
(ver F-19b-06). Ese análisis mostró:

1. **U1 no tiene ningún pin GPIO libre.** Los 6 pines PB0–PB5 ya estaban
   comprometidos (PB5=RESET/ICSP, PB0=MOSI fusionado con NSS,
   PB1=SDA, PB2=SCL fusionado con ambos INT, PB3=SCK, PB4=MISO). El diseño
   correcto necesita **7** señales (SDA, SCL, MOSI, MISO, SCK, NSS, INT
   compartido) contra **5** pines libres reales (PB0–PB4, dejando PB5
   dedicado a RESET) — un déficit de 2, no un simple error de cableado. La
   instrucción original ("wired-OR a un pin libre") asumía un pin libre que
   no existe.
2. **R3 (documentado como pull-up de RESET, 10kΩ) estaba mal conectado**:
   su pin 2 caía en la red fusionada SCL/INT_SENS, no en `/RESET`. RESET no
   tenía pull-up real — un 6º defecto no documentado en el prompt original.
3. **U3.pin10 (VLED+, alimentación del driver LED del MAX30102) está
   flotante** sin ninguna conexión — no es sólo el target cosmético del
   defecto 2 (falta de flag NC), es un pin de alimentación real sin power
   net asignado en el diseño actual.

Estos tres hallazgos se llevaron al humano vía `AskUserQuestion` (dos rondas,
porque la primera decisión — dejar el INT por hardware y sólo agregar
polling — dejaba a NSS sin pin igual, ya que ninguno de PB0–PB4 se liberaba
al sacar el INT). Decisiones:

- **Déficit de pines**: eliminar el INT por hardware — U2.INT y U3.~INT pasan
  a No-Connect explícito, firmware pollea el status por I2C. Reduce el
  déficit a 1 (NSS).
- **NSS**: reclamar PB5 (antes RESET/ICSP) para NSS. Consecuencia aceptada
  explícitamente: **ICSP estándar vía J1 deja de poder entrar en modo
  programación** (requiere RESET controlable). Mitigación: programar U1 en
  banco antes de soldar, no en circuito.
- **R3**: se corrige — se mueve al nuevo `/NSS` (pull-up de RESET y pull-up
  idle-high de NSS son, casualmente, el mismo comportamiento físico).
- **VLED+**: no se cablea a ciegas. Flag No-Connect como placeholder +
  nota explícita en el sch de que falta diseño real de alimentación LED.
  Documentado, no resuelto en 19b.

## Mapa de pines final (U1, ATtiny85 SOIC-8)

| Pin | Antes | Ahora |
|---|---|---|
| PB0 (5) | MOSI (fusionado c/ NSS) | **MOSI** solo |
| PB1 (6) | SDA | **SDA** (sin cambio) |
| PB2 (7) | SCL fusionado c/ 2×INT | **SCL** solo |
| PB3 (2) | SCK | **SCK** (sin cambio) |
| PB4 (3) | MISO | **MISO** (sin cambio) |
| PB5 (1) | RESET/ICSP | **NSS** (reclamado) |

## Worklist entregado al humano (GUI de KiCad)

1. Separar la red fusionada SCL/INT: borrar ramas a U2.pin12(INT) y
   U3.pin13(~INT), agregar No-Connect en ambas, renombrar la red restante a
   `/SCL` limpio.
2. Separar la red fusionada MOSI/NSS: borrar rama a U4.pin5(NSS) de `/MOSI`.
3. Extender/renombrar el net de U1.pin1 (antes `/RESET`) a `/NSS`, uniendo
   con U4.pin5.
4. Mover R3.pin2 de la red fusionada vieja a `/NSS`.
5. No-Connect placeholder en U3.pin10 (VLED+) + nota de texto en el sch.
6. J1: `in_bom=no`, `on_board=yes` (Defecto 5).
7. Borrar los 2 flags No-Connect dangling.
8. Tools → Update Symbols from Library en U1/U2/U3/U4 (limpia los 4
   `lib_symbol_mismatch`).
9. Guardar.

## Estado

**Cerrado.** El worklist se ejecutó en una sesión de continuación
(`sesion/19b-exec-sch-fix`, misma fecha) después de que un apagado de la
máquina borrara `/tmp/gui-test-project/` entre 19b y 19d; el proyecto se
recreó copiando `despertador_inteligente/` del Desktop (mismo sch VIEJO,
ERC baseline re-verificado idéntico: 2 errores/8 warnings) y el agente guió
al humano paso a paso por los 9 ítems del worklist en la GUI, verificando
con `run_erc` después de cada uno. Ver `## Post-fix` abajo.

## Post-fix — ejecución guiada paso a paso

**ERC final: 0 errores, 4 warnings** (los 4 `lib_symbol_mismatch`
preexistentes — ver decisión sobre el Paso 8 más abajo). Progresión medida
en vivo, paso a paso:

| Paso | Acción | Errores | Warnings |
|---|---|---|---|
| baseline | — | 2 | 8 |
| 1 | borrar los 2 wires puente (SCL/INT_SENS, MOSI/NSS) | 2 | 6 |
| 2 | No-Connect en U2.12/U3.13 (2 intentos, ver hallazgo abajo) | 1 | 4 |
| 3 | renombrar U1.pin1 RESET→MOSI | 1 | 5 (+`isolated_pin_label` en J1.5, esperado) |
| 4 | mover R3.pin2 al net reclamado (`/MOSI`) | 1 | 4 (el `isolated_pin_label` desapareció solo) |
| 5 | No-Connect en U3.pin10 (VLED+) | **0** | 4 |
| 6 | J1 `in_bom=no`/`on_board=yes` (2 intentos, ver hallazgo abajo) | 0 | 4 |
| 7 | limpiar No-Connect dangling originales | 0 | 4 (ya estaban limpios, efecto colateral del paso 2) |
| 8 | Update Symbols from Library — **revertido**, ver hallazgo | 0 | 4 |
| 9 | guardar | 0 | 4 |

### Hallazgo 1 — causa física real de las 2 fusiones de red (defectos 3/4)

Análisis estático del `.kicad_sch` (parseo de `wire`/`label` con
`sexpdata`, unión de segmentos por coordenada) encontró la causa exacta:
**dos wires cortos de 1.27mm** (`(30.48,46.99)→(31.75,46.99)` y
`(38.1,48.26)→(36.83,48.26)`) puenteando indebidamente dos stubs de label
adyacentes en el cluster pegado a U1. Verificado computacionalmente
*antes* de tocar la GUI: remover exactamente esos 2 segmentos del grafo
resuelve **todas** las colisiones de nombre de red del sheet, sin efectos
secundarios. El humano los borró en la GUI y el ERC confirmó la predicción
exacta (8→6 warnings, ambos `multiple_net_names` desaparecidos). Este
diseño netea mayormente por **texto de label coincidente** (no por wire
largo entre componentes) — cada pin tiene un stub corto + label; dos
labels con el mismo texto se unen aunque estén lejos en el sheet.

### Hallazgo 2 — corrección al mapa de pines de 19c/19b: PB0 ya era NSS, no MOSI

El mapa de pines original (`## Mapa de pines final` arriba) se derivó
parseando el netlist **fusionado** (pre-fix), donde KiCad reporta el net
combinado bajo un nombre arbitrario (`multiple_net_names`: "Both MOSI and
NSS... MOSI will be used"). Una vez separadas las dos redes (Hallazgo 1),
el netlist real mostró: `/NSS = U1.5(PB0) + U4.5` (ya correcto, sin tocar)
y `/MOSI = U4.3 + J1.3 + TP5.1` (**sin ningún pin de U1**). O sea: PB0 ya
estaba correctamente cableado a NSS; la señal que realmente le faltaba
lugar a U1 era **MOSI**, no NSS. El déficit de pines sigue siendo el mismo
(1 pin), sólo cambia qué señal se asigna al PB5 reclamado — mismo
compromiso aceptado (se pierde ICSP en circuito). Corregido en vivo antes
de ejecutar el paso 3 (se renombró a `/MOSI`, no `/NSS`).

**Mapa de pines final real (U1, ATtiny85 SOIC-8):**

| Pin | Antes | Ahora (real) |
|---|---|---|
| PB0 (5) | MOSI/NSS fusionados | **NSS** (ya estaba, sin cambio) |
| PB1 (6) | SDA | SDA (sin cambio) |
| PB2 (7) | SCL fusionado c/ 2×INT | **SCL** solo |
| PB3 (2) | SCK | SCK (sin cambio) |
| PB4 (3) | MISO | MISO (sin cambio) |
| PB5 (1) | RESET/ICSP | **MOSI** (reclamado; se pierde ICSP en circuito) |

### Hallazgo 3 — No-Connect no alcanza si el pin conserva su label (paso 2)

Primer intento: el humano agregó un flag No-Connect *cerca* de U2.12 sin
borrar el stub+label "INT_SENS" existente del pin. ERC no cambió en
absoluto (mismo `pin_to_pin` exacto) y además apareció un
`no_connect_dangling` nuevo — el flag quedó flotando, sin severar la
red por nombre de label. Causa: en KiCad los local labels netean por
**coincidencia de texto**, no por proximidad ni por wire físico; mientras
el pin conserve su propio label "INT_SENS", sigue en esa red pase lo que
se agregue alrededor. Fix: borrar el wire+label propio de cada pin
(U2.12, U3.13) primero, y **recién ahí** poner el No-Connect exactamente
sobre el pin. Segundo intento, correcto — `pin_to_pin` desapareció.

### Hallazgo 4 — "Update Symbols from Library" es destructivo en este proyecto (paso 8)

El worklist original (ítem 8) asumía que sincronizar U1–U4 con la
librería del sistema sólo limpiaría los 4 warnings `lib_symbol_mismatch`
cosméticamente. En la ejecución real, la acción **rompió el diseño**: ERC
saltó de 0 errores/4 warnings a **13 errores/8 warnings** — 6 pines
válidos (en U1, U2×2, U3×3, U4) quedaron sin conexión porque la definición
de símbolo del sistema tiene una geometría/numeración de pines
**distinta** a la copia local customizada de este proyecto. Esto es
exactamente lo que el propio `lib_symbol_mismatch` venía advirtiendo desde
el baseline (símbolo diverge de la librería) — la divergencia es
intencional/funcional, no un desactualizado inofensivo. Revertido con
Ctrl+Z en la GUI; verificado que el revert no arrastró ninguno de los
fixes previos (J1 attrs, `/MOSI`, `/NSS`, `/SCL`, VLED+ NC todos intactos
post-revert). **Decisión: no ejecutar este paso.** Los 4
`lib_symbol_mismatch` quedan como warnings documentados y aceptados —
sincronizarlos requeriría re-crear manualmente la geometría/pinout
custom de cada símbolo, fuera de alcance de esta sesión (F2/alcance: no
toca el server, y esto tampoco es una tarea de server).

## Fricciones de tool (F-19b-NN)

| ID | Descripción | Tool/capacidad faltante |
|---|---|---|
| F-19b-01 | No hay forma de borrar o reenrutar un wire/label de esquemático | falta `delete_wire`/`delete_label` o equivalente en `sch.py` |
| F-19b-02 | No hay forma de agregar un flag "No Connect" a un pin | falta `add_no_connect(ref, pin)` |
| F-19b-03 | No hay forma de togglear atributos de símbolo (`in_bom`, `on_board`, `dnp`) — sólo `property` fields ya existentes vía `set_value`/`set_footprint` | falta `set_symbol_attr` o extender `_set_symbol_property` a atributos S-expression |
| F-19b-04 | Ídem F-19b-01 para flags No-Connect huérfanos (no se pueden borrar) | mismo gap que F-19b-02, en sentido inverso |
| F-19b-05 | No hay tool equivalente a "Update Symbols from Library" | falta `sync_symbol_from_library` o similar |
| F-19b-06 | `get_world_context(kind="sch")` falla con `KICAD_CLI_FAILED` (estado inconsistente entre netlist y posiciones, `#FLG01/#FLG02/#PWR01`) sobre este proyecto — bloqueó el uso previsto de la tool para el inventario de pines de U1 en el Paso 1; se resolvió parseando `export_netlist()` a mano | bug/gap en `get_world_context` kind=sch, no investigado a fondo (fuera de alcance de 19b, que no toca el server) |
| F-19b-07 | `health()` reporta `kicad_ipc: socket missing / KICAD_NOT_RUNNING` durante toda la sesión pese a que la nota operacional indicaba KiCad abierto — bloquea cualquier verificación PCB post-F8 vía `get_world_context(kind="pcb")` | requiere acción humana (Preferences → Plugins → habilitar API), no es un bug de tool |
| F-19b-08 | `connect_pins` sólo puede *agregar* una conexión (dos local labels); no sirve para ninguno de los 5 defectos, que son todos "separar algo mal unido" | ampliar el alcance de mutación de sch más allá de lo aditivo |
| F-19b-09 | Causa raíz de F-19b-07: KiCad 10.0.4 crea el socket IPC como `/tmp/kicad/api-<PID>.sock` (sufijo de PID), pero `_DEFAULT_SOCKET_LINUX` en `bridge/ipc.py:972` asume el nombre fijo `/tmp/kicad/api.sock` (según `docs/arquitectura.md` §RNF6). El humano habilitó el API server correctamente desde el principio — `health()` reportaba `KICAD_NOT_RUNNING` igual porque buscaba el archivo equivocado. Workaround aplicado esta sesión: symlink manual `/tmp/kicad/api.sock → api-5640.sock`. Fix real: que el bridge intente `KICAD_API_SOCKET` env var, luego el path fijo, y si falla, glob `/tmp/kicad/api-*.sock` como fallback | gap en `bridge/ipc.py` (`_DEFAULT_SOCKET_LINUX` / resolución de socket), no en la sesión 19b (F2 no toca gates, pero esto no es un gate — reportar para sesión futura de server) |
| F-19b-10 | Sin tool para severar una conexión sch de forma segura: agregar un No-Connect *cerca* de un pin no lo desconecta si el pin conserva su propio label — hay que borrar wire+label del pin primero. El agente sólo pudo diagnosticarlo con análisis estático externo (parseo manual del `.kicad_sch`) y verificación empírica vía `run_erc`, sin ninguna tool que exponga "¿qué neteo tiene este pin ahora?" a nivel fino | falta un `get_pin_net_membership` o similar que muestre, para un pin dado, exactamente qué wires/labels lo alimentan — habría evitado 1 intento fallido |
| F-19b-11 | "Update Symbols from Library" (acción de GUI, sin tool ni fallback seguro) es **destructiva** cuando el símbolo local diverge intencionalmente de la librería del sistema (exactamente el caso que `lib_symbol_mismatch` señala) — introdujo 13 errores nuevos, revertido con Ctrl+Z | ninguna tool cubre esto (F-19b-05 ya lo señalaba); further el propio ERC no distingue "mismatch cosmético" de "mismatch que rompería el pinout si se sincroniza" — dato para una sesión de server que quiera automatizar este paso con una tool: haría falta un diff de pines antes de aplicar |
| F-19b-12 | `run_erc` reporta posiciones (`pos`) etiquetadas `"coordinate_units":"mm"` que en realidad están **100× más chicas** que el valor real en mm (ej. U2 pin12 real en `148.59,73.66`mm, ERC reportó `[1.4859,0.7366]`) — confirmado cruzando contra coordenadas propias del `.kicad_sch` y `get_world_context(kind=pcb)`. No bloqueó el trabajo (las posiciones sólo se usaban para identificar refs, no para navegar), pero el campo es engañoso tal cual está etiquetado | bug de conversión de unidades en `validate.py`/`bridge/rules.py` (la ruta que llama `kicad-cli sch erc`) — mismo patrón de riesgo que el gotcha de nm/mm del proyecto, aquí aparentemente un factor /100 en vez de /10⁶; no investigado a fondo (fuera de alcance, no toca el server) |

## Fixture `despertador-routed`

**Sigue marcado STALE (Opción B, ratificado).** La copia de `/tmp` recreada
para la ejecución tiene el PCB sin colocar ni rutear (footprints recién
importados por F8, sin `draw_board_outline`/`move_footprint`/`route_board`
corridos), así que regenerar el fixture exigiría el flujo completo de
colocación+ruteo (escala Dogfooding), no sólo `route_board`. Se decide
diferir la regeneración a la sesión 20 (Dogfooding 3), que de todas formas
coloca y rutea el board corregido desde cero — eso ES la regeneración. El
banner STALE en `tests/fixtures/despertador-routed/README.md` (agregado en
la sesión previa) sigue vigente y no requiere cambios.

Revisados los dos consumidores del fixture
(`tests/test_zones_e2e_gui.py`, `tests/test_reload_e2e_gui.py`, ambos
`integration_gui_slow`): ninguno assertea sobre nombres de red específicos ni
sobre R3 — sólo verifican presencia de ANT1 y cobre/DRC genérico. **No
requieren skip**, siguen siendo válidos para su propósito (colisión de cobre
denso). `pytest -m "not integration"` no se ve afectado en ningún caso.

## F8 (sync sch→pcb)

**Corrido y verificado limpio.** F-19b-07/F-19b-09 no bloquearon esta vez:
el symlink `/tmp/kicad/api.sock → api-<PID>.sock` ya estaba en su lugar al
arrancar la sesión de ejecución, `health()` reportó IPC OK durante toda la
sesión. El humano corrió Tools → Update PCB from Schematic y guardó;
`get_world_context(kind="pcb")` confirmó los 24 footprints con las redes
corregidas (`U1: 1>/MOSI 2>/SCK 3>/MISO 4>GND 5>/NSS 6>/SDA 7>/SCL 8>+3V3`),
`U2.12`/`U3.13`/`U3.10` como `unconnected-(...)` (No-Connect correctos), y
`J1` reflejando el estado exclude-from-BOM. Sin errores de sincronización.

## Cierre

Los 5 defectos eléctricos originales quedan cerrados: ERC en **0 errores**
(4 warnings `lib_symbol_mismatch` documentados y aceptados — no se
sincronizan, ver Hallazgo 4), F8 corrido y verificado sin errores de sync.
Ningún fix requirió tocar `docs/specs/**` (F1), lógica de gates (F2),
códigos de error existentes (F3), ni dependencias (F5); todo el trabajo
fue contra KiCad 10.0.4 (F4). El fixture `despertador-routed` sigue STALE,
diferido a la sesión 20. El Dogfooding 3 puede arrancar con el sch
corregido.
