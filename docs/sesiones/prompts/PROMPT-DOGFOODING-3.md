# Dogfooding 3 — Una placa real (sesión 20)

**QUÉ ES:** sesión de USO, no de desarrollo. Mismas reglas que D1 y D2:
**prohibido editar el repo de kicad-mcp**; toda falla se REGISTRA como
fricción en el log, no se arregla. Es la prueba de fuego de la hoja de
ruta v3 completa. **Objetivo ≥8/10** (D1 = 5/10, D2 = 7.5/10).

**Variable controlada:** misma placa que el D2 (despertador ATtiny85 wearable,
24 footprints). Cualquier delta de nota se atribuye directo al server, no
al problema.

**Timeboxing:** 2h target, 3h techo. Si a las 3h no estás exportando
gerbers, parar y reportar el estado. Si terminás antes de 2h, usar el
tiempo restante para reportar variantes (ej: rerutear sin plano y comparar
métricas, aplicar keepout post-route y ver qué pasa).

## ENTREGABLES

1. `/tmp/dogfood3-fricciones.md` — mismo formato F-NN de D1/D2 (qué pasó /
   qué esperaba / workaround / costo / severidad), escrito **EN EL MOMENTO**,
   no al final. Sección final de Aciertos.
2. La placa completa: PCB colocado, contorneado con plano GND, ruteado al
   100% con DRC sin errores nuevos, render final, gerbers (G3).
3. Fixture regenerado en `tests/fixtures/despertador-routed/` con el sch
   corregido (reemplaza el STALE de sesión 19b).
4. Resumen final con la nota /10 y comparación contra D2.

---

## ESTADO INICIAL DEL PROYECTO

El sch ya está corregido (sesión 19b). Estado esperado al arrancar:

- [x] Esquemático: **0 errores, 4 warnings `lib_symbol_mismatch`** aceptados
      (D-19b.1 — NO ejecutar "Update Symbols from Library").
- [x] Los 5 defectos del D2 corregidos: INT wired-OR entre U2/U3 sobre un
      pin de U1, No-Connect explícitos en U3, /SDA separado de /INT_SENS,
      /NSS separado de /MOSI (NSS ya estaba en PB0; MOSI reasignado
      reclamando pin previamente usado por ICSP), J1.in_bom=no.
- [x] **Deuda física conocida (fuera del scope del D3, no arreglar):**
      VLED+ (U3.pin10) flotante — MAX30102 no medirá SpO₂; ICSP en circuito
      perdido, U1 se programa en banco. Consecuencia para el D3: el ruteo
      no toca ninguno de esos pines.
- [?] F8 puede estar hecho o no dependiendo del estado dejado por 19b —
      verificar con `get_world_context(kind="pcb")` al inicio.
- [ ] Todo lo demás (outline, plano, colocación, ruteo, DRC, gerbers) es
      trabajo tuyo.

**Proyecto en disco:** `/tmp/gui-test-project/despertador_inteligente.kicad_pro`

---

## PRECONDICIONES OPERACIONALES (obligatorias)

1. **Restaurar copia de trabajo desde Desktop:**
   ```
   cp -r /home/astra/Desktop/Electronig_Proyects/despertador_inteligente /tmp/gui-test-project
   ```
   (El humano hace esto antes de arrancar la sesión, o el agente lo pide
   explícitamente al inicio.)
2. **KiCad reiniciado limpio** con el proyecto abierto y PCB Editor activo.
3. **Sin symlink en `/tmp/kicad/`** — la cascada de sesión 19e resuelve
   automáticamente.
4. **Env vars del server MCP en `~/.claude.json`**
   (`projects.<repo>.mcpServers.kicad-mcp.env`), no en la shell interactiva.
5. `KICAD_MCP_FREEROUTING_JAR` configurada.

Confirmar con `health()` que todo responda ok ANTES de tocar nada.

---

## CAVEATS OPERACIONALES (validados en sesión 19c — respetar)

### C1. NO aplicar `add_keepout_zone` antes de `route_board`
19c Bloque 4 demostró que el keepout circular bajo ANT1 bloquea 9/10 nets
cuando se aplica sobre un board sin cobre. **Patrón correcto**: si se quiere
proteger físicamente la zona bajo la antena, aplicar el keepout DESPUÉS del
ruteo completo y resolver manualmente los tracks que queden bajo la zona.
Para el D3, el keepout es OPCIONAL — si el tiempo no alcanza, dejarlo
fuera.

### C2. Patrón validado para plano GND
Crear y fillar el plano GND ANTES de `route_board`, sobre un board sin
cobre. Freerouting respeta nativamente `(plane)` en el DSN (D-19.1).
`timeout_s ≥ 900` (validado en 19c Bloque 3: 8.5 min de router para el
despertador).

### C3. `delete_tracks_bulk` con `dry_run=True` primero
Antes de cada borrado masivo, invocar con `dry_run=True` para ver el
conteo. Si es razonable, invocar de nuevo con `dry_run=False`.

### C4. `NET_ASSIGNMENT_MISMATCH` como señal legítima
`add_track` y `add_via` verifican el net post-creación (sesión 19d). Si el
punto pisa cobre ajeno, la tool falla con `NET_ASSIGNMENT_MISMATCH`. NO es
fallo de la tool — es señal para replanificar coordenadas. Usar
`get_tracks(bbox=<zona destino>)` para diagnosticar antes de reintentar.

---

## PUNTOS DE CONTACTO HUMANO (los ÚNICOS)

**H1 (asumido, ya hecho al arrancar):** proyecto en disco, sch corregido,
KiCad abierto, env vars ok.

**H2 (condicional):** F8 en la GUI si `get_world_context(kind="pcb")`
revela que los footprints del sch corregido NO están sincronizados en el
PCB. Pedir explícitamente: *"Corré Tools → Update PCB from Schematic (F8)
y avisame"* y esperar confirmación. Si el PCB ya refleja las 24
footprints del sch corregido, este toque no es necesario.

**H3 (revert post-route): NO EXISTE** — cerrado por D-V3.1. `route_board`
recarga automáticamente el board vivo tras escribir a disco. **Si aparece
la necesidad de un revert humano, ES UNA FRICCIÓN GRAVE — registrarla.**

**H4 (validación visual opcional):** renders intermedios si querés
segunda opinión del humano sobre colocación. Costo ~11s c/u.

---

## FLUJO ESPERADO (tu plan de vuelo)

### Fase 1: Verificación de estado (5-10 min)
1. `health()` → ipc ok, proyecto ok.
2. `run_erc()` → confirmar 0 errores, 4 warnings esperados.
3. `get_world_context(kind="pcb", max_tokens=4000)` → inventario. ¿F8 hecho
   o no? ¿Cuántos footprints en el PCB?
4. Si F8 no está hecho → H2, esperar confirmación.

### Fase 2: Contorno y plano GND (5-10 min)
5. `draw_board_outline(bbox=<40-50mm cuadrado>)`.
6. `add_zone(net="GND", layer="B.Cu", bbox=<mismo bbox del outline>,
   fill=true)`. Este es el momento clave — el plano ANTES del ruteo (C2).

### Fase 3: Colocación (30-45 min)
7. Plan breve de colocación en el chat (una línea por componente crítico:
   U1, U2, U3, U4, ANT1, BT1, J1, J2). Ver el brief real de sesión 15 en
   CONTEXT o el reporte del D2 para restricciones de posición
   (MPU-6050 con orientación acelerómetro, MAX30102 en borde inferior,
   RFM69CW lejos de sensores, BT1 en borde lateral, ANT1 borde libre, etc.).
8. `move_footprint(ref, x, y)` × 24 con deltas para verificar.
9. `save_board()`.
10. Render de control (`export_render`) — antes de rutear.

### Fase 4: Ruteo (10-20 min)
11. `route_board(timeout_s=900)`. Esperar el JSON estructurado con
    `route_ms`, nets, drc pre/post, zones, y **`reloaded=true`**.
12. Verificar el `reloaded=true` — si es `false` o `skipped_editor_closed`,
    R11 pudo haber ocurrido (fricción grave, registrar).

### Fase 5: DRC y cirugía si hace falta (variable)
13. `run_drc()` con resumen por tipo.
14. Si hay errores nuevos:
    - `get_tracks(net=<net problemática>)` para diagnóstico.
    - `delete_track(id=)` puntual o `delete_tracks_bulk(net=)` para masa.
    - `add_track` / `add_via` con expectativa de posible
      `NET_ASSIGNMENT_MISMATCH` (C4).
    - Re-route si necesario. Cada `route_board` hace revert automático.

### Fase 6: Cierre (10 min)
15. Render final.
16. `export_manufacturing()` → gerbers (G3 debe desbloquear).
17. `export_bom()`.
18. **Regenerar fixture:** copiar `.kicad_pcb`, `.kicad_pro`, `.kicad_sch`,
    `.kicad_prl` a `tests/fixtures/despertador-routed/` sobrescribiendo el
    STALE. Actualizar README del fixture con el commit hash.

### Fase 7 (opcional, si sobra tiempo)
19. `add_keepout_zone` bajo ANT1 DESPUÉS del ruteo (C1). Ver qué pasa con
    el DRC. Documentar como experimento, no bloqueante.
20. Comparar métricas con el D2: `route_ms`, vías totales, tokens
    consumidos, contactos humanos.

---

## DISCIPLINA DE CONTEXTO (igual que D1/D2)

Delta > mundo con focus > mundo completo. Renders con criterio (~11s c/u).
Reportar al final: llamadas por tool, tokens totales estimados, tiempo de
sesión, y cuántos turnos consumió cada fase (verificación / colocación /
ruteo / cierre).

---

## REGLAS PROHIBITIVAS (VIOLARLAS INVALIDA EL DOGFOOD)

1. **NO editar el repo de kicad-mcp.** Toda falla → registrar como fricción,
   NUNCA arreglar.
2. **NO manipular el `.kicad_pcb`, `.kicad_sch`, `.kicad_pro` por fuera de
   las tools.** El fix del sch fue en 19b y ya está en disco; no se toca
   más en el D3.
3. **NO invocar `kicad-cli` directo** para bypass de una tool que falla.
   Registrar la fricción, buscar workaround CON TOOLS del server.
4. **NO editar `~/.claude.json`** durante la sesión. Las env vars están
   fijas.
5. **NO reiniciar KiCad si crashea (R11)** sin registrar primero el estado
   pre-crash como fricción. Después sí, reiniciar y continuar.

---

## LOG DE FRICCIONES

Crear `/tmp/dogfood3-fricciones.md` al inicio. Formato por entrada:

```
## F-NN — Título corto
- **Qué pasó:** ...
- **Qué esperaba:** ...
- **Workaround:** ...
- **Costo:** [bajo/medio/alto]
- **Severidad:** [info/warn/bloqueante]
```

Escribir EN EL MOMENTO, no al final. Si es info menor, F-NN también.

Al final del log, sección **Aciertos**: 3-5 cosas del server que
funcionaron mejor de lo esperado.

---

## RESUMEN FINAL (última sección del log de fricciones)

Responder **explícitamente** las 10 preguntas siguientes:

1. **¿Placa completa?** ERC ✓, colocado %, ruteado %, DRC (nuevos vs
   preexistentes), gerbers ✓/✗, plano GND presente ✓.

2. **Tabla comparativa D1 vs D2 vs D3:**
   | Métrica | D1 | D2 | D3 |
   |---|---|---|---|
   | Nota | 5/10 | 7.5/10 | ? |
   | Fricciones bloqueantes | 3 | 0-1 | ? |
   | Tokens totales | ? | ~? | ? |
   | Contactos humanos | 5+ | 5 (3 revert + 1 aprob + 1 pista) | ? |
   | `route_ms` | N/A | ~925s | ? |

3. **Estado de las fricciones F-01..F-13 del D2 desde tu experiencia HOY:**
   ¿las cerradas se sienten cerradas? ¿alguna reapareció? Ver CONTEXT §Métricas
   del D2 para lista.

4. **Estado de las fricciones F-19b-01..F-19b-12 desde tu experiencia HOY:**
   idem. En particular las de la limitación de tools de sch (R12) — si NO
   tuviste que tocar el sch en el D3, marcarlas como "no ejercitadas".

5. **Las 3 fricciones nuevas más caras** (si las hay), con propuesta
   concreta.

6. **`route_ms` en tu placa** (con plano GND). Comparar con benchmark de
   sesión 18 (235-925s sin plano) y 19c Bloque 3 (512s con plano en
   fixture).

7. **Nota /10 con justificación** — objetivo ≥8. Justificar cada 0.5.

8. **¿Qué falta para usar esto todas las semanas en tus proyectos?** (la
   pregunta que definió v3, definirá v4 si aplica).

9. **¿Los 4 caveats operacionales de 19c se sintieron como fricción real
   durante la sesión?** Si sí, cuál y cómo. Si no, ¿el patrón nuevo
   (plano antes del ruteo, sin keepout) fue natural?

10. **¿Alguna tool nueva (delete_tracks_bulk, add_zone, `NET_ASSIGNMENT_MISMATCH`,
    reload automático) NO se comportó como esperabas?** Reportar el
    delta entre expectativa y realidad.

---

## Env vars

```bash
# Estas ya deben estar en ~/.claude.json → projects.<repo>.mcpServers.kicad-mcp.env
export KICAD_MCP_GUI_TEST=1
export KICAD_MCP_PROJECT=/tmp/gui-test-project
export KICAD_MCP_GUI_REF=U1
export KICAD_MCP_FREEROUTING_JAR=/home/astra/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar
```

Si el agente necesita cambiar alguna, PARAR — es fricción, registrar y
esperar al humano.

---

## Cierre esperado

D3 cerrado con nota /10 documentada, placa fabricable, fixture
regenerado, log de fricciones completo. Con nota ≥8 → ruta a open source
se abre (limpieza + ADR-0012 + issue upstream a Freerouting + licencia).
Con nota <8 → hoja de ruta v4 con los items que emerjan del log.
