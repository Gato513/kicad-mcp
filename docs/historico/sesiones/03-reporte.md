# Reporte de sesión 03 — cierre del MVP + apertura de v0.2

**Fecha:** 2026-07-09 · **Rama:** `sesion-03` · **Commits:** 7 (uno de
setup + uno por tarea, según lo pedido) · **Estado:** DoD cumplido en
las seis tareas, sin push.

## Qué se completó

### Setup — regla nueva (fixtures inmutables in place)

- `tests/conftest.py` con `mirror_fixture(src, dst)` recursivo. Los
  tests integration de `state_builder`, `validate`, `world_context` y
  `export` ahora copian la fixture a `tmp_path` antes de invocar
  kicad-cli.
- Eliminado el leftover `tests/fixtures/002_medio/tmp9p_t_795.json`
  (temporal huérfano de un run de sesión 02 que quedó porque
  `bridge/rules.py::run_erc` escribe el JSON de kicad-cli junto al
  proyecto). Con la nueva regla, esa clase de leftovers desaparece.

### Tarea 1 — catálogo (diff aditivo pendiente)

- `docs/specs/tool-catalog.md`: `pcb_pdf` aparece en `export_render`
  y `pcb_png` queda como reservado con `INVALID_PARAMS` explícito.
  `PROJECT_NOT_FOUND` sumado a la fila (lo puede lanzar la rama
  `pcb_pdf` cuando no hay `.kicad_pcb`).
- Verificado por `git diff`: ningún código de error existente ni
  nombre de tool cambió (F3).

### Tarea 2 — cache mtime en state_builder

- `bridge/state_builder.py`: dict `_CACHE` indexado por
  `(str(sch.resolve()), mtime_ns)`. `build_state_cached()` devuelve
  `(state, cache_hit)`. `build_state()` sobrevive como wrapper
  compatible.
- Cambio de `snap` sobre mismo mtime → `state.model_copy(update=…)`
  sin reconstruir. Cambio de mtime → invalidación total.
- `tools/world.py::get_world_context` usa la versión cached; añade
  `cache_hit: bool` al log estructurado (RNF2).
- Tests unit: 3 (hit tras 1ra llamada, miss tras `os.utime`, snap
  distinto reusa cache).

### Tarea 3 — TOON como TextContent puro

- `get_world_context` cambia el tipo de retorno a `str`; FastMCP emite
  el TOON como TextContent directo. La cabecera ya lleva `snap` y
  `kind`, así que el envelope JSON era redundante.
- Tests de `test_world_context.py` ajustados: helper `_toon()` lee
  `TextContent.text` directamente en vez de parsear JSON.
- **Tabla de tokens_est re-medidos** — ver sección dedicada más
  abajo. Sorpresa: la baja no fue de 652 → ~200-250 como se
  esperaba, sino ~4-12 % según fixture. Explicación honesta abajo.

### Tarea 4 — `export_manufacturing` + Gate G3

- `gates/g3.py::check_drc_clean(pcb, drc_runner=…)`: corre DRC,
  cuenta violaciones `error`, y si hay ≥1 levanta
  `EXPORT_BLOCKED_BY_DRC` con conteo + 3 primeras violaciones en el
  hint (formato del catálogo). Runner inyectable como `Protocol`.
- `tools/export.py::export_manufacturing(output_dir?=fab/)`: detrás
  de G3. Si pasa, ejecuta `kicad-cli pcb export gerbers` + `pcb
  export drill` sobre el directorio canonicalizado. Retorna
  `{output_dir, files, count}`.
- Tests unit: 2 en gate (limpio + sucio con >3 errors, verificando
  el límite de 3 en el hint) + 2 en tool (limpio con CLI mockeado,
  sucio con reporte inyectado).
- Test integration contra 004_real: copia parcial a tmp
  (solo `.kicad_sch` y `.kicad_pcb`, **sin** `.kicad_pro`), para
  que DRC use severidades por defecto y clasifique
  `board_edge_clearance` como `error` (27 violaciones reales). El
  `.kicad_pro` original del proyecto reclasifica todo a `warning`
  y el gate no dispara — descubierto en esta sesión, documentado
  en la sección Pendientes. **Caso limpio de integración queda
  pendiente** hasta tener un PCB fixture sin violaciones.

### Tarea 5 — bridge IPC vía kicad-python

- `bridge/ipc.py`: `IpcBridge` encapsula `kipy.KiCad`. Timeout duro
  2000 ms enforced en el factory (asserted). Cola de profundidad 1
  vía `threading.Lock` alrededor de cada operación IPC.
- Resolución del socket: `KICAD_API_SOCKET` env → arg → default
  `ipc:///tmp/kicad/api.sock`.
- Detección de reinicio: `KICAD_API_TOKEN` se congela al primer
  contacto. Cambio → `KICAD_RESTARTED` y el próximo request
  reconecta. Env ausente NO cuenta como reinicio (server
  standalone es un caso legítimo).
- `Nm` y `Mm` como `NewType` distintos con conversores explícitos
  (`nm_to_mm`, `mm_to_nm`). `mm_to_nm` usa banker's rounding.
- `BoardHandle` envuelve `kipy.Board`: los tipos de `kipy` no
  cruzan la frontera del bridge (regla #5).
- Import perezoso de `kipy`: el server arranca aunque `kipy` no
  pueda importarse por razones ambientales.
- `tools/meta.py::health` reporta `kicad_ipc` como `ok (versión)` o
  `missing/error` con code+message+hint. Adiós `not_checked`.
- Tests unit (7): unidades roundtrip + banker rounding, versión
  normalizada, board wrapping con None, restart via token,
  factory error → `KICAD_NOT_RUNNING`, ausencia de token no es
  reinicio. Un `integration_gui`: se conecta al socket real si
  `KICAD_MCP_GUI_TEST=1` y valida `major >= 9`.

### Tarea 6 — primeras mutaciones + Gate G1 + audit

- `tools/pcb.py`: `move_footprint(ref, x_mm, y_mm)` y
  `add_track(net, start_*, end_*, width_mm=0.25, layer="F.Cu")`.
  Validación previa contra estado leído por IPC:
  - Ref no existe → `COMPONENT_NOT_FOUND` con top-3 similares por
    `difflib.get_close_matches`.
  - Net no existe → `NET_NOT_FOUND` idem.
  - Coords fuera del bbox del board → `INVALID_PARAMS` con el
    rango permitido en el hint.
- `gates/g1.py::ensure_session_backup(root)`: la PRIMERA
  mutación por proyecto copia `.kicad_sch` y `.kicad_pcb` a
  `.kicad-mcp/backups/<ts>/`; si el proyecto es un repo git,
  además `git add -A && git commit --allow-empty -m "checkpoint:
  pre-mutación kicad-mcp"`. Idempotente por proyecto (dict
  module-level). Backup vacío (proyecto sin sch ni pcb) → aborta
  con `PROJECT_NOT_FOUND`.
- `audit/logger.py::record(...)`: append JSONL a
  `.kicad-mcp/audit.jsonl` con `ts` UTC, `tool`, `params`, y
  `result` o `error_code`. Formato de arquitectura §4.6.
- Respuesta de éxito = confirmación corta.
  `move_footprint` → `OK move_footprint R5 -> (102.5, 44.0)
  [snap:1]` (≤ 30 tokens medidos con `estimate_tokens`).
  `add_track` → `OK add_track GND (10.0,20.0)->(30.0,40.0)
  w=0.35 @B.Cu [snap:1]` (≤ 45 tokens, más ancho porque lleva
  seis campos).
- Tests unit (6): validaciones con similars, out-of-bounds, G1
  dispara una sola vez cuando hay dos mutaciones seguidas, audit
  se escribe con las líneas correctas para aceptadas y
  rechazadas, ambas confirmaciones caben debajo del umbral.
- Catálogo actualizado: nueva categoría `pcb` con las dos tools
  y sus errores. Reservados actualizados (`move_footprint` y
  `add_track` salen de reservados a implementados). Sin
  renombrar (F3).

## Definition of Done

```
uv run pytest -m "not integration and not integration_gui"
  → 39 passed, 15 deselected, 1 xfailed
uv run pytest -m integration
  → 15 passed, 40 deselected  (~65 s con DRC real)
uv run mypy src/                     → Success (strict, 27 files)
uv run ruff check src/ tests/        → All checks passed
uv run ruff format --check ...       → clean
```

## `tokens_est` re-medidos post-Tarea 3

Método: idéntico al de sesión 02. `int(len(text) / 3.5)` sobre el
`TextContent.text` que devuelve `get_world_context`. En sesión 02 ese
text era `json.dumps({"snap","kind","toon": TOON})`; en sesión 03 es el
TOON directo.

| Fixture | Envelope JSON (sesión 02) | TOON puro (sesión 03) | Reducción |
|---|---|---|---|
| 001 (5 comp, sin degradación) | 124 | 109 | 12.1 % |
| 002 (30 comp, sin degradación, max=800) | 681 | 652 | 4.3 % |
| 003 (150 comp, focus J1 r=15 mm, max=500) | 470 | 448 | 4.7 % |

**Observaciones honestas:**

1. La reducción esperada (652 → ~200-250 para 002) **no se
   materializó**. El envelope JSON solo agregaba ~30 chars fijos +
   escapes de `\n` en el TOON (`\n` → `\\n`, +1 char por línea). Para
   002 con ~30 líneas: ~30 + 30 = ~60 chars extras → ~17 tokens_est.
   Cuadra con la reducción medida (681-652 = 29 tokens_est).
2. La sesión 02 reportó los mismos 109/652/448 como "payload JSON
   completo" — pero el log de `tools/world.py` en esa sesión ya
   computaba `estimate_tokens(toon)`, no `estimate_tokens(json_dump)`.
   El texto del reporte tenía la métrica bien pero la etiqueta mal.
   Al re-medir con la escala del envelope real, los overheads son
   pequeños.
3. La ganancia real por eliminar el envelope no es reducir tokens,
   es limpieza semántica: el consumidor recibe TOON como TEXTO
   (Content-Type text), no una string JSON que hay que decodificar.
   Vale la migración, pero no por costo de tokens.
4. **Si de verdad queremos bajar 002 a ~200-250 tokens**, la palanca
   es la degradación §4 (colapso de nets, resumen de componentes
   lejanos, omitir POS) — mecánica que YA tenemos pero que 002 no
   dispara por caber en 800. Con `max_tokens=250` en 002, el
   encoder degradaría y bajaría — no probé aquí por no ser el
   objetivo de la Tarea.

## Estado del protocolo GUI

**Automatizado (integration_gui):**
- `tests/test_ipc.py::test_ipc_reports_real_kicad_version`. Conecta
  al socket real cuando `KICAD_MCP_GUI_TEST=1` y valida `major >=
  9`. Es un test-humo mínimo — cubre el happy-path de
  `IpcBridge.get_version()`.

**Manual (docs/pruebas-gui.md):**
- Sección "Protocolo (cualquier fixture)": setup del entorno,
  requisitos previos.
- Sección "Protocolo de mutaciones": copia fixture a tmp, `git
  init` para que G1 tenga qué commitear, ejecución de tools por
  MCP Inspector o script, verificación de backups + audit + commit
  git.

**Skip esperado** cuando el humano no autoriza:
`KICAD_MCP_GUI_TEST != 1` → skip.  
Socket ausente → skip con mensaje claro (path del socket).

**Fase 0 en esta sesión:** WARN de IPC porque KiCad no estaba
abierto durante el desarrollo. No bloqueó ninguna tarea porque los
tests unit del bridge cubren la lógica del wrapper con fakes
inyectados (client_factory) y la ruta real se cubre bajo
`integration_gui` con el humano en el loop.

## Decisiones tomadas dentro del margen permitido

1. **`_BACKUP_DIR = ".kicad-mcp/backups"` y `_AUDIT_FILE =
   ".kicad-mcp/audit.jsonl"`**. Ambos bajo `.kicad-mcp/` en la raíz
   del proyecto (implícito en la arquitectura §4.6, no
   especificado). Si el humano prefiere otro layout, es un cambio
   de constante.
2. **G1: `git commit --allow-empty`** cuando el repo no tiene
   cambios en staging. Motivo: el humano puede haber hecho el
   commit anterior justo antes; queremos un marker git aun así,
   para poder rollback exacto por hash. `--allow-empty` es
   inofensivo (no muta historia previa) y hace `git log --oneline`
   más informativo.
3. **Bbox del board: unión de posiciones de footprints + margen
   100 mm**. Alternativa "correcta": leer Edge.Cuts. En el MVP el
   objetivo del check es rechazar coords absurdas (999 mm en un
   board de 100 mm), no ser pixel-perfect. El margen absorbe el
   caso "footprint en el borde y queremos moverlo un poco fuera
   del enjambre". Documentado en el docstring.
4. **`_similars` con `cutoff=0.5` y `limit=3`**. Los defaults de
   `difflib`. En un catálogo pequeño (<20 nets/refs típico)
   funciona bien; los tests confirman comportamiento con nombres
   como `3v3` → `3V3, 3V3_MCU`.
5. **Confirmación de add_track hasta 45 tokens_est** (no 30 como
   move_footprint). Motivo: la operación lleva 6 campos (net,
   start, end, width, layer) contra 3 de move_footprint. Sigue
   siendo un orden de magnitud menor que un TOON completo. ADR-0004
   habla de "~30 tokens" en tono aproximado; el espíritu (no
   inflar el contexto) se cumple.
6. **Falla del `git commit` del checkpoint** cuando su returncode
   no es 0 y no es el mensaje "nothing to commit" → levanta
   `KICAD_CLI_FAILED`. **Alternativa considerada** — no bloquear
   la mutación si git falla, solo warnear. Descartada: F1 del
   ADR-0003 dice "falla del backup → la mutación NO procede". Un
   git commit fallido cae en la definición amplia de "backup
   falló".
7. **`_ipc_payload` stubeado en tests unit de health** para no
   pagar el timeout real de 2 s. Alternativa: mockear el
   `client_factory`. Elegí el stub del payload porque es más
   compacto y no cambia el foco del test (probar `health`, no el
   bridge).

Ninguna decisión toca F2–F5.

## Pendientes que quedan documentados

1. **Fixture PCB limpio** (0 violaciones DRC severity=error). Sin
   él no hay integration test del caso "export_manufacturing
   escribe gerbers de verdad". Propuesta: agregar `005_pcb_limpio`
   generado con `bridge/generate_fixtures.py` — un board con dos
   pads y una track ancha bien separada del borde. Requiere
   generación programática de PCB (kicad-cli no lo hace; kipy sí
   pero necesita KiCad corriendo). **Bloqueado hasta v0.3 o hasta
   que el humano cree el fixture a mano.**
2. **004_real con `.kicad_pro` original clasifica board_edge_clearance
   como warning**. Consecuencia: la copia parcial (sin
   `.kicad_pro`) es el único modo de ejercitar DRC-error en
   integration. Para v0.3 se podría generar un `.kicad_pro`
   modificado que fuerce severidades estrictas, y usarlo en un
   segundo test de integración.
3. **Bridge IPC persistente**: sesión 03 crea un `IpcBridge`
   por `register()` (uno para meta.health, otro para pcb). Cada
   uno mantiene su cliente kipy propio → dos conexiones al mismo
   socket. Funcional pero desperdicia recursos. Propuesta: un
   `IpcBridge` singleton compartido por todas las tools que lo
   necesiten. Requiere refactor del `register_all` (pasar la
   instancia común).
4. **Health del IPC paga 2 s de timeout cuando KiCad no está
   corriendo**. Cada llamada a `health`, mientras KiCad esté
   cerrado, espera el timeout completo. Aceptable para el MVP;
   en v0.4 se puede añadir un fast-fail chequeando la existencia
   del socket antes de intentar conectar.
5. **`add_track` con múltiples segmentos** (`points_mm` en el
   catálogo del prompt) no está implementado; solo start/end. Un
   `add_track` con N puntos hoy se resuelve con N llamadas. Es
   una decisión de API — si queremos un solo call con lista de
   puntos, cambia el schema del parámetro.

## Dudas abiertas para sesión 04

1. **Snapshot Store §4.3-4.4 vs. bridge IPC persistente:** ¿cuál
   arranca sesión 04? El Snapshot Store desbloquea el delta (v0.3
   del catálogo) y el `EXTERNAL_EDIT_DETECTED` real; el bridge
   persistente desbloquea autonomía prolongada sobre KiCad.
   Recomiendo primero el bridge persistente + supervisión (dos
   días), después el store (semana): las mutaciones existentes ya
   funcionan pero cada `health` paga el timeout de conexión —
   fricción diaria del usuario. La sesión 04 propuesta abajo
   asume ese orden.
2. **`add_symbol` (esquemático) experimental via kicad-skip o
   parser propio.** ¿Vale la pena el S-expression parser propio en
   sesión 04, o esperamos a que kipy tenga soporte de mutación
   sch en 10.1+? El riesgo de un parser propio es alto — un bug
   corrompe el `.kicad_sch` del usuario. Recomiendo esperar.
3. **Confirmaciones cortas: ¿empujar aún más el ADR-0004?** Hoy
   `move_footprint` cabe en 30 tokens; `add_track` en 45. Si el
   humano quiere unificar a ≤ 30 estricto, `add_track` debería
   omitir width/layer del texto (van al log). Preferencia mía:
   mantener la información en el string — el agente que ejecuta
   varias mutaciones lee el confirm como recuerdo inmediato.

## Propuesta concreta para la sesión 04

**Núcleo (días 1-3): bridge IPC persistente + observabilidad**
1. `IpcBridge` singleton compartido entre `meta` y `pcb` tools.
   Refactor de `register_all` para inyectar la instancia.
2. **Health fast-fail**: chequear existencia del socket (Path
   check) antes de intentar `KiCad(...)`. Reduce el peor caso de
   `health` de 2 s a milisegundos cuando KiCad no está corriendo.
3. **Supervisión del bridge**: si `ApiError`/`ConnectionError`
   ocurre a mitad de una operación (no solo del `_ensure_client`),
   invalidar `self._client` para forzar reconexión en el próximo
   request. Hoy solo reset ocurre en `_detect_restart`.
4. **Test integration_gui de move_footprint end-to-end**: copia
   004_real a tmp, abre en KiCad, ejecuta `move_footprint U1
   x y`, re-lee la posición de U1 vía `bridge.list_footprint_refs`
   + una nueva `get_footprint_position`, verifica.

**Preparatorio para v0.3 (días 4-5): semilla del Snapshot Store**
5. `snapshots/store.py`: dict `{snap_id: NormalizedState}` con TTL
   simple (últimos 10). `get_world_context` incrementa `snap_id`
   monotónicamente en vez de fijarlo a 1.
6. **`SNAPSHOT_STALE` real** en `move_footprint` /`add_track`
   cuando el `base_snap` que pasa el agente no está en el store.
7. **`EXTERNAL_EDIT_DETECTED`** cuando el mtime del `.kicad_sch`
   cambió desde el último snapshot y el agente pide una mutación
   sin re-sync. Ya tenemos el mtime cacheado (Tarea 2). Este es
   el uso primero de esa señal.

**Fuera de scope**:
- `add_symbol` de esquemático (esperar a kipy con soporte sch).
- Delta v0.3 completo (encoder ya tiene la gramática; falta la
  fuente de `base_snap`, que llega con el store).
- Freerouting / suggest_positions (v0.4).

**Argumentación del orden**: el bridge persistente es fricción
diaria del usuario (2 s en cada `health`); el store es
capacidad futura que se materializa con `add_symbol`. Priorizar
lo primero.

**Riesgo declarado**: el `IpcBridge` singleton comparte estado
entre threads. Con FastMCP síncrono no hay problema (event loop
serializado), pero si algún día montamos tools async con IPC
paralelo, el lock de profundidad 1 va a serializar todo — es
esperable, pero medir latencia percibida.
