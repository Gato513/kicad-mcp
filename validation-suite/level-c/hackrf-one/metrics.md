# Métricas — HackRF One (Validation Suite Nivel C-01, sesión 33)

Medido con `validation-suite/tools/measure_ground_truth.py` (schema 1.2,
extendido esta sesión) sobre `/usr/bin/python3` + pcbnew 10.0.4.

**Resultado de la sesión: refutación por escalabilidad (`F-V3-ROUTER-TIMEOUT-HARD`).**
`route_board` no completó el ruteo — Freerouting entró en un régimen de
excepciones internas repetidas (`NullPointerException` en
`MazeSearchAlgo`) sin progreso medible durante ~55 min, hasta el corte
duro de 3600s. El output medido abajo es el estado **terminal sin
ruteo**: 437 footprints colocados, plano GND poblado, 0 tracks, 0 vías.
Detalle completo de la secuencia de fallos en `validation-report.md`.

## Ground truth (HackRF One, migrado KiCad 6→10)

- `drc`: **22 errores / 425 warnings** (447 total, 0 `unconnected_items`
  — excepción documentada, mismo precedente que Nivel A/B)
  - Errores: `starved_thermal` 13, `footprint_type_mismatch` 7,
    `padstack` 2
  - Warnings dominantes: `lib_footprint_issues` 199, `text_height` 199
- `total_track_length_mm`: **9046.949**
- `via_count`: **498** (100% `through` — sin blind/buried pese a 4 capas)
- `copper_area_mm2`: **20345.1747** (método `union`)

### Auxiliares del ground truth

- `footprint_count`: 437 · `net_count`: 380 · `copper_layer_count`: 4
- `board_area_mm2`: 9074.4402 · `track_segment_count`: 3817 · `zone_count`: 6
- `density_pct`: 90.17% (capa `C2`/In1.Cu)
- `copper_area_by_layer_mm2`: `C1F` 2519.5376 · `C2` 8182.3388 ·
  `C3` 7766.5678 · `C4B` 1876.7304
- `track_segment_count_by_layer` (nuevo 1.2): `C1F` 2848 · `C4B` 925 ·
  `C2` 29 · `C3` 15 — **hallazgo clave para H1b**: las capas internas
  concentran la mayoría del cobre (planos) pero casi ningún track de
  señal, ya en el ground truth original. Ver §Análisis H2.
- `via_count_by_type`: 100% `through` (0 blind/buried/microvia)

## Estado inicial de `working/` (post `prepare_working.py`, pre-Bloque 2)

- 437 footprints en `(0,0)`, 0 tracks, 0 vías, 0 zonas, Edge.Cuts intacto
  (32 dibujos).
- Refs duplicados: 17× `TESTPOINT-30MIL-MASKONLY` (test points sin
  anotar) — resueltos con `set_footprint_ref` (ADR-0013): `TP1`…`TP16`;
  la 17ª instancia queda con el ref original (patrón N-1, mismo criterio
  que Nivel A/B).
- DRC baseline (todo apilado en origen): **3016** (2405 err / 611 warn) —
  `solder_mask_bridge` 798, `clearance` 500, `unconnected_items` 499,
  `shorting_items` 200, `hole_clearance` 200, `hole_to_hole` 199,
  `holes_co_located` 199 (warn), `lib_footprint_issues` 199 (warn),
  `text_height` 199 (warn), resto pre-existente/cosmético.

## Bloque 2 — secuencia real (con las 3 fricciones)

### Colocación (437 footprints)

Escala ~7× Nivel B (63). Colocación uno-por-uno en el chat (precedente
literal) era impracticable en el timebox de la sesión — decisión con el
arquitecto (`AskUserQuestion`): **grid determinístico (skyline bin
packing) + script driver secuencial** que llama `move_footprint` vía la
misma sesión MCP en proceso (mismo patrón que
`tests/test_pcb_session24_route_board_persist_gui.py`), sin batchear
llamadas IPC (cola de profundidad 1 respetada, secuencial). Detalle del
algoritmo y las 2 iteraciones (1ª con `copper_edge_clearance` nuevo por
falta de margen al borde, corregida con inset 2mm) en
`validation-report.md`.

- **Intento 1** (sin margen de borde): 437/437 `move_footprint` OK, DRC
  post: 1008 (571 err/437 warn) — **63 `copper_edge_clearance` nuevos**
  (9-10 footprints, dominado por `J2` el marco de shield RF).
- **Intento 2** (inset 2mm): 437/437 OK, DRC post: **920** (508 err/412
  warn) — `copper_edge_clearance` en 0, mismo perfil que el baseline
  esperado (unconnected + pre-existentes).

### Plano GND + intento de multi-plano (3 crashes reproducidos)

Ver `validation-report.md` §Fricciones para el detalle forense completo.
Resumen:

1. GND (In1.Cu, bbox completo) — **siempre exitoso**, 1ª llamada de cada
   intento.
2. VCC+VAA (In2.Cu) superpuestas al 100%, prioridad indefinida → **crash
   de KiCad** en la 4ª llamada (`USB_SHIELD`/F.Cu). Disco: 710 zonas (3
   reales + 707 fragmentos sin net).
3. Reintento con VCC/VAA en mitades disjuntas del bbox (sin overlap) →
   **mismo crash**, misma cantidad exacta de fragmentos (710), en la
   misma 4ª llamada. **Refuta la hipótesis de overlap.**
4. Reintento con delay de 20s entre llamadas → **mismo crash**, 3ª
   reproducción idéntica.

**Decisión con el arquitecto:** abandonar multi-plano, quedarse con GND
único (mismo alcance que Nivel A/B). Fricción registrada como
`F-V3-ZONE-FILL-CRASH` (P0/P1, BACKLOG).

### `fill_zones()` explícito

1 zona, 10253.893ms.

### DRC pre-ruteo (con GND)

**967** (555 err/412 warn): `unconnected_items` 499, `lib_footprint_issues`
199, `text_height` 199, **`starved_thermal` 47** (nuevo — pads GND sin
conexión de spoke, esperado sin cobre de señal), resto pre-existente.

### `route_board` — 2 intentos + crash de KiCad intermedio

1. **Intento 1** (`timeout_s=600`, default): `KICAD_TIMEOUT` a los 600s.
2. **Crash real de KiCad** (proceso completamente ausente, no un cuelgue
   transitorio como los de zone-fill) mientras Freerouting seguía
   corriendo huérfano — el harness abortó la espera del cliente MCP a
   los 1818s por inactividad, dejando el proceso padre de `route_board`
   muerto y Freerouting reparentado a `systemd`. Recuperado: KiCad
   relanzado, Freerouting huérfano matado, reintento vía script driver
   propio (no sujeto al timeout de inactividad del cliente MCP del
   harness) para evitar repetir el problema.
3. **Intento 2** (`timeout_s=3600`, vía script driver): `KICAD_TIMEOUT` a
   los 3600s. **Log de Freerouting (33 líneas totales) sin ninguna línea
   de score/progreso** — 6 `NullPointerException` en
   `MazeSearchAlgo.expand_to_target_doors` (`target_shape` null),
   distribuidas de 22:06 a 22:19 (huecos de varios minutos entre cada
   una). Diagnóstico: **crash-loop interno del motor, no lentitud por
   densidad** — patrón distinto al de macro-pad-12 (score estancado cerca
   del final, sesión 32).

**Decisión con el arquitecto:** cerrar como refutación por escalabilidad
(escenario 6, válido y de alto valor informativo por diseño de Nivel C).
No se reintenta una 3ª vez — el patrón (6 excepciones idénticas
distribuidas en la corrida completa) es reproducible/determinístico, no
timing aleatorio.

### DRC de cierre (estado terminal, sin ruteo)

**967** (555 err/412 warn) — idéntico al DRC pre-ruteo. `route_board`
no dejó tracks/zonas parciales tras el fallo (contrato D-23.2/ADR-0012
se sostiene: sin persistencia parcial corrupta ante fallo).

## Output (estado terminal — sin ruteo)

- `total_track_length_mm`: **0**
- `via_count`: **0**
- `copper_area_mm2`: 11096.148 (pads de footprints + plano GND, sin
  tracks de señal)
- `drc`: 555 errores / 412 warnings

## Comparación D-30.3 (sesión 33)

| Criterio | Umbral | Ground truth | Output | Resultado |
|---|---|---|---|---|
| Tracks | ±30% | 9046.949mm | 0mm | **NO APLICABLE — sin ruteo** |
| Vías | ±20% | 498 | 0 | **NO APLICABLE — sin ruteo** |
| Cobre | ±25% | 20345.17mm² | 11096.15mm² | **NO APLICABLE — sin cobre de señal, solo plano+pads** |
| DRC | 0 nuevos eléctricos/estructurales | 22 err | 555 err (todos `unconnected_items`/`starved_thermal`, esperados sin cobre) | **NO APLICABLE — comparación DRC pierde sentido sin ruteo** |

Forzar ratios numéricos sobre un output no ruteado produciría precisión
falsa (ej. "tracks −100%") sin valor diagnóstico real — D-30.2 exige
documentar honestamente, no maquillar con una tabla que aparenta medir
algo que no ocurrió.

## Métricas auxiliares (sesión 33)

### M1 — Tiempos

| Fase | Tiempo |
|---|---|
| Bloque 0 (admisión + ground truth + migración) | ~90 min |
| Colocación (437 fp, 2 intentos con corrección de margen) | ~40 min (2× ~18-20 min de aplicación + cómputo de packing) |
| Zonas (GND exitoso + 3 ciclos crash/cleanup/recuperación) | ~35 min |
| `route_board` intento 1 (timeout 600s) | 600s |
| Crash de KiCad + recuperación (relanzamiento, limpieza de huérfano) | ~10 min |
| `route_board` intento 2 (timeout 3600s, vía script driver) | 3600s |
| **Total Bloque 2** | ~3.5h |

### M2 — Intervención humana discrecional

Escala arranca en 0. Fixes conocidos (`set_footprint_ref`, patrón
D-32d.1) no suman. Esta sesión **sí** requirió intervención humana
repetida fuera del catálogo de fixes conocidos:

- 3× reinicio/reconexión del server MCP (cambios de `KICAD_MCP_PROJECT`
  en la config del harness — acción del arquitecto, no automatizable
  desde el agente).
- 2× reapertura manual de KiCad (crash de zone-fill recuperado solo;
  crash real durante `route_board` requirió relanzamiento).
- 1× decisión explícita del arquitecto sobre estrategia de colocación
  (grid vs. one-by-one).
- 3× decisión explícita del arquitecto sobre manejo de los crashes de
  zone-fill y el timeout duro de `route_board`.

**Nivel de intervención: alto** — significativamente mayor que Nivel
A/B, principalmente por la escala del board interactuando con
limitaciones de estabilidad de KiCad/Freerouting a este tamaño, no por
fricciones del código de `kicad-mcp` en sí (salvo el hallazgo de
zone-fill, ver Fricciones).

### M3.a — Integridad estructural crítica (Pass/Fail)

**PASS.** Pese a 3 crashes de KiCad y 1 timeout duro de Freerouting,
ningún estado persistido en disco quedó corrupto de forma irrecuperable:
los 710 fragmentos de zona se limpiaron determinísticamente vía pcbnew
directo, la colocación de 437 footprints sobrevivió intacta a los 3
crashes, y `route_board` no dejó tracks/zonas parciales tras fallar.

### M3.b — Cambios geométricos esperables (informativo)

No aplica de forma significativa — sin ruteo, no hay geometría nueva de
señal que comparar más allá de la colocación (ver `README.md` §Diversidad
para el detalle de la estrategia de packing).

## Análisis H2 (tercer punto de evidencia real)

Ver `docs/analisis/validation-suite-sintesis-A-B-C.md` para la síntesis
completa de los 3 puntos (A/B/C). Resumen específico de esta sesión:

- **31c ("umbral de vías mal calibrado para bases pequeñas")**: no
  evaluable — sin ruteo no hay vías que medir. Sesión 33 no aporta ni
  confirma ni refuta este diagnóstico específico.
- **32 ("confirmación con base 15x mayor")**: ídem, no evaluable.
- **"DRC estricto no distingue severidad"**: parcialmente evaluable — el
  DRC terminal (967, sin ruteo) es 100% `unconnected_items`/pre-existente/
  `starved_thermal`, **0 eléctricos/estructurales graves nuevos** más allá
  de lo esperado por falta de cobre. La tabla por severidad sigue siendo
  útil incluso en un resultado terminal sin ruteo — confirma que el
  criterio matizado (D-32.1) da lectura correcta también en este caso
  límite.
- **Dimensión nueva (descomposición por capa, propuesta de sesión 33)**:
  aporta señal real **desde el ground truth mismo**, incluso sin poder
  compararla contra un output ruteado: `track_segment_count_by_layer`
  expone que HackRF One usa las capas internas casi exclusivamente como
  planos (29 y 15 segmentos de señal en `C2`/`C3` vs 2848/925 en
  `C1F`/`C4B`) — un patrón de diseño RF real que un ratio global de cobre
  jamás habría revelado. Esto **valida la utilidad de la métrica
  propuesta** independientemente del resultado del ruteo, y es evidencia
  a favor de formalizarla en la revisión D-30.3.
- **H2 general — sesión 33 NO cierra el tercer punto de evidencia
  numérica** (los 3 criterios cuantitativos no son evaluables sin
  ruteo). Sí aporta el punto de evidencia sobre **el techo de escala del
  flujo automatizado**: en ~380 nets/4 capas, el cuello de botella no es
  el propio `kicad-mcp` sino el motor Freerouting 2.1.0 (crash-loop
  interno documentado, upstream). Ver recomendación en el documento de
  síntesis.

## Veredicto final (sesión 33)

**Escenario 6 — Refutación por escalabilidad**, con un diagnóstico más
específico que el genérico "necesitaba más tiempo": Freerouting 2.1.0
entra en un régimen de excepciones internas repetidas sobre esta
topología particular (posible interacción con el layout de 4 capas, el
plano GND parcial, o la escala de 380 nets — no investigado, fuera de
alcance de sesión 33). H1 refutada por escalabilidad del router, no del
flujo `kicad-mcp` — `route_board` se comportó correctamente ante el
fallo (contrato D-23.2 intacto, sin persistencia corrupta). H1a
parcialmente refutada por el hallazgo `F-V3-ZONE-FILL-CRASH` (P0/P1,
reproducido 3×, no investigado). H1b no evaluable en las sub-hipótesis
de capas/USB (sin ruteo), pero la sub-hipótesis de netclasses ya había
sido refutada en Bloque 0 antes de ejecutar nada. H2 no cierra
numéricamente el 3er punto, pero aporta la dimensión de "techo de
escala" como hallazgo metodológico de alto valor para la revisión D-30.3
y el release OSS (documentar el límite conocido del flujo).
