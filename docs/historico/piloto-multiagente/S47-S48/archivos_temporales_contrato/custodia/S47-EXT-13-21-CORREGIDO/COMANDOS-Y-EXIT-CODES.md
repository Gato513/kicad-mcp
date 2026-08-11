# COMANDOS-Y-EXIT-CODES — `S47-EXT-13-21`

Todos los comandos ejecutados en esta sesión, en orden, con exit code.
`GIT_OPTIONAL_LOCKS=0` y `PYTEST_ADDOPTS=''` activas durante toda la sesión.
Caches (`PYTHONPYCACHEPREFIX`, `MYPY_CACHE_DIR`, `RUFF_CACHE_DIR`,
`UV_CACHE_DIR`) bajo `$S47_TMP` durante toda la sesión.

## Fase A — Preparación y Puerta 0

```
$ mktemp -d --suffix=.s47ext                                          exit 0
$ realpath "$S47_TMP" (≠ /tmp/tmp.ZedgZwIGVl.s47, fuera del repo)      exit 0
$ realpath -m "$S47_TMP/S47-EXT-13-21" (bajo $S47_TMP)                 exit 0
$ test ! -e "$S47_EXT_DEST"                                            exit 0
$ test ! -L "$S47_EXT_DEST"                                            exit 0
$ cp -a /tmp/tmp.ZedgZwIGVl.s47/S47 <custodia>                         exit 0
$ (cd <custodia> && sha256sum -c MANIFEST.sha256)                      exit 0 (25 OK)
$ (cd /tmp/…/S47 && sha256sum -c MANIFEST.sha256)                      exit 0 (25 OK)
$ diff -rq /tmp/…/S47 <custodia>                                       exit 0 (vacío)
$ git rev-parse --show-toplevel                                        exit 0
$ git symbolic-ref --quiet --short HEAD                                exit 0 (master)
$ git rev-parse HEAD                                                   exit 0 (33e32ef…)
$ git rev-parse origin/master                                          exit 0 (33e32ef…, igual)
$ git status --porcelain=v1 -uall                                      exit 0 (vacío)
$ git worktree list --porcelain                                        exit 0 (1 worktree)
$ sha256sum <6 instrumentos normativos>                                exit 0 (6/6 coinciden)
$ (cd /tmp/…/S47 && sha256sum MANIFEST.sha256 CONTRACT.sha256
    02-candidatos/enumeracion.md 05-veredicto.md)                      exit 0 (4/4 coinciden)
$ sha256sum -c MANIFEST.sha256 (S47 original)                          exit 0 (25 OK)
$ sha256sum -c CONTRACT.sha256 (S47 original)                          exit 0 (OK)
$ (cd /tmp/…/S47-CORREGIDO-2 && sha256sum MANIFEST.sha256
    tools/inventory.py tools/cluster.py raw/inventory.json
    raw/clusters.json raw/captures.json raw/coverage.json)             exit 0 (7/7 coinciden)
$ sha256sum -c MANIFEST.sha256 (S47-CORREGIDO-2)                       exit 0 (todas OK)
$ python3 tools/inventory.py "$S47_TMP/inventory-ext.json"             exit 0
$ cmp -s inventory-ext.json raw/inventory.json                         exit 0 (byte-idéntico)
$ python3 tools/cluster.py inventory-ext.json "$S47_TMP/clusters-ext.json"  exit 0
$ cmp -s clusters-ext.json raw/clusters.json                           exit 0 (byte-idéntico)
$ python3 01-comparacion-identidad.py clusters-ext.json raw/clusters.json  exit 0 (IDENTIDAD_CONFORME)
$ uv --version                                                         exit 0
$ uv run --frozen --no-sync python --version                           exit 0
$ uv run --frozen --no-sync ruff --version                             exit 0
$ uv run --frozen --no-sync mypy --version                             exit 0
$ uv run --frozen --no-sync pytest --version                           exit 0
$ uv run --frozen --no-sync python scripts/verificar_entorno.py        exit 0 (13 OK · 3 WARN · 0 FAIL)
```

**Investigación del hallazgo `.tmp` (H-S47EXT-02)** — 7 comandos adicionales
de diagnóstico aislado, todos read-only salvo el `rm -f .tmp` final:

```
$ rm -f .tmp                                                           exit 0
$ git status --porcelain=v1 -uall (baseline limpio confirmado)         exit 0 (vacío)
$ uv --version (aislado)                                    → status   exit 0 (vacío, no reproduce)
$ uv run --frozen --no-sync python --version (aislado)       → status  exit 0 (vacío, no reproduce)
$ uv run --frozen --no-sync ruff --version (aislado)         → status  exit 0 (vacío, no reproduce)
$ uv run --frozen --no-sync mypy --version (aislado)         → status  exit 0 (vacío, no reproduce)
$ uv run --frozen --no-sync pytest --version (aislado)       → status  exit 0 (vacío, no reproduce)
$ uv run --frozen --no-sync python scripts/verificar_entorno.py (aislado) exit 0 (vacío, no reproduce)
$ <secuencia completa repetida exacta>                                 exit 0 (vacío en todos los pasos)
```

## Fase A — Baseline offline

```
$ uv run --frozen --no-sync ruff check                                 exit 0 (All checks passed!)
$ uv run --frozen --no-sync ruff format --check                        exit 0 (87 files already formatted)
$ uv run --frozen --no-sync mypy src/                                  exit 0 (Success: 35 source files)
$ uv run --frozen --no-sync pytest -o "cache_dir=$S47_TMP/pytest-cache" \
    -m "not integration and not integration_gui and not integration_gui_slow" \
    -v --no-header                                                     exit 0
    → 406 passed, 77 deselected, 0 failed, 0 errors, 34.97s
    → coincide exactamente con HIST_PASSED(406)/HIST_DESELECTED(77)/
      HIST_FAILED(0)/HIST_ERRORS(0). R-BL.0/R-BL.2 no se activan.
$ mkdir -p "$S47_EXT_DEST"                                              exit 0
```

## Fase B — M2 para candidatos 13-21

```
$ python3 02-m2-ext-input.py clusters-ext.json clusters-check-1-12.json "0:12"  exit 0
$ python3 tools/m2.py inventory-ext.json clusters-check-1-12.json \
    raw/captures.json m2-check-1-12.json                               exit 0
$ cmp -s m2-check-1-12.json raw/m2.json                                exit 0
    → CONTROL DE SANIDAD: byte-idéntico. Valida el procedimiento de
      derivación antes de aplicarlo a 13-21.
$ python3 02-m2-ext-input.py clusters-ext.json clusters-ext-1321.json "12:21"  exit 0
$ python3 tools/m2.py inventory-ext.json clusters-ext-1321.json \
    raw/captures.json m2-ext.json                                      exit 0
```

## Fase C/D — Lectura de fuente (solo lectura, sin exit code relevante)

Lectura de `src/kicad_mcp/tools/pcb.py` (secciones de los 9 candidatos:
`_similars` L95-97, `_via_params` L3146-3147, `add_via` L1332-1439,
`save_board` L1446-1480, `reload_board_from_disk` L1489-1545, `delete_track`
L1702-1719, `delete_via` L1726-1743, `get_component_detail` L1975-1995,
`get_tracks` L1749-1834, `set_footprint_ref` L1039-1152) y
`src/kicad_mcp/tools/_mutating.py` (decorador `mutating_tool`). Sin
escritura.

## Verificación de cierre

```
$ git rev-parse HEAD (después)                                         exit 0 (33e32ef…, idéntico)
$ git status --porcelain=v1 -uall (después)                            exit 0 (vacío)
$ git worktree list --porcelain (después)                              exit 0 (1 worktree, idéntico)
$ cmp -s CONTRATO-AUDITADO.md .../contrato_S47-H11-AMPLIACION-13-21_v1.md  exit 0
$ sha256sum CONTRATO-AUDITADO.md → a2fbeee4…ece6fc (idéntico al aceptado) 
```

**Ningún comando terminó con exit code distinto de 0 salvo los deliberados
de verificación negativa** (`test ! -e`, `test ! -L`, que retornan 0 cuando
la condición negativa se cumple — comportamiento esperado, no fallo).
