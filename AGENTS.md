# AGENTS.md — coordinación multiagente de kicad-mcp

Este archivo gobierna **coordinación multiagente**: roles institucionales,
autoridad transversal, separación productor/revisor, cambio de roles,
handoffs e integración autorizada.

No gobierna arquitectura del producto, reglas EDA/KiCad, specs, ADR,
reglas específicas de Claude Code, backlog, roadmap, estado operativo,
metodología general ni historia. Cada una de esas cosas tiene ya una
autoridad primaria — ver §Enlaces.

## R1 — Jerarquía técnica

La coordinación multiagente nunca anula specs, ADR, fronteras (F1–F5) ni
gates técnicos (G1–G5) existentes. Ante conflicto, prevalece la autoridad
técnica específica. Ninguna regla de este archivo ni ningún prompt de
sesión puede rebajarlos o reinterpretarlos.

## Roles institucionales

Definidos por función, no por herramienta concreta: así una implementación
puede sustituirse sin rediseñar la coordinación.

| Rol | Función |
|---|---|
| Autoridad | Objetivo, cambio de objetivo, alcance, ampliación de alcance, excepciones, publicación, push, PR, merge. |
| Arquitecto | Entender el objetivo, descomponer el problema, proponer arquitectura/estrategia, formular hipótesis, definir fronteras del trabajo, diseñar el plan, preparar el brief. |
| Auditor / reconciliador | Auditar premisas, alcance y contratos; detectar contradicciones; comparar arquitectura con evidencia; reconciliar productor y revisor; elevar decisiones a la autoridad. |
| Escritor | Produce o modifica una unidad integrable. |
| Revisor independiente | Inspecciona la unidad integrable exacta y emite veredicto. |
| Verificador mecánico | Comprueba propiedades automatizables. |

Notas por rol:

- **Autoridad** puede delegar una operación o scope concreto. La delegación
  es explícita, es acotada, no transfiere autoridad institucional y no
  desactiva controles técnicos automáticamente.
- **Arquitecto** no se convierte automáticamente en escritor ni en
  aprobador independiente.
- **Auditor / reconciliador** puede aportar crítica arquitectónica, pero no
  sustituye por defecto al arquitecto principal. La reconciliación **no**
  cuenta como revisión independiente de una unidad integrable si el
  reconciliador no inspeccionó realmente esa unidad.
- **Escritor**: un único escritor simultáneo por scope/unidad (ver R3).
- **Revisor independiente** no modifica la unidad durante una revisión
  read-only. Emite `APROBAR`, `APROBAR_CON_CAMBIOS` o `BLOQUEAR`.
- **Verificador mecánico** no decide intención, arquitectura ni adecuación
  semántica.

## Mapping operativo actual

| Rol institucional | Implementación actual |
|---|---|
| Autoridad | Humano |
| Arquitecto principal | Claude Chat |
| Auditor / reconciliador | ChatGPT |
| Ejecutor principal | Claude Code |
| Revisor independiente | Codex |
| Verificador mecánico | GitHub Actions |

El contrato de una sesión puede reasignar un rol operativo, pero debe
declararlo explícitamente y preservar las restricciones de independencia y
autoridad de este archivo.

## R2 — Autoridad humana

El humano conserva, por defecto, salvo delegación explícita y acotada,
autoridad sobre: objetivo, cambio de objetivo, alcance, ampliación de
alcance, excepciones, publicación, push, PR y merge.

## R3 — Escritor único y cambio de rol

Existe un solo escritor simultáneo por scope/unidad. Esto no significa un
único escritor para todo el repositorio a perpetuidad: distintos scopes o
unidades pueden tener escritores distintos, y un mismo agente puede
cambiar de rol entre unidades.

Todo cambio de rol debe declararse. Ejemplo: Codex puede actuar como
escritor controlado si el contrato de sesión lo declara explícitamente.
Cuando un revisor independiente pasa a escribir una unidad, deja de ser
revisor independiente de esa misma unidad.

## R4 — Independencia por unidad integrable

Quien produce o modifica una unidad destinada a integración no puede
emitir la aprobación independiente de esa misma unidad.

La unidad puede ser: un commit, una serie de commits, un diff, un
documento versionado, un contrato versionado, u otra unidad destinada a
merge. El revisor debe inspeccionar la unidad exacta.

Si una unidad cambia después de ser aprobada, la aprobación anterior deja
de cubrir el nuevo estado.

Un reporte temporal, handoff o análisis intermedio no dispara revisión
recursiva, salvo que él mismo vaya a integrarse como contenido
versionado/normativo.

## R5 — Estado, scope y hallazgos

Antes de producir o revisar una unidad relevante: verificar estado real,
verificar base, verificar scope, identificar productor, identificar la
unidad exacta. No confiar en SHAs históricos sin reverificarlos. El
estado previo dirty/untracked debe poder distinguirse de los cambios
introducidos por la sesión en curso.

Un hallazgo fuera de scope se registra y se eleva; no se corrige
silenciosamente.

## R6 — CI y revisión semántica

CI y revisión independiente son verificaciones distintas; ninguna
sustituye automáticamente a la otra. CI verde no sustituye revisión
independiente cuando ésta es requerida por el riesgo o el contrato de la
sesión. Una revisión aprobada tampoco sustituye los gates mecánicos
requeridos. La intensidad del proceso se adapta al riesgo: no todo cambio
trivial exige el mismo despliegue ceremonial.

## R7 — Handoff mínimo

Todo handoff entre roles contiene sólo lo necesario para continuar sin
cargar la conversación completa:

```text
ROL / PRODUCTOR
CONTRATO + SCOPE
BASE
UNIDAD / HEAD
RESULTADO
EVIDENCIA
HALLAZGOS + VEREDICTO
PENDIENTES + AUTORIDAD SIGUIENTE
```

Puede comprimirse cuando algún campo no aplica. No existe un archivo
separado de plantilla para esto.

## Vocabulario

Estado: `GO`, `NO_GO`.
Revisión: `APROBAR`, `APROBAR_CON_CAMBIOS`, `BLOQUEAR`.
Severidad: `BLOCKER`, `MAJOR`, `MINOR`, `NOTE`.

Formas como `APROBAR_COMMIT` o `APROBAR_COMMIT_SERIES` no son estados
nuevos, son maneras de identificar el objeto revisado. Preferir:

```text
VEREDICTO: APROBAR
UNIDAD: <referencia exacta>
```

## Modelo operativo conceptual

```text
ESTADO + CONTRATO
        ↓
PRODUCCIÓN
        ↓
VERIFICACIÓN INDEPENDIENTE
        ↓
INTEGRACIÓN AUTORIZADA
```

Esto describe responsabilidades a cubrir para producir una unidad
integrable en trabajo multiagente, no necesariamente cuatro sesiones
separadas: pueden compactarse proporcionalmente al riesgo. Lo que no puede
compactarse es que quien produce una unidad no sea también quien la
aprueba de forma independiente (R4).

## Qué pertenece al contrato de cada sesión, no a este archivo

Objetivo concreto, BASE y HEAD concretos, branch, scope concreto, archivos
permitidos y prohibidos, asignación concreta de roles, tests y criterios
de aceptación concretos, estrategia de commits, hipótesis y criterios de
refutación, delegaciones excepcionales, y nivel de despliegue de
checkpoints. Ese contenido es específico de cada trabajo y no se
institucionaliza acá.

## Enlaces (autoridad primaria — no duplicar)

- Fronteras F1–F5: `docs/adr/0000-fronteras-inviolables.md`.
- Gates G1–G5: `docs/adr/0003-gates-de-autonomia.md`.
- Reglas y comandos del ejecutor Claude Code: `CLAUDE.md`.
- Decisiones de proceso y metodología: `docs/DECISIONES.md`.
- Estado y prioridades vigentes: `docs/BACKLOG.md`, `hoja-de-ruta-v5.md`.
- Evidencia histórica del proceso: `docs/historico/`.
- Mapa general de documentación: `docs/INDEX.md`.
