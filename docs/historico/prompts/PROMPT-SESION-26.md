# Sesión 26 — Fix P1: solder mask bridge en ANT1

**Tipo:** investigación acotada + fix quirúrgico (posiblemente mínimo) + test
de regresión. Nueva rama `sesion/26-fix-solder-mask-ant1` desde `master`
**post-merge de la rama de docs de sesión 25** (fixture + CONTEXT/ROADMAP/
BACKLOG/hoja-de-ruta actualizados — mergear primero para que el reporte de
D5 esté disponible en `master`).

**Origen:** P1 vigente desde D4 (sesión 22): el pad de ANT1 hace bridge de
máscara de soldadura (`solder_mask_bridge`) con la zona GND. El fix de
sesión 21 (F-D3-01, `enforce_hole_clearance`) protege el *hole* con un
keepout de cobre — no fue diseñado para proteger la *apertura de máscara*
del pad, que es una superficie distinta.

**Dato nuevo de D5 (sesión 25) que cambia el punto de partida — leer
primero:** en el baseline DRC pre-route de D5, ANT1 mostró exactamente 1
violación `solder_mask_bridge` contra la zona GND (mismo punto que las
violaciones `hole_clearance`/`clearance`). **Post-route, las 3 desaparecieron
juntas** — el keepout `__kicadmcp_hc__` auto-generado por
`enforce_hole_clearance` (que protege el hole, radio = radio_hole +
min_hole_clearance + margen) también terminó cubriendo el caso de máscara en
esa geometría específica (ANT1 tiene un hole PTH de 2mm, relativamente
grande). Esto **no confirma que el bug esté cerrado en general** — es una
sola geometría, y el margen del keepout de hole podría no alcanzar para
apertura de máscara en pads con hole más chico o clearance de proyecto más
ajustado. Pero sí significa que **el punto de partida de esta sesión es
verificar, no asumir.**

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4.

## Preparación (antes del Bloque 0)

1. Verificar que la rama de docs de sesión 25 ya está mergeada en `master`.
2. `git checkout master && git pull`.
3. `git checkout -b sesion/26-fix-solder-mask-ant1`.
4. `/tmp/gui-test-project/` restaurado desde el fixture
   `tests/fixtures/despertador-routed/` (ya actualizado por D5 — ruteo
   completo, DRC 0/0).
5. KiCad reiniciado limpio. `health()` → ipc ok, kicad-cli 10.0.4.
6. **Lectura obligatoria antes de arrancar:**
   - `docs/historico/sesiones/25-reporte.md` (evidencia del hallazgo).
   - `docs/investigacion/21-fill-zones-holes.md` (por qué el fix de F-D3-01
     eligió keepout de cobre en vez de parchear el fill de kipy — el mismo
     razonamiento aplica acá: kipy no expone superficie de máscara vía IPC,
     confirmar si eso sigue vigente antes de diseñar el fix).
   - `src/kicad_mcp/bridge/ipc.py:1902-2036` (`enforce_hole_clearance`
     completo) — es el mecanismo que hoy protege el hole; el fix de esta
     sesión probablemente extiende o complementa este mismo pipeline, no lo
     reemplaza.

---

## Bloque 0 — Verificación de reproducción (timeout: 30 min, NUEVO respecto al patrón de sesión 24)

**Objetivo:** confirmar si el bug sigue siendo reproducible de forma
aislada, o si el hallazgo de D5 indica que ya está cerrado por accidente
geométrico en la mayoría de los casos reales.

1. Sobre el fixture actual (ya ruteado, DRC 0/0): correr
   `run_drc(min_severity="error")` — confirmar 0 `solder_mask_bridge`
   (debería coincidir con el cierre de D5).
2. **Reproducción aislada:** en una copia de trabajo separada (NO tocar el
   fixture despertador), construir el harness mínimo que aísla la variable
   "margen de keepout vs `solder_mask_margin`":
   - Board pequeño con outline arbitrario.
   - Zona de cobre GND filleada cubriendo la mitad del board.
   - Pad de test de net distinto (por ejemplo `/SIG`) con hole PEQUEÑO
     (0.3-0.5mm, bien por debajo de los 2mm de ANT1) posicionado tal que
     **la distancia entre el borde del pad y el borde interno de la zona
     GND filleada sea menor que `solder_mask_margin` del proyecto pero
     mayor que `hole_clearance`**. Esta geometría es lo que dispara el bug
     si existe: el keepout de `enforce_hole_clearance` (radio = hole +
     hole_clearance + margen) no alcanzaría a cubrir la superficie de
     máscara.
   - Correr el pipeline que dispara el mecanismo (probablemente
     `fill_zones` o `route_board` con refill, según el precedente de
     F-D3-01).
   - Verificar con `run_drc()` si aparece `solder_mask_bridge` en el pad
     de test.
3. Si el harness no dispara la violación con hole chico y distancia
   adversa → keepout de hole cubre el caso por diseño accidental de margen
   suficiente, confirmar cerrando el P1 con nota y saltar a Bloque 3.
4. Si sí dispara → bug real, proceder a Bloque 1 (diseño del fix real:
   probablemente ampliar el radio del keepout para cubrir
   `solder_mask_margin` del proyecto, o generar un keepout de máscara
   separado — evaluar cuál es menos invasivo dado que
   `enforce_hole_clearance` ya tiene toda la infraestructura de keepouts
   auto-generados).

**Salida esperada:** decisión documentada (bug cerrado incidentalmente vs.
bug real que necesita fix) ANTES de tocar código de producción.
**Escenario intermedio a considerar:** si el bug reproduce parcialmente
(aparece con hole 0.3mm pero NO con 0.5mm, o similar umbral geométrico),
tratar como "bug real" y proceder a Bloque 1 — el fix debe cubrir el peor
caso identificado, no solo el promedio.

---

## Bloque 1 — Diseño del cambio (timeout: 30 min, SOLO si Bloque 0 confirma bug real)

1. Leer cómo se lee `solder_mask_margin` en las reglas del proyecto. Si
   `rules_reader` ya lo expone → usar directamente. Si NO lo expone →
   **`AskUserQuestion` obligatoria al arquitecto** antes de extender
   `rules_reader`: es superficie de tool de lectura y puede tocar
   `tool-catalog.md` (F1). Alternativa aceptable sin extender: leer el
   valor directamente desde el archivo del proyecto en el bridge, con el
   mismo patrón de ingeniería inversa que se usó para edge clearance de
   Freerouting (D-V3.5). El arquitecto decide entre las dos rutas.
2. Decidir: ¿ampliar el radio existente del keepout de
   `enforce_hole_clearance` (radio = hole + hole_clearance + margen →
   radio = hole + max(hole_clearance, solder_mask_margin) + margen), o
   generar un segundo keepout específico de máscara? Preferir la opción
   más simple que no rompa el contrato existente de F-D3-01 (idempotencia,
   prefijo `_AUTO_KEEPOUT_PREFIX`, llamado desde `add_zone`/`fill_zones`/
   `route_board`).
3. **ADR requerido si el cambio introduce un contrato nuevo** (no solo
   aclaración) — criterio de siempre: naturaleza del cambio, no tamaño.

## Bloque 2 — Implementación (timeout: 45 min, SOLO si Bloque 1 corrió)

Igual disciplina que sesión 24: cambio mínimo, no tocar el loop de vías de
`enforce_hole_clearance` (D-23.3/R16, fuera de alcance), no tocar
`fill_zones`/`add_zone(fill=True)` más allá de lo que ya comparten con
`route_board` vía este mismo mecanismo. `ruff check` + `mypy src/` +
`pytest -m "not integration"` verdes antes de Bloque 3.

## Bloque 3 — Test de regresión (timeout: 45 min, gate del merge)

Igual que sesión 24 Bloque 3: fixture reproducible (helper que restaure
`despertador-routed` y limpie tracks, o el caso sintético de hole chico del
Bloque 0), assertion mandatoria: `run_drc()` post-fill/post-route sobre el
pad de ANT1 (o el caso sintético) tiene 0 `solder_mask_bridge`. Si el
Bloque 0 concluyó que NO había bug real, el test de regresión fija el
comportamiento actual (keepout de hole también protege máscara en la
geometría típica) para detectar si una futura sesión lo rompe.

## Bloque 4 — DoD, docs y merge (timeout: 30 min)

Checklist estándar del proyecto (`ruff`, `mypy`, `pytest -m "not integration"`,
`pytest -m integration` para el test nuevo en 2+ corridas). Actualizar
`docs/BACKLOG.md` (cerrar P1 o ajustar esfuerzo estimado según lo que salió
del Bloque 0/1). Reporte en `docs/historico/sesiones/26-reporte.md` con el
mismo formato de sesiones anteriores. **Antes de mergear:** `AskUserQuestion`
obligatoria al arquitecto con el diff completo (si hubo) y el resultado del
test.

---

## Fuera de alcance

- Loop de vías de `enforce_hole_clearance` (D-23.3, R16).
- `fill_zones`/`add_zone(fill=True)` como generalización completa de D-23.2
  (eso es sesión 27, paso separado de la secuencia).
- Cualquier feature nuevo o escalada de complejidad de placa.

## Env vars

```bash
export KICAD_MCP_GUI_TEST=1
export KICAD_MCP_PROJECT=/tmp/gui-test-project
export KICAD_MCP_GUI_REF=U1
export KICAD_MCP_FREEROUTING_JAR=/home/astra/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar
```

## Cierre esperado

- Bloque 0 documentado siempre (incluso si concluye "no hay bug que
  arreglar" — es un resultado válido y valioso, no un desperdicio de
  sesión, igual que un dogfooding sin hallazgos en Fase 3).
- Si hubo fix: mergeado con test de regresión verde, ADR si corresponde,
  `docs/BACKLOG.md` P1 cerrado.
- Si no hubo bug real: `docs/BACKLOG.md` P1 cerrado con nota explicativa +
  test de regresión que fija el comportamiento actual como contrato.
- Sesión 27 = generalización D-23.2 a `fill_zones`/`add_zone(fill=True)`,
  ya con condición de entrada cumplida desde D5.

**Nota sobre timeboxing en el escenario "no hay bug":** si el Bloque 0
concluye que el P1 se cerró incidentalmente, el tiempo total efectivo de
la sesión baja a ~105 min (Bloque 0: 30 + Bloque 3: 45 + Bloque 4: 30, con
Bloques 1 y 2 salteados). NO usar el tiempo ahorrado para expandir alcance
(por ejemplo, incluir preliminares de la generalización de sesión 27, o
meter fixes cosméticos, o investigar D-23.3/R16). El escenario "no hay
bug" es un cierre válido y limpio; terminar la sesión temprano es
correcto. La única expansión aceptable del tiempo ahorrado es reforzar el
test de regresión con más assertions defensivas — por ejemplo, verificar
el mismo comportamiento con dos tamaños de hole distintos (pequeño y
grande) para asegurar cobertura de rango, o con `solder_mask_margin`
alterado a un valor más adverso para dejar documentado el umbral de
seguridad del comportamiento actual.
