# Sesión 40 — Puerta 0: preparación

## 1. Identificación

- **Fecha:** 2026-08-06, 07:11 -03.
- **Máquina/OS:** Arch Linux, kernel 7.1.5-arch1-2, x86_64.
- **Repo:** `Gato513/kicad-mcp`, remote `origin` = `git@github.com:Gato513/kicad-mcp.git` (SSH, fetch y push).
- **Rama:** `master`.
- **HEAD local:** `99ccbd0a87531aaeb4dcc08c01c89d3b6a9fe2be`.
- **HEAD remoto:** `99ccbd0a87531aaeb4dcc08c01c89d3b6a9fe2be` (idéntico), confirmado en vivo vía `gh api repos/Gato513/kicad-mcp/commits/master` — no vía `git fetch` (ver §4, SSH no operativo en este entorno).
- **Estado del árbol:** limpio de modificados/staged; **17 archivos untracked**, todos documentación de trabajo previa (ver §10). Ningún riesgo de pérdida porque ninguna acción de esta Puerta 0 los toca ni los limpia.
- **Limitaciones de este entorno:**
  - `git fetch`/`git ls-remote` sobre `origin` fallan: `Permission denied (publickey)` — no hay clave SSH cargada ni `ssh-askpass` disponible. El estado remoto se verificó igual, por HTTPS vía `gh api`, con token autenticado (`gh auth status` → cuenta `Gato513`, scopes `repo, workflow`).
  - `.venv` ya presente y funcional; no fue necesario `uv sync` (ver §6).
  - No hay proyecto KiCad ni GUI abiertos; el socket IPC no está visible (confirmado por el propio preflight del proyecto).

## 2. Resumen ejecutivo

El HEAD real de `master` coincide exactamente con el HEAD documental esperado (`99ccbd0a…`) y con el remoto — no hay divergencia, no hay commits nuevos que auditar más allá de los ya documentados. El único cambio entre `90e355f` (post-sesión 39) y `99ccbd0` es, en efecto, `docs/analisis/CONTEXTO_CHAT.md` (708 líneas, solo alta), confirmando la premisa del prompt. Los cuatro comandos canónicos de calidad —`ruff check`, `ruff format --check`, `mypy src/`, `pytest` offline— corren en verde, y el conteo de tests offline (406 passed, 77 deselected) reproduce exactamente la cifra histórica de sesión 39. CI está presente, correctamente configurado (4 jobs independientes, actions pineadas por SHA, permisos mínimos) y el último run sobre este mismo SHA fue éxito 4/4. La protección de `master` está activa con los 4 checks como obligatorios y bloqueo de force-push/deletion, aunque sin revisión de PR obligatoria y con `enforce_admins: false`. No se encontraron secretos trackeados. El preflight del proyecto (`scripts/verificar_entorno.py`) da 12 OK / 4 WARN / 0 FAIL, modo `integration` (kicad-cli disponible, sin socket IPC porque KiCad no está corriendo). El intento de correr la suite `integration` (38 tests) colgó indefinidamente sin socket IPC vivo — se mató por timeout a los 120s con solo 14/38 tests completados; se registra como **no reproducible en este entorno** y no se insiste. Hay drift real y no bloqueante entre `CLAUDE.md` (referencias a `CONTEXT.md` y `hoja-de-ruta-v4.md` en raíz, ambos inexistentes; fase declarada "Fase 3") y el resto de la documentación vigente (`docs/CONTEXT.md`, `hoja-de-ruta-v5.md`, `docs/DECISIONES.md`), que coinciden en que el proyecto está en **Fase 4**. No hay evidencia de un segundo escritor activo (un solo worktree, sin merge/rebase pendiente, sin locks). **Veredicto: GO**, con las mitigaciones de §15.

## 3. Inventario de fuentes consultadas

| Ruta | Estado |
|---|---|
| `CLAUDE.md` | Existe, leído completo (vía contexto de sesión) |
| `.claude/settings.json` | Existe, leído |
| `.claude/settings.local.json` | Existe (no fue necesario abrirlo para el dictamen) |
| `.gitignore` | Existe, leído |
| `pyproject.toml` | Existe, leído |
| `.github/workflows/ci.yml` | Existe, leído completo |
| `docs/analisis/CONTEXTO_CHAT.md` | Existe, inspeccionado (grep dirigido) |
| `docs/BACKLOG.md` | Existe, inspeccionado (grep dirigido DT1/DT2/DT4) |
| `docs/DECISIONES.md` | Existe, inspeccionado (cabecera + fase) |
| `docs/CONTEXT.md` | Existe, leída cabecera |
| `CONTEXT.md` (raíz) | **No existe** — referenciado por `CLAUDE.md` pero ausente |
| `docs/INDEX.md` | Existe, leída cabecera |
| `hoja-de-ruta-v5.md` | Existe, leída cabecera |
| `hoja-de-ruta-v4.md` (raíz) | **No existe** — referenciado por `CLAUDE.md`/`docs/INDEX.md`, archivado en `docs/historico/roadmaps/hoja-de-ruta-v4.md` |
| `docs/adr/` | Existe, 15 ADR (0000–0014) |
| `docs/specs/tool-catalog.md` | Existe (no se auditó línea por línea — fuera de alcance de Puerta 0) |
| `docs/specs/toon-v1.md` | Existe (no se auditó línea por línea) |
| `scripts/verificar_entorno.py` | Existe, leído + ejecutado |
| `docs/historico/sesiones/35-reporte.md` | Existe (referenciado, no releído completo) |
| `docs/historico/sesiones/39-reporte.md` | Existe, leída cabecera y cifras clave |
| `AGENTS.md` | **No existe** |
| `docs/agentes/` | **No existe** |
| `docs/historico/prompts/` | Existe, 42 entradas (17 untracked, ver §10) |
| `docs/historico/sesiones/` | Existe, 45 entradas |

## 4. Verificación Git

Comandos ejecutados y resultado:

```
git remote -v
→ origin  git@github.com:Gato513/kicad-mcp.git (fetch/push)

git branch --show-current
→ master

git rev-parse HEAD
→ 99ccbd0a87531aaeb4dcc08c01c89d3b6a9fe2be

git status --short
→ (0 modificados/staged, 17 untracked — ver §10)

git status --branch --short
→ ## master...origin/master   (sin +N/-N → sin divergencia registrada localmente)

git fetch origin
→ FALLA: ssh_askpass: exec(/usr/lib/ssh/ssh-askpass): No such file or directory
           git@github.com: Permission denied (publickey).
           fatal: Could not read from remote repository.

git rev-parse origin/master
→ 99ccbd0a87531aaeb4dcc08c01c89d3b6a9fe2be   (valor cacheado localmente, coincide con lo confirmado por `gh api` — ver abajo)

git log --oneline --decorate -10 origin/master
→ 99ccbd0 (HEAD -> master, origin/master) Merge PR #11 ... arquitecto/contexto-chat-v2026-08-05
  ec93277 docs(analisis): agrega CONTEXTO_CHAT.md v2026-08-05
  90e355f Merge PR #10 ... errata/adr-0014-conteo-sitios
  08d0431 docs(adr-0014): corrige conteo de sitios de preámbulo (16→17)
  1bc38c6 Merge PR #9 ... sesion/39-mutating-tool-decorator
  c6a71e2 refactor(tools): decorador @mutating_tool ...
  989c505 Merge PR #8 ... sesion/38-cierre-gaps-encoders-ad-hoc
  8c31557 docs(sesion-38): veredictos de candidatos, P1-2 en BACKLOG
  e826de4 test(golden): canarios T5/Z6 ...
  71af76e fix(pcb): sanitiza los componentes de filter_desc ...

git merge-base HEAD origin/master
→ 99ccbd0a87531aaeb4dcc08c01c89d3b6a9fe2be   (== HEAD, == origin/master)

git rev-list --left-right --count HEAD...origin/master
→ 0	0
```

**Sustitución de `git fetch`:** dado que SSH no está disponible en este entorno (falta `ssh-askpass`, sin clave cargada), la sincronización real con el remoto se verificó por HTTPS autenticado:

```
gh auth status
→ Logged in to github.com account Gato513 (keyring); scopes: gist, read:org, repo, workflow

gh api repos/Gato513/kicad-mcp/commits/master --jq '.sha, .commit.committer.date, .commit.message'
→ 99ccbd0a87531aaeb4dcc08c01c89d3b6a9fe2be
  2026-08-05T23:26:17Z
  Merge pull request #11 from Gato513/arquitecto/contexto-chat-v2026-08-05
```

Esto confirma en vivo (no solo desde caché local) que `origin/master` == HEAD local. **No hay divergencia real.**

**Estado del árbol** (`git status --short`, `--untracked-files=all`): 0 archivos modificados, 0 staged, 17 untracked (detalle en §10). Árbol limpio a efectos de "riesgo de pérdida de trabajo" — nada trackeado está sucio.

**Operaciones en curso:**
```
git worktree list        → un solo worktree: /home/astra/Desktop/agent_proyect/kicad-mcp 99ccbd0 [master]
git branch --all         → 40 ramas locales + 10 remotas visibles (histórico de sesiones); ninguna checked out en otro worktree
test -f .git/MERGE_HEAD          → no-merge
test -d .git/rebase-merge        → no-rebase-merge
test -d .git/rebase-apply        → no-rebase-apply
ls .git/*.lock                   → sin locks
```

**Divergencias:** ninguna. HEAD local, HEAD remoto (confirmado vía `gh`) y merge-base coinciden en `99ccbd0`.

## 5. Evolución desde `90e355f` y `99ccbd0`

```
git diff --stat 90e355f..99ccbd0
→  docs/analisis/CONTEXTO_CHAT.md | 708 +++++++++++++++++++++++++++++++++++++++++
    1 file changed, 708 insertions(+)

git diff --name-status 90e355f..99ccbd0
→  A	docs/analisis/CONTEXTO_CHAT.md

git log --oneline 90e355f..99ccbd0
→  99ccbd0 Merge pull request #11 from Gato513/arquitecto/contexto-chat-v2026-08-05
   ec93277 docs(analisis): agrega CONTEXTO_CHAT.md v2026-08-05 para chat arquitecto
```

**Confirmado, no refutado:** la premisa del prompt es exacta. Entre `90e355f` y `99ccbd0` solo se agregó `docs/analisis/CONTEXTO_CHAT.md` (documentación pura, alta de archivo nuevo, sin tocar código/tests/CI/specs/dependencias). No aplica la comparación adicional `99ccbd0..origin/master` porque HEAD == origin/master (§4).

Clasificación del cambio: **documentación**. Sin impacto en código, tests, CI, contratos ni dependencias. Sin impacto sobre el piloto salvo el contenido informativo del propio `CONTEXTO_CHAT.md` (que es justamente uno de los documentos de entrada de esta Puerta 0).

## 6. Entorno

```
python3 --version   → Python 3.14.6
uv --version         → uv 0.12.0 (b88d7c5c4 2026-07-28)
git --version        → git version 2.55.0
kicad-cli version     → 10.0.5
java -version         → openjdk 21.0.12
gh --version          → gh version 2.97.0
```

**Nota F4:** `CLAUDE.md` fija objetivo productivo KiCad **10.0.4** (mínimo compatible 9.0, ADR-0002). El `kicad-cli` disponible en este entorno es **10.0.5** — una versión patch por encima del objetivo declarado. No es una violación de F4 (sigue siendo la serie 10.x, no nightly ni 11), pero es un desvío no registrado en ningún ADR; se anota como P2 en §13.

Variables sensibles (solo presencia, sin exponer valor):
```
KICAD_API_TOKEN=absent
KICAD_MCP_PROJECT=absent
KICAD_MCP_FREEROUTING_JAR=absent
```

**Preflight** (`python3 scripts/verificar_entorno.py`, exit 0):

```
[MODO: integration]
[△ WARN] Rama git            — master con cambios sin commit (los 17 untracked de §10)
[✓ OK  ] Python               3.14.6
[✓ OK  ] Repositorio git      inicializado
[✓ OK  ] uv                   uv 0.12.0
[✓ OK  ] Dependencias Python  mcp + pydantic importables vía uv
[✓ OK  ] kicad-cli             v10.0.5 (objetivo D2 cumplido)
[✓ OK  ] ERC por CLI          disponible
[✓ OK  ] kicad-cli pcb render subcomando presente
[✓ OK  ] Autorouting: java    java 21
[△ WARN] Autorouting: jar     KICAD_MCP_FREEROUTING_JAR no seteada
[✓ OK  ] Autorouting: pcbnew  /usr/bin/python3 importa pcbnew
[△ WARN] Socket IPC de KiCad  no visible (KiCad cerrado o API deshabilitado) — no bloquea MVP solo-lectura
[✓ OK  ] Fixtures validados   001_basico, 002_medio, 003_grande: OK
[✓ OK  ] Fixture 004 (real)   presente
[✓ OK  ] Permisos Claude Code settings.json presente y parseable
[△ WARN] npx (MCP Inspector)  no disponible

MODO detectado: integration
Resumen: 12 OK · 4 WARN · 0 FAIL
VEREDICTO: listo para integration con kicad-cli (sin GUI).
```

**0 FAIL.** Los 4 WARN son remediaciones fuera de mis permisos (abrir KiCad con GUI, setear `KICAD_MCP_FREEROUTING_JAR`, instalar Node) o informativos (rama con untracked). Ninguno bloquea la Puerta 0 ni el alcance típico de sesión 40 (que según `docs/BACKLOG.md` es DT1, refactor de `tools/pcb.py` — no requiere autorouting ni GUI). No fue necesario `uv sync --frozen`: el preflight ya reporta dependencias Python OK y `.venv` preexistente; no se ejecutó para no alterar el entorno sin necesidad.

**Freerouting:** JAR no configurado (WARN, fuera de mis permisos). No se investigó más porque no bloquea DT1.

## 7. Calidad local

Comandos ejecutados exactamente como especifica `CLAUDE.md`/el prompt, sin `--fix` ni mutación de archivos:

| Comando | Exit code | Resultado |
|---|---|---|
| `uv run ruff check` | 0 | "All checks passed!" |
| `uv run ruff format --check` | 0 | "86 files already formatted" |
| `uv run mypy src/` | 0 | "Success: no issues found in 34 source files" (1.4s) |
| `uv run pytest -m "not integration and not integration_gui and not integration_gui_slow"` | 0 | **406 passed, 77 deselected** en 37.25s |

**Comparación con histórico:** `docs/historico/sesiones/39-reporte.md` y `docs/analisis/CONTEXTO_CHAT.md:160` afirman 406 tests offline post-sesión 39. **Reproducido exactamente** en esta corrida (no se trató como cierto sin medir — se ejecutó y coincide).

**Integración** (`uv run pytest -m integration`, 38 tests recolectados en `test_context_delta.py`, `test_export.py`, `test_health.py`, `test_pcb_session30_solder_mask.py`, `test_pcb_session31b_duplicate_refs.py`, `test_sch.py`, `test_state_builder.py`, `test_world_context.py`):

- Varios de estos archivos referencian IPC/socket (`test_context_delta.py`, `test_health.py`, `test_pcb_session30_solder_mask.py`, `test_pcb_session31b_duplicate_refs.py`, `test_sch.py`, `test_world_context.py`, `test_state_builder.py`).
- Con el socket IPC no visible (confirmado por el preflight), el intento de ejecución **colgó**: con timeout de 120s el proceso completó solo 14/38 tests antes de ser matado (exit 124). No hubo fallos rápidos ni skips automáticos — el comando simplemente no termina en tiempo razonable sin KiCad corriendo.
- **Conclusión: la suite `integration` no es reproducible en este entorno** sin abrir KiCad con la API habilitada, lo cual está fuera del alcance y de mis permisos en esta Puerta 0 (restricción explícita: no alterar archivos KiCad, no abrir GUI). Se registra como **pendiente**, no como fallo del código.
- No se ejecutaron `integration_gui` ni `integration_gui_slow` (prohibido explícitamente en el prompt).

## 8. CI

`.github/workflows/ci.yml` (leído completo):

- **Triggers:** `push` (todas las ramas) y `pull_request` sobre `master` y `sesion*`.
- **Permisos:** `contents: read` (mínimo).
- **Concurrencia:** `group: ${{ github.workflow }}-${{ github.ref }}`, `cancel-in-progress: true`.
- **Jobs:** 4, **independientes** (cada uno hace su propio checkout + `uv sync --frozen`, no depende de artefactos de otro): `ruff-check`, `ruff-format`, `mypy`, `pytest-offline`.
- **Python:** 3.11 pineado explícitamente (mínimo soportado por `pyproject.toml: requires-python = ">=3.11"`).
- **`uv sync --frozen`:** presente en los 4 jobs.
- **Filtro pytest:** `uv run pytest -m "not integration and not integration_gui and not integration_gui_slow"` — coincide con el comando canónico de `CLAUDE.md` y con lo ejecutado en §7.
- **Actions:** `actions/checkout` y `astral-sh/setup-uv` pineadas por SHA con comentario de tag (`@3d3c42e...` `# v7.0.1`, `@c771a70...` `# v9.0.0`) — cumple la práctica de seguridad recomendada por GitHub.

**Último run sobre `master`** (vía `gh run list --workflow CI --branch master --limit 5`, y detalle vía `gh run view 31056361487 --json headSha,conclusion,createdAt,jobs`):

```
run 31056361487 · push · headSha 99ccbd0a87531aaeb4dcc08c01c89d3b6a9fe2be
createdAt 2026-08-05T23:26:19Z · conclusion: success
jobs: mypy src/ ✓ · ruff format --check ✓ · pytest (offline) ✓ · ruff check ✓
```

**Relación con HEAD:** el `headSha` del run coincide exactamente con el HEAD local/remoto actual (`99ccbd0`). CI ya validó este SHA exacto en verde, 4/4 jobs, y esta Puerta 0 lo reprodujo localmente de forma independiente (§7) con resultado consistente.

## 9. Branch protection

```
gh api repos/Gato513/kicad-mcp/branches/master/protection
```

- **Protección: activa** (no 404, no denegado — respuesta completa).
- **Checks requeridos** (`strict: true`, refuerza que la rama debe estar actualizada): `ruff check`, `ruff format --check`, `mypy src/`, `pytest (offline)` — coinciden exactamente con los 4 nombres de job del workflow.
- **Aprobación de PR requerida:** la clave `required_pull_request_reviews` **no aparece** en la respuesta → no hay revisión obligatoria configurada.
- **`enforce_admins`: `false`** — un admin puede saltarse la protección (bypass visible).
- **Force-push:** `allow_force_pushes.enabled: false` → bloqueado.
- **Deletion:** `allow_deletions.enabled: false` → bloqueado.
- **Firmas requeridas:** `required_signatures.enabled: false`.
- **Historial lineal:** no forzado.

No hubo error 404 ni ambigüedad de permisos — la respuesta fue completa y autoritativa.

## 10. Artefactos, secretos y archivos locales

**Untracked (17 archivos, todos `.md` salvo uno `.yml`, todos documentación de trabajo, ninguno código/tests/config activa):**

| Ruta | Tamaño |
|---|---|
| `docs/analisis/auditoria-tecnica-integral-2026-08.md` | 56 883 B |
| `docs/analisis/retrospectiva-metodologica-2026-08.md` | 54 070 B |
| `docs/historico/prompts/PROMPT-SESION-32c-investigacion.md` | 29 704 B |
| `docs/historico/prompts/PROMPT-SESION-32d-fix.md` | 29 456 B |
| `docs/analisis/manual-desarrollo-ia-software.md` | 27 774 B |
| `docs/historico/prompts/PROMPT-SESION-31.md` | 26 385 B |
| `docs/historico/prompts/PROMPT-SESION-32.md` | 25 316 B |
| `docs/historico/prompts/PROMPT-SESION-32b-fix.md` | 24 390 B |
| `docs/historico/prompts/PROMPT-SESION-31c-reintento.md` | 22 391 B |
| `docs/historico/prompts/PROMPT-SESION-31b-fix.md` | 19 200 B |
| `docs/historico/prompts/sesion-35-ci-github-actions.md` | 17 759 B |
| `docs/historico/prompts/sesion-38-cierre-gaps-encoders-ad-hoc.md` | 17 561 B |
| `docs/historico/prompts/sesion-39-mutating-tool-decorator.md` | 15 848 B |
| `docs/historico/prompts/sesion-37-gap-espacio-encoders-ad-hoc.md` | 12 907 B |
| `docs/historico/prompts/sesion-36-sanitizacion-encoders-ad-hoc.md` | 11 431 B |
| `docs/historico/drafts/ci.yml` | 3 957 B |
| `docs/historico/drafts/patches-h2.md` | 3 158 B |

Ninguno es un archivo `.env`, clave, backup binario grande o log. `docs/historico/drafts/ci.yml` es un borrador histórico en `docs/historico/`, no el workflow activo (que vive en `.github/workflows/ci.yml`, sí trackeado) — no hay riesgo de shadowing.

**Escaneo de patrones sensibles** (`find` por `.env*`, `*.pem`, `*.key`, `*token*`, `*secret*`, `*.lck`, `_autosave-*`, sin abrir contenido): único match `docs/adr/0004-economia-de-tokens.md` — falso positivo, es un ADR sobre economía de *tokens* de contexto LLM, ya trackeado y de contenido documental.

**`git check-ignore`** sobre `.venv .pytest_cache .mypy_cache .ruff_cache`: los cuatro coinciden con reglas de `.gitignore` (`.venv/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`). `.kicad-mcp` y `scratchpad` **no matchean** con `--no-index` fuera de contexto porque no existen en el árbol de trabajo actual como directorios a ignorar en el momento del check fuera de repo, pero **sí están declarados** en `.gitignore` (`​.kicad-mcp/`, `scratchpad/`) y `git check-ignore -v --no-index scratchpad` confirma el patrón activo (`.gitignore:8:scratchpad/`).

**Hallazgo de higiene (no bloqueante):** `scratchpad/` está en `.gitignore` pero tiene **11 archivos ya trackeados** dentro (`git ls-files scratchpad` → 11, incluyendo `scratchpad/spike-autoroute/artifacts/run1.freerouting.log` y dos PNG). Git seguirá versionándolos porque un archivo ya trackeado no se vuelve a ignorar retroactivamente por una regla de `.gitignore`. No es un secreto ni un riesgo de seguridad, es deuda de higiene documental — se anota como P2.

**`validation-suite/`** (232 archivos) y **`context_cambios.md`** están trackeados intencionalmente (no ignorados, no accidentales).

**`.kicad-mcp/`** no existe actualmente en el árbol de trabajo — no hay riesgo de que se trackee porque el patrón lo cubre si apareciera.

No se abrió el contenido de ningún archivo sensible; solo se listaron rutas y tamaños.

## 11. Contradicciones documentales

| Tema | Fuente A | Fuente B | Resolución provisional | Severidad |
|---|---|---|---|---|
| Fuente de estado del ciclo | `CLAUDE.md:11,143,186` → `CONTEXT.md` (raíz, **no existe**) | `docs/CONTEXT.md` (existe, consolidado post-sesión 24) | Usar `docs/CONTEXT.md` — es el único archivo real con ese rol | Documental no bloqueante |
| Hoja de ruta vigente | `CLAUDE.md:157,180`, `docs/INDEX.md:15,44,47` → `hoja-de-ruta-v4.md` (raíz, **no existe**) | `hoja-de-ruta-v5.md` (raíz, existe; v4 archivada en `docs/historico/roadmaps/`) | Usar `hoja-de-ruta-v5.md` — `docs/DECISIONES.md` (D-30.1/D-30.2) y el propio `hoja-de-ruta-v5.md` la confirman como vigente | Documental no bloqueante |
| Fase actual del proyecto | `CLAUDE.md:186` → "Fase 3 (consolidación), 2026-07-23" | `hoja-de-ruta-v5.md` cabecera → "Fase 4, arranca post-sesión 29, 2026-07-25"; `docs/DECISIONES.md` D-30.1/D-30.2 confirman Fase 4 | Fase 4 es la vigente — `CLAUDE.md` quedó desactualizado tras el cierre de Fase 3 (sesión 29+) | Documental no bloqueante |
| Existencia y estado de CI | `CLAUDE.md` no menciona CI ni branch protection en ninguna sección | `.github/workflows/ci.yml` existe y está activo desde sesión 35; branch protection activa (§9) | El código/config real gana — CI existe y funciona, `CLAUDE.md` simplemente no lo documenta (omisión, no contradicción activa) | Documental no bloqueante |
| Sitios de preámbulo transversal (DT2) | `docs/historico/sesiones/39-reporte.md:181` y cuerpo → "16 sitios" | ADR-0014 corregido por commit `08d0431` → 17 sitios (conteo correcto) | Usar ADR-0014 post-`08d0431` (17) — el reporte de sesión 39 quedó con el número pre-corrección | Histórica deliberada (ya hay un commit de errata que la reconoce) |
| Estado de DT1/DT2/DT4 | `docs/BACKLOG.md:504` y `docs/analisis/CONTEXTO_CHAT.md:229-232` | Coinciden entre sí: DT1 abierto (candidato sesión 40), DT2 cerrado sesión 39, DT4 cerrado sesiones 36-38 | Sin contradicción — ambas fuentes alineadas | N/A |
| Referencia a `KICAD_MCP_PROJECT` vs. board vivo en GUI | Memoria de sesiones previas (`kicad-mcp-env-project-mismatch`) advierte que `run_drc`/`route_board` resuelven por env var fija mientras `get_world_context` usa IPC vivo | No contradicho por ningún documento del HEAD actual — sigue siendo válido como riesgo operativo | No es una contradicción documental sino un riesgo latente conocido; no aplica a DT1 (refactor de encoders, sin autorouting) | N/A — riesgo operativo, no drift |

**¿La precedencia provisional del prompt (§P0.8) resuelve las contradicciones?** Sí. Aplicando el orden código/config del SHA base → specs/tests/ADR → `DECISIONES.md` → `BACKLOG.md` → `CONTEXTO_CHAT.md` → `CLAUDE.md` (solo reglas estables) → históricos, las seis filas de la tabla se resuelven sin ambigüedad: ninguna requiere intervención humana antes de empezar sesión 40, porque en todos los casos hay una fuente de rango superior que ya zanja la discrepancia. La única regla estable de `CLAUDE.md` que sigue vigente sin contradicción es todo lo que no depende de "qué sesión/fase estamos" (comandos, fronteras F1-F5, reglas de código, DoD) — eso se mantiene como autoritativo.

## 12. Preparación multiagente

```
git worktree list        → 1 worktree (este), sin otros activos sobre el mismo árbol
git branch --all         → 40 locales + 10 remotas, ninguna checked out concurrentemente
git status                → limpio de merge/rebase
test -f .git/MERGE_HEAD          → ausente
test -d .git/rebase-merge        → ausente
test -d .git/rebase-apply        → ausente
```

- **`AGENTS.md`:** no existe. **`docs/agentes/`:** no existe. Ninguno se creó (fuera de alcance de esta Puerta 0).
- **Sin evidencia de otro proceso automático modificando el repo:** un solo worktree, sin locks, sin operación pendiente.
- **Esquema propuesto (Claude Code único escritor; Codex revisor sin edición; ChatGPT auditor/reconciliador; Claude Chat arquitecto; humano autoridad) es operable tal cual está el repo hoy:** no requiere `AGENTS.md` para funcionar si Codex recibe el contexto por prompt en cada invocación (tal como ya ocurre con `CONTEXTO_CHAT.md` para el chat arquitecto). La ausencia de `AGENTS.md` es un P1 mitigable, no un bloqueador.
- **Confirmación de un único escritor activo ahora mismo:** sí — esta sesión (Claude Code, Sonnet 5/Opus 5 en este entorno) es el único proceso tocando el árbol de trabajo en este momento; no hay indicios de otro agente con cambios pendientes de commit distintos a los 17 untracked ya inventariados (que son de sesiones humanas/anteriores, no de un escritor concurrente activo).

## 13. Bloqueadores

### P0

Ninguno identificado.

### P1

1. **17 archivos untracked sin respaldo en Git** (§10). Mitigación: no requieren acción antes de sesión 40 en sí — DT1 no los toca. El humano decide si commitearlos o mantenerlos fuera de control de versiones antes de que crezca el riesgo de pérdida.
2. **Drift de `CLAUDE.md`/`docs/INDEX.md`** (rutas a `CONTEXT.md` y `hoja-de-ruta-v4.md` en raíz, ambas inexistentes; fase declarada "Fase 3" cuando el resto de la documentación dice Fase 4) (§11). Mitigación: aplicar la precedencia provisional del prompt — ya resuelve las seis contradicciones sin bloquear. No se edita `CLAUDE.md` en esta Puerta 0 (fuera de alcance explícito).
3. **Suite `integration` no reproducible en este entorno** (§7) — cuelga sin socket IPC vivo. Mitigación: no es gate de DT1 (refactor de encoders en `tools/pcb.py`, sin tocar rutas de autorouting/IPC en vivo); si DT1 llegara a tocar código cubierto por esos 38 tests, se requeriría abrir KiCad con API habilitada antes de considerar el trabajo verificado — responsabilidad del humano, fuera de mis permisos.
4. **Sin `AGENTS.md` para Codex** (§12). Mitigación: operable por prompt explícito en cada invocación, como ya se hace con el chat arquitecto.
5. **`git fetch`/`push` por SSH inoperante en este entorno** (§4). Mitigación: lectura verificada por `gh` (HTTPS); el push real lo hace el humano de todas formas (regla de `CLAUDE.md`: "Nunca push").

### P2

1. `kicad-cli` local es 10.0.5, un patch por encima del objetivo declarado en F4 (10.0.4) — no hay ADR que registre este desvío de versión (§6).
2. 11 archivos ya trackeados dentro de `scratchpad/` pese a estar en `.gitignore` — deuda de higiene, no riesgo de secreto (§10).
3. `branch protection` sin revisión de PR obligatoria y con `enforce_admins: false` (§9) — mejora recomendable para un piloto multiagente con más de un escritor humano potencial, no bloqueante para este piloto de escritor único.
4. `remotes/origin/HEAD` apunta a `sesion-01` localmente, mientras el `default_branch` real del repo (confirmado vía `gh api repos/Gato513/kicad-mcp --jq .default_branch`) es `master` — desalineación de metadata local de Git, no afecta ninguna operación de esta Puerta 0 (ya documentada en memoria de sesiones previas).
5. `docs/historico/sesiones/39-reporte.md` retiene la cifra pre-errata de "16 sitios" en el cuerpo del texto pese al commit `08d0431` que corrige a 17 (§11) — coherente con la práctica del proyecto de no reescribir históricos.

## 14. Veredicto

```
GO
```

Justificación contra el criterio del prompt: no hay P0; los 5 P1 tienen mitigación concreta y no requieren acción bloqueante antes de empezar (documentada arriba); HEAD (`99ccbd0`) y rama (`master`) están identificados sin ambigüedad y confirmados por dos vías independientes (Git local + `gh api`); árbol limpio de cambios trackeados; el preflight del proyecto da 0 FAIL; los cuatro comandos canónicos corrieron en verde con cifras que reproducen exactamente el histórico (406 tests); CI existe, está bien configurado y su último run sobre este mismo SHA fue éxito 4/4, sin contradecir lo verificado localmente; un único escritor está confirmado activo (§12); rollback es posible (rama de trabajo nueva desde `master`, sin tocar `master` directamente, con push controlado por el humano).

## 15. Acciones humanas obligatorias

1. Ninguna es estrictamente bloqueante para abrir sesión 40 con el alcance DT1 (refactor de `tools/pcb.py`, sin autorouting/IPC en vivo).
2. Si sesión 40 llegara a necesitar la suite `integration` como gate: abrir KiCad 10.0.5 con la API habilitada (Preferences → Plugins → Enable API server) antes de considerar esos 38 tests como evidencia.
3. Decidir qué hacer con los 17 archivos untracked (commitear en una rama de documentación o mantenerlos fuera de Git) — no urgente pero recomendable antes de que crezcan más.
4. Si se quiere blindar el piloto multiagente contra un segundo escritor humano futuro: considerar activar `required_pull_request_reviews` en la protección de `master` (hoy ausente) — mejora, no bloqueante.
5. Ninguna acción sobre `CLAUDE.md` se pide en esta Puerta 0 (fuera de alcance explícito); queda para una sesión de mantenimiento documental futura.

## 16. Evidencia reproducible

```bash
git remote -v
git branch --show-current
git rev-parse HEAD
git status --short --untracked-files=all
git status --branch --short
git merge-base HEAD origin/master
git rev-list --left-right --count HEAD...origin/master
gh auth status
gh api repos/Gato513/kicad-mcp/commits/master --jq '.sha, .commit.committer.date, .commit.message'
git diff --stat 90e355fb9e1700571b7d40c2f9347c52e5370635..99ccbd0a87531aaeb4dcc08c01c89d3b6a9fe2be
git diff --name-status 90e355fb9e1700571b7d40c2f9347c52e5370635..99ccbd0a87531aaeb4dcc08c01c89d3b6a9fe2be
git worktree list
test -f .git/MERGE_HEAD; test -d .git/rebase-merge; test -d .git/rebase-apply
python3 scripts/verificar_entorno.py                          # exit 0, 12 OK · 4 WARN · 0 FAIL
uv run ruff check                                              # exit 0
uv run ruff format --check                                     # exit 0
uv run mypy src/                                                # exit 0
uv run pytest -m "not integration and not integration_gui and not integration_gui_slow"
                                                                 # exit 0, 406 passed, 77 deselected, 37.25s
uv run pytest -m integration --collect-only -q                 # 38 tests recolectados
timeout 120 uv run pytest -m integration -q                    # exit 124 (timeout), 14/38 completados — no reproducible sin KiCad vivo
gh run list --workflow CI --branch master --limit 5
gh run view 31056361487 --json headSha,conclusion,createdAt,jobs
gh api repos/Gato513/kicad-mcp/branches/master/protection
gh api repos/Gato513/kicad-mcp --jq '{default_branch, private, visibility}'
find . -maxdepth 3 -type f \( -name ".env" -o -name ".env.*" -o -name "*.pem" -o -name "*.key" -o -name "*token*" -o -name "*secret*" -o -name "*.lck" -o -name "_autosave-*" \) -print
```

## 17. Afirmaciones no verificadas

- Contenido completo de `docs/specs/tool-catalog.md` y `docs/specs/toon-v1.md` — se confirmó su existencia y tamaño, no se auditó cada línea (fuera de alcance de una Puerta 0 de preparación).
- Contenido completo de `docs/historico/sesiones/35-reporte.md` — solo referenciado, no releído íntegro en esta sesión (ya cubierto por evidencia directa de CI en §8).
- El comportamiento exacto de los 38 tests `integration` cuando KiCad **sí** está corriendo con API habilitada — no se pudo observar en este entorno; se sabe que sesión 39 los reportó "38/38 verde" bajo esas condiciones, pero esta Puerta 0 no lo remidió (tratado como histórico, no como medición actual, conforme a la restricción del prompt).
- El comportamiento de `uv sync --frozen` en este entorno — no se ejecutó porque el preflight no lo señaló como remediación necesaria (dependencias ya OK); no se puede afirmar que el lock esté 100% sincronizado sin ejecutarlo, solo que las dependencias declaradas ya son importables.
- Estado de `.claude/settings.local.json` — se confirmó su existencia pero no se leyó su contenido (no era necesario para el dictamen y podría contener configuración local no relevante a Puerta 0).

## 18. Próxima acción recomendada

Proceder a abrir sesión 40 (DT1: refactor de `tools/pcb.py`) sobre una rama nueva desde `master` (`99ccbd0`), siguiendo la práctica habitual del proyecto (`sesion/40-<nombre-descriptivo>`). Antes de tocar los tres encoders ad-hoc mencionados en `CLAUDE.md` regla 6, releer `docs/analisis/CONTEXTO_CHAT.md` §"DT1: partir tools/pcb.py" (líneas ~594-620) para el estado de la discusión arquitecto/humano sobre el alcance exacto, y `docs/BACKLOG.md:500-511` para la relación de precedencia DT1↔DT2 ya cerrada. No se requiere ninguna acción humana previa de las listadas en §15 para empezar con ese alcance.
