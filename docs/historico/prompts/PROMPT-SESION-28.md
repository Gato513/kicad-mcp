# Dogfooding 6 — Segunda ratificación de Fase 3 (sesión 28)

**QUÉ ES:** sesión de USO, no de desarrollo. Mismas reglas que
D1/D2/D3/D4/D5: **prohibido editar el repo de kicad-mcp**; toda falla se
REGISTRA como fricción en el log, no se arregla. **Es el segundo
dogfooding de la Fase 3 (consolidación / aumento progresivo de confianza)
del proyecto.**

**Cambio de propósito respecto a D5 (que ya era Fase 3):** D5 fue primera
ratificación del contrato D-23.2 sobre `route_board` en producción. D6
hace dos cosas nuevas:

1. **Ratifica la extensión del contrato D-23.2 a las tres tools**
   (`route_board`, `fill_zones`, `add_zone(fill=True)` — sesión 27
   mergeada). El test de regresión de sesión 27 cubrió `fill_zones` y
   `add_zone(fill=True)` en aislado; D6 los ejercita en flujo completo
   de dogfooding real.
2. **Es la primera aplicación empírica de D-26.1** (refill obligatorio
   post-colocación pre-baseline DRC). Sesión 26 §2 estableció que
   `move_footprint` NO dispara refill de zonas; sin `fill_zones()`
   explícito entre colocación masiva y baseline, el baseline mide fill
   rancio y las violaciones detectadas son artefactos, no residuales
   reales. D5 leyó el baseline sin `fill_zones()` — no explotó por
   casualidad geométrica (colocación generosa). D6 lo aplica desde el
   arranque.

**Objetivo primario:** ratificar en dogfooding real la extensión D-23.2 y
el hallazgo D-26.1. Objetivo secundario: sumar peso estadístico al ciclo
de convergencia — si D6 verde → 2 verdes consecutivos (D5+D6), más cerca
del criterio de cierre de Fase 3.

**Variable controlada:** MISMA placa que D3/D4/D5 (despertador ATtiny85
wearable, 24 footprints, mismo sch corregido, fixture regenerado en D5).
Cualquier delta de nota vs D5 se atribuye directo a sesión 27
(generalización D-23.2) o a la aplicación de D-26.1. Cualquier delta
negativo se **sospecha regresión de sesión 27 hasta que se pruebe lo
contrario** — interpretación de Fase 3 sobre P0 nuevos.

**Objetivo nota:** ≥9/10. D5=9.5 marca la referencia; D6 sostener o
mejorar es evidencia positiva de convergencia. Con contrato extendido y
D-26.1 aplicado desde el arranque, D6 debería converger sin las 6
violaciones "residuales" del baseline de D5 (que eran fill rancio, no
residuales reales).

**Timeboxing:** 2h target, 2.5h techo. D5 tomó ~2h con contrato aguantando
por primera vez. D6 debería converger igual o más rápido — el contrato ya
no es novedad, D-26.1 no agrega tiempo neto.

---

## ENTREGABLES

1. `/tmp/dogfood6-fricciones.md` — mismo formato F-D6-NN, escrito EN EL
   MOMENTO, no al final.
2. Placa completa: PCB colocado, plano GND, ruteado, DRC coincidente con
   baseline (delta V4), gerbers G3, BOM, fixture actualizado (versión D6)
   en `tests/fixtures/despertador-routed/` **solo si D6 sale verde**.
3. Resumen final con nota /10 + comparación D2/D3/D4/D5/D6 + estado del
   ciclo de convergencia (¿2 verdes consecutivos? ¿ratifica extensión
   D-23.2? ¿ratifica D-26.1?).

---

## ESTADO INICIAL DEL PROYECTO

- [x] `master` con sesión 27 mergeada. Contrato D-23.2 implementado en
      `route_board` (sesión 24), `fill_zones` (sesión 27),
      `add_zone(fill=True)` (sesión 27).
- [x] Docs de consolidación post-sesión 27 mergeados
      (`docs/CONTEXT.md`, `docs/DECISIONES.md` con D-23.2 extendido +
      D-27.1, `docs/BACKLOG.md` P2 cerrado, `docs/ROADMAP.md`,
      `hoja-de-ruta-v4.md`).
- [x] Esquemático corregido (sesión 19b): 0 errores, 4 warnings
      `lib_symbol_mismatch` aceptados (D-19b.1).
- [x] Fixture `tests/fixtures/despertador-routed/` regenerado por D5
      (sesión 25) — baseline conocido. NO tocar hasta el final.
- [x] Server MCP con contrato D-23.2 en las tres tools + código
      `POST_ZONE_PERSIST_FAILED` disponible.
- [ ] Todo lo demás (outline, plano, colocación, ruteo, DRC, gerbers) es
      trabajo tuyo, arrancando desde board vacío como D3/D4/D5.

**Proyecto en disco:**
`/tmp/gui-test-project/despertador_inteligente.kicad_pro` (restaurado
por el humano antes del arranque — ver D-27.1 si hay drift).

---

## VERIFICACIONES ESPECÍFICAS DE D6 (mandatorias)

Estas 5 verificaciones son el punto principal de D6. Cada una se reporta
en el log de fricciones, **incluso si no hay fricción** — son evidencia
estadística de la ratificación.

### V1. Log obligatorio de keepouts auto-generados
Después de CADA `route_board`, correr:
```
get_zones(layer="B.Cu")
```
Contar los keepouts con prefijo `__kicadmcp_hc__` y registrar. Esperable:
4 fijos (ANT1 + 3× J1 NPTH). Sin cambios respecto a D5.

### V2 REFORZADA EN TRES TOOLS. Cross-check contrato D-23.2

**Diferencia clave respecto a D5:** en D5, V2 verificaba solo
`route_board`. En D6, V2 se ejercita en las TRES tools con contrato
D-23.2. Requiere al menos:

- Primera invocación de `route_board(timeout_s=600)` con V2 completo.
- Al menos una invocación explícita de `fill_zones()` con V2 completo
  (aparte del refill interno automático del `route_board`).
- Al menos una invocación de `add_zone(net=<X>, layer=<Y>, fill=True)`
  con V2 completo. **Nota:** si el flujo natural de D6 no requiere
  agregar una zona nueva post-D5 (el plano GND ya existe del `add_zone`
  de Fase 2), forzar la verificación con una zona de test menor —
  por ejemplo, `add_zone(net="GND", layer="F.Cu", bbox=<pequeño>,
  fill=True)` seguida de `delete_zone()` al final. Registrar
  explícitamente el V2 de esta invocación.

Para cada invocación, registrar:

```
## V2-<tool>-N — Cross-check D-23.2, tool=<tool>, corrida N
- **Tool invocada:** route_board / fill_zones / add_zone
- **Estado interno reportado:**
  - route_board: err_post, por_tipo
  - fill_zones/add_zone: sin campo drc por diseño (D-23.2 extendido);
    verificar disco directamente con run_drc() inmediato
- **run_drc() independiente:** X (por_tipo: {...})
- **Coinciden (route_board) o run_drc() no muestra hole_clearance
  espurio vs Zone (fill_zones/add_zone):** sí / no
- **mtime pre-operación:** T1
- **mtime post-operación:** T2 (cambió: sí / no)
- **Aparece EXTERNAL_EDIT_DETECTED en lecturas posteriores:** no / sí
```

**Criterio de ratificación:** 3 corridas por tool coincidentes → dejar
de hacer el cross-check para esa tool. Si alguna divergencia aparece
en cualquiera de las tres tools → **fricción P0 F-D6-XX + parar sesión
+ reportar como potencial regresión de sesión 27** (para
`fill_zones`/`add_zone`) o sesión 24 (para `route_board`).

### V3. Bandera roja obligatoria — DETENER SI APARECE

Cualquiera de estas condiciones es señal de regresión:

- Violación DRC con `clearance=0.0000mm` vs Zone GND.
- Violación DRC con `hole_clearance=0.0000mm` vs Zone GND.
- `route_board.drc.err_post` no coincide con `run_drc()` independiente
  inmediato SIN `save_board()` manual.
- **NUEVO en D6:** `fill_zones()` o `add_zone(fill=True)` deja el disco
  con estado distinto del vivo (verificable con `run_drc()` inmediato
  vs `get_zones()` sobre el vivo).
- `POST_ROUTE_PERSIST_FAILED` o `POST_ZONE_PERSIST_FAILED` disparado
  inesperadamente.

**Interpretación en Fase 3:** V3 activada en D6 se sospecha regresión
de sesión 27 (para `fill_zones`/`add_zone`) o sesión 24 (para
`route_board`) hasta prueba en contrario. Es información valiosa aunque
signifique nota <5 — pero no forzar V3 si no aparece.

Si aparece cualquiera:
1. **NO seguir el ruteo/fill.**
2. Registrar fricción **F-D6-XX con severidad `bloqueante` P0** —
   incluir el JSON completo de la tool que disparó + `get_zones` +
   `run_drc` pre y post.
3. Guardar el board (`save_board`).
4. Terminar sesión y reportar al arquitecto.

### V4 CON D-26.1 APLICADO. Baseline dinámico refill-corregido

**Diferencia clave respecto a D5:** en D5, el baseline se leyó
directamente post-colocación (sin `fill_zones()` explícito). Sesión 26
§2 refutó esa interpretación — sin refill, el DRC lee fill rancio y las
violaciones son artefactos. D6 aplica D-26.1: **`fill_zones()`
obligatorio entre la colocación y el baseline.**

Flujo obligatorio en Fase 1 (ver sección de flujo abajo):

1. Colocación completa de los 24 footprints con `move_footprint`.
2. **`fill_zones()` explícito** (esto es la aplicación de D-26.1).
3. **Entonces** `run_drc(min_severity="error")` para baseline.

Registrar el baseline como en D5:

```
## V4 — Baseline DRC pre-route (post-D-26.1)
- **Total errores:** X
- **por_tipo:** {"courtyards_overlap": N, ...}
- **Violaciones individuales (mandatorio, formato controlado):** una
  línea por violación con `<tipo>|<pos>|<refs>|<severidad>`.
```

**Comparación esperada vs D5:**
- D5 registró 6 violaciones en el baseline: 3× hole_clearance (J1
  pads) + 1× hole_clearance ANT1 + 1× clearance ANT1 + 1×
  solder_mask_bridge ANT1. Sesión 26 §2 mostró que estas 6 desaparecen
  con `fill_zones()` explícito (fill rancio).
- **Predicción D6:** con D-26.1 aplicado, el baseline debería tener
  **0-1 violaciones** (esperable: 0). Si aparecen las mismas 6 de D5
  → algo del contrato D-23.2 en `fill_zones` no está aguantando y hay
  que investigar antes de continuar (potencial F-D6-XX).
- **Registrar la comparación explícita en el reporte:** el delta
  observado ratifica o refuta D-26.1 empíricamente.

Después de cada `route_board`/`fill_zones`/`add_zone` posterior,
comparar `run_drc()` post contra baseline con formato de delta idéntico
al de D5.

### V5. Observación específica de F-D5-01 (isla GND sin vía al plano)

**Contexto:** D5 corrida 1 detectó F-D5-01 (severidad info): C2/C3
formaban isla GND sin vía propia al plano B.Cu tras primer autoroute.
Resuelto con `add_via` puntual. Trigger definido: si el patrón se
repite en 2 dogfoodings independientes (D6 + D7), promover a P2
investigación.

**D6 debe reportar explícitamente en el resumen final:**

- ¿Apareció el mismo patrón (isla GND de dos pads sin vía al plano tras
  autoroute)? sí / no.
- Si sí: ¿en qué net y qué pads?
- Si sí: ¿la geometría de los pads involucrados es análoga a C2/C3 de
  D5 (dos SMD en columna cerca del borde del plano)?
- Recomendación de escalado: si aparece con geometría similar a D5 →
  segundo dogfooding independiente ratifica el patrón, **promover a P2
  investigación en el reporte final**.

Sin esta pregunta explícita, F-D5-01 puede pasar desapercibida si sale
por casualidad geométrica; la disciplina de vigilancia se pierde.

---

## PRECONDICIONES OPERACIONALES

Idénticas a D5, con nota adicional sobre D-27.1:

1. `/tmp/gui-test-project/` restaurado desde el fixture
   `despertador-routed` (regenerado en D5). **Si al arrancar el fixture
   vivo no coincide con el fixture del repo** (mtime más viejo,
   contenido residual, etc.), aplicar D-27.1 (restore no destructivo:
   backup vivo → sobrescribir → `reload_board_from_disk()` → verificar
   con `get_component_detail`/`get_zones`). `AskUserQuestion` obligatoria
   antes de mutar el proyecto abierto.
2. KiCad reiniciado limpio.
3. Sin symlink en `/tmp/kicad/` (cascada de 19e).
4. Env vars del server MCP en `~/.claude.json`:
   - `KICAD_MCP_GUI_TEST=1`
   - `KICAD_MCP_PROJECT=/tmp/gui-test-project`
   - `KICAD_MCP_GUI_REF=U1`
   - `KICAD_MCP_FREEROUTING_JAR=/home/astra/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar`

Confirmar con `health()` que todo responda ok antes de tocar nada.

---

## CAVEATS OPERACIONALES (heredados, respetar)

### C1. NO aplicar `add_keepout_zone` antes de `route_board`
Solo POST-route. Sin cambios.

### C2. Patrón validado para plano GND
Crear y fillar el plano GND ANTES de `route_board`. Freerouting NO
respeta el plano como exclusión (D-19.1 v6), pero el refill posterior +
`enforce_hole_clearance` + persistencia (D-23.2, sesión 24) arreglan el
resultado.

### C3. `delete_tracks_bulk` con `dry_run=True` primero
Si necesitás re-rutear una net específica.

### C4. `NET_ASSIGNMENT_MISMATCH` como señal legítima
Si aparece, replanificar coordenadas — no bug.

### C5. Conectores con agujeros mecánicos ≥1.5-2mm del borde (D-D3.1)

### C6. `get_footprint_neighbors` inclusivo (D-D4.1)
Aplicar a cualquier footprint denso, no solo conectores con drill.

### C7. Refill obligatorio pre-baseline DRC (D-26.1 — NUEVO EN D6)
`move_footprint` NO dispara refill de zonas. Todo baseline DRC leído
inmediatamente después de una colocación masiva sin `fill_zones()`
explícito mide fill rancio, no el estado real. **Aplicar en Fase 1
mandatoriamente.**

### C8. Restore no destructivo del entorno GUI (D-27.1)
Si el fixture vivo no coincide con el fixture del repo, aplicar
procedimiento estándar sin reiniciar KiCad. `AskUserQuestion` antes de
mutar el proyecto abierto.

---

## PUNTOS DE CONTACTO HUMANO

**H1 (asumido):** proyecto en disco, sch corregido, KiCad abierto, env
vars ok.

**H2 (condicional):** F8 si `get_world_context(kind="pcb")` revela
desincronización sch↔pcb. Esperable: NO.

**H3 (revert): NO EXISTE.** Cerrado por D-V3.1.

**H4 (validación visual opcional):** renders intermedios si querés
segunda opinión.

**H5 (D-27.1):** `AskUserQuestion` obligatoria si el fixture vivo
requiere restore.

---

## FLUJO ESPERADO (tu plan de vuelo)

Diferencias respecto a D5 (subrayadas):

### Fase 1: Verificación de estado + baseline con D-26.1 (10-15 min)
1. `health()` → ipc ok.
2. `run_erc()` → confirmar 0 errores, 4 warnings esperados.
3. `get_world_context(kind="pcb", max_tokens=4000)` → inventario.
4. F8 si es necesario (esperable: NO).

### Fase 2: Contorno y plano GND (5-10 min)
5. `draw_board_outline(bbox=<40-50mm cuadrado>)`. En D3/D4/D5 fue
   44×44.
6. `add_zone(net="GND", layer="B.Cu", bbox=<mismo bbox>, fill=true)`.
   **Registrar V2 de esta invocación** — es la primera aplicación de
   `add_zone(fill=True)` en el flujo (con contrato D-23.2 extendido).

### Fase 3: Colocación con reconocimiento inclusivo (25-35 min)
7. Plan breve de colocación en el chat.
8. **`get_footprint_neighbors` inclusivo** (D-D4.1).
9. `move_footprint(ref, x, y)` × 24.
10. `save_board()`.
11. Render de control.

### Fase 3.5: **REFILL D-26.1 + BASELINE DINÁMICO V4 (mandatorio,
5-8 min — NUEVA respecto a D5)**
12. **`fill_zones()` explícito** (aplicación de D-26.1). Registrar V2
    de esta invocación — es la primera aplicación de `fill_zones()`
    directamente por el flujo (no vía `route_board`).
13. `run_drc(min_severity="error")` sobre estado post-fill.
14. Registrar V4 baseline con formato controlado.
15. **Comparar con predicción:** 0-1 violaciones esperadas (vs 6 de
    D5 pre-D-26.1). Si aparecen las 6 de D5, potencial F-D6-XX.

### Fase 4: Ruteo (5-10 min esperable)
16. Anotar mtime pre-route del `.kicad_pcb`.
17. `route_board(timeout_s=600)`.
18. Anotar mtime post-route.
19. **V1**: log de keepouts `__kicadmcp_hc__` (obligatorio).
20. **V2 REFORZADO** para `route_board` (primera corrida, o hasta 3/3).
21. **V3**: chequear bandera roja.
22. **V4 delta**: comparar `run_drc()` post contra baseline.
23. **V5**: chequear patrón F-D5-01 en `unconnected_items`.

### Fase 5: DRC + cirugía si hace falta (variable)
24. Si el delta V4 muestra **violaciones nuevas** (no en baseline) →
    diagnóstico normal.
25. Cualquier re-ruteo: repetir V1 + V2 + V3 + V4 delta.
26. **Si aparece F-D5-01 nuevamente**, resolver con `add_via` puntual
    (mismo protocolo de D5). Registrar en V5.

### Fase 5.5: **V2 explícito para add_zone(fill=True) (5 min, si
todavía no se ratificó 3/3)**
27. Si V2 para `add_zone(fill=True)` de Fase 2 no cubre 3/3 (por
    ejemplo, solo hubo una invocación en toda la sesión), forzar dos
    invocaciones adicionales de test:
    ```
    add_zone(net="GND", layer="F.Cu", bbox=<pequeño>, fill=true)
    delete_zone(id=<generado>)
    ```
    Repetir hasta acumular 3 corridas de V2 verdes para `add_zone`.
    Análogo para `fill_zones` si no se acumularon 3/3 naturalmente.

### Fase 6: Cierre (10 min)
28. Render final.
29. `export_manufacturing()` → gerbers G3.
30. `export_bom()`.
31. **Actualizar fixture** SOLO SI D6 sale verde: copiar `.kicad_pcb`,
    `.kicad_pro`, `.kicad_sch`, `.kicad_prl` a
    `tests/fixtures/despertador-routed/`. README con "versión D6,
    sesión 28, hash <commit>".

### Fase 7 (opcional, si sobra tiempo)
32. Tests operacionales que quedaron pendientes en D5 (por ejemplo,
    `delete_tracks_bulk` con `dry_run`).

---

## DISCIPLINA DE CONTEXTO

Delta > mundo con focus > mundo completo. Renders con criterio (~11s
c/u). Reportar al final: llamadas por tool, tokens totales estimados,
tiempo por fase, contactos humanos, comparación con D3/D4/D5.

---

## REGLAS PROHIBITIVAS (VIOLARLAS INVALIDA EL DOGFOOD)

1. **NO editar el repo de kicad-mcp.** Toda falla → registrar como
   fricción, NUNCA arreglar.
2. **NO manipular archivos por fuera de las tools.**
3. **NO invocar `kicad-cli` directo** para bypass.
4. **NO editar `~/.claude.json`** durante la sesión.
5. **NO reiniciar KiCad si crashea (R11)** sin registrar primero.
6. **NO omitir V1/V2/V3/V4/V5** — son el punto principal de D6.
7. **NO forzar hallazgos** que no aparecen naturalmente. Un D6 verde es
   evidencia positiva de Fase 3, no un fracaso.
8. **NO omitir D-26.1** en Fase 1. Si el ejecutor lee baseline sin
   `fill_zones()` explícito, invalida V4 y potencialmente V5.

---

## LOG DE FRICCIONES

Crear `/tmp/dogfood6-fricciones.md` al inicio. Formato:

```
## F-D6-NN — Título corto
- **Qué pasó:** ...
- **Qué esperaba:** ...
- **Workaround:** ...
- **Costo:** [bajo/medio/alto]
- **Severidad:** [info/warn/bloqueante]
```

Sección **Aciertos** al final: 3-5 cosas del server que funcionaron
mejor que en D5.

---

## RESUMEN FINAL (última sección del log)

Responder **explícitamente** las 16 preguntas siguientes:

1. **¿Placa completa?** ERC ✓, colocado %, ruteado %, DRC (delta vs
   baseline V4), gerbers ✓/✗, plano GND ✓, keepouts auto ✓.

2. **Tabla comparativa D2 vs D3 vs D4 vs D5 vs D6:**

   | Métrica | D2 | D3 | D4 | D5 | D6 |
   |---|---|---|---|---|---|
   | Nota | 7.5/10 | 8.5/10 | 4.5/10 | 9.5/10 | ? |
   | Fricciones bloqueantes | 0-1 | 1 externa | 1 P0 interna | 0 | ? |
   | `route_ms` corrida completa | 925s | 53s | 36.7s | 128.8s | ? |
   | Contactos humanos | 5 | 2 | 0 | 0 | ? |
   | Errores DRC introducidos post-route | 53 | 0 | 42 obsoletos | 1 F-D5-01 | ? |
   | Baseline V4 pre-route (violaciones) | N/A | N/A | N/A | 6 (fill rancio) | ? |
   | mtime cambia post-tool D-23.2 | N/A | N/A | N/A | sí (route_board) | ? (tres tools) |

3. **Estado del contrato D-23.2 extendido (sesión 27):**
   - V2 corridas coincidentes por tool: route_board X/3, fill_zones X/3,
     add_zone X/3.
   - ¿Alguna divergencia detectada? En qué tool?
   - ¿Ratifica la extensión sesión 27 en dogfooding real?

4. **Estado de D-26.1 (primera aplicación empírica):**
   - Baseline V4 con `fill_zones()` explícito: X violaciones.
   - Delta esperado vs D5 (que tenía 6 violaciones de fill rancio):
     ¿0-1 esperable? ¿Coincide?
   - ¿Ratifica D-26.1 empíricamente?

5. **Estado de F-D5-01 (V5):**
   - ¿Apareció el patrón (isla GND sin vía al plano)?
   - Si sí: geometría similar a D5?
   - Recomendación: ¿promover a P2 investigación (segundo dogfooding
     independiente ratifica patrón)?

6. **Estado de F-D4-02 (contrato D-23.2 en `route_board`):** ¿sigue
   ratificado 3/3 como en D5?

7. **Estado de otras fricciones históricas:**
   - F-D3-01/F-D3-03: no deberían aparecer.
   - F-D3-04: ¿`get_footprint_neighbors` sigue ahorrando tiempo?
   - F-D4-01 (R13, `get_world_context(kind="sch")` con `#PWR*/#FLG*`):
     sigue pendiente P3.

8. **Fricciones nuevas de D6 (F-D6-XX)**, si las hay, con propuesta.

9. **`route_ms` esta placa** — comparar con D5 (128.8s). Modelo mental
   actualizado: techo esperable ~200s (test regresión sesión 24 dio
   186.5s y 150.2s).

10. **`get_footprint_neighbors` en acción** (D-D4.1 inclusivo): ¿cuántas
    veces se usó? ¿Ahorró tiempo? ¿`courtyards_overlap` = 0?

11. **Nota /10 con justificación** — objetivo ≥9. Justificar cada 0.5.

12. **¿Convergimos hacia el criterio de cierre de Fase 3?**
    - Verde (≥9, 0 P0/P1 nuevos, V3 no activada, V2 3/3 por tool,
      D-26.1 ratificado): **2 verdes consecutivos.** Considerar D7 para
      3er verde consecutivo o iniciar preparación Fase 4.
    - Amarillo (8-8.9, 1-2 P1, V3 no activada): sesión de fix +
      próximo dogfooding con misma placa antes de avanzar.
    - Rojo (V3 activada, P0 nuevo, nota <8): investigación mandatoria.
      **Sospechar regresión de sesión 27** (para
      `fill_zones`/`add_zone`) o sesión 24 (para `route_board`) hasta
      prueba en contrario.

13. **Evidencia V1/V2/V3/V4/V5 consolidada:**
    - V1: keepouts auto por route_board (esperable: 4 constantes).
    - V2 reforzado: 3/3 por cada una de las 3 tools (esperable: sí).
    - V3: activada? (esperable: NO).
    - V4 con D-26.1: baseline reducido a 0-1 violaciones (esperable: sí,
      ratificando D-26.1).
    - V5: F-D5-01 apareció? (esperable: no o sí ratificado).

14. **Si D6 verde, ¿el fixture se actualiza a versión D6?**

15. **¿Qué falta para uso semanal?** (la pregunta persistente).
    Esperable en Fase 3 avanzada: "nada crítico, solo P1 solder mask
    ANT1 con investigación pendiente".

16. **¿Recomendación explícita para D7 (sesión 29)?**
    - Verde D6 → D7 = tercer dogfooding de ratificación (mismo protocolo),
      buscar 3er verde consecutivo para robustecer el criterio de cierre.
    - Amarillo D6 → sesión de fix quirúrgico + D7' con misma placa.
    - Rojo D6 → investigación mandatoria antes de continuar.

---

## Cierre esperado

D6 cerrado con:
- Nota /10 documentada.
- Placa fabricable con delta V4 = 0 violaciones nuevas.
- V1/V2/V3/V4/V5 completas.
- Log de fricciones completo.
- Fixture actualizado (si verde).
- Recomendación para D7 explícita.

Escenarios posibles según resultado:

- **Verde (≥9, 2 verdes consecutivos):** convergencia parcial de
  Fase 3. Avanzar a D7 (sesión 29) para consolidar 3er verde
  consecutivo, o iniciar preparación Fase 4 si el arquitecto lo decide.
- **Amarillo:** ciclo continúa. Sesión de fix quirúrgico + D6' con
  misma placa.
- **Rojo:** investigación mandatoria antes de D7. Sospechar regresión
  de sesión 27 o 24, revisar tests de regresión bajo lupa.

**Recordatorio operacional de Fase 3:** el objetivo es RATIFICAR, no
descubrir. No forzar hallazgos donde no los hay. No escalar
complejidad. D6 es la segunda medición formal de si Fase 3 va a
converger tan bien como esperamos.

Traeme el reporte + log de fricciones cuando termine.
