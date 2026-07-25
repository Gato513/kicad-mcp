# Dogfooding 7 — Log de fricciones

Sesión 29, 2026-07-25. Tercera ratificación de Fase 3. Ver plan aprobado en
`/home/astra/.claude/plans/dogfooding-7-async-riddle.md`.

Formato de fricción:

```
## F-D7-NN — Título corto
- **Qué pasó:** ...
- **Qué esperaba:** ...
- **Workaround:** ...
- **Costo:** [bajo/medio/alto]
- **Severidad:** [info/warn/bloqueante]
```

---

## Fase 0 — Verificación de entorno

`verificar_entorno.py`: 14 OK, 2 WARN (0 FAIL). WARN "Autorouting: jar" es
del shell del script, no del proceso servidor MCP (que ya tiene
`KICAD_MCP_FREEROUTING_JAR` seteada vía `~/.claude.json`, confirmado antes de
empezar). WARN "npx" no aplica a esta sesión (no se usa el Inspector). No
bloqueante, ambos anotados.

## Fase 1 — Restore D-27.1 + verificación de estado

- **Estado previo del proyecto vivo:** DRIFT confirmado antes de arrancar —
  `/tmp/gui-test-project` tenía el board ruteado completo de D6 (216
  segments, 29 vías, plano GND + 4 keepouts, outline Edge.Cuts 125,60→169,104).
  `draw_board_outline` lo hubiera rechazado.
- **Restore autorizado por el arquitecto (AskUserQuestion, antes de tocar
  nada):** backup no destructivo de los 4 archivos vivos a
  `.../scratchpad/d7-live-backup/`, sobrescritura en el mismo path desde
  `/home/astra/Documents/gui-test-project-pre-D3/` (sin `rm -rf`),
  `reload_board_from_disk()` sin reiniciar la GUI. `.kicad_prl` no requirió
  overwrite (sin drift).
- `reload_board_from_disk()` → `{"reloaded":true,"snap_id":1,"tracks":0,"vias":0}` — limpio.
- `run_erc()`: **0 errores, 4 warnings** `lib_symbol_mismatch` (U1, U2, U3,
  U4) — coincide exacto con D-19b.1 esperado. **F8 NO necesario.**
- `get_world_context(kind="pcb")`: `outline:none`, 23 componentes, sin
  ruteo, bbox `129.7,66.0;154.3,101.2` (coords heredadas del sch import,
  igual patrón que D5/D6 pre-colocación). sch md5 `fe63dbc1…` idéntico al
  fixture y a la fuente pre-D3.
- `get_zones(layer="B.Cu")` → 0 zonas.
- **Restore limpio, 0 fricciones.**

## Fase 2 — Contorno y plano GND (ANTES de colocar, D-28.1)

- `draw_board_outline(x_mm=125, y_mm=60, width_mm=44, height_mm=44)` → OK,
  44×44mm, `snap:3`, misma variable controlada que D3-D6.
- `add_zone(net="GND", layer="B.Cu", bbox=[125,60,169,104], fill=true)` →
  OK, filled, `area_mm2=1936` (board completo, esperado — Freerouting no
  respeta el plano como exclusión, C2/D-19.1; el refill+enforce post-route
  lo arregla).

## V2-add_zone-1 — Cross-check D-23.2, tool=add_zone

- **Tool invocada:** `add_zone(fill=true)`.
- **Estado interno reportado:** sin campo `drc` (por diseño); `filled:true`,
  `area_mm2:1936`.
- **run_drc() independiente (min_severity=error):** total 57 —
  `unconnected_items:56` (trivial, pre-route, esperable) +
  `copper_edge_clearance:1` (BT1 pad GND vs borde del outline, en su
  posición heredada del sch-import 131.9,75.0 — **antes de la colocación
  D7**, se resuelve en Fase 3 cuando BT1 se mueve a 139.5,70.0). 0
  `hole_clearance`/`clearance`/`solder_mask_bridge` contra la zona GND.
- **Coinciden / sin hole_clearance ni clearance espurio vs Zone GND:** sí.
- **mtime pre-op:** 1785002280 (14:58:00) · **mtime post-op:** 1785002362
  (14:59:22) · **cambió:** sí (+82s).
- **EXTERNAL_EDIT_DETECTED en lecturas posteriores:** no (confirmado en
  las lecturas de Fase 2, a re-confirmar en Fase 3).

## Fase 3 — Colocación con coordenadas propias (V6)

- `get_footprint_neighbors(radius_mm=3)` inclusivo (D-D4.1/C6) sobre BT1,
  U4, J1, J2, ANT1 en sus posiciones heredadas (pre-move): BT1 y U4
  `closest_edge:left, dist_mm:0` — mismo patrón que D5 (footprints densos
  fuera/al borde del futuro outline en posición heredada, esperable, se
  resuelve con el move). J1/J2/ANT1 `edge:null`. Sin sorpresas.
- 23× `move_footprint` con las coordenadas de la tabla V6 (clusters
  funcionales, anti-diagonal) → **23/23 OK**. `save_board()` OK.
- **Verificación read-only de colisiones** (script sobre el `.kicad_pcb`
  guardado, courtyards F.CrtYd/B.CrtYd bbox-level): **0 solapes** entre los
  23 footprints. Los 23 dentro del outline 125,60→169,104. `ANT1` a 15.0mm
  del borde más cercano, `J1` a 7.5mm — ambos muy por encima del mínimo
  1.5-2mm de D-D3.1.

## Fase 3.5 — Experimento aislado D-26.1 (el corazón de D7)

## V4.a — Baseline DRC SIN fill_zones() explícito

- **Total errores:** 62
- **por_tipo:** `{"unconnected_items": 56, "hole_clearance": 4, "clearance": 1, "solder_mask_bridge": 1}`
- **Violaciones individuales (hole_clearance/clearance/solder_mask_bridge):**
  ```
  hole_clearance|155.46,71.5|NPTH J1 vs Zone[GND] B.Cu|error
  hole_clearance|160.54,70.484|NPTH J1 vs Zone[GND] B.Cu|error
  hole_clearance|160.54,72.516|NPTH J1 vs Zone[GND] B.Cu|error
  hole_clearance|144.5,89|PTH ANT1(Net-(ANT1-A)) vs Zone[GND] B.Cu|error
  clearance|144.5,89|PTH ANT1(Net-(ANT1-A)) vs Zone[GND] B.Cu|error
  solder_mask_bridge|144.5,89|PTH ANT1(Net-(ANT1-A)) vs Zone[GND] B.Cu|error
  ```
- **Total no-trivial: 6** — **coincide EXACTO con el patrón de D5** (4
  hole_clearance: 3× J1 NPTH + 1× ANT1; 1 clearance ANT1; 1
  solder_mask_bridge ANT1). Con el orden de fases correcto (plano ANTES de
  colocar, D-28.1/D5), D7 reproduce limpiamente el fill rancio que D6 no
  pudo aislar. Predicción del brief (4-6): cumplida en el extremo superior.

## V2-fill_zones-1 — Cross-check D-23.2, tool=fill_zones

- **Tool invocada:** `fill_zones()` explícito — aplicación de D-26.1 (C7).
- **Estado interno reportado:** `zones_filled:1`, `duration_ms:3173.8`.
- **mtime pre-op:** 1785002509 · **mtime post-op:** 1785002619 · **cambió:**
  sí (+110s).
- **run_drc() independiente:** ver V4.b abajo — 0 no-trivial.
- **EXTERNAL_EDIT_DETECTED:** no.

## V4.b — Baseline DRC CON fill_zones() explícito (D-26.1 aplicado)

- **Total errores:** 56
- **por_tipo:** `{"unconnected_items": 56}`
- **Violaciones individuales:** NINGUNA (0 hole_clearance/clearance/solder_mask_bridge).
- **Delta contra V4.a:** 6 → 0 (todas las 6 violaciones no-triviales
  desaparecieron).
- **Violaciones eliminadas:** las 6 de V4.a (3× `hole_clearance` J1 NPTH,
  1× `hole_clearance` ANT1, 1× `clearance` ANT1, 1× `solder_mask_bridge`
  ANT1).

**Ratificación empírica de D-26.1 en D7, SIN confusor de orden de fases**
(a diferencia de D6): con el plano GND creado ANTES de la colocación
(orden D5/D-28.1, replicado exactamente), la colocación de 23 footprints
encima del plano ya filleado SÍ generó fill rancio (V4.a=6, idéntico al
patrón de D5), y `fill_zones()` explícito lo eliminó por completo
(V4.b=0). El delta V4.a→V4.b es evidencia directa y limpia: D-26.1 es
necesario en este flujo (orden plano-antes-de-colocar), no redundante como
sugería D6. **V4.b es el baseline canónico** para todos los deltas
posteriores de la sesión.

## Fase 4 — Ruteo (corrida 1, desde cero)

- mtime pre-route: 1785002619 (15:03:39).
- `route_board(timeout_s=600)` → **route_ms: 40638.2** (40.6s), corrió
  síncrono. `nets`: 10/10 ruteables ruteadas, 0 bloqueadas/parciales.
  `tracks_added=230 vias_added=22`. `drc.err_preexistentes=56
  err_post=0 err_introducidos=0 err_resueltos=56`.
- mtime post-route: 1785002744 (15:05:44) — **cambió: sí** (+125s).

## V1-1 — Keepouts auto-generados post-route 1

- **Cantidad:** 4 (`__kicadmcp_hc__*`, áreas 4.94/1.79/1.79/1.79 mm²) —
  **coincide** con el patrón esperado (ANT1 + 3× J1 NPTH).

## V2-route_board-1 — Cross-check D-23.2, tool=route_board

- **route_board.drc.err_post:** 0 · **run_drc() independiente:** 0
  (total). **Coinciden:** sí. **mtime cambió:** sí. **EXTERNAL_EDIT_DETECTED:** no.

## V3 (corrida 1): no activada

Sin `clearance`/`hole_clearance`/`solder_mask_bridge`/mismatch, `err_post`
coincide con `run_drc()`, sin `POST_ROUTE_PERSIST_FAILED`.

## V4 delta (corrida 1) — vs baseline V4.b

- Pre-corrida (V4.b): 56 `unconnected_items` (triviales).
- Post-corrida: 0 errores. **Delta: -56, 0 nuevos.** route_board resolvió
  íntegramente el baseline, sin efectos colaterales.

## V5 — Patrón F-D5-01 (isla GND sin vía al plano)

`err_post=0` total, sin `unconnected_items` residual — el patrón **NO
apareció** en la corrida 1 (a diferencia de D5, igual que D6).

## Fase 5.5 — Protocolo F-D6-01 (V7): 3 mediciones de re-ruteo parcial

Nets elegidos por grado de interconexión: `+3V3` (alto, 16 refs/18 pads),
`/SDA` (medio, 6 refs/6 pads), `/NSS` (bajo, 2 refs/2 pads — **mismo net
medido en D5 y D6**, para comparación directa).

### Medición 1 — `+3V3` (alto)

- `delete_tracks_bulk(net="+3V3", dry_run=true)` → 65 tracks, 0 vías.
  Real → 65/0 borrados, coincide exacto con el dry_run (C3). mtime **no
  cambió** tras el borrado (1785002744, mismo patrón que D6: fuera del
  contrato D-23.2).
- `route_board(timeout_s=600)` → **route_ms: 23692.3** (23.7s), corrió
  síncrono. `nets`: 10/10, 0 bloqueadas. `drc`: err_preexistentes=17
  err_post=**0** err_introducidos=0 err_resueltos=17. `tracks_added=63
  vias_added=0` (2 menos que los 65 borrados — reoptimización de
  topología, no residual).
- **V1:** 4 keepouts (KIIDs nuevos, mismas áreas). **V2:** err_post=0,
  run_drc()=0, coinciden, mtime cambió (→1785002920), sin espurio. **V3:**
  no activada. **V4 delta:** pre=17, post=0, delta=-17, 0 nuevos.

### Medición 2 — `/SDA` (medio)

- `delete_tracks_bulk(net="/SDA", dry_run=true)` → 29 tracks, 0 vías.
  Real → 29/0, coincide exacto.
- `route_board(timeout_s=600)` → **route_ms: 24407.8** (24.4s), síncrono.
  `nets`: 10/10, 0 bloqueadas. `drc`: err_preexistentes=5 err_post=**0**
  err_introducidos=0 err_resueltos=5. `tracks_added=34 vias_added=0`.
- **V1:** 4 keepouts (KIIDs nuevos, mismas áreas). **V2:** err_post=0,
  run_drc()=0, coinciden, mtime cambió (→1785003049), sin espurio. **V3:**
  no activada. **V4 delta:** pre=5, post=0, delta=-5, 0 nuevos.

### Medición 3 — `/NSS` (bajo — mismo net que D5/D6)

- `delete_tracks_bulk(net="/NSS", dry_run=true)` → 7 tracks, 0 vías. Real
  → 7/0, coincide exacto.
- `route_board(timeout_s=600)` → **route_ms: 17708.6** (17.7s), síncrono.
  `nets`: 10/10, 0 bloqueadas. `drc`: err_preexistentes=1 err_post=**0**
  err_introducidos=0 err_resueltos=1. `tracks_added=8 vias_added=0`.
- **V1:** 4 keepouts. **V2:** err_post=0, run_drc()=0, coinciden, mtime
  cambió (→1785003177), sin espurio. **V3:** no activada. **V4 delta:**
  pre=1, post=0, delta=-1, 0 nuevos.

### Tabla V7

| Net | Grado | Tracks borrados | Vías borradas | route_ms | Errores post |
|---|---|---|---|---|---|
| `+3V3` | alto | 65 | 0 | 23692.3 (23.7s) | 0 |
| `/SDA` | medio | 29 | 0 | 24407.8 (24.4s) | 0 |
| `/NSS` | bajo | 7 | 0 | 17708.6 (17.7s) | 0 |

**Análisis con N=7 total** (2 D5 ~9-10s + 2 D6 110-112s + 3 D7
17.7-24.4s, todos con `err_post=0`):

- Ninguna de las 3 mediciones de D7 se acerca al piso de D5 (~9-10s) ni al
  techo de D6 (110-112s) — caen en una banda intermedia (17.7-24.4s), más
  cerca de una corrida completa "barata" (D7 corrida 1 completa: 40.6s)
  que de un "parche" barato.
- **Dentro de D7, el costo NO escala con el grado de interconexión**: el
  net de mayor interconexión (`+3V3`, 65 tracks) costó 23.7s, muy similar
  al de interconexión media (`/SDA`, 29 tracks, 24.4s) y no muy por
  encima del de baja interconexión (`/NSS`, 7 tracks, 17.7s) — la
  diferencia entre los tres es de solo ~7s pese a que el net más grande
  tiene 9× más tracks que el más chico.
- **Comparación directa sobre el mismo net (`/NSS`) entre sesiones:** D5
  ~9-10s, D6 110-112s, D7 17.7s — tres corridas, tres órdenes de magnitud
  de varianza distintos sobre el **mismo net, mismo tamaño de placa**.
  Esto apunta más a variabilidad del proceso Freerouting/JVM en sí (carga
  de la corrida completa anterior en la misma sesión, estado interno del
  motor, warm-up de la JVM) que a una propiedad determinística del net
  borrado.
- **Recomendación:** con N=7 y sin correlación clara con interconexión,
  tamaño o capas (todo B.Cu/F.Cu, sin diferencias de capa en esta placa),
  **cerrar F-D6-01 como variabilidad inherente de Freerouting/JVM en
  re-ruteos parciales**, documentar el rango observado (9s-112s) como
  esperable en `docs/CONTEXT.md` o `docs/specs/restricciones-kicad.md`, y
  dejar de tratarlo como vigilancia activa — ningún caso superó el
  timeout de 600s ni bloqueó nets, y los 3 valores de D7 están muy por
  debajo del umbral de 60s que activaría el trigger de promoción a P2.

## Fase 5.7 — Completar V2 3/3 por tool (add_zone, fill_zones)

`route_board` ya llegó a 4/4 naturalmente (Fase 4 + las 3 mediciones V7).
Faltaban 2 corridas cada una para `add_zone`/`fill_zones` (tenían 1/3 de
la Fase 3.5). Zona de test GND en F.Cu, `bbox=[126,78.5,128,80.5]`
(2×2mm) — verificada read-only sin colisión de copper/courtyard antes de
crearla (hueco libre entre BT1 y U2 en el layout D7).

- **V2-add_zone-2:** `add_zone(fill=true)` → OK, `area_mm2=4`. mtime
  cambió (→1785003287). `run_drc()`=0. Coinciden, sin espurio.
- **V2-fill_zones-2:** `fill_zones()` → OK, `zones_filled=2`. mtime
  cambió (→1785003325). `run_drc()`=0. Coinciden, sin espurio.
- `delete_zone` (zona de test) → OK.
- **V2-add_zone-3:** `add_zone(fill=true)` (recreada) → OK, `area_mm2=4`.
  mtime cambió (→1785003374). `run_drc()`=0. Coinciden, sin espurio.
- **V2-fill_zones-3:** `fill_zones()` → OK, `zones_filled=2`. mtime
  cambió (→1785003401). `run_drc()`=0. Coinciden, sin espurio.
- `delete_zone` final (zona de test) → OK. `run_drc()`=0. `get_zones`
  confirma estado canónico: 1 plano GND + 4 keepouts, sin la zona de
  test.

**add_zone alcanza 3/3 V2 coincidentes (corridas 1, 2, 3) — ratifica
D-23.2. fill_zones alcanza 3/3 V2 coincidentes (corridas 1, 2, 3) —
ratifica D-23.2.** route_board ya estaba en 4/4. **Las tres tools cierran
D7 con 0 divergencias.**

## Fase 6 — Cierre

- Render final (`pcb.png`, 77015 bytes) — layout confirmado visualmente:
  BT1 banda superior, cluster potencia (C1/D1/TP1/TP2) arriba-derecha,
  J1+U1 banda media, U4 RF + ANT1 (2mm) abajo-derecha, cluster I2C
  (U2/U3/C5/C6/R1/R2/J2) cuadrante izquierdo — coincide con el plan V6.
- `export_manufacturing()` → **gate G3 pasó limpio**, 26 archivos (gerbers
  completos + drill + job file) en `fab/`.
- `export_bom()` → OK, `bom.csv` 1423 bytes.
- **Fixture actualizado a versión D7** (D7 salió verde, sin dudas sobre
  impacto en tests — verificado antes de tocar nada: ningún test hardcodea
  coordenadas, todos derivan bbox/zonas en runtime, D-24.1). Copiados los
  4 archivos a `tests/fixtures/despertador-routed/`, README reescrito con
  el detalle de sesión 29. `git diff --stat`: solo
  `despertador_inteligente.kicad_pcb` (2321 líneas, ruteo+colocación
  nuevos) y `README.md` — `.kicad_pro`/`.kicad_sch`/`.kicad_prl` sin
  cambios (idénticos a D6, como se esperaba).

## Aciertos (D7 vs D5/D6)

1. **Aislamiento limpio de D-26.1 por primera vez en producción real** —
   D7 replicó el orden exacto de fases de D5 (plano antes de colocar) y
   obtuvo el mismo patrón de 6 violaciones fantasma que D5, luego 0 tras
   `fill_zones()` explícito — sin el confusor de orden que dejó a D6 con
   una ratificación "débil-pero-consistente". La pregunta que D6 dejó
   abierta queda cerrada: D-26.1 es necesario, no redundante, en el flujo
   canónico.
2. **Variación geométrica controlada exitosa (V6)** — layout
   completamente nuevo (clusters en anti-diagonal, ANT1 a 2mm de U4 en vez
   de 28mm, I2C como net diagonal largo) ruteado 10/10 sin nets
   bloqueados ni parciales, en la primera pasada. La evidencia de D-23.2
   ya no depende de un único layout repetido tres veces.
3. **Protocolo F-D6-01 cerrado con conclusión, no dejado abierto** — 3
   mediciones adicionales (N=7 total) permitieron concluir "variabilidad
   inherente de Freerouting/JVM, sin correlación con interconexión" en
   vez de seguir acumulando vigilancia indefinida.
4. **route_board alcanzó 4/4 V2 sin ninguna corrida fuera del umbral
   síncrono de 120s** (40.6s / 23.7s / 24.4s / 17.7s) — a diferencia de
   D6, donde 2 de 3 re-ruteos parciales pasaron a background por superar
   120s. Sesión más fluida operacionalmente.
5. **Cero fricciones de cualquier severidad** — ninguna entrada F-D7-XX
   fue necesaria. Restore D-27.1, `get_footprint_neighbors`,
   `move_footprint`×23, `delete_tracks_bulk` dry_run→real, `add_zone`,
   `fill_zones`, `delete_zone`, `route_board`×4, exports — todo se
   comportó exactamente como documentado, sin sorpresas.

---

## Resumen final

### 1. ¿Placa completa?

Sí. ERC 0 errores/4 warnings esperados, 23/23 colocados con coordenadas
propias, plano GND filled, 4 keepouts auto-generados, ruteo 10/10 nets (4
corridas completas, todas `err_post=0`), DRC final 0 errores/0 warnings
(delta V4 = 0 en las 4 corridas contra el baseline canónico V4.b),
gerbers G3 + BOM exportados sin error.

### 2. Tabla comparativa D2-D7

| Métrica | D2 | D3 | D4 | D5 | D6 | D7 |
|---|---|---|---|---|---|---|
| Nota | 7.5 | 8.5 | 4.5 | 9.5 | 9.7 | **9.8** |
| Fricciones bloqueantes | 0-1 | 1 | 1 | 0 | 0 | **0** |
| `route_ms` corrida completa | 925s | 53s | 36.7s | 128.8s | 32.4s | **40.6s** |
| Contactos humanos | 5 | 2 | 0 | 0 | 1 | **1** (restore D-27.1 + layout V6, 1 interacción combinada) |
| Errores DRC post-route | 53 | 0 | 42 | 1 | 0 | **0** |
| Baseline V4 pre-route (no-triviales) | N/A | N/A | N/A | 6 | 0 | **6 (V4.a, sin fill) → 0 (V4.b, con fill)** |

### 3. Estado del contrato D-23.2 en 3 tools

- V2 corridas coincidentes por tool en D7: `route_board` **4/4**,
  `fill_zones` **3/3**, `add_zone` **3/3**. **0 divergencias.**
- Acumulado en producción (todas las sesiones): `route_board` 8 (previas)
  + 4 (D7) = **12/12**; `fill_zones` 4 + 3 = **7/7**; `add_zone` 3 + 3 =
  **6/6**. **Total: 25/25 verde**, sin ninguna divergencia registrada en
  la historia del contrato.

### 4. V4 EXPERIMENTO AISLADO D-26.1

- V4.a (sin `fill_zones()`): **6** violaciones no-triviales — predicción
  4-6, cumplida en el extremo superior, idéntico al patrón de D5 (3×
  `hole_clearance` J1 + 1× `hole_clearance` ANT1 + 1× `clearance` ANT1 +
  1× `solder_mask_bridge` ANT1).
- V4.b (con `fill_zones()`): **0** violaciones no-triviales — predicción
  0-1, cumplida en el extremo favorable.
- Delta V4.a→V4.b: **-6** (las 6 violaciones de fill rancio desaparecieron
  íntegramente).
- **¿Ratifica D-26.1 empíricamente sin confusor? SÍ.** D7 replicó el
  orden exacto de fases de D5 (plano ANTES de colocar, D-28.1 vinculante,
  sin desviación) y obtuvo el mismo resultado de D5 antes del fix, luego
  0 tras el fix — a diferencia de D6, donde el orden invertido ya evitaba
  el fill rancio por sí solo y dejaba el efecto de D-26.1 sin poder
  aislarse. Con D7, el par (V4.a=6, V4.b=0) es la evidencia más limpia
  que el proyecto tiene de D-26.1 hasta la fecha.

### 5. V5 Estado de F-D5-01

- ¿Apareció el patrón (isla GND sin vía al plano)? **No** — las 4 corridas
  de ruteo (1 completa + 3 parciales) terminaron con `err_post=0` total,
  sin `unconnected_items` residual.
- Trigger de promoción a P2: D5=sí (1), D6=no, D7=no → **1/3
  dogfoodings** — no se cumple el trigger de "2/3". El hallazgo se
  mantiene como observación puntual de D5 (severidad `info`), sin
  ratificar como patrón sistemático de Freerouting en esta placa.

### 6. V6 Layout con coordenadas propias

| Métrica | D5 | D6 | D7 |
|---|---|---|---|
| Densidad (courtyard/board area) | — (no medido) | — (no medido, idéntico a D5) | **46.0%** |
| Distancia ANT1 al borde | 2mm | 2mm | **15.0mm** |
| Distancia J1 al borde | 2mm | 2mm | **7.5mm** |
| Distancia ANT1↔U4 (net RF) | 28mm (columna izq. vs franja der.) | 28mm (idéntico) | **2mm** (adyacentes por diseño) |
| Patrón general | 2 bloques grandes en columna izq. + 21 componentes en franja der. estrecha (~17mm) | idéntico a D5 (réplica intencional) | **clusters funcionales en anti-diagonal** — BT1 arriba, RF+ANT1 abajo-derecha, I2C cuadrante izquierdo, MCU banda media |

Caracterización cualitativa: D7 es geométricamente **el más disperso y el
menos parecido a D5/D6** de los tres — el bloque RF quedó mucho más
compacto respecto a la antena (2mm vs 28mm), mientras que el bus I2C pasó
de tener corridas cortas dentro de una franja densa a un net diagonal de
~25mm cruzando el board. Sin hallazgos geométricos adversos:
`courtyards_overlap = 0` en la verificación read-only previa al ruteo, y
0 errores DRC en las 4 corridas confirma que la mayor dispersión no
introdujo dificultad de ruteo perceptible (`route_ms` de la corrida
completa, 40.6s, está en el mismo orden que D3/D4/D6).

### 7. V7 Protocolo F-D6-01

| Net | Grado | Tracks borrados | Vías borradas | route_ms | Errores post |
|---|---|---|---|---|---|
| `+3V3` | alto | 65 | 0 | 23692.3 (23.7s) | 0 |
| `/SDA` | medio | 29 | 0 | 24407.8 (24.4s) | 0 |
| `/NSS` | bajo | 7 | 0 | 17708.6 (17.7s) | 0 |

Análisis con N=7 (2 D5 ~9-10s + 2 D6 110-112s + 3 D7 17.7-24.4s): **sin
patrón correlacional identificable** con grado de interconexión (el net
de mayor interconexión no fue el más caro), tamaño del net (9× más
tracks, solo ~6s más caro), ni capas (toda la placa es B.Cu/F.Cu sin
diferencias de capa entre nets). La comparación directa sobre el mismo
net (`/NSS`) entre las tres sesiones — 9-10s, 110-112s, 17.7s — sugiere
que la varianza es del proceso Freerouting/JVM (estado interno, warm-up,
posible influencia de la corrida completa previa en la misma sesión), no
una propiedad determinística del net.

**Recomendación: cerrar F-D6-01 como variabilidad inherente de
Freerouting/JVM.** Documentar el rango esperable (9s-112s) en
`docs/CONTEXT.md`/`docs/specs/restricciones-kicad.md` como dato operativo
("un re-ruteo parcial puede costar tanto como una corrida completa; no
asumir que es proporcionalmente barato"), y dejar de tratarlo como
vigilancia activa — ningún valor de N=7 superó el timeout de 600s, y
ninguno de los 3 de D7 se acercó al umbral de 60s que activaría
promoción a P2.

### 8. Estado de fricciones históricas

- **F-D4-02** (contrato D-23.2 en `route_board`): sigue ratificado —
  ahora 12/12 en producción real, sin excepción.
- **F-D3-01/F-D3-03:** no aparecieron en D7.
- **F-D3-04** (`get_footprint_neighbors` inclusivo): sigue ahorrando
  tiempo — 5 llamadas en Fase 3, sin sorpresas geométricas más allá del
  patrón esperado (BT1/U4 heredados fuera del futuro outline en su
  posición pre-move, resuelto por el move).
- **F-D4-01:** sin novedad, sigue P3 sin ejercitarse en esta sesión (no
  se tocó `get_world_context(kind="sch")` con símbolos `#PWR*`/`#FLG*`).

### 9. Fricciones nuevas de D7 (F-D7-XX)

**Ninguna.** No se registró ninguna entrada F-D7-XX — sesión sin
sorpresas ni comportamiento inesperado del server en ningún punto.

### 10. `route_ms` corridas completas — comparación con D3-D6

D3=53s, D4=36.7s, D5=128.8s, D6=32.4s, **D7=40.6s** — D7 cae dentro del
rango "normal" que D3/D4/D6 establecieron (30-55s), reforzando que
128.8s de D5 fue variabilidad puntual y no la norma.

### 11. `get_footprint_neighbors` en acción

5 llamadas (BT1, U4, J1, J2, ANT1), todas en Fase 3 antes de mover. Con
el outline ya creado (a diferencia de D6, donde el outline no existía
todavía en el momento del chequeo equivalente), los 2 footprints densos
(BT1, U4) mostraron `dist_mm:0` al borde en su posición heredada —
confirmando el mismo patrón que D5 detectó por primera vez (footprints
importados del esquemático caen fuera/al borde del futuro outline) y que
se resuelve trivialmente con el `move_footprint` planeado. No detectó
nada inesperado con las coordenadas nuevas de D7 más allá de este patrón
ya conocido — el ahorro de tiempo es evitar invertir en ruteo sobre una
colocación con conflictos, no en encontrar sorpresas nuevas cada vez.

### 12. Nota /10 con justificación

**9.8.** Cero fricciones de cualquier severidad, contrato D-23.2 en
25/25 acumulado sin divergencias, D-26.1 ratificado por primera vez SIN
confusor metodológico (el objetivo central de la sesión), variación
geométrica controlada exitosa sin degradar el ruteo, protocolo F-D6-01
cerrado con conclusión clara, F-D5-01 no reapareció. No es un 10 pleno
porque queda deuda arrastrada fuera del alcance de D7 (P1 solder mask
ANT1, investigación pendiente desde sesión 26) y porque, estrictamente,
D-26.1 se ratifica sobre una sola geometría nueva (N=1 con aislamiento
limpio; D5 fue el único precedente comparable, con layout distinto) — un
4to dogfooding ratificando el mismo patrón limpio elevaría la confianza
aún más, pero no es necesario para el criterio de cierre de Fase 3.

### 13. ¿Convergimos hacia el criterio de cierre de Fase 3?

**Sí — VERDE, 3er verde consecutivo (D5=9.5, D6=9.7, D7=9.8).** Los 5
criterios del brief se cumplen: nota ≥9 ✓, 0 P0/P1 nuevos ✓, V3 no
activada en ninguna de las 10 corridas de escritura ✓, V2 3/3+ por tool
✓ (4/4, 3/3, 3/3), D-26.1 aislado sin confusor ✓, V6 con layout distinto
exitoso ✓, V7 con conclusión sobre F-D6-01 ✓. **Corresponde iniciar
preparación de Fase 4 en la sesión 30.**

### 14. Evidencia V1-V7 consolidada

- **V1:** 4 keepouts constantes en las 4 corridas de ruteo (KIIDs nuevos
  cada vez, mismas áreas 4.94/1.79/1.79/1.79 mm²).
- **V2:** 3/3+ por las 3 tools (route_board 4/4, fill_zones 3/3, add_zone
  3/3), 0 divergencias, 0 `EXTERNAL_EDIT_DETECTED` espurio en las 10
  corridas.
- **V3:** no activada en ningún momento de la sesión.
- **V4 (V4.a+V4.b):** D-26.1 aislado limpiamente por primera vez (6→0).
- **V5:** F-D5-01 no apareció (1/3 dogfoodings, trigger de promoción a
  P2 no cumplido).
- **V6:** layout completamente nuevo, variación geométrica verificada
  (ANT1 2mm de U4 vs 28mm en D5/D6, densidad 46.0%), sin degradación de
  ruteo ni DRC.
- **V7:** F-D6-01 cerrado — N=7, sin patrón correlacional, recomendación
  de cerrar como variabilidad inherente de Freerouting/JVM.

### 15. Fixture actualizado a versión D7

**Sí**, D7 salió verde. Copiados los 4 archivos a
`tests/fixtures/despertador-routed/`, README reescrito con el detalle de
sesión 29. Sin `AskUserQuestion` adicional porque el impacto en tests ya
se había verificado exhaustivamente antes de tocar nada: ningún test
GUI existente (`test_pcb_session21_neighbors_gui.py`,
`test_pcb_session21_hole_clearance_gui.py`,
`test_pcb_session24_route_board_persist_gui.py`,
`test_pcb_session27_zone_persist_gui.py`, `test_zones_e2e_gui.py`,
`test_reload_e2e_gui.py`) hardcodea coordenadas de colocación — todos
derivan bbox/zonas en runtime desde `get_world_context`/`get_zones`
(D-24.1). Único requisito de esos tests (refs `ANT1`/`J1`/presencia de
plano GND fillado/4 keepouts hc/cobre denso) se sigue cumpliendo con el
layout D7.

### 16. ¿Qué falta para uso semanal?

Nada crítico. **P1 solder mask ANT1** sigue con investigación pendiente
(sesión 26) y puede quedar como deuda arrastrada a Fase 4 — no bloqueó
ninguna corrida de D7 (0 `solder_mask_bridge` en el baseline canónico
V4.b ni en ninguna corrida posterior). El resto del pipeline
schematic→gerbers está operacionalmente estable con 3 dogfoodings verdes
consecutivos sobre geometrías distintas.

### 17. Recomendación explícita para sesión 30

**Iniciar preparación de Fase 4** con el arquitecto — el criterio de
cierre de convergencia de Fase 3 se cumple con D7 (3er verde
consecutivo, D-23.2 en 25/25, D-26.1 aislado limpiamente, F-D6-01
cerrado). Fase 4 es decisión estratégica del arquitecto (release,
features nuevos, escenarios de mayor complejidad) — D7 no prescribe el
contenido de Fase 4, solo certifica que la superficie actual
(colocación, contorno, zonas/plano, ruteo, DRC, export) está lista para
dejar de ser el foco exclusivo de vigilancia. Sugerencia operacional no
vinculante: si Fase 4 incluye escalar a una placa más compleja o
multicapa, sería el primer punto donde reintroducir tensión deliberada
(como hizo D4 con hallazgos reales) tiene sentido — la placa despertador
ya cumplió su función como variable controlada.

