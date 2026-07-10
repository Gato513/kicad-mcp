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
