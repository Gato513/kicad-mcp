# Auditoría pre-sesión 06

**Fecha:** 2026-07-10 · **Modo:** solo-lectura · **Rama:** `master` (sin
commits, sin ramas nuevas). Único archivo creado: este.

---

## Resumen ejecutivo

1. **Goldens ✓.** `pytest -k golden -v` recolecta 4 tests (001, 002, 003
   byte-a-byte + 003 determinista); TODOS pasan. `git log tests/golden/`
   sigue con un único commit (F1 intacta).
2. **Skip GUI, causa real:** el reporte previo del humano de "3 skipped"
   fue con socket ausente; con KiCad corriendo (socket presente) el
   resultado es **1 FAILED + 2 SKIPPED**. El fallo NO es del test:
   KiCad devuelve `no handler available for request of type
   kiapi.common.commands.GetVersion` (problema del API server / versión).
   Los 2 skips restantes son `KICAD_MCP_GUI_REF` no definida.
3. **Warning de versión → Hipótesis A (benigna).** Los 8 `.kicad_sch`
   de `004_real` ya vienen con `(version 20250114)` (KiCad 9.x). kicad-skip
   **preserva** ese header. **Pero** reescribe TODO el archivo colapsando
   la indentación (23 746 → 4 344 líneas): preservación semántica ✓,
   preservación de formato ✗ — dato relevante para la sesión 06.
4. **Símbolo agregado ✓.** `U13_SPIKE` presente en `rams_added.kicad_sch`
   con `(at 317.34 194.31 0)` — exactamente lo declarado por el spike.
   Sin colisiones en las otras 7 hojas.
5. **Gap D-06.1 CONFIRMADO.** `get_context_delta` (world.py:178-179)
   siempre llama `build_state_cached(schematic, snap=0)` — lectura de
   disco — y `collect_project_mtimes(schematic)`, sin ramificar por
   `entry.mtimes is None`. Un `base_snap` vivo compararía **memoria
   contra disco**, y además siempre contra el schematic (aunque el base
   sea PCB).
6. **Suite en verde:** unit+golden 82/82, integration 20/20 (4:34),
   mypy limpio, ruff limpio.
7. **Campo `data` documentado sólo específicamente**: aparece únicamente
   en las notas de `get_context_delta` (para `SNAPSHOT_STALE`); la
   sección "Taxonomía de errores (completa, F3)" NO lo describe como
   parte general del envelope.
8. Sin TODO/FIXME activos en `src/`. Un docstring viejo menciona
   "xfail" en `tests/test_toon_encoder.py:7`, sin `@pytest.mark.xfail`
   real detrás — comentario stale a limpiar.

---

## Pregunta 1 — Verificación de los goldens

### `uv run pytest -k golden -v`

```
============================= test session starts ==============================
platform linux -- Python 3.14.3, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/astra/Desktop/agent_proyect/kicad-mcp
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.14.1, asyncio-1.4.0
collected 105 items / 101 deselected / 4 selected

tests/test_toon_encoder.py ....                                          [100%]

====================== 4 passed, 101 deselected in 4.76s =======================
```

Tests recolectados y ubicación (todos en `tests/test_toon_encoder.py`):

| # | Nombre | Golden |
|---|---|---|
| 1 | `test_golden_001_minimo_byte_por_byte` | 001_minimo |
| 2 | `test_golden_002_degradacion_byte_por_byte` | 002_degradacion |
| 3 | `test_golden_003_delta_byte_por_byte` | 003_delta |
| 4 | `test_golden_003_delta_is_deterministic_across_two_runs` | 003_delta |

Los tres goldens (001/002/003) tienen consumidor; los 4 tests pasan,
incluido el determinista de la sesión 05.

**Por qué `pytest tests/golden -v` devolvió 0**: `tests/golden/` es un
directorio de fixtures (no `test_*.py`); pytest no colecciona nada bajo
esa ruta. El comando correcto es `pytest -k golden -v` (o
`pytest tests/test_toon_encoder.py -m golden -v`).

### `git log --oneline -- tests/golden/`

```
b786913 chore: estado inicial
```

Sólo el commit inicial del repo. **F1 intacta**: la sesión 05 no
modificó ningún byte bajo `tests/golden/`.

---

## Pregunta 2 — Por qué los `integration_gui` skipearon (y hoy fallan)

### `KICAD_MCP_GUI_TEST=1 uv run pytest -m integration_gui -rs`

```
SKIPPED [1] tests/test_ipc.py:596: KICAD_MCP_GUI_REF no definida; ejemplo: KICAD_MCP_GUI_REF=U1
SKIPPED [1] tests/test_ipc.py:640: KICAD_MCP_GUI_REF no definida; ejemplo: KICAD_MCP_GUI_REF=U1
1 failed, 2 skipped, 102 deselected in 4.05s
```

Con KiCad corriendo **ahora hay un test que ya no skipea**
(`test_ipc_reports_real_kicad_version` — sólo requería socket + env),
pero falla al llamar `bridge.get_version()`:

```
KicadMcpError: [KICAD_CLI_FAILED] Fallo IPC en get_version.
hint: KiCad returned error: no handler available for request of type
kiapi.common.commands.GetVersion
```

**Diagnóstico**: el socket existe y responde, pero el API server no
reconoce la RPC `GetVersion`. Esto no es un problema del test — es un
problema de configuración del KiCad abierto (versión del API server
distinta de la que kipy espera, o el API server no terminó de arrancar
tras habilitarlo). No es el escenario que el humano vio en el reporte
05 (que fue "3 skipped": ese resultado se explica porque en aquel
momento el socket no existía; ver bloque de código en test_ipc.py:562).

### Condiciones exactas de skip por test (test_ipc.py)

| Línea | Test | Condición literal |
|---|---|---|
| 555-556 | `test_ipc_reports_real_kicad_version` | `os.environ.get("KICAD_MCP_GUI_TEST") != "1"` |
| 562-563 | idem | `not Path(socket_path).exists() and not (socket or "").startswith("ipc://")` |
| 592-593 | `test_move_footprint_round_trip_against_open_board` | `KICAD_MCP_GUI_TEST != "1"` |
| 594-596 | idem | `KICAD_MCP_GUI_REF` no definida |
| 600-601 | idem | `bridge.get_open_board() is None` |
| 636-637 | `test_move_footprint_tool_returns_confirm_with_positive_snap_id` | `KICAD_MCP_GUI_TEST != "1"` |
| 638-640 | idem | `KICAD_MCP_GUI_REF` no definida |
| 641-642 | idem | `KICAD_MCP_PROJECT` no definida |
| 647-649 | idem | `bridge.get_open_board() is None` |

`docs/pruebas-gui.md` cubre bien el protocolo (fixture 004_real →
`/tmp/gui-test-project`, `export KICAD_MCP_GUI_TEST=1`,
`KICAD_MCP_PROJECT`, `KICAD_API_SOCKET`, abrir PCB). **Falta mencionar
`KICAD_MCP_GUI_REF`** — el humano tuvo que descubrirlo por el mensaje
de skip. Discrepancia reportable (no la edito por F1/scope).

### Estado del socket ahora

```
$ ls -la /tmp/kicad/
total 0
drwxr-xr-x  2 astra astra  80 Jul 10 00:24 .
drwxrwxrwt 21 root  root  700 Jul 10 00:41 ..
-rw-------  1 astra astra   0 Jul  9 15:16 api.lock
srwxr-xr-x  1 astra astra   0 Jul 10 00:24 api.sock
```

Socket presente. La razón por la que el humano vio "3 skipped" en 05
es casi seguro que el KiCad estaba cerrado en ese momento (o el
KICAD_MCP_GUI_TEST no llegó al proceso pytest).

### Checklist para correr los 3 GUI (una sola pasada, orden importa)

1. En KiCad 10.0.4 recién iniciado: **Preferences → Plugins → Enable API
   server**, **reiniciar KiCad**.
2. Verificar socket:
   ```bash
   ls -l /tmp/kicad/api.sock
   ```
3. Preparar copia escritura del fixture:
   ```bash
   rm -rf /tmp/gui-test-project
   cp -r tests/fixtures/004_real /tmp/gui-test-project
   git -C /tmp/gui-test-project init -q
   git -C /tmp/gui-test-project add -A
   git -C /tmp/gui-test-project commit -q -m "baseline"
   ```
4. En KiCad: **File → Open Project…** → `/tmp/gui-test-project/video.kicad_pro`.
   **Abrir también** el `.kicad_pcb` desde el project manager (necesario
   para que `get_open_board()` devuelva algo).
5. En la terminal del test:
   ```bash
   export KICAD_MCP_GUI_TEST=1
   export KICAD_MCP_PROJECT=/tmp/gui-test-project
   export KICAD_MCP_GUI_REF=U1     # o el ref real que aparece en el PCB
   export KICAD_API_SOCKET="ipc:///tmp/kicad/api.sock"
   uv run pytest -m integration_gui -v -rs
   ```
6. Si `test_ipc_reports_real_kicad_version` vuelve a fallar con "no
   handler available", significa mismatch de versión kipy ↔ KiCad. No
   es un problema de test: hay que abrir un ADR de compatibilidad de
   kipy (F4 sigue apuntando a KiCad 10; ver si el kipy pinneado hoy es
   consistente con esa versión). El humano debe reportar exactamente
   qué versión de KiCad tiene abierta.

---

## Pregunta 3 — Triage del warning de versión: A vs B

### Tabla `version | generator`

| Archivo | version | generator |
|---|---|---|
| `tests/fixtures/001_basico/fixture.kicad_sch` | 20230121 | fixgen |
| `tests/fixtures/002_medio/fixture.kicad_sch` | 20230121 | fixgen |
| `tests/fixtures/003_grande/fixture.kicad_sch` | 20230121 | fixgen |
| `tests/fixtures/004_real/*.kicad_sch` (los 8) | **20250114** | **"eeschema"** |
| `scratchpad/004_copy/*.kicad_sch` (los 8) | 20250114 | "eeschema" |
| `scratchpad/rams_added.kicad_sch` | **20250114** | **"eeschema"** |

Los fixtures 001-003 son sintéticos (`fixgen`) y llevan version 20230121.
Los `.kicad_sch` reales de 004 son **20250114**, generador `eeschema`.
El archivo generado por kicad-skip **preserva** el version 20250114 y el
generator "eeschema" del archivo de origen.

### Veredicto: Hipótesis **A** (benigna)

El warning que el humano vio en KiCad 10.0.4 ("This file was created by
an older version of KiCad. It will be converted to the new format when
saved") **no lo introduce kicad-skip**: es propiedad intrínseca del
fixture 004_real, cuyo header ya es 20250114 (KiCad 9.x). Cualquier
KiCad 10 abriendo el original mostraría ese mismo warning. kicad-skip
NO cambia el número de versión: escribe **el mismo entero** que leyó.

### Efecto colateral (F NO invalidante, pero relevante para sesión 06)

`diff scratchpad/004_copy/rams.kicad_sch scratchpad/rams_added.kicad_sch`
muestra que **el archivo completo cambia**:

```
líneas totales:
 23746 scratchpad/004_copy/rams.kicad_sch
  4344 scratchpad/rams_added.kicad_sch
```

Es decir, kicad-skip preserva la semántica (S-expression válida) y el
version header, pero **rehace el layout físico**: colapsa la indentación
multi-línea del original a una versión mucho más compacta. Un ejemplo
de una sola línea del generado:

```
(symbol (lib_name "SIM4X32_1") (lib_id "video_schlib:SIM4X32") (at 317.34 194.31 0) (unit 1) …)
```

vs el original de misma información en ~12 líneas indentadas. **Ninguna
línea del original permanece byte-idéntica**: el diff no es "agregado al
final", es "todo diferente". Insumo para el diseño del snapshot vivo
post-write en sesión 06: **no se puede comparar por hash de archivo ni
por diff textual** entre un `.kicad_sch` original y su versión pos-
kicad-skip. Habrá que apoyarse en el estado normalizado (delta TOON) o
en el `NormalizedState` reconstruido.

---

## Pregunta 4 — Verificación del símbolo agregado

`scratchpad/spike-kicad-skip.md` declara:

> template ref: U13
> clone.at movido: [307.34, 194.31, 0] -> [317.34, 194.31, 0]
> clone.Reference = U13_SPIKE
> archivo generado: scratchpad/rams_added.kicad_sch

Verificación en el archivo (`scratchpad/rams_added.kicad_sch`):

- Línea 4335: `(symbol (lib_name "SIM4X32_1") (lib_id "video_schlib:SIM4X32") (at 317.34 194.31 0) …)` — **posición exacta declarada ✓**.
- Línea 4337: `(property "Reference" "U13_SPIKE" (at 307.34 180.34 0) …)` — **referencia exacta ✓** (la coordenada del `at` de la property es la posición del *label* de la referencia, distinta del anchor del símbolo).
- Conteo de `property "Reference"` (proxy de "cuántos símbolos+templates"):

  ```
  scratchpad/004_copy/rams.kicad_sch   34
  scratchpad/rams_added.kicad_sch      35
  ```

  Δ = +1 ✓ (el spike suma un clon).

- Colisión de referencia `U13_SPIKE` entre las 7 hojas de `004_copy`:

  ```
  $ grep -rn "U13_SPIKE" scratchpad/004_copy/
  (sin resultados)
  ```

  Sin colisión ✓.

- La ref `U13` sólo aparece en `rams.kicad_sch` (2 hits: template + lib
  symbol table). No hay U13 en las otras 7 hojas. El clon no colisiona
  con nada existente.

---

## Pregunta 5 — Estado general del codebase

### Suite completa

```
$ uv run pytest -m "not integration and not integration_gui"
82 passed, 23 deselected in 8.16s

$ uv run pytest -m integration
20 passed, 85 deselected in 274.15s (0:04:34)

$ uv run mypy src/
Success: no issues found in 30 source files

$ uv run ruff check src/ tests/ scripts/
All checks passed!
```

### Existencia y contenido resumido

- **ADR-0007** (`docs/adr/0007-snapshots-vivos-mtimes-none.md`): explica
  `SnapshotEntry.mtimes: dict[str, int] | None`. `None` = "snapshot
  vivo" → validación de `EXTERNAL_EDIT_DETECTED` se omite (evita falso
  positivo por el `Save` del propio agente). Limitación aceptada:
  ediciones externas concurrentes no se detectan sobre vivos.
- **`get_context_delta`** en el catálogo (`docs/specs/tool-catalog.md`
  línea 28) bajo la categoría `world`; notas ampliadas en líneas 33-45
  (payload estructurado, snapshots vivos, ejemplo golden 003).
- **`snapshots/validation.py`** (54 líneas): `validate_base_snap(store,
  base_snap, schematic) -> SnapshotEntry` compartida por
  `tools/pcb.move_footprint`, `tools/pcb.add_track` y
  `tools/world.get_context_delta`. Emite `SNAPSHOT_STALE` con
  `data={"base_snap", "retention"}` o `EXTERNAL_EDIT_DETECTED`.

### Campo `data` del envelope: ¿general o específico?

**Específico**. En `docs/specs/tool-catalog.md` la única mención del
campo `data` está bajo las notas de `get_context_delta`, líneas 39-40:

```
- `SNAPSHOT_STALE` incluye en su payload estructurado `data.base_snap` y
  `data.retention` para que el agente correlacione el fallo sin parsear
  el mensaje (F3 intacta: código no renombrado).
```

La sección "**Taxonomía de errores (completa, F3)**" (línea 131) es la
tabla general del envelope y **NO menciona `data`**: sus columnas son
"Código | Significado | ¿Reintentable? | Guía del hint", y el bloque
al pie sólo dice:

> los códigos son SCREAMING_SNAKE en inglés (…); `message` y `hint` en
> el idioma de la sesión; un error nunca incluye tracebacks, rutas
> absolutas del sistema ni texto sin sanear proveniente del proyecto.

Consecuencia: hoy el contrato deja **sin documentar como campo genérico
del envelope** el `data: dict[str, Any] | None` que agregó la sesión 05
en `KicadMcpError`. Si otra tool quiere devolver payload estructurado
en otro código, el catálogo no lo respalda. Punto que el arquitecto
marcó — confirmado con evidencia.

### D-06.1 — memoria vs disco en `get_context_delta` (confirmado)

`src/kicad_mcp/tools/world.py`, dentro de `get_context_delta`:

```python
178:            curr_raw, cache_hit = build_state_cached(schematic, snap=0)
179:            mtimes = collect_project_mtimes(schematic)
180:            new_snap = store.register(curr_raw, mtimes)
```

`build_state_cached(schematic, ...)` (state_builder.py:89) construye el
estado **desde el `.kicad_sch` en disco** (netlist vía kicad-cli +
`sch_positions`). `collect_project_mtimes` también lee disco.

Trazando el flujo mutar → delta:

1. `move_footprint` (pcb.py:117-123) llama al bridge (mutación
   in-memory sobre el board de kipy) y **registra un snapshot vivo**:
   ```python
   117:            bridge.move_footprint(board, ref, Mm(x_mm), Mm(y_mm))
   122:            new_state = build_state_from_board(bridge, board)
   123:            snap_id = get_default_store().register(new_state, mtimes=None)
   ```
   `new_state.kind == "pcb"` y el disco todavía no vio la mutación
   (KiCad guarda cuando el usuario aprieta Save).
2. El agente pide `get_context_delta(base_snap=<snap_id vivo>, …)`.
3. `world.py:178` reconstruye el estado actual desde disco — es decir
   **el `.kicad_sch` (schematic), no un `.kicad_pcb`** — y lo compara
   contra `entry.state` (el board mutado en memoria).

Consecuencias observables del gap:

- La comparación cruza `kind="pcb"` (base) con `kind="sch"` (curr). El
  delta que salga es semánticamente basura (o rompe al comparar sets
  de refs distintos).
- Aun si `kind` coincidiera, el disco no refleja aún la mutación → el
  delta describiría el **inverso** de la mutación (la mutación aparece
  como "eliminada" al comparar base con estado pre-mutación).
- El nuevo snapshot registrado en línea 180 recibe `mtimes` de disco,
  no `None` — hereda la etiqueta "de disco" aunque encapsule un estado
  potencialmente inconsistente con la in-memory sobre PCB.

**Gap confirmado con evidencia de código**. La corrección natural es
ramificar en 178: si `entry.mtimes is None` (vivo) y `entry.state.kind
== "pcb"`, reconstruir `curr` desde el board vía
`build_state_from_board`; si es `sch`, ver ADR-0007 y decidir si
existe un equivalente para esquemáticos (hoy no lo hay — el path
vivo sólo lo abrieron las mutaciones PCB).

### TODO/FIXME/xfail vigentes

- `src/`: sin TODO/FIXME/HACK/XXX (grep vacío).
- `tests/`:
  - `tests/test_toon_encoder.py:7` — docstring viejo dice "Los golden
    002/003 se marcan `xfail`…". Falso: los tests son 4, todos pasan,
    sin `@pytest.mark.xfail`. Comentario stale, candidato a limpieza
    (no lo toqué).
  - `tests/test_pcb.py:33` — la palabra es "TODOS" (todo en español,
    no marcador TODO). Falso positivo.
- `xfailed` en la suite: 0 (`82 passed, 23 deselected in 8.16s`).

### Anomalías

Ninguna estructural: no aparecen imports muertos, archivos huérfanos,
ni tests silenciosamente inertes. La única deuda de documentación
detectada (además de las apuntadas arriba) es que `docs/pruebas-gui.md`
no menciona explícitamente `KICAD_MCP_GUI_REF`; el humano se entera
por el mensaje de skip del test. No lo edito por scope.

---

## Checklist para el humano (acciones manuales)

- Ejecutar el flujo GUI reportado arriba (§Pregunta 2) para validar
  los 3 `integration_gui`. Si `test_ipc_reports_real_kicad_version`
  sigue fallando con `no handler available for request of type
  kiapi.common.commands.GetVersion`, reportar la versión exacta de
  KiCad abierta y del paquete `kipy` instalado; puede indicar mismatch
  ADR-0002 que la sesión 06 tenga que dirimir.
- Abrir `scratchpad/rams_added.kicad_sch` en KiCad 10.0.4 y confirmar
  que carga sin errores. El warning "older version" es **esperado**
  (Hipótesis A): kicad-skip preserva el header 20250114 del original,
  que ya era KiCad 9.x. NO es evidencia de degradación.
- Confirmar en GUI que la reescritura compacta que hace kicad-skip
  (23 746 → 4 344 líneas) no rompe visualmente la hoja `rams.kicad_sch`
  y que el símbolo `U13_SPIKE` aparece en (317.34, 194.31) con la
  librería y forma correctas.

---

## Insumos para la sesión 06 (no son decisiones)

1. **D-06.1 es un gap real que afecta la promesa central del pipeline
   delta post-mutación.** Cualquier scope de sesión 06 que apunte a
   "el agente encadena mutaciones y pide `get_context_delta`" tiene
   que priorizar arreglar esa doble asimetría (memoria/disco + sch/pcb)
   antes que agregar tools nuevas. Solución mínima: cuando `base_snap`
   es vivo y de kind PCB, `curr` se construye vía
   `build_state_from_board`.

2. **kicad-skip es un writer válido para `add_symbol` (Hipótesis A),
   pero destructivo para el layout físico del archivo.** Implicancias:
   - No hay forma barata de detectar "sólo lo que agregó `add_symbol`"
     por diff textual — kicad-skip toca todo el archivo. Detección de
     cambios debe apoyarse en `NormalizedState` diff (delta TOON), no
     en mtime + hash de bytes.
   - El `add_symbol` que se diseñe tendrá que registrar un snapshot
     vivo `kind="sch"` en el momento del write (equivalente al T5 PCB),
     o el próximo `get_context_delta` disparará `EXTERNAL_EDIT_DETECTED`
     por su propio Save (regresa el falso positivo que ADR-0007 evita
     en PCB). La sesión 05 no dejó ningún camino de snapshot vivo para
     esquemáticos; hay que abrirlo.

3. **Deuda de documentación pequeña y contenida:**
   - Catálogo: sección general de la taxonomía debería declarar `data:
     dict[str,Any] | None` como campo estándar del envelope, no sólo
     bajo la nota de `get_context_delta`.
   - `docs/pruebas-gui.md`: añadir `KICAD_MCP_GUI_REF` a la lista de
     env vars del §E2E mutaciones.
   - `tests/test_toon_encoder.py:7`: docstring stale sobre xfails.

4. **Riesgo latente en el bridge:** el fallo `no handler available for
   request of type kiapi.common.commands.GetVersion` que observamos
   con socket presente sugiere que el kipy pinneado hoy puede no ser
   plenamente compatible con la instancia de KiCad del humano. Si se
   confirma con la validación GUI de arriba, hay un ADR de compatibilidad
   que la sesión 06 podría necesitar tocar antes de meter mano al
   pipeline de mutaciones sch.

---

Al terminar: `git status` debe mostrar `AUDITORIA-PRE-06.md` como
único archivo nuevo, sin commits.
