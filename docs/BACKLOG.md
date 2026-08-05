# Backlog — kicad-mcp

Generado en la reorganización documental (2026-07-24), repriorizado según
`docs/historico/CONTEXT-v7.md` (post-sesión 24) — la secuencia estricta de
Fase 3 sube al frente los ítems de esa secuencia (solder mask ANT1,
generalización D-23.2) y baja el CRUD de esquemático a P3, ya que v7 lo
excluye explícitamente del alcance de Fase 3. También sintetizado de
`docs/historico/analisis/ANALISIS-ESTADO-Y-BACKLOG.md` §Parte 2 y las
fricciones registradas en sesiones 21–24. Dentro de cada prioridad, orden
aproximado de severidad.

---

## P0 — Bloqueantes de dogfooding / release

### F-V3-ZONE-FILL-CRASH — `add_zone(fill=true)` crashea KiCad de forma reproducible en la 3ª-4ª llamada sobre boards grandes — No concluyente tras auditoría 34a

**Origen:** sesión 33, Validation Suite Nivel C (HackRF One, 437
footprints / 380 nets / 4 capas).

**Reproducido 3 veces** con geometrías distintas, siempre con el mismo
resultado: KiCad se cae (2 veces) o queda colgado transitoriamente y se
recupera solo (1 vez), y el disco queda con exactamente **710 zonas**
(3 reales + 707 fragmentos sin net, esparcidos entre las 2 capas
internas) tras cada intento fallido.

1. **Intento 1:** GND (In1.Cu, bbox completo, OK) → VCC + VAA (In2.Cu,
   ambas con el bbox completo superpuesto al 100%, prioridad 0 sin
   definir cuál gana) → crash en la 4ª llamada (`USB_SHIELD`/F.Cu).
2. **Intento 2 (refutación explícita, D-33.1):** mismo orden pero VCC/VAA
   en mitades disjuntas del bbox (sin overlap geométrico) → **mismo
   crash exacto**, mismos 710 fragmentos, en la misma 4ª llamada. Refuta
   la hipótesis de overlap del intento 1.
3. **Intento 3:** igual que 2 pero con 20s de delay entre cada
   `add_zone` (por si era una condición de carrera) → **mismo crash**,
   3ª reproducción idéntica.

**Patrón observado, no investigado:** el crash ocurre consistentemente
en la 3ª-4ª llamada consecutiva a `add_zone(fill=true)`, sin
correlación con la geometría/overlap de las zonas. Posibles hipótesis
no evaluadas: acumulación de estado en el motor de fill/conectividad de
pcbnew tras N llamadas sucesivas sobre un board de esta densidad (437
footprints); interacción con el mismo mecanismo de segfault ya
documentado en `validation-suite/tools/prepare_working.py` (remove+move
en el mismo proceso). Limpieza determinística posible vía `pcbnew`
directo (`board.Remove(zone)` para cada zona + `save` +
`reload_board_from_disk`), sin pérdida de otro estado del board.

**Severidad:** bloquea flujos que necesiten 3+ zonas de cobre sobre
boards grandes (típico en diseños multi-capa con múltiples planos de
alimentación). No bloquea el caso de 1-2 zonas (verificado limpio en
Nivel A/B y en esta misma sesión con GND único). Candidato a
investigación P4.0-style si reaparece en un board de escala comparable.

**Clasificación (sesión 34a, auditoría de contratos):** **no concluyente**.
Análisis de código del pipeline de `add_zone(fill=true)`
(`refill_zones()` interno del bridge → `enforce_hole_clearance()` →
`save_board()`) no encontró ninguna causa del lado del bridge — es el
mismo patrón que `fill_zones()`/`route_board()`, ninguna con crashes
reportados. La reproducción empírica con harness sintético, planeada para
esta sesión, no se ejecutó: el único KiCad vivo disponible tenía abierto
precisamente el proyecto HackRF One que ya crasheó 3/3 veces en sesión 33
(`KICAD_MCP_PROJECT` quedó fijado a esa ruta), y no existe tool en la
superficie del MCP para abrir un proyecto distinto en el editor vivo sin
operar la GUI directamente — ejercer el harness ahí habría significado
asumir el mismo riesgo que la sesión buscaba evitar, sin decisión
deliberada de hacerlo. Orientativamente compatible con un bug de
fragmentación de pcbnew a escala (la firma de 710 zonas/707 fragmentos
sin net es consistente con fill fragmentando geometría compleja
internamente, no con una operación del bridge que "corte" zonas) — sin
confirmación positiva. Detalle completo:
`docs/analisis/auditoria-contratos-bridge.md` §4.

**Próximo paso:** repro fiel contra HackRF One (asumiendo el riesgo
deliberadamente) o contra un board sintético de escala equivalente (400+
footprints, 4+ capas) — investigación propia si reaparece antes del
release; no bloquea el ciclo actual.

**Fuente:** sesión 33 (hallazgo), sesión 34a (clasificación acotada).
Detalle forense completo en
`validation-suite/level-c/hackrf-one/validation-report.md` §Fricciones.

### F-V3-ROUTER-TIMEOUT-HARD — Freerouting 2.1.0 entra en crash-loop interno sobre boards grandes (HackRF One) — Bug upstream, no investigado

**Origen:** sesión 33, Validation Suite Nivel C (HackRF One).

`route_board(timeout_s=3600)` no completó. El log interno de
Freerouting (33 líneas totales en ~55 min de corrida) no registra
**ninguna** línea de score/progreso — solo 6 `NullPointerException`
repetidas en `MazeSearchAlgo.expand_to_target_doors` (`target_shape`
null), distribuidas de forma intermitente a lo largo de toda la
corrida. Diagnóstico distinto al de sesión 32 (score estancado cerca de
completar, con progreso real hasta ahí): acá el motor no avanza,
crashea internamente en loop sin indicio de por qué esta topología
específica (4 capas, 380 nets, plano GND parcial) dispara la excepción.

**Severidad:** bloquea `route_board` end-to-end sobre boards de esta
escala/topología. No es un bug de `kicad-mcp` (`route_board` se
comportó correctamente ante el fallo — 0 persistencia corrupta, mismo
contrato D-23.2/ADR-0012 que en cualquier timeout). Es un bug upstream
de Freerouting 2.1.0, fuera del control del proyecto — documentar como
límite conocido del flujo automatizado en la documentación de
release, no "arreglar" desde `kicad-mcp`.

**Fuente:** sesión 33. Log completo en
`validation-suite/level-c/hackrf-one/working/.kicad-mcp/autoroute/freerouting.log`
(no versionado — archivo de trabajo).

### F-V2-REFILL-SILENCIOSO — `route_board(refill=true)` puede no persistir el refill sin ningún error visible — ✅ CERRADO sesión 32b

**Origen:** sesión 32, segunda Validation Suite (Nivel B, ANAVI Macro Pad 12).

**Mecanismo confirmado** (`src/kicad_mcp/tools/pcb.py`): el bloque
post-ruteo de refill+`enforce_hole_clearance`+`save_board`
(`pcb.py:2728-2733`, activado por `refill=true`) sólo se ejecuta si
`reloaded is True`. `reloaded` depende de que
`bridge.reload_board_from_disk(open_board)` no lance `KicadMcpError`
(`pcb.py:2701-2710`) — una operación de **mutación**, deliberadamente
**sin reintento** ante `AS_BUSY` transitorio (D-07.1). Si falla una sola
vez, la excepción se descarta en silencio
(`except KicadMcpError: reloaded = False`) y **todo** el paso de
seguridad que corrige que "Freerouting NO respeta el plano GND como
zona de exclusión" (D-19.1) se salta — sin `POST_ROUTE_PERSIST_FAILED`,
sin ningún error, `route_board` devuelve un payload de éxito normal con
`refill: true` solicitado pero silenciosamente no honrado.

**Reproducible en 2 sesiones independientes, no un fluke:** el audit log
de `/tmp/gui-test-project` conserva la llamada `route_board` original de
**sesión 31c** (`2026-07-29T11:13:58`) mostrando el mismo patrón exacto:
`"reloaded": false, "zones_refilladas": 0`. Sesión 31c ejecutó su propio
"Refill final" explícito pocos minutos después sin cruzar estos campos
contra la promesa de `refill=true` — el hallazgo nunca se documentó
porque el paso ya prescripto en el flujo canónico (D-23.2) lo
enmascaraba. En sesión 32, esto dejó 259 violaciones DRC reales (236
`clearance` + 23 `hole_clearance`, 100% contra la zona GND) sin resolver
hasta recuperación manual (`reload_board_from_disk()` + `fill_zones()`
explícitos).

**Por qué es P0 y no sólo P2:** rompe la garantía D-23.2/ADR-0012
("disco == memoria == err_post reportado") — el caso exacto que ese
contrato existe para prevenir — sin ninguna señal de error. Cualquier
uso de `route_board(refill=true)` que confíe en esa promesa sin un paso
de refill explícito adicional recibiría un board con clearance real
contra el plano GND sin saberlo.

**Recomendación de fix original** (sesión intermedia, patrón 31b, antes de
sesión 33): (a) desacoplar el refill+persistencia en disco de
`reload_board_from_disk` — son operaciones lógicamente independientes
(una sincroniza el editor vivo, la otra corrige y persiste el archivo);
(b) si se mantiene la dependencia, surfacear un código de error
explícito (ej. `POST_ROUTE_REFILL_SKIPPED`) en vez de éxito silencioso;
(c) evaluar si esta mutación en particular (re-sincronizar estado, no
aplicar un cambio de diseño) amerita excepción documentada al criterio
general de D-07.1 de no reintentar mutaciones.

**Cierre (sesión 32b):** la opción (a) resultó ser PELIGROSA, no sólo
descartable por preferencia — investigación previa al fix (Bloque 0)
encontró que si la recarga falló, el board vivo todavía refleja el
estado **pre-ruteo** (el `save_board` implícito bajó live→disco antes de
que Freerouting escribiera); refillear y guardar ese vivo desactualizado
pisaría el ruteo recién persistido en disco. Se aplicó la opción (b): la
excepción de `reload_board_from_disk` ya no se descarta
(`src/kicad_mcp/tools/pcb.py`, bloque de recarga automática post-route),
y cuando el refill prometido (`refill=true`, `zones_existentes > 0`) no
corre por esa razón concreta, `route_board` levanta
`POST_ROUTE_REFILL_SKIPPED` (adición pura al `StrEnum`, F1/F3 intacta) en
vez de completar en silencio. El raise se pospone hasta después del DRC
post-route + snapshot + `store.mark_live_stale` (no en el guard), para no
abrir una ventana donde un `fill_zones()` posterior pisara el ruteo. La
opción (c) NO se tomó — D-07.1 (mutación sin reintento) queda intacta,
`reload_board_from_disk` se sigue llamando una sola vez.

**H2 refutada (alcance del fix):** el prompt de sesión 32b hipotetizaba
que `fill_zones()`/`add_zone(fill=true)` podían compartir el mismo bug
(cobertura simétrica D2). Inspección del código lo refutó: ninguna de las
dos llama `reload_board_from_disk` — no tienen este camino silencioso, su
único modo de falla (`save_board()`) ya levanta `POST_ZONE_PERSIST_FAILED`
desde sesión 27. El fix quedó acotado a `route_board`.

**Ver:** `docs/adr/0012-route-board-persist-contract.md`
§"Extensión F-V2 (sesión 32b)", `docs/DECISIONES.md` D-32b.1/D-32b.2,
`docs/historico/sesiones/32b-reporte.md`,
`tests/test_pcb_session32b_refill_silencioso_canary.py` (canario
permanente), y `validation-suite/level-b/anavi-macro-pad-12/validation-report.md`
§Fricciones para el hallazgo original.

### F-V1-02 — `route_board` falla enteramente con refs de footprint duplicados/sin anotar — ✅ CERRADO sesión 31b

**Origen:** sesión 31, primera Validation Suite (Nivel A, ANAVI Dev Mic).
El diseño del autor trae 4 mounting holes con el reference designator
literal `REF**` compartido (footprints sólo-mecánicos, sin símbolo de
esquemático — nunca fueron anotados; patrón real y no infrecuente en
proyectos KiCad externos).

- **Síntoma 1 (ya conocido, P2 histórico — ver abajo, ahora resuelto):**
  `move_footprint(ref="REF**", ...)` resolvía por `fp.ref == ref` (primer
  match) — sólo podía mover UNA de las 4 instancias.
- **Síntoma 2 (root cause aislado con experimento controlado en sesión
  31):** `pcbnew.ExportSpecctraDSN()` — invocada por `_run_export_dsn`,
  paso 1 de `route_board` — **devuelve `ok=False, size=0` cuando el
  board tiene refs de footprint duplicados**, sin importar la posición
  de esos footprints. Confirmado quitando 3 de las 4 instancias `REF**`
  en una copia de prueba: la exportación pasó de fallar a `ok=True,
  size=2.4MB`. Bloqueaba `route_board` **por completo**.
- **Decisión de diseño (sesión 31b, investigación previa al fix):** el
  fix obvio (`delete_footprint(ref, kiid)` general) se descartó — ADR-0010
  dice explícitamente que borrar footprints sigue detrás de Gate G2 (que
  no existe en código), y esa asimetría con `delete_track`/`delete_via`
  es **deliberada**, no un vacío. Acotar el trigger a "ref duplicado" NO
  cambia el argumento de ADR-0010: un footprint con ref duplicado es
  igual de caro de reinstanciar que uno con ref único. Además, en el
  caso real de ANAVI Dev Mic, las 4 `REF**` son mounting holes
  **legítimas**, no basura — borrar 3 habría destruido el ground truth
  de 13 footprints que sesión 31 ya midió.
- **Fix real: anotar, no borrar.** Verificado con un spike GUI contra
  KiCad 10.0.4 real (sesión 31b, Paso 0) que `fp.reference_field.text.value`
  usa semántica de escritura en vivo en kipy (`proto_ref=`, sin
  `CopyFrom` — a diferencia de `fp.position`, la trampa de ADR-0008).
  Tool nueva: `set_footprint_ref(ref, new_ref, kiid=None)` — sólo opera
  sobre refs YA duplicados (no puede usarse como delete_footprint
  disfrazado), lista candidatos con `data.candidates` si `kiid` no se
  especifica (nunca resuelve a ciegas, mismo espíritu que la ambigüedad
  de `_delete_copper`). Complementado con un pre-check `DUPLICATE_REFS`
  en `route_board` (falla ANTES del subprocess de exportación DSN, con
  mensaje legible en vez del `KICAD_CLI_FAILED` opaco anterior).
- **Ver ADR-0013** para el contrato completo (incluye el hallazgo
  arquitectónico de la semántica `proto_ref=` de `reference_field`,
  contraparte de ADR-0008).
- **Verificación:** 12 tests unit (`_find_duplicate_refs`, pre-check de
  `route_board`, tool `set_footprint_ref` — ambigüedad, kiid stale, ref
  único rechazado, happy path) + 1 test `integration` contra pcbnew real
  (`tests/fixtures/006_pcb_refs_duplicados/`) que congela el experimento
  controlado de sesión 31 como regresión permanente.
- **Impacto en sesión 31:** H1a (estabilidad del flujo canónico) fue
  refutada honestamente en su momento — la validación Nivel A (ANAVI Dev
  Mic) cerró SIN completar el ruteo. Con este fix, el reintento de
  sesión 31 queda desbloqueado sobre el mismo `working/` ya preparado.
  Ver `validation-suite/level-a/anavi-dev-mic/validation-report.md` y
  `docs/historico/sesiones/31-reporte.md`.

Ningún P0 abierto hoy (F-V1-02 arriba cerrado en sesión 31b). **F-D4-02
cerrado y ratificado con evidencia 5/5**
(2/2 test de regresión sesión 24 + 3/3 corridas de D5, sesión 25 —
`err_post` coincidió exacto con `run_drc()` independiente, mtime cambió
post-save, cero `EXTERNAL_EDIT_DETECTED` espurio, sin ninguna excepción en
las 5 corridas). El cierre generaliza al board vivo en producción real, no
solo al contrato JSON del test controlado — ver
`docs/historico/sesiones/25-reporte.md`. **Alcance de la ratificación
ampliado en sesión 27**: el contrato D-23.2 ya cubre las tres tools
(`route_board`, `fill_zones`, `add_zone(fill=True)`) — ver P2 cerrado
abajo. **Ratificado 25/25 en producción real hasta cierre D7 (sesión 29),
sin divergencias.** Reabrir como P0 solo si una sesión futura lo ratifica
como regresión.

## P1 — `delete_tracks_bulk` no respeta D-23.2/ADR-0012 sobre zonas tocadas — Abierto, agendado `34a-fix-1`

**Origen:** observado en sesión 32b (`docs/BACKLOG.md` §Higiene menor,
histórico), no accionado por estar fuera del alcance quirúrgico de esa
sesión. **Confirmado con severidad P1** (no P3/higiene) en la auditoría
sistemática de contratos de escritura de sesión 34a.

`delete_tracks_bulk` (`src/kicad_mcp/tools/pcb.py:2039`) llama
`bridge.refill_zones(board)` cuando el borrado toca tracks de una zona de
cobre, pero **sin** `enforce_hole_clearance()` ni `save_board()`
posteriores — a diferencia de `route_board`, `fill_zones` y
`add_zone(fill=True)`, que corren las tres juntas (contrato D-23.2/
ADR-0012). Dos consecuencias concretas: (1) el clearance contra holes
puede quedar roto (mismo bug conceptual que F-D3-01, sin su workaround
acá); (2) el refill vive sólo en memoria — el payload reporta
`zones_refilled: 1` pero el disco nunca se actualiza, así que un
`run_drc()` inmediato mide el estado viejo. El propio docstring de
`enforce_hole_clearance` (`ipc.py:2016`) exige llamarlo **siempre**
inmediatamente después de `refill_zones()` — esta tool viola esa
invariante directamente.

**Evidencia de test:**
`tests/test_pcb_delete_bulk.py::test_delete_tracks_bulk_refills_zones_when_copper_zone_present`
sólo asegura `zones_refilled == 1` — sin ninguna assertion de
`save_board()`/`enforce_hole_clearance()` invocados. El test documenta el
comportamiento actual, no lo objeta.

**No fixeado en sesión 34a** (fuera de alcance: la sesión es auditoría
pura, fixes triviales <20 líneas únicamente). Hipótesis de fix agendada
como `34a-fix-1`: reemplazar la llamada inline por
`_refill_enforce_and_save(bridge, board, pcb_path, root, params,
context="borrado bulk")` (mismo helper que ya usa `route_board`), con
manejo de fallo de persistencia visible (código nuevo o reuso de
`POST_ZONE_PERSIST_FAILED`). Requiere: decisión del arquitecto sobre si
extiende ADR-0012 formalmente, test de regresión con zona de cobre real +
verificación de disco post-save, y gate GUI del DoD (toca pipeline de
zonas). Detalle completo:
`docs/analisis/auditoria-contratos-bridge.md` §3 (ficha
`delete_tracks_bulk`) y §5.3.

## P1 — Solder mask bridge en ANT1 — ✅ CERRADO sesión 30 (mecanismo aislado + fix), pendiente gate GUI

El pad de ANT1 hacía bridge con la zona GND. El fix de sesión 21 (F-D3-01)
protegía el *hole*, no el *pad*. Sesión 26 confirmó el bug como real y
alcanzable pero no logró aislar el mecanismo ni hacer efectivo un fix.
**Sesión 30 aisló el mecanismo con precisión sub-milimétrica y aterrizó el
fix.** Ver `docs/investigacion/30-solder-mask-ant1.md` (reporte completo,
continuación de `docs/investigacion/26-solder-mask-ant1.md`).

- **Origen:** fricción de D4 (sesión 22). Investigación parcial sesión 26,
  cerrada sesión 30.
- **Mecanismo:** el fill de KiCad respeta el **apotema** del keepout de
  N vértices (`r·cos(π/N)`), no un círculo ideal al radio pedido. Con
  N=16 (sesión 21-29), el déficit de apotema a los radios típicos de esta
  investigación (~1.8mm) es mayor que el margen de seguridad de 0.02mm —
  por eso el fix de sesión 26 no tuvo efecto. Sesión 26 además asumió un
  número incorrecto para la clearance natural del pad (2.00mm en vez de
  1.70mm, confundiendo `min_copper_edge_clearance` con la clearance de
  netclass), lo que hizo parecer irreconciliables sus dos experimentos.
- **Fix:** `src/kicad_mcp/bridge/ipc.py` — (1) `_circle_vertices_mm` N=16→64
  (compensa el déficit de apotema); (2) `enforce_hole_clearance` recalcula
  el radio de keepout de un pad como
  `max(hole_term, r_cobre_pad + max(pad_to_mask_clearance, solder_mask_to_copper_clearance) + margen)`
  — re-aterriza el término de máscara que sesión 26 había revertido (los
  clearances ya se leían en `rules_reader.py` desde sesión 26, sin
  consumidor hasta ahora).
- **Verificación:** unit test de la fórmula (`tests/test_pcb_hole_clearance.py`)
  + barrido `pad_to_mask_clearance` ∈ {0.0, 0.20, 0.22, 0.25, 0.30} contra
  el motor real de KiCad (`tests/test_pcb_session30_solder_mask.py`, marca
  `integration`, gate del merge) — 0 violaciones en los 5 casos, más
  control del flujo canónico sin cambio de comportamiento.
- **Gate GUI del DoD (pipeline de zonas/keepouts):** corrido contra copia
  fresca (no `/tmp/gui-test-project`, fuera de alcance de sesión 30) —
  `test_pcb_session21_hole_clearance_gui.py` 2/2 y
  `test_pcb_session27_zone_persist_gui.py` 2/2, ambos verdes. Confirma que
  el bump N=16→64 no regresiona ningún keepout auto-generado ya validado
  en D3-D7.
- **Kept de sesión 26, ahora con consumidor:** `rules_reader.py`
  (`pad_to_mask_clearance_mm`, `solder_mask_to_copper_clearance_mm`).

### P2 — Generalización D-23.2 a fill_zones y add_zone(fill=True) [CERRADO sesión 27]

- **Estado:** cerrado 2026-07-24, mergeado a master.
- **Evidencia:** test de regresión GUI 2/2 verde contra KiCad 10.0.4
  real (`tests/test_pcb_session27_zone_persist_gui.py`, 69s por
  corrida). ADR-0012 extendido con sección "Extensión de alcance
  (sesión 27)".
- **Cambio:** `POST_ZONE_PERSIST_FAILED` compartido para las dos tools.
  Contrato D-23.2 ahora aplica a tres tools (`route_board`,
  `fill_zones`, `add_zone(fill=True)`).
- **Ratificado en Fase 3** con 3 dogfoodings verdes consecutivos (D5, D6,
  D7); Fase 3 cerrada 2026-07-25.
- **Reporte:** `docs/historico/sesiones/27-reporte.md`.

## P1 — bbox de validación no leía Edge.Cuts — ✅ CERRADO sesión 31b

**Origen:** sesión 31, Bloque 2 (colocación sobre ANAVI Dev Mic).
`board_bbox_mm` (`src/kicad_mcp/bridge/ipc.py`) tenía un docstring que
decía *"Preferencia: usar la superficie declarada del board (Edge.Cuts).
Fallback: unión de bounding boxes de todos los footprints"* — pero el
código **nunca leía Edge.Cuts**, iba directo al fallback (margen de
±100mm alrededor del enjambre de posiciones de footprints).

- **Corrección de sesión 31b (investigación previa al fix):**
  `board_bbox_mm` **no tiene ningún consumidor en `src/`** — el bug real
  que sesión 31 pisó vivía en una copia inline **independiente** del
  mismo cálculo dentro de `read_board_context` (el método que
  `move_footprint`/`add_track`/`add_via` realmente usan vía
  `ctx.bbox`). La entrada original de este ítem nombraba la función
  equivocada por la misma razón estructural que causó el bug: dos
  copias divergentes de la misma lógica.
- **Cuándo importaba:** si todos los footprints están agrupados lejos
  del contorno real (ej. todos en `(0,0)`, la convención de estado
  inicial de `working/` en la Validation Suite —
  `validation-suite/tools/prepare_working.py`), el bbox calculado
  (`swarm ± 100mm`) podía no cubrir el contorno Edge.Cuts real, y
  `move_footprint`/`add_track` rechazaban con `INVALID_PARAMS` cualquier
  coordenada dentro del board real. Sesión 31 lo confirmó con ANAVI Dev
  Mic: contorno en x∈[109,144], bbox aceptado x∈[-100,100] — sin
  intersección.
- **Fix (sesión 31b):** helper lock-free `_edge_cuts_bbox_nm` extraído
  de `board_outline` (evita re-adquirir `self._lock`, no reentrante —
  `ipc.py:999-1003`), consumido por `board_outline`, `board_bbox_mm` Y
  `read_board_context` vía el helper puro `_bbox_with_margin`. Semántica
  final: **unión** de Edge.Cuts (±10mm) y enjambre de footprints
  (±100mm), no "preferir uno u otro" — estrictamente no regresivo, nunca
  devuelve un rango más chico que el código anterior.
- **Verificación:** 12 tests unit nuevos en `tests/test_ipc.py`
  (incluye un canario de deadlock que reemplaza `self._lock` por un
  wrapper que lanza en re-entrada) + suite offline completa sin
  regresiones.
- **Sin ADR** — implementa comportamiento ya documentado, sin cambiar
  contrato externo (DoD #4, "aclaración de comportamiento").

## P1-1 — Sanitización de los tres encoders ad-hoc de `tools/pcb.py` — ✅ CERRADO sesión 37, gaps derivados cerrados/delegados sesión 38

**Origen:** R2 de `docs/analisis/auditoria-tecnica-integral-2026-08.md:367`
(plan de acción C2 en `:429`, deuda técnica DT4 en `:385`). `_encode_tracks`,
`_encode_zones` y `_encode_component_detail` (`tools/pcb.py`) interpolan
`net_name`/`ref`/`pad.number` de KiCad — entrada no confiable por CLAUDE.md
regla 6 — en formatos delimitados por espacios/`|` propios (NO TOON, F1
intacto por diseño).

- **Sesión 36 (parcial):** aplicó `toon.encoder._sanitize` en los tres
  puntos de interpolación (cierra caracteres estructurales `\n`/`|`/`:`/`>`
  y control-chars) + 3 goldens byte-exactos nuevos
  (`tests/golden/004_pcb_tracks_canarios/`, `005_pcb_zones_canarios/`,
  `006_pcb_component_detail_canarios/`, `tests/test_pcb_encoders_golden.py`).
  Evaluando H36.1 activamente (no asumida), descubrió que `_sanitize` **no**
  neutraliza el espacio — el delimitador posicional real de las tres
  gramáticas ad-hoc (a diferencia de TOON, `|`-delimited). Documentado como
  golden de caracterización (líneas `T4`/`Z4`/pads 4-5) y escalado a sesión
  37 en vez de fixearlo apurado.
- **Sesión 37 (cierre):** mini-sanitizador local `_sanitize_space_delimited`
  (`tools/pcb.py`, junto al import de `_sanitize`) — compone `_sanitize` +
  `re.sub(r"\s", "_", ...)` (D37.1: whitespace unicode completo, no sólo
  `U+0020`, alcanzable vía netlists importadas; `_CONTROL_RE` de TOON ya
  cubre `\t\n\r\v\f` pero no el espacio). Aplicado en los 5 sitios
  space-delimited: `net_name` en `_encode_tracks` (segmentos y vías) y
  `_encode_zones`, `number`/`net_name` de pad en `_encode_component_detail`.
  El header `DETAIL|<ref>|pcb|...` de `_encode_component_detail` (`|`-delimitado)
  **no** se toca — H2 confirmada, un espacio ahí es inocuo.
  `toon/` no se tocó (ruta (a) del ADR propuesto en 36; la ruta (b), extender
  `_sanitize`, fue descartada explícitamente por el arquitecto para no
  invertir la dependencia núcleo↔deuda ad-hoc).
- **Goldens actualizados exactamente en las 4 líneas anticipadas** (`T4` en
  004, `Z4` en 005, pads 4-5 en 006) — H3 confirmada, regenerar con el código
  nuevo y diffear contra el golden previo no tocó ninguna otra línea.
- **Riesgo real, no sólo teórico:** hay consumidores posicionales activos que
  `.split(" ")`/`.split()` estas líneas — `tests/test_pcb_session16_gui.py:126`,
  `tests/test_pcb_session19d_gui.py:142`,
  `tests/test_pcb_session21_hole_clearance_gui.py:115`,
  `tests/test_reload_e2e_gui.py:122`. Un `net_name="GND EN"` sin el fix
  leería `net="GND"`, `layer="EN"` — corrupción silenciosa.
- **Campos fuera de alcance, quedan como candidatos futuros** (ya listados
  en la decisión #4 de sesión 36, sin sesión asignada): `filter_desc`
  (headers de `_encode_tracks`/`_encode_zones`), `it.kiid`/`z.kiid`,
  `it.layer`/`z.layer`/`p.layer` (`CopperItem.layer: str | None` renderiza
  el literal `None` cuando falta), `z.kind`, `it.via_layers`,
  `detail.bbox_source`, y `CopperItem.net_name` vacío sin fallback `or "-"`
  (a diferencia de `ZoneItem.net_name`/`PadDetail.number`/`net_name`, que sí
  lo tienen). Ver `docs/historico/sesiones/37-reporte.md`.
- **Verificación:** `pytest tests/test_pcb_encoders_golden.py` → 3 passed;
  suite offline completa → 388 passed (mismo baseline que sesión 36); `ruff
  check`/`ruff format --check`/`mypy src/` limpios.
- **Sesión 38 — cierre de 4 de los 7 campos listados arriba, veredicto
  explícito en los 7:**
  - `CopperItem.net_name` vacío → fallback `"-"` (`_encode_tracks`), ya
    consistente con `ZoneItem`/`PadDetail`. **Cerrado.**
  - `CopperItem.layer` (`str | None` renderizando `None`) → fallback `"-"`.
    Defensivo, no correctivo: hoy sólo las vías traen `layer=None` y esa
    rama no emite `layer` — inalcanzable en producción, pero el tipo lo
    permite y el fix cierra el flanco a costo cero. **Cerrado.**
  - `z.layer` (no estaba en los 4 candidatos originales del prompt de la
    sesión, pero sí en el desglose `it.layer`/`z.layer`/`p.layer` de esta
    misma entrada) → puede ser `""` (`bridge/ipc.py`, `layers[0] if layers
    else ""`), mismo colapso de columna que tenía `CopperItem.net_name`.
    Fallback `"-"`. **Cerrado** (correctivo, caso alcanzable).
  - `filter_desc` → sanitiza cada componente (`net`/`layer`/`kind`) antes de
    ensamblar, en `_tracks_filter_desc`/`_zones_filter_desc`. **Correctivo,
    no defensivo:** `layer` de `get_tracks`/`get_zones` no se valida en
    ningún punto (a diferencia de `net`/`kind`/`bbox`) y llegaba crudo al
    header — un `layer` con `\n` forjaba líneas dentro del bloque
    `TRACKS|v1|...`/`ZONES|v1|...`. **Cerrado.**
  - `kiid` → **NO cerrado, abre `P1-2`** (ver abajo): es identificador de
    round-trip (`delete_track(id=...)`, `get_copper_by_kiid`), sanitizarlo
    rompe la resolución del id — requiere discusión de diseño, no es un fix
    mecánico.
  - `bbox_source`, `kind`, `p.layer` → **refutados**, no son gaps reales:
    conjuntos cerrados de literales hard-codeados internos
    (`{"courtyard","pads"}` para `bbox_source`; `"via"/"arc"/"track"`/bool
    `is_keepout` para `kind`) o siempre no-vacíos (`_pad_layer_str` —
    `"*.Cu"` o nombre de enum en toda rama), nunca texto de archivo KiCad.
  - Canarios nuevos: `T5` en `004_pcb_tracks_canarios` (`net_name=""` +
    `layer=null`), `Z6` en `005_pcb_zones_canarios` (`layer=""`). `006` sin
    cambios (los dos candidatos que la tocaban quedaron refutados).
    `filter_desc` sin cobertura golden posible (el arnés recibe el string ya
    ensamblado) — cubierto en `tests/test_pcb_session38_filter_desc.py`.
  - Ver `docs/historico/sesiones/38-reporte.md` para el detalle con traza al
    código de cada veredicto.

## P1-2 — `kiid` sin sanitizar en los encoders ad-hoc de `tools/pcb.py` — Abierto, sin sesión asignada

**Origen:** decisión #4 de sesión 36, verificado y promovido a entrada propia
en sesión 38 (el resto de esa decisión se cerró en la misma sesión, ver
`P1-1` arriba).

**Ubicación:** `it.kiid` en `_encode_tracks` (`tools/pcb.py`, líneas de
segmento y de vía), `z.kiid` en `_encode_zones`. Ambos vienen de
`str(it.id.value)`/`str(z.id.value)` (`bridge/ipc.py`) — el KIID nativo de
KiCad, no texto arbitrario de archivo, pero tampoco garantizado libre de
caracteres estructurales por contrato (D-16.2/D-16.3 no lo especifican).

**Por qué no es un fix mecánico:** `kiid` es un identificador de
**round-trip** — el agente lo recibe de `get_tracks`/`get_zones` y lo
devuelve tal cual a `delete_track(id=...)`, `get_copper_by_kiid`, etc.
Aplicarle `_sanitize`/`_sanitize_space_delimited` (que truncan a 40 chars y
reemplazan caracteres) mutilaría el id y rompería esa resolución — el
consumidor recibiría un id que ya no identifica nada. El fix correcto, si
hace falta uno, es de otra naturaleza (ej. rechazar/loguear un ítem con
`kiid` sospechoso en vez de sanitizarlo, o documentar la garantía de KiCad de
que el KIID nunca contiene esos caracteres y cerrar el candidato como
refutado con esa evidencia) — decisión de diseño, no mecánica.

**Advertencia para quien la tome:** el sitio de emisión vive en el mismo
bloque de `tools/pcb.py` que DT1 (sesión 40, refactor de los encoders
ad-hoc) va a tocar — evaluar si conviene resolver ahí en vez de una sesión
aparte.

## DT2 — Boilerplate transversal ×19 sin decorador — ✅ CERRADO sesión 39

**Origen:** `docs/analisis/auditoria-tecnica-integral-2026-08.md` (fila DT2
de la tabla de deuda técnica en `:383`, plan de acción M1 en `:440`; el doc
en sí no está trackeado en el repo — esta entrada es la primera referencia
a DT2 en `BACKLOG.md`). Prerrequisito declarado de `DT1` (sesión 40,
partición de `tools/pcb.py`): sin un lugar único para el preámbulo
transversal, DT1 fijaría la deuda en más archivos en vez de reducirla.

**Conteo real (P3 de la sesión):** 19 tools MCP mutantes registradas, 16
sitios de preámbulo (`_delete_copper` sirve a `delete_track`+`delete_via`,
`_set_property_core` a `set_value`+`set_footprint`). Anatomía real: **tres
familias estructurales**, no una uniforme (H1 del prompt, parcialmente
refutada) — Familia A (11 tools W-IPC de PCB, preámbulo casi literal),
Familia B (`route_board`/`reload_board_from_disk`, desviaciones
deliberadas de contrato D-14.3/ADR-0011/ADR-0012), Familia C (3 mutantes
de esquemático, sin guard IPC). El epílogo (timer/G1/audit/snapshot/log)
resultó NO uniforme entre las 19 — fuera de alcance del decorador.

**Decisión:** `@mutating_tool` (`src/kicad_mcp/tools/_mutating.py`) cubre
sólo las guardas de ENTRADA (`_guard_live_stale` + `check_no_external_disk_edit`
+ `_check_base_snap`) de la Familia A. Aplicado a **12 de las 16 tools**
(`move_footprint`, `set_footprint_ref`, `add_track`, `add_via`,
`save_board`, `delete_track`, `delete_via`, `draw_board_outline`,
`add_zone`, `add_keepout_zone`, `fill_zones`, `delete_zone`).
**Excluidas con justificación** (ver `docs/adr/0014-mutating-tool-decorator.md`):
`delete_tracks_bulk` (preámbulo post early-return de `dry_run` — hoistearlo
cambiaría comportamiento observable), Familia B completa (contrato
deliberado), Familia C completa (estructuralmente distinta, candidata a
decorador hermano en sesión futura).

- **Reducción medida:** `tools/pcb.py` 3507 → 3419 líneas (-88, -2.5%).
  4 helpers movidos a `_mutating.py` (~49 líneas relocadas, no borradas).
  12 sitios de preámbulo colapsados a 1 línea de decorador cada uno (10
  sitios con reducción neta de -4/-5 líneas; `delete_track`/`delete_via`
  netean +1 cada uno porque su guard vivía una sola vez en el núcleo
  compartido `_delete_copper`, que además ganó un párrafo de docstring
  explicando por qué `base_snap_check=False`).
- **Verificación:** suite offline **392 → 406 passed** (392 baseline
  intacto sin modificar un solo test existente + 14 tests nuevos de
  `tests/test_mutating_tool.py`, aislados con spies + 2 canarios de
  registro contra `tools/pcb.py` real). `ruff check`/`ruff format
  --check`/`mypy src/` limpios.
- **Sin cambio observable:** mismos códigos de error, misma taxonomía F3,
  mismas firmas de tool (FastMCP ve la firma original vía
  `functools.wraps`/`__wrapped__`).
- Ver `docs/historico/sesiones/39-reporte.md` para el detalle completo y
  la propuesta de sesión 40 (DT1).

## P1 (investigación Fase 4) — Conectividad GND no cierra tras refill (F-D5-01 / F-V1c-01 / F-V2-VIA-HUERFANA) — CERRADO PARCIALMENTE sesión 32d, ver sub-patrón abierto abajo

**3ª instancia confirmada del patrón → cumple el trigger de promoción
explícito** ("2 dogfoodings/validaciones independientes reproducen el
patrón" para F-D5-01 original; el criterio análogo de sesión 32 exigía
específicamente una 3ª instancia en régimen distinto, ahora cumplido).

| # | Sesión | Board | Síntoma exacto |
|---|---|---|---|
| 1 | 25 (dogfooding D5) | despertador | isla GND sin vía al plano |
| 2 | 31c (Nivel A) | anavi-dev-mic | 1 vía GND (F.Cu-B.Cu) no conectada a un pad de 0.30×0.30mm (MK1) |
| 3 | 32 (Nivel B) | anavi-macro-pad-12 | 2 pads GND (J4/J5 pad 3) no conectados al plano/track tras refill |

**Origen sesión 32:** DRC de cierre post-`route_board`+refill de
recuperación (ver F-V2-REFILL-SILENCIOSO arriba — este hallazgo apareció
*después* de la recuperación manual, no es un artefacto del refill
fallido): 20 errores totales, de los cuales 2 `unconnected_items` nuevos
vs los 19 del ground truth. `_orphan_vias` (script extendido,
`measure_ground_truth.py` schema 1.1) confirmó **0 vías huérfanas** — el
mecanismo de esta 3ª instancia es a nivel de *pad* (conectividad
pad-a-zona/track), distinto del mecanismo de 31c (vía aislada), pero el
síndrome de fondo (conectividad GND que sobrevive al refill sin cerrar)
es el mismo.

- **Severidad:** el trigger de promoción elevó esto a **P1 investigación
  Fase 4** (patrón sesión 23/26, P4.0-style). No bloquea sesión 32 ni 33
  en sí (14/15 → 42/42 nets ruteables completaron en ambos casos).
- **MECANISMO AISLADO Y CONFIRMADO CAUSALMENTE (sesión 32c).** Freerouting
  rutea tracks de otros nets sin reservar corredor para que el flood-fill
  del plano GND alcance pads específicos (refinamiento medido de D-19.1).
  Cuando ese track ajeno corre en paralelo al borde de la zona en el
  mismo rango Y que un pad GND situado en un corredor angosto, su
  clearance obligatorio consume el corredor por completo — el pad se
  queda sin conexión al plano. Confirmado con 2 experimentos de borrado
  dirigido + re-fillado real (`kicad-cli pcb drc --refill-zones
  --save-board`) sobre copias desechables en anavi-macro-pad-12: borrar
  solo el track troncal `+5V` (rango Y que cubre `J4.3`/`J5.3` pero no al
  `J1.3` sano) resuelve `J5.3` (backbone real, solo faltaba el contacto
  local); `J4.3` necesita además borrar el track serpenteante de su
  propio pin 2 (no tiene ningún track/vía GND propio, patrón original de
  sesión 25). Generalización confirmada por correlación fuerte en
  anavi-dev-mic (`MK1.3` rodeado por sus propios 4 pines hermanos a
  0.85–2.94mm). 3 hipótesis alternativas refutadas con experimentos
  causales: `island_removal_mode`, keepouts de `enforce_hole_clearance`
  (9.3mm de distancia, sin relación), fill totalmente despojado.
- **Fix diferido a sesión 32d** — vive en el pipeline de refill/zonas de
  `route_board`, fuera del "SI Y SÓLO SI" de alcance quirúrgico de 32c.
  Hipótesis completa: tras el bloque D-23.2 + DRC post-route, detectar
  `unconnected_items` sobre nets con zona de cobre propia; stitching
  automático con `add_via` (ya existe la tool) solo si el pad cae dentro
  del outline de una zona de su mismo net; si no es seguro automatizar,
  exponer el conteo en clave explícita del payload en vez de diluirlo en
  `por_tipo`.
- **Hallazgo lateral, sin acción:** `L9.1` en anavi-macro-pad-12 comparte
  la misma dependencia estructural 100%-de-la-zona que `J4.3` (grafo de
  conectividad sin nodos ZONE), sin generar `unconnected_items` hoy —
  candidato de vigilancia.
- **Ver** `docs/investigacion/32c-f-d5-01.md` (reporte completo de
  investigación), `docs/historico/sesiones/32c-reporte.md` (ejecutivo),
  `validation-suite/level-a/anavi-dev-mic/metrics.md` (instancia 2) y
  `validation-suite/level-b/anavi-macro-pad-12/metrics.md` (instancia 3).

### CERRADO PARCIALMENTE (sesión 32d) — stitching automático, topología "capas opuestas"

Fix implementado en `route_board` (D-32d.1/D-32d.2,
`docs/adr/0012-route-board-persist-contract.md` §"F-D5-01 stitching"):
tras el refill final, `route_board` stitchea automáticamente una vía para
cada pad huérfano cuyo net tenga zona propia en la capa OPUESTA a la del
pad (5 guardrails geométricos estrictos, D3). Es la primera respuesta
arquitectónica del proyecto a D-19.1 (Freerouting no ve el plano como
conductor) — mitiga el síntoma, D-19.1 sigue vigente como restricción del
motor externo.

**Hallazgo de sesión 32d: las 3 manifestaciones NO comparten topología.**
Instancia 1 (despertador) e instancia 2 (`anavi-dev-mic`, `MK1.3`) son la
topología "capas opuestas" — el pad huérfano está en una capa y la(s)
zona(s) del net en la OTRA; una vía pasante conecta ambas correctamente.
**Cierra con este fix.** Instancia 3 (`anavi-macro-pad-12`, `J4.3`/`J5.3`)
es una topología DISTINTA — pad y única zona GND en la MISMA capa (B.Cu),
sin cobre GND en F.Cu. Una vía ahí uniría B.Cu (relleno retraído por el
clearance del track ajeno) con F.Cu (sin cobre GND): no conectaría nada.
El guardrail #4 rechaza correctamente (verificado con la geometría real
del fixture, no sólo por diseño teórico) — **queda abierta**, ver entrada
siguiente.

- **Verificación:** canario unit permanente (8 tests, guardrails 1-5 +
  exposición mixta + H4 + re-medición de `err_post`) + suite
  offline/integration completas verdes. Verificación end-to-end contra el
  motor real (`anavi-dev-mic` cerrando, `anavi-macro-pad-12` rechazando)
  **escrita pero pendiente de ejecución humana**
  (`tests/test_pcb_session32d_stitching_gui_slow.py`) — requiere abrir
  cada proyecto en el PCB Editor de KiCad (protocolo manual, sin
  automatización posible en este MVP). Ver
  `docs/historico/sesiones/32d-reporte.md` §"Verificación pendiente".

### Abierto — F-D5-01-B: estrangulamiento lateral en la misma capa (`anavi-macro-pad-12`)

**Origen:** sub-patrón descubierto en sesión 32d al intentar aplicar el
fix de stitching a `anavi-macro-pad-12`. El pad huérfano (`J4.3`/`J5.3`,
B.Cu) y la única zona GND del board (también B.Cu) están en la misma
capa; el track ajeno (`+5V`) que 32c aisló como causal también corre en
B.Cu — es un estrangulamiento lateral del corredor, no un problema de
capas opuestas. Ninguna vía puede remediarlo: conectaría cobre real
(B.Cu, del lado del pad) con la nada (F.Cu, sin cobre GND).

**Candidatos de mitigación NO evaluados** (fuera del alcance quirúrgico
de sesión 32d): ensanchar el corredor disponible (mover el pad o rediseñar
la zona, fuera de lo que `route_board` puede decidir autónomamente); un
keepout que empuje a Freerouting lejos del corredor angosto ANTES de
rutear (viable en principio — `add_keepout_zone` ya existe — pero
requeriría identificar el corredor angosto ANTES del ruteo, no después,
cambio de orden de pipeline no trivial); aceptar el patrón como límite
conocido del autoruteo y documentarlo en `docs/glosario.md`/
`restricciones-kicad.md` para que el agente lo anticipe en vez de
descubrirlo por DRC.

**Severidad:** no bloquea flujos existentes (evidencia: `J4.3`/`J5.3` no
impidieron que macro-pad-12 completara 15/15 nets ruteables en sesión 32).
Candidato a investigación P4.0-style si aparece una 2ª instancia
confirmada de este sub-patrón específico (capas iguales, no opuestas).

## P2 — Correcciones puntuales con evidencia repetida

| Item | Evidencia | Estado |
|---|---|---|
| `run_erc()` posiciones ÷100 | F-03 (D2), F-19b-12 (19b) | Abierto, confirmado 2 veces. |
| `health()` no distingue `PROJECT_NOT_CONFIGURED` vs `PROJECT_PATH_NOT_FOUND` | F-02 | Abierto. |
| `draw_board_outline` inmutable (sin `replace=true`/`delete`) | F-06 | Abierto. |
| Asimetría `delete_track` sí / `delete_footprint` no | D-R3, D-R8 | Abierto, sin ADR — **sigue así deliberadamente**. Escaló a P0 en sesión 31 (F-V1-02: refs duplicados bloqueaban `route_board`), pero sesión 31b cerró ese caso sin tocar la asimetría — resolvió por anotación (`set_footprint_ref`), no por borrado. Ver ADR-0013: un `delete_footprint` general sigue rechazado, ADR-0010 vigente sin excepción. |
| Doc del lock no-reentrante del bridge (`self._lock` no es reentrante) | Sesión 19d | Pendiente: documentar en `bridge/README.md` o similar. |
| Issue upstream a Freerouting sobre `gui.enabled=true` colgando la JVM (R9) | Sesión 17 | Mitigado en código; issue no abierto (no urgente). |
| `move_footprint` no dispara refill de zonas — un DRC leído de disco tras mover pads sobre un plano mide fill rancio, no el estado real | Sesión 26, investigación 26 §2 | Nota de proceso: `fill_zones()` obligatorio tras colocación masiva, antes del baseline DRC. No es un bug de la tool (su contrato nunca prometió refill) — es un punto ciego de brief/protocolo de dogfooding. |
| `route_board`/netclasses descartan silenciosamente `diff_pair_width`/`diff_pair_gap`/`diff_pair_via_gap` (`bridge/rules_reader.py:217`) — el flujo no puede dirigir el ruteo de un par diferencial por netclass, aunque el `.kicad_pro` lo declare | Sesión 32 (hallazgo estructural, H1b reformulada) | Abierto. Verificado además que **ningún** proyecto ANAVI del catálogo (dev-mic, miracle-emitter, word-clock, macro-pad-12) asigna netclasses en la práctica (`"nets": []` en todos) — la brecha de código nunca fue ejercitada por ningún candidato real hasta ahora. Candidato a Nivel C/D si aparece un board con asignación real. |

## P2 — Release polish (post-Fase 4, pre-release Open Source)

No bloqueante hoy — condicionado a las 3 validaciones exitosas de la
Validation Suite (sesiones 31-33 según `hoja-de-ruta-v5.md`) y al cierre
de P1 (ya cumplido, sesión 30). Retomar en sesión 34+ (preparación de
release Open Source), no antes.

- **ADR-0014 en adelante** (drift corregido sesión 31c — el número 0013
  ya lo consumió sesión 31b, ver `docs/adr/0013-refs-duplicados-por-anotacion-no-borrado.md`):
  documentar el mecanismo indocumentado de edge clearance de Freerouting
  (hoy solo entendido por ingeniería inversa de bytecode, D-V3.5).
- **Docs de arquitectura para colaboradores externos.**
- **Test canario de Freerouting edge clearance.**
- **Licencia + README + CONTRIBUTING.**
- **Limpieza de código muerto** de sesiones intermedias.

## P3 — CRUD de esquemático (R12)

Las tools de escritura de sch son puramente aditivas:
`add_symbol`, `set_value`, `set_footprint`, `connect_pins`, `clone_symbols`.
No existe `delete_wire`, `delete_label`, `add_no_connect`, `set_symbol_attr`,
`sync_symbol_from_library`. Un agente puede **diseñar** un sch desde cero
pero no **corregirlo** — cualquier defecto requiere GUI humana. Bajado de P1
a P3: v7 lo excluye explícitamente del alcance de Fase 3 (que se concentra en
el ciclo de ratificación PCB), habilita autocorrección de sch pero no es
bloqueante para la consolidación en curso.

- **Origen:** F-19b-01 a 05, 08, 10 (sesión 19b). Confirmado sin ejercitar en
  D3/D4 porque el sch pre-corregido no necesitó tocarse.
- **Esfuerzo estimado:** L (varias tools, cada una con su propio patrón de
  verificación de efecto vía kicad-skip).

## P3 — `get_world_context(kind="sch")` falla con `#PWR*`/`#FLG*` (R13)

Set-difference asimétrico entre posiciones (todo símbolo) y netlist
(kicad-cli excluye pseudo-símbolos `#`-prefijados). Dispara
`KICAD_CLI_FAILED` en **cualquier** esquemático con símbolos de
alimentación/power-flag — no es un caso raro.

- **Origen:** D-19e.2, confirmado de nuevo como F-D4-01 en sesión 22.
- **Workaround vigente:** `export_netlist()` + parseo manual.
- **Esfuerzo estimado:** M.

## P3 — Loop de vías de `enforce_hole_clearance` posiblemente código muerto (R16, D-23.3)

En 3 corridas de investigación de sesión 23, el loop de vías de
`enforce_hole_clearance` (líneas 1996-2032 de `ipc.py`) nunca creó un keepout
`via_*`. Deuda técnica identificada pero **no se toca en Fase 3** salvo que
aparezca evidencia nueva de que importa — es investigación independiente.

- **Origen:** D-23.3 (sesión 23).
- **Esfuerzo estimado:** S para investigar, indeterminado para el fix.

## P3 — Ergonomía de colocación (hallazgo D4)

`get_footprint_neighbors` demostró ROI real cuando se usó en conectores con
drill mecánico (J1/J2 en D4: ahorró ~34 min vs. D3). **Pero** la directiva
que lo acotaba a "solo conectores" dejó un punto ciego: 2 `courtyards_overlap`
+ 1 `solder_mask_bridge` en pasivos/ICs que no se verificaron con la tool.

- **Propuesta:** ampliar el uso recomendado de `get_footprint_neighbors` a
  toda colocación manual, no solo conectores — es un cambio de proceso/brief,
  no de código.

### P3 → CERRADO (sesión 29 D7) — F-D5-01: isla GND sin vía al plano (incidente aislado)

En D5 (sesión 25), tras la primera corrida de `route_board`, dos caps
adyacentes (C2/C3, ambos GND) quedaron unidos entre sí por un track pero sin
vía propia al plano B.Cu — a diferencia de otros caps de la misma columna
(C4/C6), que sí recibieron vía del autorouter. 1 error DRC
(`unconnected_items`), diagnosticado con `get_tracks`+`get_footprint_neighbors`
(visibilidad completa) y resuelto con un `add_via` puntual, sin re-ruteo.

**No es señal V3** (no es clearance/hole_clearance/mismatch/persist_failed
contra la zona GND) — es un dato de comportamiento de Freerouting: el motor
puede conectar pads dentro de un net entre sí sin garantizar conectividad
global de esa isla al plano fillado.

- **Estado:** cerrado como observación puntual de D5, no patrón
  sistemático.
- **Evidencia:** trigger de promoción a P2 investigación era "2
  dogfoodings independientes reproducen el patrón". Resultado final:
  D5=1, D6=0, D7=0 → 1/3, no cumplido.
- **Sin trigger de reapertura** salvo que reaparezca en futuros
  dogfoodings.
- **Origen:** F-D5-01, sesión 25. Ver `docs/historico/sesiones/25-reporte.md`
  y `docs/historico/sesiones/29-reporte.md` §Fricciones.

### P3 → CERRADO (sesión 29 D7) — F-D6-01: variabilidad inherente Freerouting/JVM

- **Estado:** cerrado como variabilidad inherente. Sin acción de código.
- **Evidencia:** 3 mediciones D7 (`+3V3`, `/SDA`, `/NSS`) + 2 D5 + 2 D6
  = N=7 total. Sin patrón correlacional con grado de interconexión,
  tamaño del net, ni capas involucradas. Comparación directa sobre
  mismo net `/NSS`: D5=9-10s, D6=110-112s, D7=17.7s — varianza del
  proceso, no propiedad determinística.
- **Documentación pendiente de transferir a `docs/specs/restricciones-kicad.md`**
  (drift detectado en sesión 31: esta entrada afirmaba la transferencia
  hecha desde sesión 29, pero el archivo nunca se tocó — único commit en
  su historia es el de estado inicial): rango operativo esperable
  (9s-112s), advertencia "no asumir que un re-ruteo parcial es
  proporcionalmente barato al tamaño del net". Diff propuesto en sesión 31,
  pendiente de que el humano lo aplique (edición bajo F1, requiere
  levantar el deny de `.claude/settings.json` puntualmente).
- **Sin trigger de reapertura** a menos que aparezcan corridas >600s
  (timeout) o >60s consistentemente en flujos productivos.
- **Origen:** F-D6-01, sesión 28. Ver `docs/historico/sesiones/28-reporte.md`
  y `docs/historico/sesiones/29-reporte.md` §Fricciones.

## P4 — Diferidos sin urgencia (re-evaluar con evidencia nueva)

Nice-to-have, para después de convergencia de Fase 3 (Fase 4).

- **Eval A** (TOON vs JSON/CSV compacto): benchmark de comprensión+tokens
  pendiente desde sesión 04, diferido reiteradamente. Condiciona la
  re-evaluación de ADR-0009 (port a Rust).
- **Soporte multi-hoja** en `get_world_context`/`get_context_delta` de disco
  (`UNSUPPORTED_HIERARCHY`). Depende de si los proyectos reales del humano
  son multi-hoja (pregunta abierta, nunca respondida formalmente).
- **Rotación en `move_footprint`.**
- **Timeout adaptativo** (en vez de fijo) para operaciones IPC largas.
- **Limpieza de tracks huérfanos** (P2.3, sesión 17b).
- **Guard cross-proceso** (sesión 17b) — hoy el lock del bridge protege
  contra concurrencia intra-proceso, no cross-proceso.
- **`add_zone` con hueco interior** (polígono con isla).
- **Opción Y de F-D4-02** (inyectar keepout real al DSN de Freerouting en
  vez de refill+enforce post-ruteo): descartada por ahora en favor de la
  Opción X (sesión 24); reconsiderar solo si aparece evidencia de
  intermitencia real del enfoque actual.
- **A* para causas de nets bloqueadas** en `route_board` — posiblemente ya
  innecesario tras las mejoras de contrato JSON de sesiones 17/19/24.
- ~~**Bbox de validación por Edge.Cuts real** (hoy es footprints ± 100mm)~~ —
  **cerrado sesión 31b** (drift corregido sesión 31c): implementado como
  unión de Edge.Cuts (±10mm) y enjambre de footprints (±100mm) en
  `board_outline`/`board_bbox_mm`/`read_board_context`. Ver F-V1-01 en
  §P1 arriba y ADR-0013 (contexto del fix compañero).
- **Unificación de `POST_ROUTE_PERSIST_FAILED`, `POST_ZONE_PERSIST_FAILED`
  y `POST_ROUTE_REFILL_SKIPPED`**: sesión 27 introdujo
  `POST_ZONE_PERSIST_FAILED` para `fill_zones` y `add_zone(fill=True)`.
  Semánticamente equivalente a `POST_ROUTE_PERSIST_FAILED` (sesión 24,
  `route_board`). Coexisten temporalmente por decisión conservadora (no
  tocar `route_board` en sesión 27). Sesión 32b sumó un tercer código,
  `POST_ROUTE_REFILL_SKIPPED` (cierre de F-V2-REFILL-SILENCIOSO) —
  semánticamente distinto de los otros dos (el refill NO se intentó, vs.
  "se intentó y no se pudo persistir"), pero la misma familia de
  "algo del contrato D-23.2/ADR-0012 no se cumplió". Refuerza la deuda,
  no la resuelve. Deuda: unificar en un solo código compartido (por
  ejemplo `PERSIST_CONTRACT_FAILED` o `TOOL_PERSIST_FAILED`), deprecando
  los tres actuales — o mantener `POST_ROUTE_REFILL_SKIPPED` separado si
  la distinción semántica (intentado-y-fallido vs. no-intentado) se
  considera valiosa al momento de unificar. Impacto bajo — el contrato
  JSON de las tools no cambia (los códigos siguen exportándose como
  strings; el llamador puede aceptar todos). Prioridad post-Fase 3, no
  bloqueante.

## Higiene menor (sin severidad, cuando haya tiempo)

- ~~Fixture `tests/fixtures/despertador-routed/` puede haber quedado stale
  tras correcciones de sch posteriores — verificar antes de reusar en D5.~~
  Resuelto: D5 (sesión 25) verificó (sch sin cambios, ERC idéntico) y
  regeneró el fixture con el ruteo nuevo.
- Contador agregado de `post_fallback` en `health()` para monitoreo pasivo de
  la derivación local (propuesto en `historico/analisis/ANALISIS-ESTADO-Y-BACKLOG.md`
  §C3, nunca implementado, 0 fallbacks observados hasta ahora).
- **P3 — `move_footprint` sin `check_no_external_disk_edit()`** (hallazgo
  auditoría 34a): a diferencia de `add_track`/`add_via`/`set_footprint_ref`/
  `delete_tracks_bulk`, `move_footprint` sólo llama `_guard_live_stale()`
  (D-14.1), no la red P3.2 independiente de `base_snap`. Inconsistencia
  menor — `_guard_live_stale()` sigue cubriendo el caso principal (ruteo
  pendiente de recarga). Candidato trivial (misma familia que A7, fix
  sesión 34a) para una futura pasada de limpieza de consistencia; no
  amerita sesión propia. Ver `docs/analisis/auditoria-contratos-bridge.md`
  §3 (ficha `move_footprint`).
- **P2 — `delete_zone`/`add_keepout_zone` no recalculan fills vecinos**
  (hallazgos A2/A3, auditoría 34a, nuevos — sin precedente previo en
  BACKLOG): ninguna de las dos corre `refill_zones()` tras mutar geometría
  que puede interactuar con zonas de cobre existentes (borrar una zona de
  cobre con vecinas solapadas; crear un keepout `no_pours` sobre un fill
  ya existente). Sin evidencia empírica de impacto real (a diferencia de
  A1, que sí tiene precedente F-D3-01) — documentado como limitación
  conocida, no como fix ciego (D-30.1/D-32c.1: investigar antes de
  fixear). Promover a investigación si la Validation Suite lo evidencia.
  Detalle: `docs/analisis/auditoria-contratos-bridge.md` §3 (fichas
  `delete_zone`, `add_keepout_zone`).

---

## Cómo mantener este documento

Al cerrar un ítem, moverlo a una nota de una línea en el reporte de la sesión
que lo cerró (no acumular aquí "cerrados"). Al abrir uno nuevo desde una
fricción de dogfooding, añadirlo con su origen (F-NN, sesión) para que
`docs/historico/` siga siendo la fuente de evidencia completa.
