# ANAVI Dev Mic — Validation Suite, Nivel A-01

Primera validación externa del flujo canónico de `kicad-mcp` sobre una
placa ajena al fixture "despertador" (sesión 31, Fase 4, D-30.1 a D-30.5).
Establece el template metodológico de la Validation Suite que las
sesiones 32-33 reutilizan.

## Origen

- **Upstream**: https://github.com/AnaviTechnology/anavi-dev-mic
- **Commit canónico**: `f742ae039ca00939cc542bea7a7982de9818d564`
  (2024-10-23, branch `main`)
- **Licencia**: CC BY-SA 4.0 (declarada en el README del repo upstream,
  compatible con inclusión en la Validation Suite — requiere atribución a
  http://www.anavi.technology, sin restricciones adicionales).
- **Descripción**: "Open source USB-C computer microphone with XIAO
  module and Raspberry Pi RP2040 microcontroller."

## Historial de selección de candidato (sesión 31)

El candidato originalmente prescrito por el prompt de sesión 31 era
`anavi-light-controller`. Se descartó en el Bloque 0 tras verificar que su
`.kicad_pcb` está en formato KiCad 4 (`(version 4) (host pcbnew
4.0.6+dfsg1-1)`), con esquemático legacy (`.sch`/`.pro`/`-cache.lib`/
`-rescue.lib`) y último commit 2018-11-03 — falla el criterio de admisión
2 (proyecto mantenido) literalmente, y la migración a KiCad 10 tiene
viabilidad incierta.

Se evaluaron 6 candidatos del catálogo público de ANAVI Technology antes
de converger en `anavi-dev-mic` (ver `docs/historico/sesiones/31-reporte.md`
para el detalle completo de cada uno):

| Candidato | Resultado |
|---|---|
| anavi-light-controller | KiCad 4/legacy, 2018 — descartado (criterio 2) |
| anavi-rtc-3032 | DRC 0/0, KiCad 10 nativo — descartado (criterio 1: sin evidencia de fabricación física en repo/blog/tienda) |
| anavi-handle | README dice "próxima campaña" (fabricación NO confirmada pese a resumen previo ambiguo) + 12 `solder_mask_bridge` — descartado (criterios 1 y 6) |
| **anavi-dev-mic** | **Seleccionado** — ver abajo |
| anavi-info-uhat | KiCad 5, `kicad-cli` ni pudo cargar el `.kicad_pcb` — descartado |
| anavi-thermometer | KiCad 5, legacy `.sch`, 2020 — descartado |

## Admisión (6 criterios, hoja-de-ruta-v5)

1. **PCB fabricada**: ✅ confirmado por el propio README del repo upstream
   ("ANAVI Dev Mic was successfully funded through a crowdfunding campaign
   at Crowd Supply on September 26, 2024") + foto del board ensamblado en
   `images/anavi-dev-mic.jpg`. Evidencia de primera mano, no inferida.
2. **Proyecto mantenido**: ✅ último commit 2024-10-23 (repo activo dentro
   de un horizonte razonable).
3. **Buenas prácticas de KiCad**: revisión visual OK — netclasses
   explícitas (`Default`/`usb`/`vcc`), un único warning ERC
   (`lib_symbol_mismatch` en `BT1`, benigno — mismo patrón que D-19b.1 de
   nuestro propio proyecto).
4. **Licencia compatible**: ✅ CC BY-SA 4.0.
5. **Esquemático + PCB completos**: ✅ `.kicad_sch` nativo (single-sheet,
   `grep -c "(sheet "` = 0) + `.kicad_pcb` (formato pre-migración KiCad 6,
   ver abajo).
6. **DRC 0/0 en el ground truth**: ❌ **NO cumple** — 43 violaciones
   totales (18 `error`: 17 `solder_mask_bridge` + 1 `starved_thermal`; 25
   `warning`: 12 `lib_footprint_mismatch`, 10 `silk_over_copper`, 2
   `text_height`, 1 `text_thickness`). **Excepción documentada, aprobada
   explícitamente por el arquitecto** (AskUserQuestion, sesión 31): los
   errores son preexistentes al layout del autor (mismo router/colocación
   que se fabricó y funciona en el hardware real), no algo introducido por
   nuestro flujo — `working/` arranca sin cobre ni colocación, así que
   estos defectos del ground truth **no se propagan** al output medido en
   Bloque 2/3. La comparación D-30.3 (Bloque 3) es sobre longitud de
   tracks / vías / área de cobre del ground truth, métricas que
   `solder_mask_bridge`/`starved_thermal` no distorsionan de forma
   material.

   Dato para el reporte: la clase de defecto (`solder_mask_bridge`) es la
   misma que investigamos internamente en sesiones 26/30 (D-30.5, P1
   ANT1) — su aparición en una placa real y fabricada por un tercero es
   evidencia externa de que es un gotcha genuino y no exclusivo de
   nuestras propias herramientas.

## Migración de formato

- **Original**: `(kicad_pcb (version 20211014) (generator pcbnew))` /
  `(kicad_sch (version 20211123) (generator eeschema))` — formato nativo
  de KiCad 6 (2021), **no legacy**: es una migración normal hacia
  adelante, sin símbolos rescatados ni bibliotecas `-cache.lib` en juego
  para el PCB/SCH principales (el repo trae un `.sch`/`.sch-bak` legacy
  residual sin usar, ignorados).
- **Migrado**: `kicad-cli sch upgrade --force` + `kicad-cli pcb upgrade
  --force` → `(version 20260306)` / `(version 20260206)`,
  `generator_version "10.0"`.
- **DRC pre vs. post migración**: **idéntico bit a bit** — 43 violaciones
  en ambos casos, mismos tipos y conteos exactos (17 `solder_mask_bridge`,
  1 `starved_thermal`, 12 `lib_footprint_mismatch`, 10 `silk_over_copper`,
  2 `text_height`, 1 `text_thickness`). La migración no introdujo ni
  resolvió ningún defecto — regla de decisión del Bloque 0 satisfecha
  (`DRC(original) == DRC(migrado)`, aunque ninguno sea 0/0; ver excepción
  del criterio 6 arriba).

## Reglas de diseño del autor (heredadas en `working/`)

- `pad_to_mask_clearance`: 0.2mm
- `min_track_width`: 0.2mm · `min_clearance`: 0mm (piso del motor, no la
  regla efectiva — ver netclasses)
- `min_via_diameter`: 0.4mm · `min_through_hole_diameter` (drill): 0.3mm
- Netclasses: `Default` (clearance 0.25mm, track 0.5mm, via 0.85/0.4mm),
  `usb` (clearance 0.254mm, track 0.254mm), `vcc` (clearance 0.254mm,
  track 1.5mm) — sin asignación explícita de nets a `usb`/`vcc` en el
  archivo (`"nets": []`), quedan como perfiles disponibles no aplicados.
- 2 capas de cobre (F.Cu/B.Cu).

## Estructura de este directorio

- `ground-truth-original/` — copia intacta del repo upstream en el commit
  canónico. **Nunca se sobrescribe.**
- `ground-truth-kicad10/` — copia migrada a formato nativo KiCad 10
  (`kicad-cli sch/pcb upgrade --force`). DRC idéntico al original (ver
  arriba). Es la referencia contra la que se miden los 4 criterios D-30.3
  en el Bloque 3.
- `working/` — copia de `ground-truth-kicad10/` con el `.kicad_pcb`
  reducido al estado inicial del flujo canónico: 0 tracks, 0 vías, 0
  zonas, los 13 footprints movidos a `(0,0)` (decisión explícita del
  arquitecto en sesión 31 — literal, no una grilla prolija). Preparado
  con `validation-suite/tools/prepare_working.py`.
- `metrics.md` — ground truth + output medidos, ratios D-30.3, M1/M2/M3,
  análisis H2.
- `validation-report.md` — reporte completo de la validación (template
  para sesiones 32-33).

## Ground truth medido (ver `metrics.md` para el detalle completo)

Medido con `validation-suite/tools/measure_ground_truth.py` sobre
`ground-truth-kicad10/anavi-dev-mic.kicad_pcb`:

- DRC: 18 errores / 25 warnings (excepción documentada arriba)
- `total_track_length_mm`: 242.8531
- `via_count`: 2
- `copper_area_mm2`: 1556.7385 (unión por capa: F.Cu 706.816 + B.Cu
  849.9225)
- `footprint_count`: 13 · `net_count`: 20 · `board_area_mm2`: 1210.9775
