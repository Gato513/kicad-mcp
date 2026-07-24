# Dogfooding 3 — Log de fricciones

Placa: despertador_inteligente (ATtiny85 wearable, 24 footprints). Sesión de
USO — prohibido editar el repo de kicad-mcp; toda falla se registra, no se
arregla. Objetivo ≥8/10 (D1=5/10, D2=7.5/10).

Inicio: 2026-07-23.

## Estado inicial verificado (Fase 1 pre-vuelo, antes de mutar nada)

- `health()`: server ok, kicad-cli 10.0.4, IPC ok, PCB Editor abierto,
  proyecto `gui-test-project` ok.
- `run_erc()`: 0 errores, 4 warnings `lib_symbol_mismatch` (U1/U2/U3/U4) —
  esperados, aceptados (D-19b.1), no tocar.
- `get_world_context(kind="pcb")`: 24 componentes, topología corregida de
  19b confirmada (U1.5=/NSS, /MOSI /MISO /SCK separados, /SCL limpio,
  U2.INT/U3.~INT/U3.VLED+ No-Connect). F8 ya hecho — H2 no necesario.
- Sin outline, sin zonas de cobre. Componentes en cluster crudo de import.

---

## Fricciones

### F-01 — `add_zone`/`fill_zones` no respeta hole clearance contra pads PTH/NPTH ajenos
- **Qué pasó:** Tras colocar los 24 footprints y correr `run_drc()`, aparecieron
  4x `hole_clearance` + 1x `clearance` + 1x `solder_mask_bridge` — todos en
  ANT1 (pad PTH `Net-(ANT1-A)`) y en los 3 agujeros NPTH mecánicos de J1
  (Tag-Connect). El plano GND en B.Cu (creado con `add_zone(bbox=<board
  completo>, fill=true)` en Fase 1, ANTES de colocar componentes) quedó con
  clearance **0.0000mm** contra esos agujeros — un short físico real (GND
  puenteado a la antena) si se fabricara así.
- **Qué esperaba:** que el fill de zona respetara automáticamente el hole
  clearance rule (0.25mm) y el clearance de net (0.2mm) contra CUALQUIER
  pad de otro net, igual que lo hace un `Ctrl+B` interactivo de KiCad. Y de
  hecho lo hace correctamente para los pads SMD de otros nets de J1
  (+3V3/SCK/MOSI/MISO/GND) — el patrón apunta a que el fallo es específico
  de pads con **agujero real** (PTH/NPTH), no de todos los pads ajenos.
- **Intento 1 (descartado):** re-`fill_zones()` sin cambiar geometría — no
  cambió nada, mismo resultado (0.0000mm). Descarta que fuera un fill
  simplemente stale por el reordenamiento de footprints.
- **Workaround (con tools, sin editar el repo):** `delete_zone` + recrear la
  zona con `add_zone(polygon=...)` en vez de `bbox`, tallando dos muescas
  rectangulares desde los bordes del board (ambos hazards caían cerca de un
  borde, lo que hizo viable la muesca sin necesitar un polígono con
  agujero interior): una de 6x6mm sobre ANT1 (entrando desde el borde
  superior) y otra de 8x5mm sobre los 3 agujeros de J1 (entrando desde el
  borde derecho). `run_drc()` post-fix: 0 errores de hole_clearance/
  clearance/solder_mask_bridge — quedan solo los 56 `unconnected_items`
  esperables pre-ruteo.
- **Costo:** medio — 1 ronda de diagnóstico (leer DRC con cuidado, notar el
  patrón PTH/NPTH vs SMD), + get_component_detail(J1) para coords exactas
  de los agujeros NPTH, + delete_zone/add_zone con polígono a mano
  (geometría calculada, no asistida por ninguna tool). ~10 min.
- **Severidad:** warn (no bloqueante — hay workaround limpio dentro de las
  tools existentes) pero el defecto de fondo es serio: un usuario que no
  revise DRC antes de exportar gerbers fabricaría una placa con GND
  puenteado a la antena. Candidato a fix real en 20b: `fill_zones` debería
  respetar hole clearance contra TODO pad con drill, no solo pads SMD.

### F-02 — `KICAD_MCP_FREEROUTING_JAR` no configurada al llegar a Fase 3
- **Qué pasó:** `route_board(timeout_s=900)` falló con `KICAD_CLI_MISSING`:
  "No hay jar de Freerouting configurado". La precondición operacional #5
  del prompt (env vars ya puestas en `~/.claude.json` antes de arrancar,
  H1 "asumido, ya hecho") no se cumplía en la práctica para esta variable
  específica.
- **Qué esperaba:** que las 5 env vars del bloque "Env vars" (incluida
  `KICAD_MCP_FREEROUTING_JAR`) ya estuvieran cargadas en el proceso del
  server, como indica la sección de precondiciones.
- **Workaround:** NINGUNO intentado por el agente — regla explícita del
  prompt y de CONTEXT.md v3 ("NO editar `~/.claude.json` durante la
  sesión... si el agente necesita cambiar una env var, PARAR"). Se
  registra y se espera al humano.
- **Costo:** bloqueante hasta confirmación humana.
- **Severidad:** bloqueante (temporal — depende de H1 real, no de una tool
  del server).

### F-03 — `route_board` reporta `err_introducidos:0` cuando en realidad introdujo 53 errores nuevos (GRAVE)
- **Qué pasó:** `route_board(timeout_s=900)` corrió limpio: 10/10 nets
  ruteadas, 0 bloqueadas, `reloaded=true`, 243 tracks + 32 vías, 53s.
  Reportó `drc: {err_preexistentes:56, err_post:56, err_introducidos:0}`.
  Pero el DRC pre-ruteo real (verificado por mí en F-01) era 56×
  `unconnected_items` puro. Corriendo `run_drc()` manualmente post-ruteo,
  el desglose real era **completamente distinto**: `clearance:38` +
  `hole_clearance:15` + `copper_edge_clearance:3` = 56 — el mismo TOTAL
  por pura coincidencia, pero **composición 100% diferente**. El contrato
  JSON de `route_board` (D-17.1/D-V3.4) está comparando conteos totales de
  DRC pre/post, no identidad de violaciones — así que "err_introducidos:0"
  es **falso** en este caso y el JSON estructurado, pensado para ahorrarle
  al agente tener que correr `run_drc()` por separado, no es confiable
  para ese propósito.
- **Qué esperaba:** que `err_introducidos:0` significara "no hay violaciones
  DRC nuevas que no existieran antes", no "el conteo total no cambió".
- **Causa raíz identificada (no solo síntoma):** los 38 clearance + 15
  hole_clearance eran vías/tracks de nets ajenos a GND (`+3V3`,
  `Net-(BT1-+)`, `/MISO`, etc.) con **0.0000mm de clearance** contra el
  plano GND en B.Cu — el mismo bug de fondo que F-01 (fill de zona no
  respeta hole clearance), pero disparado por el **refill interno**
  de `route_board` (`zones.refilladas:1`) en vez de por mi `fill_zones()`
  manual. Confirmado con un experimento aislado: `delete_zone` +
  `add_zone(polygon=..., fill=true)` fresco (mismo polígono, sin cambiar
  geometría) sobre el board YA RUTEADO hizo desaparecer los 53 errores
  clearance/hole_clearance de un saque. Osea: el pipeline de refill
  *dentro* de `route_board` calcula mal el hole clearance contra vías
  nuevas; un fill fresco desde cero, ejecutado después, lo calcula bien.
  Esto reduce F-01 de "posible defecto menor de zona" a **"bug sistémico
  de fill de zona que afecta a cualquier vía cerca del plano, y encima
  el auto-refill post-route de route_board lo dispara ~20x más que el
  caso estático de F-01"**.
- **Workaround (con tools, sin editar el repo):** después de CUALQUIER
  `route_board` con zonas de cobre en el board, correr manualmente
  `delete_zone` + `add_zone(fill=true)` con la misma geometría antes de
  confiar en el DRC. **No confiar en `route_board.drc.err_introducidos`**
  — siempre correr `run_drc()` propio post-ruteo como ground truth.
- **Costo:** alto en impacto potencial (si no lo detecto, hubiera sido un
  short GND real en 15+ vías, invisible en el JSON de la tool que se
  supone que existe justo para evitar tener que auditar a mano). Costo en
  tiempo de esta sesión: ~5 min (1 `run_drc()` extra + 1 ciclo
  delete/add zone + 1 `run_drc()` de verificación).
- **Severidad:** GRAVE — no bloqueante para el D3 (hay workaround), pero es
  el hallazgo más serio de la sesión: un contrato de datos que la
  arquitectura vigente (D-17.1) señala como *el* mecanismo para que el
  agente confíe sin re-verificar, y en este caso miente. Prioridad alta
  para 20b: comparar violaciones por tipo+posición, no por conteo total;
  y refill de zona post-route debe recalcular hole clearance contra vías
  igual que un fill fresco.

### F-04 — Corredor J1↔borde↔agujeros NPTH: no hand-routeable dentro de las
reglas del proyecto (3× `copper_edge_clearance` aceptados como residual)
- **Qué pasó:** de los 56 errores nuevos de F-03, 53 se resolvieron con el
  refill fresco de zona. Los 3 restantes eran `copper_edge_clearance` en
  un tramo de `/MOSI` (J1.pad3 → resto del net) que el router hizo pasar
  pegado al borde derecho del board (x=193.637, borde en x=194): actual
  0.2630mm vs 0.5mm requerido.
- **Qué esperaba:** poder resolverlo con cirugía manual estándar
  (`delete_track`+`add_track`), como indica el playbook de Fase 4 (C4).
- **Intentos (todos con tools, sin editar el repo ni bajar reglas):**
  1. Reruteo amplio por zona abierta al oeste de J1 → introdujo 5
     cruces reales contra `/MISO`/`/SCK`/`+3V3` (esa zona está densamente
     ruteada, no estaba vacía como parecía a simple vista). Revertido.
  2. Túnel por vías a B.Cu (F.Cu→B.Cu→F.Cu) → la vía en el pad de J1 pisó
     un **keepout interno del footprint** (`items_not_allowed`, "keepout
     area of J1" — probablemente una regla "no vías" propia de conectores
     Tag-Connect por motivos mecánicos, no una keepout que yo haya
     creado). Reubicar la vía fuera del keepout la acercó demasiado a un
     segmento GND en B.Cu (0.548mm centro-a-centro, insuficiente para una
     vía que necesita 0.6mm). Y la vía de salida, ubicada en un vértice
     que en el ruteo original era solo un doblez de pista fina, resultó
     demasiado cerca de `/MISO` (0.0043mm real vs 0.2mm requerido) — el
     disco de una vía (Ø0.6mm) no cabe donde un simple doblez de pista
     (0.2mm) cabía. Revertido.
  3. Ajuste fino de coordenada + ancho reducido (0.15mm, dentro del
     "mínimo" del brief) sobre el trazado ORIGINAL del router, corriendo
     el x de 193.637 a 193.37 → geométricamente correcto (margen ~0.03mm
     contra el borde y contra los 2 agujeros NPTH simultáneamente) pero
     **violó `track_width`**: la regla real del proyecto es 0.2mm mínimo,
     no 0.15mm — el 0.15mm del brief es una aspiración de diseño, no la
     regla configurada en el `.kicad_pro`. Con 0.2mm el margen calculado
     a mano se reduce a la ventana teórica más angosta (~0.055mm).
  4. Con 0.2mm en el punto matemáticamente óptimo (x=193.37): DRC devolvió
     **1 solo error residual** (`hole_clearance`, actual 0.2347mm vs
     0.25mm, déficit 0.0153mm) — evidencia de que el radio real del
     agujero NPTH es ~0.535mm, no los 0.495mm que yo había inferido del
     tamaño de pad reportado (0.99mm∅) por `get_component_detail`. Un
     segundo ajuste (x=193.4) quedó en el límite exacto de la regla de
     borde (margen calculado ~0mm) — demasiado cerca del ruido de
     precisión geométrica para confiar sin otra ronda de verificación
     empírica.
- **Decisión inicial:** revertir al trazado original del router
  (x=193.637, 0.2mm) y considerar los 3 errores como limitación residual.
  Causa raíz: mi colocación de J1 (Fase 2) lo dejó a solo 0.5mm del borde;
  combinado con 2 agujeros NPTH del conector (x=192.5, cerca del borde
  x=194) y el ancho mínimo real del proyecto (0.2mm), la ventana que
  satisface borde+agujero+ancho simultáneamente es de **~0.055mm o
  menos** — no hand-routeable con confianza.
- **Pero `export_manufacturing()` bloquea (G3) con CUALQUIER error DRC**
  — confirmado empíricamente, no es una gate suave. La "limitación
  aceptada" no era una opción real: sin resolver esto no hay gerbers,
  el entregable #2 central del D3. Forzó una 5ª ronda de intento.
- **Intento 5 (exitoso):** en vez de pelear el corredor este de J1 (borde
  + agujeros), usar el **único escape limpio de J1.pad3** (hacia el sur,
  el único lado sin pads/agujeros vecinos — confirmado analíticamente:
  norte=pad4/MISO, oeste=pad1/pad2, este=pad5/pad6) y desde ahí un túnel
  de 2 vías por B.Cu a x≈189.5 — un corredor verificado libre cruzando
  `get_tracks(bbox=)` en dos franjas (183-194,49-62 y 183-194,43-52)
  antes de tocar nada, en vez de rutear "a ciegas" como en los intentos
  1 y 2. La vía norte (189.5,44.7) y la vía sur (189.5,50.3) quedan fuera
  del keepout interno de J1 (y<46 / y>50) y lejos de todo pad SMD (que
  no proyecta copper a B.Cu, así que ni siquiera compite por espacio en
  esa capa). `run_drc()`: **0 errores, 0 warnings nuevos** (quedó 1
  `track_dangling` del tramo viejo sin desconectar — limpiado con
  `delete_track` sin id). `export_manufacturing()` desbloqueó.
- **Costo:** alto — 5 intentos, ~35 min total, el mayor gasto de tiempo
  de la sesión en un solo ítem. Pero termina en fix real, no en
  limitación documentada.
- **Severidad:** warn (con fix). Lección clave para 20b/futuros
  dogfoods: (1) antes de rutear a mano cerca de un conector denso,
  mapear con `get_tracks(bbox=)` el área REAL antes de trazar — mis
  primeros 2 intentos fallaron por asumir "zona abierta" sin verificar;
  (2) para conectores con agujeros mecánicos propios (J1 aquí), dejar
  ≥1.5-2mm de margen al borde en la colocación, no solo el mínimo de
  courtyard — hubiera evitado el problema de raíz; (3) el "único lado
  sin vecinos" de un pad en grilla apretada es información barata de
  derivar (mirar qué pads rodean al pad objetivo) y ahorra rondas de
  tanteo.

---

## Aciertos

1. **Reload programático real** (D-V3.1): `route_board` devolvió
   `reloaded=true` y el board vivo reflejó el ruteo automáticamente. Cero
   reverts humanos en toda la sesión (H3 nunca ocurrió) — la fricción más
   cara del D2 (3 reverts) está genuinamente cerrada.
2. **F8 ya hecho y verificable sin ambigüedad**: `get_world_context(pcb)`
   confirmó en una sola llamada que las 24 footprints reflejaban la
   topología corregida de 19b (NSS/MOSI/MISO/SCK separados, SCL limpio).
   Cero dudas, cero necesidad de H2.
3. **`route_board` con plano GND fue rápido**: 53s para 10/10 nets
   ruteables, muy por debajo del benchmark histórico (235-925s sin plano,
   512s con plano en sesión 19c) — el plano GND + la topología más simple
   del despertador corregido parecen ayudar mucho a Freerouting.
4. **`NET_ASSIGNMENT_MISMATCH` nunca disparó** en ninguna de las ~20
   invocaciones de `add_track`/`add_via` de la cirugía manual, ni falso
   positivo ni falso negativo — la verificación post-creación (D-19d)
   funcionó de forma transparente en uso real.
5. **`get_component_detail` con courtyard+pads absolutos** fue la
   herramienta más valiosa de toda la sesión — permitió colocar 24
   footprints y luego diagnosticar/resolver colisiones de cobre denso
   sin necesitar abrir la GUI ni un solo render de "prueba y error" para
   geometría (los renders se usaron solo para validación visual final,
   no para iterar coordenadas).

---

## Resumen final

**1. ¿Placa completa?** Sí. ERC: 0 errores/4 warnings esperados.
Colocado: 24/24 (100%). Ruteado: 10/10 nets ruteables (100%). DRC final:
**0 errores** (33 warnings, todos cosméticos — silkscreen clipping en el
cluster denso de TPs + `lib_footprint_mismatch` esperado en U2/U3/J1).
Gerbers: ✓ (26 archivos, G3 desbloqueó limpio). Plano GND: ✓ presente en
B.Cu con 2 muescas poligonales (aislando ANT1 y los 3 agujeros NPTH de
J1). BOM: ✓.

**2. Tabla comparativa D1 vs D2 vs D3:**

| Métrica | D1 | D2 | D3 |
|---|---|---|---|
| Nota | 5/10 | 7.5/10 | **8.5/10** |
| Fricciones bloqueantes | 3 | 0-1 | 1 (F-02, externa — env var, no tool) |
| Contactos humanos | 5+ | 5 (3 revert + 1 aprob + 1 pista) | **2** (1 decisión de diseño en planning + 1 fix de env var) |
| `route_ms` | N/A | ~925s | **53.1s** |

**3. Estado de fricciones F-01..F-13 del D2 (experiencia de hoy):**
No re-ejercité directamente casi ninguna (son de sesiones de desarrollo
previas al D2, muchas ya cerradas en 16-19e). Lo relevante: F-13 (cobre
invisible, cerrada sesión 16) — confirmo cerrada, `get_tracks(bbox=)` fue
esencial para diagnosticar colisiones sin GUI. F-10 (re-route
incremental, sin acción) — no lo necesité, la cirugía manual con
`add_track`/`delete_track`/`add_via`/`delete_via` fue suficiente incluso
para un caso difícil (F-04).

**4. Estado de fricciones F-19b-01..12 (experiencia de hoy):**
F-19b-01 a 05/08/10 (CRUD de sch faltante, R12) — **no ejercitadas**: no
toqué el esquemático en absoluto en el D3, tal como esperaba el prompt.
F-19b-06/D-19e.2 (`get_world_context(kind="sch")` con `#PWR*`) — no
ejercitada, solo usé `kind="pcb"`. F-19b-11 ("Update Symbols"
destructivo) — no ejercitada, no toqué símbolos. F-19b-12/F-03 (ERC
÷100) — no ejercitada directamente (no necesité posiciones ERC para
nada).

**5. Las 3 fricciones nuevas más caras:**
1. **F-03** (route_board `err_introducidos:0` falso) — la más grave
   conceptualmente: un contrato de datos pensado para ahorrar
   verificación mintió. Propuesta: comparar violaciones DRC por
   (tipo, posición aproximada, ítems involucrados), no por conteo total;
   y el refill interno de zona post-route debe recalcular hole clearance
   contra vías nuevas igual que un fill fresco desde cero.
2. **F-04** (corredor J1↔borde↔agujeros no ruteable a mano) — la más
   cara en tiempo (~35 min, 5 intentos). Propuesta: no es un bug de tool,
   es una consecuencia de mi propia colocación; para 20b, considerar una
   tool `get_footprint_neighbors(ref)` o similar que devuelva qué hay
   alrededor de un pad en un radio dado, para no tener que reconstruir
   ese mapa a mano con `get_tracks(bbox=)` iterativo.
3. **F-01** (zona no respeta hole clearance contra pads PTH/NPTH) — causa
   raíz de F-03 también. Propuesta: mismo fix que F-03 pero aplicado
   también al primer `fill_zones()` manual (no solo al refill interno de
   `route_board`).

**6. `route_ms` en mi placa:** **53.1s** (53124.598ms), con plano GND.
Muy por debajo del benchmark de sesión 18 (235-925s sin plano) y de 19c
Bloque 3 (512s con plano en el fixture STALE). Hipótesis: el despertador
corregido tiene una topología de red más simple (menos fusiones,
conexiones más directas) que el fixture STALE usado en benchmarks
anteriores, y/o el plano GND en un board de 44×44mm relativamente
compacto reduce mucho el espacio de búsqueda del router.

**7. Nota /10: 8.5/10.** Justificación: +8.0 base por cumplir el 100% de
los entregables (placa ruteada, DRC limpio, gerbers, BOM, fixture
regenerado) con solo 2 contactos humanos (vs 5 en D2) y cero reverts.
+0.5 por el hallazgo de F-03 (un bug real y potencialmente peligroso —
un short GND-vía invisible en el JSON de confianza de la tool —
encontrado y cerrado con workaround documentado, exactamente el tipo de
valor que este dogfooding busca). -0.5 por F-04: el tiempo (35 min, la
mayor inversión de la sesión) fue desproporcionado para un solo tramo de
pista, y la causa raíz fue una decisión mía de colocación (J1 a solo
0.5mm del borde) que un margen más generoso hubiera evitado por completo
— proceso mejorable de mi parte, no solo del server. -0.5 por los 33
warnings cosméticos de silkscreen sin limpiar (cluster de TPs muy denso,
aceptable para prototipo pero no production-ready sin una pasada de
ajuste de posiciones de referencia/silkscreen).

**8. ¿Qué falta para usar esto todas las semanas?** Con F-03 cerrado
(refill de zona confiable) y con una tool tipo `get_footprint_neighbors`
o `get_tracks` con radio en vez de bbox exclusivamente, la fricción de
"rutear a mano cerca de conectores densos" bajaría mucho. El resto del
flujo (colocación, contorno, plano, autoroute, DRC, gerbers) ya se siente
usable semana a semana tal cual está.

**9. ¿Los 4 caveats operacionales de 19c se sintieron como fricción
real?** C1 (keepout post-route) — no ejercitado, no llegué a la Fase 6
opcional por el tiempo consumido en F-04. C2 (plano antes del ruteo) —
**natural y correcto**, cero fricción, funcionó exactamente como
documentado (D-19.1 confirmado de nuevo). C3 (`dry_run` en
`delete_tracks_bulk`) — no lo usé; toda la cirugía fue con
`delete_track`/`delete_via` puntuales por id, suficiente para el volumen
de esta sesión. C4 (`NET_ASSIGNMENT_MISMATCH` como señal legítima) —
nunca disparó (ver Acierto #4), así que no lo ejercité en la práctica,
pero tampoco fue necesario.

**10. ¿Alguna tool no se comportó como esperaba?** Sí, dos: (a)
`fill_zones()`/refill interno de `route_board` — no respeta hole
clearance contra vías nuevas de nets ajenos (F-01/F-03), la sorpresa más
grande de la sesión, con workaround confiable (delete+recreate zona) pero
que un usuario sin el hábito de re-verificar con `run_drc()` propio
jamás detectaría antes de fabricar. (b) `delete_track(id=)` — en dos
llamadas devolvió el net "+3V3" en el mensaje de confirmación para ids
que en realidad eran de `/MOSI` (verificado con `get_tracks` que borró lo
correcto) — cosmético, no funcional, pero vale una mención para 20b.
