# Reporte de sesión 26 — Investigación P1 solder mask bridge ANT1

**Tipo:** verificación acotada → bug confirmado real → fix diseñado con el
arquitecto → verificación contra KiCad real → fix insuficiente → escalado
como investigación abierta (mismo protocolo que sesión 23/investigación 21).
Rama `sesion/26-fix-solder-mask-ant1` (mergeada `sesion/25-post-dogfooding-docs`
→ `master` primero, requisito de la sesión). Reporte completo con evidencia:
`docs/investigacion/26-solder-mask-ant1.md`.

## Resumen ejecutivo

El P1 vigente desde D4 (sesión 22) — el pad de ANT1 hace `solder_mask_bridge`
con la zona GND — **sigue abierto**, pero con el estado del conocimiento
completamente distinto al de inicio de sesión. Tres resultados:

1. **La hipótesis de D5 (sesión 25) es FALSA, refutada con un número.** El
   keepout auto-generado `__kicadmcp_hc__pad_ANT1_1` tiene r=1.27mm; el
   cobre del pad de ANT1 tiene r=1.50mm. El keepout está ÍNTEGRAMENTE
   DENTRO del cobre del propio pad — geométricamente incapaz de haber
   resuelto nada de máscara. No fue "cubierto por accidente geométrico".
2. **El bug es real y alcanzable.** Con `pad_to_mask_clearance` del
   proyecto ≥ ~0.22mm (valor dentro de rangos reales de fabricación), ANT1
   muestra `solder_mask_bridge` contra la zona GND SIN `clearance`/
   `hole_clearance` acompañante — un modo de falla genuinamente
   independiente del mecanismo de hole existente.
3. **El fix diseñado con el arquitecto (`AskUserQuestion`, extender
   `rules_reader` + radio único `max(hole, cobre+mask_clearance)`) NO
   resolvió el bug al verificarlo contra KiCad real** — la verificación
   propia (no solo aritmética) lo descubrió antes de mergear. Un barrido de
   radio de keepout aisló el umbral real entre 1.82mm (falla) y 2.0mm
   (resuelve), sin que ese número se derive limpiamente de la fórmula
   usada ni de una teoría única y consistente con TODOS los experimentos.

Con el mecanismo sin aislar, y siguiendo el mismo protocolo que
investigación 21 (sesión 21) estableció para esta situación exacta, se
consultó al arquitecto (`AskUserQuestion`) y se decidió **parar y escalar**
en vez de mergear un workaround no confirmado. El código del fix se
REVIRTIÓ; solo se conserva la extensión de `rules_reader.py` (lectura
correcta y testeada, independiente del mecanismo, útil para la próxima
investigación).

## Bloque 0 — Verificación de reproducción (✓ completado)

0.A (refutación geométrica, offline) y 0.B (reproducción en vivo del fill
rancio de D5, sobre `/tmp/gui-test-project` restaurado) confirmaron: la
hipótesis de D5 es falsa (0.A), y el patrón de D5 específico (zona rellena
antes de la colocación masiva de footprints, `move_footprint` no dispara
refill) es plausible como causa de ESE baseline puntual (0.B) — pero no
descarta ni confirma por sí solo el bug independiente de máscara.

0.C (barrido offline de `pad_to_mask_clearance`, `kicad-cli pcb drc` sobre
copias del fixture, control M=0 validado idéntico al board vivo) SÍ
confirmó el bug independiente: threshold entre M=0.20 (limpio) y M=0.22
(bridge sin `clearance` co-localizada), determinístico (re-corrida idéntica
en violaciones).

**Decisión 0.D:** bug real, alcanzable → proceder a Bloque 1 (contrario a
la expectativa de la sesión, que anticipaba probablemente cerrar sin fix).

## Bloque 1 — Diseño (✓ completado, con el arquitecto)

`AskUserQuestion` con dos bifurcaciones, ambas resueltas por el
arquitecto: (1) extender `rules_reader.py` con un segundo parser para el
`.kicad_pcb` (donde vive `pad_to_mask_clearance` — NO en el `.kicad_pro`
que el módulo ya leía), en vez de leer inline en el bridge; (2) un solo
keepout por pad con radio = máximo entre el término de hole existente y un
nuevo término de máscara (cobre del pad + `max(pad_to_mask_clearance,
solder_mask_to_copper_clearance)` + margen existente), en vez de un
keepout de máscara separado.

## Bloque 2 — Implementación (✓ completado, luego revertido)

Implementado exactamente según Bloque 1: `ProjectRules` ganó dos campos
(lectura dual-archivo, cache por el par de mtimes), `PadHole` ganó tamaño
de cobre, `enforce_hole_clearance` calculó el radio máximo. Unit tests
nuevos (fórmula + extracción de reglas) verdes, `ruff`/`mypy` limpios.

## Verificación adicional (no exigida por el prompt original, agregada
proactivamente antes de declarar el fix listo)

Antes de pasar a Bloque 3 (tests de regresión GUI), se verificó el fix
contra KiCad real usando el patrón offline de 0.C más inyección quirúrgica
del polígono de keepout exacto que `enforce_hole_clearance` generaría. **La
violación seguía presente, idéntica, en el valor que la fórmula del fix
calcula (1.82mm).** Un barrido de radio (manteniendo `pad_to_mask_clearance`
fijo) mostró que hacen falta ≥2.0mm — un número que no se deriva de la
fórmula acordada. Detalle completo, incluida una teoría parcial (apotema
del polígono de 16 vértices) que NO reconcilia con todos los experimentos,
en `docs/investigacion/26-solder-mask-ant1.md` §5-§6.

## Qué NO se hizo, y por qué

- **No se mergeó el fix de `enforce_hole_clearance`/`PadHole`** — se
  implementó, se verificó insuficiente, se revirtió. Mergear un radio sin
  entender por qué funciona (o no) hubiera repetido exactamente el patrón
  que investigación 21 evitó deliberadamente para el bug original de hole.
- **No se siguió ajustando el radio a ciegas** hasta encontrar un valor
  que "pasara" — el arquitecto lo descartó explícitamente
  (`AskUserQuestion`) en favor de escalar como investigación abierta.
- **No se investigó más el mecanismo dentro de esta sesión** (tercera
  opción que el arquitecto no eligió) — el timebox razonable ya se había
  excedido con evidencia genuina pero contradictoria entre dos
  experimentos.
- **Sin ADR** — no hay contrato nuevo mergeado (el único cambio de
  producción, la extensión de `rules_reader`, es aclaración/capacidad de
  lectura, no un contrato arquitectónico nuevo).
- Fuera de alcance respetado: loop de vías de `enforce_hole_clearance`
  (D-23.3/R16), generalización D-23.2 a `fill_zones`/`add_zone(fill=True)`
  (sesión 27, no bloqueada por este resultado).

## Tests de regresión

Los añadidos para `rules_reader.py` (`tests/test_rules_reader.py`) se
conservan — 7 tests nuevos cubriendo lectura dual-archivo
(`pad_to_mask_clearance` del `.kicad_pcb`, `solder_mask_to_copper_clearance`
del `.kicad_pro`, ambos juntos, cache invalidando por cualquiera de los dos
archivos, defaults). Los tests de `enforce_hole_clearance` con el radio
nuevo se revirtieron junto con el código que testeaban.

## DoD

- `uv run pytest -m "not integration"`: verde (con solo el cambio de
  `rules_reader.py` en pie).
- `uv run ruff check` / `ruff format --check`: limpio.
- `uv run mypy src/`: limpio.
- Sin cambio de tool ni de `tool-catalog.md` (ninguna tool MCP cambió de
  contrato).
- Sin ADR (criterio: no hay contrato arquitectónico nuevo mergeado).
- `docs/BACKLOG.md` P1: reescrito, no cerrado — retracción explícita de la
  hipótesis de D5, hallazgos confirmados, estado del código, condición de
  entrada para la próxima sesión sobre el tema.

## Estado del ciclo

Fase 3 sigue sin P0 nuevos. P1 pasa de "verificar hipótesis de D5" a
"investigación abierta, re-estimada M/L" — no bloquea el resto de la
secuencia: sesión 27 (generalización D-23.2 a `fill_zones`/
`add_zone(fill=True)`) puede proceder, condición de entrada ya cumplida
desde D5 y ortogonal a este hallazgo. Una futura sesión dedicada a P1
debe leer `docs/investigacion/26-solder-mask-ant1.md` completa (en
particular §5-§6, el barrido que no se explica del todo) antes de
re-intentar un fix, para no repetir el mismo diseño ya probado
insuficiente.

## Artefactos

- `docs/investigacion/26-solder-mask-ant1.md` — investigación completa.
- `docs/BACKLOG.md` — P1 reescrito.
- `docs/CONTEXT.md`, `docs/ROADMAP.md`, `hoja-de-ruta-v4.md` — actualizados.
- `src/kicad_mcp/bridge/rules_reader.py` + `tests/test_rules_reader.py` —
  únicos cambios de código que se conservan.
