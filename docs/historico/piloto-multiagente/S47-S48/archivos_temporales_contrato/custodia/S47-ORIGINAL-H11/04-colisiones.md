# 04 — Fase 4: Colisiones con riesgos fuera de scope (§9)

Matriz sobre los 12 candidatos con ficha completa. `—` = sin colisión ni
adyacencia. `ADYACENTE` = comparten dominio temático sin tocar el mismo
código (documentado en la ficha correspondiente como hallazgo §14, sin
bloquear). `TOCA` = referencia directa a un módulo del riesgo, sin ser una
colisión de lógica (import normal). Ningún candidato tiene una colisión
real (import/lógica compartida) con ninguno de los 8 riesgos — es
consistente con que los 8 clusters institucionalmente excluidos (F-DT.1) ya
absorbieron toda la superficie de zonas/route_board/stitching.

| # | Candidato | P1-2 (kiid) | DT3 (geometría en bridge/) | route_board | zone-fill | Freerouting | G2 | G4 | `_CACHE`/snapshots |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `_delete_copper` | — | — | — | — | — | — | — | TOCA (`..snapshots`, import normal) |
| 2 | `_audit_error` | — | — | — | — | — | — | — | — |
| 3 | `get_footprint_neighbors` | — | ADYACENTE | — | — | — | — | — | TOCA (`..snapshots`) |
| 4 | `_bbox_distance_to_point` | — | ADYACENTE | — | — | — | — | — | — |
| 5 | `_copper_distance_mm`+`_dist_point_segment` | — | ADYACENTE | — | — | — | — | — | — |
| 6 | `_copper_in_bbox` | — | ADYACENTE | — | — | — | — | — | — |
| 7 | `_copper_on_layer` | — | — | — | — | — | — | — | — |
| 8 | `move_footprint` | — | — | — | — | — | — | — | TOCA (`..snapshots`, `..gates.g1`) |
| 9 | `add_track` | — | ADYACENTE | — | — | — | — | — | TOCA (`..snapshots`, `..gates.g1`, `..tools.world`) |
| 10 | `draw_board_outline` | — | — | — | — | — | — | — | TOCA (`..snapshots`, `..gates.g1`) |
| 11 | `_resolve_board` | — | — | — | — | — | — | — | — |
| 12 | `_segment_intersects_bbox` | — | ADYACENTE | — | — | — | — | — | — |

## Notas

**P1-2 (kiid sin sanitizar):** el sitio de emisión (`_encode_tracks`/
`_encode_zones`) ya se movió a `pcb_encoders.py` en DT1 Slice 1 y está
completamente fuera de los 63 miembros de V de esta caracterización.
**Ninguna colisión posible.**

**DT3 (geometría de dominio dentro de `bridge/`):** DT3 está textualmente
acotada a código dentro de `bridge/` (`docs/BACKLOG.md:519`,
"Geometría de dominio dentro de `bridge/`"). Los 6 candidatos marcados
`ADYACENTE` (3, 4, 5, 6, 9, 12) son geometría de coordenadas/distancia/
colisión, pero viven en `tools/pcb.py`, **no** en `bridge/` — no hay
colisión de código ni de ubicación con lo que DT3 describe. Se marca
`ADYACENTE`, no `TOCA` ni colisión, porque es temáticamente cercano y un
humano podría razonablemente preguntarse si DT1 Slice 2 y DT3 deberían
resolverse juntos — `docs/BACKLOG.md:527` es explícito: "No mezclar con el
siguiente slice de DT1 sin decisión humana." Se eleva como hallazgo §14
(`04-hallazgos-fuera-de-scope.md`, `RIESGO_NUEVO`/`DRIFT_AFECTA_CANDIDATO`),
no como bloqueo de S47 (ninguno de los 12 candidatos alcanzó APTO de todas
formas, por motivos independientes — S1/S8 o S7).

**route_board / zone-fill / Freerouting:** ninguno de los 12 candidatos
comparte símbolos con el cluster de `route_board` ni con la familia de
zonas (ambos ya institucionalmente excluidos por F-DT.1, ver
`02-candidatos/descartados.md`). Verificado por intersección de conjuntos
vacía entre cada K y `ZONE_INSTITUTIONAL ∪ {miembros del cluster
route_board}`.

**G2 / G4:** ambos módulos de gates están **ausentes del repositorio**
(`gates/g2.py`, `gates/g4.py` — verificado en `00-preflight.md §4`). Ningún
candidato puede colisionar con código que no existe.

**`_CACHE` (snapshots/invalidación):** los candidatos que incluyen una
closure (1, 3, 8, 9, 10) importan `..snapshots` porque **toda** tool
mutante de `pcb.py` ya lo hace hoy (parte del decorador `@mutating_tool` /
patrón W-IPC descrito en CLAUDE.md regla 7-8 y DT2) — es una dependencia
externa estable preexistente, no un acoplamiento nuevo introducido por la
extracción, y no cambia con el candidato elegido. Sin colisión de lógica.
