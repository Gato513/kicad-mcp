# Sesión 27 — Generalización D-23.2 a `fill_zones` y `add_zone(fill=True)`

**Tipo:** IMPLEMENTACIÓN de generalización de contrato + test de regresión
gate del merge. Nueva rama `sesion/27-generalizacion-d23-2` desde `master`
**post-merge de la rama de docs de sesión 26** (BACKLOG con P1
re-estimado + DECISIONES con D-26.1 + CONTEXT con caveat C7 + hoja-de-ruta
con estado sesión 26 — mergear primero para que el estado documental esté
en `master`).

**Origen:** contrato D-23.2 (ADR-0012) implementado en `route_board` en
sesión 24 y ratificado en producción 5/5 (2/2 test regresión sesión 24 +
3/3 D5 sesión 25). El propio Bloque 2 de sesión 23 identificó que
`fill_zones` y `add_zone(fill=True)` sufren el mismo bug conceptual
(arreglan el board vivo pero no persisten). Con D-23.2 ratificado
estadísticamente, la generalización a esas dos tools tiene base sólida
para proceder — es el paso 3 de la secuencia estricta de Fase 3.

**Alcance mandatorio:** SOLO `fill_zones` y `add_zone(fill=True)`. NO
tocar `route_board` (ya cerrado en sesión 24). NO tocar `move_footprint`
(D-26.1 se atiende por protocolo operacional en dogfoodings, no con
cambio de código en `move_footprint`). NO tocar loop de vías de
`enforce_hole_clearance` (D-23.3/R16, deuda técnica separada). NO tocar
P1 solder mask ANT1 (investigación pendiente propia).

**Criterio de cierre (gate del merge):** test de regresión que cubra las
dos tools debe pasar de forma determinista, con verificación análoga a
la de sesión 24: `run_drc()` independiente inmediato SIN `save_board()`
manual coincide con estado interno reportado, mtime cambia
post-operación, sin `EXTERNAL_EDIT_DETECTED` espurio. 2 corridas verdes
consecutivas por tool para confirmar no-flakey.

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4.

**Consejo operacional (D-D4.1 aplicable):** los caminos sugeridos abajo
son inclusivos, no restrictivos. Si aparece una forma mejor de
estructurar el test o el helper de fixture, se puede elegir sin pedir
permiso — mientras no cambie el alcance (solo `fill_zones` y `add_zone`)
ni el criterio de cierre.

**Decisiones fijadas por el arquitecto para esta sesión (NO re-decidir
en la ejecución):**

1. **Código de error compartido `POST_ZONE_PERSIST_FAILED`**, no uno por
   tool. Argumento: semánticamente es la misma condición ("no pude
   persistir el resultado del refill de la zona"). El llamador ya sabe
   cuál tool invocó — no necesita el código para diferenciarlo. Evita
   proliferación de códigos que F3 desalienta. Si `route_board` en el
   futuro adopta el mismo código (deprecando `POST_ROUTE_PERSIST_FAILED`
   en favor de este), es refactor posterior — NO cambiar
   `route_board` en esta sesión.
2. **ADR: extender ADR-0012, NO crear ADR-0013.** Es el mismo contrato
   conceptualmente aplicado a tres tools. Crear un ADR nuevo sería
   sobre-formalización. Sección nueva en ADR-0012: "Extensión de alcance
   (sesión 27)" con la lista de tres tools cubiertas
   (`route_board`, `fill_zones`, `add_zone(fill=True)`).
3. **Patrón completo replicado (no minimalista):** `fill_zones` y
   `add_zone(fill=True)` deben incluir refill + `enforce_hole_clearance` +
   `save_board()` incondicional + fallo visible. Argumento: consistencia
   del contrato entre las tres tools. Si el Bloque 1 descubre que agregar
   `enforce_hole_clearance` a `fill_zones`/`add_zone` rompe algo o
   expande demasiado el alcance, **`AskUserQuestion` obligatoria** antes
   de proceder — puede que la decisión tenga que ser minimalista (solo
   save + fallo visible, sin extender `enforce_hole_clearance` a estas
   dos tools). Sospechar que hoy fill_zones/add_zone NO lo llaman —
   confirmar en la lectura.

**Timeboxing por bloque** (mismo modelo que sesión 24, respetar):

- Bloque 1: 30 min.
- Bloque 2: 45 min.
- Bloque 3: 60 min.
- Bloque 4: 30 min.

Total target: 2h45m. Si un bloque agota su timeout sin resultado,
documentar y continuar. NO acumular tiempo pidiendo más.

---

## Preparación (antes del Bloque 1)

1. Verificar que la rama de docs de sesión 26 ya está mergeada en
   `master`.
2. `git checkout master && git pull`.
3. `git checkout -b sesion/27-generalizacion-d23-2`.
4. `/tmp/gui-test-project/` restaurado desde el fixture
   `tests/fixtures/despertador-routed/` (baseline conocido D5).
5. KiCad reiniciado limpio.
6. `health()` → ipc ok, kicad-cli 10.0.4 detectado.
7. **Lectura obligatoria antes de arrancar:**
   - `docs/adr/0012-route-board-persist-contract.md` (contrato D-23.2).
   - `docs/historico/investigacion/23-fd4-02.md` (Bloque 2 identifica
     que `fill_zones`/`add_zone` sufren el mismo bug conceptual — punto
     de partida del alcance de esta sesión).
   - `docs/historico/sesiones/24-reporte.md` (patrón de implementación
     que sesión 27 replica — hallazgo del snapshot mtime, save
     condicional al branch, etc.).
   - `docs/historico/sesiones/25-reporte.md` (ratificación 3/3 del
     patrón en producción).
   - `src/kicad_mcp/tools/pcb.py` — `fill_zones` y `add_zone` completos.
   - `src/kicad_mcp/bridge/ipc.py:1902-2036` (`enforce_hole_clearance`,
     ya conocido) + los sitios desde donde se invoca hoy.

---

## Bloque 1 — Diseño del cambio (timeout: 30 min)

**Objetivo:** entender exactamente qué mover, agregar, o dejar donde
está, en cada una de las dos tools. NO tocar código todavía.

### Lectura obligatoria

1. `fill_zones` completo en `pcb.py`: identificar dónde está hoy el
   pipeline (refill, medición de resultado, save) y qué falta.
2. `add_zone(fill=True)` completo en `pcb.py`: identificar cuándo y
   cómo dispara el fill, si hoy hace save o no, si registra snapshot.
3. Confirmar (o refutar) la sospecha de que `enforce_hole_clearance`
   NO es llamado desde `fill_zones`/`add_zone` hoy — buscar todas las
   invocaciones en el bridge.
4. `store.register()` y semántica de `mark/clear_live_stale`:
   verificar si el patrón del snapshot mtime post-save (hallazgo #31
   de sesión 24) tiene que replicarse acá.

### Análisis a producir (documento breve, ~1 página, notas para vos
mismo — no necesita ser el reporte final)

1. **Estado actual del pipeline de `fill_zones`:**
   - ¿Refill se dispara internamente? Sí (es su tarea).
   - ¿`enforce_hole_clearance` se llama? (probablemente no — confirmar).
   - ¿`save_board()` se dispara al final? (probablemente no).
   - ¿`store.register()` de mtimes está bien ubicado o sufre el mismo
     problema pre-save que sesión 24 arregló en `route_board`?

2. **Estado actual del pipeline de `add_zone(fill=True)`:**
   - Idénticas preguntas que arriba, adaptadas a la creación de zona
     nueva + fill.

3. **Estado objetivo (post-Opción X extendida):**
   - Refill (ya presente) + `enforce_hole_clearance` (agregar si no
     está) + medición de resultado DRC (agregar si no está) +
     `save_board()` incondicional (agregar) + fallo visible con
     `POST_ZONE_PERSIST_FAILED` (agregar) + snapshot mtimes post-save
     (verificar / ajustar).

4. **Dependencias entre pasos (aprendizaje de sesión 24):** si
   `store.register()` hoy corre pre-save en cualquiera de las dos
   tools, moverlo post-save para evitar `EXTERNAL_EDIT_DETECTED`
   espurio. `mark/clear_live_stale` idem si depende del snapshot.

5. **Decisión del Bloque 1 (fricción probable):** si `enforce_hole_clearance`
   NO está hoy en `fill_zones`/`add_zone` y agregarlo:
   - Rompe tests existentes de `fill_zones`/`add_zone` → `AskUserQuestion`.
   - Requiere que estas tools ganen la infraestructura de auto-keepouts
     (prefijo `__kicadmcp_hc__`, idempotencia, etc.) → `AskUserQuestion`
     para decidir minimalista vs completo.
   - Es cambio quirúrgico limpio (unas pocas líneas de invocación) →
     proceder según decisión #3 del arquitecto.

6. **Semántica del código nuevo `POST_ZONE_PERSIST_FAILED`:**
   - "El pipeline de zona (fill + enforce si aplica) completó pero no
     pude persistir el resultado a disco. El board vivo tiene el estado
     bueno; el disco no está sincronizado."
   - Payload: `code`, `message`, `pcb_path`, hint sobre retry
     (`save_board` manual) o descarte.

7. **Docstring y ADR:**
   - Docstrings de `fill_zones` y `add_zone` actualizados con contrato
     D-23.2 en 1-2 líneas + referencia a ADR-0012 extendido.
   - ADR-0012 nueva sección "Extensión de alcance (sesión 27)".

### Salida esperada del Bloque 1

Nota breve en el reporte (`docs/historico/sesiones/27-reporte.md`,
sección "Bloque 1 — Diseño") con los 7 puntos anteriores respondidos.
Cero líneas de código modificadas en este bloque.

---

## Bloque 2 — Implementación quirúrgica (timeout: 45 min)

**Objetivo:** aplicar el diseño del Bloque 1. Solo lo diseñado ahí,
nada más.

### Cambios esperados

1. **`src/kicad_mcp/tools/pcb.py` (`fill_zones`):**
   - Refill (ya existe) → `enforce_hole_clearance` (agregar si el
     Bloque 1 lo decidió) → medición de resultado DRC (agregar) →
     `save_board()` (agregar) → manejo de fallo con
     `POST_ZONE_PERSIST_FAILED`.
   - `store.register()` con mtimes frescos post-save.
   - Docstring con D-23.2 + referencia al ADR-0012.

2. **`src/kicad_mcp/tools/pcb.py` (`add_zone(fill=True)`):**
   - Análogo a `fill_zones` pero adaptado al flujo de crear zona nueva
     antes de fillar. Solo aplica cuando `fill=True` — el path
     `fill=False` no debería tocarse (crear zona sin fillar no dispara
     el bug conceptual).
   - Idénticos ajustes de snapshot mtimes.
   - Docstring actualizado.

3. **`src/kicad_mcp/errors.py`:**
   - `POST_ZONE_PERSIST_FAILED = "POST_ZONE_PERSIST_FAILED"` agregado
     al `StrEnum ErrorCode`. Excepción sancionada de F1 (adición pura,
     no renombra nada, F3 intacta) según precedente sesión 24.

4. **`docs/specs/tool-catalog.md`:**
   - Fila nueva en Taxonomía con el nuevo código.
   - Códigos agregados a la columna de errores de `fill_zones` y
     `add_zone`.

5. **`docs/adr/0012-route-board-persist-contract.md`:**
   - Nueva sección "Extensión de alcance (sesión 27)" con:
     - Lista de tres tools cubiertas por el contrato D-23.2:
       `route_board`, `fill_zones`, `add_zone(fill=True)`.
     - Nota de que `POST_ROUTE_PERSIST_FAILED` (existente) y
       `POST_ZONE_PERSIST_FAILED` (nuevo) son semánticamente
       equivalentes; discriminación existe por origen del llamador, no
       por semántica de código. Refactor a código unificado queda como
       deuda de bajo impacto post-Fase 3.
     - Referencia a sesión 27 como origen de la extensión.

### Guardarraíles

- **NO tocar** `route_board` (ya cerrado en sesión 24; su código
  `POST_ROUTE_PERSIST_FAILED` NO se deprecia en esta sesión).
- **NO tocar** `enforce_hole_clearance` internamente (D-23.3/R16
  investigación separada). Sí extender los sitios que la LLAMAN si el
  diseño del Bloque 1 lo decidió — pero sin tocar su implementación.
- **NO tocar** `move_footprint` (D-26.1 se atiende por protocolo, NO
  con cambio de código acá).
- **NO ampliar** el docstring más allá de lo necesario para D-23.2 +
  D-19.1 v6 (si aplica al comentario cerca del bloque refill).

### Verificación intermedia

Al terminar los cambios de código, ANTES de pasar al Bloque 3:
- `ruff check` limpio.
- `mypy src/` limpio.
- `uv run pytest -m "not integration"` sigue verde.

Si algo falla, arreglar en el Bloque 2 antes de avanzar. Si falla algo
sin solución obvia en <15 min, documentar y consultar (`AskUserQuestion`)
antes de seguir.

### Fricción anticipada (posible desvío)

Si durante la implementación aparece que **el reordenamiento requiere
cambios en más de una función por tool** o que **`enforce_hole_clearance`
agregado a fill_zones/add_zone rompe tests existentes de esas tools**,
PARAR y consultar (`AskUserQuestion`) antes de expandir el scope o
recurrir a una decisión minimalista. La disciplina "cambio mínimo, patrón
consistente entre tres tools" es lo que el arquitecto fijó — no la
violés por atajo.

### Salida esperada del Bloque 2

Código modificado en las dos tools + errores + tool-catalog + ADR
extendido. Checks internos verdes. Reporte con diff resumido, archivos
tocados, decisiones tomadas durante la implementación.

---

## Bloque 3 — Test de regresión (gate del merge) (timeout: 60 min)

**Objetivo:** test que blindar la generalización D-23.2 en las dos
tools nuevas. Gate del merge.

### Fixture / helper

Preferir helper runtime (D-24.1) sobre fixture estático. Base:
`tests/fixtures/despertador-routed/` como punto de partida conocido.

Escenario a construir en el helper del test (aplica a las dos tools):
- Restaurar el fixture.
- Estado con footprints colocados + plano GND filleado + tracks/vías
  de nets ajenos DENTRO del área del plano (o cerca) — esto es lo que
  dispara el bug conceptual de fill_zones/add_zone (el refill tiene
  que trabajar contra conductor ajeno preexistente).
- Para `fill_zones`: el estado inicial es el fixture con ruteo ya
  hecho + zona GND ya presente pero potencialmente "sucia" (por
  ejemplo, borrar el fill previo con `delete_zone` + re-crear zona sin
  fillar, o simplemente re-llamar `fill_zones()` sobre estado limpio y
  verificar contrato).
- Para `add_zone(fill=True)`: el estado inicial es el fixture con
  ruteo hecho pero SIN zona GND — la tool crea zona nueva y la fillea.
  Esto puede requerir borrar la zona existente primero
  (`delete_zone`).

### Test integration a producir

Ubicación: `tests/integration/` (o donde estén los otros tests de
`fill_zones`/`add_zone`, ver convención del repo).

Marca: `integration_gui_slow` (siguiendo patrón sesión 24).

Assertions mandatorias por tool (**gate del merge**):

1. **Estado interno reportado** (`err_post` o equivalente que devuelva
   la tool) coincide con `run_drc()` independiente inmediato SIN
   `save_board()` manual — corazón del contrato D-23.2.
2. **mtime del `.kicad_pcb` cambió** entre pre-operación y
   post-operación (evidencia de que `save_board()` se ejecutó).
3. **Ninguna operación posterior dispara `EXTERNAL_EDIT_DETECTED`**
   espurio (evidencia de que el snapshot se registró con mtimes frescos
   post-save — coherente con hallazgo #31 sesión 24).
4. **Si el diseño del Bloque 1 incluyó `enforce_hole_clearance` en las
   nuevas tools:** verificar que los keepouts `__kicadmcp_hc__` se
   generan/refrescan (`get_zones(layer="B.Cu")` cuenta correcta) —
   conteo dependiente del fixture, ajustar tras primera corrida.

### Assertion opcional (nice to have, no bloqueante)

5. **Test unitario del path de error** simulando fallo de `save_board()`
   (mock/fake) y verificando que `fill_zones`/`add_zone` levantan
   `POST_ZONE_PERSIST_FAILED`. **Diferencial, no gate.** Si la
   arquitectura del bridge lo permite bajo, incluir; si requiere
   refactor mayor, omitir y documentar en el reporte.

### Determinismo del test

Assertions 1-3 deben ser robustas a la no-determinación del refill
(que no debería tener no-determinación, pero por si acaso). El test
debe pasar 2 corridas consecutivas por tool para confirmar no-flakey.

### Salida esperada del Bloque 3

Test file nuevo (o extensión de test existente), fixture vía helper,
test verde en 2 corridas por tool. Reporte con: cantidad de
assertions, corridas exitosas por tool, timing típico.

---

## Bloque 4 — DoD, docs y merge (timeout: 30 min)

### DoD checklist

1. `ruff check` limpio en todo el repo.
2. `mypy src/` limpio.
3. `uv run pytest -m "not integration"` verde (sin regresiones).
4. `uv run pytest -m integration_gui_slow` — el test nuevo pasa en 2
   corridas consecutivas por tool (`fill_zones` y `add_zone(fill=True)`).
5. **ADR-0012 actualizado** con sección "Extensión de alcance (sesión
   27)" commiteado.
6. Docstrings de `fill_zones` y `add_zone` actualizados: contrato
   D-23.2 en 1-2 líneas + referencia al ADR.
7. Código de error `POST_ZONE_PERSIST_FAILED` definido en
   `errors.py`, usado en las dos tools, listado en `tool-catalog.md`.
8. Fixture vía helper (no directorio estático) commiteado como parte
   del test file.

### Commit + merge

- Mensaje sugerido:
  `feat(zones): extend D-23.2 persist contract to fill_zones and add_zone(fill=True)`.
- Descripción del commit: referencia a
  `docs/historico/sesiones/25-reporte.md` como ratificación estadística
  que habilita la generalización + descripción breve del cambio.
- **Antes de mergear:** `AskUserQuestion` obligatoria al arquitecto
  con el diff completo y el resultado del test.

### Reporte final

`docs/historico/sesiones/27-reporte.md` con:
- Resumen ejecutivo (1 párrafo).
- Bloque 1: diseño (análisis breve, decisión sobre enforce_hole_clearance).
- Bloque 2: implementación (diff resumen, archivos tocados,
  decisiones).
- Bloque 3: test (fixture usado, assertions por tool, corridas
  exitosas).
- Bloque 4: DoD status + docs + estado del merge.
- Métricas: líneas cambiadas totales, tiempo por bloque, si hubo
  desvíos del plan.
- **Recomendación explícita para sesión 28 (D6):** ratificación
  estadística del contrato D-23.2 extendido en las tres tools. Repetir
  patrón V1/V2/V3/V4 de D5, con foco en que V2 ahora se ejercita en
  las tres tools (no solo `route_board`), y con verificación
  adicional del hallazgo D-26.1 (refill obligatorio pre-baseline —
  primera aplicación empírica).

---

## Fuera de alcance

- `route_board` (ya cerrado en sesión 24).
- `move_footprint` (D-26.1 es protocolo, no cambio de código).
- Loop de vías de `enforce_hole_clearance` (D-23.3, R16, deuda
  técnica separada).
- P1 solder mask ANT1 (investigación pendiente propia).
- Unificación de `POST_ROUTE_PERSIST_FAILED` y `POST_ZONE_PERSIST_FAILED`
  en un solo código (deuda de bajo impacto, post-Fase 3).
- Cualquier feature nuevo o escalada de complejidad.

## Env vars

```bash
export KICAD_MCP_GUI_TEST=1
export KICAD_MCP_PROJECT=/tmp/gui-test-project
export KICAD_MCP_GUI_REF=U1
export KICAD_MCP_FREEROUTING_JAR=/home/astra/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar
```

En `~/.claude.json`, `/mcp reconnect` si se editan.

**KiCad reiniciado limpio.** `/tmp/gui-test-project/` restaurado
desde el fixture `despertador-routed` del D5.

## Cierre esperado

Sesión 27 cerrada con:
- Generalización D-23.2 implementada en `fill_zones` y
  `add_zone(fill=True)`.
- Test de regresión verde en 2 corridas por tool.
- Contrato D-23.2 extendido a tres tools, documentado en ADR-0012
  actualizado.
- `POST_ZONE_PERSIST_FAILED` disponible como código de error
  compartido para ambas tools nuevas.
- Reporte de sesión completo.

Sesión 28 = D6 con la misma placa despertador, ratifica cierre real de
la generalización + primera aplicación empírica de D-26.1 (`fill_zones()`
obligatorio post-colocación pre-baseline).

Escenarios posibles según resultado de sesión 27:

- **Cierre limpio:** avanzar a sesión 28 (D6) según secuencia Fase 3.
  Si D6 verde → 2 verdes consecutivos, más cerca de criterio de
  convergencia Fase 3.
- **Bloqueo del Bloque 2 por decisión de arquitectura sobre
  `enforce_hole_clearance`:** `AskUserQuestion` obligatoria, arquitecto
  decide minimalista vs completo, sesión continúa o se re-planifica.
- **Test de regresión no verde en 2 corridas:** investigación
  mandatoria antes del merge. Sospechar (a) el patrón de sesión 24 no
  aplica idéntico a estas dos tools por diferencia estructural, o
  (b) algún test existente presume comportamiento pre-Opción X que
  el cambio rompe. En ambos casos, no mergear hasta entender.

**Recordatorio operacional:** cada bloque respeta su timeout. Cambio
quirúrgico, patrón conocido (sesión 24), test como gate del merge,
disciplina de scope. Sesión 27 es aplicación fiel del patrón ratificado
en producción, no re-diseño.
