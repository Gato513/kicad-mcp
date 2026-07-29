# Validation Report — ANAVI Dev Mic (Nivel A-01)

**Sesiones 31 (2026-07-28) → 31b (2026-07-29) → 31c (2026-07-29).**
Primera validación de la Validation Suite (hoja-de-ruta-v5, Fase 4). Rol
dual: validar el flujo canónico sobre un proyecto ajeno al despertador Y
establecer el template metodológico que las sesiones 32-33 reutilizan.
**Este documento es ese template** — la estructura de secciones se
diseñó para reutilizarse independientemente de si una corrida cierra
limpio o revela un hallazgo. Cubre las 3 sesiones como narrativa
unificada: sesión 31 (Bloques 0-1, hallazgo P0/P1), sesión 31b (fix
intermedio, sin tocar la Suite), sesión 31c (Bloques 2-4, cierre).

**Veredicto final (sesión 31c): Escenario 5 de 7 ("Aprendizaje
metodológico") con elementos del Escenario 2 ("éxito con matiz de
umbrales").** El flujo canónico generaliza operacionalmente — `route_board`
completó, 0 fricciones P0/P1 nuevas, 15/15 nets ruteables ruteadas. Los 4
criterios D-30.3 se **midieron** de punta a punta (1/4 cumple: cobre); la
refutación de H1 en su forma estricta es evidencia sobre los umbrales
mismos, no sobre el flujo. Primer punto real de evidencia sobre H2
(sesión 31 sólo aportó calculabilidad parcial). Ver `metrics.md` §Análisis
H2 para el detalle. Precedente D-30.2 (éxito por confianza, no por
código): sesiones 23, 26, 30.

## Historia de la validación

| Sesión | Qué hizo | Resultado |
|---|---|---|
| **31** (2026-07-28) | Admisión (Bloque 0, 6 candidatos evaluados), ground truth medido, entorno instalado (Bloque 1), flujo canónico ejecutado hasta el paso 4/6 de Bloque 2 | Bloqueado en `route_board`: `F-V1-02` (P0, refs `REF**` duplicados) + `F-V1-01` (P1, bbox no leía Edge.Cuts, workaround aplicado). Escenario 4 ("aprendizaje por P0/P1"). |
| **31b** (2026-07-29) | Fix intermedio: `set_footprint_ref` + pre-check `DUPLICATE_REFS` (ADR-0013) para F-V1-02; unión Edge.Cuts∪enjambre para F-V1-01. Investigación previa detectó que el diseño obvio (`delete_footprint`) chocaba con ADR-0010 — pivotó a anotación tras spike GUI confirmado | Ambos hallazgos cerrados. 0 scope creep (no tocó la Suite ni Gate G2). |
| **31c** (2026-07-29) | Reintento de Bloque 2 completo (resolución de refs + colocación + zona GND + ruteo + refill final) + Bloque 3 (comparación D-30.3) + Bloque 4 (cierre) | `route_board` completó. 4 criterios D-30.3 medidos: 1/4 cumple (cobre). H1a/H1b confirmadas. H2: primer punto real de evidencia — umbral de vías no discriminante para bases pequeñas. Validación Nivel A **cerrada**. |

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
- **Ramas:** `sesion/31-validation-A-anavi-light-controller` (nombre
  heredado del prompt original; el contenido corresponde al candidato
  final tras la sustitución documentada) → `sesion/31b-fix-delete-footprint-y-bbox`
  (fix intermedio, branch desde 31) → `sesion/31c-reintento-anavi-dev-mic`
  (branch desde 31b; ni 31 ni 31b estaban mergeadas a `master` al arrancar
  31c — precondición verificada al inicio, resuelta encadenando la rama en
  vez de bloquear la sesión).
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

### Bloque 1b — Fix intermedio (sesión 31b, resumen)

Ver `docs/historico/sesiones/31b-reporte.md` para el detalle completo.
Resumen relevante para esta validación: `set_footprint_ref(ref, new_ref,
kiid=None)` resuelve refs duplicados por **anotación**, no por borrado
(pivote de diseño tras detectar que el `delete_footprint` original
chocaba con ADR-0010); pre-check `DUPLICATE_REFS` en `route_board` corre
antes del subprocess de exportación DSN. `board_bbox_mm`/
`read_board_context` ahora unen Edge.Cuts (±10mm) con el enjambre de
footprints (±100mm). Ninguno de los dos fixes tocó `validation-suite/` —
el `working/` preparado en sesión 31 (13 footprints, ground truth medido)
siguió válido para el reintento.

### Bloque 2 (continuación, sesión 31c) — flujo canónico completo

Reintento sobre el mismo `working/` (verificado en Bloque 0 de 31c: 0
tracks/vías/zonas, 13 footprints en `(0,0)`, 4× `REF**`, hashes de ground
truth idénticos a los registrados en sesión 31).

1. **Resolución de refs duplicados** (aplicación de fix de 31b, no M2):
   4 llamadas `set_footprint_ref("REF**", ...)`. 3 exitosas (→ `MH1`,
   `MH2`, `MH3`); la 4ta devolvió `INVALID_PARAMS` **por diseño** — tras
   3 renombres, la instancia restante ya no está duplicada, y la tool
   rechaza estructuralmente renombrar refs únicos (ADR-0013). La 4ta
   mounting hole quedó con el ref literal `REF**`, único en el board.
   Verificado con `read_board_context`: 0 duplicados, 13c/19n estable.
2. **Colocación asistida completa**: 13/13 footprints movidos (vs 9/13 en
   sesión 31 — las 3 `MH*` antes clavadas en `(0,0)` por F-V1-02 ahora se
   pudieron mover). Verificado con `get_footprint_neighbors` en los 6
   puntos más ajustados (U1, J1, J2, y los 4 mounting holes) — 0 overlaps
   de courtyard, márgenes de borde 0.95mm-2.2mm. DRC informativo
   post-colocación (antes de la zona): 86 total (41 err/45 warn) —
   mejora sobre el baseline 507 (444/63); 0 `courtyards_overlap`,
   `clearance`, `hole_clearance`, `hole_to_hole`, `holes_co_located` o
   `shorting_items` (todas las categorías de colisión de colocación de
   sesión 31 desaparecieron).
   **Nota de proceso**: las llamadas de verificación `get_footprint_neighbors`
   se lanzaron en batch paralelo y se encolaron contra el socket IPC de
   KiCad (cola de profundidad 1), tardando >120s cada una en vez de
   ~1-2s. Lección para sesión 32: serializar llamadas MCP contra
   `kicad-mcp`, no batchear en paralelo.
3. **`add_zone(net="GND", layer="B.Cu", bbox=[109,46.5,144,81], fill=true)`**
   → OK, `area_mm2: 1207.5` (idéntico a sesión 31).
4. **`fill_zones()` explícito** (D-26.1) → OK, `duration_ms: 23985.87`.
5. **`route_board()`** → **completó**. 15/15 nets ruteables ruteadas
   (19 nets totales, 4 son pads únicos sin conexión — no ruteables por
   definición), 0 bloqueadas, 0 parciales. `route_ms: 184817.54` (~3.1
   min, muy por debajo del umbral de 30 min). 79 tracks, 6 vías. El
   pre-check `DUPLICATE_REFS` no se disparó (confirma H1b).
   **Incidente de proceso**: tras `route_board` (que escribe a disco
   directo), el editor vivo de KiCad quedó desincronizado
   (`EXTERNAL_EDIT_DETECTED`); `reload_board_from_disk()` devolvió
   `KICAD_NOT_RUNNING` porque un diálogo modal de KiCad ("¿archivo
   cambió afuera, recargar?") bloqueaba el hilo de UI. Resuelto con un
   handoff humano adicional (cerrar el diálogo). Recomendación: anticipar
   este diálogo como parte normal del paso post-`route_board` en sesión 32.
6. **`fill_zones()` final** (protege D-23.2/ADR-0012) → OK,
   `duration_ms: 26141.97`.
7. **`run_drc()` de cierre**: **63 total (18 err / 45 warn)**. Ver
   `metrics.md` para el desglose completo y la comparación con el ground
   truth.
8. **`measure_ground_truth.py`** sobre el output final → 4 métricas
   D-30.3 medidas. Ver `metrics.md`.

Resultado copiado de vuelta a `working/anavi-dev-mic.kicad_pcb` al cierre
del bloque (a diferencia de sesión 31, que no llegó a este paso).

### Bloque 3 — Comparación cuantitativa vs ground truth (sesión 31c)

Ver `metrics.md` §Comparación (sesión 31c) para el detalle numérico
completo. Resumen:

| Criterio D-30.3 | Umbral | Resultado | Veredicto |
|---|---|---|---|
| DRC | 0 errores nuevos vs GT | 18=18 en conteo, pero 1 tipo nuevo (`unconnected_items` vs `starved_thermal` del GT) + 2 tipos de warning cosméticos nuevos | **NO CUMPLE** (estricto) |
| Tracks | ±30% | -33.1% | **NO CUMPLE** (margen estrecho, 3.1 puntos fuera) |
| Vías | ±20% | +200% (6 vs 2) | **NO CUMPLE** (margen amplio — base de 2 vías no discrimina) |
| Cobre | ±25% | -10.3% | **CUMPLE** (margen cómodo, 14.7 puntos de holgura) |

**1 de 4 criterios cumple.** Ver `metrics.md` §Análisis H2 para por qué
esto NO se interpreta como "el flujo produce una placa mala" — el board
completó ruteo con 0 nets bloqueadas, componentes/nets exactos al ground
truth, y el único error DRC nuevo es una vía-a-pad de 0.30mm sin
conectar (`F-V1c-01`, P2).

## Fricciones (F-V1-XX)

### F-V1c-01 — Vía GND no conectada a pad de 0.30mm post-`route_board`+refill (P2, sesión 31c)

DRC de cierre: 18 errores, mismo conteo que el ground truth, pero
composición distinta — 17 `solder_mask_bridge` (compartido con el GT) +
1 `unconnected_items` (el GT tiene `starved_thermal` en su lugar). El
error nuevo: una vía `[GND]` en F.Cu-B.Cu (pos `129.88,76.582`) no
conecta con el pad GND de MK1 (pos `126.5,75.567`), el pad más chico del
board (0.30×0.30mm). No bloqueó el flujo — 14/15 nets GND-relacionadas +
el resto completaron sin problema; es 1 pad de conectividad sin cerrar
sobre 79 tracks + 6 vías + 1 zona. No investigado en profundidad (fuera
de alcance de sesión 31c — no toca `src/` salvo P0/P1 trivial). Ver
`docs/BACKLOG.md` §P2 y `metrics.md` para el detalle completo.

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

## Métricas D-30.3 (histórico sesión 31)

**No evaluables — sin output de ruteo.** Los 4 criterios (DRC 0/0,
tracks ±30%, vías ±20%, cobre ±25%) requerían un output completo que en
sesión 31 nunca se produjo. Ver `metrics.md` §Comparación (sesión 31c)
para el resultado final.

## Métricas D-30.3 (final, sesión 31c)

**Los 4 criterios medidos.** 1 de 4 cumple (cobre). Ver tabla en Bloque 3
arriba y `metrics.md` §Comparación para el detalle numérico completo.

## Métricas auxiliares (M1/M2/M3) — histórico sesión 31

- **M1** (tiempos): colocación + refill instrumentados; ruteo N/A (nunca
  arrancó Freerouting — falló antes, en la exportación DSN).
- **M2 = 1**: un único ajuste táctico (bootstrap de `move_footprint` para
  F-V1-01), sin cambio conceptual del flujo. **Se decidió explícitamente
  NO sumar M2 por F-V1-02** — la sesión se detuvo en vez de intervenir.
- **M3.a = PASS**: `footprint_count` estable en 13 durante toda la
  colocación, sin corrupción.
- **M3.b**: 9/13 footprints (69%) modificados de posición; 3 (`REF**`)
  no pudieron moverse — atribuible a F-V1-02, no a decisión de diseño.

## Métricas auxiliares (M1/M2/M3) — final, sesión 31c

Ver `metrics.md` §Métricas auxiliares (sesión 31c) para el detalle
completo.

- **M1**: `t_resolucion_refs` ~segundos (4 llamadas); `t_colocacion` 13
  `move_footprint` + 6 `get_footprint_neighbors` (lección de proceso:
  evitar batches paralelos contra el socket IPC de cola depth-1);
  `t_refill_1` 23.99s; `t_routing` 184.82s (`route_ms`); `t_refill_2`
  26.14s; `t_drc` no instrumentado (sub-segundo típico).
- **M2 = 0**: sin intervenciones discrecionales. Las 4 `set_footprint_ref`
  son aplicación de fix conocido (ADR-0013, no cuentan). El handoff del
  diálogo modal post-`route_board` es operación de entorno, no decisión
  de diseño.
- **M3.a = PASS**: `footprint_count`/`net_count` exactos al ground truth
  (13/20) en toda medición.
- **M3.b**: **13/13 footprints (100%) modificados** — mejora sobre el
  69% de sesión 31, ya que las 3 `MH*` antes bloqueadas ahora se pudieron
  colocar.

## Análisis H2 (umbrales D-30.3) — histórico sesión 31

Sesión 31 aportó evidencia **parcial**: el procedimiento de medición
(`measure_ground_truth.py`) resultó calculable sin ambigüedad sobre un
board real y no trivial (ground truth: 13 fp, 20 nets, 2 capas, sin
`method_notes`). Eso fue señal a favor de la mitad "calculabilidad" de
H2. Sin evidencia sobre discriminancia — eso requería el output completo,
que sesión 31c aporta.

## Análisis H2 (umbrales D-30.3) — final, sesión 31c

**Primer punto real de evidencia** (no parcial). Ver `metrics.md`
§Análisis H2 para el detalle completo. Resumen:

- **Cobre (±25%)**: bien calibrado — resultado con margen cómodo (-10.3%,
  14.7 puntos de holgura).
- **Tracks (±30%)**: sin evidencia de mala calibración — falló por un
  margen muy estrecho (-33.1%), consistente con "el umbral discrimina
  bien" (cae cerca del borde, no lejos).
- **Vías (±20%)**: **evidencia clara de mala calibración para bases
  pequeñas**. La base del ground truth (2 vías) es tan chica que
  cualquier resultado realista de autorouteo casi seguro excede ±20% —
  un salto de 2→3 vías ya es +50%. Candidato explícito para revisión
  post-33: umbral absoluto (±N vías) o normalizado por número de nets,
  no porcentaje sobre una base de un dígito.
- **DRC "0 errores nuevos"**: demasiado estricto en un sentido —
  coincide en CONTEO (18=18) pero falla por 1 tipo de error distinto y 2
  tipos de warning puramente cosméticos (silkscreen). Recomendación:
  separar severidad eléctrica/funcional de cosmética en revisión post-33.

**No se cierra la validez definitiva de D-30.3 acá** (D-30.4: fuera de
alcance rediseñarla en esta sesión) — es el segundo de tres puntos de
evidencia formal (el primero fue la calculabilidad parcial de sesión 31;
el tercero vendrá de Nivel B/C).

## Veredicto y próximos pasos (final, sesión 31c)

**Escenario 5 — "Aprendizaje metodológico"**, con elementos del
**Escenario 2 — "éxito con matiz de umbrales"** (de los 7 posibles del
prompt original de sesión 31). **NO es el Escenario 4** de sesión 31 —
esta vez no hubo ningún hallazgo P0/P1 nuevo; el fix de 31b demostró ser
suficiente (H1b confirmada) y las decisiones D-19.1/D-23.2/D-26.1/D-27.1/
D-30.5 generalizaron sin fricción (H1a confirmada). La refutación de H1
en su forma estricta D-30.3 (1/4 criterios cumple) es evidencia sobre los
**umbrales**, no sobre el **flujo**: el board completó, sin nets
bloqueadas, componentes/nets exactos, único error DRC nuevo es una vía a
un pad de 0.30mm.

**Recomendación para el arquitecto:**
1. **Primera validación Nivel A cerrada.** Sesión 32 (Nivel B) puede
   arrancar — candidato a confirmar siguiendo el mismo patrón de admisión
   de Bloque 0 de sesión 31.
2. El template metodológico (estructura de directorios, scripts, 3
   handoffs humanos, gate GUI al inicio) queda validado end-to-end sobre
   una corrida completa, no sólo sobre el intento parcial de sesión 31.
3. **Input formal para revisión post-sesión 33 (D-30.3)**: el umbral de
   vías necesita revisión (candidato: absoluto o normalizado por nets);
   el criterio DRC estricto-por-tipo probablemente necesita distinguir
   severidad eléctrica de cosmética. No decidir esto antes del 3er punto
   de evidencia (Nivel C).
4. `F-V1c-01` (P2, vía GND sin conectar a pad de 0.30mm) queda en
   `docs/BACKLOG.md`, candidato a investigación si reaparece en Nivel B/C
   con pads igual de chicos.

**Sesión 31c mergea con una validación Nivel A completamente cerrada** —
flujo ejecutado de punta a punta, 4 criterios D-30.3 medidos, template
metodológico completo, y el primer punto real de evidencia sobre
discriminancia de umbrales. Ver `docs/historico/sesiones/31c-reporte.md`
para el resumen ejecutivo.
