# Reporte de sesión 12 — Flujo sch mínimo + Edge.Cuts + DRC presupuestado

**Rama:** `sesion-12` · **Fecha:** 2026-07-12 · **Entorno:** KiCad 10.0.4 con
PCB Editor abierto sobre `/tmp/gui-test-project/` (proyecto `video`, multi-hoja),
`verificar_entorno.py` verde (13 OK · 0 WARN · 0 FAIL, modo integration).

**Nota de herencia (F1/proceso):** el prompt pedía leer
`docs/sesiones/11-reporte.md §6`, pero **ese archivo no existe** — los reportes
de sesión llegan hasta el 09 (los commits de las sesiones 10/11 están en git,
sin reporte redactado). No hubo notas heredadas que aplicar; me apoyé en
`HOJA-DE-RUTA-V2.1.md`, el catálogo y el código de `add_symbol`.

---

## 1. Veredictos de spikes (T1) — con evidencia

Todos en `scratchpad/spike_*.py` + `scratchpad/spike_verdicts.md`.

### D-12.2 `connect_pins` — **VERDE** ✓
- **(a) posición absoluta del pin:** kicad-skip **la expone directamente** —
  `SymbolPin.location` devuelve `AtValue(x, y, rot)` ya resuelta
  (origen+offset+rotación). No hay que calcular geometría. Ej.: R1@(152.4,50.8),
  pin 2 → `location (152.4, 55.88, 90)`.
- **(b) label local anclado:** `sch.label.new()` crea un label local desde
  plantilla (aun sin labels locales previos); `label.value = net_name`,
  `label.at.value = [x, y, 0]`, `sch.write()`.
- **(c) verificación por netlist** (`kicad-cli sch export netlist`, sobre
  001_basico con los global labels removidos para dejar pines flotantes):

  ```xml
  <net code="1" name="/SPIKE_NET" class="Default">
    <node ref="R1" pin="2" pintype="passive"/>
    <node ref="R2" pin="2" pintype="passive"/>
  </net>
  ```

  Dos pines → **misma net con el nombre pedido** (con prefijo de sheet-path `/`).
  La tool se construyó sobre este spike verde.

### D-12.4 `reload_in_gui` — **NO FACTIBLE en KiCad 10** (diferido a 11) ✗
Evidencia (spike de <1 h, read-only, sin tocar el board vivo):
- El objeto `KiCad` de esta kipy **no expone** reload agnóstico del editor
  (métodos: `get_board`, `get_open_documents`, `run_action[inestable]`, …; sin
  `get_schematic`).
- La API de documento de esquemático (`Schematic` + `.revert()`) es
  `versionadded 0.7.0 (KiCad 11)` (F4 la prohíbe).
- **Prueba en vivo contra KiCad 10.0.4:** `get_open_documents(DOCTYPE_PCB)` →
  ok (`video.kicad_pcb`); `DOCTYPE_SCHEMATIC`/`DOCTYPE_PROJECT` →
  `ApiError: no handler available for request of type
  kiapi.common.commands.GetOpenDocuments`.
- `run_action` descartado (API inestable, podría golpear el editor equivocado;
  sin xdotool por decisión).
- → **A5 cerrado, nada construido.** Hazard documentado en `guia-paleta.md`
  ("tras mutar el sch con KiCad abierto, aceptá el aviso de recarga") y en el
  catálogo (nombres reservados).

### D-12.5 `draw_board_outline` — **VERDE** ✓ (verificado en vivo)
- kipy expone `BoardRectangle` (mixin `Rectangle`: `top_left`/`bottom_right` en
  nm, setter `.layer`), creado con `board.create_items(rect)` — mismo camino que
  `add_track`/`add_via`.
- **Round-trip en vivo NET-ZERO al board real:** crear un rectángulo en
  `Edge.Cuts` subió el conteo de shapes 22→23 y devolvió KIID; borrarlo por
  KIID lo restauró 23→22.

### D-12.3 clone cross-file — **FACTIBLE** ✓ (implementado)
- kicad-skip **bloquea** el clone entre archivos por sus wrappers de colección
  (`symbol.new_from_list` / `lib_symbols.raw` levantan "Unknown element").
- **Funciona a nivel del árbol S-expr crudo** (`sch.tree`): copiar la def
  `(symbol "LIB:ID" …)` a `lib_symbols` del destino (dedup) + anexar la
  instancia con ref/uuid/posición nuevos. Verificado por netlist end-to-end vía
  la tool: `add_symbol(source="paleta.kicad_sch", lib_id="FIXLIB:R2", ref="R50")`
  → `R50` aparece como componente en el netlist del diseño.

---

## 2. `run_drc` presupuestado (T5, F-10, D-12.6) — tokens medidos

Board de disco medido: `/tmp/gui-test-project/video.kicad_pcb` con **608
violaciones** (282 error + 326 warning; el prompt citaba 283 — el estado de
disco avanzó desde entonces; 608 es un caso MÁS exigente y aun así cabe).

| Modo | Contenido | `tokens_est` | Objetivo |
|---|---|---|---|
| **Resumen (default)** | 8 tipos, count+severity+msg+5 muestras c/u, 608 viol. | **1 491** | ≤2 000 ✓ |
| Resumen con `exclude_types=[unconnected, lib_mismatch]` | 422 viol. | 1 143 | — |
| **Detalle** `detail_type="clearance", limit=20` | 20 viol. completas de 150 | 1 937 | 1 página |

Reducción vs. la respuesta cruda de la sesión 11 (18 956 tok): **~12.7×**. El
test integration re-verifica el presupuesto ≤2 000 sobre el board real. G3 (F2)
**no** consume la tool (usa `bridge.rules.run_drc` directo sobre el
`RulesReport`) → su semántica no cambió.

---

## 3. Confirms de las tools nuevas (todos ≤50 tok)

| Tool | Confirm ejemplo | tokens |
|---|---|---|
| `set_value` | `OK set_value R1 '10k'->'22k' in fixture.kicad_sch [snap:3]` | 16 |
| `set_footprint` | `OK set_footprint R1 ->Resistor_SMD:R_0805_2012Metric in … [snap:4]` | 23 |
| `connect_pins` | `OK connect_pins R1.2<->R2.2 net=I2C_SDA in fixture.kicad_sch [snap:5]` | 19 |
| `draw_board_outline` | `OK draw_board_outline @(10.0,10.0) 80.0x60.0mm Edge.Cuts [snap:6]` | 18 |
| `add_symbol` (cross-file) | `OK add_symbol R50 FIXLIB:R2 @(175.0,60.0) in design.kicad_sch [snap:1]` | 20 |

**Promedio: 19.2 tok** (techo 50, ADR-0004).

---

## 4. Estado del flujo sch/pcb end-to-end (tabla §1.3, 9 pasos)

Con **paleta + F8 humanos**, tras esta sesión:

| Paso | Antes | Ahora | Cubierto por |
|---|---|---|---|
| 1. Crear/abrir proyecto | ✗ humano | ✗ **humano** | (convención `KICAD_MCP_PROJECT`) |
| 2a. Colocar símbolos | parcial | ✓ **agente** (con paleta) | `add_symbol` + `source` (D-12.3) |
| 2b. Valores | ✗ | ✓ **agente** | `set_value` (T2) |
| 2c. Cableado | ✗ | ✓ **agente** (por labels, misma hoja) | `connect_pins` (T3) |
| 3. ERC | ✓ | ✓ | `run_erc` |
| 4. Asignar footprints | ✗ | ✓ **agente** (formato; existencia = KiCad) | `set_footprint` (T2) |
| 5. Sync sch→pcb (F8) | ✗ humano | ✗ **humano** (no factible KiCad 10, D-12.4) | GUI: File → Update PCB |
| 6. Colocar footprints | ✓ | ✓ | `move_footprint` |
| 7. Rutear | parcial | parcial (+ **borde**) | `add_track`/`add_via` + `draw_board_outline` (T4); autorouter → sesión 13 |
| 8. DRC | ✓ | ✓ **mejorado** (presupuestado) | `run_drc` (T5) |
| 9. Export fabricación | ✓ | ✓ | `export_manufacturing` (G3) |

**Cierre neto:** los pasos **2b, 2c, 4** pasan de "hueco" a cubiertos por el
agente; **2a** queda cubierto con la paleta humana; y `draw_board_outline`
agrega el borde Edge.Cuts (prerequisito de gerbers, paso 9). **Quedan en manos
del humano:** paso 1 (crear proyecto) y paso 5 (sync sch→pcb en GUI, F8 — no
automatizable en KiCad 10). **Queda para la sesión 13:** ruteo autónomo de
calidad (paso 7).

---

## 5. D-12.4 / D-12.5 — factibilidad y dónde quedó documentado

- **D-12.4 `reload_in_gui`: NO FACTIBLE en KiCad 10** (evidencia en §1 arriba).
  Documentado en: `docs/guia-paleta.md` (§"Hazard del editor abierto y
  recarga") y `docs/specs/tool-catalog.md` (§"Nombres reservados" →
  `reload_in_gui`). Nada construido.
- **D-12.5 `draw_board_outline`: FACTIBLE y construida** (kipy sí crea gráficos;
  verificado en vivo). No aplica el camino de "diferir".

---

## 6. Marker propuesto (D-12.7) y tiempos de suites

**Fenómeno de contención IPC** documentado en `docs/pruebas-gui.md`
(§"Contención IPC"): bajo ráfaga, ~4 tests `integration_gui` fallan transitorios
con `ipc_status="unhandled"` (cola de profundidad 1 de KiCad); **aislados
pasan**. Orden de corrida recomendado documentado ahí.

**Propuesta de marker** (F5 — el humano lo agrega; yo no toco `pyproject.toml`).
Línea exacta para el bloque `markers` de `[tool.pytest.ini_options]`:

```toml
    "integration_gui_slow: integration_gui pesado (loops de mutación + refill); correr aislado por la contención IPC (D-12.7)",
```

**Tiempos de suites (esta sesión):**
- `unit + golden` (`-m "not integration and not integration_gui"`):
  **171 passed en 39.1 s.**
- `integration` (kicad-cli, sin GUI): **22 passed, exit 0** (< 5 min; incluye
  ERC 001/002 y DRC resumen/detalle/exclude sobre 004).
- `integration_gui` de `draw_board_outline` (2 tests, KiCad vivo): **verde**
  (bridge create+remove net-zero; tool rechaza contorno del board real).

---

## 7. Dudas abiertas y lo que el spike de autorouting (sesión 13) debe saber

**Dudas abiertas:**
- **Cross-file clone y el bloque `(instances (project "NAME" …))`:** el clon
  hereda el nombre de proyecto de la paleta; KiCad lo tolera (re-anota al
  abrir/F8), pero no lo reescribo al proyecto destino. Si el Dogfooding 2
  reporta anotaciones raras tras F8, ese es el sospechoso #1.
- **`connect_pins` y labels preexistentes:** sobre un pin que ya carga un label
  global/jerárquico, el netlist conserva el nombre global (prioridad) y la tool
  sólo mergea; el snapshot derivado marca `net_name` en ambos pines (es una
  vista; el netlist es la verdad). Cubierto en el catálogo (caveat 4).
- **`draw_board_outline`:** sólo rectángulo; formas complejas fuera de scope.
  Valida "ya hay contorno" con `board_outline` — no valida que el contorno
  encierre los footprints (decisión: el borde puede ser mayor que el enjambre).

**Para el spike de autorouting (sesión 13, D-R11):**
- El **loop de escritura PCB está cerrado**: `add_track`/`add_via`/`delete_*` +
  `save_board` + `run_drc` (ahora barato). El autorouter puede apoyarse en
  `save_board` para bajar a disco antes de exportar DSN, y en el **`run_drc`
  presupuestado** para medir shorts sin quemar la ventana (el modo detalle
  paginado permite inspeccionar sólo `shorting_items`/`clearance`).
- `draw_board_outline` da el **Edge.Cuts** que Freerouting necesita como
  contorno de ruteo (export DSN requiere board outline).
- La contención IPC (D-12.7) importa: un router IPC de KiCad, si existe, sufrirá
  la misma cola de profundidad 1 — medir con KiCad recién quieto.
- `get_component_detail` (sesión 11) ya da pads absolutos + courtyard; el
  autorouter/medición de densidad puede reusarlo sin re-parsear el `.kicad_pcb`.

---

## Definition of Done

- `unit + golden` → **verde** (171 passed, 39 s).
- `integration` → **verde (22 passed, exit 0)** (kicad-cli, sin GUI; ERC
  001/002 + DRC resumen/detalle/exclude sobre 004 + resto).
- `integration_gui` (`draw_board_outline`) → **verde** con KiCad vivo.
- `mypy src/` → **Success (31 files)**. `ruff check`/`format` → **clean**.
- Catálogo actualizado en los mismos commits (DoD #2): `set_value`,
  `set_footprint`, `connect_pins`, `draw_board_outline`, `run_drc`
  presupuestado, `add_symbol source`; `reload_in_gui` marcado no-factible.

## Commits (uno por tarea)

1. `feat(sch): set_value + set_footprint sobre disco (T2, D-12.1)`
2. `feat(sch): connect_pins por labels locales (T3, D-12.2)`
3. `feat(pcb): draw_board_outline en Edge.Cuts vía IPC (T4, D-12.5)`
4. `feat(validate): run_drc presupuestado + paginado (T5, F-10, D-12.6)`
5. `feat(sch): add_symbol source — clone cross-file desde paleta (D-12.3)`
6. `docs: guía de paleta + D-12.7 + reporte sesión 12 (T6)`  ← este commit
