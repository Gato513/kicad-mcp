# Delegación a subagentes v1 — disciplina operativa del Escritor

**Autoridad:** Gato
**Alcance:** Claude Code en su rol de Escritor (`AGENTS.md` §2).
**Propósito:** usar subagentes sin que la delegación diluya la responsabilidad,
amplíe el alcance ni fabrique una independencia que no existe.

## 1. Naturaleza y subordinación

Un subagente **no es un rol** de `AGENTS.md` §2. Es una herramienta interna del
Escritor, del mismo orden que `grep`, `pytest` o un script. Todo lo que un
subagente produce lo firma Claude Code, y Claude Code responde por ello como si
lo hubiera escrito a mano.

Consecuencias que no son negociables:

1. Un subagente **no puede** actuar como Revisor independiente. Es parte del
   productor, y quien produce una unidad no emite su aprobación independiente
   (`AGENTS.md` §4). Ya está dicho para el caso concreto en
   `docs/proceso/JUICIO-CRUZADO-CODEX-v1.md` §3.
2. Delegar no abre un ciclo (flujo v2 §12, punto 1) ni genera un handoff
   (`AGENTS.md` §13). Un reporte de subagente es un artefacto temporal y no se
   revisa de forma recursiva (flujo v2 §12, punto 4).
3. Un subagente hereda el alcance del ciclo: F1–F5, G1–G5, el presupuesto y
   las condiciones de detención de `AGENTS.md` §11. No se delega para hacer lo
   que el ciclo no autoriza.
4. Preferencia por subagentes de sólo lectura. Un subagente con permiso de
   escritura está sujeto a las mismas fronteras y al mismo DoD que el Escritor.

Este documento no cambia el flujo v2 ni `AGENTS.md`. Ante conflicto, prevalecen
ellos.

## 2. Cuándo delegar y cuándo no

| Delegar | No delegar |
|---|---|
| Exploración de scope incierto: "¿dónde vive X?", "¿cuántos sitios hacen Y?". | Cambio trivial, o algo ya bien entendido: escribir el prompt cuesta más que hacerlo. |
| Barrido exhaustivo cuya salida bruta es ruido y cuyo valor es el resumen. | Una decisión que requiere autoridad humana (`AGENTS.md` §3). Una pregunta a Gato no se delega. |
| Segunda mirada de diseño sobre un plan ya escrito, con el plan adjunto. | El veredicto de un gate o de un test que es evidencia de DoD: se corre y se muestra la salida literal. |
| Research que llenaría el contexto principal con material que no se va a releer. | Lo que un `grep` responde en un comando. |

Criterio de corte: si el costo de escribir la instrucción más el costo de
verificar el resultado (§4) supera el de hacer la tarea directamente, no se
delega — mismo principio de proporcionalidad que `AGENTS.md` §11.

## 3. La instrucción es autocontenida

Un subagente arranca **sin memoria de la conversación**, salvo los tipos que
explícitamente la heredan. La instrucción tiene que sostenerse leída en frío
por alguien que nunca vio nada de esta sesión.

```text
CONTEXTO: qué es el proyecto, qué se está haciendo y por qué importa
TAREA: una sola pregunta o un solo entregable
ARCHIVOS DE PARTIDA: rutas absolutas, con sección o rango de líneas
QUE DEVOLVER: la forma exacta de la salida esperada
QUE NO HACER: sólo lectura / no tocar F1 / no proponer fixes / no ampliar el barrido
PRESUPUESTO: tiempo, cantidad de archivos, o condición de aborto
```

Instrucciones rotas, por definición: "hacé lo que ya hablamos", "seguí con lo
de antes", "revisá el archivo que vimos", un nombre de archivo sin ruta, una
sección citada sin número.

Si el prompt no se puede leer en frío, no está listo — el mismo corte que
D-30.1 aplica al prompt de una sesión: si no se pueden llenar los puntos, se
vuelve a diseñar en vez de lanzar.

Un subagente que devuelve algo distinto de lo que pide `QUE DEVOLVER` no se
"corrige" reinterpretando su salida: se relanza con la instrucción arreglada,
o se hace la tarea a mano.

## 4. El reporte del subagente es una afirmación, no un hecho

Antes de actuar sobre lo que trae un subagente, se verifica contra el
código o el documento real siempre que verificar sea barato. Es la misma regla
que el §9 de `JUICIO-CRUZADO-CODEX-v1.md` aplica a los jueces, y el principio
de refutación D-33.1 aplicado a una salida de agente.

| Se verifica siempre antes de actuar | Cómo |
|---|---|
| Una cita textual de un documento normativo. | Se abre el documento en la sección citada. |
| Un `archivo:línea`. | Se lee el archivo. |
| Un conteo ("hay 12 sitios"). | Se reproduce el barrido. |
| Una negativa ("no existe X", "no hay ningún caso"). | `grep` propio. "No encontré X" no es "X no existe". |
| "Corrí Y y dio Z". | La evidencia es la salida del comando, no la afirmación. |

Dos precedentes que sostienen la regla:

- Memoria `codex-review-verificar-hallazgos`: una misma revisión trajo un
  hallazgo sustantivo correcto y una afirmación fabricada dentro del mismo
  texto. Aceptar en bloque y descartar en bloque pierden información en
  direcciones opuestas.
- Práctica de esta misma sesión: antes de aceptar un diseño que un subagente
  anclaba en el §13 del flujo v2, se releyó el §13 directamente. La cita era
  correcta; el punto es que se confirmó antes de construir encima.

Un hallazgo que trae un subagente entra al criterio del §4 de
`docs/proceso/TRIAGE-SISTEMICO-DE-HALLAZGOS-v1.md` como cualquier otro: el
mecanismo que propone es hipótesis.

## 5. Paralelismo

En un mismo mensaje se lanzan sólo tareas **independientes entre sí**.

Test de independencia: si el prompt de B tendría que citar la salida de A,
no son independientes y no van en la misma tanda.

Prohibiciones concretas:

1. No se lanza en la misma tanda un subagente que depende del resultado de
   otro. Se espera y se lanza después, con el resultado ya verificado (§4).
2. No corren dos subagentes con permiso de escritura sobre el mismo scope al
   mismo tiempo: hay un solo escritor simultáneo por scope (`AGENTS.md` §4).
3. Duplicar la misma tarea en dos subagentes **no** es corroboración. Dos
   instancias del mismo modelo con el mismo prompt comparten sesgos y premisas
   (`JUICIO-CRUZADO-CODEX-v1.md` §13); su acuerdo no es evidencia y no produce
   ningún estado institucional.

## 6. Registro

No se registra cada delegación. Se registra, en una línea del reporte de sesión
de `docs/historico/sesiones/`:

- Qué delegación produjo evidencia que sostiene una decisión, y contra qué se
  verificó esa evidencia.
- Cualquier afirmación de subagente que se verificó y resultó falsa, con la
  refutación. Se documenta, no se omite en silencio — mismo criterio que la
  memoria `codex-review-verificar-hallazgos`.

No se abre artefacto propio para el reporte de un subagente ni se lo
reempaqueta (flujo v2 §11 y §12 punto 4, `AGENTS.md` §13).

## 7. Prohibiciones

1. Un subagente no revisa de forma independiente la unidad que Claude Code
   produjo, ni arbitra entre revisores.
2. No se delega una decisión reservada a Gato (`AGENTS.md` §3).
3. No se delega con una instrucción que dependa de la conversación previa.
4. No se actúa sobre una cita, un conteo o un `archivo:línea` de un subagente
   sin confirmarlo cuando confirmarlo es barato.
5. No se declara verde un test ni cumplido un gate por el reporte de un
   subagente: vale la salida literal del comando.
6. No se encadenan subagentes dependientes en la misma tanda paralela.
7. No se usa un subagente para ampliar de hecho el alcance del ciclo.

## 8. Referencias

- Roles, independencia, escritor único, autoridad reservada y handoff:
  `AGENTS.md` §§2, 3, 4, 11, 13.
- Anti-burocracia y artefactos temporales:
  `docs/proceso/FLUJO-HIBRIDO-MULTIAGENTE-v2.md` §§9, 11, 12.
- Verificación propia de hallazgos ajenos y límites de la corroboración:
  `docs/proceso/JUICIO-CRUZADO-CODEX-v1.md` §§9, 13.
- Triage de lo que un subagente reporta:
  `docs/proceso/TRIAGE-SISTEMICO-DE-HALLAZGOS-v1.md` §4.
- D-30.1 y D-33.1: `docs/DECISIONES.md`.
- Fronteras F1–F5 y DoD: `CLAUDE.md`.
