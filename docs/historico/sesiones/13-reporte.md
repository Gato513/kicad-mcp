# Reporte de sesión 13 — Spike de autorouting (D-R11)

**Rama:** `sesion-13` · **Fecha:** 2026-07-12 · **Tipo:** SPIKE (cero código de
producción, cero deps a pyproject; todo en `scratchpad/spike-autoroute/`).
**Entorno:** KiCad 10.0.4 (kicad-cli + IPC), OpenJDK 21.0.11, Freerouting
v2.1.0. `verificar_entorno.py` → 18 OK · 3 WARN · 0 FAIL (WARN resueltos con
`uv sync`; los restantes son npx/Inspector, no bloqueantes).

**El informe del spike ES el reporte:**
👉 **`scratchpad/spike-autoroute/informe.md`** (inventario de caminos con
evidencia, métricas, comparación con el Dogfooding 1, diseño de la tool,
recomendación y dudas para la 14).

---

## Veredicto en una línea

**INTEGRAR.** Hay un camino de autorouting **headless** (Freerouting jar +
round-trip Specctra vía `pcbnew` SWIG del python del sistema) que sobre la placa
real del dogfooding (24 comp, 64 conexiones) rutea el **100% con 0 errores DRC
(0 shorts, 0 clearance)** en **~2 min** y a costo de **1 llamada de herramienta**.

## Números (2 corridas, estables)

| | run1 | run2 | baseline (sin rutear) |
|---|---|---|---|
| Ratsnest ruteado | 100% | 100% | 0% (64 unconnected) |
| Errores DRC | 0 | 0 | 1 (invalid_outline) |
| Shorts / clearance | 0 / 0 | 0 / 0 | — |
| Router wall-clock | 101.8 s | 122.1 s | — |
| Tracks / vías | 318 / 26 | 348 / 24 | 0 / 0 |

Warnings restantes: 35 de serigrafía **preexistentes** (no del ruteo) + 5–7
`track_dangling` (stubs; warnings). **G3 abre** (bloquea solo con
`severity=="error"`, `gates/g3.py:45`) → gerbers habilitados.

## Comparación con el Dogfooding 1 (D-R3)

Ruteo-LLM manual: 22% ruteado, 13 shorts, ~14–16k tokens, 25–40 turnos, board
final **peor** e irreversible. Autorouter: **100%, 0 shorts, ~cientos de tokens,
1 call, board limpio.** El plan B (subir inteligencia de `add_track`) queda
descartado por costo/beneficio; `add_track`/`add_via`/`delete_track` pasan a ser
retoque puntual.

## Caminos del round-trip (evidencia)

- **kicad-cli Specctra:** CERRADO (no hay `export specctra`/`dsn` ni `import`
  SES en 10.0.4).
- **`pcbnew` SWIG (python sistema):** FUNCIONA — `ExportSpecctraDSN` /
  `ImportSpecctraSES` con forma de 2-args + `LoadBoard`/`SaveBoard` → headless.
  [camino elegido]. Fragilidad: proceso hijo (no dep de pyproject), SWIG en
  deprecación anunciada (no bloquea en KiCad 10, F4).
- **Plugin oficial Freerouting:** referencia de la receta (usa el mismo pcbnew)
  pero atado a GUI; nos dio el jar.
- **Router interno por IPC (kipy):** CERRADO — `Board` solo expone lectura de
  nets; sin autoroute/Specctra en KiCad 10.

## Fricción principal para la 14

**Split-brain disco↔editor-vivo (F-05 en reversa):** el round-trip escribe en
disco; con KiCad abierto (hay `.lck`) el editor no ve las tracks y `reload_in_gui`
no existe en KiCad 10 (D-12.4). La tool `route_board` debe: `save_board`
(live→disco) → round-trip → dejar en disco + hazard de recarga en el confirm.
Detalle y superficie propuesta (`route_board(policy?, max_passes?) → confirm`) en
el informe §6.

## Entregables

- `scratchpad/spike-autoroute/informe.md` — informe/veredicto completo.
- `scratchpad/spike-autoroute/{01_export_dsn.py, 02_import_ses.py, roundtrip.sh}`
  — round-trip ejecutable y reproducible (promovible a producción en la 14).
- Renders `/tmp/spike-route-proyecto/runs/{before,after}.png`; DRC JSON y logs
  de Freerouting en `/tmp/spike-route-proyecto/runs/run{1,2}/`.

## Qué necesita la 14 (resumen; detalle en informe §8)

- **Arquitecto:** decisión de split-brain (disco+hazard vs KiCad cerrado); gate
  de `route_board` (confirmación previa, muta cobre en masa); exponer
  `max_passes` opcional (default basta).
- **Humano:** aceptar Java 21 + jar + `pcbnew` como requisitos de sistema (estilo
  kicad-cli, NO pyproject).
- **Riesgo residual:** placa de densidad media; el rango alto (60 comp) se mide
  en el Dogfooding 2.

## Definition of Done (spike)

- Sin tocar `src/`, `pyproject.toml`, `docs/specs/**`, `tests/golden/**` (F1/F5
  intactas). Solo `scratchpad/` + este reporte.
- Round-trip probado end-to-end **2 veces** con evidencia (no leído: ejecutado).
- Veredicto con números y comparación contra el baseline D-R3.
