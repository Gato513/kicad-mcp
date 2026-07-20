# Fixture `despertador-routed`

Copia del proyecto "despertador inteligente" (24 footprints) **con contorno
Edge.Cuts y ruteo real** generados por dogfood de `route_board` en sesión 17
(P2.1/P2.2). Existe para que los tests `integration_gui` de sesión 16
(`test_add_track_pad_to_point_does_not_worsen_drc`,
`test_f13_scenario_gap_visible_and_repaired_without_external_parsing`) ejerciten
colisión real contra cobre denso — la sesión 16b los corrió contra un board
vacío (sin tracks) porque el proyecto de prueba del usuario no tenía ruteo
todavía, y no probaban de verdad la lógica de evitar cobre ajeno.

## Uso

Estos tests son `integration_gui`: necesitan KiCad vivo con **una copia** de
este fixture abierta (no hay `open_project` programático en kipy/KiCad 10).
Ver `docs/pruebas-gui.md §fixture despertador-routed` para el protocolo
completo.

## Estado del ruteo

- `min_copper_edge_clearance` del proyecto: **0.5mm** (regla real, NO bajada
  como en el Dogfooding 2).
- Generado con el `route_board` nuevo de sesión 17 (inyección de edge
  clearance al DSN vía `(clearance_class "board_edge")`, ver
  `bridge/autoroute.py`).
- 41 nets totales, 10 ruteables (multi-pin), **10/10 ruteadas**. DRC
  post-route: **1 solo error** (`unconnected_items` — el heurístico de
  ruteo/pines de `classify_net_routing` no reconstruye el grafo de
  conectividad exacto, documentado como limitación conocida) y **0
  violaciones de `copper_edge_clearance`** — el gate duro de P2.1 se cumple.
  313 tracks + 21 vías agregadas.
- Ver `docs/sesiones/17-reporte.md` para el JSON literal completo del
  resultado de `route_board`.

## ⚠️ Advertencia — NO es referencia de diseño

El esquemático de este proyecto tiene **defectos eléctricos conocidos**
(Dogfooding 2 / F-04: SCL↔INT_SENS y NSS↔MOSI fusionadas por error de
diseño). Este fixture existe **solo** para ejercitar cobre denso en tests de
colisión y regresión de `route_board` — nunca lo uses como ejemplo de un
diseño correcto.

## Regenerar el fixture

Si el esquemático cambia (deuda pendiente para sesión ≥20):

1. Copiar el proyecto fuente a un directorio de trabajo (`/tmp/...`), nunca
   mutar este fixture in-place.
2. Abrirlo en KiCad (PCB Editor) — dejarlo abierto y **no volver a tocarlo**
   desde la GUI durante los pasos siguientes.
3. **Un solo proceso Python, una sola llamada a `route_board`** (no reintentar
   en procesos separados): `route_board` hace un "save_board implícito"
   (live→disco) si el board abierto coincide con el target y el store en
   memoria no está `live_stale` — pero el flag `live_stale` vive en memoria
   del PROCESO servidor, no persiste entre invocaciones. Si corrés
   `route_board` desde scripts nuevos repetidamente, cada uno arranca con
   `live_stale=False`, dispara el save implícito, y **pisa el ruteo en disco
   con el estado viejo de la GUI** antes de re-rutear desde cero (hallazgo de
   sesión 17 — no es un bug del código, es cómo se comporta al invocarlo
   fuera de una sesión MCP persistente). Con un cliente MCP real de un agente
   (proceso persistente) esto no pasa.
4. Requiere `KICAD_MCP_FREEROUTING_JAR` apuntando al jar de Freerouting.
   **Hallazgo de sesión 17**: si la config de Freerouting
   (`$TMPDIR/freerouting/freerouting.json` o `~/.config/freerouting/…`) tiene
   `gui.enabled=true` (default de instalación), el batch mode completa el
   ruteo pero el proceso se cuelga sin escribir el `.ses` — `route_board`
   ahora fuerza `gui.enabled=false` automáticamente antes de cada invocación
   (`_ensure_freerouting_headless_config`), pero si regenerás el fixture
   manualmente con otra herramienta, tené en cuenta esto.
5. Si no tiene contorno Edge.Cuts todavía, llamar `draw_board_outline` PRIMERO
   (en el mismo proceso o uno previo — no importa para el outline porque esa
   tool hace su propio `save_board` explícito).
6. Verificar el JSON de `route_board`: `drc.por_tipo` sin
   `copper_edge_clearance`, `nets.bloqueadas` idealmente vacío.
7. Copiar `.kicad_pcb`/`.kicad_pro`/`.kicad_sch`/`.kicad_prl` **inmediatamente**
   del directorio de trabajo a `tests/fixtures/despertador-routed/` — antes de
   correr cualquier otra tool que pueda volver a disparar el save implícito.
