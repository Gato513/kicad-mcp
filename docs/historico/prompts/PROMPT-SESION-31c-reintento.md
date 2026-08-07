# Sesión 31c — Reintento de sesión 31 (ANAVI Dev Mic, post-fix 31b)

**Tipo:** reintento de la primera validación externa de la Validation
Suite (Fase 4). Continuación directa de sesión 31, con los fixes de
sesión 31b aplicados (`set_footprint_ref` + pre-check `DUPLICATE_REFS`
+ fix de `read_board_context` para bbox de Edge.Cuts).

**Rama:** `sesion/31c-reintento-anavi-dev-mic` desde `master` post-merge
de sesión 31b.

**Origen:** cierre parcial de sesión 31 (escenario 4/7 "Aprendizaje por
P0/P1") desbloqueado por sesión 31b. Ver
`docs/historico/sesiones/31-reporte.md` y `docs/historico/sesiones/31b-reporte.md`.

**Rol especial:** completa el establecimiento del template metodológico
de la Validation Suite iniciado en sesión 31 (que llegó hasta Bloque 1
antes del bloqueo). Sesión 31c completa Bloques 2-4 sobre el mismo
proyecto, con el flujo canónico desbloqueado.

## Contexto de Fase 4

- **D-30.1 estricta** para el análisis final.
- **D-30.2 aplica:** éxito = aumento de confianza. El reintento puede
  cerrar plenamente (escenario 1) o revelar hallazgos nuevos —
  cualquiera de los 7 escenarios del prompt original de sesión 31 sigue
  vigente.
- **Interpretación Fase 4:** un P0 nuevo durante el reintento es gap
  legítimo del flujo, NO regresión por default. Los fixes de 31b no
  agotan la superficie de fricciones posibles sobre un board externo.

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4.

**Regla operacional específica:** el reintento arranca sobre el mismo
proyecto (`validation-suite/level-a/anavi-dev-mic/`), pero con **M2
reiniciado desde 0**. La intervención humana registrada en sesión 31 NO
se hereda — cada validación mide una corrida limpia. El reporte de
sesión 31c es autocontenido para efectos de la métrica H2 sobre esta
placa.

---

## Estrategia de validación (D-30.1)

### Hipótesis principales

**H1 — Generalización del flujo canónico (heredada del prompt original de
sesión 31, sin cambios).** El flujo canónico produce una PCB
**igualmente válida** al ground truth de ANAVI Dev Mic según los 4
criterios D-30.3.

**H1a — Estabilidad de decisiones + fixes 31b.** Las decisiones
D-19.1, D-23.2, D-26.1, D-27.1, D-30.5 + los fixes de 31b (`set_footprint_ref`,
pre-check `DUPLICATE_REFS`, bbox de Edge.Cuts en `read_board_context`)
generalizan al proyecto ANAVI Dev Mic sin fricciones P0/P1 nuevas.

**H1b (nueva, específica del reintento) — Suficiencia del pivote de 31b.**
`set_footprint_ref` sobre las 4 instancias `REF**` de ANAVI Dev Mic
resuelve el bloqueo de `route_board` observado en sesión 31, sin efectos
colaterales inesperados sobre la comparación cuantitativa (los mounting
holes renombrados siguen siendo geométricamente idénticos a los del
ground truth original).

**H2 — Discriminación de umbrales D-30.3 (heredada, ahora ejercitable).**
Sesión 31 no aportó evidencia sobre discriminancia por falta de output
de ruteo. Sesión 31c debe aportarla o refutarla. Primer punto de
evidencia de tres.

### Evidencia confirmatoria

- **H1:** 4 criterios D-30.3 se cumplen simultáneamente.
- **H1a:** 0 fricciones P0/P1 nuevas. Fricciones P2/P3 admisibles y
  registrables.
- **H1b:** `set_footprint_ref` resuelve el bloqueo. `route_board`
  completa. La comparación cuantitativa procede.
- **H2:** las 4 métricas se calculan con procedimiento reproducible (ya
  confirmado calculable en sesión 31 — H2 mitad "calculabilidad" ya está
  parcialmente confirmada). Resultado dentro del rango donde el umbral
  discrimina útilmente.

### Evidencia refutatoria

- **H1:** cualquier criterio D-30.3 fuera de umbral → refutación parcial.
- **H1a:** cualquier fricción P0/P1 nueva → escenario 4 (aprendizaje por
  P0/P1). Cierre honesto con hallazgo, no forzado.
- **H1b:** `set_footprint_ref` funciona pero `route_board` falla por
  otra causa → hallazgo nuevo. El pre-check `DUPLICATE_REFS` protege
  contra el bug conocido; una falla distinta es evidencia legítima nueva.
- **H2:** métricas calculables pero cae en un rango no discriminante
  (muy cerca del centro sin señal) o refutatorio (fuera del umbral) —
  ambos son datos útiles.

### Protección contra regresiones

- **Suite offline** (`pytest -m "not integration"`) → verde antes del
  merge.
- **Suite integration** (`pytest -m integration`) → verde. Incluye los
  tests nuevos de sesión 31b (canario de refs duplicados, canario de
  deadlock del bbox).
- **Gate GUI del DoD** contra `/tmp/kicad-mcp-sesion31c-gui/` (copia
  fresca):
  - `test_pcb_session21_hole_clearance_gui.py` → 2/2.
  - `test_pcb_session27_zone_persist_gui.py` → 2/2.
- Sesión 31c en principio NO toca `src/`. Si aparece P0/P1 nuevo con fix
  trivial, `AskUserQuestion` antes de decidir si va acá o en sesión de
  fix separada.

---

## Reglas duras heredadas de sesión 31

### Regla de blindado del ground truth

Durante Bloque 2 (ejecución del flujo):
- NO abrir `ground-truth-original/` con editor.
- NO abrir `ground-truth-kicad10/` con editor.
- NO comparar visualmente con el diseño original.
- NO usar información del autor para ajustar decisiones.

La comparación comienza EXCLUSIVAMENTE en Bloque 3.

### Regla de conservación de evidencia original

`ground-truth-original/` y `ground-truth-kicad10/` intactos. Toda
mutación va en `working/`.

### Regla de flujo canónico intacto

Aplicar el flujo canónico tal cual. Cualquier desviación es intervención
M2 y se registra. El uso de `set_footprint_ref` sobre las 4 `REF**` **no
es intervención M2** — es aplicación explícita del fix de 31b para
desbloquear el flujo, con precedente arquitectónico documentado en
ADR-0013. Se registra en el reporte como "aplicación de fix conocido",
no como decisión discrecional.

---

## Preparación

1. Verificar que `master` incluye sesión 31b mergeada (commit `ef3e3dd`
   pusheado y mergeado). Si no, `AskUserQuestion` antes de continuar —
   la precondición es distinta a la de 31b (que se resolvió con branch
   desde 31, no viable acá).
2. `git checkout master && git pull`.
3. `git checkout -b sesion/31c-reintento-anavi-dev-mic`.
4. `/tmp/gui-test-project/` NO se toca.
5. `/tmp/kicad-mcp-sesion31c-gui/` = copia fresca del fixture despertador
   para gate GUI del DoD.
6. **Reset del `working/` al estado post-Bloque 1 de sesión 31.** Los
   pasos de colocación/zona/refill que sesión 31 alcanzó a hacer NO se
   heredan — se rehacen desde 0. Justificación: M2 se mide sobre corrida
   limpia, no acumulativa. Consecuencia práctica: verificar
   `working/anavi-dev-mic.kicad_pcb` antes de arrancar Bloque 2:
   - Footprints presentes, apilados en el origen.
   - Edge.Cuts intacto.
   - Sin tracks, sin vías, sin zonas filleadas.
   - Si el estado difiere, restaurar desde `ground-truth-kicad10/`
     aplicando los mismos pasos de Bloque 1 de sesión 31 (script
     `prepare_working.py` ya versionado en `validation-suite/tools/`).
7. **Lectura obligatoria** antes de arrancar:
   - `docs/historico/sesiones/31-reporte.md` (contexto original).
   - `docs/historico/sesiones/31b-reporte.md` (fixes aplicados).
   - `docs/adr/0013-refs-duplicados-por-anotacion-no-borrado.md`
     (contrato de `set_footprint_ref` + hallazgo arquitectónico).
   - `validation-suite/level-a/anavi-dev-mic/validation-report.md`
     (estado sesión 31).

---

## Bloque 0 — Verificación de precondiciones (15 min)

**Objetivo:** confirmar que el estado del proyecto es el esperado antes
de arrancar el reintento. Bloque corto pero necesario dado que hubo
sesión intermedia.

### Pasos

1. **`working/` reseteado** — ver Preparación §6. Si el reset se
   requiere, ejecutarlo con `prepare_working.py`.
2. **Ground truth intacto** — verificar por hash o mtime que
   `ground-truth-original/` y `ground-truth-kicad10/` no fueron tocados.
3. **Métricas de ground truth cargadas** — leer `metrics.md` de sesión
   31, confirmar que los 4 valores absolutos del ground truth están
   documentados (longitud tracks, vías, área cobre, DRC). Estos son los
   valores contra los que se va a comparar en Bloque 3, ya medidos y
   validados.
4. **Fixes de 31b disponibles** — smoke check rápido: `set_footprint_ref`
   existe en el catálogo, pre-check `DUPLICATE_REFS` activo en
   `route_board`. Confirmable por `pytest tests/test_pcb_session31b_duplicate_refs.py`
   → verde.
5. **Gate GUI baseline** — corrida rápida contra
   `/tmp/kicad-mcp-sesion31c-gui/` para confirmar que el entorno está
   funcional antes de arrancar el flujo. 2/2 × 2 verde.

### Gate del Bloque 0

Si CUALQUIERA falla, `AskUserQuestion` antes de continuar. No forzar
Bloque 2 sobre entorno sospechoso.

---

## Bloque 2 — Ejecución del flujo canónico (150 min timeboxed)

**Objetivo:** ejecutar el flujo completo sobre ANAVI Dev Mic, aplicando
el fix de refs duplicados como paso conocido antes de `route_board`.

### Regla de blindado activa

- NO abrir `ground-truth-*` con editor.
- NO comparar visualmente durante el flujo.

### Pasos del flujo canónico

1. **Resolución de refs duplicados** (paso conocido, aplicación de fix
   de 31b). Sobre las 4 instancias `REF**`:
   - `set_footprint_ref("REF**", "MH1", kiid=<kiid_1>)`.
   - `set_footprint_ref("REF**", "MH2", kiid=<kiid_2>)`.
   - `set_footprint_ref("REF**", "MH3", kiid=<kiid_3>)`.
   - `set_footprint_ref("REF**", "MH4", kiid=<kiid_4>)`.
   - Nomenclatura `MHn` es sugerencia. Cualquier nomenclatura consistente
     es admisible siempre que resulte en 4 refs únicos que no colisionen
     con refs existentes en el board.
   - Verificar post-resolución con `read_board_context` que ya no hay
     duplicados.
   - **Este paso NO cuenta como M2** — es aplicación explícita del fix
     de 31b con precedente ADR-0013. Registrar en el reporte como
     "aplicación de fix conocido, 4 llamadas".

2. **Colocación asistida** con `get_footprint_neighbors` (D-D4.1
   inclusivo). Aplicar D-D3.1 para conectores con drill.

3. **Plano GND** con `add_zone(fill=True)` (D-26.1).

4. **Refill explícito post-colocación** con `fill_zones()` (D-26.1
   mecánica).

5. **`route_board`** con Freerouting. Registrar `route_ms`.

6. **Refill final** con `fill_zones()` (protege D-23.2).

7. **`run_drc()`** → medir DRC del output. Guardar JSON.

8. **Medir el output** con
   `validation-suite/tools/measure_ground_truth.py` → registrar 4
   valores absolutos.

### Registro de métricas auxiliares durante Bloque 2

**M1 — Tiempo por fase (segundos):**
- `t_resolucion_refs` — 4 llamadas de `set_footprint_ref`.
- `t_colocacion` — desde primer `move_footprint` hasta último.
- `t_refill_1` — primer `fill_zones` post-colocación.
- `t_routing` — `route_ms` reportado por `route_board`.
- `t_refill_2` — refill final.
- `t_drc` — última `run_drc()`.
- `t_total` — suma.

**M2 — Intervención humana acumulada** (heredada operacional de sesión
31, escala 0-3-> del arquitecto). **Inicia en 0**, no hereda 31.
Registro obligatorio: suma acumulada + lista de eventos que generaron
cada punto. Recordatorio: la aplicación de `set_footprint_ref` **no
suma** — es fix conocido con precedente.

**M3.a — Integridad estructural crítica (Pass/Fail):**
- Componentes: `count(output.footprints) == count(sch.symbols)`.
  Delta > 0 → `F-V1c-CORRUPTION-COMPONENTS` → aborto validación.
- Nets: `count(output.nets) == count(sch.nets)`. Delta > 0 →
  `F-V1c-CORRUPTION-NETS`.

**M3.b — Cambios geométricos esperables (rango):**
- Footprints modificados: cantidad absoluta y porcentaje.

### Regla de timeout de Freerouting (heredada)

- **≤30 min:** normal.
- **30-60 min:** registrar `F-V1c-ROUTER-TIMEOUT` (soft), continuar y
  documentar comportamiento.
- **>60 min:** aborto controlado. Registrar `F-V1c-ROUTER-TIMEOUT-HARD`.
  Refutación parcial de H1. `AskUserQuestion` antes del cierre.

### Criterio de aborto por P0/P1 nuevo

Primera fricción P0/P1 nueva (distinta a las ya cerradas por 31b) →
parar, documentar como `F-V1c-XX`, `AskUserQuestion`.

### Salida esperada

Output ruteado, 4 métricas D-30.3 medidas, M1/M2/M3 registradas.

---

## Bloque 3 — Comparación cuantitativa vs ground truth (60 min)

**Objetivo:** aplicar D-30.3 con las métricas auxiliares. Blindado se
levanta acá.

### Pasos

1. **Cálculo de ratios D-30.3:**
   - `ratio_tracks = output.total_track_length / ground_truth.total_track_length`.
   - `ratio_vias = output.via_count / ground_truth.via_count`.
   - `ratio_cobre = output.copper_area / ground_truth.copper_area`.
   - DRC: pass/fail (con excepción de admisión documentada — el ground
     truth tiene 18 `solder_mask_bridge` preexistentes; para
     comparabilidad, DRC del output se considera pass si tiene 0 nuevos
     errores o warnings compartidos con el ground truth).

2. **Aplicar umbrales D-30.3:**
   - DRC: pass = 0 errores nuevos vs ground truth.
   - Tracks: pass si `|ratio_tracks - 1| ≤ 0.30`.
   - Vías: pass si `|ratio_vias - 1| ≤ 0.20`.
   - Cobre: pass si `|ratio_cobre - 1| ≤ 0.25`.

3. **Registro completo en `metrics.md`:**

   ```markdown
   ## Ground truth (ANAVI Dev Mic, migrado a KiCad 10) [heredado sesión 31]
   - drc: 18 errores solder_mask_bridge (excepción de admisión documentada)
   - total_track_length_mm: XXXX
   - via_count: NN
   - copper_area_mm2: YYYY

   ## Output (kicad-mcp, sesión 31c)
   - drc: X errores / Y warnings
   - drc_delta_vs_ground_truth: N errores nuevos (0 esperado para pass)
   - total_track_length_mm: XXXX
   - via_count: NN
   - copper_area_mm2: YYYY

   ## Comparación
   - ratio_tracks: 1.XX  (umbral ±30%, cumple/no cumple)
   - ratio_vias:   1.XX  (umbral ±20%, cumple/no cumple)
   - ratio_cobre:  1.XX  (umbral ±25%, cumple/no cumple)

   ## Métricas auxiliares
   - M1_tiempos: {resolucion_refs, colocacion, refill_1, routing, refill_2, drc, total}
   - M2_score: N (+ lista de eventos)
   - M3.a: componentes=PASS/FAIL, nets=PASS/FAIL
   - M3.b: footprints_modificados: N (X% del total)
   ```

4. **Actualizar `validation-suite/reports/coverage-matrix.md`** con las
   features cerradas por ANAVI Dev Mic ejercitadas end-to-end (no solo
   inicialmente listadas — algunas pueden haber quedado sin ejercer si
   Bloque 2 no las tocó).

### Análisis explícito de H2

Primer punto de evidencia real sobre discriminancia de umbrales D-30.3
(sesión 31 solo cubrió calculabilidad). Documentar en `metrics.md`
sección "Análisis H2":
- ¿Los umbrales fueron discriminantes para este caso? Interpretación:
  - Resultado con margen (±5-10%) = umbral tiene holgura, útil.
  - Resultado cerca del borde (±20-28%) = umbral discrimina bien.
  - Resultado fuera del umbral = evidencia refutatoria, proponer ajuste.
- **NO cerrar la validez definitiva de D-30.3 en sesión 31c.** Primer
  punto de tres. La decisión definitiva se toma tras sesión 33.

---

## Bloque 4 — Reporte, consolidación, cierre (60 min)

**Objetivo:** cerrar sesión 31c y dejar el template metodológico
completo para sesión 32.

### Entregables del bloque

1. **`validation-suite/level-a/anavi-dev-mic/validation-report.md`
   actualizado** con la corrida completa. **Este report es el template
   que sesión 32 reutiliza.** Escribirlo con esa intención. Debe cubrir
   sesión 31 (Bloques 0-1) + sesión 31b (fixes aplicados) + sesión 31c
   (Bloques 2-4) como narrativa unificada de la primera validación
   Nivel A. Sección "Historia de la validación" que trace las 3
   sesiones.

2. **`docs/historico/sesiones/31c-reporte.md`** con resumen ejecutivo:
   - Resultado (cuál de los 7 escenarios del prompt original de 31 aplicó).
   - Link al `validation-report.md`.
   - Fricciones nuevas si aplica.
   - Análisis H2 (primer punto real de evidencia sobre discriminancia).

3. **Actualizaciones documentales:**
   - `docs/CONTEXT.md`: estado post-sesión 31c, primera validación
     Nivel A cerrada.
   - `docs/BACKLOG.md`: fricciones `F-V1c-XX` si aplica.
   - `docs/DECISIONES.md`: **decisión metodológica del arquitecto** —
     agregar entrada nueva (candidato D-31c.1 o el número que
     corresponda) con el siguiente contenido:

     ```markdown
     - **D-31c.1** (sesión 31c, retrospectiva 31b): al cerrar decisiones
       de diseño no re-abribles en el marco del prompt de una sesión
       (patrón D1-DN), cross-check obligatorio contra ADRs vigentes que
       tocan el área operada antes de fijar el marco. Origen: sesión 31b
       reveló que D1-D4 del prompt de 31b (semántica de
       `delete_footprint`) chocaba con ADR-0010 (asimetría deliberada
       `delete_track`/`delete_footprint`) — decisión que el arquitecto
       había cerrado sin verificar el ADR vigente. Salvado por rigor
       investigativo del ejecutor + AskUserQuestion. La convención hace
       explícita la disciplina para prompts futuros: el marco cerrado
       del prompt es autoritativo pero no dispensa del cross-check con
       ADRs de la superficie tocada.
     ```

     Esta decisión es del arquitecto sobre proceso de generación de
     prompts, no del código. Es análoga a D-30.1 pero un nivel arriba.

4. **Análisis H2 documentado** como input formal para la revisión post-
   sesión 33.

### Pre-merge

- Suites offline + integration → verde.
- Gate GUI del DoD → 2/2 × 2.
- `AskUserQuestion` al arquitecto antes de mergear.

---

## Criterios de éxito

Heredados directamente del prompt original de sesión 31, ajustados al
contexto de reintento:

1. **Éxito pleno:** H1, H1a, H1b, H2 confirmadas. 4 criterios D-30.3
   cumplidos, 0 fricciones P0/P1 nuevas, umbrales discriminantes.
   Primera validación Nivel A cerrada. Habilita sesión 32.

2. **Éxito con matiz de umbrales:** H1 refutada por 1 criterio D-30.3,
   otras hipótesis confirmadas. Documentar, proponer ajuste como input
   para revisión post-sesión 33.

3. **Éxito con matiz de fricciones P2/P3:** H1, H1a, H1b, H2 ✓ con
   fricciones P2/P3 nuevas. Se registran, se agendan. Validación
   cerrada.

4. **Aprendizaje por P0/P1 nuevo:** H1a o H1b refutada por P0/P1 nuevo
   distinto de F-V1-01/F-V1-02. Cierre honesto con hallazgo. Sesión de
   fix intermedia (31d) se agenda.

5. **Aprendizaje metodológico:** H2 refutada (umbrales no discriminantes
   en este caso). Registrar como primer dato para revisión post-sesión
   33.

6. **Refutación por escalabilidad:** `F-V1c-ROUTER-TIMEOUT-HARD`.
   Refutación parcial de H1 documentada. `AskUserQuestion` sobre cierre.

7. **Corrupción crítica:** M3.a fail. Aborto inmediato con
   `F-V1c-CORRUPTION-*`. Bug estructural. Muy improbable dado sesión 31b.

---

## Entregables completos

1. **Rama** `sesion/31c-reintento-anavi-dev-mic` mergeable a `master`.
2. **`validation-suite/level-a/anavi-dev-mic/`** completo con
   `validation-report.md` unificado (31 + 31b + 31c) + `metrics.md`
   completo (ground truth + output + comparación + análisis H2).
3. **`validation-suite/reports/coverage-matrix.md`** actualizado con
   features cerradas end-to-end.
4. **Reporte** `docs/historico/sesiones/31c-reporte.md`.
5. **Actualizaciones** en `docs/CONTEXT.md`, `docs/BACKLOG.md`
   (si fricciones), `docs/DECISIONES.md` (D-31c.1 mínimo).
6. **Decisión metodológica documentada** sobre umbrales D-30.3
   (primer punto real de evidencia de tres).

---

## Recordatorios operacionales heredados de sesión 31b

Dos patrones que sesión 31b demostró y que quiero mantener presentes
para sesiones futuras (no son bloques del prompt de 31c, son
disposición general):

**Investigación previa al fix cuando el marco del prompt entra en
conflicto con evidencia.** El ejecutor de 31b encontró que D1-D4 del
prompt chocaban con ADR-0010 antes de tocar código, usando agentes
Explore + Plan verificados contra el código real. Escaló con
`AskUserQuestion`, presentó alternativa viable, esperó confirmación
antes de comprometerse. Este patrón se mantiene: **si durante sesión 31c
el estado real del sistema o del código contradice una suposición del
prompt, `AskUserQuestion` antes de improvisar**.

**Spike de confirmación antes de comprometer un enfoque nuevo.**
Sesión 31b hizo spike GUI de `set_footprint_ref` contra KiCad real antes
de escribir código en `src/`. Sesión 31c no debería necesitar spike
(los fixes ya están mergeados), pero **si aparece una decisión
discrecional durante Bloque 2 que altera el flujo canónico (M2 = 2 o
mayor), considerar spike antes de comprometer**.

---

## Aplicación de D-30.2

**Éxito por confianza, no por código.** Sesión 31c en principio NO toca
`src/`. Un cierre limpio de la primera validación Nivel A sin escribir
código propio es pleno éxito — el código valioso ya está en 31b.

Si aparece tensión entre "forzar el cierre" y "documentar honestamente",
elegir documentar. Precedentes: 23, 26, 30, 31.

---

## Fuera de alcance

- Modificar `src/` salvo P0/P1 nuevo con fix trivial (<30 líneas) —
  `AskUserQuestion` antes de decidir.
- Arrancar sesión 32.
- Rediseñar D-30.3.
- Features nuevas al MCP.
- Preparación de release Open Source.
- Resolver deuda de repositorio (discrepancia `sesion-01`/`master`,
  agendada para pre-release).
- Modificar `validation-suite/tools/` (scripts reutilizables — se
  mantienen intactos salvo bugfix menor si algo se rompió).

---

## Env vars

Sin cambios respecto a sesiones anteriores.
`KICAD_MCP_FREEROUTING_JAR` requerido.

---

## Cierre esperado

Sesión 31c cerrada con:

- Rama mergeada a master.
- Primera validación de Nivel A cerrada con conclusión clara (uno de
  los 7 escenarios).
- Template metodológico completo para sesión 32.
- Primer punto real de evidencia sobre discriminancia de umbrales D-30.3
  (H2 real, no parcial).
- D-31c.1 registrada (convención metodológica del arquitecto).

**Próxima sesión: 32 = Nivel B** (candidato tentativo: ANAVI Miracle
Emitter o MOD Control Chain Shield, a confirmar antes de sesión 32
siguiendo el mismo patrón de admisión de sesión 31 Bloque 0). Arranca
sólo cuando 31c cierre con conclusión clara y mergeada.

**Recordatorio final:** el ejecutor no está solo validando una placa.
Está cerrando el ciclo (31 → 31b → 31c) que estableció el template para
las validaciones restantes. Rigor sobre velocidad. Documentación honesta
sobre optimismo. Si aparece ambigüedad no cubierta, `AskUserQuestion`.
