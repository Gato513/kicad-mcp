# Sesión 32d — Fix: stitching automático de pads huérfanos (F-D5-01)

**Rama:** `sesion/32d-fix-orphan-pads-zone-nets`, desde `master` tras
fast-forward a `9746dbe` (tip de `sesion/32c-investigacion-f-d5-01` —
`master` no tenía mergeado ni 32b ni 32c al arrancar; precondición
verificada al inicio, resuelta con fast-forward limpio en vez de
encadenar una 4ª rama, cortando la deuda de encadenamiento observada en
31c/32b/32c).

**Tipo:** aplicación del fix con la investigación de sesión 32c
(`docs/investigacion/32c-f-d5-01.md`) como input completo. Mecanismo raíz
ya aislado y confirmado causalmente — esta sesión no re-investiga el
mecanismo.

## Resumen ejecutivo

**Fix implementado y verificado parcialmente** (escenario de éxito #2 del
prompt: fix acotado y bien verificado, con una hipótesis (H1) que se
re-baselineó a mitad de sesión por evidencia geométrica, y con la
verificación end-to-end contra el motor real escrita pero pendiente de
ejecución humana). `route_board` ahora detecta pads GND huérfanos tras el
refill final y stitchea automáticamente una vía (`add_via`) cuando 5
guardrails geométricos estrictos se cumplen; si algún guardrail rechaza,
el pad se expone en el payload (`orphan_pads`) sin levantar error.

**Hallazgo que corrigió una premisa del prompt de sesión** (documentado
abajo en detalle, ver §"Auto-corrección"): las 3 manifestaciones de
F-D5-01 no comparten la misma topología de capas. `anavi-macro-pad-12`
resultó estructuralmente distinta de las otras dos — el fix la cierra
parcialmente (mediante rechazo correcto de guardrail, no mediante
stitching). H1 se re-baselineó de `anavi-macro-pad-12` a `anavi-dev-mic`
con aprobación explícita del arquitecto antes de escribir código.

## Auto-corrección a mitad de sesión: H1 no puede basarse en macro-pad-12

Antes de escribir el plan de implementación, se inspeccionó
geométricamente (parser propio sobre los `.kicad_pcb`, sin leerlos al
contexto — point-in-polygon + distancias reales) la topología de capas de
las 3 manifestaciones:

| Manifestación | Capa del pad huérfano | Zonas de cobre GND | ¿Vía viable? |
|---|---|---|---|
| despertador (s25) | — | F.Cu + B.Cu | ✓ (por eso el `add_via` manual de s25 funcionó) |
| dev-mic `MK1.3` (s31c) | F.Cu | B.Cu únicamente | ✓ — relleno GND B.Cu vivo justo bajo el centro del pad (confirmado con point-in-polygon real) |
| macro-pad-12 `J4.3`/`J5.3` (s32) | B.Cu | **B.Cu únicamente** (1 zona de cobre real; las otras 67 son keepouts `__kicadmcp_hc__`) | ✗ **estructuralmente imposible** |

En macro-pad-12 el pad y el plano están en la MISMA capa — no hay cobre
GND en F.Cu. Una vía pasante ahí uniría B.Cu (relleno retraído por el
clearance del track `+5V` que 32c aisló como causal) con F.Cu (sin cobre
GND): no conectaría nada, sólo agregaría una vía dangling. El troncal
`+5V` causal está él mismo en B.Cu — un estrangulamiento **lateral, en la
misma capa**, que ninguna vía remedia.

Esto se reportó al arquitecto vía `AskUserQuestion` antes de escribir
código (patrón sesión 32c, corrección de premisa reportada de inmediato).
Decisión: **H1 se re-baseline a `anavi-dev-mic`** (topología "capas
opuestas", la que el guardrail #4 fue diseñado para aceptar); D1-D3 se
implementan tal cual estaban especificadas; macro-pad-12 pasa a ser el
caso canónico de H2 (rechazo correcto de guardrail) en vez de H1.
Confirmado con `AskUserQuestion`.

## Análisis comparativo obligatorio de D1-D3

### D1 — Stitching automático vs exposición explícita

**Elegida:** automático con guardrails estrictos, fallback a exposición.

**Alternativa A (sólo exposición) descartada porque:** convierte cada net
huérfano en trabajo manual — el precedente de sesión 25 (`add_via` manual)
ya demostró que la automatización es una mitigación real, y el análisis
geométrico de esta sesión confirmó que el guardrail #4 discrimina
correctamente entre casos seguros (dev-mic) e inseguros (macro-pad-12) sin
intervención humana.

**Alternativa B (automático sin guardrails) descartada porque:** habría
intentado stitchear macro-pad-12 de todas formas — el test
`test_no_stitching_when_no_opposite_layer_zone` (canario unit) demuestra
exactamente el caso que un guardrail relajado habría fallado en detectar:
crear una vía B.Cu↔F.Cu sin cobre GND real en F.Cu.

**Por qué la elegida explica mejor:** el análisis geométrico de esta
sesión (tabla arriba) es evidencia directa de que "automático" y "seguro"
no son la misma pregunta para las 3 manifestaciones — se necesitaban
AMBAS piezas (auto-stitching + guardrail) para no sobre-generalizar desde
2/3 casos observados.

### D2 — Momento del stitching en el pipeline

**Elegida:** dentro de `route_board`, post-refill final, pre-return.

**Alternativa A (tool separada `stitch_orphan_pads`) descartada porque:**
duplicaría la responsabilidad de invocación en el llamador y es un patrón
anti-arquitectural para OSS (tool nueva por síntoma). Confirmado en la
práctica: el punto de inserción natural resultó ser exactamente donde
D-23.2 ya mide `post_report` — reutilizar ese punto (en vez de crear una
fase nueva) permitió DRY real (ver §"Refactor" abajo), algo que una tool
separada no habría permitido sin duplicar el bloque refill+enforce+save.

**Alternativa B (fase `refill_with_stitching` separada) descartada
porque:** habría duplicado el contrato D-23.2 sin ganancia semántica —
confirmado en la implementación: el bloque de re-persist post-stitching
es literalmente el MISMO pipeline (`refill_zones`+`enforce_hole_clearance`
+`save_board`) que el refill de seguridad original, ahora extraído a un
único helper `_refill_enforce_and_save` compartido por ambos call sites.

**Por qué la elegida explica mejor:** el hecho de que el refactor DRY
resultara natural (mismo pipeline, dos invocaciones) es evidencia a
posteriori de que "dentro de route_board, mismo punto" era la
descomposición correcta — una tool o fase separada habría forzado esa
duplicación en vez de revelarla como código compartible.

### D3 — Guardrails y semántica ante fallo

**Elegida:** 5 condiciones estrictas (huérfano; net con zona propia; pad
dentro del outline de esa zona; zona del mismo net en la capa OPUESTA;
región inmediata libre de cobre ajeno en esa capa opuesta), rechazo =
exposición sin error.

**Alternativa A (guardrail relajado, sólo condiciones 1-2) descartada
porque:** sin la condición 4 (capa opuesta), habría intentado stitchear
macro-pad-12 y creado una vía dangling — exactamente el escenario que el
análisis geométrico de esta sesión reveló como estructuralmente
imposible. El test `test_no_stitching_when_no_opposite_layer_zone` usa
la geometría REAL de macro-pad-12 (pad B.Cu, zona GND B.Cu, sin F.Cu) y
confirma el rechazo.

**Alternativa B (guardrail con DRC re-run post-stitching) descartada
por costo:** un `run_drc()` completo (~decenas de ms a segundos vía
`kicad-cli`) por cada pad candidato es caro comparado con la verificación
geométrica local (condición 5, radio 1mm) que ya cubre el caso observado.
Diferida a sesión futura si aparece evidencia de falsos positivos del
guardrail geométrico.

**Por qué la elegida explica mejor:** las 5 condiciones, evaluadas contra
la geometría real de ambos fixtures (no sólo contra fixtures sintéticos),
produjeron el resultado correcto en ambos casos sin ajuste adicional —
evidencia de que el guardrail generaliza más allá del caso que lo motivó.

**Semántica ante fallo (confirmada en implementación):** rechazo de
guardrail → `orphan_pads` con `reason`, nunca error (D-32d.2). Fallo
técnico de `add_via` → código existente, sin reintento (D-07.1). Fallo de
`save_board()` en el re-persist post-stitching → `POST_ROUTE_PERSIST_FAILED`
(código existente de sesión 24, reutilizado — no se agregó ningún código
nuevo).

## Refactor DRY no planificado: `_refill_enforce_and_save`

El primer borrador del bloque de re-persist post-stitching duplicaba
literalmente el bloque `refill_zones`+`enforce_hole_clearance`+
`save_board`+manejo de `POST_ROUTE_PERSIST_FAILED` que ya existía para el
refill de seguridad D-23.2 original. Se extrajo un helper compartido
(`_refill_enforce_and_save`, parametrizado con `context: str` para el
mensaje de error) usado por AMBOS call sites. Motivado por la vara de
diseño de <100 líneas efectivas del prompt (`docs/historico/prompts/
PROMPT-SESION-32d-fix.md`): el diff de `pcb.py` llegó a 238 líneas antes
del refactor; el refactor no redujo el conteo bruto (el helper agrega su
propio bloque con docstring), pero eliminó una duplicación de lógica real
— valor de mantenibilidad, no de line-count.

**Diff final honesto:** `src/kicad_mcp/tools/pcb.py` quedó en ~267 líneas
insertadas / ~185 "efectivas" (código, sin contar comentarios/docstrings/
blancos) — por encima de la vara de <100 y del presupuesto de ~110
estimado en el plan. Reportado sin ocultar: la sobre-ejecución se explica
íntegramente por (a) la evaluación de 5 guardrails geométricos (D3,
aprobada explícitamente por el arquitecto, ~70 líneas) y (b) la
re-medición D-23.2-compliant post-stitching (aprobada explícitamente vía
`AskUserQuestion` antes de escribir código, ~15 líneas netas tras DRY).
Ninguna de las dos partes es recortable sin retroceder una decisión ya
tomada con el arquitecto.

## Implementación

- `src/kicad_mcp/tools/pcb.py`: `_point_in_polygon`, `_match_orphan_pad`,
  `_opposite_layer_blocked`, `_orphan_pad_dict`, `_stitched_via_dict`,
  `_evaluate_stitch_candidates` (lógica pura, testeable sin IPC) +
  `_refill_enforce_and_save` (compartido) + integración en `route_board`
  (detección post-refill, stitching, re-persist condicional, 2 claves
  nuevas de payload).
- `docs/specs/tool-catalog.md`: contrato de `stitched_vias`/`orphan_pads`
  documentado (DoD #3).
- `docs/adr/0012-route-board-persist-contract.md`: extensión
  §"F-D5-01 stitching (sesión 32d)" — precedente sesiones 27/32b, no ADR
  nuevo.

## Verificación

**Unit (canario permanente, 8/8 verde):**
`tests/test_pcb_session32d_orphan_pads_stitching_canary.py` — cada
guardrail individualmente (con la geometría REAL de macro-pad-12 replicada
para el guardrail #4), exposición mixta, H4 (camino feliz, cero costo),
re-medición de `err_post` post-stitching. Suite offline completa:
**392 passed, 39 skipped** (0 regresiones). `ruff check`/`ruff format
--check`/`mypy src/` limpios en todo el proyecto.

**Integration (motor real, sin GUI):** `pytest -m integration` — **29/29
verde**, dos corridas independientes, sin flakiness observada.

**Verificación pendiente (honesta, no oculta): GUI-slow contra el motor
real.** `tests/test_pcb_session32d_stitching_gui_slow.py` (marker
`integration_gui_slow`) implementa H1 (`anavi-dev-mic`: `route_board`
debe stitchear `MK1.3` y dejar `unconnected == 0`) y H2
(`anavi-macro-pad-12`: `route_board` NO debe stitchear `J4.3`/`J5.3`,
deben aparecer en `orphan_pads` con la razón correcta). **Escritos pero
NO corridos por el agente esta sesión** — el protocolo de este proyecto
para tests `integration_gui`/`integration_gui_slow` requiere que un
humano abra físicamente el proyecto objetivo en el PCB Editor de KiCad
antes de correr la suite (`docs/guias/pruebas-gui.md`: "No hay
automatización posible del 'abrir el proyecto en KiCad' para el MVP").
Confirmado con un probe directo por IPC en esta sesión: con KiCad
corriendo (socket presente) pero sin ningún PCB Editor en foco,
`get_open_board()` devuelve `KICAD_CLI_FAILED`
(`ipc_status=unhandled`) — no hay board vivo con el que el mecanismo de
sesión 32d (que requiere `reloaded=True`) pueda ejercitarse. Mismo
protocolo humano que el DoD exige para
`test_pcb_session21_hole_clearance_gui.py`,
`test_pcb_session27_zone_persist_gui.py` y
`test_pcb_session24_route_board_persist_gui.py` (los 3 gates GUI del
DoD) — **tampoco corridos por el agente esta sesión**, mismo motivo
estructural, no específico de este fix.

**Riesgo de no-determinismo documentado en el propio test**: a diferencia
de la reproducción offline de 32c/32d (`kicad-cli pcb drc
--refill-zones`, determinista sobre el fixture exacto), `route_board`
completo vuelve a rutear con Freerouting desde cero — no hay garantía de
que una corrida particular reproduzca el corredor angosto que el
mecanismo requiere.

**Evidencia sustituta reunida esta sesión, en ausencia de la verificación
GUI:** reproducción real con `kicad-cli pcb drc` sobre los 2 fixtures
frescos (Bloque 0, coincide exactamente con los conteos de 32c: dev-mic
1 `unconnected_items`, macro-pad-12 2) + verificación geométrica directa
(point-in-polygon contra el `filled_polygon`/outline REAL de ambos
fixtures, sin mocks) confirmando que el guardrail #4 evalúa correctamente
ambas topologías + el canario unit replica esa misma geometría en cada
test. Confianza alta en la lógica; confianza pendiente de confirmación
en el round-trip completo con Freerouting real.

## Fixtures usados (no versionados, derivables)

- `/tmp/f-d5-01-devmic-32d/` ← copia de
  `validation-suite/level-a/anavi-dev-mic/working/`.
- `/tmp/f-d5-01-macro-pad-32d/` ← copia de
  `validation-suite/level-b/anavi-macro-pad-12/working/`.
- `/tmp/f-d5-01-despertador-32d/`, `/tmp/kicad-mcp-sesion32d-gui/` ← copias
  de `tests/fixtures/despertador-routed/`.

`validation-suite/` y `tests/fixtures/` no se tocaron (sólo lectura, todas
las mutaciones en `/tmp/`).

## Estado del BACKLOG

`F-D5-01`/`F-V1c-01`/`F-V2-VIA-HUERFANA`: **cerrado parcialmente**
(topología "capas opuestas": despertador + dev-mic). Sub-patrón nuevo
`F-D5-01-B` (estrangulamiento lateral en la misma capa,
`anavi-macro-pad-12`) queda **abierto** en `docs/BACKLOG.md`, con la
evidencia geométrica de esta sesión y candidatos de mitigación NO
evaluados (ensanchar corredor, keepout pre-ruteo, o aceptar como límite
documentado).

## D-32d.1 y D-32d.2

Registradas en `docs/DECISIONES.md`. Extensión de ADR-0012 (no ADR nuevo)
— confirmado con `AskUserQuestion` antes del merge, mismo precedente que
sesiones 27 y 32b.

## Verificación pre-merge

- `uv run pytest -m "not integration"`: **392 passed, 39 skipped**.
- `uv run pytest -m integration`: **29/29 verde** (dos corridas).
- `uv run ruff check` / `uv run ruff format --check` / `uv run mypy src/`:
  limpios en todo el proyecto (`src/` + `tests/`).
- Gate GUI del DoD (`test_pcb_session21_hole_clearance_gui.py`,
  `test_pcb_session27_zone_persist_gui.py`,
  `test_pcb_session24_route_board_persist_gui.py`) y los 2 tests
  GUI-slow nuevos de H1/H2: **pendientes de ejecución humana** — ver
  §"Verificación" arriba. No es un gate saltado por decisión unilateral:
  es un límite estructural de este entorno (sin GUI de KiCad operable
  por el agente), documentado explícitamente en vez de reportado como
  "hecho".
- Fixtures del repo (`tests/fixtures/`, `validation-suite/`): verificados
  de solo lectura durante toda la sesión.

## Próxima sesión

**Antes de 33:** un humano debería correr
`test_pcb_session32d_stitching_gui_slow.py` (H1/H2) y el gate GUI del
DoD contra `/tmp/kicad-mcp-sesion32d-gui/` per protocolo
(`docs/guias/pruebas-gui.md`), para cerrar la verificación end-to-end
pendiente. Si H1 refuta (dev-mic no cierra con el motor real), escalar
con hipótesis mejorada — no forzar el cierre (D-30.2/D-32c.1).

**33 (Nivel C)** — Validation Suite, sin bloqueo: F-D5-01-B (macro-pad-12)
no impidió que sesión 32 completara su flujo canónico (42/42 nets
ruteables). Candidato tentativo: PortaPack H1/HackRF One — selección
definitiva en la conversación pre-sesión 33 (patrón de admisión de
Bloque 0 de sesiones 31/32, verificar 2-3 candidatos con clone +
inspección).
