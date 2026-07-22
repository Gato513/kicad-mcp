# Sesión 17 — P2: route_board robusto (+ P2.0 fix bug + fixture ruteado)

**Tipo:** DEV sobre kicad-mcp, **nueva rama** `sesion/17-route-board-robusto`
desde `master` (tras merge de `sesion/16-get-tracks`).

**Origen:** Hoja de ruta v3 (post-Dogfooding 2, 7.5/10). P2 = eliminar la caja
negra de `route_board`. La corrida real acumuló 4 fricciones documentadas:
`route_ms` ausente (F-08, deuda de DOS corridas), denominador engañoso (F-09,
"24/64" incluía unconnected-* de 1 pad), reglas del board no viajan al DSN
(F-11, clearance 0.47 hardcodeado ≠ 0.5 del proyecto), nets bloqueadas
silenciosas (F-12, `/RESET` imposible en 4 pases sin un solo mensaje).

**Criterio de cierre (gate):** route_board del despertador reporta `route_ms`,
un denominador correcto, causa de la net que no ruteó, y NO viola
`copper_edge_clearance` sistemáticamente. Fixture `tests/fixtures/despertador-routed/`
existe y los tests e/f de la sesión 16 corren contra ese fixture (no contra
el proyecto vivo del usuario).

## Fronteras

F1–F5 vigentes. F3 (catálogo de errores): códigos nuevos permitidos siempre
que entren al catálogo con code + hint accionable. Todo cambio de contrato
de tool queda documentado en `docs/specs/tool-catalog.md`.

---

## Tarea P2.0 — Fix bug de `get_copper_by_kiid` (prerrequisito)

**Descubierto en 16b (docs/sesiones/16b-reporte.md).** El contrato asumido
—`get_items_by_id` devuelve `[]` en not-found— no coincide con la realidad
de kipy, que lanza `ApiError("none of the requested IDs were found or valid")`.
El catch-all de `_supervise` (`bridge/ipc.py:772-797`) mapea genéricamente a
`KICAD_CLI_FAILED` antes de que `get_copper_by_kiid` pueda devolver `None`,
y `delete_track` nunca ve el `None` que debería mapear a `TRACK_ID_STALE`.

**Fix (`src/kicad_mcp/bridge/ipc.py:1235` `get_copper_by_kiid`):**
Atrapar la `ApiError` puntual de kipy en el sitio (dentro del propio
`get_copper_by_kiid`, no en `_supervise`) por tipo o por mensaje ("none of
the requested IDs were found or valid") y devolver `None` — cumpliendo el
contrato ya documentado en el docstring. Auditar el resto de los consumidores
de `get_items_by_id` en el bridge por si tienen el mismo defecto latente.

**Verificar:** en `tests/test_pcb_session16_gui.py`,
`test_delete_track_id_stale_after_external_removal` — el `xfail(strict=True)`
que dejó la 16b debe pasar de `xfail` a `xpassed`. `strict=True` va a hacer
fallar el CI, forzando a **quitar el marker**. Quitalo y el test debe quedar
verde. Esa es la señal de que P2.0 está cerrado.

---

## Tarea P2.1 — Reglas del board viajan al DSN + plumbing compartido

**Origen: F-11 + D-V3.5.** Freerouting recibe hoy un DSN sin las reglas del
proyecto: usa `copper_edge_clearance` interno ~0.47mm (violó la regla 0.5 del
proyecto en 7 sitios y forzó al humano a bajar la regla a 0.35 en el
`.kicad_pro`). Los anchos por netclass (0.15 señal / 0.25 power) tampoco
viajan: el router pone 0.2mm uniforme.

**Fix:**

1. **Lector de reglas** — módulo nuevo (p.ej. `src/kicad_mcp/bridge/rules_reader.py`)
   que lee del `.kicad_pro`:
   - `min_copper_edge_clearance`
   - netclasses: nombre, `clearance`, `track_width`, `via_diameter`, `via_drill`
   - asignación net→netclass (si hay override)
   Es lectura pura de disco, no IPC. Cacheado por `mtime` del `.kicad_pro`.

2. **Inyección al DSN** — en el generador DSN existente, emitir:
   - `(rule (clearance <edge_clearance>) ...)` para el borde
   - `(class <nombre_netclass> (clearance ...) (width ...))` por netclass
   - Asignar cada net a su clase correcta

3. **Reutilización obligatoria en `add_track`:** la validación de colisión
   de `add_track` hoy usa un clearance piso fijo 0.2mm (desviación #3 de la
   sesión 16 — autorizada como fallback). **Ahora esa lectura de reglas
   existe** → `add_track` debe consumir el mismo `rules_reader` y usar el
   clearance real de la netclass del track que se está creando. No duplicar
   plumbing.

**Test E2E:** rutear el despertador con `min_copper_edge_clearance=0.5` (sin
tocar la regla como en el D2) → resultado con 0 violaciones sistemáticas de
`copper_edge_clearance`. Este es el criterio duro de P2.1.

---

## Tarea P2.2 — route_board deja de ser caja negra (D-V3.4)

**El core de la sesión.** Contrato nuevo del `route_board` result, todo
obligatorio en la respuesta:

```
{
  "route_ms": <int>,                    // TIEMPO REAL de router — deuda F-08 desde D1
  "nets": {
    "total": <int>,
    "ruteables": <int>,                 // multi-pin; excluye unconnected-* de 1 pad
    "ruteadas": <int>,                  // llegaron a 100% en este pase
    "parciales": [{"net": ..., "faltan": <n_conexiones>}, ...],
    "bloqueadas": [                     // 0% ruteo, con causa
      {"net": "/RESET",
       "causa": "sin camino disponible; bloqueada por /SDA en B.Cu entre (3.4,8.2) y (15.7,38.7)"}
    ]
  },
  "drc": {
    "err_preexistentes": <int>,         // corridos ANTES del route
    "err_post": <int>,                  // corridos DESPUÉS
    "err_introducidos": <int>,          // post - preexistentes (puede ser negativo)
    "por_tipo": {"copper_edge_clearance": N, ...}
  },
  "session_dsn": "<path>",              // para debug reproducible
  "session_ses": "<path>"
}
```

**Detalles del contrato:**

- **`route_ms`**: instrumentar el proceso Freerouting con `time.perf_counter()`
  alrededor del subprocess. Reportar aunque falle el ruteo.

- **Denominador `nets.ruteables`**: net multi-pin del board. Excluir explícitamente
  las `unconnected-*` de 1 pad que hoy inflan el denominador (F-09: "24/64" era
  engañoso porque 33 de esos 64 eran nets de 1 pad).

- **Causa de nets bloqueadas** — heurística mínima aceptable:
  1. Parsear el `.ses` de vuelta y ver qué nets tienen 0 wires generados.
  2. Para cada una, ejecutar A* corto en una grilla gruesa (paso ~0.5mm) sobre
     una imagen binaria del cobre existente (usa `get_tracks(bbox=<board>)`
     — sí, dogfood P1).
  3. Si A* no encuentra camino: identificar la net "más grande" que atraviesa
     el corredor natural entre los dos endpoints y reportarla como bloqueadora.
  Si la heurística no puede identificar bloqueador concreto, reportar
  `"causa": "sin camino aparente; revisar manualmente"` — mejor honesto que
  inventar.

- **DRC pre/post integrado**: correr `run_drc` antes y después dentro del
  propio `route_board`; el agente no debe llamarlo por separado.

**Errores nuevos al catálogo:**
- `ROUTE_NET_BLOCKED` (informativo, no aborta): parte del payload de nets
  bloqueadas, con `data.net` y `data.causa`.

---

## Tarea P2.5 — Fix DRC pos=[0,0] en violaciones de edge clearance

**F-11 (parte B).** El DRC reporta `copper_edge_clearance` con
`pos=[0,0]` (posición del rectángulo Edge.Cuts, no del track ofensor). Esto
hace las violaciones ilocalizables programáticamente.

**Fix (`src/kicad_mcp/bridge/rules.py` o donde vive el parser de DRC):**
Cuando el tipo es `copper_edge_clearance`, extraer la posición del ítem
ofensor (típicamente el segundo actor de la violación, no el Edge.Cuts).
El JSON de DRC de KiCad lista los `items` involucrados; usar la posición del
que NO es Edge.Cuts.

---

## Tarea Fixture — `tests/fixtures/despertador-routed/`

**Doble entregable de la sesión:** el ruteo real del despertador durante
P2.2 sirve además como fixture para los tests e/f (que en 16b pasaron contra
un board vacío y no ejercitaron colisión real).

**Pasos:**

1. Verificar estado del board en `/tmp/gui-test-project/`. El reporte de 16b
   dice que es una copia pre-dogfooding del 11/07 (0 tracks, sin outline,
   min_copper_edge_clearance=0.5). **Preguntar al humano ANTES de proceder:**
   ¿existe una copia del estado post-dogfooding (con ruteo, con outline)
   guardada en algún lado? Si sí, restaurarla como punto de partida. Si no,
   partir del estado pre-dogfooding y hacer el flujo mínimo: `draw_board_outline` +
   `route_board` (usando el P2.2 recién construido, dogfood real).

2. Cuando el board llegue a un estado utilizable como fixture (ruteo ≥90% de
   nets ruteables, DRC sin errores sistemáticos de clearance), **copiar** el
   `.kicad_pcb`, `.kicad_pro`, `.kicad_sch` (referencia, aunque los tests
   solo tocan pcb) a `tests/fixtures/despertador-routed/`.

3. Actualizar los tests e/f para que usen ese fixture: copiar a un tmpdir en
   el `setup` (para no ensuciarlo), abrir con `open_project`, correr.
   **Deben seguir siendo `integration_gui`** (necesitan KiCad vivo) pero ya
   NO dependen de `KICAD_MCP_PROJECT` del usuario — usan el fixture.

4. Documentar en `docs/pruebas-gui.md` cómo regenerar el fixture si en el
   futuro cambia el sch (después de la 20 lo va a hacer).

**Nota importante:** el sch del despertador tiene errores eléctricos
conocidos (SCL↔INT_SENS, NSS↔MOSI fusionadas — deuda del arquitecto para
la 20). El fixture NO es eléctricamente correcto y no debe presentarse como
tal. Documentar en un `README.md` dentro de la carpeta del fixture:
"Fixture con cobre denso para tests de colisión y regresión de route_board.
El esquema tiene defectos eléctricos conocidos (D2/F-04) — no usar como
referencia de diseño."

---

## Fuera de alcance (para una posible 17b, NO tocar en 17)

- **P2.3** (limpieza de tracks huérfanos en re-route incremental): pendiente
  hasta ver un caso real.
- **P2.4** (timeout adaptativo): nice-to-have.
- **Zonas / plano GND** (P4, sesión 19).
- **Recarga programática post-route** (P3, sesión 18) — sigue habiendo revert
  humano tras route_board.

## Tests requeridos

Unit + integration (offline con kicad-cli), con >90% de las nuevas líneas
cubiertas:

- `rules_reader`: parsea distintos formatos de `.kicad_pro`, cache por mtime,
  degradación graceful si faltan campos.
- Generador DSN: incluye `edge_clearance` y `class` por netclass.
- `add_track` collision: consume el clearance real de la netclass, no el piso
  0.2mm.
- Parser DRC: `copper_edge_clearance` reporta posición del track ofensor
  (no [0,0]).
- Contrato de resultado de `route_board`: shape completo, denominador excluye
  unconnected-*, `route_ms` presente incluso en fallo.

`integration_gui` (contra KiCad vivo, opcionalmente contra el fixture generado):
- E2E de rutear el despertador con regla 0.5 → 0 violaciones sistemáticas de
  edge clearance.
- Tests e/f de sesión 16 corren contra el fixture, ejercitando colisión real.

## Reporte final (`docs/sesiones/17-reporte.md`)

- Diff-resumen por tarea.
- Estado del bug P2.0 (test destildado, verde).
- **`route_board` sobre el despertador con la implementación nueva** — reportar
  literal el JSON de resultado. Comparar con los datos del D2 (F-08, F-09, F-11,
  F-12): ¿cuáles fricciones cierran?
- Fixture: path, tamaño, estado (DRC, % ruteo), commit hash del board.
- Suites: unit+golden, integration, integration_gui contra fixture.
- Bugs reales descubiertos al implementar: reportar, decisión (arreglar acá
  vs próxima sesión).

## Cierre

Cuando la 17 cierre, la hoja de ruta queda: 18 (P3 revert programático), 19
(P4 zonas), 20 (Dogfooding 3 con sch corregido). El Dogfooding 3 será el
primer test real completo de todo lo construido desde sesión 15.
