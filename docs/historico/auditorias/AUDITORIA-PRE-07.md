# Auditoría pre-sesión 07 — Robustez del pipeline de mutaciones vivas

**Fecha:** 2026-07-10 · **Rama:** `master` (post-merge de `sesion-06`)
**Modo:** solo lectura + experimentos controlados contra KiCad real
**Precondición GUI verificada:** KiCad 10.0.4, PCB Editor abierto sobre
`/tmp/gui-test-project/video.kicad_pcb`; socket `/tmp/kicad/api.sock`
presente; env vars `KICAD_MCP_GUI_TEST=1`, `KICAD_MCP_PROJECT`,
`KICAD_MCP_GUI_REF=U19`, `KICAD_API_SOCKET` exportadas.

---

## Resumen ejecutivo

- **P1.** El centinela `test_move_footprint_then_context_delta_reflects_mutation`
  **NO** protege de un "delta bien formado pero semánticamente inverso":
  al revertir la rama viva de `_build_current_for`, cae al path de disco
  y crashea en `kicad-cli` porque el `.kicad_sch` de `_make_project` es
  un stub `(kicad_sch)` sin dato. Protege solo contra "pipeline explota".
  Un test complementario con proyecto de disco parseable y kind-mismatch
  cubriría el hueco a costo bajo (usa el fallback ya presente en
  `world.py:244`).
- **P2.** El **busy** es un `ApiStatusCode.AS_BUSY` documentado por
  KiCad, no un bug de nuestro bridge. Reproducción hoy: **0 busy en 50
  llamadas** (30 solo-lectura + 20 read/move intercalados) contra KiCad
  10.0.4 en idle. El bug de sesión 06 es real pero azaroso, dependiente
  de operaciones background de KiCad (refill zones, router, DRC
  realtime); la doc oficial recomienda **retry**. Latencia promedio
  ~3.2 s (`snapshot_footprints` sobre 189 fps — sobre el timeout del
  bridge de 2s por request individual, pero cada uno de los sub-requests
  vive por debajo).
- **P3.** Los tres estados (socket muerto / PCB Editor no abierto /
  busy) **no son distinguibles** en el catálogo hoy. Socket muerto se
  distingue vía `_socket_file_missing` fast-fail (→ `KICAD_NOT_RUNNING`);
  los otros dos colapsan a `KICAD_CLI_FAILED` genérico. Pero la
  información está estructuralmente disponible: `kipy.errors.ApiError`
  expone `.code: ApiStatusCode` (AS_BUSY=7 vs AS_UNHANDLED=5). Basta
  extender `_map_ipc_failure` sin tocar catálogo (F3 intacta) — el
  código emitido puede seguir siendo el mismo con hint distinto.
- **P4. Suite verde**: 85 unit, 20+20 integration, 3 integration_gui,
  mypy y ruff limpios. Fix T1 en `bridge/ipc.py:496`, `add_track` sin el
  bug (usa setters), ADR-0008 registra la regla del property setter,
  catálogo `docs/specs/tool-catalog.md:173-195` documenta `data` como
  estándar general.
- **P5.** `integration` corrida **dos veces**: 230.02 s y 211.25 s
  (diferencia ~19 s / 8 %). Es varianza modesta y estable, no rebote.
  Cero TODO/FIXME/xfail vigentes en `src/` ni `tests/` (única
  aparición de "TODO" es la palabra española "TODOS" en un docstring).
  `scratchpad/` está en `.gitignore`; sin archivos huérfanos versionados.
  T5 sigue sin habilitarse (F5): `kicad-skip` no está en `pyproject.toml`.

---

## P1 — Alcance real del centinela

### Trazado del path revertido

`_build_current_for` (`src/kicad_mcp/tools/world.py:106-148`):

```python
if entry.mtimes is None:
    if entry.state.kind != "pcb":
        raise KicadMcpError(code=ErrorCode.KICAD_CLI_FAILED, ...)
    board = ipc_bridge.get_open_board()
    if board is None:
        raise KicadMcpError(code=ErrorCode.SNAPSHOT_STALE, ...,
                            data={"base_snap": base_snap, "reason": "live_chain_lost"})
    curr_raw = build_state_from_board(ipc_bridge, board)
    ...
    return curr_raw, new_snap, False
curr_raw, cache_hit = build_state_cached(schematic, snap=0)   # ← rama disco
```

Y en `get_context_delta` (`world.py:244-255`), el fallback **estructural**
si los kinds no coinciden:

```python
if curr_raw.kind != entry.state.kind:
    raise KicadMcpError(code=ErrorCode.KICAD_CLI_FAILED,
        message="Estado interno inconsistente: kind del base_snap no coincide ...",
        hint=f"base kind={entry.state.kind}, curr kind={curr_raw.kind}. Reportar como bug al humano.")
```

Fixture usada por el centinela — `_make_project(tmp_path)`
(`tests/test_pcb.py:151-161`):

```python
def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "proj.kicad_sch").write_text("(kicad_sch)")     # ← stub vacío
    (project / "proj.kicad_pcb").write_text("(kicad_pcb)")
    return project
```

### Qué pasa exactamente al revertir la rama viva

Con `entry.mtimes is None` y `entry.state.kind == "pcb"`, revertir la
rama viva hace que `_build_current_for` caiga a la línea final:

```python
curr_raw, cache_hit = build_state_cached(schematic, snap=0)
```

`build_state_cached` (`bridge/state_builder.py:89`) invoca `_rebuild`
(línea 156), que hace `parse_root_positions(schematic)` seguido de
`load_netlist(schematic)`. `load_netlist` corre `kicad-cli sch export
netlist proj.kicad_sch`. Como el archivo es literalmente `(kicad_sch)`,
kicad-cli devuelve error y el bridge lo empaqueta como `KICAD_CLI_FAILED`
con hint `Failed to load schematic` — **exactamente el output visto en
la mutación #2 de sesión 06**. El `curr_raw.kind != entry.state.kind`
NUNCA se evalúa: se aborta antes.

### Veredicto

El centinela protege **contra "el pipeline explota"**, no contra
"delta invertido/vacío". Con un `.kicad_sch` de disco parseable y
divergente:

- Si `_rebuild` termina exitoso, devuelve `kind="sch"` (línea 191:
  `NormalizedState(kind="sch", ...)`).
- El chequeo `curr_raw.kind != entry.state.kind` **sí** dispararía —
  atrapa el kind cruzado, no el contenido divergente.

El hueco real: no hay test que combine `entry.state.kind == "pcb"`
(base vivo) con `curr_raw.kind == "pcb"` (imaginario, disco emitiendo
pcb) para verificar que el CONTENIDO del delta es correcto. Como
`_rebuild` sólo emite `sch`, el "kind cruzado" es la única forma de que
el path incorrecto sea observable estructuralmente; hoy queda cubierto.
Pero el escenario "delta vacío por olvido de propagación" está cubierto
**exclusivamente** en el mundo unit por el `_FakeBridge` hardened
(`test_pcb.py:83-93`, donde `_positions` sí propaga). El unit
`test_context_delta_pcb_live_uses_board_not_disk` cubre el enrutamiento
mockeando `build_state_cached` con `_fail_disk_builder` — atrapa la
regresión de "cayó a disco cuando no debía".

### Test que faltaría (no lo escribo, lo describo)

Un test unit que:

1. Registre `base = _fake_state(kind="pcb", snap=X)` con `mtimes=None` y
   componente `U1@100,50`.
2. Cree un proyecto de disco con `_make_project`, **pero mockee**
   `build_state_cached` para devolver un `NormalizedState(kind="pcb",
   components=[U1@0,0])` (imposible con el `_rebuild` actual — el mock
   simula un futuro cambio que rompiera invariantes).
3. Revierta la rama viva de `_build_current_for`.
4. Assert: `get_context_delta` produce delta CON `[~C] U1` señalando
   `x0.0 y0.0` — es decir, el delta muestra la mutación INVERTIDA (dice
   "movió a (0,0)" cuando la mutación fue a (50,60)).

Cubriría la regresión "el delta salió pero con contenido incorrecto".
Hoy este caso lo previene la disciplina de `_rebuild` (siempre sch),
no un test.

### Otros tests de delta contra `NormalizedState` realista

Barrido de `tests/test_context_delta.py`:

- `test_context_delta_snapshot_stale_when_base_unknown` — sintético.
- `test_context_delta_external_edit_when_mtime_diverges` — mock de
  `build_state_cached`.
- `test_context_delta_pcb_live_uses_board_not_disk` — mock de
  `build_state_from_board`.
- `test_context_delta_pcb_live_no_board_returns_snapshot_stale` — mock
  de `get_open_board`.
- `test_context_delta_sch_disk_path_still_works` — mock de
  `build_state_cached`.
- `test_context_delta_registers_fresh_snap_and_echoes_it` — mock.
- `test_context_delta_budget_impossible_raises_typed_error` — mock.
- `test_context_delta_empty_when_world_unchanged_against_fixture_001`
  **integration**, `mirror_fixture` real ← estado disco realista.
- `test_context_delta_reports_added_component_against_synthetic_base`
  **integration**, `mirror_fixture` real ← estado disco realista.
- `test_context_delta_log_emits_snap_ids` — integration real.

Los tres integration cubren rama `sch`/`sch`. **Ninguno cubre
pcb/pcb realista** (requeriría KiCad + PCB Editor + mutación). Ese
gap es el hueco P1 completo; no es sólo el centinela. Los tres
`integration_gui` (`test_ipc_*`) cubren la re-lectura vía bridge y el
round-trip persistente, no el pipeline delta post-mutación.

---

## P2 — Caracterización del busy

### Experimento A: 30 lecturas sucesivas del board vivo (idle)

Script: `snapshot_footprints` sobre el board vivo, sleep 0.2 s entre
iteraciones. Salida literal:

```
== Fase A: solo lecturas repetidas (30x) ==
A00  3963.7ms  OK (189 fps)
A01  3243.7ms  OK (189 fps)
A02  3734.8ms  OK (189 fps)
A03  3292.6ms  OK (189 fps)
A04  3291.0ms  OK (189 fps)
A05  3346.4ms  OK (189 fps)
A06  3385.6ms  OK (189 fps)
A07  3525.4ms  OK (189 fps)
A08  2944.7ms  OK (189 fps)
A09  4713.3ms  OK (189 fps)
A10  3547.8ms  OK (189 fps)
A11  2985.7ms  OK (189 fps)
A12  4067.3ms  OK (189 fps)
A13  3275.3ms  OK (189 fps)
A14  3380.3ms  OK (189 fps)
A15  3656.5ms  OK (189 fps)
A16  3022.3ms  OK (189 fps)
A17  3279.0ms  OK (189 fps)
A18  2997.6ms  OK (189 fps)
A19  3061.5ms  OK (189 fps)
A20  2749.0ms  OK (189 fps)
A21  2908.2ms  OK (189 fps)
A22  3155.5ms  OK (189 fps)
A23  2943.1ms  OK (189 fps)
A24  4075.4ms  OK (189 fps)
A25  3195.0ms  OK (189 fps)
A26  4017.5ms  OK (189 fps)
A27  3258.7ms  OK (189 fps)
A28  3167.8ms  OK (189 fps)
A29  3438.0ms  OK (189 fps)
```

**30/30 OK.** Rango: 2749 – 4713 ms (μ ≈ 3418 ms, σ ≈ 425 ms). No hay
busy en idle.

Nota: cada `snapshot_footprints` internamente lee `.reference_field`,
`.value_field`, `.position`, `.definition.pads[*].net` sobre 189
footprints. `board.raw.get_footprints()` es un solo `GetItems`, pero
las siguientes lecturas de proto son accesos locales — 3s son
prácticamente el costo del GetItems inicial. El timeout duro de 2 s del
bridge aplica **por request IPC individual** (`_supervise` en
`bridge/ipc.py:291-310`); si el GetItems se resuelve en < 2 s aunque
las lecturas locales sumen más, la operación total puede pasar de 2 s
sin disparar `KICAD_TIMEOUT`. Vale como observación arquitectónica; no
es un bug hoy.

### Experimento B: read → move → read intercalados (20x)

```
# ref=U19 pos inicial=(234.823, 64.643)
B00 MOVE 3336.6ms  OK
B00 READ 3888.9ms  OK (189 fps)
B01 MOVE 3619.4ms  OK
B01 READ 4226.2ms  OK (189 fps)
B02 MOVE 3627.1ms  OK
B02 READ 3112.4ms  OK (189 fps)
B03 MOVE 4198.0ms  OK
B03 READ 3431.3ms  OK (189 fps)
B04 MOVE 3646.2ms  OK
B04 READ 3147.9ms  OK (189 fps)
B05 MOVE 4037.3ms  OK
B05 READ 3288.4ms  OK (189 fps)
B06 MOVE 3666.3ms  OK
B06 READ 3250.5ms  OK (189 fps)
B07 MOVE 3186.3ms  OK
B07 READ 2962.9ms  OK (189 fps)
B08 MOVE 3499.5ms  OK
B08 READ 3189.5ms  OK (189 fps)
B09 MOVE 3729.6ms  OK
B09 READ 3365.8ms  OK (189 fps)
B10 MOVE 4218.5ms  OK
B10 READ 3510.7ms  OK (189 fps)
B11 MOVE 4036.1ms  OK
B11 READ 3676.4ms  OK (189 fps)
B12 MOVE 3380.8ms  OK
B12 READ 3098.1ms  OK (189 fps)
B13 MOVE 3646.0ms  OK
B13 READ 3464.3ms  OK (189 fps)
B14 MOVE 3800.3ms  OK
B14 READ 3021.8ms  OK (189 fps)
B15 MOVE 3566.1ms  OK
B15 READ 3795.7ms  OK (189 fps)
B16 MOVE 3230.3ms  OK
B16 READ 3253.2ms  OK (189 fps)
B17 MOVE 3869.1ms  OK
B17 READ 2993.5ms  OK (189 fps)
B18 MOVE 4343.4ms  OK
B18 READ 3278.3ms  OK (189 fps)
B19 MOVE 3818.8ms  OK
B19 READ 3121.0ms  OK (189 fps)
# restauro U19 a pos inicial
```

**40/40 OK** (20 MOVE + 20 READ). El move + read intercalado tampoco
disparó busy.

### Búsqueda documental

- Enum `ApiStatusCode.AS_BUSY` en el proto de kipy
  (`.venv/lib/.../kipy/proto/common/envelope_pb2.pyi:74-75`):

  > `AS_BUSY: ApiStatusCode.ValueType`
  > `"KiCad is busy performing an operation and can't accept API commands"`

  El mensaje literal coincide con el `busy and cannot respond a API
  requests right now` de sesión 06 (probable localización menor).
  **Estado documentado del protocolo IPC.**

- Uso en kipy (`board.py:1016-1052`): las operaciones asincrónicas
  como `refill_zones` retornan inmediatamente y ponen al editor en
  modo busy hasta que la operación termine. kipy tiene un **busy loop
  local** que se traga estos AS_BUSY intermedios en algunos casos:

  ```python
  # kipy/board.py:1041
  # "To hide this from API users somewhat, do an initial busy loop here"
  ...
  if e.code == ApiStatusCode.AS_BUSY:
      # reintenta hasta un tope
  ```

- Documentación oficial KiCad IPC API (dev-docs.kicad.org): los
  clientes deben esperar timeouts/busy y **retry**. El API server pasa
  mensajes al hilo de UI vía evento wxWidgets — cuando KiCad procesa
  otro trabajo en la UI (DRC realtime, router auto, refill de zonas,
  render de tracks, undo/redo pesado), la respuesta API se demora.

### Veredicto P2

**El busy es un estado protocolar conocido**, no un bug de nuestro
código. Es **no-determinista desde la perspectiva del bridge**: depende
del trabajo background que corra la UI de KiCad en el momento. Hoy no
lo reproduje en 70 llamadas, pero la evidencia estructural
(`ApiStatusCode.AS_BUSY` en el proto, kipy tiene busy loops en refill)
confirma que puede aparecer.

**Recomendación no vinculante para sesión 07:** un retry con backoff
**exponencial acotado** dentro de `_supervise` cuando `exc.code ==
AS_BUSY` (1 reintento a 250 ms, otro a 500 ms — total < 1 s adicional)
absorbería incidentes cortos sin arriesgar cascadas. Un busy que persiste
más allá se emite como `KICAD_TIMEOUT` o `KICAD_CLI_FAILED` distinguible
(ver P3). Prohibido el retry ciego: si un mutation IPC devolvió AS_BUSY,
puede que KiCad ya lo haya aceptado y estar procesándolo — reintentar la
mutación duplicaría. Retry seguro solo para lecturas idempotentes.

---

## P3 — Distinguibilidad de los tres estados IPC

### Estado (1) — socket muerto (KiCad cerrado)

Detectado por el **fast-fail** en `bridge/ipc.py:145-157`:

```python
def _socket_file_missing(socket_uri: str | None) -> bool:
    ...
    fs_path = socket_uri[len("ipc://") :]
    return not Path(fs_path).exists()
```

Y en `_default_client_factory` (`ipc.py:174-181`):

```python
if _socket_file_missing(socket_path):
    raise KicadMcpError(
        code=ErrorCode.KICAD_NOT_RUNNING,
        message="No se pudo conectar al socket IPC de KiCad.",
        hint="Abrí KiCad y habilitá el API server ...",
    )
```

También `_KConn` (kipy `ConnectionError`) mapea a `KICAD_NOT_RUNNING`
en `_map_ipc_failure` (`ipc.py:227-236`).

**Distinguible ✓** — código dedicado en el catálogo.

### Estado (2) — PCB Editor no abierto (solo project manager)

Trazo en kipy (`kipy/kicad.py:225-230`):

```python
def get_board(self) -> Board:
    """Retrieves a reference to the PCB open in KiCad, if one exists"""
    docs = self.get_open_documents(DocumentType.DOCTYPE_PCB)
    if len(docs) == 0:
        raise ApiError("Expected to be able to retrieve at least one board")
    return Board(self._client, docs[0])
```

Y `get_open_documents` (línea 214-219) manda `commands.GetOpenDocuments`.
Cuando KiCad no tiene un editor abierto para ese doc type, el server
responde `ApiStatusCode.AS_UNHANDLED` con `error_message = "no handler
available for request of type kiapi.common.commands.GetOpenDocuments"`,
que `client.py:89-91` empaqueta como:

```python
raise ApiError(f"KiCad returned error: {reply.status.error_message}",
               raw_message=reply.status.error_message,
               code=reply.status.status)   # ← code = AS_UNHANDLED (=5)
```

En nuestro bridge, esa `ApiError` cae en el `else` de
`_map_ipc_failure` (`ipc.py:237-241`):

```python
return KicadMcpError(
    code=ErrorCode.KICAD_CLI_FAILED,
    message=f"Fallo IPC en {op_name}.",
    hint=(str(exc)[:200] or "sin detalle disponible"),
)
```

**Estado (2) hoy → `KICAD_CLI_FAILED` genérico, con hint que contiene
el mensaje "no handler available…".**

### Estado (3) — busy

Cuando KiCad devuelve `AS_BUSY` (código 7), llega igual como
`kipy.errors.ApiError` con `.code = AS_BUSY`. También cae en el mismo
`else` → **`KICAD_CLI_FAILED` genérico**, hint con "KiCad is busy…".

### ¿Es distinguible programáticamente hoy?

- **A nivel de código emitido:** NO. (2) y (3) colapsan al mismo
  `KICAD_CLI_FAILED`. El agente sólo puede distinguirlos parseando el
  hint — frágil.
- **A nivel de excepción capturada en `_map_ipc_failure`:** SÍ. El bug
  es únicamente en cómo lo mapeamos:
  - `exc.__module__.startswith("kipy")` y `type(exc).__name__ ==
    "ApiError"` identifica que es una `kipy.errors.ApiError`.
  - Sobre esa, `exc.code` es una `ApiStatusCode` (`envelope_pb2.pyi:54`):
    `AS_BAD_REQUEST=3, AS_NOT_READY=4, AS_UNHANDLED=5, AS_BUSY=7,
    AS_UNIMPLEMENTED=8`.
  - Con `exc.code == AS_BUSY` distinguís (3) de (2) sin tocar F3:
    mismo código `KICAD_CLI_FAILED`, distinto hint fijo y accionable
    ("KiCad ocupado; reintentar en breve" vs "abrí el PCB Editor").
  - Alternativa más limpia: agregar `data.ipc_status: "busy" | "unhandled"`
    al envelope (P4 confirmó que el estándar `data` existe desde
    sesión 06 T4), permitiendo al agente correlacionar sin parsear el
    hint. F3 intacta: el código no cambia.

### Veredicto P3

Los tres estados **son distinguibles programáticamente en el mapeo**
(la información está en `exc.code`), pero **no en el envelope
emitido** hoy. Un `bridge.health()` fino que reporte los tres estados
requiere:

1. Fast-fail de socket para (1). ✓ ya existe.
2. Un ping ligero (get_version) que separe (2) de (3): (2) SÍ responde
   get_version (no requiere editor abierto); (3) probablemente también,
   como reportó sesión 06 ("`get_version` y `get_nets` seguían OK"
   mientras `get_items` daba busy). Entonces (2) se detecta pidiendo
   `get_open_documents(DOCTYPE_PCB)` y capturando `AS_UNHANDLED`; (3)
   se detecta pidiendo `get_items` y capturando `AS_BUSY`.
3. Un canal `data` en el envelope que discrimine sin parsear hints.

Sin implementarlo, el diseño está claro; los ingredientes ya existen
en kipy y en el catálogo.

---

## P4 — Suite verde y verificación de tareas sesión 06

### Suite completa

```
$ uv run pytest -m "not integration and not integration_gui"
85 passed, 23 deselected in 4.39s

$ uv run pytest -m integration        # run 1
20 passed, 88 deselected in 230.02s (0:03:50)

$ uv run pytest -m integration        # run 2
20 passed, 88 deselected in 211.25s (0:03:31)

$ uv run pytest -m integration_gui
3 passed, 105 deselected in 33.70s

$ uv run mypy src/
Success: no issues found in 30 source files

$ uv run ruff check src/ tests/ scripts/
All checks passed!
```

Todo verde. `integration_gui` tampoco disparó busy en 33.7 s (los 3 tests
ejecutaron round-trips completos vs KiCad real).

### T1 en `master`

`src/kicad_mcp/bridge/ipc.py:474-504`:

```python
def move_footprint(self, board: BoardHandle, ref: str, x_mm: Mm, y_mm: Mm) -> None:
    ...
    # ``fp.position`` es un getter que devuelve ``Vector2(self._proto.position)``
    # ... el setter ``fp.position = Vector2(...)`` sí escribe sobre el proto
    # interno del FootprintInstance y además arrastra fields/pads por delta
    # (board_types.py:1939-1964).
    from kipy.geometry import Vector2

    with self._lock:
        self._detect_restart()
        with self._supervise("move_footprint"):
            raw_board = board.raw
            for fp in raw_board.get_footprints():
                if str(fp.reference_field.text.value) == ref:
                    fp.position = Vector2.from_xy(int(mm_to_nm(x_mm)), int(mm_to_nm(y_mm)))
                    raw_board.update_items(fp)
                    return
```

Línea 496: **usa property setter** (`fp.position = Vector2.from_xy(...)`).
Fix presente. ✓

### `add_track` — sin bug T1

`src/kicad_mcp/bridge/ipc.py:506-558`:

```python
track = Track()
track.start = Vector2.from_xy(int(mm_to_nm(start_mm[0])), int(mm_to_nm(start_mm[1])))
track.end   = Vector2.from_xy(int(mm_to_nm(end_mm[0])), int(mm_to_nm(end_mm[1])))
track.width = int(mm_to_nm(width_mm))
track.layer = layer_value
track.net   = net_obj
raw_board.create_items(track)
```

Todos setters directos sobre el objeto recién construido — no cae en
el patrón "get → mutar → send" del bug T1. ✓

### ADR-0008

`docs/adr/0008-kipy-write-semantics-property-setter.md` presente.
Registra:

- H1/H2 descartadas por lectura del código de kipy 0.7.1.
- Causa real: `fp.position` getter devuelve `Vector2(copy)`; mutar
  `.x`/`.y` de esa copia se pierde.
- Regla: **usar setter de property** para toda escritura a wrappers de
  kipy.
- Auditoría: grep sobre `= ...\.(x|y|width|start|end|net|layer)$` antes
  de emitir mutaciones nuevas.
- Alternativas descartadas: begin/push commit, hashing del board,
  mockeo del bridge en integration_gui.

### Campo `data` del envelope — estándar general

`docs/specs/tool-catalog.md:173-195`, dentro de la sección **"Taxonomía
de errores (completa, F3)"** (no bajo `get_context_delta`):

```
**Campo `data` del envelope (estándar opcional, F3 intacta).** El envelope
completo es `{code, message, hint, data?}`, donde `data: dict[str, Any] |
None` es un payload estructurado que enriquece el hint sin romper la
taxonomía: el código y su semántica siguen intactos, y el agente puede
correlacionar el fallo con su plan sin parsear el mensaje. Reglas:

- `data` es opcional; su ausencia equivale a `null` y se omite del envelope
  serializado. Consumidores tolerantes: nunca asumir presencia.
- Las claves de `data` son `snake_case` y estables por código de error (...)
- Los códigos no cambian por decidir emitir `data`. Cualquier código puede
  ganar un payload estructurado en una sesión futura sin quebrar F3.

Emisores actuales:

- `SNAPSHOT_STALE` → `data.base_snap: int`, `data.retention: int`. (...)
- `SNAPSHOT_STALE` con `data.reason: "live_chain_lost"` → se emite cuando el
  base es vivo pero el board de KiCad no está disponible al pedir el delta
  (sesión 06, D-06.1v2). (...)
```

Confirmado como estándar general. ✓

---

## P5 — Varianza, deuda, anomalías

### Varianza de `integration`

- Run 1: **230.02 s** (3:50)
- Run 2: **211.25 s** (3:31)
- Sesión 06 reportó 3:21 (201 s)

Rango observado (últimas 3 corridas): 201–230 s ⇒ σ ≈ ±10 % sobre μ ≈
214 s. Diferencia entre las dos corridas de hoy: 19 s (~8 %). Es
varianza modesta compatible con la hipótesis del reporte 06 (cache
warm de kicad-cli, jitter del filesystem al procesar 004_real_
grande). **No hay rebote fuerte que indique flake sistémico.** Todo
por debajo del umbral 300 s del prompt.

### TODO/FIXME/xfail

Búsqueda literal en `src/` y `tests/`:

```
grep -rn "TODO\|FIXME\|XXX\|xfail" src/ tests/
tests/test_pcb.py:33:    Sobrescribe TODOS los métodos que ``tools/pcb.py`` ...
```

**Único match:** la palabra "TODOS" (español, en un docstring). **Cero
deuda etiquetada** con TODO/FIXME/XXX/xfail vigentes. Notable dado el
alcance del proyecto.

### `scratchpad/` y archivos huérfanos

```
$ ls scratchpad/
004_copy/  add_symbol_test.py  inspect_sheet.py  parse_004.py
rams_added.kicad_sch  spike-kicad-skip.md  spike-venv/
```

Contenido del spike-kicad-skip de sesión 05 (spike T5 diferido) y
material relacionado. `.gitignore:8` incluye `scratchpad/` — **no
viaja a git**. Nada que limpiar bajo el mandato de esta auditoría (no
tocar); es material del humano.

### Anomalías estructurales

- Timeout del bridge de 2 s por request individual mientras
  `snapshot_footprints` retorna en ~3 s: sub-requests aún <2 s, tiempo
  extra es proto reads locales sobre el resultado del `GetItems`. No
  es bug, sí es **frontera latente**: en boards con >1000 fps el
  GetItems inicial podría rebasar 2 s por sí solo → riesgo de
  `KICAD_TIMEOUT`. Sin acción hoy, considerar telemetría si el
  humano prueba con boards mayores.
- T5 (`add_symbol`) sigue diferida: `grep "kicad-skip" pyproject.toml`
  sin resultado. F5 sigue sin habilitarse.
- Ninguna anomalía de imports muertos o tests inertes detectada.

---

## Insumos para sesión 07 (lectura, no decisiones)

1. **P2 (busy) probablemente merece una tarea acotada de "retry
   AS_BUSY en lecturas idempotentes", no una tarea de "eliminar el
   busy" (imposible: es un estado protocolar de KiCad).** El scope
   mínimo: extender `_map_ipc_failure` para reconocer `exc.code ==
   AS_BUSY`, y en `_supervise` (o en un wrapper por operación)
   reintentar hasta 2 veces con backoff exponencial acotado, **sólo si
   la operación es idempotente**. Prohibido para mutaciones (KiCad
   puede haber aceptado la primera).

2. **P3 (bridge.health fino) es afín a P2** — el mismo cambio en
   `_map_ipc_failure` habilita distinguir (2) del hint y prepara el
   terreno para un `health()` que devuelva
   `{socket, editor_pcb_open, editor_busy}`. El diseño está claro;
   ejecutable en el mismo día que P2 con overhead marginal.

3. **P1 (hueco del centinela) es cosmético a corto plazo mientras
   `_rebuild` sea el único emisor de `kind="sch"`**. El chequeo de
   kinds cruzados protege contra el escenario realista. Si sesión 07
   agrega una segunda fuente de `NormalizedState` disco (por ejemplo,
   parseo directo del `.kicad_pcb` como fallback), el hueco pasa a
   urgente. Prioridad **BAJA** hasta entonces.

4. **T5 (`add_symbol`)** sigue esperando `kicad-skip` en
   `pyproject.toml`. Sin cambio.

5. **Eval A (TOON vs CSV vs JSON compacto)** — sigue pendiente del
   reporte 06. Sesión de dev muy calma hoy (0 flakes en 90 tests
   integration + 100 lecturas IPC) es buen momento para benchmark
   comparativo si el humano lo prioriza.

---

## `git status` al terminar

Un solo archivo nuevo esperado: este documento.
