# Spike de autorouting (D-R11) — Informe / Veredicto

**Sesión 13 · 2026-07-12 · rama `sesion-13`**
**Entorno:** KiCad 10.0.4 (kicad-cli + IPC vivos), Java OpenJDK 21.0.11,
Freerouting **v2.1.0** (jar ya presente del plugin manager de KiCad).
**Placa:** `/tmp/spike-route-proyecto/despertador_inteligente` — copia de una
placa real del humano (original en `~/Desktop/Electronig_Proyects/`, **verificado
que es la copia**). 24 footprints (ATtiny + sensor IMU + radio RFM69 + opto +
batería + test points), 10 nets reales, **0 tracks / 0 vías** al inicio, sin
contorno Edge.Cuts. 64 conexiones ratsnest a rutear.

---

## TL;DR — VEREDICTO: **INTEGRAR**

Existe un camino de autorouting **headless, sin humano**, que sobre esta placa
produjo **100% del ratsnest ruteado con DRC sin un solo error** (0 shorts, 0
clearance) en **~2 minutos wall-clock** y a un costo de contexto de **1 llamada
de herramienta** (el router no habla con el LLM). Es ~5× mejor en completitud,
∞ mejor en shorts (0 vs 13) y ~100× más barato en tokens que el ruteo manual
por `add_track` medido en el Dogfooding 1. La fricción real no es el router:
es el **round-trip disco↔editor-vivo** (split-brain, F-05 en reversa) que la
tool de producción debe manejar. Diseño propuesto abajo.

---

## 1. Inventario de caminos para el round-trip DSN/SES (con evidencia)

El problema que hace o rompe el spike: exportar un **DSN** del board e importar
el **SES** que devuelve Freerouting, **sin GUI**. Cuatro caminos probados:

### Camino 1 — `kicad-cli` Specctra: **CERRADO** ✗ (evidencia)
`kicad-cli pcb export --help` → subcomandos: `3dpdf brep drill dxf gencad
gerbers glb hpgl ipc2581 ipcd356 odb pdf ply pos ps stats step stl stpz svg
u3d vrml xao`. **No existe `specctra`/`dsn`.**
`kicad-cli pcb import --help` → `--format {pads,altium,eagle,cadstar,fabmaster,
pcad,solidworks}`. **No importa SES.** kicad-cli no puede hacer el round-trip.

### Camino 2 — módulo SWIG `pcbnew` (python del SISTEMA): **FUNCIONA** ✓ [ELEGIDO]
```
$ /usr/bin/python3 -c "import pcbnew; print(pcbnew.GetBuildVersion())"  → 10.0.4
```
Expone ambas funciones, **con forma de 2 argumentos** (clave para headless):
```
ExportSpecctraDSN(BOARD aBoard, wxString aFullFilename) -> bool
ImportSpecctraSES(BOARD aBoard, wxString aFullFilename) -> bool
LoadBoard(wxString aFileName) -> BOARD ;  SaveBoard(fn, BOARD)
```
Con `LoadBoard` + la forma de 2-args **no hace falta `GetBoard()` ni GUI**: se
carga el board de disco, se exporta el DSN, y tras rutear se importa el SES y se
guarda. Probado end-to-end (§3). El export tardó **0.02 s**, el import **0.02 s**.

**Implicancias para el veredicto (fragilidad):**
- Es un **proceso hijo** con el python del sistema que instala KiCad — **NO una
  dependencia de `pyproject`** (F5 intacta), igual que `kicad-cli`.
- La API SWIG `pcbnew` está en **camino de deprecación anunciado** por KiCad a
  favor de la IPC API (kipy). Hoy (KiCad 10) sigue empaquetada en Arch y
  funciona. Riesgo a monitorear para KiCad 11/12 (F4 nos ancla a 10, así que no
  es bloqueante ahora).
- Acopla a que el módulo `pcbnew` exista en el python del sistema (en este
  entorno, sí; en otras distros/Flatpak podría no estar accesible).

### Camino 3 — plugin oficial de Freerouting para KiCad: **referencia, no headless** ✓/✗
Instalado en `~/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/`
con `jar/freerouting-2.1.0.jar`. Su `plugin.py` hace **exactamente** el round-trip
que buscábamos: `pcbnew.ExportSpecctraDSN` → `java -jar freerouting.jar -de in
-do out -host KiCad` → `pcbnew.ImportSpecctraSES`. **Pero está atado a la GUI**
(diálogos `wx`, `pcbnew.GetBoard()` del editor abierto, `ActionPlugin`): no es
invocable tal cual sin GUI. Su valor: **confirma la receta** y nos dio el jar.
El Camino 2 replica su lógica headless (y encima nos ahorró su fixup de header,
ver §5).

### Camino 4 — router interno de KiCad vía IPC (kipy): **CERRADO** ✗ (evidencia)
`dir(kipy.board.Board)` filtrado por ruteo → solo `get_nets`,
`get_items_by_net`, `get_items_by_netclass`, `get_netclass_for_nets` (lectura de
conectividad). **No hay autoroute, ni Specctra, ni DSN/SES.** El router interno
de KiCad **no está expuesto por la IPC API en KiCad 10**. Candidato descartado
(como anticipaba el prompt), con evidencia y en <30 min.

**Camino elegido:** #2 (pcbnew SWIG headless) + Freerouting jar. Esencialmente el
plugin oficial, pero sin GUI.

---

## 2. Estado inicial (baseline)

`kicad-cli pcb drc` sobre la copia pristina:
- **64 unconnected items** (el ratsnest completo — nada ruteado).
- **36 violations**: `invalid_outline`×1 (**error**, por falta de Edge.Cuts) +
  `silk_over_copper`×28 + `silk_overlap`×7 (**warnings** de serigrafía,
  preexistentes del placement del humano).

---

## 3. El round-trip (reproducible) y las corridas

Scripts en `scratchpad/spike-autoroute/` (entregable para sesión 14):
- `01_export_dsn.py` — `LoadBoard`; si falta Edge.Cuts dibuja un rectángulo =
  bbox(items)+5 mm y guarda; `ExportSpecctraDSN`.
- `roundtrip.sh` — orquesta: export DSN → `java -jar freerouting-2.1.0.jar -de
  X.dsn -do X.ses -host KiCad` (mide solo el router) → import SES.
- `02_import_ses.py` — `LoadBoard`; `ImportSpecctraSES`; `SaveBoard`; reporta
  conteos.

Ejecución: `roundtrip.sh <src.kicad_pcb> <workdir> <label>`. Corrido **2 veces**
sobre copias limpias del pristino:

| | run1 | run2 |
|---|---|---|
| Contorno dibujado | 52.3×53.5 mm | 52.3×53.5 mm |
| Export DSN | 0.02 s | 0.02 s |
| **Router (wall-clock)** | **101.8 s** | **122.1 s** |
| Import SES | 0.02 s | 0.01 s |
| Tracks / vías resultantes | 318 / 26 | 348 / 24 |
| **Ratsnest ruteado (log)** | 24→0 unrouted | →0 unrouted |
| **DRC: unconnected** | **0** | **0** |
| **DRC: errores** | **0** | **0** |
| **DRC: shorts / clearance** | **0 / 0** | **0 / 0** |
| DRC: warnings | 35 silk + 5 dangling | 35 silk + 7 dangling |

El router (log de Freerouting) convergió por pasadas: run1 `24→21→11→8→5→1→0`
unrouted, score 793→989, auto-routing en 1 min 15 s. **Completó el 100%.**

**Estabilidad:** dos corridas independientes → **ambas 100% ruteadas, 0 errores
DRC**. El conteo de tracks/vías varía (router estocástico) pero el resultado es
equivalente y limpio en las dos. Estable.

Renders en `/tmp/spike-route-proyecto/runs/before.png` (sin trazas, bbox pegado)
y `.../after.png` (trazas + contorno con margen). Diferencia visual clara.

---

## 4. Métricas del veredicto

- **Completitud:** **100%** (64/64 conexiones; 0 unconnected en DRC, ambas
  corridas).
- **Calidad DRC:** **0 errores**, **0 shorts**, **0 clearance**. Las únicas
  violaciones son *warnings*: 35 de serigrafía **preexistentes** (venían del
  baseline, no las introdujo el ruteo) + **5–7 `track_dangling`** (stubs con un
  extremo suelto que deja el router; warnings, no bloquean nada). El único
  **error** del baseline (`invalid_outline`) **se resolvió** al dibujar el
  contorno. → **G3 abre**: `check_drc_clean` bloquea solo con `severity=="error"`
  (`gates/g3.py:45`); con 0 errores, la exportación de gerbers queda habilitada.
- **Tiempo:** round-trip total **~102–122 s**, dominado por el router
  (export+import < 0.1 s combinados). Render de verificación aparte (~5 s c/u).
- **Costo de contexto del agente:** **1 llamada de herramienta** para disparar
  el round-trip + leer ~10 líneas de resumen (≈ cientos de tokens). **El router
  no intercambia una sola palabra con el LLM.**
- **Fricción de integración:** ver §5.

---

## 5. Comparación contra el baseline del Dogfooding 1 (D-R3)

| Métrica | Ruteo-LLM manual (Dogfood 1) | **Autorouter (este spike)** |
|---|---|---|
| Completitud del ratsnest | ~14/64 (**22%**) | **64/64 (100%)** |
| Shorts introducidos | **13** + 1 crossing | **0** |
| Errores DRC finales | board quedó **peor** (irreversible) | **0 errores** |
| Tokens del agente | **~14–16k** | **~cientos** (1 call) |
| Turnos / tiempo | 25–40 turnos extrapolados | 1 call, **~2 min** wall |
| Saves humanos (Ctrl+S) | 2 | **0** (headless a disco) |
| Razonamiento geométrico | ~300 tok/track offline | **ninguno** |

El autorouter gana en **todas** las dimensiones que el Dogfooding 1 midió como
bloqueantes. El plan B (subir la inteligencia de `add_track`: anclaje a pads,
rechazo de shorts, etc.) queda **descartado por costo/beneficio**: reconstruir
medio DRC dentro de la tool para llegar, con suerte, a lo que Freerouting da
gratis en 2 minutos, no se justifica. `add_track`/`add_via`/`delete_track`
quedan como **retoque puntual** post-autoruteo (su rol correcto).

---

## 6. Fricción de integración y superficie de la tool

### 6.1 La fricción real: split-brain disco↔editor-vivo (F-05 en reversa)
El round-trip opera sobre **disco** (`LoadBoard`/`SaveBoard`). Si KiCad tiene el
board **abierto** (en este entorno hay `~*.lck` presentes), aparecen dos
problemas:
1. `SaveBoard` headless escribe el archivo **bajo los pies del editor**; si el
   humano luego guarda desde KiCad, **clobbea** el board ruteado.
2. El editor vivo **no ve** las tracks nuevas hasta recargar, y `reload_in_gui`
   **no es factible en KiCad 10** (D-12.4, diferido a 11).

En el spike esto **no afectó** porque trabajé sobre **copias** en `runs/`, no
sobre el archivo abierto. Pero la tool de producción debe resolverlo. Opciones:
- **(recomendada)** `route_board` corre el pipeline y **deja el resultado en
  disco**, devolviendo en el confirm el hazard "recargá el board en KiCad"
  (mismo patrón ya documentado en `guia-paleta.md` para mutaciones de sch). Se
  apoya en `save_board` (sesión 11) para bajar live→disco **antes** de exportar
  el DSN, de modo que el router vea el placement vigente.
- Alternativa: exigir KiCad cerrado durante `route_board` (más simple, menos
  ergonómico).

### 6.2 Superficie propuesta
```
route_board(policy?: "default"|"quality", max_passes?: int, timeout_s?: int)
  -> confirm { tracks, vias, unrouted, router_secs, drc_errors, snap_id }
```
Pipeline interno: `save_board` (live→disco) → export DSN (dibuja Edge.Cuts vía
`draw_board_outline`/D-12.5 si falta) → **Freerouting subprocess** (timeout
presupuestado, default ~180 s) → import SES → `SaveBoard` → confirm con hazard de
recarga. **Es una mutación masiva de cobre → debe pedir confirmación (G2-like)
antes de correr.** Nota de timing: el router excede de lejos el timeout IPC de
2 s, pero **corre como subprocess, no por IPC**, así que no toca la cola IPC de
profundidad 1 (solo el `save_board` inicial usa IPC). Compatible con la
contención D-12.7.

### 6.3 Pasos frágiles / notas
- **DSN header fixup:** el plugin oficial reescribe la 1ª línea del DSN y
  strippea chars Unicode (Ω µ Φ) que rompen a Freerouting. Con la forma de
  **2-args + `LoadBoard`** el DSN salió **válido directo** — Freerouting lo
  consumió sin fixup. (Si aparecieran nets con esos símbolos, reincorporar el
  strip del plugin.)
- **`track_dangling` (5–7):** stubs que deja el router; son *warnings*. Cleanup
  opcional post-ruteo con `delete_track`, o ignorar (no bloquean G3).
- **Requisitos de sistema** (decisión del humano, sesión 14; NO van a pyproject):
  (a) **Java ≥ 21** — presente (`openjdk 21.0.11`); en Arch: `sudo pacman -S
  jre-openjdk`. (b) **freerouting jar** — ya presente vía el plugin de KiCad; si
  no, release en `github.com/freerouting/freerouting/releases`. (c) **módulo
  `pcbnew`** del python del sistema — presente. Los tres se detectan/documentan
  como `kicad-cli` (health check), no como deps del proyecto.

---

## 7. Recomendación

**INTEGRAR** un `route_board` de superficie mínima en la sesión 14, con:
- **Motor:** Freerouting jar (subprocess) vía round-trip Specctra headless con
  `pcbnew` SWIG (Camino 2). NO usar IPC para el router (no existe).
- **Diseño:** confirmación previa (muta cobre en masa) · `save_board` →
  export DSN (+`draw_board_outline` si falta) → freerouting con timeout
  presupuestado → import SES → SaveBoard → confirm con conteos + hazard de
  recarga en GUI (KiCad 10 no recarga solo).
- **Requisitos de sistema documentados** (Java 21, jar, pcbnew), estilo
  kicad-cli. Cero cambios a pyproject/specs/goldens.
- **`add_track`/`add_via`/`delete_track`** quedan para retoque; el autorouter es
  el camino primario del ruteo.

Los scripts de `scratchpad/spike-autoroute/` son directamente promovibles: la
sesión 14 los envuelve en la tool.

---

## 8. Dudas abiertas / qué necesita la sesión 14

**Del arquitecto (decisiones):**
1. **Split-brain (§6.1):** ¿`route_board` deja en disco + hazard de recarga
   (recomendado), o exige KiCad cerrado? Define la ergonomía de la tool.
2. **Gate:** ¿`route_board` entra bajo G2 (confirmación interactiva, es mutación
   masiva) o como las de cobre bajo G1+git (D-R8)? Muta MUCHO cobre de una;
   me inclino por confirmación previa.
3. **Perfil del router:** el default de Freerouting basta (100%, 0 errores). No
   se probó `quality`/más pasadas — innecesario en esta placa; exponer
   `max_passes` como opcional y default = auto.

**Del humano (sistema):**
4. Confirmar que Java 21 + jar + pcbnew son requisitos aceptables de sistema
   (como kicad-cli) antes de que la 14 construya la tool.
5. Si el objetivo apunta a KiCad 11+, planear la migración del round-trip fuera
   de SWIG `pcbnew` (deprecación anunciada) — hoy no bloquea (F4 = KiCad 10).

**Riesgo residual:** la placa del spike es de 24 componentes / densidad media.
Freerouting escala peor con densidad; para el rango alto (60 comp, muchas
señales cruzadas) puede no llegar al 100% o tardar más. El Dogfooding 2 (placa
real end-to-end) es el próximo punto de medición.
