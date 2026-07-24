# Sesión 09 — Pipeline PCB completo, confiable y visible

**Rama:** `sesion-09` (desde `master`). Un commit por tarea. No pushear.
**Entorno vivo:** KiCad 10.0.4 con el PCB Editor cargado
(`/tmp/gui-test-project/video.kicad_pcb`), env vars exportadas. B1, B2 y
B3 necesitan KiCad real.

Leé antes de empezar: `CLAUDE.md`, `docs/HOJA-DE-RUTA-V2.md` (nueva — es
el plan vigente y contiene las decisiones D-R1..D-R7),
`ANALISIS-ESTADO-Y-BACKLOG.md` (tu propio análisis; las fichas B1/B2/B3
son el diseño de esta sesión) y `docs/componentes-pcb.md`.

Esta sesión cierra el pipeline PCB para habilitar el **Dogfooding
Etapa 1** (sesión 10): el humano va a usar la herramienta sobre una
placa real suya. Todo lo que quede frágil acá, explota ahí.

---

## Decisiones vinculantes del arquitecto

- **D-09.1 (superficie de la lectura PCB):** se extiende
  `get_world_context` con parámetro `kind: Literal["sch","pcb"]`
  (default `"sch"`, retrocompatible). Con `kind="pcb"`: lee el board
  VIVO vía `bridge.read_board_context` (1 pasada IPC), construye el
  estado con las piezas existentes, registra snapshot vivo
  (`mtimes=None`) y devuelve TOON con el `snap_id` en la cabecera — el
  agente puede mutar o pedir delta inmediatamente con ese base_snap.
  `focus_ref`/`radius_mm`/`max_tokens` aplican igual (la degradación §4
  es agnóstica del kind). Errores: PCB Editor cerrado →
  `KICAD_CLI_FAILED` con `data.ipc_status="unhandled"` y hint de abrir
  el editor (mapeo D-07.2 ya existente); KiCad cerrado →
  `KICAD_NOT_RUNNING`.
- **D-09.2 (teardown de tests destructivos):** los tests E2E de
  `add_track`/`add_via` limpian lo que crean. El teardown puede usar
  kipy directamente DENTRO del archivo de test (código de test, no de
  producción, documentado con comentario); NO se agrega una operación
  de borrado al bridge ni al catálogo — borrar es territorio del Gate
  G2, que no existe aún, y no se introduce por la puerta de atrás de un
  teardown.
- **D-09.3 (pcb_png):** `export_render` gana el formato `pcb_png` REAL
  vía `kicad-cli pcb render` (verificado presente en 10.0.4). Es un
  render 3D del board, no un plano de capas — documentarlo así en el
  catálogo (corrigiendo la nota desactualizada de
  `tool-catalog.md:141-143`). Propósito: feedback visual para Claude
  Code (acepta imágenes, D-R5). Respuesta de la tool: `{path, bytes}`
  como los demás exports, tokens mínimos.
- **D-09.4 (catálogo honesto, D-R7):** `get_component_detail`,
  `get_net_detail` y `list_unconnected` se MUEVEN de las tablas
  principales a "Nombres reservados". `discover_tools` se ELIMINA del
  catálogo (con una línea en el ADR de la sesión explicando por qué: 12
  tools no justifican un router; decisión D-R7). El catálogo es
  editable por vos; F3 intacta (no se toca ningún código de error).
- **D-09.5 (ADR Rust):** nuevo ADR "Port a Rust v0.4: diferido con
  condiciones" citando los datos de `ANALISIS-ESTADO-Y-BACKLOG.md §1.4`
  (89 % IPC, <0,3 % atacable, 0 bugs de lenguaje en 8 sesiones), las
  dos condiciones de re-entrada (Eval A valida el encoder + dogfooding
  revela cuello propio) y la ratificación del humano (2026-07-11).

---

## Fase 0 — Verificación

`verificar_entorno.py`; env vars; smoke `integration_gui -k version` →
PASS; suite de arranque → 112 unit esperados.

## Tarea 1 — B1: lectura de contexto PCB (D-09.1)

- Implementación + catálogo (entrada de `get_world_context`
  actualizada con el parámetro, ejemplos de ambos kinds, errores).
- Tests: unit con bridge fake (kind pcb feliz, editor cerrado, KiCad
  cerrado, focus/radius sobre posiciones pcb, budget con degradación)
  + 1 integration_gui contra el board real de 202 refs: leer sin haber
  mutado, verificar cabecera `[snap:N]` con N>0 y presencia de refs
  conocidas (usá `docs/componentes-pcb.md`). Medí tokens_est con y sin
  focus (esperable: board completo va a necesitar budget — reportá
  cuánto pide el board de 202 refs sin degradar).

## Tarea 2 — B2: E2E de `add_track` (D-09.2)

- Test integration_gui de round-trip: `add_track` en una net real del
  board (elegí una net de `docs/componentes-pcb.md` o de get_nets) →
  re-leer tracks vía kipy → verificar geometría (start/end ±1 nm) y
  net asignada → teardown que la borra (kipy directo en el test,
  comentado, try/finally).
- Si el round-trip revela un bug (precedente: T1 de la 06), aplicá el
  protocolo conocido: diagnóstico con evidencia del código de kipy,
  fix en el bridge, revalidación. Reportá aparte si ocurrió.

## Tarea 3 — B3: `add_via` (con B2 como plantilla)

- `tools/pcb.add_via(x_mm, y_mm, net, base_snap?, size/drill con
  defaults sanos del board)` vía `kipy.board_types.Via` +
  `create_items`, pipeline rápido D-08.1/D-08.2 (pre-pasada compuesta,
  post-estado derivado si aplica — evaluá si la derivación tiene
  sentido para un ítem creado; si no, una re-lectura puntual por KIID
  del ítem creado alcanza; argumentá la elección).
- Validaciones pre-mutación: net existe, posición en bbox. Confirm
  ≤50 tokens con snap_id. G1, audit, sin retry en la escritura
  (D-07.1). Catálogo completo (`add_via` ya está reservado — usá el
  nombre, F3).
- Tests: unit con fakes (éxito, net inexistente, busy sin retry) +
  integration_gui round-trip con teardown (D-09.2).

## Tarea 4 — pcb_png real (D-09.3)

- Implementación + corrección de la nota del catálogo + test
  integration (magic bytes PNG, tamaño >0) contra 005 o el proyecto
  de prueba.
- Bonus barato si el CLI lo permite sin pelea: parámetros de
  perspectiva/zoom con defaults fijos documentados. No inviertas más
  de lo S estimado; si el CLI se resiste, default pelado y anotás.

## Tarea 5 — ADR Rust diferido (D-09.5) + catálogo honesto (D-09.4)

Dos ediciones documentales, un commit cada una.

## Tarea 6 — Higiene D3

- `_ = ref` en `bridge/state_builder.py:60`.
- Sacar `_autosave-video.kicad_pcb` y `~*.lck` de
  `tests/fixtures/004_real/` + patrones en `.gitignore`
  (`_autosave-*`, `*.lck`). Ojo: los fixtures son F1 en su CONTENIDO;
  estos archivos son basura de la GUI, no fixtures — borrarlos es
  correcto, y el .gitignore evita la reincidencia. Dejalo explícito en
  el mensaje de commit.
- Docstring stale de `tools/world.py:1`.
- Listar en el reporte los scripts de `scratchpad/` archivables (no
  borrar).

---

## Fuera de scope

- Todo el Tema A (flujo sch) — es de las sesiones 11-12.
- `place_footprint`, borrado de items como tool, G2/G4/G5.
- Multi-hoja (D-R1), librerías externas (D-R4), Freerouting (D-R3),
  Rust (D-09.5).
- D4 (fixture parseable en `_make_project`) — va en la 11 junto con la
  deuda de tests sch.

## Definition of Done

```
uv run pytest -m "not integration and not integration_gui"  → verde
uv run pytest -m integration                                → verde (< 5:00)
uv run pytest -m integration_gui                            → verde (los 4 previos + los 3 nuevos: B1, B2, B3)
uv run mypy src/                                            → Success strict
uv run ruff check + format --check                          → clean
```

## Reporte final obligatorio

1. Estado por tarea. Si B2 destapó un bug de `add_track`: sección
   propia con diagnóstico y fix (protocolo ADR-0008).
2. tokens_est de `get_world_context(kind="pcb")` sobre el board de 202
   refs: completo sin budget, con focus r=20 en una ref, y con
   max_tokens forzando degradación. Latencia de la lectura.
3. Confirm literal de `add_via` + tokens. Salida del round-trip E2E de
   track y via.
4. Un `pcb_png` de muestra del board de prueba en /tmp (ruta en el
   reporte) para que el humano lo vea.
5. Promedios: global ≤400, confirms ≤50. Tiempo de integration.
6. Checklist de lo que el Dogfooding Etapa 1 necesita del humano
   (desde tu conocimiento del código): qué debe preparar (copia del
   proyecto, sch terminado, F8 hecho, KiCad abierto, env vars) para
   que la sesión 10 arranque sin fricción.
7. Dudas abiertas.
