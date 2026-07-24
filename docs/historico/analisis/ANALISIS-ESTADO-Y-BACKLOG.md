# Análisis de estado y backlog propuesto — checkpoint de re-planificación

**Fecha:** 2026-07-11 · **Rama de trabajo al analizar:** `sesion-08` (working
tree limpio salvo untracked pre-existentes) · **Modo:** solo lectura +
mediciones. Sin commits.

**Entorno durante el análisis:** `verificar_entorno.py` → 9 OK · 2 WARN ·
0 FAIL. Los WARN: socket IPC no visible (KiCad estaba **cerrado** durante
todo el análisis — las suites `integration_gui` se reportan desde la última
corrida real, sesión 08) y `npx` ausente (Inspector, no requerido).

---

## Resumen ejecutivo

**Estado en una frase:** el pipeline PCB (leer→mutar→delta→validar→exportar)
está construido, medido y validado E2E contra KiCad real; el pipeline de
esquemático recién empieza (un `add_symbol` que solo clona) y **no existe
hoy un flujo end-to-end para diseñar una placa desde cero** — el hueco está
concentrado en poblar/cablear el esquemático y en el sync sch→pcb.

Los 3 hallazgos más importantes de la Parte 1:

1. **El cuello de botella no es nuestro código.** De los 3.483 ms de una
   mutación, ~3.111 ms (89 %) son round-trips IPC con KiCad; el cómputo
   Python propio medido hoy es de 4–9 ms por operación (§1.4). Esto vacía
   de contenido técnico al port a Rust para el objetivo 1 y también acota
   cuánto más se puede optimizar.
2. **El agente no puede *ver* el PCB antes de mutar.** `get_world_context`
   lee solo el `.kicad_sch` de disco (y falla con `UNSUPPORTED_HIERARCHY`
   en multi-hoja); el estado del board vivo solo existe como snapshot
   post-mutación. Además `add_track` — una de las 3 mutaciones — nunca se
   validó contra KiCad real (§1.2).
3. **Con un workaround barato ("hoja paleta") el flujo esquemático mínimo
   está a 3 tools de distancia** (`set_value`, asignación de footprint,
   conexión por labels), todas viables con la kicad-skip ya aprobada (§1.3).

La Parte 2 propone **16 candidatos** en 5 temas, sin orden de prioridad, y
cierra con **5 preguntas** que solo el humano puede responder (tipo de
placas, pasos que prefiere manuales, cliente MCP, workaround paleta, timing
de la decisión Rust).

---

# PARTE 1 — Estado del proyecto (solo evidencia)

## 1.1 Qué funciona (verificado en esta corrida, no recordado)

### Suites ejecutadas hoy (2026-07-11, KiCad cerrado)

```
uv run pytest -m "not integration and not integration_gui"  → 112 passed en 13.97 s
uv run pytest -m integration                                → 20 passed en 244.28 s (4:04)
uv run pytest -m integration_gui                            → 4 skipped (KiCad cerrado; esperado)
uv run mypy src/                                            → Success: no issues found in 31 source files
uv run ruff check src/ tests/                               → All checks passed!
```

Los 4 `integration_gui` pasaron por última vez contra KiCad 10.0.4 real en
la sesión 08 (2026-07-10, `docs/sesiones/08-reporte.md` §DoD). Cero
TODO/FIXME/xfail en `src/` y `tests/` (grep de hoy; únicos matches son las
palabras españolas "TODO"/"TODOS" en docstrings).

### Inventario de capacidades actuales (12 tools MCP expuestas)

Fuente de tokens/latencia: reportes 02–08 (mediciones contra fixtures y
contra el board real de 202 refs). La columna **Validación** distingue
"probado contra KiCad real" de "probado solo con fakes".

| Tool | Qué hace | tokens_est típico | Latencia típica | Nivel de validación |
|---|---|---|---|---|
| `health` | Estado server/kicad-cli/IPC (3 niveles)/proyecto | 78 abierto · **107 cerrado** (techo ~100, ⚠ +7 %) | 732 ms abierto · 327 ms cerrado (07 §T3) | Unit con fakes + medido contra KiCad real (07/08) |
| `get_world_context` | TOON del **sch de disco** | 109 (5 comp) · 652 (30 comp, max 800) · 448 (150 comp, focus) (03 §tokens) | ~0.8–2 s primera (kicad-cli netlist); 0.17 ms cache hit (medido hoy) | Integration real (kicad-cli) sobre 001–003. **Solo single-sheet** (§1.2 #3). Nunca sobre proyecto real |
| `get_context_delta` | ΔTOON base→actual, kind-aware | 19–20 vacío · 106–332 (72 pads) | Disco: ídem arriba. Vivo pcb: 1 pasada IPC ~3 s | Unit + integration sch/sch + **integration_gui pcb/pcb real** (07 T4.2) |
| `run_erc` | ERC estructurado (kicad-cli) | 407 (001, 7 violaciones) | ~2–5 s | Integration contra `erc_expected` de 001/002 (KiCad real) |
| `run_drc` | DRC estructurado (kicad-cli) | variable | ~30 s en 004_real | Integration contra 004_real |
| `export_bom` / `export_netlist` | CSV / netlist | mínimo (`{path,bytes}`) | ~1–2 s | Integration real |
| `export_render` | `sch_pdf` / `pcb_pdf` (`pcb_png` reservado) | mínimo | segundos | Integration solo `sch_pdf` (magic `%PDF`); `pcb_pdf` unit-only |
| `export_manufacturing` | Gerbers+drill tras Gate G3 | mínimo | ~30 s+ (DRC previo) | Integration: happy (005 limpio) + bloqueado (`.kicad_pro` estricto) |
| `move_footprint` | Mueve footprint vía IPC | confirm 13 | **μ 3.483 ms** en board de 202 refs (08 T3) | **E2E completo**: round-trip ±1 nm contra KiCad real + derivación verificada al nm (08 T2b) + unit con contadores de pasadas |
| `add_track` | Track lineal en net/layer | confirm 18 | ~similar (1 pasada + `get_nets`) | **Solo unit con fakes.** Patrón setter auditado (ADR-0008), pero **cero tests contra KiCad real** (§1.2 #1) |
| `add_symbol` | Clona símbolo ya instanciado en un `.kicad_sch` | confirm 20 | ~1 s (unit sobre 001) | Unit (8 casos) + verificación de efecto releyendo el archivo. **Sin validación GUI/ERC del output real**; demo en `/tmp/add-symbol-demo/` pendiente de inspección humana (08 T4) |

Infraestructura transversal verificada: Gate G1 (backup+git checkpoint, una
vez por proyecto), audit JSONL, retry acotado AS_BUSY solo en lecturas
idempotentes (`bridge/ipc.py:377-390`), logging JSON con
`tokens_est`/`latency_ms`/canales `read_ms`/`lookup_ms`/`verify_ms`.

**Presupuestos ADR-0004 (post-08):** confirms promedio 17 (techo 50 ✓);
global ≤400 ✓ (peor caso delta 332); único overrun: health cerrado 107 vs
~100 (aceptado en 08 T5 como trade-off de accionabilidad).

## 1.2 Qué falla o está frágil

Bugs abiertos: **ninguno conocido**. Fragilidades y deuda vigentes HOY:

1. **`add_track` sin validación E2E.** Los 4 tests `integration_gui`
   cubren version, round-trip de `move_footprint` (×2) y delta pcb/pcb —
   ninguno ejercita `add_track` contra KiCad real. Es exactamente la clase
   de gap que ocultó el bug T1 de `move_footprint` durante 3 sesiones
   (ADR-0008: "la cobertura debe verificar el efecto"). La auditoría de
   código (usa setters, no getter-mutación) es evidencia más débil que un
   round-trip.
2. **`add_symbol` — tres flancos abiertos** (reporte 08):
   - Hazard del editor abierto: documentado, no resuelto
     (`tool-catalog.md:208-213`).
   - `base_snap` soportado pero sin test unit (08 §dudas #7).
   - El archivo generado por la tool nunca se abrió en la GUI ni se le
     corrió ERC (el demo quedó para el humano). kicad-skip además reescribe
     TODO el archivo (23.746 → 4.344 líneas en el spike, AUDITORIA-PRE-06
     §P3) — los diffs de git del usuario sobre su propio sch quedan
     ilegibles tras la primera mutación del agente.
3. **`UNSUPPORTED_HIERARCHY` parte la superficie en dos.**
   `get_world_context`/`get_context_delta` de disco fallan en proyectos
   multi-hoja (`bridge/sch_positions.py:139`); 004_real — el único proyecto
   real del repo — **no puede leerse como contexto**. Pero `add_symbol` SÍ
   recorre todas las hojas (`tools/sch.py::_collect_all_refs`). Un agente
   puede mutar un proyecto que no puede ver.
4. **No hay lectura de contexto del PCB.** `get_world_context` ancla
   siempre en el `.kicad_sch` (`tools/world.py:179-182`, kind=`sch`); el
   estado del board solo se materializa como snapshot vivo **después** de
   una mutación (`tools/world.py:142-144`). El bridge ya tiene todo
   (`read_board_context`, `snapshot_footprints`) pero ninguna tool lo
   expone como lectura inicial.
5. **Busy transitorio.** El episodio de la sesión 06 (KiCad rechazando todo
   `get_items` hasta reiniciar) nunca se reprodujo (70/70 llamadas OK en
   AUDITORIA-PRE-07 §P2); el retry D-07.1 absorbe incidentes cortos en
   lecturas, las mutaciones fallan rápido con `data.ipc_status="busy"`
   (correcto). Riesgo latente aceptado, sin monitoreo agregado.
6. **Snapshots vivos no detectan ediciones externas** (ADR-0007,
   limitación aceptada; sin falsos negativos medidos aún).
7. **Bbox de validación = unión de footprints + 100 mm**, no Edge.Cuts
   (decisión sesión 03 #3, reabierta en 08 §dudas #5). Coordenadas absurdas
   se atrapan; el borde real no.
8. **Frontera latente de timeout:** el `GetItems` de 189 fps tarda ~3 s
   total pero cada sub-request queda <2 s; en boards >1000 fps el request
   inicial podría exceder los 2 s del timeout duro (AUDITORIA-PRE-07 §P5).
9. **Patrón "stub donde debería haber fixture":**
   `tests/test_pcb.py:251` — `_make_project` escribe `"(kicad_sch)"`
   literal. La auditoría pre-07 §P1 mostró que esto degrada al centinela
   del pipeline delta ("protege contra explota, no contra delta
   invertido"). Sigue igual. No se encontraron stubs nuevos de esta clase.
10. **El catálogo declara tools que no existen.** `get_component_detail`,
    `get_net_detail`, `list_unconnected` figuran en la tabla `world`
    (`tool-catalog.md:70-72`) y `discover_tools` en `meta`
    (`tool-catalog.md:21`) — ninguna está registrada en `src/` (grep hoy:
    solo menciones en docstrings). El catálogo es el contrato que consume
    otro LLM en runtime (F1/F3): un agente que lo lea intentará llamarlas.
11. **Gates G2, G4 y G5 no implementados.** `src/kicad_mcp/gates/` contiene
    solo `g1.py` y `g3.py`. G2 (elicitation destructiva) aún no tiene
    disparador posible (no hay tools de borrado); G4 (budget de sesión) y
    G5 (invalidator con pausa) no existen — hoy G5 está aproximado por el
    chequeo de mtimes en `base_snap`, que es opt-in del agente.
12. **Higiene menor:** fixture 004_real contaminada con
    `_autosave-video.kicad_pcb` y `~*.lck` sin trackear (alguien abrió el
    fixture directo en KiCad); `_ = ref` en
    `bridge/state_builder.py:60`; scripts de medición acumulándose en
    `scratchpad/` (`baseline_08.py` ya marcado "archivable").

## 1.3 Brecha contra un flujo de trabajo REAL

**Caso de referencia:** breakout de un sensor I²C (ej. BME280) — 1 sensor,
1 regulador 3V3, 1 conector de 4-6 pines, 4-6 pasivos: **~10 componentes,
una sola hoja**. Es el proyecto personal chico plausible y además esquiva
la limitación #3 de §1.2 (single-sheet).

Evidencia de viabilidad citada: **[kipy]** = API verificada en
`.venv/.../kipy/` hoy; **[skip]** = spike sesión 05
(`scratchpad/spike-kicad-skip.md`); **[cli]** = `kicad-cli --help` corrido
hoy. Dato duro nuevo de hoy: la API de esquemático por IPC de kipy 0.7
está marcada **`versionadded:: 0.7.0 (KiCad 11)`**
(`.venv/.../kipy/schematic.py:74-76`) → **prohibida por F4**. Toda mutación
sch en KiCad 10 pasa por archivo (kicad-skip).

| Paso | ¿Tool existe? | Qué falta | Viabilidad técnica | Esfuerzo |
|---|---|---|---|---|
| 1. Crear/abrir proyecto | **No** | Tool o convención. `KICAD_MCP_PROJECT` asume proyecto existente | Alta: `.kicad_pro`/`.kicad_sch`/`.kicad_pcb` vacíos son plantillas de texto; kicad-cli no crea proyectos [cli] | S |
| 2a. Colocar símbolos | **Parcial** (`add_symbol`) | Solo clona `lib_id` YA instanciado en la hoja (`tools/sch.py:136-156`, D-08.5 #1). En hoja nueva/vacía no hay nada que clonar → hoy no puebla desde cero | Media: instanciar desde librería externa = copiar el bloque `lib_symbols` desde los `.kicad_sym` del sistema — parseables con kicad-skip pero NO probado [skip §insuficiencias]. **Workaround viable HOY**: el humano deja una "hoja paleta" con 1 ejemplar de cada símbolo y el agente clona | L (librerías) / **S (workaround documentado)** |
| 2b. Valores | **No** (`set_value` reservado) | Escribir property `Value` | Alta: mismo mecanismo property-write que `add_symbol` usa para `Reference` [skip] | S |
| 2c. **Cableado** (wires/junctions/labels) | **No** (`connect_pins` reservado v0.5) | Todo. Es el hueco más grande del flujo | Media: kicad-skip escribe s-expressions arbitrarias pero wires NO probados [skip §insuficiencias]; grilla 1,27 mm y junctions obligatorios (CLAUDE.md §errores). **Alternativa más simple**: conectar por *labels* (colocar `global_label`/`label` sobre la punta del pin conecta por nombre, sin geometría de ruteo) — misma primitiva de escritura que add_symbol | L (wires) / M (labels, con spike previo) |
| 3. ERC | **Sí** (`run_erc`) | — | Probada (integration, multi-hoja OK vía kicad-cli) | — |
| 4. Asignar footprints | **No** | Escribir property `Footprint` del símbolo | Alta: ídem 2b [skip]. Elegir el footprint correcto es juicio del LLM (arquitectura §5.5) | S/M |
| 5. Sync sch→pcb | **No, y no automatizable en KiCad 10** | — | **Nula headless**: kicad-cli 10 no tiene comando de update [cli: subcomandos pcb = drc, export, import, render, upgrade]; IPC sch es KiCad 11 [kipy] (F4). Único camino: humano en GUI (F8). `reload_in_gui` (reservado) daría al agente lenguaje para pedirlo | **Paso humano** + S (hint/tool sin efecto) |
| 6. Colocar footprints | **Sí** (`move_footprint`) | Tras el paso 5 los footprints ya existen en el board; moverlos es el caso validado E2E. `place_footprint` (crear nuevo) no hace falta en este flujo | Probada (μ 3.5 s/op) | — |
| 7. Rutear | **Parcial** (`add_track`) | Segmento único; sin `add_via` (multicapa real la necesita); sin E2E (§1.2 #1). Freerouting = v0.4 | Alta para `add_via`: `kipy.board_types.Via` existe y `create_items` acepta cualquier wrapper [kipy `board.py:341`]. Ruteo autónomo LLM: no factible con calidad (arquitectura §9) — para 10 componentes el agente con tracks+vias alcanza | S (E2E track) + M (via) / L (freerouting) |
| 8. DRC | **Sí** (`run_drc`) | — | Probada | — |
| 9. Export fabricación | **Sí** (`export_manufacturing`, G3) | — | Probada (happy + bloqueo) | — |

### Camino mínimo end-to-end (con humano en el medio)

Si el humano acepta hacer a mano: **crear el proyecto (1), mantener la
"hoja paleta" (2a) y el sync en GUI (5)** — que son 3 acciones de minutos —
el subconjunto mínimo de trabajo nuevo que habilita el flujo completo es:

- `set_value` (S) + `set_footprint` (S/M) — property-writes calcados de
  `add_symbol`.
- Conexión por **labels** (M, con spike de validación primero) — evita el
  problema geométrico de wires.
- Test E2E de `add_track` (S) + `add_via` (M) para que el ruteo del agente
  sea confiable.
- Lectura de contexto PCB (M, §1.2 #4) para que el agente vea el board
  antes de tocar.

Con eso el agente cubre 2b→4 y 6→9; ERC/DRC ya están. Total estimado:
~2-3 sesiones. Sin el workaround paleta, sumar librerías externas (L)
mueve esto a ~4-5 sesiones.

## 1.4 Análisis Rust (objetivo 2 — datos, sin romanticismo)

**¿Dónde se va el tiempo de una mutación?** (medición sesión 08 T3, board
real 202 refs, μ de 5 corridas):

| Componente | ms | % | ¿Rust lo acelera? |
|---|---|---|---|
| `read_ms` — `GetItems` IPC (hilo UI de KiCad) | 2.887 | 83 % | **No** (espera de red/UI) |
| `lookup_ms` — `get_items_by_id` IPC | 53 | 1.5 % | No |
| `verify_ms` — verificación KIID IPC | 171 | 5 % | No |
| Resto (G1 backup, derivación, encode, logging) | 372 | 11 % | Parcialmente |

Del "resto", el cómputo Python puro medido **hoy** (script
`bench_encoder.py`, fixture 003 de 150 comp): `encode` TOON con degradación
= **9,3 ms/op**; `encode_delta` = **3,9 ms/op**; cache hit del state
builder = **0,17 ms**. El resto del "resto" es I/O (copia de backup, git
commit, disco). Un core Rust atacaría <10 ms de 3.483 ms: **<0,3 %**.

**¿Y las lecturas?** `get_world_context` primera llamada = 780 ms de
`kicad-cli sch export netlist` (subprocess, medido hoy) + 9 ms de encode.
`run_drc` = ~30 s de kicad-cli. Rust no acelera subprocesos de KiCad.

**¿Tokens?** El costo en tokens depende del **formato** TOON y de la
información (los 332 tokens del delta pcb/pcb son los 72 pads del SIM4X32,
no overhead del encoder). Portar el encoder a Rust produce los mismos
bytes: ahorro de tokens = 0.

**¿Fiabilidad?** Los bugs reales de las 8 sesiones fueron de **dominio**:
semántica de property-setter de kipy (ADR-0008), delta kind-aware
(D-06.1v2), netlist que no incluye el símbolo nuevo (08 T4). Ninguno es
prevenible por el sistema de tipos de Rust — coincide con S5 de la
arquitectura ("cierto para memoria/concurrencia; falso para lógica de
dominio, que serán la mayoría", `arquitectura.md §1.5`). Crashes, races o
leaks atribuibles a Python: **cero en 8 sesiones**. Además el binding IPC
oficial es Python; el Rust es experimental sin mantenimiento declarado
(`arquitectura.md §3.1`).

**Veredicto factual (no decisión):** un core Rust mejoraría <0,3 % de la
latencia de mutación y ~1 % de la de lectura fría, no afectaría el costo en
tokens ni la fiabilidad observada, y costaría re-implementar encoder +
delta + store + el contrato del bridge (más packaging dual, riesgo R6). La
condición que la propia arquitectura puso para v0.4 — "que duela el
rendimiento/mantenibilidad" (`arquitectura.md §10`) — **no se cumple hoy**:
el cuello es el hilo de UI de KiCad y kicad-cli, exactamente como predijo
RNF1. Si el objetivo 2 se mantiene, sería por aprendizaje (objetivo 4,
declarado no-guía), no por beneficio técnico demostrado.

## 1.5 Candidatos a SIMPLIFICACIÓN (complejidad sin retorno para el objetivo 1)

1. **Tools fantasma del catálogo** (§1.2 #10): `get_component_detail`,
   `get_net_detail`, `list_unconnected`, `discover_tools`. O se implementan
   (las dos primeras son baratas y útiles para Q&A) o se mueven a "Nombres
   reservados". Dejarlas en las tablas principales es deuda de contrato.
   Tocarlo es edición de spec → decisión humana (F1).
2. **`discover_tools` / router por categorías**: resolvía "100+ schemas
   queman la ventana" (`arquitectura.md §4.1`); este server expone **12
   tools** y el roadmap realista suma <10 más. Candidato a eliminarse del
   diseño (no del código: nunca se escribió) — simplificación de specs.
3. **Justificación desactualizada de `pcb_png`**: el catálogo dice
   "kicad-cli 10 no expone rasterizado nativo" (`tool-catalog.md:141-143`),
   pero `kicad-cli pcb render` **existe en 10.0.4** y saca PNG/JPEG
   (verificado hoy con `--help`; es render 3D, no plano de capas). La nota
   merece corrección; ver ficha N para el lado constructivo.
4. **Scripts de medición en `scratchpad/`**: `baseline_08.py` (ya marcado
   archivable), `measure_*` de 07/08, spike-venv de 05. Gitignorados, no
   son deuda de código, pero el prompt de cada sesión los re-descubre.
   Costo de archivarlos: minutos del humano.
5. **Micro-limpiezas**: `_ = ref` (`bridge/state_builder.py:60`), archivos
   `_autosave`/`.lck` en `tests/fixtures/004_real/` (+ patrón en
   `.gitignore`), docstring de `tools/world.py:1` que aún dice "MVP
   implementa get_world_context" (hay 2 tools).
6. **No hay abstracciones especulativas grandes.** `src/` son 4.882 líneas
   totales, sin código muerto detectado (grep de defs vs usos): las piezas
   grandes (`ipc.py` 933, `encoder.py` 500, `sch.py` 486) están todas en el
   camino caliente. La degradación §4 del encoder es la pieza más compleja
   pero está bajo contrato F1 (goldens) y es la palanca real de tokens
   (ADR-0004 §notas). **El codebase está notablemente limpio; la
   simplificación disponible es de specs/docs, no de código.**

---

# PARTE 2 — Backlog propuesto (PROPUESTA explícita; sin orden de prioridad)

Fichas agrupadas por tema. La priorización cruza esto con los objetivos del
humano — no la hago acá. Esfuerzo: S = media sesión · M = una sesión ·
L = 2+ sesiones.

## Tema A — Cerrar el flujo de esquemático (pasos 2b–5 de la tabla 1.3)

**A1. `set_value` + `set_footprint` (property-writes vía kicad-skip)**
- **Qué:** dos tools que editan las properties `Value` y `Footprint` de un
  símbolo existente, con las mismas validaciones/G1/audit/verificación de
  efecto que `add_symbol`.
- **Objetivo:** 1. **Evidencia:** tabla 1.3 pasos 2b y 4; mecanismo idéntico
  al ya probado (`tools/sch.py` property-write de `Reference`).
- **Esfuerzo:** S cada una (comparten el 80 % del pipeline con `add_symbol`).
- **Dependencias:** ninguna técnica; `set_value` es nombre reservado (usar
  tal cual, F3).
- **Riesgo si NO:** el flujo sch queda trunco: colocar sin valorar ni
  asignar footprint no produce nada fabricable. **Riesgo de hacerlo:** bajo;
  mismo hazard del editor abierto ya documentado.

**A2. Spike + tool de conexión por labels (`connect_pins` acotado)**
- **Qué:** spike primero (¿un `label`/`global_label` escrito por kicad-skip
  sobre la punta de un pin conecta la net al re-anotar/ERC?); si es verde,
  tool `connect_pins(ref, pin, net)` que coloca labels — sin geometría de
  wires.
- **Objetivo:** 1. **Evidencia:** tabla 1.3 paso 2c — el hueco más grande;
  spike 05 declara wires no probados; pines fuera de grilla de 1,27 mm no
  conectan (CLAUDE.md).
- **Esfuerzo:** M (spike) + M (tool). Wires geométricos serían L y quedan
  como plan B.
- **Dependencias:** decisión del arquitecto sobre la semántica (¿labels es
  una implementación aceptable de `connect_pins` o merece otro nombre?).
- **Riesgo si NO:** sin conexión no hay esquemático; el agente solo decora.
  **Riesgo de hacerlo:** R1 (kicad-skip frágil); el spike acota la apuesta a
  medio día antes de escribir producción.

**A3. Patrón "hoja paleta" documentado (workaround de librerías)**
- **Qué:** documentar (README/docs) el flujo: el humano coloca en la hoja un
  ejemplar de cada símbolo que el diseño usará; el agente clona con el
  `add_symbol` ACTUAL. Cero código; opcionalmente un mensaje de error más
  pedagógico cuando la hoja está vacía.
- **Objetivo:** 1. **Evidencia:** D-08.5 #1 (clonado-only es decisión
  vigente); tabla 1.3 paso 2a.
- **Esfuerzo:** S. **Dependencias:** ninguna.
- **Riesgo si NO:** `add_symbol` es inutilizable en proyectos nuevos y nadie
  lo sabe hasta chocar. **Riesgo de hacerlo:** ninguno; es honestidad
  documental.

**A4. `add_symbol` desde librerías externas (`.kicad_sym` del sistema)**
- **Qué:** extender `add_symbol` para instanciar desde las librerías de
  KiCad copiando el bloque `lib_symbols` al archivo.
- **Objetivo:** 1 (y 3: sin esto la herramienta no generaliza).
- **Evidencia:** spike 05 §insuficiencias ("pick de librerías no probado").
- **Esfuerzo:** L (spike de parseo de `.kicad_sym` + resolución de rutas de
  librería + tests).
- **Dependencias:** A3 la vuelve no-urgente; requiere revertir la decisión
  D-08.5 #1 ("fuera de scope permanente hasta nueva decisión") → humano.
- **Riesgo si NO:** fricción permanente del workaround paleta. **Riesgo de
  hacerlo:** R1 amplificado (formato de librerías es otra superficie).

**A5. `reload_in_gui` / protocolo de sync sch→pcb**
- **Qué:** tool sin efecto (nombre ya reservado) que devuelve la
  instrucción exacta para el humano ("abrí video.kicad_pro y ejecutá F8"),
  dándole al agente lenguaje explícito para el paso 5.
- **Objetivo:** 1. **Evidencia:** tabla 1.3 paso 5 (no automatizable en
  KiCad 10 — kicad-cli sin comando, IPC sch = KiCad 11/F4); 08 §dudas #4.
- **Esfuerzo:** S. **Dependencias:** ninguna.
- **Riesgo si NO:** el agente que agregó símbolos "espera" verlos en el pcb
  y no entiende por qué no están. **Riesgo de hacerlo:** ninguno.

## Tema B — Completar y endurecer el flujo PCB (pasos 6–7)

**B1. Lectura de contexto del PCB (exponer el mundo pcb)**
- **Qué:** que el agente pueda leer el board como TOON **sin mutar antes**:
  o `get_world_context(kind="pcb")` o una tool nueva sobre
  `bridge.read_board_context` + `build_state_from_snapshot` (piezas ya
  existentes).
- **Objetivo:** 1. **Evidencia:** §1.2 #4 (`tools/world.py:179-182` ancla
  en sch; el path pcb solo existe post-mutación en `world.py:142-144`).
- **Esfuerzo:** M. **Dependencias:** decidir la superficie (¿parámetro o
  tool nueva? cambia el catálogo, aditivo, F3 OK).
- **Riesgo si NO:** el flujo real 6→7 arranca ciego: el agente muta para
  poder ver. **Riesgo de hacerlo:** costo IPC ~3 s por lectura en boards
  medianos (ya conocido).

**B2. Test E2E de `add_track` (integration_gui)**
- **Qué:** round-trip contra KiCad real: `add_track` → re-leer tracks →
  verificar geometría/net → teardown que la borra (`remove_items` existe en
  kipy `board.py:613`).
- **Objetivo:** 1 (fiabilidad). **Evidencia:** §1.2 #1; precedente directo
  del bug T1 (ADR-0008).
- **Esfuerzo:** S. **Dependencias:** KiCad abierto (protocolo GUI vigente).
- **Riesgo si NO:** una de las 3 mutaciones en producción con la misma
  clase de cobertura que ocultó el bug histórico #1 del proyecto. **Riesgo
  de hacerlo:** ninguno.

**B3. `add_via`**
- **Qué:** mutación nueva vía IPC (`kipy.board_types.Via` + `create_items`),
  mismo pipeline rápido D-08.1 que `add_track`.
- **Objetivo:** 1. **Evidencia:** tabla 1.3 paso 7; nombre ya reservado.
- **Esfuerzo:** M (con B2 como plantilla de verificación).
- **Dependencias:** B2 primero (validar el patrón de test antes de sumar
  superficie).
- **Riesgo si NO:** ruteo del agente limitado a una capa. **Riesgo de
  hacerlo:** bajo.

**B4. Bbox por Edge.Cuts (menor)**
- **Qué:** reemplazar el bbox "footprints + 100 mm" por el contorno real en
  las validaciones de mutación.
- **Objetivo:** 1. **Evidencia:** §1.2 #7; 08 §dudas #5 (dos sesiones
  arrastrándolo).
- **Esfuerzo:** S. **Dependencias:** ninguna.
- **Riesgo si NO:** el agente puede colocar fuera del borde sin error
  temprano (el DRC lo atrapa después). **Riesgo de hacerlo:** ninguno.

## Tema C — Contexto y economía de tokens (el diferencial declarado)

**C1. Eval A — TOON vs JSON compacto vs CSV**
- **Qué:** el benchmark de comprensión+tokens definido en
  `arquitectura.md §5.8`, pendiente desde la sesión 04 (diferido 4 veces).
- **Objetivo:** 1 directamente (valida LA premisa del proyecto: que el
  formato reduce tokens sin perder comprensión) y 2 indirectamente (si TOON
  no gana, portar el encoder a Rust pierde todo sentido).
- **Esfuerzo:** M ("una tarde de laboratorio" según reporte 04, más
  análisis).
- **Dependencias:** ninguna técnica; requiere presupuesto de API del humano
  (~200 llamadas).
- **Riesgo si NO:** todo el costo del encoder+degradación+goldens descansa
  en una hipótesis no validada (S1, R7). **Riesgo de hacerlo:** que el
  resultado obligue a rediseñar el encoder — que es exactamente para lo que
  sirve.

**C2. Soporte multi-hoja en el contexto de disco**
- **Qué:** levantar `UNSUPPORTED_HIERARCHY`: extender
  `sch_positions`/`state_builder` para recorrer hojas (kicad-skip ya lo
  hace: spike parseó 7 hojas/395 símbolos).
- **Objetivo:** 1 si los proyectos reales del humano son multi-hoja
  (pregunta H1); 3 seguro.
- **Esfuerzo:** L (netlist jerárquico ya funciona vía kicad-cli; el parser
  de posiciones y el encoder de refs por hoja no).
- **Dependencias:** respuesta H1; posible impacto en spec TOON (¿cómo se
  nombra la hoja en `[C]`? → F1, humano).
- **Riesgo si NO:** la herramienta solo sirve para proyectos de una hoja.
  **Riesgo de hacerlo:** scope grande; F1 roza el spec del formato.

**C3. Contador agregado de `post_fallback` en `health`**
- **Qué:** monitoreo pasivo de la derivación local (08 §dudas #1): si el
  fallback empieza a disparar, se ve en `health` sin bucear logs.
- **Objetivo:** 1 (confianza en el pipeline rápido). **Evidencia:** 0
  fallbacks en todas las mediciones — hoy es invisible si eso cambia.
- **Esfuerzo:** S. **Dependencias:** ninguna. **Riesgos:** ninguno /
  +tokens en health (cuidar el techo ~100).

## Tema D — Deuda de tests y limpieza

**D1. Test unit de `base_snap` en `add_symbol`** — S, sin dependencias
(08 §dudas #7). Riesgo si no: la única validación de coherencia de la
cadena sch está sin red.

**D2. Resolver las tools fantasma del catálogo** — S/M. Decisión humana
(F1): implementar `get_component_detail`/`get_net_detail`/`list_unconnected`
(baratas: el `NormalizedState` ya tiene todo; útiles para Q&A U1 del
objetivo 1) **o** moverlas a reservados. `discover_tools`: proponer
eliminarla del catálogo (ver §1.5 #2).

**D3. Lote de higiene** — S: `_ = ref`; `_autosave`/`.lck` de 004_real
fuera + `.gitignore`; archivar scripts viejos de `scratchpad/`; corregir
nota de `pcb_png`; docstring de `world.py:1`. Riesgo: ninguno; es media
mañana.

**D4. Fixture parseable en `_make_project`** — S/M: reemplazar el stub
`"(kicad_sch)"` por un mini-sch válido (001 recortado) para que el
centinela del pipeline delta ataje "delta invertido", no solo "explota"
(AUDITORIA-PRE-07 §P1 describe el test exacto).

## Tema E — Estrategia

**E1. Dogfooding en dos etapas**
- **Qué:** usar la herramienta en un proyecto real chico del humano como
  sesión de validación. **Etapa 1 (ya posible):** proyecto existente con
  sch terminado — el agente coloca footprints, rutea con
  `add_track`(+`add_via` si B3), corre DRC, exporta. Ejercita el pipeline
  PCB completo que YA está validado E2E. **Etapa 2 (post A1/A2):** el flujo
  sch→pcb completo del caso de referencia 1.3.
- **Objetivo:** 1 (es literalmente el objetivo 1). **Evidencia:** tabla 1.3
  — la mitad PCB del flujo está lista hoy; la mitad sch no.
- **Esfuerzo:** M por etapa. **Dependencias:** etapa 1: B1 recomendable y
  B2 prudente; etapa 2: A1+A2+A5.
- **¿Prematuro?** La etapa 1 **no** lo es: todas sus tools están validadas
  contra KiCad real. Hacerla antes de construir más superficie sch es
  además la mejor fuente de priorización para la etapa 2. La etapa 2 sí es
  prematura hasta que A1/A2 existan.
- **Riesgo si NO:** seguir construyendo contra fixtures en vez de contra la
  necesidad real — el plan original ya quedó obsoleto una vez por eso.
  **Riesgo de hacerlo:** sobre un proyecto real del humano — G1 + git
  mitigan; usar copia.

**E2. Decisión Rust: proponer "no ahora, re-evaluar con datos nuevos"**
- **Qué:** registrar (ADR o nota) que el port v0.4 se difiere hasta que (a)
  Eval A valide el encoder que se portaría, y (b) el dogfooding muestre un
  cuello de botella que sea nuestro y no de KiCad.
- **Objetivo:** 2 (el objetivo es condicional: "solo si aporta beneficio
  real demostrado" — la evidencia de §1.4 dice que hoy no).
- **Esfuerzo:** S (documento). **Dependencias:** decisión del humano; C1 y
  E1 alimentan la re-evaluación.
- **Riesgo si NO:** sesiones L invertidas en <0,3 % de mejora mientras el
  flujo real sigue trunco. **Riesgo de hacerlo:** ninguno técnico; posterga
  el objetivo 4 (aprendizaje), que el humano declaró no-guía.

---

## Preguntas que necesitan respuesta humana

1. **¿Cómo son tus placas reales típicas?** ¿Single-sheet de 10-30
   componentes (el caso 1.3) o multi-hoja? — decide si C2 (jerarquía) es
   urgente o diferible, y calibra la Eval A.
2. **¿Qué pasos aceptás hacer a mano en la GUI de forma permanente?**
   Crear proyecto, mantener la hoja paleta, F8 sch→pcb, ¿ruteo fino? — cada
   "lo hago yo" borra un candidato del backlog (A4, freerouting) y define
   el camino mínimo real.
3. **¿Qué cliente MCP usás a diario y con qué modelo?** (Claude Code /
   Desktop / otro; ¿acepta imágenes?) — condiciona la utilidad de un render
   PNG para feedback visual (§1.5 #3 muestra que `kicad-cli pcb render` ya
   existe), el diseño de elicitation para G2, y la Eval A (tokenizador
   real para recalibrar `len/3.5`).
4. **¿Te sirve el workaround "hoja paleta" (A3) como puente estable**, o
   colocar símbolos desde las librerías del sistema (A4, esfuerzo L) es
   requisito para que la herramienta te resulte usable?
5. **¿Aceptás formalizar la decisión Rust como "diferida con condiciones"
   (E2)**, o preferís mantenerla abierta en el roadmap v0.4 tal como está?
