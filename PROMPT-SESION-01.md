# PROMPT — Sesión 01: arranque de kicad-mcp

> Copiar todo lo que sigue (desde "Lee CLAUDE.md") como primer mensaje a
> Claude Code, ejecutado desde la raíz del repositorio.

---

Lee `CLAUDE.md` completo antes de cualquier acción. Este prompt lo complementa,
no lo reemplaza: ante conflicto entre este prompt y un spec de `docs/specs/`,
gana el spec; si la ambigüedad persiste, pregúntame antes de decidir.

## Fase 0 — Verificación del entorno (bloqueante)

Ejecuta `python3 scripts/verificar_entorno.py`.

- FAIL con remediación marcada como "El agente puede resolverlo" → resuélvela
  y re-ejecuta el script hasta confirmar.
- FAIL cuya remediación diga "El humano" → detente, muéstrame la instrucción
  exacta del script, y no continúes con ninguna tarea que dependa de eso.
- WARN → no bloquean esta sesión (el MVP es solo-lectura). Regístralos para
  el reporte final.

No avances a la Tarea 1 sin veredicto "listo para el MVP".

## Contexto de dependencias

El `pyproject.toml` ya existe con las dependencias pre-aprobadas y su edición
te está denegada (frontera F5). Si durante la sesión crees necesitar una
dependencia nueva: detente y propónmela con una justificación de una línea.
No la instales por otra vía.

## Tarea 1 — ADRs

Genera `docs/adr/0000-fronteras-inviolables.md` y `0001`–`0006` a partir de
`docs/arquitectura.md` (sección 11 "Registro de decisiones" y las fronteras
F1–F5 de `CLAUDE.md`). Formato por ADR: Contexto / Decisión / Consecuencias,
máximo 40 líneas cada uno. No inventes decisiones que no estén en esas
fuentes.

## Tarea 2 — Esqueleto del servidor

1. Estructura `src/kicad_mcp/` con los módulos de la arquitectura §4:
   `server.py`, `toon/`, `snapshots/`, `tools/`, `bridge/`, `gates/`,
   `audit/`, `errors.py`. Los módulos aún sin lógica quedan con interfaces
   tipadas y docstring de responsabilidad — nada de `pass` sin firma.
2. `errors.py`: la taxonomía completa de `docs/specs/tool-catalog.md` como
   enum + excepción base con `{code, message, hint}`. Los códigos son
   literales exactos del catálogo (frontera F3).
3. Servidor MCP por stdio usando FastMCP del SDK oficial (`mcp`), con la
   tool `health` implementada según su fila del catálogo: estado del server,
   versión de kicad-cli (subprocess con lista de argumentos, timeout, jamás
   `shell=True`), y proyecto activo si lo hay. Errores según taxonomía.
4. Test de `health` con cliente MCP **in-process** sobre stdio (el SDK lo
   permite); márcalo `unit` si no toca kicad-cli real, o `integration` si lo
   invoca. Quiero ambas variantes: una con el subprocess mockeado (unit) y
   una real (integration).
5. Logging estructurado JSON desde el primer tool call: `tool_name`,
   `tokens_est` (usa `len(texto)/3.5` por ahora), `latency_ms` (regla de
   código #2 de CLAUDE.md).

## Tarea 3 — Encoder TOON contra golden 001

1. Implementa `toon/schema.py` (modelos pydantic del estado normalizado,
   spec §1) y `toon/encoder.py` para el caso **sin degradación** (spec §2:
   cabecera, `[C]`, `[N]`, orden natural de refs, formato numérico, pin
   sin conectar como `>-`, sanitización §5).
2. Test `golden` que carga `tests/golden/001_minimo/` y compara **byte a
   byte**. Para `002_degradacion` y `003_delta`: crea los tests y márcalos
   `xfail(reason="degradación/delta: v0.3")` — NO implementes degradación ni
   delta en esta sesión, aunque parezca fácil.
3. Test adicional `unit`: el encoder sobre `tests/fixtures/001_basico/
   ground_truth.json` transformado al schema de entrada — debe producir un
   TOON cuyo conteo de cabecera coincida con `counts` del ground truth.
   (Los `.kicad_sch` de fixtures no se cargan al contexto: procesa con código.)

## Reglas de la sesión

- Rama `sesion-01`; un commit convencional por tarea; **nunca push**.
- Definition of Done por tarea (CLAUDE.md): `pytest -m "not integration"`
  verde, `ruff` limpio, `mypy` limpio, catálogo actualizado si aplica.
- Los golden y specs no se tocan (F1). Si crees que un golden está mal:
  detente y explícamelo con el diff exacto que observas.
- Al terminar: escribe `docs/sesiones/01-reporte.md` con: qué se completó,
  WARNs del entorno, decisiones que tomaste dentro del margen permitido,
  dudas abiertas, y tu propuesta concreta para la sesión 02.

Empieza por la Fase 0.
