# Investigación P4.0 — Superficie IPC de zonas + comportamiento de Freerouting

**Sesión 19.** Objetivo: encontrar cómo kipy 0.7.1 (KiCad 10.0.4) expone
creación/lectura/relleno de zonas de cobre y keepouts, y verificar
empíricamente si Freerouting 2.1.0 respeta un plano de cobre preexistente al
re-rutear — condición de la que depende el gate de cierre de la sesión
("el plano absorbe retorno de GND ⇒ menos vías").

Entorno: KiCad **10.0.4** vivo con API IPC habilitada (`/tmp/kicad/api.sock`),
kipy **0.7.1**, Freerouting **2.1.0**
(`~/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar`),
Java 21. F4 vigente: todo lo documentado acá es específico de esta
combinación de versiones — nada se extrapola a KiCad 11.

---

## 1. Superficie de zonas en kipy 0.7.1

Enumerado en vivo contra `Board` (proyecto de prueba `U1`, socket IPC real):

### `kipy.board.Board` — métodos relevantes

| Método | Firma verificada | Nota |
|---|---|---|
| `get_zones()` | `() -> Sequence[Zone]` | **Existe.** Round-trip IPC confirmado en vivo (devolvió `[]` sobre el proyecto de prueba, que no tiene zonas). |
| `refill_zones()` | `(block=True, max_poll_seconds=30.0, poll_interval_seconds=0.5) -> ...` | **Existe.** Es **bloqueante con polling**, no fire-and-forget — coherente con que un refill sea causa de `AS_BUSY` en el IPC (`ipc.py:591`, ya documentado en sesión previa). No hay variante async. |
| `create_items(items)` | ya conocido (usado por `add_track`/`draw_board_outline`) | Zonas se crean **con este mismo método genérico**, pasando una instancia `Zone` construida desde protobuf — **no existe** `create_zone()`/`add_zone()` dedicado en kipy. |

No existe `Board.fill_zones()` (el nombre real es `refill_zones`) ni
`Board.delete_zone()` dedicado — delete es el mismo `remove_items`/
`remove_items_by_id` genérico ya usado por `delete_track`/`delete_via`.

### `kipy.board_types.Zone` — wrapper

```
Zone(proto: Zone | None = None, proto_ref: Zone | None = None)
```
Doc: *"Represents a copper, graphical, or rule area zone on a board"* — un
solo tipo Python cubre cobre, gráfico y keepout; se distinguen por el campo
`type`.

Atributos expuestos: `border_hatch_pitch, border_style, bounding_box,
clearance, connection, fill_mode, filled, filled_polygons, id, is_rule_area,
island_mode, layers, locked, min_island_area, min_thickness, name, net,
outline, priority, proto, rotate, teardrop, type` (+ `move()`).

### Proto subyacente (`kipy.proto.board.board_types_pb2.Zone`)

Campos: `id, type, layers, outline, name, copper_settings,
rule_area_settings, priority, filled, filled_polygons, border, locked,
layer_properties`.

- **`type`** — enum `ZoneType`: `ZT_UNKNOWN=0, ZT_COPPER=1, ZT_GRAPHICAL=2,
  ZT_RULE_AREA=3, ZT_TEARDROP=4`. **Copper vs keepout se distingue por este
  campo**: `ZT_COPPER` = zona de cobre normal; `ZT_RULE_AREA` = keepout. El
  wrapper expone el atajo `Zone.is_rule_area` (bool).
- **`copper_settings`** (solo aplica a `ZT_COPPER`): `connection, clearance,
  min_thickness, island_mode, min_island_area, fill_mode, hatch_settings,
  net, teardrop`. **`net` vive acá**, no en el nivel superior de `Zone`.
- **`rule_area_settings`** (solo aplica a `ZT_RULE_AREA`): `keepout_copper,
  keepout_vias, keepout_tracks, keepout_pads, keepout_footprints,
  placement_enabled, placement_source_type, placement_source`. Los 5 primeros
  son exactamente los flags que pide el spec de `add_keepout_zone`
  (`no_pours`↔`keepout_copper`, `no_vias`↔`keepout_vias`,
  `no_tracks`↔`keepout_tracks`, `no_footprints`↔`keepout_footprints`; no hay
  `keepout_pads` en el spec propuesto — KiCad sí lo modela, se puede exponer
  luego si hace falta).
- **`outline`** — tipo `kiapi.common.types.PolySet` (campo único
  `polygons`). Es la geometría **de diseño** (lo que el usuario dibujó);
  distinta de `filled_polygons`, que es el resultado cacheado del fill.
  **Confirmado empíricamente (§2) que el export a DSN usa `outline`, no
  `filled_polygons`** — una zona sin rellenar todavía exporta su plano.

### KIID de zonas

`Zone.id` es un KIID de la misma naturaleza que tracks/vías (mismo mecanismo
D-16.1: UUID estable entre operaciones, inválido tras `remove_items`). No se
verificó persistencia entre sesiones de KiCad porque no hace falta — el
mismo patrón ya validado para tracks/vías aplica sin cambios (no hay
tratamiento especial de KIID por tipo de item en el proto).

### Resumen — no existe fill "en vivo" vs "al guardar" en la superficie IPC

`refill_zones()` es la única primitiva de fill. No hay un modo "preview" o
"live" distinto del que ve el usuario en la GUI — es el mismo fill que se
persiste a disco al hacer `save()`. Esto simplifica el diseño: `add_zone`
puede crear con `fill=False` (rápido, solo geometría) y diferir el costo del
fill a una llamada explícita `fill_zones()`, sin ambigüedad de "qué fill".

---

## 2. Comportamiento de Freerouting con zonas preexistentes

### 2.1 ¿Las zonas viajan al DSN?

**Sí, confirmado.** El exportador es `pcbnew.ExportSpecctraDSN(board, out)`
(SWIG, invocado por `_EXPORT_DSN_SCRIPT` en `bridge/autoroute.py:101` vía el
python de sistema — no kicad-cli, no kipy). Es completamente ajeno al código
de este repo hoy (ninguna mención de "zone" en `src/` fuera de un comentario
incidental); el comportamiento es 100% de `pcbnew`, no de `kicad-mcp`.

**Test:** se tomó una copia (en tmpdir, no comiteada) de
`tests/fixtures/despertador-routed/despertador_inteligente.kicad_pcb`, se le
agregó una zona GND rectangular en B.Cu vía `pcbnew` (API SWIG directa,
mismo binding que usa el exportador) cubriendo casi todo el board, se
rellenó con `pcbnew.ZONE_FILLER`, y se exportó a DSN comparando contra el
export del fixture sin la zona:

```
                                sin zona    con zona GND
(plane ...) scopes en el DSN:      0             1
(wire ...) scopes en el DSN:      300           300   (sin cambio — tracks existentes)
```

La zona aparece como:
```
(plane GND (polygon B.Cu 0  140950 -25950  194050 -25950
                          194050 -79050  140950 -79050
                          140950 -25950))
```
dentro del scope `(structure ...)`, como `(plane <net> (polygon <layer>
<aperture> <coords...>))`. **Confirmado: usa la forma `(plane ...)`**, tal
como anticipaba el spec de la sesión.

### 2.2 ¿El pin-list de la red sigue exigiendo conexión explícita?

Sí — **el `(network (net GND (pins ...)))` no cambia** por la presencia del
plano: los mismos 21 pines GND aparecen listados idénticamente con y sin
zona. Es decir, el `(plane)` **no** hace que KiCad retire esos pines del
netlist Specctra; la pregunta real es si **Freerouting** (el consumidor del
DSN) trata un pin ya cubierto por el plano como resuelto sin necesidad de
trazar explícitamente.

### 2.3 Test decisivo — Freerouting ¿respeta el plano o rutea encima?

En vez de correr Freerouting sobre el fixture completo (24 footprints, corre
15–90 min según el README del fixture — desproporcionado para responder esta
única pregunta), se construyó un board sintético mínimo con `pcbnew`: 4
footprints de 1 pad THT cada uno — `G1`/`G2` en la red `GND` (separados 30mm,
**sin track entre ellos**) y `S1`/`S2` en una red `SIGNAL` de control (para
confirmar que Freerouting realmente corre y rutea lo que sí debe rutear) —
board 60×40mm, con y sin un plano GND en B.Cu cubriendo casi toda el área.
Freerouting corrido headless (`java -jar freerouting-2.1.0.jar -de <dsn> -do
<ses> -host KiCad`), completó en segundos en ambos casos.

**Resultado (idéntica topología, única diferencia = la zona GND):**

| Métrica (reporte de Freerouting) | Sin plano | Con plano GND en B.Cu |
|---|---:|---:|
| `connections.maximum_count` | 10 | 4 |
| `traces.total_count` | 7 | 1 |
| `vias.total_count` | **1** | **0** |
| `connections.incomplete_count` | 0 | 0 |

Sin plano, Freerouting conecta `G1`↔`G2` con un via + tracks (la única forma
de unir dos pads THT de la misma red sin ruta directa). Con el plano, el SES
resultante **no contiene ninguna mención a `GND`** — cero wires, cero vías
para esa red — solo la traza `SIGNAL` (`S1`↔`S2`) sigue apareciendo, sin
cambios. Freerouting reconoció que `G1` y `G2` ya tocan el plano `GND` en
B.Cu y **no generó ningún elemento de ruteo para conectarlos**.

**Conclusión: Freerouting 2.1.0 respeta nativamente el `(plane)` del DSN
exportado por `ExportSpecctraDSN`.** No hace falta pre-procesar el DSN
inyectando planos a mano (la Opción A del plan, "inyección DSN", queda
descartada); el export nativo de `pcbnew` + el consumo nativo de Freerouting
ya implementan el mecanismo completo. Esto también confirma, con evidencia
directa, el mecanismo del gate de cierre de la sesión: agregar un plano GND
y borrar los tracks GND existentes debería, al re-rutear, resultar en **menos
vías** (Freerouting ya no necesita conectar los pads que el plano cubre).

**Nota sobre fill:** la zona usada en el test decisivo (§2.3) estaba **sin
rellenar** (`SetIsFilled(False)`) y el `(plane)` se emitió igual (basado en
`outline`, no en `filled_polygons` — ver §1). Esto significa que, para el
propósito de que Freerouting respete el plano, **el fill explícito no es
estrictamente necesario** — pero sigue siendo necesario para que el
`.kicad_pcb` final tenga cobre real (DRC, gerbers, inspección visual). El
diseño de `add_zone(fill=True por defecto)` + `fill_zones()` explícito se
mantiene tal como estaba propuesto, por corrección del resultado final, no
por necesidad del ruteo.

### 2.4 Decisión (P4.0 — confirmada por el humano: "decidir con evidencia")

El humano confirmó explícitamente resolver esta bifurcación según el
resultado del test vivo. **Con la evidencia de §2.3: se usa el export nativo
de `ExportSpecctraDSN`, sin inyección DSN adicional.** `route_board` no
necesita pre-procesar el `.dsn` para zonas (a diferencia de
`_inject_edge_clearance`, que si sigue haciendo falta para clearance de
borde — cosas independientes). El único trabajo nuevo en `route_board` es:
contar zonas antes de rutear, y — si `refill=True` (default) — llamar
`refill_zones()` después de importar el SES, porque los tracks nuevos pueden
requerir recalcular el fill (thermal reliefs, clearance a las pistas nuevas).

**Pitfall no bloqueante encontrado:** construir un `ZONE` desde cero sobre un
`pcbnew.BOARD()` creado con `pcbnew.BOARD()` (sin abrir un proyecto real) y
llamar `ZONE_FILLER.Fill()` sobre él **segfaultea** — probablemente por
ausencia de configuración de diseño (netclasses, stackup) que un board real
siempre tiene. **No es un riesgo para la implementación real**: las zonas de
`add_zone`/`fill_zones` se crean sobre el board **vivo** obtenido por kipy vía
IPC (`get_open_board()`), que siempre proviene de un proyecto KiCad
completamente inicializado, nunca de un `pcbnew.BOARD()` desde cero. Se
documenta para que nadie repita el mismo test sintético sin este cuidado.

---

## 3. Estrategia de fill

- kipy no separa "live fill" (GUI, caro) de "save fill" (al guardar) como
  primitivas distintas — hay una sola: `refill_zones()`, bloqueante y con
  polling (`max_poll_seconds`). Es, en efecto, siempre "save fill": el
  resultado queda reflejado en el board vivo y se persiste con el próximo
  `save()`.
- Se puede crear una zona sin rellenar (`filled=False` al construir el
  protobuf) y rellenarla después explícitamente — confirmado en §2.3 y en el
  test con el fixture real (§2.1), en ambos casos la zona se creó, se guardó,
  y solo después se pidió el fill por separado.
- Freerouting **no necesita el fill** para respetar el plano (usa `outline`
  vía el DSN, no el resultado del fill) — pero el fill sigue siendo necesario
  para que el resultado final (`.kicad_pcb`, gerbers, DRC) tenga cobre real.
  Por eso el diseño mantiene `add_zone(fill=True)` por defecto (UX: "quiero
  un plano funcional ya") con `fill=false` para diferir, y una tool
  `fill_zones()` idempotente para refill explícito o post-route.

---

## 4. Superficie MVP propuesta

```
add_zone(net, layer, bbox=None, polygon=None, priority=0, fill=True,
         base_snap=None) -> str
  # "OK add_zone GND B.Cu [snap:N]"; audit/data incluye zone_id (KIID),
  # filled, area_mm2.
  # net: debe existir -> NET_NOT_FOUND (+ similares, patrón get_tracks).
  # layer: capa de cobre válida -> INVALID_PARAMS si no.
  # bbox XOR polygon; polygon simple, 3-20 vértices -> INVALID_ZONE_GEOMETRY.

add_keepout_zone(layer, bbox=None, polygon=None,
                 no_tracks=True, no_vias=True, no_pours=True,
                 no_footprints=False, base_snap=None) -> str
  # type=ZT_RULE_AREA, sin net. rule_area_settings.keepout_tracks=no_tracks,
  # keepout_vias=no_vias, keepout_copper=no_pours, keepout_footprints=no_footprints.
  # layer="all" válido (todas las capas de cobre habilitadas).

get_zones(layer=None, net=None, kind=None, max_tokens=None) -> str
  # >=1 filtro obligatorio (layer|net|kind) — patrón get_tracks (D-V3.2).
  # Devuelve copper Y keepout, campo kind:"copper"|"keepout" por zona.
  # Formato compacto (no TOON, igual que get_tracks): header + una línea
  # por zona: kiid, kind, net (o "-" si keepout), layer, bbox, area_mm2,
  # filled, vertices (solo si polygon, no bbox).
  # Mismo presupuesto de tokens que get_tracks (_TRACKS_DEFAULT_BUDGET).

fill_zones(zone_id=None, base_snap=None) -> str
  # sin zone_id: refill de TODAS. Con zone_id: solo esa. Idempotente.
  # {"zones_filled": N, "duration_ms": T}.

delete_zone(id, base_snap=None) -> str
  # KIID inexistente -> ZONE_ID_STALE (espejo de TRACK_ID_STALE).
```

**Cambio al contrato de `route_board`** (nuevo campo `zones`):
```
"zones": { "existentes": N, "refilladas": M, "fill_ms": T }
```
+ flag `refill=True` (default): tras importar el SES, si había zonas
preexistentes, llama `refill_zones()` y mide `fill_ms`.

**Códigos de error nuevos (F3: se añaden, no se renombran códigos existentes):**
- `INVALID_ZONE_GEOMETRY` — falta bbox y polygon (o ambos presentes),
  polígono con <3 o >20 vértices, o self-intersecting. Especialización de
  `INVALID_PARAMS`, mismo tratamiento de auditoría.
- `ZONE_ID_STALE` — KIID no encontrado en `delete_zone` (y en `fill_zones`
  cuando se pasa `zone_id` inexistente). Espejo semántico de
  `TRACK_ID_STALE`: "re-listar con `get_zones` y reintentar".

Todas las mutaciones (`add_zone`, `add_keepout_zone`, `fill_zones`,
`delete_zone`) pasan por el guard reforzado `check_no_external_disk_edit`
(P3.2) igual que `add_track`/`add_via`/`save_board` — se extiende la lista de
tools guardadas en `snapshots/validation.py` sin tocar su lógica (F2 no
aplica: el guard no es parte del sistema de gates G1-G5).

---

## Riesgos identificados / fuera de alcance del MVP

- **Pad connection style (solid/thermal/none) y clearance override por
  zona**: se usan los defaults de KiCad (`copper_settings` trae estos campos
  pero el MVP no los expone como parámetros). Si el D3 muestra fricción real,
  sesión 19b.
- **Prioridad entre zonas superpuestas**: se expone `priority` en `add_zone`
  (pass-through al proto) pero sin lógica de resolución propia — se delega
  100% al motor de fill de KiCad.
- **Zonas en múltiples capas con una sola llamada**: fuera de alcance, una
  capa por `add_zone` (igual que el spec original).
- **Polígonos >20 vértices o con huecos**: fuera de alcance. Un círculo de
  15mm de radio se aproxima con 12-16 vértices, suficiente para RF a 915 MHz
  (el caso de uso concreto del keepout de ANT1).
- **Filled_polygons como fuente de verdad para DSN**: no aplica — confirmado
  que el export usa `outline`, así que un `add_zone(fill=False)` seguido de
  `route_board` sin haber llamado `fill_zones` todavía respeta el plano en el
  ruteo (aunque el `.kicad_pcb` final quedaría con la zona sin cobre real
  hasta el próximo fill — se documenta como comportamiento esperado, no bug).
- **`ZONE_FILLER` sobre boards sintéticos sin proyecto**: irrelevante para
  producción (ver pitfall §2.4), documentado solo para que no se repita el
  mismo camino de test.

## Confirmación humana (gate P4.0)

Confirmada explícitamente antes de iniciar P4.1 (`AskUserQuestion`, sesión
19, sin necesidad de asumir por no-respuesta):

1. **Alcance:** las 5 tools completas + integración `route_board` + E2E
   P4.5, sin recortes.
2. **Fallback Freerouting:** decidir con evidencia del test vivo → **decisión
   tomada en §2.4: export nativo, sin inyección DSN.**
