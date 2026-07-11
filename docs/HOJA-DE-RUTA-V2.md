# Hoja de ruta v2 — kicad-mcp

**Fecha:** 2026-07-11 · **Reemplaza a:** la hoja de ruta de
`docs/arquitectura.md §10` (obsoleta tras las sesiones 06-08).
**Fuentes:** `ANALISIS-ESTADO-Y-BACKLOG.md` (evidencia y candidatos),
historial de decisiones D-04..D-08 (arquitecto), y objetivos declarados
del humano (2026-07-11).

## Objetivos rectores (declarados por el humano, en orden)

1. **Herramienta personal para proyectos reales** — flujo confiable,
   rápido y barato en tokens para que agentes LLM (Claude Code con
   Opus/Sonnet) operen KiCad. Placas típicas: 10-60 componentes,
   una sola hoja.
2. **Rust v0.4: DIFERIDO con condiciones** (ratificado). Se re-evalúa
   solo si (a) la Eval A valida el encoder que se portaría, y (b) el
   dogfooding revela un cuello de botella propio (no de KiCad).
   Evidencia actual: 89 % de la latencia es IPC/UI de KiCad; el cómputo
   Python atacable es <0,3 %. Se formaliza en ADR (sesión 09).
3. **Open source: después** de que la herramienta resuelva el flujo
   personal.
4. Portfolio/aprendizaje: no guía decisiones.

## Decisiones de re-planificación (de las respuestas del humano)

- **D-R1:** Multi-hoja (`UNSUPPORTED_HIERARCHY`) diferido. Todo el
  esfuerzo va a single-sheet sólido. El error tipado se mantiene como
  frontera honesta.
- **D-R2:** Pasos manuales aceptados de forma estable: crear proyecto,
  mantener la hoja paleta, F8 (sync sch→pcb). El agente cubre el resto.
- **D-R3:** Ruteo: el agente rutea con `add_track`+`add_via`. La
  calidad se MIDE en el dogfooding Etapa 1; si no alcanza, Freerouting
  sube al roadmap (hoy no se promete).
- **D-R4:** "Hoja paleta" es el puente estable para símbolos.
  `add_symbol` desde librerías externas (A4) queda diferido hasta que
  el uso real demuestre que la paleta no alcanza.
- **D-R5:** Cliente objetivo: Claude Code (Opus/Sonnet). Acepta
  imágenes → el render PNG del board entra al plan como feedback
  visual. La Eval A usa el tokenizador real de Claude.
- **D-R6:** Conectar por labels ES una implementación válida de
  `connect_pins` (práctica estándar de KiCad); el nombre se conserva
  con semántica documentada.
- **D-R7:** Tools fantasma del catálogo (`get_component_detail`,
  `get_net_detail`, `list_unconnected`) → se mueven a "reservados" en
  la 09. Se implementan solo si el dogfooding demuestra que el agente
  las necesita. `discover_tools` se elimina del diseño (12 tools no
  justifican un router).

## Plan de sesiones

| Sesión | Tipo | Contenido | Resultado esperado |
|---|---|---|---|
| **09** | Dev | B1 leer PCB sin mutar · B2 E2E `add_track` · B3 `add_via` · `pcb_png` real (kicad-cli render) · ADR Rust diferido · catálogo honesto (D-R7) · higiene D3 | Pipeline PCB completo, confiable y visible |
| **10** | **Dogfooding Etapa 1** | El humano + agente sobre COPIA de una placa real suya (sch terminado + F8 hecho): colocar, rutear, DRC, exportar. Registro de fricciones | Priorización con datos reales; veredicto de ruteo (D-R3) |
| **11** | Dev | A3 doc paleta · A1 `set_value`+`set_footprint` · A5 `reload_in_gui` · spike A2 (labels) · D1+D4 (deuda tests) | Properties del sch editables; spike de conexión resuelto |
| **12** | Dev | A2 tool `connect_pins` por labels + tests · ajustes del dogfooding 1 | Flujo sch mínimo completo (con paleta + F8 humanos) |
| **13** | **Dogfooding Etapa 2** | Flujo end-to-end: breakout real desde hoja vacía (con paleta) hasta gerbers | Criterio de éxito del objetivo 1 |
| Flexible | Lab | **Eval A** (TOON vs JSON/CSV con tokenizador de Claude, ~200 llamadas API del humano). Recomendado: entre 10 y 11, con muestras del dogfooding | Valida la premisa del formato; condición (a) de Rust |

## Diferidos con condición de re-entrada

- **Multi-hoja (C2):** si los proyectos del humano crecen a multi-hoja.
- **Librerías externas (A4):** si la paleta demuestra fricción real.
- **Freerouting:** si el dogfooding 1 reprueba el ruteo del agente.
- **Rust (E2):** condiciones (a)+(b) arriba.
- **`get_component_detail`/`get_net_detail`/`list_unconnected`:** si el
  dogfooding las extraña.
- **Contador `post_fallback` en health (C3):** oportunista, si un
  fallback aparece en la práctica.

## Puntos de re-evaluación del plan

Tras cada dogfooding se revisa esta hoja de ruta. El plan sirve a los
objetivos; cuando la evidencia y el plan choquen, gana la evidencia —
esta v2 existe precisamente porque la v1 no sobrevivió al contacto con
KiCad real.
