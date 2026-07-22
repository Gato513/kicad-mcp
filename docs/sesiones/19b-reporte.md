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

**Esperando ejecución humana del worklist en la GUI de KiCad.** Este reporte
se completa con la sección post-fix (ERC final, resultado de F8, estado real
vs `0 errores/0 warnings`) una vez confirmada la edición.

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

## Fixture `despertador-routed`

**Marcado STALE (Opción B)** — no regenerado esta sesión: IPC estaba
inaccesible (F-19b-07), y `route_board` depende de IPC. Actualizado
`tests/fixtures/despertador-routed/README.md` con banner STALE explicando el
cambio de topología de red y por qué el fixture (los 4 archivos
`.kicad_*`) sigue siendo el esquemático viejo.

Revisados los dos consumidores del fixture
(`tests/test_zones_e2e_gui.py`, `tests/test_reload_e2e_gui.py`, ambos
`integration_gui_slow`): ninguno assertea sobre nombres de red específicos ni
sobre R3 — sólo verifican presencia de ANT1 y cobre/DRC genérico. **No
requieren skip**, siguen siendo válidos para su propósito (colisión de cobre
denso). `pytest -m "not integration"` no se ve afectado en ningún caso.

Regeneración pendiente para sesión ≥20, protocolo ya documentado en el
README del fixture.

## F8 (sync sch→pcb)

Pendiente — depende de que el humano guarde el sch corregido y corra
Tools → Update PCB from Schematic. Verificación PCB post-F8 vía
`get_world_context(kind="pcb")` depende de que IPC esté disponible
(F-19b-07); si sigue caído, se documenta como diferido, no bloquea el cierre
de ERC del sch.
