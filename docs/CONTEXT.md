# CONTEXT.md — kicad-mcp

Consolidado desde `docs/historico/CONTEXT-v7.md` (post-sesión 24, 2026-07-23)
en la reorganización documental de 2026-07-24. Visión de largo plazo para que
un arquitecto externo entienda el sistema, sus decisiones y su estado sin
revisar el histórico completo. No es el punto de entrada del agente ejecutor
— para eso está `CLAUDE.md` + `hoja-de-ruta-v5.md` + `docs/BACKLOG.md` (ver
`docs/INDEX.md`).

Este documento **resume**; no duplica. El detalle de cada decisión vive en
`docs/DECISIONES.md`, la dirección estratégica vigente en `hoja-de-ruta-v5.md`
(raíz del repo; `docs/ROADMAP.md` es un resumen de estado, ya no repite la
secuencia), los pendientes priorizados en `docs/BACKLOG.md`. La cronología
completa de sesiones, métricas comparativas y hallazgos técnicos puntuales
quedan en `docs/historico/CONTEXT-v7.md` y `docs/historico/sesiones/`.

---

## Coordinación multiagente vigente

Desde 2026-08-10 el trabajo híbrido usa un ciclo orientado a objetivos:
Claude Chat propone una unidad completa; ChatGPT realiza una auditoría previa
única; Claude Code ejecuta investigación, implementación y pruebas dentro del
alcance; Codex revisa la unidad terminada; Claude recibe el estado y cierra o
propone el objetivo siguiente. Gato conserva objetivo, alcance, excepciones,
publicación, push, PR y merge.

El piloto S40–S48 se conserva como evidencia histórica. Demostró que la
separación de roles es útil, pero que auditorías recursivas, contratos extensos
y empaquetado obligatorio para trabajo read-only generan un costo
desproporcionado. Esos mecanismos no son precedentes para ciclos nuevos.

Autoridades: `AGENTS.md` para reglas institucionales y
`docs/proceso/FLUJO-HIBRIDO-MULTIAGENTE-v2.md` para el protocolo operativo.

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

## Fases del proyecto

### Fase 1 (histórica): construcción del núcleo — sesiones 1-15
Diseño arquitectónico, primera implementación del bridge, primeras tools.
Cerrada con D1/D2 (dogfoodings tempranos).

### Fase 2 (histórica): hardening — sesiones 16-24
Cierre de bugs P0/P1 identificados en dogfoodings, contrato D-23.2 en
route_board (ADR-0012). Cerrada con generalización D-23.2 a fill_zones y
add_zone en sesión 27.

### Fase 3 (histórica): consolidación y aumento progresivo de confianza — sesiones 25-29
Ratificación estadística del contrato D-23.2 en las tres tools mediante
dogfoodings verdes sobre variable controlada. Cierre 2026-07-25 con 3
verdes consecutivos (D5=9.5, D6=9.7, D7=9.8), D-23.2 en 25/25 en producción
real, D-26.1 ratificado sin confusor, F-D6-01 y F-D5-01 cerrados.

### Fase 4 (activa): preparación para Open Source como proyecto de referencia — sesiones 30+

**Ambición estratégica:** convertir la arquitectura estable de Fase 3 en un
proyecto Open Source de alta calidad, con evidencia suficiente para respaldar
cada decisión importante. NO es expansión desordenada de capabilities.

**Criterio de decisión de Fase 4:** cada decisión se evalúa preguntando si
aumenta calidad, mantenibilidad, confianza, o experiencia de futuros
colaboradores. Ver D-30.2.

**Secuencia acordada** (ver `hoja-de-ruta-v5.md` para detalle):

1. **Investigación P1 solder mask ANT1** (sesión 30) — cierre de la única
   deuda técnica arrastrada de Fase 3 antes de exponer el proyecto.
2. **Validation Suite: primera validación de nivel A** (sesión 31) —
   primer dogfooding sobre placa ajena al despertador. Doble función:
   escalada de complejidad + arranque de la Suite.
3. **Validaciones de nivel B y C** (sesiones 32-33) — cobertura ampliada
   antes de release.
4. **Preparación de release Open Source** (sesión 34+) — docs, licencia,
   ADRs, guía de contribución, limpieza del repositorio. **Solo cuando**
   las 3 validaciones anteriores hayan cerrado exitosamente.
5. **Features nuevas** (post-release) — según necesidad detectada en uso
   real o por adopción de colaboradores, no por especulación.

**Deuda arrastrada de Fase 3 → CERRADA en sesión 30.** P1 solder mask
ANT1: mecanismo aislado (déficit de apotema del keepout circular, N=16
insuficiente a radios ~1.8mm) y fix aterrizado (N=16→64 +
`enforce_hole_clearance` recalcula el término de máscara). Ver D-30.5 y
`docs/investigacion/30-solder-mask-ant1.md`. Mergeado a `master`
(`802a32a`).

**Principios metodológicos vigentes en Fase 4:**
- D-30.1: estrategia de validación explícita antes de implementar.
- D-30.2: éxito por confianza, no por código.
- D-30.3: comparación cuantitativa contra ground truth en Validation Suite.
- D-30.4: criterio de diversidad para admisión a Validation Suite.
- D-30.5: mecanismo de apotema en keepouts circulares (sesión 30, cierre P1).
- D-31.1: convenciones estructurales de la Validation Suite (sesión 31).
- D-31c.1: cross-check obligatorio contra ADRs vigentes al fijar el marco
  de un prompt de sesión (sesión 31c).
- D-32.1: criterio DRC separado por severidad (eléctrico/estructural/
  cosmético) para el criterio DRC de D-30.3 (sesión 32).
- D-32b.1: `POST_ROUTE_REFILL_SKIPPED` — error explícito sin retry (D-07.1
  intacta) cuando el refill de seguridad de `route_board` se salta por
  fallo real de `reload_board_from_disk` (sesión 32b, cierre
  F-V2-REFILL-SILENCIOSO).
- D-32b.2: alcance del fix F-V2 acotado a `route_board` — H2 (¿afecta
  también a `fill_zones`/`add_zone`?) refutada por inspección (sesión 32b).
- D-32c.1: el objetivo de una investigación es reducir incertidumbre, no
  producir un fix (formaliza directriz de Fase 4, sesión 32c).
- D-32c.2: mecanismo raíz de F-D5-01 aislado y confirmado causalmente
  (clearance de copper de otro net estrangulando el corredor de un pad
  GND al plano, refinamiento de D-19.1); fix diferido a sesión 32d
  (sesión 32c).
- D-32d.1: fix de F-D5-01 — stitching automático de vías (`add_via`) bajo
  5 guardrails geométricos estrictos dentro de `route_board`, fallback a
  exposición explícita (`orphan_pads`) si un guardrail rechaza (sesión
  32d, extiende ADR-0012).
- D-32d.2: rechazo de guardrail nunca es error — sólo fallo técnico de
  `add_via` o de `save_board()` post-stitching lo son, con códigos ya
  existentes, sin códigos nuevos (sesión 32d).
- D-33.1: principio de refutación — toda hipótesis/explicación se
  formula preguntando primero "¿qué resultado la refuta?", generaliza a
  todo el proyecto lo que D-30.1/D-31c.1 ya exigían en sus contextos
  específicos (sesión 33, metodológico, permanente).
- D-34a.1: los 4 ejes del contrato de escritura del bridge (persistencia,
  propagación de errores, sincronización disco↔memoria, manejo de
  reload) — checklist estándar para auditorías futuras y para
  `CONTRIBUTING.md §How to add a write tool` (sesión 34a, metodológico,
  permanente).
- D-34a.2: hallazgos de asimetría de la auditoría 34a —
  `delete_tracks_bulk`/`delete_zone`/`add_keepout_zone` no aplican el
  pipeline refill+enforce+save de D-23.2/ADR-0012 pese a tocar geometría
  que interactúa con zonas; ADR-0012 se ratifica correcto en su alcance
  declarado (sesión 34a).
- ADR-0013: refs duplicados/sin anotar se resuelven por anotación, no
  borrado — `set_footprint_ref` + pre-check `DUPLICATE_REFS` en
  `route_board` (sesión 31b, cierre F-V1-02). ADR-0010 intacta.
- D-27.1: restore no destructivo del entorno GUI vivo (heredada).
- D-28.1: cambios de orden de fases requieren AskUserQuestion (heredada).
- D-28.2: barrido completo al generar diffs de decisiones (heredada).

**Interpretación de resultados en Fase 4** (ratificada por sesión 31):
la interpretación "un P0 nuevo se sospecha regresión hasta prueba en
contrario" fue apropiada durante Fase 3 (consolidación sobre variable
controlada). En Fase 4, con placas ajenas al despertador, un P0 nuevo
puede ser gap legítimo del flujo sobre decisiones de diseño no
ejercitadas antes — no regresión por default. Sesión 31 confirmó esta
interpretación en la práctica: `F-V1-02` (refs de footprint duplicados
bloquean `route_board`) es un gap real del flujo, expuesto por una
condición de diseño (refs sin anotar) que el despertador —única placa de
Fase 1-3— nunca ejercitó, no una regresión del código.

**Estado de la secuencia de Fase 4** (post-sesión 33, 2026-07-30):
1. Investigación P1 solder mask ANT1 — ✅ cerrada (sesión 30).
2. Validation Suite Nivel A — **✅ cerrada (sesión 31c).** Sesión 31
   admitió `anavi-dev-mic` (con excepción documentada de criterio 6) y
   ejecutó el flujo canónico hasta `route_board`, donde se detuvo por
   hallazgo P0 (`F-V1-02`, refs de footprint duplicados/sin anotar rompen
   la exportación DSN a Freerouting). Sesión 31b (fix intermedio) cerró
   F-V1-02 y F-V1-01: `set_footprint_ref` (ADR-0013, resuelve por
   anotación, no borrado — ADR-0010 queda intacta) + pre-check
   `DUPLICATE_REFS` en `route_board`; fix de `read_board_context`/
   `board_bbox_mm` para leer Edge.Cuts (unión con el enjambre de
   footprints, no reemplazo). **Sesión 31c reintentó el flujo completo
   sobre el mismo `working/`**: `route_board` completó (15/15 nets
   ruteables, 0 bloqueadas), H1a y H1b confirmadas (0 fricciones P0/P1
   nuevas, 1 fricción P2 nueva — `F-V1c-01`, vía GND sin conectar a un
   pad de 0.30mm). Los 4 criterios D-30.3 se **midieron** de punta a
   punta (1/4 cumple umbral — cobre; tracks y vías no cumplen, DRC
   coincide en conteo pero no en composición) — primer punto real de
   evidencia sobre H2 (discriminancia de umbrales): el umbral de vías
   (±20% sobre una base de 2) resultó no discriminante para bases
   pequeñas, candidato a revisión post-sesión 33. Escenario de cierre:
   5 ("aprendizaje metodológico") con elementos de 2 ("éxito con matiz de
   umbrales"). Ver `validation-suite/level-a/anavi-dev-mic/validation-report.md`,
   `metrics.md` y `docs/historico/sesiones/31c-reporte.md`.
3. Validation Suite Nivel B — **✅ cerrada (sesión 32).** Candidato
   prescrito (ANAVI Miracle Emitter) refutado en Bloque 0 (sin
   diversidad D-30.4 real, escala menor que Nivel A); admitido
   `anavi-macro-pad-12` (63 footprints, 48 nets, OSHWA certificado).
   Flujo canónico completo: `route_board` completó (42/42 nets
   ruteables, 0 bloqueadas) tras un primer intento con timeout (óptimo
   local real del router, no falta de tiempo — variabilidad consistente
   con F-D6-01). **3 de 4 criterios D-30.3 cumplen** (tracks −4.05%,
   vías +20.00% exacto en el borde, cobre +3.23%) — mejor resultado que
   Nivel A (1/4). DRC no cumple por conectividad GND puntual. Segundo
   punto de evidencia H2: con base de vías 15x mayor que Nivel A, el
   umbral ±20% resultó razonablemente calibrado (borde, no falla
   amplia) — apoya normalizar por tamaño de base, no cambiar el umbral.
   **Hallazgo independiente de robustez:** `route_board(refill=true)`
   puede fallar en silencio su paso de refill de seguridad
   (`F-V2-REFILL-SILENCIOSO`, P0/P1, confirmado reproducible también en
   el audit log de sesión 31c) — agenda de sesión de fix intermedia
   antes de sesión 33. **Reincidencia confirmada del patrón F-D5-01/
   F-V1c-01** (3ª instancia, ahora `F-V2-VIA-HUERFANA`) — promovido a P1
   investigación Fase 4. Escenario de cierre: 3 ("éxito con matiz de
   fricciones P2/P3") con elementos de 2. Ver
   `validation-suite/level-b/anavi-macro-pad-12/validation-report.md`,
   `metrics.md` y `docs/historico/sesiones/32-reporte.md`.
4. Preparación de release Open Source — pendiente, sesión 34+.
   **F-V2-REFILL-SILENCIOSO cerrado (sesión 32b):** la excepción de
   `reload_board_from_disk` ya no se descarta en silencio — cuando el
   refill de seguridad de `route_board(refill=true)` no puede correr por
   esa causa concreta (con ≥1 zona existente), la tool levanta
   `POST_ROUTE_REFILL_SKIPPED` en vez de completar como éxito silencioso
   (D-32b.1). H2 del prompt (¿afecta también a `fill_zones`/`add_zone`?)
   quedó refutada por inspección — ninguna de las dos llama
   `reload_board_from_disk` (D-32b.2, ver ADR-0012
   §"Extensión F-V2 (sesión 32b)").
   **Investigación P1 F-D5-01 cerrada (sesión 32c):** mecanismo raíz
   aislado y confirmado causalmente sobre el motor real de KiCad (patrón
   sesión 30) — Freerouting rutea tracks de otro net sin reservar
   corredor para que el flood-fill del plano GND alcance pads
   específicos (refinamiento medido de D-19.1); cuando ese track ajeno
   corre en el mismo rango Y que un pad GND en un corredor angosto, su
   clearance obligatorio corta el corredor por completo. Confirmado con
   2 experimentos de borrado dirigido + re-fillado real
   (`kicad-cli pcb drc --refill-zones --save-board`) sobre copias
   desechables en anavi-macro-pad-12, generalizado por correlación
   fuerte en anavi-dev-mic. 3 hipótesis alternativas refutadas con
   experimentos causales (`island_removal_mode`, keepouts de
   `enforce_hole_clearance`, fill totalmente despojado). Corrección de
   encuadre a mitad de sesión: el Bloque 0 inicial parecía fallar en las
   3 manifestaciones por un bug de medición propio de los scripts de la
   sesión (campo JSON equivocado, no presente en `src/`); corregido, 2
   de 3 reproducen exactamente. Fix diferido a **sesión 32d** (vive en
   el pipeline de refill/zonas de `route_board`, fuera del alcance
   quirúrgico de 32c) con hipótesis completamente especificada
   (D-32c.1, D-32c.2, `docs/investigacion/32c-f-d5-01.md`,
   `docs/historico/sesiones/32c-reporte.md`).
   **F-D5-01 cerrado parcialmente (sesión 32d):** stitching automático de
   vías bajo 5 guardrails geométricos dentro de `route_board`, fallback a
   exposición explícita (`orphan_pads`) cuando un guardrail rechaza
   (D-32d.1/D-32d.2, ADR-0012 §"F-D5-01 stitching"). Hallazgo que corrige
   una premisa de 32c: las 3 manifestaciones NO comparten topología de
   capas — `anavi-macro-pad-12` (`J4.3`/`J5.3`) tiene el pad y la única
   zona GND en la MISMA capa (sin cobre GND en la capa opuesta), así que
   el guardrail #4 rechaza por diseño: una vía ahí no conectaría nada.
   H1 se re-baselineó de macro-pad-12 a `anavi-dev-mic` (topología "capas
   opuestas", donde el stitching sí cierra el síntoma); macro-pad-12
   pasó a ser el caso canónico de rechazo correcto de guardrail (H2) y
   queda **abierto** como sub-patrón `F-D5-01-B` (estrangulamiento
   lateral en la misma capa, `docs/BACKLOG.md`). Verificación: canario
   unit permanente (8 tests) + suite offline/integration completas
   verdes; verificación end-to-end contra el motor real
   (`test_pcb_session32d_stitching_gui_slow.py`, marker
   `integration_gui_slow`) escrita pero **pendiente de ejecución
   humana** (requiere abrir cada proyecto en el PCB Editor de KiCad,
   sin automatización posible en este MVP — confirmado con un probe
   directo por IPC en sesión 32d). Ver
   `docs/historico/sesiones/32d-reporte.md`.
3. Validation Suite Nivel C — **✅ cerrada (sesión 33), cierra la
   trilogía A+B+C.** Admitido `hackrf-one` (Great Scott Gadgets, 437
   footprints, 380 nets, 4 capas — ~7× Nivel B) con 3 correcciones D-33.1
   a premisas del prompt (fecha de mantenimiento, licencia CERN-OHL-P,
   escala real del `.kicad_pcb`). **Resultado: Escenario 6/7 —
   refutación por escalabilidad.** `route_board` no completó: Freerouting
   2.1.0 entró en un régimen de excepciones internas repetidas
   (`NullPointerException` en `MazeSearchAlgo`, sin progreso medible en
   ~55 min) hasta el timeout duro de 3600s — diagnóstico distinto al de
   sesión 32 (score estancado cerca de completar). Los 4 criterios
   D-30.3 quedan **no evaluables** (sin ruteo, forzar ratios habría sido
   precisión falsa). **Hallazgo independiente reproducido 3 veces:**
   `add_zone(fill=true)` crashea KiCad de forma determinística en la
   3ª-4ª llamada consecutiva sobre boards de esta escala, sin
   correlación con overlap geométrico (hipótesis de overlap refutada
   explícitamente en el 2º intento — D-33.1 en acción el mismo día de
   su adopción). Registrado `F-V3-ZONE-FILL-CRASH` (P0/P1) y
   `F-V3-ROUTER-TIMEOUT-HARD` (P0, bug upstream de Freerouting). D-33.1
   (principio de refutación) formalizado al cierre. Síntesis de los 3
   puntos de evidencia sobre D-30.3 en
   `docs/analisis/validation-suite-sintesis-A-B-C.md` — recomienda
   mantener tracks/cobre, revisar con cautela vías (evidencia
   insuficiente), formalizar el criterio DRC por severidad (D-32.1,
   confirmado 3/3), e incorporar la descomposición por capa (nueva en
   esta sesión) como métrica auxiliar para boards multi-capa. Ver
   `validation-suite/level-c/hackrf-one/validation-report.md`,
   `metrics.md` y `docs/historico/sesiones/33-reporte.md`.

5. Sesión 34a — **auditoría sistemática de contratos de escritura del
   bridge — ✅ cerrada (2026-07-30).** Cumple el compromiso formal del
   arquitecto post-32b: auditó las 19 tools de escritura del bridge (20
   filas de matriz, `add_zone` dual-mode) contra los 4 ejes (persistencia,
   propagación de errores, sincronización disco↔memoria, manejo de
   reload — D-34a.1). Refutó el inventario preliminar del prompt en 3
   puntos (`delete_footprint`/`clone_symbols` no existen como tools;
   `add_keepout_zone`/`delete_zone`/`save_board`/`reload_board_from_disk`
   faltaban). **3 asimetrías confirmadas** (D-34a.2): `delete_tracks_bulk`
   (P1, refill sin enforce/save, agendada `34a-fix-1`), `delete_zone` y
   `add_keepout_zone` (P2, sin refill/save sobre zonas vecinas, sin
   precedente empírico, documentadas como limitación). **1 asimetría
   nueva fixeada in-situ:** `draw_board_outline` era la única tool W-IPC
   de PCB sin `_guard_live_stale()`/`check_no_external_disk_edit()`
   (asimetría A7) — fix trivial de 2 líneas + 2 tests offline nuevos
   (patrón `mark_live_stale`/edición externa ya usado en el repo, sin
   fixtures nuevas), calificó bajo los 5 criterios estrictos del Bloque 3.
   `F-V3-ZONE-FILL-CRASH` quedó **no concluyente**: el análisis de código
   no encontró causa del lado del bridge, pero la reproducción empírica
   planeada (harness sintético) no se ejecutó — el único KiCad vivo
   disponible tenía abierto precisamente el proyecto HackRF One que ya
   crasheó 3/3 veces en sesión 33, y no hay tooling para abrir un
   proyecto distinto sin operar la GUI; se optó por no asumir ese riesgo
   sin decisión deliberada. ADR-0012 (D-23.2) se ratifica correcto en su
   alcance declarado — la auditoría no encontró que el contrato mismo
   esté mal formulado. Suite offline 394/394 verde, `ruff`/`mypy`
   limpios. Ver `docs/analisis/auditoria-contratos-bridge.md` (documento
   principal, input para 34b/34c) y `docs/historico/sesiones/34a-reporte.md`.

6. Sesión 34b — **LICENSE + NOTICE + README público + CONTRIBUTING.md —
   ✅ cerrada (2026-07-31).** Primera exposición pública consciente del
   proyecto: escritura estructurada de documentación OSS a partir del
   input consolidado en `docs/analisis/auditoria-contratos-bridge.md` §6
   (sesión 34a). Entregables: `LICENSE` (Apache 2.0, titular "The
   kicad-mcp contributors"), `NOTICE` (dependencias con licencia distinta
   — corrige la premisa del prompt original: `kicad-skip` es
   LGPL-2.1-or-later, no MIT; documenta que `pcbnew` se invoca por
   subprocess contra el Python del sistema, nunca importado en el venv),
   `README.md` reemplazado por versión pública en inglés (pitch + escala
   validada + 10 limitaciones conocidas, cada una linkeada a su fuente),
   `README.es.md` (traducción resumida), `CONTRIBUTING.md` (setup + los 3
   hábitos metodológicos de Fase 4 en lenguaje accesible + los 4 ejes de
   D-34a.1 con ejemplos concretos + checklist de PR). Cada afirmación
   pública pasó el filtro D-33.1, auditable en
   `docs/analisis/readme-honestidad-check.md` (16/16 sostenidas, 2 con
   matiz ya incorporado al texto). Precondiciones de rama del prompt
   original no se cumplían (`master` sin renombrar a `main`, `sesion-01`
   viva) — se ramificó desde `master` sin bloquear la sesión, rename
   diferido al arquitecto. Suite offline 394/394 sin cambios (sesión
   puramente documental, `src/` intocado). Ver
   `docs/historico/sesiones/34b-reporte.md`.

**34a-fix-1 (fix de `delete_tracks_bulk`, asimetría A1)** es la próxima
sesión, con la salvedad de que `F-V3-ZONE-FILL-CRASH` y el crash-loop de
Freerouting quedan como candidatos a investigación intermedia si
reaparecen antes del release. Precede a **34c** (docs de arquitectura
para colaboradores externos), de modo que 34c documente la asimetría A1
ya resuelta.

## Estado actual: Fase 3 — consolidación (histórico, cerrada sesión 29)

El proyecto pasó de **Fase 2** (descubrimiento acelerado: ciclo intensivo
fix → dogfooding → nuevo bug, sesiones 20-24) a **Fase 3** (consolidación y
aumento progresivo de confianza, arranca en sesión 25). El objetivo de Fase 3
ya no es "encontrar causa raíz" sino "ganar confianza estadística en que las
causas raíz eliminadas realmente no vuelven".

Estado (post-sesión 29, 2026-07-25): **Fase 3 CERRADA con criterio de
convergencia cumplido** — 3 verdes consecutivos (D5=9.5, D6=9.7,
D7=9.8), D-26.1 ratificado sin confusor, D-23.2 acumulado 25/25 en
producción real (route_board 12/12 + fill_zones 7/7 + add_zone 6/6, 0
divergencias), F-D6-01 cerrado como variabilidad inherente
Freerouting/JVM. Deuda arrastrada a Fase 4 (P1 solder mask ANT1) cerrada
en sesión 30 — ver §"Estado actual: Fase 4" arriba para el estado
vigente del proyecto.

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

Secuencia y estado detallado de Fase 3: `docs/historico/roadmaps/hoja-de-ruta-v4.md`
(archivada); historial de dogfooding: `docs/ROADMAP.md`. Hoja de ruta
vigente (Fase 4): `hoja-de-ruta-v5.md` (raíz del repo).

## Decisiones vigentes

Índice completo con ADR y decisiones informales: `docs/DECISIONES.md`. Las que
más condicionan trabajo futuro:

- **D-23.2 (ratificado en 3 tools, criterio de convergencia cumplido):**
  contrato disco==memoria aplicado a `route_board` (sesión 24, ADR-0012),
  `fill_zones` (sesión 27, extensión ADR-0012), `add_zone(fill=True)`
  (sesión 27, extensión ADR-0012). **Acumulado 25/25 corridas verdes en
  producción real** (route_board 12/12 + fill_zones 7/7 + add_zone 6/6),
  0 divergencias, Fase 3 cerrada con 3 verdes consecutivos (D5/D6/D7) —
  drift corregido en sesión 31c (esta entrada seguía citando el conteo
  intermedio 15/15 pre-D7, ya desactualizado desde el cierre de Fase 3 en
  sesión 29). **Caveat sesión 32b:** ese 25/25 cuenta corridas donde el
  refill efectivamente corrió; no cubre el modo de falla
  F-V2-REFILL-SILENCIOSO (refill saltado en silencio por fallo de
  `reload_board_from_disk`), cerrado en sesión 32b con `POST_ROUTE_REFILL_SKIPPED`
  (D-32b.1). Ver `docs/DECISIONES.md` §2 y ADR-0012 §"Extensión de
  alcance (sesión 27)" + §"Extensión F-V2 (sesión 32b)" para detalles.
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
- **D-26.1 (ratificado sin confusor, sesión 29 D7):** refill obligatorio
  post-colocación pre-baseline DRC. `move_footprint` no dispara refill de
  zonas — sin `fill_zones()` explícito entre colocación masiva y baseline
  DRC, el baseline mide fill rancio. Ratificación empírica limpia en D7
  (V4.a=6 violaciones fantasma, V4.b=0 tras `fill_zones()`), con layout
  distinto de D5/D6 y orden de fases correcto (D-28.1). El fenómeno
  depende del orden de fases y del footprint set, no del layout específico
  — aplicable a cualquier flujo con este patrón. Ver `docs/DECISIONES.md`
  y C7 abajo.
- **D-28.1 — Cambios de orden de fases requieren AskUserQuestion**
  (operacional, ver `docs/DECISIONES.md`). Cambio de orden de fases en un
  brief es cambio de metodología, no de implementación, y contamina el
  experimento si se hace sin consultar. Origen: D6 invirtió el orden
  plano-vs-colocación respecto al brief sin AskUserQuestion, introduciendo
  confusor en la ratificación de D-26.1.
- **D-28.2 — Deuda del arquitecto: barrido completo al generar diffs de
  decisiones.** Cuando se actualiza una decisión en el proyecto, hacer
  barrido de TODOS los sitios donde la decisión puede aparecer
  (CONTEXT.md, ADR, BACKLOG, ROADMAP, hoja-de-ruta), no solo el más
  obvio. Origen: consolidación post-sesión 27 actualizó D-23.2 en
  DECISIONES.md y "estado en una línea" del CONTEXT, pero omitió la
  sección §"Decisiones vigentes" del mismo CONTEXT — un dogfooding lo
  detectó como drift. Ver `docs/DECISIONES.md`.

## Caveats operacionales

Hallazgos de proceso puntuales, vinculantes para quien redacte briefs de
sesión o ejecute dogfoodings — complementan los "Errores de dominio" de
`CLAUDE.md` (esos son técnicos/de API; estos son de secuencia/protocolo).

### C7 — Refill obligatorio antes de baseline DRC

Ver D-26.1 completo. En resumen: `move_footprint` no dispara refill. Todo
dogfooding que use baseline dinámico + delta (D-24.2) debe invocar
`fill_zones()` explícito entre colocación masiva y lectura del baseline.
Sin ese paso, el baseline mide fill rancio, no la geometría real.

## Riesgos abiertos

Detalle priorizado y esfuerzo estimado: `docs/BACKLOG.md`. Los que más
condicionan decisiones de arquitectura o pueden bloquear un dogfooding futuro:

| # | Riesgo | Estado |
|---|---|---|
| R12 | Tools de escritura de esquemático son puramente aditivas (sin CRUD) | Abierto, no ejercitado en D3/D4/24 |
| R13 | `get_world_context(kind="sch")` falla con símbolos `#PWR*`/`#FLG*` | Ratificado en D4, workaround `export_netlist()` |
| R14 | `fill_zones`/`add_zone(fill=True)` no garantizaban el contrato disco==memoria | **CERRADO** — D-23.2 ratificado 25/25 en producción real tras Fase 3 (D5+D6+D7), ninguna corrida con divergencia |
| R16 | Loop de vías de `enforce_hole_clearance` posiblemente código muerto | Deuda técnica (D-23.3), no tocar en Fase 3 salvo evidencia nueva |
| R9 | `Freerouting gui.enabled=true` cuelga la JVM | Mitigado en código, issue upstream pendiente |
| R17 | `route_board(refill=true)` podía saltar su refill de seguridad en silencio si `reload_board_from_disk` fallaba (F-V2-REFILL-SILENCIOSO) | **CERRADO** — sesión 32b, `POST_ROUTE_REFILL_SKIPPED` (D-32b.1); `fill_zones`/`add_zone` no afectadas (D-32b.2) |

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
