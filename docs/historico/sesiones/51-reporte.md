# Sesión 51 — ERC ×100 (F-03), pseudo-símbolos #PWR/#FLG (R13) y doc del lock no reentrante

## Resumen ejecutivo

Tres cierres de deuda del bridge, uno por commit, en la rama
`sesion/51-doc-lock-no-reentrante`. Dos son fixes de código con test; el
tercero es documentación de una regla de concurrencia. Ninguno toca
`route_board`, zonas ni gates, por lo que no aplica D-23.2 ni F2.

## Cambios

**`8611fee` — F-03 / F-19b-12: posiciones del ERC ÷100.** La causa está en
`kicad-cli` 10.0.6, no en el bridge: `sch erc --format json` reporta las
posiciones ÷100 con `coordinate_units` en mm (U1 en (127, 63.5) sale como
(1.27, 0.635)), verificado contra el `.kicad_sch`. `run_erc` compensa ×100
sólo en la serie 10.0.x (`bridge/rules.py::_erc_pos_scale`); otras
versiones pasan los valores crudos para no sobrecorregir si upstream lo
arregla. `docs/specs/tool-catalog.md` actualizado en el mismo commit (DoD
#3). Tests en `tests/test_rules.py`.

**`e086328` — R13: `get_world_context(kind="sch")` con `#PWR*`/`#FLG*`.**
`kicad-cli` excluye del netlist los refs `#`-prefijados, pero el
`.kicad_sch` raíz los trae; el cruce posiciones/netlist levantaba
`KICAD_CLI_FAILED` en cualquier esquemático con símbolos de alimentación.
Fix en `bridge/state_builder.py::_rebuild`: se descartan de las
posiciones los refs `#`-prefijados antes de indexar (cubre también `#PWR?`
repetidos). Un ref real sin netlist sigue siendo error. Tests en
`tests/test_state_builder.py` (2 unit + 1 `integration`).

**`c7be48e` — doc del lock no reentrante.** La regla central queda en el
docstring de módulo de `bridge/ipc.py`: `self._lock` no es reentrante,
re-adquirirlo es un deadlock silencioso, y los helpers que corren bajo el
lock no lo toman. Cierra la deuda registrada en sesión 19d (antecedente:
`_edge_cuts_bbox_nm`, sesión 31b).

## Verificación al cierre

- `pytest -m "not integration and not integration_gui and not integration_gui_slow"`: verde.
- `ruff check` y `ruff format --check`: limpios (95 archivos).
- `mypy src/`: sin issues (36 archivos).
- `verificar_entorno.py`: 13 OK · 3 WARN · 0 FAIL. WARN: `KICAD_MCP_FREEROUTING_JAR`
  sin setear, socket IPC no visible (KiCad cerrado), `npx` ausente.

## No verificado

- `-m integration` e `-m integration_gui_slow` **no se corrieron al cierre**
  (KiCad cerrado). El test `integration` de R13 y los cambios de bridge de
  F-03 conviene correrlos con KiCad abierto antes de mergear.
- **Sin auditoría de Codex** sobre estos tres commits (AGENTS.md §6: cambio
  a `src/` es disparador). Pendiente de decisión del humano.

## Sin ADR

Ningún contrato arquitectónico nuevo: un fix de escala por versión, un
filtro de pseudo-símbolos y una aclaración de comportamiento.

## Commits

Tres commits convencionales (`fix:`, `fix:`, `docs:`) con trailer de
atribución, más el de documentación de esta sesión. Sin push (DoD #6).
