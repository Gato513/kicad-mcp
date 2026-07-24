# Dogfooding 5 — Primera ratificación de Fase 3 (sesión 25)

**QUÉ ES:** sesión de USO, no de desarrollo. Mismas reglas que
D1/D2/D3/D4: **prohibido editar el repo de kicad-mcp**; toda falla se
REGISTRA como fricción en el log, no se arregla. **Es el primer
dogfooding de la Fase 3 (consolidación / aumento progresivo de
confianza) del proyecto.**

**Cambio explícito de propósito respecto a D1-D4:** en Fase 2 (D1-D4)
el objetivo era descubrir bugs — un dogfooding que encontraba P0/P1
nuevos era valioso. En Fase 3 el objetivo se invierte: **ratificar
que los cierres del ciclo de hardening realmente aguantan en
producción**. Un D5 verde es evidencia positiva de convergencia, no
un dogfooding "sin hallazgos". La ausencia de fricciones es
resultado, no fracaso.

**Objetivo primario:** ratificar que F-D4-02 quedó cerrado por
sesión 24 (Opción X, contrato D-23.2, ADR-0012). Objetivo secundario:
convertir en evidencia estadística el patrón que el test de
regresión mostró en 2/2 corridas contra Freerouting real.

**Variable controlada:** MISMA placa que el D3 y D4 (despertador
ATtiny85 wearable, 24 footprints, mismo sch corregido, mismo fixture
regenerado). Cualquier delta de nota vs D3 se atribuye directo a la
sesión 24. Cualquier delta negativo vs el test de regresión de
sesión 24 se **sospecha regresión hasta que se pruebe lo contrario**.

**Objetivo nota:** ≥9/10. D1=5, D2=7.5, D3=8.5, D4=4.5 (parada V3).
Con contrato D-23.2 aguantando en producción, D5 debería converger
más rápido que D3 y sin fricciones bloqueantes internas.

**Timeboxing:** 2h target, 2.5h techo. Con el stack maduro y el
contrato reforzado, D5 debería converger más rápido que D3 (que ya
converjía en 2h). Si a las 2.5h no estás exportando gerbers, parar y
reportar el estado.

---

## ENTREGABLES

1. `/tmp/dogfood5-fricciones.md` — mismo formato F-D5-NN, escrito EN
   EL MOMENTO, no al final.
2. Placa completa: PCB colocado, plano GND, ruteado, DRC coincidente
   con baseline (ver V4 abajo), gerbers G3, BOM, fixture actualizado
   (versión D5) en `tests/fixtures/despertador-routed/` si D5 sale
   verde.
3. Resumen final con nota /10 + comparación D2/D3/D4/D5 + estado de
   la ratificación (¿F-D4-02 cerrado en producción? ¿ratifica el
   patrón para generalización a `fill_zones`/`add_zone`?).

---

## ESTADO INICIAL DEL PROYECTO

- [x] `master` con sesión 24 mergeada (commit 972fa80). Contrato
      D-23.2 implementado en `route_board`.
- [x] Esquemático corregido (sesión 19b): 0 errores, 4 warnings
      `lib_symbol_mismatch` aceptados (D-19b.1 — NO ejecutar "Update
      Symbols from Library").
- [x] F8 sync sch→pcb hecho (sesión 19b y confirmado en D3).
- [x] Fixture `tests/fixtures/despertador-routed/` — baseline
      conocido, no tocado desde D3.
- [x] Server MCP con contrato D-23.2 en producción, código de error
      `POST_ROUTE_PERSIST_FAILED` disponible.
- [ ] Todo lo demás (outline, plano, colocación, ruteo, DRC, gerbers)
      es trabajo tuyo, arrancando desde board vacío como D3/D4.

**Proyecto en disco:**
`/tmp/gui-test-project/despertador_inteligente.kicad_pro` (restaurado
por el humano antes del arranque).

---

## VERIFICACIONES ESPECÍFICAS DE FASE 3 (mandatorias en D5)

Estas 4 verificaciones son el punto principal de D5. Cada una debe
reportarse en el log de fricciones, **incluso si no hay fricción** —
son evidencia estadística de ratificación del ciclo de hardening.

### V1. Log obligatorio de keepouts auto-generados
Después de CADA `route_board`, correr:
```
get_zones(layer="B.Cu")
```
Contar los keepouts con prefijo `__kicadmcp_hc__` y registrar:

```
## V1-N — Keepouts auto-generados post-route N
- **Cantidad:** X
- **Esperado en placa despertador:** 4 fijos (ANT1 + 3× J1 NPTH)
- **Coincide:** sí / no
- **Si no:** listar refs
```

Ratificado en D4 sin fricción. En D5 sigue siendo evidencia positiva
esperada.

### V2 REFORZADA. Cross-check contrato D-23.2 (fidelidad al vivo)

Sesión 24 implementó el contrato "cuando `route_board` termina OK,
disco == memoria == `err_post` reportado". D5 lo ratifica en
producción con **verificación reforzada** respecto al V2 de D4.

Después de las **primeras 3 invocaciones** de `route_board`, correr
inmediatamente y registrar:

1. `run_drc(min_severity="error")` — debe coincidir con
   `route_board.drc.err_post` en total y `por_tipo`. (V2 original de
   D4.)
2. Verificar que **no aparecen operaciones subsiguientes con
   `EXTERNAL_EDIT_DETECTED`** — evidencia de que el snapshot de
   mtimes se registró correctamente post-save (hallazgo #31 de
   sesión 24).
3. Verificar que **el mtime del `.kicad_pcb` cambió** entre pre-route
   y post-route — evidencia de que `save_board()` interno se
   ejecutó (assertion #5 opcional del test de regresión de sesión
   24, ahora obligatoria en D5).

Registrar:

```
## V2-N — Cross-check D-23.2, corrida N
- **route_board.drc.err_post:** X (por_tipo: {...})
- **run_drc() independiente:** Y (por_tipo: {...})
- **Coinciden total y por_tipo:** sí / no
- **mtime pre-route:** T1
- **mtime post-route:** T2 (cambió: sí / no)
- **Aparece EXTERNAL_EDIT_DETECTED en lecturas posteriores:** no / sí
```

Si coinciden 3/3 con mtime cambiado y sin `EXTERNAL_EDIT_DETECTED`
espurio → dejar de hacer el cross-check. Ratifica el contrato D-23.2
en producción. Si divergen alguna vez → **fricción P0 F-D5-XX +
parar sesión + reportar como potencial regresión de sesión 24**.

### V3. Bandera roja obligatoria — DETENER SI APARECE

Cualquiera de estas condiciones post-route es señal de que sesión 24
NO cerró como pensábamos:

- Violación DRC con `clearance=0.0000mm` vs Zone GND.
- Violación DRC con `hole_clearance=0.0000mm` vs Zone GND.
- `route_board.drc.err_post` no coincide con `run_drc()`
  independiente inmediato SIN `save_board()` manual.
- `POST_ROUTE_PERSIST_FAILED` disparado inesperadamente.

Si aparece cualquiera:

1. **NO seguir el ruteo.**
2. Registrar fricción **F-D5-XX con severidad `bloqueante` P0** —
   incluir el JSON completo de `route_board`, `get_zones`, `run_drc`
   pre y post.
3. Guardar el board (`save_board`).
4. Terminar sesión y reportar al arquitecto.

**Interpretación en Fase 3:** V3 activada en D5 se sospecha
regresión de sesión 24 hasta que se pruebe lo contrario. Es
información valiosa aunque signifique nota <5 — pero no forzar V3
si no aparece: no confundir rigor con paranoia.

### V4 NUEVA. Baseline dinámico + delta (D-24.2)

La placa despertador tiene ~5 errores DRC residuales
post-route no relacionados con F-D4-02 (courtyards, edge clearance
del outline, silkscreen). Sesión 24 los observó en el test de
regresión pero no los enumeró. D5 los caracteriza por primera vez.

**Fase 1 obligatoria de baseline** (antes de tocar nada del ruteo):
después de outline + plano + colocación pero ANTES de `route_board`,
correr:

```
run_drc(min_severity="error")
```

Y registrar en el log:

```
## V4 — Baseline DRC pre-route
- **Total errores:** X
- **por_tipo:** {"courtyards_overlap": N, "edge_clearance": M, ...}
- **Violaciones individuales (mandatorio, formato controlado):** una
  línea por violación con `<tipo>|<pos>|<refs>|<severidad>`. Ejemplo:
  `courtyards_overlap|(100.3,72.1)|C5,U1|error`. NO exportar el JSON
  completo de `run_drc()` — solo estos 4 campos por violación. La
  identidad importa porque delta bruto (count-only) engaña: si
  desaparece una y aparece otra distinta del mismo tipo, la cuenta
  no cambia pero hay hallazgo nuevo.
```

**Después de cada `route_board`**, comparar `run_drc()` post contra
baseline:

```
## V4-N — Delta contra baseline, corrida N
- **Total pre-route (V4 baseline):** X
- **Total post-route:** Y
- **Delta bruto:** Y - X
- **Violaciones nuevas (no en baseline):** lista
- **Violaciones desaparecidas (en baseline pero no post):** lista
- **Violaciones persistentes:** lista (baseline ∩ post)
```

**Solo las violaciones nuevas cuentan como hallazgos.** Las
persistentes son residual esperado, las desaparecidas indican que
el ruteo mejoró incidentalmente algo (poco común, pero registrar).

**Si las violaciones residuales son estables en las 3 primeras
corridas** (mismo conjunto por identidad `<tipo>|<pos>|<refs>`, no
solo por cuenta), al final del reporte proponer una **allowlist
candidata textual** (dentro del reporte, NO como artefacto
commiteado en el repo): lista de violaciones que pueden ignorarse
como "residuales esperados en despertador post-route". Esta
allowlist es **propuesta para futuros dogfoodings**, no vinculante
todavía — según D-24.2 hace falta ratificación estadística en 2-3
sesiones antes de convertirla en fixture / test canario. NO
commitear archivos con la allowlist en esta sesión. Solo texto en
el reporte.

---

## PRECONDICIONES OPERACIONALES

Idénticas a D4:

1. `/tmp/gui-test-project/` restaurado desde Desktop o desde el
   fixture `despertador-routed`.
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
Solo POST-route. Sin cambios respecto a D3/D4.

### C2. Patrón validado para plano GND
Crear y fillar el plano GND ANTES de `route_board`, sobre un board
sin cobre. Freerouting NO respeta el plano como exclusión para nets
ajenos (D-19.1 v6), pero el refill posterior + `enforce_hole_clearance`
+ persistencia (D-23.2, sesión 24) arreglan el resultado. `timeout_s
≥ 300` (D3 tomó 53s; D4 tomó 36.7s; margen amplio).

### C3. `delete_tracks_bulk` con `dry_run=True` primero
Si necesitás re-rutear una net específica.

### C4. `NET_ASSIGNMENT_MISMATCH` como señal legítima
Si aparece, replanificar coordenadas — no bug.

### C5. Conectores con agujeros mecánicos ≥1.5-2mm del borde (D-D3.1)
Verificar con `get_footprint_neighbors(ref, radius_mm=3.0,
max_tokens=3000)` antes de posición final.

### C6. `get_footprint_neighbors` inclusivo (D-D4.1)
Aplicar a cualquier footprint denso o con incertidumbre geométrica,
no solo conectores con drill mecánico. Costo bajo, evita
`courtyards_overlap`.

---

## PUNTOS DE CONTACTO HUMANO

**H1 (asumido, ya hecho):** proyecto en disco, sch corregido, KiCad
abierto, env vars ok.

**H2 (condicional):** F8 si `get_world_context(kind="pcb")` revela
que los footprints del sch corregido NO están sincronizados en el
PCB. Esperable: NO se necesita.

**H3 (revert): NO EXISTE.** Cerrado por D-V3.1 (sesión 18) y
ratificado en D3/D4. Si aparece → fricción grave.

**H4 (validación visual opcional):** renders intermedios si querés
segunda opinión. Costo ~11s c/u.

---

## FLUJO ESPERADO (tu plan de vuelo)

Casi idéntico al D4 con dos diferencias: **V4 baseline dinámico en
Fase 1** y **V2 reforzado con mtime + sin EXTERNAL_EDIT_DETECTED**.

### Fase 1: Verificación de estado + baseline (10-15 min)
1. `health()` → ipc ok.
2. `run_erc()` → confirmar 0 errores, 4 warnings esperados.
3. `get_world_context(kind="pcb", max_tokens=4000)` → inventario.
4. F8 si es necesario (esperable: NO).

### Fase 2: Contorno y plano GND (5-10 min)
5. `draw_board_outline(bbox=<40-50mm cuadrado>)`. En D3/D4 fue 44×44.
6. `add_zone(net="GND", layer="B.Cu", bbox=<mismo bbox>, fill=true)`.

### Fase 3: Colocación con reconocimiento inclusivo (25-35 min)
7. Plan breve de colocación en el chat.
8. **`get_footprint_neighbors` inclusivo** (D-D4.1): aplicar a
   conectores con drills (J1, J2), footprints grandes (BT1, U4), Y
   también a pasivos densos si hay duda geométrica.
9. `move_footprint(ref, x, y)` × 24.
10. `save_board()`.
11. Render de control.

### Fase 3.5: **BASELINE DINÁMICO V4 (mandatorio, 3-5 min)**
12. `run_drc(min_severity="error")` sobre estado colocado + plano
    filleado, sin ruteo.
13. Registrar V4 completo en `/tmp/dogfood5-fricciones.md`: total,
    `por_tipo`, violaciones individuales.

### Fase 4: Ruteo (5-10 min esperable)
14. Anotar mtime pre-route del `.kicad_pcb`.
15. `route_board(timeout_s=600)`.
16. Anotar mtime post-route.
17. **V1**: log de keepouts `__kicadmcp_hc__` (obligatorio).
18. **V2 REFORZADO** (primera vez): cross-check DRC + mtime cambió
    + no aparece `EXTERNAL_EDIT_DETECTED`.
19. **V3**: chequear bandera roja. Si aparece, parar y reportar.
20. **V4 delta**: comparar `run_drc()` post contra baseline.

### Fase 5: DRC + cirugía si hace falta (variable)
21. Si el delta V4 muestra **violaciones nuevas** (no en baseline)
    → diagnóstico normal (get_tracks, delete_track, add_track).
22. Cualquier re-ruteo: repetir V1 + V2 + V3 + V4 delta.

### Fase 6: Cierre (10 min)
23. Render final.
24. `export_manufacturing()` → gerbers G3.
25. `export_bom()`.
26. **Actualizar fixture** SOLO SI D5 sale verde: copiar
    `.kicad_pcb`, `.kicad_pro`, `.kicad_sch`, `.kicad_prl` a
    `tests/fixtures/despertador-routed/`. Actualizar README con
    "versión D5, sesión 25, hash <commit>".

### Fase 7 (opcional, si sobra tiempo)
27. **Test explícito de `add_keepout_zone` POST-route** (D-19c.1):
    agregar keepout circular bajo ANT1 con 12 vértices. Registrar si
    el DRC cambia.
28. **Test explícito de `delete_tracks_bulk`**: borrar tracks de una
    net con `dry_run=True` primero, luego `dry_run=False`.

---

## DISCIPLINA DE CONTEXTO

Delta > mundo con focus > mundo completo. Renders con criterio (~11s
c/u). Reportar al final: llamadas por tool, tokens totales estimados,
tiempo por fase, contactos humanos, comparación con D3/D4.

---

## REGLAS PROHIBITIVAS (VIOLARLAS INVALIDA EL DOGFOOD)

1. **NO editar el repo de kicad-mcp.** Toda falla → registrar como
   fricción, NUNCA arreglar.
2. **NO manipular archivos por fuera de las tools.**
3. **NO invocar `kicad-cli` directo** para bypass.
4. **NO editar `~/.claude.json`** durante la sesión.
5. **NO reiniciar KiCad si crashea (R11)** sin registrar primero.
6. **NO omitir V1/V2/V3/V4** — son el punto principal de D5.
7. **NO forzar hallazgos** que no aparecen naturalmente. Un D5 verde
   es evidencia positiva de Fase 3, no un fracaso.

---

## LOG DE FRICCIONES

Crear `/tmp/dogfood5-fricciones.md` al inicio. Formato:

```
## F-D5-NN — Título corto
- **Qué pasó:** ...
- **Qué esperaba:** ...
- **Workaround:** ...
- **Costo:** [bajo/medio/alto]
- **Severidad:** [info/warn/bloqueante]
```

Además, las entradas V1-N, V2-N, V3-N, V4-N (verificaciones), aunque
sean "todo OK sin fricción" — son evidencia obligatoria.

Sección **Aciertos** al final: 3-5 cosas del server que funcionaron
mejor que en D3/D4.

---

## RESUMEN FINAL (última sección del log)

Responder **explícitamente** las 14 preguntas siguientes:

1. **¿Placa completa?** ERC ✓, colocado %, ruteado %, DRC (delta vs
   baseline V4), gerbers ✓/✗, plano GND ✓, keepouts auto ✓.

2. **Tabla comparativa D2 vs D3 vs D4 vs D5:**

   | Métrica | D2 | D3 | D4 | D5 |
   |---|---|---|---|---|
   | Nota | 7.5/10 | 8.5/10 | 4.5/10 | ? |
   | Fricciones bloqueantes | 0-1 | 1 externa | 1 P0 interna | ? |
   | `route_ms` | 925s | 53s | 36.7s | ? |
   | Contactos humanos | 5 | 2 | 0 | ? |
   | Errores DRC "introducidos" post-route (delta V4) | N/A | 0 | 42 (obsoletos) | ? |
   | mtime cambia post-route | N/A | N/A | N/A | ? |
   | `EXTERNAL_EDIT_DETECTED` espurio | N/A | N/A | N/A | ? |

3. **Estado de F-D4-02 (el gran cierre):**
   - ¿V2 reforzado 3/3? ¿Contrato D-23.2 aguantó en producción?
   - ¿mtime cambió en las 3 corridas?
   - ¿Apareció `EXTERNAL_EDIT_DETECTED` espurio en operaciones
     posteriores?
   - ¿Hay evidencia de regresión respecto al test de sesión 24?

4. **Estado de otras fricciones históricas:**
   - F-D3-01/F-D4-02 (ya cubierto en 3).
   - F-D3-03: revocada por sesión 24, no debería aparecer.
   - F-D3-04: ¿`get_footprint_neighbors` sigue ahorrando tiempo?
   - F-D4-01 (R13, `get_world_context(kind="sch")` con
     `#PWR*/#FLG*`): sigue siendo pendiente.

5. **V4 baseline dinámico:** ¿los residuales fueron estables por
   identidad (`<tipo>|<pos>|<refs>`) en 3/3 corridas? ¿Cuáles son
   (`por_tipo` + ejemplos con formato controlado)? ¿Se puede
   proponer allowlist candidata **textual dentro del reporte** (no
   commitear artefactos ahora)?

6. **Fricciones nuevas de D5 (F-D5-XX)**, si las hay, con propuesta.

7. **`route_ms` esta placa** — comparar con D3 (53s) y D4 (36.7s).
   Esperable similar por no-determinismo de Freerouting.

8. **`get_footprint_neighbors` en acción** (D-D4.1 aplicado
   inclusivamente): ¿cuántas veces se usó? ¿Ahorró tiempo?
   ¿Aparecieron `courtyards_overlap` (esperable: no)?

9. **Nota /10 con justificación** — objetivo ≥9. Justificar cada 0.5.

10. **¿Convergimos hacia el próximo paso de Fase 3?**
    - Verde (≥9, 0 P0/P1 nuevos, V3 no activada, V2 reforzado 3/3):
      convergencia parcial. Sesión 26 = fix P1 solder mask ANT1.
    - Amarillo (8-8.9, 1-2 P1, V3 no activada): sesión de fix +
      próximo dogfooding con la misma placa antes de avanzar.
    - Rojo (V3 activada, P0 nuevo, nota <8): investigación mandatoria.
      Sospechar regresión de sesión 24 hasta que se pruebe lo
      contrario.

11. **Evidencia V1/V2/V3/V4 consolidada:**
    - V1: total keepouts auto por route_board (esperable: 4
      constantes).
    - V2 reforzado: 3/3 con mtime cambio y sin EXTERNAL_EDIT_DETECTED
      espurio (esperable: sí).
    - V3: activada? (esperable: NO).
    - V4: residuales estables + allowlist candidata (esperable: sí,
      ~5 errores no-F-D4-02).

12. **¿Ratifica el patrón D-23.2 para generalización a `fill_zones`
    y `add_zone(fill=True)`?** Con base en 3 corridas exitosas de
    V2 reforzado + delta V4 sin nuevos hallazgos, el patrón puede
    considerarse ratificado y la sesión 27 (generalización) puede
    proceder.

13. **¿Actualizado el fixture `tests/fixtures/despertador-routed/`?**
    (Solo si D5 sale verde.)

14. **¿Qué falta para uso semanal?** La pregunta persistente. Si la
    respuesta es "nada crítico, solo pendientes de secuencia Fase 3
    (P1 solder mask + generalización D-23.2)", esa es la señal de
    convergencia.

---

## Cierre esperado

D5 cerrado con:
- Nota /10 documentada.
- Placa fabricable con delta V4 = 0 violaciones nuevas.
- V1/V2/V3/V4 completas.
- Log de fricciones completo.
- Allowlist candidata **propuesta textualmente en el reporte** (si
  residuales estables por identidad, no solo por cuenta) — sin
  commitear artefactos, ratifica en D6/D7.
- Fixture actualizado (si verde).

Escenarios posibles según resultado:

- **Verde:** avanzar a sesión 26 (fix P1 solder mask ANT1). Después
  sesión 27 (generalización D-23.2). Después sesión 28 = D6.
- **Amarillo:** ciclo continúa con misma placa. Sesión de fix
  quirúrgico + próximo dogfooding antes de avanzar en la secuencia.
- **Rojo:** investigación mandatoria antes de D6. Sospechar
  regresión de sesión 24, revisar el test de regresión bajo lupa.

**Recordatorio operacional de Fase 3:** el objetivo es RATIFICAR,
no descubrir. No forzar hallazgos donde no los hay. No escalar
complejidad. Reportar evidencia estadística de estabilidad — o de
su ausencia — con el mismo rigor que se aplicó en Fase 2 para
descubrir bugs.

Traeme el reporte + log de fricciones cuando termine. D5 es la
primera medición formal de si Fase 3 va a converger tan bien como
esperamos.
