# Métricas — ANAVI Dev Mic (Validation Suite Nivel A-01, sesión 31)

Medidas con `validation-suite/tools/measure_ground_truth.py` (pcbnew
10.0.4 del sistema, `/usr/bin/python3`). Ver ese script para la
documentación completa de cada métrica (qué mide, qué asume, qué excluye).

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

## Output (kicad-mcp, sesión 31) — INCOMPLETO, Bloque 2 bloqueado en `route_board`

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

## Comparación

**No aplicable — no hay output que comparar.** Los 4 criterios D-30.3 no
se pudieron evaluar: el DRC del output no es el DRC final (ruteo nunca
corrió), y `total_track_length_mm`/`via_count`/`copper_area_mm2` del
output no existen. H1 (generalización del flujo canónico) queda **sin
veredicto** — no refutada ni confirmada, simplemente no llegó a medirse.

## Métricas auxiliares

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

## Análisis H2

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
