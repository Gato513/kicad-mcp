# Sesión 31 — Validation Suite Nivel A-01: ANAVI Light Controller

**Tipo:** primera validación externa del flujo canónico + establecimiento del
estándar metodológico de la Validation Suite. **Primera sesión operacional
de la Fase 4 sobre placas ajenas al despertador.**

**Rama:** `sesion/31-validation-A-anavi-light-controller` desde `master`
post-merge de sesión 30.

**Origen:** hoja-de-ruta-v5 §Secuencia estricta, sesión 31 = "Validation
Suite: primera validación de nivel A". Marco Fase 4 (D-30.1/2/3/4). Cierre
Fase 3 con 3 verdes consecutivos + P1 resuelto en sesión 30.

**Rol dual de sesión 31 (importante):** esta sesión valida un proyecto
externo AL MISMO TIEMPO que establece el template metodológico que
sesiones 32-33 reutilizarán. Las decisiones de proceso, estructura de
directorios, scripts de medición, formato de reporte, y convenciones
adoptadas en sesión 31 se convierten automáticamente en estándar de la
Suite. Este rol dual es específico de sesión 31 y no se repite.

## Contexto de Fase 4

- **D-30.1 aplica de manera estricta.** Bloque explícito de hipótesis /
  evidencia confirmatoria / evidencia refutatoria / protección contra
  regresiones ANTES de tocar el flujo. Ver §"Estrategia de validación".
- **D-30.2 aplica:** éxito = aumento de confianza, no volumen de código.
  Los 5 resultados posibles enumerados en §"Criterios de éxito" son todos
  válidos si están honestamente documentados.
- **Interpretación de resultados Fase 4** (hoja-de-ruta-v5): un P0 nuevo
  en validación externa es **gap legítimo del flujo**, NO regresión por
  default. Sólo un P0 en test de regresión existente es regresión.

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4.

**Regla operacional específica de esta sesión:** el ejecutor no debe
inferir criterios metodológicos por su cuenta. Todos los umbrales y reglas
que aparecen en este prompt están operacionalizados. Si el ejecutor
encuentra ambigüedad o el estado real del sistema contradice una
suposición del prompt, `AskUserQuestion` obligatoria antes de continuar.

---

## Estrategia de validación (D-30.1)

### Hipótesis principales

**H1 — Generalización del flujo canónico.** El flujo canónico
(colocación asistida → plano GND → refill → route_board → refill final →
DRC) produce una PCB **igualmente válida** al ground truth del ANAVI Light
Controller según los 4 criterios D-30.3 (DRC 0/0, tracks ±30%, vías ±20%,
área cobre ±25%).

**H1a — Estabilidad de decisiones acumuladas.** Las decisiones
D-19.1, D-23.2, D-26.1, D-27.1, D-30.5 generalizan sin excepción al
proyecto ANAVI. Se mide por 0 fricciones P0/P1 nuevas durante la ejecución
del flujo.

**H2 — Discriminación de umbrales D-30.3.** Los umbrales tentativos
(±30/±20/±25) son (a) **medibles sin ambigüedad** sobre un proyecto real,
(b) **discriminantes**. Sesión 31 aporta el PRIMER punto de evidencia de
tres; la decisión definitiva sobre los umbrales se toma con la
distribución de las 3 primeras validaciones cerradas.

### Evidencia confirmatoria

- **H1:** los 4 criterios D-30.3 se cumplen simultáneamente.
- **H1a:** el flujo ejecuta sin ninguna fricción P0/P1.
- **H2:** las 4 métricas se calculan con procedimiento reproducible y
  documentado. Un resultado con margen (por ejemplo tracks +8%, vías +5%,
  cobre +12%) también es evidencia confirmatoria — indica que los
  umbrales tienen margen suficiente.

### Evidencia refutatoria

- **H1:** cualquier criterio D-30.3 fuera de umbral → refutación parcial.
  No es fracaso: registrar el número, documentar causa, proponer input
  para revisión de D-30.3 tras sesión 33.
- **H1a:** cualquier fricción P0/P1 nueva → gap legítimo del flujo.
  Agendar sesión de fix intermedia. Sesión 31 cierra sin cerrar la
  validación.
- **H2:** imposibilidad de calcular una métrica sin ambigüedad → mayor
  impacto sobre el proyecto porque afecta las 2 sesiones siguientes.
  `AskUserQuestion` obligatoria y potencial pausa de la Suite hasta
  rediseño de D-30.3.

### Protección contra regresiones

- **Suite offline existente** (`pytest -m "not integration"`) → verde
  antes del merge.
- **Suite integration** (`pytest -m integration`) → verde antes del merge.
- **Gate GUI del DoD** contra fixture despertador estable (NO contra el
  proyecto candidato):
  - `tests/test_pcb_session21_hole_clearance_gui.py` → 2/2 verde.
  - `tests/test_pcb_session27_zone_persist_gui.py` → 2/2 verde.
  - Corridas contra `/tmp/kicad-mcp-sesion31-gui/` (copia fresca del
    fixture, NO `/tmp/gui-test-project/`).
- Sesión 31 en principio NO toca código de `src/`. Si aparecen fricciones
  que requieran fix, se agenda como sesión intermedia — sesión 31 solo
  documenta.

---

## Reglas duras de la sesión

### Regla de blindado del ground truth

Durante todo el Bloque 2 (ejecución del flujo):

- NO abrir `ground-truth-original/` con ningún editor.
- NO abrir `ground-truth-kicad10/` con ningún editor.
- NO comparar visualmente con el diseño original.
- NO usar información del ruteo/colocación del autor para tomar decisiones
  durante la ejecución.

La comparación comienza EXCLUSIVAMENTE en Bloque 3. Contaminar H1a mirando
el ground truth durante la ejecución es irreversible y anula la
validación.

### Regla de conservación de evidencia original

Nunca sobrescribir `ground-truth-original/`. Es la evidencia intacta del
autor. Todas las mutaciones (migración, medición) se hacen sobre copias
en `ground-truth-kicad10/` y `working/`.

### Regla de flujo canónico intacto

Aplicar el flujo del despertador tal cual, sin ajustes específicos al
proyecto candidato. Cualquier desviación es una intervención humana M2
(ver métricas) y debe registrarse.

---

## Preparación

1. Verificar que `master` incluye sesión 30 mergeada (commit `802a32a`).
2. `git checkout master && git pull` (si aplica).
3. `git checkout -b sesion/31-validation-A-anavi-light-controller`.
4. `/tmp/gui-test-project/` NO se toca en esta sesión.
5. Crear directorio dedicado para el gate GUI del DoD:
   `/tmp/kicad-mcp-sesion31-gui/` (copia fresca del fixture despertador).
6. **Lectura obligatoria** antes de arrancar:
   - `hoja-de-ruta-v5.md` §Validation Suite completo.
   - `docs/DECISIONES.md` D-30.1 a D-30.4 + D-30.5 completas.
   - `docs/investigacion/30-solder-mask-ant1.md` — como recordatorio del
     estilo Fase 4 (medición directa, verificación contra motor real, no
     aritmética propia).

---

## Bloque 0 — Admisión del candidato y medición del ground truth (90 min)

**Objetivo:** verificar que ANAVI Light Controller cumple los 6 criterios
de admisión y establecer el ground truth medido contra el cual se
comparará el output.

**Este bloque es un gate metodológico:** si H2 se refuta acá (métricas no
calculables sin ambigüedad), la sesión pivota y NO llega a Bloque 2. Es
mejor descubrir esto en 90 min de trabajo controlado que en 4h de
ejecución del flujo.

### Pasos

1. **Clonar el candidato:**
   ```bash
   mkdir -p /tmp/anavi-light-controller
   cd /tmp/anavi-light-controller
   git clone https://github.com/AnaviTechnology/anavi-light-controller.git .
   ```
   Registrar commit hash canónico (HEAD del clone).

2. **Verificar 6 criterios de admisión** (hoja-de-ruta-v5):
   1. PCB fabricada — confirmar por documentación del repo.
   2. Proyecto mantenido — verificar por fechas de commits.
   3. Buenas prácticas de KiCad — revisión visual del `.kicad_sch` y
      `.kicad_pcb`.
   4. Licencia compatible — verificar CC-BY-SA 4.0 en el repo.
   5. Esquemático + PCB completos — verificar presencia de `.kicad_sch`,
      `.kicad_pcb`, netlists si aplica.
   6. DRC 0/0 en ground truth — medir con `kicad-cli pcb drc --format json`
      sobre el `.kicad_pcb` **antes de migrar**.

3. **Estructura de directorios:**
   ```
   validation-suite/level-a/anavi-light-controller/
   ├── ground-truth-original/     # copia exacta del repo del autor
   ├── ground-truth-kicad10/      # migrado a KiCad 10.0.4
   ├── working/                   # sch completo, pcb sin colocar/rutear
   ├── metrics.md                 # ground truth + output medidos
   ├── validation-report.md       # reporte de la validación
   └── README.md                  # metadata
   ```

4. **Migración de formato KiCad:**
   - Copiar contenido del repo a `ground-truth-original/` (NO tocar
     después).
   - Copiar a `ground-truth-kicad10/`.
   - Abrir con KiCad 10.0.4 → migrar formato automáticamente al guardar.
   - Registrar cambios significativos observados (símbolos actualizados,
     footprints migrados, warnings de migración).
   - **Medir DRC pre y post migración:**
     - `kicad-cli pcb drc --format json ground-truth-original/*.kicad_pcb`
     - `kicad-cli pcb drc --format json ground-truth-kicad10/*.kicad_pcb`
   - **Regla de decisión:**
     - Si `DRC(original) = 0/0` y `DRC(migrado) = 0/0` → seguir.
     - Si `DRC(original) = 0/0` y `DRC(migrado) ≠ 0/0` →
       **`AskUserQuestion` obligatoria**. Opciones a presentar:
       (a) rechazar candidato, (b) intentar cargar el original en KiCad 10
       sin migrar, (c) documentar como excepción y seguir.
     - Si `DRC(original) ≠ 0/0` → candidato no cumple criterio 6 →
       rechazar y activar candidato de respaldo (ANAVI Thermometer).

5. **Escribir el script de medición** `validation-suite/tools/measure_ground_truth.py`:
   - Input: path a `.kicad_pcb`.
   - Output (JSON): 4 métricas D-30.3.
     - `drc_errors`, `drc_warnings` (via `kicad-cli pcb drc`).
     - `total_track_length_mm` (sumar longitudes de todos los tracks).
     - `via_count` (contar vías).
     - `copper_area_mm2` (sumar áreas de tracks + pads + zonas filleadas
       en todas las capas de cobre).
   - **Este script se convierte en herramienta reutilizable de la Suite.**
     Documentar cada métrica: cómo se calcula, qué asume, qué excluye.
   - Justificación operacional de cada procedimiento va en el propio
     script como docstring — el ejecutor de sesión 32 no debería tener que
     preguntar.

6. **Medir el ground truth (migrado)** con el script:
   - Ejecutar `measure_ground_truth.py` sobre
     `ground-truth-kicad10/*.kicad_pcb`.
   - Registrar los 4 valores absolutos en `metrics.md` (sección "Ground
     truth medido").

7. **Preparar el `working/`:**
   - Copiar `.kicad_sch` completo desde `ground-truth-kicad10/`.
   - Copiar `.kicad_pcb` pero **eliminar** todos los tracks, vías, zonas
     filleadas, y colocación de footprints (conservar Edge.Cuts y las
     reglas de diseño del autor).
   - Verificar que el estado inicial del `working/` tiene:
     - Todos los footprints presentes pero sin colocar (o en el origen).
     - Edge.Cuts intacto.
     - Netclasses y reglas de diseño heredadas del autor.
     - 0 tracks, 0 vías, 0 zonas filleadas.

8. **Escribir `README.md`** del proyecto:
   - URL upstream + commit hash canónico.
   - Licencia y su compatibilidad con la Validation Suite.
   - Notas sobre la migración (qué cambió, warnings observados).
   - Reglas de diseño del autor (netclasses, edge clearance,
     `pad_to_mask_clearance` si aplica, etc.).

### Gate del Bloque 0

Si CUALQUIERA de estos falla, `AskUserQuestion` antes de continuar:

- Alguno de los 6 criterios de admisión.
- Regla de decisión de migración.
- Cálculo de alguna métrica sin ambigüedad (refutación temprana de H2).

### Salida esperada

Estructura de directorios creada, ground truth medido con 4 valores en
`metrics.md`, script de medición versionado, `README.md` con metadata,
`working/` en estado inicial verificado.

---

## Bloque 1 — Baseline y configuración (30 min)

**Objetivo:** confirmar el estado inicial del `working/` es correcto y no
tiene contaminación (tracks residuales, colocación previa, etc.).

### Pasos

1. Abrir el `working/*.kicad_pcb` en KiCad 10.0.4 (nueva instancia; NO usar
   `/tmp/gui-test-project/`).
2. `run_drc()` sobre el `working/` — esperable con muchas violaciones
   `unconnected_items` (todos los nets sin rutear). Documentar el número
   de errores/warnings del baseline como referencia.
3. Verificar visualmente que:
   - Todos los footprints están presentes (contar y comparar con BOM del
     ground truth).
   - Edge.Cuts define el contorno correcto.
   - No hay tracks, vías, ni zonas filleadas residuales.
4. Snapshot del estado inicial (mtime, git status del working).

### Regla de blindado activa desde este momento

De aquí en adelante y hasta el cierre del Bloque 2, NO abrir
`ground-truth-*` en ningún editor.

---

## Bloque 2 — Ejecución del flujo canónico (150 min timeboxed)

**Objetivo:** ejecutar el flujo canónico tal cual sobre `working/`, sin
usar el ground truth como referencia.

### Regla de blindado (recordatorio)

- NO abrir `ground-truth-original/`.
- NO abrir `ground-truth-kicad10/`.
- NO comparar visualmente con el diseño original.
- NO usar información del autor para ajustar decisiones.

### Pasos del flujo canónico

1. **Colocación asistida** con `get_footprint_neighbors` (D-D4.1
   inclusivo). Aplicar D-D3.1 para conectores con drill (≥1.5-2mm del
   borde). Registrar `route_ms`-equivalente para colocación (tiempo total
   de la fase).

2. **Plano GND** con `add_zone(fill=True)` (D-26.1 se aplica: el fill
   inmediato es correcto en este orden porque colocación ya ocurrió).

3. **Refill explícito post-colocación** con `fill_zones()` — refuerza
   D-26.1. Si el orden de fases hace innecesario el refill (plano ya está
   filleado con la colocación final), documentarlo pero NO omitirlo — la
   regla D-26.1 se mantiene mecánica.

4. **`route_board`** con Freerouting. Registrar `route_ms` reportado por
   la tool.

5. **Refill final** con `fill_zones()` — protege D-23.2 en la última
   pasada.

6. **`run_drc()`** → medir DRC del output. Guardar el JSON.

7. **Medir el output** con `validation-suite/tools/measure_ground_truth.py`
   (mismo script del Bloque 0) → registrar 4 valores absolutos.

### Registro de métricas auxiliares durante Bloque 2

Registrar simultáneamente a la ejecución:

**M1 — Tiempo por fase (segundos):**
- `t_colocacion` — desde primer `move_footprint` hasta último.
- `t_refill_1` — primer `fill_zones` post-colocación.
- `t_routing` — `route_ms` reportado por `route_board`.
- `t_refill_2` — refill final.
- `t_drc` — última `run_drc()`.
- `t_total` — suma.

**M2 — Intervención humana acumulada.** Aplicar la escala del arquitecto:

- **0** — Ejecución completamente conforme al flujo canónico. Sin
  decisiones adicionales ni ajustes fuera de lo prescrito.
- **1** — Ajustes menores dentro de parámetros existentes (modificación
  de estrategia soportada, pequeños movimientos manuales por conflictos
  geométricos no previstos, reintentos equivalentes sin cambio conceptual).
- **2** — Decisiones discrecionales que alteran la ejecución (cambiar
  orden de operaciones, modificar criterios, repetir etapas con
  configuraciones diferentes buscando convergencia).
- **3** — Modificaciones manuales del diseño o configuración fuera del
  flujo (añadir keepouts manuales, modificar netclasses, editar reglas de
  diseño).
- **>3** — El flujo canónico no fue suficiente; requirió intervención
  sistemática o rediseño manual.

**Registro obligatorio:** suma acumulada + lista de eventos que generaron
cada punto. Formato:
```
M2_score: N
M2_events:
  - [tipo=1] descripción del evento
  - [tipo=2] descripción del evento
```

**M3.a — Integridad estructural crítica (Pass/Fail):**
- Componentes: `count(output.footprints) == count(sch.symbols)` → `0` si
  igual, delta si diferente. **Cualquier delta > 0 = corrupción crítica
  → aborta la validación** con `F-V1-CORRUPTION-COMPONENTS`.
- Nets: `count(output.nets) == count(sch.nets)` → mismo criterio con
  `F-V1-CORRUPTION-NETS`.

**M3.b — Cambios geométricos esperables (rango):**
- Footprints modificados: cantidad absoluta y porcentaje sobre total.
  Variación legítima esperada por el pipeline. No es fallo por default.

### Regla de timeout de Freerouting

- **≤30 min:** ejecución normal, sin hallazgo.
- **30-60 min:** registrar `F-V1-ROUTER-TIMEOUT` (soft) como hallazgo,
  continuar esperando y documentar comportamiento observado (¿progresa?
  ¿se estanca? ¿logs?).
- **>60 min:** aborto controlado del proceso Freerouting. Registrar
  `F-V1-ROUTER-TIMEOUT-HARD`. Clasificación: **refutación parcial de H1
  por límite de escalabilidad**. Estado: `AskUserQuestion` obligatoria
  antes del cierre — opciones incluyen (a) analizar estado parcial y
  cerrar validación con hallazgo, (b) reintento con configuración
  distinta (contaría como M2=+2), (c) refutación aceptada y pasar a
  Bloque 3 con lo que haya.

### Criterio de aborto por P0/P1 nuevo

Primera fricción P0/P1 nueva → parar el flujo, documentar como `F-V1-XX`,
`AskUserQuestion`. No forzar cierre con violaciones nuevas.

### Salida esperada

Output ruteado (o hallazgo documentado si aborto), 4 métricas D-30.3 del
output medidas, M1/M2/M3 registradas.

---

## Bloque 3 — Comparación cuantitativa vs ground truth (60 min)

**Objetivo:** aplicar D-30.3 y las métricas auxiliares. Sólo desde acá se
puede volver a mirar el ground truth.

### Pasos

1. **Cálculo de ratios D-30.3:**
   - `ratio_tracks = output.total_track_length / ground_truth.total_track_length`.
   - `ratio_vias = output.via_count / ground_truth.via_count`.
   - `ratio_cobre = output.copper_area / ground_truth.copper_area`.
   - DRC: pass/fail (0/0 estricto o warnings compartidos con ground truth).

2. **Aplicar umbrales D-30.3:**
   - DRC: pass = 0 errores.
   - Tracks: pass si `|ratio_tracks - 1| ≤ 0.30`.
   - Vías: pass si `|ratio_vias - 1| ≤ 0.20`.
   - Cobre: pass si `|ratio_cobre - 1| ≤ 0.25`.

3. **Registro completo en `metrics.md`** (D-30.3 exige la comparación
   completa para revisión posterior, con y sin cumplimiento):

   ```markdown
   ## Ground truth (ANAVI Light Controller, migrado a KiCad 10)
   - drc: 0 errores / N warnings
   - total_track_length_mm: XXXX
   - via_count: NN
   - copper_area_mm2: YYYY

   ## Output (kicad-mcp, sesión 31)
   - drc: X errores / Y warnings
   - total_track_length_mm: XXXX
   - via_count: NN
   - copper_area_mm2: YYYY

   ## Comparación
   - ratio_tracks: 1.XX  (umbral ±30%, cumple/no cumple)
   - ratio_vias:   1.XX  (umbral ±20%, cumple/no cumple)
   - ratio_cobre:  1.XX  (umbral ±25%, cumple/no cumple)

   ## Métricas auxiliares
   - M1_tiempos: {colocacion, refill_1, routing, refill_2, drc, total}
   - M2_score: N (+ lista de eventos)
   - M3.a: componentes=PASS/FAIL, nets=PASS/FAIL
   - M3.b: footprints_modificados: N (X% del total)
   ```

4. **Escribir `validation-suite/reports/coverage-matrix.md`** (primera
   creación). Features ejercitadas por ANAVI Light Controller:
   - Capas: 2.
   - Planos: single (GND).
   - MCU: ESP8266.
   - Interfaces: I²C (3× slots), UART.
   - Potencia: 12V + MOSFETs (3× para RGB) — feature no cubierta en
     despertador.
   - Densidad: (a medir tras Bloque 3).
   - Otras features observables durante la validación.

   Formato inicial (a evolucionar con sesión 32/33):
   ```markdown
   | Feature | Anavi Light | ...futuros proyectos |
   |---|---|---|
   | Capas: 2 | ✓ | |
   | Plano GND | ✓ | |
   | ESP8266 | ✓ | |
   | I²C | ✓ | |
   | MOSFETs potencia | ✓ | |
   | ...
   ```

### Análisis explícito de H2

Documentar en `metrics.md` sección "Análisis H2":
- ¿Fueron las 4 métricas calculables sin ambigüedad? Si no, cuáles y
  por qué.
- ¿Los umbrales fueron discriminantes para este caso? Interpretar:
  - Resultado con margen (ej. tracks +8%) = umbral tiene holgura, útil.
  - Resultado cerca del borde (ej. tracks +28%) = umbral discrimina bien.
  - Resultado fuera del umbral (ej. tracks +35%) = evidencia refutatoria,
    proponer ajuste.
- **NO cerrar la validez definitiva de D-30.3 en sesión 31.** Sesión 31
  es el primer punto de evidencia. La decisión definitiva se toma tras
  sesión 33 con la distribución de las 3 validaciones.

---

## Bloque 4 — Reporte, consolidación, cierre (60 min)

**Objetivo:** producir la documentación completa siguiendo el estándar
que sesiones 32-33 heredarán.

### Entregables del bloque

1. **`validation-suite/level-a/anavi-light-controller/validation-report.md`**
   con formato heredado de dogfoodings de Fase 3 (contexto, fases
   ejecutadas, fricciones, métricas D-30.3, métricas auxiliares M1/M2/M3,
   veredicto). Este report es el TEMPLATE que sesiones 32-33 reutilizan
   — escribirlo con esa intención.

2. **`docs/historico/sesiones/31-reporte.md`** con resumen ejecutivo:
   - Resultado (cuál de los 5 escenarios de éxito aplicó, ver §Criterios).
   - Link al `validation-report.md`.
   - Fricciones nuevas si aplica.
   - Análisis H2 (¿los umbrales D-30.3 discriminan?).

3. **Actualizaciones documentales:**
   - `docs/CONTEXT.md`: estado post-sesión 31, primera validación cerrada
     (o hallazgo documentado).
   - `docs/BACKLOG.md`: fricciones F-V1-XX si aplica.
   - `docs/DECISIONES.md`: si sesión 31 formaliza alguna convención
     (por ejemplo el procedimiento de medida, la estructura de
     directorios), agregarla como D-31.x.

4. **Análisis metodológico H2:** documentar explícitamente si los
   umbrales D-30.3 fueron discriminantes en este caso y qué input aporta
   sesión 31 para la revisión post-sesión 33.

### Pre-merge

- Correr suites offline + integration → verde.
- Correr gate GUI del DoD contra `/tmp/kicad-mcp-sesion31-gui/` → 2/2
  cada uno.
- `AskUserQuestion` al arquitecto antes de mergear con: diff completo,
  ubicación del validation-report, resumen ejecutivo, análisis H2.

---

## Criterios de éxito

Ordenados de "mejor caso" a "aprendizaje sin cierre":

1. **Éxito pleno:** H1 ✓, H1a ✓, H2 ✓. 4 criterios D-30.3 cumplidos, 0
   fricciones P0/P1, métricas medibles y discriminantes. Validación
   cerrada. Confianza +alta.

2. **Éxito con matiz de umbrales:** H1 ✗ por 1 criterio D-30.3, H1a ✓,
   H2 ✓ y refutatorio en un umbral específico. Se documenta, se propone
   ajuste como input para revisión post-sesión 33. Confianza en el proceso
   mantenida.

3. **Éxito con matiz de fricciones P2/P3:** H1 ✓, H1a ✓ con fricciones
   P2/P3 nuevas (no P0/P1), H2 ✓. Se registran F-V1-XX, se agendan.
   Validación cerrada.

4. **Aprendizaje por P0/P1:** H1a ✗ con P0/P1 nuevo. Sesión 31 no cierra
   la validación — cierra con hallazgo documentado. Sesión de fix
   intermedia se agenda. Confianza intelectual +alta (patrón Fase 3
   sesión 23/26/30).

5. **Aprendizaje metodológico:** H2 ✗ (métricas no medibles sin
   ambigüedad, o umbrales no discriminantes en ningún caso). Sesión 31
   pivota a rediseño de D-30.3 antes de sesión 32. Impacto alto pero
   valioso.

6. **Refutación por escalabilidad:** `F-V1-ROUTER-TIMEOUT-HARD` (>60min).
   Refutación parcial de H1 documentada. `AskUserQuestion` sobre cómo
   cerrar la validación con el resultado parcial.

7. **Corrupción crítica:** M3.a fail (componentes o nets alterados por el
   flujo). Aborto inmediato con `F-V1-CORRUPTION-*`. Bug estructural en
   el flujo. Fix mandatorio antes de continuar la Suite. Este es el peor
   resultado — muy improbable dado el trabajo de Fase 3, pero se detecta
   por M3.a de forma barata.

---

## Entregables completos de sesión 31

1. **Rama** `sesion/31-validation-A-anavi-light-controller` mergeable a
   `master`.
2. **Directorio** `validation-suite/level-a/anavi-light-controller/`
   completo (ground-truth-original, ground-truth-kicad10, working,
   metrics.md, validation-report.md, README.md).
3. **Script** `validation-suite/tools/measure_ground_truth.py` —
   herramienta reutilizable de la Suite. Documentado en detalle.
4. **Archivo** `validation-suite/reports/coverage-matrix.md` — primera
   creación.
5. **Reporte** `docs/historico/sesiones/31-reporte.md`.
6. **Actualizaciones** en `docs/CONTEXT.md`, `docs/BACKLOG.md`
   (si fricciones), `docs/DECISIONES.md` (si D-31.x).
7. **Decisión metodológica documentada** sobre umbrales D-30.3 (input
   para revisión post-sesión 33).

---

## Aplicación de D-30.2 en esta sesión

**Éxito por confianza, no por código.** Los 7 escenarios de éxito son
todos válidos si están honestamente documentados. Sesión 31 no debería
tocar `src/` en principio — el commit final es sólo la Validation Suite
nueva. Un cierre sin código puede ser plenamente exitoso.

Si aparece tensión entre "forzar el cierre de la validación" y
"documentar honestamente un hallazgo", elegir documentar honestamente.
Precedente: sesiones 23, 26, 30.

---

## Fuera de alcance

- Modificar código de `src/` salvo que aparezca P0/P1 con fix trivial
  (<30 líneas) — en ese caso, `AskUserQuestion` antes de decidir si el
  fix va en sesión 31 o se agenda intermedia.
- Modificar tests existentes — sesión 31 solo agrega, no cambia.
- Arrancar sesión 32 (Nivel B) durante esta sesión.
- Rediseñar D-30.3 unilateralmente — sesión 31 aporta evidencia, no
  decide.
- Features nuevas al MCP.
- Preparación de release Open Source.

---

## Env vars

Sin cambios respecto a sesiones anteriores. `KICAD_MCP_FREEROUTING_JAR`
requerido para el Bloque 2.

---

## Cierre esperado

Sesión 31 cerrada con:

- Rama mergeada a master (o agendada para merge post-fix si aparece
  P0/P1).
- Primera validación de Nivel A archivada en `validation-suite/`.
- Template metodológico establecido para sesiones 32-33.
- Análisis H2 con primer punto de evidencia sobre umbrales D-30.3.

**Próxima sesión: 32 = Nivel B (candidato tentativo: ANAVI Miracle Emitter
o MOD Control Chain Shield).** Arranca sólo cuando sesión 31 esté cerrada
con conclusión clara y mergeada a master.

**Recordatorio operacional:** primera validación externa del proyecto.
Todas las convenciones que se adopten se convierten en estándar. Si el
ejecutor se encuentra improvisando una decisión metodológica no cubierta
por este prompt, `AskUserQuestion` en vez de improvisar — porque esa
improvisación se propagaría a sesiones 32-33 sin trazabilidad.
