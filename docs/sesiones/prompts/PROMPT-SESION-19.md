# Sesión 19 — P4: Zonas (plano GND + keepouts)

**Tipo:** DEV sobre kicad-mcp, **nueva rama** `sesion/19-zonas` desde `master`
(tras merge de `sesion/18-recarga-programatica`).

**Origen:** Hoja de ruta v3, P4. Evidencia dura del Dogfooding 2:
- El agente ruteó GND como "estrella de pistas" (aceptable a 8MHz/I2C pero
  subóptimo para RF a 915 MHz del RFM69CW). No hay primitiva de plano.
- El brief del despertador pedía "keepout circular ~15mm bajo ANT1 en ambas
  capas". No existe primitiva de keepout.
- Consecuencia real: la placa fabricable del D2 tiene retorno de corriente
  degradado y la zona de antena tiene cobre GND en B.Cu que debería estar
  vacía. Esto no rompe funcionalidad a 915 MHz baseline pero sí compromete
  patrón de radiación y consumo del transceptor.

**Criterio de cierre (gate):** re-rutear el fixture `despertador-routed` con
un plano GND en B.Cu y un keepout circular bajo ANT1 → Freerouting respeta
la zona y el keepout → DRC sin errores nuevos → `get_zones` ve las 2 zonas
con KIIDs estables. Comparativo cuantitativo: el nuevo ruteo debe tener
**menos vías** que la versión sin plano (el plano absorbe retorno de GND,
eliminando parte del ruteo dedicado).

## Fronteras

F1–F5 vigentes. **F4 explicitado (heredado de sesión 18):** asume KiCad
10.0.4 exclusivamente; no asumir KiCad 11. Toda superficie kipy usada debe
verificarse contra KiCad 10.0.4 vivo, no contra documentación de versiones
posteriores.

D-17.1 (route_board JSON estructurado) y D-V3.1 (recarga programática vía
`Board.revert()`) vigentes. **Esta sesión NO revoca ninguna decisión previa
salvo que la investigación P4.0 lo justifique con evidencia.**

---

## Tarea P4.0 — Investigación: superficie IPC de zonas + comportamiento Freerouting

**Como en sesión 18, investigación primero.** Motivo: kipy tiene lagunas de
documentación, D-12.4 fue arreglada retroactivamente por P3.0. No repetir
el error de comprometerse a un diseño sin evidencia empírica.

**Investigar (documentar en `docs/investigacion/19-zonas-ipc.md`) antes de
escribir código productivo:**

### 1. Superficie de zonas en kipy 0.7.1 (KiCad 10.0.4)

Enumerar los métodos de `kipy.board.Board` y clases relacionadas para zonas:
- ¿`Board.get_zones()` existe? ¿Devuelve qué?
- ¿Hay `create_zone()`, `add_zone()`, o zonas se crean vía `create_items()`
  con protobuf `Zone`?
- ¿Cómo se distingue una zona de cobre de una keepout zone en el modelo?
- ¿Existe algo como `Board.fill_zones()` o `Board.refill_all_zones()`?
- ¿Los KIID de zonas persisten como los de tracks (D-16.1)?

Cada método candidato → probarlo en vivo contra KiCad 10.0.4 con el
proyecto de prueba abierto. **Test no destructivo** como en sesión 18: usar
`Board.revert()` para limpiar antes/después si es necesario.

### 2. Comportamiento de Freerouting con zonas preexistentes

Crítico y no obvio. El `.kicad_pcb` puede tener zonas ya rellenadas; cuando
`route_board` exporta al DSN:
- ¿Las zonas viajan al DSN? ¿Como `(plane ...)` o como `(via_type ...)`?
- ¿Freerouting rutea encima del plano (asumiendo que el fill se recalcula
  después) o intenta evitarlo?
- ¿El SES que devuelve Freerouting interactúa con las zonas?
- ¿La corrida sobre el fixture `despertador-routed` cambia si primero se le
  agrega un plano GND?

Test empírico: agregar manualmente (vía kipy o edición controlada) una zona
GND rectangular al fixture → correr `route_board` con la implementación
actual → observar qué pasa. **NO comitear ese fixture modificado**; es solo
diagnóstico.

### 3. Estrategia de fill

Las zonas de cobre en KiCad no son "cobre bruto" — son áreas que se rellenan
según reglas (thermal relief para pads del mismo net, clearance a otros
nets, prioridad de zonas superpuestas). El fill es costoso computacionalmente
y KiCad lo hace en dos modos:
- **Live fill**: durante interacción GUI, más caro.
- **Save fill**: al guardar, se persiste al `.kicad_pcb`.

Investigar:
- ¿kipy expone control sobre cuándo se rellena?
- ¿Se puede crear una zona "vacía" (sin fill) y rellenarla explícitamente
  con una tool nueva `fill_zones()`?
- ¿Freerouting necesita las zonas rellenadas para respetarlas, o le basta
  con los límites?

### 4. Reporte

Al final de P4.0, entregar:
- Los 4 puntos de arriba resueltos con evidencia empírica.
- **Superficie mínima viable propuesta** para las tools nuevas (add_zone,
  add_keepout_zone, get_zones, fill_zones, delete_zone) — firmas concretas,
  no genéricas.
- **Riesgos identificados**: qué NO va a estar cubierto por el MVP y por
  qué, con justificación.
- **Confirmación humana explícita** (via `AskUserQuestion`) antes de pasar
  a P4.1. Si el humano no responde en la sesión, ejecutar la propuesta
  documentando la asunción — mismo patrón que sesión 18.

---

## Tarea P4.1 — `add_zone` + `get_zones` (post-investigación)

**Sujeto al resultado de P4.0.** Diseño esperable, ajustable según hallazgos:

### `add_zone(net, layer, bbox=|polygon=, ...)` — nueva tool

- `net`: nombre del net al que la zona se conecta (típicamente "GND", pero
  también "VCC" válido).
- `layer`: capa de cobre (`F.Cu`, `B.Cu`, o interna si aplica en KiCad 10).
- `bbox=[min_x, min_y, max_x, max_y]` (mm) para rectángulos — caso más común.
- `polygon=[[x1,y1], [x2,y2], ...]` para formas arbitrarias — hasta 20
  vértices en MVP; más queda fuera de scope de esta sesión.
- Devuelve `{"zone_id": <KIID>, "filled": true|false, "area_mm2": <número>}`.
- **Refill automático por defecto** (para el caso común de "quiero un plano
  GND funcional"). Flag `fill=false` para diferir.
- Validaciones:
  - `net` debe existir en el board actual → si no, `NET_NOT_FOUND`.
  - `layer` debe ser capa de cobre válida.
  - Polígono debe ser simple (no self-intersecting) → si no,
    `INVALID_ZONE_GEOMETRY` (código nuevo, F3 respetada).

### `get_zones(layer=|net=|max_tokens=)` — nueva tool (paralela a get_tracks)

- Al menos un filtro obligatorio (mismo patrón que `get_tracks` de sesión 16).
- Devuelve zonas de cobre Y keepouts, con `kind: "copper"|"keepout"`.
- Cada zona: `id` (KIID), `kind`, `net` (null si keepout), `layer`,
  `bbox`, `area_mm2`, `vertices` (solo si `polygon`, no bbox), `filled`.
- Presupuesto de tokens con el mismo mecanismo que `get_tracks` (D-V3.2).

### Reutilización del guard reforzado (P3.2)

`add_zone` es mutación de disco → debe pasar el mismo guard `mtime` que
`add_track`/`add_via`/`save_board`. Extender la lista de tools guardadas en
`validation.py`.

---

## Tarea P4.2 — `add_keepout_zone` — keepouts

Los keepouts son estructuralmente similares a zonas de cobre pero NO se
conectan a un net y bloquean cierto contenido:

```
add_keepout_zone(
  layer,                   # o "all" para todas las capas
  bbox=|polygon=,
  no_tracks=true,          # default: bloquear tracks
  no_vias=true,            # default: bloquear vías
  no_pours=true,           # default: bloquear otros pours de cobre
  no_footprints=false      # opcional
)
```

Devuelve `{"zone_id": <KIID>, "keepout_flags": {...}}`.

Caso de uso canónico: keepout circular ~15mm bajo `ANT1` del despertador.
Como el MVP soporta polígonos de hasta 20 vértices, se puede aproximar un
círculo con 12-16 vértices — suficiente para RF a 915 MHz.

---

## Tarea P4.3 — `fill_zones()` + integración con route_board

### `fill_zones()` — nueva tool

- Sin parámetros: refill de TODAS las zonas del board.
- Con `zone_id=<KIID>` opcional: refill solo esa zona.
- Devuelve `{"zones_filled": N, "duration_ms": T}`.
- **Idempotente**: llamarla dos veces seguidas no rompe nada.
- Mutación de disco → guard reforzado.

### Integración con `route_board`

Dos escenarios que la investigación P4.0 debe resolver, pero el diseño
esperable es:

1. **Si hay zonas de cobre existentes en el board**: `route_board` las
   respeta (Freerouting entiende el DSN correctamente). Si no las respeta
   nativamente, `route_board` debe hacer un pre-procesamiento del DSN
   inyectando las zonas como `(plane <net>)` scopes.

2. **`route_board` debe hacer refill post-route**: después del ruteo, si
   había zonas, el fill puede necesitar recalcularse porque hay tracks
   nuevos. Agregar un paso `fill_zones()` al final de `route_board`
   internamente, opcional vía flag `refill=true` (default).

Contrato JSON de `route_board` gana:
```
"zones": {
  "existentes": N,        // zonas ya en el board pre-route
  "refilladas": M,        // cuántas se refillearon post-route
  "fill_ms": T
}
```

---

## Tarea P4.4 — `delete_zone(id=)` — completar CRUD

Simétrico con `delete_track`/`delete_via` de sesión 16:
- `delete_zone(id=<KIID>)` con firma por KIID.
- Error `ZONE_ID_STALE` si el KIID no existe (análogo a `TRACK_ID_STALE`).
- Guard reforzado.

---

## Tarea P4.5 — Test E2E: plano GND + keepout en fixture

**El test que cierra el gate.** Sobre `tests/fixtures/despertador-routed/`
(fixture con 313 tracks + 21 vías + DRC 1 error):

1. Copiar fixture a tmpdir.
2. Contar tracks y vías iniciales.
3. **Agregar plano GND en B.Cu** cubriendo el board entero:
   `add_zone(net="GND", layer="B.Cu", bbox=<board_bbox>)`.
4. **Agregar keepout circular bajo ANT1**: obtener `x,y` de ANT1 vía
   `get_component_detail("ANT1")`, `add_keepout_zone` con polígono de 12
   vértices aproximando radio 15mm centrado ahí.
5. `fill_zones()` explícito para asegurar estado consistente.
6. `run_drc()` → registrar errores actuales (baseline post-zonas).
7. **Borrar TODOS los tracks de GND** — el plano debería absorberlos:
   `get_tracks(net="GND")` → `delete_track(id=)` en loop.
8. **Re-rutear con route_board** — Freerouting debe respetar el plano GND
   (no crear vías de retorno redundantes) y el keepout (no meter cobre bajo
   ANT1).
9. `run_drc()` → **debe estar sin errores nuevos** respecto al baseline
   post-zonas.
10. **Verificación cuantitativa**:
    - `tracks_final <= tracks_inicial - tracks_gnd_borrados` (el plano
      absorbió parte)
    - `vias_final <= vias_inicial` (menos vías de retorno)
    - Área cubierta por plano GND >= 60% del área del board (heurística de
      "el fill funcionó")
11. `get_zones(layer="B.Cu")` → ve las 2 zonas con KIIDs estables.

**Métrica de éxito:** el test corre sin `pytest.skip`, sin fallar, y los 3
puntos de la verificación cuantitativa se cumplen.

---

## Fuera de alcance (no tocar en 19)

- **Reglas de zona avanzadas**: pad connection style (solid/thermal/none),
  clearance override por zona, prioridad entre zonas superpuestas. Usar los
  defaults de KiCad. Si el D3 exhibe fricción, sesión 19b.
- **Zonas en múltiples capas simultáneas** con una sola llamada. Una capa
  por `add_zone`.
- **Polígonos complejos** (>20 vértices, con huecos). MVP soporta polígonos
  simples convexos o cóncavos de hasta 20 vértices.
- **Sch fix del despertador** (sesión 19b, mi trabajo).

---

## Reporte final (`docs/sesiones/19-reporte.md`)

- **Reporte P4.0 completo** — 4 puntos con evidencia empírica, superficie
  MVP propuesta, opción confirmada.
- Diff-resumen por tarea.
- Contratos finales de las 4 tools nuevas.
- Cambios al contrato de `route_board` (campo `zones`).
- Test E2E de P4.5: pass/fail + números concretos de la verificación
  cuantitativa (tracks_inicial vs final, vias_inicial vs final, área del
  plano).
- Comparación cualitativa: DRC del ruteo original vs. ruteo con plano —
  ¿mejora, empeora, igual?
- Bugs reales encontrados (esperado: alguna sorpresa con Freerouting +
  zonas, o con el refill).

## Cierre esperado

Sesión 19 cerrada → sesión 19b (yo corrijo sch del despertador con las
tools ya con P1+P2+P3+P4) → sesión 20 (Dogfooding 3, meta ≥8/10).
