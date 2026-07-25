# Sesión 27 — Generalización del contrato D-23.2 a `fill_zones` y `add_zone(fill=True)`

**Rama:** `sesion/27-generalizacion-d23-2` (desde `master`, post-merge de
`sesion/26-fix-solder-mask-ant1`). **Tipo:** generalización de contrato
arquitectónico + test de regresión gate del merge.

## Resumen ejecutivo

Se extendió el contrato D-23.2 (ADR-0012, sesión 24: "cuando la tool termina
OK, disco == memoria") a `fill_zones` y `add_zone(fill=true)` — las dos tools
que el propio ADR-0012 había identificado en su momento como portadoras del
mismo bug conceptual que `route_board`, diferido explícitamente a una sesión
de generalización posterior. Con D-23.2 ratificado 5/5 en producción (2/2
regresión sesión 24 + 3/3 dogfooding D5 sesión 25), esa sesión fue la 27. La
lectura previa a implementar corrigió una premisa del brief: ambas tools ya
llamaban a `enforce_hole_clearance()` desde sesión 21 (F-D3-01) — lo único
que faltaba era la mitad "persistencia" del contrato (`save_board()` +
fallo tipado + mtimes post-save), así que el cambio quirúrgico resultó más
chico de lo anticipado y no requirió la decisión minimalista-vs-completo que
el brief tenía prevista como posible bifurcación. Código de error nuevo:
`POST_ZONE_PERSIST_FAILED`, compartido entre las dos tools. Validado en vivo
contra KiCad 10.0.4 real (sin Freerouting — el bug es de refill, no de
ruteo): 2/2 corridas consecutivas verdes del test de regresión sobre el
fixture `despertador-routed`, con `run_drc()` independiente inmediato
coincidiendo con el estado persistido en ambas tools, mtime cambiado, sin
`EXTERNAL_EDIT_DETECTED` espurio. Merge pendiente de confirmación del
arquitecto.

## Bloque 1 — Diseño

Exploración con dos agentes en paralelo (código de `fill_zones`/`add_zone`/
`enforce_hole_clearance`/`route_board`/`errors.py`/`store.py` por un lado;
ADR-0012, reportes de sesión 24/25, investigación 23-fd4-02 y tests
existentes por otro) más lectura directa del ADR-0012 y los tests GUI de
sesión 24. Hallazgos clave antes de tocar código:

1. **La sospecha del brief era falsa.** `fill_zones` (pcb.py:2279, previo a
   la sesión) y `add_zone` con `fill=true` (pcb.py:2056) **ya** llamaban a
   `bridge.enforce_hole_clearance()` desde sesión 21 (comentario F-D3-01:
   "workaround post-fill obligatorio en TODO camino que rellene"). De los 3
   call sites de `enforce_hole_clearance` en `src/`, 2 ya existían en las
   tools objetivo — solo `route_board` tenía además la mitad de
   persistencia. Esto colapsó la decisión #3 del arquitecto ("patrón
   completo, no minimalista") a un hecho ya cumplido en 2/3, no una elección
   a hacer.
2. **El punto crítico real era el mismo hallazgo #31 de sesión 24: mtimes
   post-save.** Ambas tools registraban `store.register(state, mtimes=None)`
   (snapshot vivo, ADR-0007) — si se agregaba el `save_board()` sin migrar
   a `mtimes` de disco recolectados **después** del save, el próximo
   `check_no_external_disk_edit` de cualquier tool dispararía un
   `EXTERNAL_EDIT_DETECTED` espurio contra el propio guardado.
3. **`add_zone(fill=false)` queda fuera por diseño** — sin fill no hay
   refill+enforce que persistir; la rama conserva `mtimes=None` sin cambios.
4. **`live_stale` no aplica.** Estas tools bajan vivo→disco (igual sentido
   que `route_board`'s save final), no dejan el disco adelante del vivo —
   `mark_live_stale` modela lo contrario.
5. **Decisión con el arquitecto durante la planificación (no en el brief
   original):** NO agregar campo `drc` al payload de `fill_zones`/`add_zone`.
   A diferencia de `route_board` (que ya reportaba `drc.err_post` desde
   sesión 17), estas dos tools nunca tuvieron ese campo — agregarlo habría
   sido un cambio de contrato JSON en dos tools baratas y frecuentes, más un
   `kicad-cli` de varios segundos por llamada (`fill_zones` se usa de forma
   idempotente y barata en flujos existentes, ver `test_zones_e2e_gui.py`).
   Para estas dos tools el contrato D-23.2 se redujo a su núcleo: disco ==
   vivo. El `run_drc()` que el agente ya puede invocar por su cuenta pasa a
   ser fiel — ese es el efecto real del fix.
6. **`POST_ZONE_PERSIST_FAILED` compartido**, no un código por tool (decisión
   fijada por el arquitecto, confirmada sin fricción): mismo argumento que
   `POST_ROUTE_PERSIST_FAILED` — el llamador ya sabe qué tool invocó.
7. **ADR: extender 0012, no crear 0013** — decisión fijada, sin fricción al
   ejecutar.

No hubo bifurcación hacia `AskUserQuestion` de arquitectura en este bloque
(el brief anticipaba una posible por el estado de `enforce_hole_clearance`,
que resultó no aplicar). Cero líneas de código tocadas.

## Bloque 2 — Implementación

**Archivos tocados:** `src/kicad_mcp/tools/pcb.py`, `src/kicad_mcp/errors.py`,
`docs/specs/tool-catalog.md`, `docs/adr/0012-route-board-persist-contract.md`,
`tests/test_pcb_zones.py`.

- **`fill_zones`:** tras `enforce_hole_clearance` (ya existente), se agregó
  un `save_board()` incondicional dentro de `try/except KicadMcpError` →
  `POST_ZONE_PERSIST_FAILED` en caso de fallo (mensaje explícito: el vivo ya
  tiene el fix, el disco no). Incondicional a propósito: aun con
  `zones_filled == 0`, `enforce_hole_clearance` puede haber tocado keepouts
  en el vivo. `store.register()` migrado a mtimes de disco recolectados
  **después** del save (antes: `mtimes=None`).
- **`add_zone`:** mismo bloque, pero **dentro del `if fill:`** ya existente
  — la rama `fill=false` no se tocó (conserva `mtimes=None`, sin persistir,
  comportamiento idéntico a antes de la sesión). Efecto secundario en la
  estructura: el `store.register()` dejó de ser una línea compartida por
  ambas ramas — cada rama registra su propio tipo de snapshot ahora.
- **`errors.py`:** `POST_ZONE_PERSIST_FAILED` agregado al final del
  `StrEnum ErrorCode` (adición pura, excepción sancionada de F1, mismo
  precedente que `POST_ROUTE_PERSIST_FAILED` en sesión 24).
- **`tool-catalog.md`:** código nuevo agregado a la columna de errores de
  `add_zone` y `fill_zones`; fila nueva en §Taxonomía (después de
  `POST_ROUTE_PERSIST_FAILED`); párrafo narrativo nuevo ("Persistencia
  D-23.2") en la sección de zonas explicando el contrato y la asimetría
  `fill=true`/`fill=false`.
- **ADR-0012:** sección nueva "Extensión de alcance (sesión 27)" — las tres
  tools cubiertas, el hallazgo de que `enforce_hole_clearance` ya estaba,
  la equivalencia semántica entre los dos códigos de persistencia (deuda de
  unificación diferida), y la decisión explícita de no agregar `drc` al
  payload de las dos tools nuevas.
- **`tests/test_pcb_zones.py`:** `_FakeBridge` ganó `save_board()` (override,
  con `fail_save_after` para simular fallo, mismo patrón que
  `test_route_board.py`) y `self.saved`. 2 tests nuevos
  (`test_add_zone_fill_true_persist_failed`,
  `test_fill_zones_persist_failed`) + assertions reforzadas en 4 tests
  existentes (`bbox_happy_path`, `polygon_happy_path`,
  `refills_all_and_is_idempotent`, `stale_zone_id`) verificando `bridge.saved`
  en cada camino (persiste / no persiste / falla).

**Guardarraíles respetados:** `route_board` no tocado (su
`POST_ROUTE_PERSIST_FAILED` sigue intacto); `enforce_hole_clearance`
internamente no tocado (D-23.3/R16 fuera de alcance); `move_footprint` no
tocado (D-26.1 es protocolo operacional).

**Diff:** `pcb.py` +74/-5 (bloques de persistencia en las dos tools, sin
reordenar nada preexistente); `errors.py` +1; `tool-catalog.md` +15/-2;
`docs/adr/0012...md` +51 (sección nueva); `test_pcb_zones.py` +77. Sin
desvíos del diseño del Bloque 1 — no hizo falta `AskUserQuestion` de
fricción de implementación. Verificación intermedia (`ruff check`/`mypy
src/`/`pytest -m "not integration"`) verde en la primera pasada.

## Bloque 3 — Test de regresión (gate del merge)

**Test nuevo:** `tests/test_pcb_session27_zone_persist_gui.py`
(`integration_gui_slow`), un test por tool sobre el fixture
`despertador-routed` ya abierto en KiCad — **sin Freerouting** (a diferencia
del test de sesión 24: el bug conceptual que se blinda es del refill, no del
ruteo, así que corre en segundos y no requiere jar/java/pcbnew de sistema).
Cada test se auto-arregla al inicio (borra cualquier zona GND de cobre
preexistente vía `delete_zone`, o la crea si falta) para ser robusto a
corridas repetidas sin depender del orden ni de qué dejó la corrida anterior
— el bbox de la zona se deriva en runtime de `get_world_context(kind="pcb")`,
nunca hardcodeado.

4 assertions gate por test:
1. Mtime del `.kicad_pcb` cambia entre pre-operación y post-operación
   (evidencia de que el `save_board()` de D-23.2 corrió).
2. **Corazón del contrato:** `run_drc()` independiente inmediato, SIN
   `save_board()` manual, no trae `hole_clearance` espurio ni `clearance`
   contra la Zone GND.
3. Una operación D-23.2 posterior (`fill_zones()` de nuevo, idempotente) no
   dispara `EXTERNAL_EDIT_DETECTED` — evidencia de que los mtimes del
   snapshot se registraron post-save (hallazgo #31 de sesión 24).
4. Conteo de keepouts en rango `[4, 8]` (umbral generoso, mismo que sesión
   24 — D-23.3/R16 sin proliferación descontrolada).

**Preparación del entorno (con confirmación del arquitecto vía
`AskUserQuestion`):** el entorno vivo (`/tmp/gui-test-project`) no coincidía
con el fixture checked-in al empezar el Bloque 3 (mtime más viejo, contenido
de una sesión anterior — probablemente residual de sesión 26). Se respaldaron
los 4 archivos de proyecto vivos a un directorio temporal, se sobrescribieron
con `tests/fixtures/despertador-routed/` (mismo path, sin `rm -rf` del
directorio para no invalidar el lock de KiCad), y se sincronizó el editor
vivo con `reload_board_from_disk()` (sin reiniciar la GUI) — confirmado
correcto con `get_component_detail(ANT1)` y `get_zones(layer="B.Cu")` (GND
filled + 4 keepouts, igual al README del fixture).

**Corridas — validado en VIVO contra KiCad 10.0.4 real:**

| Corrida | Resultado | Duración |
|---|---|---|
| 1 | ✅ 2/2 passed | 69.16s |
| 2 | ✅ 2/2 passed | 68.11s |

Ambas corridas: mtime cambiado en las dos tools, `run_drc()` independiente
sin `hole_clearance` ni `clearance`-vs-GND en ninguna, `fill_zones()` de
seguimiento sin `EXTERNAL_EDIT_DETECTED` en ninguna, 4 keepouts estables
(ANT1 + 3× J1 NPTH, sin proliferación). `run_drc()` final del board (tras
ambas corridas) confirmó 0 errores / 0 warnings — el board quedó sano.
Determinismo confirmado, sin señales de flakiness (assertion opcional del
brief — test unitario del path de fallo simulado — se cubrió en el Bloque 2
con el `_FakeBridge` en vez de acá, más barato y determinista sin KiCad).

## Bloque 4 — DoD, docs y estado del merge

### DoD checklist

1. ✅ `ruff check` limpio (repo completo; diff acotado a los archivos de esta
   sesión — se descartó un fix de formato no relacionado en
   `scripts/verificar_entorno.py` que `ruff format .` tocó de paso, mismo
   criterio que sesión 24).
2. ✅ `mypy src/` limpio (33 archivos).
3. ✅ `uv run pytest -m "not integration"`: 351 passed, 37 skipped, 22
   deselected — sin regresiones.
4. ✅ `uv run pytest -m integration_gui_slow
   tests/test_pcb_session27_zone_persist_gui.py`: 2/2 corridas verdes en
   vivo para las dos tools (ver Bloque 3).
5. ✅ ADR `docs/adr/0012-route-board-persist-contract.md` actualizado con
   "Extensión de alcance (sesión 27)".
6. ✅ Docstrings de `fill_zones` y `add_zone` actualizados (contrato D-23.2
   + referencia al ADR, junto al bloque refill+enforce).
7. ✅ `POST_ZONE_PERSIST_FAILED` definido (`errors.py`), usado en las dos
   tools, listado en `tool-catalog.md` (taxonomía + columnas de errores).
8. ✅ Fixture vía helper en runtime (no directorio estático) commiteado
   como parte del test file.

### Guardarraíles de scope — respetados

`route_board` no tocado. `move_footprint` no tocado (D-26.1 sigue siendo
protocolo operacional, sin cambio de código). Internals de
`enforce_hole_clearance` (loop de vías, D-23.3/R16) no tocados. P1 solder
mask ANT1 no tocado. Los dos códigos de persistencia (`POST_ROUTE_...` /
`POST_ZONE_...`) NO se unificaron — deuda documentada, diferida
explícitamente.

### Estado del merge

**Pendiente de confirmación explícita del arquitecto** — diff completo y
resultado de las 2 corridas del test de regresión presentados para revisión
antes de mergear a `master`. Se incluye en el mismo commit
`docs/historico/prompts/PROMPT-SESION-27.md` (prompt de esta sesión, patrón
histórico de sesiones anteriores).

## Métricas

- Líneas cambiadas: `pcb.py` +74/-5, `errors.py` +1, `tool-catalog.md`
  +15/-2, `docs/adr/0012...md` +51 (sección nueva), `test_pcb_zones.py` +77,
  `test_pcb_session27_zone_persist_gui.py` +292 (nuevo). Total ≈ +510/-7.
- Tiempo por bloque: Bloque 1 dentro del timebox (30 min, exploración en
  paralelo); Bloque 2 dentro del timebox (45 min, sin fricción); Bloque 3
  bajo el timebox nominal (60 min) pero con un desvío operacional no
  anticipado en el brief — restaurar el entorno GUI vivo antes de poder
  correrlo, resuelto con `AskUserQuestion` en vez de decisión unilateral, sin
  reiniciar la GUI; Bloque 4 dentro del timebox (30 min).
- **Desvíos del plan:** (a) la premisa del brief sobre
  `enforce_hole_clearance` ausente en `fill_zones`/`add_zone` era falsa —
  desvío positivo, redujo el alcance real del cambio; (b) el entorno GUI vivo
  no coincidía con el fixture al llegar al Bloque 3 — resuelto con
  confirmación explícita antes de mutar el proyecto abierto en KiCad, sin
  reiniciar la GUI (restore de archivos + `reload_board_from_disk()`); (c)
  no se necesitó la bifurcación minimalista-vs-completo que el brief
  anticipaba como posible.

## Recomendación explícita para sesión 28 (D6)

Ratificación estadística del contrato D-23.2 extendido, mismo patrón
V1/V2/V3/V4 de D5 (sesión 25), con dos focos nuevos:

1. **V2 ahora se ejercita en las tres tools**, no solo `route_board` — cada
   corrida de D6 debería incluir al menos una llamada real a `fill_zones()`
   y una a `add_zone(fill=true)` (no solo el refill interno de
   `route_board`) para que la ratificación cubra el código nuevo de esta
   sesión en condiciones de dogfooding real, no solo en el test de
   regresión aislado.
2. **Primera aplicación empírica de D-26.1** (`fill_zones()` obligatorio
   post-colocación, pre-baseline — hallazgo de sesión 26 sobre
   `move_footprint` no disparando refill de zonas). D6 es la primera vez que
   ese protocolo se ejercita en un dogfooding real, no solo en la
   investigación que lo originó.

Si D6 sale verde, sería el segundo verde consecutivo de Fase 3 — más cerca
del criterio de convergencia. Placa: mismo despertador (fixture
`despertador-routed`, regenerado en sesión 25).
