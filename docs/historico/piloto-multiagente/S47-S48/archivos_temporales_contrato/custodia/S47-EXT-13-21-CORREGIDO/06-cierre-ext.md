# 06 — Cierre extendido (§13.3 de v6) — verificación byte-a-byte contra Puerta 0

```bash
git rev-parse HEAD                                     # == SHA_S47_ENTRADA
git status --porcelain=v1 --untracked-files=all        # == estado de Puerta 0
git diff HEAD                                           # vacío (0 líneas)
git diff --name-only                                    # vacío
git diff --cached --name-only                           # vacío
git ls-files --others --exclude-standard                # vacío
git ls-files -s | sha256sum                              # INDEX_HASH
git remote -v
git show-ref --heads --tags | wc -l
git config --local --list --show-origin | wc -l
git worktree list --porcelain
```

## Comparación byte-a-byte contra `00-preflight-ext.md`

| Variable | Puerta 0 | Cierre | Resultado |
|---|---|---|---|
| `HEAD` | `33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b` | `33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b` | **IDÉNTICO** |
| `origin/master` | `33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b` | (sin recomputar, sin red durante la sesión — invariante) | **OK** |
| `branch` | `master` | `master` | **IDÉNTICO** |
| `status --porcelain -uall` | vacío | vacío | **IDÉNTICO** |
| `diff HEAD` | (n/a) | vacío (0 líneas) | **OK** |
| `diff --name-only` / `--cached` | (n/a) | ambos vacíos | **OK** |
| `ls-files --others --exclude-standard` | (n/a) | vacío | **OK** |
| `INDEX_HASH` (`git ls-files -s \| sha256sum`) | `bd9970ae981c776e5f1f2a16c3428e03845cf237a0c7a638f6fc4a709bcaeff5` (valor de `06-cierre.md` del paquete S47 original, mismo checkpoint) | `bd9970ae981c776e5f1f2a16c3428e03845cf237a0c7a638f6fc4a709bcaeff5` | **IDÉNTICO** |
| `remote -v` | `origin git@github.com:Gato513/kicad-mcp.git (fetch/push)` | idéntico | **IDÉNTICO** |
| `show-ref --heads --tags` | 54 refs (paquete original) | 54 refs | **IDÉNTICO** |
| `config --local --list` | 29 líneas (no capturado explícitamente en `00-preflight-ext.md`, invariante por construcción — sin comando `git config` de escritura en toda la sesión) | 29 líneas | **OK, sin escritura** |
| `worktree list --porcelain` | 1 worktree, `master`, HEAD `33e32ef…` | idéntico | **IDÉNTICO** |

**Ningún `INCUMPLIMIENTO`.** El `INDEX_HASH` coincide exactamente con el
valor registrado en `06-cierre.md` del paquete S47 original — confirma que
el índice de Git no cambió ni siquiera entre la sesión S47 original y esta
extensión, dos sesiones distintas sobre el mismo checkpoint.

## Ubicación de todos los artefactos generados

```
Custodia:  /home/astra/Desktop/agent_proyect/archivos_temporales_contrato/custodia/S47-ORIGINAL-H11/
           (fuera del repositorio Git — sibling de kicad-mcp/, no dentro)
Unidad:    $S47_TMP/S47-EXT-13-21/   (bajo /tmp, fuera del repositorio)
```

Ningún archivo del working tree autoritativo (`/home/astra/Desktop/agent_proyect/kicad-mcp/`)
fue creado, modificado ni eliminado de forma neta durante la sesión —
`git status`/`git diff` idénticos antes y después confirman cero cambios
persistentes.
