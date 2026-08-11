# Flujo híbrido multiagente v2 — protocolo operativo

**Autoridad:** Gato
**Vigencia:** 2026-08-10
**Propósito:** producir resultados con dos controles independientes como
máximo: uno antes de ejecutar y otro sobre el resultado.

## 1. Fórmula

```text
Gato: objetivo
→ Claude Chat: propuesta completa
→ ChatGPT: auditoría previa única
→ Claude Code: investigación + implementación + pruebas
→ Codex: revisión posterior única
→ Claude Chat: cierre o siguiente objetivo
```

La repetición ocurre entre objetivos terminados, no dentro de cada artefacto.

## 2. Salida de Claude Chat

Claude entrega una orden de trabajo compacta:

```text
OBJETIVO Y VALOR:
EVIDENCIA / PREMISAS:
ALCANCE:
FUERA DE ALCANCE:
ESTRATEGIA:
RAMAS PREAUTORIZADAS:
ACEPTACIÓN:
PRUEBAS:
RIESGO: R0 | R1 | R2
PRESUPUESTO / ABORTO:
```

Si la solución depende de una investigación, Claude define por anticipado qué
hacer ante cada resultado cubierto. No crea una sesión de investigación y otra
de implementación cuando ambas pueden caber con seguridad en el mismo scope.

## 3. Salida de ChatGPT

ChatGPT interviene una vez:

```text
VEREDICTO PREVIO: EJECUTABLE | EJECUTABLE_CON_AJUSTES | BLOQUEADO

AJUSTES OBLIGATORIOS:
- ...

RECOMENDACIONES NO BLOQUEANTES:
- ...

ORDEN RECONCILIADA PARA CLAUDE CODE:
- objetivo, alcance, ramas, aceptación y verificaciones
```

Comprueba evidencia, coherencia, alcance, F1–F5, pruebas, presupuesto y ramas.
Corrige directamente lo deducible. No devuelve el plan a Claude para pulirlo.
Solo pregunta a Gato si una decisión cambia objetivo, alcance o autoridad.

Después de entregar la orden reconciliada, ChatGPT sale del ciclo.

## 4. Ejecución de Claude Code

Claude Code recibe juntos el plan original y la reconciliación. Dentro del
scope puede:

- inspeccionar el estado real;
- investigar hipótesis;
- elegir una rama preautorizada;
- resolver detalles tácticos;
- implementar código, tests y documentación;
- corregir fallos de sus propios tests;
- completar la unidad sin checkpoints intermedios.

Entrega:

```text
UNIDAD EXACTA:
RAMA ELEGIDA + EVIDENCIA:
CAMBIOS:
PRUEBAS:
DESVIACIONES:
HALLAZGOS FUERA DE ALCANCE:
ESTADO: COMPLETO | PARCIAL | BLOQUEADO
```

Solo se detiene ante cambio material, F1–F5, acción reservada, evidencia no
cubierta, imposibilidad o presupuesto agotado.

## 5. Revisión de Codex

Codex revisa la unidad exacta y la aceptación, no toda la conversación:

```text
VEREDICTO: APROBAR | APROBAR_CON_CAMBIOS | BLOQUEAR
UNIDAD REVISADA:
ACEPTACIÓN VERIFICADA:
PRUEBAS VERIFICADAS:
HALLAZGOS MATERIALES:
OBSERVACIONES NO BLOQUEANTES:
ESTADO PARA CLAUDE:
```

Codex no modifica la unidad mientras la revisa. Envía el estado a Claude Chat.
ChatGPT no vuelve a reconciliar ese mismo ciclo.

## 6. Continuidad de Claude Chat

Con la revisión, Claude:

- cierra el objetivo aprobado;
- incorpora deuda no bloqueante solo si aporta valor;
- ordena una reparación acotada ante `MAJOR`;
- propone el siguiente objetivo;
- recomienda abandonar si el retorno ya no justifica el costo.

No reabre por preferencias de estilo ni por buscar perfección después de que
los criterios se cumplieron.

## 7. Una sola reparación

`NOTE` y `MINOR` no generan reparación automática. Un `MAJOR` permite una sola
reparación del delta:

```text
Codex informa MAJOR
→ Claude confirma que cabe en el objetivo
→ Claude Code repara solo el delta
→ Codex revisa el delta y su efecto
```

Si persiste un `MAJOR`, aparece un `BLOCKER` o cambia el scope, Gato decide. No
se reinicia el ciclo completo ni se repite la auditoría previa.

## 8. Riesgo proporcional

| Riesgo | Trabajo | Preparación | Control |
|---|---|---|---|
| `R0` | read-only, análisis o artefacto temporal | tarjeta breve | revisión por muestreo si la decisión lo merece |
| `R1` | cambio ordinario de código o docs | orden compacta | diff/commit + tests relevantes |
| `R2` | F1–F5, API, seguridad, datos, release, destrucción | contrato acotado | revisión exhaustiva y gates completos |

- Git identifica por defecto la unidad `R1`/`R2`.
- ZIP, hash, manifiesto y custodia requieren un riesgo de identidad concreto.
- Un artefacto temporal no se convierte en unidad normativa por haber sido
  producido por un agente.
- Un contrato `R2` no duplica specs ni prescribe cada comando.

## 9. Presupuesto

Distribución orientativa:

| Etapa | Objetivo |
|---|---:|
| Claude Chat | 15 % |
| ChatGPT | 10 % |
| Claude Code | 60 % |
| Codex | 15 % |

Si arquitectura + auditoría cuestan más que la ejecución prevista, se reduce el
control o se abandona la unidad. Un resultado inconcluso no amplía el
presupuesto automáticamente.

## 10. Estados finales

```text
OBJETIVO_CUMPLIDO
OBJETIVO_CUMPLIDO_CON_DEUDA_NO_BLOQUEANTE
OBJETIVO_NO_CUMPLIDO_POR_EVIDENCIA
OBJETIVO_BLOQUEADO_POR_DECISION_HUMANA
OBJETIVO_ABORTADO_POR_PRESUPUESTO
```

## 11. Handoff común

```text
CICLO / OBJETIVO:
ROL / PRODUCTOR:
BASE + UNIDAD:
RESULTADO:
EVIDENCIA / TESTS:
HALLAZGOS + VEREDICTO:
PENDIENTE + DESTINATARIO:
```

No se trasladan conversaciones completas ni se reempaqueta evidencia ya
aceptada.

## 12. Prohibiciones anti-burocracia

1. No crear un ciclo por documento.
2. No encadenar Claude ↔ ChatGPT sobre la misma propuesta.
3. No pedir microautorizaciones dentro del scope.
4. No revisar artefactos temporales de forma recursiva.
5. No convertir recomendaciones en requisitos sin declararlo.
6. No abrir rondas por `NOTE` o `MINOR`.
7. No superar una reparación automática.
8. No usar empaquetado criptográfico cuando Git o una ruta inequívoca bastan.
9. No exigir ausencia absoluta de observaciones para cerrar un objetivo.
10. No continuar una investigación que ya agotó su presupuesto o valor.

## 13. Excepciones

Se permite más control únicamente si Gato lo autoriza por un riesgo concreto.
La excepción debe nombrar:

- riesgo protegido;
- control adicional;
- duración o unidad a la que aplica;
- criterio de salida.

La excepción no se vuelve precedente automático.

## 14. Evaluación del piloto v2

Tras tres objetivos reales, medir:

- resultados útiles por ciclo;
- paradas humanas;
- rondas por agente;
- tiempo de coordinación frente a ejecución;
- hallazgos materiales escapados;
- cumplimiento de F1–F5 y tests.

El protocolo funciona si un objetivo ordinario termina en un ciclo, cada agente
interviene una vez, hay como máximo una pregunta humana intermedia y la
coordinación cuesta claramente menos que la ejecución.

## 15. Transición desde S40–S48

S40–S48 se conserva como evidencia del piloto y de sus decisiones técnicas.
Sus contratos, fe de erratas, paquetes, hashes y rondas de reconciliación no
gobiernan ciclos nuevos. No se reabre DT1 ni S49 por adoptar este protocolo.
