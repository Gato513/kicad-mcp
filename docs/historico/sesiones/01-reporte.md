# Reporte de sesión 01 — arranque de kicad-mcp

**Fecha:** 2026-07-08 · **Rama:** `sesion-01` · **Commits:** 3
(ADRs, esqueleto+health, encoder+golden 001) · **Estado:** DoD cumplido en las
tres tareas, sin push.

## Qué se completó

### Tarea 1 — ADRs
- `docs/adr/0000-fronteras-inviolables.md` (F1–F5).
- `docs/adr/0001..0006` mapeando D1–D6 de `docs/arquitectura.md §11`.
- Formato **Contexto / Decisión / Consecuencias**, todos ≤ 40 líneas
  (0000: 40, 0001: 35, 0002: 35, 0003: 39, 0004: 40, 0005: 33, 0006: 37).
- Enlaces internos entre ADRs con rutas relativas para navegar decisiones
  relacionadas sin ir a `arquitectura.md`.

### Tarea 2 — Esqueleto del servidor + tool `health`
- Estructura `src/kicad_mcp/`: `server.py`, `errors.py`, `logging_config.py`,
  `paths.py`, `toon/`, `snapshots/`, `bridge/`, `tools/`, `gates/`, `audit/`.
- `errors.py`: **taxonomía completa** de `tool-catalog.md §Taxonomía` como
  `ErrorCode(StrEnum)` + `KicadMcpError` con `{code, message, hint}`.
- `bridge/kicad_cli.py`: `probe_version()` con `subprocess.run(list, timeout,
  shell=False)`, `Protocol` para inyectar fake en tests, nunca lanza (retorna
  `KicadCliStatus` tipado).
- `tools/meta.py`: tool `health` que reporta server, `kicad_cli` (versión o
  `KICAD_CLI_MISSING`), `kicad_ipc` (stub `not_checked` — llega en v0.2) y
  `project` (por env `KICAD_MCP_PROJECT`, `PROJECT_NOT_FOUND` si vacío).
- `logging_config.py`: logging JSON por tool call con `tool_name`, `snap_id`,
  `tokens_est` (`len/3.5`), `latency_ms` — regla #2 de CLAUDE.md, requisito
  de ADR-0004.
- `server.py`: `FastMCP` por stdio con `instructions` corta y `register_all()`.
- Tests:
  - **3 unit** contra el servidor via `create_connected_server_and_client_session`
    (cliente MCP in-process del SDK): (a) kicad-cli ok, (b) kicad-cli
    ausente reporta `KICAD_CLI_MISSING`, (c) `KICAD_MCP_PROJECT` reporta
    `project.status=ok`.
  - **1 integration**: mismo camino pero contra `kicad-cli` real (verificó
    v10.0.4 ≥ 9 requerido por ADR-0002).
- `pyproject.toml` **no modificado** (F5).

### Tarea 3 — Encoder TOON + golden 001
- `toon/schema.py`: `Pin`, `Component`, `NormalizedState` (pydantic frozen,
  `extra="ignore"`). `net=None` ⇒ pin sin conectar.
- `toon/encoder.py`:
  - `encode_state()` — serialización sin degradación (spec §2), orden natural
    de refs y pines, poder primero por regex de §4, sanitización §5 (control
    chars, `>|:` estructurales, corte a 40 chars con `…`, aviso heurístico
    de inyección).
  - `encode(max_tokens=…)` y `encode_delta(…)` con `NotImplementedError` y
    mensaje que apunta al §4/§3 de la spec (v0.3).
- Tests:
  - **golden 001** byte-a-byte: OK.
  - **golden 002/003**: `xfail(reason="…: v0.3")` — el encoder actual llega
    al `NotImplementedError` y pytest reporta XFAIL sin ensuciar la salida.
  - **unit** sobre `tests/fixtures/001_basico/ground_truth.json`:
    transformación por código (invierte el mapa net→refs para producir el
    schema del encoder), verifica cabecera `SCH|v1|5c|6n|snap:1` contra
    `counts` del ground truth. Los `.kicad_sch` no se leen al contexto.

### Definition of Done
```
uv run pytest -m 'not integration'   →  5 passed, 2 xfailed, 1 deselected
uv run pytest -m integration         →  1 passed  (kicad-cli 10.0.4 real)
uv run mypy src/                     →  Success (strict, 15 files)
uv run ruff check src/ tests/test_*  →  All checks passed
uv run ruff format --check src/ tests/test_*  →  clean
```

## WARNs del entorno (Fase 0)

Un solo WARN, registrado y **no bloqueante para el MVP**:

- **Fixture 004 (real)** — pendiente, marca "tarea del humano".
  Remediación citada por el script: `docs/specs/fixtures.md §004_real`. No
  impacta ninguna tarea de esta sesión (usamos 001–003 sintéticas).

`kicad-cli 10.0.4`, socket IPC `/tmp/kicad/api.sock`, ERC por CLI, uv, npx,
permisos de Claude Code, dependencias importables y fixtures 001–003
validadas: todos OK. Veredicto del script: **listo para el MVP**.

## Decisiones tomadas dentro del margen permitido

1. **Handshake del encoder futuro:** dejé públicas `encode(state,
   max_tokens=…)` y `encode_delta(state, base=…, focus_ref=…, radius_mm=…,
   base_snap=…)` con `NotImplementedError` explícito y referencia al § de la
   spec. Motivo: los golden 002/003 esperan estas firmas; xfail requiere que
   la llamada exista para atrapar el fallo. Alternativa (definir sólo
   `encode_state`) me habría obligado a colar el error como `KicadMcpError`
   sin código de la taxonomía — sería inventar un código.
2. **Detección de proyecto activo por `KICAD_MCP_PROJECT`** (env var). El
   servidor MVP no negocia `roots` con el cliente MCP; la env var es la vía
   más simple, testeable con `monkeypatch.setenv`, y no compromete el diseño
   futuro (v0.2 puede reemplazarla por roots sin romper el contrato de
   `health` — solo cambia cómo se llena `project.name`).
3. **`_SubprocessRunner` como `Protocol`** en `bridge/kicad_cli.py` — para
   inyectar fakes en tests unit sin tocar `subprocess` global ni mypy strict.
4. **`AVISO` sospechoso** implementado ya en el encoder, aunque el golden 001
   no lo dispara. Motivo: la sanitización §5 es un requisito de seguridad
   (§7 de arquitectura). Dejarlo para más adelante deja código sin la
   defensa nombrada por la spec.
5. **ADRs con enlaces internos entre sí** (referencias `[ADR-0003]`) — para
   que abrir cualquiera lleve al vecino sin volver a `arquitectura.md`.

Ninguna decisión toca F1–F5.

## Dudas abiertas (para conversar antes o durante sesión 02)

1. **`ruff check` sobre archivos pre-existentes**: `scripts/verificar_entorno.py`
   y `tests/fixtures/*.py` acumulan **10 errores** de ruff desde el commit
   inicial (E501 líneas largas, RUF059 unpacked vars). No los toqué porque
   quedan fuera del alcance de la sesión y podrían sorprender al humano.
   ¿Los limpio en un commit `chore:` propio en sesión 02, o los dejamos?
2. **`fixtures/001_basico/ground_truth.json` no lleva `snap` ni `kind`**.
   Elegí `kind="sch"`, `snap=1` para el test. ¿Debe añadirse un campo
   `snap` explícito al ground_truth, o el snap sale por definición del
   turno (bridge) y este test debe forzarlo desde el llamador?
3. **`health` no distingue "KiCad IPC no arrancado" de "no habilitado"**.
   Reporté `not_checked` con nota apuntando a v0.2. En cuanto entre el
   bridge Python, la tool devolverá `KICAD_NOT_RUNNING` cuando el socket no
   exista y `ok` cuando sí. ¿Está bien mantenerlo así hasta v0.2?
4. **`tokens_est` va a stderr por defecto** (JSON logger). Cuando el cliente
   MCP corra el server por stdio, stdout es del transporte; stderr es el
   canal correcto. Confirmo que esa asunción se mantenga documentada en
   ADR-0004 o en un `docs/instrumentation.md` propio.
5. **El `[AVISO]` del encoder aparece pero no se traduce a un código de
   error de la taxonomía** — es una línea informativa dentro del TOON. Si
   quisieras que el agente reciba un error tipado en lugar (o además), lo
   añadiría a la taxonomía en v0.2 con nombre pendiente de aprobación (F3).

## Propuesta concreta para la sesión 02

Ordenada por dependencia. La idea es cerrar el "solo-lectura" del MVP
(RF2 + RF6 + RF7) antes de tocar mutaciones.

1. **`bridge/kicad_ipc.py` mínimo** que abra el socket UNIX
   `/tmp/kicad/api.sock` con `KICAD_API_TOKEN`, y tools `get_project_info` +
   listado plano de componentes. Con eso `health` deja de reportar
   `not_checked` y podemos escribir el primer test integration del bridge.
2. **`tools/world.py::get_world_context`** cableado al bridge: lee el
   estado, construye `NormalizedState`, llama `encode()` con
   `max_tokens=800`. Al superar el presupuesto (proyectos ≥ ~30
   componentes), el `NotImplementedError` del encoder aflora → aquí sale
   la primera pregunta real: **¿implementamos degradación §4 en 02 o
   diferimos a 03?** Recomendación: diferir §4 a 03 e imponer 800 tokens
   como techo estricto, devolviendo `CONTEXT_BUDGET_IMPOSSIBLE` con hint
   accionable (subir el presupuesto). Es el fallback honesto y no lo cambia
   la spec.
3. **`tools/validate.py::run_erc` + `run_drc`** usando `kicad-cli sch erc
   --exit-code-violations …` y `kicad-cli pcb drc …` con parsing del JSON
   de salida a la estructura `{rule, severity, message, items}` del
   catálogo. Prerequisito: **la ruta del proyecto** — proviene del `health`
   ya, así que la reutilizamos.
4. **`tools/export.py`** con `export_bom`, `export_netlist`, `export_render`.
   Deferrimos `export_manufacturing` hasta tener DRC en el loop (Gate G3).
5. **Aumentar `tool-catalog.md`** con notas de qué categoría exponemos por
   defecto (`meta`+`world`+`validate`) y actualización de `discover_tools`
   (aún sin implementación real, solo firma).
6. **Instrumentación**: verificar que `tokens_est` promedio del MVP cumple
   los ≤ 400 del ADR-0004 en las tools de la sesión 02. Ese número entra en
   el reporte 02.

Trabajo excluido de sesión 02 (respeta el roadmap): mutaciones, delta,
degradación §4, IPC de esquemático. Sesión 02 se queda en el corazón del MVP
solo-lectura.
