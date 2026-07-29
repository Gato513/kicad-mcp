# Sesión 31c — Reintento de sesión 31 (ANAVI Dev Mic, post-fix 31b)

**Rama:** `sesion/31c-reintento-anavi-dev-mic` (branch desde
`sesion/31b-fix-delete-footprint-y-bbox` — ni sesión 31 ni 31b estaban
mergeadas a `master` al arrancar; precondición verificada al inicio y
resuelta encadenando la rama, ver §Desviaciones abajo).
**Tipo:** reintento de la primera validación externa de la Validation
Suite (Fase 4), completando los Bloques 2-4 que sesión 31 dejó bloqueados
en `route_board` (F-V1-02) y que sesión 31b desbloqueó sin volver a
ejercitar el flujo completo.

## Resumen ejecutivo

**Escenario 5 de 7 — "Aprendizaje metodológico"**, con elementos del
**Escenario 2 — "éxito con matiz de umbrales"**. El flujo canónico
generalizó operacionalmente sobre ANAVI Dev Mic: `route_board` completó
(15/15 nets ruteables, 0 bloqueadas), 0 fricciones P0/P1 nuevas, 13/13
footprints colocados (vs 9/13 en sesión 31). De los 4 criterios D-30.3,
**1 de 4 cumple** (cobre) — pero esta refutación de H1 en su forma
estricta es evidencia sobre los **umbrales**, no sobre el **flujo**: el
board completó sin nets bloqueadas, con `footprint_count`/`net_count`
exactos al ground truth, y el único error DRC nuevo es una vía a un pad
de 0.30mm sin conectar (P2, no P0/P1).

**Link al reporte completo:**
`validation-suite/level-a/anavi-dev-mic/validation-report.md` (unificado
31→31b→31c, template para sesión 32).

## Desviaciones detectadas vs el prompt de la sesión

Verificadas contra el estado real del sistema antes de ejecutar, resueltas
con el arquitecto vía `AskUserQuestion`:

1. **`ef3e3dd` (sesión 31b) NO estaba mergeado a `master`** — el prompt
   asumía que sí. `master` seguía en `8c766bf` (consolidación
   post-sesión 30); ni sesión 31 ni 31b habían mergeado. Resuelto:
   branch desde `sesion/31b-fix-delete-footprint-y-bbox` (encadenar
   31→31b→31c), sin tocar `master`.
2. **`/tmp/gui-test-project/` no existía** — el prompt lo describía como
   el fixture despertador "que no se toca". Sesión 31 había reubicado ahí
   el `working/` de ANAVI (patrón D-27.1) y luego se limpió. Resuelto:
   se rehizo el Bloque 1 (copia fresca del despertador para el gate GUI,
   luego reubicación a ANAVI), con el gate GUI corrido **una sola vez, al
   inicio** (decisión del arquitecto, ya que sesión 31c no toca `src/`).
3. **`working/` NO necesitaba reset** — ya estaba en el estado correcto
   post-Bloque 1 de sesión 31 (0 tracks/vías/zonas, 13 footprints en
   `(0,0)`, 4× `REF**`, hashes de ground truth idénticos a los
   registrados). No se corrió `prepare_working.py` (además, el script
   aborta si el directorio destino ya existe).

Ninguna de las tres afectó el resultado — se resolvieron antes de tocar
el flujo canónico.

## Qué pasó

1. **Fase 0 + gate GUI**: entorno OK (14 OK/2 WARN no bloqueantes). Gate
   GUI del DoD corrido una sola vez al inicio contra copia fresca del
   despertador: `test_pcb_session21_hole_clearance_gui.py` 2/2 +
   `test_pcb_session27_zone_persist_gui.py` 2/2 (nota de proceso: el
   marker correcto de `session21` es `integration_gui`, no
   `integration_gui_slow` — corregido en la corrida). Suites offline (376
   passed) e integration (29 passed) verdes.
2. **Bloque 0/1**: precondiciones verificadas, entorno reubicado a ANAVI
   (3 handoffs humanos), baseline DRC 507 (444/63) coincidente exacto con
   sesión 31.
3. **Bloque 2 — flujo canónico completo**:
   - **Resolución de refs**: 4 llamadas `set_footprint_ref`, 3 exitosas
     (`MH1`/`MH2`/`MH3`) + 1 `INVALID_PARAMS` **por diseño** (tras 3
     renombres, la 4ta instancia ya no está duplicada — ADR-0013 rechaza
     estructuralmente renombrar refs únicos). La 4ta mounting hole quedó
     con el ref literal `REF**`, único en el board. Sin duplicados
     verificado con `read_board_context`.
   - **Colocación**: 13/13 footprints movidos (100%, vs 69% en sesión
     31 — las 3 `MH*` antes bloqueadas por F-V1-02 ahora se pudieron
     colocar). Verificado sin overlaps con `get_footprint_neighbors` en
     los 6 puntos más ajustados.
   - **Zona GND + refill + `route_board`**: completó. 15/15 nets
     ruteables ruteadas, 0 bloqueadas, `route_ms` 184.8s (~3 min). El
     pre-check `DUPLICATE_REFS` no se disparó — **confirma H1b**.
   - **Incidente de proceso**: tras `route_board`, un diálogo modal de
     KiCad ("¿archivo cambió afuera, recargar?") bloqueó el hilo de UI y
     causó `KICAD_NOT_RUNNING` transitorio. Resuelto con un handoff
     humano adicional.
   - **Refill final + DRC de cierre**: 63 total (18 err/45 warn).
4. **Bloque 3 — comparación D-30.3**: 1 de 4 criterios cumple (cobre,
   -10.3%, margen cómodo). Tracks falla por margen estrecho (-33.1% vs
   ±30%). Vías falla por margen amplio (+200% vs ±20%, base de 2 vías).
   DRC coincide en conteo (18=18) pero no en composición (1 tipo nuevo +
   2 tipos de warning cosméticos nuevos).

## Fricciones nuevas

- **F-V1c-01 (P2)**: vía GND en F.Cu-B.Cu no conectada al pad GND de MK1
  (0.30×0.30mm, el pad más chico del board), post-`route_board`+refill
  final. No bloqueó el flujo. No investigado en profundidad (fuera de
  alcance — sesión 31c no toca `src/` salvo P0/P1 trivial). Ver
  `docs/BACKLOG.md` §P2.

Ninguna fricción P0/P1 nueva.

## Análisis H2 (umbrales D-30.3) — primer punto real de evidencia

- **Cobre (±25%)**: bien calibrado — margen cómodo (14.7 puntos de
  holgura).
- **Tracks (±30%)**: sin evidencia de mala calibración — falla por
  margen estrecho (3.1 puntos), consistente con un umbral que discrimina
  bien.
- **Vías (±20%)**: **evidencia clara de mala calibración para bases
  pequeñas** — la base del ground truth (2 vías) es tan chica que
  cualquier resultado realista de autorouteo excede ±20%. Candidato a
  revisión: umbral absoluto o normalizado por nets.
- **DRC "0 errores nuevos"**: demasiado estricto — coincide en conteo
  total pero no distingue severidad eléctrica (relevante) de cosmética
  (silkscreen, no relevante).

**No se cierra la validez definitiva de D-30.3** — segundo de tres puntos
de evidencia formal (el primero, parcial, fue sesión 31; el tercero
vendrá de Nivel B/C). Input formal para revisión post-sesión 33.

## Actualizaciones documentales

- `validation-suite/level-a/anavi-dev-mic/validation-report.md`:
  unificado 31→31b→31c, template completo para sesión 32.
- `validation-suite/level-a/anavi-dev-mic/metrics.md`: output completo,
  comparación, análisis H2.
- `validation-suite/reports/coverage-matrix.md`: fila "Validación D-30.3
  cerrada" actualizada a ✓ + fila nueva de `route_board` end-to-end.
- `docs/BACKLOG.md`: `F-V1c-01` (P2) agregado; 2 drifts corregidos
  (bbox ya cerrado por 31b, numeración ADR-0013→0014+).
- `docs/CONTEXT.md`: estado post-31c (Validation Suite Nivel A cerrada);
  drift D-23.2 15/15→25/25 corregido.
- `docs/DECISIONES.md`: `D-31c.1` (cross-check obligatorio contra ADRs
  vigentes antes de fijar el marco de un prompt — decisión metodológica
  del arquitecto, origen: hallazgo de sesión 31b sobre ADR-0010).

## Próxima sesión

**Sesión 32 (Nivel B)**, candidato tentativo ANAVI Miracle Emitter o MOD
Control Chain Shield, a confirmar siguiendo el mismo patrón de admisión
de Bloque 0 de sesión 31. Arranca sólo tras el merge de esta rama.
