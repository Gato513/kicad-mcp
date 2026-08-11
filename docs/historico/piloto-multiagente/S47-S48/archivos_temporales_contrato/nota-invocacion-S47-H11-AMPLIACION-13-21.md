# NOTA DE INVOCACIÓN PREPARADA — `S47-H11-AMPLIACION-13-21`

**Estado:** instrumento completo pendiente de revisión independiente y aceptación humana expresa. **No es una invocación efectiva y no autoriza ejecución.**

**Separación obligatoria:** la aceptación humana debe ocurrir en un acto posterior que cite los SHA-256 completos de los bytes finales del contrato y de esta nota. Solo después puede Gato emitir una orden de invocación separada. Entregar esta nota a Claude Code, leerla o revisarla no constituye aceptación, firma ni invocación.

## 1. Instrumentos normativos

| Instrumento | Archivo / ruta | SHA-256 completo |
|---|---|---|
| Contrato de ampliación | `contrato_S47-H11-AMPLIACION-13-21_v1.md` | `a2fbeee48e7304a9a957dd2b9b69d78eb290ee148cb5e66b0d90177d35ece6fc` |
| Contrato base S47 v6 | `contrato_S47-DT1-SLICE2-CARACTERIZACION_v6.md` | `3b16079cd67357b17ff2d23064c6397454b8a06e4830684c0fa60c2eaac91402` |
| Fe de erratas v6 | `fe-de-erratas-ejecutiva-contrato-S47-v6.md` | `63fe27be8ca2fa852d2f5dfef3996549edcced710b2b67275b970c19a36dcdd4` |
| Auditoría delta de erratas | `auditoria-delta-fe-erratas-S47-v6.md` | `55850fdfb656468fe4758c3b782b7d853ec18d39cc8153ca1d6126ee653ee04a` |
| Nota original S47 | `nota-invocacion-S47.md` | `e746c33867bab1a626326522c5a94046e592e6c9835ecd8244b24237d7fb36b7` |

Rige la precedencia cerrada del contrato de ampliación: H11; adaptación explícita H11; fe de erratas y su lectura conservadora; v6 en lo restante. Esta nota no altera esa precedencia, criterios, entradas, presupuesto ni puertas.

## 2. H11 preservada como procedencia humana

La Autoridad humana, Gato, suministró directamente para esta unidad la siguiente decisión vinculante, que se incorpora sin convertirla en orden de ejecución:

```text
H11 autorizó preparar una ampliación acotada de S47 para materializar y
caracterizar exclusivamente los nueve supervivientes pendientes,
correspondientes a los candidatos 13–21 ya enumerados en la evidencia
original.

Debe preservarse 0 APTO/APTO_CONDICIONAL entre los 12 candidatos
materializados. No puede extrapolarse 0/12 → 0/21. La conclusión sobre los
21 supervivientes solo puede emitirse después de completar y reconciliar
formalmente 12 + 9 = 21.

H11 no autorizó ejecución. Autorizó preparar el contrato y la nota para
revisión y posterior aceptación humana.

Prohibiciones: no rediseñar ni iniciar S48; no implementar DT1 Slice 2; no
modificar los primeros 12; no ampliar el universo más allá de los nueve
pendientes; no alterar el resultado técnico validado; no declarar
anticipadamente un resultado sobre 21; no cerrar DT1; no commit, push, PR o
merge.
```

Procedencia: turno humano del proyecto `MCP_AUDITOR_KICAD`, Gato, informado como emitido el `2026-08-08 14:19:59 UTC-03:00`, `America/Asuncion`. Esta transcripción no sustituye el acto posterior de aceptación por hashes finales.

## 3. Base y anclas de evidencia

```text
Repositorio:                         /home/astra/Desktop/agent_proyect/kicad-mcp
HEAD exigido:                        33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
Paquete S47 original:               /tmp/tmp.ZedgZwIGVl.s47/S47/
SHA-256 de MANIFEST.sha256:         cb3bfee2b25f1e34f3b46a3ead35be7b4525eb9efb24499d0a9dba0cf5fcf078
SHA-256 de CONTRACT.sha256:         7ee91544b55916c9e92afe216c271c0b742a0e5623f0f05c9373e4c761385456
SHA-256 de enumeracion.md:          93f572849a0e41a0f270649cf17a3ae83974e547bf9b3d7248dbace951b7b67c
SHA-256 de 05-veredicto.md:         ec538b9c99a45099aabe4c4cfdda17fd2ef9603971d6694931b8fbad9ac6df3a
Unidad reproducible corregida:      /tmp/tmp.ZedgZwIGVl.s47/S47-CORREGIDO-2/
SHA-256 de su MANIFEST.sha256:      53992da2711279cbc9e0d27d48aa7c835a140acac74b5cf957015b001005c5d0
SHA-256 tools/inventory.py:         159087703980c4ad2bb4606b4c208ef289e1679495849d1442cacc18052a81e5
SHA-256 tools/cluster.py:           a33a82695166399e86d64a9feb563ec35376808d48731c6e7e99d3768eed97b0
SHA-256 raw/inventory.json:         1d6f8eb50a61fd02e07365e22e58f4a06b0d27f0af0f8167ac06fb38bc15db39
SHA-256 raw/clusters.json:          dd2d097dc86d20e392f2689412daf042b7c6565cd635ff0f96c93ec11408d2de
```

El paquete original y la unidad reproducible son entradas de solo lectura. Si falta una, un hash difiere o un manifiesto no verifica, la salida es `NO_GO_ENTRADA`.

## 4. Alcance exacto y presupuesto

```text
13. {_similars}                    LOC=13
14. {_via_params, add_via}         LOC=110
15. {delete_track}                 LOC=51
16. {delete_via}                   LOC=24
17. {get_component_detail}         LOC=30
18. {get_tracks}                   LOC=92
19. {reload_board_from_disk}       LOC=59
20. {save_board}                   LOC=44
21. {set_footprint_ref}            LOC=116
```

`UMBRAL_P_STOP_FICHAS_EXT=9`: exactamente nueve fichas nuevas, una por identidad, mismo orden, sin suplentes ni reutilización. Para reconciliación solamente, `UMBRAL_P_STOP_FICHAS_ACUMULADO=21`. Una detención antes de nueve fichas deja unidad `INCOMPLETA` y prohíbe veredicto sobre los 21.

## 5. Preparación de sesión y destino seguro

Claude Code no recibe autorización para ejecutar mediante esta nota. Tras revisión independiente y aceptación humana por hashes, la orden separada de Gato podrá permitir que el ejecutor cree:

```bash
export S47_TMP="$(mktemp -d --suffix=.s47ext)"
test -n "$S47_TMP"
test "$(realpath "$S47_TMP")" != "/tmp/tmp.ZedgZwIGVl.s47"
export S47_EXT_DEST="$S47_TMP/S47-EXT-13-21"
test "$(realpath -m "$S47_EXT_DEST")" = "$(realpath "$S47_TMP")/S47-EXT-13-21"
test ! -e "$S47_EXT_DEST"
test ! -L "$S47_EXT_DEST"
```

Cada comando debe finalizar con exit 0 antes de crear el destino. Cualquier existencia, symlink, escape o ambigüedad produce `NO_GO_ENTRADA`; no se borra, mezcla ni sobrescribe nada. No hay ruta pendiente que deba sustituirse en estos bytes.

## 6. Preflight obligatorio

Con `GIT_OPTIONAL_LOCKS=0`, `PYTEST_ADDOPTS=''` y caches bajo `$S47_TMP`, ejecutar y registrar comando, stdout, stderr y exit code:

```bash
pwd
git rev-parse --show-toplevel
git symbolic-ref --quiet --short HEAD
git rev-parse HEAD
git rev-parse origin/master
git status --porcelain=v1 -uall
git worktree list --porcelain
sha256sum contrato_S47-H11-AMPLIACION-13-21_v1.md
sha256sum contrato_S47-DT1-SLICE2-CARACTERIZACION_v6.md
sha256sum fe-de-erratas-ejecutiva-contrato-S47-v6.md
sha256sum auditoria-delta-fe-erratas-S47-v6.md
cd /tmp/tmp.ZedgZwIGVl.s47/S47
sha256sum MANIFEST.sha256 CONTRACT.sha256 02-candidatos/enumeracion.md 05-veredicto.md
sha256sum -c MANIFEST.sha256
sha256sum -c CONTRACT.sha256
cd /tmp/tmp.ZedgZwIGVl.s47/S47-CORREGIDO-2
sha256sum MANIFEST.sha256 tools/inventory.py tools/cluster.py raw/inventory.json raw/clusters.json
sha256sum -c MANIFEST.sha256
cd /home/astra/Desktop/agent_proyect/kicad-mcp
python /tmp/tmp.ZedgZwIGVl.s47/S47-CORREGIDO-2/tools/inventory.py "$S47_TMP/inventory-ext.json"
cmp -s "$S47_TMP/inventory-ext.json" /tmp/tmp.ZedgZwIGVl.s47/S47-CORREGIDO-2/raw/inventory.json
python /tmp/tmp.ZedgZwIGVl.s47/S47-CORREGIDO-2/tools/cluster.py "$S47_TMP/inventory-ext.json" "$S47_TMP/clusters-ext.json"
cmp -s "$S47_TMP/clusters-ext.json" /tmp/tmp.ZedgZwIGVl.s47/S47-CORREGIDO-2/raw/clusters.json
```

Luego ejecutar la comparación JSON exacta definida en contrato §2.1 mediante `01-comparacion-identidad.py`, conservar ese script y exigir exit 0. Deben reproducirse `29 → 8 exclusiones institucionales → 21 supervivientes`, con las 21 identidades en orden y 13–21 iguales a §4.

Seleccionar exclusivamente el modo offline de v6 §5.4 (`uv run --frozen --no-sync ...` si ya funciona; en caso contrario los binarios existentes de `.venv/`), validar versiones, caches y `scripts/verificar_entorno.py`, y ejecutar exactamente:

```bash
$RUFF check
$RUFF format --check
$MYPY src/
$PYTEST -o "cache_dir=$S47_TMP/pytest-cache" \
  -m "not integration and not integration_gui and not integration_gui_slow" \
  -v --no-header
```

Registrar todos los exits y exigir `passed=406`, `failed=0`, `errors=0`, `deselected=77`, sin drift negativo conforme a v6. **No ejecutar `uv sync`, no descargar dependencias y no acceder a red.** Si el entorno no satisface el contrato, `NO_GO_ENTRADA`.

## 7. Salida obligatoria

La unidad nueva y manifestada `$S47_EXT_DEST/` debe contener exactamente el inventario obligatorio del contrato §7, incluidos:

- nueve fichas 13–21;
- `05-RECONCILIACION.md`;
- `INFORME-EJECUCION.md`;
- `COMANDOS-Y-EXIT-CODES.md`;
- `GIT-ANTES-DESPUES.md`;
- `01-comparacion-identidad.py`;
- contrato auditado, `CONTRACT.sha256`, metadatos, procedencia, limitaciones y `MANIFEST.sha256`.

El manifiesto debe cubrir todos los archivos regulares salvo sí mismo, con rutas relativas sin `..`, y verificar con exit 0. El estado Git antes y después debe conservar el mismo HEAD y working tree limpio.

## 8. Reconciliación obligatoria

Solo tras completar las nueve fichas se combinan mecánicamente las 12 clasificaciones congeladas y las nueve nuevas. Para v6 §11.3 regla 5 se usa únicamente `UMBRAL_P_STOP_FICHAS_ACUMULADO=21`; reglas 6–13 permanecen literales.

Con ocho exclusiones institucionales:

- un `APTO` implica `GO_DENTRO_DEL_PRESUPUESTO`, no `GO`;
- 21 `NO_APTO` implican `NO_GO_POR_PRESUPUESTO`, no `NO_GO`;
- `GO_CONDICIONAL_PROPUESTO` y `EVIDENCIA_INSUFICIENTE` conservan sus reglas v6/errata.

El resultado se limita a `ALCANCE_SUPERVIVIENTES_21`, mantiene procedencia separada `12 + 9`, no equipara ganador de subconjunto con ganador global y nunca autoriza implementación o S48.

## 9. Reglas de parada

Emitir `NO_GO_ENTRADA` y no caracterizar si ocurre cualquiera de estos casos:

- falta aceptación humana previa y separada que cite los hashes finales del contrato y esta nota;
- falla identidad Git, entorno offline, hash, manifiesto, herramienta, insumo o comparación 29→8→21;
- el destino existe, es enlace, es ambiguo o escapa de `$S47_TMP`;
- se intenta mutar evidencia original, repositorio o scope;
- la identidad de cualquier candidato deriva;
- para continuar sería necesario acceder a red, sincronizar dependencias o corregir evidencia.

No se corrige silenciosamente ninguna deriva. Una detención posterior al inicio de fichas conserva la unidad como `INCOMPLETA` y no permite reconciliación global.

## 10. Prohibiciones vinculantes

```text
- No rediseñar ni iniciar S48.
- No implementar DT1 Slice 2.
- No modificar, investigar de nuevo, reclasificar ni reescribir candidatos 1–12.
- No ampliar el universo más allá de candidatos 13–21.
- No alterar 0 APTO/APTO_CONDICIONAL entre los 12 congelados.
- No declarar anticipadamente un resultado sobre los 21.
- No cerrar DT1.
- No commit, push, PR o merge.
- No sobrescribir unidades existentes.
- No convertir ningún resultado favorable en autorización de implementación.
```

## 11. Revisión y autoridad siguiente

La unidad producida requiere revisión independiente de las nueve fichas y de `05-RECONCILIACION.md`, seguida de reconciliación ChatGPT. El ejecutor no es juez único. Ningún resultado activa automáticamente S48, Slice 2, implementación ni operaciones Git.

Secuencia autorizable, todavía no autorizada:

```text
1. Revisor independiente distinto del escritor actual revisa los bytes finales.
2. Gato acepta expresamente contrato y nota citando ambos SHA-256 completos.
3. Gato emite una orden separada de invocación a Claude Code.
4. Claude Code ejecuta exclusivamente el alcance autorizado.
5. Revisión independiente del paquete y reconciliación ChatGPT.
6. Gato decide cualquier paso posterior.
```

**No existen campos pendientes, marcadores ni decisiones operativas por sustituir en esta nota. La fecha, la aceptación y la ruta concreta de sesión pertenecen a actos posteriores separados y no se simulan aquí.**

---

Fin de la nota preparada. Estado de ejecución: `NO AUTORIZADA`.
