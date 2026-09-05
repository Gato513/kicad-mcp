# Sesión 43 — fix `_copper_on_layer`: capas internas de una vía pasante

**Rama:** `sesion/42-dt1-slice2-caracterizacion` (continuación de sesión 42).

**Tipo:** fix acotado de un bug preexistente, con auditoría independiente
(Codex, read-only) del plan antes de implementar.

## Resumen ejecutivo

`docs/specs/tool-catalog.md:437` (contrato F1) promete: "`layer` filtra por
capa de cobre; una via pasante cuenta para cualquier capa de su span". La
implementación no lo cumplía: `_copper_on_layer` (`tools/pcb_geometry.py`)
matcheaba una vía sólo contra sus dos extremos (`CopperItem.via_layers:
tuple[str, str]`), no contra el span completo. En un board multicapa,
`_copper_on_layer(via_pasante, "In1.Cu")` devolvía `False` pese a que la vía
físicamente atraviesa esa capa. Bug preexistente hallado por revisión de
Codex sobre DT1 Slice 2 (sesión 42), anotado en `docs/BACKLOG.md` con la
decisión de diseño explícitamente diferida.

Esta sesión resolvió esa decisión: **poblar el span real desde el bridge,
dejar el filtro puro.** El stackup habilitado del board se resuelve donde ya
vive (`bridge/ipc.py`, reusando `_copper_layer_values`, existente desde P4)
y viaja como dato nuevo, `CopperItem.via_span_layers: tuple[str, ...] |
None`, sin tocar `via_layers` (que sigue siendo el par de extremos que el
encoder renderiza en la línea `V ... F.Cu-B.Cu`, formato congelado por
golden). `_copper_on_layer` prioriza el span si está disponible y cae al
comportamiento de extremos si no.

## Proceso: auditoría antes de implementar

Por pedido explícito del humano, el plan completo (impacto, diseño,
alternativas descartadas, tests, DoD) se auditó con Codex (`mcp__codex__codex`,
sandbox read-only) ANTES de escribir una línea de código. Veredicto:
**APROBAR_CON_CAMBIOS**, 3 hallazgos MAJOR:

1. La tesis "es un no-op estricto en boards de 2 capas" era falsa — el fix
   agrega un request IPC nuevo (`get_enabled_layers()`), así que cambia
   latencia y superficie de fallo también en 2 capas. Corregido: la
   propiedad que se sostiene es selección/encoding idénticos, no ausencia
   de costo.
2. El plan decía que `delete_tracks_bulk` (el sitio destructivo del fix)
   estaba "protegido por `dry_run`/`include_vias`". Falso, verificado contra
   `pcb.py:1584-1585`: los defaults son `include_vias=True`,
   `dry_run=False`, y el filtro corre antes del early-return — son válvulas
   *opt-in*, no protecciones automáticas.
3. Los tests propuestos originalmente (sólo helper + filtro) no detectarían
   omitir uno de los tres productores del bridge, calcular el stackup por
   ítem en vez de una vez por llamada, ni el cambio de comportamiento
   destructivo.

Sobrevivieron sin cambios: el ordenamiento del enum `BoardLayer` (verificado
independientemente contra el protobuf instalado: `BL_F_Cu=3` … `BL_B_Cu=34`),
el diseño de dos campos (`via_layers` vs. `via_span_layers` — distinción
legítima, no redundancia), la ausencia de ADR, la ausencia de reentrancia del
lock (`_copper_layer_values` es función de módulo, no método; precedente
directo: `add_keepout_zone` ya la llama con el lock tomado), y la cobertura
de consumidores (ningún otro filtro por capa incumple el contrato).

Un riesgo adicional, no levantado por la auditoría, se identificó durante la
verificación propia: `Board.get_enabled_layers()` es `versionadded 0.5.0`
(KiCad 9.0.5+), y F4 declara mínimo compatible 9.0. Meterla en el camino de
lectura de `get_tracks` sin mitigación habría regresionado esa tool en
9.0.0–9.0.4.

Tres decisiones quedaron explícitamente en manos del humano tras la
auditoría (`AskUserQuestion`), todas resueltas antes de implementar:
semántica uniforme en los tres call sites (no acotar a `get_tracks`),
degradar con log ante fallo de lectura del stackup (preservar compat 9.0),
y escribir-y-diferir el test de integración multicapa (sin fixture
disponible en el protocolo GUI de este proyecto).

## Proceso: segunda auditoría, después de implementar (commit `3f175f8`)

Por pedido explícito del humano, tras el primer commit se corrió una SEGUNDA
auditoría de Codex — esta vez sobre el código ya implementado (`git diff
11f4918..3f175f8`), no sobre el plan. Objetivo: confirmar que las 3
correcciones MAJOR de la primera auditoría se implementaron tal como se
prometió, y encontrar bugs de la implementación misma que el plan no podía
haber anticipado. Veredicto: **APROBAR_CON_CAMBIOS**, con hallazgos reales
que no estaban en el plan:

1. **MAJOR, confirmado y corregido.** `_safe_copper_layer_values` interpolaba
   `str(exc)` directamente en un literal JSON armado a mano
   (`'{"tool_name":...,"error":"%s"}' % str(exc)`) — un mensaje de excepción
   con comillas o saltos de línea produce JSON inválido. Reproducido:
   `RuntimeError('bad "quote" and\nnewline')` rompía `json.loads()`. Peor:
   el codebase YA tenía el patrón correcto (`logging_config.py`,
   `log_socket_glob_ambiguous`/`log_ipc_retry`, ambos con `json.dumps(...,
   separators=(",", ":"), ensure_ascii=False)`, ya importados en
   `bridge/ipc.py`) y el fix lo pasó por alto, copiando en cambio el patrón
   más frágil de `pcb.py:243`. **Corregido:** nuevo
   `log_copper_layer_stackup_unavailable(error: str)` en `logging_config.py`,
   mismo patrón exacto que sus dos hermanos; `_safe_copper_layer_values`
   ahora lo llama. Test nuevo que reproduce el mensaje hostil y valida con
   `json.loads()` real, no sólo `in r.message`.
2. **MINOR, confirmado y corregido.** El invariante documentado en
   `CopperItem.via_span_layers` decía que sus extremos coinciden
   POSICIONALMENTE con `via_layers` — falso si `drill.start_layer >
   drill.end_layer` (kipy no garantiza el orden), porque
   `_via_span_layer_names` siempre normaliza a orden físico ascendente
   mientras `via_layers` es el par crudo `(start, end)` tal cual lo reporta
   el drill. No afecta el filtro (que sólo consulta pertenencia), sólo la
   documentación y un test. **Corregido:** el invariante ahora se documenta
   y testea como igualdad de CONJUNTO
   (`{span[0], span[-1]} == set(via_layers)`), no de posición.
3. **MINOR, confirmado y corregido (cobertura).**
   - Faltaba el análogo de "cero llamadas IPC sin vía" para
     `list_all_copper` — sólo `list_net_copper` lo tenía. El reporte de
     sesión afirmaba esa cobertura sin que el test existiera. Agregado.
   - El test `include_vias=False` de `test_pcb_delete_bulk.py` pasaba
     igual con el bug SIN corregir (el filtro de capa ya excluía la vía por
     su cuenta, así que `include_vias=False` nunca llegaba a ejercitarse) —
     no discriminaba nada. Corregido: el test ahora primero prueba, con la
     misma geometría e `include_vias=True` (default), que el filtro
     corregido SÍ selecciona la vía — sin esa aserción de control, un fallo
     de la aserción principal sería indistinguible del bug original.
   - El test GUI elegía `vias[0]` a ciegas asumiendo que toda vía es
     pasante — rompible si el board de referencia tuviera una vía ciega/
     enterrada cuyo span no llega a la capa elegida. Corregido: busca la
     primera vía cuyo span normalizado realmente cubre la capa interna
     objetivo, y hace `skip` explícito si ninguna la cubre.

Confirmado sin cambios: `_via_span_layer_names` (extremos normales, iguales,
invertidos, ausentes — sin off-by-one), los tres productores resolviendo el
stackup exactamente una vez cuando corresponde y nunca por ítem,
`_copper_on_layer` preservando el fallback exacto en 2 capas, la semántica
compartida entre los tres call sites, F1/F3 intactas.

## Cambios

- **`src/kicad_mcp/bridge/ipc.py`:**
  - `CopperItem.via_span_layers: tuple[str, ...] | None = None` — campo
    nuevo, aditivo, con el invariante documentado de que sus extremos
    coinciden con `via_layers` cuando no es `None`.
  - `_via_span_layer_names(copper_values, start, end)` — helper puro nuevo:
    slice ordenado del stackup habilitado entre dos extremos (inclusive),
    normaliza extremos invertidos, degrada a los dos nombres de extremo si
    alguno no está en `copper_values` (defensivo, no alcanzable en
    producción).
  - `_safe_copper_layer_values(raw_board)` — envoltorio de
    `_copper_layer_values` con degradación ante fallo (compat KiCad
    9.0–9.0.4): loguea vía `log_copper_layer_stackup_unavailable`
    (`logging_config.py`, JSON real con `json.dumps`, regla 2 — ver
    corrección #1 de la segunda auditoría abajo) y devuelve `[]` en vez de
    propagar.
  - `_kipy_copper_to_item` gana `copper_values: Sequence[int] = ()` y
    puebla `via_span_layers` sólo en la rama `Via`. Default vacío ⇒
    comportamiento idéntico al previo (ningún llamador queda obligado).
  - `list_net_copper`, `list_all_copper`, `get_copper_by_kiid` resuelven el
    stackup **una vez por llamada, sólo si el resultado contiene al menos
    una vía** (cero costo IPC extra para listados de sólo tracks, o para
    `get_copper_by_kiid` resolviendo el caso típico de un track).
- **`src/kicad_mcp/tools/pcb_geometry.py`:** `_copper_on_layer` consulta
  `via_span_layers` primero; si es `None`, cae al comportamiento previo
  (`via_layers`, sólo extremos). Semántica uniforme automática en los tres
  call sites (`get_tracks`, `delete_tracks_bulk`, guardrail #5 de
  stitching) porque los tres comparten esta única función.
- **`src/kicad_mcp/logging_config.py`:** `log_copper_layer_stackup_unavailable`
  nuevo — mismo patrón exacto que `log_socket_glob_ambiguous`/`log_ipc_retry`
  (`json.dumps(..., separators=(",", ":"), ensure_ascii=False)`).
- **Sin cambios:** `tools/pcb_encoders.py` (sigue leyendo `via_layers`, el
  formato `V ... F.Cu-B.Cu` queda idéntico), `docs/specs/tool-catalog.md`
  (F1 — el contrato ya describía la semántica correcta), `tests/golden/`
  (F1 — verificados verdes sin modificarse).

## Tests (26 nuevos tras el segundo commit, 25 netos tras la auditoría de
sobre-ingeniería — ninguno de los preexistentes a sesión 43 editado)

- **`tests/test_ipc.py`** (17 nuevos, 16 tras la tercera auditoría):
  `_via_span_layer_names` (stackup de 2/4 capas, vía ciega/enterrada,
  extremos iguales/invertidos — el caso de extremo ausente del stackup se
  eliminó junto a la rama defensiva inalcanzable que protegía, hallazgo de
  la auditoría de sobre-ingeniería); `_safe_copper_layer_values` (degrada y
  loguea ante fallo, con `caplog`, + test de JSON válido con mensaje hostil
  — corrección #1 de la segunda auditoría); `_kipy_copper_to_item` (puebla
  el span con stackup dado, lo deja en `None` con `copper_values=()` ahora
  obligatorio, nunca lo puebla para un track); canarios de conteo IPC en
  los tres productores, incluido el que faltaba para `list_all_copper` sin
  vías (corrección #3).
- **`tests/test_pcb_geometry_unit.py`** (5 nuevos): el filtro con span
  (incluye capas internas), con span sigue matcheando extremos, sin span
  cae al comportamiento previo (canario de regresión), vía ciega/enterrada
  no matchea capas externas, invariante extremos-vs-span como conjunto
  (corregido de "posicional" — corrección #2).
- **`tests/test_pcb_delete_bulk.py`** (3 nuevos, uno reescrito para ser
  autocontenido): el sitio destructivo en sus tres modos — `dry_run`
  (reporta sin mutar), borrado real (el KIID de la vía llega a
  `remove_many_by_kiid`), `include_vias=False` con control de que el
  filtro SÍ selecciona la vía por defecto (corrección #3 — la versión
  original pasaba igual con el bug sin corregir). Cierra una brecha de
  cobertura preexistente: ningún test de este archivo ejercitaba el filtro
  `layer=` antes de esta sesión.
- **`tests/test_pcb_session43_multilayer_via_span_gui.py`** (nuevo,
  `integration_gui`): **escrito, ejecución pendiente del humano.** El
  protocolo GUI de este proyecto no tiene hoy ningún proyecto de referencia
  con capas internas habilitadas — hace `skip` explícito con esa razón si
  el board abierto tiene menos de 4 capas de cobre. Busca una vía cuyo span
  realmente cubra la capa interna elegida (corrección #3, no `vias[0]` a
  ciegas). Mismo precedente que sesión 32d ("verificación end-to-end
  escrita pero pendiente de ejecución humana"). No se declara verde un gate
  que no corrió.

## Proceso: tercera auditoría, sobre sobre-ingeniería (commit final)

Pedido explícito del humano: auditar el código YA implementado y ya
corregido dos veces, esta vez buscando específicamente sobre-ingeniería
(CLAUDE.md: no defender contra escenarios inalcanzables, no generalidad sin
uso, no documentación desproporcionada) — no bugs de corrección, ya
cubiertos. Veredicto: **APROBAR_CON_CAMBIOS**. Cada hallazgo se verificó
contra el código real antes de aceptarlo:

**Aplicados:**
1. La rama defensiva de `_via_span_layer_names` para un extremo ausente de
   `copper_values` era inalcanzable en producción — el propio docstring ya
   lo admitía ("defensivo, no alcanzable hoy"). Eliminada junto a su test.
2. El default `copper_values: Sequence[int] = ()` de `_kipy_copper_to_item`
   no lo usaba ningún llamador productivo (los tres productores siempre
   pasan el valor resuelto, verificado con grep). Ahora es obligatorio; el
   test que sólo consagraba el default se ajustó para pasar `()` explícito
   — esa rama (resultado sin vías / stackup degradado) sí es real.
3. Se recortaron los docstrings de `via_span_layers`,
   `_safe_copper_layer_values`, `_via_span_layer_names`,
   `log_copper_layer_stackup_unavailable` y `_copper_on_layer` al nivel de
   densidad de sus pares en el mismo archivo (comparados línea a línea
   contra `log_socket_glob_ambiguous`/`log_ipc_retry`). De paso se corrigió
   una afirmación imprecisa en `_copper_on_layer`: decía que
   `via_span_layers=None` podía deberse a un "board de 2 capas donde nunca
   se calculó" — falso, los productores sí calculan el stackup en 2 capas
   si hay una vía; `None` sólo ocurre por degradación o construcción
   manual en tests.

**Rechazados, con razón explícita (no todo hallazgo de una auditoría se
aplica ciegamente — precedente `codex-review-verificar-hallazgos`):**
- La recomendación principal, fusionar `via_layers`/`via_span_layers` en un
  único campo: la propia auditoría #1 (antes de implementar) ya había
  evaluado esta distinción como legítima, no redundancia — son datos con
  disponibilidad distinta (uno siempre disponible desde el drill, el otro
  condicionado a una lectura de stackup que puede degradar) y longitud
  distinta (2 vs N). Fusionarlos exigiría sobrecargar la semántica del
  campo y tocar de nuevo el encoder del formato F1, con riesgo de churn no
  justificado por ahorrar un campo en una superficie que ya pasó dos
  rondas de auditoría.
- La mayoría de los tests señalados como "redundantes" en realidad
  ejercitan ramas de dispatch o interacciones con flags preexistentes
  (`include_vias=False` sobre la nueva selección por capa interna,
  dispatch de `Track` vs `Via` en `_kipy_copper_to_item`) que ningún otro
  test cubre mecánicamente igual — se mantienen.
- Soporte de vías ciegas/enterradas, la degradación KiCad 9.0-9.0.4, y el
  test `integration_gui` diferido: los tres marcados **JUSTIFICADO** por la
  propia auditoría — sin cambios.

## Verificación

```
uv run ruff check --fix && uv run ruff format   # limpio
uv run mypy src/                                # Success: no issues found in 36 source files
uv run pytest -m "not integration and not integration_gui and not integration_gui_slow"
                                                 # 467 passed, 79 deselected
```

Baseline previo a la sesión: 443 passed. +23 del primer commit (verificado
con `git stash`/`--collect-only`: `test_ipc.py` 66→81,
`test_pcb_geometry_unit.py` 33→38, `test_pcb_delete_bulk.py` 10→13) + 2 de
la segunda auditoría (`test_ipc.py`: JSON hostil + skip de `list_all_copper`
sin vía) = 468. La tercera auditoría eliminó 1 test (la rama defensiva
inalcanzable, sin reemplazo) → **467 passed** final. `git diff` de la
tercera ronda toca sólo `ipc.py`, `logging_config.py`, `pcb_geometry.py` y
`test_ipc.py` — ningún test preexistente a sesión 43 fue tocado, F1 intacto
(`git diff --stat -- docs/specs/ tests/golden/` vacío). Goldens
(`test_pcb_encoders_golden.py`) verdes sin modificarse.

## Sin ADR

Mismo criterio que el fix de bbox Edge.Cuts de sesión 31b: implementa un
contrato ya documentado (`tool-catalog.md:437`) sin cambiar ninguna
superficie externa observable — "aclaración de comportamiento" (DoD #4).
`tool-catalog.md` no requiere actualización.

## Proceso: fixture de 4 capas para el test GUI diferido

El pendiente original de esta sesión era "ejecutar el test contra un
proyecto KiCad real de 4+ capas — requiere preparar ese proyecto de
referencia, ausente hoy del protocolo GUI". Esa premisa era **falsa**:
`tests/fixtures/004_real/video.kicad_pcb` —el proyecto de referencia que el
protocolo GUI ya usa— es de 4 capas con 808 vías pasantes. El bloqueo real,
descubierto al investigar antes de crear nada: `get_tracks` no trunca
(`src/kicad_mcp/tools/pcb.py:1551-1559`, lanza `CONTEXT_BUDGET_IMPOSSIBLE`
si el listado excede el presupuesto), así que contra `004_real` el test
fallaría con error en vez de saltarse — un board multicapa real, pero
inútil para este caso puntual.

Se creó `tests/fixtures/007_pcb_multicapa/` — PCB sintética mínima escrita a
mano (formato KiCad 10, `version 20260206`/`generator_version "10.0"`,
verificado contra el `kicad-cli` 10.0.5 instalado y contra los fixtures
`005_pcb_limpio`/`006_pcb_refs_duplicados` ya commiteados en ese mismo
formato): 4 capas de cobre (F.Cu/In1.Cu/In2.Cu/B.Cu), una vía pasante
F.Cu-B.Cu sobre el net GND, un segmento en F.Cu (debe quedar excluido por el
filtro `layer="In1.Cu"`) y uno en In1.Cu (debe quedar incluido), conectados
a través de la vía. 128 líneas, 4KB — sin footprints, sin `.kicad_sch`
(el camino IPC del PCB Editor no lo necesita, confirmado por precedente de
`005`/`006`), sin `.kicad_prl` (estado local de UI, KiCad lo genera solo).
`.kicad_pro` basado en la plantilla en blanco de KiCad
(`/usr/share/kicad/template/kicad.kicad_pro`).

Validado en dos capas independientes antes de commitear:
1. `kicad-cli pcb drc --severity-all`: 0 errores, 0 unconnected items (sólo
   2 warnings `track_dangling` en los extremos abiertos de los stubs, sin
   pad — esperado).
2. Cargado con el módulo `pcbnew` de KiCad 10 (mismo motor que abre el
   archivo real): `GetCopperLayerCount()==4`, capas habilitadas
   `[F.Cu, B.Cu, In1.Cu, In2.Cu]`, vía `F.Cu→B.Cu` en net `GND` — la
   estructura exacta que el test necesita.

`tests/test_pcb_session43_multilayer_via_span_gui.py` ganó un preflight
(`_preflight_same_board_open`, mismo patrón que
`test_pcb_session27_zone_persist_gui.py:90-101`): compara el board
realmente abierto en KiCad contra `KICAD_MCP_PROJECT` y hace `skip`
accionable si difieren — necesario porque ahora hay dos proyectos GUI
multicapa en juego (`004_real` de la suite general, `007_pcb_multicapa`
de este test) y correr contra el equivocado antes daba un error confuso de
presupuesto en vez de un skip claro. El docstring del módulo y los mensajes
de skip se corrigieron para no repetir la premisa falsa. Protocolo de
apertura documentado en `docs/guias/pruebas-gui.md` §Fixture
`007_pcb_multicapa`, en paralelo a la sección de `despertador-routed`.

**El test sigue pendiente de ejecución humana** — este trabajo lo hizo
ejecutable (antes era imposible de correr sin fallar), no lo declaró verde.

## Pendiente para una sesión futura

- Ejecutar `tests/test_pcb_session43_multilayer_via_span_gui.py` contra
  `tests/fixtures/007_pcb_multicapa/` siguiendo el protocolo de
  `docs/guias/pruebas-gui.md` — requiere un humano con KiCad abierto.
- El BACKLOG de sesión 42 anotaba además un candidato de campo separado
  (`kiid` sin sanitizar en los encoders ad hoc, `P1-2`) — no tocado en esta
  sesión, sigue abierto sin sesión asignada.
