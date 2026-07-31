# Sesión 33 — Validation Suite Nivel C-01 (HackRF One)

**Rama:** `sesion/33-validation-C-hackrf-one`, desde `master`
post-merge fast-forward de la secuencia 32b→32c→32d (`08c6fa4`).
**Tipo:** tercera y última validación externa del flujo canónico
(Nivel C, complejidad alta / frontera refutatoria por diseño), cierra
la trilogía A+B+C de la Validation Suite.

## Resumen ejecutivo

**Escenario 6 de 7 — "refutación por escalabilidad"**, explícitamente
válido y de alto valor informativo según el propio prompt de sesión.
`route_board` no completó sobre HackRF One (437 footprints, 380 nets, 4
capas — ~7× la escala de Nivel B): Freerouting 2.1.0 entró en un
régimen de excepciones internas repetidas (`NullPointerException` en
`MazeSearchAlgo.expand_to_target_doors`, 6 ocurrencias distribuidas en
~13 minutos de la corrida de 55, sin ninguna línea de score/progreso en
todo el log) hasta el timeout duro de 3600s acordado con el arquitecto.
Diagnóstico **distinto y más específico** que el de sesión 32 (score
estancado cerca de completar): acá el motor no avanzaba, crasheaba en
loop. Los 4 criterios D-30.3 quedan **no evaluables** (0 tracks, 0
vías) — forzar ratios sobre un output sin ruteo habría sido precisión
falsa sin valor diagnóstico.

**Hallazgo independiente de la sesión (reproducido 3×):**
`add_zone(fill=true)` crashea KiCad de forma determinística en la
3ª-4ª llamada consecutiva sobre este board, sin importar geometría —
se probó overlap total, mitades disjuntas sin overlap, y con delay de
20s entre llamadas, y las 3 veces terminó igual: KiCad caído/colgado y
exactamente 710 zonas fragmentadas (3 reales + 707 sin net) en disco.
La hipótesis inicial (conflicto de fill entre VCC/VAA superpuestas) fue
**refutada explícitamente** por el segundo intento (D-33.1 en acción).
Registrado como `F-V3-ZONE-FILL-CRASH`, P0/P1, no investigado (fuera de
alcance de sesión 33).

**Hallazgo operacional adicional:** el cliente MCP del harness tiene un
idle-timeout (~1818s observado) que puede matar la espera de un tool
call MCP de larga duración (`route_board` con `timeout_s` alto) si no
emite progreso incremental — dejando el proceso servidor muerto y
subprocesses (Freerouting) huérfanos corriendo sin nadie que lea el
resultado. Mitigado con un script driver desacoplado (`nohup`+`disown`)
para el 2º intento. No es un bug de `kicad-mcp`.

**Link al reporte completo:**
`validation-suite/level-c/hackrf-one/validation-report.md`.
**Síntesis de la trilogía A+B+C:**
`docs/analisis/validation-suite-sintesis-A-B-C.md`.

## Desviaciones detectadas vs el prompt de la sesión

1. **3 correcciones a premisas del prompt, verificadas localmente
   (D-33.1) antes de admitir.** Último commit real sobre hardware:
   2023-12-11 (no 2024-02-07, dispara el trigger de mantenimiento — el
   arquitecto decidió admitir igual). Licencia real: CERN-OHL-P v2, no
   GPL-2/CC-BY (mejor de lo esperado). `.kicad_pcb` real: 105600 líneas
   (no ~10227 — ~10× más grande de lo estimado). Ninguna cambió la
   decisión de admisión, pero las 3 habrían llevado a expectativas
   equivocadas sobre alcance y esfuerzo si no se hubieran verificado.
2. **Colocación no siguió el patrón literal "un `move_footprint` por
   turno de conversación"** de A/B — a 437 footprints (~7× Nivel B) era
   impracticable dentro del timebox. Decisión explícita con el
   arquitecto: grid determinístico + script driver. Ver
   `validation-report.md` §Bloque 2 para la justificación completa
   (D-30.3 no puntúa preferencias de colocación).
3. **`test_pcb_session32d_stitching_gui_slow.py` se intentó** (a pedido
   del arquitecto) en vez de quedar como "gate manual pendiente" — pero
   ambos sub-tests fallaron por `KICAD_TIMEOUT` a 600s (timeout
   hardcodeado en el propio test), sin resultado concluyente sobre H1/H2
   de 32d.
4. **El plan de multi-plano (GND+VCC+VAA+USB_SHIELD, replicando el
   ground truth) se abandonó** tras 3 crashes reproducidos — se cerró
   con GND único, mismo alcance que A/B, decisión explícita del
   arquitecto.
5. **Bloque 3 (comparación D-30.3) no pudo ejecutarse como estaba
   diseñado** — sin ruteo, no hay tracks/vías/cobre de señal que
   comparar cuantitativamente. Se documentó como "no evaluable" en vez
   de forzar una tabla de ratios sin sentido.

## Estado de la secuencia de Fase 4

Trilogía A+B+C de la Validation Suite **cerrada** en el sentido de
ejecución completa (las 3 sesiones corrieron de punta a punta con
hallazgos documentados), pero **no en el sentido de 3 puntos numéricos
completos de D-30.3** — Nivel C aporta solo 2/4 criterios evaluables
(ninguno, en rigor: los 4 quedan "no evaluable", no "no cumple"). Ver
`docs/analisis/validation-suite-sintesis-A-B-C.md` para el detalle
completo de qué se puede y no se puede concluir con la evidencia
disponible, y la recomendación formal por umbral.

## Fricciones registradas

- **`F-V3-ZONE-FILL-CRASH`** (P0/P1, nueva, reproducida 3×) —
  `add_zone(fill=true)` crashea KiCad de forma determinística en la
  3ª-4ª llamada sobre boards de esta escala (437 fp), sin correlación
  con overlap geométrico. Ver `validation-report.md` §Fricciones para
  el detalle forense completo de las 3 reproducciones.
- **`F-V3-ROUTER-TIMEOUT-HARD`** (P0, esperado por diseño de Nivel C) —
  Freerouting 2.1.0 crash-loop interno (`NullPointerException`) sobre
  HackRF One, sin progreso medible en 55 min. Diagnóstico específico
  (no "necesitaba más tiempo") disponible en el log de Freerouting.
  Bug upstream, fuera del control de `kicad-mcp`.
- **Idle-timeout del cliente MCP del harness** sobre tool calls largos
  — hallazgo operacional, no un bug de `kicad-mcp`, documentado como
  nota de proceso para sesiones futuras.
- **Mutadores IPC no auto-persisten a disco** (`set_footprint_ref`,
  `move_footprint` vía script) — comportamiento ya documentado
  (D-23.2/ADR-0012) pero primera vez que la Suite lo ejercita fuera del
  pipeline de `route_board`/`fill_zones` — requirió `save_board()`
  explícito antes de que `run_drc()` reflejara los cambios.

## Estado del patrón F-D5-01-B

No aplicable esta sesión — sin ruteo no hay pads huérfanos post-refill
que evaluar contra los guardrails de D-32d.1. El patrón sigue en 1
instancia confirmada (`anavi-macro-pad-12`, sesión 32d), sin nueva
evidencia de sesión 33.

## Análisis H2 — Tercer punto y síntesis A+B+C

Sesión 33 **no cierra numéricamente** el tercer punto de evidencia
sobre D-30.3 (sin ruteo, sin ratios que evaluar sobre tracks/vías/DRC).
Sí aporta:

1. **Confirmación 3/3 de D-32.1** (criterio DRC por severidad) — incluso
   en el caso límite de "board sin rutear", la tabla por severidad dio
   lectura correcta (0 eléctricos/estructurales nuevos más allá de lo
   esperado) donde el criterio literal habría marcado "555 errores,
   fail" sin matiz. Recomendación: formalizar D-32.1 como parte
   permanente del criterio DRC de D-30.3.
2. **Dimensión nueva validada** (descomposición por capa, schema 1.2 de
   `measure_ground_truth.py`) — reveló, incluso solo desde el ground
   truth, que HackRF One usa sus capas internas casi exclusivamente
   como planos (29-15 segmentos de señal vs 2848-925 en las externas).
   Señal real que un ratio de cobre global no habría expuesto.
3. **El diagnóstico de umbral de vías** (31c/32) queda sin 3er punto —
   Nivel C tenía la base más grande de la serie (498 vías en el ground
   truth) pero la refutación de H1 se llevó puesta esa oportunidad.

Detalle completo, tabla comparativa de los 3 puntos, y recomendación
formal por umbral (mantener/ajustar/formalizar) en
`docs/analisis/validation-suite-sintesis-A-B-C.md`.

## Recomendación formal para D-30.3 revisada

Ver `docs/analisis/validation-suite-sintesis-A-B-C.md` §Recomendación
formal por umbral. Resumen: **mantener** tracks (±30%) y cobre (±25%)
sin evidencia contradictoria; **revisar con cautela, no urgente** vías
(±20%, evidencia insuficiente/borde); **formalizar** el criterio DRC
por severidad (D-32.1) como parte permanente, no matiz opcional (3/3
confirmado); **incorporar** la descomposición por capa como métrica
auxiliar obligatoria para boards de 3+ capas (1 punto de evidencia,
señal real, sin base todavía para umbral pass/fail).

## Gates de cierre

- Suite offline + integration: verdes.
- `ruff`/`mypy`: limpios.
- Gate GUI: `test_pcb_session21_hole_clearance_gui.py` 2/2,
  `test_pcb_session27_zone_persist_gui.py` 2/2,
  `test_pcb_session24_route_board_persist_gui.py` 1/1 — todos verdes.
  `test_pcb_session32d_stitching_gui_slow.py` intentado, no concluyente
  (timeout de 600s hardcodeado en el test).
- Commit convencional en la rama. **Sin push.**
- `AskUserQuestion` al arquitecto antes de mergear.

## Próxima sesión

**34 = preparación release OSS**, con la salvedad de que
`F-V3-ZONE-FILL-CRASH` y el crash-loop de Freerouting 2.1.0 quedan
como candidatos a investigación intermedia si reaparecen antes del
release (mismo criterio que F-D5-01-B: reproducciones múltiples son
evidencia suficiente para registrar y priorizar, no para bloquear el
ciclo actual). La revisión formal de D-30.3 con los 3 puntos de
evidencia queda pendiente de decisión del arquitecto sobre la síntesis
en `docs/analisis/validation-suite-sintesis-A-B-C.md`.
