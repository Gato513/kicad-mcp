# Métricas — ANAVI Macro Pad 12 (Validation Suite Nivel B-01, sesión 32)

Medido con `validation-suite/tools/measure_ground_truth.py` (schema 1.1,
extendido en esta sesión) sobre `/usr/bin/python3` + pcbnew 10.0.4.

**Historia:** validación de una sola sesión (32), a diferencia del ciclo
31→31b→31c de Nivel A. El candidato prescrito por el prompt (ANAVI
Miracle Emitter) fue refutado en Bloque 0 por no aportar diversidad D-30.4
real ni alcanzar escala de Nivel B; se activó el respaldo
`anavi-macro-pad-12` (ver `README.md` de este directorio para el detalle
completo de la re-selección).

## Ground truth (ANAVI Macro Pad 12, migrado a KiCad 10)

- `drc`: **19 errores / 156 warnings** (excepción documentada — mismo
  precedente que Nivel A)
  - `drc_by_rule`: `solder_mask_bridge` 12, `starved_thermal` 1,
    `footprint_type_mismatch` 6, `silk_over_copper` 111, `text_thickness` 1,
    `text_height` 1, `lib_footprint_mismatch` 41, `lib_footprint_issues` 2
- `total_track_length_mm`: **2512.2617**
- `via_count`: **30**
- `copper_area_mm2`: **8710.4053** (método `union`, sin `method_notes`)

### Auxiliares del ground truth

- `footprint_count`: 63 · `net_count`: 48 · `copper_layer_count`: 2
- `board_area_mm2`: 8532.8488 · `track_segment_count`: 410 · `zone_count`: 2
  (el autor pobló GND en ambas capas; nuestro flujo canónico usa una sola
  zona B.Cu, patrón heredado de Nivel A — D-26.1)
- `density_pct`: 63.88% · `orphan_vias`: 0 (ground truth sano)

## Estado inicial de `working/` (post `prepare_working.py`, pre-Bloque 2)

- 63 footprints en `(0,0)`, 0 tracks, 0 vías, 0 zonas, Edge.Cuts intacto
  (12 dibujos).
- Refs duplicados: 4× `REF**` (mounting holes) — **presentes también en
  el ground truth original** (verificado: el autor nunca los anotó
  tampoco). Resueltos con `set_footprint_ref` (ADR-0013): `MH1`, `MH2`,
  `MH3`; la 4ª instancia queda `REF**` (única, patrón N-1 heredado de
  31b/31c).
- DRC baseline (todo apilado en origen): **1840** (1397 err / 443 warn) —
  `clearance` 500, `solder_mask_bridge` 235, `shorting_items` 200,
  `courtyards_overlap` 199, `hole_clearance` 199, `holes_co_located` 199
  (warn), `silk_over_copper` 199 (warn), `lib_footprint_mismatch` 41 (warn),
  `hole_to_hole` 12, `footprint_type_mismatch` 6, `lib_footprint_issues` 2
  (warn), `text_height`/`text_thickness` 1 c/u.

## Output (kicad-mcp, sesión 32) — flujo completo

Colocación (63 footprints, referencia mecánica del ground truth — ver
nota de diseño abajo) → `add_zone(GND, B.Cu, fill=true)` → `fill_zones()`
explícito → `route_board(timeout_s=1500)` **falla por timeout** →
`route_board(timeout_s=3600)` completa → **hallazgo P0** (refill interno
de `route_board` no persistió — ver `validation-report.md` §Fricciones)
→ recuperación manual (`reload_board_from_disk` + `fill_zones()`) →
DRC de cierre.

- `drc`: **20 errores / 159 warnings** (post recuperación manual)
  - `drc_by_rule`: `solder_mask_bridge` 12, `footprint_type_mismatch` 6,
    `silk_over_copper` 111, `text_thickness` 1, `text_height` 1,
    `lib_footprint_mismatch` 42, `lib_footprint_issues` 2,
    `track_dangling` 2 (warn), `unconnected_items` 2 (err)
- `total_track_length_mm`: **2410.5425**
- `via_count`: **36**
- `copper_area_mm2`: **8991.6797** (método `union`, sin `method_notes`)

### Auxiliares del output

- `footprint_count`: 63 (exacto) · `net_count`: 48 (exacto) ·
  `board_area_mm2`: 8532.8488 (**idéntico** al ground truth — confirma el
  fix de bbox de 31b sigue estable)
- `track_segment_count`: 429 (coincide exacto con `tracks_added` de
  `route_board`) · `zone_count`: 1 · `density_pct`: 90.07%
- `orphan_vias`: **0** (mi función `_orphan_vias` no encontró vías
  aisladas — ver nota sobre F-D5-01 abajo, el hallazgo de esta sesión es
  a nivel de **pad**, no de vía, distinto mecanismo del mismo síndrome)

### Nota de diseño: resolución de las 4 `REF**`

Igual que en Nivel A (sesión 31b): con 4 duplicados sólo son
posibles/necesarias 3 llamadas a `set_footprint_ref` — la 4ª instancia
queda con el ref original, ya único tras las otras 3 renombres.

### Nota metodológica: contaminación de la muestra representativa de colocación

D-D4.1 pedía ejercitar `get_footprint_neighbors` de forma genuina
(descubrimiento, sin mirar el ground truth) para una muestra
representativa antes de usar las coordenadas del GT para el resto
(colocación mecánicamente restringida por la grilla de keycaps + 4
mounting holes del enclosure — decisión tomada con el arquitecto,
`AskUserQuestion` previo a colocar).

Durante el incidente de proyecto erróneo (Bloque 1, ver
`validation-report.md`), un `get_world_context(kind="pcb")` disparado
para diagnosticar el mismatch de proyecto expuso **sin querer** las 63
posiciones completas del ground truth antes de empezar la colocación
real. Reportado al arquitecto de inmediato (`AskUserQuestion`); decisión:
usar las coordenadas del GT para los 63 footprints (ya conocidas, son la
referencia mecánica real del enclosure de todos modos) y reservar
`get_footprint_neighbors` sólo para verificación de colisión
post-colocación (rol legítimo, no contaminado). **Consecuencia:** M1/M2
de esta sesión NO aportan evidencia limpia sobre D-D4.1 en modo
"descubrimiento" — gap honesto, no forzado. La colocación en sí resultó
limpia (DRC post-colocación: 0 `clearance`/`shorting_items`/
`courtyards_overlap`/`hole_clearance`, ver M3 abajo).

## Comparación (sesión 32)

| Criterio D-30.3 | Ground truth | Output | Ratio | Desviación | Umbral | Veredicto |
|---|---|---|---|---|---|---|
| Tracks (mm) | 2512.2617 | 2410.5425 | 0.9595 | −4.05% | ±30% | **CUMPLE** (cómodo) |
| Vías | 30 | 36 | 1.2000 | +20.00% | ±20% | **CUMPLE** (justo en el borde) |
| Cobre (mm²) | 8710.4053 | 8991.6797 | 1.0323 | +3.23% | ±25% | **CUMPLE** (cómodo) |
| DRC (matizado, ver abajo) | 175 (19e/156w) | 179 (20e/159w) | — | — | 0 nuevos eléctricos/estructurales graves | **NO CUMPLE** |

**3 de 4 criterios cuantitativos cumplen** — resultado muy superior a
Nivel A (1/4). El único que no cumple es DRC, por el hallazgo de
conectividad GND (ver Fricciones).

### Análisis por-net (reflexión #1 de 31c)

Ningún net aparece en sólo uno de los dos lados — **los 47 nets con
copper del output coinciden exactamente con los 47 nets con copper del
ground truth** (0 nets huérfanos de comparación, sin fricción P2 nueva
de este ángulo).

**Top 5 por delta absoluto de longitud:**

| Net | GT (mm) | Output (mm) | Delta | % |
|---|---|---|---|---|
| GND | 76.86 | 29.15 | −47.71 | −62.1% |
| Net-(SW4-Pad1) | 141.59 | 108.40 | −33.19 | −23.4% |
| Net-(D12-Pad2) | 120.37 | 144.15 | +23.78 | +19.8% |
| Net-(SW7-Pad1) | 162.71 | 141.53 | −21.18 | −13.0% |
| Net-(Q1-Pad2) | 75.91 | 89.04 | +13.13 | +17.3% |

**Top 5 por delta porcentual:** idéntico al de arriba salvo el 4º lugar,
que pasa a ser `Net-(D9-Pad1)` (19.28→23.05mm, +19.6%) — los deltas
absolutos grandes ya capturan los porcentuales relevantes en este board.

**Interpretación:** el mayor delta (GND, −62%) es exactamente el
comportamiento esperado y saludable — con el plano GND presente, la
mayoría de las conexiones GND se resuelven por la zona en vez de tracks
discretos, así que GND *debería* tener mucho menos cobre en tracks que
en un layout sin plano explícito medido igual. No es sub-ruteo, es
absorción por el plano. Los otros deltas (`SW4/SW7/D12/Q1-Pad2`) son
topologías alternativas razonables dentro de una matriz de teclas con
múltiples caminos válidos entre pines — ningún patrón sistemático de
sub-ruteo uniforme.

### Vías por net (descomposición del ratio, cross-check H2)

| Net | GT | Output | Delta |
|---|---|---|---|
| GND | 5 | 13 | +8 |
| Net-(D11-Pad2) | 7 | 5 | −2 |
| Net-(D12-Pad2) | 6 | 2 | −4 |
| Net-(SW7-Pad1) | 1 | 3 | +2 |
| +5V | 3 | 2 | −1 |
| +3V3 | 1 | 2 | +1 |
| Net-(L3-Pad2) | 0 | 2 | +2 |
| Net-(L6-Pad2) | 0 | 2 | +2 |
| (resto, 6 nets) | 1 c/u | 1 c/u | 0 |

**GND explica +8 de las +6 vías netas totales** (30→36) — el resto se
compensa entre nets (D11/D12 usan menos vías, L3/L6 usan más). Esto es
consistente con una topología de ruteo distinta pero no sistemáticamente
"peor" — es exactamente el tipo de variación por-net que 31c predijo que
el ratio global no podía distinguir.

### Tabla DRC por severidad (reflexión #2 de 31c, propuesta D-32.1)

| Bucket | Ground truth | Output | Delta | Criterio |
|---|---|---|---|---|
| **Eléctricos** (`unconnected_items`, `clearance`, `hole_clearance`, `hole_to_hole`, `track_dangling`, `via_dangling`, `copper_edge_clearance`, `starved_thermal`, `shorting_items`) | 1 (`starved_thermal`) | 4 (`unconnected_items` 2 + `track_dangling` 2) | **+4 nuevos, −1 resuelto** | 0 nuevos (estricto) → **NO CUMPLE** |
| **Estructurales** (`solder_mask_bridge`, `courtyards_overlap`, `footprint_type_mismatch`, `lib_footprint_mismatch`, `lib_footprint_issues`, `invalid_outline`, `zones_intersect`) | 61 (12+6+41+2) | 62 (12+6+42+2) | +1 (`lib_footprint_mismatch`) | Registrar deltas (moderado) → delta mínimo |
| **Cosméticos** (`silk_over_copper`, `text_height`, `text_thickness`) | 113 | 113 | 0 | Informativo → idéntico |

**Interpretación del criterio DRC:** el conteo total (175→179, +4) parece
casi idéntico, pero la composición cambia exactamente donde importa —
los 4 nuevos son 100% eléctricos (2 `unconnected_items` + 2
`track_dangling`, ambos describiendo las mismas 2 ubicaciones físicas
desde dos reglas DRC distintas — ver Fricciones). El bucket cosmético es
bit-a-bit idéntico. Esto confirma la utilidad de la tabla separada: un
criterio "0 errores nuevos" sobre el total (175 vs 179) habría ocultado
que el defecto real es puntual y eléctrico, no ruido cosmético.

## Métricas auxiliares (sesión 32)

### M1 — Tiempos

- `t_resolucion_refs` + `t_colocacion` (63 `move_footprint` + 3
  `set_footprint_ref`, serializados uno por uno): 16:12:52 → 16:35:34 UTC
  = **22m42s** (67 llamadas).
- `t_zona` (`add_zone(GND, B.Cu, fill=true)`): 16:37:15, `area_mm2` 8519.1.
- `t_refill_1` (`fill_zones()` explícito post-colocación, D-26.1):
  **23.63s** (`duration_ms: 23627.793`).
- `t_routing` intento 1 (`timeout_s=1500`): **FALLA** — `KICAD_TIMEOUT`
  a los 1500s (25min). Log de Freerouting confirma plateau real: score
  estancado en 980.45 (1 sin rutear) durante los últimos ~50 de 195
  passes — no era falta de tiempo, era un óptimo local.
- `t_routing` intento 2 (`timeout_s=3600`): **route_ms 328943.848ms
  (328.94s ≈ 5m29s)** — 42/42 nets ruteables ruteadas, 0 bloqueadas, 0
  parciales. Variabilidad Freerouting/JVM entre intentos consistente con
  F-D6-01 (sesión 29, cerrado como variabilidad inherente).
- Brecha de investigación (diálogo modal bloqueando IPC post-`route_board`,
  mismo patrón de incidente que 31c): ~45 min de intervención humana +
  diagnóstico antes de poder ejecutar `reload_board_from_disk`.
- `t_refill_2` (recuperación manual — ver Fricciones): `reload_board_from_disk`
  (18:09:58) + `fill_zones()` **23.26s** (`duration_ms: 23257.221`,
  18:10:38) + `save_board` (18:12:08).
- `t_drc`: no instrumentado por separado (múltiples `run_drc()` de
  diagnóstico durante la investigación del hallazgo P0).

### M2 — Intervención humana discrecional

**Score: 0** (sin intervenciones discrecionales fuera del flujo
canónico). Detalle de lo que NO cuenta como M2 (aplicación explícita de
convenciones ya sancionadas):
- 3 `set_footprint_ref` (ADR-0013, patrón heredado).
- Colocación por coordenadas del ground truth (decisión explícita del
  arquitecto pre-Bloque 2, dado que la matriz de teclas está
  mecánicamente restringida por el enclosure — no es "atajo", es la
  restricción física real).
- Recuperación manual `reload_board_from_disk` + `fill_zones()` tras el
  hallazgo P0: es literalmente el paso 6 "Refill final" ya prescripto
  en el flujo canónico, ejecutado explícitamente porque el intento
  interno de `route_board` falló en silencio (ver Fricciones) — no es
  una intervención fuera del flujo, es el flujo mismo.
- Reintento de `route_board` con `timeout_s` mayor tras el primer
  timeout: aplicación de la regla de 3 tramos ya prescripta en el
  prompt, no una decisión nueva.

### M3.a — Integridad estructural crítica (Pass/Fail)

**PASS.** `footprint_count` estable en 63 durante todo el flujo.
`net_count` exacto (48) en ground truth y output. `board_area_mm2`
idéntico bit a bit (8532.8488) — confirma el fix de bbox de 31b sigue
sólido bajo un board 5x más grande que Nivel A.

### M3.b — Cambios geométricos esperables (informativo)

63/63 footprints movidos (100%) — mejora sobre 69% (9/13) de sesión 31 y
en línea con el 100% (13/13) de 31c.

## Análisis H2 (segundo punto de evidencia real)

**Cross-check contra los 2 diagnósticos de sesión 31c:**

1. **"Vías mal calibrado para bases pequeñas"** — Macro Pad 12 tiene una
   base de 30 vías (15x la de Nivel A). Resultado: ratio 1.2000 (+20.00%),
   **exactamente en el borde del umbral ±20%** — pasa, pero por el margen
   más estrecho posible. Esto **confirma parcialmente** el diagnóstico de
   31c: con una base 15x más grande, el mismo tipo de variación
   por-topología (que en Nivel A disparaba +200% de desviación) ahora
   produce apenas +20%. La normalización por tamaño de base parece ser
   el mecanismo real detrás de la mala calibración observada en 31c, no
   el umbral en sí — un umbral relativo se comporta razonablemente bien
   cuando la base ya no es de un solo dígito.
2. **"DRC estricto no distingue severidad"** — confirmado de nuevo, y de
   forma más clara que en 31c: sin la tabla separada, "175→179 (+4)"
   parece un resultado casi perfecto. Con la tabla separada, se ve que
   el 100% del delta neto es eléctrico (el bucket que realmente importa),
   mientras cosmético y estructural están prácticamente intactos. El
   criterio matizado (D-32.1 propuesta) sí distingue correctamente que
   esta validación **no** cumple DRC, mientras que un conteo total crudo
   habría sido ambiguo.

**Dimensión nueva no vista en Nivel A:** el análisis por-net de vías
(esta sesión) mostró que un solo net (GND) puede explicar la mayor parte
de un delta de vías agregado (+8 de +6 netos, compensado por otros nets
que usaron menos) — el ratio agregado por sí solo no distingue "todos
los nets usan un poco más" de "un net domina el delta". Candidato a
agregar como dimensión de análisis en sesión 33.

**No se cierra D-30.3 en esta sesión.** Tercer punto pendiente: sesión 33
(Nivel C). Con dos puntos ahora (31c: base chica, mal calibrado; 32: base
grande, calibrado razonablemente), la hipótesis de trabajo para la
revisión post-33 es: **normalizar el umbral de vías por tamaño de la
base del ground truth** (ej. umbral absoluto para bases <10, umbral
relativo ±20% para bases ≥10), no cambiar el número ±20% en sí.

## Veredicto final (sesión 32)

- **H1** (generalización D-30.3, matizada): 3/4 criterios cumplen
  (tracks, vías, cobre) — **mejor resultado que Nivel A**. DRC no cumple
  por el hallazgo de conectividad GND (ver Fricciones). Refutación
  parcial y localizada, no generalizada.
- **H1a** (estabilidad end-to-end): **confirmada con matiz**. 0
  fricciones P0/P1 nuevas de *flujo* (el hallazgo del refill silencioso
  es de *robustez de `route_board`*, no del flujo canónico en sí — el
  flujo ya incluye el paso de recuperación como parte de su propio
  diseño). 1 fricción P2 (3ª instancia del patrón F-D5-01/F-V1c-01,
  promovida a P1 investigación).
- **H1b** (reformulada — features de Nivel B): **confirmada**. Matriz de
  teclas con diodo por tecla, backlighting por tecla, footprints hot-swap
  Kailh, y migración de formato KiCad 6→10 real, todas ejercitadas sin
  bloqueo del flujo.
- **H2**: segundo punto de evidencia real, con dimensión nueva (análisis
  por-net de vías). Ver arriba.

**Escenario de cierre: 3 ("éxito con matiz de fricciones P2/P3") con
elementos de 2 ("éxito con matiz de umbrales")**, más un hallazgo
independiente de robustez en `route_board` (ver `validation-report.md`
§Fricciones para el detalle completo del hallazgo del refill silencioso).
