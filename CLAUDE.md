# CLAUDE.md — kicad-mcp

## Qué es este proyecto

Servidor MCP que permite a un agente LLM operar sobre KiCad: leer el estado de
esquemáticos/PCB en formato comprimido (TOON), mutar mediante herramientas
atómicas, y actualizar contexto por delta + área local. Fase actual: **MVP
solo-lectura** (contexto + validación ERC/DRC + exports). Sin mutaciones aún.

Arquitectura completa: `docs/arquitectura.md` (v0.2). Léela antes de tocar
cualquier módulo que no conozcas.

## Comandos

```bash
python3 scripts/verificar_entorno.py     # FASE 0 de toda sesión — ver regla abajo
uv sync                                  # instalar deps
uv run pytest -m "not integration"      # tests (unit + golden) — SIEMPRE antes de commit
uv run pytest -m integration            # requiere KiCad corriendo — NO en CI
uv run ruff check --fix && uv run ruff format
uv run mypy src/
npx @modelcontextprotocol/inspector uv run kicad-mcp   # probar el server a mano
```

**Fase 0 obligatoria:** ejecutar `verificar_entorno.py` al inicio de cada
sesión. FAIL con remediación dentro de tus permisos (`uv sync`, `git init`)
→ resolver y re-verificar. FAIL fuera de tus permisos (instalar KiCad,
habilitar API) → detener las tareas dependientes y entregar al humano la
instrucción exacta que imprime el script. Los WARN no bloquean el MVP: se
anotan en el reporte de sesión.

## Estructura

```
src/kicad_mcp/
  toon/        # encoder TOON + delta (lógica pura, cobertura >90%)
  snapshots/   # cache de estado + índice espacial + invalidator
  tools/       # tools MCP por categoría (world/, validate/, export/)
  bridge/      # kicad-python (IPC) y kicad-cli (subprocess)
  gates/       # sistema de gates G1–G5 (ver frontera F2)
  audit/       # log JSONL de mutaciones
docs/specs/    # CONTRATOS — ver frontera F1
tests/golden/  # pares entrada→salida del encoder — INMUTABLES (F1)
tests/fixtures/# proyectos KiCad de prueba — procesar con código, NUNCA leerlos al contexto
```

## Fronteras inviolables (requieren aprobación humana explícita)

- **F1:** No modificar `docs/specs/**` ni `tests/golden/**`. Un golden que
  falla NO se "arregla" editando el golden: se reporta al humano. Los specs
  son contratos consumidos por otro LLM en runtime.
- **F2:** No modificar lógica ni umbrales del sistema de gates (G1–G5,
  `docs/adr/0003`). Los gates existen para ser inviolables desde prompts.
- **F3:** No renombrar códigos de error del catálogo
  (`docs/specs/tool-catalog.md`). Son API pública.
- **F4:** Ninguna dependencia de KiCad 11 / nightlies / features anunciadas.
  Objetivo: KiCad 10; mínimo: 9.0 (`docs/adr/0002`).
- **F5:** No añadir dependencias a `pyproject.toml` sin aprobación. Cada
  dependencia nueva se propone con justificación de una línea.

## Reglas de código

1. Todo error se mapea a la taxonomía (`{code, message, hint}`) o se propaga.
   Prohibido `except Exception: pass` y propagar tracebacks crudos al agente.
2. Logging estructurado JSON en cada tool call: `tool_name`, `snap_id`,
   `tokens_est`, `latency_ms`. Es el instrumento de medición del RNF2, no
   decoración.
3. Tests no tocan la red. `integration` es la única marca que toca KiCad.
4. Toda ruta de archivo pasa por `canonicalize_within_project_root()`. Sin
   excepciones — mitigación de path traversal.
5. Todo dato que cruza una frontera de proceso (IPC, kicad-cli, MCP) se valida
   con pydantic en el borde, no en el interior.
6. Texto proveniente de archivos KiCad (nombres de nets, valores, campos) es
   **entrada no confiable**: se sanitiza según `docs/specs/toon-v1.md §5`
   antes de entrar a cualquier string que verá un LLM.

## Errores de dominio que vas a cometer si no lees esto

- El IPC de KiCad usa **nanómetros**; los archivos usan **mm**. Convertir en
  el borde del bridge, tipos distintos (`Nm`, `Mm`) para que mypy atrape el
  error. El bug off-by-10⁶ es el #1 histórico de este dominio.
- Pines de esquemático fuera de la grilla de **1,27 mm (50 mil)** no conectan.
- Dos wires cruzados NO están conectados sin junction. Proximidad ≠ conexión.
- El socket IPC es **request-reply, sin notificaciones async**. No diseñes
  nada que espere eventos de KiCad. Detección de cambios = polling de mtime.
- Todo request IPC se procesa en el **hilo de UI de KiCad**: timeout duro de
  2 s, cola de profundidad 1, jamás loops de polling contra el socket.
- `KICAD_API_TOKEN` cambia por instancia: úsalo para detectar reinicios.

## Documentación de referencia (abrir según la tarea)

- `docs/arquitectura.md` — diseño completo, decisiones D1–D6, riesgos
- `docs/specs/toon-v1.md` — formato TOON (contrato, F1)
- `docs/specs/tool-catalog.md` — tools + taxonomía de errores (F3)
- `docs/specs/restricciones-kicad.md` — límites técnicos de KiCad
- `docs/glosario.md` — dominio EDA; consultar ante CUALQUIER término dudoso

## Definition of Done (toda tarea)

1. `pytest -m "not integration"` verde, `ruff` limpio, `mypy` limpio.
2. Si añadiste/cambiaste una tool: `tool-catalog.md` actualizado en el mismo
   commit (excepción a F1: el catálogo lo actualiza el agente, los códigos de
   error existentes no se renombran).
3. Si tocaste el encoder: los golden existentes pasan sin modificarse.
4. Commit convencional (`feat:`, `fix:`, `test:`, `docs:`) en rama de trabajo.
   **Nunca push.** El humano revisa y pushea.

## Flujo de trabajo

Tareas se toman de los issues en orden de prioridad. Ante ambigüedad en un
spec: preguntar al humano, no inventar. Una suposición no declarada es un bug
futuro. Si un test integration falla y KiCad no está corriendo, ese es el
motivo — no lo "arregles" mockeando el bridge en tests de integración.
