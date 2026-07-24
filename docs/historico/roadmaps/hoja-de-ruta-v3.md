# Hoja de ruta v3 — kicad-mcp (post-Dogfooding 2, 2026-07-17)

**Evidencia base:** `dogfood2-fricciones.md` + handoff (corrida 2, 2026-07-16).
**Resultado:** 7.5/10 (E1: 5, corrida 1: 7). Objetivo ≥8 NO alcanzado.
**Meta v3:** Dogfooding 3 con nota ≥8, cero cirugía a ciegas, ≤1 contacto humano por sesión.

---

## Decisiones de arquitectura modificadas por la evidencia

### D-V3.1 — Se revoca la aceptación del revert humano post-route (modifica D-R2/D-14.1)
D-14.1 aceptaba F8 + 1 recarga como toques humanos tolerables. La sesión real tuvo
**3 reverts** (uno por cada route de una sesión iterativa) más 1 aprobación de regla
más 1 pista en GUI = 5 contactos. El supuesto "1 route por sesión" era falso: el
ruteo real es iterativo. El revert deja de ser aceptable como costo fijo por
iteración. Prioridad: recarga programática (IPC `RevertBoard` o equivalente) o, si
el IPC no lo permite, batching documentado (N routes → 1 revert).

### D-V3.2 — TOON no crece; nace `get_tracks` (ratifica y extiende el scope de TOON)
La exclusión de tracks del TOON fue correcta para lectura de mundo (presupuesto).
La evidencia muestra que la cirugía necesita otra vista, no la misma vista más
gorda. Tool nueva de solo lectura: `get_tracks(net=|bbox=|layer=)` → segmentos y
vías con **ID estable**, endpoints, layer, width, net. El ID es el contrato para
D-V3.3. TOON queda intacto (F1 no se toca).

### D-V3.3 — Selección por ID reemplaza desambiguación por radio (modifica delete_track)
El radio fijo de 0.5mm hace inseleccionables segmentos cortos junto a uniones
(evidencia F-13: borrar de afuera hacia adentro). `delete_track(id=)` /
`delete_via(id=)` con IDs de get_tracks. La firma por coordenadas se conserva por
compatibilidad, pero el error debe entregar `data.candidates` con IDs (hoy los
promete y no llegan — bug).

### D-V3.4 — route_board deja de ser caja negra (modifica contrato de route_board)
Resultado enriquecido obligatorio:
- `route_ms` (deuda de DOS corridas — F-08 E1 y F-08 E2)
- Denominador claro: `nets_ruteables` (multi-pin) vs `nets_totales`; excluir
  unconnected-* de 1 pad del conteo
- Post-DRC integrado: resumen por net (ruteada / parcial / bloqueada)
- Nets bloqueadas con causa: "net X sin camino: bloqueada por net Y en layer Z"
  (evidencia F-12: /RESET imposible en 4 pases sin un solo mensaje)
- `drc_err` desglosado: preexistentes vs introducidos por este pase

### D-V3.5 — Las reglas del board viajan al DSN (modifica exportación a Freerouting)
Evidencia F-11: clearance al borde ~0.47 hardcodeado en Freerouting vs 0.5 del
board → 7 violaciones sistemáticas + relajación de regla aprobada a mano.
Inyectar al DSN: `min_copper_edge_clearance`, anchos por netclass (0.15 señal /
0.25 power del brief eran inalcanzables), clearances de netclass.

### D-V3.6 — El brief se genera con tools, no se redacta (proceso, vinculante para el arquitecto)
Tres fricciones de esta corrida (F-01 path, F-04 "ERC limpio" falso, F-07
dimensiones ~2× erradas + keepout imposible) fueron causadas por el brief, es
decir por el arquitecto. Riesgo 8 ocurrió por TERCERA vez. Regla nueva:
- Dimensiones de componentes: siempre de `get_component_detail`, nunca del texto
- Estado ERC: siempre de `run_erc` ejecutado, nunca declarado
- Paths: verificados con `ls` antes de escribirse en un prompt
- Chequeo geométrico grosero (suma de courtyards vs área de placa) antes de
  prometer keepouts

---

## Backlog v3 priorizado

### P1 — Visibilidad del cobre (F-13) — la fricción más cara (~50% de sesión)
1. `get_tracks(net=|bbox=|layer=)` con IDs estables (D-V3.2)
2. `delete_track(id=)` / `delete_via(id=)` (D-V3.3)
3. `add_track` acepta `from_pad` + coordenadas mezcladas (caso natural: reparación
   pad→punto)
4. Fix: `data.candidates` prometido en el hint debe llegar en la respuesta
5. Modelar roundrect de pads en la validación de colisiones del server (costó 2
   iteraciones DRC al agente con verificador casero)

**Criterio de cierre:** el patrón borrar→verificar→añadir ejecutable sin parsear
el .kicad_pcb con Python externo.

### P2 — route_board robusto (F-08, F-09, F-10, F-12)
1. Contrato D-V3.4 completo (route_ms, denominador, post-DRC por net, causas)
2. Reglas al DSN (D-V3.5)
3. Re-route incremental: limpieza previa de tracks huérfanos (pads movidos cuyos
   tracks quedaron) — con get_tracks (P1) se vuelve trivial detectarlos
4. Timeout adaptativo o hint temprano: si el pase previo tardó T, sugerir
   timeout_s ≥ 3T para incrementales

### P3 — Eliminar el revert humano (D-V3.1)
1. Investigar IPC: ¿existe RevertBoard / ReloadBoard en la API de KiCad 11?
2. Si sí: recarga programática post-route → 0 contactos humanos en ruteo
3. Si no: modo batch documentado (acumular mutaciones, 1 revert final) y
   evaluar rutear sobre el board vivo vía IPC en lugar de disco

### P4 — Zonas / plano GND
- `add_zone(net=, layer=, bbox=|polygon=)` mínimo viable (relleno rectangular)
- Evidencia: GND en estrella aceptable a 8MHz pero subóptimo para RF; el keepout
  de antena tampoco es expresable hoy
- Segunda utilidad: keepout zones (el brief pedía una y no existe la primitiva)

### P5 — Correcciones menores con evidencia
| Item | Evidencia | Fix |
|---|---|---|
| ERC posiciones ÷100 | F-03 | Bug de conversión de unidades en run_erc |
| health() no distingue estados | F-02 | `PROJECT_NOT_CONFIGURED` vs `PROJECT_PATH_NOT_FOUND` con hints distintos |
| move_footprint ignora Edge.Cuts | F-05 | El rango válido debe ser unión(bbox cluster ±100, bbox outline + margen) |
| Contorno inmutable | F-06 | `draw_board_outline(replace=true)` o `delete_board_outline` |
| CONTEXT_BUDGET_IMPOSSIBLE hint | log §7.6 | Recalcular mínimo real; hint decía ≈1001 y 1100 falló |
| DRC pos=[0,0] en edge clearance | F-11 | Reportar posición del track ofensor, no del rectángulo Edge.Cuts |

### Diferido (sin cambio)
- Eval A (TOON vs JSON/CSV) — sigue sin urgencia
- Rotación en move_footprint — deseable, no apareció como bloqueante en el log
- Tool de reglas (.kicad_pro) — el workaround manual con aprobación funcionó;
  reevaluar si vuelve a aparecer

---

## Deuda del esquemático (arquitecto + humano, NO server)

La placa fabricable actual hereda del sch:
- `pin_to_pin` INT U2↔U3 (dos outputs atados)
- `pin_not_connected` en U3
- Nets fusionadas: SCL→/INT_SENS y NSS→/MOSI (U4.3 y U4.5 en la misma net)

**La placa NO es eléctricamente correcta aunque el DRC dé 0.** Decisión requerida
del humano: ¿corregir el sch ahora (implica re-F8 + re-route completo) o aceptar
esta placa como artefacto de dogfooding y corregir para la fab real? Recomendación
del arquitecto: NO fabricar estos gerbers; corregir sch primero. El re-route será
además el primer test de P1/P2 cuando estén implementados.

También: J1 debe marcarse `in_bom no` en el sch (hoy aparece en bom.csv).

---

## Secuencia de sesiones propuesta

| Sesión | Contenido | Gate de salida |
|---|---|---|
| 16 | P1 completo (get_tracks + delete por ID + add_track mixto + candidates) | Cirugía de una net sin Python externo, test E2E |
| 17 | P2 (contrato route_board + reglas al DSN + limpieza huérfanos) | route_ms presente; net bloqueada reporta causa; anchos por netclass respetados |
| 18 | P3 (revert programático o batch) + P5 (menores) | Sesión de ruteo con 0 contactos humanos (o 1 si batch) |
| 19 | P4 (zonas mínimas) | Plano GND rectangular + keepout expresable |
| 20 | **Dogfooding 3**: corregir sch del despertador + re-route completo con todo lo nuevo | **Nota ≥8** |

Dogfooding 3 reutiliza la misma placa con el sch corregido: es el escenario
perfecto (re-route real, cirugía esperada, RF con zonas) y cierra la deuda
eléctrica pendiente.

---

## Qué respondió la evidencia a la pregunta 7 ("¿qué falta para usarlo todas las semanas?")

Las 6 respuestas del agente mapean 1:1 al backlog: visibilidad del cobre (P1),
route_board robusto (P2), sin revert humano (P3), zonas (P4), ergonomía de
cirugía (P1), detalles (P5). No hay pedidos fuera del backlog: la hoja de ruta
v3 ES la respuesta a la pregunta 7. Si las sesiones 16-19 cierran, el uso
semanal deja de tener bloqueantes conocidos.
