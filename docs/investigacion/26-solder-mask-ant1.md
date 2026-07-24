# Investigación 26.1 (F-P1-solder-mask) — Solder mask bridge en ANT1

**Sesión 26**. Objetivo: verificar si el P1 vigente (pad de ANT1 hace
`solder_mask_bridge` con la zona GND) sigue siendo reproducible tras el dato
de D5 (sesión 25), y si es real, diseñar y verificar un fix.

**Resultado: hallazgo mixto.** El bug ES real y reproducible con evidencia
sólida (§1–§3). La hipótesis registrada en `docs/BACKLOG.md`/`25-reporte.md`
("el keepout de hole cubrió el caso de máscara por accidente geométrico") es
FALSA, refutada con un número (§1). Pero el fix diseñado en esta misma
sesión, siguiendo el criterio arquitectónico acordado (`AskUserQuestion`,
§4), **no resuelve el bug en el valor que su propia fórmula calcula** — la
verificación contra KiCad real (no solo aritmética propia) lo descubrió antes
de mergear (§5). La causa exacta del mecanismo de `solder_mask_bridge` de
KiCad **no se pudo aislar con confianza** dentro del timebox razonable de
esta sesión (§6) — mismo resultado de investigación 21 con el bug original
de `hole_clearance`, mismo protocolo de cierre: reportar el hallazgo
negativo/parcial y escalar al humano antes de mergear un workaround no
confirmado (`AskUserQuestion`, decisión: parar).

**Estado del código:** el fix de `enforce_hole_clearance` se implementó,
verificó como insuficiente, y se REVIRTIÓ antes de cerrar la sesión — no
está en el árbol de trabajo. La extensión de `rules_reader.py` (lectura de
`pad_to_mask_clearance` y `solder_mask_to_copper_clearance`) SÍ se conserva
— es correcta, testeada, e independiente de resolver el mecanismo; la
necesitará cualquier investigación futura sobre este tema.

---

## 1. Refutación de la hipótesis de D5 (geométrica, offline)

Medido directo sobre `tests/fixtures/despertador-routed/despertador_inteligente.kicad_pcb`:

| Radio | Valor | Origen |
|---|---:|---|
| Agujero ANT1 | 1.00 mm | `(drill 2)`, pad `1` de `TestPoint_Plated_Hole_D2.0mm` |
| **Keepout `__kicadmcp_hc__pad_ANT1_1`** | **1.27 mm** | 1.00 + 0.25 (`min_hole_clearance`) + 0.02 (`_HOLE_CLEARANCE_MARGIN_MM`); 16-gon x=163.73→166.27, área 4.94 mm² — coincide exacto con lo medido en D5 |
| Cobre del pad | 1.50 mm | `(size 3 3)` |
| Apertura de máscara (M=0, C=0 del proyecto) | 1.50 mm | 1.50 + `pad_to_mask_clearance`(=0) |
| Borde del fill GND (clearance ordinaria) | 2.00 mm | 1.50 + 0.5 (`zones.min_clearance` del proyecto) |

Orden: **1.27 < 1.50 = 1.50 < 2.00**. El keepout de ANT1 vive íntegramente
DENTRO del cobre del propio pad, y solo en `B.Cu`. Era geométricamente
incapaz de resolver nada de máscara — la hipótesis de D5/BACKLOG es falsa
para ANT1. (Para J1 el mecanismo sí opera: sus NPTH no tienen cobre de pad
propio, keepout r=0.7655mm es el único mecanismo de exclusión y sí funciona
— no confundir los dos casos.)

## 2. Reproducción en vivo del fill rancio (descartada como causa de D5)

Sobre `/tmp/gui-test-project` (board vivo, restaurado desde el fixture
post-D5, DRC 0/0 confirmado antes de empezar): se movió ANT1 a un punto
verificado libre de tracks/pads ajenos (166.5, 100.5), SIN refill
intermedio, y se guardó. `run_drc` mostró exactamente las 3 violaciones
co-localizadas (`solder_mask_bridge` + `clearance` + `hole_clearance`,
contraparte `Zone [GND] on B.Cu` en los tres casos) — la firma exacta del
baseline de D5. `fill_zones()` posterior las eliminó a las tres juntas. Esto
confirma que el patrón de D5 (zona rellenada ANTES de la colocación masiva
de footprints) es *plausible* como explicación del baseline histórico de D5
— pero, como se ve en §3, no descarta que exista TAMBIÉN un bug de máscara
genuino e independiente del fill rancio.

ANT1 fue restaurado a (165,93) al cierre de este experimento;
`fill_zones()` + `run_drc()` confirmaron 0 errores antes de continuar.

**Hallazgo transferible de proceso** (no depende de resolver el mecanismo
de máscara): `move_footprint` NO dispara refill de zonas (solo
`add_zone(fill=True)`, `fill_zones`, `route_board` con refill, y
`delete_tracks_bulk` lo hacen). Un baseline DRC leído inmediatamente después
de una colocación masiva sobre una zona ya rellenada mide fill rancio, no
el estado real. Recomendación para futuros dogfoodings: `fill_zones()`
obligatorio después de la colocación, antes de leer el baseline DRC.

## 3. Barrido de `pad_to_mask_clearance` — el bug independiente SÍ existe

Ruta 100% offline (justificación en §7): copias de
`tests/fixtures/despertador-routed` con `pad_to_mask_clearance` (campo del
`(setup ...)` del `.kicad_pcb`) variado, `kicad-cli pcb drc
--severity-error --format json`. Control (`M=0`, sin modificar) reprodujo
EXACTO el DRC del board vivo (0 violaciones) — la ruta offline es
equivalente.

| M (mm) | Violaciones totales del board | ANT1 directo vs `Zone[GND]` | `clearance`/`hole_clearance` co-localizada |
|---|---:|---|---|
| 0.0 (control) | 0 | — | — |
| 0.05 – 0.20 | 0 – 24 | no | — |
| **0.22** | 62 | **sí** | **no** |
| 0.25 | 114 | sí (determinístico, re-corrida idéntica) | no |
| 0.3 | 141 | sí | no |

El umbral está entre M=0.20 (no) y M=0.22 (sí). En TODO el rango, el 100%
de las violaciones son `solder_mask_bridge` — cero `clearance`/
`hole_clearance` en todo el board, confirmando que `pad_to_mask_clearance`
solo afecta geometría de máscara, no de cobre.

**Esto SÍ es un bug independiente, real, y alcanzable**: 0.22mm de
`pad_to_mask_clearance` no es un valor exótico — está dentro del rango que
algunos procesos de fabricación/ensamblado usan para relief de máscara. El
proyecto del fixture usa M=0 (default de KiCad), así que el despertador NO
está expuesto hoy — pero un proyecto real con relief de máscara mayor sí
lo estaría, y `enforce_hole_clearance` no lo defendería.

## 4. Decisión de diseño con el arquitecto

Con el bug confirmado real (contradiciendo la expectativa inicial de la
sesión, que era "cerrar sin fix" según el dato de D5), se consultó al
arquitecto vía `AskUserQuestion` sobre dos bifurcaciones:

1. **Cómo leer `pad_to_mask_clearance`** (vive en el `.kicad_pcb`, NO en el
   `.kicad_pro` que `rules_reader.py` ya parseaba — un archivo y formato
   distinto). Decisión: **extender `rules_reader.py`** con un segundo
   parser (regex puntual sobre el `.kicad_pcb`, no un parser S-expression
   completo) en vez de leer inline en el bridge — superficie reutilizable.
2. **Forma del fix**: el mecanismo de `enforce_hole_clearance` protege
   hoy por radio de AGUJERO, no de cobre de pad. Decisión: **un solo
   keepout por pad, radio = max(término de hole, término de máscara)** —
   término de máscara = radio de cobre del pad + max(`pad_to_mask_clearance`,
   `solder_mask_to_copper_clearance`) + el margen existente
   (`_HOLE_CLEARANCE_MARGIN_MM` = 0.02mm) — en vez de un segundo keepout
   dedicado.

## 5. Implementación y verificación — el fix NO resolvió el bug

Implementado exactamente según la decisión de §4:
`rules_reader.ProjectRules` ganó `pad_to_mask_clearance_mm` y
`solder_mask_to_copper_clearance_mm` (lectura dual-archivo, cache por el par
de `(mtime,size)` de ambos); `PadHole` ganó `pad_w_mm`/`pad_h_mm`;
`enforce_hole_clearance` calculó `radius_mm = max(hole_radius_mm,
mask_radius_mm)`. Unit tests (formula, extracción de reglas) verdes, `ruff`/
`mypy` limpios.

**Antes de dar el fix por bueno**, se verificó contra KiCad real (no solo
contra la aritmética propia) usando el mismo patrón offline de §3 más un
script que inyecta directamente el polígono del keepout que
`enforce_hole_clearance` generaría (ver `docs/investigacion/19-zonas-ipc.md`
§2.3 para el precedente de inyección quirúrgica sin `pcbnew` en un board
vacío — acá, igual que en `21-fill-zones-holes.md` §4.2, sobre una copia
real del fixture, nunca un board sintético vacío).

Con M=0.3 (radio de fórmula = 1.5 + 0.3 + 0.02 = **1.82mm**): la violación
`solder_mask_bridge` de ANT1 contra `Zone[GND]` **seguía presente,
idéntica en todo (mismo tipo, mismos ítems, mismo punto) a la corrida sin
el fix.** El fix, en el valor que su propia fórmula calcula, no tuvo efecto
observable.

## 6. Barrido de radio de keepout — el número real no se aisló

Manteniendo M=0.3 fijo, se barrió el radio del keepout inyectado
directamente (reemplazando el polígono de 16 vértices del keepout
`__kicadmcp_hc__pad_ANT1_1` en una copia), refill + DRC en cada paso:

| Radio de keepout (mm) | Violación ANT1-vs-`Zone[GND]` |
|---:|---|
| 1.82 (fórmula del fix) | presente |
| 2.0 | resuelta |
| 2.5 | resuelta |
| 3.0 | resuelta |
| 5.0 | resuelta |
| 8.0 | resuelta (única violación que cambia respecto del board sin tocar — las otras 2 violaciones de ANT1, contra pads de D1/R3 por proximidad de track, NO relacionadas con la zona GND, persisten sin cambio en todos los radios) |

El umbral real está entre 1.82mm (falla) y 2.0mm (resuelve) — un rango
angosto. **2.0mm no se deriva de ninguna combinación obvia de las reglas
del proyecto vía la fórmula usada** (aunque coincide numéricamente con
`cobre_pad(1.5) + zone.min_clearance(0.5)`, una cantidad DISTINTA a
`pad_to_mask_clearance` que la fórmula del fix usaba).

**Intento de explicación (apotema del polígono, NO confirmado del todo):**
`_circle_vertices_mm` genera un 16-gono con los VÉRTICES exactos al radio
pedido, pero el apotema (distancia del centro al punto medio de una arista)
es menor: `r_v · cos(π/16) ≈ r_v · 0.9808`. La apertura de máscara real
(círculo, radio 1.5+0.3=1.80mm) puede "asomar" por el punto medio de una
arista del keepout incluso si los vértices están más lejos que 1.80mm. Para
r_v=1.82: apotema=1.785mm < 1.80mm (asoma, consistente con "falla"). Para
r_v=2.0: apotema=1.962mm > 1.80mm (no asoma, consistente con "resuelve").
Este mecanismo es plausible y aritméticamente consistente con el barrido de
§6 — pero **NO reconcilia con el barrido de §3**: ahí, el keepout NO se
modificó (quedó en su valor STOCK de 1.27mm, con apotema≈1.245mm) y aun así
el bug NO apareció hasta M≈0.21 (apertura≈1.71mm) — muy por debajo de
1.245mm, es decir la violación debería haber aparecido desde M=0 bajo esta
misma teoría del apotema, y no lo hizo. Dos experimentos, dos umbrales que
no encajan bajo un único modelo simple.

**Conclusión honesta:** no se descarta que el apotema sea PARTE de la
explicación, pero hay al menos una segunda variable no identificada
(candidatas sin verificar: el algoritmo de fill puede NO tomar el máximo
entre el keepout explícito y la clearance natural del pad sino privilegiar
uno sobre otro según alguna condición no aislada; el chequeo de
`solder_mask_bridge` de KiCad puede no operar sobre el polígono de fill
real sino sobre alguna proyección intermedia distinta; puede haber una
`SolderMaskMinWidth` u otra configuración avanzada no expuesta en
`.kicad_pro`/`.kicad_pcb` estándar interviniendo). Aislarla requeriría
inspeccionar el código fuente de KiCad (`pcbnew`/`kicad-cli` no son
open-source-inspeccionables desde este entorno sin clonar el repo de
KiCad) o instrumentación adicional fuera del alcance razonable de esta
sesión.

## 7. Nota de infraestructura (para la próxima investigación)

- `kicad-cli pcb drc` (10.0.4) acepta `--refill-zones` y `--save-board` —
  motor de fill + DRC completo, 100% offline, sin `pcbnew`. Evita el
  segfault de `ZONE_FILLER.Fill()` sobre un `pcbnew.BOARD()` vacío
  documentado en `19-zonas-ipc.md` §2.3 (siempre que se use sobre una copia
  de un proyecto real, con netclasses/stackup — nunca un board sintético
  vacío).
- `pad_to_mask_clearance` NO se puede cambiar contra el board VIVO vía IPC
  sin reiniciar KiCad (KiCad solo lo lee al cargar el proyecto) — cualquier
  barrido de este parámetro tiene que ser offline, sobre copias.
- El python del venv del proyecto (cpython freethreaded) no puede importar
  `pcbnew`; solo `/usr/bin/python3` (confirmado, ya documentado en sesiones
  previas).
- El injection quirúrgico de un keepout (reemplazar el bloque `(pts ...)`
  de una zona por texto) es suficiente para experimentar con geometría de
  keepout sin pasar por IPC ni por `pcbnew` — más rápido que ambos para
  este tipo de barrido. Script usado (no versionado, vivió en el
  scratchpad de la sesión): localiza el bloque `(zone ...)` por el nombre
  de la zona, reemplaza su `(pts ...)` por un 16-gono nuevo.

## 8. Qué queda y qué no

**Se conserva** (mergeado con esta sesión): `rules_reader.py` extendido con
`pad_to_mask_clearance_mm`/`solder_mask_to_copper_clearance_mm` — lectura
correcta y testeada (`tests/test_rules_reader.py`), independiente de
resolver el mecanismo. Cualquier investigación futura sobre este tema la
va a necesitar.

**Se revirtió** (no está en el árbol de trabajo al cierre de la sesión): el
cambio de `enforce_hole_clearance`/`PadHole` en `ipc.py` — el radio
calculado por la fórmula acordada con el arquitecto no protege el caso que
debía proteger, y no hay evidencia suficiente para calibrar un radio
distinto con confianza dentro de esta sesión.

**Sigue abierto:** P1 (`docs/BACKLOG.md`), re-estimado de S/M a M/L —
requiere una sesión de investigación dedicada a aislar el mecanismo real de
`solder_mask_bridge` de KiCad (posiblemente con acceso al código fuente de
KiCad, o con más instrumentación) antes de poder diseñar un fix con
confianza.
