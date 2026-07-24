# Sesión 14 — `route_board`: autorouting en producción

**Rama:** `sesion-14` (desde `master`). Un commit por tarea. No pushear.
**Entorno:** KiCad 10.0.4 vivo sobre `/tmp/gui-test-project/`, env vars
de siempre + **`KICAD_MCP_FREEROUTING_JAR`** apuntando al jar (el humano
la exporta). Java 21 y `pcbnew` (python del sistema) presentes —
verificalo en Fase 0 y frená si falta algo.

Leé antes: `scratchpad/spike-autoroute/informe.md` (el diseño validado —
los scripts `01_export_dsn.py`/`02_import_ses.py`/`roundtrip.sh` se
PROMUEVEN, no se reinventan), `docs/sesiones/13-reporte.md`, y
`docs/HOJA-DE-RUTA-V2.1.md`. El Dogfooding 2 pasa a la sesión 15; esta
sesión existe para que llegue con el paso 7 resuelto.

---

## Decisiones vinculantes del arquitecto

- **D-14.1 (split-brain: cadena viva obsoleta post-route):**
  `route_board` escribe a DISCO; el board vivo de KiCad queda detrás. El
  peligro no es cosmético: una mutación IPC + `save_board` posteriores
  PISARÍAN el ruteo con cobre viejo. Mecanismo obligatorio:
  - `route_board` setea un flag de store `live_stale=True` y registra
    snapshot de DISCO post-route.
  - Con `live_stale` activo: `move_footprint`, `add_track`, `add_via`,
    `delete_track`, `delete_via` y `save_board` FALLAN con
    `EXTERNAL_EDIT_DETECTED` (código existente, F3 intacta; encaja: el
    disco cambió por fuera del editor vivo) y hint: "el disco tiene el
    ruteo y el editor vivo no; recargá el board en KiCad (File→Revert)
    y confirmá con get_world_context(kind='pcb', confirm_reloaded=true)".
  - `get_world_context(kind="pcb", confirm_reloaded=true)` limpia el
    flag (parámetro nuevo, default false; con el flag activo y sin
    confirm_reloaded, la lectura viva FUNCIONA pero el TOON lleva una
    línea de aviso `[AVISO] editor vivo detras del disco (route_board)`).
  - Las tools de DISCO (`run_drc`, `export_render`,
    `export_manufacturing`, tools sch) NO se bloquean: leen el estado
    correcto.
  - Tests unit de CADA rama del flag (mutación bloqueada, save
    bloqueado, lectura con aviso, confirm_reloaded limpia, disco-tools
    inmunes).
- **D-14.2 (sin gate interactivo):** coherente con D-R8/ADR-0010 — es
  cobre, re-ruteable, G1+git protegen. Obligatorio: G1 backup pre-route,
  audit JSONL, y confirm que reporta conteos:
  `OK route_board 64/64 nets +318 tracks +26 vias drc_err=0 [snap:N]`
  (≤50 tokens). ADR nuevo (0011) documentando D-14.1 + D-14.2 + los
  requisitos de sistema.
- **D-14.3 (superficie de la tool):**
  `route_board(max_passes: int | None = None, timeout_s: int = 600)`.
  Pipeline interno: si hay cadena viva con cambios → `save_board`
  implícito primero (live→disco); export DSN (subprocess python del
  sistema con pcbnew, promovido del spike); Freerouting jar headless
  (subprocess java, timeout → `KICAD_TIMEOUT` con hint); import SES +
  SaveBoard (subprocess pcbnew); DRC rápido post-route para el conteo
  de errores del confirm (usa `bridge.rules`, como G3); snapshot disco;
  flag D-14.1; confirm. Los subprocesos NUNCA usan el venv del proyecto
  (pcbnew es del python del sistema — documentá la invocación exacta).
- **D-14.4 (errores tipados del pipeline):** java ausente, jar ausente
  (env `KICAD_MCP_FREEROUTING_JAR` no seteada o ruta inexistente),
  pcbnew no importable, export DSN falla (típico: sin Edge.Cuts → hint
  "dibujá el contorno con draw_board_outline"), Freerouting exit≠0 o
  timeout, import SES falla. Cada uno con código EXISTENTE que mejor
  encaje (argumentá el mapeo; F3: cero códigos nuevos — si creés que
  falta uno, se reporta) + hint accionable + `data` estructurado donde
  ayude.
- **D-14.5 (verificador):** `scripts/verificar_entorno.py` gana tres
  checks WARN-level (no bloquean sesiones que no rutean): `java
  -version` ≥17, jar en `KICAD_MCP_FREEROUTING_JAR` existente,
  `python3 -c "import pcbnew"` con el python del SISTEMA. Con los tres
  OK, imprime "flujo de autorouting disponible".

---

## Tareas

**Fase 0:** verificador + suite + los tres requisitos de sistema
presentes (si falta alguno, instrucción exacta al humano y STOP).

**T1 — Bridge/runner del round-trip:** módulo (p. ej.
`bridge/autoroute.py`) que envuelve los tres subprocesos con timeouts,
captura de stderr para hints, y tipos primitivos afuera. Promové los
scripts del spike adaptándolos al estilo del proyecto (errores
taxonomía, logging JSON con `latency_ms` desglosado:
`export_ms/route_ms/import_ms`). Unit tests con subprocess fakeado
(éxito, cada fallo de D-14.4, timeout).

**T2 — Tool `route_board` + flag D-14.1:** la tool completa (D-14.3) +
el mecanismo `live_stale` en el store + `confirm_reloaded` en
`get_world_context`. Catálogo: entrada completa de `route_board` +
actualización de las tools afectadas por el flag + el parámetro nuevo.
Unit tests del flag (todas las ramas de D-14.1) y de la tool con runner
fakeado.

**T3 — Test real (marker `integration_gui_slow`):** round-trip completo
contra una COPIA del proyecto de spike (`cp -r` a tmp — no re-rutees el
board de 189 fp de gui-test-project: usá el proyecto chico que el
humano dejó en `/tmp/spike-route-proyecto` copiándolo primero). Verifica:
confirm con 64/64, DRC post-route sin errores, flag activo y mutación
bloqueada post-route, `confirm_reloaded` destraba tras recarga simulada.
Marcalo `integration_gui_slow` (el marker ya existe en pyproject).

**T4 — Docs:** ADR-0011, catálogo al día, `docs/pruebas-gui.md` con el
protocolo de recarga manual post-route, y una sección nueva en
`docs/guia-paleta.md` o donde corresponda: "flujo completo de 9 pasos"
actualizado con route_board en el paso 7. Reporte en
`docs/sesiones/14-reporte.md` (regla de proceso: siempre en el commit
final).

## Fuera de scope

- Tuning de perfiles de Freerouting (default + max_passes alcanza).
- Ruteo incremental/parcial por zona. Detección automática de recarga.
- Multi-hoja, pyproject, specs, goldens (F1/F5 — Opción A si hace falta).

## Definition of Done

```
unit+golden → verde · integration → verde (<5:00) · integration_gui →
verde · integration_gui_slow (T3) → verde aislado · mypy strict ·
ruff clean
```

## Reporte final

1. Confirm literal del route_board real (T3) + desglose de latencia.
2. Output del test del flag: la mutación post-route bloqueada y el
   destrabe con confirm_reloaded.
3. Mapeo de errores D-14.4 elegido (tabla fallo→código→hint).
4. tokens_est del confirm y promedios (≤50 / ≤400).
5. Estado del flujo de 9 pasos actualizado (¿queda solo 1 y 5 en manos
   humanas?).
6. Checklist de preparación del Dogfooding 2 (sesión 15): qué necesita
   el humano, incluyendo los requisitos de sistema del ruteo.
7. Dudas abiertas.
