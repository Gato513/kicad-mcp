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
`_sanitize`. **El espacio NO** — es el delimitador posicional de las tres
gramáticas (space-delimited a nivel de ítem, a diferencia de TOON que es
`|`-delimited) y `_sanitize` no lo toca. El ítem con espacio en cada golden
(`T4`/`Z4`/pad 4-5) es de **caracterización**: fija el gap conocido, no el
comportamiento deseado — si sesión 37 lo cierra, ese golden (no los otros)
se espera que cambie, con ADR. `004` también incluye un ítem con
`net_name=""` (vía `V1`): gap pre-existente distinto, `CopperItem.net_name`
no tiene fallback `or "-"` a diferencia de `ZoneItem`/`PadDetail`.
