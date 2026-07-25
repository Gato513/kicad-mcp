# Dogfooding 7 — Tercera ratificación de Fase 3 (sesión 29)

**QUÉ ES:** sesión de USO, no de desarrollo. Mismas reglas que
D1/D2/D3/D4/D5/D6: **prohibido editar el repo de kicad-mcp**; toda falla
se REGISTRA como fricción en el log, no se arregla. **Es el tercer
dogfooding de la Fase 3 (consolidación / aumento progresivo de
confianza) del proyecto.**

**Cambio de propósito respecto a D6:** D5 fue primera ratificación en
producción de D-23.2 (`route_board`). D6 fue segunda ratificación
extendida a las tres tools + primera aplicación empírica de D-26.1 (con
matiz metodológico documentado). **D7 busca:**

1. **3er verde consecutivo del criterio de cierre de Fase 3**
   (≥2-3 verdes, hoy vamos 2/3). Si sale verde, corresponde iniciar
   preparación de Fase 4 en la sesión 30.
2. **Aislamiento correcto de D-26.1** que D6 no logró por confusor de
   orden de fases. D7 replica el orden EXACTO de D5 (plano ANTES de
   colocar) y ejecuta un experimento controlado con/sin `fill_zones()`
   explícito.
3. **Variación geométrica controlada** para ratificar bajo condiciones
   no idénticas — D5 y D6 fueron réplicas exactas del mismo layout;
   D7 usa mismo footprint set, mismo outline, mismo sch, **pero
   coordenadas de colocación distintas** dentro del outline (respetando
   D-D3.1 ≥1.5-2mm de borde). No es escalada de complejidad, es
   control de variable "layout".
4. **Protocolo F-D6-01:** 2-3 mediciones adicionales de re-ruteo
   parcial para llegar a N=6-7 total y entender el patrón (o cerrar
   como variabilidad inherente).

**Objetivo nota:** ≥9/10. D5=9.5, D6=9.7. D7 sostener o mejorar es
evidencia positiva de convergencia. Con el aislamiento correcto de
D-26.1, la evidencia de D7 debería ser metodológicamente más limpia que
D6.

**Timeboxing:** 2h target, 2.5h techo. D6 fue 28min con layout heredado;
D7 requiere ejercicio de layout nuevo (coordenadas propias) + experimento
D-26.1, así que 45-60min es esperable, dentro del techo.

**Reglas nuevas de la sesión (formalizadas post-D6):**

- **D-28.1 vinculante:** cualquier cambio de orden de fases respecto al
  brief requiere `AskUserQuestion` ANTES de ejecutar. Fase 2
  (contorno + plano ANTES de mover footprints) es orden crítico
  metodológicamente — no invertir bajo ninguna circunstancia sin
  consultar.
- **D-27.1 vigente:** restore no destructivo del entorno GUI vivo con
  `AskUserQuestion` obligatoria antes de mutar el proyecto abierto.

---

## ENTREGABLES

1. `/tmp/dogfood7-fricciones.md` — mismo formato F-D7-NN, escrito EN EL
   MOMENTO, no al final.
2. Placa completa: PCB colocado (con coordenadas propias), plano GND,
   ruteado, DRC coincidente con baseline (delta V4), gerbers G3, BOM,
   fixture actualizado (versión D7) en `tests/fixtures/despertador-routed/`
   **solo si D7 sale verde**.
3. Resumen final con nota /10 + comparación D2-D7 + estado del ciclo
   de convergencia (¿3 verdes consecutivos? ¿D-26.1 aislado
   limpiamente? ¿F-D6-01 con patrón identificable o cerrar como
   variabilidad?).

---

## ESTADO INICIAL DEL PROYECTO

- [x] `master` con sesión 28 mergeada (fixture D6). Contrato D-23.2
      implementado en las tres tools + D-27.1 y D-28.1 formalizadas +
      drift documental corregido.
- [x] Esquemático corregido (sesión 19b): 0 errores, 4 warnings
      `lib_symbol_mismatch` (D-19b.1).
- [x] Fixture `tests/fixtures/despertador-routed/` regenerado por D6.
      NO tocar hasta el final.
- [ ] Colocación con coordenadas propias (no heredadas de D5/D6),
      variando controladamente el layout.

**Proyecto en disco:**
`/tmp/gui-test-project/despertador_inteligente.kicad_pro` (restaurado
por el humano antes del arranque — ver D-27.1 si hay drift).

---

## VERIFICACIONES ESPECÍFICAS DE D7 (mandatorias)

Estas 6 verificaciones son el punto principal de D7.

### V1. Log obligatorio de keepouts auto-generados

Sin cambios respecto a D5/D6. Después de cada `route_board`:
`get_zones(layer="B.Cu")`, contar `__kicadmcp_hc__*`, esperable 4
(ANT1 + 3× J1 NPTH).

### V2 REFORZADA EN TRES TOOLS

Sin cambios respecto a D6. `route_board` + `fill_zones` +
`add_zone(fill=True)` cada uno con V2 completo (mtime cambió,
`run_drc()` independiente coincide, sin `EXTERNAL_EDIT_DETECTED`
espurio). 3 corridas coincidentes por tool ratifica; divergencia →
**potencial regresión, F-D7-XX P0**.

### V3. Bandera roja — DETENER SI APARECE

Sin cambios respecto a D6. Interpretación Fase 3: potencial regresión
de sesión 27 (para `fill_zones`/`add_zone`) o sesión 24 (para
`route_board`).

### V4 EXPERIMENTO AISLADO DE D-26.1 (NUEVO EN D7)

**Este es el punto metodológico crítico de D7.** El brief D6 aplicó
D-26.1 pero el orden de fases contaminó el experimento. D7 lo hace
correctamente:

**Precondición mandatoria (D-28.1):** el plano GND debe crearse ANTES
de la colocación masiva de footprints (orden de D5, no de D6). No
invertir bajo ninguna circunstancia. Si el agente considera invertir,
`AskUserQuestion` obligatoria al arquitecto ANTES de ejecutar.

**Experimento (dos mediciones consecutivas, sin re-ruteo entre ellas):**

Después de la colocación completa de los 23 footprints con las nuevas
coordenadas (ver V6), sin `fill_zones()` explícito:

**V4.a — Baseline SIN `fill_zones()` explícito** (replica el error
metodológico de D5):

```
run_drc(min_severity="error")
```

Registrar:

```
## V4.a — Baseline DRC SIN fill_zones() explícito
- **Total errores:** X
- **por_tipo:** {...}
- **Violaciones individuales con hole_clearance/clearance/solder_mask_bridge:**
  <lista completa con formato controlado <tipo>|<pos>|<refs>|<severidad>>
```

**Predicción:** 4-6 violaciones fantasma (fill rancio, mismo patrón que
D5 tuvo: `hole_clearance` en pads con hole PTH cerca del borde del
fill + posible `solder_mask_bridge` en ANT1 si aplica).

**V4.b — Baseline CON `fill_zones()` explícito**:

Inmediatamente después de V4.a, correr:

```
fill_zones()
run_drc(min_severity="error")
```

Registrar V2 completo para `fill_zones()` (mtime, run_drc coincide,
sin espurio) y luego el baseline:

```
## V4.b — Baseline DRC CON fill_zones() explícito (D-26.1 aplicado)
- **Total errores:** X
- **por_tipo:** {...}
- **Violaciones individuales:** <lista>
- **Delta contra V4.a:** X_baseline_a - X_baseline_b
- **Violaciones eliminadas:** <lista de las que estaban en V4.a y no en V4.b>
```

**Predicción:** 0-1 violaciones no-triviales. Las violaciones de V4.a
que no aparecen en V4.b son las que D-26.1 elimina.

**Ratificación empírica de D-26.1 en D7:** el delta V4.a → V4.b es la
evidencia directa. Si V4.a tiene 4-6 violaciones fantasma y V4.b tiene
0-1, D-26.1 queda ratificado sin confusor. Si V4.a tiene 0 violaciones
(no aparece fill rancio), significa que el orden "plano antes de
colocar" es suficiente por sí solo y D-26.1 no aporta valor incremental
observable en este flujo — hallazgo importante que también hay que
documentar honestamente.

Para todas las lecturas de DRC posteriores en la sesión, comparar delta
contra V4.b (baseline canónico post-D-26.1) con el mismo formato de D5/D6.

### V5. Observación específica de F-D5-01 (isla GND sin vía al plano)

Sin cambios respecto a D6. Reportar explícitamente en el resumen final:

- ¿Apareció el patrón?
- Si sí: geometría similar a D5 (dos SMD en columna cerca del borde
  del plano)?
- Trigger para promoción a P2: 2 dogfoodings independientes reproducen
  el patrón. D5 tuvo (1), D6 no tuvo (0), D7 lo confirma o cierra.
  Si D7 lo tiene → 2/3 dogfoodings → promover a P2 investigación.

### V6 NUEVA — Coordenadas de colocación distintas de D5/D6

**Objetivo:** ratificar D-23.2 y D-26.1 bajo variación geométrica
controlada. D5 y D6 usaron literalmente el mismo layout, la evidencia
estadística es más débil de lo que parece.

**Restricciones (mandatorias):**

- Mismo footprint set (los 23 componentes del sch corregido).
- Mismo outline 44×44mm desde (125, 60) hasta (169, 104).
- Mismo sch (F8 no necesario).
- **Coordenadas de colocación distintas** de las de D5/D6.

**Guidelines para la colocación nueva (inclusivas, no restrictivas):**

- D-D3.1 vigente: conectores con drill mecánico (ANT1, J1, J2) ≥1.5-2mm
  del borde del outline.
- D-D4.1 vigente: `get_footprint_neighbors` inclusivo antes de mover
  cualquier footprint denso.
- Colocación que evite `courtyards_overlap = 0` en baseline V4.b.
- No forzar imitación de D5/D6 — el objetivo es varianza controlada, no
  optimización.

**Registrar en el reporte final la comparación de layout:**

```
| Métrica | D5 | D6 | D7 |
|---|---|---|---|
| Densidad promedio | ... | ... | ... |
| Distancia mínima entre pads de nets distintos | ... | ... | ... |
| Distancia ANT1 al borde | 2mm | 2mm | ... |
| Distancia J1 al borde | 2mm | 2mm | ... |
```

Comparaciones cualitativas (compacto vs disperso, alineado vs disperso)
también válidas.

### V7 NUEVA — Protocolo F-D6-01 (medición de re-ruteos parciales)

**Objetivo:** llegar a N=6-7 mediciones totales de re-ruteo parcial
para determinar si el costo depende del grado de interconexión del net
borrado.

**Metodología (dentro de la Fase 5 de cirugía, si aplica, o Fase 7
opcional):**

Elegir 2-3 nets del board con distinto grado de interconexión:

- Un net "hub" (muchas conexiones a otros pads, ej. GND si no es plano,
  o VCC): alta interconexión.
- Un net "puente" (2-3 pads, conecta islas): media interconexión.
- Un net "señal aislada" (2 pads, punto a punto): baja interconexión.

Para cada net elegido:

1. `delete_tracks_bulk(net="<net>", dry_run=True)` → registrar cantidad
   de tracks/vías que se borrarían.
2. `delete_tracks_bulk(net="<net>", dry_run=False)` → borrar.
3. Anotar tiempo pre-route.
4. `route_board(timeout_s=600)` → registrar `route_ms` de la re-ruta
   parcial.
5. Anotar tiempo post-route.
6. Verificar `err_post = 0`. Si no, cirugía normal y reportar.

Registrar tabla:

```
| Net | Grado | Tracks borrados | Vías borradas | route_ms | Errores post |
|---|---|---|---|---|---|
| <hub> | alto | ... | ... | ... | ... |
| <puente> | medio | ... | ... | ... | ... |
| <aislada> | bajo | ... | ... | ... | ... |
```

**Análisis en el resumen final:**

- Con las 2 mediciones de D5 (~9-10s) + 2 de D6 (110-112s) + 2-3 de D7
  → N=6-7 total.
- ¿El costo correlaciona con grado de interconexión (# conexiones a
  otros nets)? ¿Con tamaño (# tracks/vías del net original)? ¿Con
  capas involucradas? ¿O es ruido?
- **Trigger para cerrar F-D6-01 como variabilidad:** si N=6-7 no
  muestra patrón claro correlacional, cerrar la vigilancia y
  documentar el rango esperable (9s-112s hasta ahora) en
  `docs/CONTEXT.md` o `docs/specs/restricciones-kicad.md`.
- **Trigger para promoción a P2 investigación:** solo si N=6-7 muestra
  costo consistentemente >60s en re-ruteos parciales, lo que sería
  regresión operacional inaceptable respecto al piso histórico.

---

## PRECONDICIONES OPERACIONALES

Idénticas a D6:

1. `/tmp/gui-test-project/` restaurado desde el fixture
   `despertador-routed` (regenerado en D6). Aplicar D-27.1 si drift.
2. KiCad reiniciado limpio.
3. Sin symlink en `/tmp/kicad/` (cascada de 19e).
4. Env vars del server MCP en `~/.claude.json`.

Confirmar con `health()` antes de tocar nada.

---

## CAVEATS OPERACIONALES (heredados, respetar)

- **C1**. NO `add_keepout_zone` antes de `route_board`.
- **C2**. Patrón validado plano GND (fill=true en Fase 2).
- **C3**. `delete_tracks_bulk` con `dry_run=True` primero.
- **C4**. `NET_ASSIGNMENT_MISMATCH` como señal legítima.
- **C5**. Conectores con drill ≥1.5-2mm del borde (D-D3.1).
- **C6**. `get_footprint_neighbors` inclusivo (D-D4.1).
- **C7**. Refill obligatorio pre-baseline DRC (D-26.1) — aplicable
  después de V4.a en el experimento aislado.
- **C8**. Restore no destructivo del entorno GUI (D-27.1).
- **C9 NUEVO en D7**. **Cambios de orden de fases del brief requieren
  `AskUserQuestion`** (D-28.1). No invertir Fase 2 (plano antes de
  colocar) bajo ninguna circunstancia sin consultar.

---

## PUNTOS DE CONTACTO HUMANO

**H1 (asumido):** proyecto en disco, sch corregido, KiCad abierto, env
vars ok.

**H2 (condicional):** F8 si desincronización sch↔pcb. Esperable: NO.

**H3 (revert): NO EXISTE.**

**H4 (validación visual opcional):** renders intermedios.

**H5 (D-27.1):** `AskUserQuestion` obligatoria si el fixture vivo
requiere restore.

**H6 (D-28.1 NUEVO en D7):** `AskUserQuestion` obligatoria si el
agente considera cambiar el orden de fases del brief.

---

## FLUJO ESPERADO (tu plan de vuelo)

**Orden mandatorio respetando D-28.1:**

### Fase 1: Verificación de estado (5-10 min)

1. `health()` → ipc ok.
2. `run_erc()` → 0 errores, 4 warnings esperados.
3. `get_world_context(kind="pcb", max_tokens=4000)` → inventario.
4. F8 si necesario (esperable: NO).
5. Si el fixture vivo tiene ruteo/plano previo → D-27.1 restore no
   destructivo con `AskUserQuestion`.

### Fase 2: Contorno y plano GND (5-10 min)

**MANDATORIO ANTES DE FASE 3 — D-28.1 vinculante.**

6. `draw_board_outline(x_mm=125, y_mm=60, width_mm=44, height_mm=44)`.
7. `add_zone(net="GND", layer="B.Cu", bbox=[125,60,169,104], fill=true)`.
8. **Registrar V2-add_zone-1** de esta invocación.

### Fase 3: Colocación con coordenadas propias (25-35 min)

9. Plan breve de colocación en el chat, explicitando **variación
   geométrica** respecto a D5/D6 (compacto, disperso, otro patrón —
   criterio del agente, no imitación de D5/D6).
10. `get_footprint_neighbors` inclusivo (D-D4.1) para BT1, U4, J1, J2,
    ANT1 y cualquier otro footprint denso.
11. 23× `move_footprint` con coordenadas **distintas de D5/D6**.
12. `save_board()`.
13. Render de control opcional.

### Fase 3.5: **EXPERIMENTO AISLADO D-26.1 (V4.a + V4.b, MANDATORIO)**

14. **V4.a**: `run_drc(min_severity="error")` sin `fill_zones()` previo.
    Registrar formato controlado.
15. **V4.b**: `fill_zones()` explícito → registrar **V2-fill_zones-1** →
    `run_drc(min_severity="error")` → registrar delta V4.a → V4.b.

### Fase 4: Ruteo (5-10 min esperable)

16. Anotar mtime pre-route.
17. `route_board(timeout_s=600)`.
18. Anotar mtime post-route.
19. **V1**: log de keepouts.
20. **V2-route_board-1**: cross-check completo.
21. **V3**: chequear bandera roja.
22. **V4 delta**: comparar `run_drc()` post contra baseline V4.b.
23. **V5**: chequear F-D5-01 en `unconnected_items`.

### Fase 5: DRC + cirugía si hace falta (variable)

24. Delta V4 muestra violaciones nuevas → diagnóstico normal.
25. Re-ruteos completos: V1 + V2-route_board + V3 + V4 delta.

### Fase 5.5: **PROTOCOLO F-D6-01 (V7, MANDATORIO si posible)**

26. Elegir 2-3 nets con distinto grado de interconexión (ver V7).
27. Para cada uno: `delete_tracks_bulk(dry_run=True)` → registrar →
    `delete_tracks_bulk(dry_run=False)` → `route_board` → registrar
    `route_ms` y `err_post`.
28. Compilar tabla V7 con las 3 mediciones.

### Fase 5.7: V2 explícito para tools no ejercitadas 3/3 naturalmente

29. Si `fill_zones` no acumuló 3/3 corridas naturales → forzar
    `fill_zones()` explícitos hasta llegar a 3.
30. Idem `add_zone(fill=True)` con invocaciones de test menores +
    `delete_zone` al final.

### Fase 6: Cierre (10 min)

31. Render final.
32. `export_manufacturing()` → gerbers G3.
33. `export_bom()`.
34. **Actualizar fixture** SOLO SI D7 sale verde con las nuevas
    coordenadas: copiar los 4 archivos a `tests/fixtures/despertador-routed/`.
    README con "versión D7, sesión 29, hash <commit>". **Nota:** el
    fixture cambia el layout (era D6, ahora D7); esto puede afectar
    tests existentes que dependan de coordenadas específicas.
    `AskUserQuestion` obligatoria antes de actualizar el fixture si
    hay dudas sobre impacto en tests.

### Fase 7 (opcional, si sobra tiempo)

35. Tests operacionales pendientes.

---

## DISCIPLINA DE CONTEXTO

Delta > mundo con focus > mundo completo. Renders con criterio.
Reportar al final: llamadas por tool, tokens totales estimados, tiempo
por fase, contactos humanos, comparación con D3/D4/D5/D6.

---

## REGLAS PROHIBITIVAS (VIOLARLAS INVALIDA EL DOGFOOD)

1. **NO editar el repo de kicad-mcp.** Toda falla → registrar.
2. **NO manipular archivos por fuera de las tools.**
3. **NO invocar `kicad-cli` directo** para bypass.
4. **NO editar `~/.claude.json`** durante la sesión.
5. **NO reiniciar KiCad si crashea (R11)** sin registrar primero.
6. **NO omitir V1/V2/V3/V4/V5/V6/V7** — son el punto principal de D7.
7. **NO forzar hallazgos.** Un D7 verde es evidencia positiva de Fase 3,
   no un fracaso.
8. **NO omitir D-26.1** en Fase 3.5 (V4.a + V4.b es el experimento
   crítico).
9. **NO cambiar el orden de fases del brief** sin `AskUserQuestion`
   (D-28.1 vinculante). Fase 2 SIEMPRE antes de Fase 3.
10. **NO imitar exactamente las coordenadas de D5/D6.** El objetivo de
    V6 es variación geométrica controlada.

---

## LOG DE FRICCIONES

Crear `/tmp/dogfood7-fricciones.md` al inicio. Formato:

```
## F-D7-NN — Título corto
- **Qué pasó:** ...
- **Qué esperaba:** ...
- **Workaround:** ...
- **Costo:** [bajo/medio/alto]
- **Severidad:** [info/warn/bloqueante]
```

Además, las entradas V1-N, V2-N, V3-N, V4-N (con V4.a y V4.b), V5-N,
V6, V7-N son evidencia obligatoria.

Sección **Aciertos** al final: 3-5 cosas del server que funcionaron
mejor que en D5/D6.

---

## RESUMEN FINAL (última sección del log)

Responder **explícitamente** las 17 preguntas siguientes:

1. **¿Placa completa?** ERC, colocado, ruteado, DRC (delta vs V4.b),
   gerbers, plano GND, keepouts auto.

2. **Tabla comparativa D2-D7:**

   | Métrica | D2 | D3 | D4 | D5 | D6 | D7 |
   |---|---|---|---|---|---|---|
   | Nota | 7.5 | 8.5 | 4.5 | 9.5 | 9.7 | ? |
   | Fricciones bloqueantes | 0-1 | 1 | 1 | 0 | 0 | ? |
   | `route_ms` corrida completa | 925s | 53s | 36.7s | 128.8s | 32.4s | ? |
   | Contactos humanos | 5 | 2 | 0 | 0 | 1 | ? |
   | Errores DRC post-route | 53 | 0 | 42 | 1 | 0 | ? |
   | Baseline V4 pre-route (no-triviales) | N/A | N/A | N/A | 6 | 0 | ? |

3. **Estado del contrato D-23.2 en 3 tools:**
   - V2 corridas coincidentes por tool: route_board X/3, fill_zones X/3,
     add_zone X/3.
   - ¿Divergencia detectada? En qué tool?
   - Acumulado en producción: X/(15 + N) verde.

4. **V4 EXPERIMENTO AISLADO D-26.1 (el punto crítico de D7):**
   - V4.a (sin `fill_zones()`) violaciones no-triviales: X (predicción:
     4-6).
   - V4.b (con `fill_zones()`) violaciones no-triviales: X (predicción:
     0-1).
   - Delta V4.a → V4.b: X (predicción: el conjunto de las violaciones
     de fill rancio que D-26.1 elimina).
   - **¿Ratifica D-26.1 empíricamente sin confusor?** Sí/no + razón.
   - Si V4.a = 0: hallazgo importante (D-26.1 no aporta valor
     incremental observable en este flujo con plano fresco), documentar.

5. **V5 Estado de F-D5-01:**
   - ¿Apareció el patrón?
   - Si sí: geometría similar a D5?
   - Trigger de promoción a P2: 2/3 dogfoodings independientes cumplen
     (D5=sí, D6=no, D7=?). Si D7 sí → promover a P2.

6. **V6 Layout con coordenadas propias:**
   - Tabla comparativa densidad/distancia mínima/distancia al borde
     vs D5/D6.
   - Caracterización cualitativa (compacto, disperso, patrón).
   - Cualquier hallazgo geométrico relevante (`courtyards_overlap`,
     márgenes ajustados, etc.).

7. **V7 Protocolo F-D6-01:**
   - Tabla con 2-3 mediciones (net, grado de interconexión, tracks/vías
     borrados, `route_ms`, errores post).
   - Análisis con N=6-7 total (2 D5 + 2 D6 + 2-3 D7): ¿patrón
     correlacional identificable? ¿Con interconexión, tamaño, capas?
   - Recomendación: cerrar F-D6-01 como variabilidad, o promover a P2
     investigación, o mantener P3 vigilancia con más mediciones.

8. **Estado de F-D4-02 y otras fricciones históricas:**
   - F-D4-02: sigue ratificado?
   - F-D3-01/F-D3-03: no aparecieron?
   - F-D3-04: `get_footprint_neighbors` sigue ahorrando tiempo?
   - F-D4-01: sigue pendiente P3 sin novedad?

9. **Fricciones nuevas de D7 (F-D7-XX)**, si las hay.

10. **`route_ms` corridas completas** — comparar con D3-D6.

11. **`get_footprint_neighbors` en acción**: ¿cuántas veces? ¿Ahorró
    tiempo? ¿Detectó algo con las nuevas coordenadas que D5/D6 no
    ejercitaron?

12. **Nota /10 con justificación** — objetivo ≥9.

13. **¿Convergimos hacia el criterio de cierre de Fase 3?**
    - Verde (≥9, 0 P0/P1 nuevos, V3 no activada, V2 3/3 por tool,
      D-26.1 aislado sin confusor, V6 con layout distinto exitoso, V7
      con conclusión sobre F-D6-01): **3 verdes consecutivos —
      criterio cumplido.** Iniciar preparación Fase 4 (sesión 30).
    - Amarillo (8-8.9, 1-2 P1, V3 no activada): sesión de fix +
      próximo dogfooding.
    - Rojo (V3 activada, P0 nuevo, nota <8): investigación mandatoria.

14. **Evidencia V1-V7 consolidada:**
    - V1: 4 keepouts constantes.
    - V2 3/3 por las 3 tools.
    - V3 no activada.
    - V4 (V4.a + V4.b): D-26.1 aislado.
    - V5 F-D5-01: apareció?
    - V6 layout: variación verificada.
    - V7 F-D6-01: conclusión.

15. **Si D7 verde, ¿el fixture se actualiza a versión D7?** Impacto
    en tests existentes que dependan de coordenadas específicas — si
    hay dudas, `AskUserQuestion`.

16. **¿Qué falta para uso semanal?** (la pregunta persistente).
    Esperable: "nada crítico. P1 solder mask ANT1 sigue con
    investigación pendiente y puede quedar como deuda arrastrada a
    Fase 4."

17. **¿Recomendación explícita para sesión 30?**
    - Verde D7 (3er verde consecutivo) → **iniciar preparación Fase 4**
      con el arquitecto. Cerrar Fase 3.
    - Amarillo D7 → sesión de fix quirúrgico + D7' con misma placa
      antes de avanzar.
    - Rojo D7 → investigación mandatoria antes de continuar.

---

## Cierre esperado

D7 cerrado con:

- Nota /10 documentada.
- Placa fabricable con delta V4 = 0 violaciones nuevas.
- V1-V7 completas.
- Log de fricciones completo.
- Fixture actualizado con nuevo layout (si verde y sin impacto en tests).
- Recomendación para sesión 30 explícita.

Escenarios posibles:

- **Verde (≥9, 3 verdes consecutivos):** criterio de cierre de Fase 3
  cumplido. Sesión 30 inicia preparación Fase 4 (release, features,
  escalada de complejidad — decisión estratégica del arquitecto con
  esta evidencia).
- **Amarillo:** ciclo continúa. Sesión de fix quirúrgico + D7'.
- **Rojo:** investigación mandatoria. Sospechar regresión de sesión
  27/28 o consolidación reciente.

**Recordatorio operacional de Fase 3 avanzada:** el objetivo es
RATIFICAR con evidencia metodológicamente limpia (aislamiento D-26.1),
no descubrir. Un D7 verde con V4.a → V4.b claro cierra el ciclo de
Fase 3 con confianza. **No forzar hallazgos, no escalar complejidad, y
NO invertir orden de fases sin `AskUserQuestion`.**

Traeme el reporte + log de fricciones cuando termine.
