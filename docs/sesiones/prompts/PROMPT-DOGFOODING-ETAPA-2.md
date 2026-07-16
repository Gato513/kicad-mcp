# Dogfooding Etapa 2 — Una placa real, de la nada a los gerbers

**QUÉ ES:** sesión de USO, no de desarrollo (mismas reglas que la Etapa
1: prohibido editar el repo de kicad-mcp; toda falla se REGISTRA en el
log de fricciones, no se arregla). Es la prueba de fuego del objetivo 1
de la hoja de ruta: diseñar una placa real completa con las tools,
apuntando a superar la nota 5/10 de la Etapa 1 — **objetivo ≥8/10**.

**ENTREGABLES:**
1. `/tmp/dogfood2-fricciones.md` — mismo formato F-NN de la Etapa 1
   (qué pasó / qué esperaba / workaround / costo / severidad), escrito
   EN EL MOMENTO. Sección final de Aciertos.
2. La placa: sch completo con ERC limpio → PCB colocado, contorneado,
   ruteado al 100% con DRC sin errores → render final → gerbers (G3).
3. Resumen final con la nota /10 y la comparación contra la Etapa 1.

---

## El diseño a construir

El humano te va a dar (en su primer mensaje o cuando se lo pidas) un
**brief de diseño**: lista de componentes con valores y footprints, y la
conectividad (qué pin va con qué pin / qué nets existen). Es una placa
real suya de ~10-30 componentes. Si algo del brief es ambiguo,
preguntale ANTES de construir — una pregunta barata ahora vale más que
un rework después.

## Puntos de contacto humano (los ÚNICOS — todo lo demás es tuyo)

El flujo de 9 pasos tiene exactamente estos toques humanos (D-R2 +
D-12.4 + D-14.1). Pedilos explícitamente cuando toquen, con una
instrucción de una línea, y esperá su confirmación:

- **H1 (ya hecho al arrancar):** proyecto nuevo creado en
  `KICAD_MCP_PROJECT` + `paleta.kicad_sch` con los símbolos del brief.
- **H2 (tras tu sch con ERC limpio):** F8 en la GUI — *"Corré
  Tools → Update PCB from Schematic (F8) y avisame"*.
- **H3 (tras route_board):** recarga — *"File → Revert en el PCB Editor
  y avisame"* → recién ahí `get_world_context(kind='pcb',
  confirm_reloaded=true)` y seguís.
- **H4 (opcional):** validación visual de renders intermedios si querés
  una segunda opinión de colocación.

## El flujo (tu plan de vuelo)

1. **Sch desde la paleta:** `add_symbol(source="paleta.kicad_sch", …)`
   por componente del brief → `set_value` → `set_footprint` →
   `connect_pins` (nombres de net significativos — vos los elegís) →
   `run_erc` iterativo hasta limpio. Verificá tu modelo con
   `get_world_context(kind="sch")` (con budget) cuando lo necesites.
2. **H2 (F8 humano).**
3. **PCB:** `get_world_context(kind="pcb", focus/budget)` →
   `draw_board_outline` (¡antes de rutear! route_board sin Edge.Cuts
   falla) → plan de colocación (breve, en el chat) → `move_footprint`
   por componente con deltas para verificar → `save_board` → render de
   control.
4. **Ruteo:** `route_board` (timeout default; reportá el `route_ms` de
   TU placa — es el dato de densidad que la sesión 14 pidió medir).
5. **H3 (recarga humana) + confirm_reloaded.**
6. **Cierre:** `run_drc` (resumen; si hay errores: diagnóstico con el
   detalle paginado, retoque con delete_track/add_track si es puntual,
   o re-route) → render final → `export_manufacturing` (G3) →
   `export_bom` si aplica.

## Disciplina de contexto (igual que la Etapa 1)

Delta > mundo con focus > mundo completo. Renders con criterio (~11 s
c/u). Reportá al final: llamadas por tool, tokens totales estimados,
tiempo de sesión, y cuántos turnos consumió cada fase (sch / colocación
/ ruteo / cierre).

## Resumen final (última sección del log)

1. ¿Placa completa? (ERC ✓, colocado %, ruteado %, DRC, gerbers ✓/✗)
2. Tabla comparativa Etapa 1 vs Etapa 2: fricciones bloqueantes,
   tokens, saves humanos, resultado de la placa.
3. Estado de las fricciones F-01..F-11 de la Etapa 1 desde tu
   experiencia de HOY: ¿las cerradas se sienten cerradas?
4. Las 3 fricciones nuevas más caras (si las hay) con propuesta.
5. `route_ms` y calidad del ruteo en tu placa (dato de densidad).
6. **Nota /10 con justificación** — la Etapa 1 dio 5/10; el objetivo de
   todo lo construido desde entonces es ≥8.
7. ¿Qué falta para que uses esto todas las semanas en tus proyectos?
   (la pregunta que define la hoja de ruta v3.)
