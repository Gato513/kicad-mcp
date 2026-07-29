# ANAVI Macro Pad 12 — Validation Suite, Nivel B-01

Primera validación de Nivel B (complejidad media) del flujo canónico de
`kicad-mcp` (sesión 32, Fase 4, D-30.1/D-30.4). Segundo de tres puntos de
evidencia sobre los umbrales D-30.3 (el primero fue Nivel A-01, sesión
31→31b→31c). Hereda el template metodológico establecido por Nivel A-01.

## Origen

- **Upstream**: https://github.com/AnaviTechnology/anavi-macro-pad-12
- **Commit canónico**: `0d3e1be82352e1ebd58966d3fda7a9cdf9e1d509`
  (2025-12-07, branch `main` — única rama existente en el upstream, no hay
  `master`).
- **Licencia**: CC BY-SA 4.0 (declarada en el `README.md` del repo
  upstream; el campo `license` de la API de GitHub es `null` — mismo
  patrón no-normativo ya visto en Nivel A, admitido igual).
- **Descripción**: "Mini hot-swappable mechanical keyboard with 12 Cherry
  MX compatible switches, translucent key caps, USB-C, RP2040
  microcontroller, mini OLED display, backlighting and under lighting."

## Historial de selección de candidato (sesión 32)

El candidato prescrito por el prompt de sesión 32 era **ANAVI Miracle
Emitter**. Se descartó en el Bloque 0 tras verificación directa (fetch del
repo real, no sólo el prompt) por **dos motivos simultáneos**:

1. **No aporta la diversidad D-30.4 prometida por el prompt**: sin
   footprint USB-C (el USB-C vive en el módulo XIAO, no en cobre propio),
   sin nets D+/D− diferenciales, sin footprint WS2812B (la tira es
   externa vía `TerminalBlock_Phoenix`). El "ESP32-C3 vs ESP8266 del
   Nivel A" del prompt también era falso: Nivel A nunca usó ESP8266, y el
   footprint de Miracle Emitter es un carrier XIAO genérico, misma familia
   que el XIAO RP2040 de `anavi-dev-mic`.
2. **No alcanza escala de Nivel B**: 15 footprints / 19 nets / 2 capas —
   igual o menor escala que Nivel A (13 footprints / 20 nets / 2 capas).

Verificado con el arquitecto (`AskUserQuestion`, pre-sesión) tras
enumerar la evidencia de código (ver más abajo, "Hallazgo estructural"),
y confirmado explícitamente: activar candidato de respaldo.

| Candidato | Resultado |
|---|---|
| anavi-miracle-emitter (prescrito) | Descartado — sin diversidad real, escala menor que Nivel A |
| **anavi-macro-pad-12** | **Seleccionado** — ver abajo |
| mod-audio/cc-hw-arduino-shield | Respaldo #2 no evaluado (macro-pad-12 admitido en primer intento) |
| anavi-thermometer(-mini) | Respaldo #3, ya usado como respaldo de Nivel A en sesión 31 |

## Admisión (6 criterios, hoja-de-ruta-v5)

1. **PCB fabricada**: ✅ crowdfunded en Crowd Supply (2023), OSHWA
   certificado, disponible en venta en Crowd Supply / Tindie / LectronZ.
   Evidencia externa al repo (no sólo autodeclarada).
2. **Proyecto mantenido**: ✅ actividad 2023-01-30 → 2025-12-07 (~2 años),
   9 commits, no archivado.
3. **Buenas prácticas de KiCad**: revisión OK — netclasses explícitas
   (`Default`/`usb`/`vcc`, mismo patrón que Nivel A: declaradas pero sin
   asignación — `netclass_assignments`/`netclass_patterns` ausentes,
   `"nets": []` en `usb`/`vcc`).
4. **Licencia compatible**: ✅ CC BY-SA 4.0.
5. **Esquemático + PCB completos**: ✅ `.kicad_sch` nativo single-sheet
   (`grep -c "(sheet "` = 0) + `.kicad_pcb` (formato pre-migración
   KiCad 6).
6. **DRC 0/0 en el ground truth**: ❌ **NO cumple** — 179 violaciones
   totales en el original (23 `error`, 156 `warning`). **Mismo precedente
   sancionado que Nivel A** (excepción documentada, sesión 31): los
   defectos (`solder_mask_bridge` ×12, `silk_over_copper` ×111,
   `lib_footprint_mismatch` ×41, etc.) son preexistentes al layout del
   autor — `working/` arranca sin cobre ni colocación, no se propagan al
   output medido en Bloque 2/3.

## Diversidad D-30.4 (features nuevas de Nivel B)

Contra `validation-suite/reports/coverage-matrix.md` (estado post Nivel
A-01):

- **Matriz de teclas con diodo por tecla** — topología en malla (12
  switches × 12 diodos), patrón ausente en despertador y en Nivel A
  (ninguno tiene más de un punto de entrada por señal digital).
- **Backlighting por tecla** (12 LED + 12 resistor, 1:1 con cada switch)
  — patrón de "N instancias del mismo sub-circuito" no visto antes.
- **Footprints hot-swap** (`keyswitches:Kailh_socket_MX`, ×12) — familia
  de footprint nueva.
- **Migración de formato KiCad real** (6→10, ver abajo) — Nivel A ya era
  nativo KiCad 10 (sin necesidad de migrar); ésta es la primera migración
  real de la Suite.
- **Escala**: 63 footprints / 48 nets — ~3× Nivel A (13/20), primera
  entrada de la matriz en el rango "complejidad media".
- **Base de vías grande** (30, medidas en el ground truth) — Nivel A
  tenía sólo 2, diagnosticado en 31c como "umbral de vías mal calibrado
  para bases pequeñas" (H2). Macro Pad 12 es la primera oportunidad real
  de poner a prueba ese diagnóstico contra una base no trivial.

**No confirmado como diversidad**: el README dice "USB-C" y "RP2040", pero
ambos viven dentro del módulo XIAO (carrier genérico `Seeeduino
XIAO-MOUDLE14P-2.54-21X17.8MM`) — no hay cobre propio de USB-C en este
board, igual que en Nivel A. Se verifica en Bloque 2 si aparece algún par
diferencial en el conector `Connector_PinHeader_2.54mm` o si es
irrelevante (ver "Hallazgo estructural" abajo).

## Hallazgo estructural (independiente del candidato, condiciona H1b)

Verificado antes de admitir cualquier candidato:

1. **`src/kicad_mcp/bridge/rules_reader.py:217`** (`_extract_classes`) lee
   sólo `clearance`/`track_width`/`via_diameter`/`via_drill` de cada
   netclass del `.kicad_pro` — **descarta silenciosamente**
   `diff_pair_width`/`diff_pair_gap`/`diff_pair_via_gap`.
   `route_board` (`tools/pcb.py:2578`) sólo acepta `max_passes`,
   `timeout_s`, `refill` — ningún parámetro de netclass o par
   diferencial. Grep de `diff_pair|differential|impedance` sobre `src/` y
   `tests/`: cero hits.
2. **Ningún proyecto ANAVI verificado (dev-mic, miracle-emitter,
   word-clock, macro-pad-12) asigna netclasses** — todos comparten el
   mismo template de KiCad con clases `Default`/`usb`/`vcc` declaradas y
   `"nets": []`.

⇒ La rama "diff-pair dirigido por netclass" de H1b es inejecutable por
construcción del código, independientemente de qué placa ANAVI se elija.
Registrado como ítem de BACKLOG (P2/P3), no como fricción de esta sesión.

## Migración de formato

- **Original**: `(kicad_pcb (version 20211014) (generator pcbnew))` /
  `(kicad_sch (version 20211123) (generator eeschema))` — formato nativo
  de KiCad 6 (2021).
- **Migrado**: `kicad-cli sch upgrade --force` + `kicad-cli pcb upgrade
  --force` → `(version 20260306)` (sch) / `(version 20260206)` (pcb),
  `generator_version "10.0"`.
- **DRC pre vs. post migración**:

  | | Total | Errores | Warnings |
  |---|---|---|---|
  | Original (pre) | 179 | 23 | 156 |
  | Migrado (post) | 175 | 19 | 156 |

  El post es **subconjunto estricto** del pre: los 4 errores
  `invalid_outline` del original desaparecen por completo tras la
  migración (resolución de arcos del contorno mejorada entre KiCad 6 y
  10) y **ningún tipo de violación nuevo aparece**. Regla de decisión del
  Bloque 0: `pre≠0/0` → aplica el mismo precedente sancionado de Nivel A
  (criterio 6, arriba); el caso es incluso más cómodo que Nivel A (que
  tuvo DRC idéntico bit a bit) porque acá la migración además **redujo**
  violaciones sin introducir ninguna categoría nueva.

## Reglas de diseño del autor (heredadas en `working/`)

- `min_clearance`: 0mm (piso del motor) · `min_track_width`: 0.2mm ·
  `min_via_diameter`: 0.4mm · `min_through_hole_diameter` (drill): 0.3mm ·
  `min_hole_to_hole`: 0.25mm · `min_copper_edge_clearance`: 0.025mm.
- Netclasses: `Default` (clearance 0.25mm, track 0.5mm, via 0.85/0.4mm,
  diff_pair 0.2/0.25mm), `usb` (clearance 0.254mm, track 0.254mm,
  `"nets": []`), `vcc` (clearance 0.254mm, track 1.5mm, `"nets": []`) —
  idéntico patrón de "perfiles declarados, no aplicados" que Nivel A.
- 2 capas de cobre (F.Cu/B.Cu).

## Estructura de este directorio

- `ground-truth-original/` — copia intacta del repo upstream en el commit
  canónico (sin `.git`). **Nunca se sobrescribe.**
- `ground-truth-kicad10/` — copia migrada a formato nativo KiCad 10
  (`kicad-cli sch/pcb upgrade --force`). Es la referencia contra la que
  se miden los 4 criterios D-30.3 en el Bloque 3.
- `working/` — copia de `ground-truth-kicad10/` con el `.kicad_pcb`
  reducido al estado inicial del flujo canónico: 0 tracks, 0 vías, 0
  zonas, los 63 footprints movidos a `(0,0)`. Preparado con
  `validation-suite/tools/prepare_working.py`.
- `gt-measured.json` — salida cruda de `measure_ground_truth.py` (schema
  1.1) sobre `ground-truth-kicad10/`. Primera vez que la Suite committea
  el JSON crudo además de transcribirlo a `metrics.md` (Nivel A no lo
  hizo).
- `metrics.md` — ground truth + output medidos, ratios D-30.3, análisis
  por-net, tabla DRC por severidad, M1/M2/M3, análisis H2.
- `validation-report.md` — reporte completo de la validación.

## Ground truth medido (ver `metrics.md` para el detalle completo)

Medido con `validation-suite/tools/measure_ground_truth.py` (schema 1.1,
extendido en sesión 32) sobre `ground-truth-kicad10/anavi-macro-pad-12.kicad_pcb`:

- DRC: 19 errores / 156 warnings (excepción documentada arriba;
  `drc_by_rule`: `solder_mask_bridge` 12, `starved_thermal` 1,
  `footprint_type_mismatch` 6, `silk_over_copper` 111, `text_thickness` 1,
  `text_height` 1, `lib_footprint_mismatch` 41, `lib_footprint_issues` 2)
- `total_track_length_mm`: 2512.2617
- `via_count`: **30** (vs 2 de Nivel A — base grande, ver análisis H2 en
  `metrics.md`)
- `copper_area_mm2`: 8710.4053 (método `union`, sin `method_notes`)
- `footprint_count`: 63 · `net_count`: 48 · `board_area_mm2`: 8532.8488 ·
  `density_pct`: 63.88
- `orphan_vias`: 0 (ground truth sano, sin vías huérfanas — baseline para
  el chequeo del Bloque 2)
