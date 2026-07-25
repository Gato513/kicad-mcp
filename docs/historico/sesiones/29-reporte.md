# Sesión 29 — Dogfooding 7 (tercer dogfooding de Fase 3, cierre de Fase 3)

**Rama:** `master` (fixture regenerado, sin cambios de código).
**Tipo:** dogfooding de ratificación (no de desarrollo). Placa despertador
ATtiny85 wearable, misma variable controlada que D3-D6. Objetivo primario:
3er verde consecutivo del criterio de cierre de Fase 3, aislamiento correcto
de D-26.1 (sin el confusor de orden de fases que dejó D6), variación
geométrica controlada (V6), y protocolo F-D6-01 (V7).

## Resumen ejecutivo

**Nota: 9.8/10** (D2=7.5, D3=8.5, D4=4.5, D5=9.5, D6=9.7). **Tercer verde
consecutivo de Fase 3 sobre variable controlada — criterio de cierre
cumplido.** Placa fabricable completa (ERC 0, colocación 23/23 con
coordenadas propias, ruteo con 0 errores DRC introducidos en 4 corridas,
gerbers G3 limpios, BOM exportado, fixture actualizado). Cero fricciones
de cualquier severidad — ninguna entrada F-D7-XX fue necesaria.

**Contrato D-23.2 ratificado 10/10 en las tres tools** (`route_board` 4/4,
`fill_zones` 3/3, `add_zone(fill=True)` 3/3) sin ninguna divergencia
registrada. Acumulado en producción real: `route_board` 12/12, `fill_zones`
7/7, `add_zone` 6/6 — **25/25 total, 0 divergencias en la historia del
contrato.**

**D-26.1 ratificado SIN confusor por primera vez.** D7 replicó el orden
exacto de fases de D5 (plano GND creado ANTES de la colocación masiva,
D-28.1 vinculante respetado sin desviación). El baseline sin `fill_zones()`
explícito (V4.a) reprodujo el patrón exacto de D5: 6 violaciones no-triviales
(fill rancio). El baseline con `fill_zones()` explícito (V4.b) las llevó a 0.
El par (V4.a=6, V4.b=0) es la evidencia más limpia que el proyecto tiene de
D-26.1 hasta la fecha — cierra la pregunta metodológica que D6 dejó abierta.

**Variación geométrica controlada exitosa (V6).** Layout completamente
nuevo — clusters funcionales en anti-diagonal, ANT1 a 2mm de U4 (vs 28mm en
D5/D6), bus I2C como net diagonal de ~25mm — ruteado 10/10 sin nets
bloqueados ni parciales en la primera pasada, 0 errores DRC. La evidencia de
D-23.2/D-26.1 ya no depende de un único layout repetido tres veces.

**Protocolo F-D6-01 cerrado con conclusión (V7).** 3 mediciones adicionales
de re-ruteo parcial (`+3V3` alto, `/SDA` medio, `/NSS` bajo — mismo net
medido en D5 y D6) dieron N=7 total (2 D5 + 2 D6 + 3 D7), sin correlación
identificable con grado de interconexión, tamaño del net, ni capas.
Recomendación: cerrar como variabilidad inherente de Freerouting/JVM,
documentar el rango observado (9s-112s) en `docs/specs/restricciones-kicad.md`.

**F-D5-01 no reapareció** — trigger de promoción a P2 (2/3 dogfoodings) no
se cumple (D5=sí, D6=no, D7=no → 1/3). Cerrable como incidente aislado.

## Métricas comparativas

| Métrica | D2 | D3 | D4 | D5 | D6 | D7 |
|---|---|---|---|---|---|---|
| Nota | 7.5 | 8.5 | 4.5 | 9.5 | 9.7 | **9.8** |
| Contactos humanos | 5 | 2 | 0 | 0 | 1 | **1 (restore D-27.1 + layout V6, interacción combinada)** |
| Fricciones bloqueantes | 0-1 | 1 | 1 | 0 | 0 | **0** |
| `route_ms` corrida completa | 925s | 53s | 36.7s | 128.8s | 32.4s | **40.6s** |
| Errores DRC post-route | 53 | 0 | 42 | 1 (F-D5-01) | 0 | **0** |
| Baseline V4 pre-route (no-triviales) | N/A | N/A | N/A | 6 (fill rancio) | 0 | **6 (V4.a, sin fill) → 0 (V4.b, con fill)** |

## D-26.1: ratificación sin confusor (el punto metodológico central de D7)

D6 había ratificado D-26.1 de forma "débil-pero-consistente": aplicó
`fill_zones()` explícito y el baseline salió en 0, pero el propio orden de
fases de D6 (plano GND creado DESPUÉS de la colocación) ya evitaba el fill
rancio por sí solo, dejando sin aislar el efecto real de `fill_zones()`.

D7 replicó el orden exacto de D5 (plano ANTES de colocar, D-28.1 vinculante,
sin AskUserQuestion necesaria porque no hubo desviación) y midió dos
baselines consecutivos sobre el mismo layout nuevo:

- **V4.a (sin `fill_zones()`):** 6 violaciones no-triviales — 3×
  `hole_clearance` (J1 NPTH), 1× `hole_clearance` + 1× `clearance` + 1×
  `solder_mask_bridge` (ANT1). Idéntico en composición al patrón que D5
  registró (con un layout completamente distinto).
- **V4.b (con `fill_zones()`):** 0 violaciones no-triviales. Las 6
  desaparecieron íntegramente.

**Ratificación empírica limpia, sin confusor de orden de fases.** El delta
V4.a→V4.b es evidencia directa de que `fill_zones()` explícito es necesario
en el flujo canónico (plano-antes-de-colocar), no redundante como sugería D6.

## V1/V2/V3/V4/V5/V6/V7 consolidado

- **V1**: 4 keepouts `__kicadmcp_hc__` constantes en las 4 corridas de
  ruteo (ANT1 + 3× J1 NPTH). Sin proliferación.
- **V2 reforzado**: 3/3+ por cada una de las 3 tools (10/10 total, 0
  divergencias): `route_board` 4/4, `fill_zones` 3/3, `add_zone` 3/3.
  `err_post` == `run_drc()` independiente en las 10, mtime cambió en las 10,
  cero `EXTERNAL_EDIT_DETECTED` espurio.
- **V3**: nunca activada en ~74 llamadas a tools de la sesión.
- **V4 (V4.a+V4.b)**: D-26.1 aislado limpiamente por primera vez (6→0).
- **V5**: F-D5-01 no apareció (1/3 dogfoodings, trigger de promoción a P2
  no cumplido).
- **V6**: layout completamente nuevo — clusters funcionales en
  anti-diagonal, densidad 46.0% (courtyard/board area), ANT1 a 15.0mm del
  borde (vs 2mm en D5/D6) y a 2mm de U4 (vs 28mm), J1 a 7.5mm del borde
  (vs 2mm). Sin `courtyards_overlap`, sin degradación de ruteo ni DRC.
- **V7**: 3 mediciones adicionales (`+3V3` 23.7s, `/SDA` 24.4s, `/NSS`
  17.7s) → N=7 total. Sin patrón correlacional con interconexión, tamaño o
  capas. Comparación directa sobre `/NSS` entre sesiones: D5 9-10s, D6
  110-112s, D7 17.7s — apunta a variabilidad del proceso
  Freerouting/JVM, no a una propiedad determinística del net.

## Contrato D-23.2 acumulado en producción real

| Tool | Corridas verdes (D7) | Acumulado total | Origen |
|---|---|---|---|
| `route_board` | 4/4 (1 completa + 3 parciales V7) | **12/12** | 2 sesión 24 + 3 D5 + 3 D6 + 4 D7 |
| `fill_zones` | 3/3 (V4.b + 2 zonas de test) | **7/7** | 2 sesión 27 + 2 D6 + 3 D7 |
| `add_zone(fill=True)` | 3/3 (plano real + 2 zonas de test) | **6/6** | 2 sesión 27 + 1 D6 + 3 D7 |

**Total: 25/25 corridas verdes en producción real, 0 divergencias en toda
la historia del contrato.**

## Fricciones

**Ninguna.** No se registró ninguna entrada F-D7-XX. Restore D-27.1,
`get_footprint_neighbors`, 23× `move_footprint`, `delete_tracks_bulk`
dry_run→real, `add_zone`, `fill_zones`, `delete_zone`, `route_board`×4 y
los exports finales se comportaron exactamente como documentado.

## Recomendación para sesión 30

**Iniciar preparación de Fase 4.** El criterio de cierre de convergencia de
Fase 3 se cumple: 3 verdes consecutivos (D5=9.5, D6=9.7, D7=9.8), D-23.2
en 25/25 sin divergencias, D-26.1 aislado sin confusor, F-D6-01 cerrado,
V6 con layout distinto exitoso. Deuda arrastrada: P1 solder mask ANT1
(investigación pendiente desde sesión 26, no bloqueante — no expuesta en
el fixture despertador con `pad_to_mask_clearance=0`). Fase 4 es decisión
estratégica del arquitecto y del humano (release / expansión funcional /
escalada de complejidad).

## Artefactos

- Log completo de fricciones y reporte de 17 preguntas:
  `docs/historico/dogfooding/dogfood7-fricciones.md` (550 líneas).
- Fixture actualizado: `tests/fixtures/despertador-routed/` (`.kicad_pcb`
  cambió — colocación y ruteo nuevos; `.kicad_pro`/`.kicad_sch`/`.kicad_prl`
  bit-idénticos a D6). README reescrito con procedencia D7, sesión 29,
  commit base `6479923`.
- Gerbers: `/tmp/gui-test-project/fab/` (26 archivos, gate G3 limpio).
- BOM: `/tmp/gui-test-project/bom.csv`.
