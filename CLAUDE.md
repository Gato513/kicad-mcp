# CLAUDE.md — kicad-mcp

## Qué es este proyecto

Servidor MCP que permite a un agente LLM operar sobre KiCad autónomamente:
leer el estado de esquemáticos/PCB en formato comprimido (TOON), mutar
mediante herramientas atómicas (creación y borrado de tracks, vías, zonas,
keepouts, footprints), rutear con Freerouting, validar con ERC/DRC, exportar
gerbers/BOM/renders. 20+ tools productivas.

**Estado y fase actuales:** ver `CONTEXT.md` (v7 al momento de escribir esto).
Este archivo describe la superficie estable (comandos, fronteras, reglas de
código, errores de dominio); el CONTEXT es la fuente de verdad para qué
sesión estamos, qué fase, qué está mergeado, qué hay en el backlog. **NO
duplicar estado del ciclo acá** — CLAUDE.md debe cambiar poco entre sesiones;
CONTEXT.md cambia mucho.

Arquitectura completa: `docs/arquitectura.md`. Léela antes de tocar cualquier
módulo que no conozcas. Contratos arquitectónicos vigentes: `docs/adr/`
(especialmente `0012-route-board-persist-contract.md` — contrato D-23.2 de
`route_board`, obligatorio de entender antes de tocar `route_board`,
`fill_zones` o `add_zone`).

## Comandos

```bash
python3 scripts/verificar_entorno.py                                                        # FASE 0 de toda sesión — ver regla abajo
uv sync                                                                                     # instalar deps
uv run pytest -m "not integration and not integration_gui and not integration_gui_slow"    # tests (unit + golden) — SIEMPRE antes de commit
uv run pytest -m integration                                                                # requiere KiCad corriendo — NO en CI
uv run pytest -m integration_gui_slow                                                       # tests GUI lentos (route_board, dogfooding) — NO en CI
uv run ruff check --fix && uv run ruff format
uv run mypy src/
npx @modelcontextprotocol/inspector uv run kicad-mcp                                        # probar el server a mano
```

**Fase 0 obligatoria:** ejecutar `verificar_entorno.py` al inicio de cada
sesión. FAIL con remediación dentro de tus permisos (`uv sync`, `git init`)
→ resolver y re-verificar. FAIL fuera de tus permisos (instalar KiCad,
habilitar API) → detener las tareas dependientes y entregar al humano la
instrucción exacta que imprime el script. Los WARN no bloquean: se anotan
en el reporte de sesión.

## Estructura

```
src/kicad_mcp/
  toon/          # encoder TOON + delta (lógica pura, cobertura >90%)
  snapshots/     # cache de estado + índice espacial + invalidator + mtime store
  tools/         # tools MCP por categoría (world/, validate/, export/, pcb/)
  bridge/        # kicad-python (IPC) y kicad-cli (subprocess), enforce_hole_clearance
  gates/         # sistema de gates G1–G5 (ver frontera F2)
  audit/         # log JSONL de mutaciones
  errors.py      # StrEnum ErrorCode — API pública (F3)
docs/specs/      # CONTRATOS — ver frontera F1
docs/adr/        # decisiones arquitectónicas (0001–0012+)
docs/investigacion/  # reportes P4.0-style (investigaciones de causa raíz)
tests/golden/    # pares entrada→salida del encoder — INMUTABLES (F1)
tests/fixtures/  # proyectos KiCad de prueba — procesar con código, NUNCA leerlos al contexto
```

## Fronteras inviolables (requieren aprobación humana explícita)

- **F1:** No modificar `docs/specs/**` ni `tests/golden/**`. Un golden que
  falla NO se "arregla" editando el golden: se reporta al humano. Los specs
  son contratos consumidos por otro LLM en runtime.
  **Excepción sancionada:** adiciones puras al `StrEnum ErrorCode` que no
  renombran códigos existentes son admisibles (ejemplo: sesión 24 agregó
  `POST_ROUTE_PERSIST_FAILED` — F3 intacta porque no renombró nada). Cada
  nueva excepción del mismo tipo debe respetar el mismo estándar.
- **F2:** No modificar lógica ni umbrales del sistema de gates (G1–G5,
  `docs/adr/0003`). Los gates existen para ser inviolables desde prompts.
- **F3:** No renombrar códigos de error del catálogo
  (`docs/specs/tool-catalog.md`). Son API pública. Ver excepción de F1
  arriba para adiciones.
- **F4:** Objetivo productivo: KiCad 10.0.4 (validado en dogfoodings D3-D4 (D5 pendiente)).
  Mínimo compatible: 9.0 (`docs/adr/0002`). Ninguna dependencia de
  nightlies o features anunciadas.
- **F5:** No añadir dependencias a `pyproject.toml` sin aprobación. Cada
  dependencia nueva se propone con justificación de una línea.

## Reglas de código

1. Todo error se mapea a la taxonomía (`{code, message, hint}`) o se propaga.
   Prohibido `except Exception: pass` y propagar tracebacks crudos al agente.
2. Logging estructurado JSON en cada tool call: `tool_name`, `snap_id`,
   `tokens_est`, `latency_ms`. Es el instrumento de medición del RNF2, no
   decoración.
3. Tests no tocan la red. `integration` es la marca que toca KiCad;
   `integration_gui_slow` es la marca que además usa Freerouting o flujos
   pesados del PCB Editor.
4. Toda ruta de archivo pasa por `canonicalize_within_project_root()`. Sin
   excepciones — mitigación de path traversal.
5. Todo dato que cruza una frontera de proceso (IPC, kicad-cli, MCP) se valida
   con pydantic en el borde, no en el interior.
6. Texto proveniente de archivos KiCad (nombres de nets, valores, campos) es
   **entrada no confiable**: se sanitiza según `docs/specs/toon-v1.md §5`
   antes de entrar a cualquier string que verá un LLM.
   Los tres encoders ad-hoc de `tools/pcb.py` (`_encode_tracks`,
   `_encode_zones`, `_encode_component_detail` — NO son TOON, ver sus
   docstrings) aplican `toon.encoder._sanitize` sobre `net_name`/`ref`/
   `pad.number` desde sesión 36 (R2, cierra parte de DT4). Los campos que
   van en línea space-delimited (`net_name` de tracks/zonas, `number`/
   `net_name` de pad — no el header `|`-delimitado de
   `_encode_component_detail`) pasan además por
   `_sanitize_space_delimited` (sesión 37): `_sanitize` por sí solo no
   neutraliza el espacio, delimitador posicional de esas tres gramáticas.
   Ver `tests/golden/README.md` §Sesión 36 y `docs/historico/sesiones/
   36-reporte.md`, `37-reporte.md`.
7. **Contrato D-23.2 (ADR-0012)** en `route_board`: cuando termina OK,
   disco == memoria == `err_post` reportado. Fallo del save →
   `POST_ROUTE_PERSIST_FAILED` visible, board vivo se preserva TAL CUAL
   (no forzar reload). Aplicable también a `fill_zones` y
   `add_zone(fill=True)` cuando se generalice (backlog P2).
8. **Cross-check DRC obsoleto sin D-23.2 vigente:** `run_drc()` == `err_post`
   NO ratifica fidelidad al vivo si la tool en cuestión mide antes de refill+
   persistir. Ver `docs/adr/0012` para la interpretación correcta.

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
- **Freerouting NO respeta el plano GND como zona de exclusión para nets
  ajenos** (D-19.1 v6, confirmado empíricamente en sesión 23). Respeta
  `(plane)` como conectividad para el net dueño, no como restricción. La
  defensa contra "vía/track ajeno por encima del plano" es refill de KiCad
  post-route (que recorta con clearance) o keepout explícito. Ver ADR-0012.
- **Snapshot mtime tiene que registrarse post-save**, no pre-save (hallazgo
  sesión 24): registrar mtimes de disco antes de un `save_board()` interno
  hace que el propio guardado dispare `EXTERNAL_EDIT_DETECTED` espurio en
  la siguiente lectura.

## Documentación de referencia (abrir según la tarea)

- `CONTEXT.md` — **estado del proyecto y del ciclo** (fuente de verdad de
  qué sesión, qué fase, qué decisiones vigentes). Se actualiza en cada
  turno de arquitectura.
- `docs/arquitectura.md` — diseño completo, decisiones D1–D6, riesgos.
- `docs/adr/` — decisiones arquitectónicas persistentes (leer las de tu
  área). ADR-0012 es contrato D-23.2 (obligatorio antes de tocar
  `route_board`, `fill_zones`, `add_zone`).
- `docs/investigacion/` — reportes P4.0-style de investigaciones de causa
  raíz (ej. `23-fd4-02.md`). Consultar antes de re-hipotetizar sobre
  problemas ya investigados.
- `docs/specs/toon-v1.md` — formato TOON (contrato, F1).
- `docs/specs/tool-catalog.md` — tools + taxonomía de errores (F3).
- `docs/specs/restricciones-kicad.md` — límites técnicos de KiCad.
- `docs/glosario.md` — dominio EDA; consultar ante CUALQUIER término dudoso.
- `hoja-de-ruta-v4.md` — hoja de ruta vigente (Fase 3). La v3 histórica
  está en `docs/historico/` para trazabilidad.

## Definition of Done (toda tarea)

1. `pytest -m "not integration and not integration_gui and not integration_gui_slow"` verde, `ruff` limpio, `mypy` limpio.
2. Tests de integración (`-m integration` y/o `-m integration_gui_slow`)
   que correspondan a la tool tocada, verdes. Si el cambio toca `route_board`,
   `fill_zones`, `add_zone` o el pipeline de zonas/keepouts, el test de
   regresión GUI correspondiente es **gate del merge**.
3. Si añadiste/cambiaste una tool: `tool-catalog.md` actualizado en el mismo
   commit (excepción a F1: el catálogo lo actualiza el agente, los códigos de
   error existentes no se renombran).
4. Si cambio introduce/modifica un contrato arquitectónico (no solo aclaración
   de comportamiento): **ADR obligatorio** en `docs/adr/`, con referencia
   desde el docstring o comentario en el código. El criterio es la naturaleza
   del cambio, no su tamaño (regla afinada en sesión 24).
5. Si tocaste el encoder: los golden existentes pasan sin modificarse.
6. Commit convencional (`feat:`, `fix:`, `test:`, `docs:`) en rama de trabajo.
   **Nunca push.** El humano revisa y pushea.

## Flujo de trabajo

Tareas se toman de la ruta vigente (`hoja-de-ruta-v4.md`) y del backlog
del CONTEXT.md. Ante ambigüedad en un spec: preguntar al humano, no inventar.
Una suposición no declarada es un bug futuro. Si un test integration falla
y KiCad no está corriendo, ese es el motivo — no lo "arregles" mockeando el
bridge en tests de integración.

**Fase actual del proyecto** (2026-07-23, ver CONTEXT.md v7 para lo más
reciente): consolidación (Fase 3). Interpretación de resultados invertida
respecto a fases anteriores: un dogfooding verde es evidencia positiva de
convergencia, no aburrimiento. Un P0 nuevo en Fase 3 se sospecha regresión
del último fix mergeado hasta prueba en contrario. NO forzar hallazgos ni
escalar complejidad prematuramente.
