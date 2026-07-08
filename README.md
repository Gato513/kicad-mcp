# kicad-mcp — Servidor MCP para automatización de KiCad

Agente LLM que opera sobre KiCad: lee esquemáticos en formato comprimido (TOON),
ejecuta herramientas atómicas, y actualiza el contexto por delta + área local.

## Quickstart

```bash
# Fase 0: verificar el entorno (obligatoria)
python3 scripts/verificar_entorno.py

# Si todo OK, seguir el PROMPT-SESION-01.md
```

## Estructura

```
docs/               — Documentación y especificaciones (contratos)
  arquitectura.md   — Diseño v0.2 del sistema
  adr/              — Decisiones de arquitectura (a generar)
  specs/            — Contratos técnicos (TOON, tools, restricciones, glosario)
  glosario.md       — Dominio EDA/KiCad

src/kicad_mcp/      — Código del servidor (a generar)
  server.py         — Servidor MCP + protocolo
  toon/             — Encoder TOON v1
  snapshots/        — Cache + índice espacial
  tools/            — Tools MCP por categoría
  errors.py         — Taxonomía de errores

tests/
  golden/           — Golden files: input + expected output (INMUTABLES)
  fixtures/         — Proyectos KiCad de prueba (sintéticos, validados contra kicad-cli)
  (tests/*.py)      — Tests (a generar)

.claude/            — Permisos y configuración de Claude Code
CLAUDE.md           — Memoria del proyecto (leer primero)
PROMPT-SESION-01.md — Prompt inicial para el agente
pyproject.toml      — Dependencias pre-aprobadas
```

## Para el agente

1. Lee `CLAUDE.md` completamente.
2. Ejecuta `python3 scripts/verificar_entorno.py` (Fase 0).
3. Sigue `PROMPT-SESION-01.md`.

## Para el humano

- `docs/arquitectura.md` — contexto del sistema.
- `docs/preparacion-claude-code.md` — cómo se preparó esto para el agente.
- `scripts/verificar_entorno.py` — diagnóstico de tu máquina (corre antes de cada sesión).

## Documentación de referencia

- `docs/specs/toon-v1.md` — especificación del formato TOON (contrato F1).
- `docs/specs/tool-catalog.md` — catálogo de tools + taxonomía de errores (contrato F3).
- `docs/specs/restricciones-kicad.md` — limitaciones técnicas de KiCad.
- `docs/glosario.md` — dominio EDA (consultar ante dudas).

## Estado

MVP (solo-lectura): contexto + validación + exportación.

**Verificado:** fixtures sintéticos validados contra kicad-cli real; permisos del agente
configurados; arquitectura v0.2 con decisiones cerradas.

**Pending (la máquina del humano):** KiCad 10 (KiCad 9 mínimo); habilitar API server.
