# CONTRATO ARQUITECTÓNICO DE SESIÓN
## `S47-DT1-SLICE2-CARACTERIZACION` — v6

**Versión:** v6 (post-auditoría ChatGPT del 2026-08-08 sobre v5 `3fc56ce8…`)
**Estado:** DRAFT del Arquitecto principal, listo para sexta auditoría de ChatGPT.
**Naturaleza:** READ-ONLY DE FUENTES Y ESTADO AUTORITATIVO. Definición precisa en §5.
**Autor:** Arquitecto principal (Claude Chat).
**Ejecutor previsto:** Claude Code. **Revisor:** Codex. **Auditor:** ChatGPT. **Autoridad:** Humano.

**Changelog v5 → v6 (respuesta a la auditoría):**

- BLOCKER-01: Regla exhaustiva para mezcla `NO_APTO + NO_CLASIFICABLE` sin APTO → `EVIDENCIA_INSUFICIENTE`.
- BLOCKER-02: F-DT.2 rediseñada como marcador `CONSUMIDOR_MONKEYPATCH_OBLIGATORIO`. NO refuta automáticamente; exige ficha completa y evaluación de R4/R14/E3.
- BLOCKER-03: Introducción de `M2_estado_actual(K)` y `M2_estado_proyectado(K, diseño)` con modelo de fronteras homogéneo, unidad de conteo por dimensión y ejemplo antes/después.
- BLOCKER-04: Tabla normativa de mapping excepción → gates dispensables. Semántica formal de `APTO_CONDICIONAL` con dispensas nominales.
- MAJOR-01: F-DT.1 pasa a `EXCLUSION_CATEGORIAL_INSTITUCIONAL` (no refutación). Nuevo contador `N_excluidos_institucional`.
- MAJOR-02: Nuevo estado `GO_DENTRO_DEL_PRESUPUESTO` cuando universo no evaluado exhaustivamente.
- MAJOR-03: `CONTRACT.sha256` con formato normativo y semántica de verificación (V0.4 verifica archivo, V0.5 compara con hash aprobado por ChatGPT).
- MAJOR-04: `GIT_OPTIONAL_LOCKS=0` exportado. Hash del index en invariantes protegidas.
- MAJOR-05: `UV_CACHE_DIR` validado canónicamente como el resto de caches.
- MAJOR-06: `PYTEST_ADDOPTS=''` + `-o "cache_dir=..."` explícita en invocación.
- MAJOR-07: Prescripción S48 usa clones externos (no worktrees ligadas), manifiesto de tracked files con SHA-256+modo, igualdad exacta tras reverse.
- MAJOR-08: Política cerrada de resolución AST + `REFERENCIA_AMBIGUA` como estado explícito.
- MINOR-01: R-P0.8 única regla sobre worktrees; G0.7 armonizado.
- MINOR-02: Nota humana con una sola referencia al contrato (hash).
- MINOR-03: §11.1 dice "delta concreto propuesto" (no "aprobado específicamente").
- MINOR-04: Changelog consistente con estados del cuerpo.

---

## 1. Objetivo

Rederivar, sobre HEAD actual de `master`, la caracterización comparativa estructural de `src/kicad_mcp/tools/pcb.py` posterior a DT1 Slice 1, y **determinar si existe un candidato ganador para una futura sesión de caracterización de detalle**.

S47 es la primera de la secuencia canónica (§18):

```
S47 → caracterización comparativa (READ-ONLY, esta sesión)
S48 → caracterización de detalle del ganador (READ-ONLY, requiere nueva autorización humana)
S49 → implementación (requiere nueva autorización humana; no se diseña aquí)
```

**S47 no autoriza implementación.**

### 1.1 Siete estados de salida

```
NO_GO_ENTRADA               → no fue posible iniciar una caracterización
                              válida (Puerta 0 falla o ausencia de nota).
EVIDENCIA_INSUFICIENTE      → la investigación no permite decidir con la
                              evidencia obtenida dentro del presupuesto.
NO_GO                       → investigación completa (universo evaluado
                              exhaustivamente); TODOS los candidatos del
                              universo fueron refutados.
NO_GO_POR_PRESUPUESTO       → F-DT.3/F-DT.4 o F-DT.1 excluyeron candidatos
                              sin refutación; todos los evaluados NO_APTO.
                              Reintentable por H11.
GO                          → existe APTO demostrado (§11.4) sobre un
                              universo evaluado exhaustivamente
                              (N_excluidos_presup == 0 Y
                               N_excluidos_institucional == 0).
GO_DENTRO_DEL_PRESUPUESTO   → existe APTO demostrado pero
                              N_excluidos_presup > 0 o
                              N_excluidos_institucional > 0.
                              El candidato es el mejor del subconjunto
                              EVALUADO, no del universo total.
GO_CONDICIONAL_PROPUESTO    → NO existe candidato APTO y existe al menos
                              uno APTO_CONDICIONAL con excepción de §11.7.
                              La instancia concreta NO está autorizada
                              por la nota pre-S47; su aprobación queda
                              reservada al humano tras revisión de Codex
                              y reconciliación de ChatGPT (H2-bis).
```

Precedencia estricta en §11.3.

Cualquier estado negativo (`NO_GO_ENTRADA`, `EVIDENCIA_INSUFICIENTE`, `NO_GO`, `NO_GO_POR_PRESUPUESTO`) es un resultado válido.

**Nota terminológica:** el estado autorizado `GO_CONDICIONAL` (que produciría autorización de S48) solo puede ser emitido por el humano tras aprobación específica de la instancia de excepción. S47 nunca emite `GO_CONDICIONAL` autorizado.

---

## 2. Contexto mínimo asumido como checkpoint (no como HECHO ACTUAL)

```
Repo:              github.com/Gato513/kicad-mcp
Branch:            master
SHA esperado:      33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
Versión paquete:   0.1.0
KiCad objetivo:    10.0.4 (mínimo declarado 9.0)   [F4]
Python:            >= 3.11

CI baseline hist. (categorías del checkpoint):
    HIST_PASSED       = 406
    HIST_DESELECTED   = 77
    HIST_FAILED       = 0    (implícito)
    HIST_ERRORS       = 0    (implícito)
    HIST_COLLECTED    = PENDIENTE_DE_VERIFICACIÓN
    HIST_SELECTED     = PENDIENTE_DE_VERIFICACIÓN
    HIST_SKIPPED      = PENDIENTE_DE_VERIFICACIÓN

DT1 Slice 1:       cerrada (extracción a pcb_encoders.py)
DT1 Slice 2:       no caracterizada, no autorizada
DT2, DT4:          cerradas en su alcance
P1-2, DT3:         abiertas, SEGREGADAS de DT1
G2, G4:            no implementadas (HTTP 404 histórico)
```

Documentos autoritativos vigentes:

```
specs / ADR / F1–F5 / G1–G5
        ↓
AGENTS.md
        ↓
CLAUDE.md
        ↓
docs/BACKLOG.md
        ↓
hoja-de-ruta-v5.md
        ↓
docs/historico/sesiones/41-reporte.md
        ↓
contrato S47 v6 (este documento)
```

Fronteras recordadas: **F1** specs/goldens inmutables; **F2** gates G1–G5 no modificables; **F3** códigos de error son API pública; **F4** KiCad 10.0.4 objetivo; **F5** sin dependencias nuevas.

---

## 3. Hipótesis a evaluar

| ID | Hipótesis | Refutable si… |
|----|---|---|
| **H1** | El grafo de referencias tipadas admite al menos un cluster cohesivo, dependency-closed, superficie-neutral y reversible-preliminar. | Ningún cluster con ficha cumple simultáneamente §11.4 S1–S8. |
| **H2** | Al menos uno de los priors históricos sigue vigente. | Todos caen por al menos un criterio §11.5. |
| **H3** | Los tests actuales bastan sin ampliar la suite. | Existe al menos un camino relevante en `COBERTURA_INFERIDA` o `COBERTURA_DESCONOCIDA`. |
| **H4** | La reducción de LOC de `register()` es por sí sola proxy suficiente de deuda. | Un candidato con alta reducción M1 donde M2 no domina en al menos una dimensión, o M3/M4 no mejoran. Un contraejemplo basta. |

---

## 4. Criterios de refutación explícitos

```
CR1  Priors de S40 siguen siendo los tres mejores.
CR2  Cifras de LOC reducibles del contexto siguen válidas post-Slice 1.
CR3  Dependencias listadas en S40 no han cambiado.
CR4  Consumidores privados siguen siendo los conocidos.
CR5  Monkeypatches históricos siguen siendo los únicos relevantes.
CR6  Extraer una closure es preferible a extraer helpers top-level.
CR7  "Reducción de LOC de register()" es proxy suficiente de deuda.
CR8  Ausencia de fallos de tests es prueba de suficiencia de cobertura.
```

Registro: `REFUTADA`, `NO REFUTADA`, `INSUFICIENTE_EVIDENCIA`.

---

## 5. Preparación pre-S47 y Puerta 0

### 5.1 Definición precisa de READ-ONLY

```
READ-ONLY DE FUENTES Y ESTADO AUTORITATIVO

  Estado NO alterado por S47:
    - contenido de tracked files
    - rama activa
    - HEAD, index (verificado por hash del index en §13.3)
    - configuración Git (git config --local)
    - remotes (git remote -v)
    - refs locales: branches y tags (git show-ref)
    - .venv (previamente sincronizada por preparación pre-S47)

  Mutaciones EFÍMERAS PERMITIDAS, expresamente enumeradas:
    - archivos en $S47_TMP (fuera del working tree)
    - caches Python (__pycache__) redirigidos vía
      PYTHONPYCACHEPREFIX a $S47_TMP
    - caches mypy, ruff, pytest, uv redirigidas a $S47_TMP
      (validación canónica en §5.4)

  Endurecimiento operativo:
    - GIT_OPTIONAL_LOCKS=0 exportado en el shell de la sesión
      para evitar refresco de index durante lecturas.
    - Todas las variables de cache validadas canónicamente
      dentro de $S47_TMP antes de invocar cualquier herramienta.
    - PYTEST_ADDOPTS=''  (neutralizada; opciones de cache pasadas
                          explícitamente por -o).

  NO permitido dentro de S47:
    - git en forma mutante: fetch, switch, checkout, pull, commit,
      push, merge, reset, stash, rebase, apply (ninguna forma),
      branch mutante, tag mutante, config mutante,
      worktree add/remove (solo `worktree list --porcelain` permitido).
    - uv sync, uv add, uv remove, uv lock
    - cualquier modificación de refs remotas o locales
    - cualquier archivo dentro del working tree del repo
    - fallback mutante: ni modo (a) ni modo (b) → NO_GO_ENTRADA
```

### 5.2 Preparación pre-S47 (responsabilidad humana)

```
PRE-0  Exportar en el shell de la sesión:
         export GIT_OPTIONAL_LOCKS=0
         export PYTEST_ADDOPTS=''
         export S47_TMP=<ruta absoluta canónica fuera del working tree>
         export PYTHONPYCACHEPREFIX=$S47_TMP/pycache
         export MYPY_CACHE_DIR=$S47_TMP/mypy-cache
         export RUFF_CACHE_DIR=$S47_TMP/ruff-cache
         export UV_CACHE_DIR=$S47_TMP/uv-cache
       Nota: la nota humana §11.9 registra la ruta S47_TMP exacta.
PRE-1  Rama `master` activa.
PRE-2  HEAD == origin/master (git fetch + verificación).
PRE-3  Working tree limpio.
PRE-4  Entorno sincronizado (uv sync --frozen exitoso).
PRE-5  pcb_encoders.py presente.
PRE-6  Modo de invocación no-sync disponible: (a) uv run --frozen
       --no-sync o (b) binarios directos en .venv/bin/*.
PRE-7  Nota de invocación humana producida (§11.9).
PRE-8  $S47_TMP creado y validado canónicamente fuera del working
       tree.
```

### 5.3 Verificación observacional — Git

**Con `GIT_OPTIONAL_LOCKS=0` en el entorno.**

```bash
# Identidad de rama y HEAD
git branch --show-current                                 # BRANCH_ACTUAL
git rev-parse HEAD                                        # SHA_S47_ENTRADA
git rev-parse --abbrev-ref HEAD                           # confirma no detached
git rev-parse origin/master                               # SHA_REMOTO

# Estado del working tree
git status --porcelain=v1 --untracked-files=all           # STATUS_RAW
git diff --name-only                                      # UNSTAGED_FILES
git diff --cached --name-only                             # STAGED_FILES
git ls-files --others --exclude-standard                  # UNTRACKED_FILES
git diff --check                                          # WHITESPACE_WARNINGS

# Trazabilidad
git log -3 --oneline --decorate HEAD
git log -3 --oneline --decorate origin/master

# Snapshots de invariantes protegidas por READ-ONLY (CIERRE-CAPTURA)
git config --local --list --show-origin                   # CONFIG_ANTES
git remote -v                                             # REMOTES_ANTES
git show-ref --heads --tags                               # REFS_ANTES

# Hash del index (garantía adicional de no alteración)
git ls-files -s | sha256sum                               # INDEX_HASH_ANTES

# Worktrees adicionales
git worktree list --porcelain                             # WORKTREE_LIST
# Por cada worktree distinta de la activa:
#   git -C <ruta> status --porcelain=v1 --untracked-files=all
#   git -C <ruta> rev-parse HEAD
#   git -C <ruta> branch --show-current
```

### 5.4 Verificación observacional — Entorno

**Resolución canónica de rutas:**

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
REPO_ROOT_CANON="$(realpath "$REPO_ROOT")"
S47_TMP_CANON="$(realpath "$S47_TMP")"

case "$S47_TMP_CANON/" in
    "$REPO_ROOT_CANON"/*)
        echo "FAIL: S47_TMP dentro del working tree"; exit 1 ;;
    *)  echo "OK: S47_TMP fuera del working tree" ;;
esac
```

**Versiones (registrar salida y exit code):**

```bash
uv --version

if uv run --frozen --no-sync python --version 2>/dev/null; then
    MODE="a"
    PY="uv run --frozen --no-sync python"
    RUFF="uv run --frozen --no-sync ruff"
    MYPY="uv run --frozen --no-sync mypy"
    PYTEST="uv run --frozen --no-sync pytest"
elif [ -x .venv/bin/python ] && [ -x .venv/bin/ruff ] \
  && [ -x .venv/bin/mypy ] && [ -x .venv/bin/pytest ]; then
    MODE="b"
    PY=".venv/bin/python"
    RUFF=".venv/bin/ruff"
    MYPY=".venv/bin/mypy"
    PYTEST=".venv/bin/pytest"
else
    echo "FAIL: ni modo (a) ni modo (b)"; exit 1
fi
echo "MODE=$MODE"

$PY --version
$RUFF --version
$MYPY --version
$PYTEST --version

$PY scripts/verificar_entorno.py
```

**Validación de caches (todas las variables):**

```bash
for V in PYTHONPYCACHEPREFIX MYPY_CACHE_DIR RUFF_CACHE_DIR UV_CACHE_DIR; do
    if [ -z "${!V}" ]; then
        echo "FAIL: $V no definida"; exit 1
    fi
    RUTA_CANON="$(realpath -m "${!V}")"
    case "$RUTA_CANON/" in
        "$S47_TMP_CANON"/*|"$S47_TMP_CANON") echo "OK: $V" ;;
        *) echo "FAIL: $V fuera de S47_TMP: $RUTA_CANON"; exit 1 ;;
    esac
done

# PYTEST_ADDOPTS explícitamente neutralizada
if [ -n "$PYTEST_ADDOPTS" ]; then
    echo "FAIL: PYTEST_ADDOPTS debe ser cadena vacía, no '$PYTEST_ADDOPTS'"
    exit 1
fi
echo "OK: PYTEST_ADDOPTS neutralizada"

# GIT_OPTIONAL_LOCKS
if [ "$GIT_OPTIONAL_LOCKS" != "0" ]; then
    echo "FAIL: GIT_OPTIONAL_LOCKS != 0"; exit 1
fi
echo "OK: GIT_OPTIONAL_LOCKS=0"
```

Cualquier `FAIL` en §5.4 → `NO_GO_ENTRADA`.

### 5.5 Reglas de interpretación de Puerta 0

```
R-P0.1  BRANCH_ACTUAL != "master"                       → NO_GO_ENTRADA
R-P0.2  HEAD detached                                    → NO_GO_ENTRADA
R-P0.3  UNSTAGED_FILES no vacío                          → NO_GO_ENTRADA
R-P0.4  STAGED_FILES no vacío                            → NO_GO_ENTRADA
R-P0.5  UNTRACKED_FILES no vacío                         → NO_GO_ENTRADA
R-P0.6  SHA_S47_ENTRADA != SHA_REMOTO                    → NO_GO_ENTRADA
R-P0.7  WHITESPACE_WARNINGS no vacío                     → registrar
R-P0.8  Worktree adicional con estado dirty              → NO_GO_ENTRADA
        (Única regla sobre worktrees adicionales. Una worktree limpia
         en otra rama NO bloquea; solo se registra.)
R-P0.9  SHA_S47_ENTRADA != checkpoint SIN ancla
        alternativa autorizada en §11.9                  → NO_GO_ENTRADA
R-P0.10 Nota humana §11.9 ausente o mal formada          → NO_GO_ENTRADA
R-P0.11 Ni modo (a) ni modo (b) disponibles              → NO_GO_ENTRADA
R-P0.12 verificar_entorno.py exit != 0                   → NO_GO_ENTRADA
R-P0.13 Alguna variable de cache no dentro de $S47_TMP   → NO_GO_ENTRADA
R-P0.14 $S47_TMP dentro del working tree                 → NO_GO_ENTRADA
R-P0.15 GIT_OPTIONAL_LOCKS != 0 o PYTEST_ADDOPTS != ''   → NO_GO_ENTRADA
```

### 5.6 Baseline actual observado

```bash
$RUFF check
$RUFF format --check
$MYPY src/
$PYTEST -o "cache_dir=$S47_TMP/pytest-cache" \
        -m "not integration and not integration_gui and not integration_gui_slow" \
        -v --no-header
```

Notar el `-o "cache_dir=..."` explícito. `PYTEST_ADDOPTS` está neutralizada.

Registro:

```
BASELINE_ACTUAL_OBSERVADO = {
    passed:      <n>,
    failed:      <n>,
    errors:      <n>,
    deselected:  <n>,
    skipped:     <n>,
    collected:   <n>   ← HECHO ACTUAL, NO gate contra histórico
}
```

Reglas R-BL.0 a R-BL.5 idénticas a v5:

```
R-BL.0 failed > 0 o errors > 0                → NO_GO_ENTRADA
R-BL.1 baseline conforme al histórico         → continuar
R-BL.2 checkpoint exacto + drift negativo     → NO_GO_ENTRADA
R-BL.3 SHA alternativo + drift negativo:
       R-BL.3.a candidato afectado → NO_CLASIFICABLE
       R-BL.3.b si no queda ningún candidato clasificable Y
                existe al menos un NO_CLASIFICABLE
                → EVIDENCIA_INSUFICIENTE global
R-BL.4 skipped inesperado                     → HALLAZGO §14 P2
R-BL.5 collected sin denominador histórico    → HECHO ACTUAL
```

### 5.7 Verificación de consistencia estructural

```bash
test -f src/kicad_mcp/gates/g2.py     && echo "PRESENTE g2.py" || echo "AUSENTE g2.py"
test -f src/kicad_mcp/gates/g4.py     && echo "PRESENTE g4.py" || echo "AUSENTE g4.py"
test -f src/kicad_mcp/tools/pcb_encoders.py \
    && echo "PRESENTE pcb_encoders.py" \
    || { echo "AUSENTE pcb_encoders.py"; exit 1; }
```

### 5.8 Puerta 0 — GO / NO_GO_ENTRADA

Puerta 0 emite **GO** solo si TODAS:

```
G0.1  Nota humana §11.9 presente y bien formada (R-P0.10).
G0.2  BRANCH_ACTUAL == "master" (R-P0.1).
G0.3  HEAD no detached (R-P0.2).
G0.4  Working tree activo limpio (R-P0.3–5).
G0.5  SHA_S47_ENTRADA == SHA_REMOTO (R-P0.6).
G0.6  Divergencia con checkpoint (si existe) autorizada (R-P0.9).
G0.7  Worktrees adicionales limpias (R-P0.8, única regla).
G0.8  scripts/verificar_entorno.py exit 0 (R-P0.12).
G0.9  Modo (a) o (b) disponible con versiones registradas (R-P0.11).
G0.10 Variables de cache validadas canónicamente incluyendo
      UV_CACHE_DIR (R-P0.13).
G0.11 $S47_TMP validado canónicamente fuera del working tree (R-P0.14).
G0.12 GIT_OPTIONAL_LOCKS=0 y PYTEST_ADDOPTS='' (R-P0.15).
G0.13 pytest offline: failed == 0 AND errors == 0 AND conteos
      obtenidos (R-BL.0 satisfecha).
G0.14 R-BL.2 no activada.
G0.15 pcb_encoders.py presente.
G0.16 Snapshots CONFIG_ANTES, REMOTES_ANTES, REFS_ANTES,
      INDEX_HASH_ANTES capturados.
```

Si alguna falla → **NO_GO_ENTRADA** y `PAQUETE_ENTRADA_FALLIDA` (§15.1).

---

## 6. Fase 1 — Inventario actual (rederivación total)

Rederivación total, sin copiar cifras del contexto.

### 6.1 Alcance

Igual que v5, con el añadido de **política de resolución AST cerrada** (§7.1.1.bis).

### 6.2 Herramientas

`ast`, `hashlib`, `json` de stdlib; `grep -rn`, `wc -l`, `awk`, `sed`, `realpath`. No añadir dependencias.

### 6.3 Entregable

`01-inventario-actual.md` con evidencia citada.

---

## 7. Fase 2 — Reconstrucción de clusters candidatos

### 7.1 Algoritmo determinista de enumeración

#### 7.1.1 Grafo de referencias tipadas

```
V = { @mcp.tool de pcb.py } ∪
    { closures directas de register() } ∪
    { helpers top-level de pcb.py } ∪
    { constantes top-level de pcb.py }

E = referencias dirigidas tipadas: (u, v, tipo) donde tipo ∈ TIPOS.

TIPOS = {
  CALL,           # invocación directa u(...) → v
  NAME_REF,       # referencia por nombre sin llamada
  DECORATOR,      # v se usa como decorador de u
  DEFAULT,        # v aparece en parámetro default
  ANNOTATION,     # v aparece en anotación de tipo
  ATTRIBUTE_READ, # u lee v.<attr>
  CONSTANT_READ,  # u lee la constante v
  MONKEYPATCH_TARGET  # v es target de patch()/monkeypatch por path
}
```

#### 7.1.1.bis Política cerrada de resolución AST

Toda referencia detectada debe caer en una categoría explícita:

```
RESUELTA_A_V
  → símbolo del nombre resoluble a un elemento concreto de V.

RESUELTA_A_MODULO_EXTERNO
  → símbolo resoluble a un módulo importado (`from ... import X`
    o import calificado). Se registra como frontera_saliente_otras.

RESUELTA_A_STDLIB_O_BUILTIN
  → sys, os, typing, dataclasses, etc. Se registra pero no crea
    aristas ni fronteras.

REFERENCIA_AMBIGUA
  → cualquiera de:
    - alias sin poder trazarse al import original;
    - shadowing local con nombre igual a un elemento de V;
    - atributo dinámico (getattr, __dict__, setattr por string);
    - string de patch()/monkeypatch que no puede resolverse a
      un símbolo específico;
    - referencias calificadas desde módulos externos que no se
      pueden desambiguar;
    - anotaciones aplazadas (`from __future__ import annotations`
      o strings) no evaluables estáticamente;
    - decoradores/fábricas que no resuelven a un símbolo de V.

  Efecto:
    - Se registra en frontera_saliente_ambigua(K) con path:línea
      y descripción textual.
    - Un cluster con |frontera_saliente_ambigua(K)| > 0 debe
      declarar la ambigüedad en su ficha.
    - Si la ambigüedad afecta un símbolo cuya extracción se
      propone (no solo referencia) → activa R10 (complejidad
      alta) y puede activar NO_APTO.

REFERENCIA_INEXPRESABLE
  → construcciones que ast no puede parsear (código dinámico
    generado, exec/eval, etc.). Se registra como
    LIMITACION_METODOLOGICA en §14 y activa NO_APTO para el
    cluster afectado.
```

Ninguna referencia debe desaparecer silenciosamente. Toda referencia sin resolución explícita se registra en al menos una de las cinco categorías.

#### 7.1.2 Fronteras (cuatro tipos)

```
frontera_entrante_interna(K)   = { u ∈ V \ K : ∃ k ∈ K, (u, k, _) ∈ E }

frontera_entrante_src(K)       = { m ∈ SRC_MODULES \ {pcb.py} :
                                     algún símbolo de m referencia
                                     algún k ∈ K }

frontera_entrante_tests(K)     = { t ∈ TESTS_MODULES :
                                     t importa o patcha algún k ∈ K
                                     por path pcb.<k> }

frontera_saliente_otras(K)     = símbolos externos invocados por K,
                                  resueltos a módulos estables.

frontera_saliente_ambigua(K)   = referencias REFERENCIA_AMBIGUA emitidas
                                  por K (§7.1.1.bis).

frontera_saliente_hacia_pcb(K) = símbolos de pcb.py que K referenciaría
                                  desde el módulo nuevo (relevante en
                                  el modelo proyectado).
```

#### 7.1.3 Enumeración de semillas

Igual a v5 (S1, S2, S3, S4) con `seed_symbols(seed)` explícito.

#### 7.1.4 Materialización (expansión hasta punto fijo)

Igual a v5 (C1–C5).

#### 7.1.5 Clave de orden estable

Igual a v5.

#### 7.1.6 Filtros de descarte temprano (semántica corregida por MAJOR-01/BLOCKER-02)

**F-DT.1: EXCLUSION_CATEGORIAL_INSTITUCIONAL** — no refuta.

```
F-DT.1 Cluster que toca zonas / route_board / stitching / add_zone /
       add_keepout / delete_tracks_bulk / delete_zone.
       → EXCLUSION_CATEGORIAL_INSTITUCIONAL.
       NO se refuta. Se excluye del universo evaluable por decisión
       institucional del contrato (§13.2 zonas prohibidas de S47).
       Contribuye a N_excluidos_institucional.
       Registro en descartados.md con motivo "frontera segregada
       institucional".
```

**F-DT.2: CONSUMIDOR_MONKEYPATCH_OBLIGATORIO** — marca, no refuta.

```
F-DT.2 Cluster cuya semilla es run_drc, run_autoroute, o
       cualquier símbolo cubierto por monkeypatches ADR-0012.
       → MARCADO como CONSUMIDOR_MONKEYPATCH_OBLIGATORIO.
       NO se refuta automáticamente. Se materializa ficha completa.
       En la ficha, la existencia del monkeypatch se registra
       nominalmente (path pcb.<nombre>).
       En Fase 3:
         - Si la ficha demuestra que ningún reexport puede
           preservar el path del monkeypatch → NO_APTO por R4
           con evidencia específica.
         - Si un reexport lo preserva → R4 no se activa por
           este motivo. Puede activarse APTO_CONDICIONAL vía E3
           si el conteo de reexports excede UMBRAL_R7_REEXPORTS.
         - Si el reexport requerido cambia el schema del monkeypatch
           (por ejemplo, path esperado) → R14 (cambio de contrato
           observable).
       NO contribuye a N_refutados_temprano por su sola existencia.
```

**F-DT.3 y F-DT.4: exclusiones presupuestarias.**

```
F-DT.3 (presupuestario) LOC_actuales > UMBRAL_F_DT3_LOC (default 400)
       → EXCLUSION_PRESUPUESTARIA_TAMAÑO.
       Contribuye a N_excluidos_presup.

F-DT.4 (presupuestario) |frontera_entrante_src(K)| >= UMBRAL_F_DT4_MODS
       (default 3) → EXCLUSION_PRESUPUESTARIA_ACOPLAMIENTO.
       Contribuye a N_excluidos_presup.
       (F-DT.4 usa frontera_entrante_src, no interna ni tests.)
```

#### 7.1.7 Presupuesto de materialización

```
Paso 1: Generar TODAS las semillas por S1–S4.
Paso 2: Expandir cada semilla por C1–C5.
Paso 3: Deduplicar por conjunto exacto de símbolos.
Paso 4: Aplicar F-DT.1 (exclusión institucional).
Paso 5: Marcar candidatos por F-DT.2 (no excluir).
Paso 6: Aplicar F-DT.3 y F-DT.4 (exclusiones presupuestarias).
Paso 7: Ordenar candidatos supervivientes por clave_orden(K).
Paso 8: Materializar fichas completas hasta UMBRAL_P_STOP_FICHAS.
        Los candidatos marcados F-DT.2 tienen prioridad al menos
        igual al orden estable; nunca son omitidos por presupuesto
        antes de un candidato no marcado.
        Default: 12. Revisable en §11.9.

Contadores del universo:
  N_universo_total       = candidatos del Paso 3
  N_excluidos_institucional = candidatos por F-DT.1
  N_excluidos_presup     = candidatos por F-DT.3/F-DT.4
  N_marcados_monkeypatch = candidatos con F-DT.2
  N_supervivientes       = N_universo_total - N_excluidos_institucional
                                            - N_excluidos_presup
  N_fichas_completas     = min(N_supervivientes, UMBRAL_P_STOP_FICHAS)
  N_evaluados            = N_fichas_completas
                           (F-DT.2 no refuta; F-DT.1 excluye;
                            F-DT.3/F-DT.4 excluyen)

  Nota: N_refutados_temprano no existe en v6. Toda refutación
  produce ficha (aunque abreviada) o se difiere a Fase 3.
```

### 7.2 Contraste con priors históricos

Idéntico a v5 con actualización terminológica.

### 7.3 Matriz obligatoria de candidatos con ficha completa

Columnas de v5 + nuevas:

| Columna nueva | Definición |
|---|---|
| `M2_actual_vector` | `M2_estado_actual(K)` (§10-M2, medido sobre el estado actual del cluster dentro de pcb.py) |
| `M2_proyectado_vector` | `M2_estado_proyectado(K, diseño)` (medido sobre el estado tras la reubicación hipotética) |
| `marca_monkeypatch` | true si F-DT.2 marcó al cluster; incluye lista de paths de monkeypatches |
| `frontera_saliente_ambigua` | lista de REFERENCIA_AMBIGUA con path:línea |
| `excepciones_propuestas` | subconjunto de {E1, E2, E3} con instancia concreta por excepción |

### 7.4 Entregable de Fase 2

```
02-candidatos/
├── README.md
├── enumeracion.md       ← trazabilidad §7.1 + contadores completos
├── descartados.md       ← F-DT.1 (institucional) + F-DT.3/F-DT.4
│                          (presupuestarias). NO incluye F-DT.2 pues
│                          esos reciben ficha completa.
└── <nombre>.md          ← ficha por cada candidato materializado
                          (supervivientes + los marcados F-DT.2)
```

---

## 8. Fase 3 — Criterios de rechazo aplicados

```
VEREDICTO_INDIVIDUAL ∈ {
    APTO,
    APTO_CONDICIONAL,
    NO_APTO,
    NO_CLASIFICABLE (por R-BL.3.a)
}
```

Aplicar S1–S8 (AND) y R1–R14 (OR) según §11.4 y §11.5.

Para `APTO_CONDICIONAL`, seguir la tabla normativa de §11.7.

### 8.1 Deudas segregadas (§11.4-S6)

```
REFERENCIA_EXISTENTE → admisible con evidencia.
CAMBIO_INCIDENTAL    → NO_APTO por R5.
PRERREQUISITO        → NO_APTO por R5 + hallazgo §14
                       PRERREQUISITO_ELEVADO.
```

---

## 9. Fase 4 — Colisiones con riesgos fuera de scope

Matriz `04-colisiones.md`:

| Candidato | P1-2 | DT3 | route_board | zone-fill | Freerouting | G2 | G4 | _CACHE |
|---|---|---|---|---|---|---|---|---|

---

## 10. Métricas — cuatro dimensiones

**M1 — Volumen (escalar).**
LOC actual, proyectado, neto en `pcb.py`, en módulo nuevo hipotético; closures eliminadas.

**M2 — Acoplamiento (vector nominal ordenado con medición homogénea).**

Dos funciones de medición sobre el **mismo modelo de fronteras**:

```
M2_estado_actual(K) mide el cluster K mientras reside dentro de pcb.py.

  d1_capturas_scope_actual
    = nº de símbolos que serían inyectables como parámetros/imports
      si se extrajera K, pero que en el estado actual son referencias
      libres al scope de register() desde código dentro de K.
    Unidad: símbolos distintos. Deduplicación: por nombre.

  d2_cortes_hacia_pcb_actual
    = nº de referencias que K hace a símbolos de V \ K dentro de pcb.py.
    Unidad: aristas (u, v) con u ∈ K, v ∈ V \ K, cualquier tipo.
    Deduplicación: por par (u nombre, v nombre, tipo).

  d3_modulos_externos_actual
    = nº de módulos externos distintos que K referencia
      (frontera_saliente_otras).
    Unidad: módulos distintos por ruta canónica.
    Deduplicación: por ruta canónica.

  d4_helpers_multi_consumer_actual
    = nº de helpers de K con |consumidor(h) \ K| >= 1.
    Unidad: símbolos distintos.

  d5_fronteras_entrantes_actual
    = |frontera_entrante_interna(K)| +
      |frontera_entrante_src(K)| +
      |frontera_entrante_tests(K)|.
    Unidad: sumatoria de módulos/símbolos, cada frontera con
    su propia deduplicación (símbolos para interna, módulos
    canónicos para src, módulos para tests).


M2_estado_proyectado(K, diseño_extracción) mide el cluster K
tras la reubicación hipotética a un módulo nuevo.

  d1_capturas_scope_proy
    = nº de símbolos que efectivamente quedan como parámetros
      añadidos o imports del módulo nuevo hacia otros módulos
      inferiores, según diseño_extracción.
    Unidad y deduplicación: idénticas a d1_actual.

  d2_cortes_hacia_pcb_proy
    = |frontera_saliente_hacia_pcb(K)| tras extracción.
      Referencias que el módulo nuevo debe importar de vuelta desde
      pcb.py. En el estado actual d2_actual mide referencias internas;
      en el proyectado d2_proy mide imports desde el nuevo módulo
      hacia pcb.py. Ambos son "cortes" entre K y pcb.py.
    Unidad: referencias post-extracción, deduplicadas por
    (nombre, tipo).

  d3_modulos_externos_proy
    = nº de módulos externos distintos que el módulo nuevo referencia.
    Igual a d3_actual salvo si diseño_extracción reubica imports.

  d4_helpers_multi_consumer_proy
    = nº de helpers del módulo nuevo con consumidor externo tras
      extracción. Con reexports desde pcb.py, esto puede reducirse.

  d5_fronteras_entrantes_proy
    = suma equivalente medida sobre el módulo nuevo.


COMPARACIÓN

M2_nuevo NO_EMPEORA M2_actual  ↔
    ∀ i ∈ {1..5}: M2_proyectado[i] <= M2_actual[i]

M2_nuevo dom M2_actual (dominancia estricta)  ↔
    NO_EMPEORA Y ∃ i: M2_proyectado[i] < M2_actual[i]

Orden lexicográfico sobre M2_proyectado (para §11.6):
    (d1, d2, d3, d4, d5)


EJEMPLO MÍNIMO

Cluster K = { closure C, helper H }, actualmente en register()/pcb.py.
Diseño_extracción: mover a modulo M; inyectar H como parámetro
                    a C; reexport de C desde pcb.py.

Estado actual:
  d1_actual = 1  (H usa `board_ipc` capturado del scope de register())
  d2_actual = 3  (C llama a X, Y, Z en pcb.py)
  d3_actual = 2  (K referencia kicad_python.foo y stdlib_bar
                  → solo kicad_python.foo cuenta;
                    stdlib_bar es RESUELTA_A_STDLIB, no cuenta)
              = 1
  d4_actual = 0
  d5_actual = 4  (frontera_entrante_interna=2, src=1, tests=1)

Estado proyectado (M reexporta nada; pcb.py reexporta C):
  d1_proy = 1  (board_ipc inyectado como parámetro)
  d2_proy = 3  (M importa X, Y, Z desde pcb.py)
  d3_proy = 1  (M importa kicad_python.foo directamente)
  d4_proy = 1  (C reexportada desde pcb.py: consumidor externo
                efectivo)
  d5_proy = 4  (src y tests siguen accediendo por pcb.C)

En este ejemplo, M2_proy vs M2_actual:
  (1,3,1,1,4) vs (1,3,1,0,4)
  d4 empeora (0→1). M2_nuevo NO_EMPEORA es FALSO.
  S8 NO se cumple. R11 activa (beneficio marginal).
  El candidato es NO_APTO por S8/R11.
```

**M3 — Superficie observable.**
Firmas `@mcp.tool`; códigos de error [F3]; reexports; contratos de persistencia; auditoría.

**M4 — Cobertura por camino.**

```
COBERTURA_DEMOSTRADA
  Test offline nombrado con evidencia de que la aserción falla
  si el camino no se ejecuta. grep NO puede elevar a este nivel.

COBERTURA_REFERENCIADA
  Test menciona/importa el símbolo, sin evidencia de que la
  aserción dependa del camino.

COBERTURA_INFERIDA
  Alcanzable por transitividad, sin test focal.

COBERTURA_DESCONOCIDA
  No se pudo determinar; documentar por qué.
```

---

## 11. Criterios GO / NO_GO / EVIDENCIA_INSUFICIENTE

### 11.1 Definición formal de candidato ganador

```
cohesivo
pequeño (§11.4 S7)
dependency-closed y acíclico (§11.4 S1)
reversibilidad preliminar demostrada (§11.4 S3)
superficie MCP-neutral (§11.4 S2)
contract-neutral
testable con la suite offline actual (§11.4 S4) o con delta
  concreto propuesto (via §11.7-E2; la aprobación específica de
  la instancia queda a decisión humana post-S47, §11.7.bis)
sin dependencias nuevas (F5)
sin mezcla de deudas (§11.4-S6)
sin ampliación silenciosa de scope
```

> **El objetivo no es maximizar LOC movidas, sino reducir una unidad de deuda estructural demostrable con el menor riesgo contractual posible.**

### 11.2 Preflight de veredicto

Igual a v5, con V0.7 actualizada:

```
V0.7 Contadores del universo registrados:
     N_universo_total, N_excluidos_institucional,
     N_excluidos_presup, N_marcados_monkeypatch,
     N_supervivientes, N_fichas_completas, N_evaluados
```

### 11.3 Reglas de agregación (excluyentes, ordenadas, exhaustivas)

Evaluar en orden; retornar el primer estado aplicable:

```
1. Si Puerta 0 falló                           → NO_GO_ENTRADA
2. Si R-BL.2 se activó                         → NO_GO_ENTRADA
3. Si R-BL.3.b activa insuficiencia global     → EVIDENCIA_INSUFICIENTE
4. Si alguna V0.2–V0.7 no cumplida             → EVIDENCIA_INSUFICIENTE
5. Si N_supervivientes > UMBRAL_P_STOP_FICHAS  → EVIDENCIA_INSUFICIENTE
6. Si algún candidato con ficha queda sin
   clasificar entre APTO/APTO_CONDICIONAL/
   NO_APTO/NO_CLASIFICABLE                    → EVIDENCIA_INSUFICIENTE
7. Si N_evaluados == 0                         → EVIDENCIA_INSUFICIENTE
8. Si existe >=1 candidato APTO Y
   N_excluidos_presup == 0 Y
   N_excluidos_institucional == 0             → GO
9. Si existe >=1 candidato APTO Y
   (N_excluidos_presup > 0 O
    N_excluidos_institucional > 0)            → GO_DENTRO_DEL_PRESUPUESTO
10. Si NO existe APTO y existe >=1
    APTO_CONDICIONAL con excepción §11.7      → GO_CONDICIONAL_PROPUESTO
11. Si NO existe APTO ni APTO_CONDICIONAL
    y existe >=1 NO_CLASIFICABLE               → EVIDENCIA_INSUFICIENTE
   (regla nueva por BLOCKER-01; garantiza
    exhaustividad ante mezclas)
12. Si TODOS los candidatos evaluados son
    NO_APTO Y N_excluidos_presup == 0 Y
    N_excluidos_institucional == 0             → NO_GO
13. Si TODOS los candidatos evaluados son
    NO_APTO Y (N_excluidos_presup > 0 O
    N_excluidos_institucional > 0)            → NO_GO_POR_PRESUPUESTO
```

Cobertura formal: cada combinación posible de {APTO≥0, APTO_CONDICIONAL≥0, NO_APTO≥0, NO_CLASIFICABLE≥0} con N_evaluados > 0 activa exactamente una regla de 8–13.

Si existen dos o más candidatos `APTO`, se ordenan por §11.6.

### 11.4 Aceptación (AND) — S1..S8

Idéntico a v5 con S8 usando la comparación M2 homogénea de §10.

### 11.5 Rechazo (OR) — R1..R14

Idéntico a v5. R4 explícitamente activada solo por evidencia (no por marca F-DT.2 sola). R11 activada por S8 sin dominancia.

### 11.6 Orden de preferencia entre APTOs

```
1. Preferir dominancia estricta (M2_proy dom M2_actual sobre el
   candidato A vs candidato B: preferir A si M2_A dom M2_B en la
   comparación cruzada).
2. Si son incomparables por dominancia, orden lexicográfico
   sobre M2_proy.
3. En empate M2 lex, mayor proporción de COBERTURA_DEMOSTRADA.
4. En empate M4, menor colisión con §9.
5. En empate final, menor complejidad_extraccion_estimada.
```

### 11.7 Excepciones estructurales del candidato — tabla normativa

**Tabla normativa de dispensa (BLOCKER-04):**

| Excepción | Gates que puede dispensar | Evidencia mínima requerida | Efecto |
|---|---|---|---|
| **E1** | S7 (si S7.a/b/c no se cumplen Y S7.d no se pudo demostrar) | Argumento estructural nominal: qué responsabilidad se agrupa, qué fan-in cruzado se elimina cualitativamente, con métricas alternativas si las hay | Habilita APTO_CONDICIONAL si todos los demás gates (S1–S6, S8) se cumplen |
| **E2** | S4 (COBERTURA_REFERENCIADA/INFERIDA/DESCONOCIDA), R3, R9 | Delta nominal de tests: lista de tests a añadir (nombres exactos, aserciones esperadas), no genérico. NO admite eliminación de tests | Habilita APTO_CONDICIONAL si el delta cubre los caminos afectados y todos los demás gates se cumplen |
| **E3** | R7 (reexports), y R4 SOLO SI los reexports demuestran preservar el path exacto del monkeypatch | Lista nominal de reexports concretos con path exacto. Para dispensar R4 adicionalmente: prueba de que el path pcb.<nombre> se preserva byte-a-byte | Habilita APTO_CONDICIONAL si los reexports son <= 2 × UMBRAL_R7_REEXPORTS y todos los demás gates se cumplen |

**Semántica formal de APTO_CONDICIONAL:**

```
APTO_CONDICIONAL(candidato) ↔
    ∃ subconjunto E' ⊆ {E1, E2, E3} tal que:
      (1) todas las excepciones de E' están preautorizadas
          categorialmente en la nota humana §11.9;
      (2) el candidato propone instancias concretas de cada
          excepción de E' con la evidencia mínima requerida
          en la tabla;
      (3) cada dispensa está ligada a una sola evidencia
          nominal (no comparte evidencia con otra dispensa);
      (4) sea D(E') = unión de gates dispensados por E'.
          Todos los gates de {S1..S8} \ D(E') se cumplen;
      (5) todos los criterios R que NO son dispensables por E'
          NO se activan;
      (6) los criterios R que SÍ son dispensables por E' están
          dispensados por al menos una excepción de E'.

Combinación explícita: E' puede tener cardinalidad 1, 2 o 3.
                       Si cardinalidad > 1, la ficha declara
                       explícitamente que la combinación se
                       propone conjuntamente.
```

**Criterios NO dispensables (nunca por E1, E2 ni E3):**

- S1 (dependency-closed y acíclico) — nunca dispensable.
- S2 (superficie MCP-neutral) — nunca dispensable.
- S3 (reversibilidad preliminar) — nunca dispensable.
- S5 (fuera de zonas prohibidas) — nunca dispensable.
- S6 (relación con P1-2/DT3 no es CAMBIO_INCIDENTAL ni PRERREQUISITO) — nunca dispensable.
- S8 (M2 no empeora) — nunca dispensable.
- R1, R2, R5, R6, R8, R10, R11, R12, R13, R14 — nunca dispensables.

**Explícitamente NO admisibles como excepción:**

```
- Divergencia de SHA o baseline.
- Excepciones sobre F1–F5 o G1–G5.
- Renombrado o eliminación de códigos de error [F3].
- Cambio en API MCP visible.
- Cambio en semántica de persistencia.
- Cambio en goldens [F1].
- Mezcla no aislable con P1-2 o DT3.
- Adición de dependencias [F5].
- Eliminación de tests existentes (§12).
```

### 11.7.bis Distinción entre preautorización categorial y aprobación específica

Idéntica a v5. La nota humana pre-S47 preautoriza categorías. La instancia concreta la aprueba el humano post-S47 vía H2-bis.

### 11.8 Efectos secundarios prohibidos del veredicto

Iguales a v5.

### 11.9 Nota de invocación humana (obligatoria, referencia única al contrato)

```
NOTA DE INVOCACIÓN S47
=====================
Fecha:                 <ISO 8601>
Contrato aprobado:
    Versión:           S47 vN
    SHA-256:           <hash exacto del archivo>
    (Este es el único identificador del contrato en la nota.)
Ancla de sesión SHA:   <checkpoint 33e32ef… o SHA alternativo>
Umbrales autorizados:
    UMBRAL_S7_LOC          = <valor>   (default 80)
    UMBRAL_S7_CLOSURES     = <valor>   (default 3)
    UMBRAL_S7_PCB_LOC      = <valor>   (default 100)
    UMBRAL_R7_REEXPORTS    = <valor>   (default 3)
    UMBRAL_F_DT3_LOC       = <valor>   (default 400)
    UMBRAL_F_DT4_MODS      = <valor>   (default 3)
    UMBRAL_P_STOP_FICHAS   = <valor>   (default 12)
Categorías §11.7 preautorizadas como evaluables:
    [E1, E2, E3] o subconjunto.
    (Preautorización categorial. NO autoriza ninguna instancia
    específica.)
S47_TMP:               <ruta absoluta canónica fuera del working
                        tree, validable con realpath>
Aprobación:            <nombre humano o identificador> explícita
```

Sin nota o con nota mal formada → `NO_GO_ENTRADA` (R-P0.10).

---

## 12. Fase 5 — Prescripción de equivalencia futura

**Ancla de equivalencia: `SHA_S47_ENTRADA + BASELINE_ACTUAL_OBSERVADO + lista_nominal_pre de tests focales`.**

**Ancla nominal de tests:** `lista_nominal_post ⊇ lista_nominal_pre`. Eliminación de tests fuera del alcance de S47/S48/S49 (H13).

Contenido de la prescripción:

```
Ancla de equivalencia
  SHA de referencia:            SHA_S47_ENTRADA
  Baseline pre-cambio:          BASELINE_ACTUAL_OBSERVADO
  Tests focales del candidato:  lista_nominal_pre (nombres exactos)
  Goldens ejercidos:            lista nominal
  Monkeypatches vigentes:       lista con path exacto

Verificaciones estáticas post-implementación (S49)
  tool_count global antes/después
  tool_count exportadas por pcb.py antes/después
  tool names antes/después
  tool schemas antes/después
  flags @mutating_tool antes/después
  códigos de error emitidos antes/después
  reexports públicos de pcb.py antes/después
  imports circulares: ninguno introducido

Verificaciones dinámicas post-implementación (S49)
  Tests focales: ejecutados individualmente, 0 failed
  lista_nominal_post ⊇ lista_nominal_pre
  suite offline post:
    passed_post >= passed_pre  (contra BASELINE_ACTUAL_OBSERVADO)
    failed_post == 0
    errors_post == 0
    tests eliminados == 0
  ruff, ruff format, mypy: sin nuevos hallazgos

Verificaciones de persistencia y snapshots
  contrato W-IPC/W-Composite/W-SKIP/Infra: sin cambio
  snapshots ejercidos: sin cambio

Verificaciones de reversibilidad mecánica (RESERVADAS PARA S48)

  Prohibición estricta:
    - NO `git worktree add` sobre el repositorio autoritativo
      (mutaría refs de admin interna).
    - NO modificar el repositorio autoritativo en ningún paso.

  Método autorizado (S48 lo detallará en su contrato):
    - Producir patch de extracción P fuera del working tree
      autoritativo.

    - Clonar el repo autoritativo a directorios EXTERNOS
      independientes:
        git clone --local <repo autoritativo> $EXTERNAL_TMP/PRE
        git clone --local <repo autoritativo> $EXTERNAL_TMP/POST
      (--local usa hardlinks; sigue siendo repo separado.
       No modifica el original.)

    - Ambos clones checkout de SHA_S48_ENTRADA.

    - Verificar patch aplica sobre PRE:
        git -C $EXTERNAL_TMP/PRE apply --check P    (exit 0)
      (No aplicar realmente en PRE; PRE queda como referencia.)

    - Aplicar patch a POST:
        git -C $EXTERNAL_TMP/POST apply P

    - Producir MANIFIESTO_PRE: lista de tracked files de PRE con
      SHA-256 y modo, ordenada lexicográficamente. Excluye
      `.git/`, `__pycache__/`, caches.
        (cd $EXTERNAL_TMP/PRE && git ls-files -s > .../MANIFIESTO_PRE.raw)
        Cada línea: <modo> <sha1> 0 <path>
        Ampliar con SHA-256 por archivo:
        for f in $(git -C $EXTERNAL_TMP/PRE ls-files); do
          echo "$(sha256sum "$EXTERNAL_TMP/PRE/$f" | cut -d' ' -f1) \
                $(git -C $EXTERNAL_TMP/PRE ls-files -s "$f" | cut -d' ' -f1) \
                $f"
        done | sort > MANIFIESTO_PRE

    - Aplicar reverse a POST:
        git -C $EXTERNAL_TMP/POST apply --reverse P

    - Producir MANIFIESTO_POST_RESTAURADO con el mismo método.

    - Igualdad esperada:
        diff MANIFIESTO_PRE MANIFIESTO_POST_RESTAURADO   (exit 0)
      Cada línea idéntica: mismo path, mismo modo, mismo SHA-256.

    - Ninguna operación toca el repo autoritativo. S48 preserva
      READ-ONLY sobre el repo mediante clones externos.

Auditoría
  eventos de auditoría emitidos por tools mutantes: sin cambio
```

Un candidato sin prescripción de equivalencia clara no puede recibir `APTO`.

---

## 13. Scope permitido y prohibido

### 13.1 Permitido en S47

Igual a v5 con endurecimientos:

```
Leer todo el árbol.
git observacional (con GIT_OPTIONAL_LOCKS=0 en el entorno):
  rev-parse, log, status, diff (sin -w, sin apply), diff --check,
  worktree list --porcelain,
  ls-files (incluyendo `ls-files -s` para hash del index),
  branch --show-current,
  config --local --list --show-origin,
  remote -v,
  show-ref --heads --tags.
CI offline con modo (a) uv run --frozen --no-sync o modo (b)
  binarios directos .venv/bin/*.
ruff, mypy, ruff format --check en modo no-sync.
pytest con -o "cache_dir=$S47_TMP/pytest-cache" explícito,
  PYTEST_ADDOPTS=''.
scripts/verificar_entorno.py en modo no-sync.
Análisis con ast, hashlib, json, grep, wc, awk, sed, realpath.
Producir artefactos en $S47_TMP.
Caches en $S47_TMP (PYTHONPYCACHEPREFIX, MYPY_CACHE_DIR,
  RUFF_CACHE_DIR, UV_CACHE_DIR, pytest cache_dir).
```

### 13.2 Prohibido en S47

Igual a v5 con:

```
git worktree add / remove / prune (solo list --porcelain permitido).
Fallback mutante uv.
Ejecutar sin GIT_OPTIONAL_LOCKS=0.
Ejecutar con PYTEST_ADDOPTS no vacío.
```

### 13.3 Salida esperada al cierre (verificable mecánicamente)

```bash
# Identidad
git rev-parse HEAD                                     # == SHA_S47_ENTRADA
git rev-parse origin/master                            # == SHA_REMOTO de Puerta 0
git branch --show-current                              # == "master"

# Working tree
git status --porcelain=v1 --untracked-files=all        # == estado de Puerta 0
git diff HEAD                                          # vacío

# Snapshots protegidos (igualdad byte-a-byte con Puerta 0)
git config --local --list --show-origin                # CONFIG_DESPUES == CONFIG_ANTES
git remote -v                                          # REMOTES_DESPUES == REMOTES_ANTES
git show-ref --heads --tags                            # REFS_DESPUES == REFS_ANTES

# Hash del index (NUEVO por MAJOR-04)
git ls-files -s | sha256sum                            # INDEX_HASH_DESPUES == INDEX_HASH_ANTES
```

Cualquier diferencia byte-a-byte → INCUMPLIMIENTO en `06-cierre.md` y elevación al humano.

---

## 14. Hallazgos fuera de scope

`04-hallazgos-fuera-de-scope.md`:

```
Categoría:    DRIFT_DOC / BACKLOG_NUEVO / RIESGO_NUEVO / METRICA /
              MONKEYPATCH_NUEVO / TEST_HUERFANO / DELTA_BASELINE /
              PRIOR_HISTORICO_NO_REPRODUCIDO / PRERREQUISITO_ELEVADO /
              DRIFT_AFECTA_CANDIDATO / REFERENCIA_AMBIGUA /
              LIMITACION_METODOLOGICA / OTRO
Prioridad:    P0 / P1 / P2 / P3
Evidencia:    path:linea o comando + salida + exit code
Acción:       NO CORREGIR en S47. Elevar al humano en 05-veredicto.
```

---

## 15. Formato del reporte (entregables)

Rutas relativas canónicas al root `S47/`, separador `/`, verificables desde `S47/` como directorio de trabajo.

### 15.1 `PAQUETE_ENTRADA_FALLIDA` (para `NO_GO_ENTRADA`)

**Contiene exactamente 7 archivos totales:**

```
S47/
├── PACKAGE-METADATA.md
├── CONTRATO-AUDITADO.md
├── CONTRACT.sha256
├── 00-preflight.md
├── 05-veredicto.md
├── 06-cierre.md
└── MANIFEST.sha256
```

### 15.2 `PAQUETE_INVESTIGACION` (para EVIDENCIA_INSUFICIENTE, NO_GO, NO_GO_POR_PRESUPUESTO, GO, GO_DENTRO_DEL_PRESUPUESTO, GO_CONDICIONAL_PROPUESTO)

```
S47/
├── PACKAGE-METADATA.md
├── CONTRATO-AUDITADO.md
├── CONTRACT.sha256
├── 00-preflight.md
├── 01-inventario-actual.md
├── 02-candidatos/
│   ├── README.md
│   ├── enumeracion.md
│   ├── descartados.md
│   └── <nombre>.md
├── 03-refutacion.md
├── 04-colisiones.md
├── 04-hallazgos-fuera-de-scope.md
├── 05-veredicto.md
├── 06-cierre.md
└── MANIFEST.sha256
```

### 15.3 Formato normativo de `CONTRACT.sha256`

Formato exacto, compatible con `sha256sum -c` ejecutado desde `S47/`:

```
<sha256 de CONTRATO-AUDITADO.md><dos espacios>CONTRATO-AUDITADO.md
```

Una sola línea, terminada en `\n`. Ejemplo:

```
3fc56ce82ae5c7a396bd667e55228785e2073ea556373846cf0696ed6c75b7a2  CONTRATO-AUDITADO.md
```

**Semántica de verificación (MAJOR-03):**

- `MANIFEST.sha256` hashea el archivo `CONTRACT.sha256` como archivo (para integridad).
- `sha256sum -c CONTRACT.sha256` (desde `S47/`) verifica el contenido de `CONTRATO-AUDITADO.md`.
- Codex compara el hash listado en `CONTRACT.sha256` con el SHA-256 del contrato aprobado por ChatGPT y consignado en la nota humana §11.9.

Estas son tres verificaciones distintas y complementarias.

### 15.4 Estructura obligatoria de `05-veredicto.md` (paquete de investigación)

```
1. Estado inicial verificado (SHA_S47_ENTRADA)
2. Baseline actual observado por categoría con delta contra HIST_*
3. Nota humana §11.9 referenciada por hash único
4. Inventario resumido
5. Grafo tipado y componentes conectados (resumen)
6. Consumidores privados relevantes (src + tests separados)
7. Monkeypatches relevantes
8. Enumeración de candidatos con contadores del universo:
   N_universo_total, N_excluidos_institucional, N_excluidos_presup,
   N_marcados_monkeypatch, N_supervivientes, N_fichas_completas,
   N_evaluados
9. Matriz de candidatos con ficha completa
10. Candidatos descartados institucional o presupuestariamente
    (referenciados desde descartados.md)
11. Candidatos refutados por §11.5 con criterio activado
12. Candidatos NO_CLASIFICABLE por R-BL.3.a
13. Mejor candidato, si existe (con calificación:
    global si N_excluidos_* == 0;
    "dentro del presupuesto" en otro caso)
14. Alternativa secundaria, si existe
15. Excepciones §11.7 propuestas por candidato APTO_CONDICIONAL
    con mapping a la tabla normativa (dispensas, evidencia)
16. Riesgos residuales
17. Prescripción de equivalencia futura (§12)
18. Veredicto (uno de los siete estados)
19. Estado git final (idéntico a Puerta 0, snapshots + index_hash
    comparados)
20. Referencia a MANIFEST.sha256 y CONTRACT.sha256
21. Siguiente unidad según §18: S48 solo con nueva autorización
    humana (H2 para GO/GO_DENTRO_DEL_PRESUPUESTO;
    H2-bis para GO_CONDICIONAL_PROPUESTO)
```

### 15.5 Invalidación

```
Cambio del contrato    → nueva auditoría del contrato por ChatGPT,
                         nueva versión byte-a-byte con SHA-256 propio.
Cambio del paquete S47 → nueva revisión de Codex y nueva reconciliación
                         por ChatGPT. El contrato NO requiere nueva
                         auditoría si no cambió.
```

---

## 16. Handoff a Codex — Revisión independiente

### 16.1 Verificación de identidad y esquema

```
V0.1  MANIFEST.sha256 presente y bien formado.
V0.2  `sha256sum -c MANIFEST.sha256` desde S47/ exit code 0.
V0.3  CONTRATO-AUDITADO.md presente y hasheado en MANIFEST.
V0.4  CONTRACT.sha256 con formato normativo §15.3;
      `sha256sum -c CONTRACT.sha256` desde S47/ exit code 0.
V0.5  Hash listado en CONTRACT.sha256 == SHA-256 del contrato
      aprobado por ChatGPT, consignado en la nota humana §11.9
      (comparación semántica, no solo integridad del archivo).
V0.6  SHA_S47_ENTRADA en PACKAGE-METADATA.md == en 00-preflight.md.
V0.7  HEAD actual del repo == SHA_S47_ENTRADA.
V0.8  Determinar esquema declarado a partir de 05-veredicto.md.
V0.9  Verificar el esquema exacto según §15.
V0.10 Snapshots CONFIG/REMOTES/REFS + INDEX_HASH antes vs después
      iguales byte-a-byte en 06-cierre.md.
```

### 16.2 Alcance de revisión

Codex intenta refutar al menos:

```
- clausura de dependencias del ganador sobre grafo tipado
- dirección acíclica (S1)
- resolución AST completa: ninguna REFERENCIA_AMBIGUA desaparece
  silenciosamente; toda referencia se registra en una de las
  categorías de §7.1.1.bis
- consumidores privados omitidos (src externo, tests)
- monkeypatches omitidos
- ciclos de import posibles
- reexports realmente necesarios
- contratos indirectos afectados
- clasificación de cobertura por camino
- suficiencia de tests para probar equivalencia
- riesgo de persistencia
- riesgo de snapshots
- relación con P1-2/DT3
- reversibilidad preliminar
- beneficio estructural exagerado (M2 homogénea, dominancia)
- excepción §11.7 fuera de la tabla normativa o sin evidencia
  mínima requerida
- ganador presentado como global cuando N_excluidos_* > 0
- ancla de equivalencia usa BASELINE_ACTUAL_OBSERVADO
- lista_nominal_post ⊇ lista_nominal_pre
- prescripción S48 usa clones externos (no worktrees)
  y manifiesto de tracked files (no diff -r que incluye .git)
- F-DT.2 correctamente aplicado como marca, no como refutación
- F-DT.1 correctamente aplicado como exclusión institucional,
  no como refutación con R5/R13
- vector M2 con medición homogénea antes/después
- APTO_CONDICIONAL cumple semántica formal §11.7 (dispensas
  ligadas a evidencia nominal única, todos los gates no
  dispensados satisfechos)
```

### 16.3 Verificaciones mecánicas

```
V1  Identidad git preservada (incluyendo INDEX_HASH).
V2  Working tree activo == Puerta 0.
V3  Recomputar M1 y ambos M2 (actual y proyectado) para ganador.
    Discrepancia > 5 % → red flag.
V4  Cita al azar por bloque.
V5  Ningún APTO viola R1..R14.
V6  Hallazgos §14 registrados y no corregidos.
V7  No se propone Slice 2.
V8  Ninguna cobertura DEMOSTRADA se sostiene solo en grep.
V9  Delta de tests propuesto en §11.7-E2 con evidencia mínima.
V10 Siguiente unidad respeta §18 (H2 vs H2-bis correcto).
V11 Precedencia §11.3 respetada.
V12 §12 usa BASELINE_ACTUAL_OBSERVADO.
V13 §12 exige lista_nominal_post ⊇ lista_nominal_pre.
V14 Contadores del universo consistentes.
V15 Distinción correcta: GO vs GO_DENTRO_DEL_PRESUPUESTO según
    N_excluidos_*. NO_GO vs NO_GO_POR_PRESUPUESTO ídem.
V16 §12 prohíbe worktree sobre repo autoritativo; usa clones
    externos y manifiesto SHA-256 + modo.
V17 GO_CONDICIONAL_PROPUESTO cumple tabla normativa §11.7:
    dispensas explícitas, gates no dispensados satisfechos.
```

### 16.4 Veredictos permitidos

```
APROBAR
APROBAR_CON_CAMBIOS
BLOQUEAR
```

Severidades: `BLOCKER`, `MAJOR`, `MINOR`, `NOTE`.

---

## 17. Handoff a ChatGPT — Reconciliación

### 17.1 Verificación de identidad

```
Q0.1  MANIFEST.sha256 verificado (V0.1–V0.10).
Q0.2  CONTRATO-AUDITADO.md == contrato v6 aprobado (hash de la
      nota humana == hash de CONTRACT.sha256).
```

### 17.2 Alcance

```
Q1  Contrastar contra checkpoint, 41-reporte.md, hoja-de-ruta-v5.md,
    BACKLOG.md, AGENTS.md, CLAUDE.md, ADR vigentes.
Q2  Detectar contradicciones con F1–F5, G1–G5, ADR.
Q3  Detectar drift documental producido o revelado.
Q4  Detectar scope creep implícito.
Q5  Compatibilidad de veredictos con §2.
Q6  Verificar GO_CONDICIONAL_PROPUESTO conforme a §11.7 tabla
    normativa + §11.7.bis.
Q7  Distinción entre EVIDENCIA_INSUFICIENTE, NO_GO,
    NO_GO_POR_PRESUPUESTO.
Q8  Siguiente unidad respeta §18.
Q9  Precedencia §11.3 y exhaustividad (regla 11 activa cuando
    corresponde).
Q10 Coherencia esquema de paquete vs estado.
Q11 Ancla de equivalencia = BASELINE_ACTUAL_OBSERVADO.
Q12 Ancla nominal de tests preservada.
Q13 GO vs GO_DENTRO_DEL_PRESUPUESTO usados correctamente.
Q14 F-DT.2 aplicado como marca, no refutación.
Q15 F-DT.1 como exclusión institucional.
Q16 M2 con medición homogénea.
```

### 17.3 Dictamen

```
SLICE_AUTORIZABLE
SLICE_AUTORIZABLE_CON_CAMBIOS
NO_AUTORIZABLE
INVESTIGACION_INSUFICIENTE
INSTANCIA_CONDICIONAL_PARA_APROBACION_HUMANA
GANADOR_DENTRO_DEL_PRESUPUESTO_PARA_APROBACION_HUMANA
  (nuevo: cuando GO_DENTRO_DEL_PRESUPUESTO llega bien fundado y
   el humano debe decidir si acepta la limitación de universo)
```

---

## 18. Secuencia canónica de sesiones

```
S47  Caracterización comparativa (esta sesión)
     Naturaleza:  READ-ONLY DE FUENTES Y ESTADO AUTORITATIVO
     Producto:    veredicto (uno de siete estados)

S48  Caracterización de detalle del ganador
     Naturaleza:  READ-ONLY DE FUENTES Y ESTADO AUTORITATIVO
     Método de reversibilidad:
       - clones externos vía `git clone --local`;
       - NO `git worktree add` sobre el repo autoritativo;
       - manifiesto de tracked files con SHA-256 + modo;
       - igualdad exacta del manifiesto tras reverse.
     Autorización requerida:  nueva nota humana.
       - GO o GO_DENTRO_DEL_PRESUPUESTO: H2 (más H11 opcional
         para ampliar presupuesto si S47 fue limitado).
       - GO_CONDICIONAL_PROPUESTO: H2-bis (aprobación específica
         de la instancia de excepción).

S49  Implementación
     Naturaleza:  mutante, produce diff sobre el repo autoritativo.
     Autorización requerida:  nueva nota humana tras S48.
```

---

## 19. Puntos de decisión humana

```
H1     Emitir nota de invocación §11.9 antes de S47.
H2     Autorizar S48 tras GO o GO_DENTRO_DEL_PRESUPUESTO.
H2-bis Aprobar instancia específica de excepción §11.7 tras
       GO_CONDICIONAL_PROPUESTO (delta nominal de tests, reexports
       concretos, argumento estructural).
H3     Emitir nota de invocación de S48.
H4     Aceptar delta de tests propuesto (E2) tras revisión.
H5     Elegir alternativa secundaria.
H6     Rechazar todos los candidatos aun con GO técnico.
H7     Suspender DT1 o cerrarlo.
H8     Autorizar sesión separada para corregir hallazgos §14.
H9     Autorizar excepciones a F1–F5 o umbrales G1–G5.
H10    Push, PR, merge.
H11    Reintentar S47 tras EVIDENCIA_INSUFICIENTE o
       NO_GO_POR_PRESUPUESTO con presupuesto ampliado o alcance
       restringido; también aplicable para ampliar universo tras
       GO_DENTRO_DEL_PRESUPUESTO si se busca ganador global.
H12    Autorizar S49 solo tras S48 completada y revisada.
H13    Autorizar sesión específica para modificar la suite de tests
       (eliminación, restructuración). Fuera de S47/S48/S49.
```

---

## 20. Nota metodológica final

Este contrato v6 está diseñado para poder terminar en cualquiera de los siete estados con dignidad epistemológica.

La distinción entre `GO` global y `GO_DENTRO_DEL_PRESUPUESTO`, entre `NO_GO` universal y `NO_GO_POR_PRESUPUESTO`, es central: reconoce que el presupuesto de análisis puede ser inferior al universo total y que un ganador dentro del subconjunto evaluado no es automáticamente el mejor del universo.

`F-DT.2` reconoce que la existencia de un monkeypatch es señal de contrato observable adicional, no refutación automática; un reexport puede preservar el path. La ficha completa permite evaluar si esa preservación es viable.

La medición homogénea de M2 (actual vs proyectado) sobre el mismo modelo de fronteras elimina la ambigüedad de comparar estados no equivalentes. La tabla normativa de §11.7 elimina la ambigüedad de qué gates dispensa cada excepción.

La política cerrada de resolución AST (§7.1.1.bis) evita que referencias no-call ni ambigüedades desaparezcan silenciosamente. `REFERENCIA_AMBIGUA` como estado explícito garantiza que el análisis declare sus propios límites.

La equivalencia futura se ancla al estado real de la sesión y a listas nominales de tests. Los tests no se eliminan por conteo; eliminarlos requiere unidad separada (H13).

La demostración mecánica de reversibilidad en S48 usa clones externos independientes con manifiesto de tracked files SHA-256 + modo. `git worktree add` sobre el repo autoritativo queda prohibido para preservar READ-ONLY institucional sobre el repo original.

Los priors de S40 se someten al algoritmo determinista como cualquier otro candidato. F-DT.1 los excluye institucionalmente si tocan zonas prohibidas (no los refuta con R falsos); F-DT.2 los marca si son monkeypatch-cubiertos (no los descarta); F-DT.3/F-DT.4 los excluyen presupuestariamente si exceden umbrales; en otros casos reciben ficha completa.

La próxima unidad, si el veredicto y el humano lo permiten, es **S48**, no implementación.

---

**Fin del contrato v6.** Listo para sexta auditoría de ChatGPT.
