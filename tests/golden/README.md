# Golden files del encoder TOON

**Estado: BORRADOR pendiente de validación humana.** Generados a partir de
`docs/specs/toon-v1.md` y verificados por consistencia interna programática
(cabeceras vs. conteos, membresías de nets, orden de refs, presupuestos).
Falta la validación final del humano: leer cada `expected.toon` contra la
spec y firmar quitando esta línea y el estado BORRADOR.

## Regla F1 (CLAUDE.md)

Estos archivos son **inmutables** para el agente. Un test golden que falla
significa que el encoder está mal, no el golden. Si crees que el golden está
mal: detente y repórtalo al humano. Añadir golden nuevos está permitido;
modificar existentes requiere bump del formato a v2 y aprobación.

## Estructura

- `001_minimo/` — codificación básica sin degradación. `input.json → expected.toon`
- `002_degradacion/` — colapso de nets de poder bajo presupuesto (`params.json`
  fuerza `max_tokens: 220`; GND=13 y 3V3=12 miembros superan el umbral de 8)
- `003_delta/` — ΔTOON: `base.json` (snap 7) + `input.json` (snap 8) +
  `params.json` (foco U1, radio 40 mm) → `[+]`, `[~N]` ×2, `[AREA]`

El test compara **igualdad exacta de string** (byte a byte, un `\n` final).

## Sesión 36 — encoders ad-hoc de `tools/pcb.py` (R2, no son TOON)

`004_pcb_tracks_canarios/`, `005_pcb_zones_canarios/` y
`006_pcb_component_detail_canarios/` cubren `_encode_tracks`,
`_encode_zones` y `_encode_component_detail` — tres formatos propios (F1
intacto: no son TOON, lo dicen sus propios docstrings) que interpolaban
`net_name`/`ref`/`pad.number` sin sanitizar. La sesión 36 les aplicó
`toon.encoder._sanitize` (§5) antes de interpolar. `expected.txt`, no
`.toon`, para no sugerir que son el formato TOON.

Cada golden trae un ítem por canario en el campo sanitizable: `\n`, `|`,
`"`, y `" "` (espacio). Los tres primeros quedan neutralizados por
`_sanitize`. El espacio, al momento de esta sesión, **no** — es el
delimitador posicional de las tres gramáticas (space-delimited a nivel de
ítem, a diferencia de TOON que es `|`-delimited) y `_sanitize` no lo toca.
El ítem con espacio en cada golden (`T4`/`Z4`/pad 4-5) quedó marcado como
**caracterización**: fija el gap conocido, no el comportamiento deseado.
Sesión 37 cerró el gap con `_sanitize_space_delimited` (`tools/pcb.py`) — los
tres ítems cambiaron a `_` en lugar de conservar el espacio; ver §Sesión 37.
`004` también incluye un ítem con `net_name=""` (vía `V1`): gap pre-existente
distinto, `CopperItem.net_name` no tenía fallback `or "-"` a diferencia de
`ZoneItem`/`PadDetail` — cerrado en sesión 38, ver §Sesión 38.

## Sesión 37 — cierre del gap del espacio

`_sanitize_space_delimited` (`tools/pcb.py`) compone `_sanitize` con
neutralización de todo whitespace (`re.sub(r"\s", "_", ...)`), aplicado en
los 5 sitios space-delimited: `net_name` en `_encode_tracks` (segmentos y
vías) y `_encode_zones`, `number`/`net_name` de pad en
`_encode_component_detail`. El header `DETAIL|<ref>|pcb|...` (`|`-delimitado)
no se toca — un espacio ahí es inocuo (H2). Los ítems de caracterización
(`T4`/`Z4`/pads 4-5) cambiaron exactamente en la línea anticipada; ningún
otro ítem se movió (H3). Ver `docs/historico/sesiones/37-reporte.md`.

## Sesión 38 — fallbacks de `layer`/`net_name` vacíos + `filter_desc`

Cierra tres de los gaps que la decisión #4 de sesión 36 había dejado sin
veredicto (`docs/BACKLOG.md`, entrada `P1-1`):

- `CopperItem.net_name` vacío ahora cae a `"-"` (`_encode_tracks`), como ya
  hacían `ZoneItem.net_name`/`PadDetail.net_name`. Canario: vía `V1` en
  `004_pcb_tracks_canarios` (preexistente, ya no colapsa la columna).
- `CopperItem.layer` (`str | None`) y `ZoneItem.layer` (puede ser `""`) caen
  a `"-"`. `CopperItem.layer=None` sólo ocurre hoy en vías, cuya línea no
  emite `layer` — el fallback es defensivo (cierra el flanco a nivel de
  tipo), no correctivo. `ZoneItem.layer=""` sí es alcanzable (`bridge/ipc.py`,
  `layers[0] if layers else ""`) y el fallback ahí sí es correctivo. Canarios
  nuevos: `T5` en `004_pcb_tracks_canarios` (`net_name=""` + `layer=null` en
  la misma línea) y `Z6` en `005_pcb_zones_canarios` (`layer=""`).
- `filter_desc` de los headers `TRACKS|v1|...`/`ZONES|v1|...` ahora sanitiza
  cada componente (`net`/`layer`/`kind`/etc.) antes de ensamblar, en
  `_tracks_filter_desc`/`_zones_filter_desc` — **no** en el string ya
  ensamblado, porque `_sanitize` neutraliza `|`/`:`, que son la gramática
  propia del header. `layer` era el único componente sin validar antes de
  llegar al header: el fix es correctivo (cierra una inyección real vía
  parámetro MCP no validado), no defensa en profundidad. Sin cobertura
  golden posible — el arnés de `test_pcb_encoders_golden.py` recibe
  `filter_desc` ya ensamblado — cubierto en
  `tests/test_pcb_session38_filter_desc.py`.

`006_pcb_component_detail_canarios` no cambió: `bbox_source` y `p.layer`
(candidatos evaluados esta sesión) quedaron refutados — ver
`docs/historico/sesiones/38-reporte.md`.
