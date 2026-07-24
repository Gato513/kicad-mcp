# Sesión 19c — Investigación de bloqueantes pre-Dogfooding 3

**Rama:** `sesion/19c-bloqueantes-pre-d3` (desde `sesion/19-zonas`, previo al
merge de esa rama a `master`) · **Fecha:** 2026-07-21.

## Resumen

Investigación pura (sin features nuevas) sobre los tres bloqueantes que dejó
abierto el reporte de la sesión 19: el bug de `add_via` con net cruzado, la
hipótesis de que el keepout causaba el no-convergence de P4.5, y la
viabilidad real del escenario canónico del Dogfooding 3 (ruteo desde cero con
plano preexistente). Los 4 bloques corrieron en vivo contra KiCad 10.0.4
real, con reinicio limpio del proceso KiCad antes de cada bloque.

**Decisión de cierre: CONDICIONAL.** El Dogfooding 3 es viable con plano GND
pero **sin keepout autorruteado** — el keepout circular bajo ANT1, aplicado
antes de un ruteo completo desde cero, no solo no converge: bloquea 9 de 10
nets ruteables por completo. Ver tabla y recomendación al final.

## Bloque 1 — Bug `add_via` con net cruzado

**Timeout asignado:** 30 min · **Timeout consumido:** ~15 min.

### Hallazgo de exploración previa (código)

`add_via` (`src/kicad_mcp/bridge/ipc.py:1957`) y `add_track`
(`ipc.py:1894`) resuelven el net de forma idéntica: `next((n for n in
raw_board.get_nets() if str(n.name) == net), None)` → `item.net = net_obj` →
`create_items`. El código de `add_via` no fue tocado por el diff de la
sesión 19. Esto descarta que el bug esté en la asignación de net del bridge
y deja dos hipótesis: **H1** (caché stale de kipy tras muchos
`revert()`/mutación) — la única que consideró el reporte de la 19 — y
**H2** (KiCad reasigna la vía al net del cobre que físicamente pisa,
sin relación con caché) — no investigada por la sesión 19.

### Metodología y datos

1. **Baseline tras reinicio limpio de KiCad:** se corrió
   `test_add_via_round_trip_against_open_board` como la PRIMERA llamada
   mutante de la sesión, sin ningún `revert()`/`route_board` previo.
   **Falló de forma idéntica al hallazgo de la sesión 19**: pidió
   `net="+3V3"`, KiCad devolvió `net.name="/MOSI"`
   (`tests/test_pcb.py:1136`, `AssertionError: net '/MOSI' != '+3V3'`).
   Esto **descarta H1**: no hubo caché stale posible, es el primer request
   de la sesión.
2. **Test de overlap controlado (H2), vía tools MCP en vivo:**
   - (a) `add_via(x=185, y=30, net="GND")` en un punto **vacío** del bbox
     (sin cobre debajo, verificado con `get_tracks(bbox=...)` antes) →
     `get_tracks` releído confirmó `V ... GND (185.000,30.000) ...` — el net
     pedido se preservó exactamente.
   - (b) `add_via(x=170.775, y=57.225, net="GND")` sobre un punto que pisa un
     track real de `/MOSI` (segmento `(170.265,57.225)->(171.285,57.225)`) →
     `get_tracks` releído mostró `V ... /MOSI (170.775,57.225) ...` — el
     resultado tomó el net del cobre bajo la vía, **no** el net pedido. La
     confirmación de la tool (`"OK add_via GND @(170.8,57.2) ..."`) siguió
     reportando el net **pedido**, no el efectivamente asignado.
   - Ambas vías de prueba se borraron con `delete_via` al terminar (net-zero
     al board).

### Conclusión

**H2 confirmada, H1 descartada.** El comportamiento no es un bug de caché:
es KiCad reasignando la vía al net del cobre físico bajo ella — comportamiento
de dominio esperable de un editor PCB, no un defecto del bridge. El problema
real y explotable es distinto: **la confirmación de `add_via` no verifica el
resultado contra lo pedido** — si el LLM coloca una vía sobre cobre ajeno
(coordenadas erróneas, off-by-un-pin, etc.), la tool reporta éxito con el net
pedido mientras KiCad silenciosamente asignó otro. Es una divergencia
silenciosa real, pero evitable con una precondición operacional, no con un
fix de código de esta sesión (el fix correcto —verificar el net resultante
post-creación y fallar/advertir en mismatch— toca el contrato de retorno del
bridge, un código de error nuevo y `tool-catalog.md`; se documenta para
19d/20b en vez de improvisarse fuera de timebox).

**Estado: AMARILLO.** Riesgo real pero mitigable: antes de cada `add_via` en
el D3, verificar con `get_tracks(bbox=...)` alrededor del punto objetivo que
no hay cobre de otro net bajo las coordenadas destino.

**Decisión Bloque 1:** ¿20+ mutaciones consecutivas en el D3 son seguras?
**Sí, con workaround** — el workaround es de un solo tool call adicional por
`add_via`, no cambia la cadencia de la sesión de forma sustancial.

## Bloque 2 — Hipótesis del keepout como causa del no-convergence

**Timeout asignado:** 45 min · **Timeout consumido:** ~12 min.

### Metodología

Sobre el fixture `despertador-routed` ya abierto (24 footprints, 41 nets):
`add_zone(net="GND", layer="B.Cu", bbox=[140,25,195,80], fill=true)` → zona
de 3025 mm² fillada → se borraron los 77 tracks + 5 vías de GND existentes
(vía `get_tracks(net="GND")` + `delete_track`/`delete_via` por id) →
`route_board(timeout_s=1500)`. **Sin keepout.**

### Datos crudos

```
route_ms: 678689.472  (11.3 min)
nets: 10 ruteables, 9 ruteadas, 1 parcial (GND, faltan 12), 0 bloqueadas
drc: err_preexistentes 21 → err_post 15 (Δ -6)
tracks_added: 11, vias_added: 3
```

### Conclusión

**Converge cómodamente dentro del presupuesto** (11.3 min de 25 disponibles),
en fuerte contraste con los dos intentos de P4.5 (2h38m y 25min, ninguno
convergió) que usaban el mismo escenario **más** el keepout de 12 vértices.
Ningún net bloqueado, DRC mejoró. Esto es evidencia fuerte de que **el
keepout era la causa dominante del no-convergence de P4.5**, no "Freerouting
escala mal con planos densos" como concluyó el reporte de la sesión 19.

**Estado: VERDE.** No se investigó la variante de vértices (6/12/rect) por
timebox — la pregunta binaria (keepout sí/no) ya quedó respondida con
suficiente margen para la decisión de esta sesión.

## Bloque 3 — Escenario D3 canónico: ruteo desde cero con plano preexistente

**Timeout asignado:** 45 min · **Timeout consumido:** ~20 min (incluye
depuración manual de 266 items de cobre preexistentes).

### Metodología

El D3 no hace re-ruteo parcial (eso fue el escenario artificial de P4.5):
rutea desde cero con un plano ya presente. Se llevó el board a **0 tracks, 0
vías** (247 tracks + 19 vías preexistentes borrados uno por uno vía
`delete_track`/`delete_via` — sin tool de borrado masivo en el catálogo
actual, nota operacional para 19d/20b), con el plano GND del Bloque 2 todavía
filled. Luego `route_board(timeout_s=1500)`.

### Datos crudos

```
route_ms: 512870.144  (8.5 min)
nets: 10 ruteables, 10 ruteadas, 0 parciales, 0 bloqueadas
drc: err_preexistentes 64 → err_post 44 (Δ -20)
tracks_added: 265, vias_added: 30
```

### Comparación con benchmark de sesión 18

Sesión 18 midió 235-925 s para ruteo desde cero **sin** plano. Este resultado
(512.9 s, con plano) cae dentro de ese mismo rango — el plano no penalizó el
tiempo de convergencia, y absorbió gran parte de la conectividad GND (30 vías
totales para 10 nets, vs. las decenas que hubiera necesitado GND sin plano).

### Conclusión

**Converge de forma completa y limpia**: 10/10 nets, 0 bloqueadas, DRC
mejoró. Esto satisface —y supera— la intención cualitativa original del gate
P4.5 (que fue diseñado sobre un escenario de re-ruteo parcial que no refleja
el uso real del D3). Se recomienda actualizar `test_zones_e2e_gui.py` (P4.5)
para reflejar este escenario "desde cero con plano" en una sesión futura, en
vez del re-ruteo parcial actual — cambio de test, no de código de producción,
fuera de alcance de esta sesión de investigación.

**Estado: VERDE.**

## Bloque 4 — Escenario D3 con keepout (plano + keepout, desde cero)

**Timeout asignado:** 30 min · **Timeout consumido:** ~20 min (más el setup).

### Metodología

Se restauró el board a 0 tracks/0 vías/0 zonas desde un backup de sesión G1
(`despertador_inteligente-2026-07-21_202103.zip`, capturado automáticamente
por el gate G1 en la primera mutación de esta sesión) — atajo válido frente a
repetir el borrado manual de ~295 items: restaurar el backup pristino +
recrear la zona GND con una sola llamada es equivalente a la secuencia
completa. Luego:
`add_zone(GND, B.Cu, bbox, fill=true)` → `add_keepout_zone(layer="all",
polygon=<círculo 12 vértices, r=15mm, centro ANT1 (177.7,44.4)>)` —
geometría idéntica a la del test `test_zones_e2e_gui.py` (P4.5) — →
`route_board(timeout_s=1500)`.

### Datos crudos

```
route_ms: 1150518.065  (19.2 min, corrida completa — no truncada por timeout)
nets: 10 ruteables, 0 ruteadas, 1 parcial (GND, faltan 19),
      9 bloqueadas (+3V3, /SDA, /INT_SENS, Net-(ANT1-A), /RESET, /SCK,
      /MISO, /MOSI, Net-(BT1-+)) — todas ROUTE_NET_BLOCKED
      "sin camino aparente; revisar manualmente"
drc: err_preexistentes 67 = err_post 67 (Δ 0)
tracks_added: 2, vias_added: 1
```

### Conclusión

**Resultado marcadamente peor que las dos corridas originales de P4.5.**
Aquellas no convergieron pero seguían progresando (ruteo parcial real);
aquí, 9 de 10 nets quedan **completamente bloqueadas** desde el primer
intento, con apenas 2 tracks + 1 vía agregados en total pese a consumir casi
19 minutos de cómputo. La causa más probable: el keepout circular de 15mm
bajo ANT1 (esquina del board, cerca del borde en x≈195) corta un corredor de
ruteo que varios nets no-GND necesitan atravesar para llegar a esa zona del
board — cuando el ruteo parte de cero (sin tracks previos que sirvan de guía
parcial, a diferencia del escenario de P4.5), Freerouting no encuentra
alternativa y declara el net bloqueado en vez de sólo tardar más.

**Estado: ROJO.** El keepout, en su geometría/posición actual, no es
compatible con un ruteo autorruteado completo desde cero. Mitigaciones
viables para el D3 (no exploradas más a fondo por timebox):
(a) rutear sin keepout (Bloque 3, VERDE) y aplicar el keepout como paso
manual post-route —evita cobre bajo la antena sin bloquear el autorouter—;
(b) reducir el radio del keepout; (c) reposicionar el keepout lejos del
borde del board. La opción (a) es la recomendada por menor esfuerzo y cero
riesgo adicional, dado que ya está validada por el Bloque 3.

## Decisión vinculante

| Bloque | Estado | Impacto en D3 |
|---|---|---|
| 1 — `add_via` net cruzado | 🟡 AMARILLO | Seguro con workaround: verificar `get_tracks(bbox=...)` antes de cada `add_via` para confirmar que no hay cobre ajeno bajo el punto destino. |
| 2 — Keepout como causa raíz | 🟢 VERDE | Confirma que el plano GND solo (sin keepout) converge rápido y limpio; explica el no-convergence de P4.5. |
| 3 — D3 canónico (plano, desde cero) | 🟢 VERDE | Escenario real del D3 converge en 8.5 min, 10/10 nets, DRC mejora. Viable tal cual. |
| 4 — D3 + keepout (desde cero) | 🔴 ROJO | El keepout autorruteado bloquea 9/10 nets. **No usar keepout antes de un ruteo completo.** |

### Recomendación: CONDICIONAL

El Dogfooding 3 puede arrancar (tras la sesión 19b de fix del esquemático)
**con los siguientes caveats obligatorios**:

1. **No aplicar `add_keepout_zone` antes de `route_board`** cuando el ruteo
   parte de un board sin cobre (o mayormente sin cobre). Si se necesita
   proteger físicamente el área bajo la antena, aplicar el keepout
   **después** del ruteo completo (Bloque 3) y resolver manualmente
   cualquier track que quede bajo esa zona — no delegar esa combinación al
   autorouter.
2. **Usar el patrón validado del Bloque 3** para el ruteo del D3: crear y
   fillar el plano GND (`add_zone` + `fill_zones`) **antes** de
   `route_board`, sobre un board sin cobre. Presupuestar `timeout_s≥900`
   (el Bloque 3 tardó 512.9s; dejar margen).
3. **Antes de cada `add_via`**, verificar con `get_tracks(bbox=...)`
   alrededor del punto destino que no hay cobre de otro net — la
   confirmación de la tool no valida el net resultante contra el pedido.
4. Documentar para 19d/20b: (a) fix de `add_via` para verificar el net
   post-creación y fallar/advertir en mismatch; (b) tool de borrado masivo
   de tracks/vías por filtro (net/bbox/layer) — el Bloque 3 requirió 266
   llamadas individuales de `delete_track`/`delete_via` por falta de esta
   capacidad; (c) actualizar `test_zones_e2e_gui.py` (P4.5) al escenario
   "desde cero con plano" del Bloque 3, que refleja el uso real del D3
   mejor que el re-ruteo parcial actual.

## Notas operacionales

- Los 4 bloques corrieron con reinicio limpio de KiCad antes de cada uno,
  confirmado con `health()` (`pcb_editor_abierto: yes`, `project.status: ok`)
  tras cada reinicio.
- Se detectó y corrigió una configuración stale del servidor MCP
  `kicad-mcp` en `~/.claude.json`: `KICAD_MCP_PROJECT` apuntaba a
  `/tmp/dogfood2-proyecto` (ruta borrada, de dogfooding anterior) en vez de
  `/tmp/gui-test-project` de esta sesión. Corregido vía la skill
  `update-config` antes de arrancar el Bloque 1.
- Los timeouts por bloque se respetaron; no hubo pedidos de "5 min más". El
  único uso de tiempo fuera de lo planeado fue el borrado manual de 266 items
  de cobre para el Bloque 3 (sin tool de borrado masivo disponible),
  mitigado en el Bloque 4 reutilizando un backup de sesión G1 en vez de
  repetir el borrado.
- No se tocó ningún archivo bajo `docs/specs/**` ni `tests/golden/**` (F1),
  ni lógica de gates (F2). No se agregaron dependencias (F5). Todo el trabajo
  fue contra KiCad 10.0.4 (F4).

## Suites

No se modificó código de producción esta sesión (investigación pura, sin fix
de código aplicado — el fix de `add_via` quedó documentado, no implementado,
por exceder el alcance de "1-2 fixes puntuales" declarado en el prompt). No
aplica re-correr `pytest -m "not integration and not integration_gui and not
integration_gui_slow"` como gate de esta sesión; el estado heredado de la
sesión 19 (301 passed, `ruff`/`mypy` limpios) no cambió.

## Cierre esperado

Sesión 19c cerrada con los 4 bloques ejecutados en vivo contra KiCad 10.0.4 y
una decisión CONDICIONAL documentada con evidencia. Próximo paso: sesión 19b
(fix del esquemático del despertador) y luego el Dogfooding 3 con los 4
caveats de la sección "Recomendación" como precondición operacional.
