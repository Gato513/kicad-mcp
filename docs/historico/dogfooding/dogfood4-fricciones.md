# Dogfood 4 — Log de fricciones

Sesión 22. Placa despertador ATtiny85 wearable, variable controlada (misma
placa que D3). Objetivo ≥9/10. Formato F-D4-NN + verificaciones V1/V2/V3
obligatorias (evidencia aunque no haya fricción).

Timebox: 2h target / 2.5h techo.

---

## Preflight (Fase 0, hecho en planning — read-only)

- `health()`: server ok, kicad-cli 10.0.4, IPC ok, PCB editor abierto,
  proyecto `gui-test-project`.
- `run_erc()`: 0 errores, 4 warnings `lib_symbol_mismatch` (esperado, D-19b.1).
- `get_world_context(pcb)`: `outline:none`, 23 footprints listados en el
  header (`23c`), colocación tipo import/cluster (x129-154, y66-101).
  **Anomalía:** brief y memoria esperan 24 footprints → ver F-D4-01.

---

## Nota de proceso — `get_footprint_neighbors` en Fase 3 (uso proactivo, C5)
Tras colocar los 23 footprints en el nuevo outline 44×44mm, se corrió
`get_footprint_neighbors(radius_mm=3.0, max_tokens=3000)` sobre J1 (Tag-Connect)
y J2 (JST) — los dos conectores con drill mecánico — ANTES de continuar a
ruteo, siguiendo D-D3.1/C5.
- **J1:** `closest_edge=top, dist_mm=2.0`. Sin pads/tracks/vías ajenas en
  radio 3mm; los 3 `npth` en el resultado son del propio J1 (autoref).
  Colocación validada en una sola llamada, sin necesidad de reposicionar.
- **J2:** `closest_edge=bottom, dist_mm=1.72` (por encima del piso 1.5mm).
  Vecinos más cercanos: C6 (1.83mm), R2/R3 (2.59mm) — sin colisión.
  Colocación validada sin reposicionar.
- **Comparación con D3 (F-D3-04, ~35 min perdidos):** en D4, verificar ambos
  conectores costó 2 llamadas / ~1 min y confirmó la colocación a la primera
  — sin iteración de prueba-y-error contra DRC post-route. Ahorro de tiempo
  real y tangible frente a D3. Ver pregunta 8 del resumen final.

---

## Nota de proceso — Fase 3 completa
23/23 footprints colocados en outline nuevo 44×44mm (x100-144,y50-94), plano
GND filleado (1936mm²) creado antes del ruteo (C2). Render de control
(`export_render(pcb_png)`) confirma separación limpia entre todos los
footprints, sin solapamientos de courtyard/pads. Único detalle cosmético:
etiquetas de silkscreen TP2/TP3 se superponen levemente en el render (no es
colisión de footprint, no debería afectar DRC). `save_board()` OK.

---

## V1-1 — Keepouts auto-generados post-route 1
- **Cantidad:** 4 (via `get_zones(layer="B.Cu")`: 1 zona GND `copper` + 4
  entradas `keepout` — espera, recontar: la salida lista 1 `copper` GND + 4
  `keepout` → **4 keepouts**, áreas 4.94 / 1.79 / 1.79 / 1.79 mm²).
- **Esperado en placa despertador:** 4 fijos (ANT1 + 3× J1 NPTH).
- **Coincide con esperado:** sí (cantidad coincide; el formato TOON compacto
  de `get_zones` no expone el nombre/prefijo `__kicadmcp_hc__` por zona, solo
  `kind=keepout` y `net=-`, así que la verificación del PREFIJO exacto queda
  sin confirmar textualmente — ver limitación abajo).
- **Nota:** el conteo (4) es consistente con F-D3-01 funcionando para los
  puntos protegidos conocidos (ANT1, 3× NPTH de J1). El problema nuevo (ver
  F-D4-02) es que este mecanismo NO cubre vías nuevas creadas por el
  autorouter durante `route_board` — ver abajo.

## V2-1 — Cross-check DRC contrato JSON, corrida 1
- **route_board.drc.err_post:** 51
- **run_drc() independiente:** 51 (`counts.error:51`)
- **Coinciden:** sí (1/3 hacia la ratificación de D-D3.2).
- Nota: cross-check válido pero la sesión se detiene por V3 antes de llegar
  a la 2ª y 3ª corrida — D-D3.2 queda con evidencia parcial (1/3), NO
  ratificada.

## V3 — BANDERA ROJA ACTIVADA (sesión detenida)
Tras la ÚNICA invocación de `route_board` de esta sesión, se cumplen **2 de
las 3 condiciones de parada obligatoria**:

1. **Clearance con `actual=0.0000mm` exacto** — 30 instancias, tipo
   `clearance`, ej. `Track [/MOSI] on B.Cu` vs `Zone [GND] on B.Cu` en
   `pos=[106.646,84.706]` y otros 4+ puntos muestreados, todos
   `actual 0.0000 mm` contra el `clearance 0.2000 mm` configurado.
2. **`hole_clearance` post-route con zona de cobre presente** — 16
   instancias (12 introducidas por este route, según
   `drc.por_tipo_introducidos.hole_clearance:12`), TODAS son
   `Via [<net>] on F.Cu - B.Cu` vs `Zone [GND] on B.Cu`, `actual 0.0000mm`
   contra `0.2500mm` configurado. Ejemplos: vías de `/MOSI` en
   `(127.414,77.414)`, `(137.604,82.957)`, `(106.646,84.706)`,
   `(122.737,78.233)`; vía de `/SCL` en `(130.237,74.343)`.

La bandera `pos=[0,0]` (condición 3 del checklist) NO se observó — todas las
posiciones son coordenadas válidas dentro del board.

**Diagnóstico preliminar (no se investiga más, se reporta):** el patrón de
todos los `hole_clearance` post-route son **vías nuevas creadas por
Freerouting durante `route_board`**, no los huecos mecánicos pre-existentes
que protege `enforce_hole_clearance`/F-D3-01 (J1 NPTH, ANT1). Los 4 keepouts
auto-generados (V1-1) siguen presentes y correctos para sus puntos fijos,
pero **no hay mecanismo que aplique la misma protección a las vías que el
autorouter coloca de cero contra el plano GND ya filleado**. Esto sugiere
que F-D3-01 resuelve el caso "hueco mecánico preexistente cerca de zona" pero
NO el caso "vía nueva post-route cerca de zona ya rellenada" — un gap
distinto, no cubierto por el fix de sesión 21.

También aparecen 2 `courtyards_overlap` (C5/C1 en `(109,76)`, C2/U1 en
`(136.5,63)`) — la colocación manual dejó menos margen del que el render
visual sugería (ver F-D4-02 nota de causa raíz, colocación propia, no bug de
tool). Y 1 `solder_mask_bridge` en el pad de ANT1 contra la zona GND
`(140.5,90)` — coherente con que ANT1 no tiene keepout de aislamiento propio
(el keepout de sesión 21 protege el *hole*, no necesariamente el *pad* contra
puente de máscara con la zona).

**Acción tomada, según protocolo D4:**
1. NO se continúa el ruteo ni se hace cirugía de DRC.
2. Se registra esta fricción bloqueante P0 (F-D4-02, abajo) con el JSON
   completo.
3. Se ejecuta `save_board()` para persistir el estado actual (con errores)
   para inspección del arquitecto.
4. Se termina la sesión y se reporta.

---

## F-D4-02 — [BLOQUEANTE P0] hole_clearance + clearance=0.0000mm post-route contra zona GND ya filleada
- **Qué pasó:** primera y única invocación de `route_board(timeout_s=600)`
  en la sesión. Completó en 36.7s, rutea 10/10 nets ruteables, pero deja
  **51 errores DRC post-route** (`err_introducidos: 42` sobre
  `err_preexistentes: 65`, `err_resueltos: 56`). De esos, 30 son `clearance`
  y 16 son `hole_clearance`, ambos con `actual=0.0000mm` — dos de las tres
  condiciones de bandera roja V3 del protocolo D4. El patrón: vías nuevas
  colocadas por el autorouter (`/MOSI`, `/SCL`) quedan a distancia 0 del
  plano GND ya filleado en B.Cu.
- **Qué esperaba:** dado que sesión 21 cerró F-D3-01
  (`enforce_hole_clearance`) y el D4 existe para confirmar que aguanta en
  producción, esperaba 0 errores post-route o, como mucho, los mismos tipos
  de fricción ya conocidos y diferidos (F-D3-05). No esperaba
  `hole_clearance` masivo contra vías nuevas del autorouter.
- **JSON completo — `route_board` response:**
```json
{"route_ms":36710.886,"nets":{"total":44,"ruteables":10,"ruteadas":10,"parciales":[],"bloqueadas":[]},"drc":{"err_preexistentes":65,"err_post":51,"err_introducidos":42,"err_resueltos":56,"por_tipo":{"solder_mask_bridge":1,"copper_edge_clearance":2,"courtyards_overlap":2,"clearance":30,"hole_clearance":16},"por_tipo_introducidos":{"copper_edge_clearance":2,"clearance":28,"hole_clearance":12}},"tracks_added":238,"vias_added":28,"snap":28,"session_dsn":"/tmp/gui-test-project/.kicad-mcp/autoroute/route.dsn","session_ses":"/tmp/gui-test-project/.kicad-mcp/autoroute/route.ses","reloaded":true,"zones":{"existentes":5,"refilladas":1,"fill_ms":2289.828}}
```
- **JSON completo — `get_zones(layer="B.Cu")` response:**
```
ZONES|v1|layer:B.Cu|5
Z 5b12ac66-2818-41f8-be58-32e399af6b34 copper GND B.Cu bbox=100.000,50.000;144.000,94.000 area=1936.00 filled=1
Z 6e12bef6-9437-4e4a-9812-e2219d80dcd4 keepout - B.Cu verts=16 area=4.94 filled=0
Z 10036f7d-a49f-4729-90a6-accfa528ca53 keepout - B.Cu verts=16 area=1.79 filled=0
Z dd1a539c-6268-4d0f-bed8-65d06062f8e3 keepout - B.Cu verts=16 area=1.79 filled=0
Z 41128c60-c37e-4145-a752-7e1a8fcf3736 keepout - B.Cu verts=16 area=1.79 filled=0
```
- **JSON completo — `run_drc(min_severity="error")` response:**
```json
{"mode":"summary","total":51,"counts":{"error":51,"warning":0},"coordinate_units":"mm","kicad_version":"10.0.4","by_type":[{"type":"clearance","count":30,"severity":"error","message":"Clearance violation ( clearance 0.2000 mm; actual 0.0000 mm)","samples":[{"pos":[106.646,84.706],"items":["Track [/MOSI] on B.Cu, length 9.1534 mm","Zone [GND] on B.Cu, priority 0"]},{"pos":[127.414,78.233],"items":["Track [/MOSI] on B.Cu, length 4.6775 mm","Zone [GND] on B.Cu, priority 0"]},{"pos":[113.118,78.233],"items":["Track [/MOSI] on B.Cu, length 9.6184 mm","Zone [GND] on B.Cu, priority 0"]},{"pos":[132.88,78.233],"items":["Track [/MOSI] on B.Cu, length 5.4659 mm","Zone [GND] on B.Cu, priority 0"]},{"pos":[127.414,78.233],"items":["Track [/MOSI] on B.Cu, length 0.8194 mm","Zone [GND] on B.Cu, priority 0"]}]},{"type":"hole_clearance","count":16,"severity":"error","message":"Hole clearance violation (board setup constraints hole clearance 0.2500 mm; actual 0.0000 mm)","samples":[{"pos":[127.414,77.414],"items":["Via [/MOSI] on F.Cu - B.Cu","Zone [GND] on B.Cu, priority 0"]},{"pos":[137.604,82.957],"items":["Via [/MOSI] on F.Cu - B.Cu","Zone [GND] on B.Cu, priority 0"]},{"pos":[106.646,84.706],"items":["Via [/MOSI] on F.Cu - B.Cu","Zone [GND] on B.Cu, priority 0"]},{"pos":[122.737,78.233],"items":["Via [/MOSI] on F.Cu - B.Cu","Zone [GND] on B.Cu, priority 0"]},{"pos":[130.237,74.343],"items":["Via [/SCL] on F.Cu - B.Cu","Zone [GND] on B.Cu, priority 0"]}]},{"type":"copper_edge_clearance","count":2,"severity":"error","message":"Board edge clearance violation (board setup constraints edge clearance 0.5000 mm; actual 0.3820 mm)","samples":[{"pos":[143.518,74.302],"items":["Track [GND] on F.Cu, length 1.4397 mm","Rectangle on Edge.Cuts"]},{"pos":[143.518,74.302],"items":["Via [GND] on F.Cu - B.Cu","Rectangle on Edge.Cuts"]}]},{"type":"courtyards_overlap","count":2,"severity":"error","message":"Courtyards overlap","samples":[{"pos":[109,76],"items":["Footprint C5","Footprint C1"]},{"pos":[136.5,63],"items":["Footprint C2","Footprint U1"]}]},{"type":"solder_mask_bridge","count":1,"severity":"error","message":"Rear solder mask aperture bridges items with different nets","samples":[{"pos":[140.5,90],"items":["PTH pad 1 [Net-(ANT1-A)] of ANT1","Zone [GND] on B.Cu, priority 0"]}]}],"hint":"detalle completo por páginas: run_drc(detail_type=<tipo>, offset=0, limit=20). Filtrá con exclude_types=[...] o min_severity='error'."}
```
- **Workaround:** ninguno aplicado (regla D4: no arreglar, reportar). Sesión
  detenida en Fase 4 según protocolo V3.
- **Costo:** alto — sesión terminada ~50-60 min en (dentro de Fase 1-4),
  sin placa completa, sin gerbers.
- **Severidad:** bloqueante P0.

---

## Aciertos (D4 vs D3, hasta el punto de corte)

1. **`get_footprint_neighbors` demostró valor real y medible.** Usado
   proactivamente en J1/J2 antes de rutear (C5): confirmó colocación válida
   en 2 llamadas / ~1 min, contra los 35 min perdidos en D3 por F-D3-04. ROI
   directo del fix P1 de sesión 21.
2. **V1 (keepouts auto-generados) coincide exactamente con lo esperado**: 4
   keepouts para los puntos fijos conocidos (ANT1 + 3× J1 NPTH), confirmando
   que `enforce_hole_clearance`/F-D3-01 sigue protegiendo correctamente ese
   caso específico.
3. **V2 (cross-check contrato DRC) coincide exactamente** en la única
   corrida realizada: `route_board.drc.err_post=51` = `run_drc()=51`. El
   contrato JSON de `route_board` es fiel a la realidad del board — F-D3-03
   sigue resuelto en cuanto a fidelidad del reporte (el problema encontrado
   es de fondo — DRC real — no de reporte falso).
4. **`route_board` corrió más rápido que D3**: 36.7s vs 53s, y ruteó 10/10
   nets sin parciales ni bloqueadas — el motor de autoruteo en sí funciona
   bien.
5. **El desglose `por_tipo`/`por_tipo_introducidos` del contrato JSON
   permitió diagnóstico de causa raíz sin llamadas extra** — se pudo
   identificar el patrón (vías nuevas vs. huecos preexistentes) directamente
   del payload de `route_board`, sin iterar con `get_tracks`.

---

## RESUMEN FINAL (sesión detenida en Fase 4 por V3 — ver F-D4-02)

**1. ¿Placa completa?** NO.
- ERC: ✓ (0 errores, 4 warnings `lib_symbol_mismatch` esperados).
- Colocado: 100% (23/23 footprints, outline 44×44mm nuevo).
- Ruteado: 10/10 nets ruteables autoruteadas por Freerouting, PERO con 51
  errores DRC post-route (42 introducidos por el ruteo).
- DRC: ✗ NO limpio — bloqueante (F-D4-02).
- Gerbers: ✗ no se llegó (sesión detenida antes de Fase 5/6).
- BOM: ✗ no se llegó.
- Plano GND: ✓ creado y filleado antes del ruteo (1936 mm²).
- Keepouts auto: ✓ 4/4 esperados (V1-1).
- Fixture: ✗ NO actualizado (no corresponde tocar el repo con una placa que
  no cumple DoD).

**2. Tabla comparativa D2 vs D3 vs D4:**

| Métrica | D2 | D3 | D4 |
|---|---|---|---|
| Nota | 7.5/10 | 8.5/10 | 4.5/10 (ver Q9) |
| Fricciones bloqueantes | 0-1 | 1 externa | 1 (F-D4-02, interna, P0) |
| `route_ms` | 925s | 53s | 36.7s |
| Contactos humanos | 5 | 2 | 0 (sesión detenida, reportando ahora) |
| Errores DRC introducidos post-route | 53 (enmascarados) | 0 | 42 |

**3. Estado F-D3-01 a F-D3-05:**
- **F-D3-01:** parcialmente cerrado. El workaround
  (`enforce_hole_clearance`) aguanta para los 4 puntos fijos pre-conocidos
  (V1 coincide 4=4) pero **NO cubre vías nuevas creadas por el autorouter
  contra un plano ya filleado** — gap nuevo y distinto, ver F-D4-02. F-D3-01
  necesita reabrirse con este alcance ampliado.
- **F-D3-03:** V2 coincide 1/3 (no se alcanzaron las 3 corridas por corte de
  sesión). Evidencia parcial positiva; D-D3.2 sigue sin ratificación
  completa (pendiente para D5).
- **F-D3-04:** SÍ, `get_footprint_neighbors` ahorró tiempo real y tangible
  (ver Aciertos #1 y Q8).
- **F-D3-05:** no se alcanzó a evaluar (sesión cortada antes de esa fase;
  sigue diferido).
- **F-D3-02** (`KICAD_MCP_FREEROUTING_JAR`): sí, seteado y funcional
  (`route_board` corrió exitosamente en 36.7s).

**4. Estado F-01 a F-13 del D2:** no ejercitadas de forma diferenciable en
lo alcanzado (Fase 1-4); ninguna reapareció explícitamente.

**5. Estado F-19b-XX (R12 sch aditivas):** confirmado que NO se ejercitaron
— el esquemático pre-corregido no fue tocado, F8 no fue necesario.

**6. Las 3 fricciones nuevas más caras del D4:**
1. **F-D4-02 (P0, bloqueante):** `hole_clearance`+`clearance=0.0000mm`
   contra zona GND en vías nuevas del autorouter. **Propuesta:** ampliar
   `enforce_hole_clearance` (o agregar un paso equivalente post-ruteo) para
   aplicar clearance a TODAS las vías creadas durante `route_board` contra
   zonas ya filleadas, no solo a los huecos mecánicos pre-identificados.
2. **F-D4-01 (warn):** `get_world_context(kind="sch")` falla con
   `KICAD_CLI_FAILED` por refs de power-flag/power-symbol (`#FLG*`,
   `#PWR*`) normales de cualquier esquemático — no debería romper el
   builder de contexto.
3. **2× `courtyards_overlap` (C5/C1, C2/U1) + 1× `solder_mask_bridge` en
   ANT1:** causa raíz es mi propia colocación (holgura insuficiente en 2 de
   23 posiciones; `get_footprint_neighbors` solo se aplicó a J1/J2 por
   directiva C5, no a pasivos/ICs). No es fricción de tool — es una
   limitación de mi proceso. Propuesta para D5: usar
   `get_footprint_neighbors` más ampliamente, no solo en conectores con
   drill mecánico.

**7. `route_ms` esta placa:** 36.7s (36710.886ms) — más rápido que D3
(53s), dentro de lo esperable por no-determinismo de Freerouting.

**8. `get_footprint_neighbors` en acción:** usado 2 veces (J1, J2),
proactivamente en Fase 3. Ambas confirmaron colocación válida sin necesidad
de reposicionar — ahorro real de ~34 min vs F-D3-04 en D3. Caso NO cubierto:
pasivos/ICs (C1/C5, C2/U1) que sí terminaron con `courtyards_overlap` —
la directiva C5 lo acota a "conectores con drill mecánico propio", dejando
un punto ciego que esta sesión expuso.

**9. Nota /10: 4.5/10.**
- Justificación: la sesión ejecuta correctamente Fase 1-3 (ERC limpio,
  colocación 23/23 sin fricción de tool, plano GND, verificación proactiva
  con `get_footprint_neighbors`) — esa parte sería de nivel D3/D4 normal.
  Pero el criterio "Rojo" del brief (V3 activada, o P0 nuevo, o nota <8) se
  cumple de forma inequívoca: V3 se activó con evidencia sólida (30
  `clearance=0.0000mm` + 16 `hole_clearance` contra zona GND), hay un P0
  nuevo confirmado (F-D4-02), y no hay placa entregable (sin DRC limpio, sin
  gerbers, sin fixture). Se descuenta fuerte por: sesión incompleta (-3),
  P0 nuevo que revela que F-D3-01 no generaliza (-2), pese a que el
  diagnóstico recolectado es de alta calidad y la Fase 1-3 fue impecable
  (+0 extra, es la expectativa base, no un bonus).

**10. ¿Convergimos hacia release?** NO. Hay 1 P0 nuevo confirmado con
evidencia empírica reproducible (F-D4-02): F-D3-01 cubre huecos mecánicos
pre-identificados pero no generaliza a vías nuevas del autorouter contra
zonas ya filleadas — el patrón de plano-GND-antes-de-rutear (C2), que es el
flujo recomendado y validado desde D-19.1, puede terminar bloqueado por DRC
en cualquier placa con plano de cobre. **Recomendación: investigación
mandatoria antes de D5** (no D5 con escalada, no preparación de release).
Esto coincide con el escenario "Rojo" descrito en el brief: "F-D3-01 tiene
más profundidad de la que vimos y necesita otra sesión de investigación
P4.0-style."

**11. Evidencia V1/V2/V3 consolidada:**
- **V1:** 4 keepouts auto en la única corrida — coincide con esperado (4).
- **V2:** 1/3 corridas coincidentes (51=51) — no se alcanzaron las 3
  corridas por corte de sesión.
- **V3:** SÍ activada — 2 de 3 condiciones cumplidas (clearance=0.0000mm
  masivo en 30 instancias + hole_clearance post-route con zona de cobre
  presente en 16 instancias). La condición `pos=[0,0]` no se observó.

**12. ¿Qué falta para uso semanal?** Esto NO es "solo polish". Falta que la
protección de hole/copper clearance se generalice a **cualquier vía nueva
creada durante el autoruteo contra una zona ya filleada**, no solo a los
puntos fijos pre-identificados (ANT1, J1 NPTH). Sin este fix, cualquier
placa que siga el patrón recomendado (plano GND antes de rutear, C2) puede
terminar con DRC bloqueante post-route de forma sistemática — no es un caso
raro, es el flujo estándar del propio protocolo D4. Requiere fix +
reverificación empírica (D5) antes de considerar release.

---

## F-D4-01 — `get_world_context(kind="sch")` falla con KICAD_CLI_FAILED pese a ERC limpio
- **Qué pasó:** al intentar cruzar el inventario de footprints (23 en PCB vs
  24 esperados según brief/memoria D3), llamé
  `get_world_context(kind="sch", max_tokens=4000)` y devolvió error:
  `[KICAD_CLI_FAILED] Estado inconsistente entre netlist y posiciones. hint:
  posición sin netlist: #FLG01, #FLG02, #PWR01`. Estas refs (`#FLG*`, `#PWR*`)
  son símbolos de power-flag/power-symbol auto-generados por KiCad, normales
  en cualquier esquemático con símbolos de alimentación — no deberían romper
  la construcción del contexto.
- **Qué esperaba:** que `get_world_context(kind="sch")` devolviera el
  inventario del esquemático igual que `run_erc()` lo validó limpio (0
  errores, solo los 4 warnings `lib_symbol_mismatch` esperados).
- **Workaround:** no se investigó más a fondo (fuera de scope del D4, no
  bloquea PCB). Se continúa usando `get_world_context(kind="pcb")`, que sí
  funciona, como fuente de inventario. El delta 23 vs 24 footprints queda sin
  resolver — no bloqueante, se seguirá con 23 (lo que reporta el PCB vivo).
- **Costo:** bajo (una llamada, ~1 min).
- **Severidad:** warn (no bloquea el dogfood, pero es un bug real: refs
  invisibles de power no deberían tumbar el builder de contexto sch).

---
