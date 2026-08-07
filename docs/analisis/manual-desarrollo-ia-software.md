# Manual de Desarrollo para Proyectos de IA y Software

**Versión:** 1.0 · **Naturaleza:** metodología normativa agnóstica de
dominio, stack o herramienta — el cuerpo de este documento no menciona
ninguno específico, así que es deliberadamente portable en ese sentido. No es
independiente de su origen: toda su base empírica proviene de un único
proyecto (evidencia n=1), y cada afirmación normativa está etiquetada según
cuánto de esa evidencia realmente la sostiene (ver §0.1). La evidencia
empírica que lo originó (un proyecto real de 24 días, 163 commits, 34
sesiones de desarrollo agente+humano) vive en el Anexo, separable del cuerpo
normativo.

**Cómo usar este manual:** no es una lista de buenas intenciones. Cada
principio tiene una contramedida operacional — algo que se hace distinto en la
práctica, no una actitud a adoptar. Cada fase tiene un criterio de salida
falsable — algo que puede fallar y bloquear el avance, no una casilla que se
tilda por costumbre. Si un principio no cambia una decisión concreta la
próxima vez que aplique, no está funcionando como principio: está funcionando
como decoración.

---

## 0. Premisa

**Hipótesis metodológica de origen:** en el proyecto que da origen a este
manual (ver Anexo), la fricción dominante no fue la capacidad técnica sino la
**acumulación silenciosa de supuestos no verificados**: sobre qué escala
soportará el sistema, sobre si una decisión de diseño generaliza más allá del
caso que la motivó, sobre si la disciplina que el equipo se impone a sí mismo
sigue vigente sin que nada la verifique mecánicamente. Este manual está
organizado alrededor de esa idea: **la calidad de un proyecto es la calidad
de sus supuestos verificados, no el volumen de su código o de su
documentación.** No hay evidencia de más de un proyecto que sostenga esto
como ley general — se ofrece como el eje organizador más útil que esta
experiencia particular produjo.

De ahí se derivan dos compromisos que atraviesan todo el documento —
*[RECOMENDACIÓN]*: respaldados por la evidencia del proyecto de origen, no
verdades independientes del contexto (su peso depende del costo real de dejar
un supuesto sin verificar o un criterio sin automatizar):

1. **Todo supuesto de alto apalancamiento debe tener una fecha y un método de
   verificación**, no solo quedar registrado como "cosa que creemos".
2. **Todo criterio de calidad que pueda expresarse como comando ejecutable
   debe convertirse en un gate automático**, no quedar como una convención que
   depende de que alguien se acuerde de aplicarla.

### 0.1 Cómo leer las etiquetas de este manual

Este manual deriva de un único proyecto (ver Anexo) — su evidencia es n=1, no
una muestra de múltiples proyectos. Para no vestir de ley universal lo que,
en la mayoría de los casos, es una experiencia concreta bien documentada,
cada afirmación normativa de este documento lleva una etiqueta:

- **PRINCIPIO GENERAL** — verdadero por la estructura lógica del enunciado,
  no por la frecuencia con que se observó. No depende de más muestra para
  sostenerse. Ninguna entrada normativa de §0–§7 de este manual califica como
  principio general tal como está enunciada: toda norma de este documento
  depende, en algún grado, de costo, riesgo, contexto, estructura documental
  o capacidad de automatización, así que la categoría queda definida aquí
  pero sin miembros en el cuerpo.
- **RECOMENDACIÓN** — respaldada por evidencia real del proyecto de origen,
  pero sin verificación fuera de él. Vale la pena intentarla; no está probada
  como óptima.
- **PATRÓN OBSERVADO** — ocurrió una vez, documentado con evidencia
  verificable, con un mecanismo de prevención derivable de su propia
  estructura. Razonable esperar que reaparezca en contextos similares; no
  confirmado que sea frecuente en general.
- **REGLA LOCAL** — presupone una política, un rol o una arquitectura de un
  proyecto en particular (ej. el modelo arquitecto-humano + agente-ejecutor
  de kicad-mcp, el proyecto de origen de este manual). Generaliza solo a
  proyectos con una estructura equivalente; el texto de cada entrada indica
  el proyecto de origen cuando es relevante.
- **HIPÓTESIS METODOLÓGICA** — propuesta razonable, nunca ejecutada ni
  medida en el proyecto de origen. Se ofrece para probar, no como práctica
  ya validada.

---

## 1. Fases del proyecto

*[RECOMENDACIÓN — aplicada y verificada en un ciclo agente-ejecutor +
arquitecto-humano operando sobre una herramienta externa cara de ejercitar;
ver Anexo]*

Seis fases, cada una con objetivo, entregable, y **criterio de salida
falsable** — una condición que puede efectivamente no cumplirse, y que si no
se cumple, bloquea el avance a la fase siguiente. Una fase que "generalmente
progresa" no es un criterio de salida; una fase que puede fallar
verificablemente sí lo es.

### Fase 0 — Contratos

**Objetivo:** fijar, antes de escribir código de producto, lo que el sistema
nunca podrá negociar consigo mismo bajo presión — sus fronteras, su taxonomía
de errores, y la lista completa de supuestos sobre los que se apoya el diseño.

**Entregables:**
- Documento de fronteras inviolables: qué partes del sistema no se modifican
  sin un proceso de aprobación explícito y por qué (ver §3, Principio 1).
- Taxonomía de errores tipada, versionada como contrato desde el primer
  commit — *[REGLA LOCAL, de kicad-mcp: relevante cuando el sistema
  expone una superficie de error a través de un borde de proceso o de
  agente; en otros dominios el entregable equivalente puede ser distinto]*.
- Lista completa de supuestos de diseño, cada uno marcado como **validado**,
  **por validar (con fecha)**, o **asumido sin plan de validación** —
  categoría que debe quedar vacía antes de salir de esta fase.

**Criterio de salida (falsable):** ningún supuesto de alto apalancamiento
(uno cuya falsedad invalidaría una porción significativa del diseño) queda en
la categoría "asumido sin plan de validación". Si existe uno, la fase no
cierra — se agenda su verificación o se reduce el alcance del diseño que
depende de él.

### Fase 1 — Núcleo mínimo

**Objetivo:** el loop más corto posible que atraviesa el sistema de punta a
punta, aunque el resultado sea tosco. No es un prototipo desechable: es el
esqueleto real sobre el que se construye todo lo demás.

**Entregables:**
- El loop mínimo funcionando de punta a punta sin intervención humana
  obligatoria en ningún paso intermedio.
- **Infraestructura de calidad automatizada desde el primer commit**: todo
  lo que la Fase 0 definió como contrato verificable por comando (lint,
  tipos, tests) corre en un gate que bloquea la integración, no en una
  convención escrita.

**Criterio de salida (falsable):** el loop cierra de punta a punta sin que un
humano tenga que intervenir manualmente en ningún paso que el diseño declaró
automatizable. Si un paso requiere intervención manual, se documenta
explícitamente como límite conocido de esta fase — no se declara "completo"
con el paso escondido.

### Fase 2 — Contacto con la realidad

**Objetivo:** exponer el núcleo mínimo a un caso de uso real cuanto antes,
antes de construir ninguna capacidad adicional sobre supuestos no probados.

**Entregables:**
- Un primer ejercicio de uso real (no un test sintético) contra el sistema
  completo, con una métrica numérica comparable y un criterio de corte
  explícito definido **antes** de correr el ejercicio.
- Registro completo de fricciones encontradas, priorizadas por severidad y
  costo, sin filtrar las que resulten incómodas para el diseño original.

**Criterio de salida (falsable):** existe una métrica numérica registrada
(no una impresión cualitativa) y una lista de gaps priorizada. El resultado
puede ser malo — de hecho, un resultado malo temprano es la señal más
valiosa que esta fase puede producir, porque es la más barata de obtener.

### Fase 3 — Hardening dirigido por evidencia

**Objetivo:** cerrar, en orden de severidad, los gaps que la Fase 2 reveló —
nunca los que parecen más interesantes de resolver.

**Entregables:**
- Para cada hallazgo no trivial: una sesión de investigación separada de la
  sesión de fix, con hipótesis explícita y criterio de refutación formulado
  antes de aceptar una causa raíz (ver §2, Marco de decisión).
- Todo fix lleva un test de regresión que falla sin el fix y pasa con él.

**Criterio de salida (falsable):** cero hallazgos de severidad máxima del
ciclo de contacto anterior quedan sin resolver o sin una decisión explícita y
documentada de diferirlos con condición de reapertura (ver §3, Principio 15).

### Fase 4 — Validación con variación deliberada

**Objetivo:** demostrar que el sistema generaliza, no que un experimento es
repetible. En el proyecto de origen, esta fue la fase que se ejecutó peor:
repetir la misma prueba varias veces y llamarlo "convergencia" fue la trampa
metodológica más costosa de todo el ciclo (ver §4, Antipatrón A3;
*[PATRÓN OBSERVADO]*).

**Entregables:**
- Cada ronda de validación varía deliberadamente al menos un factor no
  ejercitado en la ronda anterior (escala, dominio de datos, topología del
  problema, condiciones de entorno — lo que sea relevante para el sistema en
  cuestión).
- Criterios de aceptación cuantitativos, fijados **antes** de correr la
  validación, contra una referencia externa e independiente cuando exista una
  disponible.

**Criterio de salida (falsable):** el sistema fue puesto a prueba contra al
menos dos configuraciones que difieren en una dimensión que el diseño
original no ejercitó, y el resultado de ambas —incluyendo fracasos— está
documentado con el mismo nivel de detalle que los éxitos. Una sola
configuración validada repetidamente, sin importar cuántas veces, **no
satisface este criterio**.

### Fase 5 — Consolidación y release

**Objetivo:** cerrar la brecha entre lo que el sistema hace y lo que se puede
verificar mecánicamente que hace — sin que la deuda estructural pierda
sistemáticamente frente a agregar capacidades nuevas.

**Entregables:**
- Deuda estructural identificada en fases anteriores, con presupuesto
  explícito de esta fase dedicado a pagarla — no solo documentarla.
- El criterio de éxito de esta fase incluye "deuda pagada" como resultado
  válido con el mismo peso que "feature nueva entregada".

**Criterio de salida (falsable):** el release no se declara con hallazgos de
severidad máxima conocidos y sin resolver, salvo con un plan público, fechado
y con dueño explícito para cada uno.

---

## 2. Marco para la toma de decisiones

*[RECOMENDACIÓN — aplicada una vez, retrospectivamente, sobre la decisión
más costosa del proyecto de origen (ver Anexo); no tiene todavía una corrida
prospectiva registrada]*

Un proceso de 7 pasos para cualquier decisión técnica no trivial —
arquitectónica, de diagnóstico de causa raíz, o de alcance de un fix.

1. **Definir el problema** en una frase verificable, no en una intuición
   ("¿el sistema es confiable para el siguiente paso?", no "quiero que
   funcione mejor").
2. **Formular la hipótesis** que se está evaluando, explícitamente, por
   escrito.
3. **Formular el criterio de refutación ANTES de investigar** *[RECOMENDACIÓN
   — el núcleo popperiano, pero su peso concreto en un proceso dado depende
   del costo de estar equivocado; el dato de frecuencia es del proyecto de
   origen]* — la pregunta obligatoria es "¿qué resultado demostraría que
   esta hipótesis es falsa?". En el proyecto de origen fue el paso que más
   tardó en formalizarse como contrato explícito (ver Anexo); por
   construcción es candidato a mayor apalancamiento del proceso completo: una
   hipótesis aceptada sin haber definido qué la refutaría tiende a
   sobrevivir aunque sea incorrecta, porque nadie diseñó el experimento
   capaz de tumbarla.
4. **Investigar alternativas** — incluyendo la alternativa de no actuar, y la
   de variar la prueba en vez de repetirla.
5. **Construir el experimento o prototipo más barato posible** que pueda
   producir el resultado definido en el paso 3, no el más completo.
6. **Ejecutar y comparar contra el criterio de refutación**, no contra la
   expectativa inicial. Si el resultado refuta la hipótesis, la hipótesis se
   descarta — no se reinterpreta para que sobreviva.
7. **Documentar el razonamiento completo**, incluyendo las alternativas
   descartadas y por qué — no solo la decisión final. Una decisión sin su
   razonamiento es indistinguible de una corazonada seis meses después.

**Regla de aplicación:** el paso 3 no es opcional ni diferible a "cuando haya
tiempo". Una decisión que llega al paso 6 sin haber pasado por el paso 3 no
está validada — está confirmada por sesgo de confirmación, que es la forma
más barata de sentirse seguro y la más cara de estar equivocado.

**Regla de proporcionalidad:** el peso de este proceso escala con el costo de
estar equivocado. Una decisión reversible en minutos rara vez necesita las 7
líneas escritas; una decisión que condiciona el diseño de módulos futuros o
que es cara de revertir sí las necesita — el criterio es el costo de la
decisión, no una casilla a marcar por trámite.

---

## 3. Principios de ingeniería

Quince principios, cada uno con su contramedida operacional — qué se hace
distinto, no qué actitud se adopta.

**P1 — Toda frontera inviolable necesita un mecanismo, no una convención.**
*[RECOMENDACIÓN]* Si algo no debe cambiar bajo presión, protegerlo con
algo difícil de sortear (un assert estructural, un test que falla, un gate
de CI) en vez de solo una regla escrita que un ejecutor bajo presión pueda
racionalizar como excepción justificada — el costo de construir el mecanismo
debe pesarse contra el costo real de esa frontera fallando en silencio.
*Cuándo aplica:* cualquier contrato cuya violación sería cara de detectar
tarde. *Contramedida al fallar:* si la frontera solo existe en prosa, no está
protegida — tratarla como pendiente, no como cerrada.

**P2 — El rigor de la automatización debe igualar al rigor del método.**
*[RECOMENDACIÓN]* Un proceso de decisión excelente documentado en prosa, sin
un gate ejecutable
que lo verifique, caduca en el próximo cambio que nadie revisó con el mismo
cuidado. Todo criterio de calidad expresable como comando se convierte en
gate automático en la misma fase en la que se define, no se difiere.

**P3 — La premisa de una tarea es hipótesis, no hecho.** *[RECOMENDACIÓN]*
Antes de actuar sobre lo que un encargo, un ticket o un plan asume como
cierto, verificarlo contra el estado real del sistema. En el proyecto de
origen, verificar la premisa contra el estado real corrigió el rumbo en al
menos 6 de 34 sesiones (ver Anexo); ejecutar sin verificar propaga ese error
al resultado.

**P4 — Formular el criterio de refutación es la primera línea de trabajo, no
la última.** *[RECOMENDACIÓN]* Ver §2, paso 3. Repetido aquí porque, según la
evidencia que origina este manual, es un candidato fuerte a principio de
mayor apalancamiento: su ausencia fue, en ese proyecto, una fuente relevante
de trabajo desperdiciado observada (ver Anexo) — el proyecto de origen no
llevó un censo de causas que permita afirmar que fue la más frecuente.

**P5 — Una investigación que cierra sin arreglar nada, pero reduce
incertidumbre real, puede contar como éxito.** *[RECOMENDACIÓN]* El objetivo
de investigar no tiene que ser producir un fix — puede ser saber más de lo
que se sabía antes con la misma confianza; cuánto pesa eso frente a un fix
depende del criterio de éxito que se haya fijado para esa fase. Refutar una
hipótesis con evidencia sólida vale, bajo ese criterio, tanto como confirmar
otra. *Contramedida:* evitar forzar un cierre con fix cuando la evidencia
todavía no sostiene una causa raíz; documentar "no sabemos X, pero
descartamos Y y Z con evidencia" suele ser preferible a una explicación
plausible sin refutar.

**P6 — Un criterio de convergencia declarado sobre una sola variable
controlada es frágil.** *[RECOMENDACIÓN]* Repetir el mismo experimento con el
mismo resultado demuestra que el experimento es repetible, no que el sistema
generaliza. Un criterio de "está listo para el siguiente paso" es más
confiable cuando incluye variación deliberada de al menos un factor no
ejercitado antes; cuánta variación es necesaria depende del costo de
equivocarse sobre esa convergencia.

**P7 — La restricción que más condiciona el alcance se mide lo antes
posible.** *[RECOMENDACIÓN]* Si el sistema depende de un componente,
proveedor o algoritmo con
reputación de fragilidad a escala, ese límite se estresa en un experimento
temprano y barato — nunca se descubre después de haber construido semanas de
diseño que lo daban por resuelto.

**P8 — Una verdad, un dueño; el resto enlaza.** *[REGLA LOCAL — depende de la
arquitectura documental del proyecto: solo aplica sin matices donde enlazar
con un identificador estable es tan barato como resumir; en kicad-mcp, con
ADR y `docs/DECISIONES.md` como fuentes autoritativas, lo fue]* Un hecho del
proyecto con más de una fuente autoritativa es una fuente de divergencia
silenciosa. Donde enlazar sea viable, un documento que necesite referenciarlo
enlaza con un identificador estable en vez de resumirlo o reescribirlo con
sus propias palabras — cada resumen es una copia que puede divergir del
original sin que nadie lo note; esto no implica que ningún documento pueda
resumir nunca, sino que todo resumen es un riesgo a sopesar contra el costo
de no tener uno.

**P9 — Una decisión merece registro permanente solo si condiciona trabajo
futuro de alguien más.** *[RECOMENDACIÓN]* No todo hallazgo necesita un
documento de decisión
formal. El criterio de admisión: ¿alguien, en una tarea futura no relacionada
con esta, necesitará saber esto para no repetir el error o la investigación?
Si no, un comentario o un commit alcanza.

**P10 — El criterio de éxito de cualquier fase debe incluir un eje donde
pagar deuda estructural pueda ganar frente a agregar una capacidad nueva.**
*[PATRÓN OBSERVADO — ver A7]* Si el criterio de éxito mide únicamente
volumen de funcionalidad entregada, la deuda tiende a perder sistemáticamente
contra features, porque features son visibles y deuda no. Corregir esto
requiere hacer la deuda visible en la misma métrica que las features.

**P11 — Fragmentación repetida de la unidad de trabajo es una señal de mal
dimensionamiento, no de mala suerte puntual.** *[HIPÓTESIS METODOLÓGICA — en
el proyecto de origen las tres fragmentaciones registradas llegaron a 3, 3 y
4 sub-unidades; "dos veces" es un umbral de alarma propuesto, no calibrado
contra un caso que se haya detenido justo ahí]* Si la misma unidad de trabajo
nominal se divide en sub-unidades dos veces seguidas, el problema no es la
ejecución de esa unidad: es que se dimensionó mal desde el principio. La
corrección es ajustar el criterio de dimensionamiento de la siguiente unidad,
no tolerar que la fragmentación se vuelva la norma.

**P12 — Toda fricción de entorno que aparece dos veces se convierte en
tarea de tooling.** *[RECOMENDACIÓN — el umbral "dos veces" es una elección
operacional razonable, no derivada de comparar distintos umbrales; el caso
de origen (ver Anexo) llegó a 3 ocurrencias en una sola sesión]* Una fricción
operacional documentada una vez es información. Documentada dos veces sin que nadie la resuelva es deuda
aceptada tácitamente. La segunda ocurrencia dispara automáticamente una
tarea de eliminación, no una tercera nota en el próximo reporte.

**P13 — La métrica de progreso central es el uso real de punta a punta.**
*[RECOMENDACIÓN]* Ninguna revisión de diseño, por rigurosa que sea, sustituye
a ejecutar el sistema completo contra un caso de uso real con un número
comparable y un criterio de corte fijado antes de medir. En el proyecto de
origen, los gaps estructurales más caros aparecieron bajo uso real y no bajo
revisión estática (ver Anexo) — no hay evidencia de que esto sea universal,
pero es razón suficiente para no sustituir uso real por revisión de diseño.

**P14 — Un supuesto de alto apalancamiento sin plan de verificación agendado
tiende, en la práctica, a quedar igual de sin verificar que si no estuviera
documentado.** *[RECOMENDACIÓN]* Listar un supuesto en una tabla de riesgos
no lo verifica por sí solo. Sin una fecha y un método de verificación
asociados, tiende a seguir sin verificarse — no necesariamente por mala fe,
sino porque nada empuja a resolverlo mientras no falle visiblemente; cuánto
importa esto escala con el apalancamiento real del supuesto.

**P15 — Diferir una decisión sin una condición de reapertura escrita y
verificable equivale, en la práctica, a abandonarla.** *[RECOMENDACIÓN — el
núcleo lógico ("una condición no especificable no es comprobable") es
independiente del contexto; el peso de exigirla por escrito en cada decisión
diferida depende del costo de esa decisión]* "Lo revisamos cuando haya
evidencia" sin especificar qué contaría como esa evidencia deja la decisión
sin un mecanismo real de reapertura. Cuanto más cara sea revertir el efecto
de diferir, más vale que la condición de reapertura sea concreta al punto de
que cualquiera pueda comprobar, sin ambigüedad, si ya se cumplió.

---

## 4. Antipatrones y contramedidas

*[PATRÓN OBSERVADO, los diez — cada uno ocurrió en el proyecto de origen
(ver Anexo); "recurrentes" describe la expectativa de que reaparezcan en
contextos similares, no una frecuencia ya medida entre proyectos]*

Diez patrones de fallo documentados con evidencia, cada uno con su mecanismo
concreto de prevención — no una advertencia general, sino una acción
específica que rompe el patrón antes de que se instale.

**A1 — Frontera que protege el vacío.** Declarar "inviolable" un contrato,
gate o mecanismo que todavía no existe en código. El resultado es una
garantía documentada que engaña a cualquiera que la lea confiando en que
protege algo real. *Prevención:* una frontera se declara junto con su
implementación, o después — nunca antes. Si algo se planea proteger mañana,
se documenta como "planeado", no como "inviolable".

**A2 — Gate escrito sin gate ejecutable.** Una lista de criterios de calidad
en prosa (una "definición de terminado") que depende de que un humano la
recuerde y la ejecute manualmente cada vez. *Prevención:* todo criterio
expresable como comando (lint, tipos, tests, formato) se convierte en un
paso de integración continua automático en cuanto se define — nunca se dejan
como "pasos a correr antes de integrar" en un documento.

**A3 — Convergencia sobre variable controlada.** Declarar que un sistema
"converge" o está "listo" a partir de repetir el mismo experimento múltiples
veces sin variar ningún factor relevante. En el caso que origina este
antipatrón (ver Anexo), la primera vez que se ejercitó una dimensión
distinta, el sistema falló, y la "convergencia" declarada resultó haber sido
una ilusión estadística sobre una muestra sin diversidad real. *Prevención:* ningún criterio de "listo para
avanzar" se aprueba sin al menos una variación deliberada de un factor no
probado antes.

**A4 — Techo de escala medido al final.** Descubrir el límite estructural
real de una capacidad crítica (usualmente ligada a un componente de terceros)
recién en la validación final, después de haber construido semanas de diseño
que asumían que ese límite estaba resuelto. *Prevención:* todo componente
crítico con reputación de fragilidad a escala se somete a un experimento de
estrés temprano y barato, antes de comprometer diseño encima de su supuesto
de escalabilidad.

**A5 — Verdad duplicada en N documentos.** El mismo hecho reescrito con
distintas palabras en varios lugares, que empieza a divergir de sí mismo sin
que nadie lo note hasta que alguien lo detecta por accidente. *Prevención:*
un hecho, una fuente. Todo lo demás enlaza con un identificador estable. Si
se detecta duplicación, se elimina en el momento —no se agrega un proceso de
"barrido periódico" que trata el síntoma en vez de la causa.

**A6 — Inflación de registro de decisiones.** Registrar formalmente cada
micro-decisión con el mismo aparato que una decisión arquitectónica real,
hasta que el volumen de registros vuelve imposible saber cuáles importan.
*Prevención:* aplicar P9 estrictamente — el criterio de admisión al registro
formal es si alguien, en el futuro, necesita esa información para no repetir
trabajo. Si no, no entra.

**A7 — Deuda estructural sin eje de éxito que la premie.** Un criterio de
éxito que solo mide "código nuevo entregado" o "features cerradas" hace que
pagar deuda compita en desventaja estructural frente a features, porque no
aparece en la misma métrica.
*Prevención:* P10 — hacer visible pagar deuda en el mismo criterio de éxito
que las features, con presupuesto de tiempo explícito por ciclo.

**A8 — Supuesto tabulado sin eval.** Un supuesto de diseño de alto
apalancamiento queda listado en una tabla de riesgos o de supuestos, marcado
como "pendiente de validar", y nunca se vuelve a tocar porque nada obliga a
hacerlo. *Prevención:* P14 — todo supuesto de alto apalancamiento lleva fecha
de verificación agendada en el momento en que se identifica, no "cuando se
pueda".

**A9 — Fricción de entorno documentada en vez de eliminada.** Un problema
operacional recurrente (un paso manual, un reinicio, una configuración que se
pierde) se anota cada vez que ocurre, con el mismo detalle, sin que nadie lo
convierta en una tarea de eliminación. *Prevención:* P12 — la segunda
ocurrencia documentada de la misma fricción dispara automáticamente una tarea
de tooling con prioridad, no una tercera nota.

**A10 — Contrato nuevo creado para esquivar una frontera protegida.** Cuando
extender una frontera protegida requeriría un proceso de aprobación más
lento que crear algo técnicamente distinto que el mismo caso de uso podría
usar en su lugar, existe la tentación de crear ese "algo distinto" —
cumpliendo la letra de la frontera mientras se erosiona su propósito. El
resultado: un contrato nuevo, informal, sin las garantías (spec, tests,
validación) que sí tiene el contrato original que se evitó tocar.
*Prevención:* si el espíritu de una frontera protegida aplica a un caso
nuevo, se pide su extensión explícita a través del proceso de aprobación
correspondiente — nunca se construye un atajo paralelo para evitar el
trámite, sin importar cuánto más rápido parezca.

---

## 5. Anatomía de una unidad de trabajo

*[RECOMENDACIÓN — describe la estructura que usó el proyecto de origen, con
un modelo de dos roles (arquitecto-humano que encarga, agente-ejecutor que
ejecuta y reporta); el paso de escalamiento presupone esa separación de
roles]*

Sea cual sea el nombre que se le dé (sesión, sprint, ticket, iteración), toda
unidad de trabajo bien dimensionada comparte esta estructura:

**Al empezar:**
- Objetivo verificable en una frase, no una intención vaga.
- Si la unidad involucra una hipótesis técnica o un cambio de comportamiento
  del sistema: hipótesis + evidencia que la confirmaría + evidencia que la
  refutaría + estrategia de protección contra regresión, **formulados antes
  de tocar nada** (aplicación directa de §2, paso 2-3).
- Verificación explícita de que la premisa de la tarea sigue siendo cierta
  contra el estado real del sistema (P3) — no asumirla porque así se escribió
  el encargo.

**Durante:**
- Cualquier desviación del plan original que cambie el estado observable del
  sistema (no solo detalles de implementación dentro del plan) se escala
  antes de ejecutarse, no se decide unilateralmente y se explica después
  *[REGLA LOCAL, de kicad-mcp: presupone un rol externo a quien escalar;
  en un equipo sin esa separación, sustituir por el mecanismo de revisión
  equivalente]*.
- Toda decisión no trivial pasa por el marco de §2 en proporción a su costo
  de estar equivocada.

**Al cerrar:**
- Qué se completó, verificado contra el objetivo del inicio — no reformulado
  para que parezca que se completó.
- Qué fricciones nuevas aparecieron, con severidad y costo explícitos, sin
  filtrar las incómodas para el diseño.
- Toda decisión persistente tomada durante la unidad, con su razonamiento
  (P9: solo las que condicionan trabajo futuro).
- Una propuesta concreta y accionable para la siguiente unidad de trabajo —
  no una lista abierta de posibilidades.

**Señal de mal dimensionamiento (P11):** si esta unidad se fragmenta en
sub-unidades dos veces, el problema es el tamaño con el que se planificó, no
la ejecución. Ajustar el criterio de dimensionamiento antes de planificar la
siguiente.

---

## 6. Métricas mínimas

*[Ver etiquetas individuales abajo — solo la primera métrica tiene historia
de uso real en el proyecto de origen; las otras cuatro son propuestas
consistentes con los antipatrones de §4, nunca calculadas]*

Un proyecto complejo necesita, como mínimo, estas métricas para evaluarse a
sí mismo sin autoengaño:

- **Una métrica de uso real de punta a punta** *[RECOMENDACIÓN — con
  historia real, ver Anexo]*, numérica y comparable entre ciclos, con
  criterio de corte fijado antes de medir (P13). Es la métrica central —
  todas las demás son de apoyo.
- **Cobertura de gates automáticos** *[HIPÓTESIS METODOLÓGICA — nunca
  calculada en el proyecto de origen]* sobre el total de criterios de
  calidad definidos: qué proporción de la "definición de terminado" está
  verificada por un comando ejecutable versus por convención escrita (mide
  directamente el riesgo del Antipatrón A2).
- **Ratio de deuda pagada versus deuda identificada** *[HIPÓTESIS
  METODOLÓGICA — nunca calculada en el proyecto de origen]* por ciclo — no
  solo cuánta deuda se documenta, sino cuánta efectivamente se cierra (mide
  directamente el riesgo del Antipatrón A7).
- **Diversidad de la validación** *[HIPÓTESIS METODOLÓGICA — nunca
  calculada como número en el proyecto de origen]*: cuántos factores
  distintos se han ejercitado deliberadamente contra el sistema, no cuántas
  veces se ha probado (mide directamente el riesgo del Antipatrón A3).
- **Supuestos de alto apalancamiento sin verificar**, con antigüedad
  *[HIPÓTESIS METODOLÓGICA — el proyecto de origen identificó un supuesto
  de este tipo (S1, TOON vs JSON) pero nunca trackeó su antigüedad como
  campo]*. Un supuesto que lleva mucho tiempo en esa lista sin fecha de
  verificación es una señal de alarma, no un detalle administrativo.

---

## 7. Control de calidad y gestión de riesgos

**Control de calidad** *[RECOMENDACIÓN — lección derivada de la ausencia de
CI observada en el proyecto de origen, no de un caso donde se haya ejecutado
así desde el primer commit; ver Anexo]*: todo criterio de calidad expresable
como comando ejecutable (formato, tipos, tests, lint, cobertura mínima) es un
gate automático desde el primer commit del proyecto, no una aspiración de
fase tardía (P2, A2). La práctica más estricta es no integrar ningún cambio
que rompa un gate, sin hacer excepción por "es una corrección rápida" o "lo
arreglo después" — precisamente las circunstancias bajo las que la
disciplina escrita suele fallar; qué tan estrictamente aplicarla depende del
costo de bloquear una integración urgente.

**Gestión de riesgos** *[RECOMENDACIÓN — estructura usada en el proyecto de
origen, no verificada fuera de él]*: un riesgo entra al registro del proyecto
cuando se identifica, con severidad, probabilidad, y —idealmente— una acción
concreta y un dueño, no solo una descripción. Un riesgo sin acción asociada
tiende a funcionar como una lista de preocupaciones más que como gestión de
riesgos. Revisar periódicamente los riesgos abiertos con una disciplina
comparable a la de las tareas activas ayuda a que un riesgo que envejece sin
resolverse ni revisarse no termine siendo, en la práctica, indistinguible de
uno que nunca se documentó.

**Presupuesto de documentación:** documentar es necesario; documentar más de
lo necesario tiene costo real (mantenimiento, divergencia, tiempo de lectura
que compite con tiempo de trabajo). Regla práctica: si un hecho ya vive en un
lugar autoritativo, la siguiente mención suele ser mejor como enlace que como
una nueva explicación completa (P8, A5). *[HIPÓTESIS METODOLÓGICA — el umbral que
sigue no está calibrado: el único caso medido del proyecto de origen llegó a
7 reescrituras completas antes de reconocerse como problema, ver Anexo]* Si
un documento necesita reescribirse por completo más de dos o tres veces en la
vida del proyecto, la causa probablemente no es que el proyecto cambia mucho
— es que ese documento intenta ser la fuente de demasiadas verdades a la vez
y debería dividirse o reducirse a un índice que enlaza a fuentes más
estables.

---

## Anexo — Origen empírico de este manual

Este manual se deriva de una retrospectiva metodológica sobre un proyecto
real de 24 días calendario (163 commits, ~34 unidades de trabajo numeradas,
~45 ramas según el inventario usado en la retrospectiva original — el número
histórico exacto no puede reconstruirse con fiabilidad a partir de las refs
actuales), documentada en
`docs/analisis/retrospectiva-metodologica-2026-08.md`. Cada principio,
antipatrón y fase de este documento tiene su evidencia de origen — qué
ocurrió, qué costó, qué habría cambiado el resultado — desarrollada con
detalle en ese análisis. Este anexo es la única sección de todo el manual que
depende del proyecto de origen; el cuerpo normativo (§0-§7) es
intencionalmente independiente de él y no requiere leer la retrospectiva para
aplicarse a un proyecto nuevo.

**Mapa de trazabilidad** (principio/antipatrón → sección de la retrospectiva
donde se fundamenta):

| Este manual | Retrospectiva |
|---|---|
| P1, A1 (frontera del vacío) | §4-3, §5-6 |
| P2, A2 (gate sin automatizar) | §5-1, §9 |
| P3 (premisa como hipótesis) | §6, §7 |
| P4, §2 paso 3 (refutación primero) | §6, §8, §12 |
| P5 (investigación sin fix = éxito) | §4-5, §8 |
| P6, A3 (convergencia sobre variable controlada) | §5-2, §7, §11 |
| P7, A4 (techo de escala tardío) | §5-3, §10 |
| P8, A5 (verdad duplicada) | §5-4, §9 |
| P9, A6 (inflación de decisiones) | §7 |
| P10, A7 (deuda sin eje de éxito) | §5-5, §9 |
| P11 (fragmentación de unidad de trabajo) | §5-8, §2 |
| P12, A9 (fricción de entorno repetida) | §5-10, §9 |
| P13 (uso real como métrica central) | §4-4, §6 |
| P14, A8 (supuesto sin eval) | §10 |
| P15 (diferir con condición escrita) | §7 |
| A10 (contrato paralelo para esquivar frontera) | §5-7 |

Un lector que quiera ver estos principios en acción, con nombres de sesión,
commits y números concretos, debe acudir a ese documento — este manual
deliberadamente no los incluye para mantenerse aplicable a cualquier proyecto
futuro sin edición.
