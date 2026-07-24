# Fixture `despertador-routed`

## Actualizado en sesión 25 (Dogfooding 5, 2026-07-24, commit base `100cb3a`)

Este fixture fue **regenerado desde cero** en la sesión 25 (Dogfooding 5,
primer dogfooding de Fase 3), partiendo del mismo esquemático corregido de
sesión 19b usado en D3/D4 (0 errores ERC, 4 warnings `lib_symbol_mismatch`
aceptados — D-19b.1). Reemplaza al fixture de sesión 20 (D3): misma placa,
misma topología eléctrica, colocación física nueva (diseñada en esta sesión,
sin reutilizar coordenadas de D3).

**Objetivo de D5:** ratificar en producción el contrato D-23.2 (ADR-0012,
sesión 24) — cuando `route_board` termina OK, disco == memoria == `err_post`
reportado. Ver `/tmp/dogfood5-fricciones.md` (log completo de la sesión,
no versionado) para el detalle de las 3 corridas de verificación.

- Topología de red: idéntica a D3/D4 (`/NSS` separado de `/MOSI`, `/SCL`
  limpio, No-Connect explícitos en U2.INT/U3.~INT/U3.VLED+).

## Uso

Estos tests son `integration_gui`: necesitan KiCad vivo con **una copia**
de este fixture abierta (no hay `open_project` programático en kipy/KiCad
10). Ver `docs/pruebas-gui.md §fixture despertador-routed` para el
protocolo completo.

## Estado del ruteo

- Board: 44×44mm (contorno `(125,60)`→`(169,104)`), plano GND en B.Cu
  filled desde cero antes del ruteo (C2, Freerouting no respeta el plano
  como exclusión de nets ajenos — D-19.1 v6 — se resuelve con refill +
  `enforce_hole_clearance` + persistencia D-23.2 post-route).
- Colocación: BT1 (batería, 24×21mm) + U4 (RF, 18.5×16.5mm) en cluster
  izquierdo con margen ≥2mm de borde; resto de los 23 footprints en franja
  derecha, verificados sin overlap de courtyard vía `get_footprint_neighbors`
  inclusivo (D-D4.1) antes de rutear. Baseline DRC pre-route (V4): **0
  courtyards_overlap, 0 edge_clearance, 0 silkscreen** — mejor que el
  residual histórico ~5 de D3/D4 (ver log de sesión).
- Ruteo en 3 corridas de `route_board` (1 completa desde cero + 2
  re-ruteos parciales de `/NSS` y `/SCK` para ejercitar V2-reforzado):
  10/10 nets ruteables ruteadas en las 3, 0 bloqueadas. Corrida 1 (desde
  cero): **128.8s**, 221 tracks + 27 vías. Corridas 2-3 (re-ruteo parcial):
  ~9-10s cada una.
- **DRC final: 0 errores, 0 warnings.**
- Único hallazgo de la sesión: corrida 1 dejó 1 `unconnected_items`
  (C2/C3 formaban una isla GND unida entre sí pero sin vía propia al
  plano). Diagnosticado con `get_tracks`/`get_footprint_neighbors` (sin
  cirugía a ciegas) y resuelto con un `add_via` puntual — no requirió
  re-ruteo completo ni tocó el mecanismo D-23.2.
- Gerbers (G3) y BOM exportados sin error, gate G3 pasó limpio (DRC=0
  bloquea el gate si hay errores; no fue necesario ningún workaround).

## Ratificación de D-23.2 (ADR-0012) — ya NO requiere el workaround manual

**Importante — supera al punto 6 histórico de "Regenerar el fixture" más
abajo:** el fixture de sesión 20 (D3) documentaba como paso obligatorio un
refill manual (`delete_zone`+`add_zone(fill=true)`) porque el refill interno
de `route_board` no recalculaba `hole_clearance` correctamente contra vías
nuevas (F-03, sesión 20, pre-D-23.2). Sesión 24 implementó el contrato
D-23.2 para cerrar esa clase de bug. **D5 (sesión 25) verificó 3/3 corridas
consecutivas de `route_board` donde `err_post` coincidió exactamente (total
y por_tipo) con un `run_drc()` independiente inmediato, sin necesidad del
refill manual, con mtime de disco cambiando post-save en las 3 y sin ningún
`EXTERNAL_EDIT_DETECTED` espurio.** El workaround del punto 6 se considera
**obsoleto para el server actual** (mantenido abajo solo como nota
histórica de por qué existía).

## ⚠️ Advertencia — no es referencia de diseño de colocación óptima

El esquemático y la topología eléctrica son correctos y representan el
diseño real del despertador. La **colocación física** fue diseñada por el
agente en una sola sesión (D5, tiempo acotado) — sirve para ejercitar cobre
denso, zonas, vías y el pipeline completo schematic→gerbers, pero no está
optimizada para RF (antena) ni para producción en serie sin revisión humana
adicional.

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
6. ~~Tras cualquier `route_board` con zonas de cobre en el board, correr
   `delete_zone`+`add_zone(fill=true)` con la misma geometría antes de
   confiar en el DRC~~ — **obsoleto desde D-23.2 (sesión 24), ratificado
   en D5 (sesión 25).** El refill interno de `route_board` ya recalcula
   `hole_clearance` correctamente y persiste antes de reportar `err_post`.
   Seguí corriendo `run_drc()` propio como cross-check de todos modos
   (buena práctica, no por desconfianza en el contrato).
7. Verificar el JSON de `route_board`: `drc.por_tipo` sin
   `copper_edge_clearance`, `nets.bloqueadas` idealmente vacío. Luego
   `run_drc()` manual para confirmar (coincide con `err_post` si D-23.2
   se sostiene — ver sección de ratificación arriba).
8. Copiar `.kicad_pcb`/`.kicad_pro`/`.kicad_sch`/`.kicad_prl`
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
real de un agente (proceso persistente, como en sesiones 20 y 25) esto no
pasa.
