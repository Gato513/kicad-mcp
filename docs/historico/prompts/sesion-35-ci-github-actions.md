# Prompt sesión 35 — CI en GitHub Actions + corrección de markers de test_sch.py

**Rama:** `sesion/35-ci-github-actions`
**Rama base verificada:** `master` @ `b2d385e` (la rama `sesion/34b-license-readme-contributing` ya se mergeó y se borró — el HEAD real de `origin/master` es el commit auditado).
**Fecha del prompt:** 2026-08-04 (revisión de la versión 2026-08-02).
**Fase de proyecto:** 5 (Consolidación y release) — primera sesión de la fase.
**Contexto asumido:** el agente ya leyó los cuatro documentos del traspaso *y* la sección §Historial de este prompt.

---

## Historial del prompt (por qué esta es la versión revisada)

La versión 2026-08-02 asumía, siguiendo la auditoría §1, que `pytest -m "not integration"` producía **394 passed** sobre una máquina limpia. Verificación P3 previa contra `origin/master` refutó esa premisa:

- Con `kicad-cli` en PATH (máquina del autor): 394 passed, coincide con la auditoría.
- Sin `kicad-cli` (entorno CI limpio, `ubuntu-latest`): **9 failed, 385 passed, 68 deselected**. Los 9 son de `test_sch.py`, todos con `[KICAD_CLI_MISSING]`, todos marcados `@pytest.mark.unit` — que la definición de marker de `pyproject.toml:35` describe como *"lógica pura, sin I/O"*.

Es un mis-labeling: son tests que shellean a `kicad-cli` (vía las tools `add_symbol`, `set_footprint`, `connect_pins`, `set_value`) y por definición deberían llevar el marker `integration`, no `unit`. La docstring del propio archivo (`test_sch.py:1-20`) refuerza la confusión: dice *"Nada de KiCad IPC — la superficie es 100 % `.kicad_sch` sobre disco (D-08.5 #3)"* — cierto para el propósito declarado, falso para la implementación real.

Esta sesión resuelve las dos cosas en un mismo PR — CI ejecutable + reetiquetado de los 9 tests — porque son la misma verdad medida desde dos ángulos: sin CI, el mis-labeling era invisible; con CI y sin corregir el mis-labeling, el CI arranca rojo el día uno. La alternativa (una sesión "35a" que sólo mueve 9 líneas) fragmenta la unidad de trabajo (retrospectiva §5-8, antipatrón).

**Descarto explícitamente** dos caminos evaluados:

- Instalar `kicad-cli` en el runner de CI (viola la premisa "los tests offline no lo necesitan" y esconde el mis-labeling detrás de una variable controlada — antipatrón A3-adyacente).
- `--deselect` de los 9 tests en la CLI del CI (§Nota Preventiva de la versión anterior lo lista como violación directa).

---

## Objetivo (verificable en una frase)

Convertir los seis criterios de Definition of Done de `CLAUDE.md:150-163` en un gate ejecutable de GitHub Actions que bloquee cualquier PR que rompa `ruff check`, `ruff format --check`, `mypy src/` o `pytest -m "not integration and not integration_gui and not integration_gui_slow"`, **y** dejar el suite offline realmente offline reetiquetando los 9 tests de `test_sch.py` que hoy dependen de `kicad-cli` bajo un marker mentiroso.

## Hipótesis y criterio de refutación

### H1 — El workflow bloquea integraciones rotas

Un workflow con los cuatro checks sobre `push`/`pull_request` bloquea mecánicamente la integración de código que rompe cualquiera de los cuatro criterios.

**Refutación:** dos PRs, ambos `draft`:
- **PR-clean** (rama base + este PR de sesión 35 sin las fixtures rotas): los cuatro jobs pasan verdes. Si alguno rojo → H1 refutada; workflow bugueado o rama base no está limpia.
- **PR-broken** (rama base + cuatro archivos deliberadamente rotos, uno por check): los cuatro jobs rojos con mensajes identificables. Si algún job verde, o rojo sin causa clara → H1 refutada.

### H2 — El filtro actual deja pasar `integration_gui_slow` (auditoría R8)

**Pre-confirmada por P3 con evidencia dura** — el agente no re-ejecuta el criterio de refutación:

```
uv run pytest -m "not integration" --collect-only              → 433 tests
uv run pytest -m "not integration and not integration_gui and not integration_gui_slow" --collect-only → 394 tests
Diferencia: 39 tests marcados sólo con integration_gui_slow (sin integration_gui) que el filtro actual deja pasar.
```

Además el `394` del filtro amplio **coincide exacto** con el "394 passed" que reportó la auditoría §1 — el autor original ya corría el comando canónico completo del contexto §7 en local, no el `addopts` del pyproject. La desincronización entre pyproject y CLAUDE.md ya estaba operando, sólo que no se notaba porque cambiaba el conteo en 39 tests que localmente pasan igual.

**Consecuencia:** aplicar Parche A (`pyproject.toml`) y Parche B (`CLAUDE.md`) en este mismo PR. Detalle en §Alcance.

### H3 — Los 9 tests fallantes deben ir marcados `integration`, no `unit`

Los 9 tests listados en §Alcance/D disparan `[KICAD_CLI_MISSING]` en un entorno sin `kicad-cli`, y `pyproject.toml:37` define `integration` como *"requiere kicad-cli o KiCad corriendo (excluida por defecto)"*. Esa es la definición semánticamente correcta.

**Refutación:** cambiar sólo el marker de esos 9 tests y correr, **sin `kicad-cli` en PATH**, `uv run pytest -m "not integration and not integration_gui and not integration_gui_slow"`. Debe reportar **0 failed** y (385 passed, `deselected` mayor que antes). Si algún test que no está en la lista de 9 falla → H3 refutada; hay más superficie de dependencia oculta a kicad-cli y hay que ampliar la corrección o escalar.

Ejecutar también, **con `kicad-cli` en PATH**, `uv run pytest -m integration` y confirmar que los 9 tests corren y pasan bajo su nuevo marker — sino H3 se refuta desde el otro lado (el marker es un rótulo sin efecto real).

## Verificación de premisa (P3)

Antes de tocar código:

1. `git checkout master && git pull --ff-only && git status`. HEAD debe ser `b2d385e` con working tree limpia. Si no, la base cambió — escalar.
2. Confirmar `.github/` inexistente: `test ! -d .github && echo OK`. Si existe, la premisa "no hay CI" es falsa — escalar.
3. Los tres checks que P3 previa reportó limpios: `uv sync --frozen && uv run ruff check && uv run ruff format --check && uv run mypy src/`. Si alguno falla, la rama base cambió desde el 2026-08-04 — reportar y esperar.
4. **No** hace falta re-correr el criterio de refutación de H2; ya está confirmada con evidencia y anotada arriba. Sí hace falta ejecutar el criterio de refutación de H3 (§Refutación de H3) como parte de la sesión, sobre la rama de sesión con los markers ya corregidos.

## Alcance

### Dentro (in)

**A. `.github/workflows/ci.yml` con los cuatro jobs.** Detalles vinculantes:

- Trigger: `push` a cualquier rama + `pull_request` contra `master` y ramas `sesion*` (glob permisivo — cubre las dos convenciones observadas en el repo, `sesion/N-descripcion` y `sesion-N`).
- Runner: `ubuntu-latest`. Ninguna instalación de KiCad, Freerouting ni Java — con la corrección de markers de §D, el suite offline queda realmente offline.
- Python: resuelto por `uv sync` desde `pyproject.toml` (`requires-python = ">=3.11"`). Fijar la mínima soportada (3.11) para el runner — el CI verde ahí implica verde en 3.12/3.13 (subconjunto usual; si en el futuro se agrega algo específico de 3.12+, esto se replantea).
- Instalación: `uv sync --frozen` para respetar `uv.lock` (verificado presente).
- Cuatro jobs paralelos independientes (`ruff-check`, `ruff-format`, `mypy`, `pytest-offline`), no un job con cuatro steps — para que criterio de éxito #3 se cumpla sin trucos de `if: always()`. Costo: `uv sync` corre 4 veces, mitigado por el cache de `astral-sh/setup-uv`.
- Cada step falla la corrida completa si su comando devuelve exit code ≠ 0. Sin `continue-on-error`.
- Actions pineadas por SHA de 40 caracteres con comentario `# vX.Y.Z`. Renovate/Dependabot los actualiza — no un editor humano al azar.
- `permissions: contents: read` mínimo top-level. Sin secretos.
- `concurrency` con `cancel-in-progress: true` sobre `${{ github.workflow }}-${{ github.ref }}` — evita que corridas viejas del mismo ref pisen a las nuevas.
- Filtro de `pytest` explícito en la CLI del workflow, **independiente** del `addopts` de `pyproject.toml` (la CLI gana sobre `addopts` cuando ambos declaran `-m`): `-m "not integration and not integration_gui and not integration_gui_slow"`.

**B. Corrección de H2 en el mismo PR.**

- `pyproject.toml:33` cambia `addopts = "-m 'not integration and not integration_gui' -q"` → `addopts = "-m 'not integration and not integration_gui and not integration_gui_slow' -q"`. Verificación: `uv run pytest --collect-only 2>&1 | tail -3` sobre la rama con el parche debe recolectar 394 - N tests, donde N es el número de tests marcados `integration` (los que P3 excluye por otro filtro que sigue igual).
- `CLAUDE.md`: sincronizar el comando documentado de `pytest` a la forma completa. `grep -n 'not integration' CLAUDE.md` para inventariar; reemplazar sólo las ocurrencias del comando de test, no otras menciones del término.
- **Sólo estos dos cambios en `CLAUDE.md`.** El resto del drift documental (P1-4 del contexto: `CONTEXT.md` en raíz, `hoja-de-ruta-v4.md`, snapshots con "índice espacial") queda como sesión aparte de mantenimiento documental.

**C. Los dos PRs de prueba para validar H1.**

- **PR-clean:** rama `sesion/35-ci-github-actions` con A + B + D aplicados, sin las fixtures rotas de §E. CI debe pasar los cuatro jobs en verde en menos de 15 min totales.
- **PR-broken:** rama `sesion/35-pr-broken-canary` partida de la misma base + las cuatro fixtures rotas de §E (una por check). CI debe fallar los cuatro jobs con mensajes identificables.
- Ambos PRs en `draft`, resultado registrado en el reporte de cierre, cerrados sin merge una vez validado H1.

**D. Corrección de markers en `test_sch.py` (Camino 4 confirmado por el arquitecto).**

Cambiar `@pytest.mark.unit` → `@pytest.mark.integration` en exactamente estos 9 tests:

- `test_add_symbol_happy_path_on_001_basico`
- `test_add_symbol_registers_disk_snapshot_with_fresh_mtimes`
- `test_set_value_happy_path`
- `test_set_value_disk_snapshot_has_mtimes`
- `test_set_footprint_happy_path`
- `test_connect_pins_golden_netlist`
- `test_connect_pins_snapshot_and_audit`
- `test_add_symbol_cross_file_from_explicit_palette`
- `test_add_symbol_default_palette_lookup`

Verificación local sin `kicad-cli`: los tres commands (§Refutación de H3). Los 9 quedan en `deselected`, el resto pasa.

**Actualización de docstring de `test_sch.py`** (líneas 1-20): la afirmación *"Nada de KiCad IPC — la superficie es 100 % `.kicad_sch` sobre disco (D-08.5 #3)"* debe reescribirse a la verdad — algunos tests shellean a `kicad-cli` para validaciones internas de las tools, por eso están bajo marker `integration`. Referenciar el hallazgo con un ancla al reporte de la sesión 35.

**No** re-clasificar tests `integration_gui` ni `integration_gui_slow`; los 9 son los únicos que P3 previa expuso como mis-etiquetados con evidencia. Si al ejecutar la refutación de H3 aparecen otros → escalar antes de tocarlos.

**E. Cuatro fixtures del PR-broken.** Una por check. Contenido y ubicación en las fixtures listadas en §Entregables. No se mergean; viven sólo en la rama del PR-broken.

### Fuera (out)

- `pre-commit` local o cualquier hook cliente — dependencia nueva, requiere ADR (F5).
- Badge de CI en `README.md` — cosmético; sesión de seguimiento cuando el workflow esté estable en `master` y su nombre canónico esté fijado.
- Branch protection rules en la UI de GitHub (require status checks) — paso administrativo del arquitecto humano; fuera del alcance del agente. **Se registra explícitamente en el reporte de cierre como acción pendiente del arquitecto** para que el hallazgo "el CI marca rojo pero no bloquea el merge" no aparezca en una sesión futura como sorpresa.
- `pytest-cov` — sesión C6 del roadmap; requiere F5.
- Publicación en PyPI, contenedor, empaquetado — Fase 5 posterior.
- Refactorización de `tools/pcb.py`, decorador `@mutating_tool`, sanitización de encoders — sesiones 36+.
- Corregir el drift documental restante de `CLAUDE.md` (P1-4).
- Investigar el root cause del mis-labeling (¿qué tool interna shellea a `kicad-cli`?, ¿cómo debería mockearse para un test unit de verdad?). El re-etiquetado a `integration` es la fix de comportamiento correcta; el análisis del root cause es una investigación de causa raíz que amerita su propio documento en `docs/investigacion/`. **Se propone como candidata para la sesión 37 o 38** al cierre.

Si detectás algo indispensable no listado, escalar antes de agregarlo (retrospectiva §5-8).

## Fronteras aplicables

- **F5** — Ninguna dependencia nueva en `pyproject.toml` en esta sesión. Todos los checks usan tooling ya declarado (`ruff`, `mypy`, `pytest`, `uv`).
- **F1 / F3 / F4** — No aplican directamente. Si algún efecto colateral las tocara, escalar.
- **F2** — No aplica (no se declara ni implementa gate nuevo). G2/G4 siguen abiertos como P1-3.

## Criterio de éxito (falsable)

La sesión cierra sí y sólo sí:

1. `.github/workflows/ci.yml` existe en la rama de sesión, sintácticamente válido (validar con `actionlint` si el arquitecto lo tiene local; no dependencia del proyecto).
2. Sobre PR-clean: los cuatro jobs corren y pasan verdes en menos de 15 min. Falsación: cualquier job rojo.
3. Sobre PR-broken: los cuatro jobs corren y **fallan los cuatro** con mensajes que identifican la violación. Falsación: cualquier job verde, o rojo sin causa identificable.
4. Los cuatro comandos del workflow corren con los mismos argumentos que el desarrollador local. Sin discrepancia CI/local.
5. H3 verificada con evidencia: `pytest -m "not integration and not integration_gui and not integration_gui_slow"` sobre la rama de sesión, **sin `kicad-cli` en PATH**, reporta 0 failed. Y con `kicad-cli` en PATH, los 9 tests corren y pasan bajo su nuevo marker `integration`.
6. Docstring de `test_sch.py:1-20` actualizada a reflejar la realidad medida.
7. `pyproject.toml` y `CLAUDE.md` con los parches de H2 aplicados.
8. Reporte de cierre en `docs/historico/sesiones/sesion-35-ci-github-actions.md` con: resultado de H1, resultado de H3 (con conteos), decisiones tomadas (P9), fricciones nuevas, y propuesta concreta para la sesión 36.

**Ninguno de los ocho es opcional.** Si aparece discrepancia al ejecutar local, la sesión no cierra hasta resolverla o escalar.

## Riesgos identificados a priori

- **Latencia del runner.** Si `pytest` tarda demasiado en CI, evaluar cache. No `--timeout` laxo, no `--skip` de tests lentos — si algún test intrínsecamente lento aparece, se marca `slow` y se excluye por filtro con ADR. No aplicar antes de medirlo (P5 del manual).
- **`mypy --strict` distinto CI vs local por versión de mypy.** `uv.lock` fija la versión; `uv sync --frozen` la respeta. Sin cambios en dependencias esta corrida.
- **Los 9 tests reetiquetados dejan de correrse por defecto localmente.** Consecuencia directa de la corrección: el desarrollador que quiera esos tests corre `uv run pytest -m integration` (que ya sabe hacerlo). Esto se debe mencionar en el reporte de cierre y —si aplica— en `CLAUDE.md`, para que un colaborador nuevo no piense "esos tests no existen".
- **Root cause del mis-labeling no resuelto.** Reetiquetar es la fix correcta *de rótulo*, pero el hallazgo subyacente ("una tool declarada disk-only shellea a kicad-cli") queda registrado. Es material para investigación futura, no urgente.

## Entregables esperados

1. `.github/workflows/ci.yml`
2. Diff en `pyproject.toml:33` (parche H2-A)
3. Diff en `CLAUDE.md` (parche H2-B)
4. Diff en `test_sch.py` — 9 markers `unit` → `integration` + docstring corregida
5. Cuatro fixtures del PR-broken, en su rama aparte `sesion/35-pr-broken-canary`, ubicaciones:
   - `src/kicad_mcp/_ci_broken_lint.py` — F401 (import no usado)
   - `src/kicad_mcp/_ci_broken_format.py` — espaciado en firma
   - `src/kicad_mcp/_ci_broken_mypy.py` — return type mismatch
   - `tests/test_ci_broken.py` — `assert False`
6. Los dos PRs (clean y broken), en `draft`, para validación externa
7. Reporte de cierre `docs/historico/sesiones/sesion-35-ci-github-actions.md`
8. Propuesta concreta para sesión 36 al final del reporte

## Drafts disponibles para reutilización

Existen artefactos ya redactados en la conversación previa del arquitecto que el agente **puede reutilizar tal cual o descartar según juicio propio**:

- `ci.yml` completo con las cinco decisiones D-35.1..D-35.5 comentadas al inicio. Requiere una corrección para esta versión revisada: el `pull_request: branches: [main, 'sesion/*']` debe cambiar a `[master, 'sesion*']`.
- Cuatro fixtures del PR-broken con docstrings explicativas.
- `patches-h2.md` con las dos ubicaciones exactas y el criterio de refutación de H2.
- Esqueleto del reporte de cierre con placeholders `⚠️` para los resultados de H1 y H3.

Si el agente los usa, verifica cada uno contra el estado del repo antes de commitear. Si los descarta, escribe todo desde cero — no importa cuál camino elija mientras el resultado cumpla §Criterio de éxito.

## Nota preventiva

Cualquier variante de "hacer que el CI ignore este test", `continue-on-error`, saltear `mypy --strict`, o instalar `kicad-cli` en el runner para que los tests unit-mal-etiquetados pasen — viola el propósito de la sesión y en varios casos alguna frontera. Escalar. El objetivo no es que el CI esté verde: es que el CI diga la verdad sobre el estado del código, y que los rótulos del código digan la verdad sobre lo que hace.

---

**Fin del prompt.** El agente abre la rama `sesion/35-ci-github-actions`, comienza por la verificación de premisa (§P3), y si algún paso falla, reporta y espera decisión antes de continuar.
