# Sesión 19d — Fixes puntuales pre-Dogfooding 3

**Tipo:** DEV sobre kicad-mcp, **nueva rama** `sesion/19d-fixes-preD3` desde
`sesion/19-zonas` (no desde master — mantenemos 19 sin mergear hasta que 19d
cierre).

**Origen:** Los 3 items diferidos de la sesión 19c (§Recomendación, punto 4)
+ verificación de una hipótesis colateral del arquitecto.

**Criterio de cierre:** los 4 caveats operacionales del D3 declarados por la
sesión 19c pasan de "documentar en el prompt del D3" a "resueltos en las
tools" o "confirmados como no resolubles en el timebox de esta sesión".

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4. No refactorizar. No agregar features
fuera de este alcance. **Cada tarea tiene fix trivial (< 40 líneas) o queda
documentada para 20b.**

---

## Tarea 19d.0 — ¿`add_track` tiene el mismo bug de net-hijacking? (timeout: 20 min)

**Hipótesis del arquitecto:** el reporte 19c confirmó que `add_via`
reasigna el net al del cobre físico bajo el punto (H2). El código de
`add_track` resuelve el net **idéntico** a `add_via` según la exploración
de 19c. Es plausible que `add_track` tenga el mismo comportamiento
silencioso cuando un track cruza cobre ajeno durante creación.

### Investigación (misma metodología que 19c Bloque 1)

1. Reiniciar KiCad limpio con el fixture despertador-routed.
2. Test controlado con tools MCP en vivo:
   - **Baseline vacío:** `add_track(net="GND", start=<punto vacío>, end=<otro
     punto vacío>)` sobre zona sin cobre ajeno. Verificar con
     `get_tracks(bbox=)` que quedó con net="GND".
   - **Cruce con cobre ajeno:** identificar un segmento existente de otro net
     (ej: `/MOSI`), tirar un `add_track(net="GND")` que CRUCE ese segmento.
     Releer con `get_tracks`. ¿El track resultante quedó como GND o como
     /MOSI?

### Resultado esperable
- **Si tiene el bug:** aplicar el mismo fix que 19d.1 al bridge de
  `add_track`.
- **Si no lo tiene:** documentar la asimetría (por qué add_via reasigna
  pero add_track no), agregar test de regresión para que no aparezca en el
  futuro.

**Timeout duro 20 min.** Si el experimento se complica, documentar la duda
y pasar a 19d.1 con solo el fix de `add_via`.

---

## Tarea 19d.1 — Fix `add_via` con verificación post-creación

**Diseño del fix (bridge/ipc.py, método `add_via`):**

1. Tras `create_items()` con la vía nueva, hacer un round-trip inmediato:
   obtener el KIID del ítem creado, releerlo con `get_items_by_id([kiid])`.
2. Comparar el `net.name` real con el `net` solicitado.
3. Si coinciden → OK, retornar como antes.
4. Si no coinciden → **revertir la creación** (borrar el ítem recién
   creado) y lanzar `NET_ASSIGNMENT_MISMATCH` (código nuevo, F3 respetada)
   con `data`:
   ```
   data.requested_net: "+3V3"
   data.actual_net: "/MOSI"
   data.at: [x, y]
   ```
   Hint: "el punto solicitado pisa cobre de otro net; verificar coordenadas
   o borrar cobre ajeno primero".

**Si 19d.0 confirmó que `add_track` también tiene el bug:** aplicar el
mismo patrón a `add_track` (con el ajuste natural de que un track tiene
dos endpoints y el hijacking puede ocurrir en cualquier punto del recorrido).

**Test de regresión unit** con fake bridge que simula el reasignamiento —
debe capturar el mismatch y devolver el error nuevo.

**Test integration_gui** que reproduce el escenario del Bloque 1 de 19c
(add_via sobre cobre /MOSI) y verifica que ahora el error se dispara
correctamente en vez de devolver silenciosamente.

---

## Tarea 19d.2 — `delete_tracks_bulk` (nueva tool)

Motivación: el Bloque 3 de 19c requirió 266 llamadas individuales de
delete_track/delete_via para llevar el board a 0 cobre. El D3 va a repetir
esa fricción si iteramos ruteos. Fix trivial con enorme retorno.

### Firma propuesta

```
delete_tracks_bulk(
  net=None,          # filtro por net
  bbox=None,         # filtro por bbox [min_x, min_y, max_x, max_y]
  layer=None,        # filtro por layer
  include_vias=True, # borrar también vías que coincidan con el filtro
  dry_run=False      # si true, solo lista qué borraría sin ejecutar
) -> {"tracks_deleted": N, "vias_deleted": M, "snap_id": <nuevo>}
```

Al menos un filtro obligatorio (mismo patrón que `get_tracks`). Sin
filtros → `INVALID_PARAMS` con hint (borrar todo el cobre a ciegas es
riesgoso).

**Modo `dry_run=True` obligatorio para uso inicial en D3.** El agente
puede ver cuántos ítems borraría antes de comprometerse.

Reutilizar el guard reforzado de P3.2 (mutación de disco). Refill de zonas
post-bulk (D-14.1 sigue vigente).

Test unit + integration_gui básico (borrar todo GND del fixture, verificar
que quedaron 0 tracks GND).

---

## Tarea 19d.3 — Actualizar `test_zones_e2e_gui.py` al escenario del Bloque 3

El test P4.5 actual (re-ruteo parcial con plano + keepout) fue el escenario
que no convergió. El escenario del D3 real es "desde cero con plano".

### Cambios al test

1. Reemplazar el flujo actual por: partir de fixture →
   `delete_tracks_bulk(net=<todos>, dry_run=False)` (o equivalente que
   lleve a 0 cobre) → `add_zone(GND, B.Cu, bbox)` → `fill_zones()` →
   `route_board(timeout_s=900)` → verificaciones.
2. **NO agregar keepout antes del ruteo** — 19c demostró que bloquea. Si
   el test quiere ejercitar keepout, agregarlo POST-route como paso
   separado y verificar el DRC.
3. Verificaciones cuantitativas del gate P4.5 original:
   - `tracks_final < N_ORIGINAL` (menos tracks GND porque el plano absorbe)
   - `vias_final <= vias_original`
   - Área del plano >= 60% del board

Con este flujo el test debe converger consistentemente (Bloque 3 tardó 8.5
min, presupuesto 900s deja margen).

---

## Fuera de alcance

- Refactor de bridge/ipc.py más allá del fix puntual.
- Cualquier cambio a route_board (contrato JSON, timeouts adaptativos, A*
  de bloqueador).
- Cualquier cambio al sch del despertador (19b).
- Cualquier feature nueva de zonas.

## Reporte final (`docs/sesiones/19d-reporte.md`)

- Resultado de 19d.0 (add_track: tiene el bug sí/no + evidencia).
- Diff-resumen por tarea.
- Contrato final de las tools modificadas/nuevas.
- Estado de los 4 caveats de 19c: cuáles se cerraron en tools, cuáles
  siguen como "documentar en prompt D3".
- Bugs reales encontrados durante los fixes.

## Env vars

Las mismas de 19c:

```bash
export KICAD_MCP_GUI_TEST=1
export KICAD_MCP_PROJECT=/tmp/gui-test-project
export KICAD_MCP_GUI_REF=U1
export KICAD_MCP_FREEROUTING_JAR=/home/astra/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar
```

**KiCad reiniciado desde cero antes de arrancar.**
