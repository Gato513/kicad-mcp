# Sesión 32b — Fix intermedio: refill post-route silencioso

**Tipo:** sesión de fix intermedia post-sesión 32. Resuelve
F-V2-REFILL-SILENCIOSO (P0/P1) — cierre del contrato D-23.2 sobre un
modo de falla no cubierto, descubierto en sesión 32.

**Rama:** `sesion/32b-fix-refill-silencioso` desde `master` post-merge
de la secuencia 31→31b→31c→32.

**Origen:** hallazgo P0/P1 de sesión 32 —
`docs/historico/sesiones/32-reporte.md` §Fricciones, entrada
`F-V2-REFILL-SILENCIOSO` de `docs/BACKLOG.md`.

**Precedente metodológico:** patrón sesión 30 (aislar mecanismo con
precisión sub-milimétrica antes de proponer fix, verificar contra motor
real) + sesión 31b (fix quirúrgico con disciplina de alcance +
cross-check ADRs D-31c.1).

## Contexto de Fase 4

- **D-30.1 estricta.** Bloque explícito de hipótesis / evidencia
  confirmatoria / refutatoria / protección antes de tocar código.
- **D-30.2 aplica:** éxito = aumento de confianza. Un fix correcto con
  evidencia sólida vale más que dos fixes apurados.
- **D-31c.1 aplicada:** cross-check contra ADRs vigentes YA hecho por
  el arquitecto al escribir este prompt. ADRs verificados: **ADR-0012**
  (contrato route_board persist), **ADR-0013** (contrato
  set_footprint_ref), **D-07.1** (mutación sin reintento). Ninguna
  decisión D1-D3 conflictúa; ver §"Decisiones de diseño cerradas".
- **Interpretación Fase 4:** este bug NO es regresión — fue enmascarado
  desde su origen por el paso "Refill final" del flujo canónico
  prescripto en D-26.1. Sesión 32 es la primera que efectivamente lo
  detectó por cruce contractual explícito. Es exactamente el tipo de
  hallazgo que Fase 4 espera producir.

## Alcance operacional

**Dentro:**
- F-V2-REFILL-SILENCIOSO en `route_board(refill=True)`.
- Extensión coherente del fix a `fill_zones()` y `add_zone(fill=True)`
  (mismo mecanismo, mismo modo de falla probable — ADR-0012 §"Extensión
  de alcance (sesión 27)" ya las hermana bajo el mismo contrato).
- Tests de regresión: unit (mock) + integration (motor real).

**Fuera** (explícito):
- **F-D5-01 promoción a P1 investigación Fase 4** — se agenda como
  sesión 32c independiente. Investigación pura ≠ fix quirúrgico.
  Precedente 30 vs 31b.
- **Rediseño de D-07.1 (mutación sin reintento).** El fix respeta la
  disciplina D-07.1 en vez de agregar retry.
- **Nuevas tools o features del MCP.**
- **Cualquier otra deuda de BACKLOG.**

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4.

**Regla operacional:** fix quirúrgico. Precedente sesión 30 (~35 líneas
efectivas) + sesión 31b (~100 líneas totales). Si aparece tentación de
expandir alcance, `AskUserQuestion` antes.

---

## Estrategia de validación (D-30.1)

### Hipótesis principales

**H1 — Detección honesta del fallo.** Cuando `reload_board_from_disk`
lanza una excepción durante el refill interno de
`route_board(refill=True)` (u homólogos `fill_zones` /
`add_zone(fill=True)`), el llamador recibe un código de error explícito
`POST_ROUTE_REFILL_FAILED` (o el nombre que el proyecto acuerde,
convención con ADR-0012 §códigos de error) en vez de completar
silenciosamente con `reloaded: false, zones_refilladas: 0`.

**H2 — Cobertura simétrica de las tres tools.** El mismo modo de falla
se manifiesta en `route_board(refill=True)`, `fill_zones()` y
`add_zone(fill=True)`. Aplicar el fix a las tres cierra el contrato
D-23.2/ADR-0012 §"Extensión de alcance (sesión 27)" de forma coherente.

**H3 — El fix respeta D-07.1.** No introduce retry automático. El
llamador ve el error, decide cómo actuar (invocar `fill_zones()`
explícito post-hoc, reintentar `route_board`, o abortar). Simetría con
D-23.2 original.

**H4 — Sin regresión sobre el flujo canónico despertador.** El
despertador (que ejerce el flujo D3-D7 25/25 verde) no ve el nuevo
código de error en corridas normales. El fix solo se activa cuando el
refill efectivamente falla — que es raro pero real, evidenciado en
sesiones 31c y 32.

### Evidencia confirmatoria

- **H1:** en un fixture minimal con inyección forzada de excepción en
  `reload_board_from_disk`, `route_board(refill=True)` retorna con
  código `POST_ROUTE_REFILL_FAILED` + los campos diagnósticos
  correspondientes (`reloaded: false`, exception details).
- **H2:** el mismo mock aplicado a `fill_zones()` y `add_zone(fill=True)`
  produce el mismo comportamiento (código de error propagado).
- **H3:** el fix NO invoca reintentos automáticos. Verificable por
  inspección del código + test que confirma que la tool solo llama a
  `reload_board_from_disk` una vez.
- **H4:** el gate GUI del DoD contra despertador (session21_hole_clearance
  + session27_zone_persist) sigue verde. Suite integration completa
  verde. Test específico sobre el flujo canónico (colocar → zona →
  refill → ruteo → refill final) sobre fixture despertador no produce
  el error nuevo en corrida normal.

### Evidencia refutatoria

- **H1:** el fallo silencioso NO se explica por excepción de
  `reload_board_from_disk` sino por otra causa (ejemplo: mtime race
  detectado y silenciado en otra capa). Investigar antes de mergear el
  fix — sería síntoma de mecanismo raíz más profundo.
- **H2:** una de las tres tools tiene un mecanismo distinto de fallo
  silencioso. Aplicar fix diferenciado (por ejemplo: si `add_zone` usa
  camino distinto a `route_board`, tratar caso separado).
- **H3:** el fix necesita retry para ser útil en la práctica → conflicto
  directo con D-07.1. `AskUserQuestion` obligatoria: replantear D-07.1
  con evidencia, o descartar el fix propuesto por incompatibilidad
  arquitectónica.
- **H4:** el fix regresiona el flujo del despertador — falsos positivos
  del nuevo error en corridas normales. Fix requiere refinamiento
  (probablemente refinar el criterio de "cuándo el refill falló" para
  distinguir excepción real de "no había nada que rellenar").

### Protección contra regresiones

- **Suite offline** (`pytest -m "not integration"`) → verde antes del
  merge.
- **Suite integration** (`pytest -m integration`) → verde. Incluye los
  tests nuevos de sesión 32b + regresión de sesiones 31b (canario refs
  duplicados) y sesión 30 (canario apotema/máscara).
- **Gate GUI del DoD** contra `/tmp/kicad-mcp-sesion32b-gui/` (copia
  fresca):
  - `test_pcb_session21_hole_clearance_gui.py` → 2/2.
  - `test_pcb_session27_zone_persist_gui.py` → 2/2.
- **Test canario nuevo permanente** (gate de regresión contra
  F-V2-REFILL-SILENCIOSO):
  - `tests/test_pcb_session32b_refill_silencioso_canary.py`.
  - Verifica que si `reload_board_from_disk` falla durante refill
    post-route, `route_board` (y `fill_zones`, `add_zone`) devuelven
    error explícito, no silenciosamente `reloaded: false`.
  - Este test queda como canario permanente.

---

## Decisiones de diseño cerradas

Las 3 preguntas de diseño cerradas por el arquitecto antes de la
ejecución, con cross-check ADRs vigentes (D-31c.1):

### D1 — Semántica ante fallo de `reload_board_from_disk`

**Decisión:** **propagar excepción visible con código de error nuevo
`POST_ROUTE_REFILL_FAILED`** (nombre a validar contra convenciones del
proyecto — si el proyecto prefiere `PERSIST_REFILL_FAILED` o similar
para hermanar con la unificación diferida de códigos de error, adoptar).

**NO agregar `retry=True`** — eso rompería D-07.1 (mutación sin
reintento) y agregaría superficie de error sin necesidad.

Cross-check:
- **ADR-0012** (contrato route_board persist): se mantiene, se agrega
  código específico al modo de falla detectado. Simetría con
  `POST_ROUTE_PERSIST_FAILED` original y `POST_ZONE_PERSIST_FAILED` de
  sesión 27. Coherente con la unificación diferida
  (`PERSIST_CONTRACT_FAILED`) del BACKLOG P4.
- **D-07.1** (mutación sin reintento): respetada. El llamador decide
  cómo reaccionar. No hay retry automático.

Razonamiento operacional: el llamador (usuario/agente) que reciba
`POST_ROUTE_REFILL_FAILED` puede reaccionar de tres formas legítimas:
- Invocar `fill_zones()` explícito post-hoc (el "Refill final"
  prescripto por D-26.1 en el flujo canónico funciona como recuperación
  natural).
- Reintentar `route_board`.
- Abortar el flujo.

Ninguna de las tres requiere que la tool decida por el llamador.

### D2 — Cobertura del pre-check / propagación

**Decisión:** aplicar a las **tres tools** simultáneamente:
`route_board(refill=True)`, `fill_zones()`, `add_zone(fill=True)`.

Cross-check:
- **ADR-0012 §"Extensión de alcance (sesión 27)"**: las tres tools
  comparten `POST_ZONE_PERSIST_FAILED` en el contrato. El fallo
  silencioso detectado en `route_board` probablemente afecta a las tres
  del mismo modo (la ruta común de `reload_board_from_disk` es
  compartida).
- Cobertura completa evita deuda diferida y aplica la lección de
  sesión 27 (ampliación coherente de contrato en un solo commit).

Si durante la ejecución el ejecutor descubre que una de las tres tools
tiene mecanismo distinto (H2 refutada parcialmente), `AskUserQuestion`
antes de introducir fix diferenciado.

### D3 — Test canario: alcance de la reproducción

**Decisión:** **ambos** — unit con mock + integration con motor real.

Cross-check:
- **Sesión 30 precedente**: la investigación P1 solder mask combinó
  unit test aritmético + integration contra motor real (`kicad-cli`) +
  gate GUI del DoD. Los tres niveles cubren dimensiones distintas.
- **Sesión 31b precedente**: fixture minimal + integration contra
  pcbnew real.

**Unit test (mock)** — reproducibilidad determinista:
- Injecta excepción sintética en `reload_board_from_disk` durante refill
  post-route.
- Verifica propagación del error a cada una de las 3 tools.
- Verifica NO retry (test específico de H3).

**Integration test (motor real)** — verificación empírica:
- Fixture que dispara la condición real que causó el bug en sesiones
  31c y 32 (probablemente mtime race del reload — investigable en
  Bloque 0).
- Sobre pcbnew real, confirma que el error se dispara en el escenario
  natural.

Si la condición real no se puede reproducir determinísticamente en
integration (el mtime race es intermitente por diseño), el integration
test se marca como `flaky` con reintento controlado, o se convierte en
test de humo (documenta la observación, no bloquea merge). Decisión
final la toma el ejecutor tras el Bloque 0 de reproducción.

---

## Preparación

1. **Merge de la secuencia 31→31b→31c→32 a `master`** — antes de
   arrancar 32b. Cuatro ramas encadenadas sin mergear es deuda
   estructural que no debe seguir creciendo.
   - Verificar orden lineal de commits: 31 → 31b → 31c → 32.
   - Mergear en secuencia con fast-forward donde aplique, o merge
     commits si el humano prefiere preservar identidad de las ramas.
   - **Si el merge en secuencia genera conflictos inesperados,
     `AskUserQuestion` antes de continuar** — no es fase para resolver
     conflictos ad hoc.
2. `git checkout master && git pull` post-merge.
3. `git checkout -b sesion/32b-fix-refill-silencioso`.
4. `/tmp/gui-test-project/` NO se toca.
5. `/tmp/kicad-mcp-sesion32b-gui/` = copia fresca del fixture despertador
   para gate GUI del DoD.
6. **Lectura obligatoria** antes de arrancar:
   - `docs/historico/sesiones/32-reporte.md` (contexto completo,
     especialmente §"Hallazgo independiente más valioso").
   - `docs/BACKLOG.md` entrada `F-V2-REFILL-SILENCIOSO`.
   - `docs/adr/0012-route-board-persist-contract.md` (contrato base +
     extensión sesión 27).
   - `docs/DECISIONES.md` D-07.1 (mutación sin reintento) — decisión
     central que el fix respeta.
   - Audit log de sesión 31c que evidencia la reproducibilidad
     (referenciado en el reporte de sesión 32).

---

## Bloque 0 — Reproducción controlada del bug (45 min)

**Objetivo:** confirmar que reproducimos el fallo silencioso en un
fixture acotado antes de tocar código. Gate metodológico — si no
reproducimos, no fixeamos a ciegas.

### Sub-bloque 0.1 — Reproducción con mock (unit)

1. Escribir un fixture minimal (`tests/fixtures/refill-silencioso/`)
   con:
   - Board con al menos una zona rellena y un footprint que va a ser
     movido/afectado por route.
   - Estado inicial verificable (DRC 0/0 o baseline documentado).
2. Mock de `reload_board_from_disk` que lanza excepción sintética
   (`RuntimeError` o similar) al ser invocado.
3. Invocar `route_board(refill=True)` con el mock activo → observar el
   comportamiento actual del código.
4. **Verificación esperada:** hoy la tool retorna `reloaded: false,
   zones_refilladas: 0` sin código de error. Confirma el bug.

### Sub-bloque 0.2 — Reproducción con motor real (integration)

1. Identificar la condición real que causó el bug en 31c/32. Hipótesis
   principal: **mtime race** del reload — el board se guarda, se recarga
   inmediatamente, pero el mtime del archivo no ha cambiado
   perceptiblemente y el sistema lo ve como "sin cambios" o "modificado
   externamente".
2. Verificar contra el audit log de sesión 31c (referenciado en el
   reporte de 32): buscar los campos `reloaded: false,
   zones_refilladas: 0` y la timeline de eventos que los rodea.
3. Intentar reproducir determinísticamente en fixture. Si es imposible
   (el race es no-determinista por naturaleza), documentar en Bloque 0
   la observación y proceder con test de humo o flaky-marked
   integration.

### Sub-bloque 0.3 — Reproducción sobre las tres tools

1. Aplicar el mismo mock del sub-bloque 0.1 a `fill_zones()` y
   `add_zone(fill=True)`.
2. Verificar si el comportamiento es idéntico (fallo silencioso con
   `zones_refilladas: 0`).
3. Si es idéntico → H2 confirmada. Aplicar fix a las tres.
4. Si difiere → registrar cada caso, `AskUserQuestion` antes de aplicar
   fix uniforme.

### Gate del Bloque 0

- Si el mock reproduce en las tres tools → seguir a Bloque 1.
- Si NO reproduce en alguna → `AskUserQuestion` antes de continuar.
- Si la condición real (Sub-bloque 0.2) NO se puede reproducir
  determinísticamente → seguir con unit test como principal evidencia,
  integration como observación adicional.

### Salida esperada

- Fixture minimal versionado en `tests/fixtures/refill-silencioso/`.
- Bug reproducido con mock en las 3 tools (o hallazgo de asimetría
  registrado).
- Documento de mecanismo raíz probable (mtime race o el que
  investigación descubra) — input para diseño del fix en Bloque 1.

---

## Bloque 1 — Implementación del fix (60-90 min)

**Objetivo:** implementar el fix con propagación explícita del error a
las 3 tools + tests de regresión.

### Sub-bloque 1.1 — Propagación del error

1. Ubicar el punto exacto en el código donde `reload_board_from_disk`
   se invoca durante el refill post-route (probablemente en el bridge
   IPC o en la tool `route_board` misma).
2. Wrap con try/except que captura la excepción específica
   (probablemente algo tipo `ReloadError` o `KiCadException`) y la
   convierte en el retorno explícito `POST_ROUTE_REFILL_FAILED`.
3. **Respetar D-07.1:** no reintentar. Un solo intento, error propagado.
4. Nombre exacto del código de error a acordar con la convención del
   proyecto — proponer `POST_ROUTE_REFILL_FAILED` y confirmar con
   `AskUserQuestion` si el proyecto prefiere unificar (ej.
   `PERSIST_REFILL_FAILED` para hermanar con la unificación diferida
   BACKLOG P4).

### Sub-bloque 1.2 — Extensión a `fill_zones()` y `add_zone(fill=True)`

1. Aplicar mismo patrón de propagación a las dos tools hermanas.
2. Verificar que el código de error retornado es coherente con el de
   `route_board` — no crear tres códigos distintos, uno solo o dos con
   nombres simétricos.
3. Cross-check ADR-0012 §"Extensión de alcance (sesión 27)": las tres
   tools comparten `POST_ZONE_PERSIST_FAILED`. El nuevo código debe
   coexistir simétricamente (o unificarse con él como parte del mismo
   commit, si el proyecto acuerda ir por la unificación diferida del
   BACKLOG P4 — decisión de scope creep, `AskUserQuestion` primero).

### Sub-bloque 1.3 — Tests unit

- `test_route_board_refill_error_propagated` — mock lanza excepción,
  verificar retorno con código explícito.
- `test_fill_zones_refill_error_propagated` — idem.
- `test_add_zone_refill_error_propagated` — idem.
- `test_route_board_no_retry_on_refill_failure` — verifica que
  `reload_board_from_disk` se llama exactamente una vez (respeta
  D-07.1).

### Sub-bloque 1.4 — Test canario permanente

`tests/test_pcb_session32b_refill_silencioso_canary.py` — gate de
regresión permanente contra F-V2-REFILL-SILENCIOSO. Si en el futuro
alguien re-introduce el fallo silencioso (por ejemplo, atrapando la
excepción y silenciándola en el nombre de "robustez"), el canario lo
detecta.

### Sub-bloque 1.5 — Integration test (si Bloque 0.2 lo permite)

Si la reproducción de motor real fue determinista en Bloque 0.2, agregar
integration test que dispara la condición natural. Si fue no-determinista,
marcar como flaky o dejar como observación en el reporte.

---

## Bloque 2 — Gate de regresión y validación integral (45 min)

**Objetivo:** confirmar que el fix no rompe nada existente y que el
gate GUI del DoD sigue verde.

### Pasos

1. **Suite offline** (`pytest -m "not integration"`) → verde. Incluye
   los tests nuevos.
2. **Suite integration** (`pytest -m integration`) → verde. Incluye el
   test integration nuevo si aplica, y regresión completa de tests
   heredados de sesión 30, 31b, etc.
3. **Gate GUI del DoD** contra `/tmp/kicad-mcp-sesion32b-gui/`:
   - `test_pcb_session21_hole_clearance_gui.py` → 2/2.
   - `test_pcb_session27_zone_persist_gui.py` → 2/2.
4. **`ruff` + `mypy`** limpios en los archivos tocados.
5. **Ejercicio de humo sobre despertador:** correr el flujo canónico
   completo (colocar → zona → refill → route → refill final → DRC)
   sobre copia del despertador con footprints reales. Verificar que
   `POST_ROUTE_REFILL_FAILED` NO se dispara en corrida normal. Este es
   el test de "no regresión de H4".

Si CUALQUIER gate falla, `AskUserQuestion` antes de mergear.

---

## Bloque 3 — Consolidación documental (30 min)

**Objetivo:** dejar el registro claro para sesiones 32c (investigación
F-D5-01) y 33 (Nivel C).

### Actualizaciones

1. **`docs/BACKLOG.md`:**
   - `F-V2-REFILL-SILENCIOSO`: cerrado en sesión 32b con detalle del
     fix (`POST_ROUTE_REFILL_FAILED` + extensión a tres tools).
   - Nota adicional: la unificación diferida de códigos
     (`POST_ROUTE_PERSIST_FAILED` + `POST_ZONE_PERSIST_FAILED` +
     ahora `POST_ROUTE_REFILL_FAILED` → `PERSIST_CONTRACT_FAILED`) sigue
     como deuda P4 en BACKLOG. Sesión 32b agrega el tercer código,
     refuerza la deuda pero no la resuelve — está fuera de alcance.

2. **`docs/DECISIONES.md`:**
   - D-32b.1 (candidato): decisión formal del fix — propagación
     explícita del error de refill sin retry, respetando D-07.1.
     Referencia a ADR-0012.
   - Si durante la ejecución surgió alguna decisión de alcance nueva
     (por ejemplo, unificación de códigos), registrar como D-32b.2 con
     evidencia.

3. **`docs/adr/`:** decidir si el fix amerita ADR-0014 o si se documenta
   solo en ADR-0012 §"Extensión F-V2 (sesión 32b)" — precedente sesión
   27 hizo lo segundo. Recomendación: extensión de ADR-0012, no ADR
   nuevo. Confirmar en `AskUserQuestion` pre-merge.

4. **`docs/CONTEXT.md`:** estado post-sesión 32b — F-V2-REFILL-SILENCIOSO
   cerrado, F-D5-01 pendiente para sesión 32c, sesión 33 Nivel C tras
   32c.

5. **`docs/historico/sesiones/32b-reporte.md`:** reporte de la sesión
   con formato heredado. Bloques ejecutados, evidencia por hipótesis
   H1-H4, tests agregados, decisión sobre alcance de ADRs.

### Pre-merge

- Diff completo revisado.
- Todos los gates verdes.
- `AskUserQuestion` al arquitecto con: diff, resumen ejecutivo,
  confirmación de próximo paso (sesión 32c = investigación F-D5-01,
  luego sesión 33 = Nivel C).

---

## Criterios de éxito

1. **Éxito pleno:** H1, H2, H3, H4 confirmadas con evidencia contra
   motor real (o unit + humo despertador si integration no fue
   determinista). Todos los gates verdes. Fix acotado (<100 líneas
   efectivas totales, esperable dado precedente 30/31b).

2. **Éxito parcial:** H1 confirmada + una de las otras refutada
   (ejemplo: H2 refuta simetría entre las tres tools; se aplica fix
   diferenciado con evidencia). `AskUserQuestion` sobre cómo cerrar.

3. **Aprendizaje por refutación:** el fix diseñado NO resuelve el bug
   (patrón sesión 26). Reportar honestamente, revertir cambios, escalar.
   NO mergear fix no verificado.

4. **Aprendizaje metodológico:** el bug no era `reload_board_from_disk`
   con excepción — es otro mecanismo (por ejemplo, silenciamiento
   deliberado aguas arriba que investigación descubre). Fix propuesto
   se descarta, sesión pivota a investigación adicional o se cierra con
   hallazgo.

---

## Entregables

1. **Rama** `sesion/32b-fix-refill-silencioso` mergeable a `master`.
2. **Fix propagando error de refill** en `src/kicad_mcp/` sobre las 3
   tools (`route_board`, `fill_zones`, `add_zone`).
3. **Tests unit** (mock) para las 3 tools + test de no-retry (D-07.1).
4. **Test canario permanente**
   `tests/test_pcb_session32b_refill_silencioso_canary.py`.
5. **Integration test** si Bloque 0.2 fue determinista, o observación
   documentada si no.
6. **Fixture** `tests/fixtures/refill-silencioso/` versionada.
7. **Reporte** `docs/historico/sesiones/32b-reporte.md`.
8. **Actualizaciones** en `docs/BACKLOG.md`, `docs/CONTEXT.md`,
   `docs/DECISIONES.md`, extensión de `docs/adr/0012-route-board-persist-contract.md`
   (o ADR nueva según decisión pre-merge).

---

## Recordatorios operacionales

**Investigación previa al fix cuando el marco entra en conflicto con
evidencia** (patrón sesión 31b). Si durante el Bloque 0 el bug no
reproduce como espera el prompt, `AskUserQuestion` antes de improvisar.

**Fix quirúrgico, no expansión** (patrón sesión 30). El fix debería
rondar <100 líneas efectivas totales. Si el diff se acerca a 200+ líneas
hay probable scope creep — parar y verificar.

**Cross-check contra ADRs vigentes** (D-31c.1). Aplicado por el
arquitecto al escribir este prompt. Si aparecen decisiones nuevas
durante ejecución, mismo criterio.

**Verificar antes de mutar** (patrón sesión 31c). Reproducir el bug en
fixture (Bloque 0) antes de tocar código en Bloque 1.

---

## Aplicación de D-30.2

**Éxito por confianza, no por código.** Un fix pequeño y bien verificado
(escenario 1) es pleno éxito. Un aprendizaje por refutación honesta
(escenario 3) también es éxito, aunque no cierre la validación.

Si aparece tensión entre "forzar el cierre" y "documentar honestamente",
elegir documentar. Precedentes: 23, 26, 30, 31b.

---

## Fuera de alcance

- F-D5-01 promoción a P1 investigación Fase 4 — sesión 32c separada.
- Rediseño de D-07.1.
- Unificación de códigos (`PERSIST_CONTRACT_FAILED`) — deuda BACKLOG P4
  no urgente.
- Nuevas tools o features del MCP.
- Cualquier deuda de BACKLOG no relacionada con F-V2-REFILL-SILENCIOSO.
- Arrancar sesión 32c o sesión 33.
- Resolver `sesion-01` congelada (agendada para pre-release).

---

## Env vars

Sin cambios respecto a sesiones anteriores.

---

## Cierre esperado

Sesión 32b cerrada con:

- Rama mergeada a master.
- F-V2-REFILL-SILENCIOSO (P0/P1) cerrado con fix verificado (unit +
  humo despertador mínimo; integration si Bloque 0.2 lo permitió).
- Canario permanente contra el fallo silencioso.
- Contrato D-23.2/ADR-0012 extendido coherente para las 3 tools.
- Regla de disciplina cumplida: fix quirúrgico.

**Próxima sesión: 32c = investigación P1 Fase 4 sobre patrón F-D5-01**
(3 instancias: sesión 25 despertador, sesión 31c anavi-dev-mic, sesión
32 anavi-macro-pad-12). Arranca solo cuando sesión 32b cierre con
todos los gates verdes y mergeada. Sesión 33 (Nivel C) tras 32c.

**Recordatorio final:** el ejecutor debe respetar la regla de alcance.
Si aparece durante la ejecución cualquier decisión de diseño no cubierta
por D1-D3, `AskUserQuestion` en vez de improvisar. Las 3 decisiones
cerradas son el marco — todo lo demás es consulta.
