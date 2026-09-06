# Juicio cruzado de Codex v1 — protocolo de revisión doble

**Autoridad:** Gato
**Alias coloquial:** "judgment day" (frase disparadora, ver §2)
**Propósito:** revisar una unidad de riesgo alto con dos revisores
independientes entre sí, ciegos y simultáneos, sin ampliar la autoridad de
nadie ni el número de reparaciones permitidas.

## 1. Naturaleza y subordinación

Este protocolo es una variante intensiva y **opcional** del §5 "Revisión de
Codex" de `docs/proceso/FLUJO-HIBRIDO-MULTIAGENTE-v2.md`. No lo reemplaza, no
lo amplía y no crea un rol nuevo: sigue siendo la revisión posterior única que
`AGENTS.md` §6 ya prevé, ejecutada con dos jueces en lugar de uno.

Formalmente es una instancia pre-redactada de la excepción del §13 del flujo
v2. Que esté escrita no la activa: cada corrida exige la declaración del §4 de
este documento. Conforme al §13 del flujo v2, **una corrida no se vuelve
precedente automático**: no obliga a repetirla en unidades comparables ni
convierte el juicio doble en el control por defecto.

Ante conflicto prevalecen `AGENTS.md` y el flujo v2. Este documento no
reinterpreta F1–F5, G1–G5, severidades ni estados de cierre; los reusa.

## 2. Cuándo se activa

Se activa sólo si se cumplen las dos condiciones a la vez:

| Condición | Contenido |
|---|---|
| Riesgo | Unidad `R2` según `AGENTS.md` §8, o `R1` de riesgo alto. |
| Pedido | Gato lo pide de forma explícita para esa unidad concreta. |

`R1` de riesgo alto significa, y sólo significa: superficie consumida en
runtime por otro agente, ruta destructiva o de borrado masivo, o código cuyo
comportamiento crítico no tiene verificación mecánica equivalente.

Frases disparadoras reconocidas: "corré judgment day", "juicio cruzado",
"revisión cruzada doble", "doble juicio ciego sobre X". Cualquiera de ellas
inicia el §3; ninguna de ellas sustituye la declaración del §4.

No se activa por iniciativa del Escritor, por `R0`, por `R1` ordinario, ni
"por las dudas". La intensidad sigue siendo proporcional al riesgo
(`AGENTS.md` §8, flujo v2 §8): un `R1` ordinario se revisa con una sola pasada
de Codex y eso es lo correcto, no una carencia.

### Señalamiento proactivo (obligación del Escritor)

No activarlo por iniciativa propia no exime de avisar. Cuando Claude Code
identifica, durante el trabajo normal, una unidad que cumple el criterio de
riesgo de la tabla de arriba (`R2`, o `R1` de riesgo alto según la
definición de este documento), debe señalarlo a Gato en el momento en que
lo detecta — con la razón concreta, no genérica ("toca F1-F5 porque X",
"borra Y de forma irreversible", no "podría ser riesgoso") — y sugerir la
activación del juicio cruzado **sólo si a su criterio está genuinamente
justificado**, no como oferta reflexiva ante cualquier cambio de riesgo
`R1` ordinario. La decisión de activar sigue siendo de Gato (§2, condición
de pedido); esto sólo obliga a ofrecerle la información y la sugerencia a
tiempo para decidir.

## 3. Roles durante el juicio

| Rol de este documento | Rol de `AGENTS.md` §2 | Agente | Qué puede |
|---|---|---|---|
| Autoridad | Autoridad | Gato | Activa, fija presupuesto, resuelve contradicción y `BLOQUEAR`. |
| Juez A | Revisor independiente (instancia 1) | `mcp__codex__codex`, modelo M1 | Emite un veredicto sobre la unidad congelada. |
| Juez B | Revisor independiente (instancia 2) | `mcp__codex__codex`, modelo M2 | Íd., sin ver nada del Juez A. |
| Orquestador | Escritor | Claude Code | Congela, lanza, transcribe, empareja hallazgos y verifica. |

"Juez A/B" y "Orquestador" son nombres de función dentro de ESTE protocolo,
no roles nuevos: la columna derecha es el mapeo obligatorio a los roles ya
existentes de `AGENTS.md` §2. Ningún rol de `AGENTS.md` se duplica ni se
reemplaza — el Revisor independiente simplemente corre dos veces.

Claude Code **no es un tercer juez**. Produjo la unidad, así que por
`AGENTS.md` §4 no puede emitir su aprobación independiente. Su reconciliación
(§8) es un emparejamiento mecánico y auditable, no un voto, y el veredicto
compuesto (§10) se deriva por tabla, no por criterio suyo. Claude Code nunca
sube ni baja el veredicto de un juez.

## 4. Declaración de activación

Antes de lanzar, se registra el bloque que exige el §13 del flujo v2:

```text
JUICIO CRUZADO — ACTIVACIÓN
RIESGO PROTEGIDO:
UNIDAD ALCANZADA:
CONTROL ADICIONAL: dos jueces Codex ciegos y simultáneos
MODELOS: M1 = ... | M2 = ...
PRESUPUESTO / ESPERA MÁXIMA:
CRITERIO DE SALIDA:
```

`CRITERIO DE SALIDA` nombra qué termina la excepción: normalmente "cierre de
esta unidad". Sin este bloque no hay juicio cruzado; hay revisión simple.

## 5. Congelamiento de la unidad exacta

Rige el mismo criterio que el resto del proyecto: se juzga la unidad exacta
—diff o rango de commits—, no la conversación (`AGENTS.md` §4, flujo v2 §5).

1. Git es la identidad por defecto (`AGENTS.md` §8). Si el árbol está sucio,
   los cambios se consolidan en un commit de trabajo en la rama vigente antes
   de lanzar. No se usan ZIP, hashes ni manifiestos: no hay un riesgo de
   identidad que Git no resuelva.
2. Se registra `BASE..HEAD`, la rama, la lista de archivos y el resultado de
   `git status --porcelain`. Un estado sucio previo se distingue de los
   cambios de la sesión (`AGENTS.md` §12).
3. **Congelamiento de escritura:** entre el lanzamiento del primer juez y la
   recepción de ambos veredictos, Claude Code no edita ningún archivo del
   repositorio ni ejecuta nada que lo modifique. Si la unidad cambia, la
   corrida queda anulada y se relanza desde cero: una revisión no cubre una
   unidad posterior a ella (`AGENTS.md` §4).

Si Gato prohíbe el commit de trabajo, se admite congelar el árbol de trabajo
tal cual, declarándolo en el registro; el congelamiento de escritura pasa a
ser la única garantía de identidad y debe respetarse sin excepción.

## 6. Lanzamiento de los dos jueces

Ambas invocaciones se emiten **en el mismo mensaje**, como dos tool calls
simultáneas, con el mismo prompt carácter por carácter y distinto `model`.

Reglas de ceguera e independencia:

1. Dos sesiones nuevas. Está prohibido usar `mcp__codex__codex-reply` para el
   segundo juez: compartiría contexto y anularía la independencia.
2. Ningún prompt menciona la existencia del otro juez, ni cita su salida, ni
   se lanza el segundo después de leer al primero.
3. El prompt no incluye la autoevaluación de Claude Code ni el relato de cómo
   se llegó a la solución: sólo unidad, aceptación y criterios. Contar la
   defensa del autor contamina al revisor.
4. `sandbox: read-only` y `approval-policy: never` no son preferencias: son la
   garantía mecánica de que el revisor no modifica lo que revisa (flujo v2 §5).
5. M1 y M2 son identificadores de modelo distintos, fijados por Gato en el §4.
   Por defecto, dos variantes de razonamiento distintas del modelo disponible
   en `mcp__codex__codex` (parámetro `model` del tool).

Prompt congelado (idéntico para ambos jueces, salvo el `model`):

```text
Sos el revisor independiente de esta unidad. Modo read-only: no modifiques
ningún archivo.

UNIDAD EXACTA: <rama> <BASE>..<HEAD>
ARCHIVOS: <lista>
COMANDO PARA VERLA: git diff <BASE>..<HEAD>

CRITERIOS DE ACEPTACIÓN:
<criterios literales del ciclo>

PRUEBAS DECLARADAS:
<comandos y resultados declarados>

Revisá la unidad exacta y la aceptación, no la conversación ni la historia
previa del repositorio.

Para cada hallazgo indicá archivo y línea, el mecanismo concreto del defecto
y su severidad en el vocabulario del proyecto: BLOCKER, MAJOR, MINOR, NOTE.
Si no podés verificar una afirmación con el código a la vista, decilo en vez
de asumirla.

Respondé exactamente con esta plantilla y nada más:

VEREDICTO: APROBAR | APROBAR_CON_CAMBIOS | BLOQUEAR
UNIDAD REVISADA:
ACEPTACIÓN VERIFICADA:
PRUEBAS VERIFICADAS:
HALLAZGOS MATERIALES:
OBSERVACIONES NO BLOQUEANTES:
ESTADO PARA CLAUDE:
```

Invocación (`mcp__codex__codex`, una por juez, mismo mensaje):

```text
prompt:           <el prompt de arriba, congelado>
cwd:              <raíz del repositorio>
sandbox:          read-only
approval-policy:  never
model:            M1        # Juez A — M2 para el Juez B
```

## 7. Salida de cada juez

Cada juez devuelve la plantilla del §5 del flujo v2, sin modificación:

```text
VEREDICTO: APROBAR | APROBAR_CON_CAMBIOS | BLOQUEAR
UNIDAD REVISADA:
ACEPTACIÓN VERIFICADA:
PRUEBAS VERIFICADAS:
HALLAZGOS MATERIALES:
OBSERVACIONES NO BLOQUEANTES:
ESTADO PARA CLAUDE:
```

No hay formato nuevo, ni JSON, ni puntajes, ni veredictos en inglés. Las dos
salidas se transcriben literalmente al registro (§14). Claude Code no las
resume, no las reescribe y no completa lo que un juez dejó vacío. Una salida
que no respeta la plantilla se trata como invocación fallida (§12), no se
"arregla".

## 8. Reconciliación de hallazgos

Claude Code empareja los hallazgos de A y B. Dos hallazgos son **el mismo**
sólo si coinciden en ubicación —mismo archivo y mismo símbolo, o rangos de
línea solapados— **y** en el mecanismo del defecto. La redacción distinta no
importa; el mecanismo distinto sí: dos defectos distintos en la misma función
son dos hallazgos, no uno corroborado.

| Estado | Criterio | Tratamiento |
|---|---|---|
| `CONFIRMADO` | Ambos jueces, misma ubicación y mismo mecanismo. | Verificación prioritaria (§9). |
| `SOSPECHA` | Un solo juez. | Se registra. No dispara reparación automática. Se verifica igual. |
| `CONTRADICCIÓN` | Los jueces afirman lo opuesto sobre el mismo punto. | No la resuelve Claude Code: va a Gato (§10). |

El emparejamiento se registra citando textualmente las dos formulaciones, para
que un humano pueda auditar si la equivalencia declarada es real.

Asimetría deliberada por severidad: un `BLOCKER` de un solo juez es
`SOSPECHA` a efectos de corroboración, pero arrastra el veredicto compuesto a
`BLOQUEAR` (§10). Nunca se descarta por falta de acuerdo. Un defecto de
seguridad, de datos o de frontera F1–F5 no deja de existir porque el segundo
juez no lo haya mirado.

## 9. La corroboración no reemplaza la verificación

**Ningún hallazgo se aplica a ciegas, ni siquiera un `CONFIRMADO` por ambos
jueces.** Antes de tocar una línea, Claude Code verifica el hallazgo contra el
código real y registra la evidencia. El acuerdo de dos jueces baja el listón
de sospecha y ordena la prioridad; no sustituye la evidencia.

Es una divergencia consciente respecto del protocolo externo que inspira este
documento, que trata el acuerdo de dos revisores como corroboración suficiente
por sí sola. Dos modelos del mismo proveedor comparten sesgos: pueden coincidir
en un error. El precedente del proyecto es el contrario y se conserva
(`docs/historico/sesiones/43-reporte.md`: hallazgos de auditoría aceptados y
rechazados, cada uno con evidencia propia).

Tras la verificación, cada hallazgo queda en uno de tres estados:

| Estado | Criterio | Consecuencia |
|---|---|---|
| `VERIFICADO` | La evidencia propia lo sostiene. | Entra a la reparación única si es `MAJOR`. |
| `REFUTADO` | La evidencia propia lo desmiente. | Se registra con la evidencia. No se toca el código. |
| `NO_DECIDIBLE` | La evidencia disponible no alcanza. | `MAJOR`/`BLOCKER` → Gato. `MINOR`/`NOTE` → deuda registrada. |

Un `SOSPECHA` que la verificación sostiene pasa a `VERIFICADO` y pesa igual
que un `CONFIRMADO`: la corroboración prioriza, la evidencia decide.

Refutar un hallazgo no cambia el veredicto compuesto. Claude Code no se
aprueba a sí mismo (`AGENTS.md` §4): entrega el veredicto compuesto junto con
las refutaciones y su evidencia, y el cierre lo decide quien ya lo decide hoy
(flujo v2 §6, o Gato ante `BLOQUEAR`).

## 10. Veredicto compuesto

Se deriva por tabla, tomando la severidad mayor de los dos jueces:

| Juez A \\ Juez B | `APROBAR` | `APROBAR_CON_CAMBIOS` | `BLOQUEAR` |
|---|---|---|---|
| `APROBAR` | `APROBAR` | `APROBAR_CON_CAMBIOS` | `BLOQUEAR` + `DIVERGENCIA_MAXIMA` |
| `APROBAR_CON_CAMBIOS` | `APROBAR_CON_CAMBIOS` | `APROBAR_CON_CAMBIOS` | `BLOQUEAR` |
| `BLOQUEAR` | `BLOQUEAR` + `DIVERGENCIA_MAXIMA` | `BLOQUEAR` | `BLOQUEAR` |

El vocabulario es el de `AGENTS.md` §10. No existen `APPROVED`, `ESCALATED`
ni ningún estado importado.

Máxima severidad, y no "acuerdo necesario para actuar", es deliberado: si un
solo juez ve un `MAJOR` y el veredicto compuesto fuera `APROBAR`, el juicio
doble sería más permisivo que la revisión ordinaria de un solo Codex (flujo
v2 §§5-7), donde ese mismo `MAJOR` habría disparado la reparación única
(§7). Un control adicional no puede debilitar el control que reemplaza.

Escalan a Gato, además de todo `BLOQUEAR`:

- `DIVERGENCIA_MAXIMA`: un juez aprueba y el otro bloquea la misma unidad.
- Toda `CONTRADICCIÓN` del §8, cualquiera sea el veredicto compuesto.
- Todo `NO_DECIDIBLE` de severidad `MAJOR` o `BLOCKER`.

La escalada entrega las dos salidas literales y la evidencia propia. Claude
Code no propone cuál juez tiene razón.

## 11. Una sola reparación y re-juicio acotado

Rige sin cambios el tope de `AGENTS.md` §9 y del flujo v2 §7: **una sola
reparación acotada**. Este protocolo no compra una ronda extra por tener dos
jueces.

```text
Veredicto compuesto APROBAR_CON_CAMBIOS
→ Claude Code verifica cada MAJOR contra el código (§9)
→ Claude confirma que la reparación cabe en el objetivo
→ Claude Code repara sólo los MAJOR en estado VERIFICADO
→ Re-juicio acotado sobre el delta
```

`NOTE` y `MINOR` no abren reparación. `REFUTADO` no se repara. `BLOQUEAR` no
va a reparación: va a Gato.

El re-juicio recibe **sólo el delta de la corrección**, no la unidad completa:
dos invocaciones nuevas de `mcp__codex__codex` en paralelo, mismos M1 y M2,
mismo sandbox y política, con un prompt que contiene el delta exacto
(`git diff <HEAD_juicio>..<HEAD_reparación>`), la lista de `MAJOR` que el
delta pretende cerrar, los criterios de aceptación originales, y la
instrucción explícita de juzgar sólo si el delta cierra esos `MAJOR` y si
introduce defectos nuevos dentro del delta — sin volver a revisar la base.

El re-juicio usa la misma plantilla, la misma reconciliación y la misma tabla
de composición. Si el veredicto compuesto del re-juicio no es `APROBAR`
—persiste un `MAJOR`, aparece un `BLOCKER` o cambia el scope— el resultado es
`BLOQUEAR` y decide Gato. No hay segunda reparación ni se reinicia el ciclo
(`AGENTS.md` §9, flujo v2 §7).

Gato puede autorizar, en el §4, que el re-juicio corra con un solo juez para
una unidad `R1` de riesgo alto, por costo. Si lo hace, el re-juicio queda
anotado como juicio simple y sus hallazgos no pueden alcanzar `CONFIRMADO`.

## 12. Fallo de una invocación

Un juez falla si la invocación devuelve error, agota la espera declarada en el
§4, o devuelve una salida que no respeta la plantilla del §7.

1. **Un reintento**, con el mismo prompt y el mismo modelo. Ninguno más.
2. Si tras el reintento siguen respondiendo los dos, el juicio continúa
   normalmente.
3. Si un juez sigue fallando, el protocolo **no espera** y **no degrada en
   silencio**. Se elige explícitamente, y la elección es de Gato:

| Salida | Qué queda registrado |
|---|---|
| Degradar a juez único | Veredicto anotado `JUICIO_SIMPLE_POR_FALLO_DE_JUEZ: <A\|B>`. Ningún hallazgo puede ser `CONFIRMADO`: un solo juez no corrobora. Todos son `SOSPECHA` y se verifican igual (§9). |
| Volver al §5 ordinario | La corrida se cierra sin veredicto de juicio cruzado; vale como la revisión simple que institucionalmente ya alcanza. |
| Abortar | `OBJETIVO_ABORTADO_POR_PRESUPUESTO` si el motivo es presupuesto agotado. |

Si fallan los dos jueces, no hay revisión: la unidad queda sin veredicto y el
ciclo se detiene hasta que Gato decida. Una corrida degradada nunca se
registra como juicio cruzado completo.

## 13. Lo que este protocolo no garantiza

- Los dos jueces son del mismo proveedor. La independencia es de modelo, no de
  proveedor: pueden compartir puntos ciegos y coincidir en un error. Por eso
  el §9 es obligatorio.
- Ambos leen el mismo repositorio y el mismo `AGENTS.md`, así que comparten
  las mismas premisas institucionales. El acuerdo sobre una premisa equivocada
  no la valida.
- Dos jueces no reemplazan al verificador mecánico. Tests, `ruff` y `mypy` del
  DoD de `CLAUDE.md` se corren igual, antes y después de la reparación.
- Cuesta aproximadamente el doble que la revisión del §5, y hasta el cuádruple
  con re-juicio, sobre el 15 % que el flujo v2 §9 asigna a Codex. Si eso supera
  el costo de ejecutar la unidad, no se activa: se reduce el control o se
  abandona (flujo v2 §9).

## 14. Registro

Una corrida se documenta en el reporte de sesión de `docs/historico/sesiones/`,
igual que las auditorías de Codex hoy (precedente: sesión 43). El reporte
incluye el bloque de activación (§4), la unidad congelada, los dos modelos, las
dos salidas literales, la tabla de reconciliación con las citas emparejadas, la
evidencia propia de cada hallazgo verificado o refutado, el veredicto compuesto
y el resultado del re-juicio si lo hubo.

Si las salidas literales son largas, van a `docs/historico/auditorias/` como
artefacto propio y el reporte de sesión las referencia por ruta. No se
reempaquetan (`AGENTS.md` §13).

`docs/BACKLOG.md` **no** registra corridas. `SOSPECHA`/`CONFIRMADO`/
`VERIFICADO`/`REFUTADO` son vocabulario de ESTE documento, no de
`docs/BACKLOG.md`. Lo único que se traslada ahí, si sobrevive al cierre y
sigue siendo trabajo pendiente (una sospecha no decidida, un `MINOR` que
aporta valor, una deuda declarada), se agrega con el formato que la regla
de mantenimiento real de `docs/BACKLOG.md` exige: origen y sesión, como una
entrada nueva — no como una corrida de juicio cruzado.

## 15. Prohibiciones

1. No autoriza commit, push, PR ni merge. Rige la política ordinaria:
   `AGENTS.md` §3 y el DoD 6 de `CLAUDE.md` — commit convencional en rama de
   trabajo, nunca push; el humano revisa y publica. Un `APROBAR` compuesto es
   un veredicto de revisión, no una autorización de entrega.
2. No hay tercer juez, ni subagente de Claude arbitrando entre A y B.
3. No se lanza el segundo juez después de leer al primero, ni con
   `codex-reply`.
4. No se edita nada entre el lanzamiento y la recepción de ambos veredictos.
5. No se reescribe, completa ni resume la salida de un juez.
6. No hay segunda reparación, ni tercera pasada de jueces.
7. Una aprobación no cubre una unidad que cambió después (`AGENTS.md` §4).
8. Haberlo corrido una vez no obliga ni habilita a correrlo por defecto
   (flujo v2 §13).

## 16. Handoff de cierre

Se usa el handoff mínimo de `AGENTS.md` §13, sin campos nuevos:

```text
CICLO / OBJETIVO:
ROL / PRODUCTOR: Claude Code (orquestador del juicio cruzado)
BASE + UNIDAD EXACTA:
RESULTADO:
EVIDENCIA / TESTS:
HALLAZGOS + VEREDICTO: veredicto compuesto + reconciliación (CONFIRMADO/SOSPECHA/CONTRADICCIÓN, §8) + verificación (VERIFICADO/REFUTADO/NO_DECIDIBLE, §9)
PENDIENTE + DESTINATARIO SIGUIENTE:
```

Los estados de cierre del ciclo son los de `AGENTS.md` §10. Este protocolo no
agrega ninguno.

## 17. Referencias

- Flujo operativo y §5/§7/§8/§13 invocados aquí:
  `docs/proceso/FLUJO-HIBRIDO-MULTIAGENTE-v2.md`.
- Roles, independencia, severidades y estados: `AGENTS.md`.
- DoD y política de publicación: `CLAUDE.md`.
- Precedente de auditoría Codex con verificación propia de hallazgos:
  `docs/historico/sesiones/43-reporte.md`.
