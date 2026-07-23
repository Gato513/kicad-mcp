# Sesión 21 — Fix P0 (F-D3-01, F-D3-03) + P1 (`get_footprint_neighbors`)

**Rama:** `sesion/21-p0-p1-hardening` (desde `master`, post-merge Dogfooding 3)
· **Fecha:** 2026-07-23.

## Resumen

Los 2 bugs P0 del Dogfooding 3 (shorts físicos reales invisibles en el DRC)
y la tool P1 identificada como necesaria (`get_footprint_neighbors`) se
cierran en esta sesión. F-D3-01 resultó más difícil de lo previsto: la
investigación mandatoria no logró aislar la causa raíz exacta pese a un
esfuerzo sustancial, y el fix final es un workaround post-fill decidido
explícitamente por el humano (`AskUserQuestion`), no una corrección del
pipeline interno. F-D3-03 y 21.3 salieron según lo planeado.

Filosofía respetada: hardening conservador, cero refactor oportunista, cero
mezcla con P3/P4 (F-D3-05 no tocado), exclusivamente estos 3 items.

---

## 21.1 — F-D3-01: fill de zona vs hole clearance PTH/NPTH

### Investigación (Fase A, obligatoria)

Reporte completo: `docs/investigacion/21-fill-zones-holes.md`. Hallazgos
clave:

1. **El fill es 100% delegado al motor de KiCad** — `add_zone`/`fill_zones`/
   el refill interno de `route_board` llaman todos a
   `raw_board.refill_zones()` de kipy, sin ninguna matemática de clearance
   del lado de kicad-mcp. No hay `hole_clearance` leído en ningún lado de
   `src/` (confirmado por grep, no sólo inferencia).
2. **Experimento sintético (pcbnew, fuera de kicad-mcp):** el motor de fill
   de KiCad, en abstracto, computa hole clearance CORRECTAMENTE y es
   indiferente al orden fresh-fill vs refill-tras-agregar-pads (clearance
   idéntica bit-a-bit en ambos casos, PTH: 0.9005mm, NPTH: 0.2505mm vs
   0.25mm requerido).
3. **3 reproducciones vía el pipeline real de kicad-mcp** (sobre una copia
   de trabajo del fixture `despertador-routed`, restaurada limpia antes y
   después de cada prueba): vía con net ajeno inyectada directo en el
   `.kicad_pcb` (mismo mecanismo que usa `route_board`), pad PTH con net
   real no relacionado, y NPTH real (sin net, igual que los 3 agujeros de
   J1) — **ninguna reprodujo el patrón "0.0000mm" del D3** en ubicaciones
   verificadas limpias (un primer intento contaminado por proximidad real a
   un pad de BT1 mostró un déficit de sólo 0.03mm, descartado como ruido del
   test, no evidencia del bug).
4. **Conclusión:** resultado negativo bien establecido, no prueba de
   ausencia de bug — el D3 es un reporte de primera mano con evidencia
   concreta (6 violaciones DRC reales, luego 53 tras el refill interno de
   `route_board`, resueltas de forma reproducible por el agente con
   `delete_zone`+`add_zone` fresco). La diferencia más probable con mis
   repros: la zona original se rellenó sobre un board con **cero
   footprints** (Fase 1 del D3, antes de colocar componentes) — condición no
   probada — y/o el round-trip real de Freerouting (sólo repliqué su
   mecanismo de reemplazo de archivo, no el ruteo real).

### Gate humano

Dado el resultado inconcluso en un bug P0 de seguridad física, se activó el
gate mandatorio: `AskUserQuestion` presentó 3 opciones (seguir investigando
las condiciones exactas del D3, workaround post-fill defensivo, o diferir
21.1). **Decisión: workaround post-fill defensivo.**

### Fix implementado

`IpcBridge.enforce_hole_clearance(board, pcb_path)` (`bridge/ipc.py`) — se
llama inmediatamente después de TODO `refill_zones()` (en `add_zone`,
`fill_zones`, y el refill interno de `route_board`):

1. Borra sus propios keepouts de la pasada anterior (tag
   `__kicadmcp_hc__`) — idempotente, no acumula duplicados entre llamadas
   repetidas.
2. Lee `min_hole_clearance` del `.kicad_pro` (nuevo campo en
   `bridge/rules_reader.py::ProjectRules`, mismo patrón dual-path que
   `min_copper_edge_clearance` — kipy no expone esta regla vía IPC).
3. Para cada zona de cobre, protege con un keepout circular
   (`keepout_copper=True`, `keepout_vias/tracks/footprints=False`) todo pad
   con drill (PTH/NPTH) o vía de net distinto (o sin net — NPTH siempre
   ajeno), con radio = radio del agujero + `min_hole_clearance` + margen de
   0.02mm.
4. Refillea de nuevo si se creó algún keepout.

Lectura nueva compartida con 21.3: `IpcBridge.list_pad_holes` /
`bridge.ipc.PadHole` — el modelo de pad NUNCA leía el drill antes de esta
sesión (sólo el de vías); ahora lo hace en una pasada `get_footprints()` +
`definition.pads`, filtrando pads sin drill real (SMD/edge-connector).

### Tests

- **Unit** (`tests/test_pcb_hole_clearance.py`, 6 tests): protección de PTH
  ajeno + NPTH sin net, exclusión de pad mismo-net, protección de vía ajena
  (usa `drill_diameter`, no el ancho de cobre), idempotencia (no duplica
  keepouts en 2 llamadas seguidas), no-op sin zonas de cobre,
  `list_pad_holes` reporta ref/net/kind/diámetro correctos.
- **integration_gui** (`tests/test_pcb_session21_hole_clearance_gui.py`):
  repro exacta del D3 (`add_zone(bbox=...)` simple sin muescas sobre
  ANT1+J1 reales) → 0 errores; `fill_zones()` (refill, no recrear) también
  → 0 errores. **Pendiente de correr en vivo — ver sección Verificación.**

### Contrato

Sin cambios de superficie pública (`add_zone`/`fill_zones`/`route_board`
mantienen su forma de retorno). Efecto secundario documentado en
`tool-catalog.md`: `get_zones` puede mostrar keepouts nuevos
`__kicadmcp_hc__pad_*`/`__kicadmcp_hc__via_*`, auto-generados.

---

## 21.2 — F-D3-03: `route_board.drc.err_introducidos` por identidad

### Fix

`bridge.rules.diff_violations(pre, post)` — nueva función, junto a
`filter_by_min_severity`. Identidad de violación =
`(rule, pos_redondeada_0.1mm, items_ordenados_por_desc)`, comparada como
multiset (`collections.Counter`, no `set` — preserva duplicados genuinos).
`err_introducidos` = violaciones nuevas por identidad; `err_resueltos`
(nuevo) = violaciones pre-route que ya no aparecen; `por_tipo_introducidos`
(nuevo) = desglose de las introducidas por `rule`. Los 3 campos nuevos
coexisten con `err_preexistentes`/`err_post`/`por_tipo` (sin renombrar,
F3). `Violation`/`Item` ya eran `@dataclass(frozen=True)` — hashables sin
cambios.

### Tests

- **Unit del helper aislado** (`tests/test_rules.py`, 5 tests): escenario
  exacto del D3 (3 tipo A pre + 3 tipo B post, mismo total, composición
  100% distinta → `introducidas=3, resueltas=3`, no 0), violaciones
  idénticas no cuentan, tolerancia de posición 0.1mm, sólo `error` cuenta,
  multiset preserva duplicados.
- **Unit route_board** (`tests/test_route_board.py`,
  `test_route_board_err_introducidos_by_identity_not_totals`): mismo
  escenario a través del contrato JSON completo de la tool — con la lógica
  vieja `err_introducidos` daría 0 (falso), con la nueva da 3 y
  `err_resueltos=3`. Las 2 aserciones preexistentes que codificaban la
  resta de totales se actualizaron para incluir los campos nuevos (una de
  ellas, `err_post=2/err_preexistentes=0`, ya daba el mismo resultado bajo
  ambas semánticas — no requirió cambio de valores, sólo de forma).
- **integration_gui** (`tests/test_pcb_session21_route_board_drc_gui.py`):
  valida el contrato real end-to-end contra kicad-cli real (no mockeado) —
  consistencia entre `route_board.drc.err_introducidos`/`err_resueltos` y
  un `run_drc()` independiente pre/post vía `diff_violations` directo.
  Forzar el escenario EXACTO de composición-distinta-mismo-total contra un
  round-trip real de Freerouting no es práctico (no determinístico en el
  detalle de qué traza dónde) — ya cubierto de forma determinística por el
  test unit. **Pendiente de correr en vivo.**

### Contrato

```json
"drc": {
  "err_preexistentes": <int>, "err_post": <int>,
  "err_introducidos": <int>,        // SEMÁNTICA CAMBIADA: identidad, no resta
  "err_resueltos": <int>,           // NUEVO
  "por_tipo": {...},
  "por_tipo_introducidos": {...}    // NUEVO
}
```

Documentado en `tool-catalog.md` con el cambio de semántica explícito.

---

## 21.3 — P1: `get_footprint_neighbors`

### Diseño

Read-only, reutiliza `get_component_detail` (bbox/pads del target y de cada
vecino candidato — iteración O(N) de footprints, aceptable para el tamaño
de board de este MVP), `list_all_copper` (tracks/vías, mismo pass que
`get_tracks`), `list_pad_holes` (nuevo, compartido con 21.1) y
`board_outline` (bbox de Edge.Cuts). Distancia = mínimo entre el bbox del
footprint target y el ítem vecino (punto-a-AABB para pads/holes/vías;
aproximación por extremos de segmento para tracks/arcos — mismo nivel de
rigor ya aceptado en otras partes del catálogo). Presupuesto de tokens
igual a `get_tracks` (D4, 800 default) sobre el JSON serializado.
`live_stale` como banner (clave `aviso`), no guard — es lectura pura.

Nuevo helper de bridge compartido: `PadHole`/`list_pad_holes` (ver 21.1).

### Tests

- **Unit** (`tests/test_pcb_session21_neighbors.py`, 6 tests): pad vecino
  dentro/fuera de radio, holes propios (NPTH) + ajenos (PTH) mezclados,
  borde más cercano con distancia correcta, `edge=null` si está más lejos
  que el radio, `COMPONENT_NOT_FOUND` con ref inexistente,
  `CONTEXT_BUDGET_IMPOSSIBLE` con radio grande + muchos vecinos + budget
  chico.
- **integration_gui** (`tests/test_pcb_session21_neighbors_gui.py`):
  `get_footprint_neighbors("J1", radius_mm=5.0)` sobre el fixture real →
  3 agujeros NPTH propios + borde derecho ~0.5mm; un radio de prueba
  (0.01mm) trae menos o igual holes que uno de 5mm (el filtro de radio
  funciona de verdad). **Pendiente de correr en vivo.**

### Contrato

Nueva tool, sin tocar superficie existente. Ver `tool-catalog.md` para el
JSON completo. Errores reusados (`COMPONENT_NOT_FOUND`, `INVALID_PARAMS`,
`CONTEXT_BUDGET_IMPOSSIBLE`) — ninguno nuevo, F3 intacta.

---

## Definition of Done

- [x] `uv run pytest -m "not integration"` verde (todos los tests unit +
      golden, incluidos los 17 nuevos de sesión 21).
- [x] `uv run ruff check`/`ruff format` limpio.
- [x] `uv run mypy src/` limpio.
- [x] `tool-catalog.md` actualizado en el mismo commit (route_board.drc
      extendido, `get_footprint_neighbors` nueva entrada, efecto
      secundario de `enforce_hole_clearance` en `get_zones` documentado).
- [x] Golden (`tests/golden/**`) y specs (`docs/specs/**` salvo el
      catálogo, excepción de F1) intactos.
- [x] **Verificación en vivo contra KiCad 10.0.4 real** — servidor
      reiniciado, los 3 items verificados con éxito (ver abajo).

## Verificación en vivo

Servidor kicad-mcp reiniciado (`/mcp` reconectado) para cargar el código de
la sesión. Los 5 tests `integration_gui`/`integration_gui_slow` de sesión
21 corridos de verdad contra KiCad 10.0.4 real (fixture `despertador-routed`
restaurado antes/después de cada mutación) — **los 5 pasan**.

### 21.1 — hole clearance

- `add_zone(net="GND", layer="B.Cu", bbox=<board completo>, fill=true)`
  **sin muescas manuales** (repro exacta del patrón F-01 del D3) sobre
  ANT1(PTH, drill 2.0mm)+J1(3× NPTH, drill 0.99mm) reales → **0 errores DRC**
  (antes del fix: 6 en el D3 original). `get_zones(kind="keepout")` mostró
  **4 keepouts auto-generados** (`__kicadmcp_hc__...`): área 4.94mm² (ANT1,
  radio≈1.25mm ≈ 1.0mm drill/2 + 0.25mm hole_clearance + margen) y 3× área
  1.79mm² (J1, radio≈0.755mm ≈ 0.4955mm drill/2 + 0.25 + margen) —
  coincide exactamente con lo esperado por diseño.
- `fill_zones()` (refill explícito, sin recrear) → también 0 errores,
  keepouts recreados idempotentemente (4, no 8, tras una segunda pasada).
- **`route_board` real** (Freerouting 2.1.0, 178.7s, 10/10 nets, 8 tracks
  nuevos): el refill interno (`zones.refilladas:1`) corrió
  `enforce_hole_clearance` automáticamente — DRC post-route independiente:
  **0 errores**, keepouts presentes. Este es el mecanismo EXACTO de F-03
  (refill interno de `route_board` disparando el bug) — verificado cerrado.
- Tests automatizados: `test_pcb_session21_hole_clearance_gui.py` — **2/2
  passed** (35.52s).

### 21.2 — `route_board.drc` por identidad

- `route_board(timeout_s=180)` real sobre el fixture: contrato completo
  `{err_preexistentes:0, err_post:0, err_introducidos:0, err_resueltos:0,
  por_tipo:{}, por_tipo_introducidos:{}}` — los 3 campos nuevos presentes y
  tipados correctamente en un round-trip real de Freerouting (no mockeado).
- Test automatizado `test_pcb_session21_route_board_drc_gui.py` — **1/1
  passed** (254.08s): confirma que `err_introducidos`/`err_resueltos`/
  `por_tipo_introducidos` de `route_board` coinciden EXACTAMENTE con
  `diff_violations` aplicado a un `run_drc()` independiente pre/post (el
  ground truth) — el contrato no miente. El escenario exacto de
  "mismo total, composición distinta" del D3 no se forzó de forma
  determinística contra el round-trip real (no práctico, ver el docstring
  del test) — queda cubierto por el test unit
  (`test_route_board_err_introducidos_by_identity_not_totals`).
- Este mismo `route_board` real ejercitó AMBOS fixes simultáneamente (21.1
  vía su refill interno + 21.2 vía su contrato DRC) sin conflicto: `err_post
  = 0` confirma que el workaround de 21.1 no introdujo ninguna violación
  propia.

### 21.3 — `get_footprint_neighbors`

- `get_footprint_neighbors("J1", radius_mm=5.0, max_tokens=3000)` real:
  **3 agujeros NPTH** (`belongs_to:"J1"`, `diameter_mm:0.991`, `dist_mm:0`
  — propios), **borde derecho a 0.5mm exactos** (`closest_edge:"right"`) —
  coincide EXACTO con lo que el plan pedía verificar. 23 vecinos de cobre
  reales (tracks+vías, varios nets) dentro de 5mm; 0 pads de otros
  footprints (BT1/U4 quedan a >5mm del bbox de J1 en este layout —
  comportamiento correcto, no un bug).
- Presupuesto de tokens: el default (800) NO alcanza para J1 en este
  cluster denso (≈2244 tokens estimados) — `CONTEXT_BUDGET_IMPOSSIBLE` con
  hint correcto, confirmado en vivo antes de subir `max_tokens`.
- Tests automatizados: `test_pcb_session21_neighbors_gui.py` — **2/2
  passed** (14.65s, tras corregir `max_tokens` en el test — el default no
  alcanzaba, bug del test no de la tool).

## Estado de D-D3.2 ("correr `run_drc()` manual tras cada `route_board`")

**Revocada, con evidencia en vivo.** La verificación confirmó ambas
condiciones: (1) `route_board.drc.err_introducidos`/`err_resueltos`
coinciden exactamente con un `run_drc()` independiente (21.2, test
automatizado + cross-check manual), y (2) el refill interno de
`route_board` no deja hole clearance en 0mm — el mecanismo EXACTO que
disparó F-03 en el D3 quedó cerrado (21.1, verificado con un `route_board`
real de 178.7s). La regla operacional "no confiar en el JSON, correr
`run_drc()` propio siempre" ya no es necesaria: el contrato vuelve a
cumplir su propósito original (D-17.1, evitar re-verificación).

**Caveat honesto:** la causa raíz de F-D3-01 sigue sin aislarse (el
workaround es defensivo, no una corrección del mecanismo interno de kipy —
ver `docs/investigacion/21-fill-zones-holes.md`). Si el Dogfooding 4
(sesión 22) encuentra un caso donde `enforce_hole_clearance` no alcanza a
proteger algo (p. ej. un patrón geométrico no contemplado), eso sería
evidencia nueva sobre el mecanismo real — no una regresión del fix, que
está probado correcto para los escenarios PTH/NPTH/vía-de-otro-net
verificados acá.
