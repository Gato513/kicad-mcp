# Sesión 32 — Validation Suite Nivel B-01: ANAVI Miracle Emitter

**Tipo:** segunda validación externa del flujo canónico (Nivel B).
Continúa el establecimiento de la Validation Suite iniciado en el ciclo
31→31b→31c.

**Rama:** `sesion/32-validation-B-anavi-miracle-emitter` desde `master`
post-merge de la secuencia 31→31b→31c.

**Origen:** hoja-de-ruta-v5 §Secuencia estricta, sesión 32 = "Validation
Suite: nivel B". Primer punto de evidencia real cerrado en sesión 31c
sobre umbrales D-30.3 (H2 parcial → primera métrica calculable con
discriminancia observada, ver §Análisis H2 al final).

**Candidato tentativo:** **ANAVI Miracle Emitter**
(`https://github.com/AnaviTechnology/anavi-miracle-emitter`) — verificado
en preparación de este prompt:
- Licencia CC-BY-SA 4.0 (compatible).
- ESP32-C3 RISC-V + USB-C + WS2812B (NeoPixels addressable) + I²C + OLED.
- Certificado OSHWA por familia ANAVI.
- 2 capas probable (a confirmar en Bloque 0).
- Fabricado y vendido comercialmente.
- **Diversidad D-30.4 legítima:** agrega USB-C con diff-pair, WS2812B
  cadena serial (patrón distinto a I²C), ESP32-C3 RISC-V (vs ESP8266 del
  Nivel A).

**Candidatos de respaldo** (a activar si Bloque 0 rechaza el candidato
principal):
1. **MOD Control Chain Arduino Shield** (`https://github.com/mod-archive/`)
   — shield form-factor con headers + comunicación diferencial CAN.
2. **ANAVI Thermometer** — validado como respaldo de Nivel A en sesión
   31, pero puede escalar a Nivel B por cantidad de sensores + OLED si
   Miracle Emitter y MOD Shield fallan admisión.

## Rol de esta sesión

**Sesión 32 hereda el template metodológico completo de 31/31b/31c y lo
adapta a Nivel B.** No re-establece convenciones — las reutiliza. Si
durante la ejecución aparece una convención nueva de la Suite que no
estaba en el template, `AskUserQuestion` antes de introducirla (para no
propagarla sin trazabilidad a sesión 33).

Diferencia clave vs sesión 31: Nivel B agrega **diversidad D-30.4**
(features no cubiertas en Nivel A). Sesión 32 tiene que documentar
explícitamente cuáles features ejercita ese Nivel A no tenía.

## Contexto de Fase 4

- **D-30.1 estricta.** Bloque explícito de hipótesis / evidencia
  confirmatoria / refutatoria / protección antes de tocar el flujo.
- **D-30.2 aplica:** éxito = aumento de confianza. Los 7 escenarios
  heredados de sesión 31 siguen vigentes.
- **D-30.4 aplica desde este proyecto:** diversidad legítima requerida.
  Miracle Emitter agrega USB-C, WS2812B cadena serial, ESP32-C3 —
  features no cubiertas por Nivel A.
- **Interpretación Fase 4:** un P0 nuevo es gap legítimo del flujo, NO
  regresión por default. Nivel B puede exponer fricciones no vistas en
  el ciclo 31→31c precisamente porque agrega features.

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4.

---

## Convenciones metodológicas heredadas del template (31/31b/31c)

Estas convenciones ya están establecidas y **no se re-discuten en sesión
32** — se aplican directamente:

- **Estructura de directorios:** `validation-suite/level-b/<proyecto>/`
  con `ground-truth-original/` + `ground-truth-kicad10/` + `working/` +
  `metrics.md` + `validation-report.md` + `README.md`.
- **Regla de blindado del ground truth durante Bloque 2** (heredada
  literalmente).
- **Regla de conservación de evidencia original** (heredada).
- **Regla de flujo canónico intacto** (heredada). Aplicación de fixes
  conocidos (ADR-0013 `set_footprint_ref` si aparecen refs duplicados)
  no cuenta como intervención M2.
- **Gate GUI del DoD una sola vez al inicio si sesión 32 no toca `src/`**
  (convención cristalizada en sesión 31c). Si aparece P0/P1 con fix
  trivial que requiera tocar `src/`, escalar y el gate GUI se re-corre
  al cierre.
- **Migración de formato KiCad con DRC pre y post** (heredada). Regla de
  decisión inalterada: pre=0/0 & post=0/0 seguir; pre=0/0 & post≠0/0
  `AskUserQuestion`; pre≠0/0 rechazar (con excepción explícita del tipo
  aplicada a ANAVI Dev Mic solo si hay precedente sancionado).
- **Escala M2 del arquitecto** con lista de eventos obligatoria.
- **M3.a (Pass/Fail crítico) + M3.b (rango informativo)** — heredado.
- **Timeout de Freerouting** con 3 tramos y `F-V2-ROUTER-TIMEOUT`/
  `F-V2-ROUTER-TIMEOUT-HARD` (nota la evolución: V1c → V2 para
  distinguir naming de fricciones por sesión).
- **Reset del `working/` = footprints al origen sin tracks/vías/zonas**
  (convención adoptada por sesión 31, D-31c.1).

---

## Reflexiones de sesión 31c integradas

Tres cosas que sesión 31c descubrió y que sesión 32 aplica desde el
arranque:

### 1. Métrica opcional de longitud por-net

Cuando `ratio_tracks` global falla por margen estrecho (como en 31c:
−33.1% vs ±30%), el número no distingue entre "el flujo sub-ruteó
uniformemente" y "el flujo tomó topologías más directas en ciertos nets
grandes". **Sesión 32 debe calcular longitud por-net del ground truth y
del output**, y reportar en `metrics.md` un análisis descompuesto:
- Top 5 nets por delta absoluto de longitud.
- Top 5 nets por delta porcentual.
- Nets que el output ruteó y el ground truth no (o viceversa) — si
  aparecen, es fricción P2 nueva.

Esto no es un umbral D-30.3 nuevo — es una descomposición explicativa
para interpretar el ratio global.

### 2. DRC separado en eléctrico vs cosmético

Sesión 31c descubrió que "0 errores nuevos" es un criterio demasiado
estricto porque no distingue severidad. **Sesión 32 debe registrar en
`metrics.md` una tabla de tipos de error DRC**, separando:
- **Eléctricos** (unconnected, shorts, clearance, hole_clearance) —
  criterio estricto: 0 nuevos vs ground truth.
- **Estructurales** (solder_mask_bridge, courtyards_overlap) — criterio
  moderado: registrar deltas, no falla automática.
- **Cosméticos** (silkscreen, fabrication) — criterio informativo: solo
  registro.

Sigue reportándose el conteo total como comparación con D-30.3
histórica, pero la interpretación de "pass/fail" del criterio DRC de
D-30.3 se hace sobre eléctricos + estructurales, no sobre el total.

### 3. F-V1c-01 (vía huérfana) — vigilancia como posible reincidencia F-D5-01

Sesión 31c reportó una vía GND F.Cu-B.Cu no conectada al pad más chico
del board (0.30×0.30mm). Es P2, no bloqueó. **Es el segundo caso del
patrón F-D5-01 en régimen distinto** (sesión 25 = despertador D5;
sesión 31c = ANAVI Dev Mic MK1). No cumple estrictamente el trigger de
promoción a P2 investigación (2 dogfoodings independientes = mismo tipo
de placa) pero está cerca.

**Sesión 32 debe:**
- Al terminar Bloque 2, chequear explícitamente si hay vías huérfanas
  post-`route_board`+refill final. Comando: verificar conectividad de
  cada vía GND a su plano vía DRC + inspección de tracks conectados.
- Si aparece una tercera instancia del patrón → promover
  automáticamente a P1 investigación Fase 4 (agenda sesión de fix
  intermedia).
- Si NO aparece → registro en el reporte de "sin reincidencia
  observada", cierra sesgo hacia patrón sistemático.

### 4. Convención cristalizada en D-31c.1

**Cross-check contra ADRs vigentes** antes de fijar decisiones no
re-abribles en el marco del prompt. **Yo (arquitecto) apliqué esta
disciplina al escribir este prompt** — verificado que ninguna decisión
D-N conflictúa con ADR-0010, ADR-0012, ADR-0013 vigentes.

---

## Estrategia de validación (D-30.1)

### Hipótesis principales

**H1 — Generalización a Nivel B.** El flujo canónico produce una PCB
igualmente válida al ground truth de ANAVI Miracle Emitter según los 4
criterios D-30.3 (con interpretación matizada de DRC — ver §Reflexiones).

**H1a — Estabilidad end-to-end.** Las decisiones + fixes acumulados
(D-19.1, D-23.2, D-26.1, D-27.1, D-30.5 + ADR-0013 + fix bbox de 31b)
generalizan al proyecto sin fricciones P0/P1 nuevas.

**H1b — Cobertura de features nuevas de Nivel B.** El flujo maneja
correctamente las features de Miracle Emitter NO cubiertas en Nivel A:
- **USB-C con diff-pair D+/D−** — netclass diferencial, reglas de
  impedancia.
- **WS2812B cadena serial** — patrón distinto a I²C (topología en
  cadena, no en bus).
- **ESP32-C3** (RISC-V) — footprint distinto al ESP8266 de Nivel A.

Refutación de H1b sería la evidencia más útil de la sesión — expone
techo de complejidad del flujo por features no ejercitadas antes.

**H2 — Discriminancia de umbrales D-30.3 (segundo punto de evidencia).**
Sesión 31c aportó el primer punto real con diagnóstico específico:
- Cobre (±25%): bien calibrado.
- Tracks (±30%): sin evidencia de mala calibración.
- Vías (±20%): mal calibrado para bases pequeñas.
- DRC estricto: no distingue severidad.

Sesión 32 aporta el segundo punto. **La decisión definitiva sobre
umbrales se toma tras sesión 33** con tres puntos de evidencia. Nivel B
puede confirmar/refutar los diagnósticos de 31c o agregar dimensiones
nuevas.

### Evidencia confirmatoria

- **H1:** 4 criterios D-30.3 cumplen (interpretación matizada de DRC).
- **H1a:** 0 fricciones P0/P1 nuevas. Fricciones P2/P3 admisibles.
- **H1b:** las 3 features nuevas se ejercen sin bloqueo. Ideal: `route_board`
  respeta netclass diff-pair de USB-C (verificable por inspección de
  tracks del par D+/D−: ¿corren en paralelo con separación configurada?).
- **H2:** métricas calculables + análisis descompuesto (por-net + DRC
  separado) aporta insight sobre umbrales.

### Evidencia refutatoria

- **H1:** cualquier criterio D-30.3 fuera de umbral matizado. Registrar,
  proponer input para revisión post-33.
- **H1a:** cualquier fricción P0/P1 nueva → escenario 4 (aprendizaje).
  Cierre honesto con hallazgo. Sesión 32b intermedia si aplica.
- **H1b:** el flujo falla específicamente sobre alguna feature de Nivel
  B. Ejemplo: `route_board` no respeta la netclass diff-pair, o cada pixel
  de WS2812B queda sin ruta. Gap arquitectónico del flujo, muy útil como
  evidencia.
- **H2:** primer diagnóstico (vías mal calibrado para bases pequeñas)
  refutado por Nivel B → indica que la fricción es del proyecto, no del
  umbral. O primer diagnóstico confirmado → dos puntos concordantes,
  base más sólida para revisión post-33.

### Protección contra regresiones

- **Suite offline** (`pytest -m "not integration"`) → verde antes del
  merge.
- **Suite integration** (`pytest -m integration`) → verde. Incluye tests
  nuevos de sesión 31b (canario de refs duplicados, canario de deadlock
  del bbox).
- **Gate GUI del DoD** contra `/tmp/kicad-mcp-sesion32-gui/` (copia
  fresca del fixture despertador):
  - `test_pcb_session21_hole_clearance_gui.py` → 2/2.
  - `test_pcb_session27_zone_persist_gui.py` → 2/2.
- **Convención D-31c.1 heredada:** gate GUI corrido **una sola vez al
  inicio** si sesión 32 no toca `src/`. Si aparece fix de código,
  re-correr al cierre.

---

## Preparación

1. Verificar que `master` incluye la secuencia 31→31b→31c mergeada. Si
   NO está mergeada (patrón observado en 31c) → `AskUserQuestion` sobre
   si arrancar encadenando desde `sesion/31c-*` o esperar el merge.
2. `git checkout master && git pull` (si aplica).
3. `git checkout -b sesion/32-validation-B-anavi-miracle-emitter`.
4. `/tmp/kicad-mcp-sesion32-gui/` = copia fresca del fixture despertador.
5. `/tmp/gui-test-project/` NO se toca (a menos que sea necesario para
   Bloque 1 según el patrón de 31c — en cuyo caso `AskUserQuestion`).
6. **Lectura obligatoria** antes de arrancar:
   - `docs/historico/sesiones/31c-reporte.md` (contexto Suite + análisis H2).
   - `docs/historico/sesiones/31b-reporte.md` (fixes aplicados).
   - `docs/adr/0013-refs-duplicados-por-anotacion-no-borrado.md`
     (contrato `set_footprint_ref`).
   - `docs/DECISIONES.md` D-30.1 a D-30.5 + D-31c.1.
   - `validation-suite/level-a/anavi-dev-mic/validation-report.md`
     (template a heredar).
   - `validation-suite/reports/coverage-matrix.md`.

---

## Bloque 0 — Admisión del candidato (90 min)

**Objetivo:** verificar Miracle Emitter contra los 6 criterios de
admisión + medir ground truth. Si falla, activar candidato de respaldo.

### Pasos

1. **Clonar el candidato:**
   ```bash
   mkdir -p /tmp/anavi-miracle-emitter
   cd /tmp/anavi-miracle-emitter
   git clone https://github.com/AnaviTechnology/anavi-miracle-emitter.git .
   ```
   Registrar commit hash canónico.

2. **Verificar 6 criterios de admisión** + **diversidad D-30.4**:
   - PCB fabricada, mantenida, buenas prácticas, licencia, sch+pcb
     completos, DRC 0/0 → los 6 heredados.
   - **Diversidad D-30.4:** listar explícitamente qué features de
     Miracle Emitter NO están en Nivel A cerrado. Referencia:
     `validation-suite/reports/coverage-matrix.md`.

3. **Migración de formato KiCad** (patrón sesión 31):
   - `ground-truth-original/` intacto, `ground-truth-kicad10/` migrado.
   - Medir DRC pre y post. Aplicar regla de decisión heredada.

4. **Reutilizar el script de medición**
   `validation-suite/tools/measure_ground_truth.py` (versionado desde
   sesión 31). **Si el script no cubre alguna métrica que Nivel B
   necesita** (por ejemplo, cálculo de longitud por-net que sesión 32
   requiere) → extenderlo con función nueva, NO reemplazar la existente.
   Backwards-compatible con sesiones 31.

5. **Medir el ground truth** con el script → 4 métricas D-30.3 + longitud
   por-net + tabla de tipos de DRC.

6. **Preparar el `working/`** (patrón sesión 31): sch completo, pcb sin
   colocar/rutear. Reutilizar `prepare_working.py` de la Suite.

7. **Escribir `README.md`** del proyecto con metadata.

### Gate del Bloque 0

Si CUALQUIERA falla:
- Alguno de los 6 criterios → activar candidato de respaldo (MOD
  Control Chain Shield o ANAVI Thermometer). Registrar en el reporte el
  rechazo con evidencia.
- Diversidad D-30.4 insuficiente → activar respaldo.
- Migración pre/post DRC no coincide → `AskUserQuestion`.
- Cálculo de alguna métrica sin ambigüedad → escenario 5 (aprendizaje
  metodológico), pausar y escalar.

### Salida esperada

Ground truth medido, working/ preparado, features de diversidad
documentadas en `README.md`.

---

## Bloque 1 — Baseline y configuración (30 min)

**Objetivo:** confirmar estado inicial correcto del `working/`.

### Pasos (heredados de sesión 31)

1. Abrir `working/*.kicad_pcb` en KiCad 10.0.4.
2. `run_drc()` sobre `working/` — esperable con muchas violaciones
   `unconnected_items`.
3. Verificar visualmente: footprints presentes apilados en el origen,
   Edge.Cuts intacto, sin tracks/vías/zonas.
4. Snapshot del estado inicial.

### Regla de blindado activa desde este momento

De aquí en adelante y hasta cierre del Bloque 2: NO abrir
`ground-truth-*` con editor.

---

## Bloque 2 — Ejecución del flujo canónico (150 min timeboxed)

**Objetivo:** flujo canónico sobre Miracle Emitter con foco explícito
en features de Nivel B (H1b).

### Pasos del flujo canónico

1. **Resolución de refs duplicados** (si aplica): si Miracle Emitter
   tiene refs duplicados (poco esperable dado que es proyecto
   comercialmente mantenido), aplicar `set_footprint_ref` con precedente
   ADR-0013. NO cuenta como M2.

2. **Colocación asistida** con `get_footprint_neighbors` (D-D4.1
   inclusivo), aplicar D-D3.1 para USB-C (conector con drill).

3. **Plano GND** con `add_zone(fill=True)` (D-26.1).

4. **Refill explícito post-colocación** (D-26.1).

5. **`route_board`** con Freerouting. Registrar `route_ms`.

   **Verificación H1b in-flight:** después de `route_board`, inspeccionar
   inmediatamente:
   - Nets del par diff USB-C (D+/D−): ¿fueron ruteados? Si sí, ¿corren
     en paralelo con separación configurada por la netclass?
   - Nets de la cadena WS2812B: ¿todas conectadas? La topología en
     cadena requiere que cada pixel tenga IN desde el anterior y OUT al
     siguiente.
   - Si alguna feature de H1b falla → registrar `F-V2-XX` con severidad
     asignada, considerar si es P0/P1 (aborto del flujo) o P2 (registro
     y sigue).

6. **Refill final** (D-23.2).

7. **`run_drc()`** → medir DRC del output.

8. **Chequeo específico de vías huérfanas** (reflexión #3 de sesión 31c):
   - Para cada vía en el output, verificar que está conectada a al menos
     un track o pad.
   - Si aparece vía huérfana → registrar `F-V2-VIA-HUERFANA` con nota
     "tercera reincidencia F-D5-01, cumple trigger de promoción a P1
     investigación Fase 4".
   - Si NO aparece → registrar en el reporte "sin reincidencia F-D5-01
     observada".

9. **Medir el output** con
   `validation-suite/tools/measure_ground_truth.py` + análisis por-net.

### Registro de métricas auxiliares durante Bloque 2

**M1 — Tiempo por fase (heredado, con desglose por sub-etapas de
`route_board` si Freerouting reporta).**

**M2 — Intervención humana** (escala heredada). Inicia en 0.
Aplicación de fixes conocidos NO suma.

**M3.a — Integridad estructural crítica** — Pass/Fail heredado.

**M3.b — Cambios geométricos esperables** — rango informativo.

### Regla de timeout de Freerouting (heredada)

- **≤30 min:** normal.
- **30-60 min:** `F-V2-ROUTER-TIMEOUT` (soft), continuar.
- **>60 min:** `F-V2-ROUTER-TIMEOUT-HARD`. Refutación parcial de H1.
  `AskUserQuestion` antes del cierre.

### Criterio de aborto por P0/P1 nuevo

Primera fricción P0/P1 nueva → parar, documentar como `F-V2-XX`,
`AskUserQuestion`.

### Salida esperada

Output ruteado (o hallazgo documentado si aborto), métricas D-30.3
medidas + análisis por-net + tabla DRC separada, M1/M2/M3 registradas,
chequeo H1b + chequeo vías huérfanas registrado.

---

## Bloque 3 — Comparación cuantitativa con análisis descompuesto (60-75 min)

**Objetivo:** aplicar D-30.3 con las tres mejoras interpretativas
heredadas (por-net, DRC separado, análisis H2 sobre 2 puntos).

### Pasos

1. **Cálculo de ratios D-30.3** (heredado).

2. **Análisis descompuesto por-net** (reflexión #1):
   - Tabla de top 5 nets por delta absoluto de longitud.
   - Tabla de top 5 nets por delta porcentual.
   - Detección de nets ruteados en solo uno de los dos (output o ground
     truth) — si aparecen, registrar como P2.

3. **Análisis DRC separado por severidad** (reflexión #2):
   - Tabla de tipos de error DRC del output.
   - Tabla comparativa vs ground truth.
   - Interpretación de pass/fail sobre eléctricos + estructurales, no
     sobre el total.

4. **Aplicar umbrales D-30.3** con matices:
   - Tracks: `|ratio - 1| ≤ 0.30`.
   - Vías: `|ratio - 1| ≤ 0.20` **y** documentar si la base del ground
     truth es pequeña (< 5) — si sí, marcar el resultado como "afectado
     por sesgo de base pequeña" (input directo para revisión post-33).
   - Cobre: `|ratio - 1| ≤ 0.25`.
   - DRC: 0 nuevos errores eléctricos + 0 nuevos errores estructurales.

5. **Actualizar `validation-suite/reports/coverage-matrix.md`** con las
   features cerradas end-to-end de Miracle Emitter. Diferenciar
   claramente las features NUEVAS de Nivel B (USB-C diff-pair, WS2812B
   cadena serial, ESP32-C3) de las heredadas de Nivel A.

### Análisis H2 (segundo punto de evidencia)

Documentar en `metrics.md` sección "Análisis H2":

- ¿Los umbrales fueron discriminantes en este caso?
- **Cross-check con el primer punto (sesión 31c):**
  - Diagnóstico "vías mal calibrado para bases pequeñas" — Miracle
    Emitter ¿tiene base pequeña de vías? Si sí, ¿se reproduce el sesgo?
  - Diagnóstico "DRC estricto no distingue severidad" — con la tabla
    separada, ¿el criterio matizado da un resultado más útil?
- ¿Aparecen dimensiones nuevas de discriminancia no vistas en Nivel A?
- **NO cerrar D-30.3 en sesión 32.** Segundo punto de tres.

---

## Bloque 4 — Reporte, consolidación, cierre (60 min)

**Objetivo:** cerrar sesión 32 y preparar el input para sesión 33.

### Entregables

1. **`validation-suite/level-b/anavi-miracle-emitter/validation-report.md`**
   con formato heredado del template de 31/31b/31c. Debe reutilizar la
   estructura del template pero adaptar la sección "Historia de la
   validación" a una sola sesión (no ciclo de 3 como fue 31).

2. **`docs/historico/sesiones/32-reporte.md`** con resumen ejecutivo:
   - Resultado (cuál de los 7 escenarios).
   - Link al validation-report.
   - Fricciones nuevas.
   - Análisis H2 (segundo punto de evidencia).
   - Estado del patrón F-D5-01 (¿reincidencia? ¿promoción a P1?).

3. **Actualizaciones documentales:**
   - `docs/CONTEXT.md`: estado post-sesión 32.
   - `docs/BACKLOG.md`: fricciones `F-V2-XX` si aplica; F-V1c-01
     actualización según reincidencia.
   - `docs/DECISIONES.md`: si sesión 32 formaliza convención nueva
     (por ejemplo, D-32.1 sobre criterio DRC separado por severidad
     adoptado formalmente), agregarla.
   - `validation-suite/reports/coverage-matrix.md` actualizado.

4. **Análisis metodológico consolidado con dos puntos** — preparación
   para la síntesis final de sesión 33.

### Pre-merge

- Suites offline + integration → verde.
- Gate GUI del DoD → 2/2 × 2 (una sola corrida al inicio si no se tocó
  `src/`).
- `AskUserQuestion` al arquitecto antes de mergear.

---

## Criterios de éxito (7 escenarios heredados)

1. **Éxito pleno:** H1, H1a, H1b, H2 confirmadas.
2. **Éxito con matiz de umbrales:** H1 refutada por 1 criterio, otras ✓.
3. **Éxito con matiz de fricciones P2/P3.**
4. **Aprendizaje por P0/P1 nuevo** (H1a o H1b refutada). Sesión 32b
   intermedia si aplica.
5. **Aprendizaje metodológico** (H2 refutada — métricas no discriminantes
   o dimensión nueva no capturada).
6. **Refutación por escalabilidad** (`F-V2-ROUTER-TIMEOUT-HARD`).
7. **Corrupción crítica** (M3.a fail).

Adicional específico de Nivel B: **si aparece reincidencia F-D5-01**
(tercera vía huérfana en régimen distinto) → agenda sesión de fix
intermedia con severidad P1 investigación Fase 4, INDEPENDIENTE del
escenario que aplique al resto de la sesión.

---

## Entregables completos

1. **Rama** `sesion/32-validation-B-anavi-miracle-emitter` mergeable a
   `master`.
2. **`validation-suite/level-b/anavi-miracle-emitter/`** completo.
3. **`validation-suite/tools/measure_ground_truth.py`** extendido si se
   requirió (con función nueva backwards-compatible).
4. **`validation-suite/reports/coverage-matrix.md`** actualizado con
   features Nivel B.
5. **Reporte** `docs/historico/sesiones/32-reporte.md`.
6. **Actualizaciones** en `docs/CONTEXT.md`, `docs/BACKLOG.md`,
   `docs/DECISIONES.md` (si D-32.x nueva).
7. **Análisis metodológico consolidado** con dos puntos de evidencia
   sobre umbrales D-30.3 — input directo para sesión 33.

---

## Recordatorios operacionales

**Investigación previa al fix cuando el marco entra en conflicto con
evidencia** (patrón 31b). Si durante sesión 32 el estado real contradice
una suposición del prompt, `AskUserQuestion` antes de improvisar.

**Spike de confirmación antes de comprometer enfoque nuevo** (patrón
31b). Si aparece decisión discrecional que altera el flujo canónico
(M2 = 2 o mayor), considerar spike antes.

**Cross-check contra ADRs vigentes** (D-31c.1). Aplicado por el
arquitecto al escribir este prompt; si aparecen decisiones nuevas durante
ejecución, mismo criterio.

**Verificar antes de mutar, no mutar por convención** (patrón sesión
31c). Si el `working/` ya está en el estado esperado, no re-correr
`prepare_working.py` innecesariamente.

---

## Aplicación de D-30.2

**Éxito por confianza, no por código.** Sesión 32 en principio NO toca
`src/`. Un cierre limpio sin escribir código propio es pleno éxito.

Si aparece tensión entre "forzar el cierre" y "documentar honestamente",
elegir documentar. Precedentes: 23, 26, 30, 31, 31c.

---

## Fuera de alcance

- Modificar `src/` salvo P0/P1 nuevo con fix trivial (<30 líneas) →
  `AskUserQuestion` antes.
- Arrancar sesión 33.
- Rediseñar D-30.3.
- Features nuevas al MCP.
- Preparación de release Open Source.
- Resolver deuda de repositorio (`sesion-01` congelada, agendada para
  pre-release).
- Investigación exhaustiva de F-V1c-01 (P2, sólo se vigila reincidencia
  en Bloque 2).

---

## Env vars

Sin cambios. `KICAD_MCP_FREEROUTING_JAR` requerido.

---

## Cierre esperado

Sesión 32 cerrada con:

- Rama mergeada a master.
- Segunda validación Nivel B cerrada con conclusión clara.
- Segundo punto de evidencia real sobre umbrales D-30.3.
- Diversidad D-30.4 documentada explícitamente (features nuevas de
  Nivel B).
- Estado del patrón F-D5-01 documentado (reincidencia o no).
- Coverage matrix con features Nivel A + Nivel B separadas.

**Próxima sesión: 33 = Nivel C** (candidato tentativo: PortaPack H1 con
fork migrado, HackRF One como frontera refutatoria). Selección definitiva
en la conversación pre-sesión 33 siguiendo el patrón de 32 (verificar
2-3 candidatos, no prescribir uno solo).

**Recordatorio final:** sesión 32 es el segundo de tres puntos de
evidencia para la revisión de D-30.3. La calidad de la decisión final
sobre umbrales depende de la calidad del reporte de esta sesión. Rigor
sobre velocidad. Documentación honesta sobre optimismo. `AskUserQuestion`
sobre improvisación.
