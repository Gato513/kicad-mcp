# Sesión 32c — Investigación P1 Fase 4: patrón F-D5-01

**Tipo:** sesión de **investigación pura** (no fix). Aislar el mecanismo
raíz del patrón "conectividad GND que sobrevive al refill sin cerrar"
observado en 3 instancias independientes.

**Rama:** `sesion/32c-investigacion-f-d5-01` desde `master` post-merge
de sesión 32b (`fb00a73`).

**Origen:** promoción a P1 investigación Fase 4 disparada por sesión 32
tras cumplir el trigger de 3 manifestaciones en régimen distinto:
- **F-D5-01** (sesión 25, despertador D5): 2 caps GND unidos entre sí
  por un track pero sin vía propia al plano B.Cu.
- **F-V1c-01** (sesión 31c, anavi-dev-mic): vía GND F.Cu-B.Cu no
  conectada al pad más chico del board (MK1, 0.30×0.30mm).
- **F-V2-VIA-HUERFANA** (sesión 32, anavi-macro-pad-12): 2 pads GND no
  conectados al plano/track tras refill.

**Precedente metodológico central:** **sesión 30** — investigación P1
solder mask ANT1. Aislamiento de mecanismo con precisión
sub-milimétrica, medición directa contra motor real (no aritmética
propia), corrección de errores numéricos de sesiones anteriores,
cierre honesto con o sin fix.

**Precedentes de cierre honesto sin fix** (patrón sesión 23, sesión 26):
si la investigación no converge en un mecanismo raíz aislado dentro
del timebox, la sesión cierra con hallazgos documentados y sin fix. El
progreso está en **reducir la incertidumbre**, no en producir código.

---

## Directriz metodológica central de Fase 4 (nueva, adoptada esta sesión)

**El objetivo principal de una sesión de investigación NO es encontrar
un fix. Es reducir la incertidumbre del proyecto.**

Una sesión de investigación que descarte hipótesis con evidencia sólida
—aunque no produzca cambios de código— es una sesión completamente
exitosa. La confianza en el proyecto sube tanto por saber "qué NO es"
como por saber "qué ES". Precedentes: sesión 23 (loop de vías), sesión
26 (solder mask ANT1 primera investigación), sesión 30 (solder mask
ANT1 aislamiento completo).

Esta directriz se documenta como D-32c.1 al cierre de esta sesión.

---

## Contexto de Fase 4

- **D-30.1 estricta** — hipótesis / evidencia confirmatoria /
  refutatoria / protección antes de tocar experimentos. Ver
  §"Estrategia de investigación".
- **D-30.2 aplica y se refuerza:** éxito = aumento de confianza. Cero
  código puede ser resultado pleno.
- **D-31c.1 aplicada por el arquitecto al escribir este prompt** —
  cross-check ADRs vigentes hecho: ADR-0012 (contrato route_board
  persist), ADR-0013 (set_footprint_ref), D-19.1 (Freerouting no
  respeta plano GND como exclusión). Ninguna decisión metodológica
  de este prompt conflictúa. Detalle: **D-19.1 puede ser central en
  el mecanismo** — ver Hipótesis H2 abajo.
- **Interpretación Fase 4:** las 3 manifestaciones son gaps legítimos
  del flujo sobre configuraciones no ejercitadas antes. NO regresión.

## Alcance operacional

**Dentro:**
- Aislamiento del mecanismo raíz del síndrome "conectividad GND que
  sobrevive al refill sin cerrar" — o refutación explícita de la
  hipótesis de mecanismo raíz común.
- Instrumentación experimental controlada sobre fixtures reales
  (despertador D5, anavi-dev-mic, anavi-macro-pad-12).
- Documentación exhaustiva del hallazgo, sea cual sea.
- **Fix quirúrgico en la misma sesión SI Y SÓLO SI** los tres criterios
  se cumplen simultáneamente:
  1. Mecanismo raíz aislado con evidencia suficiente (nivel sesión 30 —
     medición directa, no correlación).
  2. Cambio claramente quirúrgico (<50 líneas efectivas).
  3. No modifica pipelines críticos de zonas/keepouts, no amplía el
     alcance de la investigación.

En cualquier otro caso: cerrar con investigación documentada, fix
diferido a sesión 32d.

**Fuera** (explícito):
- Refactor de `enforce_hole_clearance` o del pipeline de fill de zonas
  (fuera de alcance salvo que el fix quirúrgico caiga exactamente en
  el criterio del "SI Y SÓLO SI").
- Rediseño del contrato de refill de `route_board` (D-23.2, ADR-0012).
- Nuevas tools o features del MCP.
- Cualquier deuda de BACKLOG no relacionada con F-D5-01.
- Arrancar sesión 33 (Nivel C).
- Investigar la asimetría de `delete_tracks_bulk` observada en 32b
  (deuda diferida, sin relación con este patrón).
- Resolver `sesion-01` congelada (pre-release).

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4.

**Regla operacional específica:** esta es investigación pura. Cero
tolerancia a scope creep. Si aparece tentación de "aprovechar para
mirar también X", `AskUserQuestion` obligatoria. Precedente sesión 30
(35 líneas efectivas de fix + ~200 líneas de documentación) es la
vara.

---

## Estrategia de investigación (D-30.1)

### Hipótesis del mecanismo raíz

Las 3 instancias observadas comparten **síntoma** (conectividad GND
incompleta post-refill) pero tienen **mecanismos aparentes distintos**:

- Sesión 25: 2 caps GND unidos entre sí, sin vía al plano.
- Sesión 31c: vía GND no conectada al pad más chico.
- Sesión 32: 2 pads GND no conectados al plano/track.

**Hipótesis principal H1 — Mecanismo raíz común existe.** Las 3
manifestaciones son proyecciones distintas del mismo bug arquitectónico
subyacente. Candidatos concretos a mecanismo (ordenados por
probabilidad estimada):

- **H1.a — Freerouting no ve el plano GND como conductor** (D-19.1
  documentada, ADR-0012). Freerouting rutea "en el aire" para GND
  porque no interpreta la zona fill del `.dsn` como cobre real,
  entonces conecta pads/caps entre sí con tracks pero omite crear vías
  al plano donde el plano ya "está debajo". Cuando el refill re-fillea
  la zona, el fill de KiCad cierra la mayoría de los caminos pero deja
  islas donde la geometría de tracks/vías generados por Freerouting no
  toca el fill re-computado.
- **H1.b — El refill post-route re-computa el fill con un algoritmo
  que no garantiza conectividad global**. La zona se fillea por regiones
  pero pads en los bordes de esas regiones pueden quedar aislados si
  cierto `min_thickness` o `hatch_gap` interactúa con el keepout de
  `enforce_hole_clearance`.
- **H1.c — Interacción entre `enforce_hole_clearance` y el fill del
  plano**. Los keepouts que sesión 30 confirmó bien dimensionados
  (N=64 vértices, apotema respetado) pueden estar cortando conectividad
  de pads que geométricamente están sobre el plano pero cuyo cobre
  propio no toca el fill re-computado tras el refill.
- **H1.d — Bug en el pipeline `route_board` + refill implícito** — el
  save/reload del board (D-14.3, D-07.1) entre `route_board` y el
  refill puede perder información de conectividad implícita generada
  por Freerouting.

**Hipótesis alternativa H2 — Coincidencia de síntomas, no de mecanismo.**
Las 3 manifestaciones tienen mecanismos genuinamente distintos que
comparten síntoma por accidente. En este caso, F-D5-01 no es un patrón
sistemático — son 3 bugs independientes con manifestación similar.
Este resultado degradaría el hallazgo de P1 a "3 P2 aislados sin
relación", con impacto arquitectónico distinto (menos preocupante
para release).

**Hipótesis H3 — Mecanismo raíz específico de Freerouting.** La causa
está aguas arriba del `.kicad_pcb` — en cómo Freerouting genera el
DSN de salida (tracks + vías) sobre nets GND cuando el plano está
presente. El fix requeriría patch a Freerouting o workaround en el
post-procesado del `.ses` (el archivo que Freerouting devuelve). Es
sub-caso de H1.a pero más específico.

### Metodología de aislamiento (heredada de sesión 30)

1. **Medición directa contra motor real**, no aritmética propia. La
   herramienta base es `kicad-cli pcb drc --format json` sobre copias
   controladas + inspección del `filled_polygon` de la zona en el
   `.kicad_pcb`.
2. **Auto-corrección durante la sesión.** Si durante la investigación
   se descubre que la medición inicial tenía un error (patrón sesión
   26 → 30 con la clearance de netclass vs `min_copper_edge_clearance`),
   parar, corregir, re-verificar.
3. **Sub-líneas escalonadas.** Si la hipótesis principal se refuta,
   pasar a la siguiente. No forzar convergencia con evidencia
   insuficiente.
4. **Fixture central + fixtures de control.** Empezar por la
   manifestación más reciente (anavi-macro-pad-12), mantener las otras
   2 como controles de reproducibilidad.
5. **Instrumentación reproducible.** Si se escribe un harness para
   medir la geometría del fill o para inyectar keepouts, versionar en
   `scratchpad/` para que sea reutilizable — precedente sesión 30
   (`scratchpad/solder-mask/sweep.py`).

### Evidencia confirmatoria

- **H1.a confirmada:** medición directa sobre el `.ses` de Freerouting
  muestra que para nets GND, Freerouting genera tracks entre pads pero
  omite sistemáticamente vías al plano cuando el plano cubre la región.
  Reproducible en las 3 manifestaciones.
- **H1.b confirmada:** el `filled_polygon` del `.kicad_pcb` post-refill
  muestra fracturas topológicas en las 3 manifestaciones cuya geometría
  correlaciona con parámetros de fill (`min_thickness`, `hatch_gap`).
- **H1.c confirmada:** los keepouts de `enforce_hole_clearance` cortan
  cobertura del pad problemático — medición del apotema del keepout vs
  posición del borde del fill (patrón sesión 30, ahora aplicado a la
  conectividad pad-plano en vez de a máscara).
- **H1.d confirmada:** captura de `board.zones[i].filled_polygon` antes
  y después del ciclo save/reload muestra diferencia — con misma zona,
  mismos parámetros, mismo timestamp.

### Evidencia refutatoria (H2)

Los tres experimentos de reproducción sobre las manifestaciones
individuales muestran mecanismos genuinamente distintos, sin
convergencia:
- El pad de macro-pad-12 falla por geometría X.
- La vía de anavi-dev-mic falla por geometría Y (no X).
- Los caps del despertador D5 fallan por interacción Z (no X ni Y).

Refutación de H1 → adopción de H2. **Resultado sigue siendo pleno
éxito** — reduce la incertidumbre y previene fix apresurado basado en
correlación de síntomas.

### Protección contra regresiones

Esta es investigación, no fix. La protección aplica en dos direcciones:

- **Contra regresión de lo estable:** los experimentos NO modifican el
  código de `src/` salvo que caiga el "SI Y SÓLO SI" del fix
  quirúrgico. Los fixtures (`tests/fixtures/despertador-routed/`,
  `validation-suite/level-a/anavi-dev-mic/`,
  `validation-suite/level-b/anavi-macro-pad-12/`) son de solo lectura —
  todas las mutaciones ocurren en `/tmp/` sobre copias.
- **Contra propagación de conclusiones especulativas:** si el
  aislamiento no converge, el reporte debe decir explícitamente "no
  se aisló mecanismo raíz" — no debe inventar un mecanismo probable
  sin evidencia. Precedente sesión 26: cerró con hallazgo
  parcial explícito, no forzó fix.

---

## Preparación

1. Verificar que `master` incluye la secuencia 31→31b→31c→32→32b
   mergeada (commit `fb00a73` o el hash equivalente post-merge).
2. `git checkout master && git pull` (si aplica).
3. `git checkout -b sesion/32c-investigacion-f-d5-01`.
4. **Fixtures de investigación:**
   - Copia limpia de `tests/fixtures/despertador-routed/` en
     `/tmp/f-d5-01-despertador/`.
   - Copia limpia de `validation-suite/level-a/anavi-dev-mic/working/`
     en `/tmp/f-d5-01-anavi-dev-mic/`.
   - Copia limpia de `validation-suite/level-b/anavi-macro-pad-12/working/`
     en `/tmp/f-d5-01-macro-pad/` — **fixture central de investigación**.
5. `/tmp/gui-test-project/` NO se toca (no aplica en esta sesión salvo
   fix quirúrgico).
6. **Lectura obligatoria** antes de arrancar:
   - `docs/historico/sesiones/25-reporte.md` §F-D5-01 (primera
     manifestación).
   - `docs/historico/sesiones/31c-reporte.md` §F-V1c-01.
   - `docs/historico/sesiones/32-reporte.md` §F-V2-VIA-HUERFANA.
   - `docs/adr/0012-route-board-persist-contract.md` (contrato refill).
   - `docs/DECISIONES.md` D-19.1 (Freerouting no respeta plano GND
     como exclusión) — **potencialmente central en H1.a**.
   - `docs/investigacion/30-solder-mask-ant1.md` (patrón metodológico
     de referencia para esta sesión).

---

## Timebox flexible con checkpoint

**Timebox base:** 4 horas nominales. **Checkpoint a las 3 horas.**

A las 3h de trabajo efectivo, evaluación explícita:

- **Si el mecanismo raíz está aislado o cerca de aislarse** con
  evidencia sólida → continuar hasta 4h, cerrar con hallazgo completo.
- **Si el fix quirúrgico está identificado y cumple el "SI Y SÓLO SI"**
  → continuar hasta 4h (o más con `AskUserQuestion`) para aplicarlo y
  verificarlo.
- **Si múltiples hipótesis están refutadas pero ninguna confirmada** →
  continuar hasta 4h para intentar hipótesis siguientes.
- **Si el aislamiento no progresa** (>3h sin evidencia decisiva y sin
  hipótesis siguiente clara) → `AskUserQuestion` obligatoria. Opciones:
  cerrar honestamente con lo obtenido, o extender con hipótesis
  específica.

**No hay tope duro** salvo el sentido común. Sesión 30 tomó una
sesión completa; sesión 32c puede tomar menos, igual, o (con
justificación) marginalmente más. Precedente sesión 26 (cierre a las
~3h con hallazgo parcial explícito) es válido.

---

## Bloque 0 — Inspección de las 3 manifestaciones (30-45 min)

**Objetivo:** confirmar que reproducimos las 3 manifestaciones sobre
sus fixtures antes de arrancar la investigación. Establecer el
baseline observacional.

### Sub-bloque 0.1 — Manifestación central (macro-pad-12)

1. Sobre `/tmp/f-d5-01-macro-pad/`: cargar el output ruteado de
   sesión 32 (o re-ejecutar `route_board` + refill si necesario).
2. Identificar los 2 pads GND no conectados con `kicad-cli pcb drc
   --format json` — deben aparecer las violaciones registradas en
   sesión 32.
3. Extraer el `filled_polygon` de la zona GND en B.Cu para inspección
   posterior.
4. Registrar geometría exacta: coordenadas de los 2 pads, distancia al
   borde más cercano del `filled_polygon`, keepouts
   `__kicadmcp_hc__*` circundantes.

### Sub-bloque 0.2 — Manifestaciones secundarias (control)

Para cada una:
- `/tmp/f-d5-01-anavi-dev-mic/`: cargar el output ruteado de 31c,
  reproducir la vía huérfana MK1.
- `/tmp/f-d5-01-despertador/`: cargar el estado post-D5, reproducir
  los 2 caps GND sin vía al plano.

Solo registrar geometría (coordenadas, distancias, keepouts). NO
experimentar todavía.

### Gate del Bloque 0

- Si las 3 manifestaciones reproducen sobre sus fixtures → seguir a
  Bloque 1.
- Si alguna NO reproduce → `AskUserQuestion`. Puede ser que el
  fixture haya sido mutado desde el reporte original, o que haya
  refill posterior que enmascare — investigación distinta.

### Salida esperada

3 archivos de geometría (uno por manifestación) con coordenadas exactas
+ inspección visual (posible con `kicad-cli pcb render` o similar).
Baseline observacional establecido.

---

## Bloque 1 — Sub-líneas de investigación escalonadas (2-2.5h)

Ordenadas por probabilidad estimada y costo de instrumentación. Cada
sub-línea es autocontenida — al cerrar cada una, evaluar si confirma
o refuta H1.X, y decidir si pasar a la siguiente.

**Regla de escalada:** si una sub-línea confirma su hipótesis con
evidencia decisiva sobre las 3 manifestaciones, NO continuar a las
siguientes (patrón sesión 30 §"no fue necesario continuar a la
sub-línea 2.3"). Si confirma parcialmente (1-2 de 3), decidir si
continuar como refinamiento o si abrir sub-línea nueva.

### Sub-línea 1.a — Freerouting no genera vía al plano (D-19.1)

**Hipótesis:** para nets GND, Freerouting genera tracks entre pads
pero omite sistemáticamente vías al plano cuando el plano cubre la
región. D-19.1 documenta que Freerouting no ve el plano como
exclusión — extensión probable: tampoco lo ve como conductor destino.

**Instrumentación:**
1. Sobre macro-pad-12: extraer el `.ses` de Freerouting (archivo de
   salida antes del import a `.kicad_pcb`).
2. Parsear tracks y vías generados para el net GND específico.
3. Verificar: ¿hay vía en la región del pad huérfano? Si no hay,
   confirma parcialmente.
4. Repetir sobre las 2 manifestaciones de control.

**Confirmación decisiva:** las 3 manifestaciones muestran ausencia
sistemática de vía al plano en la región del componente huérfano.

**Refutación:** las 3 muestran vía presente en el `.ses` pero no en
el `.kicad_pcb` post-refill → mecanismo aguas abajo (H1.b, H1.d).

**Costo estimado:** 30-45 min.

### Sub-línea 1.b — Fill del plano no garantiza conectividad global

**Hipótesis:** el `filled_polygon` post-refill tiene fracturas
topológicas que aíslan los componentes huérfanos, aunque
geométricamente estén sobre el plano.

**Instrumentación:**
1. Sobre macro-pad-12: extraer `filled_polygon` de la zona GND.
2. Verificar conectividad topológica: usar `shapely` u homólogo para
   detectar si el `filled_polygon` es un único polígono conectado o
   múltiples islas.
3. Si son múltiples islas, verificar en qué isla cae cada pad GND.
4. Comparar con las 2 manifestaciones de control.

**Confirmación decisiva:** los pads huérfanos caen en islas separadas
del `filled_polygon` en las 3 manifestaciones.

**Refutación:** el `filled_polygon` es un único polígono conectado
que contiene los pads huérfanos → mecanismo distinto (H1.c o H1.a).

**Costo estimado:** 30-45 min.

### Sub-línea 1.c — Interacción `enforce_hole_clearance` × fill

**Hipótesis:** los keepouts que sesión 30 confirmó bien dimensionados
para máscara pueden estar cortando conectividad de pads que
geométricamente están sobre el plano pero cuyo cobre propio no toca el
fill re-computado tras el refill.

**Instrumentación:**
1. Sobre macro-pad-12: medir distancia del centro de los 2 pads GND al
   borde más cercano del keepout `__kicadmcp_hc__*` de otro footprint
   cercano.
2. Medir apotema del keepout circundante (sesión 30 confirmó apotema =
   `r·cos(π/N)` con N=64).
3. Medir distancia del centro del pad al borde del `filled_polygon`.
4. Verificar: ¿el keepout de un vecino corta el fill donde debería
   estar el pad huérfano?

**Confirmación decisiva:** en las 3 manifestaciones, el keepout de
`enforce_hole_clearance` de un footprint vecino explica la fractura
topológica.

**Refutación:** los keepouts no correlacionan con las fracturas → H1.c
descartada, mecanismo distinto.

**Costo estimado:** 30-45 min. Requiere aplicar precedente sesión 30
(medición vs apotema teórico).

### Sub-línea 1.d — Pipeline save/reload rompe conectividad

**Hipótesis:** el ciclo save/reload entre `route_board` y refill (D-14.3
+ D-07.1) pierde información de conectividad implícita generada por
Freerouting.

**Instrumentación:**
1. Sobre macro-pad-12: interceptar antes del reload (post-Freerouting,
   pre-`reload_board_from_disk`) el `.kicad_pcb` intermedio.
2. Extraer `filled_polygon` de ese estado intermedio (antes de reload).
3. Comparar con `filled_polygon` post-reload+refill.
4. Verificar: ¿hay diferencia topológica introducida por el reload?

**Confirmación decisiva:** el `filled_polygon` pre-reload NO tiene la
fractura; post-reload+refill SÍ la tiene, en las 3 manifestaciones.

**Refutación:** el `filled_polygon` intermedio ya tiene la fractura →
el reload no es la causa, mecanismo es upstream (H1.a) o intrínseco al
fill (H1.b).

**Costo estimado:** 45-60 min. Requiere instrumentación más invasiva
(interceptar el pipeline).

### Sub-línea 1.e — Adopción de H2 (coincidencia de síntomas)

Si las sub-líneas 1.a-1.d refutan cada una individualmente sobre las 3
manifestaciones sin converger en un mecanismo común → H2 se adopta.

**Instrumentación:** revisión honesta de la evidencia acumulada.
Cada manifestación se documenta con su mecanismo específico observado
(o "mecanismo específico no aislado" si aplica), y se registra como
3 P2 independientes con nota de "3 síntomas similares sin mecanismo
raíz común identificado en investigación 32c".

**Este es un resultado válido y esperable** — 30-40% de probabilidad
subjetiva. NO forzar convergencia si la evidencia no la sostiene.

---

## Bloque 2 — Decisión sobre fix (si aplica) (0-60 min)

**Solo se entra a este bloque si el "SI Y SÓLO SI" del alcance se cumple:**

1. Mecanismo raíz aislado con evidencia (patrón sesión 30, medición
   directa).
2. Fix quirúrgico <50 líneas efectivas.
3. No modifica pipeline crítico de zonas/keepouts, no amplía alcance.

Si los 3 se cumplen: aplicar fix en la misma sesión, con tests unit +
integration + gate GUI del DoD del pipeline afectado.

Si alguno NO se cumple: **fix diferido a sesión 32d.** Documentar
la hipótesis de fix con toda la evidencia acumulada — el ejecutor de
32d va a tener el ADR y el reporte de 32c como input completo.

Cross-check ADRs vigentes obligatorio antes de aplicar (D-31c.1).

---

## Bloque 3 — Consolidación documental (30-45 min)

**Objetivo:** dejar el registro completo, sea cual sea el resultado.

### Entregables documentales

1. **`docs/investigacion/32c-f-d5-01.md`** — reporte de investigación
   con formato heredado de `docs/investigacion/30-solder-mask-ant1.md`:
   - Contexto (3 manifestaciones + trigger de promoción a P1).
   - Metodología (sub-líneas escalonadas, medición directa).
   - Sub-línea por sub-línea con hallazgos, confirmaciones,
     refutaciones. **Cada sub-línea con evidencia sólida y numérica**,
     no correlaciones vagas.
   - Conclusión: mecanismo raíz aislado (con nombre, ecuación, o
     descripción precisa) o adopción de H2 con evidencia de refutación
     de H1.a-d.
   - Recomendación para BACKLOG.
   - Nota metodológica sobre auto-correcciones durante la sesión
     (si aplicaron — patrón sesión 30 §2.1).

2. **`docs/historico/sesiones/32c-reporte.md`** — reporte ejecutivo
   con resumen, evidencia por hipótesis, decisión sobre fix (aplicado,
   diferido, o no aplicable), próximo paso.

3. **`docs/BACKLOG.md`** — actualización de `F-D5-01/F-V1c-01/
   F-V2-VIA-HUERFANA`:
   - Si mecanismo aislado + fix aplicado: cerrado con detalle del fix.
   - Si mecanismo aislado + fix diferido: P1 activo con hipótesis
     concreta de fix documentada + referencia al reporte.
   - Si mecanismo no aislado + H1 no refutada del todo: P1 activo con
     "línea de investigación específica siguiente" documentada.
   - Si H2 adoptada: degradado a 3 P2 aislados con nota de "3 síntomas
     similares sin mecanismo raíz común identificado en investigación
     32c".

4. **`docs/DECISIONES.md`:**
   - **D-32c.1** (obligatoria, se registra al cierre independientemente
     del resultado): "El objetivo principal de una sesión de
     investigación NO es encontrar un fix. Es reducir la incertidumbre
     del proyecto. Una sesión de investigación que descarte hipótesis
     con evidencia sólida —aunque no produzca cambios de código— es una
     sesión completamente exitosa." Origen: directriz metodológica
     adoptada por el arquitecto pre-sesión 32c, formalizada al cierre.
     Precedentes: sesión 23, 26, 30.
   - Si mecanismo aislado y fix aplicado: **D-32c.2** con la decisión
     técnica del fix (referencia al ADR nuevo o extensión de ADR-0012).
   - Si adoptamos H2: **D-32c.2 alternativa** con la decisión de
     degradar a 3 P2 aislados y no seguir tratando como patrón único.

5. **`docs/adr/`** — si el fix se aplica en esta sesión:
   - Si extiende ADR-0012 (contrato refill): sección "Extensión F-D5-01
     (sesión 32c)".
   - Si es mecanismo distinto: **ADR-0014** o el número que corresponda.
   - Recomendación: verificar contra convenciones del proyecto en
     `AskUserQuestion` pre-merge.

6. **`docs/CONTEXT.md`** — estado post-sesión 32c, próxima sesión = 33
   Nivel C (o 32d si fix diferido).

### Pre-merge

- Suites offline (`pytest -m "not integration"`) → verde. Si fix
  aplicado, incluye tests nuevos.
- Suites integration (`pytest -m integration`) → verde.
- Gate GUI del DoD contra `/tmp/kicad-mcp-sesion32c-gui/` (copia
  fresca) → 2/2 × 2 SOLO SI se aplicó fix. Si no hubo fix, gate GUI no
  requerido (patrón sesión 26).
- `AskUserQuestion` al arquitecto antes de mergear con: reporte
  ejecutivo, decisión sobre fix, estado del BACKLOG.

---

## Criterios de éxito

Todos son plenos éxitos si están honestamente documentados. **D-30.2
aplicada estrictamente + D-32c.1 nueva.**

1. **Mecanismo raíz aislado + fix aplicado** (patrón sesión 30). Todos
   los gates verdes. Confianza +alta.

2. **Mecanismo raíz aislado + fix diferido** (no cumple "SI Y SÓLO
   SI"). Confianza +alta sobre el bug, próxima sesión 32d tiene ADR
   completo como input.

3. **Mecanismo raíz aislado + adopción de H1.X específica con evidencia
   fuerte sobre 2 de 3 manifestaciones**. Cierre parcial honesto:
   documentar la manifestación no explicada como excepción con
   hipótesis específica siguiente.

4. **H1 refutada + H2 adoptada** — 3 P2 aislados sin mecanismo común.
   Confianza +alta sobre lo que el bug NO es. Descarga presión
   arquitectónica sobre F-D5-01 (baja de "patrón sistemático" a "3
   bugs independientes").

5. **Investigación abierta con hipótesis siguiente específica** — no
   se aisló mecanismo pero se refutaron algunas sub-líneas y hay línea
   siguiente concreta. F-D5-01 sigue P1 con hipótesis explícita para
   sesión 32d.

6. **Investigación abierta sin hipótesis siguiente clara** — no se
   aisló nada, todas las sub-líneas dieron resultados ambiguos.
   `AskUserQuestion` al cierre sobre degradar a P2 con nota o mantener
   P1 con la línea de investigación que quede menos refutada.

**NO son éxito:**
- Cierre con fix aplicado sin evidencia sólida de mecanismo (patrón
  sesión 26 primer intento — expresamente evitar).
- Cierre con conclusión especulativa sin backup empírico.
- Scope creep hacia otras deudas de BACKLOG.

---

## Entregables

1. **Rama** `sesion/32c-investigacion-f-d5-01` mergeable a `master`.
2. **`docs/investigacion/32c-f-d5-01.md`** — reporte de investigación
   completo, formato heredado de 30-solder-mask-ant1.md.
3. **`docs/historico/sesiones/32c-reporte.md`** — reporte ejecutivo.
4. **`docs/BACKLOG.md`** — F-D5-01/F-V1c-01/F-V2-VIA-HUERFANA
   actualizado según resultado.
5. **`docs/DECISIONES.md`** — D-32c.1 (obligatoria) + D-32c.2 (según
   resultado).
6. **`docs/CONTEXT.md`** — estado post-32c.
7. **Fix aplicado + tests + ADR** — SOLO si el "SI Y SÓLO SI" se cumple.
8. **Instrumentación reusable** — scripts de análisis en `scratchpad/`
   (patrón sesión 30 `scratchpad/solder-mask/sweep.py`).

---

## Recordatorios operacionales

**Investigación previa antes de tocar código** (patrón sesión 30 y
32b). Antes de cualquier hipótesis de fix, el mecanismo tiene que
estar aislado con evidencia numérica.

**Auto-corrección durante la sesión** (patrón sesión 30 §2.1). Si
descubrís que una medición inicial estaba mal (por ejemplo, la
distancia se midió a vértice cuando debía ser a segmento), parar,
corregir, re-verificar. NO seguir con la medición mal — contamina la
conclusión.

**Refutación es progreso** (D-32c.1). Descartar una hipótesis con
evidencia sólida vale tanto como confirmar otra. No forzar
convergencia.

**Cross-check contra ADRs vigentes** (D-31c.1). El arquitecto lo hizo
para este prompt (ADR-0012, ADR-0013, D-19.1). Si aparecen decisiones
nuevas durante ejecución, mismo criterio.

**Fix quirúrgico o diferido**, nunca ampliar alcance (regla dura del
prompt). El "SI Y SÓLO SI" es intencionalmente restrictivo.

---

## Aplicación de D-30.2 + D-32c.1

**Éxito por confianza, no por código.** Los 6 escenarios de éxito son
todos válidos si están honestamente documentados. Un cierre sin código
puede ser el resultado más valioso — patrón sesión 26 estableció
precedente, D-32c.1 lo formaliza como principio de Fase 4.

Si aparece tensión entre "forzar convergencia" y "documentar
honestamente lo que se sabe y lo que no", elegir documentar.

---

## Env vars

Sin cambios. `KICAD_MCP_FREEROUTING_JAR` disponible si se necesita
re-ejecutar `route_board` sobre alguna manifestación
(jar del plugin KiCad 9.0 documentado en sesión 32b).

---

## Cierre esperado

Sesión 32c cerrada con **al menos uno** de los siguientes:

- Mecanismo raíz de F-D5-01 aislado + fix aplicado o diferido con
  hipótesis concreta.
- H2 adoptada con evidencia sólida de refutación de H1.a-d.
- Investigación abierta con línea siguiente específica y refutaciones
  documentadas.

Cualquiera de los tres cierra la sesión honestamente y avanza el
proyecto. Confianza +alta en los tres casos.

**Próxima sesión:**
- **Si fix aplicado:** sesión 33 = Nivel C.
- **Si fix diferido:** sesión 32d = aplicación del fix con ADR de
  32c como input completo, después sesión 33.
- **Si H2 adoptada:** sesión 33 = Nivel C (F-D5-01 degradada, no
  bloquea).
- **Si investigación abierta con línea siguiente:** sesión 32d =
  continuación con esa línea, después sesión 33.

**Recordatorio final:** el objetivo NO es encontrar un fix. Es reducir
la incertidumbre. Sesión 30 lo hizo aislando el mecanismo. Sesión 26
lo hizo cerrando honestamente sin fix (aunque parecía derrota, era
progreso — el terreno quedó listo para sesión 30). Sesión 32c está
diseñada para poder cerrar honestamente en cualquiera de las
direcciones. Rigor sobre optimismo. Documentación sobre especulación.
