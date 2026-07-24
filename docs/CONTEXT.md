# CONTEXT.md — kicad-mcp

Consolidado desde `docs/historico/CONTEXT-v7.md` (post-sesión 24, 2026-07-23)
en la reorganización documental de 2026-07-24. Visión de largo plazo para que
un arquitecto externo entienda el sistema, sus decisiones y su estado sin
revisar el histórico completo. No es el punto de entrada del agente ejecutor
— para eso está `CLAUDE.md` + `hoja-de-ruta-v4.md` + `docs/BACKLOG.md` (ver
`docs/INDEX.md`).

Este documento **resume**; no duplica. El detalle de cada decisión vive en
`docs/DECISIONES.md`, la dirección estratégica vigente en `hoja-de-ruta-v4.md`
(raíz del repo; `docs/ROADMAP.md` es un resumen de estado, ya no repite la
secuencia), los pendientes priorizados en `docs/BACKLOG.md`. La cronología
completa de sesiones, métricas comparativas y hallazgos técnicos puntuales
quedan en `docs/historico/CONTEXT-v7.md` y `docs/historico/sesiones/`.

---

## Qué es el sistema

Servidor MCP que permite a un agente LLM (Claude Code) operar KiCad
autónomamente: leer el estado de esquemáticos/PCB en formato comprimido
(TOON), mutar mediante herramientas atómicas, y validar con ERC/DRC. El
proyecto ya superó el estadio de MVP solo-lectura: hoy tiene **20+ tools
productivas** con un **loop de escritura de PCB cerrado** — colocación,
contorno, zonas/plano GND, ruteo vía Freerouting (autorouter headless), DRC,
recarga programática, export de gerbers — sin reverts humanos en el camino.
Validado empíricamente contra KiCad 10.0.4 real en 5 rondas de dogfooding
(ver `docs/ROADMAP.md`).

**Objetivo del proyecto:** herramienta de calidad de referencia, no release
apurado. Publicar (open source u otro) solo cuando el ciclo de consolidación
actual (ver más abajo) cierre con estabilidad estadística demostrada.

## Arquitectura y principios de diseño

Diseño completo, decisiones D1–D6 y riesgos de fondo: `docs/arquitectura.md`.
Piezas clave que todo cambio debe respetar:

- **TOON v1** (`docs/specs/toon-v1.md`) — formato comprimido de contexto,
  actualizado por delta + área local en vez de resnapshot completo. Contrato
  F1: inmutable sin aprobación humana.
- **Snapshots vivos** — cache de estado en memoria; el snapshot post-mutación
  no lleva mtimes de disco (ADR-0007). Detección de cambios externos = polling
  de mtime, no eventos (el socket IPC de KiCad es request-reply, sin
  notificaciones async).
- **Bridge dual** — `kicad-python` (IPC, nanómetros) para operaciones en vivo
  y `kicad-cli` (subprocess, milímetros) para DRC/export. La conversión de
  unidades ocurre en el borde del bridge, con tipos distintos (`Nm`, `Mm`)
  para que mypy la valide — el bug off-by-10⁶ es el error de dominio #1
  histórico de este proyecto.
- **Gates de autonomía (G1–G5)** — backups, confirmación destructiva, budget
  de sesión; deterministas, no prompteados (ADR-0003). Frontera F2: la lógica
  y los umbrales no se tocan desde prompts.
- **Taxonomía de errores** `{code, message, hint}` — todo error se mapea a
  ella o se propaga; prohibido `except Exception: pass` o tracebacks crudos al
  agente. Códigos de error son API pública (frontera F3, catálogo completo en
  `docs/specs/tool-catalog.md`).
- **Fronteras inviolables F1–F5** (`docs/adr/0000-fronteras-inviolables.md`):
  specs/goldens, gates, códigos de error, versión objetivo de KiCad (10, mínimo
  9.0 — sin 11/nightlies), dependencias nuevas en `pyproject.toml`. Todas
  requieren aprobación humana explícita.

## Estado actual: Fase 3 — consolidación

El proyecto pasó de **Fase 2** (descubrimiento acelerado: ciclo intensivo
fix → dogfooding → nuevo bug, sesiones 20-24) a **Fase 3** (consolidación y
aumento progresivo de confianza, arranca en sesión 25). El objetivo de Fase 3
ya no es "encontrar causa raíz" sino "ganar confianza estadística en que las
causas raíz eliminadas realmente no vuelven".

**Estado en una línea (post-sesión 26):** D5 (sesión 25) — primer dogfooding
de Fase 3 — salió **verde, 9.5/10**; contrato D-23.2 ratificado **5/5
corridas** en producción real. Sesión 26 refutó con evidencia geométrica la
hipótesis de D5 sobre P1 (el keepout de hole NO cubría el caso de máscara
por accidente, como se creía), confirmó que el bug de `solder_mask_bridge`
es real y alcanzable con valores de `pad_to_mask_clearance` realistas, pero
el fix diseñado con el arquitecto **no resolvió el bug en verificación
contra KiCad real** — mecanismo no aislado, P1 queda **abierto** como
investigación pendiente (re-estimado M/L). Sin P0 nuevos. Próximo paso:
sesión 27 (generalización D-23.2 a `fill_zones`/`add_zone(fill=True)`, no
bloqueada por P1 — ver `docs/BACKLOG.md`). Detalle:
`docs/historico/sesiones/25-reporte.md`,
`docs/investigacion/26-solder-mask-ant1.md`,
`docs/historico/sesiones/26-reporte.md`.

**Qué cerró Fase 2:** F-D4-02 — el último P0 conocido (bug de orden de
medición + falta de persistencia en `route_board`, causaba que el DRC
post-route reportado no coincidiera con el estado real en disco). Cerrado en
sesión 24 (Opción X: reordenar medición + persistir + fallo visible si el save
falla), documentado en `docs/adr/0012-route-board-persist-contract.md`, con
test de regresión en vivo 2/2 corridas contra KiCad 10.0.4 + Freerouting real.

**Qué ratificó D5 (sesión 25):** primer dogfooding de Fase 3 sobre la placa
despertador (misma variable controlada que D3/D4). El contrato D-23.2 se
sometió a un cross-check reforzado (V2) en 3 corridas consecutivas de
`route_board` — `err_post` coincidió exacto (total y `por_tipo`) con
`run_drc()` independiente inmediato en las 3, mtime del `.kicad_pcb` cambió
post-save las 3 veces, cero `EXTERNAL_EDIT_DETECTED` espurio. Sumado a las
2/2 corridas del test de regresión de sesión 24, el contrato acumula **5/5
ratificaciones en producción real, sin excepción** — el workaround manual de
refill (`delete_zone`+`add_zone`) que el fixture de D3 documentaba como
obligatorio quedó explícitamente obsoleto. D5 también re-ratificó dos
decisiones informales: **D-D4.1** (`get_footprint_neighbors` inclusivo,
aplicado más allá de conectores, detectó BT1/U4 fuera del contorno antes de
rutear) y **D-19c.1** (`add_keepout_zone` POST-route es inocuo — test
explícito en Fase 7 de D5, 0 errores DRC nuevos). Único hallazgo: F-D5-01
(isla GND sin vía al plano tras el primer autoroute, severidad `info`,
resuelta con `add_via` puntual con visibilidad completa, sin cirugía a
ciegas) — ver `docs/BACKLOG.md` P3.

**Ciclo de Fase 3:**
```
[Dogfooding ratificación] → [Sesión de fix pequeña si corresponde] →
[Nuevo dogfooding] → [Repetir hasta 2-3 verdes consecutivos]
```
Reglas: cada bug nuevo se registra (F-DN-XX); un P0 nuevo durante Fase 3 se
sospecha regresión del último fix mergeado hasta que se pruebe lo contrario
(al revés de Fase 2, donde se sospechaba gap nuevo); todo fix trae test de
regresión; **no escalar complejidad hasta 2-3 verdes consecutivos**.

**Interpretación de resultados de dogfooding en Fase 3** (invertida respecto a
Fase 2 — importante para quien retome el rol):
- **Verde** (nota ≥9, 0 P0/P1 nuevos) → evidencia positiva de convergencia,
  avanzar al siguiente paso.
- **Amarillo** (nota 8-8.9, 1-2 P1) → ciclo continúa: fix + próximo dogfooding.
- **Rojo** (V3 activada, P0 nuevo, nota <8) → señal fuerte de regresión,
  investigación mandatoria antes de continuar.

Un dogfooding aburrido (sin hallazgos) es la señal buscada en Fase 3, no un
desperdicio de sesión — ver "disciplina de Fase 3" más abajo.

**Criterio operacional de convergencia** (condición para pensar en Fase 4 —
release / features nuevos / escenarios más complejos):
- ≥2-3 dogfoodings consecutivos verdes (nota ≥9) sobre la misma placa.
- P1 conocido (solder mask bridge ANT1) resuelto — **reabierto tras sesión
  26**: bug confirmado real, fix no verificado, investigación pendiente
  (ver `docs/BACKLOG.md` P1, `docs/investigacion/26-solder-mask-ant1.md`).
  No bloquea el resto de la secuencia de convergencia (D-23.2 sí puede
  avanzar en paralelo).
- Generalización del contrato D-23.2 a `fill_zones`/`add_zone(fill=True)`
  completada y ratificada.
- Sin P0 nuevos en la superficie ratificada.

Secuencia y estado detallado de cada paso: `hoja-de-ruta-v4.md` (raíz del
repo); historial de dogfooding: `docs/ROADMAP.md`.

## Decisiones vigentes

Índice completo con ADR y decisiones informales: `docs/DECISIONES.md`. Las que
más condicionan trabajo futuro:

- **Contrato disco==memoria==reportado** (ADR-0012 / D-23.2): hoy garantizado
  solo en `route_board`. `fill_zones` y `add_zone(fill=True)` todavía no lo
  cumplen — es la generalización pendiente de Fase 3 (paso 3 de la secuencia).
- **KIID sobre coordenadas/radio** para desambiguar cobre (`delete_track`,
  `delete_via`) — D-V3.3.
- **Reglas del board viajan al DSN de Freerouting** (edge clearance vía
  ingeniería inversa de bytecode) — D-V3.5.
- **Nunca `add_keepout_zone` antes de un `route_board` autorruteado desde
  cero** — bloquea nets sistemáticamente (D-19c.1). Aplicar keepouts después
  del ruteo. Re-ratificado en D5 (sesión 25, Fase 7): keepout redundante
  agregado POST-route sobre ANT1 no generó errores DRC nuevos.
- **`get_footprint_neighbors` inclusivo, no acotado a conectores** (D-D4.1,
  origen sesión 22): aplicar a cualquier footprint denso o con incertidumbre
  geométrica antes de colocar. Re-ratificado con impacto real en D5: detectó
  BT1/U4 con bbox fuera del contorno del board antes de invertir tiempo en
  ruteo.
- **Fixture helper runtime > directorio estático con coords hardcodeadas**
  para tests que dependen de geometría del board (D-24.1) — la copia de
  trabajo real puede tener origen absoluto distinto del fixture crudo.
- **Baseline dinámico + delta > allowlist estática** para verificar que un
  cambio no introduce errores nuevos en placas con DRC preexistente (D-24.2):
  `run_drc()` inicial registra el residual, mediciones posteriores comparan
  solo deltas.

## Riesgos abiertos

Detalle priorizado y esfuerzo estimado: `docs/BACKLOG.md`. Los que más
condicionan decisiones de arquitectura o pueden bloquear un dogfooding futuro:

| # | Riesgo | Estado |
|---|---|---|
| R12 | Tools de escritura de esquemático son puramente aditivas (sin CRUD) | Abierto, no ejercitado en D3/D4/24 |
| R13 | `get_world_context(kind="sch")` falla con símbolos `#PWR*`/`#FLG*` | Ratificado en D4, workaround `export_netlist()` |
| R14 | `fill_zones`/`add_zone(fill=True)` no garantizan el contrato disco==memoria | Cerrado en `route_board`; residual abierto hasta generalización D-23.2 |
| R16 | Loop de vías de `enforce_hole_clearance` posiblemente código muerto | Deuda técnica (D-23.3), no tocar en Fase 3 salvo evidencia nueva |
| R9 | `Freerouting gui.enabled=true` cuelga la JVM | Mitigado en código, issue upstream pendiente |

## Precondiciones y conocimiento para decisiones futuras

Errores de dominio recurrentes — cualquiera que toque el bridge o mutaciones
de PCB/esquemático debe conocerlos (fuente completa: `CLAUDE.md` §"Errores de
dominio", `docs/glosario.md`):

- IPC usa **nanómetros**; los archivos usan **mm**. Convertir siempre en el
  borde del bridge.
- Pines de esquemático fuera de la grilla de **1,27 mm (50 mil)** no conectan.
- Dos wires cruzados sin junction **no están conectados** — proximidad ≠
  conexión. El neteo de esquemático es por coincidencia de texto de label, no
  por geometría (D-19b.2).
- El socket IPC es **request-reply, sin eventos async** — nada de loops de
  polling contra el socket. Todo request se procesa en el hilo de UI de KiCad:
  timeout duro de 2s, cola de profundidad 1.
- `KICAD_API_TOKEN` cambia por instancia — úsalo para detectar reinicios.

Disciplina de proceso para quien opere en Fase 3 (arquitecto o agente):
resistir la tentación de forzar hallazgos donde no los hay o escalar
complejidad prematuramente "para que la sesión valga la pena". La convergencia
estadística es evidencia positiva incluso cuando se siente aburrida.

Antes de aceptar "X escala mal" o "X no funciona" como conclusión, exigir
prueba de que X aislado también falla — dos veces una conclusión así resultó
estar causada por un factor externo combinado, no por X en sí.
