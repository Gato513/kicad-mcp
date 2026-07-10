# Sesión 07 — Resiliencia IPC: busy, estados distinguibles, health fino

**Rama:** `sesion-07` (crearla desde `master` al inicio). Un commit por
tarea. No pushear.
**Entorno:** KiCad 10.0.4 abierto con el PCB Editor cargado
(`/tmp/gui-test-project/video.kicad_pcb`), API server habilitado, env
vars exportadas. Podés correr `integration_gui`. Si KiCad no responde,
avisale al humano con la acción concreta (reabrir editor, reiniciar) y
seguí con lo que no requiera GUI mientras tanto.

Leé `CLAUDE.md`, `AUDITORIA-PRE-07.md` (raíz o `docs/sesiones/`),
`docs/adr/0008-*.md` y el catálogo antes de tocar nada.

---

## Contexto (hallazgos de la auditoría pre-07)

1. El "busy" de KiCad es `ApiStatusCode.AS_BUSY`, estado protocolar
   documentado del API IPC — no un bug nuestro. No reproducible en
   idle (70/70 OK), pero garantizado que aparece cuando la UI de KiCad
   procesa trabajo background (refill zones, DRC realtime, router).
   kipy mismo tiene busy-loops internos para operaciones async.
2. Los tres estados IPC (socket muerto / PCB Editor no abierto / busy)
   NO son distinguibles en el envelope hoy: (2) y (3) colapsan a
   `KICAD_CLI_FAILED` genérico. La información SÍ está disponible:
   `kipy.errors.ApiError.code` trae `AS_UNHANDLED` (=5) vs `AS_BUSY`
   (=7). Evidencia: kipy `client.py:89-91`, nuestro
   `_map_ipc_failure` en `ipc.py:237-241`.
3. Gap de tests: ningún test cubre el pipeline delta pcb/pcb con
   estados realistas; el centinela solo atrapa crashes, y la invariante
   "solo `_rebuild` emite kind=sch" no está testeada.

---

## Decisiones vinculantes del arquitecto

- **D-07.1 (política de retry para AS_BUSY):** retry con backoff
  exponencial acotado SOLO para operaciones de lectura idempotentes,
  declaradas en una whitelist explícita en el bridge (get_version,
  get_open_board/documents, get_footprints/get_items de lectura,
  get_nets, get_footprint_position, snapshot_footprints). Máximo 2
  reintentos: 250 ms y 500 ms (< 1 s total adicional). Las MUTACIONES
  (move_footprint, add_track, create/update/delete items) JAMÁS se
  reintentan ante AS_BUSY: KiCad puede haber aceptado la primera y el
  retry duplicaría. Un busy que persiste tras los reintentos se emite
  como error tipado (D-07.2). La whitelist es explícita y auditable,
  no una heurística por nombre.
- **D-07.2 (discriminación en el envelope, F3 intacta):**
  `_map_ipc_failure` reconoce `ApiError.code`:
  - `AS_BUSY` → `KICAD_CLI_FAILED` con hint fijo accionable ("KiCad
    está ocupado con una operación en curso; reintentá en unos
    segundos") y `data.ipc_status="busy"`.
  - `AS_UNHANDLED` → `KICAD_CLI_FAILED` con hint "el editor requerido
    no está abierto en KiCad (abrí el PCB Editor)" y
    `data.ipc_status="unhandled"`.
  - Resto de ApiError → comportamiento actual (hint del mensaje).
  Los códigos del catálogo NO cambian. Las keys nuevas de `data` se
  documentan en la sección estándar del catálogo (agente-editable).
  El import de los enums de kipy sigue el contrato perezoso
  (nada de kipy a nivel de módulo).
- **D-07.3 (health fino SIN sondear busy):** el tool `health` se
  extiende para reportar el estado IPC en tres niveles:
  `socket` (existe el archivo), `ipc_responde` (get_version OK),
  `pcb_editor_abierto` (get_open_documents(DOCTYPE_PCB) no-vacío,
  capturando AS_UNHANDLED como "no"). El health NO ejecuta get_items
  ni ningún probe de busy: detectar busy cuesta un GetItems real (~3 s
  en el board de prueba) — demasiado caro para un health check. El
  busy es transitorio y se surfacea por operación vía D-07.2, no por
  health. Presupuesto: el health sigue ≤ ~100 tokens_est y el probe
  extra no puede agregar más de ~1 s de latencia con KiCad abierto
  (get_open_documents es liviano); con KiCad cerrado, el fast-fail de
  socket corta antes (comportamiento de sesión 04 intacto).
- **D-07.4 (cierre del gap de tests delta pcb/pcb):** dos tests:
  1. Unit: la invariante del centinela. Registrar base
     `kind="pcb"` vivo con U1@(100,50); mockear `build_state_cached`
     para devolver un `NormalizedState(kind="pcb")` VÁLIDO pero
     divergente (U1@(0,0)); verificar que con la rama viva presente el
     delta es el correcto, y documentar en el docstring que este test
     ata la invariante "el path de disco jamás debe usarse para bases
     vivas" — si alguien la rompe, el delta saldría con la mutación
     invertida y este test lo atrapa.
  2. integration_gui: pipeline completo realista contra KiCad vivo:
     `get_world_context`-equivalente del board → mutar U19 vía tool →
     `get_context_delta(base=snap pre-mutación)` → el TOON delta
     contiene `[~C] U19` con la posición nueva. Restaurar la posición
     de U19 al final (teardown), como hizo la auditoría.
- **D-07.5 (latencia de mutaciones — medir, NO arreglar):** la
  auditoría midió ~3.6 s por `move_footprint` porque el bridge itera
  `get_footprints()` completo para hallar la ref (O(board) por
  mutación). NO optimices en esta sesión. Tarea: instrumentar la
  medición (el logging JSON ya trae `latency_ms` — verificá que las
  mutaciones lo emitan bien) y en el reporte proponer 1-2 diseños de
  optimización con trade-offs (¿kipy soporta GetItems filtrado?
  ¿cache ref→item invalidado por snapshot? ¿otro?) para que el
  arquitecto decida en la 08.

---

## Fase 0 — Verificación del entorno vivo

1. `python3 scripts/verificar_entorno.py`.
2. Env vars presentes; smoke `integration_gui -k version` → PASS.
3. Suite de arranque: `pytest -m "not integration and not integration_gui"`
   → 85 passed esperados.

## Tarea 1 — `_map_ipc_failure` reconoce ApiStatusCode (D-07.2)

- Implementar la discriminación por `exc.code` con import perezoso de
  los enums (patrón: resolver el valor dentro de la función, o comparar
  por int con constante local documentada citando
  `envelope_pb2.pyi:74-75` — elegí el que mejor conviva con mypy
  strict y el contrato perezoso; argumentá en el commit).
- Catálogo: documentar `data.ipc_status` en la sección estándar de
  `data` (valores, códigos que lo emiten, ejemplos de hint).
- Tests unit: ApiError sintética con code AS_BUSY → hint de busy +
  `data.ipc_status="busy"`; con AS_UNHANDLED → hint de editor +
  `data.ipc_status="unhandled"`; ApiError sin code conocido →
  comportamiento actual; kipy ConnectionError → sigue en
  `KICAD_NOT_RUNNING` (regresión sesión 06 T1 del endurecimiento).

## Tarea 2 — Retry acotado para lecturas idempotentes (D-07.1)

- Wrapper de retry en el bridge (probablemente alrededor de
  `_supervise` o como decorador interno) con la whitelist EXPLÍCITA.
  Backoff 250 ms → 500 ms, máximo 2 reintentos, solo si el fallo
  mapeado es busy (D-07.2).
- Las mutaciones quedan estructuralmente FUERA: que sea imposible por
  construcción aplicarles retry (no un flag que alguien pueda
  encender), p. ej. dos caminos de invocación distintos.
- Logging: cada retry emite una línea JSON (`tool_name`, `op_name`,
  `attempt`, `backoff_ms`) para que el busy real sea observable en
  producción cuando ocurra.
- Tests unit: client fake que devuelve AS_BUSY una vez y luego OK →
  la lectura termina OK con 1 retry registrado; AS_BUSY persistente →
  error tipado tras 2 reintentos con `data.ipc_status="busy"`;
  mutación con AS_BUSY → error INMEDIATO sin retry (el test cuenta
  las invocaciones al fake y exige exactamente 1).

## Tarea 3 — Health fino (D-07.3)

- Extender `tools/meta.health` con los tres niveles (`socket`,
  `ipc_responde`, `pcb_editor_abierto`). Con socket ausente, el
  fast-fail actual corta y los niveles superiores se reportan como
  no-evaluados (no como false engañoso — distinguí "no" de "no sé").
- Catálogo: actualizar la entrada de `health` con el output nuevo y
  ejemplo.
- Tests unit con bridge fake por cada combinación de estados; medir
  tokens_est del health nuevo (≤ ~100) y reportar la latencia con
  KiCad abierto y cerrado.

## Tarea 4 — Cierre del gap de tests delta (D-07.4)

Los dos tests descritos en la decisión. Para el integration_gui,
seguí el protocolo de la auditoría: guardar posición inicial de U19,
mutar, verificar delta, restaurar en teardown (incluso si el assert
falla — try/finally). Regla 7 no aplica al board de /tmp (es copia
descartable), pero el teardown mantiene el entorno estable para
corridas repetidas.

## Tarea 5 — Instrumentación de latencia de mutaciones (D-07.5)

- Verificar que el logging JSON de `move_footprint`/`add_track` emite
  `latency_ms` correcto y que se puede desglosar la parte de búsqueda
  de la ref (si hace falta, un campo `extra.lookup_ms` — logging es
  aditivo, no toca F3).
- Correr 5 mutaciones contra KiCad real y reportar la tabla de
  latencias con desglose.
- En el reporte: 1-2 propuestas de optimización argumentadas con
  trade-offs, SIN implementar.

## Tarea 6 (OPCIONAL — solo si T1-T5 con DoD) — `add_symbol` mínimo

Misma precondición dura que sesión 06: `grep -n "kicad-skip"
pyproject.toml` → si no está, la tarea NO existe y lo reportás en una
línea. Si está: el diseño completo es el de la sesión 06 T5 (clonado
desde template, validaciones pre-mutación, snapshot de DISCO post-write
según D-06.2, G1 backup, hazard del editor abierto documentado,
verificación de efecto per D-06.3, confirm ≤ 50 tokens).

---

## Fuera de scope

- Optimizar la búsqueda de refs en mutaciones (D-07.5: medir y
  proponer, la 08 decide).
- Probe de busy dentro del health (D-07.3: descartado por costo).
- Retry de mutaciones bajo ninguna forma (D-07.1).
- Eval A de formato — recandidatear para la 08.
- Códigos de error nuevos (F3), dependencias (F5), pyproject.

## Definition of Done

```
uv run pytest -m "not integration and not integration_gui"  → verde
uv run pytest -m integration                                → verde (< 5:00, reportar tiempo)
uv run pytest -m integration_gui                            → verde, incluido el nuevo delta pcb/pcb
uv run mypy src/                                            → Success strict
uv run ruff check + format --check                          → clean
```

## Reporte final obligatorio

1. Estado por tarea. Para T2: output del test que demuestra que una
   mutación con AS_BUSY hace exactamente 1 invocación (cero retry).
2. Mutation testing del retry: forzar AS_BUSY persistente en el fake y
   confirmar que el error final trae `data.ipc_status="busy"` y que el
   log registró los 2 intentos.
3. Salida TOON literal del delta pcb/pcb del test integration_gui
   nuevo (T4.2) y sus tokens_est.
4. Tabla de latencias de T5 con desglose, y las propuestas de
   optimización para la 08.
5. tokens_est y latencia del health nuevo (KiCad abierto y cerrado).
6. Confirmación de promedios: global ≤ 400, confirms ≤ 50.
7. Tiempo de integration; si > 5:00, candidatos a `integration_slow`
   (el humano edita pyproject).
8. Dudas abiertas y candidatos argumentados para la sesión 08.
