# kicad-mcp — Servidor MCP para automatización de KiCad

Agente LLM que opera sobre KiCad 10.0.4: lee esquemáticos/PCB en formato
comprimido (TOON), muta mediante herramientas atómicas vía IPC (kicad-python)
y kicad-cli, y actualiza el contexto por delta + área local. El diferencial
declarado es la economía de tokens (TOON + delta), no la mera conectividad
con KiCad.

## Estado (post-sesión 24, 2026-07-24)

Ya **no** es un MVP solo-lectura: el loop completo de escritura de PCB está
cerrado — esquemático → colocación → contorno → zonas/plano GND → ruteo
(autorouter Freerouting) → DRC → recarga programática → gerbers — validado
contra KiCad real en 4 rondas de dogfooding (D1–D4). Ver `docs/ROADMAP.md`
para el estado exacto y la próxima etapa (D5).

Escritura de esquemático sigue siendo la superficie más débil: las tools
existentes son puramente aditivas (sin CRUD) — ver `docs/BACKLOG.md`.

## Quickstart

```bash
# Fase 0: verificar el entorno (obligatoria al inicio de cada sesión)
python3 scripts/verificar_entorno.py

uv sync                                  # instalar deps
uv run pytest -m "not integration"      # tests (unit + golden)
```

Para retomar el trabajo del proyecto: leer `CLAUDE.md` (cómo trabajar) +
`docs/ROADMAP.md` (qué sigue) + `docs/BACKLOG.md` (pendientes). No hace falta
leer la cronología completa en `docs/historico/` salvo para investigar el
porqué de una decisión puntual.

## Estructura

```
CLAUDE.md            — memoria del proyecto para el agente ejecutor (leer primero)
docs/
  INDEX.md            — mapa de navegación: qué leer y cuándo
  CONTEXT.md          — visión del sistema, estado, riesgos (mantenido por el arquitecto)
  DECISIONES.md        — índice de ADR + decisiones vigentes no formalizadas
  ROADMAP.md          — estado actual y próximas etapas
  BACKLOG.md          — pendientes priorizados
  arquitectura.md     — diseño del sistema (v0.2)
  glosario.md         — dominio EDA/KiCad
  componentes-pcb.md  — referencia del PCB de prueba (202 comp.)
  guias/              — protocolos operativos (paleta de símbolos, pruebas GUI)
  specs/              — CONTRATOS: TOON, catálogo de tools, restricciones (frontera F1/F3)
  adr/                — decisiones de arquitectura individuales
  historico/          — reportes de sesión, prompts, investigaciones, dogfooding
                        (evidencia del proceso; no hace falta leerlo para
                        entender el estado actual)

src/kicad_mcp/
  toon/        — encoder TOON + delta
  snapshots/   — cache de estado + índice espacial
  tools/       — tools MCP (world/, sch, pcb, validate/, export/)
  bridge/      — kicad-python (IPC) y kicad-cli (subprocess)
  gates/       — sistema de gates de autonomía
  audit/       — log JSONL de mutaciones

tests/
  golden/      — pares entrada→salida del encoder (INMUTABLES, frontera F1)
  fixtures/    — proyectos KiCad de prueba
```

## Documentación de referencia

- `docs/specs/toon-v1.md` — especificación del formato TOON (contrato F1).
- `docs/specs/tool-catalog.md` — catálogo de tools + taxonomía de errores (contrato F3).
- `docs/specs/restricciones-kicad.md` — limitaciones técnicas de KiCad.
- `docs/glosario.md` — dominio EDA (consultar ante dudas).
- `docs/adr/` — decisiones de arquitectura, una por archivo.

## Para el humano

- `docs/guias/pruebas-gui.md` — cómo correr los tests `integration_gui` a mano.
- `docs/guias/guia-paleta.md` — cómo mantener la "hoja paleta" de símbolos.
- `scripts/verificar_entorno.py` — diagnóstico de tu máquina (corre antes de cada sesión).
