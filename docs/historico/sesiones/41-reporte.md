# Sesión 41 — DT1 Slice 1: extracción de encoders ad hoc

```text
Sesión: 41
Objetivo: implementar DT1 Slice 1 — extracción de encoders ad hoc
Rama: sesion/41-dt1-pcb-encoders
SHA inicial: 72bd34c17728915ce9d30e27101832fb31336842
Commit funcional: 69b5b0e394a935cb864c17b02b9ad4b2e95621d0
Merge commit: 8d3696b890b4719ef19a96db26735b25da0214b5
PR: #13
Estado: cerrada y mergeada
```

**Ejecutor operativo del slice funcional:** Claude Code.

**Autor Git registrado del commit funcional:** Gato513.

**Revisor independiente del slice funcional:** Codex, modo read-only.

**Autor operativo de este cierre documental:** Codex.

**Estado de este cierre documental al redactar el reporte:** commit local
pendiente de revisión independiente, push, PR, CI y decisión humana de merge.

## 1. Objetivo

Extraer el cluster de encoders ad hoc caracterizado y autorizado en sesión
40, sin cambiar comportamiento ni ampliar DT1. **HECHO_VERIFICADO:** Git
confirma que el PR #13 contiene un único commit funcional y que el merge
incorpora sólo `pcb.py` y el nuevo `pcb_encoders.py`.

## 2. Preflight

**HECHO_HISTORICO:** la sesión partió de `72bd34c`, rama limpia
`sesion/41-dt1-pcb-encoders`, con el Slice 1 aprobado por
`docs/analisis/40-dt1-caracterizacion.md`. **HECHO_VERIFICADO:** `69b5b0e` es
hijo directo de `72bd34c`; `8d3696b` es el merge commit de PR #13.

## 3. Intervención humana por `uv sync`

**HECHO_HISTORICO:** el preflight detectó el entorno Python sin sincronizar y
la sincronización mediante `uv sync` requirió intervención humana.
**NO_VERIFICABLE_EN_EL_ENTORNO:** no existe una traza versionada que permita
atribuir el comando exacto o su salida a una persona concreta.

## 4. Baseline

**HECHO_HISTORICO:** antes del cambio se fijaron 32 tools MCP totales, 19
registradas por `pcb.py`, 12 marcas `@mutating_tool` y 406 tests offline.
Estas cifras coinciden con la caracterización 40 y el cuerpo público del PR
#13; no se presentan como ejecución de esta bitácora.

## 5. Alcance

El alcance aprobado fue una extracción mecánica del cluster de encoders y
filtros. No incluyó nuevas tools, contratos, dependencias ni cambios de
sanitización.

## 6. Cambios

**HECHO_VERIFICADO:** se creó
`src/kicad_mcp/tools/pcb_encoders.py` (294 líneas en el commit) y se redujo
`pcb.py`; el diff funcional suma 311 inserciones y 275 borrados en dos
archivos.

## 7. Funciones y constante trasladadas

**HECHO_VERIFICADO:** se trasladaron `_WHITESPACE_RE` y las siete funciones
`_sanitize_space_delimited`, `_zone_is_axis_aligned_rect`,
`_zones_filter_desc`, `_encode_zones`, `_encode_component_detail`,
`_tracks_filter_desc` y `_encode_tracks`.

## 8. Política de re-exports

**HECHO_VERIFICADO:** `pcb.py` importa con alias redundante y re-exporta
explícitamente las siete funciones. Esto preserva los imports privados
existentes usados por tests y consumidores conocidos.

## 9. Imports eliminados

**HECHO_VERIFICADO:** `pcb.py` dejó de importar `re`, `Final`,
`ComponentDetail` y `toon.encoder._sanitize` cuando dejaron de ser necesarios
allí; esos imports viven donde corresponde en `pcb_encoders.py`. `CopperItem`,
`Mm` y `ZoneItem` permanecen importados en `pcb.py` porque otros helpers aún
los consumen.

## 10. Desviación por formato/isort

**HECHO_HISTORICO:** Ruff/isort normalizó los re-exports a una sentencia por
símbolo. **HECHO_VERIFICADO:** el comentario versionado en `pcb.py` documenta
la causa y el resultado estable; no implica cambio funcional.

## 11. Smoke tests

**NO_VERIFICABLE_EN_EL_ENTORNO:** no quedó salida versionada ni evidencia
consolidada suficiente para afirmar el comando, alcance o resultado de smoke
tests separados de los 21 tests focales. No se reconstruye ese dato.

## 12. Tests focales

**HECHO_HISTORICO:** 21 tests focales pasaron. El cuerpo público del PR #13
confirma el conteo; no es una ejecución actual.

## 13. Gates completos

**HECHO_HISTORICO:** `pytest` offline: 406 passed, 77 deselected; `ruff
check`, `ruff format --check` y `mypy src/`: verdes. Estos resultados
pertenecen a sesión 41 y se mantienen separados de cualquier reejecución
posterior.

## 14. Verificación de superficie MCP

**HECHO_HISTORICO:** se verificaron 32 tools MCP totales y 19 registradas por
`pcb.py`, sin cambios de firmas ni superficie. El PR #13 registra el mismo
resultado.

## 15. Verificación de marcas mutantes

**HECHO_HISTORICO:** se verificaron 12 tools con `@mutating_tool`, sin cambio
en flags ni en las excepciones deliberadas de ADR-0014.

## 16. Verificación de goldens

**HECHO_HISTORICO:** los tres goldens de tracks, zonas y detalle de componente
permanecieron byte-exactos. **HECHO_VERIFICADO:** el commit funcional no
modifica ningún archivo de `tests/golden/`.

## 17. Equivalencia AST

**HECHO_HISTORICO:** la sesión comparó el AST de las siete funciones antes y
después y obtuvo equivalencia. El cuerpo público del PR #13 registra esa
verificación; la evidencia completa del script no quedó versionada.

## 18. Revisión independiente de Codex

**HECHO_HISTORICO:** Codex emitió `APROBAR_COMMIT` sobre el commit funcional
`69b5b0e394a935cb864c17b02b9ad4b2e95621d0`.
**NO_VERIFICABLE_EN_EL_ENTORNO:** el texto íntegro de esa revisión no forma
parte del historial Git consultado.

## 19. Incidencia de `.mypy_cache`

**HECHO_HISTORICO:** `mypy` escribió `.mypy_cache`, efecto operativo ignorado
por Git; se comprobó que no añadió cambios trackeados. No se versionó cache.

## 20. Push y PR realizados por el humano

**HECHO_HISTORICO:** el humano realizó el push y abrió PR #13.
**HECHO_VERIFICADO:** la API pública identifica head
`sesion/41-dt1-pcb-encoders`, base `master` y commit `69b5b0e`.

## 21. Incidencia de GitHub Actions

**HECHO_HISTORICO:** inicialmente no se materializó uno de los eventos de CI
esperados para el PR. No se atribuye una causa técnica no demostrada.

## 22. Resolución mediante cierre/reapertura del PR

**HECHO_HISTORICO:** el humano cerró y reabrió el PR para provocar el evento
faltante. **NO_VERIFICABLE_EN_EL_ENTORNO:** la consulta de eventos fue
limitada por la API pública y no se obtuvo la secuencia completa.

## 23. Resultados de CI

**HECHO_HISTORICO:** finalizaron con éxito dos runs, uno por `push` y otro por
`pull_request`. No se confunden con gates reejecutados durante este cierre
documental.

## 24. Merge

**HECHO_VERIFICADO:** PR #13 fue mergeado en `master` el
2026-08-07T01:33:51Z; merge commit `8d3696b890b4719ef19a96db26735b25da0214b5`.

## 25. Alcance no tocado

**HECHO_VERIFICADO:** el diff funcional no toca tests, specs, goldens, ADR,
CI ni dependencias. **HECHO_HISTORICO:** tampoco cambió P1-2, DT3,
`route_board`, `run_drc` ni `run_autoroute`.

## 26. Deuda abierta

P1-2 (`kiid`) continúa abierto y requiere decisión de diseño. DT3 continúa
abierta. La partición general de `pcb.py` no termina con este slice.

## 27. Decisión sobre DT1

```text
DT1 Slice 1 — encoders ad hoc: CERRADO.
DT1 general: ABIERTA.
P1-2: ABIERTA y no modificada.
DT3: ABIERTA y no modificada.
```

## 28. Siguiente paso recomendado

**INFERENCIA:** recaracterizar `tools/pcb.py` post-Slice 1 y elegir el segundo
cluster por cohesión, dependencias, consumidores, monkeypatches, ciclos,
re-exports, cobertura y reversibilidad, no sólo por LOC.
**DECISION_HUMANA_PENDIENTE:** autorizar el cluster y la sesión concreta.

## 29. Fricciones metodológicas

La sincronización del entorno y las acciones remotas dependieron del humano;
la normalización automática de imports produjo una desviación textual
explicable; y una anomalía de eventos de GitHub Actions se resolvió de forma
operativa sin convertir una hipótesis causal en hecho.

## 30. Evidencia y comandos

Fuentes: historial Git de `72bd34c`, `69b5b0e`, `8d3696b`; diff
`72bd34c..69b5b0e`; `docs/analisis/40-dt1-caracterizacion.md`; cuerpo y
metadatos públicos del PR #13; resultados consolidados suministrados para el
cierre.

```bash
git show --stat 72bd34c17728915ce9d30e27101832fb31336842
git show --stat 69b5b0e394a935cb864c17b02b9ad4b2e95621d0
git show --stat 8d3696b890b4719ef19a96db26735b25da0214b5
git diff 72bd34c17728915ce9d30e27101832fb31336842 \
  69b5b0e394a935cb864c17b02b9ad4b2e95621d0
uv run pytest -m "not integration and not integration_gui and not integration_gui_slow"
uv run ruff check
uv run ruff format --check
uv run mypy src/
```

Los cuatro comandos `uv run` de este bloque describen los gates históricos;
las reejecuciones del cierre documental deben registrarse por separado.

## Reejecución durante el cierre documental (sesión 42A)

**HECHO_VERIFICADO (2026-08-06, árbol documental sin commit):** tras `uv
sync`, `python3 scripts/verificar_entorno.py` informó 14 OK, 2 WARN y 0 FAIL;
`uv run ruff check`, `uv run ruff format --check` y `uv run mypy src/`
terminaron verdes; la suite offline terminó con `406 passed, 77 deselected`
en 42.74 s. No se ejecutaron tests de integración ni se abrió KiCad. Los WARN
fueron el JAR de Freerouting no configurado y el socket IPC no visible.
