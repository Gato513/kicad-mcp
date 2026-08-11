# AGENTS.md — coordinación multiagente de kicad-mcp

Este archivo gobierna la coordinación multiagente: autoridad, roles,
independencia, ciclos de objetivo, handoffs e integración. No gobierna la
arquitectura del producto, KiCad, specs, ADR técnicos, backlog ni roadmap.

## 1. Jerarquía técnica

La coordinación nunca anula specs, ADR, fronteras F1–F5 ni gates G1–G5. Ante
conflicto prevalece la autoridad técnica específica. Ningún prompt puede
rebajarla o reinterpretarla.

## 2. Roles institucionales

| Rol | Función |
|---|---|
| Autoridad | Fija objetivo, alcance, excepciones, publicación, push, PR y merge. |
| Arquitecto | Propone una unidad completa, estrategia, aceptación, riesgo y ramas preautorizadas. |
| Auditor previo | Audita premisas y alcance una vez; entrega una orden reconciliada ejecutable. |
| Escritor | Investiga, implementa, prueba y documenta la unidad autorizada. |
| Revisor independiente | Inspecciona la unidad exacta terminada y emite veredicto. |
| Verificador mecánico | Comprueba propiedades automatizables. |

### Mapeo operativo normal

| Rol | Agente |
|---|---|
| Autoridad | Gato |
| Arquitecto | Claude Chat |
| Auditor previo | ChatGPT |
| Escritor / ejecutor | Claude Code |
| Revisor independiente | Codex |
| Verificador mecánico | GitHub Actions / tests |

Una orden puede reasignar un rol para una unidad concreta si lo declara
expresamente. Quien escribe una unidad no puede revisarla de forma
independiente.

Notas por rol:

- Una delegación de la autoridad es explícita y acotada; no transfiere la
  autoridad institucional ni desactiva controles técnicos.
- El arquitecto no se convierte automáticamente en escritor ni en aprobador
  independiente.
- El auditor previo puede aportar crítica arquitectónica, pero no sustituye al
  arquitecto principal. Su reconciliación tampoco cuenta como revisión
  independiente si no inspeccionó la unidad exacta terminada.
- El revisor independiente trabaja en modo read-only sobre la unidad revisada
  y emite `APROBAR`, `APROBAR_CON_CAMBIOS` o `BLOQUEAR`.
- El verificador mecánico no decide intención, arquitectura ni adecuación
  semántica.

## 3. Autoridad humana reservada

Gato conserva, salvo delegación explícita y acotada, autoridad sobre:

- objetivo y cambio de objetivo;
- alcance y ampliación material de alcance;
- excepciones a F1–F5;
- acciones destructivas;
- publicación, push, PR y merge;
- continuación tras un `BLOCKER` o presupuesto agotado.

No necesita aprobar comandos, elecciones tácticas dentro del alcance,
documentos temporales, `NOTE`, `MINOR` ni el paso normal entre agentes.

## 4. Escritor único e independencia por unidad

Existe un solo escritor simultáneo por scope/unidad. Distintos scopes pueden
tener escritores distintos.

Quien produce o modifica una unidad integrable no puede emitir su aprobación
independiente. El revisor debe inspeccionar la unidad exacta. Si esta cambia
después de la revisión, la aprobación anterior deja de cubrirla.

La unidad integrable puede ser un commit, una serie de commits, un diff, un
documento o contrato versionado, u otra unidad destinada a integración.

Un análisis, handoff o reporte temporal no dispara revisión recursiva salvo que
él mismo vaya a integrarse como contenido normativo.

## 5. Unidad básica: ciclo de objetivo

Un ciclo representa un resultado útil, no un documento ni una conversación.
Debe iniciar con:

```text
CICLO / OBJETIVO:
RESULTADO ESPERADO:
ALCANCE:
FUERA DE ALCANCE:
CRITERIOS DE ACEPTACIÓN:
RIESGO: R0 | R1 | R2
PRESUPUESTO + CONDICIÓN DE ABORTO:
```

Un ciclo puede incluir investigación, implementación, tests y documentación.
No se abren ciclos separados para brief, contrato, informe, diff o corrección
editorial.

## 6. Secuencia operativa vigente

```text
Gato fija el objetivo
→ Claude propone una unidad completa
→ ChatGPT audita y reconcilia una sola vez
→ Claude Code ejecuta el alcance de punta a punta
→ Codex revisa la unidad exacta terminada
→ Claude cierra o propone el siguiente objetivo
```

Reglas obligatorias:

1. Una propuesta recibe como máximo una auditoría previa de ChatGPT.
2. ChatGPT no devuelve la misma propuesta a Claude para ciclos editoriales.
3. Claude Code puede investigar, elegir una rama preautorizada, implementar y
   corregir sus propios fallos de tests sin microautorizaciones.
4. Codex realiza una revisión posterior de la unidad terminada.
5. ChatGPT no reconcilia de nuevo el mismo ciclo salvo petición expresa de
   Gato por una contradicción material.
6. `NOTE` y `MINOR` no abren una reparación automática.
7. Se permite como máximo una reparación acotada por hallazgos `MAJOR`.
8. Un `BLOCKER`, una segunda reparación o un cambio de objetivo vuelve a Gato.

El detalle operativo vive en
`docs/proceso/FLUJO-HIBRIDO-MULTIAGENTE-v2.md`.

## 7. Ramas preautorizadas

Si hay incertidumbre técnica, Claude puede autorizar en una misma propuesta:

```text
Si evidencia E1 confirma H1 → implementar A + pruebas TA.
Si E1 refuta H1 y confirma H2 → implementar B + pruebas TB.
Si no ocurre A ni B → detener con EVIDENCIA_NO_CUBIERTA.
```

ChatGPT audita las ramas una sola vez. Claude Code investiga y continúa por la
rama respaldada. Separa investigación de implementación solo cuando cambie la
autoridad requerida, el riesgo o no sea posible acotar ramas seguras.

## 8. Intensidad proporcional al riesgo

| Nivel | Ejemplo | Preparación | Identidad / revisión |
|---|---|---|---|
| `R0` | análisis read-only o documento temporal | tarjeta breve | ruta; sin ZIP, hash ni manifiesto |
| `R1` | código o documentación ordinaria | orden compacta | diff/commit + tests relevantes |
| `R2` | F1–F5, API pública, seguridad, datos, release o acción destructiva | contrato acotado | unidad exacta + gates completos |

Git es la identidad predeterminada. Hashes, manifiestos, ZIP y custodia solo se
usan cuando existe un riesgo concreto que Git no resuelve. Un contrato `R2`
describe decisiones y límites; no duplica specs ni prescribe cada comando.

## 9. Hallazgos y reparaciones

| Severidad | Consecuencia |
|---|---|
| `NOTE` | Registrar; no reabrir. |
| `MINOR` | No bloquea; trasladar solo si aporta valor. |
| `MAJOR` | `APROBAR_CON_CAMBIOS`; una reparación acotada. |
| `BLOCKER` | `BLOQUEAR`; decide Gato. |

La reparación toca solo hallazgos `MAJOR` enumerados, conserva el objetivo y no
repite la auditoría previa. El revisor inspecciona el nuevo delta y su efecto.
Si persiste un `MAJOR` o aparece un `BLOCKER`, no hay otra ronda automática.

## 10. Estados de cierre

```text
OBJETIVO_CUMPLIDO
OBJETIVO_CUMPLIDO_CON_DEUDA_NO_BLOQUEANTE
OBJETIVO_NO_CUMPLIDO_POR_EVIDENCIA
OBJETIVO_BLOQUEADO_POR_DECISION_HUMANA
OBJETIVO_ABORTADO_POR_PRESUPUESTO
```

Una unidad aprobada no se reabre por estilo o preferencia. Reabrir exige
evidencia nueva y un nuevo objetivo.

Vocabulario transversal:

- Estado operativo: `GO`, `NO_GO`.
- Revisión: `APROBAR`, `APROBAR_CON_CAMBIOS`, `BLOQUEAR`.
- Severidad: `BLOCKER`, `MAJOR`, `MINOR`, `NOTE`.

Formas como `APROBAR_COMMIT` no son estados distintos: la unidad exacta se
identifica por separado del veredicto.

## 11. Presupuesto y detenciones

Arquitectura y auditoría deben consumir claramente menos esfuerzo que la
ejecución prevista. Toda investigación declara la decisión que desbloquea, la
evidencia mínima, el universo o tiempo máximo y el estado válido si no logra
decidir.

El escritor solo se detiene por:

- cambio material de objetivo o alcance;
- F1–F5 no autorizada;
- acción destructiva, publicación, push, PR o merge no autorizados;
- evidencia no cubierta por las ramas;
- imposibilidad demostrada;
- presupuesto agotado.

## 12. Estado, scope y CI

Antes de producir o revisar una unidad relevante: verificar estado real, base,
scope, productor y unidad exacta. El estado dirty previo debe distinguirse de
los cambios de la sesión. Un hallazgo fuera de scope se registra y no se
corrige silenciosamente.

CI y revisión semántica son controles distintos. Ninguno sustituye al otro
cuando ambos sean requeridos. La intensidad se adapta al riesgo.

## 13. Handoff mínimo

```text
CICLO / OBJETIVO:
ROL / PRODUCTOR:
BASE + UNIDAD EXACTA:
RESULTADO:
EVIDENCIA / TESTS:
HALLAZGOS + VEREDICTO:
PENDIENTE + DESTINATARIO SIGUIENTE:
```

Se adjunta solo lo necesario. Los artefactos históricos se referencian por
ruta o commit; no se reempaquetan.

El objetivo concreto, base y HEAD, branch, scope, archivos permitidos y
prohibidos, tests, aceptación, estrategia de commits, hipótesis, ramas,
delegaciones excepcionales y checkpoints pertenecen al contrato específico de
cada ciclo; no se institucionalizan en este archivo.

## 14. Enlaces de autoridad primaria

- Flujo operativo: `docs/proceso/FLUJO-HIBRIDO-MULTIAGENTE-v2.md`.
- Fronteras F1–F5: `docs/adr/0000-fronteras-inviolables.md`.
- Gates G1–G5: `docs/adr/0003-gates-de-autonomia.md`.
- Ejecutor Claude Code: `CLAUDE.md`.
- Decisiones de proceso y método: `docs/DECISIONES.md`.
- Estado y prioridades: `docs/BACKLOG.md`, `hoja-de-ruta-v5.md`.
- Evidencia histórica: `docs/historico/`.
- Mapa documental: `docs/INDEX.md`.

## 15. Regla de transición

Los artefactos S40–S48 conservan valor histórico y probatorio, pero sus
procedimientos específicos no son precedentes operativos para trabajos nuevos.
En conflicto de proceso, este archivo y el flujo v2 prevalecen sobre contratos,
prompts, fe de erratas o paquetes históricos, sin alterar sus conclusiones
técnicas.
