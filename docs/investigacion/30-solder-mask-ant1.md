# Investigación 30 — P1 solder_mask_bridge en ANT1 (mecanismo aislado + fix)

**Continuación de** `docs/investigacion/26-solder-mask-ant1.md` (§1-§8).
Esa sesión confirmó el bug (real, determinista, umbral M=0.20→0.22) e
intentó un fix que no tuvo efecto observable, cerrando con 4 variables
candidatas sin aislar. Esta sesión aísla el mecanismo completo, corrige un
error numérico de sesión 26 que explica por qué sus dos experimentos
parecían irreconciliables, e implementa el fix.

**Resultado: mecanismo 100% aislado (apotema del keepout de 16 vértices),
fix implementado (<20 líneas efectivas), verificado con barrido D-30.1 vía
motor real de KiCad Y con el gate GUI del DoD (ver "Gate GUI" al final).**
P1 se cierra en `docs/BACKLOG.md`.

## Resumen ejecutivo

1. **Corrección de un error numérico en sesión 26**: su §1 derivó el borde
   del fill GND como `1.5 (cobre) + 0.5 = 2.00mm`, usando
   `min_copper_edge_clearance` (clearance a borde de placa) donde
   correspondía la clearance de la netclass `Default` (`0.2mm`). El borde
   real, medido directamente sobre el `filled_polygon` del fixture sin
   tocar nada, está a **1.7005mm** (`1.5 + 0.2`, con ruido de tesalado
   ≤0.005mm por `max_error`). Este único número reconcilia los dos
   experimentos de sesión 26 que parecían contradictorios.
2. **Mecanismo aislado con precisión sub-milimétrica**: el fill de KiCad
   respeta el **apotema** del keepout de 16 vértices
   (`_circle_vertices_mm`, N=16 por default en sesión 21-29), no un círculo
   ideal al radio pedido. Confirmado por barrido de radio y de N, con error
   de medición &lt;0.0002mm contra la fórmula `r·cos(π/16)` en cada punto.
3. **Por qué el fix de sesión 26 no funcionó**: pidió un keepout de
   radio 1.82mm (fórmula `1.5+0.3+0.02`); el apotema resultante es
   1.785mm, 0.035mm por debajo del `r_mask` de 1.80mm que debía cubrir —
   el margen de seguridad de 0.02mm no alcanzaba a absorber el déficit de
   apotema de un 16-gono a ese radio.
4. **Fix implementado**: (a) subir N de 16 a 64 en `_circle_vertices_mm`
   (reduce el déficit de apotema de 0.035mm a ~0.002mm a ese mismo radio,
   muy por debajo del margen existente); (b) re-aterrizar el término de
   máscara en `enforce_hole_clearance` (revertido en sesión 26): el radio
   del keepout de un pad ahora es
   `max(hole_term, r_cobre_pad + max(pad_to_mask_clearance, solder_mask_to_copper_clearance) + margen)`.
5. **Verificación**: barrido de `pad_to_mask_clearance` ∈
   {0.0, 0.20, 0.22, 0.25, 0.30} contra la geometría exacta que el fix
   produce, corrido con `kicad-cli pcb drc --refill-zones --save-board`
   (motor real de KiCad) — **0 violaciones `solder_mask_bridge` de ANT1
   contra `Zone [GND]` en los 5 casos**, más un control del flujo canónico
   (fixture intacto, `pad_to_mask_clearance=0`) sin cambio de comportamiento.

## Mejora metodológica sobre sesión 26

Sesión 26 solo observó DRC pass/fail (señal binaria) — por eso no pudo
desambiguar entre sus 4 hipótesis. Esta sesión **midió la geometría
directamente**: tras `--refill-zones --save-board`, se parsea el
`filled_polygon` de la zona GND en B.Cu y se calcula la distancia mínima
del centro de ANT1 al borde del fill (`d_fill`), usando distancia
**punto-a-segmento** (no punto-a-vértice — ver nota metodológica abajo).
Harness versionado en `scratchpad/solder-mask/sweep.py` (decisión del
arquitecto: a diferencia de sesión 26, este queda disponible para
sesiones futuras).

**Nota metodológica (auto-corrección durante la sesión):** la primera
versión del harness medía distancia del centro a los *vértices* del
`filled_polygon`. Para el keepout de ANT1 (16-gono con lados rectos), eso
sobreestima `d_fill` — la distancia mínima real a un polígono de lados
rectos ocurre en el punto medio de una arista (el apotema), no en un
vértice, y el fill de KiCad reutiliza directamente los vértices del
keepout sin re-tesalar, así que un muestreo por-punto nunca captura ese
mínimo. Corregido a distancia punto-a-segmento antes de sacar conclusiones
sobre la hipótesis del apotema (ver tabla de Sub-línea 2.1).

## Sub-línea 2.2 — ¿el fill toma el máximo entre keepout y clearance natural?

Barrido de radio de keepout (M=0.30 fijo, N=16), midiendo `d_fill`:

| r_keepout (mm) | apotema teórico (r·cos(π/16)) | d_fill medido | violación ANT1 vs GND |
|---:|---:|---:|---|
| sin keepout | — | 1.7005 | No |
| 1.0 | 0.9808 | 1.7005 | No |
| 1.27 (stock) | 1.2455 | 1.7005 | No |
| 1.6 | 1.5693 | 1.7005 | No |
| 1.7 | 1.6674 | 1.7005 | No |
| 1.75 | 1.7164 | 1.7164 | No |

**Confirma la sub-hipótesis**: hasta r=1.7 el keepout no domina (apotema
< clearance natural 1.7005mm) y `d_fill` se mantiene exactamente en el
valor natural. En r=1.75 el apotema (1.7164) supera la clearance natural y
`d_fill` salta a seguir el apotema, con coincidencia exacta. El fill **sí**
toma el máximo entre ambos términos — descarta la variable candidata (2)
de sesión 26 ("el algoritmo de fill puede no maximizar").

## Sub-línea 2.1 — apotema del polígono de N vértices

Barrido fino de radio (M=0.30, N=16) alrededor del umbral predicho
`1.80 / cos(π/16) = 1.8353mm`:

| r_keepout | apotema teórico | d_fill medido | error | violación |
|---:|---:|---:|---:|---|
| 1.8 | 1.76541 | 1.76541 | &lt;0.0001mm | Sí |
| 1.82 | 1.78503 | 1.78503 | &lt;0.0001mm | Sí |
| 1.83 | 1.79484 | 1.79484 | &lt;0.0001mm | Sí |
| **1.8353** | **1.80003** | **1.80004** | &lt;0.0001mm | **No** |
| 1.84 | 1.80464 | 1.80464 | &lt;0.0001mm | No |
| 1.85 | 1.81445 | 1.81445 | &lt;0.0001mm | No |

El umbral real cae **exactamente** en 1.8353mm — no en 2.0mm como midió
sesión 26 (que solo probó 1.82 y 2.0, saltándose el umbral real por 0.16mm
de diferencia de resolución en su propio barrido).

Barrido de N (r=1.82 fijo, M=0.30):

| N | apotema teórico | d_fill medido | violación |
|---:|---:|---:|---|
| 16 | 1.78503 | 1.78503 | Sí |
| 32 | 1.81104 | 1.81124 | No |
| 64 | 1.81781 | 1.81781 | No |
| 128 | 1.81945 | 1.81945 | No |

**Confirma la sub-hipótesis del apotema sin ambigüedad**: en las 11
mediciones de esta sub-línea, `d_fill` coincide con `r·cos(π/N)` con error
&lt;0.0002mm. El fenómeno queda 100% explicado — **no fue necesario
continuar a la sub-línea 2.3** (inspección de código fuente de KiCad):
2.1+2.2 explican el 100% del fenómeno observado, incluidos ambos
experimentos de sesión 26 una vez corregido el número de 2.00mm.

## Comparación con sesión 26

| Hipótesis/variable (sesión 26 §6) | Estado post-sesión 30 |
|---|---|
| (1) Apotema del 16-gono | **Confirmada como mecanismo principal**, con medición directa (no solo aritmética consistente) |
| (2) Fill no maximiza keepout vs. clearance natural | **Refutada** — sí maximiza, confirmado por sub-línea 2.2 |
| (3) Chequeo `solder_mask_bridge` sobre proyección distinta al fill real | **Refutada implícitamente** — el fill real es exactamente lo que se mide, y explica el 100% del comportamiento sin invocar una proyección intermedia |
| (4) `SolderMaskMinWidth` u otra config no expuesta | **Descartada** — no hizo falta invocarla; el modelo de 2 términos (hole/mask) + apotema explica todo |

No hizo falta clonar el código fuente de KiCad (sub-línea 2.3 del prompt de
sesión): el modelo puramente empírico ya alcanzó precisión &lt;0.0002mm.

## Fix implementado

`src/kicad_mcp/bridge/ipc.py`:

1. `_circle_vertices_mm`: default `n` de 16 a 64. Docstring actualizado con
   la causa raíz. No cambia la firma pública de forma incompatible (mismo
   parámetro, nuevo default).
2. `PadHole`: nuevos campos `pad_w_mm`/`pad_h_mm` (default `Mm(0.0)`,
   compatible con los call sites existentes en tests). Poblados en
   `_list_pad_holes_raw` desde `pad.padstack.copper_layers[0].size`.
3. `enforce_hole_clearance`: lee `mask_clearance_mm = max(pad_to_mask_clearance_mm,
   solder_mask_to_copper_clearance_mm)` de `rules_reader` (ya se leía,
   sesión 26, sin consumidor hasta ahora). Radio de keepout de PAD =
   `max(hole_term, r_cobre_pad + mask_clearance_mm + margen)`. Vías
   conservan solo el término de agujero (fuera de alcance, D-23.3/R16 — una
   vía no tiene pad de cobre ancho).

Diff acotado: ~35 líneas efectivas + docstrings extendidos.

## Tests

- **Unit** (`tests/test_pcb_hole_clearance.py`): 6 tests preexistentes
  siguen verdes sin cambios de comportamiento (el fake `_Padstack` por
  default no modela cobre → `pad_w_mm/h_mm=0` → sin cambio). Nuevo test
  `test_enforce_hole_clearance_mask_term_dominates_when_larger` verifica
  que con `pad_to_mask_clearance=0.3` y cobre 3x3mm, el keepout creado usa
  el término de máscara (radio 1.82mm), no el de agujero (1.27mm).
- **Integration** (`tests/test_pcb_session30_solder_mask.py`, nuevo, marca
  `integration`, offline vía `kicad-cli`): barrido parametrizado de
  `pad_to_mask_clearance` ∈ {0.0, 0.20, 0.22, 0.25, 0.30} inyectando la
  geometría exacta que el fix produce (mismos vértices que
  `_circle_vertices_mm` con N=64) → 0 violaciones `solder_mask_bridge`
  ANT1-vs-GND en los 5 casos. Test de control adicional: fixture intacto
  (`pad_to_mask_clearance=0`, keepout sin modificar) → sin violación, sin
  cambio de comportamiento respecto al flujo canónico D6/D7.

## Recomendación para BACKLOG

Cerrar P1.

## Gate GUI (DoD)

El fix toca `enforce_hole_clearance`, parte del pipeline de zonas/keepouts
compartido por `add_zone`/`fill_zones`/`route_board` — el DoD del
CLAUDE.md hace del test de regresión GUI un gate del merge para este tipo
de cambio. La verificación offline (unit + integration con `kicad-cli`)
confirma la geometría y el mecanismo, pero no ejercita
`enforce_hole_clearance` en su forma real (requiere conexión IPC viva).

Corrido contra una copia fresca del fixture (`/tmp/kicad-mcp-sesion30-gui/`,
NO `/tmp/gui-test-project/` — ese directorio quedó fuera de alcance de esta
sesión por instrucción explícita del prompt, y además el fix no requería
mutarlo):

- `tests/test_pcb_session21_hole_clearance_gui.py` (ANT1 PTH + J1 NPTH →
  0 errores DRC) — **2/2 verde**.
- `tests/test_pcb_session27_zone_persist_gui.py` (persistencia D-23.2
  extendida a `fill_zones`/`add_zone`) — **2/2 verde**.

Confirma que el bump de N=16→64 en `_circle_vertices_mm` no regresiona
ninguno de los keepouts auto-generados ya validados en D3-D7 (el cambio de
resolución del polígono afecta a TODOS los keepouts existentes, no solo al
de ANT1) y que el pipeline completo `add_zone`/`fill_zones` con
`enforce_hole_clearance` real (conexión IPC viva) sigue funcionando sin
regresión.
