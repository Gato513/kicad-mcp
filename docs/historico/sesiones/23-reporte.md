# Reporte de sesión 23 — Investigación F-D4-02

**Tipo:** investigación pura (sin fix de fondo). Rama
`sesion/23-investigacion-fd4-02`. Reporte completo con evidencia:
`docs/investigacion/23-fd4-02.md`.

## Resumen ejecutivo

F-D4-02 (bandera roja V3 de Dogfooding 4) **no es lo que parecía**. No es un
mecanismo de protección ausente contra vías nuevas del autorouter — es un
**bug de orden de medición + falta de persistencia** en `route_board`,
compuesto con un **hallazgo arquitectónico real** sobre Freerouting:
Freerouting no respeta el plano GND como exclusión para nets ajenos, sólo
para el net dueño del plano. El post-procesamiento existente
(`refill_zones()` + `enforce_hole_clearance()`) SÍ arregla el problema en el
board vivo — confirmado 3/3 veces en esta sesión — pero (a) `route_board`
mide y reporta el DRC ANTES de que ese arreglo corra, y (b) nunca lo guarda a
disco automáticamente. El board que D4 dejó guardado (encontrado al inicio de
esta sesión, todavía vivo en KiCad) **ya estaba arreglado** sin que la sesión
22 se diera cuenta.

## Bloque 1 — Reproducción (✓ completado, reproducido en vivo)

Estado inicial encontrado: KiCad seguía abierto con el proyecto de D4 (no
reinicié — sin control de GUI). Forense sorpresa: el board vivo, con las
mismas 28 vías reportadas como violación en D4, mostraba **0
`hole_clearance`** — evidencia preservada en scratchpad.

Reproducción controlada (autorizada explícitamente por el humano vía
`AskUserQuestion` para el `delete_tracks_bulk`): tracks borrados →
`run_drc()` pre-route (0 `hole_clearance` preexistentes, aclara la pregunta
del prompt: los "4" del prompt eran los keepouts V1-1, no errores DRC) →
`route_board(timeout_s=600)` → `err_post:40` con `hole_clearance:10` →
`run_drc()` independiente = 40 (coincide) → **`save_board()` → `run_drc()` =
9, `hole_clearance:0`.** El simple guardado elimina el problema.

## Bloque 2 — Instrumentación (✓ completado, sin editar código fuente)

No se pudo hacer logging con `print()` (hubiera requerido `/mcp reconnect`,
que interrumpe la sesión de KiCad en vivo y no lo puedo disparar yo). Se
aisló el mecanismo con los parámetros ya expuestos: `route_board(refill=
false)` + `fill_zones()` por separado + `kicad-cli` directo sobre disco en
cada paso. Resultado: ninguna de las 3 hipótesis del arquitecto es
exactamente correcta. La real (llamada Hipótesis D en el reporte): bug de
orden de medición + persistencia. Hallazgo secundario: el loop de
`enforce_hole_clearance` que protege vías con keepouts nunca creó un keepout
nuevo en 3 corridas — el arreglo viene enteramente del `refill_zones()`
plano sobre un board recién recargado de disco. No se aplicó fix trivial
(el reordenamiento real toca ~30 líneas con dependencias entre pasos, fuera
del límite de <15-20 líneas).

## Bloque 3 — ¿Freerouting respeta el plano como exclusión? (✓ completado)

**No.** Test sintético (mismo patrón P4.0 de sesión 19, board construido con
`pcbnew` desde cero — no hay `open_project` programático, no se pudo usar el
board despertador para esto): 3 corridas (sin plano / con plano / con plano
+ keepouts de cobre explícitos). Con plano, Freerouting cruza el via+track
directo por el centro del polígono GND, `clearance_violations:0` según su
propio reporte. Con keepouts de cobre explícitos, el patrón de ruteo SÍ
cambia (vía desplazada, fuera del radio protegido) — confirma que Freerouting
respeta keepouts reales, sólo NO respeta el plano como exclusión para otros
nets. Descarta la Opción "inyectar sólo el plano" al DSN; una inyección de
keepout real sí sería viable (Opción Y del Bloque 4).

## Bloque 4 — Opciones de fix (✓ completado)

Tres opciones documentadas con alcance/costo/trade-offs/verificación en
`docs/investigacion/23-fd4-02.md`:

- **Opción X (recomendada primero):** reordenar la medición del DRC
  reportado en `route_board` a después del refill+enforce, y persistir con
  `save_board()`. Costo medio-bajo, arregla el 100% de lo observado.
- **Opción Y:** inyectar keepout real al DSN para nets ajenos vs zona GND.
  Costo alto, la más completa arquitectónicamente, pero no se justifica
  todavía dado que el post-procesamiento ya funciona 3/3.
- **Opción Z:** extender `enforce_hole_clearance` para que su loop de vías
  realmente cree keepouts (hoy no lo hace nunca). Refuerzo de robustez para
  el caso intermitente ("A veces" del docstring de kipy), a combinar con X.

**Recomendación:** Opción X en sesión 24, Opción Z como refuerzo si D5
revela intermitencia real, Opción Y descartada por ahora.

**Decisión del arquitecto (`AskUserQuestion`, cierre de sesión 23):**
confirmada Opción X primero, tal como recomendaba el agente. Z queda diferida
a si D5 revela intermitencia real; Y descartada por ahora.

## Fix trivial aplicado

Ninguno. Se evaluó explícitamente en Bloque 2 y se decidió documentar y parar
(el reordenamiento real no es un cambio de <15-20 líneas sin refactor).

## DoD verificado

`uv run pytest -m "not integration"` verde (0 fallos, resto skipped por
marcas de integración GUI no aplicables). `ruff check` limpio. `mypy src/`
limpio. Sin cambios de código fuente en esta sesión — sólo
`docs/investigacion/23-fd4-02.md` y este reporte.

## Estado del board de pruebas

`/tmp/gui-test-project/despertador_inteligente.kicad_pcb` quedó en un estado
limpio (0 `hole_clearance`, ruteo de la última corrida de Bloque 2) tras las
reproducciones de esta sesión — no es un fixture del repo, no requiere
acción. El estado final del D4 (238 tracks + 28 vías) se preservó como
evidencia forense en el scratchpad de la sesión antes de mutarlo
(`post-d4-final-state.kicad_pcb` + DRC asociado).

## Fuera de alcance (según el prompt)

`solder_mask_bridge` de ANT1, features nuevos, backlog P2/P3/P4,
optimización de Freerouting — no tocados.

## Próximos pasos

Sesión 24: implementar Opción X (+ decidir sobre Z) con test de regresión.
Sesión 25 (D5): re-validar con la misma placa despertador, cerrando el
gate de esta investigación.
