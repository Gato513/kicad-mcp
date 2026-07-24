# Dogfooding Etapa 1 — Log de fricciones

Sesión iniciada: 2026-07-11
Herramienta bajo prueba: kicad-mcp (MVP solo-lectura + mutaciones placement/routing)
Rol: primer usuario real. Objetivo: colocar y rutear una placa real.

---

## Fricciones

## F-01 · 22:47 · get_world_context (focus)
**Qué pasó:** Pedí `focus_ref=U1, max_tokens=2000` y devolvió el board ENTERO (24 comp, 41 nets), no una vecindad local de U1.
**Qué esperaba:** Que `focus_ref` recortara a un radio alrededor de U1, o al menos que el output indicara "cabe entero, sin recorte". No pasé `radius_mm` (es opcional) así que quizá por eso no recortó.
**Workaround:** Ninguno necesario — la placa es chica y entró entera en budget. Salió bien de casualidad.
**Costo:** 0 (fue útil), pero en un board grande esperar recorte y recibir todo sería caro.
**Severidad:** cosmético (documentación: aclarar que focus sin radius_mm no recorta)

## F-02 · 22:49 · export_render (output_path)
**Qué pasó:** Pasé `output_path=/tmp/dogfood-proyecto/render-inicial.png` (absoluto) y el confirm devolvió `"output_path":"render-inicial.png"` (relativo). Tuve que hacer un `find`/`ls` para confirmar dónde quedó.
**Qué esperaba:** Que el confirm devuelva la ruta absoluta final del archivo, así la leo directo sin buscarla.
**Workaround:** `ls` en el dir del proyecto — quedó donde pedí.
**Costo:** 1 turno extra de Bash (~bajo).
**Severidad:** molesto

## F-03 · 22:51 · reconocimiento (contorno de placa)
**Qué pasó:** La placa NO tiene contorno Edge.Cuts ni ningún elemento gráfico (0 gr_line/rect/poly). El borde del render es el bounding-box auto. Lo descubrí leyendo el .kicad_pcb con código; ninguna tool MCP me lo dice ni me deja verlo/dibujarlo.
**Qué esperaba:** (a) que `get_world_context(pcb)` incluyera dimensiones/contorno de placa, y (b) alguna forma de saber el área útil para colocar sin salirme. Para fabricar (G3) hará falta un borde.
**Workaround:** Leí Edge.Cuts del archivo crudo (permitido: es copia descartable, no fixture del repo). Voy a colocar dentro del cluster actual x150–178 / y35–68.
**Costo:** 2 turnos de Bash.
**Severidad:** molesto (bloqueante para fabricación final si G3 exige borde)

## F-04 · 22:55 · move_footprint / get_world_context (geometría de footprint)
**Qué pasó:** Para colocar sin solapar necesito el tamaño de cada footprint y la posición de sus pads. El TOON solo da el ORIGEN (x,y) del componente, no dimensiones ni coords de pad. Para poner la antena "junto al pin 9 de U4" o un 0402 sin pisar el chip, necesito saber cuánto ocupa cada uno.
**Qué esperaba:** Que get_world_context incluya un bbox/courtyard por componente (aunque sea WxH), y ojalá la posición de cada pad para rutear a coordenada exacta.
**Workaround:** Parseé pad spans del .kicad_pcb crudo con Python (2 intentos, el 1º falló por anidamiento). Obtuve: BT1 22mm, U4 15×14, U1 7.2×3.8, etc.
**Costo:** ~3 turnos de Bash + razonamiento. En un board sin acceso al archivo, esto sería colocar a ciegas.
**Severidad:** molesto (bloqueante para colocación precisa y para ruteo a pad exacto)

## F-05 · 22:58 · SPLIT-BRAIN live/disco — el hallazgo central ⚠️ BLOQUEANTE
**Qué pasó:** Tras mover 5 footprints por IPC, `export_render` devolvió un PNG **byte-idéntico** al inicial (mismo md5 `38a8d6bb…`). El `.kicad_pcb` en disco NO cambió (mtime 22:31, pre-sesión; ANT1 sigue en 177.665,44.435). Las mutaciones de PCB viven SOLO en el editor IPC (`mtimes=None`, catálogo L244-245); `export_render`/`run_drc`/`export_manufacturing` usan kicad-cli que lee **disco**. No hay tool para persistir live→disco.
**Qué esperaba:** Que después de mutar, el pipeline de verificación (render/DRC) y de salida (gerbers) reflejara lo que acabo de hacer. O una tool `save_board`/`commit` que baje el estado vivo a disco. Es la operación más obvia que falta.
**Qué implica:** Un agente autónomo NO puede cerrar el loop place→ver→rutear→DRC→export: tras la 1ª mutación vuela ciego y DRC/export validan el board VIEJO. La inspección visual del hito de colocación es imposible sin intervención humana.
**Workaround:** Pedir al humano que haga Ctrl+S en el PCB Editor (baja live→disco). Prescrito por el prompt ("contale qué necesitás de él"), pero rompe la autonomía y hay que repetirlo en cada hito.
**Costo:** Alto — 1 render desperdiciado (~11s), investigación del catálogo (~5 turnos), y una dependencia humana en cada ciclo de verificación de acá en más.
**Severidad:** BLOQUEANTE (es EL gap del MVP: falta el puente live→disco)

## F-06 · 23:05 · add_track / add_via — ruteo a coordenadas, sin pads ni feedback
**Qué pasó:** `add_track` toma x,y absolutos de inicio/fin, pero ninguna tool me da la posición de los pads. Tuve que:
  1. Parsear TODOS los pads del .kicad_pcb y calcular su posición absoluta (origen + offset rotado). ~40 líneas de Python. (F-04 agravado).
  2. Para CADA track, calcular a mano si cruza otra track/pad de otro net (no hay chequeo previo; el DRC recién lo veré tras guardar). Rutear a 2 capas obligó a razonar cruces en la cabeza.
  3. Rutear COMPLETAMENTE A CIEGAS: por el split-brain (F-05), las tracks no aparecen en ningún render hasta que el humano guarde. No vi ni una track mientras ruteaba 18.
**Qué esperaba:** (a) coords de pad en el contexto o una tool `route_net(net)` / `add_track` que acepte `from_pad="U1.8" to_pad="C2.2"` en vez de coordenadas; (b) validación de cruce/clearance en el add_track (rechazo tipado) en vez de descubrirlo en DRC; (c) poder ver el estado ruteado sin depender de un save humano.
**Números medidos (subconjunto ruteado):**
  - 18 tracks + 2 vías colocadas. Elementos de ruteo con confirm OK: 20/20 (la tool en sí nunca falló).
  - Confirm ≈ 25 tokens c/u. El costo real NO es el confirm: es el RAZONAMIENTO GEOMÉTRICO por track (buscar 2 pads, chequear cruces) — ~200-500 tokens de "pensar" por conexión no trivial.
  - Batching paralelo (sin base_snap) funcionó: 4-5 tracks por turno. Eso ayuda MUCHO (bajó de ~20 turnos a ~5 para 18 tracks).
  - El board tiene ~64 conexiones MST totales. Ruteé ~14 de las fáciles (poder local). Las ~50 restantes son las CARAS: señales SPI/I2C que cruzan todo el board (J1 ICSP arriba ↔ U1 abajo ↔ U4 abajo-izq), cada una necesitando vías y ruteo multi-segmento a ciegas.
**Workaround:** Ruteo por batches, geometría calculada offline, dejo señales largas sin rutear.
**Costo:** El ruteo de poder (14 conexiones) me llevó ~6 turnos + toda la extracción de pads. Extrapolando, el board completo a mano serían 25-40 turnos SOLO de tool calls, + el razonamiento de cruces, + N ciclos save→DRC→fix a ciegas.
**Severidad:** molesto (bloqueante de facto para rutear un board completo sin autorouter)

## F-07 · 23:06 · ANT1 / feed RF (colocación sin pads)
**Qué pasó:** Coloqué ANT1 arriba-derecha de U4 pensando acortar el feed, pero el pin de antena real (U4.9) está en el BORDE INFERIOR del módulo (160.2, 72.3). El feed quedó ~12mm diagonal y su ruteo directo roza los pads U4.10/U4.13. Dejé la antena SIN rutear para no meter un clearance error que no puedo depurar a ciegas.
**Qué esperaba:** Saber la posición del pin objetivo al colocar (otra vez: falta geometría de pad). Con eso habría puesto ANT1 en (164,72), feed de 4mm recto.
**Workaround:** Antena sin rutear; se documenta.
**Costo:** 1 conexión RF no ruteada + churn mental.
**Severidad:** molesto

## F-08 · 23:10 · NO HAY TOOL DE BORRADO ⚠️ BLOQUEANTE (co-headline)
**Qué pasó:** El DRC reveló ~13 shorts + 1 crossing + 2 vías-sobre-pad que mis tracks introdujeron. Para corregir un short hay que BORRAR el track ofensor. El catálogo NO tiene `delete_track`/`delete_via`/`remove`/`undo`. Las tools de mutación son solo aditivas: move_footprint, add_track, add_via, add_symbol.
**Qué esperaba:** `delete_track`/`delete_via` (por id o por coordenada+net), o un `undo` del último snap. Es la contraparte OBVIA de add_*.
**Qué implica:** Un agente que rutea mal se pinta solo en un rincón: cada track malo es permanente desde las tools. NO puedo llegar a DRC limpio ni destrabar el Gate G3. Deliverable #2 (DRC limpio + gerbers) es INALCANZABLE por el agente solo. Depende 100% de que el humano borre a mano en KiCad.
**Workaround:** Ninguno vía MCP. Habría que pedirle al humano que borre los tracks malos en KiCad.
**Costo:** Bloquea el cierre entero del pipeline. Todo el ruteo hecho es irreversible desde mi lado.
**Severidad:** BLOQUEANTE (junto con F-05, define los dos gaps que impiden un flujo autónomo end-to-end)

## F-09 · 23:11 · add_track dibuja shorts sin avisar
**Qué pasó:** `add_track` es un "dibujador de líneas tonto": traza el segmento recto pedido sin chequear si cruza un pad/track de OTRO net. Varios shorts salieron porque la línea recta pad-A→pad-B pasa por encima de un tercer pad (ej: +3V3 de C5→D1.2 cruza D1.1=BT+; el par de tracks de C3 corren a 0.05mm). No hubo ni un warning; me enteré recién en el DRC post-save.
**Qué esperaba:** Que add_track rechace (error tipado tipo `WOULD_SHORT`/`CLEARANCE_VIOLATION`) o al menos advierta cuando el segmento viola clearance o toca otro net. Prevención barata >> DRC caro + sin poder borrar.
**Workaround:** Ninguno; agravado por F-08 (no puedo deshacer el short).
**Costo:** ~10 tracks buenos en intención, malos en resultado; irreversibles.
**Severidad:** molesto (se vuelve bloqueante combinado con F-08)

## F-10 · 23:12 · run_drc — violaciones con ref:null, difícil mapear al culpable
**Qué pasó:** El DRC devuelve para casi todos los items `"ref":null,"net":null` y solo `pos:[x,y]`. Para saber QUÉ track/net corregir tengo que revertir coordenadas a mis tracks. Los footprints sí traen ref (courtyards). El mensaje de shorting_items sí nombra los nets ("GND and +3V3"), pero el item a tocar no dice cuál es.
**Qué esperaba:** Que cada violación traiga el/los objeto(s) involucrados con su tipo (track/via/pad), net y —si es track— sus endpoints.
**Workaround:** Cruzar posiciones con mi tabla de pads/tracks a mano.
**Costo:** Alto si tuviera que depurar los 24 errores uno por uno.
**Severidad:** molesto

## F-11 · 23:13 · Colocación a ciegas → courtyards solapados (consecuencia de F-04)
**Qué pasó:** 5 courtyards_overlap + 1 pth_inside_courtyard: C3/U3, ANT1/U4, ANT1/TP1, C2/TP4, C6/U4. Coloqué "pegado al IC" sin saber el tamaño del courtyard, así que quedé demasiado cerca.
**Qué esperaba:** Courtyard/bbox por componente en el contexto, o que move_footprint avise si el destino solapa otro courtyard.
**Workaround:** Re-mover no sirve: los tracks ya están a esas coords; mover el footprint los dejaría atrás desconectados, y sin delete (F-08) no puedo re-rutear. Callejón sin salida por el orden de operaciones.
**Costo:** 6 errores de placement (baratos de evitar con info de courtyard) ahora irreversibles.
**Severidad:** molesto

---

## Aciertos

- **get_context_delta = la joya.** Barato, preciso, mostró EXACTAMENTE los 5 componentes movidos (`[~C]`) y el resto `ok`. Verifiqué 5 mutaciones sin re-leer el mundo. Tal cual promete el diseño (10-100× más barato).
- **Batching paralelo de add_track/add_via sin base_snap.** Disparé 4-5 tracks por turno; el server los serializó sobre IPC sin drama. Bajó el ruteo de ~20 turnos a ~5. Gran win de economía.
- **Confirms diminutos con snap embebido.** `OK add_track ... [snap:N]` ~25 tokens, encadenables. La economía de tokens en la escritura es excelente (ADR-0004 cumplido).
- **TOON de get_world_context.** El board de 24 comp + 41 nets entró en ~1600 tokens, legible. La sección `[N]` (adyacencia por net) fue genuinamente la que me dejó entender el circuito. Formato compacto y bueno.
- **Gate G3 honesto.** `export_manufacturing` bloqueó con `EXPORT_BLOCKED_BY_DRC` + conteo (86) + 3 muestras. El gate hace su trabajo y no se puede saltar desde el prompt. Inviolable como se diseñó (F2).
- **health claro y completo.** Un solo call me dio server/cli/ipc/pcb-abierto/proyecto. Buen primer paso de sesión.
- **Robustez total de las tools.** 34 llamadas MCP, CERO crashes, CERO tracebacks crudos. Todo salió tipado (incluso los errores). La disciplina de la regla #1 se nota.
- **Render 3D real.** El pcb_png es lindo y útil para VER placement/ruteo... cuando el disco está sincronizado.

---

## Resumen final

### 1. ¿Hasta dónde llegué?
- **Colocación:** ~100% revisada; 5 componentes reubicados (ANT1 + 4 desacoples). Mejoré la lógica (desacoples junto a IC, antena cerca del radio) PERO introduje 6 solapes de courtyard por colocar sin info de tamaño (F-11). Neto: mejor intención, placement con defectos.
- **Ruteo:** ~14 de ~64 conexiones MST (≈22%). Todo el poder local (desacoples + spines +3V3/GND + jumper con vías) + 2 señales I2C. 18 tracks + 2 vías.
- **DRC:** 86 errores. Desglose: ~45 unconnected (nets no ruteados a propósito), ~17 solder_mask_bridge, ~13 shorting_items (REALES, míos), 6 courtyard/pth, 2 clearance, 1 crossing, 2 via-on-pad, 1 sin-Edge.Cuts. **NO limpio.**
- **Exports:** render inicial/colocado/ruteo OK. Manufacturing **bloqueado por G3** (correcto). Gerbers NO generados.
- **Veredicto de estado:** la placa quedó PEOR que como llegó en cuanto a DRC (introduje ~24 errores que NO puedo revertir). El valor de la sesión está 100% en el log de fricciones.

### 2. Las 3 fricciones más caras
1. **F-05 Split-brain live/disco.** Las mutaciones IPC no tocan disco; render/DRC/export leen disco. Sin puente live→disco, el agente vuela ciego tras la 1ª mutación y necesita un Ctrl+S humano en cada hito. → **Tool `save_board` (o auto-save post-mutación opcional).** Es el fix #1.
2. **F-08 Sin tool de borrado.** add_* es solo aditivo; no hay delete_track/delete_via/undo. Un ruteo malo es permanente → imposible llegar a DRC limpio solo. → **`delete_track`/`delete_via` (por coord+net o por id) + idealmente `undo` del último snap.** Fix #2, empatado en prioridad.
3. **F-04/F-06 Sin geometría de pad.** El contexto da orígenes de componente, no bbox/courtyard ni posición de pad. Tuve que parsear el .kicad_pcb crudo para colocar y para rutear a coordenada. → **Exponer pads (ref.pad→x,y) y courtyard/bbox en get_world_context, y/o `add_track(from_pad, to_pad)` anclado a pads en vez de coords crudas.** Elimina F-06, F-07, F-11 y la mitad de F-04 de un saque.

### 3. Veredicto de ruteo (D-R3)
**El ruteo manual por add_track/add_via NO es viable para un board completo de 10-60 componentes por un agente autónomo.** Números:
- Throughput: ~18 tracks en ~5 turnos (batched), PERO cada track no trivial costó ~200-500 tok de razonamiento geométrico offline (buscar 2 pads + chequear cruces a mano) → efectivo ~300 tok/track útil, además de ~40 líneas de Python para extraer pads.
- Calidad a ciegas: ruteando SOLO el poder local (lo más fácil) generé ~13 shorts + 1 crossing. Tasa de defecto alta porque add_track no chequea clearance (F-09) y no veo el resultado hasta un save humano (F-05).
- Extrapolación al board completo (~64 conexiones): ~25-40 turnos de tool calls + ~20k tokens + N ciclos save→DRC→fix, y como no puedo borrar (F-08), cada error me acerca a un estado irrecuperable.
- **Conclusión:** hace falta un autorouter (freerouting / el de KiCad vía IPC) O subir MUCHO la inteligencia del primitivo (add_track anclado a pads + rechazo de shorts + delete). Para D-R3, lo pragmático es **integrar un autorouter** y dejar add_track/add_via para retoques puntuales.

### 4. ¿Qué haría distinto en Etapa 2?
- **Arreglar primero F-05 y F-08** antes de intentar rutear nada; sin ellos el loop no cierra y la Etapa 2 chocaría con lo mismo.
- Exponer pads/courtyard en el contexto (F-04) — sin eso, colocar y rutear obliga a salir de las tools.
- Empezar por un board MÁS chico (5-8 comp, 2 capas triviales) para medir el ruteo manual limpio de punta a punta antes de un board denso como este (ATtiny + 3 sensores + radio = interconexión que cruza todo).
- Definir Edge.Cuts (o una tool para ello) desde el inicio: sin borde, el DRC arranca con `invalid_outline` y G3 nunca abriría.
- Rutear SIEMPRE con render intermedio disponible (requiere F-05 resuelto): rutear a ciegas fue la causa raíz de casi todos mis errores.

### 5. Nota de usabilidad global: **5/10**
Los primitivos de LECTURA y la economía de contexto (delta, TOON, confirms, batching, gates) son excelentes y sólidos; pero la falta del puente live→disco (F-05) y de un borrado (F-08), más la ausencia de geometría de pad (F-04), hacen que el flujo de ESCRITURA end-to-end (colocar→rutear→DRC-limpio→fabricar) sea imposible de completar sin un humano en el loop. Es un gran visor + un mutador manco.

---

## Presupuesto de la sesión (medido)
- **Llamadas MCP: 34** — health×1, get_world_context×1, get_context_delta×1, move_footprint×5, add_track×18, add_via×2, run_drc×1, export_render×4, export_manufacturing×1.
- **Bash auxiliar: ~10** (verificar_entorno, Edge.Cuts×2, tamaños footprint×2, pads×2, polls de save×2, etc.).
- **Saves humanos requeridos: 2** (Ctrl+S) — 1 por hito, exigidos por F-05.
- **Tokens de tools (estimado): ~14-16k.** El pico único fue el volcado de DRC (86 violaciones con coords ≈ 4-5k tokens en una sola respuesta — F-10 secundaria: `run_drc` no permite filtrar/paginar; `min_severity=error` igual devolvió los 45 unconnected esperados).
- **Tiempo de sesión: ~30-35 min** de pared, dominado por los 4 renders (~11s c/u) y las 2 esperas de Ctrl+S.
