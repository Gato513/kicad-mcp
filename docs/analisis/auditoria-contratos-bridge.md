# Auditoría sistemática de contratos de escritura del bridge

**Fecha:** 2026-07-30 · **Sesión:** 34a · **Tipo:** investigación pura
(auditoría, D-30.1/D-33.1), sin fixes salvo excepción trivial (Bloque 3).

**Origen:** compromiso formal del arquitecto post-sesión 32b: auditar
todos los contratos de escritura del bridge, no para reescribirlos, sino
para verificar que cumplen el mismo modelo de persistencia, propagación de
errores y sincronización disco↔memoria. Rol dual: verificación interna +
inventario de la superficie pública que 34b/34c documentarán (README,
CONTRIBUTING).

**Documento vivo** — patrón `validation-suite-sintesis-A-B-C.md`. Sesiones
futuras (`34a-fix-N`) actualizan las recomendaciones a medida que se
resuelven asimetrías.

---

## §0 — Refutación del inventario preliminar

El prompt de sesión 34a incluía un inventario preliminar con la advertencia
explícita de que podía estar incompleto (D-33.1: "este listado puede estar
incompleto... Bloque 0 debe refutar la hipótesis con inspección directa del
código"). La inspección lo refuta en tres puntos:

1. **`delete_footprint` no existe.** El inventario preliminar lo listaba
   como tool nueva de sesión 31b. En realidad, [ADR-0013](../adr/0013-refs-duplicados-por-anotacion-no-borrado.md)
   registra que un `delete_footprint` general fue **explícitamente
   rechazado** — choca con [ADR-0010](../adr/0010-borrado-de-cobre-sin-gate-g2.md)
   (footprints siguen detrás de Gate G2, que no existe en código). Sesión
   31b resolvió el caso real (refs `REF**` duplicados) por **anotación**
   (`set_footprint_ref`), no por borrado. La asimetría `delete_track` sí /
   `delete_footprint` no es una decisión de diseño deliberada y vigente
   (`docs/BACKLOG.md:452`).
2. **`clone_symbols` no es una tool registrada.** Sólo aparece mencionada
   una vez en `docs/BACKLOG.md:477` en una lista informal; no hay
   `@mcp.tool(name="clone_symbols", ...)` en `src/kicad_mcp/tools/sch.py`
   ni en ningún otro módulo. `add_symbol` ya cubre "clonar un símbolo" (su
   propia descripción: *"Clona un símbolo... y lo coloca con nueva ref"*).
3. **Faltantes reales:** `add_keepout_zone`, `delete_zone`, `save_board` y
   `reload_board_from_disk` no aparecían en el listado preliminar. Además,
   `set_value`/`set_footprint` son tools de **esquemático** (W-SKIP,
   `src/kicad_mcp/tools/sch.py`), no de PCB como agrupaba el listado
   preliminar del prompt.

**Método de verificación:** `grep -n '@mcp.tool' src/kicad_mcp/tools/*.py`
sobre las 31 ocurrencias del decorador en el árbol de tools, clasificadas
una por una por lectura directa del código (no por nombre inferido).
Confirmado contra la lista de tools MCP expuestas en runtime (31 tools
totales, lectura + escritura).

---

## §1 — Taxonomía y superficie real

| Categoría | Definición | Tools |
|---|---|---|
| **W-IPC** | Mutación del board vivo vía IPC (kipy), snapshot registrado con `mtimes=None` (D0007), **sin** `save_board()` propio | `move_footprint`, `set_footprint_ref`, `add_track`, `add_via`, `delete_track`, `delete_via`, `delete_tracks_bulk`, `draw_board_outline`, `add_keepout_zone`, `delete_zone`, `add_zone(fill=False)` |
| **W-COMPOSITE** | Mutación + `refill_zones()` + `enforce_hole_clearance()` + `save_board()` incondicional, contrato D-23.2/ADR-0012 | `route_board`, `fill_zones`, `add_zone(fill=True)` |
| **W-SKIP** | Escritura directa a disco vía `kicad-skip` (sin IPC — KiCad 10 no expone IPC de esquemático, D-08.5) | `add_symbol`, `set_value`, `set_footprint`, `connect_pins` |
| **Infra** | No mutan diseño; sostienen los 4 ejes para las demás | `save_board`, `reload_board_from_disk` |

`add_zone` es **dual-mode**: W-IPC con `fill=False` (`pcb.py:2438`,
`mtimes=None`), W-COMPOSITE con `fill=True` (`pcb.py:2415` save,
`pcb.py:2435` mtimes frescos). Auditada como dos filas.

**19 tools únicas, 20 filas de matriz** (por el split de `add_zone`).

---

## §2 — Matriz completa

Veredictos: **C** = cumple · **C-m** = cumple con matiz · **N** = no
cumple / no aplica por diseño (ver ficha) · **N/A** = eje no aplicable a
esta tool.

| Tool | Tipo | Eje 1 Persistencia | Eje 2 Errores | Eje 3 Sync | Eje 4 Reload | ADRs |
|---|---|---|---|---|---|---|
| `route_board` | W-COMPOSITE | C | C | C | C | ADR-0012, ADR-0013 |
| `fill_zones` | W-COMPOSITE | C | C | C | N/A | ADR-0012 |
| `add_zone(fill=True)` | W-COMPOSITE | C | C | C | N/A | ADR-0012 |
| `add_zone(fill=False)` | W-IPC | C-m (por diseño) | C | C | N/A | ADR-0012 |
| `delete_tracks_bulk` | W-IPC | **N** (asimetría A1) | C-m | C | N/A | ADR-0012 (no cubierta) |
| `delete_track` | W-IPC | N/A (no toca zonas) | C | C | N/A | — |
| `delete_via` | W-IPC | N/A (no toca zonas) | C | C | N/A | — |
| `delete_zone` | W-IPC | **N** (asimetría A2) | C | C | N/A | — |
| `add_keepout_zone` | W-IPC | **N** (asimetría A3) | C | C | N/A | — |
| `set_footprint_ref` | W-IPC | C-m (por diseño) | C | C | N/A | ADR-0013 |
| `move_footprint` | W-IPC | C-m (por diseño) | C | C | N/A | — |
| `add_track` | W-IPC | C-m (por diseño) | C | C | N/A | — |
| `add_via` | W-IPC | C-m (por diseño) | C | C | N/A | — |
| `draw_board_outline` | W-IPC | C-m (por diseño) | C | **C** (A7, fix aplicado sesión 34a) | N/A | — |
| `save_board` | Infra | C (es el mecanismo) | C | C | N/A | — |
| `reload_board_from_disk` | Infra | N/A | C | C (es el mecanismo) | C (es el mecanismo) | — |
| `add_symbol` | W-SKIP | C | C | C | N/A | D-08.5 |
| `set_value` | W-SKIP | C | C | C | N/A | D-08.5, D-12.1 |
| `set_footprint` | W-SKIP | C | C | C | N/A | D-08.5, D-12.1 |
| `connect_pins` | W-SKIP | C | C | C | N/A | D-08.5, D-12.2 |

**Lectura de la fila "C-m (por diseño)" en Eje 1**, aplicada a 6 W-IPC:
estas tools NUNCA persisten a disco — el snapshot es explícitamente
`mtimes=None` (vivo). Bajo D-14.3, esto es una decisión de diseño válida
(el llamador orquesta `save_board()` cuando quiere persistir), **no** un
incumplimiento del contrato D-23.2 (que sólo aplica a las 3 tools
W-COMPOSITE). El matiz es que ninguna de las 6 lo declara en su propia
respuesta (ver A6, §3).

---

## §3 — Fichas por tool

### W-COMPOSITE (máxima superficie contractual)

#### Tool: `route_board`

**Ubicación:** `src/kicad_mcp/tools/pcb.py:2782-3208`. **ADRs:**
[ADR-0012](../adr/0012-route-board-persist-contract.md) (contrato central,
extendido sesiones 27/32b/32d), [ADR-0013](../adr/0013-refs-duplicados-por-anotacion-no-borrado.md)
(pre-check `DUPLICATE_REFS`).

- **Eje 1 — Persistencia:** `save_board()` implícito pre-ruteo (D-14.3,
  línea 2844, sólo si `is_target_open and not live_stale`); reemplazo
  atómico `os.replace()` del `.kicad_pcb` ruteado (línea 2885, no pasa por
  kipy); `save_board()` condicional post-refill (`_refill_enforce_and_save`,
  línea 2959, sólo si `refill and zones_existentes > 0 and reloaded is
  True`); `save_board()` adicional si hubo stitching (línea 3024).
  *Refutación:* ¿hay un camino donde termina OK con disco≠memoria≠`err_post`?
  No — es precisamente lo que D-23.2 garantiza y lo que
  `POST_ROUTE_REFILL_SKIPPED` (D-32b.1) cierra para el único hueco
  encontrado en Fase 4 (recarga fallida silenciosa). **Veredicto: cumple.**
  Cobertura de test: `tests/test_pcb_session24_route_board_persist_gui.py`,
  `tests/test_pcb_session32b_refill_silencioso_canary.py`.
- **Eje 2 — Propagación de errores:** `DUPLICATE_REFS` (pre-check),
  `POST_ROUTE_PERSIST_FAILED` (save post-refill falla),
  `POST_ROUTE_REFILL_SKIPPED` (recarga falló, refill nunca corrió). Todos
  adiciones puras al `ErrorCode` StrEnum (F1/F3 intactas). *Refutación:*
  ¿algún camino descarta una excepción real sin código? Hasta sesión 32b
  sí (`except KicadMcpError: reloaded = False`, silencioso) — cerrado por
  D-32b.1: el `reload_error` se conserva y alimenta el raise final.
  **Veredicto: cumple** (post-fix; pre-32b era el hallazgo F-V2).
- **Eje 3 — Sincronización disco↔memoria:** no usa `_guard_live_stale()`
  al inicio (no aplica — `route_board` es lo que *genera* el estado que el
  guard protege en otras tools), pero sí aplica `store.mark_live_stale()`
  / `store.clear_live_stale()` al final según `reloaded` (línea 3064-3067).
  *Refutación:* ¿puede terminar con el flag en el estado incorrecto?
  Requeriría que `reloaded is True` pero el disco no reflejara el vivo —
  no hay tal camino: `reloaded is True` sólo se setea tras
  `bridge.reload_board_from_disk()` exitoso. **Veredicto: cumple.**
- **Eje 4 — Manejo de reload:** invoca `reload_board_from_disk` (línea
  2917) sólo si `is_target_open`; la excepción se captura y **se
  propaga como diagnóstico** (D-32b.1), no se reintenta (D-07.1 respetado
  — el raise es al final, no en el punto de fallo, precisamente para no
  reintentar y sí reportar). **Veredicto: cumple.**

**Asimetrías vs. otras tools:** es la única W-COMPOSITE con reload propio
y con stitching automático (F-D5-01, D-32d.1) — extensión legítima, no
asimetría (documentada en el ADR mismo como "extiende, no reabre" D-23.2).

**Precedentes Fase 4:** F-D4-02 (sesión 23-24, causa raíz de ADR-0012),
F-V2-REFILL-SILENCIOSO (32b), F-D5-01 (32c/32d).

**Recomendación:** correcta por diseño. Contrato más maduro de la
superficie — referencia para las demás.

---

#### Tool: `fill_zones`

**Ubicación:** `pcb.py:2628-2721`. **ADRs:** ADR-0012 (extensión sesión 27).

- **Eje 1:** `refill_zones()` (línea 2660) + `enforce_hole_clearance()`
  **incondicional** (línea 2663, corre aun con `zones_filled==0` — comentario
  explícito: puede tocar keepouts) + `save_board()` **incondicional** (línea
  2671). *Refutación:* ¿puede reportar éxito sin persistir? No — el
  `save_board()` no tiene guard condicional (a diferencia de `route_board`,
  que sí depende de `reloaded is True`). **Veredicto: cumple**, y de forma
  más estricta que `route_board` (sin condición de reload previa).
- **Eje 2:** `ZONE_ID_STALE` (id inexistente), `POST_ZONE_PERSIST_FAILED`
  (save falla). *Refutación:* ¿el catch de `save_board()` pierde
  información? No — re-envuelve con `data.live_has_fix: True`, mismo
  patrón que `POST_ROUTE_PERSIST_FAILED`. **Veredicto: cumple.** Test:
  `tests/test_pcb_zones.py::test_fill_zones_persist_failed`.
- **Eje 3:** `_guard_live_stale()` (línea 2638) + `check_no_external_disk_edit`
  (línea 2639) al inicio. **Veredicto: cumple.**
- **Eje 4 (N/A):** no invoca `reload_board_from_disk` — ADR-0012 lo
  documenta explícitamente: "abren con `_guard_live_stale()`... no existe
  la llamada cuya excepción se pudiera descartar en silencio" — el
  guard de entrada reemplaza la necesidad de reload.

**Asimetrías vs. `route_board`:** ninguna estructural. `fill_zones` no
tiene el condicional `reloaded is True` porque no necesita reload (opera
directo sobre el vivo, protegido por el guard de entrada) — diseño más
simple, mismo contrato satisfecho.

**Recomendación:** correcta por diseño.

---

#### Tool: `add_zone` (fill=True) — W-COMPOSITE

**Ubicación:** `pcb.py:2338-2460`, rama `if fill:` (líneas 2404-2436).

- **Eje 1:** `enforce_hole_clearance()` (2409) + `save_board()` (2415)
  dentro de `if fill:`. **Veredicto: cumple**, idéntico patrón a
  `fill_zones`.
- **Eje 2:** `POST_ZONE_PERSIST_FAILED` (mismo código que `fill_zones`,
  decisión deliberada de ADR-0012: "semánticamente equivalentes... se
  discriminan por origen del llamador, no por semántica de código").
  **Veredicto: cumple.** Test:
  `tests/test_pcb_zones.py::test_add_zone_fill_true_persist_failed`.
- **Eje 3:** guard + check al inicio (2358-2361). **Veredicto: cumple.**
- **Eje 4 (N/A):** mismo razonamiento que `fill_zones`.

**Recomendación:** correcta por diseño.

---

### W-IPC — hallazgo 32b y vecinas de zonas (foco de asimetrías)

#### Tool: `add_zone` (fill=False) — W-IPC

**Ubicación:** `pcb.py:2437-2439` (rama `else:`).

- **Eje 1:** `mtimes=None`, sin `save_board()`. **Veredicto: cumple con
  matiz — por diseño explícito.** ADR-0012 es taxativo: *"`add_zone(fill=false)`
  queda fuera por diseño — sin fill no hay refill+enforce que persistir,
  ni bug conceptual que cerrar"* — es la única tool de la matriz cuya
  exclusión del contrato D-23.2 está **documentada en el ADR mismo**, no
  inferida por esta auditoría.
- **Eje 2/3:** idénticos a la rama `fill=True` (comparten el mismo bloque
  de validación previo). **Veredicto: cumple.**
- **Eje 4:** N/A.

**Recomendación:** correcta por diseño, ya documentada.

---

#### Tool: `delete_tracks_bulk`

**Ubicación:** `pcb.py:1939-2068`. **Hallazgo previo:** sesión 32b,
`docs/BACKLOG.md:622`.

- **Eje 1 — Persistencia:** llama `bridge.refill_zones(board)` (línea
  2039) cuando el borrado toca una zona de cobre, pero **sin**
  `enforce_hole_clearance()` **ni** `save_board()` posteriores.
  *Refutación de "cumple":* el propio docstring de `enforce_hole_clearance`
  (`ipc.py:2016`, citado en `_refill_enforce_and_save`) dice **"Llamar
  SIEMPRE inmediatamente después de `refill_zones()`"** — `delete_tracks_bulk`
  viola esa invariante directamente. Y sin `save_board()`, el fill nuevo
  vive solo en memoria: un DRC por `kicad-cli` inmediato (que lee de
  disco) NO reflejaría el refill que el payload reporta
  (`zones_refilled: 1`). **Veredicto: NO CUMPLE — asimetría A1,
  confirmada** (no sólo observada como en 32b, sino verificada contra el
  contrato exacto que rompe). Cobertura de test:
  `tests/test_pcb_zones.py` no cubre este camino;
  `tests/test_pcb_delete_bulk.py::test_delete_tracks_bulk_refills_zones_when_copper_zone_present`
  sólo asegura `zones_refilled == 1` y `bridge.refill_calls == 1` — **no
  hay ninguna assertion de `save_board()` ni de `enforce_hole_clearance()`
  llamados**, lo cual es evidencia adicional (el test documenta el
  comportamiento actual, no lo objeta).
- **Eje 2 — Errores:** sin código específico para el fallo de refill —
  si `refill_zones()` lanza, se propaga tal cual (sin taxonomía dedicada,
  a diferencia de `POST_ZONE_PERSIST_FAILED`). **Veredicto: cumple con
  matiz** (propaga, pero sin el diagnóstico rico de las W-COMPOSITE).
- **Eje 3:** `_guard_live_stale()` + `check_no_external_disk_edit()` al
  inicio (líneas 2024-2027). **Veredicto: cumple.**
- **Eje 4:** N/A (sin reload).

**Impacto funcional concreto:** un agente que borra tracks sobre una zona
GND, ve `zones_refilled: 1` en la respuesta, y confía en que el clearance
está arreglado — pero (a) el clearance contra holes puede seguir roto
(F-D3-01 sin su workaround), y (b) el disco nunca se actualizó, así que un
`run_drc()` inmediato mide el estado viejo. Es el mismo bug conceptual que
F-D4-02 (sesión 23-24), sin cerrar para esta tool.

**Recomendación:** **fix agendado, no trivial** — requiere: (a) decidir si
`delete_tracks_bulk` entra al alcance de ADR-0012 (extensión de contrato,
ADR obligatorio per DoD #4), (b) reusar `_refill_enforce_and_save` en vez
de la llamada inline a `refill_zones`, (c) test de regresión GUI (D-23.2
es gate del merge para tools que tocan zonas/keepouts/route). Ver §5,
`34a-fix-1`.

---

#### Tool: `delete_zone`

**Ubicación:** `pcb.py:2727-2775`.

**Hipótesis:** cumple el mismo modelo de las demás W-IPC de zonas.
**Refutación:** borra una zona de **cobre** (`item.kind` puede ser
`"copper"`) sin refill ni save posteriores (líneas 2746-2761, borrado +
`store.register(..., mtimes=None)` directo). Si el board tiene zonas de
cobre vecinas cuyo fill dependía del outline de la zona borrada (prioridad,
solapamiento), esas zonas vecinas quedan con un fill potencialmente
obsoleto en el vivo — y el disco ni siquiera refleja el borrado.

- **Eje 1: NO CUMPLE — asimetría A2 (nueva, hallazgo de esta auditoría).**
  Mismo patrón de riesgo que A1: sin `save_board()`, el borrado de zona
  vive solo en memoria. A diferencia de `delete_tracks_bulk`, `delete_zone`
  ni siquiera intenta un refill — es la asimetría más simple y más severa
  de la familia "borrado sin persistir" en el pipeline de zonas.
- **Eje 2:** `ZONE_ID_STALE` (id inexistente/borrado concurrente).
  **Veredicto: cumple** para el caso feliz de identificación de target;
  no hay código para "borré la zona pero el fill vecino puede estar sucio"
  porque la tool no lo detecta ni lo intenta.
- **Eje 3:** guard + check al inicio. **Veredicto: cumple.**
- **Eje 4:** N/A.

**Precedente:** ninguno documentado — no aparece en el BACKLOG previo a
esta auditoría. Es hallazgo nuevo de sesión 34a.

**Recomendación:** **documentar como limitación conocida** en esta pasada
(severidad P2 — no hay evidencia empírica de un DRC roto real, a
diferencia de A1 que sí tiene precedente F-D3-01). Candidato a
`34a-fix-2` si aparece evidencia de impacto real (patrón "investigación
antes de fix", D-32c.1/D-30.1 — no se especula un mecanismo sin
reproducirlo).

---

#### Tool: `add_keepout_zone`

**Ubicación:** `pcb.py:2466-2543`.

**Hipótesis:** como crea un keepout con `no_pours=True` (default
implícito en muchos usos), debería re-recortar los fills existentes que
ahora invaden el área prohibida — igual que `enforce_hole_clearance` hace
para holes.

**Refutación:** inspección de `bridge.add_keepout_zone` (`ipc.py`, zona de
creación de keepouts) muestra que la tool **no** dispara ningún refill
interno — a diferencia de `bridge.add_zone(..., fill=True)`
(`ipc.py:1918`, que sí llama `raw_board.refill_zones()` internamente
cuando corresponde). El código de `pcb.py:2496-2516` va directo de
`bridge.add_keepout_zone(...)` a `store.register(..., mtimes=None)`, sin
refill/enforce/save.

- **Eje 1: NO CUMPLE — asimetría A3 (nueva).** Un fill existente que ahora
  invade el keepout recién creado no se recorta hasta la próxima llamada
  manual a `fill_zones()`. El vivo queda en un estado geométricamente
  inconsistente con las reglas que el propio keepout declara
  (`no_pours`), y el disco nunca ve ni el keepout ni el estado inconsistente.
- **Eje 2:** sin código específico para "keepout creado pero fills
  vecinos no recortados" — no hay detección, por lo tanto no hay taxonomía
  que la cubra. **Veredicto: N/A** (no hay error porque no hay detección,
  no porque el caso esté resuelto).
- **Eje 3:** guard + check presentes. **Veredicto: cumple.**
- **Eje 4:** N/A.

**Diferencia con A1/A2:** A3 es la más "por diseño" de las tres — un
keepout recién creado sin fill previo dentro de su área simplemente no
tiene nada que recortar (caso común: keepouts se crean antes de rutear).
El riesgo real es acotado a "keepout agregado DESPUÉS de un fill existente
que lo invade", un orden de operaciones menos común pero no imposible
(ej. ajuste post-hoc de zona de exclusión).

**Recomendación:** **documentar como limitación conocida**, severidad P3
(sin evidencia de impacto en dogfooding/Validation Suite hasta ahora — a
diferencia de A1, que tiene precedente F-D3-01 directo).

---

### W-IPC — Fase 4 (nuevas)

#### Tool: `set_footprint_ref`

**Ubicación:** `pcb.py:1124-1243`. **ADR:** ADR-0013.

- **Eje 1:** `mtimes=None`, sin save (línea 1228). **Veredicto: cumple con
  matiz — por diseño**, mismo criterio D-14.3 que el resto de W-IPC. No
  hay mención específica en ADR-0013 de que deba auto-persistir — el ADR
  se centra en la semántica de escritura kipy (property setter sin copia,
  hallazgo de sesión 31b), no en persistencia.
- **Eje 2:** `COMPONENT_NOT_FOUND`, `INVALID_PARAMS` (ref no duplicado),
  `DUPLICATE_REFS` (ambigüedad de kiid). **Veredicto: cumple** — mismo
  patrón "nunca resolver a ciegas" que `_delete_copper`.
- **Eje 3:** guard + check al inicio (1142-1145). **Veredicto: cumple.**
- **Eje 4:** N/A.

**Precedente Fase 4:** único caso confirmado de F-V3 (`docs/historico/sesiones/33-reporte.md:105-107`,
"Mutadores IPC no auto-persisten a disco (`set_footprint_ref`,
`move_footprint` vía script)") donde el comportamiento por-diseño
sorprendió al agente ejecutando la Suite. No es un bug — es evidencia de
que el matiz de Eje 1 necesita mejor visibilidad (ver A6).

**Recomendación:** correcta por diseño; candidata a la mejora de mensaje
de A6.

---

### W-IPC — históricas

#### Tool: `move_footprint`

**Ubicación:** `pcb.py:1012-1115`.

- **Eje 1:** `mtimes=None` (1088). **Veredicto: C-m, por diseño** (D-14.3).
- **Eje 2:** `COMPONENT_NOT_FOUND`, `INVALID_PARAMS` (fuera de bbox).
  **Veredicto: cumple.**
- **Eje 3:** `_guard_live_stale()` al inicio (1014) — nota: **no** llama
  `check_no_external_disk_edit()` (P3.2), a diferencia de `add_track`,
  `add_via`, `set_footprint_ref`, `delete_tracks_bulk`. *Refutación
  parcial:* ¿esto es un hueco de seguridad? Inspección de
  `check_no_external_disk_edit`: es una red adicional independiente de
  `base_snap` contra ediciones externas concurrentes del archivo. Su
  ausencia en `move_footprint` es una inconsistencia menor (P3), no un
  hueco crítico — `_guard_live_stale()` sigue cubriendo el caso principal
  (ruteo pendiente de recarga). **Veredicto: cumple con matiz** (falta de
  uniformidad, no de protección).
- **Eje 4:** N/A.

**Recomendación:** P3, deuda cosmética — unificar la llamada a
`check_no_external_disk_edit()` en `move_footprint` para consistencia con
sus pares. Es un candidato de la misma familia que A7 (guard faltante) y
probablemente igual de trivial de resolver y verificar offline — pero
severidad menor (`_guard_live_stale()` ya cubre el caso principal, esto
sólo agrega la red P3.2). No se aplicó en el Bloque 3 de esta sesión por
foco: el tiempo se priorizó en A7 (P1, sin protección alguna) sobre este
caso (P3, protección parcial ya presente). Queda anotado en el BACKLOG
para una futura pasada de limpieza de consistencia, no amerita sesión
propia.

---

#### Tool: `add_track`

**Ubicación:** `pcb.py:1249-1421`.

- **Eje 1:** `mtimes=None` (1391). **Veredicto: C-m, por diseño.**
- **Eje 2:** `NET_NOT_FOUND`, `INVALID_PARAMS` (bbox, colisión con pad
  ajeno — `_find_track_pad_collision`, clearance real de netclass).
  **Veredicto: cumple** — el más rico en validación previa a mutar de toda
  la familia W-IPC.
- **Eje 3:** guard + check (1262-1265). **Veredicto: cumple.**
- **Eje 4:** N/A.

**Recomendación:** correcta por diseño, referencia de buena práctica
(validación de colisión antes de mutar) para tools W-IPC futuras.

---

#### Tool: `add_via`

**Ubicación:** `pcb.py:1427-1540`.

- **Eje 1:** `mtimes=None` (1513). **Veredicto: C-m, por diseño.**
- **Eje 2:** `NET_NOT_FOUND`, `INVALID_PARAMS` (bbox, drill≥size).
  **Veredicto: cumple.**
- **Eje 3:** guard + check (1443-1446). **Veredicto: cumple.**
- **Eje 4:** N/A.

**Nota:** docstring inline documenta explícitamente D-07.1 ("No hay retry
en la escritura... `add_via` viaja por `_supervise` directo en el
bridge") — ejemplo de la declaración explícita que A6 pide generalizar.

**Recomendación:** correcta por diseño.

---

#### Tool: `draw_board_outline`

**Ubicación:** `pcb.py:2252-2332`.

**Hipótesis:** cumple el mismo patrón de guards que el resto de W-IPC.

**Refutación — CONFIRMADA, asimetría nueva (A7):** verificado por
`grep`/lectura línea por línea del cuerpo completo de la tool — **no
llama `_guard_live_stale()` ni `check_no_external_disk_edit()`**, a
diferencia de las otras 9 tools W-IPC de PCB. Es la única mutación de PCB
de la superficie completa sin ninguno de los dos guards de sincronía.

- **Eje 1:** `mtimes=None` (2314). **Veredicto: C-m, por diseño**, igual
  que el resto.
- **Eje 2:** `INVALID_PARAMS` (dimensiones ≤0, fuera de rango, contorno ya
  existente). **Veredicto: cumple** para su propio dominio de errores.
- **Eje 3 — NO CUMPLE.** Sin `_guard_live_stale()`: si el disco tiene un
  ruteo de `route_board` pendiente de recarga (`live_stale=True`), esta
  tool mutaría el vivo desactualizado igual — exactamente el escenario que
  D-14.1 existe para prevenir en todas sus pares. Sin
  `check_no_external_disk_edit()`: sin la red P3.2 contra ediciones
  externas concurrentes.
- **Eje 4:** N/A.

**Por qué probablemente pasó desapercibido:** `draw_board_outline` se usa
casi siempre **al principio** del flujo de un proyecto nuevo (antes de que
exista ruteo o zonas que puedan quedar `live_stale`), así que la ventana
de riesgo real es angosta en el uso típico — pero el código no la excluye
estructuralmente. El comentario inline de la tool ("el contorno no vive en
NormalizedState... El loop cierra con save_board") sugiere que el autor
original asumió un flujo de uso donde el guard era innecesario, sin
codificarlo como precondición.

**Impacto funcional concreto:** agente que rutea (`route_board`, deja
`live_stale=True` porque el editor no pudo recargar) y luego, sin darse
cuenta, llama `draw_board_outline` para ajustar el contorno — la mutación
pasa sin rechazo, y un `save_board()` posterior (que sí tiene el guard)
recién ahí lo bloquearía, pero el vivo ya quedó mutado con el contorno
nuevo sobre una base desactualizada.

**Recomendación / resolución:** **fix trivial aplicado en Bloque 3 de esta
sesión** (`src/kicad_mcp/tools/pcb.py`, +6 líneas efectivas incluyendo el
comentario de atribución). Calificó bajo los 5 criterios estrictos: (1)
trivial, 2 líneas de guard; (2) bajo riesgo, no toca zonas/keepouts/route;
(3) sin dependencias arquitectónicas, aplica D-14.1/P3.2 ya existentes sin
tocar ningún ADR; (4) verificable **sin fixtures nuevos** — el patrón de
rechazo offline ya existe en el repo (`get_default_store().mark_live_stale(1)`,
`tests/test_reload_board.py:103`; edición externa simulada con
`os.utime`, `tests/test_pcb_session11.py:341-374`) y se replicó tal cual
en `tests/test_pcb.py` (`test_draw_board_outline_rejects_when_live_stale`,
`test_draw_board_outline_rejects_external_disk_edit`); (5) cross-check
ADR OK, D-14.1 es exactamente lo que se aplica, sin conflicto.

**Verificación ejecutada:** las 5 tests de `draw_board_outline` en
`tests/test_pcb.py` (3 preexistentes + 2 nuevas) pasan; suite offline
completa (`pytest -m "not integration"`) 394 passed / 0 failed; `ruff
check` y `mypy src/` limpios.

**Verificación NO ejecutada, con motivo documentado:** existe un test
`integration_gui` específico para esta tool
(`tests/test_pcb.py::test_draw_board_outline_tool_rejects_existing_outline_on_real_board`,
protocolo manual per `docs/guias/pruebas-gui.md`) que este fix no gatilla
como obligatorio del DoD — el gate GUI es mandatorio para cambios que
tocan el pipeline de zonas/keepouts/route (DoD #2), y este fix no lo toca
(agrega un guard de sincronía preexistente, sin cambiar la lógica de
creación del outline). Se dejó sin correr además porque el único KiCad
vivo disponible en esta sesión tiene abierto el board real de HackRF One
(ver §4) — ejecutar un test GUI ahí, aunque de bajo riesgo por diseño del
propio test, se evitó por el mismo criterio de no experimentar contra ese
proyecto sin necesidad. Queda pendiente de ejecución humana antes del
release, mismo patrón que otras verificaciones GUI diferidas en Fase 4
(sesión 32d).

---

### Infraestructura del contrato

#### Tool: `save_board`

**Ubicación:** `pcb.py:1546-1586`.

- **Eje 1:** ES el mecanismo de persistencia — `bridge.save_board(board)`
  (1562), snapshot de **disco** con mtimes frescos (no `mtimes=None`,
  1566-1567, "patrón sch de D-08.5"). **Veredicto: cumple**, es la
  referencia.
- **Eje 2:** sin código propio — un fallo de `bridge.save_board()` se
  propaga tal cual (comentario inline: "busy → se propaga tal cual").
  **Veredicto: cumple con matiz** — decisión consciente y documentada, no
  omisión.
- **Eje 3:** `_guard_live_stale()` + check (1553-1556). **Veredicto:
  cumple.**
- **Eje 4:** N/A (es la contraparte de reload, no lo invoca).

**Recomendación:** correcta por diseño.

---

#### Tool: `reload_board_from_disk`

**Ubicación:** `pcb.py:1595-1651`.

- **Eje 1:** N/A (no persiste, re-lee).
- **Eje 2:** remapea sólo `PROJECT_NOT_FOUND` → `RELOAD_FAILED` (editor no
  abierto); el resto de fallos IPC se propaga sin reenvolver "para no
  perder esa señal" (comentario inline). **Veredicto: cumple** — el
  criterio de qué remapear y qué no está justificado explícitamente en el
  código, no es arbitrario.
- **Eje 3:** `store.clear_live_stale()` (1631) — **es** el mecanismo que
  destraba el guard de las demás. **Veredicto: cumple.**
- **Eje 4:** N/A (es la tool, no la usa). Deliberadamente **no** pasa por
  `_guard_live_stale()` — docstring lo explicita: "esta tool es
  precisamente el mecanismo que lo destraba". Nota importante para
  `route_board`: cuando ESTA tool falla dentro del pipeline de
  `route_board` (línea 2917-2921), la excepción real es la que
  `POST_ROUTE_REFILL_SKIPPED` diagnostica — la tool en sí misma no tiene
  retry (D-07.1) cuando se invoca standalone tampoco.

**Recomendación:** correcta por diseño.

---

### W-SKIP (esquemático — arquitectura legítimamente distinta)

**Contexto compartido de las 4 tools:** KiCad 10 no expone IPC de
esquemático (D-08.5) — la escritura es directa a disco vía `kicad-skip`
(parseo/serialización de S-expr), no hay "vivo" IPC que sincronizar. El
patrón compartido: pre-estado derivado localmente (`build_state_cached`)
→ Gate G1 (`ensure_session_backup`) → escritura a disco → verificación del
efecto releyendo el archivo escrito (D-06.3) → snapshot con
`collect_project_mtimes()` **frescos** (nunca `mtimes=None` — D-08.5 #4).

#### Tool: `add_symbol`

**Ubicación:** `sch.py:848-996`.

- **Eje 1:** escritura directa (`_add_symbol_to_sheet`/`_add_symbol_cross_file`)
  + verificación por relectura (`_verify_effect`, 947) + mtimes frescos
  (964-965). **Veredicto: cumple** — el eje "persistencia" para W-SKIP
  ES la escritura misma, no hay estado "vivo" intermedio que perder.
- **Eje 2:** `INVALID_PARAMS` (ref inválido, coords fuera de bbox de
  hoja, ref duplicado en proyecto), errores de `_resolve_source`/`_find_template`
  propagados. **Veredicto: cumple.**
- **Eje 3:** `validate_base_snap()` si corresponde; no hay guard
  `_guard_live_stale()` porque no aplica (sin IPC, sin concepto de "vivo
  desactualizado"). **Veredicto: cumple** (eje satisfecho por ausencia
  estructural de la condición que motiva el guard en PCB).
- **Eje 4:** N/A por diseño arquitectónico (D-08.5).

**Recomendación:** correcta por diseño — la arquitectura W-SKIP entera es
una decisión legítima, no una asimetría respecto a W-IPC/W-COMPOSITE.

---

#### Tool: `set_value` / `set_footprint` (núcleo compartido `_set_property_core`)

**Ubicación:** `sch.py:998-1103` (núcleo), `1063-1103` (`set_value`),
`1105-1152` (`set_footprint`, no leída línea por línea pero comparte
`_set_property_core` verificado).

- **Eje 1:** `_set_symbol_property()` + `_verify_property()` (D-06.3) +
  mtimes frescos (1041-1042). **Veredicto: cumple**, mismo patrón que
  `add_symbol`.
- **Eje 2:** `COMPONENT_NOT_FOUND` (ref no existe, con similares),
  `INVALID_PARAMS` (`_validate_value`). **Veredicto: cumple.**
- **Eje 3:** `validate_base_snap()`. **Veredicto: cumple.**
- **Eje 4:** N/A.

**Recomendación:** correcta por diseño. El núcleo compartido
(`_set_property_core`) es exactamente el tipo de unificación que A4 pide
para el lado PCB (`_refill_enforce_and_save`) — W-SKIP ya lo tiene
resuelto para su propio dominio.

---

#### Tool: `connect_pins`

**Ubicación:** `sch.py:1157-1258`.

- **Eje 1:** `_place_labels_on_sheet()` + `_verify_labels()` + mtimes
  frescos (1230-1231). **Veredicto: cumple.**
- **Eje 2:** `COMPONENT_NOT_FOUND`, `INVALID_PARAMS` (mismo pin dos veces,
  hojas distintas — labels locales tienen scope de hoja). **Veredicto:
  cumple.**
- **Eje 3:** `validate_base_snap()`. **Veredicto: cumple.**
- **Eje 4:** N/A.

**Recomendación:** correcta por diseño.

---

## §4 — F-V3-ZONE-FILL-CRASH: clasificación acotada

**Alcance ejecutado:** harness sintético + análisis de código (sin bajar
HackRF One), por decisión del arquitecto pre-Bloque 2.

**Hipótesis (D-33.1):** F-V3-ZONE-FILL-CRASH es bug de motor externo
(pcbnew/kipy 0.7.1), no asimetría contractual del bridge.

**Refutación buscada:** un orden de operaciones IPC en `add_zone`/
`bridge.add_zone` que deje a pcbnew en estado inconsistente antes de la
llamada siguiente.

### Análisis de código (completado)

`add_zone(fill=True)` (`pcb.py:2396-2436`) ejecuta, por llamada:
`bridge.add_zone(..., fill=True)` → dentro del bridge
(`ipc.py:1887-1918`), crea la zona y, si `fill`, llama
`raw_board.refill_zones()` (el fill **interno** de kipy, primera pasada) →
de vuelta en `pcb.py`, `bridge.enforce_hole_clearance()` (que internamente
vuelve a tocar keepouts, línea `ipc.py:2053`) → `bridge.save_board()`.
**Cada llamada a `add_zone(fill=True)` dispara 2 fills completos de TODAS
las zonas del board** (uno interno del bridge en la creación, más lo que
`enforce_hole_clearance` pueda re-tocar) — no sólo de la zona nueva. Sobre
un board de 437 footprints / 4 capas (HackRF One), esto es
computacionalmente pesado pero no evidencia, por sí sola, un bug del
bridge: es el mismo patrón que `fill_zones` (siempre refillea TODO, kipy
0.7.1 no tiene fill selectivo, `docs/investigacion/19-zonas-ipc.md §1/§3`)
y `fill_zones` no tiene reportes de crash en la Validation Suite.

**La firma diagnóstica de sesión 33** (710 zonas en disco: 3 reales + 707
fragmentos sin net, esparcidos en las 2 capas internas, tras cada intento
fallido) es la pista más fuerte: fragmentación masiva de zonas sin net es
consistente con un fill de pcbnew que fragmenta polígonos internamente
durante el cálculo (comportamiento documentado de KiCad al toparse con
geometría compleja/self-intersecting derivada, no con una operación del
bridge que "corte" zonas — el bridge nunca fragmenta zonas, sólo crea
(`add_zone`) o borra (`delete_zone`) zonas completas).

### Harness sintético — bloqueado por restricción de entorno no anticipada

El plan asumía poder sintetizar un board mínimo y ejecutar `add_zone(fill=true)`
contra él, evitando explícitamente reabrir el board real de HackRF One.
Verificado al llegar a este bloque (`health()` + inspección de
`/proc/<pid>/environ` del proceso del servidor MCP): el PCB Editor de
KiCad, corriendo en esta sesión, tiene **abierto exactamente el proyecto
`validation-suite/level-c/hackrf-one/working`** — el mismo board de 437
footprints que crasheó 3/3 veces en sesión 33 — porque `KICAD_MCP_PROJECT`
quedó fijado a esa ruta desde entonces.

La superficie de tools disponible no incluye ningún mecanismo para abrir
un proyecto distinto en el PCB Editor vivo (`reload_board_from_disk`
re-lee el **mismo** archivo ya abierto, no cambia de proyecto; no hay
`open_project`). Sintetizar y ejercer un board nuevo habría requerido
either (a) operar la GUI de KiCad directamente para abrir otro archivo —
fuera de la superficie de herramientas de esta sesión — o (b) ejecutar el
harness igual contra el board de HackRF ya abierto, que es exactamente el
escenario de riesgo que la opción "harness sintético, sin bajar HackRF
One" fue elegida para evitar (arriesgar el crash real contra el proyecto
que ya lo disparó 3 veces, en lugar de un board descartable). Se optó por
**no ejecutar el harness en vivo** en vez de tomar ese riesgo sin
consultarlo — mismo criterio que el resto de la sesión: ante una premisa
del plan que no se sostiene al verificarla, corregir y documentar en vez
de forzar.

### Clasificación

**No concluyente — limitado a análisis de código, sin repro empírica esta
sesión.** El análisis de código (arriba) no encontró, del lado del bridge,
ningún camino que **cause** el estado inconsistente: el orden
refill→enforce→save de `add_zone(fill=true)` es el mismo patrón que
`fill_zones`/`route_board`, sin reportes de crash análogos en esas dos. La
refutación de "es bug del bridge" no prosperó por esa vía — pero tampoco
hay una reproducción positiva que confirme "es motor externo puro" con
certeza, sólo la ausencia de causa identificable del lado del bridge más
la correlación con escala ya documentada en sesión 33 (710 zonas
fragmentadas, patrón consistente con un fill de pcbnew fragmentando
geometría compleja internamente, no con una operación del bridge que
"corte" zonas).

**Gate del Bloque 2 aplicado:** "si la reproducción con harness minimal no
funciona → clasificar como 'no concluyente' y documentar como limitación
conocida... sin promover a investigación propia." Se aplica — con la
salvedad honesta de que "no funciona" acá es "no se pudo ejecutar sin
asumir el riesgo que la opción elegida buscaba evitar", no "se ejecutó y
no reprodujo". Repro real queda condicionada a que una sesión futura
decida asumir ese riesgo deliberadamente (reabrir HackRF One a propósito)
o a que aparezca un mecanismo para levantar un proyecto sintético sin
tocar el editor ya abierto.

**Documentado en `docs/BACKLOG.md`** (actualización §5) como: *"No
concluyente tras auditoría 34a — sin causa identificada del lado del
bridge (mismo patrón refill+enforce+save que `fill_zones`, sin crashes
reportados); orientativamente compatible con bug de fragmentación de
pcbnew a escala, sin confirmación positiva. Repro fiel contra HackRF One
o un board sintético de escala equivalente queda para investigación
propia si reaparece antes del release."*

---

## §5 — Síntesis

### §5.1 — Tabla comparativa por categoría

**W-COMPOSITE (3 entradas):** las tres cumplen los 4 ejes de forma
uniforme. `route_board` es estructuralmente más compleja (reload propio,
stitching) pero la complejidad extiende el contrato sin romperlo — la
extensión está documentada en el ADR mismo en cada paso. **Categoría más
consistente de la superficie.**

**W-IPC (11 entradas):** consistentes en Eje 1 (todas `mtimes=None` por
diseño, D-14.3) y, tras el fix de A7 en esta sesión, también en Eje 3
(11/11 con guard+check — `draw_board_outline` era la única excepción).
**Inconsistentes en el eje que W-IPC comparte parcialmente con
W-COMPOSITE**: 3 de las 11 (`delete_tracks_bulk`, `delete_zone`,
`add_keepout_zone`) mutan geometría que interactúa con zonas de cobre
existentes sin aplicar ningún tramo del pipeline refill+enforce+save —
mientras que las 8 restantes correctamente no lo necesitan (no tocan
zonas). La inconsistencia no es "W-IPC vs W-COMPOSITE" en general, es
específica al subconjunto que toca zonas.

**W-SKIP (4 entradas):** perfectamente uniformes entre sí (núcleo
compartido `_set_property_core` para 2 de las 4). Arquitectura
legítimamente distinta de W-IPC/W-COMPOSITE (sin IPC, D-08.5) — **no es
una asimetría del proyecto**, es una decisión de plataforma (KiCad 10 no
expone IPC de esquemático).

### §5.2 — Asimetrías clasificadas por severidad

| ID | Tool(s) | Descripción | Severidad | Recomendación |
|---|---|---|---|---|
| A1 | `delete_tracks_bulk` | Refill sin enforce ni save — clearance puede quedar roto, disco no refleja el refill reportado | **P1** | Fix agendado (`34a-fix-1`), extensión de ADR-0012 |
| A7 | `draw_board_outline` | Única W-IPC sin `_guard_live_stale()` ni `check_no_external_disk_edit()` | **P1** | **Fixed en esta sesión** (Bloque 3) — GUI verification pendiente de ejecución humana |
| A2 | `delete_zone` | Borra zona de cobre sin refill/save — fills vecinos no recalculados, sin precedente empírico | P2 | Documentar como limitación conocida |
| A3 | `add_keepout_zone` | Keepout nuevo no recorta fills existentes que invade — orden de uso típico lo mitiga | P2 | Documentar como limitación conocida |
| A6 | 6 tools W-IPC | Ninguna declara en su propia respuesta que la mutación no persiste a disco (D-14.3 correcto, pero implícito) | P2 | Mejora de mensaje/documentación, no de código — input directo para CONTRIBUTING |
| A4 | `add_zone`/`fill_zones` vs. `route_board` | Secuencia refill+enforce+save duplicada inline en vez de reusar `_refill_enforce_and_save` | P3 | Deuda post-release — refactor sin cambio de comportamiento |
| Move-P3.2 | `move_footprint` | Sin `check_no_external_disk_edit()`, a diferencia de sus pares W-IPC | P3 | Deuda post-release |
| F-V3 | `add_zone(fill=true)` a escala | No concluyente — ver §4 | — | Documentado como limitación; investigación propia si reaparece |

**A5 refutada explícitamente** (no es asimetría): sólo `route_board`
invoca reload y sólo él necesita `POST_ROUTE_REFILL_SKIPPED` — ADR-0012 ya
documenta, con evidencia de inspección, que `fill_zones`/`add_zone` no
tienen el camino silencioso porque no llaman `reload_board_from_disk` en
absoluto. Confirmado en esta auditoría por lectura directa de ambos
cuerpos (§3).

### §5.3 — Sesiones futuras agendadas (hipótesis completas)

**`34a-fix-1` — `delete_tracks_bulk` respeta D-23.2 sobre zonas tocadas.**
Hipótesis: reemplazar la llamada inline a `bridge.refill_zones(board)`
(línea 2039) por `_refill_enforce_and_save(bridge, board, pcb_path, root,
params, context="borrado bulk")`, con manejo de
`POST_ROUTE_PERSIST_FAILED` o código nuevo equivalente
(`POST_BULK_DELETE_PERSIST_FAILED`, adición pura F1/F3). Requiere: (a)
decisión del arquitecto sobre si extiende ADR-0012 formalmente o registra
un ADR nuevo acotado; (b) test de regresión con zona de cobre real +
verificación de disco post-save; (c) gate GUI del DoD (toca pipeline de
zonas).

**`34a-fix-2` (condicional) — `delete_zone` sobre zonas de cobre con
vecinas.** Sólo si aparece evidencia empírica de fill vecino roto
(patrón "investigación antes de fix", D-30.1/D-32c.1) — no se agenda como
fix ciego. Documentar primero como limitación (§5.2), promover a
investigación si la Validation Suite lo evidencia.

**`34a-fix-3` (cerrada, no queda agendada) — `draw_board_outline` agrega
los guards D-14.1/P3.2.** Resuelta en Bloque 3 de esta misma sesión (ver
ficha de la tool en §3): el caso de prueba realista SÍ resultó cubrible
offline (`mark_live_stale(1)` directo sobre el store, patrón ya usado en
`test_reload_board.py`), sin necesitar un board GUI real — la suposición
inicial de que requería GUI fue una sobre-estimación del riesgo,
corregida al verificar el patrón de test existente antes de descartar el
fix. Único pendiente: la ejecución humana del test `integration_gui`
específico de la tool antes del release (no gate del DoD para este
cambio, ver ficha).

### §5.4 — D-34a.1 y convención de los 4 ejes

Ver `docs/DECISIONES.md` para el texto formal. Resumen: los 4 ejes
(persistencia / propagación de errores / sincronización disco↔memoria /
manejo de reload) se adoptan como checklist estándar para: (a) auditorías
futuras de la superficie de escritura, (b) revisión de toda tool de
escritura nueva antes de merge, (c) input directo para
`CONTRIBUTING.md §How to add a write tool`.

**Aprendizaje metodológico:** los 4 ejes, tal como los formuló el
arquitecto, resultaron **suficientes** para esta auditoría — no
requirieron refinamiento. La única ambigüedad operacional encontrada fue
qué hacer con Eje 1 cuando la tool nunca persiste por diseño (D-14.3): se
resolvió con el veredicto "cumple con matiz — por diseño", distinto de
"no cumple", y esa distinción resultó necesaria para no sobre-reportar
asimetrías donde no las hay (6 de las 11 W-IPC caen en esa categoría, y
ninguna es un problema real).

---

## §6 — Input consolidado para CONTRIBUTING y README (34b/34c)

### Para README §"Known limitations"

- Las mutaciones W-IPC (`add_track`, `add_via`, `move_footprint`,
  `set_footprint_ref`, etc.) **no persisten a disco automáticamente** —
  llamar `save_board()` explícitamente para bajar el estado vivo a disco.
  Sólo `route_board`, `fill_zones` y `add_zone(fill=true)` garantizan
  disco==memoria al terminar (contrato D-23.2/ADR-0012).
- `delete_tracks_bulk` sobre zonas de cobre refilla en memoria pero no
  persiste ni corrige clearance contra holes — llamar `fill_zones()`
  después si el borrado tocó zonas.
- `delete_zone`/`add_keepout_zone` no recalculan fills vecinos
  automáticamente — llamar `fill_zones()` tras cualquier cambio de
  geometría de zonas/keepouts si hay zonas de cobre cercanas.
- `add_zone(fill=true)` puede crashear KiCad en boards muy grandes
  (400+ footprints, 4+ capas) tras 3-4 llamadas consecutivas — causa no
  concluyente (ver `docs/BACKLOG.md`), mitigación: espaciar llamadas o
  usar `fill_zones()` una sola vez al final en vez de `fill=true` por
  zona.
- Freerouting no respeta el plano GND como zona de exclusión para nets
  ajenos (D-19.1) — mitigado por refill+enforce post-ruteo, no
  eliminado en el 100% de los casos geométricos (F-D5-01).
- El esquemático se edita por escritura directa de archivo
  (`kicad-skip`), no por IPC — KiCad 10 no expone IPC de esquemático.

### Para CONTRIBUTING §"Bridge write contracts"

Los 4 ejes con ejemplos concretos de esta auditoría:
1. **Persistencia:** ¿la tool guarda a disco? Si sí, ¿siempre o
   condicional? Ejemplo de contrato estricto: `fill_zones` (save
   incondicional). Ejemplo de diseño válido sin persistencia: `add_track`
   (documentar explícitamente que el llamador debe invocar `save_board()`).
2. **Propagación de errores:** todo fallo de escritura visible con
   `{code, message, hint}`, nunca silencioso. Ejemplo de lo que NO hacer:
   el `except KicadMcpError: reloaded = False` pre-32b en `route_board`
   (F-V2-REFILL-SILENCIOSO).
3. **Sincronización disco↔memoria:** toda mutación IPC empieza con
   `_guard_live_stale()` + `check_no_external_disk_edit()`, salvo que
   exista una razón documentada para omitirlos (ejemplo válido:
   `reload_board_from_disk`, que es el mecanismo que destraba el guard).
4. **Manejo de reload:** si la tool invoca `reload_board_from_disk`, la
   excepción debe propagarse con diagnóstico, nunca descartarse en
   silencio (D-07.1: sin reintento, pero con reporte).

### Para CONTRIBUTING §"How to add a new write tool" (checklist)

- [ ] ¿Muta zonas/keepouts existentes, directa o indirectamente? Si sí,
  ¿corre `refill_zones()` + `enforce_hole_clearance()` + `save_board()`
  juntos (reusar `_refill_enforce_and_save`), o documenta explícitamente
  por qué no?
- [ ] ¿Empieza con `_guard_live_stale()` + `check_no_external_disk_edit()`?
  Si no, ¿por qué la tool es una excepción legítima?
- [ ] ¿El payload/confirm deja claro si el cambio quedó en disco o sólo en
  memoria?
- [ ] ¿Todo código de error nuevo es adición pura al `ErrorCode` StrEnum
  (F1/F3), documentado en `tool-catalog.md` en el mismo commit?
- [ ] Si la tool toca el pipeline de zonas/route: test de regresión GUI es
  gate del merge (DoD #2).
