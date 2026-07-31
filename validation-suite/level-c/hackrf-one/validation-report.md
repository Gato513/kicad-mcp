# Validation Report — HackRF One (Nivel C-01)

**Sesión 33 (2026-07-30), sesión única.** Tercera y última validación
externa del flujo canónico de `kicad-mcp`, primera y ancla de Nivel C
(complejidad alta / frontera refutatoria, criterio de diversidad D-30.4).
Cierra la trilogía A+B+C. Veredicto final: **Escenario 6 de 7**
("refutación por escalabilidad") con diagnóstico específico — crash-loop
interno de Freerouting 2.1.0, no lentitud genérica — más un hallazgo
independiente de robustez en `add_zone`/fill de zonas a esta escala
(P0/P1, ver §Fricciones).

## Historia de la validación

| Sesión | Qué hizo | Resultado |
|---|---|---|
| **33** (2026-07-30) | Admisión (con 3 correcciones D-33.1 a premisas del prompt) + Bloque 1 + Bloque 2 (colocación 437 fp con estrategia de grid/script, plano GND, 3 reproducciones de crash de zone-fill, 2 intentos de `route_board` con un crash real de KiCad intermedio) + Bloque 3 (comparación D-30.3 no aplicable sin ruteo, análisis H2) + Bloque 4 (cierre, síntesis trilogía) | 0/4 criterios D-30.3 evaluables cuantitativamente (sin ruteo). `route_board` alcanzó el timeout duro de 3600s con Freerouting en crash-loop interno (`NullPointerException` repetida en `MazeSearchAlgo`, no score estancado). Hallazgo independiente: `add_zone(fill=true)` crashea KiCad de forma reproducible (3×) al agregar la 3ª-4ª zona sobre este board de 437 footprints, sin importar geometría/overlap/delay. Validación Nivel C **cerrada** como frontera refutatoria (resultado esperado y de alto valor por diseño de Nivel C). |

---

## Contexto

- **Candidato:** HackRF One (Great Scott Gadgets),
  `github.com/greatscottgadgets/hackrf` (`hardware/hackrf-one/`), commit
  `24b53345afb79ebe34129bb68396614ab75f5637` ("update version to 10").
- **Correcciones D-33.1 a premisas del prompt** (verificadas localmente
  antes de admitir, ver `README.md` para el detalle completo):
  1. Último commit real sobre hardware: **2023-12-11** (no 2024-02-07
     como estimó una verificación remota previa) — más viejo de lo
     estimado, dispara el trigger de mantenimiento del prompt.
  2. Licencia real: **CERN-OHL-P v2** (permisiva), no GPL-2/CC-BY.
  3. `.kicad_pcb` real: **105600 líneas / 4.6MB** (no ~10227
     líneas/920KB como estimaba el prompt — ~10× más grande).
- **Decisión del arquitecto (`AskUserQuestion`, pre-Bloque 0):** admitir
  igual pese al trigger de mantenimiento — producto en venta activa,
  board r10 estable, sin necesidad de revisión desde entonces.
- **Rama:** `sesion/33-validation-C-hackrf-one`, desde `master`
  post-merge fast-forward de la secuencia 32b→32c→32d (`08c6fa4`).
- **Excepción de admisión (criterio 6, DRC 0/0):** mismo precedente
  sancionado que Nivel A/B. Ground truth original: 470 violaciones (22
  err/448 warn). Post-migración: 447 (22 err/425 warn) — errores
  idénticos, la reducción de warnings es 100% re-etiquetado de reglas
  de librería (`lib_footprint_mismatch`→`lib_footprint_issues`), no una
  corrección real. **Chequeo de trivialidad de la migración (D-33.1):**
  7 conteos estructurales (segmentos/arcos/vías/zonas/keepouts/
  footprints/nets) **idénticos bit a bit** pre/post — la migración es
  geométricamente un no-op.
- **Diversidad D-30.4:** 4 capas de cobre reales con stackup RF
  documentado (dieléctricos 0.2104/1.065/0.2104mm), esquemático
  jerárquico multi-hoja (primera vez en la Suite), escala 437 fp/380
  nets (~7-8× Nivel B), USB con cobre propio (a diferencia de A/B donde
  vivía en un módulo XIAO externo), RF (SMA, frontend de precisión).
  **Refutado antes de ejecutar:** netclasses de impedancia — el ground
  truth solo define `Default`, sin asignaciones (mismo patrón que
  ANAVI, ya documentado en BACKLOG P2 desde sesión 32).

## Fases ejecutadas

### Bloque A — Gate GUI de regresión (adelantado, D-31.1 §6)

`test_pcb_session21_hole_clearance_gui.py` 2/2 +
`test_pcb_session27_zone_persist_gui.py` 2/2 +
`test_pcb_session24_route_board_persist_gui.py` 1/1, contra copia fresca
de `despertador-routed` en `/tmp/kicad-mcp-sesion33-gui/`.
`test_pcb_session32d_stitching_gui_slow.py` (H1/H2 de sesión 32d)
**intentado a pedido del arquitecto** (no quedó como "gate manual
pendiente") pero **ambos sub-tests fallaron por `KICAD_TIMEOUT` a 600s**
(timeout hardcodeado en el test, sin `timeout_s` explícito) — no
concluyente, no es evidencia ni a favor ni en contra del fix de 32d.
Registrado como gate parcial. Suites offline + integration verdes,
`ruff`/`mypy` limpios.

### Bloque 0 — Admisión y ground truth (~90 min)

Ver §Contexto arriba y `README.md` para el detalle completo de las 3
correcciones D-33.1, los 6 criterios de admisión, y la migración KiCad
6→10 (primera vez con un esquemático jerárquico en la Suite — hallazgo:
`kicad-cli sch upgrade` sobre la hoja raíz **no migra las sub-hojas
automáticamente**, hubo que migrar cada una de las 3 individualmente).

`measure_ground_truth.py` extendido a schema 1.2 (aditivo):
`track_length_by_layer_mm`, `track_segment_count_by_layer`,
`via_count_by_type` — necesario para distinguir "sub-ruteo uniforme" de
"capas internas usadas solo como plano" en un board de 4 capas.
Verificado retrocompatible contra el JSON de Nivel B ya medido (suma de
`track_length_by_layer_mm` = `total_track_length_mm` exacto).

### Bloque 1 — Baseline

Server MCP reapuntado a `working/` (requirió 2 rondas de reconexión —
la primera actualización de `KICAD_MCP_PROJECT` en la config del
harness no se propagó al primer `/mcp` porque el proceso servidor no se
relanzó; se identificó y corrigió editando `~/.claude.json` directamente
y reconectando de nuevo). Baseline confirmado: 437/437 footprints en
`(0,0)`, 0 tracks/vías/zonas, Edge.Cuts intacto (32 dibujos). DRC
baseline: 3016 (2405 err/611 warn), consistente con footprints 100%
solapados (mismo patrón que A/B a mayor escala).

### Bloque 2 — Flujo canónico (con 3 fricciones documentadas)

Ver `metrics.md` para el detalle cuantitativo completo. Resumen
narrativo:

1. **Refs duplicados:** 17× `TESTPOINT-30MIL-MASKONLY` (test points sin
   anotar) → `set_footprint_ref` ×16 (ADR-0013, patrón N-1). No cuenta
   como M2.

2. **Colocación — decisión de escala (`AskUserQuestion`):** 437
   footprints (~7× Nivel B) hacían impracticable el patrón "un
   `move_footprint` por turno de conversación" dentro del timebox de la
   sesión. D-30.3 excluye explícitamente "preferencias de colocación
   específicas" del criterio de validez, así que se optó por un **grid
   determinístico (skyline bin packing, best-fit decreasing area)**
   calculado localmente vía `pcbnew`, aplicado con un **script driver
   que abre su propia sesión MCP en proceso** (mismo patrón que
   `tests/test_pcb_session24_route_board_persist_gui.py`:
   `create_connected_server_and_client_session`) y llama
   `move_footprint` secuencialmente contra el mismo KiCad vivo — mismas
   llamadas MCP reales, sin batchear IPC (cola de profundidad 1
   respetada), solo sin el overhead de turno de chat.
   - **Intento 1** (sin margen al Edge.Cuts): 437/437 OK, pero DRC
     expuso **63 `copper_edge_clearance` nuevos** (J2, el marco de
     shield RF de 51.6×41.4mm, y otros 8-9 footprints quedaron con
     pads tocando el borde real del contorno — el packer usó el bbox
     completo sin inset).
   - **Intento 2** (inset 2mm + fórmula de offset corregida para
     footprints ya no-en-origen): 437/437 OK, `copper_edge_clearance`
     → 0, DRC limpio (solo baseline esperado).
   - **Hallazgo lateral:** los mutadores IPC (`set_footprint_ref`,
     `move_footprint` vía script) **no auto-persisten a disco** — hubo
     que llamar `save_board()` explícito antes de que `run_drc()`
     (que opera sobre el archivo, vía `kicad-cli`) reflejara los
     cambios. Ya documentado como comportamiento esperado del contrato
     (D-23.2/ADR-0012), pero es la primera vez que la Suite lo ejercita
     con mutaciones fuera del pipeline de `route_board`/`fill_zones`.

3. **Plano GND + intento de multi-plano — 3 crashes reproducidos:**
   - GND (`In1.Cu`, bbox completo) siempre exitoso (1ª llamada).
   - **Intento 1:** VCC+VAA en `In2.Cu` con el bbox completo superpuesto
     al 100%, prioridad indefinida → **KiCad se cayó por completo**
     (proceso ausente) en la 4ª llamada (`USB_SHIELD`/F.Cu). Disco:
     **710 zonas** (3 reales + 707 fragmentos sin net, esparcidos entre
     `C2`/`C3`).
   - Hipótesis inicial: conflicto de fill sin prioridad resuelta entre
     VCC/VAA superpuestas.
   - **Intento 2** (con el arquitecto, `AskUserQuestion`): VCC/VAA en
     mitades disjuntas del bbox (sin overlap geométrico) → **mismo
     crash exacto**, mismos 710 fragmentos, en la misma 4ª llamada.
     **Refuta la hipótesis de overlap** (D-33.1 en acción — la
     explicación inicial no sobrevivió el intento de refutación).
   - **Intento 3** (con delay de 20s entre cada `add_zone`, por si era
     una condición de carrera): **mismo crash**, 3ª reproducción
     idéntica.
   - KiCad se recuperó solo las 2 primeras veces (proceso sobrevivió,
     solo el IPC quedó colgado transitoriamente); limpieza determinística
     vía `pcbnew` directo (remove zones + save + `reload_board_from_disk`)
     cada vez, sin pérdida de la colocación (437/437 verificados intactos
     tras cada limpieza).
   - **Decisión final con el arquitecto:** abandonar multi-plano, GND
     único (mismo alcance que A/B). Registrado como `F-V3-ZONE-FILL-CRASH`
     (P0/P1) — no investigado en sesión 33 (fuera de alcance), 3
     reproducciones son evidencia sólida para promover a investigación
     futura si reaparece.

4. **Refill explícito:** `fill_zones()`, 1 zona, 10253.893ms.

5. **`route_board` — 2 intentos + 1 crash real de KiCad intermedio:**
   - Intento 1 (`timeout_s=600`, default): `KICAD_TIMEOUT`.
   - **Crash real** (no transitorio esta vez — proceso KiCad
     completamente ausente) mientras Freerouting seguía corriendo
     huérfano en background. Causa identificada: el harness abortó la
     espera del cliente MCP a los 1818s por inactividad (política de
     idle-timeout del propio harness, no de `kicad-mcp`), dejando
     muerto el proceso Python padre que había spawneado Freerouting —
     el subprocess quedó reparentado a `systemd`, corriendo sin que
     nada fuera a leer su resultado. Recuperado: proceso huérfano
     matado, KiCad relanzado por el humano, reconexión verificada.
   - **Mitigación aplicada:** reintento vía script driver propio
     (`nohup` + `disown`, totalmente desacoplado del ciclo de vida del
     tool-call MCP del harness) en vez de la llamada directa al tool —
     evita que el mismo mecanismo de idle-timeout mate el intento 2.
   - Intento 2 (`timeout_s=3600`, vía script driver): `KICAD_TIMEOUT` a
     los 3600s. **Diagnóstico distinto al de macro-pad-12** (sesión 32,
     donde el score quedaba estancado cerca del final): el log de
     Freerouting (33 líneas totales) **no tiene ninguna línea de
     score/progreso** — solo 6 `NullPointerException` en
     `MazeSearchAlgo.expand_to_target_doors` (`target_shape` null),
     distribuidas de 22:06 a 22:19 con huecos de varios minutos entre
     cada una. El motor entró en un régimen de excepciones internas
     repetidas sin progreso medible, no en una búsqueda lenta pero
     activa.
   - **Decisión final con el arquitecto:** cerrar como refutación por
     escalabilidad (escenario 6). No se reintenta una 3ª vez — patrón
     reproducible/determinístico (6 excepciones idénticas en una sola
     corrida), no varianza de timing.

6. **DRC de cierre (estado terminal, sin ruteo):** 967 (555 err/412
   warn) — **idéntico** al DRC pre-ruteo. `route_board` no dejó
   tracks/zonas parciales tras fallar (D-23.2/ADR-0012 se sostiene: sin
   persistencia corrupta ante fallo).

7. **Chequeo F-D5-01-B:** no aplicable — sin ruteo no hay pads huérfanos
   post-refill que evaluar contra los guardrails de stitching.

### Bloque 3 — Comparación cuantitativa (D-30.3)

**Los 4 criterios no son evaluables numéricamente** — sin ruteo, forzar
ratios (ej. "tracks −100%") produciría precisión falsa sin valor
diagnóstico. Ver `metrics.md` §Comparación D-30.3 para la tabla completa
con la justificación de cada "no aplicable", y §Análisis H2 para lo que
sí se pudo extraer (la descomposición por capa del ground truth, útil
independientemente del resultado del ruteo).

## Fricciones

### F-V3-ZONE-FILL-CRASH (P0/P1) — `add_zone(fill=true)` crashea KiCad de forma reproducible a esta escala

Reproducido **3 veces** con geometrías distintas (overlap total, mitades
disjuntas, con delay de 20s) — siempre en la 3ª-4ª llamada consecutiva a
`add_zone(fill=true)` sobre este board de 437 footprints / 380 nets / 4
capas, siempre dejando exactamente 710 zonas fragmentadas en disco (3
reales + 707 fragmentos sin net en `C2`/`C3`). No correlaciona con
overlap de geometría (refutado explícitamente, D-33.1). Hipótesis no
investigadas: acumulación de estado en el motor de fill/conectividad de
pcbnew tras N llamadas sucesivas sobre un board de esta densidad;
posible interacción con el mismo mecanismo de segfault documentado en
`prepare_working.py` (remove+move en el mismo proceso). **No investigado
en sesión 33** (fuera de alcance) — registrado en BACKLOG para
investigación futura si reaparece en un board de escala comparable.

### F-V3-ROUTER-TIMEOUT-HARD (P0, esperado por diseño de Nivel C) — Freerouting 2.1.0 crash-loop interno sobre HackRF One

`route_board(timeout_s=3600)` no completó. Diagnóstico específico (no
genérico): el log interno de Freerouting muestra 6
`NullPointerException` repetidas en `MazeSearchAlgo.expand_to_target_doors`
sin ninguna línea de progreso/score en toda la corrida. Distinto del
patrón de sesión 32 (score estancado cerca de completar). Evidencia de
que el techo de escala del flujo automatizado en ~380 nets/4 capas está
en el motor Freerouting, no en `kicad-mcp` (`route_board` se comportó
correctamente ante el fallo — sin persistencia corrupta). No investigado
(bug upstream de Freerouting 2.1.0, fuera del alcance y del control del
proyecto).

### Hallazgo operacional — timeout de inactividad del harness sobre tool calls MCP largos

`route_board` con `timeout_s` alto (600-3600s) puede exceder el
idle-timeout del cliente MCP del harness (~1818s observado) si no emite
progreso incremental, abortando la espera del lado del cliente y matando
el proceso servidor que sostenía la llamada — dejando subprocesses
(Freerouting) huérfanos corriendo sin que nada lea su resultado. Mitigado
en esta sesión con un script driver desacoplado (`nohup`+`disown`). Nota
de proceso para sesiones futuras que necesiten invocar tools de larga
duración — no es un bug de `kicad-mcp`.

## Estado del patrón F-D5-01-B

No aplicable esta sesión — sin ruteo no hay pads post-refill que
evaluar contra los guardrails de D-32d.1.

## Análisis H2 (tercer punto de evidencia)

Ver `metrics.md` §Análisis H2 y `docs/analisis/validation-suite-sintesis-A-B-C.md`
para la síntesis completa de los 3 puntos. Sesión 33 no cierra
numéricamente el tercer punto de evidencia de D-30.3 (sin ruteo, sin
ratios que evaluar), pero aporta dos contribuciones de valor:

1. La descomposición por capa (extensión schema 1.2) revela un patrón de
   diseño real (capas internas ≈ solo planos) directamente desde el
   ground truth, útil independientemente del resultado del ruteo.
2. El techo de escala del flujo automatizado se ubica en el motor
   Freerouting, no en el código propio — información directa para la
   recomendación de umbrales D-30.3 y para el release OSS (documentar el
   límite conocido en vez de prometer cobertura universal).

## Gates de cierre

- Suite offline + integration: verdes.
- `ruff`/`mypy`: limpios.
- Gate GUI: 3/3 completados al inicio (session21/session27/session24);
  session32d_stitching intentado, no concluyente (timeout).
- Commit convencional en la rama. **Sin push.**
- `AskUserQuestion` al arquitecto antes de mergear (pendiente, próximo
  paso de la sesión).

## Próxima sesión

**34 = preparación release OSS**, con la salvedad de que
`F-V3-ZONE-FILL-CRASH` queda como candidato a sesión de investigación
intermedia si reaparece en un board de escala comparable antes del
release (mismo criterio que F-D5-01-B: 3 reproducciones son evidencia
suficiente para registrar, no para bloquear el ciclo actual).
