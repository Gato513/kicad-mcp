# Sesión 40 — Puerta 1: diseño y auditoría del contrato

## 1. Identificación

- **Fecha:** 2026-08-06.
- **Máquina/OS:** Arch Linux, kernel 7.1.5-arch1-2, x86_64.
- **Repo:** `Gato513/kicad-mcp`.
- **Rama:** `master`.
- **HEAD:** `99ccbd0a87531aaeb4dcc08c01c89d3b6a9fe2be` — idéntico al esperado por el prompt y al validado en Puerta 0.
- **Contrato auditado:** `S40-DT1-CARACTERIZACION` (versión preliminar, redactada por el chat arquitecto e incorporada al prompt de Puerta 1 §7).
- **Rol de esta intervención:** verificador técnico de premisas, alcance, contratos y ejecutabilidad. **No** ejecutor de DT1.
- **Autoridad final:** humano.
- **Naturaleza de la intervención:** lectura, inspección y dictamen. Ningún archivo del repositorio fue modificado; ninguna rama creada; ningún commit; ningún push.

## 2. Veredicto

```text
APROBAR_CON_CAMBIOS
```

**0 BLOCKER · 3 MAJOR · 4 MINOR · 2 NOTE.**

El contrato es estructuralmente correcto: es genuinamente de caracterización y su redacción no permite derivar en implementación funcional. Pero (a) contiene un error factual sobre la superficie de tools de `tools/pcb.py`, (b) omite un acoplamiento real entre la suite de tests y el módulo, que vuelve **contradictorio** el par «no modificar tests» + «partir por familias» para al menos un eje de partición explícitamente sugerido por la documentación, y (c) las cuatro correcciones obligatorias C1–C4 no están incorporadas al texto: dos ausentes por completo, dos parciales, una de ellas autocontradicha por el propio contrato.

Ninguno de los tres MAJOR requiere rediseñar el objetivo: se corrigen con cláusulas y cifras. De ahí `APROBAR_CON_CAMBIOS` y no `BLOQUEAR`.

## 3. Resumen ejecutivo

La premisa de identidad se sostiene íntegra: rama `master`, SHA `99ccbd0a…`, cero cambios trackeados, un único worktree, sin merge/rebase/lock pendiente — un solo escritor. No apareció evidencia que contradiga la Puerta 0; la única corrección de estado es aritmética y esperable: los untracked hoy son **18**, no 17, porque el propio reporte de Puerta 0 pasó a ser el archivo nº 18.

La caracterización de DT1 es **ejecutable sin mover código**. La inspección dirigida confirmó que la frontera de partición es identificable estáticamente: las 20 closures de `register()` capturan exactamente dos nombres del entorno léxico —`mcp` y `bridge`— y el patrón de desacople ya existe en el repositorio (`tools/__init__.py::register_all` inyecta `mcp` + el `IpcBridge` singleton a seis sub-registradores). Es decir: la hipótesis de que existen slices mecánicos puede evaluarse por análisis estático, sin tocar un solo archivo productivo. Esto valida el diseño del contrato como investigación previa a la implementación.

El hallazgo de mayor valor de esta puerta no está en el contrato sino en el código: **la suite de tests está acoplada al namespace `kicad_mcp.tools.pcb` de dos formas distintas y con consecuencias distintas.** Seis helpers privados se importan por nombre (entre ellos los tres encoders ad-hoc, que son precisamente el eje de partición más sugerido por la documentación) — ese acoplamiento sobrevive a un re-export desde `pcb.py`. Pero cuatro archivos de test hacen `monkeypatch.setattr(pcb_module, "run_drc"/"run_autoroute", …)`, y el AST demuestra que ambos símbolos se usan **exclusivamente** dentro de `register.route_board`. Ese segundo acoplamiento **no** sobrevive a un re-export: parchear `pcb.run_drc` no altera lo que resuelva `routing.run_drc` en sus propios globals. Consecuencia dura: mientras rija la prohibición de modificar tests, `route_board` no puede salir de `tools/pcb.py`. El contrato preliminar no lo contemplaba y habría permitido llegar a Puerta 2 con un primer slice inejecutable.

En cuanto a las correcciones obligatorias: **C2 y C4 están ausentes** del texto auditado (ni comandos de baseline, ni límite alguno al primer slice). **C1 y C3 están parciales**, y C3 además está autocontradicha: el contrato exige inventario reproducible en su sección de alcance y, en su sección de hipótesis, asserta «las 32 tools» — número copiado de documentación y falso para `tools/pcb.py`, que registra **19** de las 32 del servidor. La auditoría encontró una segunda cifra documental vencida (`register()` «~2 215 LOC» medido el 2026-08-01; el valor real sobre este SHA es 2173, porque sesión 39 quitó 88 líneas), lo que confirma que la regla C3 debe extenderse más allá del conteo de tools, a LOC y complejidad ciclomática.

El contrato final corregido (§9) incorpora C1–C4 verbatim, seis invariantes verificables derivadas del código real, el veto sobre `route_board` como primer slice, y resuelve la tensión aparente entre «no modificar tests» y la nota de sesión 39 sobre actualizar los canarios: un slice mecánico es superficie-neutra por definición, de modo que los canarios pasan sin tocarse — y si un slice exigiera tocarlos, eso mismo lo refuta.

## 4. Fuentes inspeccionadas

| Fuente | Uso |
|---|---|
| `CLAUDE.md` | fronteras F1–F5, DoD, reglas de código, drift de fase |
| `docs/analisis/CONTEXTO_CHAT.md` | estado de DT1/P1-2/DT3 (§II.229, §III.1, §III.2, nota de versión) |
| `docs/BACKLOG.md` | P1-2 (`kiid`) abierto, DT2 cerrado con errata, advertencia de colisión con DT1 |
| `docs/DECISIONES.md` | índice de ADR vigentes |
| `docs/CONTEXT.md` | rol del documento, estado del sistema |
| `docs/INDEX.md` | jerarquía documental |
| `hoja-de-ruta-v5.md` | **Fase 4**, ambición Open Source, secuencia estricta |
| `docs/adr/0014-mutating-tool-decorator.md` | anatomía de las 3 familias, 17 sitios, errata, DT1 anticipado |
| `docs/adr/0000, 0011, 0012` (referencia) | fronteras, autorouting, contrato de persistencia D-23.2 |
| `docs/historico/sesiones/39-reporte.md` | propuesta para sesión 40, entregables, nota sobre canarios |
| `docs/historico/sesiones/40-puerta-0-reporte.md` | estado aceptado de Puerta 0, conteo de untracked |
| `src/kicad_mcp/tools/pcb.py` | AST completo, imports, closures, capturas |
| `src/kicad_mcp/tools/_mutating.py` | decorador, flags, orden de guardas, exclusiones |
| `src/kicad_mcp/tools/__init__.py` | `register_all`, patrón de inyección `mcp`+`bridge` |
| `tests/**.py` | AST de imports desde `tools.pcb`; targets de `monkeypatch` |
| `pyproject.toml` | filtro `addopts`, marcas, mypy strict, F5 |
| `.github/workflows/ci.yml` | 4 jobs, actions pineadas, permisos mínimos |
| `.claude/settings.json` | allow/deny de Edit y Bash — protección efectiva de F1/F3/F5 |
| `scripts/verificar_entorno.py` | existencia y rol de Fase 0 (no re-ejecutado; Puerta 0 lo cubrió) |

## 5. Verificaciones iniciales

```text
git branch --show-current          → master
git rev-parse HEAD                 → 99ccbd0a87531aaeb4dcc08c01c89d3b6a9fe2be
git diff --name-only               → (vacío)
git status --short -uall           → 0 modificados, 0 staged, 18 untracked
git worktree list                  → 1 worktree
.git/{rebase-merge,rebase-apply,MERGE_HEAD,CHERRY_PICK_HEAD} → ninguno
```

**Conclusión:** rama y SHA coinciden con lo esperado; no hay cambios trackeados inesperados; no hay operaciones Git pendientes; un único escritor activo. No se re-ejecutó la suite de calidad: ninguna premisa relevante cambió desde Puerta 0 (árbol trackeado bit a bit idéntico, mismo SHA).

## 6. Evidencia técnica derivada del código

Todas las cifras de esta sección se derivaron por AST o `grep` sobre el SHA base, no de documentación. Los comandos están en §12.

### 6.1 Tamaño y forma de `tools/pcb.py`

| Métrica | Valor | Fuente |
|---|---|---|
| LOC del archivo | 3419 | `wc -l` |
| `register()` | L1027–L3199 = **2173 LOC** (63,6 % del archivo) | AST |
| Funciones a nivel de módulo | 33 (25 antes de `register`, 8 después) | AST |
| Funciones anidadas en `register()` | 20 (19 tools + `_delete_copper`) | AST |
| Closure más grande | `route_board`, 426 LOC | AST |
| Segunda más grande | `add_track`, 167 LOC | AST |
| Núcleo compartido | `_delete_copper`, 149 LOC | AST |

Comparación con la documentación: `docs/analisis/CONTEXTO_CHAT.md:229` declara «~2 215 LOC» con medición fechada 2026-08-01, previa a sesión 39 (−88 líneas). Diferencia de 42 líneas. La complejidad ciclomática 146 de la misma fuente **no es verificable** en este entorno sin añadir una herramienta (F5).

### 6.2 Superficie de tools

| Módulo | Tools registradas |
|---|---|
| `pcb.py` | **19** |
| `sch.py` | 4 |
| `export.py` | 4 |
| `world.py` | 2 |
| `validate.py` | 2 |
| `meta.py` | 1 |
| **Total servidor** | **32** |

Las 19 de `pcb.py`: `move_footprint`, `set_footprint_ref`, `add_track`, `add_via`, `save_board`, `reload_board_from_disk`, `delete_track`, `delete_via`, `get_tracks`, `delete_tracks_bulk`, `get_component_detail`, `get_footprint_neighbors`, `draw_board_outline`, `add_zone`, `add_keepout_zone`, `get_zones`, `fill_zones`, `delete_zone`, `route_board`.

De ellas, **12** llevan `@mutating_tool` — coincide exactamente con ADR-0014 post-errata. `route_board` y `reload_board_from_disk` (Familia B) no lo llevan, por contrato deliberado; `delete_tracks_bulk` tampoco, por el early-return de `dry_run`.

### 6.3 Estado capturado por las closures

`register(mcp, *, ipc_bridge=None)` tiene un único assign en su cuerpo: `bridge = ipc_bridge or IpcBridge()`. El análisis de nombres libres da:

- las **20** closures capturan `mcp`;
- **18** capturan además `bridge`;
- `delete_track` y `delete_via` capturan sólo `mcp` — delegan en `_delete_copper`, que es quien captura `bridge`.

**Interpretación (INFERENCIA, alta confianza):** el estado compartido es mínimo y explícito. Un slice no necesita inventar un contrato de estado: replica el patrón que `tools/__init__.py::register_all` ya usa con seis módulos —firma `register_x(mcp, *, bridge)`— y el `IpcBridge` sigue siendo singleton por proceso. Esto es lo que hace la hipótesis evaluable sin mover código.

### 6.4 Acoplamiento de la suite de tests con `tools.pcb`

**Vía A — import por nombre** (16 archivos de test referencian el módulo):

| Símbolo | Archivos |
|---|---|
| `register` | 13 |
| `_encode_tracks`, `_encode_zones`, `_encode_component_detail` | `test_pcb_encoders_golden.py` |
| `_find_duplicate_refs` | `test_pcb_session31b_duplicate_refs.py` |
| `_tracks_filter_desc`, `_zones_filter_desc` | `test_pcb_session38_filter_desc.py` |

Este acoplamiento **sobrevive** a un re-export: si `pcb.py` conserva `from .pcb_encoders import _encode_tracks`, el `from kicad_mcp.tools.pcb import _encode_tracks` del test sigue resolviendo.

**Vía B — monkeypatch de globals del módulo** (4 archivos):

```text
tests/test_route_board.py:323-324
tests/test_pcb_session31b_duplicate_refs.py:262-263
tests/test_pcb_session32b_refill_silencioso_canary.py:210-211
tests/test_pcb_session32d_orphan_pads_stitching_canary.py:294-295
    monkeypatch.setattr(pcb_module, "run_drc", _fake_drc)
    monkeypatch.setattr(pcb_module, "run_autoroute", _fake_autoroute)
```

El AST muestra que `run_drc` y `run_autoroute` se usan **exclusivamente** dentro de `register.route_board`. Este acoplamiento **no sobrevive** a un re-export: el parche sustituye el atributo en el namespace `kicad_mcp.tools.pcb`; código movido a otro módulo resuelve el nombre en *sus* globals y llamaría al Freerouting real y al DRC real. Los tests dejarían de aislar, o fallarían.

**Consecuencia normativa:** bajo la prohibición de modificar tests, `route_board` —la closure más grande y candidata intuitiva a extraerse primero— es la **menos** extraíble del archivo.

### 6.5 Riesgo de ciclos de import

No se detectó riesgo estructural nuevo. ADR-0014 ya resolvió la única dirección conflictiva: cuatro helpers (`_project_root`, `_guard_live_stale`, `_check_base_snap`, `_resolve_root_schematic_or_pcb`) se movieron a `_mutating.py` precisamente porque «`pcb.py` no puede importarlos de vuelta sin ciclo», y `pcb.py` los reimporta desde ahí. Un módulo `pcb/<familia>.py` que importe de `_mutating.py` y de `bridge/` reproduce esa topología sin ciclo. (INFERENCIA, a confirmar por el ejecutor en P3.)

### 6.6 Orden de guardas

Contractualizado en `_mutating.py` (docstring del módulo) y ADR-0014: live-guard → disk-check → base_snap, con `tool_call_timer` arrancando después. Un slice que mueva la closure **con su decorador intacto** preserva el orden por construcción — es exactamente la «buena señal temprana» que anticipa `39-reporte.md:250-253`. Verificable con los dos canarios existentes.

## 7. Hallazgos

```text
ID: H-01
Severidad: MAJOR
Clasificación: HECHO
Ubicación: contrato §Hipótesis («las 32 tools»); src/kicad_mcp/tools/*.py
Evidencia: grep -rc "mcp.tool(" → pcb 19, sch 4, export 4, world 2, validate 2,
  meta 1. Total servidor 32. AST confirma 19 closures decoradas con @mcp.tool
  dentro de register() de pcb.py.
Impacto: el invariante central de la hipótesis es falso para el módulo bajo
  análisis. Un ejecutor que lo tome literal buscaría 32 tools en pcb.py, no las
  encontraría, e improvisaría un criterio. Es además el error exacto que C3
  existe para prevenir: cifra copiada de documentación (CONTEXTO_CHAT.md:695,
  donde es correcta pero se refiere al servidor completo).
Corrección mínima: «las 19 tools registradas por tools/pcb.py (de 32 totales
  del servidor), cifra a re-derivar por AST en P3».
```

```text
ID: H-02
Severidad: MAJOR
Clasificación: HECHO
Ubicación: tests/test_route_board.py:38,323-324;
  tests/test_pcb_session31b_duplicate_refs.py:59,262-263;
  tests/test_pcb_session32b_refill_silencioso_canary.py:64,210-211;
  tests/test_pcb_session32d_orphan_pads_stitching_canary.py:62,294-295;
  src/kicad_mcp/tools/pcb.py:2774-3199 (route_board)
Evidencia: §6.4 vía B. Los 4 tests parchean pcb_module.run_drc y
  pcb_module.run_autoroute; el AST prueba que ambos símbolos se usan
  exclusivamente en register.route_board. Un re-export no restaura el parche.
Impacto: mover route_board a un módulo nuevo rompe 4 archivos de test, y
  repararlos es «modificar tests», explícitamente fuera de alcance. El contrato
  preliminar permitía proponer «routing» como primer slice — es uno de los ejes
  que CONTEXTO_CHAT.md:611 sugiere — y llegar a Puerta 2 con un slice
  inejecutable, descubriéndolo recién al correr la suite.
Corrección mínima: invariante I-4 (frontera de monkeypatch) + veto explícito de
  route_board en el universo de primeros slices, con esta evidencia citada.
```

```text
ID: H-03
Severidad: MAJOR
Clasificación: HECHO
Ubicación: tests/test_pcb_encoders_golden.py,
  tests/test_pcb_session38_filter_desc.py,
  tests/test_pcb_session31b_duplicate_refs.py, + 13 tests que importan register
Evidencia: §6.4 vía A. Seis helpers privados importados por nombre desde
  kicad_mcp.tools.pcb.
Impacto: el eje «encoders» —el más cohesivo, y el que CONTEXTO_CHAT.md:611 y
  BACKLOG.md:500 señalan como natural— toca cinco de esos seis helpers. Sin una
  invariante explícita de re-export, el slice rompe tests que no se pueden
  editar. Con re-export funciona; pero eso debe ser condición declarada del
  contrato, no un descubrimiento del ejecutor a mitad de Puerta 2.
Corrección mínima: invariante I-3, con la lista de símbolos derivada por AST.
```

```text
ID: H-04
Severidad: MINOR
Clasificación: HECHO
Ubicación: contrato §Estado operativo; git status
Evidencia: git ls-files --others --exclude-standard | wc -l → 18. El reporte de
  Puerta 0 (:11) dice 17 y es correcto para su momento: el archivo nº 18 es el
  propio 40-puerta-0-reporte.md.
Impacto: si C2 se implementa asumiendo 17, el diff de cierre arroja un falso
  positivo desde la primera corrida y se normaliza ignorarlo — justo lo que C2
  quiere evitar.
Corrección mínima: el contrato no fija número; fija el procedimiento de captura
  en vivo y declara 18 como cifra observada, de contraste.
```

```text
ID: H-05
Severidad: MINOR
Clasificación: HECHO
Ubicación: docs/analisis/CONTEXTO_CHAT.md:229 (citado por el contrato)
Evidencia: AST → register() = 2173 LOC. La doc dice ~2215, medición 2026-08-01,
  previa a sesión 39 (−88 líneas en el archivo).
Impacto: bajo en sí mismo; alto como confirmación de que la regla C3 debe
  cubrir LOC y complejidad ciclomática, no sólo el conteo de tools. La CC 146 es
  hoy NO_VERIFICABLE sin añadir herramienta (F5).
Corrección mínima: exigir re-medición de LOC; para CC, medirla sin tocar
  pyproject.toml o declararla NO_VERIFICABLE.
```

```text
ID: H-06
Severidad: MINOR
Clasificación: HECHO
Ubicación: .claude/settings.json (permissions.allow)
Evidencia: allow-Edit cubre ./src/**, ./tests/**, ./docs/adr/**, ./README.md.
  Los entregables naturales de la caracterización viven en docs/analisis/ y
  docs/historico/sesiones/ — no allow-listados.
Impacto: no bloquea (habrá prompt de permiso), pero el contrato debe nombrar las
  rutas exactas para que el humano autorice una vez. Riesgo secundario: escribir
  en docs/adr/ «porque está permitido», cuando la caracterización NO introduce
  contrato arquitectónico y por tanto NO amerita ADR (DoD §4).
Corrección mínima: fijar las rutas de entregable; prohibir crear ADR en esta
  etapa.
```

```text
ID: H-07
Severidad: MINOR
Clasificación: HECHO
Ubicación: contrato §Estado operativo; hoja-de-ruta-v5.md:1; CLAUDE.md
Evidencia: hoja-de-ruta-v5.md:1 «Fase 4, arranca post-sesión 29»; :22 «Convertir
  la arquitectura estable de Fase 3 en un proyecto Open Source». CLAUDE.md
  declara «Fase 3 / consolidación» y referencia CONTEXT.md y hoja-de-ruta-v4.md
  en raíz, ambos inexistentes (drift ya registrado en Puerta 0).
Impacto: menor. El contrato reproduce el drift en vez de citar la fuente
  vigente. Por jerarquía de evidencia (2-3 sobre 10) manda hoja-de-ruta-v5.md.
Corrección mínima: «Fase 4 (hoja-de-ruta-v5.md:1). Drift de CLAUDE.md conocido,
  fuera de alcance.»
```

```text
ID: H-08
Severidad: NOTE
Clasificación: HECHO
Ubicación: docs/historico/sesiones/39-reporte.md:264-268
Evidencia: la propuesta de sesión 39 dice que los canarios
  test_tools_decoradas_llevan_la_marca_mutating_tool y
  test_tools_excluidas_no_llevan_la_marca «deben actualizarse junto con
  cualquier cambio de superficie que DT1 introduzca».
Impacto: tensión aparente con «no modificar tests». Se resuelve por
  construcción, no por excepción: un slice mecánico es superficie-neutro
  (mismos nombres, mismas exclusiones) ⇒ los canarios pasan sin tocarse. Que un
  slice exija tocarlos es evidencia de que no es mecánico, y lo refuta por el
  propio criterio C4.
Corrección mínima: invariante I-5 + señal de refutación explícita.
```

```text
ID: H-09
Severidad: NOTE
Clasificación: HECHO
Ubicación: src/kicad_mcp/tools/pcb.py:1653-1801 (_delete_copper)
Evidencia: closure de 149 LOC que sirve a delete_track y delete_via; ambas
  llevan base_snap_check=False porque la validación de base_snap vive dentro del
  núcleo compartido (ADR-0014).
Impacto: {_delete_copper, delete_track, delete_via} es unidad indivisible a
  efectos de slicing. Relevante para el límite «una sola familia funcional».
Corrección mínima: registrarlo como unidad atómica en el contrato (I-6).
```

## 8. Validación C1–C4

| Corrección | Estado | Evidencia | Cambio requerido |
|---|---|---|---|
| **C1 — Propuesta modular condicional** | **PARCIAL** | El contrato dice «proponer módulos solo si la evidencia lo permite» (§Dentro del alcance), pero no define qué se entrega si NO existe frontera. Sin cláusula de resultado alternativo, «informe de refutación» no es un cierre válido y el ejecutor siente presión a proponer algo. | Incorporar el párrafo de C1 verbatim como §Resultados admisibles. |
| **C2 — Baseline de untracked** | **AUSENTE** | El texto no contiene ningún comando de baseline ni de diff de cierre; sólo la afirmación «17 untracked preexistentes», además vencida (H-04). | Incorporar los dos bloques de comandos verbatim, con 18 como dato de contraste, no como assert. |
| **C3 — Inventario reproducible** | **PARCIAL / AUTOCONTRADICHO** | El alcance pide «inventariar funciones, closures y tools», pero la §Hipótesis del mismo contrato asserta «las 32 tools» — copiado de doc y falso para pcb.py (H-01). Segunda cifra vencida detectada: LOC de register() (H-05). | Exigir derivación por AST/registro real; corregir 32→19; extender la regla a LOC y CC; obligar a las 4 categorías (a–d). |
| **C4 — Límite del primer slice** | **AUSENTE** | El texto dice «identificar slices incrementales; seleccionar un primer slice» sin techo de familias, sin techo de módulos nuevos, sin cláusula de «DT1 necesita diseño adicional». | Incorporar las 5 condiciones de C4 más las restricciones derivadas de H-02 (veto a routing), H-03 (re-export) y H-09 (unidad atómica). |

## 9. Contrato final corregido

*(Texto completo, listo para aprobación humana. Reemplaza íntegramente al preliminar.)*

```text
════════════════════════════════════════════════════════════════════════
CONTRATO S40-DT1-CARACTERIZACION — v2 (post-Puerta 1)
════════════════════════════════════════════════════════════════════════

## 1. Identificación

ID:                          S40-DT1-CARACTERIZACION
Versión:                     v2 (incorpora C1–C4 y hallazgos H-01…H-09)
Tipo:                        investigación arquitectónica verificable
Repositorio:                 Gato513/kicad-mcp
Rama base:                   master
Commit base:                 99ccbd0a87531aaeb4dcc08c01c89d3b6a9fe2be
Responsable de ejecución:    Claude Code
Auditor de contrato:         ChatGPT (preliminar) + Claude Code (Puerta 1)
Revisor independiente:       Codex, modo revisor sin edición
Autoridad final:             humano

## 2. Estado operativo verificado sobre el SHA base

- Fase vigente: Fase 4 (hoja-de-ruta-v5.md:1) — ambición de release Open
  Source. El drift de CLAUDE.md (declara "Fase 3", referencia CONTEXT.md y
  hoja-de-ruta-v4.md en raíz, ambos inexistentes) es conocido y queda FUERA
  DE ALCANCE.
- DT2 cerrado en sesión 39; @mutating_tool vive en
  src/kicad_mcp/tools/_mutating.py (173 LOC) y está aplicado a 12 tools.
  ADR-0014 §Contexto declara DT2 como prerrequisito explícito de DT1.
- CI (4 jobs) y branch protection activos; último run verde 4/4 sobre este SHA.
- Baseline offline reproducido en Puerta 0: 406 passed, 77 deselected;
  ruff check, ruff format --check y mypy src/ verdes.
- Suite integration (38 tests) NO reproducible sin KiCad vivo. No es fallo.
- 18 archivos untracked al abrir Puerta 1 (los 17 de Puerta 0 + el reporte de
  Puerta 0). Todos fuera de alcance, congelados.
- Un solo worktree, sin merge/rebase/lock pendiente: un único escritor.
- src/kicad_mcp/tools/pcb.py = 3419 LOC; register() = L1027-L3199 = 2173 LOC
  (63,6 %); registra 19 tools MCP de las 32 del servidor.

## 3. Objetivo

Caracterizar DT1 contra el código real del SHA base y producir un plan
incremental, verificable y reversible para dividir
src/kicad_mcp/tools/pcb.py, SIN modificar ni una línea de código productivo
en esta etapa.

El objetivo se considera cumplido cuando el humano dispone de material
suficiente para tomar UNA decisión binaria explícita:

  «¿Se autoriza el primer slice propuesto (o el informe de refutación) como
   alcance de una sesión posterior — SÍ / NO?»

Una descripción extensa sin esa decisión disponible NO cierra el contrato.

## 4. Hipótesis

H-DT1: tools/pcb.py puede dividirse progresivamente en módulos cohesivos
mediante slices mecánicos que preserven:

  - las 19 tools registradas por tools/pcb.py (cifra a re-derivar, §9);
  - nombres, firmas y descripciones MCP, y por tanto los esquemas generados;
  - la taxonomía y las condiciones de emisión de errores (F3);
  - el orden de guardas de entrada (live-guard → disk-check → base_snap,
    ADR-0014) y los flags de @mutating_tool;
  - los contratos de persistencia (D-23.2/ADR-0012, D-14.1/D-14.3, ADR-0011);
  - los símbolos importados hoy por la suite de tests;
  - el comportamiento observable;
  - los 406 tests offline, sin modificar ninguno.

## 5. Invariantes verificables

I-1  Superficie MCP: el conjunto {nombre, firma, descripción} de las tools
     registradas por tools/pcb.py es idéntico antes y después de cualquier
     slice. Verificable llamando register() sobre un FastMCP de prueba y
     comparando el registro.
I-2  Marca de mutación: el conjunto de tools con __mutating_tool__ y sus flags
     (live_guard / disk_check / base_snap_check) no cambia.
I-3  RE-EXPORT OBLIGATORIO. tools/pcb.py debe seguir exponiendo todo símbolo
     que la suite importe hoy desde kicad_mcp.tools.pcb. Lista derivada por
     AST sobre tests/ al SHA base: register, _encode_tracks, _encode_zones,
     _encode_component_detail, _find_duplicate_refs, _tracks_filter_desc,
     _zones_filter_desc.
I-4  FRONTERA DE MONKEYPATCH. Cuatro tests parchean
     kicad_mcp.tools.pcb.run_drc y .run_autoroute
     (test_route_board.py:323-324;
      test_pcb_session31b_duplicate_refs.py:262-263;
      test_pcb_session32b_refill_silencioso_canary.py:210-211;
      test_pcb_session32d_orphan_pads_stitching_canary.py:294-295).
     Ambos símbolos se usan EXCLUSIVAMENTE dentro de register.route_board.
     Un re-export NO restaura el parche. Por tanto: ningún código que
     resuelva run_drc o run_autoroute puede salir del namespace
     tools/pcb.py mientras rija la prohibición de modificar tests.
I-5  Canarios intactos: test_tools_decoradas_llevan_la_marca_mutating_tool y
     test_tools_excluidas_no_llevan_la_marca deben pasar SIN edición. Que un
     slice exija tocarlos es evidencia de que no es superficie-neutro y lo
     refuta por sí solo (resuelve la tensión con 39-reporte.md:264-268).
I-6  Unidad atómica: {_delete_copper, delete_track, delete_via} es
     indivisible — el núcleo compartido aloja la validación de base_snap de
     ambas tools (base_snap_check=False, ADR-0014).

## 6. Evidencia de refutación

H-DT1 se considera refutada, o debe reformularse, si el primer slice
razonable exige cualquiera de:

  - cambiar firmas, nombres o descripciones MCP;
  - rediseñar ampliamente register() (más allá de delegar a
    sub-registradores con firma register_x(mcp, *, bridge), patrón que ya
    existe en tools/__init__.py::register_all);
  - tocar F1-F5;
  - alterar la precedencia o las condiciones de emisión de errores;
  - introducir ciclos de import inevitables;
  - mover estado compartido (bridge, mcp) sin contrato explícito;
  - violar I-3, I-4, I-5 o I-6;
  - modificar múltiples familias inseparables;
  - añadir dependencias;
  - mezclar DT1 con P1-2, DT3 u otra deuda.

## 7. Resultados admisibles

  La propuesta modular solo será obligatoria si el análisis demuestra al
  menos una frontera cohesiva, mecánica y reversible. Si no existe, el
  resultado válido será un informe de refutación o reformulación de DT1.

Ambos desenlaces cierran el contrato. Producir una propuesta modular sin
frontera demostrada es un INCUMPLIMIENTO, no un cumplimiento parcial.

## 8. Dentro del alcance

  1. Medir LOC de pcb.py y de register() re-derivándolas del código (no
     copiar de documentación). Complejidad ciclomática: medirla sin añadir
     dependencia al proyecto, o declararla NO_VERIFICABLE.
  2. Inventariar funciones a nivel de módulo, closures de register() y tools.
  3. Mapear imports y dependencias internas/externas por función.
  4. Identificar el estado capturado por cada closure.
  5. Clasificar responsabilidades por familia funcional.
  6. Proponer módulos SOLO bajo la condición de §7.
  7. Identificar slices incrementales candidatos.
  8. Seleccionar un primer slice conforme a §10, o declarar que no existe.
  9. Definir invariantes y procedimiento de prueba de ese slice.
 10. Producir los entregables de §11.

## 9. Inventario reproducible obligatorio

El inventario debe derivarse del registro real, del AST o de inspección
reproducible del código, con el comando o script citado en el reporte.
COPIAR CIFRAS DE LA DOCUMENTACIÓN NO ES EVIDENCIA ACEPTABLE — la Puerta 1
detectó dos cifras documentales erróneas o vencidas (32 tools atribuidas a
pcb.py; register() ~2215 LOC).

Deben distinguirse explícitamente cuatro categorías:

  a) tools globales del servidor (esperado 32, a re-derivar);
  b) tools registradas por tools/pcb.py (esperado 19, a re-derivar);
  c) operaciones mutantes (marca __mutating_tool__, más las excluidas con la
     justificación de ADR-0014);
  d) funciones auxiliares que NO son tools (nivel de módulo y closures).

## 10. Límite del primer slice

El primer slice propuesto:

  - no puede afectar más de UNA familia funcional principal;
  - no puede exigir más de DOS módulos productivos nuevos;
  - no puede mezclar refactor mecánico con corrección funcional;
  - no puede exigir cambios en F1-F5;
  - no puede depender de P1-2 ni de DT3;
  - NO puede incluir route_board ni ningún código que resuelva
    run_drc / run_autoroute (I-4);
  - debe preservar I-1, I-2, I-3, I-5 e I-6;
  - debe ser reversible con un único git revert.

Si no existe un slice que cumpla TODAS estas condiciones, debe declararse
explícitamente que DT1 NECESITA DISEÑO ADICIONAL — y eso cierra el contrato
conforme a §7.

## 11. Entregables

  E1. docs/analisis/40-dt1-caracterizacion.md — inventario, matriz de
      dependencias, clasificación por familias, slices candidatos, primer
      slice propuesto (o informe de refutación), riesgos, invariantes y
      procedimiento de prueba. Cada cifra con su comando de derivación.
  E2. docs/historico/sesiones/40-reporte.md — bitácora de la sesión.
  E3. Diff de untracked (§12), adjunto al reporte.

Referencias obligatorias en E1: SHA base, ruta y línea de cada afirmación
sobre el código, y el comando exacto que la reproduce — de modo que Codex
pueda revisar sin reconstruir el historial del proyecto.

Rutas de escritura autorizadas en esta etapa: docs/analisis/,
docs/historico/sesiones/ y el archivo de baseline en /tmp. Ninguna otra.

## 12. Procedimiento de untracked

Al abrir la sesión, antes de cualquier otra acción:

  git ls-files --others --exclude-standard | sort \
    > /tmp/kicad-mcp-s40-untracked-baseline.txt

Antes del cierre:

  git ls-files --others --exclude-standard | sort \
    > /tmp/kicad-mcp-s40-untracked-final.txt

  diff -u \
    /tmp/kicad-mcp-s40-untracked-baseline.txt \
    /tmp/kicad-mcp-s40-untracked-final.txt

El diff puede contener únicamente los documentos nuevos expresamente
autorizados para sesión 40 (E1, E2). Cualquier otra línea es un hallazgo que
debe reportarse al humano antes del cierre. Cifra observada al abrir Puerta
1: 18 archivos — dato de contraste, nunca assert codificado.

## 13. Fuera del alcance (prohibiciones duras)

  - mover código; crear módulos productivos; modificar imports productivos;
  - modificar tests (incluidos los canarios de test_mutating_tool.py);
  - modificar specs, goldens, CLAUDE.md, pyproject.toml, CI;
  - CREAR O MODIFICAR ADR (la caracterización no introduce contrato
    arquitectónico; DoD §4 no aplica en esta etapa);
  - cambiar @mutating_tool, sus flags o el orden de guardas;
  - resolver P1-2 (kiid) ni DT3;
  - modificar _CACHE; investigar F-V3-ZONE-FILL-CRASH;
  - cambiar tools, añadir dependencias, modificar proyectos KiCad;
  - corregir drift documental global (incluido el de CLAUDE.md);
  - actualizar docs/BACKLOG.md sin aprobación humana explícita;
  - git add ., commits sobre master, y git push en cualquier caso;
  - abrir KiCad o ejecutar pruebas GUI.

Corregir un defecto descubierto durante la caracterización está PROHIBIDO:
se registra en E1 como hallazgo y se eleva al humano.

## 14. Verificación de cierre

  1. git diff --name-only sobre archivos trackeados: vacío.
  2. Diff de untracked (§12): sólo E1 y E2.
  3. git rev-parse HEAD == 99ccbd0a… (ningún commit creado).
  4. Toda cifra de E1 acompañada de su comando de derivación.
  5. Veredicto explícito de §7: propuesta con frontera demostrada, o informe
     de refutación.

No se requiere re-ejecutar ruff/mypy/pytest: sin cambios en src/ ni en
tests/, el baseline de Puerta 0 sigue vigente. Si por cualquier motivo se
tocara código, el contrato queda incumplido.
════════════════════════════════════════════════════════════════════════
```

## 10. Decisiones humanas pendientes

1. **Aprobar o rechazar el contrato v2** de §9.
2. **P1-2 (`kiid`)**: ¿entra en el alcance de sesión 40 o queda como sesión aparte? El v2 lo excluye. `docs/BACKLOG.md:496-500`, `39-reporte.md:255-259` y `CONTEXTO_CHAT.md:615-632` lo proponen como integrable. *Recomendación: mantenerlo fuera* — no es fix mecánico (muta un identificador de round-trip) y mezclarlo viola C4 de forma directa.
3. **Autorizar las 3 rutas de escritura** (`docs/analisis/`, `docs/historico/sesiones/`, `/tmp`), no cubiertas por `.claude/settings.json` (H-06).
4. **Ratificar la prohibición de crear ADR** en esta etapa, pese a que `docs/adr/**` sí está allow-listado.
5. **Complejidad ciclomática**: ¿se acepta declararla `NO_VERIFICABLE`, o se autoriza medirla con herramienta efímera fuera de `pyproject.toml` (F5 intacta)?
6. **Los 18 untracked** (19 con este reporte): ¿se commitean en una rama documental antes de sesión 40, o siguen fuera de Git? No bloquea; recomendación pendiente desde Puerta 0 §15.3.
7. **Confirmar la interpretación de fase** como Fase 4 (`hoja-de-ruta-v5.md`) por sobre el drift de `CLAUDE.md`, y que corregir ese drift sigue fuera de alcance.

## 11. Condición para abrir Puerta 2

Puerta 2 se abre **únicamente** cuando el humano haya, en un solo acto explícito:

1. aprobado el **contrato v2 de §9** (o su variante con las decisiones de §10 resueltas);
2. respondido las 7 decisiones de §10 — como mínimo la 2 (P1-2), la 3 (rutas) y la 5 (CC), que cambian lo que el ejecutor puede hacer;
3. ratificado que el primer slice queda sujeto al §10 del contrato, incluido el veto sobre `route_board` (I-4);
4. confirmado que Puerta 2 arranca sobre `99ccbd0a…` sin commits intermedios; si `master` avanzó, Puerta 0 debe re-ejecutarse antes.

En Puerta 2, Claude Code entra **como ejecutor de la caracterización**: `verificar_entorno.py` como Fase 0, baseline de untracked, análisis por AST/inspección, y E1+E2 como únicos archivos creados. **Ningún código productivo se mueve en Puerta 2.** La partición real es una sesión posterior, condicionada a que el primer slice se apruebe por separado.

## 12. Comandos ejecutados

Todos de lectura. Ninguno destructivo, ninguno con efectos sobre el árbol o el índice de Git.

```bash
git branch --show-current
git rev-parse HEAD
git status --short --untracked-files=all
git diff --name-only
git worktree list
git ls-files --others --exclude-standard | wc -l
ls -d .git/rebase-merge .git/rebase-apply .git/MERGE_HEAD .git/CHERRY_PICK_HEAD

wc -l <fuentes obligatorias>
ls src/kicad_mcp/tools/
grep -rn "mcp.tool(" src/kicad_mcp/ | wc -l
grep -rc "mcp.tool(" src/kicad_mcp/tools/*.py
grep -rn "mutating_tool(" src/kicad_mcp/tools/*.py
grep -rn "monkeypatch.setattr" tests/*.py
grep -rn "pcb_module" tests/*.py
grep -n "DT1" docs/BACKLOG.md docs/DECISIONES.md docs/CONTEXT.md \
              docs/analisis/CONTEXTO_CHAT.md hoja-de-ruta-v5.md docs/INDEX.md
grep -n "P1-2\|DT3\|F-V3-ZONE-FILL-CRASH" docs/BACKLOG.md docs/CONTEXT.md \
              docs/analisis/CONTEXTO_CHAT.md
```

Scripts AST de solo lectura (Python, sin escritura a disco):

1. **Estructura de `pcb.py`** — recorre `ast.parse`, imprime cada `FunctionDef`/`AsyncFunctionDef` con rango de líneas, LOC y decoradores, anidando las closures de `register()`.
2. **Capturas de closure** — extrae parámetros y asignaciones del cuerpo de `register()`, y para cada closure calcula la intersección de sus `ast.Name` con ese conjunto.
3. **Usos de globals parcheados** — para `run_drc`, `run_autoroute`, `diff_violations`, `classify_net_routing`, `audit_record` y `load_project_rules`, reporta qué función los referencia.
4. **Imports de tests** — recorre `tests/*.py` y recoge todo `ImportFrom` cuyo módulo contenga `tools.pcb`, con el archivo de origen.

## 13. Afirmaciones no verificadas

| Afirmación | Motivo |
|---|---|
| Complejidad ciclomática 146 de `register()` | requeriría añadir herramienta (F5); no medida. Queda `NO_VERIFICABLE` en este entorno. |
| Ausencia de ciclos de import tras un slice hipotético | `INFERENCIA` fundada en la topología que ADR-0014 ya estableció con `_mutating.py`; sólo comprobable al ejecutar un slice real. |
| Que `route_board` sea el único bloqueo de tipo monkeypatch | verificado para `run_drc`/`run_autoroute`. No se auditó exhaustivamente todo `monkeypatch.setattr` de la suite contra otros namespaces (`bridge/`, `snapshots/`), fuera del alcance de Puerta 1. El ejecutor debe repetir el barrido en P3. |
| Reproducibilidad de la suite `integration` | no intentada; Puerta 0 ya la registró como no reproducible sin KiCad vivo. |
| Baseline de calidad (`ruff`/`mypy`/`pytest`) | no re-ejecutado. Se hereda de Puerta 0 por identidad de SHA y árbol trackeado. |

## 14. Cierre

Puerta 1 emite **APROBAR_CON_CAMBIOS**. El contrato v2 de §9 incorpora las cuatro correcciones obligatorias y los nueve hallazgos. No quedan BLOCKER; los tres MAJOR están resueltos en el texto de v2. Las decisiones humanas están explicitadas en §10.

La condición formal de cierre de Puerta 1 —«el veredicto sea APROBAR»— se cumple cuando el humano aprueba el contrato v2, momento en el cual `APROBAR_CON_CAMBIOS` se convierte en `APROBAR` sobre el texto corregido. Hasta entonces, Puerta 1 permanece abierta a la espera de esa decisión.

**Ningún archivo del repositorio fue modificado durante esta intervención.** El presente reporte es el único archivo creado, y pasa a ser el untracked nº 19 — mismo precedente que sentó Puerta 0 con el suyo.
