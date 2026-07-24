# Dogfooding 4 — Primer test empírico del ciclo de hardening (sesión 22)

**QUÉ ES:** sesión de USO, no de desarrollo. Mismas reglas que D1/D2/D3:
**prohibido editar el repo de kicad-mcp**; toda falla se REGISTRA como
fricción en el log, no se arregla. Es el primer dogfooding del ciclo de
hardening post-sesión 21. **Objetivo ≥9/10** (D1=5, D2=7.5, D3=8.5).

**Variable controlada:** MISMA placa que el D3 (despertador ATtiny85
wearable, 24 footprints, mismo sch corregido, mismo fixture regenerado).
Cualquier delta de nota vs D3 se atribuye directo a los fixes de sesión 21
(P0 F-D3-01 + F-D3-03 + P1 `get_footprint_neighbors`), no al problema.

**Timeboxing:** 2h target, 2.5h techo. Con los P0 cerrados, la nueva tool
`get_footprint_neighbors` y el resto del stack maduro, D4 debería
converger más rápido que D3. Si a las 2.5h no estás exportando gerbers,
parar y reportar el estado.

---

## ENTREGABLES

1. `/tmp/dogfood4-fricciones.md` — mismo formato F-D4-NN, escrito **EN EL
   MOMENTO**, no al final.
2. Placa completa: PCB colocado, plano GND, ruteado, DRC 0 errores,
   gerbers G3, BOM, fixture actualizado (versión D4) en
   `tests/fixtures/despertador-routed/`.
3. Resumen final con nota /10 + comparación D2/D3/D4 + estado del ciclo
   de hardening (¿convergimos hacia release o hay más iteraciones?).

---

## ESTADO INICIAL DEL PROYECTO

Idéntico al D3, con un cambio: **el fixture del D3 es tu baseline de
verificación en tests, pero para el D4 partís de un board colocado desde
cero** (mismo escenario que D3 arrancó, para comparabilidad estricta).

- [x] Esquemático corregido (sesión 19b): 0 errores, 4 warnings
      `lib_symbol_mismatch` aceptados (D-19b.1 — NO ejecutar "Update
      Symbols from Library").
- [x] F8 sync sch→pcb hecho (sesión 19b y confirmado en D3).
- [x] Fixture `tests/fixtures/despertador-routed/` regenerado por D3
      (baseline de estabilidad — no lo toques hasta el final).
- [x] Server MCP con fixes de sesión 21 en producción.
- [ ] Todo lo demás (outline, plano, colocación, ruteo, DRC, gerbers) es
      trabajo tuyo.

**Proyecto en disco:** `/tmp/gui-test-project/despertador_inteligente.kicad_pro`
(restaurado por el humano antes del arranque).

---

## VERIFICACIONES ESPECÍFICAS DE SESIÓN 21 (mandatorias en D4)

Estas 3 verificaciones son el propósito principal del D4. Cada
`route_board` debe reportar estos datos en el log de fricciones, **incluso
si no hay fricción** — son evidencia empírica de que sesión 21 quedó bien
cerrada.

### V1. Log obligatorio de keepouts auto-generados
Después de CADA `route_board`, correr:
```
get_zones(layer="B.Cu")
```
Contar los keepouts con prefijo `__kicadmcp_hc__` y registrar el número
en el log:

```
## V1-N — Keepouts auto-generados post-route N
- **Cantidad:** X
- **Esperado en placa despertador:** 4 fijos (ANT1 + 3× J1 NPTH)
- **Coincide con esperado:** sí / no
- **Si no:** listar refs de los pads/vías protegidos
```

Este dato confirma en producción que `enforce_hole_clearance` (fix 21.1)
está corriendo correctamente. Cero fricción esperada, pero registrar
igual como evidencia.

### V2. Cross-check del contrato JSON de route_board
Después de las **primeras 3 invocaciones** de `route_board`, correr
inmediatamente:
```
run_drc(min_severity="error")
```
Y comparar contra `route_board.drc.err_post`. Registrar:

```
## V2-N — Cross-check DRC contrato JSON, corrida N
- **route_board.drc.err_post:** X
- **run_drc() independiente:** Y
- **Coinciden:** sí / no
- **Si no:** delta por tipo
```

Si coinciden 3 veces consecutivas → dejar de hacer el cross-check
(basta para ratificar D-D3.2 permanentemente revocada). Si divergen
alguna vez → **fricción P0 nueva F-D4-XX + parar sesión + reportar**.

### V3. Bandera roja obligatoria — DETENER SI APARECE
Cualquiera de estas tres condiciones post-route es señal de que F-D3-01
NO está tan cerrado como pensamos:
- Violación DRC con `clearance=0.0000mm` o similar (cerca de 0).
- Violación DRC con `pos=[0,0]` (posición inválida).
- Cualquier violación `hole_clearance` post-route con zonas de cobre
  presentes en el board.

Si aparece cualquiera:
1. **NO seguir el ruteo.**
2. Registrar fricción **F-D4-XX con severidad `bloqueante` P0** — incluir
   el JSON completo de `route_board` + `get_zones` + `run_drc` en el log.
3. Guardar el board en el estado actual (`save_board`).
4. Terminar sesión y reportar al arquitecto.

Esta es la señal de que la investigación de sesión 21 tiene que
reanudarse antes de continuar el ciclo.

---

## PRECONDICIONES OPERACIONALES

Idénticas al D3, ya deberían estar hechas por el humano antes del arranque:

1. `/tmp/gui-test-project/` restaurado desde Desktop o desde el fixture
   `despertador-routed`.
2. KiCad reiniciado limpio.
3. Sin symlink en `/tmp/kicad/` (cascada de 19e).
4. Env vars del server MCP en `~/.claude.json`:
   - `KICAD_MCP_GUI_TEST=1`
   - `KICAD_MCP_PROJECT=/tmp/gui-test-project`
   - `KICAD_MCP_GUI_REF=U1`
   - `KICAD_MCP_FREEROUTING_JAR=/home/astra/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar`

Confirmar con `health()` que todo responda ok antes de tocar nada.

---

## CAVEATS OPERACIONALES (heredados de 19c/D3, respetar)

### C1. NO aplicar `add_keepout_zone` antes de `route_board`
Solo POST-route. Sin cambios respecto a D3.

### C2. Patrón validado para plano GND
Crear y fillar el plano GND ANTES de `route_board`, sobre un board sin
cobre. Freerouting respeta nativamente `(plane)` (D-19.1). `timeout_s ≥ 300`
(D3 tomó 53s; margen amplio).

### C3. `delete_tracks_bulk` con `dry_run=True` primero
Si necesitás re-rutear una net específica.

### C4. `NET_ASSIGNMENT_MISMATCH` como señal legítima
Si aparece, replanificar coordenadas — no bug.

### C5. Conectores con agujeros mecánicos ≥1.5-2mm del borde (NUEVO desde D3)
**D-D3.1**: antes de colocar J1 (Tag-Connect) o J2 (JST con clips),
verificar con `get_footprint_neighbors(ref, radius_mm=3.0)` que hay
margen suficiente al borde y sin conflictos con otros footprints. Esto
habría eliminado F-D3-04 (35 min perdidos en el D3).

**Uso recomendado de `get_footprint_neighbors`:**
- Antes de colocar cualquier conector con drill mecánico propio.
- Ante cualquier duda de "¿hay lugar para rutear acá?" durante colocación.
- No es reemplazo de `get_tracks(bbox=)` para diagnóstico fino; es para
  reconocimiento de espacio rápido.

**Consideración de presupuesto de tokens**: para clusters densos (J1
resultó en ~2244 tokens en el D3), `max_tokens=3000` es un buen default
inicial. Si aparece `CONTEXT_BUDGET_IMPOSSIBLE`, subir progresivamente.

---

## PUNTOS DE CONTACTO HUMANO

**H1 (asumido, ya hecho):** proyecto en disco, sch corregido, KiCad abierto,
env vars ok.

**H2 (condicional):** F8 si `get_world_context(kind="pcb")` revela que los
footprints del sch corregido NO están sincronizados en el PCB. Esperable:
NO se necesita (el D3 ya lo hizo).

**H3 (revert): NO EXISTE.** Cerrado por D-V3.1 (sesión 18) y ratificado en
D3. Si aparece → fricción grave.

**H4 (validación visual opcional):** renders intermedios si querés
segunda opinión. Costo ~11s c/u.

---

## FLUJO ESPERADO (tu plan de vuelo)

Casi idéntico al D3 con dos diferencias: **usar `get_footprint_neighbors`
proactivamente** en Fase 3 y **ejecutar V1/V2** en Fase 4/5.

### Fase 1: Verificación de estado (5-10 min)
1. `health()` → ipc ok.
2. `run_erc()` → confirmar 0 errores, 4 warnings esperados.
3. `get_world_context(kind="pcb", max_tokens=4000)` → inventario.
4. F8 si es necesario (esperable: NO).

### Fase 2: Contorno y plano GND (5-10 min)
5. `draw_board_outline(bbox=<40-50mm cuadrado>)`. En D3 fue 44×44mm.
6. `add_zone(net="GND", layer="B.Cu", bbox=<mismo bbox>, fill=true)`.

### Fase 3: Colocación con reconocimiento de espacio (25-35 min, esperable
menos que D3)
7. Plan breve de colocación en el chat.
8. **Para conectores con drills (J1, J2) y footprints grandes (BT1, U4)**:
   invocar `get_footprint_neighbors(ref, radius_mm=3.0, max_tokens=3000)`
   antes de decidir posición final. Registrar en el log si algún resultado
   ahorra tiempo real vs D3.
9. `move_footprint(ref, x, y)` × 24.
10. `save_board()`.
11. Render de control.

### Fase 4: Ruteo (5-10 min esperable)
12. `route_board(timeout_s=600)`.
13. **V1**: log de keepouts `__kicadmcp_hc__` (obligatorio).
14. **V2** (primera vez): cross-check DRC contra `run_drc()` manual.
15. **V3**: chequear bandera roja. Si aparece, parar y reportar.

### Fase 5: DRC + cirugía si hace falta (variable)
16. `run_drc()` → esperable 0 errores dado sesión 21.
17. Si hay errores nuevos → diagnóstico normal (get_tracks, delete_track,
    add_track).
18. Cualquier re-ruteo: repetir V1 + V2 + V3 (V2 solo si aún no llegamos
    a 3 corridas consecutivas coincidentes).

### Fase 6: Cierre (10 min)
19. Render final.
20. `export_manufacturing()` → gerbers G3.
21. `export_bom()`.
22. **Actualizar fixture**: copiar `.kicad_pcb`, `.kicad_pro`, `.kicad_sch`,
    `.kicad_prl` a `tests/fixtures/despertador-routed/`. Actualizar README
    con "versión D4, sesión 22, hash <commit>".

### Fase 7 (opcional, si sobra tiempo)
23. **Test explícito de `add_keepout_zone` POST-route** (validación de
    D-19c.1): agregar keepout circular bajo ANT1 con 12 vértices. Registrar
    si el DRC cambia y cuántos tracks quedan bajo la zona (que habría que
    resolver manualmente).
24. **Test explícito de `delete_tracks_bulk`**: borrar todos los tracks de
    una net específica con `dry_run=True` primero, luego `dry_run=False`.
    Registrar tiempo total vs delete por id.

---

## DISCIPLINA DE CONTEXTO

Delta > mundo con focus > mundo completo. Renders con criterio (~11s c/u).
Reportar al final: llamadas por tool, tokens totales estimados, tiempo por
fase, contactos humanos, comparación con D3.

---

## REGLAS PROHIBITIVAS (VIOLARLAS INVALIDA EL DOGFOOD)

1. **NO editar el repo de kicad-mcp.** Toda falla → registrar como
   fricción, NUNCA arreglar.
2. **NO manipular archivos por fuera de las tools.**
3. **NO invocar `kicad-cli` directo** para bypass.
4. **NO editar `~/.claude.json`** durante la sesión.
5. **NO reiniciar KiCad si crashea (R11)** sin registrar primero.
6. **NO omitir V1/V2/V3** — son el punto principal del D4.

---

## LOG DE FRICCIONES

Crear `/tmp/dogfood4-fricciones.md` al inicio. Formato:

```
## F-D4-NN — Título corto
- **Qué pasó:** ...
- **Qué esperaba:** ...
- **Workaround:** ...
- **Costo:** [bajo/medio/alto]
- **Severidad:** [info/warn/bloqueante]
```

Además, las entradas V1-N, V2-N, V3-N (verificaciones), aunque sean
"todo OK sin fricción" — son evidencia obligatoria.

Sección **Aciertos** al final: 3-5 cosas del server que funcionaron mejor
que en D3.

---

## RESUMEN FINAL (última sección del log)

Responder **explícitamente** las 12 preguntas siguientes:

1. **¿Placa completa?** ERC ✓, colocado %, ruteado %, DRC (nuevos vs
   preexistentes), gerbers ✓/✗, plano GND ✓, keepouts auto ✓.

2. **Tabla comparativa D2 vs D3 vs D4:**

   | Métrica | D2 | D3 | D4 |
   |---|---|---|---|
   | Nota | 7.5/10 | 8.5/10 | ? |
   | Fricciones bloqueantes | 0-1 | 1 externa | ? |
   | `route_ms` | 925s | 53s | ? |
   | Contactos humanos | 5 | 2 | ? |
   | Errores DRC introducidos post-route | 53 (enmascarados) | 0 | ? |

3. **Estado de F-D3-01 a F-D3-05** (fricciones del D3):
   - F-D3-01: ¿el workaround aguantó? V1 count coincidente en cada
     route_board?
   - F-D3-03: coincidencia 3/3 en V2? ¿D-D3.2 permanentemente revocada?
   - F-D3-04: ¿`get_footprint_neighbors` ahorró tiempo real vs D3?
   - F-D3-05: ¿volvió a aparecer? (esperable: sí, sigue diferido)
   - F-D3-02: ¿`KICAD_MCP_FREEROUTING_JAR` seteado esta vez? (esperable: sí)

4. **Estado de F-01 a F-13 del D2**: las cerradas ¿siguen cerradas? ¿Alguna
   reapareció bajo condiciones del D4? Ver CONTEXT §Métricas D2.

5. **Estado de F-19b-XX**: las de R12 (tools sch aditivas) no deberían
   ejercitarse (sch pre-corregido). Confirmar.

6. **Las 3 fricciones nuevas más caras del D4 (F-D4-XX)**, si las hay,
   con propuesta.

7. **`route_ms` esta placa** — comparar con D3 (53s). Esperable similar o
   levemente distinto por no-determinismo de Freerouting.

8. **`get_footprint_neighbors` en acción**: ¿cuántas veces se usó? ¿Ahorró
   tiempo? ¿Aparecieron casos que no cubre bien?

9. **Nota /10 con justificación** — objetivo ≥9. Justificar cada 0.5.

10. **¿Convergimos hacia release?** Con base en el ciclo de hardening
    (CONTEXT v4 §Ruta estratégica):
    - ¿0 P0 nuevos? ¿0 P1 nuevos?
    - ¿P0/P1 anteriores confirmados cerrados por evidencia empírica?
    - Recomendación del agente: **continuar ciclo (D5) / preparar release
      (P2) / requiere más fixes antes de D5**.

11. **Evidencia V1/V2/V3 consolidada:**
    - V1: total de keepouts auto por route_board (esperable: 4 constantes).
    - V2: coincidencia N/3 (esperable: 3/3).
    - V3: activada? (esperable: NO).

12. **¿Qué falta para uso semanal?** (la pregunta persistente). Si la
    respuesta es "nada crítico, solo polish", esa es la señal de
    convergencia.

---

## Cierre esperado

D4 cerrado con nota /10 documentada, placa fabricable, fixture
actualizado, V1/V2/V3 completas, log de fricciones completo.

Escenarios posibles según resultado:

- **Verde (nota ≥9, 0 P0/P1, V3 no activada):** convergencia parcial. El
  arquitecto decide entre D5 con escalada de complejidad o preparación
  de release.
- **Amarillo (nota 8-8.9, 1-2 P1, V3 no activada):** ciclo continúa.
  Sesión de fix + D5.
- **Rojo (V3 activada, o P0 nuevo, o nota <8):** investigación mandatoria
  antes de D5. F-D3-01 tiene más profundidad de la que vimos y necesita
  otra sesión de investigación P4.0-style.

Traeme el reporte + log de fricciones cuando termine. Este es el
momento clave del ciclo de hardening — el que dice si los fixes de
sesión 21 aguantan en producción.
