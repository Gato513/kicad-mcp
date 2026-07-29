# Validation Report — ANAVI Macro Pad 12 (Nivel B-01)

**Sesión 32 (2026-07-29), sesión única — a diferencia del ciclo
31→31b→31c de Nivel A.** Segunda validación externa del flujo canónico
de `kicad-mcp`, primera de Nivel B (complejidad media, criterio de
diversidad D-30.4). Veredicto final: **Escenario 3 de 7** ("éxito con
matiz de fricciones P2/P3") con elementos de Escenario 2, más un hallazgo
independiente de robustez en `route_board` (P0/P1, ver §Fricciones).

## Historia de la validación

| Sesión | Qué hizo | Resultado |
|---|---|---|
| **32** (2026-07-29) | Admisión (con re-selección de candidato) + Bloque 1 (con incidente de proyecto erróneo) + Bloque 2 completo (colocación + zona + refill + ruteo, con timeout y hallazgo P0 de refill silencioso) + Bloque 3 (comparación D-30.3) + Bloque 4 (cierre) | 3/4 criterios D-30.3 cumplen (tracks, vías, cobre). DRC no cumple por hallazgo de conectividad GND (3ª instancia F-D5-01, promovida a P1 investigación). Hallazgo independiente: `route_board`'s refill interno falla en silencio bajo ciertas condiciones IPC — confirmado reproducible también en el audit log de sesión 31c. Validación Nivel B **cerrada**. |

---

## Contexto

- **Candidato prescrito por el prompt:** ANAVI Miracle Emitter — **refutado en Bloque 0** por verificación directa contra el repo real: sin diversidad D-30.4 genuina (sin cobre propio de USB-C, sin WS2812B, "ESP32-C3 vs ESP8266" del prompt era falso) y escala menor que Nivel A (15 fp/19 nets vs 13/20).
- **Candidato admitido:** `AnaviTechnology/anavi-macro-pad-12`, commit `0d3e1be82352e1ebd58966d3fda7a9cdf9e1d509` (2025-12-07, única rama `main`). OSHWA certificado, crowdfunded (Crowd Supply 2023), vendido en 3 tiendas. CC BY-SA 4.0.
- **Rama:** `sesion/32-validation-B-anavi-macro-pad-12`, encadenada desde `sesion/31c-reintento-anavi-dev-mic` (master no tenía mergeada la secuencia 31→31b→31c al arrancar sesión 32 — mismo patrón observado en 31c).
- **Excepción de admisión (criterio 6, DRC 0/0):** mismo precedente sancionado que Nivel A. Ground truth original: 179 violaciones (23 err/156 warn). Post-migración: 175 (19 err/156 warn) — **subconjunto estricto** del original (los 4 `invalid_outline` desaparecen, ningún tipo nuevo aparece). Caso más cómodo que Nivel A (que tuvo DRC idéntico bit a bit).
- **Diversidad D-30.4:** matriz de teclas con diodo por tecla (topología en malla), backlighting por tecla (12 LED + 12 resistor), footprints hot-swap Kailh, migración de formato KiCad real (6→10, primera de la Suite), escala 63 fp/48 nets (~3x Nivel A).

## Fases ejecutadas

### Bloque A — Gate GUI de regresión (adelantado, D-31.1 §6)

`test_pcb_session21_hole_clearance_gui.py` 2/2 + `test_pcb_session27_zone_persist_gui.py` 2/2, contra copia fresca de `despertador-routed` en `/tmp/kicad-mcp-sesion32-gui/`. Corrido una sola vez al inicio (sesión no toca `src/`).

### Bloque 0 — Admisión y ground truth (~2h con re-selección)

1. Verificación directa del candidato prescrito (fetch del repo real, no sólo el prompt) → refutado.
2. Encuesta de candidatos de respaldo del catálogo ANAVI (macro-pad-12, word-clock, thermometer) + MOD shield — `anavi-macro-pad-12` admitido en el primer intento de respaldo.
3. Clonado, 6 criterios + D-30.4 verificados con evidencia externa (OSHWA, Crowd Supply, Tindie, LectronZ).
4. Migración KiCad 6→10 (`kicad-cli sch/pcb upgrade --force`), DRC pre/post comparado (175 ⊂ 179, sin categorías nuevas).
5. `measure_ground_truth.py` extendido (schema 1.0→1.1, aditivo): `track_length_by_net_mm`, `via_count_by_net`, `drc_by_rule`, `orphan_vias`. **Regresión verificada** contra Nivel A: los valores de schema 1.0 (drc, tracks, vías, cobre, footprint/net/board_area/etc.) coinciden exactamente con los ya registrados en `metrics.md` de Nivel A.
6. `prepare_working.py` sobre el ground truth migrado: 63 footprints a `(0,0)`, 0 tracks/vías/zonas.

### Bloque 1 — Baseline (con incidente de proyecto erróneo)

**Hallazgo de entorno, no de flujo:** el servidor `kicad-mcp` resuelve
`run_drc`/`route_board`/auditoría vía la variable de entorno
`KICAD_MCP_PROJECT` (fija desde el arranque del proceso), independiente
de qué proyecto esté abierto en el GUI vivo (que sólo
`get_world_context` rastrea). `KICAD_MCP_PROJECT` seguía apuntando a
`/tmp/gui-test-project`, que todavía tenía el board de ANAVI Dev Mic de
la sesión 31c. Un `run_drc()` devolvió violaciones de un board
completamente ajeno (refs `MK1`/`C1`/`C2`) hasta que se diagnosticó vía
`get_world_context` + inspección de archivos.

**Fix aplicado (patrón D-27.1, reubicación no destructiva):** se
reemplazó el contenido de `/tmp/gui-test-project` con los archivos de
`working/anavi-macro-pad-12`, y se re-abrió el proyecto correcto en el
mismo path en el GUI vivo. Verificado con `get_world_context` +
`run_drc()` en simultáneo hasta que ambos coincidieron.

**Efecto colateral no buscado:** durante el diagnóstico, un
`get_world_context(kind="pcb")` disparado antes de detectar el mismatch
expuso sin querer las 63 posiciones completas del ground truth (antes de
empezar la colocación real). Reportado de inmediato al arquitecto;
decisión (`AskUserQuestion`): usar las coordenadas del GT para los 63
footprints (mecánicamente correctas de todos modos, dado el enclosure) y
reservar `get_footprint_neighbors` sólo para verificación post-colocación.

Baseline DRC (63 footprints apilados en origen): 1840 (1397 err/443
warn) — consistente entre ambas rutas de resolución tras el fix.

### Bloque 2 — Flujo canónico

1. **Refs duplicados:** 4× `REF**` (mounting holes, presentes también en
   el ground truth sin anotar) → `set_footprint_ref` ×3 (ADR-0013,
   patrón N-1). No cuenta como M2.
2. **Colocación:** 63 `move_footprint`, serializados uno por uno (lección
   de 31c: nunca batchear llamadas MCP en paralelo — cola IPC de
   profundidad 1). DRC post-colocación: 112 errores, **0** de
   `clearance`/`shorting_items`/`courtyards_overlap`/`hole_clearance`/
   `hole_to_hole` — placement físicamente limpio, sólo defectos
   heredados del ground truth (`solder_mask_bridge` 12,
   `footprint_type_mismatch` 6) + `unconnected_items` esperables
   (94, sin cobre todavía).
3. **Plano GND** (`add_zone`, B.Cu, `fill=true`) + **refill explícito**
   (D-26.1, `fill_zones()`, 23.63s).
4. **`route_board`, intento 1** (`timeout_s=1500`): **falla** —
   `KICAD_TIMEOUT` a los 1500s. Log de Freerouting confirma que no era
   falta de tiempo: el score quedó estancado en 980.45 (1 net sin
   rutear) durante los últimos ~50 de 195 passes — óptimo local real, no
   progreso interrumpido.
5. **`route_board`, intento 2** (`timeout_s=3600`): completa en
   `route_ms` 328943.848ms (≈5m29s) — **42/42 nets ruteables ruteadas, 0
   bloqueadas, 0 parciales**. Variabilidad entre intentos consistente con
   F-D6-01 (variabilidad Freerouting/JVM, cerrada sesión 29 como
   inherente al motor, no al flujo).
6. **Hallazgo P0/P1** (ver §Fricciones): el refill interno de
   `route_board` (`refill=true`) no persistió — `reloaded: false`,
   `zones.refilladas: 0` — dejando 259 violaciones DRC nuevas reales
   (236 `clearance` + 23 `hole_clearance`, 100% contra la zona GND).
   Recuperado manualmente ejecutando el propio paso 6 del flujo canónico
   ("Refill final") de forma explícita: `reload_board_from_disk()` +
   `fill_zones()`. Post-recuperación: `clearance`/`hole_clearance` → 0.
7. **DRC de cierre:** 179 total (20 err/159 warn). 2 `unconnected_items`
   nuevos (pads GND de `J4`/`J5` no conectados al plano/track) —
   **3ª instancia del patrón F-D5-01/F-V1c-01** (sesión 25 despertador →
   31c anavi-dev-mic → 32 macro-pad-12). Cumple el trigger de promoción a
   P1 investigación Fase 4 (ver BACKLOG).
8. **Chequeo de vías huérfanas** (script extendido, `_orphan_vias`):
   **0 encontradas.** El hallazgo del punto 7 es a nivel de *pad*
   (conectividad al plano/track), mecanismo distinto al de una vía
   aislada — mismo síndrome de familia, no reincidencia idéntica.

### Bloque 3 — Comparación cuantitativa (D-30.3, con análisis descompuesto)

| Criterio D-30.3 | Umbral | Resultado | Veredicto |
|---|---|---|---|
| Tracks | ±30% | −4.05% | **CUMPLE** |
| Vías | ±20% | +20.00% (exacto) | **CUMPLE** (borde) |
| Cobre | ±25% | +3.23% | **CUMPLE** |
| DRC (matizado) | 0 nuevos eléctricos/estructurales graves | +4 eléctricos nuevos, −1 resuelto | **NO CUMPLE** |

Análisis por-net, tabla DRC por severidad, y análisis H2 completo:
`metrics.md` de este directorio.

## Fricciones

### F-V2-REFILL-SILENCIOSO (P0/P1) — refill de `route_board` no persiste bajo falla de `reload_board_from_disk`

**Severidad:** P0/P1 — rompe la garantía D-23.2/ADR-0012
("disco == memoria == err_post reportado") sin señal de error visible.

**Mecanismo confirmado** (investigación de código, `src/kicad_mcp/tools/pcb.py`):
el bloque de refill+`enforce_hole_clearance`+`save_board` post-ruteo
(`pcb.py:2728-2733`) sólo se ejecuta si `reloaded is True`. `reloaded`
depende de que `bridge.reload_board_from_disk(open_board)` no lance
`KicadMcpError` (`pcb.py:2701-2710`) — una operación de **mutación**,
deliberadamente **sin reintento** incluso ante un `AS_BUSY` transitorio
(D-07.1). Si falla una sola vez, la excepción se descarta en silencio
(`except KicadMcpError: reloaded = False`), y **todo** el paso de
seguridad (el que existe específicamente para corregir que "Freerouting
NO respeta el plano GND como zona de exclusión", D-19.1) se salta sin
que `route_board` reporte ningún error — devuelve un payload de éxito
normal con `refill: true` solicitado pero silenciosamente no honrado.

**No es un hallazgo aislado de esta sesión.** El audit log de
`/tmp/gui-test-project` conserva la llamada `route_board` original de
**sesión 31c** (`2026-07-29T11:13:58`): `"reloaded": false,
"zones_refilladas": 0` — **idéntico patrón**, en un board y una sesión
distintos. Sesión 31c ejecutó su propio "Refill final" explícito pocos
minutos después (11:16:46) sin cruzar estos campos contra la promesa de
`refill=true` — el hallazgo nunca se documentó porque el paso
compensatorio del flujo canónico (ya prescripto independientemente,
D-26.1/D-23.2) enmascaró el síntoma. **Con 2 sesiones independientes
mostrando el mismo patrón, esto es un comportamiento reproducible del
código, no una casualidad de esta corrida.**

**Por qué no bloqueó esta sesión:** el flujo canónico prescribe un paso
explícito de "Refill final" (D-23.2) *independiente* de si el refill
interno de `route_board` funcionó — ese paso, ejecutado manualmente
(`reload_board_from_disk()` + `fill_zones()`), corrigió las 259
violaciones. El riesgo real es para cualquier uso de `route_board(refill=true)`
que confíe en esa promesa **sin** el paso explícito adicional — el
parámetro `refill=true` está, en la práctica, no funcional bajo esta
condición, y no lo comunica.

**Recomendación:** agenda de sesión de fix intermedia (patrón 31b) antes
de sesión 33. Candidatos de fix: (a) que el refill+persistencia en disco
NO dependa de `reload_board_from_disk` (son operaciones lógicamente
independientes: una sincroniza el *editor vivo*, la otra corrige y
persiste el *archivo en disco*); (b) si se mantiene la dependencia,
surfacear un código de error explícito (ej. `POST_ROUTE_REFILL_SKIPPED`)
en vez de un payload de éxito silencioso; (c) reintentar
`reload_board_from_disk` una vez ante `AS_BUSY` específicamente (D-07.1
excluye mutaciones del retry general, pero esta mutación en particular
sólo re-sincroniza estado, no aplica un cambio de diseño — candidato a
excepción documentada).

### F-V2-VIA-HUERFANA (P2, 3ª instancia — promovido a P1 investigación)

2 pads GND (`J4` pad 3, `J5` pad 3) no conectados al plano/track tras el
refill de recuperación — mismo síndrome que F-D5-01 (sesión 25) y
F-V1c-01 (sesión 31c), mecanismo a nivel de *pad* (no de vía aislada,
ver Bloque 2 punto 8). **3ª instancia del patrón → cumple el trigger de
promoción explícito del prompt de sesión 32: "agenda sesión de fix
intermedia con severidad P1 investigación Fase 4, INDEPENDIENTE del
escenario que aplique al resto de la sesión."**

### F-V2-ROUTER-TIMEOUT (P2/P3, variabilidad esperada)

Intento 1 de `route_board` (`timeout_s=1500`) no convergió — óptimo
local real (score estancado), no falta de tiempo. Intento 2
(`timeout_s=3600`) completó en 5m29s. Consistente con F-D6-01 (variabilidad
Freerouting/JVM, cerrada sesión 29). Recomendación operacional para
sesiones futuras sobre boards densos: partir de `timeout_s` alto (≥1800s)
en vez de escalar por tramos, dado que un intento que plateau no mejora
con más tiempo del mismo intento — conviene reintentar con semilla nueva
en vez de esperar más.

## Métricas D-30.3, auxiliares (M1/M2/M3), y Análisis H2

Ver `metrics.md` de este directorio para el detalle numérico completo.

## Veredicto y próximos pasos

**Escenario 3 de 7** ("éxito con matiz de fricciones P2/P3"), con
elementos del Escenario 2 (matiz de umbrales — DRC no cumple pero por
motivo puntual y explicado). El hallazgo del refill silencioso
(F-V2-REFILL-SILENCIOSO) es la evidencia más valiosa de la sesión:
expone un gap de robustez arquitectónico real en `route_board`, presente
desde al menos sesión 31c, nunca antes documentado porque el flujo
canónico lo compensaba sin que nadie cruzara los campos de diagnóstico.

**Segundo punto de evidencia sobre D-30.3** (ver `metrics.md` §Análisis
H2): con una base de vías 15x más grande que Nivel A, el umbral ±20%
resultó razonablemente calibrado (justo en el borde, no una falla
amplia) — apoya la hipótesis de que el problema de 31c era el tamaño de
la base, no el umbral relativo en sí.

**Recomendaciones para BACKLOG/DECISIONES/sesión 33:**
1. Agendar sesión de fix intermedia (32b-style) para
   F-V2-REFILL-SILENCIOSO antes de sesión 33 — severidad P0/P1,
   reproducible en 2 sesiones independientes.
2. F-D5-01/F-V1c-01/F-V2-VIA-HUERFANA: promover a investigación P1 Fase 4
   (3ª instancia, trigger cumplido).
3. Tercer punto de evidencia H2 en sesión 33 antes de cerrar la revisión
   de umbrales D-30.3 post-33.
