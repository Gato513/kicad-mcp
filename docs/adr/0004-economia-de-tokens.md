# ADR-0004 — Calibración de contexto para costo mínimo (D4)

**Fecha:** 2026-07-08 · **Estado:** aceptado · **Fuente:** arquitectura §11 D4

## Contexto

P4 pide defaults del refresh graduado, presupuesto TOON, tools visibles y
política de re-sync. Eje: minimizar tokens nuevos por turno (lo único que
controla el servidor) sin degradar comprensión ni inducir drift (S2). La
política óptima depende de Eval A/B; hasta entonces se necesitan defaults
razonables, medibles y modificables sin cambios de código.

## Decisión

Defaults del MVP, configurables e instrumentados vía el logging de RNF2:

- **Refresh tras mutación:** `confirmación` (~30 tok). `delta` solo si la
  operación cambió conectividad o falló; `full` bajo demanda, tras DRC/ERC,
  o forzado cada `re_sync_interval = 10` deltas.
- **Presupuesto TOON completo:** 800 tokens, con degradación automática por
  bloques funcionales (`docs/specs/toon-v1.md` §4).
- **Tools visibles por defecto:** 6–8 (`world`+`validate`+`discover_tools`).
- **Schemas/descripciones inmutables durante la sesión**, con prefijos
  estables → maximiza el hit-rate del prompt caching.
- **Confirmaciones sin eco de parámetros.**
- **Métrica de éxito:** ≤ 400 tokens nuevos promedio por operación en
  proyectos ≤ 50 componentes.

## Consecuencias

- La instrumentación (logging JSON con `tool_name`, `tokens_est`,
  `latency_ms`, `snap_id`) es requisito. Sin telemetría no hay recalibración
  post-MVP y las decisiones D4 quedan huecas.
- Estimador: `tokens_est = len(texto) / 3.5`, recalibrado en Eval A.
- `re_sync_interval = 10` es provisional hasta Eval B; parámetro clave contra
  el drift S2.
- Descripciones de tools estables → cambiarlas es cambio de contrato, requiere
  bump de versión del catálogo.
- Si la métrica del MVP no cumple ≤ 400 tokens, se recalibra con datos, no
  con intuición.
