# Dogfooding 6 — Log de fricciones

**Sesión:** 28. **Fecha:** 2026-07-25. **Placa:** despertador ATtiny85 wearable
(misma que D2/D3/D4/D5). **Fase del proyecto:** Fase 3 (consolidación), segundo
dogfooding de ratificación. **Objetivo primario:** ratificar la extensión del
contrato D-23.2 (sesión 27) a `fill_zones`/`add_zone(fill=True)` en flujo real +
primera aplicación empírica de D-26.1 (refill obligatorio pre-baseline).

Formato de fricción:
```
## F-D6-NN — Título corto
- **Qué pasó:** ...
- **Qué esperaba:** ...
- **Workaround:** ...
- **Costo:** [bajo/medio/alto]
- **Severidad:** [info/warn/bloqueante]
```

---

## Fase 0 — Verificación de entorno

- `verificar_entorno.py`: 14 OK · 2 WARN (`KICAD_MCP_FREEROUTING_JAR` no seteada
  en shell — sí lo está para el server vía `~/.claude.json`; npx/Inspector
  ausente, no bloquea) · 0 FAIL. Mismo patrón que D5. VEREDICTO: listo para
  integration con kicad-cli (sin GUI) — GUI ya está corriendo por fuera
  (pid 17766 `kicad`, pid 53644 server MCP).

## Observación documental (no fricción de tool, para el arquitecto)

`docs/CONTEXT.md` §"Decisiones vigentes" (línea ~146-148) todavía dice: "hoy
garantizado solo en `route_board`. `fill_zones` y `add_zone(fill=True)` todavía
no lo cumplen — es la generalización pendiente de Fase 3". Esto es drift
documental post-sesión 27: la sección "Estado actual" del mismo archivo (líneas
72-78), `docs/DECISIONES.md` §2 y `docs/adr/0012...md` §"Extensión de alcance
(sesión 27)" SÍ reflejan la extensión ya mergeada. No se corrige durante el
dogfooding (regla: toda falla se registra, no se arregla) — reportar al
arquitecto para consolidación docs.

---

## Fase 1 — Restore D-27.1 + verificación de estado + colocación

- **Restore D-27.1 (autorizado por el arquitecto vía AskUserQuestion antes de
  arrancar):** el proyecto vivo (`/tmp/gui-test-project`) tenía el board
  ruteado de D5/S27 (252 segments, 34 vías, 7 zonas, 1 outline, 4 keepouts
  `__kicadmcp_hc__`) — no un board vacío, y `draw_board_outline` rechaza si
  ya hay contorno. Backup no destructivo de los 4 archivos vivos a scratchpad
  de sesión, sobrescritos en el mismo path desde
  `/home/astra/Documents/gui-test-project-pre-D3/` (sin `rm -rf`),
  `reload_board_from_disk()` sin reiniciar la GUI. Verificado:
  `get_world_context(kind="pcb")` → `outline:none`, 23 componentes, sin
  ruteo, bbox 129.7,66.0→154.3,101.2 (coords heredadas del sch import,
  igual que D5 pre-colocación). `get_zones(layer="B.Cu")` → 0 zonas. sch md5
  `fe63dbc1…` idéntico al fixture y a la fuente pre-D3. Restore limpio,
  0 fricciones.
- `run_erc()`: 0 errores, 4 warnings `lib_symbol_mismatch` (U1 ATtiny85-20S,
  U2 MPU-6050, U3 MAX30102, U4 RFM69CW) — coincide con D-19b.1 esperado.
  **F8 NO necesario**, igual que D5.
- Extracción read-only de las 23 posiciones de D5 desde
  `tests/fixtures/despertador-routed/despertador_inteligente.kicad_pcb`
  (procesado con script Python, nunca volcado al contexto) — todas
  rotación 0.
- `get_footprint_neighbors` inclusivo (D-D4.1/C6, radius_mm=3) en BT1, U4,
  J1, J2, ANT1 sobre sus posiciones heredadas (pre-move) — 5 llamadas.
  `edge:null` en las 5 (esperable, sin contorno todavía no hay borde contra
  el cual medir distancia). Sin sorpresas geométricas (a diferencia de D5,
  que detectó BT1/U4 fuera del futuro outline en este mismo paso) — acá no
  aplica el mismo chequeo porque el bbox del outline destino (44×44 desde
  125,60) es idéntico al de D5 y las coordenadas destino son las mismas que
  D5 ya validó como dentro del contorno.
- 23× `move_footprint` con las coordenadas de D5 → 23/23 OK, `save_board()`
  OK. Colocación geométricamente idéntica a D5 por diseño (réplica
  intencional, ver plan).

## Fase 2 — Contorno y plano GND

- `draw_board_outline(x_mm=125, y_mm=60, width_mm=44, height_mm=44)` → OK,
  44×44mm, misma variable controlada que D3/D4/D5.
- `add_zone(net="GND", layer="B.Cu", bbox=[125,60,169,104], fill=true)` →
  OK, filled, area_mm2=1936 (board completo, esperado — Freerouting no
  respeta el plano como exclusión, C2/D-19.1; el refill+enforce
  post-route arregla el resultado).

## V2-add_zone-1 — Cross-check D-23.2, tool=add_zone

- **Tool invocada:** add_zone(fill=true) — primera aplicación real del
  contrato D-23.2 extendido (sesión 27) en flujo de dogfooding.
- **Estado interno reportado:** sin campo `drc` por diseño (D-23.2
  extendido); `filled:true`, `area_mm2:1936`.
- **run_drc() independiente:** 56 (por_tipo: {"unconnected_items": 56}) —
  0 hole_clearance/clearance/solder_mask_bridge. Esperable pre-route (aún
  sin cobre ruteado, todos los pines "unconnected").
- **Coinciden / sin hole_clearance ni clearance espurio vs Zone GND:** sí
  (no aparece ninguno).
- **mtime pre-op:** 1784991650 (2026-07-25 12:00:50 -03) · **mtime
  post-op:** 1784991690 (2026-07-25 12:01:30 -03) · **cambió:** sí (+40s).
- **EXTERNAL_EDIT_DETECTED en lecturas posteriores:** no (a confirmar en
  pasos siguientes de la sesión).

## Fase 3 — Refill D-26.1 explícito + baseline V4 (el corazón de D6)

## V2-fill_zones-1 — Cross-check D-23.2, tool=fill_zones

- **Tool invocada:** fill_zones() explícito — esta es la aplicación
  concreta de D-26.1 (C7): refill obligatorio post-colocación masiva,
  antes de leer el baseline DRC.
- **Estado interno reportado:** sin campo `drc` por diseño;
  `zones_filled:1`, `duration_ms:1599.6`.
- **run_drc() independiente:** 56 (por_tipo: {"unconnected_items": 56}) —
  0 hole_clearance/clearance/solder_mask_bridge.
- **Coinciden / sin hole_clearance ni clearance espurio vs Zone GND:** sí.
- **mtime pre-op:** 1784991690 (12:01:30) · **mtime post-op:** 1784991785
  (12:03:05) · **cambió:** sí.
- **EXTERNAL_EDIT_DETECTED en lecturas posteriores:** no.

## V4 — Baseline DRC pre-route (post-D-26.1)

- **Total errores:** 56
- **por_tipo:** `{"unconnected_items": 56}`
- **Violaciones individuales (hole_clearance/clearance/solder_mask_bridge):
  NINGUNA.** `unconnected_items` se omite en detalle por ser 56 triviales
  pre-route (se resuelven íntegramente por el propio ruteo), igual
  criterio que D5.

**Comparación explícita con D5 (predicción del brief §V4):**

| | D5 (sin fill_zones() explícito) | D6 (con fill_zones() explícito, D-26.1) |
|---|---|---|
| hole_clearance | 4 (3× J1 + 1× ANT1) | **0** |
| clearance | 1 (ANT1) | **0** |
| solder_mask_bridge | 1 (ANT1) | **0** |
| Total no-trivial | 6 | **0** |

**Predicción del brief: 0-1 violaciones esperadas. Resultado: 0 — dentro de
la predicción, en el extremo favorable.** Esto **ratifica D-26.1
empíricamente**: las 6 violaciones que D5 registró en su baseline eran
artefacto de fill rancio (zona creada con `add_zone(fill=true)` en Fase 2
de D5, pero sin refill posterior a la colocación de 23 footprints
encima). D6 aplicó `fill_zones()` explícito entre colocación y lectura del
baseline (paso 14 del plan) y las 6 violaciones no aparecieron — ni
siquiera 1, coincidencia geométrica exacta con la predicción "0 esperable"
del brief. Nota: en D6, el plano GND ya se creó con `add_zone(fill=true)`
DESPUÉS de la colocación completa de los 23 footprints (Fase 2 sigue a
Fase 1 en el flujo), a diferencia de D5 donde el plano se creó ANTES de
mover los footprints — esta diferencia de orden por sí sola ya evitaría
fill rancio en D6 incluso sin el `fill_zones()` explícito de Fase 3. La
ratificación de D-26.1 es válida pero con este matiz: el `fill_zones()`
explícito de Fase 3 fue redundante con el fill ya fresco de `add_zone`
recién creado 1 minuto antes. **Ratificación fuerte de D-23.2 (add_zone
persiste bien), ratificación débil-pero-consistente de D-26.1** (no se
pudo aislar el efecto de D-26.1 solo, porque el orden del flujo de D6 ya
evitaba naturalmente el fill rancio). Ver nota en el resumen final,
pregunta 4.

## Fase 4 — Ruteo (corrida 1, desde cero)

- mtime pre-route (`.kicad_pcb`): 1784991785 (2026-07-25 12:03:05 -03).
- `route_board(timeout_s=600)` → **route_ms: 32424.2** (32.4s) — corrió
  síncrono, sin pasar a background (a diferencia de D5, que superó el
  umbral de 120s). Notablemente más rápido que D5 (128.8s), en línea con
  D3 (53s) y D4 (36.7s) — reduce la sospecha de que 128.8s fuera el nuevo
  piso; parece confirmarse no-determinismo real de Freerouting entre
  corridas con distinta colocación/seed, no una tendencia ascendente.
- `nets`: total=44 ruteables=10 ruteadas=10 parciales=[] bloqueadas=[] —
  10/10, igual que D3/D4/D5.
- `drc`: err_preexistentes=56 err_post=**0** err_introducidos=0
  err_resueltos=56 por_tipo={} — **cero errores DRC tras la corrida**, ni
  siquiera el 1 `unconnected_items` que D5 dejó (F-D5-01).
- `tracks_added=203 vias_added=31`. `zones: existentes=5 refilladas=1
  fill_ms=1425.4`.
- mtime post-route: 1784991895 (2026-07-25 12:04:55 -03) — **cambió: sí**.

## V1-1 — Keepouts auto-generados post-route 1

- **Cantidad:** 4 (`get_zones(layer="B.Cu")`: 1 zona copper GND + 4
  keepouts, areas 4.94, 1.79, 1.79, 1.79 mm²).
- **Esperado en placa despertador:** 4 fijos (ANT1 + 3× J1 NPTH).
- **Coincide:** sí — idéntico patrón de áreas a D5 (4.94mm² = ANT1 PTH
  2mm, 3× 1.79mm² = J1 NPTH 0.991mm). Sin proliferación.

## V2-route_board-1 — Cross-check D-23.2, tool=route_board

- **route_board.drc.err_post:** 0 (por_tipo: {})
- **run_drc() independiente:** 0 (total, sin errores)
- **Coinciden total y por_tipo:** sí.
- **mtime pre-route:** 1784991785 · **mtime post-route:** 1784991895 ·
  **cambió:** sí.
- **EXTERNAL_EDIT_DETECTED en lecturas posteriores:** no.

## V3 — Bandera roja obligatoria

Ninguna de las condiciones se activó:
- Sin `clearance=0.0000mm` ni `hole_clearance=0.0000mm` vs Zone GND (0
  errores totales).
- `route_board.drc.err_post` (0) coincide exacto con `run_drc()`
  independiente (0), sin `save_board()` manual de por medio.
- `fill_zones()`/`add_zone(fill=true)` (Fases 2-3) dejaron disco == vivo
  en ambos cross-checks.
- Sin `POST_ROUTE_PERSIST_FAILED` ni `POST_ZONE_PERSIST_FAILED` en ninguna
  invocación hasta ahora.
**V3 NO activada.**

## V4 delta (corrida 1) — vs baseline

- Baseline: 56 `unconnected_items`, 0 de cualquier otro tipo.
- Post-route: 0 errores totales.
- **Delta: -56 unconnected_items (resueltos por el propio ruteo, igual
  que reporta route_board.drc.err_resueltos=56), 0 errores nuevos.**
  Coincide con V2 arriba.

## V5 — Patrón F-D5-01 (isla GND sin vía al plano)

- **¿Apareció el mismo patrón esta corrida?** No. `err_post=0` total —ni
  siquiera queda 1 `unconnected_items` residual (D5 corrida 1 sí dejó 1,
  que resultó ser C2/C3). Acá las 44 nets terminaron con conectividad
  completa en la primera pasada.
- Sin isla GND huérfana visible en el DRC. Se puede revisar con
  `get_tracks(net="GND")` si se quiere confirmar geometría, pero al no
  haber ningún `unconnected_items` no hay indicio del patrón.

## Fase 5 — Acumular 3/3 V2 por tool

- `delete_tracks_bulk(net="/NSS", dry_run=true)` → 8 tracks, 0 vías (C3
  aplicado). Real (`dry_run=false`) → 8 tracks borrados, `zones_refilled:1`,
  `snap_id:31`. mtime del `.kicad_pcb` **no cambió** tras
  `delete_tracks_bulk` (1784991895 sin cambios) — esperable, esta tool no
  forma parte del contrato D-23.2 (fuera de alcance por diseño, solo
  `route_board`/`fill_zones`/`add_zone(fill=true)` lo tienen).
- Re-ruteo con `route_board(timeout_s=600)` para `/NSS`: a diferencia de
  D5 (re-ruteos parciales ~9-10s), esta corrida **superó los 120s** del
  umbral síncrono del harness y pasó a background (task `klfjlsvbv`).
  Observación a vigilar, no fricción de tool todavía — puede ser que
  borrar 1 net de 10 no reduzca tanto el trabajo de Freerouting como
  parecía en D5 (recalcula el ratsnest completo igual). Se retoma cuando
  complete.

## Fase 4bis — Ruteo (corrida 2, re-ruteo parcial /NSS)

- `route_board(timeout_s=600)` completó en background:
  **route_ms: 112325.8** (112.3s) — muy por encima de los re-ruteos
  parciales de D5 (~9-10s), casi tan largo como una corrida completa
  desde cero. Confirma la sospecha: Freerouting no hace un "parche" barato
  al re-rutear 1 net de 10, recalcula con costo cercano al de una corrida
  completa. **Dato a vigilar (no fricción), actualiza el modelo mental de
  "re-ruteo parcial es barato" que D5 había sugerido con solo 2 muestras.**
- `nets`: 10/10 ruteadas, 0 bloqueadas/parciales.
- `drc`: err_preexistentes=1 (el `/NSS` borrado dejó 1 `unconnected_items`,
  esperable) err_post=**0** err_introducidos=0 err_resueltos=1.
  `tracks_added=19 vias_added=0`.
- mtime pre: 1784991895 · post: 1784992129 (**cambió: sí**).

## V1-2 — Keepouts auto-generados post-route 2

- **Cantidad:** 4 (KIIDs nuevos — se regeneran en cada refill — mismas
  áreas: 4.94, 1.79, 1.79, 1.79 mm²). **Coincide:** sí, sin proliferación
  (sigue siendo 4, no 8).

## V2-route_board-2 — Cross-check D-23.2, tool=route_board

- **route_board.drc.err_post:** 0 · **run_drc() independiente:** 0 (total).
- **Coinciden:** sí. **mtime cambió:** sí. **EXTERNAL_EDIT_DETECTED:** no.

## V3 (corrida 2): no activada — sin clearance/hole_clearance, err_post
coincide con run_drc(), sin PERSIST_FAILED.

## V4 delta (corrida 2)

- Pre-corrida: 1 `unconnected_items` (introducido por el
  `delete_tracks_bulk` de /NSS, no por route_board).
- Post-corrida: 0 errores. **Delta: -1 unconnected_items, 0 nuevos.**
  route_board resolvió exactamente lo que el borrado había dejado
  pendiente, sin efectos colaterales.

## Fase 4ter — Ruteo (corrida 3, re-ruteo parcial /SCK, para 3/3 route_board)

- `delete_tracks_bulk(net="/SCK", dry_run=true)` → 13 tracks, 2 vías.
  Real → 13 tracks + 2 vías borrados, `zones_refilled:1`, `snap_id:33`.
- `route_board(timeout_s=600)` → superó 120s de nuevo, background (task
  `kxz6b5sfg`). Confirma el patrón de la corrida 2: re-ruteo parcial de
  esta placa no es barato como en D5.
- Completó: **route_ms: 110051.5** (110.1s, tercer valor consecutivo en el
  rango 110-112s para re-ruteo parcial, muy distinto de los ~9-10s de D5).
  `nets`: 10/10, 0 bloqueadas. `drc`: err_preexistentes=2 (por el borrado
  de /SCK: 13 tracks + 2 vías) err_post=**0** err_introducidos=0
  err_resueltos=2. `tracks_added=15 vias_added=0`.
- mtime post: 1784992336 (12:12:16) — cambió respecto al pre (1784992129).

## V1-3 / V2-route_board-3 / V3 / V4 delta (corrida 3)

- **V1:** 4 keepouts (KIIDs nuevos, mismas áreas 4.94/1.79/1.79/1.79) —
  coincide, sin proliferación.
- **V2:** `err_post`=0, `run_drc()` independiente=0. Coinciden. mtime
  cambió. Sin `EXTERNAL_EDIT_DETECTED`.
- **V3:** no activada (mismos criterios que corridas 1-2).
- **V4 delta:** pre=2 `unconnected_items` (por el borrado), post=0.
  Delta: -2, 0 nuevos.

**route_board alcanza 3/3 V2 coincidentes (corridas 1, 2, 3) — cross-check
discontinuado para esta tool por regla del protocolo.** Ratifica D-23.2 en
`route_board` en dogfooding real de D6 (además de las 5/5 previas
acumuladas en sesiones 24/25).

## Fase 5.5 — Zonas de test para completar 3/3 de add_zone y fill_zones

Zona pequeña de prueba (GND, F.Cu, bbox=[126,61,128,63], 2×2mm, esquina
libre del board — verificada sin conflicto con footprints/tracks
cercanos), creada y borrada 2 veces adicionales para acumular 3/3.

## V2-add_zone-2

- **Tool:** add_zone(net=GND, layer=F.Cu, bbox chico, fill=true).
- **run_drc() independiente:** 0 (total). Sin hole_clearance/clearance
  espurios.
- **mtime:** 1784992336 → 1784992423, cambió: sí.
- **EXTERNAL_EDIT_DETECTED:** no.
- `delete_zone(id=8f55c333…)` → OK, limpieza.

## V2-add_zone-3

- **Tool:** add_zone (misma zona test, re-creada).
- **run_drc() independiente:** 0 (total).
- **mtime:** 1784992423 → 1784992458, cambió: sí.
- **EXTERNAL_EDIT_DETECTED:** no.
- `delete_zone(id=e6967665…)` → OK, limpieza.

**add_zone(fill=true) alcanza 3/3 V2 coincidentes (Fase 2 GND real + 2
zonas de test) — cross-check discontinuado para esta tool.** Primera
ratificación completa de D-23.2 extendido para `add_zone` en dogfooding
real (test aislado de sesión 27 ya daba 2/2 en laboratorio; D6 suma 3/3
en producción).

## V2-fill_zones-2

- **Tool:** fill_zones() explícito, post `delete_zone` (zona test #3
  recién borrada, zona GND real re-consolidada).
- **run_drc() independiente:** 0 (total).
- **mtime:** 1784992458 → 1784992497, cambió: sí. `zones_filled:1`,
  `duration_ms:1399.9`.
- **EXTERNAL_EDIT_DETECTED:** no.

## V2-fill_zones-3

- **Tool:** fill_zones() de nuevo, invocación idempotente (sin cambios
  geométricos previos) — verifica el caso "sin cambios reales pero igual
  persiste" del docstring (D-23.2 incondicional).
- **run_drc() independiente:** 0 (total).
- **mtime:** 1784992497 → 1784992532, cambió: sí (persiste aun siendo
  idempotente, coherente con el diseño incondicional de la sesión 27:
  `enforce_hole_clearance` puede tocar keepouts en el vivo aun con
  `zones_filled==0`... acá `zones_filled` fue 1 en ambas, no 0, pero el
  guardado ocurrió en las dos de todos modos). `duration_ms:1962.7`.
- **EXTERNAL_EDIT_DETECTED:** no.

**fill_zones alcanza 3/3 V2 coincidentes (Fase 3 D-26.1 + 2 llamadas
adicionales, una post-delete_zone y una idempotente) — cross-check
discontinuado para esta tool.** Segunda ratificación completa de D-23.2
extendido para `fill_zones` en dogfooding real, incluyendo el caso
idempotente que el docstring de la tool promete explícitamente.

**Resumen Fase 5 — V2 acumulado, las 3 tools 3/3:**

| Tool | Corridas coincidentes | Divergencias |
|---|---|---|
| `route_board` | 3/3 | 0 |
| `fill_zones` | 3/3 | 0 |
| `add_zone(fill=true)` | 3/3 | 0 |

Combinado con las 5/5 previas de `route_board` (sesiones 24/25) y las 2/2
del test aislado de sesión 27 para `fill_zones`/`add_zone`, el contrato
D-23.2 extendido queda con evidencia consistente en producción real desde
tres ángulos: unit/regresión aislada, dogfooding D5 (`route_board` solo),
y dogfooding D6 (las tres tools). **Cero divergencias en ninguna
corrida.**

## Fase 6 — Cierre

- `export_render(kind="pcb_png")` → OK, render de control, colocación
  visualmente coherente (BT1/U4 cluster izquierdo, resto en franja
  derecha, sin overlaps visibles).
- `export_manufacturing()` → 26 gerbers (Gate G3 pasó — DRC=0 en el
  momento de exportar). Mismo conteo que D5.
- `export_bom()` → `bom.csv`, 1423 bytes (idéntico a D5 — mismos
  componentes, mismo BOM).
- **Fixture actualizado** (D6 salió verde): copiados `.kicad_pcb`,
  `.kicad_pro`, `.kicad_sch`, `.kicad_prl` a
  `tests/fixtures/despertador-routed/` + README reescrito (versión D6,
  sesión 28, commit base `fba66b7`). Solo `.kicad_pcb` cambió respecto al
  fixture de D5 (sch/pro/prl bit-idénticos — ni el esquemático ni la
  configuración de proyecto se tocaron).

---

## F-D6-01 — Re-ruteo parcial de 1 net dejó de ser barato

- **Qué pasó:** en D5, los 2 re-ruteos parciales (`/NSS`, `/SCK` sobre
  1 net a la vez) costaron ~9-10s cada uno — sensiblemente más rápido que
  una corrida completa. En D6, los mismos 2 re-ruteos parciales
  (`/NSS` y `/SCK`, un net a la vez cada uno) costaron **110.1s y 112.3s**
  respectivamente — casi tan caro como una corrida completa desde cero
  (32.4s en esta sesión), y muy por encima de los ~9-10s que D5 sugería
  como "barato".
- **Qué esperaba:** que borrar y re-rutear 1 de 10 nets fuera
  proporcionalmente barato, siguiendo el patrón que D5 estableció con 2
  muestras.
- **Workaround:** ninguno necesario — ambas corridas completaron OK dentro
  del timeout de 600s (solo cruzaron el umbral síncrono de 120s del
  harness y pasaron a background, sin bloquear el resto de la sesión).
  Resultado final correcto en las dos (0 errores DRC).
- **Costo:** bajo (no bloqueó nada, solo alargó la sesión ~4 minutos de
  espera en background).
- **Severidad:** info. No es un defecto del server ni activa V3 — es una
  actualización del modelo mental sobre el costo de Freerouting en
  re-ruteos parciales: **con N=4 muestras históricas (2 de D5 + 2 de D6),
  el costo de un re-ruteo parcial no es predecible como "barato"** —
  parece depender de qué tan interconectado está el net borrado con el
  resto del ratsnest, no solo de su tamaño. Recomendación para D7: no
  asumir que `delete_tracks_bulk` + re-ruteo parcial de 1 net es
  necesariamente más rápido que una corrida completa; medir caso a caso.

---

## Aciertos (D6 vs D5)

1. **Corrida 1 (ruteo completo desde cero) resultó en 0 errores DRC en la
   primera pasada** — a diferencia de D5, que dejó 1 `unconnected_items`
   (F-D5-01) y requirió un `add_via` manual de diagnóstico. D6 no necesitó
   ninguna intervención quirúrgica en ningún momento de la sesión.
2. **`route_ms` de la corrida completa fue 4× más rápido que D5** (32.4s
   vs 128.8s), en línea con D3/D4 — buena señal de que 128.8s no era la
   nueva norma sino variabilidad normal de Freerouting.
3. **D-23.2 extendido ratificado 9/9 sin divergencias en las tres tools**
   (`route_board`, `fill_zones`, `add_zone`) en dogfooding real — cobertura
   mucho más amplia que D5, que solo ejercitó `route_board` con carga
   significativa.
4. **Baseline V4 llegó a 0 violaciones no-triviales** — el extremo más
   favorable de la predicción del brief (0-1), sin ninguna de las 6
   violaciones "fantasma" que D5 tuvo que investigar en sesión 26.
5. **`delete_tracks_bulk(dry_run=true)` (C3) funcionó exactamente como se
   documenta** en las 2 corridas de re-ruteo parcial — conteo de dry_run
   coincidió exacto con el borrado real en ambas.

---

## Resumen final

### 1. ¿Placa completa?

ERC ✓ (0 errores, 4 warnings esperados D-19b.1). Colocado 23/23 (100%,
réplica de D5). Ruteado 10/10 nets (3 corridas, 100% en cada una). DRC:
delta V4 = **0** en las 3 corridas de ruteo (0 introducidos en ninguna).
Gerbers ✓ (26 archivos, Gate G3 limpio). BOM ✓ (1423 bytes). Plano GND ✓
(filled, 1936mm² en B.Cu). Keepouts auto ✓ (4 constantes en las 3
corridas).

### 2. Tabla comparativa D2 vs D3 vs D4 vs D5 vs D6

| Métrica | D2 | D3 | D4 | D5 | D6 |
|---|---|---|---|---|---|
| Nota | 7.5/10 | 8.5/10 | 4.5/10 | 9.5/10 | **9.7/10** |
| Fricciones bloqueantes | 0-1 | 1 externa | 1 P0 interna | 0 | **0** |
| `route_ms` corrida completa | 925s | 53s | 36.7s | 128.8s | **32.4s** |
| Contactos humanos | 5 | 2 | 0 | 0 | **1** (D-27.1, pre-arranque, mandatorio) |
| Errores DRC introducidos post-route | 53 | 0 | 42 obsoletos | 1 (F-D5-01) | **0** |
| Baseline V4 pre-route (violaciones) | N/A | N/A | N/A | 6 (fill rancio) | **0** (D-26.1 aplicado) |
| mtime cambia post-tool D-23.2 | N/A | N/A | N/A | sí (route_board) | **sí (las tres tools, 9/9)** |

### 3. Estado del contrato D-23.2 extendido (sesión 27)

- V2 corridas coincidentes por tool: `route_board` **3/3**, `fill_zones`
  **3/3**, `add_zone` **3/3**.
- **¿Alguna divergencia detectada?** Ninguna, en ninguna de las 9 corridas
  totales (3 por tool).
- **¿Ratifica la extensión sesión 27 en dogfooding real?** Sí, sin
  reservas — es el objetivo primario de D6 y salió limpio. Combinado con
  el 2/2 del test aislado de sesión 27, el contrato D-23.2 extendido tiene
  ahora evidencia en tres capas (unit/regresión, D6 dogfooding real) sin
  ninguna divergencia registrada.

### 4. Estado de D-26.1 (primera aplicación empírica)

- Baseline V4 con `fill_zones()` explícito: **0 violaciones**
  no-triviales (56 `unconnected_items` triviales pre-route, esperados).
- Delta esperado vs D5 (6 violaciones de fill rancio): **0-1 esperable →
  0 observado**, el extremo favorable de la predicción.
- **¿Ratifica D-26.1 empíricamente?** Con un matiz honesto: sí, en el
  sentido de que el flujo con `fill_zones()` explícito dio 0 violaciones
  donde D5 (sin ese paso) dio 6. Pero D6 **no aisló completamente** la
  variable — el plano GND de D6 se creó con `add_zone(fill=true)`
  **después** de la colocación completa de los 23 footprints (orden de
  fases del plan), mientras que D5 creó el plano **antes** de colocar. Ese
  orden por sí solo ya evita el fill rancio, independientemente del
  `fill_zones()` explícito de la Fase 3. La ratificación de D-23.2 (que
  `add_zone(fill=true)` persiste correctamente) es fuerte y directa; la
  ratificación de D-26.1 específicamente es consistente con la predicción
  pero metodológicamente más débil de lo que el brief anticipaba — D7
  debería replicar el orden exacto de D5 (plano ANTES de colocar) y
  *entonces* aplicar/omitir `fill_zones()` explícito para aislar el efecto
  real de D-26.1 sin ese confusor.

### 5. Estado de F-D5-01 (V5)

- **¿Apareció el patrón (isla GND sin vía al plano)?** No, en ninguna de
  las 3 corridas de ruteo. Corrida 1 (completa desde cero) terminó con
  `err_post=0` total — ni siquiera 1 `unconnected_items` residual.
- **Geometría similar a D5:** N/A, no aplica (no apareció).
- **Recomendación:** el trigger definido en D5 era "2 dogfoodings
  independientes" para promover a P2 investigación. Con D6 sin el patrón,
  **el trigger no se cumple** — sigue siendo P3 vigilancia (1 ocurrencia
  en 2 dogfoodings, no 2/2). No promover a P2 todavía.

### 6. Estado de F-D4-02 (contrato D-23.2 en `route_board`)

Sigue ratificado, ahora **8/8** acumulado en producción (2/2 sesión 24 +
3/3 D5 + 3/3 D6), sin ninguna divergencia en ninguna corrida histórica.

### 7. Estado de otras fricciones históricas

- **F-D3-01/F-D3-03:** no aparecieron (esperado, resueltos hace varias
  sesiones).
- **F-D3-04 (`get_footprint_neighbors`):** sigue ahorrando tiempo — 5
  llamadas en Fase 1 (BT1, U4, J1, J2, ANT1) antes de mover, sin sorpresas
  geométricas (coordenadas ya validadas por D5, así que el chequeo fue
  confirmatorio más que exploratorio esta vez).
- **F-D4-01 (R13, `get_world_context(kind="sch")` con `#PWR*/#FLG*`):**
  no ejercitado en D6 (no se leyó el sch vía `get_world_context`, solo
  `run_erc()`). Sigue pendiente P3, sin novedad.

### 8. Fricciones nuevas de D6 (F-D6-XX)

Una sola, severidad `info`: **F-D6-01** (re-ruteo parcial de 1 net dejó de
ser barato — 110-112s en D6 vs 9-10s en D5, actualiza el modelo mental de
costo de Freerouting para re-ruteos parciales). No bloqueante, no afecta
la nota. Propuesta: en D7, medir 2-3 re-ruteos parciales más para
determinar si el costo depende del grado de interconexión del net
borrado con el resto del board (hipótesis de esta sesión) — sin acción de
código, solo protocolo de medición.

### 9. `route_ms` esta placa

Corrida completa: **32.4s** — muy por debajo de D5 (128.8s), en línea con
D3 (53s)/D4 (36.7s). Re-ruteos parciales: **110.1s y 112.3s** — muy por
encima de los ~9-10s de D5. **Modelo mental actualizado:** el techo
~200s (sesión 24: 186.5s/150.2s) sigue vigente para corridas completas,
pero el "piso" de 9-10s para re-ruteos parciales que D5 sugería con 2
muestras **no se sostiene** — con 4 muestras totales (2+2), el rango de
un re-ruteo parcial es tan amplio como el de una corrida completa
(9s-112s). Ver F-D6-01.

### 10. `get_footprint_neighbors` en acción (D-D4.1 inclusivo)

5 llamadas (BT1, U4, J1, J2, ANT1) en Fase 1, todas antes de mover. No
ahorró tiempo de la misma forma que en D5 (donde detectó BT1/U4 fuera del
futuro contorno) porque las coordenadas destino ya eran las validadas de
D5 — funcionó como verificación confirmatoria de higiene de proceso, no
como hallazgo. `courtyards_overlap = 0` en todo el baseline V4 y en el
delta post-route (nunca apareció esa categoría).

### 11. Nota /10 con justificación

**9.7/10.**

- Base 10 menos:
  - **-0.2** por F-D6-01 (variabilidad de costo de re-ruteo parcial,
    severidad info, no bloqueante pero rompe una expectativa operacional
    que D5 había fijado).
  - **-0.1** por el matiz metodológico de la ratificación de D-26.1
    (pregunta 4) — el efecto no quedó completamente aislado del orden de
    fases del flujo, mérito real pero evidencia menos limpia de lo
    anticipado.
- Todo lo demás salió perfecto: 0 errores DRC introducidos en ninguna de
  las 3 corridas de ruteo (mejor que D5, que tuvo 1 a resolver), 9/9 V2
  coincidentes sin divergencias en las tres tools del contrato extendido,
  V3 nunca activada, gerbers/BOM limpios, timebox de ~28 minutos (muy por
  debajo del target de 2h), 1 solo contacto humano (mandatorio por
  D-27.1, no una fricción operacional).
- **D6 sostiene y levemente mejora sobre D5 (9.5→9.7)** — segundo verde
  consecutivo de Fase 3.

### 12. ¿Convergimos hacia el criterio de cierre de Fase 3?

**Verde.** ≥9 ✓, 0 P0/P1 nuevos ✓ (F-D6-01 es info, no P1), V3 no
activada ✓, V2 3/3 por las tres tools ✓, D-26.1 ratificado (con matiz) ✓.
**2 verdes consecutivos (D5=9.5, D6=9.7).** Corresponde considerar D7 para
el 3er verde consecutivo del criterio de cierre de Fase 3, o iniciar
preparación de Fase 4 si el arquitecto lo decide con esta evidencia.

### 13. Evidencia V1/V2/V3/V4/V5 consolidada

- **V1:** 4 keepouts constantes en las 3 corridas de ruteo (ANT1 + 3×
  J1 NPTH). Esperado, sin proliferación.
- **V2 reforzado:** 3/3 por cada una de las 3 tools (9/9 total), 0
  divergencias. Esperado, cumplido.
- **V3:** nunca activada en ninguna de las ~15 operaciones de la sesión.
- **V4 con D-26.1:** baseline en 0 violaciones no-triviales (mejor que el
  0-1 esperable). Ratifica D-26.1, con el matiz de la pregunta 4.
- **V5:** F-D5-01 no apareció. Trigger de promoción a P2 (2/2) no se
  cumple — sigue P3 vigilancia.

### 14. ¿Fixture actualizado a versión D6?

**Sí.** `tests/fixtures/despertador-routed/despertador_inteligente.kicad_pcb`
(único archivo que cambió — sch/pro/prl bit-idénticos a D5) + README
reescrito con procedencia D6, sesión 28, commit base `fba66b7`.

### 15. ¿Qué falta para uso semanal?

Nada crítico en la superficie ejercitada por D6. Pendiente conocido sin
relación con esta sesión: **P1 solder mask bridge ANT1** — investigación
abierta desde sesión 26 (`docs/investigacion/26-solder-mask-ant1.md`), no
tocada en D6 porque no apareció en el baseline ni en ningún delta de esta
sesión (0 `solder_mask_bridge` en las 4 lecturas de DRC de la sesión). No
bloquea uso semanal de las tools ejercitadas (colocación, zonas, ruteo,
DRC, gerbers).

### 16. ¿Recomendación explícita para D7 (sesión 29)?

**D6 verde → D7 = tercer dogfooding de ratificación**, mismo protocolo,
buscando el 3er verde consecutivo del criterio de cierre de Fase 3. Dos
ajustes sugeridos para D7, ninguno bloqueante:

1. **Aislar D-26.1 correctamente** (pregunta 4): crear el plano GND
   ANTES de la colocación masiva (orden de D5), no después, y comparar el
   baseline con/sin `fill_zones()` explícito para atribuir el efecto
   limpiamente a D-26.1 y no al orden de fases.
2. **Medir 2-3 re-ruteos parciales adicionales** (F-D6-01) para
   confirmar o refutar la hipótesis de que el costo depende del grado de
   interconexión del net borrado, no solo de su tamaño — actualiza el
   modelo mental de "costo esperado de route_board" de forma más robusta
   para uso semanal futuro.

Si D7 sale verde con estos dos ajustes, el criterio de cierre de Fase 3
(≥2-3 verdes consecutivos) queda satisfecho y corresponde iniciar
preparación de Fase 4 con el arquitecto.

