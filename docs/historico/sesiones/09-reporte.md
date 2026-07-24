# Reporte de sesión 09 — Pipeline PCB completo, confiable y visible

**Fecha:** 2026-07-11 · **Rama:** `sesion-09` · **Entorno:** KiCad 10.0.4 con
PCB Editor cargado sobre `/tmp/gui-test-project/video.kicad_pcb` (189
footprints / 588 nets), env vars exportadas. Fase 0 (`verificar_entorno.py`):
**19 OK · 2 WARN · 0 FAIL** → modo `integration_gui`; los 2 WARN (proyecto no
instalado) se resolvieron con `uv sync`.

Un commit por tarea (T5 = 2 commits documentales). Nunca push.

```
ca5f6ec feat(world): get_world_context kind="pcb" (B1, D-09.1)
bbe63bc test(pcb): E2E round-trip de add_track (B2, D-09.2)
13f0d9c feat(pcb): add_via (B3, D-09.3)
24826cb feat(export): pcb_png real vía kicad-cli pcb render (D-09.3)
e0122ce docs(adr): ADR-0009 port a Rust diferido con condiciones (D-09.5)
452aa46 docs(catalog): catálogo honesto (D-09.4)
1085823 chore: higiene D3
```

---

## 1. Estado por tarea

| Tarea | Estado | Notas |
|---|---|---|
| **T1 · B1 lectura PCB** (D-09.1) | ✅ | `get_world_context(kind="pcb")` lee el board vivo en 1 pasada IPC, snapshot vivo (`mtimes=None`), TOON con `snap_id`. 6 unit + 1 integration_gui. |
| **T2 · E2E add_track** (D-09.2) | ✅ | Round-trip contra KiCad real con teardown kipy. **No reveló bug.** |
| **T3 · add_via** (D-09.3) | ✅ | Bridge + tool + catálogo. 5 unit tool + 1 bridge (busy sin retry) + 1 integration_gui round-trip. |
| **T4 · pcb_png real** (D-09.3) | ✅ | `kicad-cli pcb render` (render 3D). Nota del catálogo corregida. Test integration (magic bytes PNG). |
| **T5 · ADR Rust + catálogo honesto** (D-09.4/5) | ✅ | ADR-0009; phantom tools → reservadas; `discover_tools` eliminada. |
| **T6 · Higiene D3** | ✅ | `_ = ref` eliminado; `.gitignore` de basura GUI; `video-backups/` removido; docstrings stale corregidos. |

### ¿B2 destapó un bug de `add_track`? — NO

A diferencia del precedente T1 de `move_footprint` (ADR-0008), el round-trip
E2E de `add_track` **pasó a la primera sin bug**. Diagnóstico de por qué el
patrón era seguro (ya anticipado en ADR-0008 §"Adicionalmente"): `add_track`
construye un `Track()` vacío y asigna por **setters directos**
(`track.start`, `track.end`, `track.width`, `track.layer`, `track.net`) sobre
el proto interno, y persiste con `create_items` — nunca cayó en el patrón
getter-mutación que perdía la escritura en `move_footprint`. La verificación
E2E lo confirma: geometría exacta (±1 nm) y net asignada. `add_via` sigue el
mismo patrón seguro y también pasó a la primera.

---

## 2. Tokens y latencia de `get_world_context(kind="pcb")` — board real

Board de prueba: **189 footprints / 588 nets** (de las 202 refs, 189 son
footprints en el `.kicad_pcb`; el resto son símbolos sin footprint).

| Lectura | tokens_est | Latencia | Notas |
|---|---|---|---|
| Completo (sin budget efectivo) | **16 804** | **~2.5 s** | 1 pasada IPC `read_board_context` |
| Focus r=20 @U19 (max=14000) | **7 720** (degradado) | ~2.6 s | el focus recorta ~54 % |
| Sin focus, max=16000 | **CONTEXT_BUDGET_IMPOSSIBLE** | — | piso de nets > 16 000 tok |

**Lectura clave para el dogfooding:** este board de 189 fp / 588 nets es un
**caso de estrés muy por encima del objetivo** (placas típicas 10-60
componentes, hoja de ruta v2 §objetivo 1). El listado de 588 nets **domina el
payload**: sin focus, ni la degradación §4 completa baja de ~15 600 tokens
(el colapso de nets de poder + omisión de posiciones no toca la mayor parte
del listado de nets). Con `focus_ref` + budget, el board local sí cabe
(7 720 tok con r=20). Para placas del tamaño objetivo el TOON completo será de
cientos a pocos miles de tokens y el problema no aparece. **Implicación:** en
boards grandes el agente DEBE usar `focus_ref` desde el arranque; conviene que
el prompt del agente lo instruya.

Latencia de la lectura viva: **~2.5 s** (una pasada `get_footprints()` en el
hilo de UI; consistente con el 83 % IPC de la descomposición de sesión 08).

---

## 3. Confirms de mutación + round-trips E2E

Confirms literales (todos **≤ 50 tokens**, ADR-0004):

| Tool | Confirm | tokens_est |
|---|---|---|
| `add_via` | `OK add_via +3.3V @(213.8,113.3) d0.80/0.40 [snap:1]` | **14** |
| `add_track` | `OK add_track +3.3V (208.8,108.3)->(210.8,110.3) w=0.25 @F.Cu [snap:1]` | **19** |
| `move_footprint` | `OK move_footprint U19 -> (…) [snap:N]` | 13 |

**Round-trip E2E `add_track` (B2):**
```
confirm:  OK add_track +3.3V (208.8,108.3)->(210.8,110.3) w=0.25 @F.Cu [snap:1]
kipy read: start=Vector2(208788000, 108331000) end=Vector2(210788000, 110331000) net=+3.3V
→ geometría ±1 nm ✓, net asignada ✓, teardown (remove_items) ✓
```

**Round-trip E2E `add_via` (B3):**
```
confirm:  OK add_via +3.3V @(213.8,113.3) d0.80/0.40 [snap:1]
kipy read: pos=Vector2(213788000, 113331000) net=+3.3V d=800000 drill=400000
→ posición ±1 nm ✓, net ✓, diámetro 0.8 mm ✓, drill 0.4 mm ✓, teardown ✓
```
Latencia (log JSON): `add_track` 2 883 ms (read 2 691), `add_via` 2 547 ms
(read 2 356) — el read IPC domina, escritura y derivación son marginales.

---

## 4. `pcb_png` de muestra

Render 3D del board de prueba (189 fp), vista top:

```
/tmp/gui-test-project-render.png   (118 987 bytes, PNG, 1600×900)
```

Generado con `kicad-cli pcb render --side top` (~2.6 s de render + ~8 s de
carga del modelo = ~11 s wall). El fixture limpio 005 rinde en el test
integration (9 734 bytes). Es un render 3D real (no un plano de capas):
feedback visual para el cliente MCP (Claude Code acepta imágenes, D-R5).

---

## 5. Promedios y tiempos (DoD)

- **Confirms:** μ ≈ 15 tokens (14/19/13), techo 50 ✓.
- **Refreshes acotados (confirm/delta):** ≤ 400 ✓ (peor caso histórico delta
  332). El `full` de `get_world_context` es **agente-presupuestado** vía
  `max_tokens`/`focus_ref`: en un board del tamaño objetivo cabe en cientos de
  tokens; en el board de estrés de 189 fp pide 16 804 sin budget (por eso la
  tool expone la degradación §4 y el focus).
- **Suites (DoD):**

```
uv run pytest -m "not integration and not integration_gui"  → 123 passed (~13 s)
uv run pytest -m integration                                → 21 passed (3:37)
uv run pytest -m integration_gui                            → 7 passed (54.8 s)  [4 previos + B1+B2+B3]
uv run mypy src/                                            → Success (31 files, strict)
uv run ruff check + format --check                          → clean (50 files)
```

---

## 6. Checklist para Dogfooding Etapa 1 (sesión 10)

Lo que el humano debe preparar para que la sesión 10 arranque sin fricción
(desde el conocimiento del código):

1. **Copia descartable del proyecto real.** Copiar la carpeta del proyecto
   KiCad fuera del repo (p. ej. a `/tmp/dogfood-proyecto/`). G1 + git mitigan,
   pero trabajar sobre copia es la regla (E1 §riesgo). El proyecto debe tener
   `.kicad_pro` + `.kicad_sch` + `.kicad_pcb` con nombres coincidentes (el
   resolvedor ancla el raíz por el `.kicad_pro`).
2. **Esquemático terminado.** El flujo PCB asume el sch ya poblado y cableado
   (el flujo sch es de las sesiones 11-12). ERC idealmente limpio.
3. **F8 hecho (sync sch→pcb).** Los footprints deben existir en el board:
   `move_footprint` mueve, no crea. En KiCad: *Tools → Update PCB from
   Schematic* (F8). Sin esto el board está vacío y no hay nada que colocar.
   **Single-sheet** (multi-hoja está diferido, D-R1: la lectura sch de disco
   falla con `UNSUPPORTED_HIERARCHY`; la lectura pcb viva NO tiene ese
   límite, así que la mitad PCB del flujo funciona igual).
4. **KiCad abierto con el PCB Editor cargado** sobre la copia, y el **API
   server habilitado** (*Preferences → Plugins → Enable API server*). Sin PCB
   Editor abierto, `kind="pcb"` responde `KICAD_CLI_FAILED`
   (`ipc_status="unhandled"`).
5. **Env vars exportadas** en la shell que corre el agente/servidor:
   - `KICAD_MCP_PROJECT=/tmp/dogfood-proyecto` (carpeta del proyecto).
   - `KICAD_API_SOCKET=ipc:///tmp/kicad/api.sock` (o el que reporte KiCad).
   - `KICAD_API_TOKEN` lo setea KiCad; el bridge lo usa para detectar
     reinicios. Si reiniciás KiCad a mitad de sesión, el agente recibirá
     `KICAD_RESTARTED` y deberá re-pedir `get_world_context`.
6. **DRC de partida conocido.** `export_manufacturing` está tras el Gate G3
   (bloquea si hay errores de DRC). Si la placa arranca con errores, el
   agente los verá y el export quedará bloqueado hasta resolverlos — es el
   comportamiento correcto, pero conviene saberlo de antemano.
7. **Recomendación de uso:** arrancar con `get_world_context(kind="pcb",
   focus_ref=<ref>, max_tokens=…)` en boards medianos/grandes — sin focus el
   payload puede ser de miles de tokens (ver §2).

Flujo que YA está validado E2E y cubre la Etapa 1: leer contexto PCB (B1) →
`move_footprint` → `add_track` → `add_via` → `run_drc` → `export_render`
(pcb_png para inspección visual) → `export_manufacturing` (G3).

---

## 7. Dudas abiertas

1. **Fixture 004_real con drift tracked.** `tests/fixtures/004_real/video.kicad_prl`
   y `video.kicad_pro` figuran **modificados** en git desde antes de esta
   sesión (alguien abrió el fixture en KiCad). Son contenido de fixture (F1),
   así que **no los toqué ni los revertí**. Recomendación: el humano decide si
   `git checkout` para restaurar el contenido committeado o si el cambio es
   intencional. (La basura *no tracked* —`video-backups/`— sí la removí y
   quedó gitignorada.)
2. **Defaults de via fijos vs. del board.** `add_via` usa defaults fijos
   0.8/0.4 mm (los clásicos de KiCad), no los del netclass/design-rules del
   board. Leerlos exigiría más superficie IPC (design settings). ¿Vale la
   pena, o los fijos alcanzan para el dogfooding? Se puede reabrir si el
   ruteo real lo pide.
3. **Piso de tokens en boards grandes (§2).** En placas con cientos de nets el
   listado de nets domina y la degradación §4 no baja de ~15 k tokens sin
   focus. Para el objetivo (10-60 comp) no es problema, pero si aparece un
   proyecto grande en el dogfooding, convendría un modo de degradación que
   resuma también el listado de nets (colapsar nets no-locales a un conteo).
   No lo hice: fuera de scope y sin evidencia de necesidad todavía.
4. **`pcb_png`: parámetros de cámara diferidos.** El CLI expone
   `--perspective/--zoom/--rotate/--side`; sólo fijé `--side top`. Si el
   dogfooding pide vistas isométricas o de detalle, exponerlos como params de
   la tool es barato (S).

### Scripts de `scratchpad/` archivables (no borrados)

De `scratchpad/` (gitignorado; el prompt de cada sesión los re-descubre).
Archivables por el humano: `baseline_08.py` (ya marcado), `measure_health.py`,
`measure_mutation_latency.py`, `verify_derivation.py`, `parse_004.py`,
`inspect_sheet.py`, `add_symbol_test.py`, `add_symbol_demo.py`. Conservar:
`spike-kicad-skip.md` (referencia del spike sesión 05). Directorios de trabajo
(`004_copy/`, `spike-venv/`, `rams_added.kicad_sch`) también archivables.
