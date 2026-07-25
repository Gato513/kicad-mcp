# Fixture `despertador-routed`

## Actualizado en sesión 28 (Dogfooding 6, 2026-07-25, commit base `fba66b7`)

Este fixture fue **regenerado desde cero** en la sesión 28 (Dogfooding 6,
segundo dogfooding de Fase 3), partiendo del mismo esquemático corregido de
sesión 19b usado en D3/D4/D5 (0 errores ERC, 4 warnings `lib_symbol_mismatch`
aceptados — D-19b.1). Reemplaza al fixture de sesión 25 (D5): misma placa,
misma topología eléctrica, **misma colocación física que D5** (réplica
intencional de las 23 coordenadas de D5, decisión tomada con el arquitecto
al planificar D6 para que el baseline DRC fuera geométricamente comparable
y aislara el efecto de D-26.1/D-23.2 extendido de cualquier variable de
colocación nueva).

**Objetivo de D6:** ratificar en producción (a) la extensión del contrato
D-23.2 (ADR-0012, sesión 27) a `fill_zones` y `add_zone(fill=true)` — antes
solo validada en un test aislado (2/2) — y (b) D-26.1 (refill obligatorio
post-colocación antes de leer baseline DRC, sesión 26). Ver
`/tmp/dogfood6-fricciones.md` (log completo de la sesión, no versionado)
para el detalle de las 5 corridas de verificación.

- Topología de red: idéntica a D3/D4/D5 (`/NSS` separado de `/MOSI`, `/SCL`
  limpio, No-Connect explícitos en U2.INT/U3.~INT/U3.VLED+).

## Uso

Estos tests son `integration_gui`: necesitan KiCad vivo con **una copia**
de este fixture abierta (no hay `open_project` programático en kipy/KiCad
10). Ver `docs/pruebas-gui.md §fixture despertador-routed` para el
protocolo completo.

## Estado del ruteo

- Board: 44×44mm (contorno `(125,60)`→`(169,104)`, idéntico a D5), plano
  GND en B.Cu filled desde cero antes del ruteo (C2, Freerouting no respeta
  el plano como exclusión de nets ajenos — D-19.1 v6 — se resuelve con
  refill + `enforce_hole_clearance` + persistencia D-23.2 post-route).
- Colocación: réplica exacta de las 23 coordenadas de D5 (BT1 batería + U4
  RF en cluster izquierdo con margen ≥2mm de borde; resto en franja
  derecha). `get_footprint_neighbors` inclusivo (D-D4.1) corrido sobre BT1,
  U4, J1, J2, ANT1 antes de mover, sin sorpresas geométricas (coordenadas
  ya validadas por D5).
- **Baseline DRC pre-route (V4), con `fill_zones()` explícito aplicado
  entre colocación y lectura (D-26.1):** total **0** — 56
  `unconnected_items` (triviales, se resuelven con el ruteo) y **0**
  `hole_clearance`/`clearance`/`solder_mask_bridge`. Compara contra las 6
  violaciones no-triviales que el baseline de D5 registró (fill rancio,
  sin `fill_zones()` explícito) — **ratifica D-26.1 empíricamente**, con
  el matiz de que en D6 el plano GND se creó ya con la colocación completa
  (orden de flujo distinto de D5), así que el efecto de D-26.1 no quedó
  100% aislado del orden de las fases (ver log de sesión, sección V4).
- Ruteo en **5 corridas de `route_board`** (1 completa desde cero + 2
  re-ruteos parciales de `/NSS` y `/SCK`, cada uno con su corrida de
  `delete_tracks_bulk(dry_run=true)` previa — C3): 10/10 nets ruteables
  ruteadas en las 3 corridas de ruteo, 0 bloqueadas. Corrida 1 (desde
  cero): **32.4s** — sensiblemente más rápido que D5 (128.8s), en línea
  con D3 (53s)/D4 (36.7s). Corridas 2-3 (re-ruteo parcial de 1 net):
  **110-112s cada una** — a diferencia de D5, donde los re-ruteos
  parciales costaron ~9-10s; dato a vigilar en D7 (ver log de sesión,
  Fase 5).
- **DRC final: 0 errores, 0 warnings en las 3 corridas de ruteo.** Ninguna
  corrida introdujo un error nuevo (delta V4 = 0 en las 3).
- **F-D5-01 (isla GND sin vía al plano) NO reapareció** en ninguna de las 3
  corridas — corrida 1 terminó con `err_post=0` total, sin ningún
  `unconnected_items` residual (a diferencia de D5, que dejó 1). Una
  ocurrencia de 2 dogfoodings no ratifica el patrón como sistemático (el
  trigger definido era "2/2" para promover a P2 investigación) — con D6 sin
  el patrón, el trigger no se cumplió.
- Gerbers (G3) y BOM exportados sin error, gate G3 pasó limpio.

## Ratificación de D-23.2 extendido (ADR-0012, sesión 27) en dogfooding real

**D6 (sesión 28) verificó 3/3 corridas coincidentes por cada una de las
tres tools cubiertas por el contrato:**

| Tool | Corridas V2 | Coincidencias | Divergencias |
|---|---|---|---|
| `route_board` | 3 (1 completa + 2 re-ruteos parciales) | 3/3 | 0 |
| `fill_zones` | 3 (D-26.1 explícito + post-delete_zone + idempotente) | 3/3 | 0 |
| `add_zone(fill=true)` | 3 (plano GND real + 2 zonas de test F.Cu) | 3/3 | 0 |

En las 9 corridas totales: `run_drc()` independiente inmediato coincidió
exacto con el estado reportado/persistido, mtime del `.kicad_pcb` cambió en
las 9, cero `EXTERNAL_EDIT_DETECTED` espurio. Combinado con las 5/5 previas
de `route_board` (sesiones 24/25) y el 2/2 del test aislado de sesión 27
para `fill_zones`/`add_zone`, el contrato D-23.2 extendido queda ratificado
en las tres tools desde tres ángulos distintos de evidencia (unit/regresión,
D5, D6) sin ninguna divergencia registrada.

## ⚠️ Advertencia — no es referencia de diseño de colocación óptima

El esquemático y la topología eléctrica son correctos y representan el
diseño real del despertador. La **colocación física** fue diseñada
originalmente por el agente en D5 (sesión 25, tiempo acotado) y replicada
sin cambios en D6 — sirve para ejercitar cobre denso, zonas, vías y el
pipeline completo schematic→gerbers, pero no está optimizada para RF
(antena) ni para producción en serie sin revisión humana adicional.

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
   PRIMERO. Crear y fillar el plano GND (`add_zone`) ANTES de
   `route_board` — Freerouting respeta `(plane)` nativo (D-19.1).
6. Tras la colocación masiva (`move_footprint` × N) y antes de leer
   cualquier baseline DRC, correr `fill_zones()` **explícito** — D-26.1
   (sesión 26, ratificado en D6): `move_footprint` no dispara refill de
   zonas, un baseline leído sin este paso mide fill rancio.
7. El refill interno de `route_board`/`fill_zones`/`add_zone(fill=true)`
   ya recalcula `hole_clearance` correctamente y persiste antes de
   reportar (D-23.2, ADR-0012, extendido sesión 27 a las tres tools,
   ratificado 3/3 por tool en D6). **No hace falta** el workaround manual
   de `delete_zone`+`add_zone(fill=true)` que el fixture de sesión 20 (D3)
   documentaba como obligatorio — obsoleto desde sesión 24, ratificado en
   D5 y D6. Seguí corriendo `run_drc()` propio como cross-check de todos
   modos (buena práctica, no por desconfianza en el contrato).
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
real de un agente (proceso persistente, como en sesiones 20, 25 y 28) esto
no pasa.
