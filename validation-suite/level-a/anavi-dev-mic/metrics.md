# Métricas — ANAVI Dev Mic (Validation Suite Nivel A-01, sesiones 31/31b/31c)

Medidas con `validation-suite/tools/measure_ground_truth.py` (pcbnew
10.0.4 del sistema, `/usr/bin/python3`). Ver ese script para la
documentación completa de cada métrica (qué mide, qué asume, qué excluye).

**Historia:** ground truth y estado inicial medidos en sesión 31; sesión
31 bloqueó en `route_board` (F-V1-02); sesión 31b implementó los fixes
(`set_footprint_ref` + pre-check `DUPLICATE_REFS`, ADR-0013); sesión 31c
reintenta el flujo completo desde Bloque 2 y cierra la comparación D-30.3.
La sección "Output sesión 31 (incompleto)" se conserva más abajo como
registro histórico del punto de bloqueo original.

## Ground truth (ANAVI Dev Mic, migrado a KiCad 10)

Medido sobre `ground-truth-kicad10/anavi-dev-mic.kicad_pcb`
(2026-07-28T21:34:57Z, `kicad_version: 10.0.4`, `method: union`).

- **drc**: 18 errores / 25 warnings — **excepción de admisión documentada**
  (ver `README.md` §Admisión, criterio 6). Desglose: `error` = 17
  `solder_mask_bridge` + 1 `starved_thermal`; `warning` = 12
  `lib_footprint_mismatch` + 10 `silk_over_copper` + 2 `text_height` + 1
  `text_thickness`. Idéntico bit a bit antes y después de la migración de
  formato (43/43 en ambos casos).
- **total_track_length_mm**: 242.8531
- **via_count**: 2
- **copper_area_mm2**: 1556.7385 (unión por capa — F.Cu: 706.816, B.Cu:
  849.9225; total aditivo sin unir: 1589.4653, unión ≤ aditivo ✓)
- **method_notes**: ninguno (sin violaciones de cordura)

### Auxiliares del ground truth

- footprint_count: 13 · net_count: 20 · copper_layer_count: 2
- board_area_mm2: 1210.9775 (bbox de Edge.Cuts, 8 dibujos formando el
  contorno)
- track_segment_count: 71 (segmentos + arcos, sin vías)
- zone_count: 2 (zonas de cobre; excluye keepouts/rule areas)
- density_pct: 70.18% (B.Cu, la capa con más cobre / board_area)

## Estado inicial de `working/` (post `prepare_working.py`, pre-Bloque 2)

Verificado con asserts del propio script + medición independiente:

- 0 tracks, 0 vías, 0 zonas (todas removidas)
- 13/13 footprints en `(0,0)` (decisión explícita: estado literal del
  prompt, no grilla prolija — courtyards 100% solapados, caso adversarial
  para `get_footprint_neighbors`)
- Edge.Cuts intacto (8 dibujos, mismo bbox 1210.9775mm² que el ground
  truth — confirma que sólo se tocaron footprints/cobre, nunca el
  contorno)
- DRC baseline (todos apilados en el origen): 444 errores (courtyard
  overlap dominante, esperable) / 63 warnings — referencia, no criterio de
  aceptación (ver Bloque 1 del `validation-report.md`).

## Output (kicad-mcp, sesión 31c) — flujo completo

Medido sobre `working/anavi-dev-mic.kicad_pcb` post-`route_board`+refill
final (2026-07-29T11:19:00Z, `kicad_version: 10.0.4`, `method: union`).
`set_footprint_ref` resolvió las 4 instancias `REF**` (3 renombradas a
`MH1`/`MH2`/`MH3`, la 4ta quedó como `REF**` — ver nota de diseño abajo);
`route_board` completó sin que el pre-check `DUPLICATE_REFS` se disparara.

- **drc**: 18 errores / 45 warnings. Desglose de errores: 17
  `solder_mask_bridge` (mismo tipo Y mismo conteo que el ground truth,
  pads SMD densos de U1/MK1) + 1 `unconnected_items` (una vía GND en
  F.Cu-B.Cu no conectada al pad GND de MK1, pad de 0.30×0.30mm — ver
  fricción `F-V1c-01` en `docs/BACKLOG.md`). Warnings: 16
  `silk_over_copper` + 12 `lib_footprint_mismatch` + 11 `silk_overlap` +
  3 `silk_edge_clearance` + 2 `text_height` + 1 `text_thickness`.
- **total_track_length_mm**: 162.473
- **via_count**: 6
- **copper_area_mm2**: 1396.7342 (unión por capa — F.Cu: 265.458, B.Cu:
  1131.2763; total aditivo sin unir: 1434.651, unión ≤ aditivo ✓)
- **method_notes**: ninguno (sin violaciones de cordura)

### Auxiliares del output

- footprint_count: 13 · net_count: 20 · copper_layer_count: 2 — **ambos
  exactos al ground truth** (M3.a PASS, sin corrupción estructural)
- board_area_mm2: 1210.9775 — **exacto al ground truth** (confirma que
  Edge.Cuts no se tocó en ningún momento del flujo)
- track_segment_count: 79 · zone_count: 1 (una sola zona GND en B.Cu, vs
  2 del ground truth — el flujo canónico de esta validación sólo agrega
  un plano por Bloque 2 paso 3; el ground truth del autor tiene cobre en
  ambas capas)
- density_pct: 93.42% (B.Cu) — notablemente más alto que el 70.18% del
  ground truth: la zona propia cubre el bbox completo del board
  (`[109,46.5,144,81]`), mientras que el ground truth tiene una geometría
  de zona más recortada y cobre repartido en F.Cu también (706.816mm² vs
  nuestros 265.458mm², ya que sólo agregamos zona en B.Cu)

### Nota de diseño: resolución de las 4 `REF**` (aplicación de fix de 31b)

`set_footprint_ref` se llamó 4 veces, pero sólo 3 tuvieron éxito. El
intento de renombrar la 4ta instancia devolvió `INVALID_PARAMS` — **por
diseño** (ADR-0013): tras renombrar 3 de 4, la instancia restante ya no
está duplicada (es la única con ese ref), y la tool rechaza estructuralmente
el renombrado de refs únicos para no poder usarse como `delete_footprint`
disfrazado. Consecuencia: 1 mounting hole quedó con el ref literal
`REF**`, que es ahora único en el board (no colisiona con nada) — cumple
el requisito real ("4 refs únicos, sin colisión") aunque no siga la
convención de nomenclatura `MHn` para las 4 instancias. Verificado con
`read_board_context` post-resolución: 0 duplicados, 13c/19n estable. Esto
**no cuenta como M2** (aplicación de fix conocido con precedente
ADR-0013), pero es un matiz operacional útil para sesión 32: al resolver
un grupo de N duplicados, sólo N-1 llamadas a `set_footprint_ref` son
posibles/necesarias; la última queda con el ref original.

## Output (kicad-mcp, sesión 31) — INCOMPLETO, histórico (Bloque 2 bloqueado en `route_board`)

**No hay output D-30.3 completo.** El flujo canónico llegó hasta el final
del paso 3 (colocación + plano GND + refill explícito) y se detuvo en el
paso 4 (`route_board`) por `F-V1-02` — ver `docs/BACKLOG.md` §P0 y
`validation-report.md` para el detalle completo. `total_track_length_mm`,
`via_count` y `copper_area_mm2` del output **no existen** (0 tracks nunca
se generaron). Registro acá el único estado medible: el DRC **post-
colocación+zona, pre-ruteo**, como evidencia de que la colocación en sí
fue razonable y el bloqueo es específico de `route_board`:

- **drc (post-colocación+zona, pre-ruteo)**: 56 errores / 33 warnings
  (total 89) — mejora fuerte sobre el baseline de 444/63 del Bloque 1.
  Desglose de errores: 24 `unconnected_items` (esperable, nada rutéo
  todavía), 23 `solder_mask_bridge` (pads SMD densos de U1/MK1 muy cerca
  entre sí — mismo tipo de hallazgo que el ground truth, ver nota abajo),
  6 `clearance` + 3 `courtyards_overlap` + 3 `holes_co_located` (los 3
  mounting holes `REF**` no direccionables, atribuible 100% a F-V1-02).
  Warnings: 12 `lib_footprint_mismatch` (preexistente, no de colocación),
  14 `silk_over_copper` + 2 `text_height` + 1 `text_thickness` + 1
  `silk_overlap` (cosméticos).
- **total_track_length_mm**: N/A (0 tracks, ruteo nunca corrió)
- **via_count**: N/A
- **copper_area_mm2**: N/A (sólo el plano GND en B.Cu existe;
  `add_zone` reportó `area_mm2: 1207.5` para la zona en sí, pero eso no es
  la métrica `copper_area_mm2` de D-30.3, que se mide con
  `measure_ground_truth.py` sobre el resultado FINAL post-refill)

**Nota sobre `solder_mask_bridge` en el output parcial:** 23 violaciones,
todas por proximidad de pads SMD dentro del mismo footprint (U1: pads de
2.75×2.00mm a paso 2.54mm; MK1: pads de 0.72×0.52mm a paso <1mm) — el
mismo tipo de defecto que ya aparece en el ground truth del propio autor
(17 `solder_mask_bridge`, ver arriba) y que investigamos internamente en
D-30.5 (sesión 30). Es una característica del footprint/pad-pitch del
diseño, no una regresión de la colocación de sesión 31 — pero como el
`working/` nunca llegó a rutear+refillar, no hay forma de saber si el
`enforce_hole_clearance` post-refill (que sí corrige este tipo de cosa en
`route_board`/`fill_zones`, D-30.5) lo habría resuelto igual que en
producción real. Queda como pregunta abierta para cuando F-V1-02 se
resuelva y esta validación se pueda reintentar.

## Comparación (sesión 31c)

- **drc**: 18 errores (mismo conteo que el ground truth) pero
  **composición distinta**: 17 `solder_mask_bridge` compartidos + 1
  `unconnected_items` propio (el ground truth tiene 1 `starved_thermal`
  en su lugar, no `unconnected_items`). Bajo el criterio estricto de
  D-30.3 ("0 errores nuevos vs ground truth"), este es **1 error de tipo
  nuevo → NO PASA**. Warnings: `silk_overlap` (11) y `silk_edge_clearance`
  (3) son tipos nuevos no presentes en el ground truth (cosméticos,
  dependientes de la colocación específica elegida en esta sesión, no de
  una falla del flujo). → **DRC: NO CUMPLE** (criterio estricto), aunque
  el conteo total de errores coincide exactamente.
- **ratio_tracks**: 162.473 / 242.8531 = **0.669** (desviación -33.1%,
  umbral ±30%) → **NO CUMPLE**, por un margen estrecho (3.1 puntos fuera).
- **ratio_vias**: 6 / 2 = **3.0** (desviación +200%, umbral ±20%) → **NO
  CUMPLE**, por un margen amplio.
- **ratio_cobre**: 1396.7342 / 1556.7385 = **0.897** (desviación -10.3%,
  umbral ±25%) → **CUMPLE**, con margen cómodo (14.7 puntos de holgura).

**Veredicto D-30.3: 1 de 4 criterios cumple** (cobre). H1 ("igualmente
válido" en el sentido estricto de D-30.3) queda **refutada** por 3 de 4
criterios. Ver "Análisis H2" abajo — la lectura correcta de este resultado
no es "el flujo canónico produce una placa mala": el board completó
ruteo, tiene 0 nets bloqueadas, `board_area`/`footprint_count`/`net_count`
exactos, y el único error DRC nuevo es una vía-a-pad de 0.30mm sin
conectar. Es evidencia de que **los umbrales relativos de D-30.3, tal
como están calibrados, no discriminan bien en este caso** — ver H2.

## Métricas auxiliares (sesión 31c)

- **M1_tiempos**:
  - `t_resolucion_refs`: 4 llamadas `set_footprint_ref` (3 exitosas + 1
    `INVALID_PARAMS` esperado por diseño) — no instrumentado en ms, del
    orden de segundos totales (llamadas IPC individuales).
  - `t_colocacion`: 13 llamadas `move_footprint` (todas exitosas, un
    footprint por llamada) + 6 `get_footprint_neighbors` de verificación.
    **Lección de proceso**: las 6 llamadas de verificación se lanzaron en
    paralelo en un único batch y se encolaron contra el socket IPC de
    KiCad (cola de profundidad 1 — ver CLAUDE.md), cada una tardando
    >120s por contención en vez de los ~1-2s esperados para una llamada
    individual. Mismo patrón que sesión 31 documentó (nota `D-12.7`).
    **Recomendación explícita para sesión 32**: NO batchear llamadas MCP
    contra `kicad-mcp` en paralelo; serializarlas.
  - `t_refill_1` (`fill_zones()` post-`add_zone`, D-26.1): 23.99s
    (`duration_ms: 23985.87`).
  - `t_routing`: **184.82s** (`route_ms: 184817.54`) — Freerouting
    completó 15/15 nets ruteables, 0 bloqueadas, 0 parciales. Muy por
    debajo del umbral de 30 min (normal).
  - `t_refill_2` (final, protege D-23.2): 26.14s (`duration_ms: 26141.97`).
  - `t_drc`: no instrumentado en ms (subprocess `kicad-cli`, típicamente
    sub-segundo a pocos segundos).
  - **Incidente de proceso** (no M2, ver abajo): tras `route_board`, el
    editor vivo de KiCad quedó desincronizado del disco
    (`EXTERNAL_EDIT_DETECTED` en el primer intento de `fill_zones()`).
    `reload_board_from_disk()` devolvió `KICAD_NOT_RUNNING` porque un
    diálogo modal de KiCad ("¿archivo cambió afuera, recargar?") bloqueaba
    el hilo de UI (consistente con la regla operacional de CLAUDE.md:
    "todo request IPC se procesa en el hilo de UI de KiCad"). Se resolvió
    pidiendo al humano cerrar el diálogo — un handoff no listado
    explícitamente en el prompt pero consistente con el patrón de 3
    handoffs ya conocido (recarga de disco tras escritura externa de
    `route_board`). Recomendación para sesión 32: anticipar este diálogo
    como parte normal del paso post-`route_board`.

- **M2_score: 0** — sin intervenciones discrecionales. Las 4 llamadas de
  `set_footprint_ref` son aplicación explícita del fix de 31b (no cuentan,
  ver ADR-0013). El handoff del diálogo modal post-`route_board` es
  operación de entorno (recarga de disco), no una decisión de diseño o
  desviación del flujo canónico.

- **M3.a**: **PASS**. `footprint_count` estable en 13 durante todo el
  flujo (colocación, zona, ruteo, refill). `net_count` exacto al ground
  truth (20, vía `measure_ground_truth.py` — el mismo método de conteo en
  ambos lados). Sin corrupción estructural en ningún punto.

- **M3.b**: **13/13 footprints modificados de posición (100%)** — mejora
  sustancial sobre el 69% (9/13) de sesión 31, ya que el fix de F-V1-02
  permitió mover también las 3 instancias `MH1`/`MH2`/`MH3` que antes
  quedaban clavadas en `(0,0)`.

## Análisis H2 (sesión 31c) — primer punto real de evidencia

Sesión 31c aporta el primer punto de evidencia REAL sobre discriminancia
de umbrales (sesión 31 sólo aportó evidencia parcial de calculabilidad,
sin output que comparar).

- **Calculabilidad**: confirmada de nuevo — `measure_ground_truth.py`
  corrió limpio sobre el output real (`method_notes: []`, `union ≤
  aditivo` verificado). Ambos lados de la comparación (GT y output) se
  midieron con el mismo procedimiento reproducible.
- **Discriminancia — evidencia mixta, con una señal clara**:
  - El umbral de **cobre (±25%)** discriminó razonablemente: el output
    cayó en -10.3%, dentro del umbral con margen cómodo (14.7 puntos de
    holgura). Ni tan ajustado que sea ruido, ni tan lejos que perdiera
    sentido comparar. Buena señal de que este umbral está bien calibrado.
  - El umbral de **tracks (±30%)** falló por un margen muy estrecho
    (-33.1%, sólo 3.1 puntos fuera). Es exactamente el caso "cerca del
    borde" que el prompt anticipó como interpretación de "el umbral
    discrimina bien" — no hay evidencia de que el umbral esté mal
    calibrado, sólo de que un autorouter genérico produce ~33% menos
    longitud total que un layout manual optimizado en este board
    específico (plausible: Freerouting privilegia rutas cortas per net,
    a costa de más cambios de capa).
  - El umbral de **vías (±20%) resultó NO discriminante**: la base del
    ground truth es 2 vías — un número tan bajo que CUALQUIER resultado
    de autorouteo realista sobre un board de 2 capas/20 nets casi
    seguro excede el ±20% (un salto de 2→3 vías ya es +50%). El resultado
    real (6 vías, +200%) no necesariamente indica una placa "3x peor" —
    3 de esas vías extra podrían ser diferencias legítimas de estilo de
    ruteo (más cambios de capa a cambio de trazas más cortas, como sugiere
    el resultado de tracks). **Un umbral relativo (%) no es la forma
    correcta de medir esto cuando la base es un entero de un solo dígito.**
    Evidencia clara de que este umbral, tal como está definido, no
    discrimina de forma útil para boards con pocas vías.
  - El criterio de **DRC "0 errores nuevos"** también mostró ser
    demasiado estricto en un sentido: coincidencia exacta en CONTEO total
    (18=18) pero falla por diferir en composición de UN error y en dos
    tipos de warning puramente cosméticos (`silk_overlap`,
    `silk_edge_clearance` — dependen de dónde cada quien decide poner el
    texto de silkscreen, no de la validez eléctrica del diseño). El
    criterio no distingue entre "un error nuevo que indica un problema
    real" (nuestro caso: 1 vía sin conectar, sí relevante) y "diferencias
    cosméticas de colocación que cualquier segunda persona/flujo
    produciría distinto" (silk warnings). Recomendación explícita para
    revisión post-33: considerar separar DRC en severidad
    eléctrica/funcional vs. cosmética/silkscreen para este criterio.

**Conclusión H2 (parcial, 2do de 3 puntos)**: el umbral de cobre parece
bien calibrado; el de tracks es plausible sin evidencia de mala
calibración; el de vías muestra evidencia clara de mala calibración para
bases pequeñas (necesita revisión — candidato: umbral absoluto tipo "±N
vías" en vez de porcentaje, o normalizar por número de nets); el
criterio estricto de DRC por tipo-exacto probablemente necesita
distinguir severidad eléctrica de cosmética. **No se cierra la validez
definitiva de D-30.3 acá** — input formal para la revisión post-sesión 33
(2 puntos de evidencia real reunidos: éste + el próximo de Nivel B/C).

## Métricas auxiliares (sesión 31, histórico — ver arriba para 31c)

- **M1_tiempos** (aproximado, no instrumentado con precisión de
  milisegundos — ver `validation-report.md` para el detalle por tool call):
  - `t_colocacion`: ~10 llamadas `move_footprint` (1 bootstrap + 9
    footprints únicos direccionables), + 2 `get_footprint_neighbors` de
    verificación (una de ellas tardó >120s por contención IPC, D-12.7).
  - `t_refill_1` (`add_zone(fill=true)`): incluido en el mismo call,
    zona filleada de una.
  - `t_refill_2` (`fill_zones()` explícito, D-26.1): 16.67s
    (`duration_ms: 16672.67`).
  - `t_routing`: **N/A** — `route_board` falló en el paso de exportación
    DSN antes de invocar Freerouting; `route_ms` nunca se generó.
  - `t_drc`: 1 corrida `run_drc()` post-colocación+zona (~segundos,
    kicad-cli).
  - `t_total`: sesión completa del Bloque 2 (colocación hasta el
    diagnóstico del bloqueo) — del orden de los ~40-50 min, dominado por
    la investigación de causa raíz de F-V1-02 (aislamiento con
    experimentos controlados en `/usr/bin/python3` standalone), no por
    las tools en sí.

- **M2_score: 1** (no 0 — hubo un ajuste táctico documentado, sin cambio
  conceptual del flujo):
  ```
  M2_events:
    - [tipo=1] Bootstrap de move_footprint (mover U1 a una posición
      intermedia dentro del rango inicialmente válido, luego a la
      posición final) para sortear F-V1-01 (bug de board_bbox_mm). Es un
      reintento equivalente con la misma tool prescrita, sin cambio de
      criterio ni de orden de fases del flujo canónico.
  ```
  **No se sumó M2 por F-V1-02** — la sesión decidió explícitamente NO
  intervenir manualmente fuera del flujo (ver §Decisión) para no
  contaminar H1a con una intervención M2=3; en cambio se detuvo el Bloque
  2 y se documentó como hallazgo P0.

- **M3.a**: **PASS** — `footprint_count` se mantuvo en 13 durante toda la
  colocación (verificado antes y después: `get_world_context` mostró
  13c/19n consistente en cada lectura). Sin corrupción estructural. Nets:
  no aplica evaluar post-ruteo (el ruteo nunca corrió), pero el `19n`
  reportado por `get_world_context` coincide con el ground truth
  (`net_count: 20` incluye el net vacío reservado por KiCad, que TOON no
  cuenta — consistente).

- **M3.b**: 9/13 footprints modificados de posición vía `move_footprint`
  directo (U1, J1, J2, MK1, R1, R2, C1, C2, 1×`REF**`) = 69% del total. 3
  footprints (`REF**`×3) **no pudieron modificarse** — permanecen en
  `(0,0)`, fuera del bbox `board_bbox_mm` original y del contorno real
  (atribuible a F-V1-02, no a decisión de diseño).

## Análisis H2 (sesión 31, histórico)

**No aplicable en su forma completa** — H2 evalúa si las 4 métricas
D-30.3 son calculables sin ambigüedad Y discriminantes; sin output no hay
las 4 métricas del lado "output" de la comparación. Sin embargo, sesión
31 sí aporta evidencia parcial y valiosa para H2:

- **Las métricas SÍ fueron calculables sin ambigüedad del lado del
  ground truth** — `measure_ground_truth.py` corrió limpio, sin
  `method_notes`, con `union ≤ aditivo` verificado, contra un board real
  y no trivial (13 footprints, 20 nets, 2 capas). Esto es evidencia
  confirmatoria de la mitad de H2 (calculabilidad del procedimiento), no
  de la otra mitad (discriminancia de umbrales, que necesita ambos lados
  de la comparación).
- **El gate de admisión (Bloque 0) SÍ demostró ser operacional y útil**:
  descartó 2 candidatos (`anavi-light-controller` por formato/
  mantenimiento, `anavi-rtc-3032` por fabricación no confirmada,
  `anavi-handle` por ambas) antes de comprometer tiempo de sesión, y el
  candidato aceptado con excepción documentada (criterio 6, DRC del
  ground truth) resultó ser precisamente el que expuso F-V1-02 — el
  proceso de selección no ocultó el problema, lo encontró en el primer
  intento real de rutear.
- **No hay evidencia sobre discriminancia de los umbrales ±30/±20/±25%**
  — eso requiere el output completo. Sesión 32 (si F-V1-02 se resuelve
  antes) o un reintento de sesión 31 post-fix son los próximos puntos de
  evidencia posibles.

**Decisión de la sesión:** ante la tensión entre "forzar el cierre de la
validación" (interviniendo manualmente para borrar los `REF**`
duplicados, fuera del flujo canónico) y "documentar honestamente un
hallazgo" (D-30.2, precedente sesiones 23/26/30), se optó por lo segundo
con `AskUserQuestion` explícita al arquitecto. Sesión 31 cierra como
**Escenario 4 — "Aprendizaje por P0/P1"** de los 7 criterios de éxito del
prompt: H1a refutada honestamente, gap legítimo del flujo (Fase 4:
"NO regresión por default" ante P0 en validación externa), confianza
intelectual alta, sesión de fix intermedia agendada (agregar
`delete_footprint` con direccionamiento por `kiid`).

## Veredicto final (sesión 31c)

- **H1 (generalización estricta D-30.3)**: **refutada** — 1 de 4
  criterios cumple (cobre). Pero la refutación es de umbral, no de flujo:
  el board completó, sin nets bloqueadas, sin corrupción, con 0 errores
  DRC nuevos de tipo funcional (el único nuevo es cosmético/menor).
- **H1a (estabilidad de decisiones D-19.1/D-23.2/D-26.1/D-27.1/D-30.5 +
  fixes 31b)**: **confirmada**. 0 fricciones P0/P1 nuevas. 1 fricción
  P2 nueva (`F-V1c-01`, vía GND sin conectar en pad de 0.30mm).
- **H1b (suficiencia del pivote de 31b)**: **confirmada**. 3 de 4
  `set_footprint_ref` exitosas + 1 rechazo estructural esperado (ADR-0013)
  resolvieron el bloqueo por completo; `route_board` completó sin que el
  pre-check `DUPLICATE_REFS` se disparara.
- **H2 (discriminación de umbrales)**: **evidencia mixta real** (primer
  punto no-parcial de tres) — cobre bien calibrado, tracks plausible,
  vías mal calibrado para bases pequeñas, DRC estricto-por-tipo
  probablemente necesita distinguir severidad eléctrica de cosmética.

**Escenario aplicado (de los 7 del prompt original de sesión 31):
Escenario 5 — "Aprendizaje metodológico"** (H2 refutada/matizada en el
sentido de "los umbrales, tal como están calibrados, no discriminan bien
en todos los casos"), con elementos del **Escenario 2** ("éxito con matiz
de umbrales" — el flujo en sí generaliza correctamente, sólo los umbrales
cuantitativos de 3 de 4 criterios no calzan). **NO es el Escenario 4**
(aprendizaje por P0/P1) — no hubo ningún hallazgo P0/P1 nuevo esta vez, y
el fix de 31b demostró ser suficiente. Primera validación Nivel A
**cerrada** con conclusión clara: el flujo canónico generaliza
operacionalmente (H1a, H1b confirmadas), pero D-30.3 tal como está
definido necesita revisión antes del cierre de Fase 4 — input formal para
la revisión post-sesión 33, no una acción de esta sesión (D-30.4: fuera
de alcance rediseñar D-30.3 acá).
