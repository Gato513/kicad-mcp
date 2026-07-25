# Fixture `despertador-routed`

## Actualizado en sesión 29 (Dogfooding 7, 2026-07-25, commit base `6479923`)

Este fixture fue **regenerado desde cero** en la sesión 29 (Dogfooding 7,
tercer dogfooding de Fase 3), partiendo del mismo esquemático corregido de
sesión 19b usado en D3-D6 (0 errores ERC, 4 warnings `lib_symbol_mismatch`
aceptados — D-19b.1). Reemplaza al fixture de sesión 28 (D6): misma placa,
misma topología eléctrica, **colocación física nueva** (V6 de D7 — 23
coordenadas propias, distintas de D5/D6, decididas por el agente en clusters
funcionales dispuestos en anti-diagonal, no imitación de D5/D6).

**Objetivo de D7:** (a) 3er verde consecutivo del criterio de cierre de
Fase 3 (D5=9.5, D6=9.7, D7=9.8 — ver detalle abajo); (b) aislar
correctamente el efecto de D-26.1 (sesión 26) replicando el orden de fases
exacto de D5 (plano GND creado ANTES de la colocación, D-28.1 vinculante) —
a diferencia de D6, donde el orden invertido dejó el experimento
confundido; (c) variación geométrica controlada (V6) para que la evidencia
de D-23.2/D-26.1 no dependa de un único layout; (d) protocolo F-D6-01 (V7):
3 mediciones adicionales de re-ruteo parcial para cerrar la vigilancia
sobre el costo de `route_board` en re-ruteos parciales. Ver
`/tmp/dogfood7-fricciones.md` (log completo de la sesión, no versionado)
para el detalle de las 4 corridas completas de ruteo + experimento V4.

- Topología de red: idéntica a D3-D6 (`/NSS` separado de `/MOSI`, `/SCL`
  limpio, No-Connect explícitos en U2.INT/U3.~INT/U3.VLED+).

## Uso

Estos tests son `integration_gui`: necesitan KiCad vivo con **una copia**
de este fixture abierta (no hay `open_project` programático en kipy/KiCad
10). Ver `docs/pruebas-gui.md §fixture despertador-routed` para el
protocolo completo. **Ningún test de este repo hardcodea las coordenadas de
colocación** — todos derivan bbox/zonas/posiciones en runtime (D-24.1), así
que el cambio de layout D6→D7 no afecta ninguna aserción existente.

## Estado del ruteo

- Board: 44×44mm (contorno `(125,60)`→`(169,104)`, idéntico a D3-D6), plano
  GND en B.Cu filled desde cero **antes** de la colocación (orden D5/D-28.1,
  no D6) y antes del ruteo (C2, Freerouting no respeta el plano como
  exclusión de nets ajenos — D-19.1 v6 — se resuelve con refill +
  `enforce_hole_clearance` + persistencia D-23.2 post-route).
- **Colocación (V6, coordenadas nuevas):** clusters funcionales en
  anti-diagonal — BT1 (batería) en la banda superior, cluster de potencia
  (C1/D1/TP1/TP2) arriba-derecha, J1+U1 (MCU, hub SPI/I2C) en banda media,
  U4 (RF) + ANT1 pegada a 2mm de distancia (vs 28mm en D5/D6) en el
  cuadrante inferior-derecho, cluster I2C (U2/U3/C5/C6/R1/R2/J2) en el
  cuadrante izquierdo. `get_footprint_neighbors` inclusivo (D-D4.1) corrido
  sobre BT1, U4, J1, J2, ANT1 antes de mover — con el outline ya creado
  (orden D-28.1), a diferencia de D6. Verificación read-only adicional de
  solapes de courtyard tras la colocación: 0 solapes, los 23 dentro del
  outline, ANT1 a 15mm del borde y J1 a 7.5mm (ambos muy por encima del
  mínimo 1.5-2mm de D-D3.1).
- **Experimento aislado D-26.1 (V4.a → V4.b, el punto metodológico central
  de D7):** con el orden de fases correcto (plano antes de colocar, sin
  confundir con D6), el baseline **sin** `fill_zones()` explícito (V4.a)
  reprodujo el patrón exacto de D5: **6 violaciones no-triviales** (3×
  `hole_clearance` J1 NPTH + 1× `hole_clearance` ANT1 + 1× `clearance`
  ANT1 + 1× `solder_mask_bridge` ANT1) — fill rancio del plano creado antes
  de mover los 23 footprints encima. El baseline **con** `fill_zones()`
  explícito (V4.b) llevó esas 6 violaciones a **0**. **Ratificación
  empírica de D-26.1 sin el confusor de orden de fases que tuvo D6** — el
  delta V4.a→V4.b es evidencia directa: el refill explícito es necesario
  en el flujo plano-antes-de-colocar, no redundante.
- Ruteo en **4 corridas completas de `route_board`** (1 desde cero + 3
  re-ruteos parciales del protocolo F-D6-01, sobre `+3V3` [alto grado de
  interconexión, 65 tracks], `/SDA` [medio, 29 tracks] y `/NSS` [bajo, 7
  tracks — mismo net medido en D5 y D6], cada uno con su corrida de
  `delete_tracks_bulk(dry_run=true)` previa — C3): 10/10 nets ruteables
  ruteadas en las 4 corridas, 0 bloqueadas. Corrida 1 (desde cero):
  **40.6s**. Re-ruteos parciales: **23.7s / 24.4s / 17.7s** — ni tan
  baratos como los de D5 (~9-10s) ni tan caros como los de D6 (110-112s);
  sin correlación observable con el grado de interconexión del net dentro
  de esta sesión. Con N=7 total (2 D5 + 2 D6 + 3 D7) el rango 9s-112s no
  muestra patrón correlacional claro con interconexión/tamaño/capas — **se
  cierra F-D6-01 como variabilidad inherente de Freerouting/JVM**, sin
  activar el trigger de promoción a P2 (que requería >60s consistente).
- **DRC final: 0 errores, 0 warnings en las 4 corridas de ruteo.** Ninguna
  corrida introdujo un error nuevo (delta V4 = 0 en las 4, contra el
  baseline canónico V4.b).
- **F-D5-01 (isla GND sin vía al plano) NO reapareció** — corrida 1 y las 3
  parciales terminaron todas con `err_post=0` total, sin ningún
  `unconnected_items` residual. D5=sí (1 ocurrencia), D6=no, D7=no — el
  trigger de promoción a P2 ("2/3 dogfoodings") **no se cumple** (1/3).
- Gerbers (G3) y BOM exportados sin error, gate G3 pasó limpio.

## Ratificación de D-23.2 extendido (ADR-0012, sesión 27) en dogfooding real

**D7 (sesión 29) verificó 3/3 (o más) corridas coincidentes por cada una de
las tres tools cubiertas por el contrato:**

| Tool | Corridas V2 | Coincidencias | Divergencias |
|---|---|---|---|
| `route_board` | 4 (1 completa + 3 re-ruteos parciales, protocolo V7) | 4/4 | 0 |
| `fill_zones` | 3 (D-26.1 explícito V4.b + 2 zonas de test F.Cu) | 3/3 | 0 |
| `add_zone(fill=true)` | 3 (plano GND real + 2 zonas de test F.Cu) | 3/3 | 0 |

En las 10 corridas totales: `run_drc()` independiente inmediato coincidió
exacto con el estado reportado/persistido, mtime del `.kicad_pcb` cambió en
las 10, cero `EXTERNAL_EDIT_DETECTED` espurio. Combinado con las 9/9 de D6 y
las 5/5 previas de `route_board` (sesiones 24/25) y el 2/2 del test aislado
de sesión 27 para `fill_zones`/`add_zone`, el contrato D-23.2 extendido
queda ratificado en las tres tools desde cuatro ángulos distintos de
evidencia (unit/regresión, D5, D6, D7) sin ninguna divergencia registrada —
**3er verde consecutivo de Fase 3, criterio de convergencia cumplido.**

## ⚠️ Advertencia — no es referencia de diseño de colocación óptima

El esquemático y la topología eléctrica son correctos y representan el
diseño real del despertador. La **colocación física** fue diseñada por el
agente en D7 (sesión 29, tiempo acotado, variación geométrica deliberada
respecto a D5/D6) — sirve para ejercitar cobre denso, zonas, vías y el
pipeline completo schematic→gerbers, pero no está optimizada para RF
(antena) ni para producción en serie sin revisión humana adicional. En
particular, ANT1 quedó mucho más cerca de U4 (2mm) que en D5/D6 (28mm) —
deliberado para variar la geometría, no una recomendación de diseño RF.

## Regenerar el fixture (si el esquemático vuelve a cambiar)

1. Copiar el proyecto fuente a un directorio de trabajo (`/tmp/...`),
   nunca mutar este fixture in-place.
2. Abrirlo en KiCad (PCB Editor) — dejarlo abierto y no volver a tocarlo
   desde la GUI durante los pasos siguientes.
3. Un solo proceso Python/sesión MCP persistente para todas las llamadas
   a `route_board` (ver advertencia histórica sobre `live_stale` más
   abajo).
4. Requiere `KICAD_MCP_FREEROUTING_JAR` apuntando al jar de Freerouting.
5. Si no tiene contorno Edge.Cuts todavía, llamar `draw_board_outline`
   PRIMERO, y crear/fillar el plano GND (`add_zone`) **antes de la
   colocación masiva de footprints** — D-28.1 vinculante, cualquier
   inversión de este orden requiere `AskUserQuestion` al arquitecto y
   contamina la medición de D-26.1 (ver hallazgo de D6). Freerouting
   respeta `(plane)` nativo (D-19.1).
6. Tras la colocación masiva (`move_footprint` × N) y antes de leer
   cualquier baseline DRC, correr `fill_zones()` **explícito** — D-26.1
   (sesión 26, ratificado sin confusor en D7): `move_footprint` no dispara
   refill de zonas, un baseline leído sin este paso mide fill rancio (D7
   lo confirmó: 6 violaciones fantasma sin el refill, 0 con él).
7. El refill interno de `route_board`/`fill_zones`/`add_zone(fill=true)`
   ya recalcula `hole_clearance` correctamente y persiste antes de
   reportar (D-23.2, ADR-0012, extendido sesión 27 a las tres tools,
   ratificado 3/3+ por tool en D6 y D7). **No hace falta** el workaround
   manual de `delete_zone`+`add_zone(fill=true)` que el fixture de sesión
   20 (D3) documentaba como obligatorio — obsoleto desde sesión 24,
   ratificado en D5, D6 y D7. Seguí corriendo `run_drc()` propio como
   cross-check de todos modos (buena práctica, no por desconfianza en el
   contrato).
8. Verificar el JSON de `route_board`: `drc.por_tipo` sin
   `copper_edge_clearance`, `nets.bloqueadas` idealmente vacío. Luego
   `run_drc()` manual para confirmar (coincide con `err_post` si D-23.2 se
   sostiene — ver sección de ratificación arriba).
9. Copiar `.kicad_pcb`/`.kicad_pro`/`.kicad_sch`/`.kicad_prl`
   inmediatamente del directorio de trabajo a
   `tests/fixtures/despertador-routed/` — antes de correr cualquier otra
   tool que pueda volver a disparar el save implícito.

### Nota histórica: constraint de `live_stale`

`route_board` hace un "save_board implícito" (live→disco) si el board
abierto coincide con el target y el store en memoria no está
`live_stale` — pero ese flag vive en memoria del PROCESO servidor, no
persiste entre invocaciones. Si se corre `route_board` desde scripts
nuevos repetidamente, cada uno arranca con `live_stale=False`, dispara el
save implícito, y pisa el ruteo en disco con el estado viejo de la GUI
antes de re-rutear desde cero (hallazgo de sesión 17). Con un cliente MCP
real de un agente (proceso persistente, como en sesiones 20, 25, 28 y 29)
esto no pasa.
