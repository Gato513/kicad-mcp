# Sesión 19c — Investigación de bloqueantes pre-Dogfooding 3

**Tipo:** Sesión de INVESTIGACIÓN sobre kicad-mcp, **nueva rama** `sesion/19c-bloqueantes-pre-d3` desde `master` (tras merge de `sesion/19-zonas`).

**Origen:** El reporte de la sesión 19 dejó tres incertidumbres que comprometen la viabilidad del Dogfooding 3:

1. **P4.5 no convergió** — dos corridas de `route_board` sobre el despertador con plano GND + keepout no convergieron (2h38m + 25min).
2. **Hipótesis alternativa no descartada** — el reporte concluye "Freerouting escala mal con planos densos", pero no probó la alternativa: el keepout circular de 12 vértices no es respetado y Freerouting queda en loop.
3. **Bug `add_via` con net cruzado no investigado** — el test devolvió una vía con `net.name="/MOSI"` cuando pedía `"+3V3"`. Riesgo silencioso alto para el D3.

**Objetivo estratégico:** decisión vinculante **GO / NO-GO / CONDICIONAL** sobre el Dogfooding 3 con las tools actuales.

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4 exclusivamente.

**Esta sesión NO implementa features nuevas.** Es investigación pura + posiblemente 1-2 fixes puntuales si un bug tiene fix trivial y bloqueante. Cualquier fix mayor queda documentado para 19d/20b.

**Timeboxing duro:** cada bloque tiene timeout máximo declarado. Si un bloque agota el timeout sin resultado concluyente, se DOCUMENTA y se CONTINÚA con el siguiente. NO acumular tiempo pidiendo "5 min más" — antipatrón que hizo perder 2h38m en la sesión 19.

---

## Bloque 1 — Bug `add_via` con net cruzado (timeout: 30 min)

**Prioridad máxima.** Bloqueante más peligroso: si degrada silenciosamente tras `revert()`, el D3 puede corromper nets sin señal.

### Preparación
1. **Reiniciar KiCad completamente.** Cerrar la instancia actual, abrir una nueva limpia con el proyecto de prueba.
2. Confirmar con `health()` estado limpio.

### Investigación
1. **Baseline sin `revert()`:** correr `test_add_via_round_trip_against_open_board` inmediatamente tras reiniciar KiCad.
   - Falla igual → NO es caché stale, es bug real de código o kipy.
   - Pasa → probablemente caché stale.

2. **Si pasó el baseline:**
   - Ciclo `route_board` → `revert()` × 5 (simular condición del D3).
   - Volver a correr el test. ¿Falla ahora?
   - Falla → caché stale confirmado. Identificar dónde vive el caché.

3. **Investigar código de `add_via` en `tools/pcb.py` y `bridge/ipc.py`:**
   - ¿Net se resuelve por nombre → net_code cada llamada, o se cachea?
   - ¿Resolución usa estado vivo o snapshot?
   - ¿Hay lookup name→code que puede quedar stale?

### Criterios de salida
- **Bug real de código:** identificar causa raíz. Fix < 20 líneas → aplicar con test de regresión. Mayor → documentar y agendar.
- **Caché stale de kipy:** mitigación obligatoria — invalidación explícita del handle tras `revert()` o forzar re-fetch. Si no factible → documentar workaround para D3.
- **No reproducible tras reinicio:** intermitente, riesgo medio. Recomendar reinicio de KiCad cada N horas.

**Decisión Bloque 1:** ¿es seguro hacer 20+ mutaciones consecutivas en el D3? Sí / No / Sí con workaround.

---

## Bloque 2 — Hipótesis del keepout como causa del no-convergence (timeout: 45 min)

### Investigación
1. **Reiniciar KiCad limpio.**
2. Reproducir P4.5 **SIN el keepout**:
   - Copiar fixture `despertador-routed` al proyecto vivo.
   - `add_zone(net="GND", layer="B.Cu", bbox=<board_bbox>)` → plano GND.
   - `fill_zones()`.
   - Borrar todos los tracks de GND.
   - `route_board(timeout_s=1500)`.
3. Registrar: converge o no, cuánto tiempo, resultado.

### Interpretación
- **Converge (< 1500s):** el keepout ERA el problema. Freerouting escala bien con plano solo.
- **No converge:** el keepout NO era el problema principal. Escalabilidad genuina de Freerouting con re-ruteo parcial + plano. Ir a Bloque 3.

### Si converge — investigación complementaria (dentro del timeout)
- Repetir con keepout de 12 vértices — ¿converge?
- Repetir con keepout de 6 vértices — ¿converge?
- Repetir con keepout como bbox rectangular — ¿converge?

Objetivo: identificar qué del keepout rompe. Puede ser número de vértices, geometría poligonal, o interacción con plano circundante.

---

## Bloque 3 — Escenario D3 canónico: ruteo desde cero con plano preexistente (timeout: 45 min)

**El bloque clave.** El D3 NO va a hacer "re-ruteo parcial" — ese fue el escenario artificial de P4.5. El D3 va a rutear desde cero con plano GND ya presente.

### Investigación
1. **Reiniciar KiCad limpio.**
2. Partir del despertador **SIN cobre**:
   - Restaurar desde `.kicad_pcb` pre-ruteo de sesión 17, o generar con `delete_track`/`delete_via` en loop sobre fixture ruteado.
   - Verificar: 0 tracks, 0 vías, 24 footprints, outline correcto.
3. Agregar plano GND en B.Cu (bbox del board).
4. `fill_zones()`.
5. `route_board(timeout_s=1500)`.
6. Registrar métricas completas: `route_ms`, nets ruteadas, `tracks_added`, `vias_added`, DRC pre/post, `reloaded`.

### Comparación con benchmark de sesión 18
Los 235-925s de sesión 18 fueron ruteo desde cero SIN plano. Ahora medimos ruteo desde cero CON plano. Predicción:
- Menos tiempo (plano absorbe conexiones GND).
- Menos vías totales.
- Similar tasa de convergencia.

### Si converge
- Comparar métricas con/sin plano.
- Si vías bajaron y DRC mejoró: **el gate cualitativo original de P4.5 se cumple**, aunque por vía distinta.
- Actualizar el test E2E de P4.5 para usar "desde cero con plano" — refleja uso real.

### Si no converge
- Freerouting tiene problema estructural con planos densos. **Riesgo alto para D3.**
- Explorar mitigaciones: (a) reducir dimensiones del plano, (b) rutear sin plano y agregar `fill_zones` después, (c) documentar que D3 se hace SIN plano.

---

## Bloque 4 — Solo si Bloques 1, 2, 3 pasaron: escenario D3 con keepout (timeout: 30 min)

Si los tres bloques dieron verde:
1. Repetir Bloque 3 (desde cero con plano) + agregar keepout bajo ANT1 antes de `route_board`.
2. ¿Converge? ¿Cuánto tarda?

Si converge: **D3 plenamente viable con plano + keepout.**
Si no converge: **D3 viable con plano pero keepout se aplica como paso post-route manual.** Documentar workaround.

---

## Reporte final (`docs/sesiones/19c-reporte.md`)

Cada bloque documenta: hipótesis, metodología, datos crudos, conclusión con evidencia, timeouts consumidos vs asignados.

### Decisión vinculante al final

| Bloque | Estado | Impacto en D3 |
|---|---|---|
| 1 | Verde/Amarillo/Rojo | ... |
| 2 | Verde/Amarillo/Rojo | ... |
| 3 | Verde/Amarillo/Rojo | ... |
| 4 | Verde/Amarillo/Rojo/N/A | ... |

### Recomendación GO / NO-GO / CONDICIONAL para Dogfooding 3

- **GO:** los 4 bloques verdes → sesión 19b arranca sch fix y luego D3.
- **CONDICIONAL:** algunos amarillos → D3 con caveats documentados (ej: sin keepout, `revert()` explícito cada N mutaciones). Especificar qué caveats.
- **NO-GO:** algún bloque crítico rojo → sesión adicional antes del D3. Especificar qué resolver.

---

## Fuera de alcance

- Zonas poligonales complejas (fuera desde sesión 19).
- A* de bloqueador concreto (17b).
- Cualquier feature nuevo.
- Corrección del sch del despertador (sesión 19b).
- Optimización de Freerouting más allá de mitigaciones puntuales.

## Precondiciones antes de arrancar

- KiCad 10.0.4 cerrado y reabierto limpio.
- `KICAD_MCP_FREEROUTING_JAR` configurada.
- Fixture `tests/fixtures/despertador-routed/` accesible.
- `.kicad_pcb` original pre-ruteo (sesión 17) recuperable — si no, generar con delete_all al inicio del Bloque 3.

## Recordatorio operacional

Cada bloque debe RESPETAR SU TIMEOUT. La sesión 19 se degradó parcialmente por dejar Freerouting sin límite; la 19c NO puede repetir ese antipatrón. **El valor de esta sesión es la DECISIÓN, no convergencias heroicas.**

---

## Env vars para la sesión

Mismas que 19:

```bash
export KICAD_MCP_GUI_TEST=1
export KICAD_MCP_PROJECT=/tmp/gui-test-project
export KICAD_MCP_GUI_REF=U1
export KICAD_MCP_FREEROUTING_JAR=/home/astra/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar
```

**Y KiCad reiniciado desde cero** — no la instancia que quedó de la sesión 19.
