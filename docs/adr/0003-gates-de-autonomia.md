# ADR-0003 — Autonomía con gates deterministas (D3)

**Fecha:** 2026-07-08 · **Estado:** aceptado · **Fuente:** arquitectura §11 D3 · **Refuerza:** [ADR-0000](0000-fronteras-inviolables.md) F2

## Contexto

Pregunta P3: cuánta autonomía dar al agente entre revisiones humanas.
Confirmar cada operación mata el flujo; delegar sin límites permite
mutaciones destructivas, drift y bypasses por prompt injection. Pedir
confirmación al humano *desde el prompt* del agente es defensa en papel: un
prompt inyectado puede alterarla.

## Decisión

El agente ejecuta mutaciones sin aprobación por operación. La intervención
humana se concentra en **cinco gates** — tres automáticos, dos interactivos —
que viven en el servidor, no en el prompt del modelo:

| Gate | Disparador | Tipo | Acción |
|---|---|---|---|
| G1 | Inicio de sesión de mutación | Automático | Backup a `.kicad-mcp/backups/`; commit si hay git |
| G2 | Borrado >5 ítems / sobrescritura / design rules | Interactivo | Elicitation; sin ella → `GATE_DENIED` |
| G3 | `export_manufacturing` | Automático | Bloqueado si ERC/DRC severidad error |
| G4 | 200 ops o 150 k tokens emitidos | Interactivo | `BUDGET_EXCEEDED`; requiere confirmación |
| G5 | Invalidator detecta edición externa (mtime) | Automático | Pausa; fuerza re-sync completo |

Umbrales configurables por el usuario; códigos de error literales de la
taxonomía F3.

## Consecuencias

- Los gates son inviolables desde el prompt: modificarlos requiere editar
  código auditado. Defensa concreta contra prompt injection vía campos.
- G1 obliga a rollback trivial en toda sesión de mutación.
- G3 → "el agente pasó DRC" es enunciado con contenido, no flag configurable.
- G4 visibiliza costo acumulado y exige autorización para superarlo.
- G5 acepta la race con edición externa (KiCad no emite eventos) y la
  mitiga a posteriori.
- Frontera F2: cambiar lógica/umbrales requiere aprobación humana.
