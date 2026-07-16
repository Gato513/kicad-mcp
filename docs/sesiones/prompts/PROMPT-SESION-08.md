# Sesión 08 — Mutaciones rápidas (≤4 s) + `add_symbol`

**Rama:** `sesion-08` (desde `master`). Un commit por tarea. No pushear.
**Entorno vivo:** KiCad 10.0.4 con el PCB Editor cargado
(`/tmp/gui-test-project/video.kicad_pcb`), API server habilitado, env
vars exportadas. Podés correr `integration_gui`. Si KiCad deja de
responder, pedile al humano la acción concreta y seguí con lo unit.

Leé `CLAUDE.md`, `docs/sesiones/07-reporte.md` y
`docs/componentes-pcb.md` (inventario de las 202 refs del board de
prueba — usalo para elegir refs variadas en tests: `U1` grande, `R5`
chica, `P1` conector) antes de tocar nada.

---

## Contexto

La telemetría de la sesión 07 midió **~13.6 s por mutación vía tool**:
4 iteraciones O(board) de ~3.4 s cada una (validar refs, validar bbox,
lookup del move, snapshot post-mutación). Es el problema #1 del
proyecto: un agente encadenando mutaciones es inusable. Esta sesión lo
baja a ≤4 s y, con el pipeline rápido, implementa `add_symbol` sobre el
diseño ya cerrado.

**Corrección del arquitecto a la Propuesta A del reporte 07:** tal como
se propuso ("colapsar a una iteración") es imposible — el snapshot
post-mutación debe leerse DESPUÉS de mutar y no puede compartir la
pasada previa. La consolidación del pre-work da 2 iteraciones (~6.8 s).
Para llegar a ~3.5 s hay que derivar el post-estado localmente
(decisión D-08.2 abajo).

---

## Decisiones vinculantes del arquitecto

- **D-08.1 (consolidación del pre-work):** el bridge gana UNA operación
  compuesta de lectura (nombre sugerido: `read_board_context(board)`)
  que en una sola pasada de `get_footprints()` devuelve todo lo que el
  pre-work de una mutación necesita: la lista de refs, el bbox, y los
  `FootprintData` completos (el snapshot pre-mutación). Las tools de
  mutación validan y encuentran el target sobre ESE resultado; el
  `move_footprint` del bridge recibe el footprint/identificador ya
  resuelto y NO vuelve a iterar. La operación compuesta es de lectura
  idempotente → entra en la whitelist de retry (D-07.1). Devuelve
  primitivos/dataclasses (regla 5), jamás tipos de kipy.
- **D-08.2 (post-estado derivado + verificación puntual):** tras la
  mutación, el post-snapshot NO se re-lee con una pasada completa. Se
  DERIVA: post-estado = pre-estado (de D-08.1) con la mutación aplicada
  localmente (la conocemos: fuimos nosotros). Verificación de efecto
  (D-06.3 sigue vigente): re-leer SOLO el ítem mutado vía
  `board.get_items_by_id([kiid])` (kipy `board.py:384-399`, filtro del
  lado de KiCad, O(1) de red) y comparar con lo derivado (tolerancia
  ±1 nm, redondeo banker's conocido). Si coincide → registrar el
  snapshot derivado. Si diverge → log warning con ambas posiciones +
  fallback a re-lectura completa (una pasada) + registrar lo re-leído.
  El fallback garantiza corrección aunque KiCad clampee o redondee
  distinto de lo previsto.
  - Prerequisito dentro de la tarea: capturar el KIID en
    `FootprintData` durante la pasada de D-08.1 (campo nuevo aditivo).
  - Mini-verificación empírica ANTES de implementar el camino
    derivado: 3 moves contra KiCad real comparando posición pedida vs
    posición leída por KIID. Si KiCad redondea > 1 nm sistemáticamente,
    reportá y ajustá la derivación a la regla observada.
- **D-08.3 (retry de lecturas pre-mutación):** las lecturas previas a
  una mutación (la operación compuesta de D-08.1, el net-lookup de
  `add_track`) SÍ pueden retry ante busy — son reads idempotentes. La
  ESCRITURA (`update_items`/`create_items`) jamás se reintenta (D-07.1
  intacta). Estructuralmente: el retry solo puede envolver código que
  corre ANTES de la primera escritura; que la separación sea por
  construcción, como en la 07.
- **D-08.4 (presupuesto de latencia):** objetivo ≤4 s por
  `move_footprint` vía tool contra el board de 202 refs, medido con la
  misma metodología del reporte 07 (5 mutaciones consecutivas, tabla
  con `lookup_ms` → renombrá el campo si la estructura cambió, p. ej.
  `extra.read_ms` / `extra.verify_ms`). Si no llegás a 4 s, reportá el
  desglose y hasta dónde llegaste — no sacrifiques corrección por el
  número.
- **D-08.5 (`add_symbol`: las decisiones de la sesión 06 T5 SIGUEN
  vigentes — no se re-litigan):**
  1. Librería: SOLO clonado desde un símbolo/template ya presente en el
     archivo (`lib_id` existente). Pick desde librerías externas: fuera
     de scope permanente hasta nueva decisión.
  2. Cableado: fuera de scope (v0.5). `add_symbol` coloca, no conecta.
  3. Superficie: `add_symbol` toca SOLO el `.kicad_sch`. No genera
     footprint ni toca el `.kicad_pcb` (eso es re-anotación/sync de
     KiCad, fuera de scope).
  4. Snapshot Store: snapshot de DISCO post-write con mtimes frescos
     (D-06.2), nuevo snap_id en el confirm (≤50 tokens). El patrón
     vivo (mtimes=None) es exclusivo de mutaciones IPC.
- **D-08.6 (hint del health cerrado):** acortar a "Abrí KiCad y
  habilitá el API server (Preferences → Plugins)." para volver bajo el
  techo de ~100 tokens.

---

## Fase 0 — Verificación

1. `verificar_entorno.py`; env vars presentes; smoke
   `integration_gui -k version` → PASS.
2. Suite de arranque: 101 unit esperados.
3. Línea base de latencia: 2 mutaciones vía tool contra KiCad real con
   la telemetría actual (~13.6 s esperados). Guardá los números: el
   reporte compara antes/después.

## Tarea 1 — Operación compuesta de lectura (D-08.1)

- `read_board_context` en el bridge (una pasada, retry-elegible,
  primitivos afuera, KIID capturado en `FootprintData`).
- Refactor de `tools/pcb.move_footprint` y `add_track` para consumirla:
  validaciones + lookup sobre el resultado, cero iteraciones extra.
- `build_state_from_board` puede construirse desde el resultado de la
  operación compuesta (evitá que quede una segunda pasada escondida).
- Tests unit: los fakes existentes se adaptan; test específico de que
  una mutación vía tool provoca EXACTAMENTE una lectura O(board) en el
  fake pre-mutación (contador de invocaciones, como el patrón de la 07).

## Tarea 2 — Post-estado derivado + verificación por KIID (D-08.2)

- Mini-verificación empírica primero (3 moves, pedido vs leído por
  KIID) — reportar la tabla.
- Implementar derivación + verificación puntual + fallback.
- Tests unit: derivación correcta (el snapshot registrado refleja la
  mutación); divergencia simulada en el fake → warning + fallback a
  re-lectura completa (contador: 2ª pasada solo en fallback);
  verificación puntual usa get_items_by_id (el fake lo registra).
- El test integration_gui de cruce (T4.2 de la 07) debe seguir verde
  sin cambios de semántica: el delta pcb/pcb post-mutación sale igual.

## Tarea 3 — Medición final (D-08.4)

- 5 mutaciones consecutivas vía tool contra KiCad real. Tabla
  comparativa sesión 07 vs 08 con desglose. Objetivo ≤4 s.
- De paso: los scripts de medición que la 07 dejó en `scratchpad/`
  (`measure_health.py`, `measure_mutation_latency.py`) — si los
  reusás, actualizalos; si quedaron obsoletos, listalos en el reporte
  como candidatos a limpieza (no borres sin avisar).

## Tarea 4 — `add_symbol` (D-08.5)

- `tools/sch.add_symbol(sheet, lib_id, ref, x_mm, y_mm, base_snap)`
  según el diseño de la sesión 06 T5 + las 4 decisiones de D-08.5:
  validaciones pre-mutación (ref sin colisión en NINGUNA hoja, lib_id
  presente en el archivo, posición dentro del área de la hoja), G1
  backup, write con kicad-skip, snapshot de disco post-write, confirm
  ≤50 tokens con el snap_id nuevo, audit JSONL.
- Verificación de efecto (D-06.3): re-leer el archivo escrito y
  confirmar símbolo presente, conteo +1, posición correcta.
- Hazard del editor abierto: documentado en catálogo + ADR (el usuario
  con el sch abierto en KiCad verá el aviso de recarga; MVP documenta,
  no resuelve).
- Catálogo: entrada nueva completa (params, errores posibles, ejemplo).
- Tests: unit contra copias de `001_basico` y `004_real` en `tmp_path`
  (regla 7), incluyendo: colisión de ref → error tipado, lib_id
  inexistente → error tipado, éxito con verificación de efecto.
- El texto que entra al archivo proviene de params del LLM → aplica la
  regla 6 (sanitización) a `ref` y cualquier string que se escriba.

## Tarea 5 — Ajustes menores

- Hint del health cerrado (D-08.6) + re-medir tokens_est (esperado
  ≤~100).
- Si `docs/pruebas-gui.md` o el catálogo quedaron desactualizados por
  T1/T2 (telemetría renombrada, operación compuesta), actualizalos.

## Tarea 6 (OPCIONAL) — Eval A: TOON vs alternativas

Solo si T1-T5 con DoD. En `scratchpad/eval-a/`: comparar tokens_est de
`get_world_context` y `get_context_delta` en TOON vs CSV compacto vs
JSON compacto sobre los fixtures 001/002/003 y el board real. Sin
tocar producción: es un estudio. Entregable:
`scratchpad/eval-a/informe.md` con tablas y tu recomendación (¿TOON se
sostiene? ¿dónde pierde?). El arquitecto decide en la 09 si algo cambia.

---

## Fuera de scope

- Propuesta B completa (cache ref→KIID persistente): D-08.2 usa
  get_items_by_id solo para la verificación puntual; el cache con
  invalidación queda para cuando se mida que hace falta.
- Exponer `has_open_pcb` como MCP tool separada (YAGNI; health ya lo
  surfacea).
- Cableado de pines, pick de librerías externas, sync sch↔pcb (D-08.5).
- Códigos nuevos (F3), dependencias nuevas (F5), goldens (F1).

## Definition of Done

```
uv run pytest -m "not integration and not integration_gui"  → verde
uv run pytest -m integration                                → verde (< 5:00)
uv run pytest -m integration_gui                            → verde (incluye T4.2 de la 07 sin regresión)
uv run mypy src/                                            → Success strict
uv run ruff check + format --check                          → clean
```

## Reporte final obligatorio

1. Tabla antes/después de latencia de mutaciones (línea base Fase 0 vs
   T3). ¿Se llegó a ≤4 s? Desglose.
2. Resultado de la mini-verificación empírica de D-08.2 (¿KiCad
   redondea?, tabla de 3 moves) y cuántas veces disparó el fallback en
   toda la sesión.
3. Output del test contador: una mutación = exactamente 1 pasada
   O(board) pre + 0 pasadas post (salvo fallback).
4. Para `add_symbol`: confirm literal con tokens_est, salida de la
   verificación de efecto, y el archivo de prueba generado que el
   humano pueda abrir en KiCad GUI para validar visualmente (dejalo en
   una ruta de /tmp y decila).
5. tokens_est del health cerrado post-D-08.6.
6. Promedios: global ≤400, confirms ≤50.
7. Si corrió la Eval A: resumen de una pantalla + link al informe.
8. Dudas abiertas y candidatos argumentados para la sesión 09.
