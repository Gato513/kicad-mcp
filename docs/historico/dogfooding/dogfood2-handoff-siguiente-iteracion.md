# Handoff — Dogfooding Etapa 2 (corrida 2, 2026-07-16) → siguiente iteración

Contexto consolidado para la próxima sesión (DEV sobre kicad-mcp / hoja de ruta v3).
Log crudo F-NN con detalle completo: `/tmp/dogfood2-fricciones.md` (leerlo junto a este).

---

## Resultado en una línea

Placa `despertador_inteligente` (ATtiny85 wearable, 24 fps, 40×40mm, 2 capas) llevada
de PCB-sin-colocar a **gerbers fabricables (G3) con DRC 0 errores**. **Nota 7.5/10**
(corrida 1: 7/10; Etapa 1: 5/10; objetivo ≥8 NO alcanzado).

## Qué frenó el ≥8 (priorizado para v3)

### P1 — El cobre es invisible para el agente (F-13) ⇒ la fricción más cara
- TOON (`get_world_context` pcb) muestra componentes+nets pero **no tracks ni vías**.
- Consecuencia real: ~50% de la sesión fue "cirugía a ciegas": hubo que parsear el
  `.kicad_pcb` con Python externo y armar un verificador de colisiones casero para
  poder usar `add_track` sin adivinar. Aun así 2 iteraciones DRC se perdieron por
  esquinas redondeadas de pads (roundrect) no modeladas.
- **Propuesta v3:** `get_tracks(bbox=|net=)` (segmentos+vías con endpoints, layer,
  width, net) o sección `[T]` opcional en TOON. Con eso el patrón
  borrar→verificar→añadir se vuelve determinista.

### P2 — delete_track no puede seleccionar segmentos junto a uniones (F-13)
- Desambiguación por radio fijo 0.5mm: un segmento de <1mm conectado a otros dos es
  **inseleccionable** (todo punto del segmento queda a <0.5 de un vecino). Workaround
  usado: borrar de afuera hacia adentro. Además el error promete `data.candidates`
  y no viene en la respuesta.
- **Propuesta:** IDs estables de track en el error/`get_tracks` + `delete_track(id=)`.

### P3 — route_board: caja negra con métricas engañosas (F-08, F-09, F-12)
- `route_ms` **sigue sin reportarse** (ya era F-08 de la corrida 1 — pendiente).
- "N/M nets" confunde: pase 1 dijo `24/64` (¿64 incluye 33 nets unconnected-* de
  1 pad?); pase 4 dijo `0/1 +10 tracks` — los 10 tracks fueron re-ruteos silenciosos
  de OTRAS nets, cero cobre de la net objetivo.
- Pase 1 dejó 40 unconnected (GND fragmentado, 1 sola vía); convergió recién en el
  pase 3. El pase 2 (incremental, tras mover 2 fps) hizo TIMEOUT a 600s; con
  `timeout_s=1800` ok. `/RESET` (2 pads) resultó **imposible en 4 pases** — la dorsal
  B.Cu de /SDA (3.4,8.2)→(15.7,38.7) parte la placa sin puertas y el router no lo
  dice; terminó ruteándola el humano con push-and-shove en GUI.
- **Propuesta:** post-DRC integrado al resultado de route_board (por net), route_ms,
  denominador claro, y reporte "net X no ruteable: bloqueada por Y".

### P4 — Freerouting no hereda las reglas de KiCad (F-11)
- Produce clearance al contorno fija ~0.47mm vs regla 0.5 ⇒ 7 violaciones
  `copper_edge_clearance` sistemáticas (0.4696) + 4 más profundas (0.3791).
- Peor: el DRC reporta esas violaciones con `pos=[0,0]` (posición del rectángulo
  Edge.Cuts, no del track) ⇒ **ilocalizables programáticamente**.
- Workaround (aprobado explícitamente por el humano tras bloqueo del clasificador):
  `min_copper_edge_clearance` 0.5→0.35 editado a mano en `.kicad_pro` (no hay tool
  de reglas). 0.35 sigue ≥0.3 típico de fabricación.
- Anchos: el router usó 0.2mm uniforme; el brief pedía 0.15 señal / 0.25 power —
  no configurable por tool.
- **Propuesta:** inyectar reglas del board al DSN (edge clearance, anchos por
  netclass) y arreglar el pos del DRC.

### P5 — El loop route→File→Revert humano (×3 en la sesión)
- `route_board` escribe a disco; el board vivo queda stale. El guard
  `EXTERNAL_EDIT_DETECTED` **funcionó perfecto** (bloqueó un delete_track que habría
  pisado el pase 4) pero cada route exige un humano haciendo File→Revert.
- **Propuesta:** recarga programática post-route (IPC RevertBoard si existe, o
  rutear sobre el vivo), o al menos batching: un solo revert por sesión de ruteo.

## Fricciones menores (detalle en el log F-NN)

- **F-03:** `run_erc` reporta posiciones **÷100** (dice mm; U3 real x≈45.7 → reporta 0.457).
- **F-05:** `move_footprint` valida contra bbox del cluster ±100mm e **ignora el
  Edge.Cuts** ⇒ el contorno dibujado en (0,0) era inalcanzable. Truco descubierto:
  mover 1 fp "puente" al borde del rango lo expande (el bbox se recalcula).
- **F-06:** contorno inmutable: no hay delete/resize/replace de Edge.Cuts (ya era
  F-06 en corrida 1 — pendiente).
- **F-02:** config MCP en `~/.claude.json` apuntaba a `KICAD_MCP_PROJECT=/tmp/dogfood2-proyecto`
  (inexistente); symlink al proyecto real (`/tmp/gui-test-project`) lo resolvió sin
  reiniciar el server. `health()` no distingue "no configurado" de "path no existe".
- **add_track** no acepta mezclar `from_pad` con coordenadas crudas (pad→punto es
  el caso natural de reparación).
- **CONTEXT_BUDGET_IMPOSSIBLE** con hint inconsistente: "mínimo ≈1001 tokens" pero
  max_tokens=1100 también falló.
- Sin tool de **zonas/pours** ⇒ sin plano GND (subóptimo para RF; GND quedó como
  estrella de pistas — aceptable a 8MHz/I2C).
- Sin **rotación** en move_footprint (ya conocido).
- BOM incluye J1 (Tag-Connect) que el brief declaraba `in_bom no` — el sch no lo marca
  (dato para el arquitecto, no bug del server).

## Aciertos a preservar (no romper en v3)

- `get_component_detail` (courtyard + pads absolutos) — la base de toda la colocación.
- Guard `live_stale` / `EXTERNAL_EDIT_DETECTED` con hint accionable.
- `run_drc` presupuestado con `min_severity` + resumen por tipo (8 corridas, fue el
  oráculo de toda la cirugía).
- Gate G3: `export_manufacturing` bloqueó con DRC sucio y desbloqueó en 0 errores.
- `draw_board_outline` anti-apilado; `PATH_OUTSIDE_PROJECT` en exports.
- Las tools de cirugía en sí: 13 delete_track, 21 add_track, 6 add/delete_via
  ejecutadas — repararon 5 nets que el autorouter no pudo.

## Estado del proyecto en disco (por si la próxima sesión lo retoma)

- Proyecto: `/tmp/gui-test-project/` (¡sin subdirectorio! el brief decía otra ruta — F-01).
  Symlink `/tmp/dogfood2-proyecto` → ahí (lo espera la config MCP).
- `despertador_inteligente.kicad_pcb`: colocado + ruteado 100%, DRC 0 err / 31 warn
  (silkscreen + lib_mismatch). `min_copper_edge_clearance=0.35` en el `.kicad_pro`.
- Gerbers: `/tmp/gui-test-project/fab/` (26 archivos + drill). BOM: `bom.csv`.
  Renders: `pcb.png`, `pcb.pdf`.
- **Deuda del ESQUEMÁTICO (arquitecto, no server):** ERC con 2 errores (pin_to_pin
  INT U2↔U3; pin_not_connected U3) y nets fusionadas: SCL→/INT_SENS y NSS→/MOSI
  (U4.3 y U4.5 en la misma net). La placa ruteada hereda esas fusiones tal cual.
  Re-fabricar tras corregir el sch implicaría re-rutear.

## Métricas de la sesión

~118 llamadas MCP: 32 move_footprint (6 err rango), 21 add_track (2 err), 13
delete_track (4 err desambiguación), 8 run_drc, 8 get_world_context (3 err
presupuesto), 6 get_component_detail, 6 add/delete_via, 5 route_board (1 timeout),
5 save_board, 4 export_render (1 err path), 2 health, 2 draw_board_outline (1 err),
1 run_erc, 1 export_manufacturing, 1 export_bom. Contactos humanos: 3 reverts +
1 aprobación de regla + 1 pista /RESET en GUI. Duración ≈2.5h (≈45min de router).
