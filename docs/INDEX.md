# Índice de documentación — kicad-mcp

Mapa de qué leer y cuándo. Generado en la reorganización documental de
2026-07-24 (ver `docs/historico/analisis/` para el análisis completo que la
originó). El objetivo: que nadie —humano o agente— necesite abrir
`docs/historico/` para entender el estado actual del proyecto.

## Contexto mínimo para arrancar una sesión de trabajo

En este orden, y solo lo que aplique a la tarea:

1. **`AGENTS.md`** (raíz) — contrato transversal para trabajo multiagente:
   roles, autoridad, independencia, handoffs. Leer cuando la herramienta lo
   cargue como instrucciones del repositorio; no es requisito para una
   tarea humana que no involucra agentes.
2. **`CLAUDE.md`** (raíz) — siempre para el ejecutor Claude Code. Es su
   contrato específico: comandos, fronteras F1–F5, reglas de código,
   Definition of Done. Se auto-carga.
3. **`hoja-de-ruta-v5.md`** (raíz) — hoja de ruta estratégica vigente.
4. **`docs/BACKLOG.md`** — pendientes priorizados, para no reabrir un ítem ya
   conocido como investigación nueva.
5. El **prompt/brief específico** de la tarea que te haya dado el humano.

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
| `AGENTS.md` | Contrato transversal de coordinación multiagente: roles, autoridad, independencia, handoffs | Humano, tras cada sesión que cambie reglas de coordinación |
| `CLAUDE.md` | Contrato del ejecutor Claude Code | Humano, tras cada sesión que cambie reglas |
| `README.md` | Punto de entrada, quickstart, mapa de estructura | Humano/agente al DoD |
| `docs/CONTEXT.md` | Visión consolidada del sistema y riesgos | Humano |
| `docs/DECISIONES.md` | Índice de ADR + decisiones vigentes no formalizadas | Humano/agente |
| `docs/ROADMAP.md` | Puente documental e historial del ciclo; no es la dirección vigente | Humano/agente |
| `hoja-de-ruta-v5.md` | Dirección estratégica vigente | Humano/agente |
| `docs/BACKLOG.md` | Pendientes priorizados | Humano/agente |
| `docs/arquitectura.md` | Diseño del sistema v0.2, principios, riesgos de fondo | Estable, rara vez cambia |
| `docs/glosario.md` | Dominio EDA/KiCad | Estable |
| `docs/componentes-pcb.md` | Referencia del PCB de prueba (202 comp.) | Estable |
| `docs/guias/guia-paleta.md` | Protocolo humano: paleta de símbolos para `add_symbol` | Humano |
| `docs/guias/pruebas-gui.md` | Protocolo manual de tests `integration_gui`/`integration_gui_slow` | Humano |
| `docs/specs/*.md` | **Contratos** (TOON, catálogo de tools, restricciones, fixtures) — frontera F1/F3 | El agente actualiza el catálogo como parte del DoD; el resto no se edita sin aprobación |
| `docs/adr/*.md` | Decisiones de arquitectura, una por archivo | Se agregan, nunca se editan retroactivamente |
| `docs/investigacion/*.md` | Investigaciones de causa raíz (P4.0-style), referenciadas desde ADR/specs — lectura obligatoria antes de re-hipotetizar sobre un bug ya investigado | Se agregan por sesión, no se editan retroactivamente |
| `docs/analisis/40-dt1-caracterizacion.md` | Caracterización canónica de DT1 y autorización de Slice 1 | Histórico de decisión, base para recaracterizar DT1 |
| `docs/analisis/CONTEXTO_CHAT.md` | Handoff previo a sesión 40; su cierre lo declara obsoleto después de esa sesión | Histórico, no fuente viva |

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
| `roadmaps/` | Hojas de ruta v2, v3 y v4 archivadas (v4: `docs/historico/roadmaps/hoja-de-ruta-v4.md`); la vigente es `hoja-de-ruta-v5.md` en la raíz |
| `dogfooding/` | Logs de fricciones de las 4 rondas de dogfooding (D1–D4) + brief del proyecto de referencia (despertador ATtiny85) |
| `CONTEXT-v7.md` | El handoff monolítico previo a esta reorg — post-sesión 24, fuente de la consolidación de 2026-07-24 en `docs/CONTEXT.md` + `DECISIONES`/`ROADMAP`/`BACKLOG`. (Reemplaza a `CONTEXT-v3.md`, congelado en sesión 19e, que el arquitecto retiró al entregar v7.) |

Nota: `investigacion/` **no** está bajo `historico/` — vive en
`docs/investigacion/` (ver tabla de arriba) porque `docs/adr/0012` y
`docs/specs/tool-catalog.md` (ambos contratos F1/nunca-editados-retroactivamente)
ya la referencian como lectura obligatoria, no como archivo. Un movimiento
anterior de esta misma reorg la había anidado bajo `historico/`, rompiendo
esas referencias — corregido.

**Regla:** si estás por citar algo de `historico/` en una decisión activa,
promové el resumen a `DECISIONES.md`/`ROADMAP.md`/`BACKLOG.md` y dejá el
puntero — no repitas el detalle completo fuera de `historico/`.

Para el cierre de DT1 Slice 1, ver
`docs/historico/sesiones/41-reporte.md` (sesión 41, PR #13, merge
`8d3696b890b4719ef19a96db26735b25da0214b5`).

## Trabajo futuro fuera de esta reorg (no hacer todavía)

- `docs/metodologia/`: consolidar de `historico/prompts/` y `historico/sesiones/`
  los patrones que funcionaron/fallaron en el proceso de trabajo asistido por
  IA — es un objetivo secundario declarado del proyecto, pendiente de
  suficiente evidencia acumulada. Distinto de `AGENTS.md`: esto sería
  investigación/consolidación metodológica general, no el contrato operativo
  de coordinación multiagente del proyecto.
- La coordinación transversal entre roles (arquitecto de chat, que no
  escribe código, y agente ejecutor Claude Code, que sí escribe código) ya
  no se consolida dentro de `CLAUDE.md`: vive en `AGENTS.md`, que separa
  esos roles institucionalmente.
