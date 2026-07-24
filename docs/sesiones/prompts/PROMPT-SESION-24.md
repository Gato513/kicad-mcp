# Sesión 24 — Fix F-D4-02 (Opción X): reordenar medición DRC + persistir en `route_board`

**Tipo:** IMPLEMENTACIÓN de fix quirúrgico + test de regresión gate del
merge. Nueva rama `sesion/24-fix-fd4-02-opcion-x` desde `master`
**post-merge de la rama de sesión 23** (`sesion/23-investigacion-fd4-02`,
que es solo docs — mergear primero para que el reporte de investigación
esté disponible en `master`).

**Origen:** F-D4-02 cerrada en investigación por sesión 23. Causa raíz
confirmada empíricamente (3/3 reproducciones + test sintético): NO es
protección ausente, es **bug de orden de medición + falta de
persistencia** en `route_board`. El pipeline mide DRC sobre disco crudo
antes del refill+enforce interno, y nunca guarda el vivo ya arreglado.
Opción X acordada por el arquitecto: reordenar la medición a DESPUÉS
del bloque refill+enforce, y persistir con `save_board()` al final.
Fallo visible si no se puede garantizar disco==memoria==err_post.

**Alcance mandatorio:** SOLO `route_board`. `fill_zones` y
`add_zone(fill=True)` sufren el mismo patrón conceptual (identificado
en Bloque 2 de sesión 23) pero quedan diferidos a una sesión de
generalización POSTERIOR — el arquitecto fue explícito: causa raíz →
cambio mínimo → test de regresión → dogfooding, sin ampliar
superficie. NO tocar esas otras dos tools en esta sesión aunque sea
tentador.

**Criterio de cierre (gate del merge):** el test de regresión del
Bloque 3 debe pasar de forma determinista y debe cubrir el patrón
completo del contrato reforzado — no es suficiente verificar el JSON
de `route_board`, también hay que verificar que un `run_drc()`
independiente inmediato (sin `save_board()` manual) coincide con
`err_post`. El humano fue explícito: sin ese test verde no se mergea.

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4.

**Consejo operacional (D-D4.1 aplicable a esta sesión):** los caminos
sugeridos abajo son inclusivos, no restrictivos. Si aparece una forma
mejor de estructurar el test o el helper de fixture, se puede elegir
sin pedir permiso — mientras no cambie el alcance (solo `route_board`)
ni el criterio de cierre (test como gate del merge).

**Timeboxing por bloque** (mismo modelo que sesión 23, respetar):

- Bloque 1: 30 min.
- Bloque 2: 60 min.
- Bloque 3: 45 min.
- Bloque 4: 30 min.

Total target: 2h45m. Si un bloque agota su timeout sin resultado,
documentar y continuar. NO acumular tiempo pidiendo más.

---

## Preparación (antes del Bloque 1)

1. Verificar que `sesion/23-investigacion-fd4-02` ya está mergeada en
   `master` (docs de investigación disponibles).
2. `git checkout master && git pull`.
3. `git checkout -b sesion/24-fix-fd4-02-opcion-x`.
4. `/tmp/gui-test-project/` restaurado desde el fixture
   `tests/fixtures/despertador-routed/` (baseline conocido).
5. KiCad reiniciado limpio.
6. `health()` → ipc ok, kicad-cli 10.0.4 detectado.
7. **Lectura obligatoria antes de arrancar:**
   `docs/investigacion/23-fd4-02.md` completo. Ahí está la causa raíz
   con evidencia bit-exacta y las tres opciones evaluadas. El fix de
   esta sesión es la Opción X descrita ahí — no reinterpretes.

---

## Bloque 1 — Diseño del cambio (timeout: 30 min)

**Objetivo:** entender exactamente qué mover, dónde cortar, qué
depende de qué. NO tocar código todavía. El propósito es evitar el
antipatrón "implemento primero y descubro las dependencias después".

### Lectura obligatoria

1. `src/kicad_mcp/tools/pcb.py:2366-2588` (función `route_board`
   completa).
2. `src/kicad_mcp/bridge/ipc.py:1902-2036` (`enforce_hole_clearance`).
3. Ubicación actual de `refill_zones` y `save_board` en el bridge.
4. Si existe, la definición del set de códigos de error
   (`SNAPSHOT_STALE`, `EXTERNAL_EDIT_DETECTED`, etc.) para saber dónde
   agregar `POST_ROUTE_PERSIST_FAILED`.

### Análisis a producir (documento breve, ~1 página, notas para vos
mismo — no necesita ser el reporte final)

1. **Estado actual del pipeline:**
   - Paso 1 (línea 2416): `save_board` implícito.
   - Paso 2: `run_autoroute` (subproceso).
   - Paso 3: `os.replace(routed_pcb, pcb_path)` — disco = salida cruda.
   - Paso 4 (línea 2434): **`post_report = run_drc(pcb_path)`** ← acá
     se mide, sobre disco crudo. Este es el que hay que MOVER.
   - Paso 5 (línea 2479): `reload_board_from_disk(open_board)`.
   - Paso 6 (líneas 2500-2509): branch condicional
     `if refill and zones_existentes>0 and reloaded is True`:
     `refill_zones()` + `enforce_hole_clearance()`.
   - Paso 7: construcción del payload de retorno.
   - **Falta:** ningún `save_board()` post-paso-6.

2. **Estado objetivo del pipeline:**
   - Reordenar: paso 6 (refill+enforce) va ANTES del cómputo de
     `post_report`.
   - `post_report` se mide sobre el archivo en disco DESPUÉS de que el
     bloque refill+enforce haya persistido su resultado.
   - **`save_board()` incondicional al final del branch condicional
     `if refill and zones_existentes>0 and reloaded is True`** —
     dentro del mismo branch donde vive el refill+enforce, para que
     los casos `refill=False` o `zones_existentes=0` no dispare save
     automático (razón: si el llamador desactiva refill explícitamente
     o no hay zonas, el disco ya es la salida cruda por diseño).
   - Si `save_board()` falla → levantar
     `POST_ROUTE_PERSIST_FAILED` con mensaje claro. Ver punto 3.

3. **Dependencias entre pasos:**
   - `pre_report` (medido antes del route) → sigue igual, no cambia.
   - `post_report` (hoy paso 4) → se mueve a después del paso 6.
   - `por_tipo_introducidos` = `diff_violations(pre_report,
     post_report)` — al mover `post_report`, este diff pasa a
     computarse sobre el estado real persistido. Verificar en la
     lectura que no haya nada más que dependa del `post_report`
     "temprano".
   - `zones.refilladas` en el payload de retorno (hoy proviene del
     bloque refill) → sigue funcionando igual, solo cambia el orden
     relativo al `post_report`.

4. **Diseño del código de error `POST_ROUTE_PERSIST_FAILED`:**
   - Semántica: "`route_board` completó ruteo + refill pero no pudo
     garantizar que el disco quedara sincronizado con el estado
     interno del board (memoria)".
   - Distinto de `EXTERNAL_EDIT_DETECTED` (que indica que algo
     externo modificó el archivo). Este es "yo mismo no pude
     escribir".
   - Payload sugerido: `code`, `message`, y contexto útil (por
     ejemplo, el `pcb_path`, si el vivo tiene el estado bueno o no,
     hint de qué puede hacer el llamador — por ejemplo intentar
     `save_board()` manual).

5. **Comportamiento del board vivo cuando save falla:**
   - Decisión sugerida (no impuesta): dejar el vivo COMO ESTÁ (con el
     estado arreglado post-refill), NO forzar reload que lo volvería
     a la salida cruda. El error `POST_ROUTE_PERSIST_FAILED` informa
     al llamador que puede retry `save_board()` explícito, o
     descartar. NO tocar el vivo.
   - Si tenés otra opinión al leer el código, dejarlo documentado en
     el reporte final y proceder.

6. **Docstring / documentación en código:**
   - **ADR obligatorio** en `docs/adr/`
     (`0013-route-board-persist-contract.md` o el número que
     corresponda en la secuencia actual). El criterio es la
     **naturaleza del cambio, no su tamaño**: D-23.2 introduce un
     contrato arquitectónico nuevo ("cuando `route_board` termina OK,
     disco == memoria == err_post reportado"), no una mera aclaración
     de comportamiento. El ADR puede ser breve pero es mandatorio
     porque futuras sesiones no deben poder reinterpretar el contrato
     por ambigüedad de docs.
   - Docstring de `route_board`: párrafo breve que remita al ADR y
     describa el contrato reforzado en 1-2 líneas. No repetir el
     razonamiento — referenciar.
   - Comentario o docstring cerca del bloque refill: mencionar
     D-19.1 v6 (Freerouting no respeta el plano GND como exclusión
     para nets ajenos; el refill es lo que arregla el clearance vs
     zona, no cosmético). Ubicación exacta a criterio. Esto es
     aclaración de comportamiento — docstring/comentario alcanza, no
     necesita ADR separado.

### Salida esperada del Bloque 1

Nota breve en el reporte (`docs/sesiones/24-reporte.md`, sección
"Bloque 1 — Diseño") con los 6 puntos anteriores respondidos. Cero
líneas de código modificadas en este bloque.

---

## Bloque 2 — Implementación quirúrgica (timeout: 60 min)

**Objetivo:** aplicar el diseño del Bloque 1. Solo lo diseñado ahí,
nada más.

### Cambios esperados

1. **`src/kicad_mcp/tools/pcb.py` (`route_board`):**
   - Mover el bloque `if refill and zones_existentes>0 and reloaded
     is True: refill_zones() + enforce_hole_clearance()` ANTES del
     cómputo de `post_report`.
   - Agregar `save_board()` al final de ese branch.
   - Manejo de fallo del save → `POST_ROUTE_PERSIST_FAILED`.
   - Docstring actualizado con el contrato D-23.2.
2. **Definición del código de error `POST_ROUTE_PERSIST_FAILED`** en
   el módulo donde vivan los otros códigos.
3. **Comentario / docstring** cerca del bloque refill mencionando
   D-19.1 v6.

### Guardarraíles

- **NO tocar** `enforce_hole_clearance` (líneas 1902-2036 de
  `ipc.py`). El loop de vías (D-23.3, R16) es scope creep y va en
  P3/P4. Si aparece algo evidente en la lectura, dejarlo como TODO
  en el reporte, no arreglar acá.
- **NO tocar** `fill_zones` ni `add_zone(fill=True)`. Sufren el mismo
  bug conceptual pero se difieren a sesión de generalización.
- **NO tocar** el generador DSN (Opción Y descartada).
- **NO ampliar** el docstring más allá de lo necesario para D-23.2 +
  D-19.1 v6.

### Verificación intermedia

Al terminar los cambios de código, ANTES de pasar al Bloque 3:
- `ruff check` limpio.
- `mypy src/` limpio.
- `uv run pytest -m "not integration"` sigue verde (sin regresiones
  en unit tests).

Si algo de esto falla, arreglar en el Bloque 2 antes de avanzar. Si
falla algo que no tiene solución obvia en <15 min, documentar y
consultar (`AskUserQuestion` explícita) antes de seguir.

### Fricción anticipada (posible desvío)

Si durante la implementación aparece que **el reordenamiento requiere
cambios en más de una función** o que **`por_tipo_introducidos`
computa algo que se rompe con el nuevo orden**, PARAR y consultar
(`AskUserQuestion`) antes de expandir el scope. La disciplina
"cambio mínimo, causa raíz única" es explícita del arquitecto — no
la violés por atajo.

### Salida esperada del Bloque 2

Código modificado, checks internos verdes. Reporte en la sección
"Bloque 2 — Implementación" con: diff resumido (líneas añadidas /
removidas / modificadas), archivos tocados, decisiones tomadas
durante la implementación.

---

## Bloque 3 — Test de regresión (gate del merge) (timeout: 45 min)

**Objetivo:** producir el test que va a bloquear regresiones futuras.
Este bloque es el que define si el merge procede o no.

### Fixture

Fixture nuevo:
`tests/fixtures/route_board_persist_regression/`.

**Contenido esperado:** estado con footprints colocados, plano GND
filleado, 4 keepouts `__kicadmcp_hc__` (los fijos: ANT1 + 3× J1 NPTH),
0 tracks/vías.

**Cómo generar el fixture (opciones, elegir la más limpia):**

- **Opción (b) recomendada:** helper en el test que restaure el
  fixture existente `despertador-routed`, borre tracks con
  `delete_tracks_bulk(bbox=<board>, include_vias=True)`, guarde y
  use ese estado. Es reproducible, no depende de artefactos de
  sesiones externas, y la generación queda en el propio código de
  test.
- **Opción (a):** copiar manualmente el estado
  post-`delete_tracks_bulk` de la reproducción de sesión 23 al
  fixture nuevo. Frágil (depende de reproducir bit-exacto un estado
  transitorio de otra sesión) — evitar.
- **Opción (c):** fixture sintético mínimo (no la placa despertador).
  Ventaja: rápido. Desventaja: hay que verificar que dispara el bug
  (el bug se manifiesta con planos + ruteo denso — un fixture
  demasiado chico puede no disparar). Solo si (b) presenta problemas.

Si (b) es viable, ir por ahí. Si aparece obstáculo (ej. el bbox del
`delete_tracks_bulk` no se calcula obvio), documentar y consultar.

### Test integration a producir

Ubicación: `tests/integration/` (o donde estén los otros tests de
`route_board`).

Assertions mandatorias (**gate del merge**):

1. **`result.drc.err_post.por_tipo.hole_clearance` == 0.**
2. **`result.drc.err_post.por_tipo.clearance` no incluye
   violaciones cuyos ítems referencien `Zone [GND]`.** (Otras
   violaciones de clearance pueden existir por otras causas — por
   ejemplo courtyards del proceso — el punto es que el patrón "net
   ajeno vs Zone GND" quedó eliminado.)
3. **`run_drc()` independiente inmediato SIN llamar `save_board()`
   manual coincide con `result.drc.err_post`** (total y desglose por
   tipo). Este es el corazón del contrato D-23.2 — si esto falla,
   el fix no cerró el bug.
4. **`get_zones(layer="B.Cu")` muestra los 4 keepouts fijos, sin
   proliferación descontrolada** (no más de, digamos, 8 keepouts —
   umbral generoso para no ser flakey si el pipeline agrega alguno
   por-vía en el futuro).

Assertions opcionales (nice to have, no bloqueantes):

5. **mtime del `.kicad_pcb` cambió** entre pre-route y post-route
   (evidencia adicional de que `save_board()` se ejecutó).
6. **Test unitario adicional** simulando fallo de `save_board()`
   (mock/fake) y verificando que `route_board` levanta
   `POST_ROUTE_PERSIST_FAILED`. **Este es diferencial, no gate.** Si
   la arquitectura del bridge hace este mock difícil (por ejemplo,
   requiere refactor mayor), documentar y omitir sin bloqueo. Un
   test manual del path de error en el reporte del Bloque 4 puede
   suplirlo.

### Determinismo del test

`route_board` invoca Freerouting, que tiene componente
no-determinístico. Las assertions 1-4 deberían ser robustas a esa
no-determinación (el bug era estructural, no de posiciones
específicas). Si el test resulta flakey en 2+ corridas, es señal de
que el fix tiene un caso borde no cubierto — reportar y consultar.

### Salida esperada del Bloque 3

Test file nuevo, fixture nuevo (o helper), test verde en al menos 2
corridas seguidas para confirmar no-flakey. Reporte con: cantidad de
assertions, corridas exitosas, timing típico.

---

## Bloque 4 — DoD, docs y merge (timeout: 30 min)

### DoD checklist

1. `ruff check` limpio en todo el repo.
2. `mypy src/` limpio.
3. `uv run pytest -m "not integration"` verde (sin regresiones en
   unit tests).
4. `uv run pytest -m integration` — el test nuevo pasa en al menos 2
   corridas consecutivas.
5. **ADR `0013-route-board-persist-contract.md`** (o el número
   correspondiente) commiteado en `docs/adr/` con los cuatro puntos
   listados abajo.
6. Docstring de `route_board` actualizado: contrato D-23.2 en 1-2
   líneas + referencia al ADR.
7. Docstring o comentario cerca del bloque refill mencionando
   D-19.1 v6.
8. Código de error `POST_ROUTE_PERSIST_FAILED` definido y usado.
9. Fixture nuevo (o helper) commiteado.

### Documentación en `docs/`

**ADR obligatorio** (decidido por naturaleza del cambio, no por
longitud): `docs/adr/0013-route-board-persist-contract.md` (o el
número que corresponda en la secuencia actual). Debe contener:

- **Contrato D-23.2 explícito:** "cuando `route_board` termina OK,
  disco == memoria == err_post reportado".
- **Referencia a la investigación de sesión 23**
  (`docs/investigacion/23-fd4-02.md`) como origen del contrato.
- **Alcance actual acotado a `route_board`** y nota explícita de que
  `fill_zones` y `add_zone(fill=True)` sufren el mismo patrón
  conceptual pero quedan diferidos a sesión de generalización
  posterior — para que quien lea el ADR en el futuro entienda el
  porqué del alcance limitado y no lo tome como decisión permanente.
- **Código de error `POST_ROUTE_PERSIST_FAILED` y su semántica**:
  fallo del contrato de sincronización disco/memoria, distinto de
  `EXTERNAL_EDIT_DETECTED`, con nota de qué puede hacer el llamador
  (retry `save_board` manual, descartar).

Docstring de `route_board` remite al ADR y describe el contrato en
1-2 líneas — no repetir razonamiento. El comentario/docstring cerca
del bloque refill sobre D-19.1 v6 va inline (no requiere ADR
separado, es aclaración de comportamiento).

### Commit + merge

- Mensaje sugerido:
  `fix(route_board): reorder DRC measurement + persist, close F-D4-02
  (Opción X)`.
- Descripción del commit: referencia a `docs/investigacion/23-fd4-02.md`
  + descripción breve del cambio.
- **Antes de mergear:** `AskUserQuestion` obligatoria al arquitecto
  con el diff completo y el resultado del test. El arquitecto puede
  querer revisar antes del merge — el humano fue explícito en que
  este test es gate del merge.

### Reporte final

`docs/sesiones/24-reporte.md` con:
- Resumen ejecutivo (1 párrafo).
- Bloque 1: diseño (análisis breve).
- Bloque 2: implementación (diff resumen, archivos tocados,
  decisiones).
- Bloque 3: test (fixture usado, assertions, corridas exitosas).
- Bloque 4: DoD status + docs + estado del merge.
- Métricas: líneas cambiadas totales, tiempo por bloque, si hubo
  desvíos del plan.
- **Recomendación explícita para sesión 25 (D5):** las mismas
  precondiciones que D3/D4 + verificación específica del contrato
  reforzado (repetir la trilogía V1/V2/V3 del D4 con foco en que V2
  ahora ratifica fidelidad al vivo, no solo consistencia de lectura
  de disco).

---

## Fuera de alcance

- `fill_zones` y `add_zone(fill=True)` (P2 posterior, sesión de
  generalización).
- Loop de vías de `enforce_hole_clearance` (D-23.3, R16, deuda
  técnica en P3/P4).
- Solder mask bridge en ANT1 (P1 separado).
- Opción Y (inyección keepout al DSN por-net vs zonas). Descartada.
- Cualquier feature nuevo.
- Cualquier item del backlog no listado como P0 F-D4-02.

## Env vars

Las mismas de siempre:

```bash
export KICAD_MCP_GUI_TEST=1
export KICAD_MCP_PROJECT=/tmp/gui-test-project
export KICAD_MCP_GUI_REF=U1
export KICAD_MCP_FREEROUTING_JAR=/home/astra/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar
```

En `~/.claude.json`, `/mcp reconnect` si se editan.

**KiCad reiniciado limpio.** `/tmp/gui-test-project/` restaurado
desde el fixture `despertador-routed` del D3.

## Cierre esperado

Sesión 24 cerrada con:
- Fix Opción X implementado y mergeado.
- Test de regresión verde en al menos 2 corridas consecutivas.
- Contrato D-23.2 documentado en código.
- Reporte de sesión completo.

Sesión 25 = D5 con la misma placa despertador. Ratifica cierre real
del F-D4-02 en producción y de la trilogía V1/V2/V3 del D4. Si D5
verde → considerar D6 con escalada de complejidad o preparar
release. Si D5 abre nuevo P0 → más iteraciones del ciclo de
hardening.

**Recordatorio operacional:** cada bloque respeta su timeout. Fix
quirúrgico, causa raíz única, test como gate del merge, disciplina
de scope. Sesión 23 identificó exactamente qué cambiar y por qué —
sesión 24 es ejecución fiel de esa decisión, no re-diseño.
