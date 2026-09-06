# Triage sistémico de hallazgos v1 — criterio de clasificación y de fix

**Autoridad:** Gato
**Propósito:** decidir, ante un hallazgo o un lote de hallazgos, qué clase de
cosa es cada uno, cuáles comparten causa raíz y qué fix corresponde — sin
crear estados, roles ni ciclos nuevos.

## 1. Naturaleza y subordinación

Esto es un criterio de decisión, no un protocolo. No agrega una etapa al flujo,
no convoca a ningún agente, no produce un artefacto propio y no abre un ciclo
(flujo v2 §12, punto 1: "no crear un ciclo por documento"). Se aplica dentro
del trabajo que el Escritor ya hace (`AGENTS.md` §6) y del cierre que Claude
Chat ya hace (flujo v2 §6).

Formaliza dos prácticas que el proyecto ya ejerce y que hoy viven dispersas:
el trigger de promoción por repetición de `docs/BACKLOG.md` y la auditoría de
sobre-ingeniería de la sesión 43. No inaugura ninguna de las dos.

Ante conflicto prevalecen `AGENTS.md` y el flujo v2. Este documento no
reinterpreta severidades, veredictos, estados de cierre, F1–F5 ni G1–G5: los
reusa.

## 2. Cuándo se aplica

| Situación | Aplica |
|---|---|
| Cerrar, promover, degradar o descartar un ítem de `docs/BACKLOG.md`. | Sí. |
| Recibir un lote de hallazgos de una revisión de Codex, de un juicio cruzado o de una auditoría. | Sí, antes de reparar. |
| Decidir la forma del fix de un bug con causa no trivial. | Sí. |
| Abrir un ítem nuevo desde una fricción de dogfooding o de Validation Suite. | Sí, al menos §3 y §4. |
| Hallazgo `NOTE`, corrección editorial, typo, fix de una línea con causa evidente. | No. |
| El fix ya está prescripto por un ADR vigente. | No; rige el ADR. |

El costo es leer una lista, no producir un documento. Si el triage en sí
mismo cuesta más que el fix, se hace el fix directamente — mismo principio
de proporcionalidad de esfuerzo que `AGENTS.md` §11 ("arquitectura y
auditoría deben consumir claramente menos esfuerzo que la ejecución
prevista") y flujo v2 §12, punto 10 ("no continuar una investigación que ya
agotó su presupuesto o valor").

## 3. Paso 1 — clase de causa raíz

Se clasifica por **causa raíz**, no por síntoma.

| Clase | Criterio | Tratamiento |
|---|---|---|
| `YA_RESUELTO` | Un cambio posterior lo superó. | Se verifica contra el código actual y se cierra sin fix, con la evidencia. |
| `DUPLICADO` | Misma causa raíz que un ítem ya registrado. | Se fusiona bajo el ítem más antiguo; no se abre entrada nueva. |
| `CLUSTER` | N hallazgos comparten una causa raíz. | **Un solo fix.** Un ítem con N instancias listadas, no N ítems. |
| `AISLADO` | Causa raíz propia, sin otros hallazgos que la compartan. | Fix localizado, según §5 y §6. |
| `CAPACIDAD_FALTANTE` | No es un defecto: es una función que nunca existió. | No entra por la puerta de "bug". Va a `docs/BACKLOG.md` con su prioridad; nunca a la reparación acotada de un `MAJOR` (`AGENTS.md` §9). |
| `SIN_CLASIFICAR` | Todavía no hay evidencia para clasificar. | Estado válido y temporal. Se registra como tal; no se fuerza una clase para poder avanzar. |

Criterio de identidad para `CLUSTER` y `DUPLICADO`: rige el mismo del §8 de
`JUICIO-CRUZADO-CODEX-v1.md`. Dos hallazgos son el mismo sólo si coinciden en
ubicación **y** en mecanismo. La redacción distinta no importa; el mecanismo
distinto sí.

Un clúster propuesto antes de aislar la causa es una hipótesis de clúster, y
se trata como tal (§4). Precedente calibrado: F-D5-01 / F-V1c-01 /
F-V2-VIA-HUERFANA se agruparon por "síndrome de fondo" cuando la propia
entrada del BACKLOG anotaba que la instancia 3 era a nivel de pad y la
instancia 2 a nivel de vía. La agrupación quedó confirmada recién en la
sesión 32c, cuando la investigación aisló un mecanismo común
(D-32c.2) — no antes.

Contraste explícito: N hallazgos con el mismo síntoma y mecanismos distintos
son N hallazgos `AISLADO`, no un clúster.

Señal de clasificación mal hecha: se declaró `CLUSTER` y el plan de fix tiene
un fix por hallazgo. O la clase está mal, o el fix ataca síntomas.

## 4. Paso 2 — el mecanismo es una hipótesis; el síntoma es la evidencia

| Es evidencia | Es hipótesis |
|---|---|
| El síntoma observado y reproducible. | La causa raíz propuesta. |
| La salida literal de un comando o de un test. | El `archivo:línea` que un revisor señala. |
| Un log, un conteo medido, un DRC. | La explicación de por qué ocurre. |
| Un experimento causal (borrar X y observar el cambio). | La afirmación "esto lo arregla". |

Antes de aceptar un mecanismo se responde la pregunta de D-33.1: **¿qué
resultado demostraría que esto es falso?** Si no hay respuesta, el hallazgo es
`SIN_CLASIFICAR`, no `CLUSTER`.

Esto vale para cualquier origen: Codex, un juicio cruzado, un subagente,
ChatGPT, el humano o Claude Code. Un revisor puede acertar en lo sustantivo y
fabricar una afirmación falsa dentro del mismo texto (memoria
`codex-review-verificar-hallazgos`; sesión 43, tres hallazgos aplicados y
tres rechazados con razón explícita).

Se reusan, sin definir vocabulario nuevo, los tres estados del §9 de
`JUICIO-CRUZADO-CODEX-v1.md`:

| Estado | Consecuencia acá |
|---|---|
| `VERIFICADO` | Habilita elegir fix (§5, §6). |
| `REFUTADO` | Se cierra con la evidencia de la refutación. No se toca el código. |
| `NO_DECIDIBLE` | `MAJOR`/`BLOCKER` → Gato. `MINOR`/`NOTE` → deuda registrada. |

Refutar bien es un resultado, no un fracaso (D-32c.1: el objetivo de una
investigación es reducir incertidumbre, no producir un fix).

## 5. Paso 3 — test de sobre-ingeniería del fix propuesto

Se aplica al fix, no al hallazgo. Cuatro preguntas:

| Pregunta | Si la respuesta es sí |
|---|---|
| ¿Agrega un estado nuevo que el sistema debe mantener coherente? | Rediseñar. Cada estado nuevo es una combinación nueva que hay que probar. |
| ¿Agrega un verbo, un flag o un parámetro nuevo a una superficie existente? | Rediseñar. Un flag nuevo es una rama nueva que alguien tiene que elegir bien. |
| ¿Agrega un gate o una guarda de admisión nueva? | Rediseñar. Además, los gates G1–G5 son F2: no se tocan sin aprobación humana (`CLAUDE.md`). |
| ¿Crea una representación paralela de algo que el sistema ya representa? | Rediseñar. Dos representaciones del mismo hecho divergen. |

Ejemplo real de representación paralela, ya registrado como deuda en
`docs/BACKLOG.md`: `POST_ROUTE_PERSIST_FAILED`, `POST_ZONE_PERSIST_FAILED` y
`POST_ROUTE_REFILL_SKIPPED`. Cada adición fue localmente razonable — la
segunda se documenta explícitamente como "decisión conservadora" de la sesión
27 — y el agregado es hoy una deuda de unificación. Un código de error nuevo
es un estado nuevo en la superficie F3, no una línea más.

Regla de orientación, no prohibición: **el fix correcto casi siempre borra
código**. Si el diff del fix es sólo adiciones, no está prohibido, pero el
reporte de la sesión dice en una línea por qué no había nada que borrar.

Precedentes del proyecto en ambas direcciones:

- Sesión 43: se eliminó una rama defensiva inalcanzable junto con su test, y
  se recortaron docstrings desproporcionados; se rechazó con razón explícita
  la recomendación de fusionar dos campos con disponibilidad y longitud
  distintas. No todo hallazgo de una auditoría de sobre-ingeniería se aplica.
- Sesión 39: `@mutating_tool` colapsó el preámbulo de 12 tools, `tools/pcb.py`
  3507 → 3419 líneas, sin cambio observable de contrato — y excluyó tres
  casos con justificación registrada en ADR-0014.

## 6. Paso 4 — ranking de fixes candidatos

Se ordenan por lo que **eliminan**, no por lo que agregan:

| Nivel | Fix | Cuándo |
|---|---|---|
| 1 | Borrar el mecanismo problemático. | El comportamiento no tiene consumidor real verificado. Es el fix preferido. |
| 2 | Guarda estática o ratchet. | El mecanismo debe existir, pero se puede volver imposible reintroducir el defecto. Ejemplo: los canarios de registro contra `tools/pcb.py` real en `tests/test_mutating_tool.py` (sesión 39). |
| 3 | Fix localizado dentro de la superficie existente. | El defecto es local y la superficie no cambia. |
| 4 | Superficie nueva: código de error, flag, campo, tool, estado. | Última opción. Arrastra el DoD 3 y 4 de `CLAUDE.md` (catálogo en el mismo commit, ADR si introduce contrato). |

No se elige el nivel 4 sin dejar escrito por qué fallan 1, 2 y 3. Un nivel 4
elegido por comodidad es exactamente lo que el §5 busca frenar.

## 7. Dead-ends: severidad máxima, no mínima

Un hallazgo sin salida real — "esto no se arregla sin rehacer X", "el usuario
llega a un estado del que no puede salir" — es `BLOCKER` y decide Gato
(`AGENTS.md` §9). No es `NOTE` por el hecho de que hoy no haya nada que
construir.

El fix de un dead-end es **un mensaje de salida ejecutable**, no maquinaria
nueva para evitar el estado: el error tipado `{code, message, hint}` de la
regla 1 de `CLAUDE.md`, con un `hint` que diga qué hacer a continuación.
Construir infraestructura para que el estado sea inalcanzable es, casi
siempre, un nivel 4 del §6 disfrazado de necesidad.

Precedente del patrón: F-V3-ROUTER-TIMEOUT-HARD en `docs/BACKLOG.md` — bug
upstream de Freerouting 2.1.0, fuera del control del proyecto. La decisión
registrada fue documentarlo como límite conocido del flujo automatizado, no
"arreglarlo" desde `kicad-mcp`.

Un dead-end **declarado** no es un dead-end **demostrado**. La afirmación "no
se puede sin rehacer X" es un mecanismo propuesto y pasa por el §4 como
cualquier otro.

## 8. Tests en verde con comportamiento roto

La combinación "suite verde + comportamiento roto en producción o en
dogfooding" no se explica primero por mala suerte de cobertura. Se sospecha
que un test fue enseñado a estar de acuerdo: ajustado para pasar en vez de
para detectar.

Tres preguntas sobre el test que cubre la zona del defecto:

1. ¿Qué comportamiento observable fallaría si este test se rompiera? Si la
   respuesta es "ninguno", el test consagra una implementación, no un
   contrato.
2. ¿Se editó este test en el mismo commit que introdujo el código que ahora
   falla? `git log -p` sobre el archivo de test lo responde.
3. ¿El test ejercita el camino real o un doble que replica la suposición
   equivocada?

Reglas ya vigentes que este documento no reemplaza y sólo invoca:

- F1 (`CLAUDE.md`): un golden que falla **no** se arregla editando el golden.
- `CLAUDE.md` §Flujo de trabajo: si un test `integration` falla y KiCad no
  está corriendo, ese es el motivo — no se "arregla" mockeando el bridge.

Si el fix incluye editar un test existente, el reporte de la sesión dice qué
comportamiento cubría antes ese test y por qué esa cobertura ya no aplica.
Precedentes de la forma correcta: sesión 39 declaró el baseline de tests
intacto sin modificar un solo test existente; sesión 43 eliminó un test
junto con la rama inalcanzable que era su único objeto, y lo dejó escrito
con el conteo antes y después.

## 9. Efecto sobre `docs/BACKLOG.md`

`docs/BACKLOG.md` ya tiene su propia regla de mantenimiento y su propio
trigger de promoción por repetición. Este documento no los cambia; los precisa
en tres puntos.

| Ya vigente en el BACKLOG | Precisión que agrega este criterio |
|---|---|
| Un candidato repetido se promueve con evidencia; el trigger se declara al abrir el ítem. | La instancia N+1 sólo cuenta si comparte **causa raíz** (§3), no sólo síntoma. Si el mecanismo difiere y todavía no hay causa común aislada, se anota como hipótesis de clúster, no como instancia cumplida. |
| Un candidato refutado se cierra con evidencia, sin fix. | El cierre declara qué evidencia lo reabriría — es la línea "sin trigger de reapertura" que ya usan F-D5-01 y F-D6-01. |
| Al cerrar un ítem se lo mueve a una nota de una línea en el reporte de la sesión que lo cerró. | Sin cambios. Un `CLUSTER` cerrado es **una** nota, no N. |

El mismo trigger explícito de F-D5-01 sirvió en las dos direcciones: cerró el
ítem en sesión 29 al quedar en 1/3, y sostuvo la promoción a P1 investigación
cuando se confirmó la 3ª instancia. Ese es el comportamiento buscado; no hace
falta inventar un mecanismo nuevo.

Un `CAPACIDAD_FALTANTE` entra al BACKLOG con prioridad propia y nunca por la
vía de la reparación acotada de un `MAJOR`.

## 10. Registro

No se registra el triage de cada hallazgo. Se registra el de los hallazgos
cuya clasificación decidió algo no obvio: un cierre sin fix, una promoción, la
fusión de N ítems en uno, o la elección de un fix de nivel 4.

Va en el reporte de sesión de `docs/historico/sesiones/`, igual que las
auditorías de Codex hoy. No abre artefacto nuevo (flujo v2 §12, puntos 1 y 4:
"no crear un ciclo por documento" / "no revisar artefactos temporales de
forma recursiva").

```text
TRIAGE — <ID del hallazgo>
SINTOMA OBSERVADO (evidencia):
MECANISMO PROPUESTO (hipótesis) + ORIGEN:
REFUTACION INTENTADA (D-33.1):
ESTADO: VERIFICADO | REFUTADO | NO_DECIDIBLE
CLASE: YA_RESUELTO | DUPLICADO | CLUSTER | AISLADO | CAPACIDAD_FALTANTE | SIN_CLASIFICAR
CLUSTER CON:
TEST DE SOBRE-INGENIERIA: estado / verbo o flag / gate / representación paralela
NIVEL DE FIX: 1 borrar | 2 ratchet | 3 localizado | 4 superficie nueva
POR QUE NO EL NIVEL ANTERIOR:
SEVERIDAD: BLOCKER | MAJOR | MINOR | NOTE
DESTINO: fix en este ciclo | BACKLOG (prioridad) | cerrado con evidencia | Gato
```

Los campos que no se decidieron se dejan vacíos. No se completan por simetría.

## 11. Lo que este criterio no garantiza

- Las clases del §3 son ortogonales a las severidades de `AGENTS.md` §9. No
  las reemplazan ni las derivan: un `CLUSTER` puede ser `MINOR` y un `AISLADO`
  puede ser `BLOCKER`.
- La clase asignada es ella misma una afirmación. Clasificar mal un hallazgo
  como `DUPLICADO` lo entierra. Ante duda, `SIN_CLASIFICAR`.
- No autoriza a cerrar nada. El cierre lo decide quien ya lo decide hoy
  (flujo v2 §6; Gato ante `BLOCKER`, `AGENTS.md` §3).
- El test de sobre-ingeniería es un criterio de diseño, no un gate mecánico.
  No hay verificador que lo compruebe, y el verificador mecánico no decide
  adecuación semántica (`AGENTS.md` §2).
- Divergencia deliberada respecto de la herramienta externa que inspira este
  documento: allí el triage produce un vocabulario propio de estados y una
  fase separada. Acá no hay fase, no hay artefacto y no hay vocabulario nuevo
  de severidad ni de veredicto. Lo único nuevo son las seis clases del §3, y
  existen porque el proyecto no tenía forma de decir "estos cuatro son uno".

## 12. Prohibiciones

1. No se declara `CLUSTER` sin causa raíz común verificada o sin marcarlo como
   hipótesis de clúster.
2. No se acepta un mecanismo propuesto sin intentar refutarlo (§4, D-33.1).
3. No se cierra un hallazgo como `YA_RESUELTO` sin verificar contra el código
   actual.
4. No se elige un fix de nivel 4 sin dejar escrito por qué fallan 1, 2 y 3.
5. No se edita un golden ni un test para que un fix pase (F1, §8).
6. No se convierte una `CAPACIDAD_FALTANTE` en reparación de un `MAJOR`.
7. No se degrada un dead-end a `NOTE` porque hoy no haya nada que construir.
8. Este criterio no abre un ciclo, no convoca a un agente y no crea un
   artefacto propio.

## 13. Referencias

- Severidades, estados de cierre y autoridad: `AGENTS.md` §§3, 9, 10.
- Flujo operativo, cierre y presupuesto:
  `docs/proceso/FLUJO-HIBRIDO-MULTIAGENTE-v2.md` §§6, 7, 9, 12.
- Identidad de hallazgos y estados de verificación:
  `docs/proceso/JUICIO-CRUZADO-CODEX-v1.md` §§8, 9.
- Fronteras F1–F5, regla del error tipado y DoD: `CLAUDE.md`.
- Trigger de promoción, cierres por refutación y regla de mantenimiento:
  `docs/BACKLOG.md`.
- D-30.1 (hipótesis y evidencia de refutación), D-32c.1 (una investigación
  reduce incertidumbre), D-33.1 (principio de refutación): `docs/DECISIONES.md`.
- Auditoría de sobre-ingeniería con hallazgos aplicados y rechazados:
  `docs/historico/sesiones/43-reporte.md`.
- Fix que borra superficie, con exclusiones justificadas:
  `docs/historico/sesiones/39-reporte.md` y `docs/adr/0014-mutating-tool-decorator.md`.
