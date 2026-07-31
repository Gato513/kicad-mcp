# HackRF One (Great Scott Gadgets) — Validation Suite, Nivel C-01

Primera y ancla del Nivel C (complejidad alta / frontera refutatoria) del
flujo canónico de `kicad-mcp` (sesión 33, Fase 4, D-30.1/D-30.4). Tercer y
último punto de evidencia sobre los umbrales D-30.3 — cierra la trilogía
A ([anavi-dev-mic](../../level-a/anavi-dev-mic/)) + B
([anavi-macro-pad-12](../../level-b/anavi-macro-pad-12/)) + C. Hereda el
template metodológico establecido por Nivel A/B.

## Origen

- **Upstream**: https://github.com/greatscottgadgets/hackrf
  (`hardware/hackrf-one/`).
- **Commit canónico**: `24b53345afb79ebe34129bb68396614ab75f5637`
  ("HackRF One: update version to 10"), branch `main`.
- **Licencia**: **CERN-OHL-P v2** (permisiva) — verificado localmente
  contra el archivo `LICENSE` del propio directorio. **Corrige una
  premisa del prompt de sesión**, que citaba GPL-2/CC-BY (esa combinación
  aplica al firmware/software del proyecto HackRF más amplio, no al
  hardware de `hackrf-one/`, que tiene su propio `LICENSE`).
- **Descripción**: SDR (software-defined radio) de 1 MHz a 6 GHz, USB 2.0,
  MCU + CPLD + frontend RF, 4 capas.

## Admisión (6 criterios, D-33.1 — cada uno con su refutación explícita)

1. **PCB fabricada**: ✅ producto comercial en venta activa por Great Scott
   Gadgets (referencia industrial, featured en KiCad.org "Made with
   KiCad"). Refutación buscada: ¿evidencia más allá del propio repo? Sí —
   es hardware ampliamente distribuido y clonado (7.9k★/1.7k forks),
   citado en publicaciones de seguridad/RF.
2. **Proyecto mantenido**: ⚠️ **matiz, no refutación limpia**. Verificado
   localmente (`git log -- hardware/hackrf-one/`): último commit
   **2023-12-11** (`24b53345`, "update version to 10"), no 2024-02-07 como
   había estimado una verificación remota previa (LLM) — **corrección
   D-33.1**: la fecha remota inicial era incorrecta, la real es aún más
   vieja (~2 años 8 meses al momento de sesión 33). Dispara el trigger de
   ">2 años sin commits sobre hardware" del prompt. **Decisión del
   arquitecto (`AskUserQuestion`, pre-Bloque 0): admitir de todas formas**
   — producto en venta activa, hardware r10 estable, sin necesidad de
   revisión de layout desde entonces. Existe rama `h1r9` (revisión r9) no
   evaluada — fuera de alcance, `main` es la referencia.
3. **Buenas prácticas de KiCad**: ✅ revisión OK — stackup RF documentado
   explícitamente en el `.kicad_pcb` (dieléctricos con espesor real),
   netclasses declaradas (`Default` únicamente — ver "Hallazgo
   estructural" abajo), símbolo custom (`74AUP2G58GU.kicad_sym`) con
   `sym-lib-table`/`fp-lib-table` propios.
4. **Licencia compatible**: ✅ CERN-OHL-P v2 (permisiva) — mejor que lo
   estimado en el prompt.
5. **Esquemático + PCB completos**: ✅, con matiz — **`.kicad_sch` es
   MULTI-HOJA** (`grep -c "(sheet " hackrf-one.kicad_sch` = 3: `baseband`,
   `frontend`, `mcu`). Primera entrada jerárquica de la Suite. **No
   bloquea**: verificado que ni `run_erc()` ni
   `get_world_context(kind="sch")` se usan en el flujo canónico de Nivel
   A/B (grep sobre ambos `validation-report.md`, cero hits) — el flujo va
   por `route_board`/`fill_zones`/etc. contra el **board vivo**
   (`kind="pcb"`), que no tiene noción de jerarquía de esquemático.
6. **DRC 0/0 en el ground truth**: ❌ **NO cumple** — 470 violaciones
   totales en el original (22 `error`, 448 `warning` según el campo
   `severity` del JSON de `kicad-cli`; 0 `unconnected_items`). **Mismo
   precedente sancionado
   que Nivel A/B** (excepción documentada): el desglose (`text_height`
   ×199, `lib_footprint_mismatch` ×199, `lib_footprint_issues` ×23,
   `starved_thermal` ×13, `text_thickness` ×13, `silk_edge_clearance`
   ×13, `footprint_type_mismatch` ×7, `padstack` ×2,
   `nonmirrored_text_on_back_layer` ×1) es mayoritariamente cosmético o
   producto de no tener localmente las librerías custom exactas del
   autor (`lib_footprint_mismatch`/`lib_footprint_issues`, 222/470 = 47%)
   — mismo patrón ya visto en ambos niveles previos. **0 `unconnected_items`
   confirma que el ground truth está 100% ruteado** (no hay indicio de
   que el autor haya dejado nets sin conectar).

## Diversidad D-30.4 (features nuevas de Nivel C)

Contra `validation-suite/reports/coverage-matrix.md` (estado post Nivel B):

- **4 capas de cobre reales** (`F.Cu`≡`C1F`, `In1.Cu`≡`C2`, `In2.Cu`≡`C3`,
  `B.Cu`≡`C4B` — nombres de capa custom del autor, no los canónicos de
  KiCad) — primera entrada de la Suite. **Nota importante para Bloque
  2/3**: en el ground truth, las capas internas concentran la MAYORÍA del
  cobre (`C2` 8182mm², `C3` 7767mm² — más que `C1F`/`C4B` juntas) pero
  casi ningún track de señal (`C2` 29 segmentos, `C3` 15 segmentos, vs.
  `C1F` 2848 y `C4B` 925) — el ground truth mismo usa las capas internas
  casi exclusivamente como **planos**, no para rutear señal. Esto
  recalibra la expectativa de H1b: "0 tracks de señal en capas internas"
  en el output NO sería necesariamente una refutación si el ground truth
  tampoco los tiene.
- **Stackup RF real** con espesores de dieléctrico declarados (prepreg
  0.2104mm ×2, core 1.065mm — total 1.6116mm) — primera vez que la Suite
  ejercita un `.kicad_pcb` con `(stackup ...)` no trivial.
- **Escala**: 437 footprints / 380 nets / 3817 segmentos / 498 vías — ~8×
  Nivel B en nets (48), ~7× en footprints (63). Salto de escala, no
  incremental.
- **Esquemático jerárquico multi-hoja** (3 sub-hojas) — primera vez.
- **Footprints QFN/alta densidad** — MCU (LPC4320) y CPLD en QFN,
  densidad global del ground truth 90.17% (capa `C2`, la de mayor
  cobre) — más denso que Nivel B (63.88% B.Cu).
- **RF**: conectores SMA, antena, frontend de RF con componentes pasivos
  de precisión — régimen no ejercitado por A/B.
- **USB 2.0** (conector propio en el board, a diferencia de A/B donde el
  USB vivía dentro de un módulo XIAO externo) — primera vez con cobre de
  USB propio en la Suite.

**No confirmado como diversidad — refutado antes de ejecutar (D-33.1)**:
netclasses de impedancia. Ver "Hallazgo estructural" abajo.

## Hallazgo estructural (refutación D-33.1, previa a cualquier ejecución)

Verificado localmente contra `hackrf-one.kicad_pro` (`net_settings.classes`):
el ground truth define **una única netclass `Default`**
(track 0.127mm, clearance 0.127mm, vía 0.4572/0.254mm, con
`diff_pair_width`/`diff_pair_gap` poblados pero **sin ninguna asignación
de net** a clases distintas de `Default`). Mismo patrón que **todos** los
proyectos ANAVI verificados en Nivel A/B (BACKLOG P2, "ningún proyecto del
catálogo ANAVI asigna netclasses en la práctica").

⇒ **La sub-hipótesis de H1b "netclasses respetadas" queda refutada por el
propio ground truth, antes de tocar `route_board`.** No es un hallazgo
nuevo sobre el código (ya documentado en BACKLOG P2 desde sesión 32,
"candidato a Nivel C/D si aparece un board con asignación real") — HackRF
One tampoco la ejercita. El control de impedancia de este board es
**geométrico** (anchos de trace dibujados a mano por el autor sobre pistas
específicas, visible en el `.kicad_pcb` como tracks con `width` explícito
distinto del netclass default), no por reglas de netclass — evidencia
directa de que el control de impedancia RF real no pasa por el mecanismo
que `route_board`/`rules_reader.py` ignora. H1b sesión 33 queda acotada a:
uso de capas internas, densidad/escala, USB (conector propio, sin
diff-pair dirigido — ver arriba).

## Migración de formato (primera migración de un sch JERÁRQUICO de la Suite)

- **Original**: `(kicad_pcb (version 20211014) (generator pcbnew))` /
  `(kicad_sch (version 20211123) (generator eeschema))` en las 4 hojas —
  formato nativo de KiCad 6 (2021). Mismas versiones exactas que Nivel B.
- **Procedimiento**: `kicad-cli sch upgrade --force` sobre la hoja raíz
  **no migra las sub-hojas automáticamente** — hallazgo de esta sesión,
  no documentado en el precedente de Nivel B (single-sheet). Se migró
  cada una de las 3 sub-hojas (`baseband.kicad_sch`, `frontend.kicad_sch`,
  `mcu.kicad_sch`) individualmente con el mismo comando, además de
  `kicad-cli pcb upgrade --force` sobre el `.kicad_pcb`.
- **Migrado**: `(version 20260306)` (sch, las 4 hojas) / `(version
  20260206)` (pcb).
- **DRC pre vs. post migración**:

  | | Total | Errores | Warnings | Unconnected |
  |---|---|---|---|---|
  | Original (pre) | 470 | 22 | 448 | 0 |
  | Migrado (post) | 447 | 22 | 425 | 0 |

  Los 22 errores son **idénticos** pre/post (mismo conteo exacto),
  desglosados en `starved_thermal` (13), `footprint_type_mismatch` (7),
  `padstack` (2) — ninguno es `clearance`/`shorting_items`/
  `hole_clearance`/`courtyards_overlap` (las categorías eléctricas/
  estructurales graves de D-32.1); son defectos preexistentes del layout
  del autor, no bugs de conectividad. El descenso de warnings (448→425)
  es enteramente explicado por una **re-etiquetación de reglas** de
  kicad-cli, no por una corrección real:
  `lib_footprint_mismatch` (199 pre) → 0 post, `lib_footprint_issues` (23
  pre) → 199 post (la diferencia neta, -23, es la única variación real;
  todo lo demás —`text_height`, `text_thickness`, `starved_thermal`,
  `silk_edge_clearance`, `footprint_type_mismatch`, `padstack`,
  `nonmirrored_text_on_back_layer`— idéntico pre/post, conteo por conteo).
- **Chequeo de trivialidad (D-33.1 — refutar activamente antes de
  aceptar)**: comparación estructural pre/post vía `pcbnew` directo
  (segmentos, arcos, vías, zonas, keepouts, footprints, nets) — **los 7
  conteos son IDÉNTICOS bit a bit** (3817 segmentos, 0 arcos, 498 vías, 6
  zonas, 3 keepouts, 437 footprints, 380 nets, ambos lados). La migración
  es geométricamente un no-op; el único cambio real es el re-etiquetado
  de 23 violaciones DRC entre dos categorías de librería. **Hipótesis
  "migración trivial" sobrevive el intento de refutación** — se acepta.

## Estado de `working/`

Preparado con `prepare_working.py` sin modificaciones (reutilizado sin
cambios de Nivel A/B): 437 footprints en `(0,0)`, 0 tracks, 0 vías, 0
zonas, 32 dibujos en Edge.Cuts conservados. Verificado con asserts del
propio script (no en silencio).

## Métricas de referencia del ground truth (`gt-measured.json`, schema 1.2)

| Métrica | Valor |
|---|---|
| DRC | 22 errores / 425 warnings (447 total, 0 unconnected) |
| Longitud total de tracks | 9046.949 mm |
| Vías | 498 (100% `through` — sin blind/buried pese a 4 capas) |
| Cobre (unión) | 20345.17 mm² |
| Cobre por capa | C1F 2519.54 · C2 8182.34 · C3 7766.57 · C4B 1876.73 mm² |
| Footprints / Nets | 437 / 380 |
| Densidad (capa máxima / área board) | 90.17% |
| Área del board | 9074.44 mm² |

`drc_errors`/`drc_warnings` del script (22/425) coinciden exactamente con
el campo `severity` crudo de `kicad-cli` post-migración (22 `error` / 425
`warning`) — sin reclasificación, la fusión `violations`+
`unconnected_items` de `_run_drc` es aditiva únicamente.
