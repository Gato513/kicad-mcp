# 00 — Preflight extendido (Puerta 0 de `S47-H11-AMPLIACION-13-21`)

## 1. Identidad Git

```
$ pwd
/home/astra/Desktop/agent_proyect/kicad-mcp
$ git rev-parse --show-toplevel
/home/astra/Desktop/agent_proyect/kicad-mcp
$ git symbolic-ref --quiet --short HEAD
master
$ git rev-parse HEAD
33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
$ git rev-parse origin/master
33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
$ git status --porcelain=v1 -uall
(vacío)
$ git worktree list --porcelain
worktree /home/astra/Desktop/agent_proyect/kicad-mcp
HEAD 33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
branch refs/heads/master
```

R-P0.1 branch=master: OK. R-P0.2 HEAD no detached: OK. R-P0.3–5 working tree
limpio: OK. R-P0.6/9 `SHA_S47_ENTRADA` == checkpoint exigido
(`33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b`): OK. `origin/master` alineado: OK.
Una sola worktree, la activa: OK (R-P0.8 no aplica).

## 2. Hallazgo transitorio `.tmp` (documentado, no bloqueante)

Durante la primera pasada combinada de verificación de versiones (`uv --version`,
`uv run --frozen --no-sync {python,ruff,mypy,pytest} --version`,
`scripts/verificar_entorno.py`), `git status --porcelain=v1 -uall` reportó un
archivo vacío nuevo, `.tmp`, en la raíz del repositorio (0 bytes,
`Aug 8 16:51`). Investigación aislada — 6 pruebas: `uv --version` solo,
`uv run ... python --version` solo, `... ruff --version` solo,
`... mypy --version` solo, `... pytest --version` solo,
`scripts/verificar_entorno.py` solo, y luego la secuencia completa repetida
exactamente — **no reprodujo el archivo en ninguna de las 7 corridas
posteriores**. No se identificó qué proceso lo creó; no corresponde a ningún
comando exigido por Puerta 0 de forma determinista y repetible. Se eliminó
(`rm -f .tmp`, único comando de escritura sobre el working tree en esta sesión,
restaurando el estado previo verificado) y se reconfirmó árbol limpio antes de
continuar. No activa "mutación inevitable" (fe de erratas Regla 6, categoría 2)
porque no hay evidencia de que sea consecuencia necesaria de un comando
mandatado — es un evento de una sola ocurrencia, no reproducible. Se registra
aquí por transparencia, no como `NO_GO_ENTRADA`.

## 3. Hashes de instrumentos normativos

```
a2fbeee48e7304a9a957dd2b9b69d78eb290ee148cb5e66b0d90177d35ece6fc  contrato_S47-H11-AMPLIACION-13-21_v1.md
08e916d4dff2cb9827f3a222675a3c498dc9196599e0f9af5a0462a01cd95498  nota-invocacion-S47-H11-AMPLIACION-13-21.md
3b16079cd67357b17ff2d23064c6397454b8a06e4830684c0fa60c2eaac91402  contrato_S47-DT1-SLICE2-CARACTERIZACION_v6.md
63fe27be8ca2fa852d2f5dfef3996549edcced710b2b67275b970c19a36dcdd4  fe-de-erratas-ejecutiva-contrato-S47-v6.md
55850fdfb656468fe4758c3b782b7d853ec18d39cc8153ca1d6126ee653ee04a  auditoria-delta-fe-erratas-S47-v6.md
e746c33867bab1a626326522c5a94046e592e6c9835ecd8244b24237d7fb36b7  nota-invocacion-S47.md
```

Los seis coinciden exactamente con los valores anclados en contrato §0/§10 y
nota §1.

## 4. Custodia del paquete original (contrato §2.1.1)

```
Origen:  /tmp/tmp.ZedgZwIGVl.s47/S47/
Destino: /home/astra/Desktop/agent_proyect/archivos_temporales_contrato/custodia/S47-ORIGINAL-H11/
```

Destino no existía antes de esta sesión, no era symlink. Copia con `cp -a`.

```
$ (cd custodia/S47-ORIGINAL-H11 && sha256sum -c MANIFEST.sha256)
25 entradas: OK (exit 0)
$ (cd /tmp/tmp.ZedgZwIGVl.s47/S47 && sha256sum -c MANIFEST.sha256)
25 entradas: OK (exit 0)
$ diff -rq /tmp/tmp.ZedgZwIGVl.s47/S47 custodia/S47-ORIGINAL-H11
(vacío, exit 0)
```

Copia byte-idéntica confirmada; original no movido ni modificado.

## 5. Anclas de evidencia (§2 del contrato)

```
$ cd /tmp/tmp.ZedgZwIGVl.s47/S47 && sha256sum MANIFEST.sha256 CONTRACT.sha256 \
    02-candidatos/enumeracion.md 05-veredicto.md
cb3bfee2b25f1e34f3b46a3ead35be7b4525eb9efb24499d0a9dba0cf5fcf078  MANIFEST.sha256
7ee91544b55916c9e92afe216c271c0b742a0e5623f0f05c9373e4c761385456  CONTRACT.sha256
93f572849a0e41a0f270649cf17a3ae83974e547bf9b3d7248dbace951b7b67c  02-candidatos/enumeracion.md
ec538b9c99a45099aabe4c4cfdda17fd2ef9603971d6694931b8fbad9ac6df3a  05-veredicto.md
$ sha256sum -c MANIFEST.sha256   → 25 entradas OK, exit 0
$ sha256sum -c CONTRACT.sha256   → OK, exit 0

$ cd /tmp/tmp.ZedgZwIGVl.s47/S47-CORREGIDO-2 && sha256sum MANIFEST.sha256 \
    tools/inventory.py tools/cluster.py raw/inventory.json raw/clusters.json \
    raw/captures.json raw/coverage.json
53992da2711279cbc9e0d27d48aa7c835a140acac74b5cf957015b001005c5d0  MANIFEST.sha256
159087703980c4ad2bb4606b4c208ef289e1679495849d1442cacc18052a81e5  tools/inventory.py
a33a82695166399e86d64a9feb563ec35376808d48731c6e7e99d3768eed97b0  tools/cluster.py
1d6f8eb50a61fd02e07365e22e58f4a06b0d27f0af0f8167ac06fb38bc15db39  raw/inventory.json
dd2d097dc86d20e392f2689412daf042b7c6565cd635ff0f96c93ec11408d2de  raw/clusters.json
761242ad3ecf8f9b97c820f8177c20007e7a663803ee250efd8b4a46496f99ee  raw/captures.json
ea885be3c9bb7fc787713585450e6fb294694803bfc297dfb13ebe1e8eb430a4  raw/coverage.json
$ sha256sum -c MANIFEST.sha256   → todas las entradas OK, exit 0
```

Los 6 hashes de §2 (contrato) coinciden exactamente. `captures.json` y
`coverage.json` se hashean adicionalmente aquí porque son insumo directo de
Fase B/C de esta extensión (M2 d1, M4) y están cubiertos por el manifiesto de
`S47-CORREGIDO-2`.

## 6. Re-derivación Fase 2 (§2.1.2)

```
$ python3 .../S47-CORREGIDO-2/tools/inventory.py "$S47_TMP/inventory-ext.json"
OK -> inventory-ext.json   |V|=63  |E|=92
exit 0
$ cmp -s "$S47_TMP/inventory-ext.json" .../raw/inventory.json
exit 0

$ python3 .../S47-CORREGIDO-2/tools/cluster.py "$S47_TMP/inventory-ext.json" "$S47_TMP/clusters-ext.json"
N_universo_total=29 N_excluidos_institucional=8 N_excluidos_presup=0
N_supervivientes=21 N_fichas_completas=12 N_evaluados=12
exit 0
$ cmp -s "$S47_TMP/clusters-ext.json" .../raw/clusters.json
exit 0
```

`inventory-ext.json` y `clusters-ext.json` son **byte-idénticos** (mismo
SHA-256) a los `raw/*.json` anclados, re-derivados sobre el árbol de trabajo
actual (`src/kicad_mcp/tools/pcb.py` en HEAD `33e32ef…`). Confirma que el
código fuente no cambió desde que se generó la evidencia anclada.

## 7. Comparación de identidad (§2.1.3, `01-comparacion-identidad.py`)

```
$ python3 01-comparacion-identidad.py "$S47_TMP/clusters-ext.json" .../raw/clusters.json
IDENTIDAD_CONFORME
N_universo_total=29 N_excluidos_institucional=8 N_excluidos_presup=0 N_supervivientes=21
Posiciones 1-21 del array survivors coinciden exactamente con enumeracion.md §5
(1-12) y contrato §2 (13-21), mismo orden.
exit 0
```

Sin drift. Puerta 0 §2.1 completa (1)–(5): **coincidencia exacta**.

## 8. Entorno offline (§5.4 v6)

```
$S47_TMP fuera del working tree: OK
uv 0.12.0 (b88d7c5c4 2026-07-28 x86_64-unknown-linux-gnu)
Modo (a) disponible: uv run --frozen --no-sync
  python 3.14.3 / ruff 0.15.20 / mypy 2.2.0 / pytest 9.1.1
PYTHONPYCACHEPREFIX / MYPY_CACHE_DIR / RUFF_CACHE_DIR / UV_CACHE_DIR: OK,
  todas bajo $S47_TMP.
PYTEST_ADDOPTS='' : OK
GIT_OPTIONAL_LOCKS=0 : OK
$ uv run --frozen --no-sync python scripts/verificar_entorno.py
13 OK · 3 WARN (rama con cambios sin commit — falso positivo del .tmp
  transitorio de §2, no reproducible; branch, IPC no visible, freerouting
  jar no seteada, ninguno bloqueante para MVP solo-lectura) · 0 FAIL
exit 0
```

Sin `uv sync`, sin acceso a red.

## 9. Baseline offline

```
$ RUFF check                    → All checks passed! (exit 0)
$ RUFF format --check           → 87 files already formatted (exit 0)
$ MYPY src/                     → Success: no issues found in 35 source files (exit 0)
$ PYTEST -o "cache_dir=$S47_TMP/pytest-cache" \
    -m "not integration and not integration_gui and not integration_gui_slow" \
    -v --no-header
406 passed, 77 deselected in 34.97s (exit 0)
```

`BASELINE_ACTUAL_OBSERVADO = {passed: 406, failed: 0, errors: 0, deselected: 77,
skipped: 0}`. Coincide exactamente con `HIST_*` de S47 original (`05-veredicto.md
§2`). R-BL.0 no se activa, R-BL.1 conforme, R-BL.2 no se activa (checkpoint
exacto, drift 0).

## 10. Veredicto de Puerta 0

**GO.** Todas las condiciones de contrato §2.1(1)-(5) y v6 §5 se cumplen.
Ninguna condición de `NO_GO_ENTRADA` (contrato §9, fe de erratas Regla 6) se
activó. Se procede a Fase 3 (caracterización de los 9 candidatos).
