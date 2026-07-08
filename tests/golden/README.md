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
