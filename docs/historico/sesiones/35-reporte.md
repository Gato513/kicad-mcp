# Sesión 35 — CI en GitHub Actions + corrección de markers de `test_sch.py`

**Rama:** `sesion/35-ci-github-actions` (desde `master` @ `b2d385e`, HEAD real
de `origin/master` — `sesion-01` sigue congelada y separada, ver
[[git-rama-principal-master-no-sesion-01]]). Rama secundaria
`sesion/35-pr-broken-canary` (desde `sesion/35-ci-github-actions`, sólo las 4
fixtures rotas, no se mergea).

**Tipo:** infraestructura (primer CI ejecutable del repo) + corrección de
mis-labeling en tests existentes. Primera sesión de la Fase 5
(Consolidación y release).

## Resumen ejecutivo

Se agregó `.github/workflows/ci.yml` con cuatro jobs paralelos que cubren los
cuatro criterios ejecutables de la Definition of Done (`ruff check`,
`ruff format --check`, `mypy src/`, `pytest` offline). En el camino se
confirmó y corrigió el hallazgo de la auditoría previa (R8): 9 tests de
`tests/test_sch.py` estaban marcados `@pytest.mark.unit` pero shellean a
`kicad-cli` (directamente en los helpers de verificación del propio archivo,
e indirectamente vía `tools/sch.py` → `bridge/state_builder.build_state_cached`
→ `bridge/netlist.load_netlist`). Se reetiquetaron a `integration` y se
corrigió la docstring del archivo, que afirmaba (falsamente para esos 9)
"nada de KiCad IPC".

**Bloqueo no anticipado por el prompt:** `.claude/settings.json` deniega
`Edit`/`Write` sobre `pyproject.toml` y `CLAUDE.md` a nivel de permisos del
harness. El consentimiento verbal del arquitecto en el chat no puede
saltear un `deny` — es un bloqueo técnico, no un prompt de confirmación.
Los parches H2 (Parche A y B) quedaron preparados como diff exacto en
`docs/historico/drafts/patches-h2-final.diff`, verificados contra el árbol
real, y el arquitecto los aplicó manualmente (2026-08-04).

**Actualización de cierre (2026-08-04):** la aplicación manual inicial tenía
dos errores — faltaba el `not` antes de `integration_gui_slow` en `addopts`
(invertía la lógica del filtro: exigía el marker en vez de excluirlo,
colapsando la colecta a ~5 tests) y un `+` literal colado al inicio de
`CLAUDE.md:29` (residuo de un diff mal aplicado). Ambos detectados y
corregidos en la misma sesión de verificación, commit `4620b97`. Verificado
post-fix: `pytest --collect-only` (con el `addopts` corregido, sin `-m`
explícito) → **385** tests, coincide con el conteo esperado de H3 (394 antes
del reetiquetado − 9 tests movidos a `integration`); `pytest` completo → **0
failed**; `mypy src/` limpio. `ruff check` reporta 2 errores, ambos en
`docs/historico/drafts/pr-broken-fixtures/*.py` (drafts untracked, ya
señalados como riesgo no bloqueante más abajo en este reporte) — no afectan
código trackeado.

## H1 — El workflow bloquea integraciones rotas

**Estado: confirmada con evidencia real de GitHub Actions (2026-08-04).** El
arquitecto instaló `gh`, se autenticó, pusheó ambas ramas y abrió los dos PRs
(sin marcarlos `draft`, desviación menor del plan original que no afecta la
validación — la CI corre sobre el head SHA independientemente del estado
draft/ready o de la rama base).

- **PR #4** (clean, `sesion/35-ci-github-actions` → `master`, head
  `622a94f`, incluye los fixes de H2): los 4 jobs **verdes**
  (`ruff check`, `ruff format --check`, `mypy src/`, `pytest offline` →
  **385 passed, 0 failed**). Corrió dos veces (trigger `push` + trigger
  `pull_request`, ambos declarados en el workflow), mismas conclusiones en
  las dos corridas. **Mergeado a `master`** (merge commit `897d6a0`,
  2026-08-04T15:57:50Z).
- **PR #5** (broken, `sesion/35-pr-broken-canary` → `master` — base
  desviada del plan, que pedía `sesion/35-ci-github-actions`; sin efecto
  sobre el resultado de la CI, sólo cambia el diff mostrado en la UI del
  PR), head `072c896`: los 4 jobs **fallan**, cada uno con causa
  identificable en el log:
  - `ruff check` → `F401 'os' imported but unused` (`_ci_broken_lint.py`)
  - `ruff format --check` → `Would reformat: src/kicad_mcp/_ci_broken_format.py`
  - `mypy src/` → `Incompatible return value type (got "int", expected "str")` (`_ci_broken_mypy.py:15`)
  - `pytest (offline)` → `AssertionError` del canario, `1 failed, 385 passed, 77 deselected`
  - **Cerrado sin merge** (por diseño — nunca debía mergearse).

Nota: esta rama (`sesion/35-pr-broken-canary`, creada como `072c896` sobre
`38db5bc`) nunca incorporó los commits de fix de H2 (`4620b97`, `622a94f`) —
no hacía falta, porque el job de `pytest` del workflow pasa su propio filtro
`-m` explícito por CLI (independiente del `addopts` de `pyproject.toml`, por
diseño de §Alcance/A del prompt), así que el bug de `addopts` nunca afectó a
la CI, sólo a la invocación local sin `-m` explícito — de ahí que ambas
ramas reporten el mismo "385 passed" base.

H1 queda **confirmada**: el workflow bloquea (reporta rojo con causa clara)
exactamente las cuatro clases de ruptura, y dejaría pasar únicamente el
código que cumple los cuatro criterios de la DoD.

Cada una de las 4 fixtures del PR-broken fue verificada **localmente antes
de commitear**, corriendo los 4 comandos exactos del workflow sobre el árbol
con los 4 archivos copiados a su destino real, confirmando que cada una
dispara **sólo** su check:

| Fixture | Destino | Check que dispara | Verificado |
|---|---|---|---|
| `_ci_broken_lint.py` | `src/kicad_mcp/` | `ruff check` → F401 | ✅ único error, los otros 3 checks limpios |
| `_ci_broken_format.py` | `src/kicad_mcp/` | `ruff format --check` → reformat | ✅ único, `ruff check` no lo toca |
| `_ci_broken_mypy.py` | `src/kicad_mcp/` | `mypy src/` → return-value | ✅ único, ruff limpio |
| `test_ci_broken.py` | `tests/` | `pytest` offline → 1 failed | ✅ único, `mypy` no ve `tests/`, ruff limpio |

**Desviación del draft:** el draft original usaba `assert False` en el
fixture de pytest; se cambió a `assert 1 == 2, "..."` porque `assert False`
dispara `B011` de `ruff` (`flake8-bugbear`, parte del `select` activo en
`pyproject.toml`) y hubiera contaminado también el job de lint —
comprobado empíricamente antes de decidir el cambio.

**Resuelto:** el arquitecto instaló `gh`, se autenticó, pusheó ambas ramas y
abrió los PRs #4 y #5. Resultado real en runner de GitHub Actions
documentado arriba en §H1.

## H2 — Brecha del filtro de pytest (auditoría R8)

**Confirmada, con una corrección al número del prompt.**

El prompt (v2026-08-04) citaba una brecha de "39 tests". Esa cifra comparaba
`-m "not integration"` (433, un filtro de CLI) contra el filtro completo
(394, otro filtro de CLI) — ambos pasados explícitamente por línea de
comandos, donde `-m` en la CLI **reemplaza** por completo al `-m` de
`addopts` (no se combinan). Esa comparación no mide el `addopts` real del
pyproject, mide dos filtros de CLI distintos.

La medición correcta, aislando el efecto exacto del `addopts` vigente
(`-m 'not integration and not integration_gui'`, sin CLI override) contra el
filtro canónico completo:

```
addopts vigente (equivalente a correr sin -m explícito)     → 403 tests
filtro canónico completo (+ 'not integration_gui_slow')      → 394 tests
-m "integration_gui_slow and not integration_gui"             →   9 tests
```

**La brecha real es de 9 tests**, todos `integration_gui_slow` sin
`integration_gui`, que el `addopts` actual deja pasar sin querer. H2 sigue
**confirmada** — el mecanismo del hallazgo (R8) es correcto, sólo el número
del prompt estaba mal derivado.

**Parche A** (`pyproject.toml:33`, `addopts`) y **Parche B** (`CLAUDE.md`
líneas 29 y 151) preparados en
`docs/historico/drafts/patches-h2-final.diff`, verificados: con el Parche A
aplicado, `pytest --collect-only` recolecta 394 (confirmado corriendo el
filtro completo explícito por CLI, que produce el mismo resultado que
tendría el `addopts` corregido). **No aplicados** por el bloqueo de permisos
descrito arriba.

## H3 — Los 9 tests deben ir bajo `integration`, no `unit`

**Confirmada en ambos lados, con evidencia limpia.**

Lado 1 — sin `kicad-cli` en PATH (`PATH` apuntado a un directorio vacío,
`kicad-cli` real en `/usr/bin` oculto por completo):

```
uv run pytest -m "not integration and not integration_gui and not integration_gui_slow"
385 passed, 0 failed, 77 deselected in 43.88s
```

`77 deselected` = 68 (previos) + 9 (recién reetiquetados) — coincide
exactamente con lo esperado. **0 failed**: ningún test que no está en la
lista de 9 depende ocultamente de `kicad-cli`; no se amplió el alcance de
la corrección.

Lado 2 — con `kicad-cli` en PATH (máquina del autor, `/usr/bin/kicad-cli`):

```
Baseline previo a los cambios: uv run pytest -m integration → 29 passed, 0 failed
Tras el reetiquetado:          uv run pytest -m integration → 38 passed, 0 failed
                                (29 + 9 = 38 ✅)
uv run pytest -m integration tests/test_sch.py --collect-only -q → 9 collected
uv run pytest -m integration tests/test_sch.py -q                → 9 passed
```

(Nota operativa: la primera corrida de este segundo lado se reportó como
"failed" por un `task-notification` del harness porque el comando encadenaba
un `grep -E "PASSED|FAILED|ERROR"` que no matcheó nada — la verbosidad neta
de `-v` explícito combinado con el `-q` de `addopts` colapsa a modo por
defecto, que imprime puntos, no la palabra `PASSED` por test. `grep` sin
matches sale con código 1, y ese código propagó al bash encadenado. No fue
un fallo de test: la corrida real, sin depender de `grep`, ya había
reportado "38 passed" en el mismo log. Se re-verificó limpio con
`--collect-only` + corrida simple, sin pipes frágiles.)

## Root cause del mis-labeling

Los 9 tests ejercitan `add_symbol`, `set_value`, `set_footprint` y
`connect_pins` de punta a punta, no sólo el archivo `.kicad_sch` en disco
como afirmaba la docstring original. La cadena real es
`tools/sch.py` → `bridge/state_builder.build_state_cached` →
`bridge/netlist.load_netlist`, que shellea a
`kicad-cli sch export netlist --format kicadxml` (`subprocess.run`,
`bridge/netlist.py:11`) para derivar conectividad — la netlist es la fuente
de verdad de conectividad según `docs/specs/restricciones-kicad.md`, no se
reimplementa desde el archivo. Los helpers `_netlist_comps` /
`_netlist_nodes_by_net` del propio `test_sch.py` hacen lo mismo para
verificar el efecto post-mutación.

**No se investiga en esta sesión** por qué una tool declarada "disk-only"
termina shelleando a `kicad-cli` — el fix de comportamiento correcto (mover
el rótulo del test para que diga la verdad) ya está aplicado y no requiere
resolver esa pregunta. **Se propone como investigación para la sesión 37 o
38**: ¿debería `build_state_cached` derivar conectividad sin re-correr
`kicad-cli` cuando la mutación ya conoce el efecto localmente (patrón que
`add_symbol`/`connect_pins` ya usan parcialmente, ver comentarios en
`tools/sch.py:928-931` y `tools/sch.py:1032`)? Eso permitiría, en teoría,
tests unitarios reales de esas tools sin `kicad-cli`.

## Decisiones tomadas (P9)

1. **H1 sin `gh`/sin push:** el agente prepara ambas ramas localmente
   commiteadas; el arquitecto pushea y abre los PRs draft. Decisión tomada
   con `AskUserQuestion` antes de empezar.
2. **Nombre del reporte:** `35-reporte.md`, siguiendo la convención de
   31/32/32b/32c/32d/33/34a/34b, no el nombre literal del prompt
   (`sesion-35-ci-github-actions.md`).
3. **`docs/historico/drafts/` queda untracked**, no se commitea nada de ahí.
   Ver riesgo abajo.
4. **Bloqueo de permisos sobre `pyproject.toml`/`CLAUDE.md`:** confirmado que
   ni `Edit` ni `Write` lo saltean; se preparó el diff en vez de forzar un
   camino alternativo (ej. editar `.claude/settings.json`, también denegado).
5. **`assert False` → `assert 1 == 2`** en el fixture de pytest del
   PR-broken, para no contaminar el job de lint con `B011`.
6. **Python pineado a 3.11** en el workflow (mínima soportada), desviación
   documentada respecto al draft original que lo dejaba implícito en
   `uv sync`.
7. **SHAs de actions verificados con `git ls-remote --tags`** (no había
   acceso a la API HTTP de GitHub desde este entorno — `curl`/`WebFetch`
   denegados por configuración). Ambos coincidieron exactamente con los del
   draft: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1),
   `astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9` (v9.0.0).
8. **Disposición final de los PRs (2026-08-04, tras validar H1 en runner
   real):** PR #5 (broken) cerrado sin merge — nunca debía mergearse, era
   sólo el canario de H1. PR #4 (clean) mergeado a `master` (`897d6a0`) —
   trae el CI real más los fixes de H2 ya verificados, decisión explícita
   del arquitecto vía `AskUserQuestion` frente a la alternativa de cerrar
   ambos sin mergear (que hubiera dejado `ci.yml` fuera de `master`).

## Fricciones nuevas

- **Permisos del harness más estrictos que el alcance del prompt.** El
  prompt asumía implícitamente que el agente podía tocar `pyproject.toml` y
  `CLAUDE.md` con aprobación del arquitecto ya dada por escrito en el propio
  prompt (H2 es "aplicar sin re-preguntar" según el texto). La capa de
  permisos del harness no distingue esa aprobación previa de una petición
  nueva — deniega el tool call sin importar el contexto conversacional. Vale
  la pena que el arquitecto decida si esas dos entradas del `deny` deberían
  moverse a un `ask` (prompt de confirmación) en vez de `deny` absoluto,
  dado que ya hay guardarraíles equivalentes en CLAUDE.md (F5) y en el
  propio prompt de sesión.
- **Sin `gh` ni acceso HTTP saliente** en este entorno: cualquier sesión que
  necesite abrir/inspeccionar PRs, o resolver SHAs de GitHub Actions por API,
  tiene que usar `git ls-remote` como alternativa (funciona, `git` sí tiene
  salida de red) o delegarle el paso al arquitecto.
- **`actionlint` y `pyyaml` no disponibles localmente** — la sintaxis de
  `ci.yml` se validó a mano (sin tabs, indentación consistente, estructura
  calcada del draft ya revisado) pero no con una herramienta dedicada. Si el
  arquitecto tiene `actionlint`, correrlo antes de pushear es la
  verificación real que falta.
- **Salida de `pytest -v` engañosa cuando `addopts` ya trae `-q`**: los
  flags de verbosidad se netean (`-q` + `-v` = nivel 0, dots), no se
  combinan en "verbose gana". Cualquier automatización futura que dependa de
  parsear "PASSED"/"FAILED" de la salida de pytest debe pasar
  `-vv` (dos niveles) o `-p no:cacheprovider --tb=short -rA` en vez de
  confiar en que `-v` sobreescriba `addopts`.
- **`gh pr merge` bloqueado por el clasificador de auto-mode** (a diferencia
  de `gh pr close`, que sí pasó): mergear a `master` vía agente disparó un
  bloqueo aunque el arquitecto ya lo había autorizado explícitamente en el
  chat inmediatamente antes. Mismo patrón que el `deny` de permisos sobre
  `pyproject.toml`/`CLAUDE.md` — la autorización conversacional no alcanza
  para saltear un bloqueo de la capa de herramientas; el arquitecto tuvo que
  correr `gh pr merge 4 --merge` él mismo. Documentado para que una sesión
  futura no asuma que puede automatizar merges a `master` de punta a punta.

## Riesgo registrado (no bloqueante)

`docs/historico/drafts/pr-broken-fixtures/*.py` (los drafts originales del
arquitecto, no las copias verificadas de esta sesión) siguen untracked en el
repo y rompen `ruff check`/`ruff format --check` si algún día se commitean
tal cual (verificado en la §Verificación de premisa: 2 errores de lint + 1
de formato, ambos en esos archivos). No se tocaron ni se movieron — quedan
como estaban, con esta nota como advertencia explícita para que no
sorprenda en una sesión futura.

## Acción pendiente del arquitecto (branch protection)

Fuera del alcance del agente (paso administrativo de la UI de GitHub):
activar **branch protection rules** con "require status checks to pass"
sobre `master` para los cuatro jobs de `ci.yml`. Sin esto, el CI corre y
reporta el estado correcto pero **no bloquea** ningún merge — el hallazgo
"el CI marca rojo pero no impide mergear" quedaría como sorpresa de una
sesión futura si no se registra ahora.

## Estado de los ocho criterios de éxito

| # | Criterio | Estado |
|---|---|---|
| 1 | `ci.yml` existe, sintaxis válida | ✅ (validación manual; `actionlint` no disponible) |
| 2 | PR-clean 4 jobs verdes <15 min | ✅ confirmado en GitHub Actions, PR #4 mergeado a `master` (`897d6a0`) |
| 3 | PR-broken 4 jobs rojos con causa identificable | ✅ confirmado en GitHub Actions, PR #5 cerrado sin merge |
| 4 | Comandos del workflow == comandos locales | ✅ |
| 5 | H3 con evidencia (0 failed sin kicad-cli; 9/9 pasan con kicad-cli) | ✅ |
| 6 | Docstring `test_sch.py` actualizada | ✅ |
| 7 | Parches H2 (`pyproject.toml`, `CLAUDE.md`) | ✅ aplicados y corregidos (commit `4620b97`) |
| 8 | Este reporte | ✅ |

## Próxima sesión (propuesta para sesión 36)

1. **Único pendiente real de la sesión 35:** activar branch protection
   rules sobre `master` (requerir los 4 status checks de `ci.yml`) — paso
   administrativo de la UI de GitHub, fuera del alcance del agente. Sin
   esto, el CI corre y reporta pero no bloquea merges.
2. Badge de CI en `README.md` (explícitamente fuera de esta sesión) una vez
   el workflow esté estable en `master` con nombre canónico fijado.
3. Investigación de causa raíz del mis-labeling (propuesta arriba): si
   `build_state_cached` puede derivar conectividad sin `kicad-cli` en el
   camino caliente de mutación, abriría la puerta a tests unitarios reales
   de `add_symbol`/`set_value`/`set_footprint`/`connect_pins`.
4. Evaluar con el arquitecto si el `deny` de `.claude/settings.json` sobre
   `pyproject.toml`/`CLAUDE.md` debería relajarse a `ask` para sesiones con
   aprobación ya explícita en el prompt, o si el patrón correcto sigue
   siendo "el agente prepara el diff, el humano aplica" (como se resolvió
   acá).
