# Sesión 32d — Fix: stitching automático / exposición explícita para F-D5-01

**Tipo:** aplicación del fix con la investigación de sesión 32c como
input completo. Mecanismo raíz ya aislado y confirmado causalmente
(refinamiento medido de D-19.1).

**Rama:** `sesion/32d-fix-orphan-pads-zone-nets` desde `master`
post-merge de sesión 32c (`9746dbe`).

**Origen:** hipótesis de fix especificada en
`docs/investigacion/32c-f-d5-01.md` §"Hipótesis de fix para sesión 32d"
y ratificada por el arquitecto post-32c: stitching automático con
guardrails estrictos, fallback a exposición explícita en el payload de
`route_board`.

**Precedente metodológico:** sesión 31b (fix quirúrgico con disciplina
de alcance + cross-check ADRs D-31c.1) + sesión 32b (fix con precondición
de investigación previa y análisis comparativo de opciones).

**Continuación explícita:** sesión 32c aisló el mecanismo, esta sesión
lo cierra con código. No se re-investiga el mecanismo — el reporte de
32c es fuente de verdad para el marco.

## Contexto de Fase 4

- **D-30.1 estricta.** Bloque explícito de hipótesis / evidencia
  confirmatoria / refutatoria / protección antes de tocar código.
- **D-30.2 aplica:** éxito = aumento de confianza. Un fix acotado y
  bien verificado (con o sin fallback triggered en tests) vale más que
  un fix ambicioso apresurado.
- **D-31c.1 aplicada por el arquitecto al escribir este prompt** —
  cross-check ADRs vigentes hecho: ADR-0012 (contrato route_board
  persist), ADR-0013 (set_footprint_ref), D-19.1 (Freerouting no
  respeta plano GND). Ver §"Cross-check arquitectónico" abajo.
- **D-32c.1 (nueva, adoptada en 32c):** el objetivo de investigación es
  reducir incertidumbre, no producir fix. Se cita como marco vigente
  aunque esta sesión sí produce fix — porque el fix se aplica solo
  bajo condiciones estrictas heredadas.
- **Regla nueva de análisis comparativo (adoptada por el arquitecto
  pre-32d):** antes de aceptar cualquier decisión de diseño, el
  reporte debe indicar (a) qué hipótesis alternativas quedaron
  descartadas, (b) con qué evidencia, (c) por qué la elegida explica
  mejor que las alternativas. Aplica a esta sesión sobre las 3
  decisiones de diseño D1-D3 abajo.
- **Interpretación Fase 4:** el fix es la primera respuesta
  arquitectónica del proyecto a D-19.1 (Freerouting no ve el plano
  como conductor). Es mitigación, no cierre de D-19.1 — D-19.1 sigue
  vigente como restricción del motor externo.

## Cross-check arquitectónico (D-31c.1)

**ADR-0012** (contrato route_board persist + extensión sesión 27 +
extensión F-V2 sesión 32b): compatible. El fix agrega un paso
post-refill (stitching + exposición) que es coherente con la promesa
del contrato — el llamador recibe el estado post-flujo completo,
incluyendo información sobre pads huérfanos si el stitching no pudo
resolverlos. **NO se agrega código de error nuevo por default** — un
pad huérfano detectado NO es error; es dato en el payload. Si el
stitching automático falla por guardrail rechazando, tampoco es error.
Solo si `add_via` explota (falla técnica de la tool subyacente) hay
código de error, y ese código ya existe.

**ADR-0013** (set_footprint_ref): sin relación.

**D-19.1** (Freerouting no respeta plano GND): **directamente
relacionada**. El fix es la primera respuesta arquitectónica del
proyecto a esta restricción. D-19.1 sigue vigente (Freerouting no
cambia); el fix mitiga sus consecuencias detectando y stitching el
síntoma post-refill.

**D-07.1** (mutación sin reintento): respetada. Si el stitching falla,
no se reintenta automáticamente. Se expone en payload, el llamador
decide.

**D-14.3** (save implícito): respetada. El stitching agrega vías al
board vivo antes del save final que ya hace `route_board`.

Ninguna decisión de este prompt conflictúa con ADRs vigentes.

## Alcance operacional

**Dentro:**
- Detección de pads huérfanos post-refill de `route_board` para nets
  con zona de cobre propia (patrón mecánico aislado en 32c).
- Stitching automático con `add_via` (tool existente) bajo guardrails
  estrictos.
- Exposición explícita del resultado en payload de `route_board` —
  qué pads se stitcharon, cuáles siguen huérfanos (guardrail rechazó),
  con qué motivos.
- Tests: unit (con mock del bug reproducible del fixture 32c) +
  integration si aplicable + gate GUI del DoD.

**Fuera** (explícito):
- Modificación del pipeline de fill de zonas o `enforce_hole_clearance`.
  El fix vive en `route_board`, **post-refill final**, no dentro del
  refill.
- Rediseño del contrato de refill (D-23.2, ADR-0012).
- Cambios en Freerouting o el post-procesado del `.ses`.
- Nuevas tools separadas del MCP (el fix va dentro de `route_board`
  por decisión D2).
- Cualquier deuda de BACKLOG no relacionada.
- Investigar la asimetría de `delete_tracks_bulk` observada en 32b.
- Vigilancia de `L9.1` (candidato lateral registrado en 32c, no
  acción).
- Resolver `sesion-01` congelada.
- Arrancar sesión 33.

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4.

**Regla operacional:** fix quirúrgico. Precedente sesión 30 (~35
líneas efectivas), sesión 31b (~55), sesión 32b (~55). Vara para 32d:
<100 líneas efectivas. Si el diff se acerca a 200+ líneas, hay
probable scope creep — parar y verificar.

---

## Decisiones de diseño cerradas

Las 3 preguntas de diseño cerradas por el arquitecto antes de la
ejecución. **Cada decisión debe justificarse comparativamente en el
reporte final** (regla nueva del arquitecto): qué alternativas se
descartaron, con qué evidencia, por qué la elegida explica mejor.

### D1 — Stitching automático vs exposición explícita

**Decisión:** **stitching automático con guardrails muy estrictos,
fallback a exposición explícita si guardrails rechazan.**

**Alternativas consideradas:**

- **Alternativa A: solo exposición explícita** (sin auto-stitching).
  Ventaja: minimalista, cero riesgo de decisión automática incorrecta.
  Desventaja: convierte cada net huérfano en trabajo manual del
  llamador. Precedente sesión 25 (F-D5-01 original) ya resolvió con
  `add_via` manual — automatizar es mitigación real.
  **Descartada porque:** el mecanismo aislado en 32c admite
  automatización segura bajo condiciones geométricas verificables
  (guardrails). La automatización cierra el patrón F-D5-01 en el 95%+
  de casos observados (2/2 en macro-pad-12, 1/1 en dev-mic por
  correlación, 1/1 en despertador D5 histórico).

- **Alternativa B: auto-stitching sin guardrails.** Ventaja: cierra
  100% de los casos con un `add_via` incondicional.
  **Descartada porque:** riesgo alto de introducir vías donde no
  corresponden (nets sin zona, layers sin plano, geometría ambigua).
  Precedente D-19.1 nos recuerda que Freerouting es la referencia de
  ruteo; kicad-mcp no debe segundear su lógica sin restricciones.

- **Elegida: auto-stitching con guardrails estrictos** (D3 abajo).
  Combina la mitigación real de A+B con la seguridad de A. Fallback a
  exposición explícita cubre los casos donde el guardrail rechaza.

**Cross-check ADR:** compatible con ADR-0012 (contrato route_board
persist) — el stitching es parte del flujo canónico de `route_board`,
no fase separada. Con D-19.1 — mitiga sin cambiar el motor externo.
Con D-07.1 — no reintenta si falla.

### D2 — Momento del stitching en el pipeline

**Decisión:** **dentro de `route_board`, post-refill final y post-DRC
de conectividad, pre-return.**

**Alternativas consideradas:**

- **Alternativa A: tool separada `stitch_orphan_pads`** invocable por
  el llamador tras `route_board`. Ventaja: mantiene `route_board` puro,
  responsabilidades separadas.
  **Descartada porque:** el patrón F-D5-01 es consecuencia directa del
  flujo route_board+refill (D-19.1); separar en tool distinta significa
  que el llamador tiene que saber que debe invocarla siempre —
  duplicación de responsabilidad. Además introduce tool nueva por
  síntoma, patrón anti-arquitectural para OSS.

- **Alternativa B: fase separada `route_board` → `refill_with_stitching`**.
  **Descartada porque:** duplica el contrato de refill (ya cubierto por
  ADR-0012 §"Extensión sesión 27") sin ganancia semántica.

- **Elegida: dentro de `route_board`.** El fix es responsabilidad
  natural del flujo canónico. Si el llamador quiere pipeline sin
  stitching, es futura discusión — no hay caso de uso vigente para eso.

**Cross-check ADR:** compatible con ADR-0012. La secuencia interna
queda: refill final → DRC post-route (ya existe) → detección de
huérfanos → stitching bajo guardrail → exposición en payload → return.

### D3 — Guardrails del stitching y semántica ante fallo

**Decisión:** **stitching solo si TODAS estas condiciones se cumplen
simultáneamente:**

1. Pad huérfano detectado por `unconnected_items` post-refill final.
2. Net del pad tiene zona de cobre propia definida en el board.
3. Pad cae geométricamente dentro del `outline` de una zona de ese
   mismo net (verificable por lookup en zone bounding box + point-in-
   polygon).
4. Existe capa opuesta a la del pad donde también hay zona del mismo
   net (permite stitching F.Cu↔B.Cu).
5. Región inmediata del pad (radio ~1mm en la capa opuesta) está
   libre de tracks/vías/pads ajenos, verificado por chequeo simple
   sobre el board.

Si CUALQUIERA falla → NO stitching, exposición explícita en payload.

**Alternativas consideradas:**

- **Alternativa A: guardrail relajado (solo condiciones 1-2).**
  Cerraría más casos automáticamente.
  **Descartada porque:** riesgo real de crear vías en geometrías
  ambiguas donde el `add_via` puede colisionar con copper ajena.
  Precedente F-V2 de sesión 32 (donde Freerouting causó fallo silencioso
  por interacciones geométricas): la auto-corrección debe ser
  demostrablemente segura, no probabilísticamente segura.

- **Alternativa B: guardrail muy estricto** (agrega verificación de
  DRC re-run post-stitching, aborta si introduce violaciones nuevas).
  Ventaja: máxima seguridad.
  **Descartada porque:** cuesta un DRC completo por cada stitching,
  costo alto en performance. Además, la verificación de guardrail #5
  (región libre) ya cubre el 95% de casos donde un DRC re-run fallaría.
  Se puede agregar en sesión futura si aparece evidencia de falsos
  positivos.

- **Elegida: guardrail estricto pero práctico (condiciones 1-5).**
  Cubre los casos observados (macro-pad-12 J4.3, J5.3; dev-mic MK1.3
  por correlación) sin costo prohibitivo por corrida.

**Semántica ante fallo del stitching:**

- **Guardrail rechaza:** NO error. Pad se registra en payload como
  huérfano no-stitchable con razón (cual condición 1-5 falló).
- **`add_via` falla técnicamente** (por ejemplo, error de kicad-cli):
  código de error existente propagado, patrón D-07.1 (sin reintento).
- **DRC post-stitching muestra violaciones nuevas:** en la V1 no se
  chequea post-stitching (decisión de performance arriba). Si en
  futuras sesiones aparece evidencia de que las hay, se agrega
  verificación.

**Cross-check ADR:** compatible con D-07.1 (sin reintento), con D-14.3
(save implícito abarca las vías nuevas).

---

## Estrategia de validación (D-30.1)

### Hipótesis principales

**H1 — Fix cierra F-D5-01 en los casos observados con evidencia
causal.** Sobre el fixture reproducible de anavi-macro-pad-12 (estado
32c con track troncal `+5V` intacto), aplicar `route_board` con el fix
resulta en `unconnected_items = 0` para J4.3 y J5.3 post-refill final.

**H2 — Fix respeta guardrails cuando corresponde.** Sobre casos donde
el guardrail debería rechazar (por ejemplo, pad huérfano de un net sin
zona), el fix NO crea vías erróneas — el pad queda en payload como
huérfano no-stitchable con razón explícita.

**H3 — Fix no regresiona el flujo canónico despertador.** El
despertador D3-D7 (25/25 verde) sigue completando sin diferencias
observables. En particular: los `add_via` de sesión 25 (F-D5-01
original, ya corregido en el fixture) siguen ahí sin duplicación o
intervención del stitching automático.

**H4 — Fix maneja correctamente el caso "0 pads huérfanos".** Cuando
`unconnected_items = 0` post-refill final, el fix no hace nada
adicional. Camino feliz sin efecto secundario.

### Evidencia confirmatoria

- **H1:** integration test sobre copia de `validation-suite/level-b/anavi-macro-pad-12/`
  con track `+5V` restaurado (reversión del fix manual de 32c),
  aplicar `route_board`, verificar que J4.3 y J5.3 quedan conectados.
- **H2:** unit tests con mock que simulan cada condición del
  guardrail fallando individualmente. Verificar que no se crea vía y
  que el payload expone el pad huérfano con razón correcta.
- **H3:** gate GUI del DoD contra `/tmp/kicad-mcp-sesion32d-gui/` +
  smoke integration sobre despertador (25/25 verde mantenido).
- **H4:** unit test camino feliz — mock con `unconnected_items = 0`
  post-refill, verificar payload limpio sin `stitched_vias` ni
  `orphan_pads`.

### Evidencia refutatoria

- **H1 refutada:** el stitching genera vías pero DRC post-flujo sigue
  mostrando `unconnected_items` sobre J4.3/J5.3. Indicaría que la
  hipótesis de conectividad geométrica del reporte 32c estaba
  incompleta. Registrar, revertir fix, escalar con hipótesis mejorada
  para sesión 32e.
- **H2 refutada:** el guardrail crea vías donde no corresponde
  (falso positivo). Registrar geometría específica, refinar guardrail
  o descartar decisión D3 tal como está.
- **H3 refutada:** despertador D3-D7 muestra diferencia
  post-fix. Grave — regresión real. Escalar, revertir.
- **H4 refutada:** el fix hace algo cuando no debería. Bug de diseño,
  revertir.

### Protección contra regresiones

- **Suite offline** (`pytest -m "not integration"`) → verde antes del
  merge.
- **Suite integration** (`pytest -m integration`) → verde. Incluye
  tests nuevos de 32d + regresión de 32b (canario refill silencioso) +
  31b (canario refs duplicados) + 30 (canario apotema).
- **Gate GUI del DoD** contra `/tmp/kicad-mcp-sesion32d-gui/` (copia
  fresca):
  - `test_pcb_session21_hole_clearance_gui.py` → 2/2.
  - `test_pcb_session27_zone_persist_gui.py` → 2/2.
  - `test_pcb_session24_route_board_persist_gui.py` → 1/1 (humo H4
    despertador — heredado de 32b como gate estándar).
- **Test canario nuevo permanente**
  `tests/test_pcb_session32d_orphan_pads_stitching_canary.py`:
  - Reproduce F-D5-01 con fixture derivado de macro-pad-12.
  - Verifica que aplicar `route_board` cierra J4.3/J5.3
    automáticamente.
  - Verifica que el payload incluye `stitched_vias` y no incluye
    `orphan_pads` cuando el stitching es completo.
  - Verifica los caminos del guardrail rechazando (condiciones 1-5
    individuales).

---

## Timebox flexible con checkpoint

**Timebox base:** 4 horas nominales. **Checkpoint a las 3 horas.**

Evaluación explícita a las 3h:

- **Si fix implementado + tests pasando** → seguir hasta 4h para gate
  GUI del DoD + consolidación documental.
- **Si fix implementado pero tests fallan** → 3h suele indicar
  refinamiento posible. Continuar con AskUserQuestion sobre modo de
  refinar (por ejemplo, ajustar guardrail #5).
- **Si fix parcial y guardrail complicado más de lo esperado** →
  AskUserQuestion. Opciones: cerrar con fix parcial documentado (parte
  del stitching funciona, parte queda diferida) o continuar hasta 4h
  con hipótesis clara de refinamiento.
- **Si el bug no reproduce en fixture y no podemos verificar H1** →
  AskUserQuestion urgente. La sesión 32c dependió de reproducción
  causal sobre este mismo fixture; una falla de reproducción es señal
  de que hay algo en el pipeline distinto entre 32c y ahora.

**No hay tope duro** salvo sentido común. Precedente sesión 32b
(4h efectivas incluyendo humo motor real) es la referencia.

---

## Preparación

1. **Merge de sesión 32c a `master`** — antes de arrancar 32d.
   Verificar que 9746dbe está mergeado. Si NO está (patrón 32c/31c/32b
   observado — encadenar es válido pero acumula deuda), decidir con
   AskUserQuestion.
2. `git checkout master && git pull`.
3. `git checkout -b sesion/32d-fix-orphan-pads-zone-nets`.
4. **Fixtures:**
   - Copia limpia de `validation-suite/level-b/anavi-macro-pad-12/working/`
     en `/tmp/f-d5-01-macro-pad-32d/`.
   - **Restaurar el track `+5V` troncal** que 32c documentó como el
     causante del bug de J4.3/J5.3. Esta copia con el track restaurado
     es el **fixture principal del bug reproducible**.
   - Copia limpia de `tests/fixtures/despertador-routed/` en
     `/tmp/f-d5-01-despertador-32d/` (control de no-regresión).
5. `/tmp/gui-test-project/` NO se toca.
6. `/tmp/kicad-mcp-sesion32d-gui/` = copia fresca del fixture
   despertador para gate GUI del DoD.
7. **Lectura obligatoria** antes de arrancar:
   - `docs/investigacion/32c-f-d5-01.md` §"Mecanismo confirmado
     causalmente" y §"Hipótesis de fix para sesión 32d". Este es el
     input principal.
   - `docs/historico/sesiones/32c-reporte.md` (resumen ejecutivo +
     lecciones metodológicas — `HitTestFilledArea()` no confiable,
     `unconnected_items` es clave de nivel superior del JSON).
   - `docs/adr/0012-route-board-persist-contract.md` (contrato).
   - `docs/DECISIONES.md` D-19.1 (Freerouting no respeta plano),
     D-32c.1 (objetivo investigación).

---

## Bloque 0 — Reproducción controlada del bug (30 min)

**Objetivo:** confirmar reproducción sobre el fixture antes de tocar
código. Gate metodológico.

### Pasos

1. Sobre `/tmp/f-d5-01-macro-pad-32d/`: aplicar `route_board` (sin
   fix) y verificar que J4.3 y J5.3 quedan huérfanos con
   `unconnected_items` post-refill final.
2. **Usar la clave correcta** (`unconnected_items` de nivel superior
   del JSON, no `violations[].type` — lección de 32c auto-corrección
   #1).
3. **NO usar `HitTestFilledArea()`** para validar conectividad — no es
   confiable (lección de 32c auto-corrección #2). Usar `unconnected_items`
   directo.
4. Confirmar geometría (coordenadas de J4.3, J5.3, track `+5V`
   troncal) coincide con lo reportado en 32c.

### Gate

- Si reproduce como espera → seguir a Bloque 1.
- Si NO reproduce → `AskUserQuestion` urgente. Puede ser que la
  restauración del track no se hizo bien, o que 32c documentó un caso
  distinto al observado ahora. Ambas hipótesis requieren investigación
  antes de tocar código.

---

## Bloque 1 — Implementación del fix (90-120 min)

**Objetivo:** implementar el fix de stitching automático con guardrails
+ exposición explícita, siguiendo D1-D3 cerradas.

### Sub-bloque 1.1 — Detección de pads huérfanos post-refill

1. Ubicar el punto en `src/kicad_mcp/tools/pcb.py::route_board` donde
   se ejecuta el DRC post-refill final. Es el punto natural para leer
   `unconnected_items`.
2. Extraer los pads huérfanos con su ref, kiid, coordenadas, net.
3. Filtrar los que están sobre nets con zona de cobre propia (lookup
   sobre las zonas del board).

### Sub-bloque 1.2 — Guardrails (D3)

Para cada pad huérfano candidato, verificar las 5 condiciones:

1. `unconnected` post-refill (ya cumplido por filtro).
2. Net tiene zona propia (ya cumplido por filtro).
3. Pad dentro del outline de una zona del mismo net — point-in-polygon
   sobre el outline (no el filled_polygon, para permitir stitching
   incluso cuando el filled tiene fracturas).
4. Capa opuesta tiene zona del mismo net (F.Cu↔B.Cu típicamente).
5. Región inmediata (~1mm radio en la capa opuesta) libre de tracks/
   vías/pads ajenos.

Cada pad que pasa las 5: candidato a stitching. Cada pad que no:
registrar en payload como `orphan_pad` con razón de rechazo.

### Sub-bloque 1.3 — Stitching automático

Para candidatos a stitching:
1. Elegir posición de la vía: centro del pad (más simple, cubre todos
   los casos observados). Si aparece caso donde el centro no funciona,
   se refinará en sesión futura con evidencia.
2. Invocar `add_via(x, y, layer_from, layer_to, net)` con los
   parámetros correspondientes.
3. Registrar la vía creada en payload como `stitched_via` con pad_ref
   y kiid.

### Sub-bloque 1.4 — Exposición en payload

Extender el payload de `route_board` con dos claves nuevas:
- `stitched_vias`: array de vías creadas por el stitching (cada una
  con pad_ref, kiid, coordenadas, layers).
- `orphan_pads`: array de pads huérfanos que el guardrail rechazó
  (cada uno con pad_ref, kiid, net, razón).

Ambas claves ausentes o vacías cuando no aplica (H4).

### Sub-bloque 1.5 — Tests

**Unit tests** con mock del bridge (`_FakeBridge` de precedente 32b):
- `test_orphan_pad_stitched_when_guardrails_pass`.
- `test_no_stitching_when_net_has_no_zone` (guardrail 2).
- `test_no_stitching_when_pad_outside_zone_outline` (guardrail 3).
- `test_no_stitching_when_no_opposite_layer_zone` (guardrail 4).
- `test_no_stitching_when_area_not_free` (guardrail 5).
- `test_payload_lists_stitched_and_orphan` (exposición).
- `test_no_effect_when_zero_orphans` (H4).

**Integration test** sobre fixture con motor real:
- `test_orphan_pads_stitching_end_to_end` — sobre
  `/tmp/f-d5-01-macro-pad-32d/`, aplicar `route_board`, verificar que
  J4.3/J5.3 quedan conectados y `stitched_vias` contiene 2 entradas.

**Test canario permanente**
`tests/test_pcb_session32d_orphan_pads_stitching_canary.py`.

---

## Bloque 2 — Gate de regresión y validación integral (45 min)

**Objetivo:** confirmar que el fix no rompe nada existente.

### Pasos

1. **Suite offline** → verde.
2. **Suite integration** → verde. Incluye tests nuevos.
3. **Gate GUI del DoD** contra `/tmp/kicad-mcp-sesion32d-gui/`:
   - `test_pcb_session21_hole_clearance_gui.py` → 2/2.
   - `test_pcb_session27_zone_persist_gui.py` → 2/2.
   - `test_pcb_session24_route_board_persist_gui.py` → 1/1 (humo H3
     despertador — verifica que los `add_via` de sesión 25 siguen
     intactos y el fix no genera vías duplicadas).
4. **`ruff` + `mypy`** limpios.
5. **Verificación semántica adicional:** re-correr `route_board`
   sobre `/tmp/f-d5-01-despertador-32d/` (despertador ya corregido en
   sesión 25 con `add_via` manual). Verificar que `stitched_vias`
   está vacío o ausente (los `add_via` de sesión 25 ya cerraron el
   caso; el fix no debería re-generar nada). Este es el humo directo
   de H3.

Si CUALQUIER gate falla → `AskUserQuestion` antes de mergear.

---

## Bloque 3 — Consolidación documental (30-45 min)

**Objetivo:** dejar el registro completo con análisis comparativo
(regla nueva del arquitecto).

### Análisis comparativo obligatorio

El reporte debe incluir, para cada decisión D1-D3, una sección
explícita con:

- **Alternativas consideradas y descartadas** (ya listadas en este
  prompt como base — el reporte confirma con evidencia real de la
  ejecución).
- **Evidencia que las descartó** — de este prompt + observaciones
  durante ejecución.
- **Por qué la elegida explica mejor** — sintetizado con el resultado
  de la sesión.

Ejemplo para D1: "auto con guardrails elegida sobre auto sin guardrails
porque el test `test_no_stitching_when_area_not_free` demostró que la
condición 5 rechaza correctamente casos donde el guardrail relajado
habría creado colisión con via existente cercana".

### Actualizaciones documentales

1. **`docs/BACKLOG.md`:**
   - **F-D5-01/F-V1c-01/F-V2-VIA-HUERFANA cerrado en sesión 32d** con
     detalle del fix (stitching automático + guardrails + exposición).
   - Nota sobre el patrón: primera respuesta arquitectónica a D-19.1
     (Freerouting no ve plano como conductor). D-19.1 sigue vigente
     como restricción.

2. **`docs/DECISIONES.md`:**
   - D-32d.1: decisión formal del fix — stitching automático con
     guardrails + exposición explícita como fallback.
   - D-32d.2 (si aplica): decisión sobre semántica ante fallo — no
     error por default, exposición en payload.

3. **`docs/adr/`:** decidir en `AskUserQuestion` pre-merge si el fix
   amerita ADR-0014 o extensión de ADR-0012 §"F-D5-01 stitching
   (sesión 32d)". Recomendación: extensión de ADR-0012, no ADR nuevo
   (precedente sesión 27, sesión 32b).

4. **`docs/CONTEXT.md`:** estado post-32d — F-D5-01 cerrado, próxima
   sesión = 33 (Nivel C).

5. **`docs/historico/sesiones/32d-reporte.md`:** reporte de la sesión
   con **análisis comparativo obligatorio** de D1-D3.

### Pre-merge

- Diff completo revisado.
- Todos los gates verdes.
- `AskUserQuestion` al arquitecto con: diff, resumen ejecutivo,
  confirmación de próximo paso (sesión 33 Nivel C).

---

## Criterios de éxito

1. **Éxito pleno:** H1, H2, H3, H4 confirmadas. Todos los gates verdes.
   Fix acotado (<100 líneas efectivas). F-D5-01 cerrado.

2. **Éxito parcial:** H1 confirmada + una de las otras refutada
   (ejemplo: H2 refutada en un guardrail específico, se refina la
   condición). `AskUserQuestion` sobre cómo cerrar.

3. **Aprendizaje por refutación:** el fix diseñado NO cierra el
   síntoma (H1 refutada). Reportar honestamente, revertir cambios,
   escalar con hipótesis mejorada para sesión 32e. Precedente sesión
   26.

4. **Aprendizaje por regresión:** H3 refutada (despertador D3-D7
   pierde estado). Grave — revertir inmediato. Este es el peor
   resultado y también el más informativo si aparece.

---

## Entregables

1. **Rama** `sesion/32d-fix-orphan-pads-zone-nets` mergeable a
   `master`.
2. **Fix** en `src/kicad_mcp/tools/pcb.py::route_board`.
3. **Tests unit + integration + canario permanente**.
4. **Reporte** `docs/historico/sesiones/32d-reporte.md` **con análisis
   comparativo obligatorio** de D1-D3.
5. **Actualizaciones** en `docs/BACKLOG.md`, `docs/CONTEXT.md`,
   `docs/DECISIONES.md`, extensión de ADR-0012 (o ADR nuevo según
   decisión pre-merge).
6. **Fixture** `/tmp/f-d5-01-macro-pad-32d/` documentado (aunque no
   versionado — se documenta cómo derivarlo del fixture principal).

---

## Recordatorios operacionales

**Investigación previa aplicada** (patrón sesión 30, 32b). El
mecanismo YA está aislado por 32c. Esta sesión aplica el fix directamente
sin re-investigar.

**Fix quirúrgico, no expansión** (patrón sesión 30, 31b, 32b). <100
líneas efectivas. Si el diff se acerca a 200+, parar y verificar.

**Cross-check contra ADRs vigentes** (D-31c.1). Aplicado por el
arquitecto al escribir este prompt. Si aparecen decisiones nuevas
durante ejecución, mismo criterio.

**Auto-corrección durante la sesión** (patrón sesión 30, 32c). Si
durante la ejecución se descubre que una hipótesis está mal (por
ejemplo: la lectura de `unconnected_items` sigue siendo compleja pese
a lo que aprendimos en 32c), parar, verificar, corregir.

**Análisis comparativo obligatorio** (regla nueva del arquitecto). El
reporte final debe justificar cada decisión de diseño contra las
alternativas descartadas con evidencia.

**Regla de fixtures del repo:** `tests/fixtures/` y `validation-suite/`
son de solo lectura durante toda la sesión. Todas las mutaciones
ocurren en `/tmp/`. Precedente sesión 32c.

---

## Aplicación de D-30.2 + D-32c.1

**Éxito por confianza, no por código.** Los 4 escenarios de éxito son
válidos si están honestamente documentados. Un fix aplicado con
guardrails funcionando + exposición explícita cerrando parcialmente
es tan valioso como un fix que cierra 100% (H1 pleno) — porque el
guardrail que rechaza es evidencia de decisión de diseño correcta.

Si aparece tensión entre "forzar el cierre" y "documentar honestamente",
elegir documentar. Precedentes: 23, 26, 30, 31b, 32b, 32c.

---

## Fuera de alcance

- Refactor del pipeline de fill de zonas o `enforce_hole_clearance`.
- Rediseño del contrato de refill (D-23.2).
- Cambios en Freerouting o el post-procesado del `.ses`.
- Nuevas tools separadas del MCP (fix va dentro de `route_board`).
- Cualquier deuda de BACKLOG no relacionada.
- Vigilancia de `L9.1` (candidato lateral de 32c, no acción).
- Asimetría de `delete_tracks_bulk` (deuda diferida 32b).
- Unificación `PERSIST_CONTRACT_FAILED` (deuda P4).
- `sesion-01` congelada (pre-release).
- Arrancar sesión 33.

---

## Env vars

Sin cambios. `KICAD_MCP_FREEROUTING_JAR` requerido para integration
test (jar del plugin KiCad 9.0 documentado en sesión 32b).

---

## Cierre esperado

Sesión 32d cerrada con:

- Rama mergeada a master.
- F-D5-01/F-V1c-01/F-V2-VIA-HUERFANA cerrado con fix verificado (unit
  + integration + gate GUI del DoD + humo despertador).
- Canario permanente contra reincidencia.
- Contrato ADR-0012 extendido con la mitigación de D-19.1.
- Análisis comparativo de D1-D3 documentado con evidencia real.

**Próxima sesión: 33 = Nivel C Validation Suite** (candidato tentativo:
PortaPack H1 con fork migrado, HackRF One como frontera refutatoria).
Selección definitiva en la conversación pre-sesión 33 siguiendo el
patrón de 32 (verificar 2-3 candidatos con clone + inspección, no
prescribir uno solo).

**Recordatorio final:** el ejecutor debe respetar la regla de alcance.
Si aparece durante la ejecución cualquier decisión de diseño no
cubierta por D1-D3, `AskUserQuestion` en vez de improvisar. Las 3
decisiones cerradas son el marco — todo lo demás es consulta. El
análisis comparativo obligatorio en el reporte final es requisito de
merge, no opcional.
