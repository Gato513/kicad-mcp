# Validation Report — ANAVI Dev Mic (Nivel A-01)

**Sesión 31, 2026-07-28.** Primera validación de la Validation Suite
(hoja-de-ruta-v5, Fase 4). Rol dual: valida el flujo canónico sobre un
proyecto ajeno al despertador Y establece el template metodológico que
las sesiones 32-33 reutilizan. **Este documento es ese template** — la
estructura de secciones se diseñó para reutilizarse aunque el resultado
de esta corrida particular sea un hallazgo, no un cierre exitoso.

**Veredicto: Escenario 4 de 7 ("Aprendizaje por P0/P1").** El flujo se
detuvo en `route_board` por un hallazgo P0 (`F-V1-02`, ver abajo). Los 4
criterios D-30.3 no se pudieron evaluar. Sesión cierra con hallazgo
documentado, no con validación completa. Precedente: sesiones 23, 26, 30
(D-30.2 — éxito por confianza, no por código).

---

## Contexto

- **Candidato final:** ANAVI Dev Mic (`AnaviTechnology/anavi-dev-mic`,
  commit `f742ae039ca00939cc542bea7a7982de9818d564`, 2024-10-23). Ver
  `README.md` de este directorio para el historial completo de selección
  de candidato (el prescrito originalmente, `anavi-light-controller`, se
  descartó por formato KiCad 4/2018; se evaluaron 6 candidatos en total).
- **Licencia:** CC BY-SA 4.0.
- **Placa:** microphone USB-C con XIAO RP2040, 2 capas, 13 footprints, 20
  nets, ~35×34.5mm (octágono con esquinas cortadas).
- **Rama:** `sesion/31-validation-A-anavi-light-controller` (nombre
  heredado del prompt original; el contenido corresponde al candidato
  final tras la sustitución documentada).
- **Excepción de admisión aprobada:** criterio 6 (DRC 0/0 del ground
  truth) NO se cumple — 18 errores / 25 warnings preexistentes al layout
  del autor (`solder_mask_bridge`×17, `starved_thermal`×1). Aprobada
  explícitamente por el arquitecto vía `AskUserQuestion` en Bloque 0 — ver
  `README.md` §Admisión para el razonamiento completo.

## Fases ejecutadas

### Bloque A — Gate GUI de regresión (adelantado antes del Bloque 0)

Corrido primero (no al final, como en el prompt original) para minimizar
los cambios de proyecto abierto en KiCad — sesión 31 no tocó `src/`, así
que el gate corrido al inicio es evidencia de no-regresión válida.

- `test_pcb_session21_hole_clearance_gui.py`: **2/2 verde** contra copia
  fresca en `/tmp/kicad-mcp-sesion31-gui/`.
- `test_pcb_session27_zone_persist_gui.py`: **2/2 verde** (marca
  `integration_gui_slow`, no `integration_gui` — corregido en la corrida,
  ver nota de proceso abajo).
- `pytest -m "not integration"`: verde (exit 0).
- `pytest -m integration`: verde (exit 0).

**Nota de proceso para sesiones 32/33:** el `addopts` por defecto de
`pyproject.toml` excluye `integration_gui` Y `integration_gui_slow`; hay
que pasar `-m integration_gui` o `-m integration_gui_slow` explícito según
el marker real de cada archivo de test (`test_pcb_session27_zone_persist_gui.py`
usa `integration_gui_slow`, no el genérico).

### Bloque 0 — Admisión y ground truth (~90 min, incluyó re-selección de candidato)

Ver `README.md` de este directorio para el detalle completo de los 6
candidatos evaluados. Entregables:

- `ground-truth-original/` — copia intacta del commit canónico.
- `ground-truth-kicad10/` — migrado con `kicad-cli sch/pcb upgrade
  --force`. DRC idéntico bit a bit pre/post migración (43/43 violaciones,
  mismos tipos y conteos) — regla de decisión del Bloque 0 satisfecha.
- `validation-suite/tools/measure_ground_truth.py` — script de medición
  reutilizable. Union geométrica por capa (no suma aditiva) para
  `copper_area_mm2`, verificado con `union ≤ aditivo` en 3 boards
  distintos (despertador-routed, ground-truth-kicad10, working/).
  **Hallazgo durante su construcción**: `board.GetBoardEdgesBoundingBox()`
  de pcbnew NO se limita a Edge.Cuts pese a su nombre — incluye la bbox de
  otros ítems del board. El script calcula el bbox de Edge.Cuts
  explícitamente en su lugar (ver docstring de `_board_area_mm2` en el
  script).
- `validation-suite/tools/prepare_working.py` — genera `working/` desde
  `ground-truth-kicad10/`. **Hallazgo durante su construcción**: pcbnew
  10.0.4 hace **segfault** (SIGSEGV) si se remueven tracks/zonas y se
  mueve un footprint en el MISMO proceso Python — incluso releyendo el
  board recién guardado. Aislado por bisección manual (remover tracks
  solo: OK; remover zonas solo: OK; mover solo: OK; remover+mover en el
  mismo proceso: crash). Mitigación: cada etapa de mutación corre en su
  propio subprocess (ver docstring del script). No se investigó la causa
  raíz en pcbnew mismo (fuera de alcance — es un binding de terceros).
- Ground truth medido: DRC 18e/25w, 242.85mm tracks, 2 vías, 1556.74mm²
  cobre (unión). Ver `metrics.md`.

### Bloque 1 — Instalación del entorno vivo y baseline (~15 min)

- Reubicación de `working/` en `/tmp/gui-test-project` (donde apunta el
  server MCP persistente vía `KICAD_MCP_PROJECT`), con el despertador
  respaldado no-destructivamente en
  `/tmp/gui-test-project.despertador-bak/` (patrón D-27.1). 3 handoffs
  humanos: cerrar despertador, abrir ANAVI (proyecto), abrir ANAVI (PCB
  Editor específicamente — el primer intento sólo abrió el Project
  Manager, `health()` lo detectó con `pcb_editor_abierto: "no"`).
- `get_world_context(kind="pcb")` confirmó 13c/19n, bbox de Edge.Cuts
  coincidente con lo medido, todos los footprints en `(0,0)`.
- `run_drc()` baseline: **507 total (444 errores / 63 warnings)** —
  coincide con `measure_ground_truth.py` corrido independientemente sobre
  el mismo archivo (444/63 exacto), buena validación cruzada entre la
  tool MCP y el script standalone.

### Bloque 2 — Flujo canónico (bloqueado en el paso 4 de 6)

Orden ejecutado: colocación asistida → plano GND (B.Cu) → refill
explícito → **route_board falla** → (refill final y DRC de cierre nunca
corrieron).

1. **Colocación asistida.** `get_footprint_neighbors` + `move_footprint`
   ×10 (1 bootstrap de `U1` + 9 footprints únicos: `U1, J1, J2, MK1, R1,
   R2, C1, C2`, más 1 de las 4 instancias `REF**`). Verificación de
   colisión con `get_footprint_neighbors(J1)` y `get_footprint_neighbors(U1)`
   — sin overlaps en los puntos más ajustados. `D-D3.1` (margen de borde
   ≥1.5-2mm) no se pudo cumplir estrictamente para `J1` (quedó a 1.2mm del
   borde izquierdo) — el board es genuinamente denso (U1 solo ocupa
   18.9×18.0mm de un board de 35×34.5mm); se aceptó el margen menor ante
   la restricción física real, sin que DRC lo marcara como violación.
2. **`add_zone(net="GND", layer="B.Cu", bbox=[109,46.5,144,81], fill=true)`**
   → OK, `area_mm2: 1207.5` (board completo, esperado — D-19.1).
3. **`fill_zones()` explícito** (D-26.1, mecánico) → OK,
   `duration_ms: 16672.67`.
4. **`route_board()`** → **`KICAD_CLI_FAILED`, stage `export_dsn`.**
   Ver `F-V1-02` abajo para el diagnóstico completo.
5. Refill final: no corrió (bloqueado por el paso 4).
6. `run_drc()` de cierre: no corrió como paso del flujo, pero se ejecutó
   una lectura **informativa** post-colocación+zona para documentar el
   estado en el punto de bloqueo: **89 total (56 errores / 33
   warnings)** — mejora fuerte sobre el baseline 507. Ver `metrics.md`
   §Output para el desglose completo.

## Fricciones (F-V1-XX)

### F-V1-01 — `board_bbox_mm` no lee Edge.Cuts pese a documentarlo (P1)

Bloqueaba mover CUALQUIER footprint al contorno real cuando todos parten
apilados en `(0,0)` (la convención de estado inicial que esta misma
sesión adoptó para `working/`). Causa: `src/kicad_mcp/bridge/ipc.py:1422-1452`
nunca implementa la preferencia de Edge.Cuts que su propio docstring
declara. **Workaround dentro del flujo canónico** (autorizado por el
arquitecto): mover un footprint a una posición intermedia dentro del
rango inicialmente válido primero, lo que expande el bbox aceptado
(basado en el enjambre de posiciones ±100mm) para el resto de la
colocación. Un solo bootstrap alcanzó para desbloquear todo el board.
Registrado en `docs/BACKLOG.md` §P1 con fix propuesto (~10 líneas).

### F-V1-02 — Refs de footprint duplicados/sin anotar bloquean `route_board` enteramente (P0)

El diseño trae 4 mounting holes con reference designator literal `REF**`
compartido (footprints sólo-mecánicos, nunca anotados por el autor —
patrón real en diseños externos, no un artefacto de nuestra
preparación). Dos síntomas, uno ya sospechado y otro nuevo:

1. `move_footprint(ref="REF**", ...)` sólo puede direccionar UNA de las 4
   instancias (`_find_target` en `src/kicad_mcp/tools/pcb.py:100-114`
   resuelve por primer match de `fp.ref == ref`). Las otras 3 quedan
   clavadas en `(0,0)` para siempre.
2. **Nuevo, aislado con experimento controlado**: `pcbnew.ExportSpecctraDSN()`
   — invocada por `route_board` para generar el `.dsn` que consume
   Freerouting — devuelve `ok=False, size=0` cuando el board tiene refs
   duplicados, **sin importar su posición**. Confirmado quitando 3 de las
   4 instancias `REF**` en una copia de prueba (`/usr/bin/python3`
   standalone, sin tocar el flujo MCP): la exportación pasó de fallar a
   `ok=True, size=2.4MB`.

**Por qué esto detuvo la sesión en vez de forzar un workaround:** no
existe tool `delete_footprint` en el catálogo MCP (asimetría ya conocida,
`docs/BACKLOG.md` §P2 histórico — sesión 31 la escala a P0 con evidencia
concreta). Borrar las 3 instancias sobrantes requeriría scripting `pcbnew`
directo fuera del flujo canónico — una intervención M2=3 ("modificaciones
manuales... fuera del flujo", la categoría más alta de la escala del
prompt) que contaminaría H1a. Presentado al arquitecto vía
`AskUserQuestion`; decisión: cerrar la sesión con el hallazgo documentado
en vez de forzar el cierre con una intervención no canónica. Fix
propuesto: `delete_footprint(ref, kiid=None)` direccionable por `kiid`
cuando `ref` es ambiguo. Ver `docs/BACKLOG.md` §P0 para el detalle
completo y la propuesta de fix.

## Métricas D-30.3

**No evaluables — sin output de ruteo.** Los 4 criterios (DRC 0/0,
tracks ±30%, vías ±20%, cobre ±25%) requieren un output completo que
nunca se produjo. Ver `metrics.md` §Comparación.

## Métricas auxiliares (M1/M2/M3)

Ver `metrics.md` §Métricas auxiliares para el detalle completo.

- **M1** (tiempos): colocación + refill instrumentados; ruteo N/A (nunca
  arrancó Freerouting — falló antes, en la exportación DSN).
- **M2 = 1**: un único ajuste táctico (bootstrap de `move_footprint` para
  F-V1-01), sin cambio conceptual del flujo. **Se decidió explícitamente
  NO sumar M2 por F-V1-02** — la sesión se detuvo en vez de intervenir.
- **M3.a = PASS**: `footprint_count` estable en 13 durante toda la
  colocación, sin corrupción.
- **M3.b**: 9/13 footprints (69%) modificados de posición; 3 (`REF**`)
  no pudieron moverse — atribuible a F-V1-02, no a decisión de diseño.

## Análisis H2 (umbrales D-30.3)

Sesión 31 aporta evidencia **parcial**: el procedimiento de medición
(`measure_ground_truth.py`) resultó calculable sin ambigüedad sobre un
board real y no trivial (ground truth: 13 fp, 20 nets, 2 capas, sin
`method_notes`). Eso es señal a favor de la mitad "calculabilidad" de H2.
No hay evidencia sobre la mitad "discriminancia de umbrales" — eso
requiere comparar contra un output que no se produjo. **No se puede
cerrar H2 con este único punto**; sesión 31 pasa a ser el primer intento
de Nivel A, pendiente de reintento post-fix de F-V1-02.

## Veredicto y próximos pasos

**Escenario 4 — "Aprendizaje por P0/P1"** (de los 7 posibles del prompt).
H1a refutada honestamente: el flujo canónico, tal cual existe hoy, NO
generaliza a boards con reference designators duplicados/sin anotar —
gap legítimo del flujo (interpretación Fase 4: "NO regresión por
default" ante P0 en validación externa), no un bug oculto del despertador
que reapareció.

**Recomendación para el arquitecto:**
1. Sesión de fix intermedia: agregar `delete_footprint(ref, kiid=None)`
   al catálogo de tools (fix de `F-V1-02`, requiere ADR si formaliza un
   contrato de direccionamiento por `kiid` para tools existentes). Fix
   menor de `board_bbox_mm` (F-V1-01) puede agruparse en la misma sesión.
2. Tras el fix, **reintentar sesión 31** sobre el mismo `working/` de
   ANAVI Dev Mic (ya preparado, ya blindado, ya con ground truth medido —
   el trabajo de Bloque 0/1 es reutilizable íntegro) para completar
   Bloque 2/3/4 con el flujo desbloqueado.
3. La estructura de directorios, el script de medición, y el patrón de 3
   handoffs humanos (cerrar proyecto anterior → abrir nuevo proyecto →
   abrir específicamente el PCB Editor) quedan validados como parte del
   template para sesiones 32/33, independientemente del resultado de
   esta corrida particular.

**Sesión 31 NO mergea con una validación cerrada** — mergea con el
hallazgo documentado, la Validation Suite inicializada (estructura +
tooling), y el backlog actualizado. Ver `docs/historico/sesiones/31-reporte.md`
para el resumen ejecutivo.
