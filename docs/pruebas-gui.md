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

## Próximas cargas (sesión 03 en adelante)

Se agregarán en Tarea 6:

- Un `integration_gui` que ejecuta `move_footprint` sobre un board
  copiado a tmp y relee la posición vía IPC para verificarla.
- Un `integration_gui` que ejecuta `add_track` entre dos pines de un
  net conocido y valida que el track aparezca en el board.

Ambos requieren el board de prueba **cargado en la sesión de KiCad**
antes de correr los tests. Sin eso, `get_board()` devuelve `None` y los
tests se saltan.
