# Fixture `despertador-routed`

## Regenerado en sesión 20 (Dogfooding 3, 2026-07-23)

Este fixture fue **regenerado desde cero** en la sesión 20 (Dogfooding 3,
`docs/sesiones/prompts/PROMPT-DOGFOODING-3.md`) partiendo del esquemático
**corregido en sesión 19b** (commit base `b27254e`). Reemplaza al fixture
STALE anterior (generado en sesión 17 sobre el sch viejo con las 5 fusiones
de red defectuosas).

- Esquemático fuente: 0 errores ERC, 4 warnings `lib_symbol_mismatch`
  aceptados (D-19b.1 — símbolos locales divergen intencionalmente de la
  librería del sistema, no ejecutar "Update Symbols from Library").
- Topología de red: `/NSS` separado de `/MOSI`, `/SCL` limpio (sin fusión
  con `/INT_SENS`), No-Connect explícitos en U2.INT/U3.~INT/U3.VLED+.

## Uso

Estos tests son `integration_gui`: necesitan KiCad vivo con **una copia**
de este fixture abierta (no hay `open_project` programático en kipy/KiCad
10). Ver `docs/pruebas-gui.md §fixture despertador-routed` para el
protocolo completo.

## Estado del ruteo

- Board: 44×44mm, contorno Edge.Cuts + plano GND en B.Cu (con 2 muescas
  poligonales para aislar ANT1 y los 3 agujeros NPTH de J1 — ver
  `docs/sesiones/dogfooding/` o el log de fricciones de sesión 20, F-01).
- `min_copper_edge_clearance` del proyecto: **0.5mm**.
- Generado con `route_board(timeout_s=900)`: 10/10 nets ruteables
  ruteadas, 0 bloqueadas, 243 tracks + 32 vías del autorouter, 53s.
  `reloaded=true` (recarga programática, sin revert humano — D-V3.1).
- **DRC final: 0 errores, 33 warnings** (todos cosméticos: silkscreen
  clipping/overlap en el cluster denso de TPs y `lib_footprint_mismatch`
  esperado en U2/U3/J1, mismo espíritu que los warnings ERC aceptados).
- Cirugía manual post-autoroute (documentada en el log de fricciones de
  sesión 20): refill de zona con `delete_zone`+`add_zone` (bug de
  `fill_zones`/refill interno de `route_board` no limpiaba hole clearance
  contra vías nuevas — F-03) + reruteo de `/MOSI` cerca de J1 vía un
  túnel de 2 vías por B.Cu (corredor este de J1, entre el borde del board
  y sus propios agujeros NPTH, resultó no ruteable dentro de las reglas
  del proyecto — F-04).
- Gerbers (G3) y BOM exportados sin error.

## ⚠️ Advertencia — no es referencia de diseño de colocación óptima

El esquemático y la topología eléctrica son correctos y representan el
diseño real del despertador. La **colocación física** fue diseñada por el
agente en una sola sesión con el tiempo acotado del Dogfooding 3 — sirve
para ejercitar cobre denso, zonas, vías y el pipeline completo
schematic→gerbers, pero no está optimizada para RF (antena) ni para
producción en serie sin revisión humana adicional.

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
6. **Tras cualquier `route_board` con zonas de cobre en el board**,
   correr `delete_zone`+`add_zone(fill=true)` con la misma geometría
   antes de confiar en el DRC — el refill interno de `route_board` no
   recalcula hole clearance correctamente contra vías nuevas (F-03,
   sesión 20). No confiar en `route_board.drc.err_introducidos`; correr
   `run_drc()` propio siempre.
7. Verificar el JSON de `route_board`: `drc.por_tipo` sin
   `copper_edge_clearance`, `nets.bloqueadas` idealmente vacío. Luego
   `run_drc()` manual para el estado real (ver punto 6).
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
real de un agente (proceso persistente, como en sesión 20) esto no pasa.
