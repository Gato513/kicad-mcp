# Pruebas GUI — protocolo manual (marca `integration_gui`)

Este documento describe cómo un humano puede correr los tests marcados
`integration_gui`, que requieren un KiCad **con el API server activo**
y un proyecto de prueba abierto. No hay automatización posible del
"abrir el proyecto en KiCad" para el MVP (F4: sin nightlies / features
anunciadas).

## Requisitos previos

1. KiCad ≥ 9.0 instalado (ADR-0002). Recomendado: 10.0.4.
2. En KiCad: **Preferences → Plugins → Enable API server**. Reiniciar
   KiCad después del cambio.
3. Verificar que el socket existe:
   ```bash
   ls -l /tmp/kicad/api.sock
   ```
   Si no existe, el API server no está corriendo (revisar Preferences).

## Protocolo (cualquier fixture)

Los tests `integration_gui` deben ver **una copia** del proyecto en
`tmp` (regla de la sesión 03: los fixtures nunca se mutan in place).

1. Copiar la fixture a una carpeta escritura:
   ```bash
   cp -r tests/fixtures/004_real /tmp/gui-test-project
   ```
2. Abrir el proyecto en KiCad:
   - **File → Open Project…** → `/tmp/gui-test-project/video.kicad_pro`.
   - Abrir la PCB desde el project manager (necesario para que
     `get_board()` devuelva algo).
3. En una terminal, con KiCad ya abierto:
   ```bash
   export KICAD_MCP_GUI_TEST=1
   export KICAD_MCP_PROJECT=/tmp/gui-test-project
   # Si KiCad no exportó KICAD_API_SOCKET al ambiente donde corre el
   # test (típico: el terminal es una sesión distinta), fijalo:
   export KICAD_API_SOCKET="ipc:///tmp/kicad/api.sock"
   uv run pytest -m integration_gui -v
   ```
4. Al terminar: cerrar KiCad (o dejarlo abierto para más pruebas). El
   directorio `/tmp/gui-test-project` puede borrarse — no hay
   nada en él que no sea reproducible.

## Skip esperados

Un test `integration_gui` hace **skip con mensaje claro** cuando:

- `KICAD_MCP_GUI_TEST != 1` — el humano no autorizó ejercitar el socket.
- El socket no existe o la conexión falla — el humano no abrió KiCad,
  o el API server está deshabilitado.

Skip **no** es fallo: es la vía de que CI y `pytest -m integration`
(sin `_gui`) sigan siendo automáticos.

## Cobertura actual (`integration_gui`)

- `tests/test_ipc.py::test_ipc_reports_real_kicad_version` (Tarea 5):
  conecta al socket real, pide `get_version()` y valida
  `major ≥ 9`. Es el test-humo mínimo del bridge.
- `tests/test_ipc.py::test_move_footprint_round_trip_against_open_board`
  (sesión 04 T6): E2E de mutaciones. Ver §E2E mutaciones abajo.

## §E2E mutaciones (`test_move_footprint_round_trip_against_open_board`)

Verifica que `move_footprint` persiste vía IPC y que
`get_footprint_position` re-lee el cambio con tolerancia de redondeo.
No requiere que el humano ejecute mutaciones a mano; sólo abrir el
proyecto y pasarle el `ref` conocido al test.

Pasos:

1. Copiá 004_real a tmp e iniciá git:
   ```bash
   cp -r tests/fixtures/004_real /tmp/mut-round-trip
   git -C /tmp/mut-round-trip init && git -C /tmp/mut-round-trip add -A \
     && git -C /tmp/mut-round-trip commit -m "baseline"
   ```
2. Abrí `/tmp/mut-round-trip/video.kicad_pro` en KiCad y **abrí también
   el .kicad_pcb** (el board debe estar en foco para que `get_board()`
   devuelva algo).
3. Elegí un `ref` conocido del board — por ejemplo `U1` para 004_real
   (`kicad-cli pcb export drl --list-refs …` o simplemente mirando el
   esquemático). Anotalo.
4. En terminal:
   ```bash
   export KICAD_MCP_GUI_TEST=1
   export KICAD_MCP_GUI_REF=U1                              # ejemplo
   export KICAD_MCP_PROJECT=/tmp/mut-round-trip
   export KICAD_API_SOCKET="ipc:///tmp/kicad/api.sock"
   uv run pytest -m integration_gui -k round_trip -v
   ```
5. El test:
   - Lee la posición inicial de `KICAD_MCP_GUI_REF` vía IPC.
   - Desplaza 0.127 mm (grilla de 50 mil) en x e y.
   - Llama `move_footprint`.
   - Re-lee y verifica igualdad con ±1 nm (redondeo banker's).
6. Al terminar: cerrar KiCad y borrar `/tmp/mut-round-trip`.

**Skip esperados:**
- Sin `KICAD_MCP_GUI_TEST=1` → skip claro.
- Sin `KICAD_MCP_GUI_REF` → skip con ejemplo del env var.
- Sin `KICAD_MCP_PROJECT` → skip (para el test de la tool MCP; el round-trip
  crudo del bridge no lo necesita).
- KiCad abierto pero sin board en foco → skip con "No hay board abierto".

**Env vars (checklist, sesión 06 auditoría):**

| Env var                | Requerida para                                    | Ejemplo                              |
|------------------------|---------------------------------------------------|--------------------------------------|
| `KICAD_MCP_GUI_TEST=1` | Todos los `integration_gui`                       | `1`                                  |
| `KICAD_MCP_PROJECT`    | Tests que registran audit y snapshots             | `/tmp/gui-test-project`              |
| `KICAD_MCP_GUI_REF`    | Round-trip y confirm con ref del board            | `U19` (cualquier ref existente)      |
| `KICAD_API_SOCKET`     | Direccionar el socket (default: `/tmp/kicad/api.sock`) | `ipc:///tmp/kicad/api.sock`     |

**Diagnóstico H1 vs H2 (sesión 06 T1).** Si el round-trip falla con
`x1 == x0` **exacto** (la mutación no se movió aunque el confirm reportó
éxito), el candidato inmediato es una de estas dos causas:

- **H1 histórica**: kipy exige `begin_commit()` / `push_commit()` explícito.
  **DESCARTADA** por doc de kipy 0.7.1 (`kipy/board.py:315-316`): *"If you
  do not call begin_commit, any changes made to the board will be committed
  immediately"*. Sin `begin_commit` la escritura es inmediata.
- **H1 real (nombre confuso, causa distinta)**: el bridge está mutando una
  **copia local del proto** en lugar del interno. En kipy 0.7.1
  (`board_types.py:1935-1937` y `geometry.py:38-42`), el getter
  `fp.position` devuelve `Vector2(self._proto.position)` — un objeto NUEVO
  que hace `CopyFrom` del proto. Escribir `fp.position.x = valor` muta esa
  copia; `raw_board.update_items(fp)` envía el proto original sin cambios.
  Fix: usar el setter `fp.position = Vector2.from_xy(nm_x, nm_y)` que
  escribe sobre `self._proto.position` y arrastra fields/pads por delta.
- **H2**: la re-lectura devuelve estado cacheado. Descartada por
  inspección de `board.get_footprints()` en kipy (siempre pide `GetItems`
  al server; no hay cache local).

Este diagnóstico está anclado en el `ADR-0008` (kipy write semantics).

## Protocolo de mutaciones (`move_footprint`, `add_track`)

Estas tools están detrás del Gate G1: la PRIMERA mutación de la
sesión copia `.kicad_sch` y `.kicad_pcb` a
`<proyecto>/.kicad-mcp/backups/<ts>/` y hace un `git commit` si el
proyecto es un repo. Ejecutar el protocolo de mutaciones en una copia
tmp del fixture (nunca sobre el fixture original) y validar releyendo
por IPC.

Pasos manuales:

1. Copiá el proyecto a tmp e iniciá un repo local para probar el
   checkpoint git de G1:
   ```bash
   cp -r tests/fixtures/004_real /tmp/mut-test
   git -C /tmp/mut-test init && git -C /tmp/mut-test add -A \
     && git -C /tmp/mut-test commit -m "baseline"
   ```
2. Abrí `/tmp/mut-test/video.kicad_pro` en KiCad y también su
   `.kicad_pcb`.
3. En terminal (con KiCad abierto):
   ```bash
   export KICAD_MCP_GUI_TEST=1
   export KICAD_MCP_PROJECT=/tmp/mut-test
   export KICAD_API_SOCKET="ipc:///tmp/kicad/api.sock"
   ```
4. Ejecutá el ping mínimo (Tarea 5): `uv run pytest -m integration_gui`.
5. Para las mutaciones (sesión siguiente), correr manualmente contra
   el servidor por MCP Inspector o llamando la tool desde un script.
   El test automatizado de mutación con relectura queda propuesto
   para v0.3 (requiere Snapshot Store para verificar).

Después de las mutaciones deberías ver:

- `/tmp/mut-test/.kicad-mcp/backups/<timestamp>/*.kicad_pcb` y `.kicad_sch`.
- `/tmp/mut-test/.kicad-mcp/audit.jsonl` con una línea JSON por
  cada mutación (aceptada o rechazada).
- Un commit git en `HEAD` con mensaje `checkpoint: pre-mutación
  kicad-mcp`.

Al terminar: cerrar KiCad y borrar `/tmp/mut-test` — es reproducible.

## Contención IPC de la suite `integration_gui` (D-12.7, sesión 12)

**Fenómeno observado.** Bajo carga (correr toda la suite `integration_gui`
seguida, con el PCB Editor procesando otras cosas), un puñado de tests
—históricamente ~4— fallan de forma **transitoria** con un
`KICAD_CLI_FAILED` cuyo `data.ipc_status == "unhandled"` (mapeado desde
`AS_UNHANDLED` del envelope IPC). **Corridos en aislamiento pasan.** No es
un bug del código: es la cola de profundidad 1 de KiCad (todo request se
procesa en el hilo de UI, timeout duro de 2 s) rechazando peticiones
mientras la UI está ocupada. Es el mismo estado protocolar que distingue
"PCB Editor no abierto" de "ocupado"; bajo ráfaga se manifiesta como ruido.

**Orden de corrida recomendado.** Para minimizar el ruido transitorio:

1. Dejá que KiCad **termine de abrir** el board y de refill/DRC en tiempo
   real ANTES de lanzar la suite (esperá a que la UI quede quieta).
2. Corré los tests de LECTURA primero (los round-trips de
   `get_world_context`/`get_component_detail`), luego los de MUTACIÓN
   (`add_track`, `add_via`, `move_footprint`, `draw_board_outline`), que
   son más pesados y dejan a KiCad ocupado (refill de zonas).
3. Si un test falla con `ipc_status="unhandled"`, **re-corrélo aislado**
   (`uv run pytest -m integration_gui -k <nombre>`) antes de reportar un
   bug: la mayoría de las veces pasa.
4. Evitá correr `run_drc`/`export_*` (que lanzan `kicad-cli` sobre disco,
   ~40 s) intercalados con mutaciones IPC en la misma ráfaga: compiten por
   la UI y amplifican el fenómeno.

**Propuesta de marker `integration_gui_slow` (F5 — el humano decide).** El
loop completo de mutación de la sesión 11 (T6) y los round-trips lentos se
beneficiarían de un marker separado para poder correrlos aislados del resto.
No toco `pyproject.toml` (F5); la línea exacta para agregar al bloque
`markers` de `[tool.pytest.ini_options]` sería:

```toml
    "integration_gui_slow: integration_gui pesado (loops de mutación + refill); correr aislado por la contención IPC (D-12.7)",
```

Con ese marker, la suite rápida quedaría `-m "integration_gui and not
integration_gui_slow"` y el loop pesado `-m integration_gui_slow`, cada uno
con KiCad recién quieto. Si el humano lo agrega, marcar los tests del loop
completo (sesión 11 T6) y los round-trips de `draw_board_outline` con él.

## Recarga manual post-`route_board` (sesión 14, D-14.1)

`route_board` escribe el ruteo a **disco** (headless, subprocess Freerouting +
`pcbnew` del sistema); el **PCB Editor vivo queda detrás**. Mientras eso pasa,
el store marca `live_stale=True` y `route_board` bloquea toda mutación IPC y
`save_board` con `EXTERNAL_EDIT_DETECTED` — si el agente mutara y guardara,
**pisaría el ruteo con cobre viejo**. Protocolo para volver a un editor
consistente:

1. **Verificá el confirm** de `route_board`
   (`OK route_board X/X nets +NNN tracks +NN vias drc_err=0 [snap:N]`). El
   ruteo YA está en disco y es correcto; el DRC de disco lo confirma
   (`run_drc`, `export_render pcb_png`, `export_manufacturing` leen el estado
   ruteado sin bloquearse).
2. **Recargá el board en KiCad**: en el PCB Editor, **File → Revert**
   (`Ctrl+…` según binding) para descartar el estado vivo viejo y cargar el
   `.kicad_pcb` de disco (con el ruteo). Alternativa equivalente: cerrar el
   board (sin guardar) y reabrir el `.kicad_pcb`. **NO uses `Ctrl+S`** antes de
   revertir: guardarías el board viejo sobre el ruteo.
3. **Confirmá la recarga al agente**:
   `get_world_context(kind='pcb', confirm_reloaded=true)`. Esto limpia el flag
   `live_stale`; a partir de ahí las mutaciones IPC y `save_board` vuelven a
   funcionar sobre el board ya ruteado. Sin `confirm_reloaded`, la lectura viva
   sigue funcionando pero el TOON lleva una línea
   `[AVISO] editor vivo detras del disco (route_board)` para recordártelo.

**Por qué manual:** KiCad 10 no expone recarga programática del board (D-12.4,
`reload_in_gui` diferido a KiCad 11). El paso 2 es humano por necesidad, no por
diseño — es una acción de segundos.

**Test `integration_gui_slow` del round-trip (sesión 14, T3).**
`tests/test_route_board_gui_slow.py` ejercita el flujo COMPLETO contra una
**copia** del proyecto chico de spike (`/tmp/spike-route-proyecto`, 24 fp / 64
conexiones) — **no** el board de 189 fp de gui-test-project (demasiado denso).
Dura ~2–3 min (dominado por el router). Correr AISLADO:
`uv run pytest -m integration_gui_slow`. Requiere los tres requisitos de
sistema (Java ≥17, `KICAD_MCP_FREEROUTING_JAR`, `pcbnew` del sistema) — se
salta si falta alguno. Simula el paso 2 con `confirm_reloaded=true` (no recarga
KiCad de verdad, sólo verifica el destrabe del flag).
