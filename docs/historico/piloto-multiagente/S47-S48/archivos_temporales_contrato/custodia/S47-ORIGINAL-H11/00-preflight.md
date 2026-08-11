# 00 — Preflight (Puerta 0) — S47

**Contrato:** `contrato_S47-DT1-SLICE2-CARACTERIZACION_v6.md`, SHA-256
`3b16079cd67357b17ff2d23064c6397454b8a06e4830684c0fa60c2eaac91402`.
**Anexos vinculantes:** fe de erratas SHA-256
`63fe27be8ca2fa852d2f5dfef3996549edcced710b2b67275b970c19a36dcdd4`; auditoría delta SHA-256
`55850fdfb656468fe4758c3b782b7d853ec18d39cc8153ca1d6126ee653ee04a`.
**Nota humana §11.9:** presente en
`/home/astra/Desktop/agent_proyect/archivos_temporales_contrato/nota-invocacion-S47.md`,
firmada, Aprobación = "Gato" (la invocación de Claude Code con la nota constituye la
confirmación expresa). Los tres hashes anteriores fueron reverificados por
`sha256sum` contra los tres archivos referenciados en la nota y coinciden exactamente.
→ **R-P0.10 satisfecha.**

Evidencia cruda de esta sección: `$S47_TMP/raw/git-puerta0.txt`,
`$S47_TMP/raw/env-1-modo.txt`, `$S47_TMP/raw/env-2-versiones-verificar.txt`,
`$S47_TMP/raw/env-3-caches.txt`, `$S47_TMP/raw/env-4-estructura.txt`,
`$S47_TMP/raw/baseline-{1,2,3}-*.txt`.

---

## 1. Identidad y estado git (§5.3)

| Variable | Valor observado |
|---|---|
| `BRANCH_ACTUAL` | `master` |
| `SHA_S47_ENTRADA` (`git rev-parse HEAD`) | `33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b` |
| `git rev-parse --abbrev-ref HEAD` | `master` (no detached) |
| `SHA_REMOTO` (`git rev-parse origin/master`) | `33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b` |
| `STATUS_RAW` (`status --porcelain=v1 -uall`) | vacío |
| `UNSTAGED_FILES` | vacío |
| `STAGED_FILES` | vacío |
| `UNTRACKED_FILES` | vacío |
| `WHITESPACE_WARNINGS` (`diff --check`) | vacío, exit 0 |
| `git log -3` HEAD | `33e32ef` (HEAD -> master, origin/master) Merge PR #18 · `5a6df6f` docs: institucionaliza coordinación híbrida mínima · `d646176` Merge PR #17 |
| `git log -3` origin/master | idéntico al de HEAD |
| `CONFIG_ANTES` | 26 líneas, `git config --local --list --show-origin`, capturadas íntegras en `raw/git-puerta0.txt` |
| `REMOTES_ANTES` | `origin git@github.com:Gato513/kicad-mcp.git (fetch)` / `(push)` |
| `REFS_ANTES` | 54 refs (`heads`+`tags`, sin tags), capturadas íntegras en `raw/git-puerta0.txt`; incluye `refs/heads/master` = `33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b` |
| `INDEX_HASH_ANTES` (`git ls-files -s \| sha256sum`) | `bd9970ae981c776e5f1f2a16c3428e03845cf237a0c7a638f6fc4a709bcaeff5` |
| `WORKTREE_LIST` | una sola worktree: `/home/astra/Desktop/agent_proyect/kicad-mcp`, HEAD `33e32ef…`, branch `refs/heads/master` |

**Aplicación de R-P0.1–R-P0.9:**

| Regla | Condición | Resultado |
|---|---|---|
| R-P0.1 | `BRANCH_ACTUAL != "master"` | NO se activa → OK |
| R-P0.2 | HEAD detached | NO se activa → OK |
| R-P0.3 | `UNSTAGED_FILES` no vacío | NO se activa → OK |
| R-P0.4 | `STAGED_FILES` no vacío | NO se activa → OK |
| R-P0.5 | `UNTRACKED_FILES` no vacío | NO se activa → OK |
| R-P0.6 | `SHA_S47_ENTRADA != SHA_REMOTO` | NO se activa (idénticos) → OK |
| R-P0.7 | `WHITESPACE_WARNINGS` no vacío | NO se activa (registrado, vacío) → OK |
| R-P0.8 | worktree adicional dirty | NO aplica (worktree única, la activa) → OK |
| R-P0.9 | `SHA_S47_ENTRADA` != checkpoint sin ancla autorizada | `SHA_S47_ENTRADA` == ancla de §2 de v6 (`33e32ef…`) == ancla de la nota §11.9 → OK, coincidencia exacta, sin necesidad de invocar la cláusula de divergencia explicable |

## 2. `S47_TMP` — divergencia entre la nota y el entorno (hallazgo P1, ver `04-hallazgos-fuera-de-scope.md`)

```
S47_TMP registrado literalmente en la nota firmada (§11.9): /tmp/tmp.xOUY807dLa.s47
S47_TMP exportado en el shell de la sesión (PRE-0):          /tmp/tmp.ZedgZwIGVl.s47
```

Ambas rutas existen en disco, ambas son directorios `mktemp -d --suffix=.s47` fuera del
working tree (verificado con `realpath`). La ruta de la nota (`.../xOUY807dLa.s47`) está
**vacía** (creada 10:54, sin contenido). La ruta del entorno (`.../ZedgZwIGVl.s47`) es la que
efectivamente recibió `PYTHONPYCACHEPREFIX`, `MYPY_CACHE_DIR`, `RUFF_CACHE_DIR` y
`UV_CACHE_DIR` en el shell real de ejecución (creada 11:07).

**Decisión de la Autoridad (obtenida en esta sesión, antes de ejecutar Puerta 0):** la
Autoridad ratifica `/tmp/tmp.ZedgZwIGVl.s47` como el `S47_TMP` real de esta ejecución de S47;
la línea de la nota es un pegado obsoleto de una ejecución previa de PRE-0. Todas las
verificaciones canónicas de esta Puerta 0 (R-P0.13, R-P0.14, G0.10, G0.11) se evalúan contra
la ruta ratificada. Se registra como hallazgo `DRIFT_DOC` prioridad **P1** en
`04-hallazgos-fuera-de-scope.md` — no bloquea Puerta 0 (no es una de las tres causas de
`NO_GO_ENTRADA` de la Regla 6: no es preflight fallido sobre identidad/estado del repo, no es
mutación, no es violación de scope, no es ausencia de autorización — es un drift documental
de un campo operativo secundario de la nota, resuelto por ratificación expresa de la
Autoridad).

## 3. Entorno (§5.4)

```
REPO_ROOT_CANON  = /home/astra/Desktop/agent_proyect/kicad-mcp
S47_TMP_CANON    = /tmp/tmp.ZedgZwIGVl.s47   (ratificado, ver §2)
```

`S47_TMP_CANON` fuera de `REPO_ROOT_CANON` → OK (R-P0.14).

**Modo de invocación (R-P0.11):**

- `uv --version` → `uv 0.12.0 (b88d7c5c4 2026-07-28 x86_64-unknown-linux-gnu)`
- Modo (a) `uv run --frozen --no-sync python --version` → `Python 3.14.3`, exit 0 →
  **MODE=a** seleccionado.
- Versiones bajo modo (a):
  - `python --version` → `Python 3.14.3`
  - `ruff --version` → `ruff 0.15.20`
  - `mypy --version` → `mypy 2.2.0 (compiled: yes)`
  - `pytest --version` → `pytest 9.1.1`
- Nota informativa: `.venv/bin/python` es un symlink a
  `cpython-3.14+freethreaded-linux-x86_64-gnu/bin/python3.14t` (CPython 3.14 free-threaded).
  Cumple `>= 3.11` (§2 del contrato). No se usó modo (b) porque modo (a) estuvo disponible.

**`scripts/verificar_entorno.py` (R-P0.12):** exit code `0`. Resumen: **13 OK · 3 WARN · 0
FAIL**. VEREDICTO impreso: "listo para integration con kicad-cli (sin GUI)". Los 3 WARN
(`KICAD_MCP_FREEROUTING_JAR` no seteada; socket IPC de KiCad no visible; `npx` no disponible)
son irrelevantes para S47 (S47 no ejecuta rutas `integration`/`integration_gui_slow`, no usa
Freerouting, no usa IPC vivo, no usa el Inspector) y **no bloquean** conforme a CLAUDE.md
("los WARN no bloquean: se anotan en el reporte de sesión"). Salida completa en
`raw/env-2-versiones-verificar.txt`.

**Validación canónica de variables de caché (R-P0.13), contra `S47_TMP_CANON` ratificado:**

| Variable | Valor | Resultado |
|---|---|---|
| `PYTHONPYCACHEPREFIX` | `/tmp/tmp.ZedgZwIGVl.s47/pycache` | OK |
| `MYPY_CACHE_DIR` | `/tmp/tmp.ZedgZwIGVl.s47/mypy-cache` | OK |
| `RUFF_CACHE_DIR` | `/tmp/tmp.ZedgZwIGVl.s47/ruff-cache` | OK |
| `UV_CACHE_DIR` | `/tmp/tmp.ZedgZwIGVl.s47/uv-cache` | OK |
| `PYTEST_ADDOPTS` | `''` (vacía) | OK, neutralizada |
| `GIT_OPTIONAL_LOCKS` | `0` | OK |

→ **R-P0.15 satisfecha** (convención [C]: cubre explícitamente estas dos variables).

## 4. Consistencia estructural (§5.7)

```
AUSENTE g2.py           (src/kicad_mcp/gates/g2.py)     — esperado (§2: "G2, G4: no implementadas")
AUSENTE g4.py           (src/kicad_mcp/gates/g4.py)     — esperado
PRESENTE pcb_encoders.py (src/kicad_mcp/tools/pcb_encoders.py) — obligatorio, G0.15 OK
```

## 5. Baseline actual observado (§5.6)

```bash
uv run --frozen --no-sync ruff check                    # exit 0 — "All checks passed!"
uv run --frozen --no-sync ruff format --check            # exit 0 — "87 files already formatted"
uv run --frozen --no-sync mypy src/                       # exit 0 — "Success: no issues found in 35 source files"
uv run --frozen --no-sync pytest -o "cache_dir=$S47_TMP/pytest-cache" \
    -m "not integration and not integration_gui and not integration_gui_slow" \
    -v --no-header
```

```
BASELINE_ACTUAL_OBSERVADO = {
    passed:      406,
    failed:      0,
    errors:      0,
    deselected:  77,
    skipped:     0,
    collected:   483
}
```

Salida íntegra en `raw/baseline-3-pytest.txt`. Sesión de 42.32 s, sin red, sin KiCad
requerido (ninguna marca `integration*` seleccionada).

**Contraste contra histórico del checkpoint (§2):**

```
HIST_PASSED     = 406   →  observado 406   →  delta 0
HIST_DESELECTED = 77    →  observado 77    →  delta 0
HIST_FAILED     = 0     →  observado 0     →  delta 0
HIST_ERRORS     = 0     →  observado 0     →  delta 0
HIST_COLLECTED  = PENDIENTE_DE_VERIFICACIÓN → observado 483 (HECHO ACTUAL, §5.6 R-BL.5)
HIST_SELECTED   = PENDIENTE_DE_VERIFICACIÓN → observado 406 (HECHO ACTUAL)
HIST_SKIPPED    = PENDIENTE_DE_VERIFICACIÓN → observado 0   (HECHO ACTUAL)
```

**Aplicación de R-BL.0–R-BL.5:**

| Regla | Evaluación | Resultado |
|---|---|---|
| R-BL.0 | `failed > 0` o `errors > 0` | NO se activa (0/0) → continuar |
| R-BL.1 | baseline conforme al histórico | SÍ, delta 0 en passed y deselected → continuar |
| R-BL.2 | checkpoint exacto + drift negativo | NO aplica (checkpoint exacto, drift 0, no negativo) → NO se activa |
| R-BL.3 | SHA alternativo + drift negativo | NO aplica (`SHA_S47_ENTRADA` es el checkpoint exacto, no un SHA alternativo) |
| R-BL.4 | skipped inesperado | `skipped = 0`, sin inesperados → sin hallazgo |
| R-BL.5 | collected sin denominador histórico | `collected = 483` registrado como HECHO ACTUAL, sin denominador histórico previo (`HIST_COLLECTED` era `PENDIENTE_DE_VERIFICACIÓN`) |

## 6. `S47_TMP` — procedencia de v5 (nota, no gate)

`v6` delega en `v5` para §§7.1.3–7.1.5, 7.2, 7.3, 11.2 (V0.1–V0.6), 11.4 (S1–S8), 11.5
(R1–R14), 11.7.bis, 11.8, 13.1/13.2. El archivo `contrato_S47-DT1-SLICE2-CARACTERIZACION_v5.md`
no fue incluido en `archivos_temporales_contrato/`. Se localizó una copia en
`~/.local/share/Trash/files/contrato_S47-DT1-SLICE2-CARACTERIZACION_v5.md` (fuera del
working tree y fuera de `archivos_temporales_contrato/`, en la papelera de reciclaje del
sistema — se leyó sin moverla ni modificarla). Su SHA-256:

```
3fc56ce82ae5c7a396bd667e55228785e2073ea556373846cf0696ed6c75b7a2
```

coincide exactamente con `3fc56ce8…`, el hash que el propio encabezado de v6 (línea 4) cita
como la versión auditada por ChatGPT que dio origen a v6 ("v6 (post-auditoría ChatGPT del
2026-08-08 sobre v5 `3fc56ce8…`)"). Auto-verificación positiva: es la v5 correcta. **Decisión
de la Autoridad:** usar esta copia como fuente normativa para las secciones delegadas,
citando su hash en cada referencia. Hallazgo `DRIFT_DOC` **P2** en
`04-hallazgos-fuera-de-scope.md` (paquete de invocación incompleto: falta el anexo v5).

## 7. Veredicto de Puerta 0

Todas las gates G0.1–G0.16 de §5.8 se satisfacen:

```
G0.1  ✓  Nota humana §11.9 presente y bien formada
G0.2  ✓  BRANCH_ACTUAL == "master"
G0.3  ✓  HEAD no detached
G0.4  ✓  Working tree activo limpio
G0.5  ✓  SHA_S47_ENTRADA == SHA_REMOTO
G0.6  ✓  Sin divergencia con checkpoint (coincidencia exacta)
G0.7  ✓  Worktrees adicionales — no hay otras, única worktree limpia
G0.8  ✓  verificar_entorno.py exit 0
G0.9  ✓  Modo (a) disponible, versiones registradas
G0.10 ✓  Variables de caché validadas canónicamente contra S47_TMP ratificado (§2)
G0.11 ✓  S47_TMP (ratificado) validado canónicamente fuera del working tree
G0.12 ✓  GIT_OPTIONAL_LOCKS=0 y PYTEST_ADDOPTS=''
G0.13 ✓  pytest offline: failed==0, errors==0, conteos obtenidos
G0.14 ✓  R-BL.2 no activada
G0.15 ✓  pcb_encoders.py presente
G0.16 ✓  Snapshots CONFIG_ANTES, REMOTES_ANTES, REFS_ANTES, INDEX_HASH_ANTES capturados
```

**PUERTA 0: GO.** La caracterización READ-ONLY continúa a Fase 1.
