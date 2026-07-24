# Dogfooding 5 — Log de fricciones

**Sesión:** 25. **Fecha:** 2026-07-24. **Placa:** despertador ATtiny85 wearable
(misma que D3/D4). **Fase del proyecto:** Fase 3 (consolidación), primer D5.
**Objetivo:** ratificar F-D4-02 / contrato D-23.2 (ADR-0012) en producción.

Formato de fricción:
```
## F-D5-NN — Título corto
- **Qué pasó:** ...
- **Qué esperaba:** ...
- **Workaround:** ...
- **Costo:** [bajo/medio/alto]
- **Severidad:** [info/warn/bloqueante]
```

---

## Fase 1 — Verificación de estado + baseline entorno

- `verificar_entorno.py`: 14 OK · 2 WARN (jar no seteada en shell — sí lo está
  para el server vía `~/.claude.json`; npx/Inspector ausente, no bloquea) · 0 FAIL.
- `health()`: server ok, kicad-cli 10.0.4, IPC ok, pcb_editor_abierto=yes,
  proyecto gui-test-project.
- `run_erc()`: 0 errores, 4 warnings `lib_symbol_mismatch` (U1 ATtiny85-20S, U2
  MPU-6050, U3 MAX30102, U4 RFM69CW) — coincide con D-19b.1 esperado. **F8 NO
  necesario.**
- `get_world_context(kind="pcb")`: `outline:none`, sin ruteo, 23 footprints
  sincronizados, bbox 129.7,66.0 → 154.3,101.2.
  - Nota cosmética: header TOON dice `23c` (23 componentes) vs "24 footprints"
    del protocolo. No es fricción bloqueante — mismo fixture que D3/D4, solo
    discrepancia de conteo en la descripción. Registrado como observación, no
    como F-D5-NN (no afecta el trabajo).

---

## Fase 2/3 — Outline, plano GND, colocación

- `draw_board_outline(x=125,y=60,w=44,h=44)` → OK, 44×44mm (matching D3/D4 controlled
  variable), contiene el bbox de footprints original (129.7,66→154.3,101.2) con margen.
- `add_zone(net=GND, layer=B.Cu, bbox=[125,60,169,104], fill=true)` → OK, filled,
  area_mm2=1936 (board completo, esperado con Freerouting no respetando el plano como
  exclusión — C2).
- Colocación: `get_footprint_neighbors` inclusivo (D-D4.1/C6) en J1, J2, BT1, U4, ANT1
  ANTES de mover reveló que **BT1 y U4 (footprint bbox, no solo "at") se extendían fuera
  del outline** (`edge.dist_mm:0` en ambos, bbox mínimo x=120.0/120.5 < outline x=125).
  Esto confirma que las posiciones "at" heredadas del sch import NO eran una colocación
  D3/D4 lista para usar — era necesario colocar desde cero, como se esperaba. No es
  fricción (el chequeo inclusivo hizo exactamente su trabajo: detectarlo ANTES de rutear).
- Colocación manual calculada (23 footprints) respetando bboxes reales via
  `get_footprint_neighbors(radius_mm≈0.1)` por footprint + verificación de no-overlap
  a mano, priorizando: BT1 (24×21mm, batería) + U4 (18.5×16.5mm, RF) en cluster izquierdo
  con margen ≥2mm de borde; U1/U2/U3/J1/J2/ANT1/pasivos en franja derecha. `save_board()`
  OK tras las 23 `move_footprint`.

## V4 — Baseline DRC pre-route

- **Total errores:** 62
- **por_tipo:** `{"unconnected_items": 56, "hole_clearance": 4, "clearance": 1, "solder_mask_bridge": 1}`
- **Violaciones individuales (hole_clearance/clearance/solder_mask_bridge — las que
  importan por identidad; unconnected_items se omite por ser 56 triviales pre-route,
  se resuelven íntegramente por el propio ruteo):**
  - `hole_clearance|(149.46,64)|J1|error`
  - `hole_clearance|(154.54,62.984)|J1|error`
  - `hole_clearance|(154.54,65.016)|J1|error`
  - `hole_clearance|(165,93)|ANT1|error`
  - `clearance|(165,93)|ANT1|error`
  - `solder_mask_bridge|(165,93)|ANT1|error`
- **Observación:** estas 6 violaciones (3× J1 NPTH + 3× ANT1 PTH, mismo punto) son
  exactamente las que el mecanismo de auto-keepout `__kicadmcp_hc__` de `route_board`
  (V1, `enforce_hole_clearance`) está diseñado para resolver — 4 holes total (J1×3 +
  ANT1×1), coincide con "4 fijos" esperado en V1.
- **Divergencia positiva vs protocolo:** el protocolo esperaba "~5 errores residuales
  (courtyards, edge_clearance del outline, silkscreen)" no relacionados con F-D4-02.
  Esta colocación resultó en **0 courtyards_overlap, 0 edge_clearance, 0 silkscreen**
  en el baseline — la colocación manual con `get_footprint_neighbors` inclusivo evitó
  esas categorías por completo. A confirmar si esto se sostiene tras el ruteo (V4 delta).

## Fase 4 — Ruteo, corrida 1

- mtime pre-route (`.kicad_pcb`): 1784909926 (2026-07-24 13:18:46 -03).
- `route_board(timeout_s=600)` invocado — superó los 120s de umbral síncrono del
  harness (D3=53s, D4=36.7s), se movió a background. Anotado como dato: puede ser
  no-determinismo normal de Freerouting o placa más densa que D3/D4 (mismos 23
  footprints pero distinta colocación geométrica de esta sesión). Se resuelve en el
  Resumen final vs baseline histórico.

## route_board — corrida 1 (resultado crudo)

```
route_ms: 128786.647
nets: total=44 ruteables=10 ruteadas=10 parciales=[] bloqueadas=[]
drc: err_preexistentes=62 err_post=1 err_introducidos=1 err_resueltos=62
     por_tipo={"unconnected_items":1} por_tipo_introducidos={"unconnected_items":1}
tracks_added=221 vias_added=27
zones: existentes=5 refilladas=1 fill_ms=1741.442
```

**route_ms = 128.8s** — notablemente más lento que D3 (53s) y D4 (36.7s), aunque
dentro del timeout (600s) y sin bloquear. Candidato a no-determinismo de Freerouting
(mismos 23 footprints, colocación geométrica distinta a D3/D4). Se compara en el
resumen final; no es señal V3 (no es clearance/hole_clearance/mismatch/persist_failed).

## V1-1 — Keepouts auto-generados post-route 1

- **Cantidad:** 4 (via `get_zones(layer="B.Cu")`: 1 zona copper GND + 4 keepouts,
  areas 4.94, 1.79, 1.79, 1.79 mm²)
- **Esperado en placa despertador:** 4 fijos (ANT1 + 3× J1 NPTH)
- **Coincide:** sí — 4.94mm² es consistente con el hole PTH de 2mm de ANT1, los
  tres de 1.79mm² con los NPTH de 0.991mm de J1. Coincide exactamente con las 4
  violaciones hole_clearance/clearance/solder_mask_bridge del baseline V4 (mismos
  4 puntos: 3× J1 NPTH + 1× ANT1 PTH).
- **Si no:** N/A

## V2-1 — Cross-check D-23.2, corrida 1

- **route_board.drc.err_post:** 1 (por_tipo: {"unconnected_items": 1})
- **run_drc() independiente:** 1 (por_tipo: {"unconnected_items": 1})
- **Coinciden total y por_tipo:** sí
- **mtime pre-route:** 1784909926 (2026-07-24 13:18:46 -03)
- **mtime post-route:** 1784910147 (2026-07-24 13:22:27 -03) (cambió: sí, +221s)
- **Aparece EXTERNAL_EDIT_DETECTED en lecturas posteriores:** no (get_zones y
  run_drc inmediatos post-route respondieron limpio, sin error de esa clase)

## V3-1 — Bandera roja

- **Activada:** NO.
- clearance=0.0000mm vs Zone GND: no aparece post-route (las 6 violaciones del
  baseline contra GND se resolvieron vía los 4 keepouts auto-generados).
- hole_clearance=0.0000mm vs Zone GND: no aparece post-route.
- err_post vs run_drc independiente: coinciden (ver V2-1).
- POST_ROUTE_PERSIST_FAILED: no disparado.

## V4-1 — Delta contra baseline, corrida 1

- **Total pre-route (V4 baseline):** 62 (56 unconnected_items + 4 hole_clearance +
  1 clearance + 1 solder_mask_bridge)
- **Total post-route:** 1 (1 unconnected_items)
- **Delta bruto:** -61
- **Violaciones nuevas (no en baseline por identidad exacta pos+refs):**
  - `unconnected_items|(162.52,66)|C3,Via[GND]|error` — analizar: ¿es genuinamente
    nueva o es una de las 56 unconnected_items del baseline que sobrevivió el
    ruteo? Ver diagnóstico abajo.
- **Violaciones desaparecidas:** las 4× hole_clearance (J1×3, ANT1×1) + 1×
  clearance (ANT1) + 1× solder_mask_bridge (ANT1) — resueltas por los 4 keepouts
  auto-generados (V1-1). Más 55 de las 56 unconnected_items originales, resueltas
  por el ruteo (221 tracks + 27 vías).
- **Violaciones persistentes:** ninguna por identidad exacta (posición cambia
  entre pre/post porque pre-route location era la del pad huérfano genérico, no
  hay tracking de identidad estable entre "no conectado a nada" y "no conectado a
  X específico").

**Diagnóstico de la violación remanente (C3 GND no conectado a Via[GND] en
162.52,66):** RESUELTO. `get_tracks(net=GND, bbox=[159,62,169,72])` mostró que
C2.1 y C3.1 (ambos GND) están unidos entre sí por el track `6b6672bf`
(162.52,66)→(162.52,64), formando una isla GND aislada del plano — a diferencia
de C4 y C6, que sí tienen vía propia hacia el plano B.Cu. No es señal V3 (no es
clearance=0 vs zona, no es mismatch de contrato, no es persist_failed) — es un
hueco de ruteo genuino y acotado: Freerouting conectó el par C2-C3 entre sí pero
no bajó una vía al plano para esa isla.

**Cirugía:** `add_via(x=162.52, y=66, net=GND, size_mm=0.6, drill_mm=0.3)` —
tamaño consistente con las vías existentes en la zona (`d0.600/0.300`).
`save_board()`. `run_drc(min_severity="error")` → **0 errores, 0 warnings.**
`get_zones(layer="B.Cu")` → los 4 keepouts siguen intactos (mismos ids, mismas
áreas) — la cirugía puntual no afectó el mecanismo D-23.2/V1.

**Costo:** bajo (1 diagnóstico con get_tracks + 1 add_via + 1 save + 1 verificación).
Este es exactamente el tipo de "cirugía a ciegas" que Etapa 2 señaló como fricción
#1 histórica — pero acá `get_footprint_neighbors`+`get_tracks` dieron visibilidad
completa de la geometría sin necesidad de adivinar. Candidato a **Acierto**.

## Fase 7 (adelantada) — Test delete_tracks_bulk + re-ruteo, corrida 2

Ejercicio combinado: satisface el punto 28 del protocolo (dry_run primero) Y
genera la 2ª corrida de `route_board` requerida para V2-reforzado 3/3.

- `delete_tracks_bulk(net="/NSS", dry_run=true)` → `{tracks_deleted:7, vias_deleted:2}`
  (coincide exacto con `get_tracks(net="/NSS")`: 7 tracks + 2 vías U1.5↔U4.5).
- `delete_tracks_bulk(net="/NSS", dry_run=false)` → mismo resultado, `zones_refilled:1`.
  `save_board()`.
- mtime pre-route-2: 1784910399 (13:26:39 -03)
- `route_board(timeout_s=600)` → **route_ms=9429.64 (9.4s)** — mucho más rápido que
  corrida 1 (128.8s), esperado (solo 1 net de 10 necesitaba re-ruteo). 10/10 ruteadas,
  0 parciales/bloqueadas, `err_preexistentes=1, err_post=0, err_resueltos=1`.

## V1-2 — Keepouts auto-generados post-route 2

- **Cantidad:** 4 (áreas 4.94, 1.79, 1.79, 1.79 mm² — idénticas a corrida 1; ids
  nuevos porque route_board regenera los keepouts en cada corrida, esperado)
- **Coincide:** sí

## V2-2 — Cross-check D-23.2, corrida 2

- **route_board.drc.err_post:** 0 (por_tipo: {})
- **run_drc() independiente:** 0
- **Coinciden total y por_tipo:** sí
- **mtime pre-route:** 1784910399 (13:26:39 -03)
- **mtime post-route:** 1784910434 (13:27:14 -03) (cambió: sí, +35s)
- **Aparece EXTERNAL_EDIT_DETECTED en lecturas posteriores:** no

## V3-2 — Bandera roja

- **Activada:** NO. 0 errores totales, ninguna condición de V3 aplica.

## V4-2 — Delta

- **Total post-route:** 0. Placa completamente limpia tras la 2ª corrida.

## Fase 7 (adelantada) — Test delete_tracks_bulk + re-ruteo, corrida 3

Mismo patrón que corrida 2, net distinta (/SCK, 3 pines J1-U1-U4, 16 tracks/0 vías) —
completa la 3ª invocación mandatoria de V2-reforzado.

- `delete_tracks_bulk(net="/SCK", dry_run=true)` → `{tracks_deleted:16, vias_deleted:0}`
  (coincide exacto con `get_tracks`). `dry_run=false` → idéntico, `zones_refilled:1`.
  `save_board()`.
- mtime pre-route-3: 1784910525 (13:28:45 -03)
- `route_board(timeout_s=600)` → **route_ms=10025.6 (10.0s)**. 10/10 ruteadas, 0
  parciales/bloqueadas, `err_preexistentes=2, err_post=0, err_resueltos=2`.

## V1-3 — Keepouts auto-generados post-route 3

- **Cantidad:** 4 (áreas 4.94, 1.79, 1.79, 1.79 mm² — idénticas a corridas 1-2)
- **Coincide:** sí — **3/3 corridas, conteo y áreas constantes.**

## V2-3 — Cross-check D-23.2, corrida 3

- **route_board.drc.err_post:** 0. **run_drc() independiente:** 0. **Coinciden:** sí.
- **mtime pre-route:** 1784910525 (13:28:45 -03)
- **mtime post-route:** 1784910561 (13:29:21 -03) (cambió: sí, +36s)
- **Aparece EXTERNAL_EDIT_DETECTED:** no

## V3-3 — Bandera roja

- **Activada:** NO.

## V2 REFORZADO — CONSOLIDADO 3/3

| Corrida | err_post route_board | run_drc independiente | Coinciden | mtime cambió | EXTERNAL_EDIT_DETECTED |
|---|---|---|---|---|---|
| 1 | 1 (unconnected_items) | 1 (unconnected_items) | sí | sí (+221s) | no |
| 2 | 0 | 0 | sí | sí (+35s) | no |
| 3 | 0 | 0 | sí | sí (+36s) | no |

**3/3 limpio.** Contrato D-23.2 (ADR-0012, sesión 24) ratificado en producción:
disco == memoria == `err_post` reportado en las 3 corridas, mtime post-save
siempre posterior al pre-save (evidencia de que `save_board()` interno se
ejecutó), sin ningún `EXTERNAL_EDIT_DETECTED` espurio en 3 ciclos completos de
lectura inmediatamente posteriores al guardado. Cross-check discontinuado a
partir de acá (regla del protocolo: 3/3 limpio → dejar de hacer cross-check).

## Fase 7 punto 27 — Test add_keepout_zone POST-route bajo ANT1 (D-19c.1)

- `add_keepout_zone(layer="B.Cu", polygon=<12 vértices, radio 2.5mm centrado en
  ANT1 165,93>)` → OK, area_mm2=17.888. Se solapa con el keepout auto-generado
  existente (4.94mm²) — KiCad permite keepouts solapados sin conflicto.
- `run_drc(min_severity="error")` → **0 errores, sin cambio.** Confirma D-19c.1:
  agregar keepout POST-route es seguro (a diferencia de pre-route, que bloqueaba
  9/10 nets — sesión 19c, ya no aplica acá porque el ruteo ya existe).
- Removido tras la prueba (`delete_zone`) para no dejar duplicado innecesario en
  el fixture final — el keepout auto-generado ya cubre el hole de ANT1.
  `save_board()` + `run_drc()` → 0 errores, confirmado limpio tras el revert.
- **Costo:** bajo. **Hallazgo:** ninguno (comportamiento esperado, ratifica C1).

## V1 — Keepouts auto-generados post-route

(placeholder legado, ver V1-1/V1-2/V1-3 arriba — se consolida en Resumen final)

## V2 — Cross-check contrato D-23.2

(placeholder legado, ver V2-1 arriba — se consolida en Resumen final)

## V3 — Bandera roja

(placeholder legado, ver V3-1 arriba — se consolida en Resumen final)

## V4 — Baseline DRC + delta

(placeholder legado, ver V4-1 arriba — se consolida en Resumen final)

---

## Fase 6 — Cierre

- Render final (`pcb_png`) inspeccionado visualmente: colocación limpia, sin
  overlaps visibles, keepout de ANT1 visible como anillo de exclusión, sin
  footprints fuera del contorno.
- `export_manufacturing()` → 26 archivos en `/tmp/gui-test-project/fab/`
  (gerbers + drill + job file). Gate G3 pasó sin bloqueo (DRC=0).
- `export_bom()` → `/tmp/gui-test-project/bom.csv`, 1423 bytes.
- Fixture actualizado en `tests/fixtures/despertador-routed/` (`.kicad_pcb`,
  `.kicad_pro` cambiaron; `.kicad_sch`/`.kicad_prl` idénticos — sch no tocado
  esta sesión, consistente con "F8 no necesario"). README reescrito con
  procedencia D5, sesión 25, commit base `100cb3a`, y la ratificación de
  D-23.2 documentada explícitamente (workaround manual del punto 6 marcado
  obsoleto).

---

## Fricciones

### F-D5-01 — Isla GND sin vía al plano tras primer autoroute
- **Qué pasó:** tras la corrida 1 de `route_board`, C2 y C3 (ambos GND) quedaron
  unidos entre sí por un track pero sin vía propia al plano B.Cu — a diferencia
  de C4/C6 en la misma columna, que sí recibieron vía. 1 error DRC
  (`unconnected_items`).
- **Qué esperaba:** que el autorouter asegure que todo pad GND llegue al plano,
  no solo a otro pad GND vecino.
- **Workaround:** diagnóstico con `get_tracks(net=GND, bbox=...)` +
  `get_footprint_neighbors` (visibilidad completa, sin cirugía a ciegas) →
  `add_via` puntual en la posición del pad de C3. 0 errores tras el fix.
- **Costo:** bajo (1 diagnóstico + 1 llamada de fix).
- **Severidad:** info — no bloqueante, no es señal V3, resuelto en la misma
  sesión sin re-ruteo. Posible patrón a vigilar en próximos dogfoodings (¿es
  específico de esta geometría de columna de caps, o un patrón general de
  Freerouting con islas de 2 pads del mismo net?) — no forzado como hallazgo
  mayor porque una sola ocurrencia no es evidencia suficiente.

---

## Aciertos

1. **`get_footprint_neighbors` inclusivo detectó un problema de colocación
   ANTES de rutear:** el chequeo en BT1/U4 (D-D4.1, aplicado con criterio
   amplio, no solo a conectores) reveló que sus bboxes reales excedían el
   contorno — invisible si solo se mira la posición "at" del footprint. Evitó
   arrancar el ruteo con footprints fuera de placa.
2. **Contrato D-23.2 sostuvo 3/3 sin excepción:** `err_post` de `route_board`
   coincidió exacto (total y por_tipo) con `run_drc()` independiente en las 3
   corridas, mtime cambió las 3 veces, cero `EXTERNAL_EDIT_DETECTED` espurio.
   Reemplaza por completo el workaround manual de refill que D3 necesitaba
   (F-03, sesión 20) — ver README del fixture actualizado.
3. **`get_tracks(net=..., bbox=...)` dio visibilidad total para diagnosticar
   F-D5-01 sin adivinar:** contraste directo con la fricción histórica #1 de
   Etapa 2 ("cobre invisible por tools — cirugía a ciegas"). El diagnóstico
   completo (identificar la isla GND, confirmar ausencia de vía) tomó 1
   llamada.
4. **`delete_tracks_bulk(dry_run=True)` + re-ruteo parcial funcionó limpio**
   en 2 nets distintas (/NSS, /SCK): conteos de dry_run coincidieron exacto
   con el borrado real, y `route_board` re-ruteó solo lo necesario (9-10s vs
   128.8s de la corrida completa) sin afectar el resto del cobre ya bueno.
5. **`add_keepout_zone` POST-route confirmado inocuo (D-19c.1):** agregar un
   keepout redundante sobre ANT1 después de rutear no generó ningún error
   DRC nuevo, y se pudo remover limpiamente con `delete_zone`.

---

## Resumen final

### 1. ¿Placa completa?
- ERC: ✓ (0 errores, 4 warnings esperados)
- Colocado: ✓ 23/23 footprints, 0 courtyards_overlap, 0 edge_clearance (baseline V4)
- Ruteado: ✓ 10/10 nets ruteables, 0 parciales/bloqueadas (3/3 corridas)
- DRC: ✓ 0 errores, 0 warnings (final)
- Gerbers: ✓ (26 archivos, gate G3 pasó limpio)
- Plano GND: ✓ filled, 1936mm²
- Keepouts auto: ✓ 4/4 constante en 3 corridas

### 2. Tabla comparativa D2/D3/D4/D5

| Métrica | D2 | D3 | D4 | D5 |
|---|---|---|---|---|
| Nota | 7.5/10 | 8.5/10 | 4.5/10 | **9.5/10** |
| Fricciones bloqueantes | 0-1 | 1 externa | 1 P0 interna | **0** |
| `route_ms` (corrida completa) | 925s | 53s | 36.7s | **128.8s** |
| Contactos humanos | 5 | 2 | 0 | **0** |
| Errores DRC "introducidos" post-route (delta V4) | N/A | 0 | 42 (obsoletos) | **1 (resuelto misma sesión)** |
| mtime cambia post-route | N/A | N/A | N/A | **sí, 3/3** |
| `EXTERNAL_EDIT_DETECTED` espurio | N/A | N/A | N/A | **no, 0/3** |

### 3. Estado de F-D4-02 (el gran cierre)
- V2 reforzado: **3/3 limpio.** Contrato D-23.2 aguantó en producción sin
  ninguna divergencia.
- mtime cambió en las 3 corridas (+221s, +35s, +36s — todas positivas y
  consistentes con el tiempo real de ruteo+save+fill).
- `EXTERNAL_EDIT_DETECTED` espurio: no apareció ninguna vez, en ninguna
  lectura posterior a un `route_board` o `save_board`.
- Evidencia de regresión respecto al test de sesión 24: **ninguna.** El
  workaround manual de refill (`delete_zone`+`add_zone`) que el fixture de D3
  documentaba como obligatorio (F-03) ya NO fue necesario ni una vez.

### 4. Estado de otras fricciones históricas
- F-D3-01/F-D4-02: cubierto en punto 3 — cerrado y ratificado.
- F-D3-03: no apareció (revocada por sesión 24, consistente con lo esperado).
- F-D3-04 (`get_footprint_neighbors` ahorra tiempo): **sí, confirmado y
  reforzado** — esta sesión detectó un problema real de colocación (BT1/U4
  fuera del contorno) antes de invertir tiempo en ruteo. Ver Acierto #1.
- F-D4-01 (R13, `get_world_context(kind="sch")` con `#PWR*/#FLG*`): **no
  ejercitado esta sesión** (no hubo necesidad de tocar el esquemático — F8 no
  fue necesario). Sigue pendiente, sin novedad.

### 5. V4 baseline dinámico
- Baseline pre-route: 62 errores, pero **0 courtyards_overlap, 0
  edge_clearance, 0 silkscreen** — las 3 categorías residuales que el
  protocolo esperaba (~5 errores) no aparecieron en absoluto. Los 62 eran
  56 `unconnected_items` (triviales, board sin copper) + 6 `hole_clearance/
  clearance/solder_mask_bridge` contra la zona GND en J1(×3)/ANT1(×1) —
  exactamente lo que el mecanismo de auto-keepout de `route_board` resuelve
  por diseño.
- Post-route (3 corridas): 1→0→0 errores. No hay conjunto de residuales
  estables por identidad porque no hubo residuales — la placa convergió a 0.
- **Allowlist candidata textual: NO aplica esta sesión** — no hay
  violaciones residuales que ameriten allowlist. Esto es una divergencia
  positiva respecto a D3/D4 (que sí tenían courtyards/edge/silkscreen
  residuales); posiblemente atribuible a la colocación más generosa en
  margen de esta sesión (usé ≥1.5-2mm de margen sistemáticamente) más que a
  una mejora del server. No generalizar sin más datos.

### 6. Fricciones nuevas de D5
Una sola, F-D5-01 (ver arriba), severidad `info`, costo bajo, resuelta en la
misma sesión. Propuesta: vigilar en D6/D7 si el patrón "isla de 2 pads GND
sin vía al plano" se repite; si aparece de nuevo, investigar si es
específico de Freerouting con columnas de decoupling caps muy juntos.

### 7. `route_ms` esta placa
Corrida 1 (completa, 10/10 nets desde cero): **128.8s** — notablemente más
lento que D3 (53s) y D4 (36.7s), pese al mismo count de nets ruteables (10).
No hay señal de causa (no fue timeout, no hubo bloqueadas/parciales, DRC
resultante fue mejor que D3/D4). Se atribuye a no-determinismo de
Freerouting + colocación geométrica distinta (distancias de ruteo distintas
a las de D3/D4). Corridas 2-3 (re-ruteo parcial de 1 net): 9.4s y 10.0s,
coherente con el patrón esperado (mucho más rápido cuando solo 1 de 10 nets
necesita trabajo).

### 8. `get_footprint_neighbors` en acción
Usado 5 veces con `radius_mm=3` (J1, J2, BT1, U4, ANT1 — D-D4.1 inclusivo) +
7 veces con `radius_mm=0.1` para extraer bboxes exactos sin gastar tokens en
vecinos (U1, U2, U3, D1, C1, R1, TP1, más C3 en el diagnóstico de F-D5-01) =
12 llamadas totales. Ahorró tiempo de forma directa: detectó BT1/U4 fuera del
contorno ANTES de mover nada más, evitando descubrir el problema recién en
el baseline DRC o peor, después de rutear. **0 `courtyards_overlap`**
apareció en ningún momento de la sesión — ni en el baseline ni post-route.

### 9. Nota /10: **9.5/10**
- **-0** placa completa, DRC final 0/0, gerbers+BOM limpios, fixture
  actualizado.
- **-0** V1/V2/V3/V4 completas y consistentes; V2 reforzado 3/3 sin ninguna
  divergencia — el objetivo primario de la sesión (ratificar D-23.2) se
  cumplió sin matices.
- **-0.25** un hallazgo real (F-D5-01) apareció en la primera corrida —
  aunque de severidad `info`/bajo costo y resuelto con total visibilidad
  (sin cirugía a ciegas), no fue una placa "perfecta a la primera".
- **-0.25** `route_ms` de la corrida completa (128.8s) sin explicación clara
  frente al histórico D3/D4 — no afecta el resultado pero es una variable no
  controlada que vale la pena seguir observando en D6/D7.
- No hay deducción por V3 (nunca se activó) ni por contactos humanos (0).

### 10. ¿Convergimos hacia el próximo paso de Fase 3?
**Verde.** Nota 9.5 ≥ 9, 0 P0/P1 nuevos (F-D5-01 es `info`), V3 no activada,
V2 reforzado 3/3. Convergencia parcial confirmada — corresponde avanzar a
sesión 26 (fix P1 solder mask ANT1, si sigue vigente ese pendiente) y luego
sesión 27 (generalización D-23.2 a `fill_zones`/`add_zone(fill=True)`).

### 11. Evidencia V1/V2/V3/V4 consolidada
- V1: 4/4 keepouts constantes en las 3 corridas (áreas 4.94, 1.79, 1.79,
  1.79 mm² idénticas, ids nuevos cada vez — regeneración esperada).
- V2 reforzado: 3/3 limpio (ver tabla en la sección V2 REFORZADO —
  CONSOLIDADO 3/3 más arriba).
- V3: no activada, ninguna corrida.
- V4: residuales NO estables por identidad porque no hubo residuales
  persistentes — convergencia a 0 en la corrida 1 (tras 1 fix puntual) y se
  mantuvo en 0 en corridas 2-3.

### 12. ¿Ratifica el patrón D-23.2 para generalización a `fill_zones`/`add_zone(fill=True)`?
**Sí.** 3/3 corridas de `route_board` (que internamente usa el mismo
mecanismo de refill+persistencia) confirmaron el contrato sin excepción. Con
esta tercera ratificación consecutiva (test de regresión de sesión 24 +
D5), la generalización a `fill_zones` y `add_zone(fill=True)` (backlog P2,
sesión 27) tiene base sólida para proceder.

### 13. ¿Actualizado el fixture?
**Sí.** `tests/fixtures/despertador-routed/` actualizado con los 4 archivos
(`.kicad_pcb`, `.kicad_pro` cambiaron; `.kicad_sch`/`.kicad_prl` idénticos a
D3 porque el sch no se tocó). README reescrito con procedencia D5, sesión
25, commit base `100cb3a`, y sección explícita de ratificación de D-23.2
que marca obsoleto el workaround manual de refill documentado en D3.

### 14. ¿Qué falta para uso semanal?
Nada crítico. Los pendientes son de secuencia de Fase 3: (a) fix P1 solder
mask ANT1 si sigue vigente (sesión 26), (b) generalización D-23.2 a
`fill_zones`/`add_zone(fill=True)` (sesión 27, con base sólida ahora), (c)
vigilar si F-D5-01 (isla GND sin vía) es un patrón recurrente o un evento
aislado. Ninguno de los tres es bloqueante para el flujo schematic→gerbers
completo, que funcionó de punta a punta sin contacto humano.
