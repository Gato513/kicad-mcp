# Índice de documentación — kicad-mcp

Mapa de qué leer y cuándo. Generado en la reorganización documental de
2026-07-24 (ver `docs/historico/analisis/` para el análisis completo que la
originó). El objetivo: que nadie —humano o agente— necesite abrir
`docs/historico/` para entender el estado actual del proyecto.

## Contexto mínimo para arrancar una sesión de trabajo

En este orden, y solo lo que aplique a la tarea:

1. **`CLAUDE.md`** (raíz) — siempre. Es el contrato del agente ejecutor:
   comandos, fronteras F1–F5, reglas de código, Definition of Done. Se
   auto-carga.
2. **`hoja-de-ruta-v4.md`** (raíz) — dirección estratégica vigente: secuencia
   de Fase 3, gates de salida por sesión, criterio de convergencia.
   `docs/ROADMAP.md` complementa con el historial de dogfooding pero ya no
   duplica la secuencia.
3. **`docs/BACKLOG.md`** — pendientes priorizados, para no reabrir un ítem ya
   conocido como investigación nueva.
4. El **prompt/brief específico** de la tarea que te haya dado el humano.

Eso alcanza para el 90% de las sesiones. Lo demás es "bajo demanda":

| Si vas a... | Leé |
|---|---|
| Tocar o agregar una tool MCP | `docs/specs/tool-catalog.md` (contrato F3 — actualizar en el mismo commit) |
| Tocar el encoder TOON o el delta | `docs/specs/toon-v1.md` (contrato F1 — nunca editar sin aprobación) |
| Cuestionar o extender una decisión existente | `docs/DECISIONES.md` → el ADR puntual referenciado |
| Entrar a un módulo que no conocés | `docs/arquitectura.md` |
| Toparte con un término de dominio EDA dudoso | `docs/glosario.md` |
| Verificar límites técnicos de KiCad | `docs/specs/restricciones-kicad.md` |
| Correr tests `integration_gui`/`integration_gui_slow` a mano | `docs/guias/pruebas-gui.md` |
| Poblar un esquemático con `add_symbol` | `docs/guias/guia-paleta.md` |
| Tocar `route_board`, `fill_zones` o `add_zone` | `docs/adr/0012-route-board-persist-contract.md` + `docs/investigacion/23-fd4-02.md` (obligatorios, ver DoD) |
| Reconstruir *por qué* se tomó una decisión o por qué falló algo | `docs/historico/` (ver mapa abajo) |

## Documentos activos (conocimiento vigente)

| Archivo | Qué es | Mantenido por |
|---|---|---|
| `CLAUDE.md` | Contrato del agente ejecutor | Humano, tras cada sesión que cambie reglas |
| `README.md` | Punto de entrada, quickstart, mapa de estructura | Humano/agente al DoD |
| `hoja-de-ruta-v4.md` (raíz) | Dirección estratégica vigente de Fase 3: secuencia estricta, gates de salida, criterio de convergencia | Humano, se reemplaza por v5 al cerrar Fase 3 |
| `docs/CONTEXT.md` | Visión del sistema, estado (Fase 3), riesgos — consolidado desde `CONTEXT-v7.md`, documento del arquitecto | Humano |
| `docs/DECISIONES.md` | Índice de ADR + decisiones vigentes no formalizadas | Humano/agente |
| `docs/ROADMAP.md` | Estado en una línea + historial de dogfooding (la secuencia vigente vive en `hoja-de-ruta-v4.md`) | Humano/agente |
| `docs/BACKLOG.md` | Pendientes priorizados | Humano/agente |
| `docs/arquitectura.md` | Diseño del sistema v0.2, principios, riesgos de fondo | Estable, rara vez cambia |
| `docs/glosario.md` | Dominio EDA/KiCad | Estable |
| `docs/componentes-pcb.md` | Referencia del PCB de prueba (202 comp.) | Estable |
| `docs/guias/guia-paleta.md` | Protocolo humano: paleta de símbolos para `add_symbol` | Humano |
| `docs/guias/pruebas-gui.md` | Protocolo manual de tests `integration_gui`/`integration_gui_slow` | Humano |
| `docs/specs/*.md` | **Contratos** (TOON, catálogo de tools, restricciones, fixtures) — frontera F1/F3 | El agente actualiza el catálogo como parte del DoD; el resto no se edita sin aprobación |
| `docs/adr/*.md` | Decisiones de arquitectura, una por archivo | Se agregan, nunca se editan retroactivamente |
| `docs/investigacion/*.md` | Investigaciones de causa raíz (P4.0-style), referenciadas desde ADR/specs — lectura obligatoria antes de re-hipotetizar sobre un bug ya investigado | Se agregan por sesión, no se editan retroactivamente |

## `docs/historico/` — evidencia del proceso, no operativo

No hace falta leer esto para trabajar hoy. Sirve para *arqueología*: entender
por qué una decisión se tomó, qué se probó y falló, o reconstruir el
contexto exacto de un bug ya cerrado.

| Carpeta | Contenido |
|---|---|
| `sesiones/` | 24 reportes de sesión (01–24, incluye 16b, 19b–19e) |
| `prompts/` | Prompts de sesión y de dogfooding — evidencia de cómo evolucionó el proceso de trabajo, no plantillas reutilizables |
| `auditorias/` | Auditorías puntuales pre-sesión (PRE-06, PRE-07) |
| `analisis/` | Análisis de estado/backlog de checkpoints intermedios (sesión 08) y la preparación inicial del repo para Claude Code |
| `roadmaps/` | Hojas de ruta v2 y v3, superadas por `hoja-de-ruta-v4.md` (raíz) |
| `dogfooding/` | Logs de fricciones de las 4 rondas de dogfooding (D1–D4) + brief del proyecto de referencia (despertador ATtiny85) |
| `CONTEXT-v7.md` | El handoff monolítico previo a esta reorg — post-sesión 24, fuente de la consolidación de 2026-07-24 en `docs/CONTEXT.md` + `DECISIONES`/`ROADMAP`/`BACKLOG`. (Reemplaza a `CONTEXT-v3.md`, congelado en sesión 19e, que el arquitecto retiró al entregar v7.) |

Nota: `investigacion/` **no** está bajo `historico/` — vive en
`docs/investigacion/` (ver tabla de arriba) porque `docs/adr/0012` y
`docs/specs/tool-catalog.md` (ambos contratos F1/nunca-editados-retroactivamente)
ya la referencian como lectura obligatoria, no como archivo. Un movimiento
anterior de esta misma reorg la había anidado bajo `historico/`, rompiendo
esas referencias — corregido.

**Regla:** si estás por citar algo de `historico/` en una decisión activa,
promové el resumen a `DECISIONES.md`/`hoja-de-ruta-v4.md`/`BACKLOG.md` y
dejá el puntero — no repitas el detalle completo fuera de `historico/`.

## Trabajo futuro fuera de esta reorg (no hacer todavía)

- `docs/metodologia/`: consolidar de `historico/prompts/` y `historico/sesiones/`
  los patrones que funcionaron/fallaron en el proceso de trabajo asistido por
  IA — es un objetivo secundario declarado del proyecto, pendiente de
  suficiente evidencia acumulada.
- Consolidar metodología/rol dentro de `CLAUDE.md` — con cuidado de no
  confundir la persona "arquitecto" del chat de planificación (no escribe
  código) con el agente ejecutor Claude Code (sí escribe código) — son roles
  distintos aunque compartan proyecto.
