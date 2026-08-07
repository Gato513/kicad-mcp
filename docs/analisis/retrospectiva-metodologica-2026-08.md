# Retrospectiva metodológica — kicad-mcp

**Fecha:** 2026-08-01 · **Alcance:** 163 commits, sesiones 1–34b (2026-07-08 →
2026-07-31), ~45 ramas según el inventario usado en la retrospectiva original
(el número histórico exacto no puede reconstruirse con fiabilidad a partir de
las refs actuales, ver §3), ~130 documentos `.md`.
**Objeto de análisis:** no el software — eso ya lo cubre
`docs/analisis/auditoria-tecnica-integral-2026-08.md` (media 7,0/10, madurez
Beta). Este documento audita **el método**: cómo el par arquitecto-humano +
agente-ejecutor investigó, decidió, validó y se corrigió durante 24 días de
desarrollo real. Es el insumo directo de
`docs/analisis/manual-desarrollo-ia-software.md`, que destila esta evidencia en
una metodología portable.

**Método de esta retrospectiva:** lectura directa de `git log` completo, los 14
ADR, `docs/DECISIONES.md` (44 decisiones con fecha de origen), los 40 reportes
de sesión, los 7 logs de dogfooding, las 3 validaciones externas y el backlog.
Cada juicio cita sesión, commit o documento — nada se afirma sin ancla
verificable.

---

## 1. Resumen ejecutivo

kicad-mcp pasó de un esqueleto de servidor MCP solo-lectura (sesión 1,
2026-07-08) a un servidor Beta de 32 tools con loop de escritura de PCB cerrado
— colocación, zonas, autoruteo, DRC, export de fabricación — validado contra
KiCad 10.0.4 real sobre tres placas open-hardware ajenas al proyecto, en 24 días
calendario y 163 commits. La velocidad de producción de código no es lo
distintivo: lo distintivo es que el proyecto **midió su propia confianza en
cada paso** en vez de asumirla, con un aparato de evidencia (14 ADR, 44
decisiones rastreadas, 7 investigaciones de causa raíz, 7 dogfoodings
numerados). No hay dato comparativo disponible sobre otros proyectos para
calibrar ese volumen en términos relativos, pero es alto en términos
absolutos para un ciclo de 24 días.

**Los hitos que definieron la trayectoria**, en orden:

1. **El primer dogfooding (Etapa 1, 2026-07-11) obtuvo 5/10** y expuso que la
   lectura funcionaba pero la escritura no cerraba el loop (sin `save_board`,
   sin borrado, sin geometría de pad). Ese log de fricciones — no el diseño
   original — reescribió la hoja de ruta.
2. **El spike de autorouting (sesión 13, D-R11)** midió con números que el
   ruteo manual por LLM no era viable (~300 tok/track, 13 shorts en el
   subconjunto fácil) y decidió integrar Freerouting con evidencia, no
   intuición.
3. **La bandera roja del dogfooding D4 (sesión 22, nota 4,5/10)** reveló el bug
   más caro del proyecto: `route_board` medía DRC antes de persistir, así que
   el contrato "lo que reporto es lo que hay en disco" era falso. El fix
   (ADR-0012/D-23.2, sesión 24) se convirtió en el contrato arquitectónico más
   importante del proyecto, extendido tres veces más (sesiones 27, 32b, 32d).
4. **Tres dogfoodings verdes consecutivos (D5-D7, sesiones 25-29, notas 9,5 /
   9,7 / 9,8)** cerraron la Fase 3 declarando "criterio de convergencia
   cumplido" — sobre una única placa, variable controlada. Es la decisión más
   discutible del proyecto (§5, §7): la primera placa ajena (sesión 31) generó
   un P0 nuevo casi de inmediato.
5. **La preparación de release (sesiones 34a-34b)** cerró con una auditoría
   sistemática de 19 tools de escritura contra 4 ejes fijos y con LICENSE +
   README + CONTRIBUTING honestos — pero sin CI, sin cobertura instrumentada, y
   con dos P0 conocidos sin cerrar.

**Los mayores cambios de dirección:**

- Ruteo manual por LLM → autorouter delegado (D-R11, sesión 13), decidido con
  medición, no con intuición.
- Revert humano post-route → recarga programática automática (D-V3.1, sesión
  18): eliminó el último punto de contacto humano obligatorio del loop.
- La interpretación de "P0 nuevo" se invirtió deliberadamente entre fases: en
  Fase 3 (variable controlada) se sospechaba regresión por defecto; en Fase 4
  (placas ajenas) se sospechaba gap legítimo por defecto (`hoja-de-ruta-v5.md`
  §"Interpretación de resultados"). Es un cambio epistemológico consciente, no
  un parche.
- Stack Rust+Python planificado en `docs/arquitectura.md` v0.2 → todo-Python
  diferido con condiciones explícitas de reapertura (ADR-0009) — la decisión
  correcta, tomada temprano, nunca revisitada sin evidencia nueva.

**Qué caracteriza la forma de trabajar:** un modelo arquitecto-humano +
agente-ejecutor donde la sesión es la unidad atómica de trabajo, protegida por
fronteras que el agente no puede negociar desde un prompt (F1-F5, ADR-0000), y
donde la métrica de verdad no es "el código compila" sino "un dogfooding
numerado contra KiCad real lo confirma". Es un método con un rigor de
validación consistente y trazable a lo largo de las 34 sesiones — con la
ironía documentada en §5 y §9 de que ese mismo rigor metodológico nunca se
tradujo en gates ejecutables.

---

## 2. Línea de tiempo del proyecto

### Etapa 1 — Construcción en ráfaga (sesiones 1–9, 2026-07-08 → 2026-07-11)

67 commits en 4 días (12+23+21+11), el tramo de mayor densidad de todo el
proyecto. Arranca con 7 ADR fundacionales escritos en la sesión 1 antes de una
sola línea de tool (`d5b6af7`), esqueleto FastMCP + tool `health`, encoder TOON
contra golden byte-exacto. Cada sesión cierra con un reporte y —desde la
sesión 2— con una propuesta concreta para la siguiente. El MVP solo-lectura
queda funcional a la sesión 4 (`get_world_context` + ERC/DRC + exports).

**Por qué esta cadencia:** el diseño previo (`docs/arquitectura.md`, fechado
julio 2026, anterior a la sesión 1) ya había resuelto las preguntas
arquitectónicas grandes — stack, fronteras, taxonomía de errores — así que las
primeras sesiones ejecutaron un plan ya validado en papel, no exploraron.

### Etapa 2 — Primer contacto con la realidad y pivote (sesiones 9–13,
2026-07-11 → 2026-07-13)

**El dogfooding Etapa 1 (2026-07-11, nota 5/10) es el punto de inflexión real
del proyecto.** Hasta ese momento el plan era "hoja de ruta v2": más tools de
lectura, más cobertura de esquemático. El log de fricciones
(`docs/historico/dogfooding/dogfood-fricciones.md`) mostró algo distinto: las
tools de lectura eran excelentes (`get_context_delta` — "la joya" — TOON
compacto, cero crashes en 34 llamadas) pero **el loop de escritura no cerraba**
— split-brain vivo/disco sin `save_board` (F-05, bloqueante), sin
`delete_track`/`delete_via` (F-08, bloqueante), sin geometría de pad expuesta
(F-04/F-06). La hoja de ruta v2 se descartó el mismo día por la v2.1, que
reordenó todo el trabajo alrededor de cerrar esos tres gaps antes de cualquier
otra cosa (`HOJA-DE-RUTA-V2.md` vs `PROMPT-DOGFOODING-ETAPA-1.md`).

Sesión 13 fue un **spike explícito** (D-R11): ¿integrar un autorouter o subir
la inteligencia de `add_track`? Veredicto con números, no con preferencia: el
ruteo manual por LLM medía ~300 tok/track de razonamiento geométrico y una
tasa de defecto alta (13 shorts en el subconjunto fácil de la Etapa 1) —
Freerouting headless entra al plan.

### Etapa 3 — Cierre del loop + integración de autorouting (sesiones 14–18,
2026-07-12 → 2026-07-20)

`route_board` nace (T1-T4, sesión 14), con `live_stale` como flag explícito.
Sesión 18 elimina el último punto de contacto humano del loop: `Board.revert()`
permite recargar el PCB Editor vivo programáticamente tras un save externo
(D-V3.1), reemplazando el "pedile al humano que aprete Ctrl+S" documentado
como fricción bloqueante desde la Etapa 1.

**Nota de cadencia:** entre el último commit de sesión 13 (`287594b`,
2026-07-13) y el commit que cierra sesión 16 (`b26801b`, 2026-07-18) hay una
ventana de 5 días con solo 4 commits sueltos, tres de ellos del 2026-07-16
(`c393d89`, `40b4af5`, `dad8e44` — limpieza de entorno y logs de la corrida 2
de dogfooding Etapa 2) — la única pausa larga documentada en la historia del
proyecto. No hay reporte que explique el motivo; es una laguna en la propia
trazabilidad que el proyecto se exige a sí mismo (ver §5, hallazgo menor).

### Etapa 4 — Crisis, hardening y el contrato más importante del proyecto
(sesiones 19–24, 2026-07-20 → 2026-07-23)

Densidad de sub-sesiones más alta de todo el proyecto: **19 → 19b → 19c → 19d
→ 19e**, cinco iteraciones sobre la misma unidad de trabajo nominal en cuatro
días. Cada una resolvió un bloqueante real (símbolos de esquemático rotos,
socket IPC que no sobrevivía a un reinicio de KiCad, caveats de `add_via`) pero
la fragmentación en sí es evidencia de mal dimensionamiento del alcance
original de la sesión 19 (§5, §7).

**El evento central de esta etapa es el dogfooding D4 (sesión 22, nota
4,5/10)** — la única "bandera roja" real de todo el proyecto
(`docs/historico/dogfooding/dogfood4-fricciones.md`). `route_board` reportó 51
errores DRC post-route: 46 de ellos concentrados en 30 `clearance` + 16
`hole_clearance`, ambos a `actual=0.0000mm` contra el plano GND (los 5
restantes — 2 `copper_edge_clearance`, 2 `courtyards_overlap`, 1
`solder_mask_bridge` — no comparten ese patrón). El protocolo de la sesión —definido
*antes* de que ocurriera el hallazgo— exigía detener sin cirugía y reportar,
no arreglar a ciegas. Se respetó. Sesión 23 investigó causa raíz pura (sin
fix): el problema no era falta de protección sino **orden de medición y falta
de persistencia** — `route_board` medía el DRC *antes* de refillear+persistir.
Sesión 24 aplicó el fix ("Opción X": reordenar medición + persistir +
propagar fallo visible) y lo validó 2/2 en vivo contra KiCad real. Nace
ADR-0012 (D-23.2): el contrato "disco == memoria == `err_post` reportado", que
se extendería tres veces más en sesiones posteriores (27, 32b, 32d) — el
contrato arquitectónico más duradero y más citado del proyecto.

### Etapa 5 — Consolidación estadística: Fase 3 (sesiones 25–29, 2026-07-23 →
2026-07-25)

Ciclo deliberado: `[Dogfooding] → [fix si corresponde] → [nuevo dogfooding] →
[repetir hasta 2-3 verdes consecutivos]`. D5=9,5 (sesión 25), investigación de
solder mask que **cierra sin fix** por elección metodológica correcta (sesión
26, ver §6), D6=9,7 (sesión 28), D7=9,8 (sesión 29). El 25 de julio se declara
"Fase 3 CERRADA con criterio de convergencia cumplido": 3 verdes consecutivos,
D-23.2 en 25/25 corridas de producción real, sin P0 nuevos.

**El problema estructural de esta etapa** (desarrollado en §5 y §7): las tres
"verdes consecutivas" ocurrieron sobre la **misma placa** (el despertador
ATtiny85), con capas fijas, footprints fijos, topología fija. "Convergencia"
significó, en los hechos, "el mismo experimento no cambió de resultado al
repetirlo" — no "el sistema generaliza". La sesión 31 (la primera placa
externa) lo demostró en la práctica: generó un P0 nuevo (`F-V1-02`, refs de
footprint duplicados) casi de inmediato.

### Etapa 6 — Fase 4: validación externa + preparación de release (sesiones
30–34b, 2026-07-25 → 2026-07-31)

Secuencia estricta y explícita (`hoja-de-ruta-v5.md`): investigación P1 solder
mask (sesión 30, cierre real esta vez — ver §6) → Validation Suite Nivel A/B/C
(sesiones 31-33, sobre placas OSHWA reales) → auditoría de contratos de
escritura (sesión 34a) → LICENSE/README/CONTRIBUTING (sesión 34b). La Suite
introdujo por primera vez un criterio operacional cuantitativo de "válido"
(D-30.3: DRC 0 + tracks ±30% + vías ±20% + cobre ±25% contra ground truth
fabricado). Nivel C (HackRF One, 437 footprints/4 capas) **no completó** —
Freerouting entró en crash-loop y `add_zone(fill=true)` crasheó KiCad
reproduciblemente 3/3 veces. El proyecto lo registró como "Escenario 6/7:
refutación por escalabilidad" y lo publicó, sin ocultarlo (§4). Sesión 34a
auditó sistemáticamente 19 tools de escritura contra 4 ejes fijos y encontró
3 asimetrías reales que ADR-0012 no cubría.

**Momentos de bloqueo:** D4 (sesión 22, bandera roja completa). **Momentos de
aceleración:** sesiones 1-9 (plan ya validado en papel), D5-D7 (ciclo maduro,
sesión más corta de la serie en 28 min). **Cambios de estrategia:** los cuatro
listados en §1, más el cambio de criterio de éxito de Fase 3 ("convergencia
técnica") a Fase 4 ("aumento de confianza, no volumen de código" — D-30.2).

---

## 3. Análisis de nuestra forma de trabajo

**Investigación.** El patrón dominante desde la sesión 23 en adelante es
*investigación separada del fix*: una sesión dedicada a aislar causa raíz,
otra —a veces días después— a aplicar el fix con la hipótesis ya especificada.
Este desacople es la práctica individual de mayor valor del proyecto (ver §4,
§8): impidió el patrón "arreglar lo que se ve, no lo que causa" dentro de este
ciclo de trabajo. Formalizado tardíamente como D-32c.1 ("el objetivo de una
investigación es reducir incertidumbre, no producir un fix") — practicado ya
desde la sesión 23, nombrado recién en la 32c.

**Experimentación.** Dos spikes explícitos con veredicto numérico (sesión 13,
autorouting; y de facto, cada dogfooding es un experimento con nota). La
Validation Suite (sesiones 31-33) institucionalizó la experimentación contra
ground truth real con umbrales cuantitativos predefinidos — la práctica más
cercana a ingeniería experimental disciplinada que tiene el proyecto.

**Planificación.** Cada sesión arranca de un prompt escrito por el arquitecto
(`docs/historico/prompts/`) y cierra con un reporte que incluye una propuesta
concreta para la siguiente. Es planificación incremental, sesión a sesión, sin
un plan maestro que sobreviva más de 3-5 sesiones sin reescritura (5 hojas de
ruta completas: v2, v2.1, v3, v4, v5). El patrón es sano cuando el mundo
cambia rápido (etapas 1-2) y se vuelve costoso cuando ya no debería cambiar
tan seguido (§9).

**Validación.** El dogfooding numerado es la validación central y la práctica
más fuerte del proyecto — un número comparable, con criterio de corte
explícito ("rojo" = V3 activada o P0 nuevo o nota <8), que no se puede
argumentar. Pero la validación tuvo un techo estructural durante 6 de las 7
rondas: variable controlada, una sola placa (§5, §7).

**Toma de decisiones.** Ver §7 en detalle. El patrón dominante: decisiones
técnicas locales excelentes (con datos, con condición de reapertura escrita),
decisiones de alcance/proceso (declarar convergencia, declarar gates bajo
frontera inviolable sin implementarlos) más débiles.

**Documentación.** Sobreabundante en volumen (35 586 líneas de `.md` contra
11 988 de `src/` al cierre de sesión 34b, ratio ~3:1) y desigual en calidad: excelente como *registro
de decisiones con evidencia* (ADRs, investigaciones), débil como *sistema sin
duplicación* (la misma verdad reescrita en `CONTEXT.md`, `DECISIONES.md`,
`BACKLOG.md`, `ROADMAP.md` y la hoja de ruta vigente — D-28.2 es un parche
sobre ese síntoma, no una cura).

**Priorización.** P0/P1/P2/P3 explícito y consistente desde sesión ~20 en
adelante, con criterio de severidad documentado (`docs/BACKLOG.md`). Buena
disciplina de "un bug nuevo se registra siempre" — pero el CI, que llevaba 163
commits sin existir, nunca entró como P0 hasta que una auditoría externa lo
señaló (§5, §9).

**Organización.** Rama por sesión (~45 ramas según el inventario utilizado en
la retrospectiva original; el número histórico exacto no puede reconstruirse
con fiabilidad a partir de las refs actuales porque ramas posteriores
pudieron eliminarse, moverse o crearse apuntando a commits antiguos), commit
convencional por tarea, merge explícito. Consistente y trazable de punta a
punta — la mejor característica organizativa del proyecto.

**Aprendizaje.** El proyecto aprende de sí mismo de forma explícita y
verificable: cada decisión informal lleva "Contexto → Decisión → Fuente",
cada ADR se referencia desde el código que protege. El aprendizaje metodológico
(D-30.1, D-33.1, D-34a.1) llegó tarde en el ciclo (sesiones 30, 33, 34a): la
disciplina de refutación no quedó formalizada como contrato explícito hasta
la sesión 30; antes de ello existen señales de uso parcial o inconsistente,
pero no evidencia suficiente para cuantificar cuántas sesiones la omitieron.

---

## 4. Qué hicimos bien

1. **Tipos que hacen imposible el bug de dominio #1.** `Nm`/`Mm` como tipos
   distintos con `mypy --strict` limpio convierte el error histórico #1 del
   dominio (off-by-10⁶ nanómetros↔milímetros) en un error de compilación, no
   en un bug de producción. Funcionó porque el error se identificó *antes* de
   escribir el bridge (`CLAUDE.md`), no se descubrió por accidente.

2. **Un `assert` como frontera estructural, no un flag.** `_IDEMPOTENT_OPS`
   (`bridge/ipc.py`) hace estructuralmente imposible aplicar retry a una
   mutación — hay que borrar código explícito para reabrir esa puerta, no
   cambiar un booleano. Es la clase de decisión que un plazo apretado
   normalmente sacrifica por un flag más rápido de escribir.

3. **Fronteras inviolables que sobrevivieron 34 sesiones de presión.** F1-F5
   (`ADR-0000`) nunca se negociaron desde un prompt de sesión, ni siquiera
   cuando negociarlas habría sido más rápido (ej.: los 3 encoders ad-hoc de
   `get_tracks`/`get_zones`/`get_component_detail` se inventaron como formatos
   nuevos específicamente para no tocar el spec TOON protegido por F1 —
   evidencia de que la frontera se respetó incluso bajo presión de conveniencia,
   con el costo colateral que se documenta en §5).

4. **Dogfooding numerado como métrica de verdad, no reporte de estado.** Una
   nota comparable (5 → 7,5 → 8,5 → 4,5 → 9,5 → 9,7 → 9,8) con criterio de
   corte explícito ("rojo" = detener, no negociar) obligó a admitir el
   retroceso de la sesión 22 en vez de reformularlo como éxito parcial.

5. **Investigación separada del fix, con causa raíz confirmada
   experimentalmente, no por inspección.** Sesión 32c refutó tres hipótesis
   alternativas (`island_removal_mode`, keepouts de
   `enforce_hole_clearance`, fill despojado) con experimentos de borrado
   dirigido sobre el motor real de KiCad, no con lectura de código. Sesión 23
   hizo lo mismo con F-D4-02. Es el patrón de investigación de mayor calidad
   del proyecto.

6. **El principio de refutación, una vez adoptado, encontró un error el mismo
   día.** D-33.1 ("¿qué resultado demostraría que esto es falso?") se aplicó
   contra la propia hipótesis inicial de la sesión 33 sobre el crash de
   `add_zone` — y esa hipótesis (overlap geométrico VCC/VAA) resultó falsa al
   intentar refutarla explícitamente, evitando que quedara documentada como
   causa raíz incorrecta.

7. **La Validation Suite contra ground truth fabricado, con umbrales
   predefinidos.** Comparar el output automatizado contra placas que sus
   autores originales realmente fabricaron, con criterios numéricos fijados
   *antes* de correr la validación (D-30.3), es metodología de ingeniería
   real. Publicar el fracaso de Nivel C (0/4 criterios evaluables, refutación
   por escalabilidad) con el mismo detalle que los éxitos de A y B es lo que
   distingue esta práctica de una demo.

8. **Honestidad pública verificada, no declarada.** El README público lidera
   con "Known limitations" en vez de esconderlas, y cada afirmación pasó un
   chequeo dedicado (`docs/analisis/readme-honestidad-check.md`, 16/16
   sostenidas). Es una práctica de comunicación técnica que este proyecto no
   diluyó ni siquiera en su primera exposición pública consciente (sesión
   34b).

---

## 5. Qué hicimos mal

Diez fallos, costeados con evidencia — no genéricos.

1. **Cero CI en 163 commits.** La Definition of Done (`CLAUDE.md`, 6 puntos)
   fue prosa desde la sesión 1 hasta el cierre de este análisis. Nada impide
   mecánicamente mergear con tests rojos, `ruff` sucio o `mypy` roto — toda la
   garantía dependió de que un humano corriera 3 comandos antes de cada
   commit. **Costo real:** ninguno se materializó porque la disciplina humana
   se sostuvo — pero esa disciplina no escala a un solo colaborador nuevo, y
   es exactamente el gap que la propia auditoría técnica marca como acción
   #1 de mayor impacto/esfuerzo del repositorio entero.

2. **Declarar "criterio de convergencia cumplido" sobre variable controlada
   única.** Fase 3 cerró (sesión 29, 2026-07-25) con "3 verdes consecutivos" —
   los tres sobre la misma placa (despertador ATtiny85), mismos footprints,
   misma topología. **Costo medido:** la primera placa ajena (sesión 31, seis
   días después) generó un P0 (`F-V1-02`) casi inmediatamente. El criterio de
   convergencia medía "el experimento es repetible", no "el sistema
   generaliza" — y el proyecto lo llamó convergencia de todos modos.

3. **El techo de escala del producto se descubrió en la sesión 33 de 34.**
   Freerouting entra en crash-loop y `add_zone(fill=true)` crashea KiCad
   reproduciblemente sobre boards de 437 footprints/4 capas — el límite real
   del producto se midió a un paso del release, no en el spike de autorouting
   (sesión 13) donde había una oportunidad natural de estresar el límite
   superior antes de comprometer 20 sesiones de trabajo sobre un diseño que
   asumía "el autorouter escala".

4. **Ratio docs:código de ~3:1 con reescritura recurrente de la misma
   verdad.** 35 586 líneas de `.md` contra 11 988 de `src/` (cierre de sesión
   34b). `CONTEXT.md` se reescribió como consolidación completa al menos 7
   veces (dos pasadas post-sesión 24, post-27, post-28, post-29, dos pasadas
   post-sesión 34); D-23.2 sola aparece citada y re-explicada en `CONTEXT.md`,
   `DECISIONES.md`, `ADR-0012`, `BACKLOG.md`, `ROADMAP.md` y la hoja de ruta
   vigente. D-28.2 ("barrido completo al generar diffs de decisiones") es un
   parche escrito *sobre el síntoma* (drift entre documentos) en vez de
   atacar la causa (demasiadas fuentes de la misma verdad).

5. **`register()` de `pcb.py`: 2 215 líneas, complejidad ciclomática 146,
   nunca refactorizado en 34 sesiones.** El costo compuesto: para la sesión 34,
   ninguna tool nueva puede testearse sin construir el servidor entero, y
   cualquier diff de una tool toca un archivo de 3 402 líneas. El proyecto
   documentó exhaustivamente *qué* estaba mal (auditoría técnica, sesión de
   este mismo día) pero ninguna de las 34 sesiones incluyó "reducir esta
   complejidad" como objetivo — el criterio de éxito de cada sesión (D-30.2:
   "confianza, no volumen de código") nunca incluyó un eje donde pagar deuda
   estructural pudiera ganar frente a agregar una tool nueva.

6. **Gates declarados bajo frontera "inviolable" sin implementar.** ADR-0003
   define G2 (confirmación destructiva) y G4 (presupuesto de sesión) bajo F2
   ("los gates existen para ser inviolables desde prompts"). Ninguno existe en
   código; `GATE_DENIED`/`BUDGET_EXCEEDED` son códigos de error sin emisor.
   Proteger de modificación un gate que no existe es una garantía vacía que
   además engaña a la lectura del catálogo de errores.

7. **Tres formatos de serialización ad-hoc para esquivar F1 en la letra, no
   en el espíritu.** `TRACKS|v1`, `ZONES|v1`, `DETAIL|...` se inventaron
   explícitamente para no tocar el spec TOON protegido (`pcb.py:817`: "NO es
   TOON... F1 intacto"). El resultado: tres contratos que un LLM parsea, sin
   spec, sin golden test, y sin la sanitización que sí tiene el pipeline
   TOON — la frontera se cumplió literalmente y se erosionó en el propósito
   que la motivaba.

8. **Fragmentación repetida de la unidad de trabajo nominal.** 19→19b→19c→
   19d→19e (5 iteraciones), 31→31b→31c (3), 32→32b→32c→32d (4). Cada
   sub-sesión resolvió algo real, pero el patrón repetido tres veces
   distintas es evidencia de que el alcance original de la sesión-madre se
   subestimó sistemáticamente, no de mala suerte puntual.

9. **La sesión 26 cerró un hallazgo sin refutar su propia hipótesis, y hubo
   que reabrirlo en la sesión 30.** El fix de solder mask de sesión 26 se
   diseñó, se verificó como insuficiente, y se revirtió — cerrando la sesión
   con "mecanismo no aislado". D-33.1 (refutación activa) no existía todavía;
   de haber existido, la pregunta "¿qué refutaría esta hipótesis?" aplicada
   en la sesión 26 —no en la 33— probablemente hubiera evitado el ciclo
   completo de re-investigación 4 sesiones más tarde.

10. **Fricción de entorno resuelta con disciplina humana repetida en vez de
    tooling.** Editar `bridge/`/`tools/` con el server MCP activo exige matar
    el proceso y pedirle al humano `/mcp reconnect` — ocurrió 3 veces en una
    sola sesión (19e). La fricción se documentó cada vez que ocurrió, nunca se
    convirtió en una tarea de tooling (hot-reload, o al menos un script de
    reinicio) pese a repetirse.

---

## 6. Cómo enfrentamos los problemas

**Patrón dominante, y en general correcto:** *bandera roja → detener sin
cirugía → sesión de investigación pura (sin fix) → sesión de fix con hipótesis
ya especificada y test de regresión*. Este ciclo se ejecutó de forma
consistente desde la sesión 22 (D4) en adelante: 22→23→24 (bloqueo → causa
raíz → fix validado en vivo), 32→32c→32d (hallazgo → mecanismo aislado → fix
con guardrails). El protocolo explícito de "no arreglar a ciegas, reportar" —
vigente ya en el prompt de la sesión 22, antes de que ocurriera el hallazgo —
es la razón por la cual el proyecto nunca acumuló un parche mal entendido
sobre un síntoma.

**Incertidumbre:** manejada con hipótesis explícitas antes de actuar desde la
sesión 30 en adelante (D-30.1: hipótesis / evidencia confirmatoria /
refutatoria / protección contra regresión), y con `AskUserQuestion` como
mecanismo de escalamiento cuando el ejecutor encontraba una premisa dudosa del
prompt — usado activamente en sesiones 27, 31b, 32d, 33, 34a, 34b para
refutar o corregir una premisa antes de comprometerse con una implementación
(ej.: sesión 31b descubrió que el marco cerrado del prompt chocaba con
ADR-0010 vigente, y lo escaló antes de tocar código; sesión 34b corrigió que
`kicad-skip` era LGPL, no MIT, antes de fijar la licencia).

**Cambios de objetivos:** el cambio de criterio de éxito entre Fase 3
("convergencia técnica") y Fase 4 ("aumento de confianza, no volumen de
código", D-30.2) se declaró explícitamente y con fecha, no se dedujo
retroactivamente — evita el patrón común de reescribir la historia para que
parezca que siempre se apuntó ahí.

**Dónde el manejo de problemas falló:** la sesión 26 (§5, hallazgo #9) es el
único caso donde el protocolo "cerrar sin fix si no hay evidencia sólida"
produjo un cierre prematuro en vez de una investigación completa —
precisamente porque la disciplina de refutación activa (D-33.1) todavía no
existía. La lección correcta ya se aplicó (D-32c.1 y D-33.1 llegaron 4-7
sesiones después) pero llegó tarde respecto al costo que ya había generado.

**¿Fue adecuada la forma de resolver?** Sí, con una salvedad estructural: el
proyecto resolvía bien los problemas *que ya habían aparecido* (protocolo de
bandera roja, investigación separada del fix) pero era más débil detectando
problemas *antes de que aparecieran* (§5 ítems 2, 3, 6 — todos son casos donde
un chequeo de diseño previo, no una sesión de investigación posterior, habría
sido más barato). La alternativa mejor no es "investigar más rápido" sino
mover el criterio de refutación (D-30.1/D-33.1) al *diseño* de cada fase, no
solo a la ejecución de cada sesión — ver §11-§12.

---

## 7. Análisis de la toma de decisiones

**¿Decidimos demasiado rápido?** En el plano técnico local, no — las
decisiones locales (D-R8 borrado sin gate, D-19c.1 orden de keepouts,
D-24.1/D-24.2 patrones de fixture y baseline) llegaron con evidencia y quedaron
documentadas con su razonamiento. En el plano de alcance/proceso, sí en un
caso concreto y costoso: declarar G2/G4 "inviolables" (F2) en la misma sesión
que se diseñaron, sin plan de implementación ni fecha — una decisión de
proceso tomada con la misma velocidad que una decisión de código, cuando
ameritaba un ciclo de diseño propio.

**¿Decidimos demasiado lento?** Sí, en una decisión concreta: nunca se decidió
formalmente "necesitamos CI" pese a que la brecha era visible desde la primera
sesión que definió una Definition of Done no automatizable. No hay una
decisión explícita de posponerla —simplemente nunca entró en la agenda de una
sesión hasta que una auditoría externa la señaló.

**¿Investigamos demasiado antes de actuar?** No en general — el patrón
dominante (§6) es investigar lo necesario y actuar con hipótesis. La excepción
es sesión 34a: la reproducción empírica planeada de `F-V3-ZONE-FILL-CRASH` no
se ejecutó porque el único KiCad vivo disponible tenía el proyecto que ya
crasheaba — una limitación de infraestructura de pruebas (sin capacidad de
abrir dos proyectos KiCad en paralelo), no de exceso de cautela.

**¿Experimentamos lo suficiente?** El spike de autorouting (sesión 13) y la
Validation Suite (31-33) son los dos mejores ejemplos de experimentación con
criterio numérico predefinido del proyecto. Pero el "experimento" de Fase 3
(dogfooding D5-D7) repitió la misma variable tres veces en vez de variar un
solo factor por vez — más repetición que experimentación real.

**Decisiones mejor fundamentadas:** ADR-0012/D-23.2 (evidencia empírica, dos
rondas de regresión en vivo, extendido tres veces con la misma disciplina);
ADR-0009 (Rust diferido, con condición de reapertura explícita y verificable:
"evidencia de cuello de botella real"); D-R11 (autorouter, con números).

**Decisiones más impulsivas:** declarar Fase 3 convergente sobre una placa
(§5-2); fijar el umbral de vías ±20% de D-30.3 antes de tener ningún dato —
el propio proyecto lo detectó (sesión 31c: "el umbral no resultó discriminante
para bases pequeñas") y lo dejó como candidato a revisión, sin revisarlo
todavía a la fecha de este análisis.

**Decisión de mayor valor generado:** ADR-0012/D-23.2, sin comparación. Cerró
el único P0 que detuvo por completo un dogfooding (D4, nota 4,5/10), se
extendió sin reabrir el diseño original tres veces más (sesiones 27, 32b, 32d)
con la misma disciplina de "no reabrir el contrato, extender su alcance
declarado" — el ejemplo más limpio de una decisión arquitectónica que
absorbió evidencia nueva sin degradarse.

**Patrón general:** el proyecto es fuerte decidiendo *qué construir* (con
evidencia, con reversión documentada cuando corresponde) y comparativamente
débil decidiendo *qué reparar en el propio proceso* — CI, refactor de
`register()`, gates a medio implementar. Las decisiones sobre el producto
pasaron por un ciclo de validación; las decisiones sobre la infraestructura del
propio desarrollo, en su mayoría, no pasaron por ningún ciclo — simplemente no
se tomaron.

---

## 8. Cómo investigamos

**Metodología dominante (desde sesión 23):** hipótesis explícita → experimento
causal sobre el motor real (nunca solo inspección de código) → refutación
activa de alternativas → documentación completa incluso si no hay fix.
Sesión 32c es el ejemplo más completo: refutó 3 hipótesis alternativas con
experimentos de borrado dirigido y re-fillado real sobre copias desechables
(nunca sobre fixtures del repo), y se autocorrigió dos veces a mitad de sesión
cuando su propia instrumentación resultó poco fiable (`HitTestFilledArea()` no
confiable para conectividad pad-zona) — documentando el error metodológico en
vez de ocultarlo.

**Comparación de alternativas:** consistente cuando hay una decisión de diseño
en juego (sesión 32d evaluó explícitamente 3 alternativas de fix con sus
trade-offs antes de elegir stitching automático con guardrails). Menos
consistente en decisiones de umbral (D-30.3 se fijó sin comparar alternativas
de valor, solo con juicio razonable a priori).

**Validación de hipótesis:** el punto más fuerte del proyecto, una vez
adoptado D-33.1 (sesión 33) — "¿qué resultado la refutaría?" antes de aceptar
cualquier explicación, aplicado con éxito medible el mismo día de su adopción
(la hipótesis de overlap geométrico se refutó en el acto, antes de quedar
documentada como causa raíz incorrecta).

**Documentación de resultados:** exhaustiva y con codificación consistente
(P4.0-style: hipótesis, mecanismo, evidencia, refutaciones intentadas) en las
7 investigaciones de `docs/investigacion/`. Cada investigación cerrada,
incluso sin fix, deja un artefacto reusable.

**¿Fue eficiente?** Sí en el mecanismo (experimentos causales baratos sobre
copias desechables, nunca sobre datos que importan), no en el timing: la
disciplina de refutación que definió la calidad de las últimas 5 sesiones
llegó en la sesión 33 de 34 — tarde respecto al valor que habría generado si
hubiera sido principio fundacional desde la sesión 1. La sesión 26 (§5, §6) es
el costo concreto y medible de esa demora.

**Qué mejorar:** (a) mover D-30.1/D-33.1 al principio del proyecto, no
descubrirlos por acumulación de evidencia sobre sus propios costos; (b)
resolver la limitación de infraestructura que impidió la repro de sesión 34a
(un único KiCad vivo, sin forma de abrir un segundo proyecto sin operar la
GUI) — es un gap de tooling de pruebas, no de disciplina investigativa; (c)
revisar los umbrales fijados sin datos previos (D-30.3) con la misma disciplina
de refutación que se aplica a hipótesis técnicas.

---

## 9. Análisis de productividad

**Actividades de mayor impacto medido:**
- Dogfooding numerado — cada ronda generó al menos un hallazgo accionable con
  costo/severidad explícitos, y forzó admitir retrocesos (D4).
- Spikes con veredicto numérico (sesión 13) — evitaron construir una capacidad
  entera (ruteo manual asistido) sobre una intuición no verificada.
- Investigaciones de causa raíz separadas del fix — evitaron parches sobre
  síntomas, medible en que ningún fix de este tipo tuvo que revertirse.

**Actividades de poco valor o valor decreciente:**
- Reescritura completa de `CONTEXT.md` como consolidación (≥7 veces) — cada
  una reprodujo información ya presente en ADRs/DECISIONES.md con distinto
  nivel de resumen. El costo no es solo el tiempo de escritura: es la
  superficie de drift que D-28.2 tuvo que nacer para mitigar.
- D-28.2 en sí misma ("barrido completo de sitios al generar diffs") es una
  tarea recurrente de mantenimiento manual que existe porque hay demasiadas
  fuentes de la misma verdad — trabajo generado por la propia estructura
  documental, no por el dominio del problema.

**Tareas repetitivas identificadas:**
- El preámbulo de mutación (guard + check de disco + base_snap + G1 + audit +
  timer + log) se repite ~19 veces a mano en `tools/pcb.py`, documentado por
  la propia auditoría técnica como el mayor candidato a decorador
  (`@mutating_tool`) — nunca extraído en 34 sesiones pese a que el patrón era
  visible desde las primeras tools de mutación (sesión 9-11).
- Handoffs GUI manuales (`/mcp reconnect`, cerrar/abrir proyecto en KiCad,
  abrir específicamente el PCB Editor) — documentados como fricción repetida
  desde la sesión 19e, sin automatizarse.

**Cuellos de botella:**
- **KiCad vivo único, sin forma de abrir un segundo proyecto sin operar la
  GUI** — bloqueó directamente la reproducción planeada de
  `F-V3-ZONE-FILL-CRASH` en sesión 34a.
- **Timeout de idle de clientes MCP más corto que un autoruteo completo**
  (~1818s observados vs. `route_board` que puede tardar más) — mitigado con un
  proceso desacoplado, pero es un techo estructural del modelo de interacción
  síncrona.
- **Cola IPC de profundidad 1** (correcto por diseño — protege el hilo de UI
  de KiCad — pero fija el techo de paralelismo de cualquier operación).
- **Ausencia de CI** como cuello de botella de *confianza*, no de velocidad:
  cada merge dependió de que un humano corriera manualmente `pytest`+`ruff`+
  `mypy`, sin que nada lo verificara de forma independiente.

**Cómo eliminarlos:** CI ejecutable elimina el cuello de confianza sin costo
de rediseño (la propia auditoría técnica lo marca como la acción de mejor
relación impacto/esfuerzo de todo el repositorio). El decorador transversal
elimina la repetición del preámbulo de mutación y baja el riesgo de que una
tool nueva olvide un guard. Un mecanismo de recarga en caliente del server MCP
(o al menos un script de reinicio) elimina la fricción de `/mcp reconnect`
recurrente. Consolidar la fuente única de "estado del ciclo" (un documento
vivo, el resto enlaza) elimina el trabajo de barrido manual que D-28.2 intenta
mitigar sin atacar la causa.

---

## 10. Si comenzáramos nuevamente desde cero

**Qué haríamos igual:**
- Fronteras inviolables (F1-F5) desde el primer commit, con mecanismo que
  impida negociarlas desde un prompt — funcionó exactamente como se diseñó.
- ADRs con "Contexto → Decisión → Consecuencias" para toda decisión que
  condiciona trabajo futuro, más un índice vivo (`DECISIONES.md`) que apunte
  a ellos sin duplicar su contenido — la parte de la práctica documental que
  sí generó valor limpio.
- Tipos distintos para unidades físicamente incompatibles donde el
  type-checker puede atrapar el error (`Nm`/`Mm`), aplicado a cualquier
  frontera de conversión de unidades o formatos.
- Dogfooding numerado contra el sistema real, con criterio de corte explícito
  fijado antes de correr la prueba.
- Investigación separada del fix como default para cualquier hallazgo cuya
  causa raíz no sea obvia en menos de 15 minutos.
- El spike con veredicto numérico antes de comprometerse con una capacidad
  cara (autorouting).

**Qué haríamos diferente:**
- **CI ejecutable desde el primer commit**, no como acción de cierre de fase.
  El costo de configurarlo es mínimo (`ruff`+`mypy`+`pytest -m "not
  integration"` en push/PR) y elimina por completo el riesgo #1 identificado
  por la auditoría técnica.
- **Una placa ajena al proyecto de referencia entra en el plan desde la
  segunda fase de validación, no en la sesión 31 de 34.** El criterio de
  convergencia de cualquier fase de consolidación exige, desde el diseño,
  variar al menos una dimensión real (placa, topología, escala) — no solo
  repetir el mismo experimento sobre la misma variable.
- **Medir el techo de escala del componente más caro (aquí, el autorouter)
  en el spike, no en la validación final.** Un spike de escala barato (probar
  el autorouter sobre un board sintético grande, sin integrarlo al pipeline
  todavía) habría informado el diseño de `route_board` antes de construir 20
  sesiones de features encima de un supuesto de escala no verificado.
- **Decorador transversal para cross-cutting concerns desde la primera tool
  de mutación**, no diferido indefinidamente. El patrón era visible con la
  segunda o tercera tool que repetía el mismo preámbulo.
- **Refactor incremental agendado por sesión**, no diferido a "cuando haya
  evidencia". Un criterio explícito ("cada 5 sesiones de features, 1 sesión
  de consolidación de deuda") habría evitado que `register()` llegara a 2 215
  líneas sin que ninguna sesión lo tratara como su objetivo principal.
- **Una única fuente de verdad para "estado del ciclo"**, con el resto de
  documentos enlazando en vez de resumiendo — el mismo principio que D-28.2
  intenta parchear, aplicado desde el diseño documental inicial en vez de
  como corrección posterior.
- **Formalizar D-30.1 (hipótesis/confirma/refuta/protege) y D-33.1
  (refutación activa) como principio 0 del proyecto**, no como aprendizaje de
  las sesiones 30 y 33.

**Qué evitaríamos completamente:**
- Declarar un contrato "inviolable" (frontera F2 sobre G2/G4) antes de que el
  contrato exista en código — la protección debe llegar junto con la
  implementación, no antes.
- Anunciar "criterio de convergencia cumplido" con una sola variable
  controlada. Un criterio de convergencia debería exigir, por definición,
  variación deliberada de al menos un factor no ejercitado antes.
- Crear un formato de serialización nuevo específicamente para esquivar una
  frontera protegida, aunque sea técnicamente conforme a la letra de la
  regla — si el espíritu de la frontera aplica, extenderla explícitamente
  (con aprobación) es más honesto que rodearla.

**Qué decidiríamos antes:** la escala objetivo del producto (footprints
máximos, capas máximas) como parámetro de diseño explícito desde la
arquitectura inicial, no como hallazgo de la sesión 33. Cambia el diseño del
pipeline de autorouting, la estrategia de zonas, y probablemente la decisión
de si Freerouting es la herramienta correcta para el rango superior del
producto.

**Qué tecnologías elegiríamos:** el mismo stack (Python + FastMCP + `mypy
--strict` + `ruff`), que demostró ser la decisión correcta y barata frente a
la alternativa Rust+Python originalmente considerada — pero con `pytest-cov`
y CI desde el `pyproject.toml` inicial, no como deuda diferida.

**Qué arquitectura usaríamos:** la misma separación de capas (`tools → bridge
→ externo`, sin ciclos de import — la auditoría técnica confirma que esto se
mantuvo limpio en 34 sesiones), pero con el decorador transversal y con
`enforce_hole_clearance`/la geometría de dominio viviendo en un módulo de
dominio separado desde el inicio, no dentro del bridge de transporte.

**Qué metodología seguiríamos:** la misma —sesión atómica, prompt escrito,
reporte de cierre, dogfooding numerado, ADR para toda decisión persistente—
con los principios de refutación (D-30.1/D-33.1) presentes desde la sesión 1
en vez de descubiertos por acumulación de costo.

**Qué validaríamos primero:** el supuesto S1 del propio diseño original
(`docs/arquitectura.md`: "el LLM lee TOON tan bien como JSON") — es la
hipótesis diferenciadora explícita del proyecto ("el diferencial de este
proyecto es la economía de tokens... no la existencia del puente en sí") y
nunca se sometió a un eval propio en 34 sesiones. Es el supuesto de mayor
apalancamiento sin verificar de todo el proyecto.

**Qué investigaríamos primero:** el techo de escala real del pipeline
completo (autorouter + fill de zonas) sobre un board sintético grande, antes
de comprometer el diseño de `route_board` a una arquitectura que asume que
Freerouting escala linealmente.

---

## 11. Propuesta de metodología de trabajo

Ver `docs/analisis/manual-desarrollo-ia-software.md` §"Fases del proyecto"
para la versión normativa completa, portable a cualquier proyecto. Resumen
aplicado a este tipo de sistema (agente operando una herramienta compleja de
terceros, con validación empírica cara):

| Fase | Objetivo | Entregable | Criterio de salida (falsable) |
|---|---|---|---|
| **0. Contratos** | Fijar fronteras, taxonomía de errores, supuestos falsables | ADRs fundacionales, lista de supuestos con eval agendado | Ningún supuesto de alto apalancamiento queda sin plan de verificación |
| **1. Núcleo mínimo** | Loop end-to-end más corto posible, aunque sea feo | MVP con CI desde el primer commit | El loop cierra de punta a punta sin intervención humana obligatoria |
| **2. Contacto con la realidad** | Exponer el núcleo al uso real cuanto antes | Primer dogfooding numerado, con nota y criterio de corte | Nota registrada + lista de gaps priorizada, sin importar el resultado |
| **3. Hardening dirigido por evidencia** | Cerrar los gaps que el contacto real reveló, en orden de severidad | Fixes con investigación separada + test de regresión | Cero P0 abiertos del ciclo de contacto anterior |
| **4. Validación con variación deliberada** | Probar contra al menos un factor no ejercitado antes (escala, topología, dominio) por ronda | Reporte de validación con criterio cuantitativo fijado antes de correr | El criterio de "convergencia" exige variación real, no repetición |
| **5. Consolidación y release** | Cerrar deuda que compite con features en el criterio de éxito | Deuda estructural con presupuesto explícito pagada, no solo documentada | El release no se declara con P0 conocidos sin cerrar o sin plan público |

La diferencia con lo que el proyecto hizo: la Fase 4 aquí exige variación
deliberada *desde la primera ronda*, no como una etapa separada que llega
después de declarar convergencia sobre variable controlada (§5-2). Y la Fase
5 incluye deuda estructural como entregable con el mismo peso que features,
no como ítem que compite y pierde sistemáticamente contra "confianza, no
volumen de código" mal aplicado.

---

## 12. Marco para la toma de decisiones

Ver manual §"Marco de decisión" para el proceso normativo de 7 pasos con
criterios de corte. Aplicado retrospectivamente a la decisión más costosa de
este proyecto (declarar Fase 3 convergente):

1. **Definir el problema:** ¿el sistema es suficientemente confiable para
   pasar a validación externa?
2. **Formular hipótesis:** "3 dogfoodings verdes consecutivos indican
   confiabilidad suficiente."
3. **Formular el criterio de refutación ANTES de correr el experimento**
   (paso que el proyecto omitió en este caso): "¿qué resultado demostraría
   que NO es confiable pese a 3 verdes?" — respuesta correcta, en
   retrospectiva: una placa con topología distinta rompiendo en el primer
   intento. Esa pregunta, hecha en la sesión 25, habría exigido variar la
   placa antes de declarar convergencia.
4. **Investigar alternativas:** ¿variar placa, capas, densidad, o repetir la
   misma variable con más muestras? El proyecto eligió la última sin
   comparar explícitamente.
5. **Prototipo mínimo / experimento barato:** una ronda de dogfooding sobre
   una placa ajena simple habría costado lo mismo que la tercera ronda sobre
   el despertador (D7) y habría dado información estrictamente mayor.
6. **Validar con métricas:** el proyecto sí definió métricas (nota, P0/P1) —
   el problema no fue la métrica sino el dominio sobre el que se midió.
7. **Comparar resultados y documentar el razonamiento:** hecho con calidad
   alta (`docs/CONTEXT.md`, `docs/ROADMAP.md`) — el defecto está en el paso 3,
   no en la ejecución posterior.

La lección estructural: el marco de decisión del proyecto era fuerte en los
pasos 4-7 (investigar, prototipar, medir, documentar) y débil en el paso 3
(formular explícitamente qué refutaría la hipótesis antes de aceptarla) hasta
que D-33.1 lo formalizó — en la sesión 33, después de que la decisión de
Fase 3 ya se había tomado y comunicado como cierre.

---

## 13. Principios de ingeniería

Desarrollados con evidencia y contramedida en
`docs/analisis/manual-desarrollo-ia-software.md` §"Principios". Lista aquí,
referencia cruzada a la evidencia de este documento:

1. Toda frontera que un ejecutor pudiera racionalizar cambiar necesita un
   mecanismo que no acepte argumentos, no una convención (§4-3, §5-6).
2. El rigor de la automatización debe igualar al rigor del método; donde no,
   el método caduca en el siguiente commit (§5-1, §9).
3. La premisa de una tarea es hipótesis, no hecho — verificarla contra el
   estado real es el primer bloque de trabajo, no un paso opcional (§6, §7).
4. Formular el criterio de refutación es la primera línea de una
   investigación, no la última (§6, §8, §12).
5. Una investigación que cierra sin fix pero reduce incertidumbre real es
   éxito pleno, no un resultado a medias (§4-5, §8).
6. Ningún criterio de convergencia se declara sobre una sola variable
   controlada — exige variación deliberada de al menos un factor no
   ejercitado antes (§5-2, §7, §11).
7. La restricción que más condiciona el alcance del sistema se mide en el
   spike más temprano posible, no en la validación final (§5-3, §10).
8. Una verdad, un dueño — el resto enlaza, nunca resume ni duplica (§5-4,
   §9).
9. Una decisión merece registro permanente solo si condiciona trabajo
   futuro de alguien más — no todo hallazgo necesita un ADR (§7).
10. El criterio de éxito de cualquier fase debe incluir un eje donde pagar
    deuda estructural pueda ganar frente a agregar una feature (§5-5, §9).
11. Fragmentación repetida de la unidad de trabajo nominal es una señal de
    mal dimensionamiento del alcance, no de mala suerte — se corrige
    ajustando el tamaño de la siguiente unidad, no tolerando la
    fragmentación (§5-8, §2).
12. Toda fricción de entorno que aparece dos veces se convierte en tarea de
    tooling, no en una nota que se repite en el próximo reporte (§5-10, §9).
13. La métrica de progreso central es el uso real de punta a punta contra el
    sistema real, con un número comparable y un criterio de corte fijado
    antes de correr la prueba (§4-4, §6).
14. Un supuesto de alto apalancamiento tabulado sin un plan de verificación
    agendado equivale, en la práctica, a no tenerlo documentado (§10).
15. Diferir una decisión es legítimo solo con una condición de reapertura
    escrita y verificable — "cuando haya evidencia" sin especificar cuál no
    es una condición (§7).

---

## 14. Riesgos metodológicos

Hábitos observados en este proyecto que, sin corrección deliberada, perjudican
cualquier proyecto futuro que herede la misma forma de trabajar. Cada uno con
mecanismo de prevención concreto.

| Riesgo | Cómo apareció aquí | Mecanismo de prevención |
|---|---|---|
| **Frontera que protege el vacío** | G2/G4 declarados "inviolables" bajo F2 sin implementación (§5-6) | Una frontera solo se declara junto con (o después de) su implementación; nunca antes |
| **Rigor de método sin rigor de automatización** | DoD de 6 puntos en prosa, cero gates ejecutables en 163 commits (§5-1) | Todo criterio de Definition of Done que pueda expresarse como comando se convierte en gate de CI en la misma sesión que se define |
| **Convergencia sobre variable controlada** | Fase 3 cerrada con "criterio cumplido" sobre 1 placa (§5-2, §7) | Ningún cierre de fase de validación se aprueba sin al menos un factor deliberadamente variado |
| **Techo de escala medido al final** | Freerouting/`add_zone` fallando en la sesión 33 de 34 (§5-3) | Todo componente de terceros con reputación de fragilidad a escala se estresa en un spike temprano, antes de comprometer diseño encima |
| **Verdad duplicada en N documentos** | D-23.2 en 6+ documentos distintos; `CONTEXT.md` reescrito 7+ veces (§5-4, §9) | Una fuente autoritativa por hecho; todo lo demás enlaza con un identificador estable, nunca resume el contenido completo |
| **Deuda estructural sin eje de éxito que la premie** | `register()` 2215 líneas / complejidad 146, nunca agendada en 34 sesiones (§5-5) | El criterio de éxito de cada fase incluye explícitamente "deuda pagada" como resultado válido, con presupuesto de sesiones dedicado |
| **Supuesto de alto apalancamiento sin eval** | S1 (TOON vs JSON), la hipótesis diferenciadora del proyecto, nunca validada (§10) | Todo supuesto identificado en el diseño inicial lleva una fecha de verificación agendada, no solo una fila en una tabla |
| **Contrato nuevo para esquivar una frontera protegida** | 3 encoders ad-hoc sin spec/golden/sanitización, creados para no tocar F1 (§5-7) | Si el espíritu de una frontera protegida aplica a un caso nuevo, se pide extensión explícita — nunca se crea un contrato paralelo fuera de su alcance para evitar el trámite |
| **Fragmentación tolerada de la unidad de trabajo** | 19→19e (5), 31→31c (3), 32→32d (4) (§5-8) | Dos fragmentaciones consecutivas de la misma unidad nominal disparan una revisión explícita del criterio de dimensionamiento, no solo la ejecución de la siguiente sub-sesión |
| **Refutación tardía como aprendizaje, no como principio fundacional** | D-30.1 llega en sesión 30, D-33.1 en sesión 33 (§8, §12); la fecha de formalización no permite cuantificar cuántas sesiones previas omitieron la disciplina | Los principios de refutación activa se adoptan por escrito en la sesión 0 del proyecto, no se esperan a descubrir por acumulación de costo |

---

## 15. Conclusión

**La mayor lección aprendida:** este proyecto demuestra, con evidencia
repetida, que **el rigor del método y el rigor de su automatización son ejes
independientes** — se puede tener un aparato de decisiones excepcional (14
ADRs, 44 decisiones rastreadas, investigaciones con refutación causal) y al
mismo tiempo cero gates ejecutables que impidan romper ese mismo aparato en el
siguiente commit. La disciplina intelectual no sustituye a la disciplina
mecánica; se necesitan las dos, y la segunda es más barata de construir de lo
que el proyecto la trató.

**Errores que no deberíamos volver a cometer:**
- Declarar convergencia o madurez sobre una sola variable controlada.
- Proteger con una frontera "inviolable" un contrato que todavía no existe en
  código.
- Dejar que la deuda estructural compita contra features en el criterio de
  éxito de una fase y pierda sistemáticamente.
- Descubrir el techo de escala de una dependencia crítica de terceros después
  de construir 20 sesiones de diseño que lo asumían resuelto.

**Qué deberíamos conservar:** las fronteras inviolables con mecanismo real; el
dogfooding numerado con criterio de corte explícito; la investigación separada
del fix; el hábito —una vez adoptado— de exigir refutación antes de aceptar
una explicación; el registro de decisiones con evidencia trazable a sesión y
commit.

**Qué deberíamos cambiar de inmediato, sin esperar al próximo proyecto:** CI
ejecutable (costo mínimo, la brecha de mayor impacto documentada), el
decorador transversal que elimina el preámbulo repetido 19 veces, y una fuente
única de verdad para el estado del ciclo con el resto de documentos enlazando.

**La metodología ideal para proyectos complejos de IA y software**, según la
evidencia de este proyecto: fronteras inviolables *que existen en código, no
solo en prosa*, desde el primer commit; un ciclo de contacto temprano con la
realidad que reemplace el plan por evidencia en cuanto la evidencia esté
disponible; una disciplina de refutación activa presente desde la sesión 0, no
descubierta por el costo acumulado de no tenerla; criterios de convergencia
que exijan variación deliberada, nunca repetición de la misma prueba; y un
criterio de éxito de cada fase que trate pagar deuda estructural como un
resultado tan válido como una feature nueva. Esta síntesis se desarrolla como
metodología normativa, independiente de este proyecto, en
`docs/analisis/manual-desarrollo-ia-software.md`.
