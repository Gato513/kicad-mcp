# Hoja de ruta v4 — kicad-mcp (post-sesión 24, 2026-07-23)

**Evidencia base:** `CONTEXT.md` v7 + `docs/investigacion/23-fd4-02.md` +
`docs/adr/0012-route-board-persist-contract.md` + reportes de sesiones 20-24.
**Cambio de fase respecto a v3:** el proyecto salió de Fase 2 (descubrimiento
acelerado, v3 la coordinaba) y entró a **Fase 3 (consolidación / aumento
progresivo de confianza).**
**Meta v4:** cerrar Fase 3 con estabilidad estadística demostrada y P0/P1
resueltos, para habilitar Fase 4 (release / expansión).

**Documentos hermanos:**
- `docs/CONTEXT.md` — visión consolidada del sistema para arquitecto externo
  (síntesis, no cronología); `docs/historico/CONTEXT-v7.md` — fuente
  original sesión-por-sesión de la que se consolidó.
- `docs/BACKLOG.md` — backlog priorizado vigente (reemplaza a la sección
  "Backlog priorizado v7" de CONTEXT.md v7, que no se replicó tal cual en
  el CONTEXT.md consolidado).
- `docs/historico/roadmaps/hoja-de-ruta-v3.md` — hoja anterior, archivada por
  trazabilidad. Sus objetivos (P1-P5, sesiones 16-20) se cumplieron con
  variaciones y hallazgos que la evidencia forzó.

---

## Qué respondió la evidencia a la hoja de ruta v3

La v3 era post-D2, meta D3≥8. La secuencia real fue:

| v3 planeaba | Realidad |
|---|---|
| Sesión 16: P1 (get_tracks, delete por ID) | Ejecutada, cerrada. |
| Sesión 17: P2 (route_board contrato + reglas DSN) | Ejecutada. `route_board` con contrato JSON D-V3.4 (matices D-D3.2 v6/D-17.1 v6 aparecidos después). |
| Sesión 18: P3 (revert programático) | `Board.revert()` funciona nativo (D-V3.1). Revuelta cerrada. |
| Sesión 19: P4 (zonas mínimas) + P5 menores | Ejecutada. Plano GND + keepouts + `add_zone`/`fill_zones`/`add_keepout_zone`. Descubrió complicaciones que v3 no anticipaba (D-19.1 v6: Freerouting no respeta plano como exclusión). |
| Sesión 20: D3 nota ≥8 | **D3 = 8.5.** Meta alcanzada. |

Post-D3 la hoja v3 quedó agotada operacionalmente. Fase 2 continuó
con sesiones 21-24 (fix P0 F-D3-03, mitigación F-D3-01, D4 con V3
activada, investigación sesión 23, fix sesión 24 Opción X mergeada
972fa80). `docs/historico/CONTEXT-v7.md` tiene la crónica completa.

---

## Estado técnico tras D5 (sesión 25)

**Cerrado con evidencia:**
- Loop de escritura PCB completo (P1 v3).
- `route_board` con contrato JSON D-V3.4 + D-23.2 reforzado (ADR-0012).
  Post-sesión 24: disco == memoria == `err_post` reportado al terminar OK.
- Test de regresión GUI para D-23.2 (gate del merge, 2/2 corridas en vivo
  contra Freerouting real).
- **Contrato D-23.2 ratificado en producción real, 5/5 corridas sin
  excepción** (2/2 test de regresión sesión 24 + 3/3 D5, sesión 25 — `err_post`
  == `run_drc()` independiente, mtime cambia post-save, cero
  `EXTERNAL_EDIT_DETECTED` espurio). El workaround manual de refill que el
  fixture de D3 documentaba como obligatorio quedó obsoleto. **Alcance:
  `route_board` solamente** — `fill_zones`/`add_zone(fill=True)` no
  generalizados todavía (paso 3, sesión 27).
- Zonas y keepouts operativos.
- Revert humano eliminado (D-V3.1).
- Freerouting operativo con reglas DSN (D-V3.5) y edge clearance
  (ingeniería inversa documentada).
- Regeneración de sch mecanizada donde aplicable (sesión 19b).
- D-D4.1 (`get_footprint_neighbors` inclusivo) y D-19c.1 (keepout
  POST-route inocuo) re-ratificados con impacto real en D5.

**Deuda técnica conocida y priorizada:**
- P1: solder mask bridge en ANT1 (pad no protegido por hole keepout,
  aparecido en D4 como colateral del fix sesión 21). **Sesión 26 —
  verificar primero el hallazgo de D5**: en la corrida de D5 el
  `solder_mask_bridge` de ANT1 desapareció junto con el `hole_clearance`
  al aplicarse el keepout auto-generado — puede que el alcance del fix sea
  menor de lo previsto. Ver `docs/BACKLOG.md` P1.
- P2 top: generalización D-23.2 a `fill_zones` y `add_zone(fill=True)`
  (mismo patrón conceptual, mismo bug latente). **Condición de entrada
  cumplida** — D5 ratificó el patrón en `route_board` (sesión 27).
- P3: F-D5-01 (isla GND sin vía al plano, sesión 25) — vigilancia, sin
  acción hasta 2 dogfoodings independientes que reproduzcan el patrón.
- P3-P4: R12 (CRUD de sch), R13 (`get_world_context(kind="sch")` con
  `#PWR*/#FLG*`), R16 (loop de vías de `enforce_hole_clearance`
  posiblemente código muerto), y varios menores. Ver `docs/BACKLOG.md`.

**Deuda física del proyecto físico (fuera de scope kicad-mcp):**
- ICSP en circuito perdido.
- VLED+ flotante → MAX30102 no medirá SpO₂.
- INT eliminado; firmware pollea.

Esta deuda no afecta al software del server ni a los dogfoodings — la
placa despertador se usa como variable controlada del test, no como
producto fabricable. La corrección eléctrica del proyecto físico queda
para una decisión aparte del humano.

---

## Ruta estratégica v4 (Fase 3)

**Objetivo:** consolidar la superficie estable con evidencia estadística.
NO expandir capabilities. NO escalar complejidad prematuramente.

**Secuencia estricta:**

| Sesión | Contenido | Gate de salida | Estado |
|---|---|---|---|
| 25 | **Dogfooding 5** con baseline dinámico + V1/V2/V3 reforzadas | Nota ≥9, V2 3/3 con mtime cambio y sin `EXTERNAL_EDIT_DETECTED` espurio, delta V4 sin violaciones nuevas | ✅ **Completada — 9.5/10.** Gate cumplido sin excepción: V2 3/3 limpio, delta V4 = 1 hallazgo menor resuelto misma sesión (F-D5-01). Ver `docs/historico/sesiones/25-reporte.md`. |
| 26 | Fix P1 solder mask bridge ANT1 + test de regresión | Test verde, sin regresiones en tests existentes | ⏭️ **Siguiente.** Verificar primero si el hallazgo de D5 (solder_mask_bridge de ANT1 resuelto por el keepout de hole existente) cambia el alcance del fix — ver `docs/BACKLOG.md` P1. |
| 27 | Generalización D-23.2 a `fill_zones` + `add_zone(fill=True)` + tests | Tests de regresión análogos al de sesión 24, verdes | Pendiente — condición de entrada (D5 verde) ya cumplida. |
| 28 | **Dogfooding 6** con misma placa despertador | Nota ≥9, ratifica sesiones 26+27, sin P0/P1 nuevos | Pendiente. |
| 29+ | Iterar hasta convergencia si D6 abre pendientes | — | Pendiente. |

**Criterio de cierre de Fase 3 (habilita Fase 4):**
- ≥2-3 dogfoodings consecutivos verdes (nota ≥9) sobre misma placa.
- P1 (solder mask ANT1) resuelto y ratificado.
- Generalización D-23.2 completada y ratificada.
- Sin P0 nuevos en la superficie ratificada.
- Estabilidad sostenida.

**Escalada de complejidad (Fase 4):** SOLO tras cierre de Fase 3.
Escenarios candidatos: placas con >30 footprints, múltiples planos, capas
adicionales, placas RF más exigentes. NO ejercitar antes.

---

## Interpretación de resultados en Fase 3

Cambio de disposición respecto a Fase 2 (v3 no lo articulaba):

- **Verde (nota ≥9, 0 P0/P1 nuevos, V3 no activada):** evidencia positiva
  de convergencia. Avanzar al siguiente paso de la secuencia. No forzar
  hallazgos: la ausencia de fricciones es resultado, no fracaso.
- **Amarillo (nota 8-8.9, 1-2 P1):** ciclo continúa. Sesión de fix
  quirúrgico + próximo dogfooding sobre la MISMA placa antes de avanzar
  en la secuencia.
- **Rojo (V3 activada, P0 nuevo, nota <8):** señal fuerte. **Sospechar
  regresión del último fix mergeado hasta que se pruebe lo contrario.**
  Esto es distinto de Fase 2, donde un P0 nuevo se sospechaba gap.
  Investigación mandatoria antes de continuar.

---

## Backlog v4 (resumen)

Detalle priorizado vigente en `docs/BACKLOG.md`. Resumen:

- **P0:** vacío tras D5. F-D4-02 cerrado y ratificado 5/5. Reabrir solo si
  un dogfooding futuro lo fuerza.
- **P1:** solder mask bridge ANT1 (sesión 26 — verificar primero el
  hallazgo de D5 sobre alcance real del fix).
- **P2 top:** generalización D-23.2 a `fill_zones` + `add_zone(fill=True)`
  (sesión 27, condición de entrada cumplida — D5 salió verde).
- **P2 polish (post-Fase 3):** ADRs de decisiones aún no formalizadas,
  docs para colaboradores, test canario Freerouting, issue upstream sobre
  R9, licencia + README + CONTRIBUTING, limpieza código muerto, política
  de locking del bridge.
- **P3:** CRUD de sch (R12), R13 `#PWR*/#FLG*`, F-03 (`run_erc` posiciones
  ÷100), `get_pin_net_membership`, `delete_track` cosmético, A* de
  bloqueador concreto, `route_ms` en ruta de fallo, convención
  `__kicadmcp_hc__*`, default `max_tokens` de `get_footprint_neighbors`,
  discrepancia 23 vs 24 footprints, investigación R16 (loop de vías),
  F-D5-01 (isla GND sin vía al plano, vigilancia — sesión 25).
- **P4 (para Fase 4):** rotación en `move_footprint`, timeout adaptativo,
  limpieza tracks huérfanos, guard cross-proceso, `add_zone` con hueco
  interior, Opción Y de F-D4-02 descartada por ahora.

---

## Qué NO se prioriza en Fase 3

Deliberadamente diferido para no contaminar la variable controlada:

- **Nuevas capabilities** (features nuevos, tools nuevas).
- **Escalada de complejidad** de dogfoodings (placas más grandes,
  escenarios distintos al despertador).
- **Release** (licencia, docs de colaboradores, distribución).
- **Investigaciones no bloqueantes** (R16 loop de vías, etc.).

Estos elementos son legítimos y necesarios para Fase 4. Adelantarlos a
Fase 3 tiene costo alto y sin retorno: aumentaría el riesgo de que un
P0 nuevo en un dogfooding tenga múltiples causas plausibles, complicando
el diagnóstico.

---

## Relación con documentos hermanos

- **`docs/historico/CONTEXT-v7.md`:** estado vivo, sesión-por-sesión,
  decisiones vigentes, congelado post-sesión 24. Es lo que se destila y pasa
  a un nuevo chat de arquitecto. Su síntesis para lectura sin cronología
  vive en `docs/CONTEXT.md`.
- **CLAUDE.md:** superficie estable del repo (comandos, fronteras, reglas
  de código, errores de dominio, DoD). Cambia poco entre sesiones.
- **docs/adr/0012-route-board-persist-contract.md:** ADR del contrato
  D-23.2. Obligatorio de leer antes de tocar `route_board`, `fill_zones`
  o `add_zone`.
- **docs/investigacion/23-fd4-02.md:** investigación P4.0-style que
  identificó la causa raíz de F-D4-02. Obligatorio de leer antes de
  re-hipotetizar sobre bugs de reporte/persistencia en pipelines
  similares.
- **PROMPT-SESION-XX.md:** prompts operacionales generados por el
  arquitecto para cada sesión. Se descartan una vez la sesión cierra
  (no se preservan como documentación).

---

## Cierre esperado de Fase 3

Cuando 2-3 dogfoodings consecutivos salgan verdes con la placa despertador
+ P1 solder mask ANT1 resuelto + generalización D-23.2 completada, se
convoca decisión estratégica del humano:

1. **Avanzar a Fase 4** (release / expansión funcional / escalada de
   complejidad). Se cierra hoja v4, se abre v5.
2. **Continuar consolidación** con criterios extendidos si aparecen
   deudas nuevas durante el ciclo.

La decisión no es del arquitecto solo — es del proyecto. Fase 4 implica
compromisos que hoy no queremos asumir (soporte a usuarios externos,
compatibilidad con más versiones de KiCad, docs de contribución). Fase 3
mantiene el foco en calidad interna sin esas cargas.
