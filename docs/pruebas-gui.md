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
