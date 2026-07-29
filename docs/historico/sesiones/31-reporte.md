# Sesión 31 — Validation Suite Nivel A-01 (ANAVI Dev Mic)

**Rama:** `sesion/31-validation-A-anavi-light-controller` (nombre heredado
del prompt; el candidato final es ANAVI Dev Mic tras sustitución
documentada en Bloque 0).
**Tipo:** primera validación externa del flujo canónico + arranque de la
Validation Suite (Fase 4, D-30.1 a D-30.5). Rol dual: valida Y establece
el template metodológico de sesiones 32-33.

## Resumen ejecutivo

**Escenario de éxito: 4 de 7 — "Aprendizaje por P0/P1".** No es fracaso:
es exactamente el tipo de resultado que D-30.2 (éxito por confianza, no
por código) valida como legítimo, con precedente directo en sesiones 23,
26 y 30. El flujo canónico se detuvo en `route_board` por un hallazgo P0
nuevo (`F-V1-02`), descubierto y diagnosticado con causa raíz aislada
mediante experimento controlado — no una sospecha, un hecho verificado.

**Link al reporte completo:**
`validation-suite/level-a/anavi-dev-mic/validation-report.md`.

### Qué pasó

1. **Candidato original descartado en Bloque 0.** `anavi-light-controller`
   (prescrito por el prompt) resultó ser KiCad 4 (2018), esquemático
   legacy, sin commits desde 2018 — falla criterio de admisión 2
   literalmente. Se evaluaron 6 candidatos del catálogo ANAVI antes de
   converger en `anavi-dev-mic` (fabricación confirmada por el propio
   README del repo: "successfully funded... Crowd Supply, Sept 26,
   2024" + foto del hardware ensamblado). Admitido con una excepción
   documentada y aprobada por el arquitecto: el ground truth NO tiene
   DRC 0/0 (18 errores preexistentes al layout del autor, mismo tipo de
   defecto — `solder_mask_bridge` — que investigamos internamente en
   D-30.5/sesión 30).
2. **Bloque 0/1 completos sin fricciones nuevas de severidad alta.**
   Tooling reutilizable construido y verificado (`measure_ground_truth.py`,
   `prepare_working.py`), con dos hallazgos de entorno documentados en el
   camino (bug de `GetBoardEdgesBoundingBox()` en el script propio, corregido;
   segfault de pcbnew al combinar remoción+movimiento en el mismo proceso,
   mitigado con subprocesos separados — ambos documentados en los
   docstrings de las tools para que sesión 32 no tenga que redescubrirlos).
3. **Bloque 2 avanzó bien hasta el ruteo.** Colocación asistida (10
   `move_footprint`, sin colisiones), plano GND, refill — DRC bajó de 507
   (baseline, todo apilado en el origen) a 89 violaciones (post-colocación
   + zona). Buena señal de que el flujo funciona sobre un board externo.
4. **`route_board` falló en el paso de exportación DSN.** Causa raíz
   aislada con experimento controlado: 4 mounting holes del diseño
   comparten el reference designator literal `REF**` (nunca anotados por
   el autor). `pcbnew.ExportSpecctraDSN()` falla enteramente con refs
   duplicados en el board, sin importar su posición — confirmado quitando
   3 de las 4 instancias en una copia de prueba (la exportación pasó de
   fallar a generar 2.4MB de DSN válido).
5. **Decisión del arquitecto (vía `AskUserQuestion`): cerrar la sesión
   con el hallazgo documentado, no forzar con una intervención manual
   fuera del flujo canónico.** El catálogo MCP no tiene tool
   `delete_footprint` — asimetría ya conocida (`docs/BACKLOG.md`, P2
   histórico), ahora escalada a P0 con evidencia concreta de que bloquea
   `route_board` por completo, no sólo ensucia el DRC.

### Fricciones nuevas

- **F-V1-01 (P1):** `board_bbox_mm` no implementa su propia preferencia
  documentada (leer Edge.Cuts); usa siempre el fallback de enjambre de
  footprints ±100mm. Bloqueaba mover footprints al contorno real cuando
  todos parten apilados en `(0,0)` — la convención de estado inicial que
  esta misma sesión adoptó para `working/`. Resuelto con workaround
  dentro del flujo (un movimiento bootstrap). Fix propuesto: ~10 líneas.
- **F-V1-02 (P0):** ver arriba. Bloquea `route_board` con refs de
  footprint duplicados/sin anotar. Fix propuesto: tool `delete_footprint`
  direccionable por `kiid`.

Ambas en `docs/BACKLOG.md`.

### Interpretación Fase 4

Ambos hallazgos son **gaps legítimos del flujo sobre decisiones de diseño
no ejercitadas antes** (interpretación explícita de Fase 4: un P0 en
validación externa NO se sospecha regresión por default). El despertador
—única placa usada en Fase 1-3— siempre tuvo refs completamente anotados
y footprints con posiciones distintas al origen desde el import de
netlist; ninguna de las dos condiciones que expusieron estos bugs se
había dado antes. Esto es exactamente el valor que la Validation Suite
existe para producir.

## Análisis H2 (umbrales D-30.3)

Evidencia **parcial**: el procedimiento de medición
(`measure_ground_truth.py`) fue calculable sin ambigüedad sobre un board
real no trivial (13 fp, 20 nets, 2 capas, `union ≤ aditivo` verificado, 0
`method_notes`). Es señal a favor de la mitad "calculabilidad" de H2. Sin
output de ruteo, no hay evidencia sobre discriminancia de los umbrales
±30/±20/±25%. Sesión 31 no cierra este análisis — queda como el primer
punto (parcial) de tres.

## Actualizaciones documentales

- `docs/BACKLOG.md`: `F-V1-01` (P1) y `F-V1-02` (P0, con fix propuesto).
- `docs/CONTEXT.md`: estado post-sesión 31 (ver diff en el commit).
- `validation-suite/`: primera creación completa (estructura, 2 scripts
  reutilizables, `coverage-matrix.md`, proyecto `anavi-dev-mic` con
  ground truth medido y admitido).

## Próxima sesión

**No es sesión 32.** Se agenda una sesión de fix intermedia: agregar
`delete_footprint(ref, kiid=None)` (fix de `F-V1-02`) + fix de
`board_bbox_mm` (`F-V1-01`, agrupable en la misma sesión). Tras el fix,
reintentar sesión 31 sobre el `working/` de ANAVI Dev Mic ya preparado
(Bloque 0/1 reutilizables íntegros) para completar Bloque 2/3/4. Sesión
32 (Nivel B) arranca sólo cuando sesión 31 cierre con conclusión clara.
