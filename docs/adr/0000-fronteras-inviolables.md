# ADR-0000 — Fronteras inviolables del proyecto

**Fecha:** 2026-07-08 · **Estado:** aceptado · **Fuente:** CLAUDE.md §"Fronteras inviolables"

## Contexto

Agentes LLM editan este código. Sin límites explícitos, un agente puede
"arreglar" un golden editándolo, renombrar un código de error, o añadir una
dependencia útil sin discusión. Cada acto rompe un contrato consumido por
otro subsistema (LLM en runtime, catálogo público, build).

## Decisión

Cinco fronteras que ningún agente cruza sin aprobación humana explícita:

- **F1 — Specs y goldens son contratos.** No se modifican `docs/specs/**` ni
  `tests/golden/**`. Un golden que falla NO se "arregla" editando el golden:
  se reporta el diff exacto al humano. Excepción única:
  `docs/specs/tool-catalog.md` se actualiza por el agente al añadir tools o
  códigos nuevos (jamás renombrar existentes).
- **F2 — Gates inviolables.** No se modifica lógica ni umbrales de G1–G5
  (ver [ADR-0003](0003-gates-de-autonomia.md)).
- **F3 — Códigos de error estables.** La taxonomía de `tool-catalog.md` es
  API pública consumida por otro LLM en runtime. No se renombra. Se añade.
- **F4 — Sin dependencia de KiCad 11 / nightlies.** Objetivo primario KiCad
  10; mínimo KiCad 9.0 (ver [ADR-0002](0002-versiones-de-kicad.md)).
- **F5 — Sin dependencias nuevas sin aprobación.** No se edita `pyproject.toml`
  para añadirlas. Propuesta con justificación de una línea; el humano decide.

## Consecuencias

- Un agente que actúa dentro del margen permitido no rompe contratos con
  terceros: la sorpresa queda acotada.
- El agente **pregunta** ante discrepancias spec↔realidad en lugar de
  resolverlas unilateralmente. El costo por interrupción es aceptado.
- Añadir tools/códigos nuevos requiere disciplina en el commit (spec + código
  + tests) pero no aprobación previa: la fricción está reservada al
  renombrado/eliminación (F3) y a las dependencias (F5).
- Si una regla parece equivocada, se cambia el ADR en un commit propio antes
  de actuar: nunca excepciones "por esta vez".
