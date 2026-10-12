# Investigación C4 — timeout de `route_board` en H1 (anavi-dev-mic, gate GUI 32d)

**Contexto:** Ciclo C4 (orden de ejecución "gate GUI 32d") pedía correr
`tests/test_pcb_session32d_stitching_gui_slow.py` (H1/H2) contra el motor
real de KiCad, gate pendiente desde sesión 32d para el fix de stitching
F-D5-01 (ver `docs/investigacion/32c-f-d5-01.md`). H1 (intento 1, HEAD
`9a00d92`, KiCad 10.0.5) falló con `KICAD_TIMEOUT` a los 600s por defecto,
sin haber tocado disco ni el board vivo (el timeout ocurre en el paso
Freerouting, antes de cualquier persist — contrato D-23.2 intacto). Esta
nota documenta la investigación read-only de causa posterior al fallo,
autorizada explícitamente por el arquitecto tras el DETENIDO de C4.
**Ningún archivo del repo ni del board fue modificado** — solo lectura vía
IPC, del `.dsn`/log generados por el intento fallido, y del historial git.

## Qué reprodujo el fallo

- Fixture: `/tmp/f-d5-01-devmic-32d/anavi-dev-mic.kicad_pcb`, copia
  byte-idéntica a `validation-suite/level-a/anavi-dev-mic/working/anavi-dev-mic.kicad_pcb`
  al momento del intento.
- Comando: `route_board()` sin argumentos (vía el test H1), `timeout_s`
  por defecto = 600.
- Resultado: `KICAD_TIMEOUT` a los 638.91s de wall-clock del test
  (600s de presupuesto de Freerouting + overhead de export/import DSN).
- Log de Freerouting (`freerouting.log`, 118KB, preservado íntegro):
  desde el pass #1 hasta el #73 (~10 min) el score quedó **fijo en
  969.16–969.19, siempre "2 unrouted"** — cero progreso en ~10 minutos.
  La falla reportada pasa de `"no connection was found between their
  nets"` (pass 0) a **`"the maze search algorithm could not be
  created"`** en todos los passes siguientes, con errores internos de
  geometría inmediatamente después de cada intento
  (`ShapeSearchTree45Degree.complete_shape: cannot convert Simplex to
  IntOctagon`).

## Identificación de la conexión atascada

Mapeando el orden de `(place ...)` del `.dsn` exportado (1-indexado:
`#1=U1 … #11=MK1 …`) contra el log, la conexión que nunca resolvió es
**`MK1` pin 2** — miembro de `Net-(MK1-Pad2)` (pines `R1-1 MK1-2 R2-2`
según la sección `(network ...)` del `.dsn`). Se verificó que la
numeración de pines del footprint (`(image
"Sensor_Audio:Knowles_LGA-5_3.5x2.65mm" ...)`) coincide 1:1 con los
números de pad de KiCad, sin reordenamiento — la lectura "pin #2 de MK1"
es correcta y NO corresponde al pad `MK1.3` (GND) que el propio test
espera dejar huérfano a propósito.

Esto es notable: **el atasco no está en el pad que el test ejercita**
(el orphan pad GND de la hipótesis F-D5-01), sino en un net vecino que,
por inspección del grafo de tracks del fixture (`get_tracks` vía IPC), ya
parece estar completamente trazado de punta a punta (`R1-1` → … →
posición exacta de `MK1-2`).

## Hipótesis descartada: segmento degenerado

Se encontró un segmento de **0.02mm** en `Net-(MK1-Pad2)`
(`127.824,75.700 → 127.824,75.720`, más corto que su propio ancho de
0.5mm) muy cerca del punto donde se atasca la búsqueda — candidato
razonable a "input degenerado que rompe el motor de geometría de
Freerouting".

**Refutada por comparación directa**: se extrajo del historial git
(commit `791cd22`, cierre de sesión 31c) el output *exitoso* de
`route_board()` sobre esta misma placa — ruteado desde cero en 184.82s,
15/15 nets ruteables, 0 bloqueadas. Ese output contiene **el mismo
segmento**, en coordenadas prácticamente idénticas
(`127.8236,75.7003 → 127.8236,75.7201`), más otros 9 segmentos
igual de cortos (0.003–0.031mm) repartidos por el board — aparentemente
un subproducto normal de cómo Freerouting cierra transiciones de vía/giro,
no un defecto. Si el segmento rompiera el motor de geometría, 31c
también debería haber fallado. No falló.

## Hallazgo actual (sin cerrar con certeza)

El fixture de H1 **no es un board vacío**: fue preparado partiendo del
output ya ruteado de 31c (mismas coordenadas de tracks, incluidos los
segmentos "degenerados"), con la conexión GND de `MK1.3` removida a
propósito para fabricar el escenario "capas opuestas" que el guardrail
de stitching debe aceptar. El resto de los nets —incluido
`Net-(MK1-Pad2)`— llega ya trazado.

La zona `MK1`/`R1`/`R2`/`C1`/`C2` es un cluster muy chico (~10mm²) con
cobre de **tres nets superpuestos**: `Net-(MK1-Pad2)`, `+3V3`, y la zona
GND llena en B.Cu por debajo. La cadena de objetos que Freerouting reporta
junto al pin atascado son, consistentemente en cada intento, tracks de
`+3V3` (`C1-1, C2-1, J2-3, U1-12`) y la `conductionarea` (zona GND) — la
misma firma que el mecanismo raíz ya documentado en
`docs/investigacion/32c-f-d5-01.md` (D-19.1: "corredor angosto
estrangulado por cobre ajeno"), aquí aplicado a un net de señal en vez de
a un pad GND huérfano.

**La paradoja no resuelta**: sesión 31c generó esta misma geometría
final *desde cero* (0 tracks al empezar) y no tuvo ningún problema en
184s. H1 arranca con esa geometría *ya precargada* como obstáculo fijo y
ahí sí se traba — pese a que, en teoría, tiene *menos* trabajo pendiente
(la mayoría de los nets ya están conectados). La lectura más plausible,
sin confirmación causal: `route_board`/Freerouting trata **todo** el
cobre preexistente (de cualquier net, no solo GND) como obstáculo fijo al
recibir un board ya mayormente ruteado — lo cual puede volver mucho más
difícil encontrar espacio remanente en un cluster ya denso que ruteando
todo junto desde cero, donde el optimizador tiene libertad completa desde
el principio.

## Límites de esta investigación

Es inferencia por análisis de logs y geometría estática, **no una prueba
causal controlada** — no se removió el segmento ni se re-corrió
Freerouting con una variante del fixture, porque mutar el board o el
repo estaba fuera del mandato read-only de C4. No se descarta que la
causa real sea otra (p. ej. una violación de clearance puntual entre
`Net-(MK1-Pad2)` y la zona/tracks vecinos que el export DSN no refleja
igual que el motor DRC de KiCad, dado que el `.kicad_pcb` tiene overrides
de `clearance 0` por zona/ítem que la clase `kicad_default` del `.dsn`
—`width 500 / clearance 250`— no necesariamente replica 1:1).

## Evidencia preservada

- `/tmp/claude-1000/…/scratchpad/h1-attempt1.log` — salida completa de
  pytest (assertion de `KICAD_TIMEOUT`).
- `/tmp/f-d5-01-devmic-32d/.kicad-mcp/autoroute/freerouting.log` —
  log completo de Freerouting (118KB, 73 passes).
- `/tmp/f-d5-01-devmic-32d/.kicad-mcp/autoroute/route.dsn` — DSN exportado
  para el intento fallido.
- `/tmp/f-d5-01-devmic-32d/anavi-dev-mic.kicad_pcb` — copia del fixture
  usada en el intento (sin mutar por el fallo, D-23.2).
- Output de 31c extraído del historial git (`791cd22`) para comparación,
  copiado a scratchpad de la sesión (no versionado).

## Estado

C4 permanece **DETENIDO** (evidencia no concluyente sobre la causa raíz
exacta, aunque sí sobre qué NO es la causa). No se reintentó H1, no se
subió `timeout_s`, no se corrió H2. `git status --short` vacío en todo
momento — este documento es la única adición al repo, explícitamente
autorizada como "documentar el hallazgo formalmente" tras el cierre de la
investigación. Decisión sobre próximos pasos (reintentar con más
`timeout_s`, rediseñar cómo se prepara el fixture de H1, promover a
hallazgo P1/P0, o descartar) queda con el arquitecto.
