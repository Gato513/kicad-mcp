# Sesión 47 — recordatorio formal de auditoría de Codex en AGENTS.md

## Resumen ejecutivo

A pedido del usuario ("recordame hacer las auditorías... a veces las
olvido"), se evaluó cuándo corresponde recordar la revisión de Codex
(flujo v2 §5) antes de cerrar un ciclo, y se agregó una extensión: recordar
también la auditoría del PLAN de plan mode antes de implementar, para
unidades `R2`, no sólo el resultado. Se presentó como propuesta, el usuario
la aceptó, y se auditó con Codex antes de comitear — encontró 1 `MAJOR`
real y autorreferencial: la propia unidad auditada (un cambio a `AGENTS.md`)
no activaba ninguno de los disparadores propuestos.

## Cambios

**`AGENTS.md` §6** — nueva subsección "Recordatorio de auditoría
(obligación del Escritor)", después de la regla 4. Seis disparadores:
cambio a `src/`, test con lógica nueva, documento normativo nuevo o
modificado sustantivamente, cierre de `P0`/`P1`/`P2` del BACKLOG con fix
real, cambios a `tool-catalog.md`/códigos de error, y un plan `R2` antes de
implementar (reasigna a Codex el rol de Auditor previo cuando ChatGPT no
está disponible, sin sumar una segunda auditoría previa — sigue siendo la
única que la regla 1 del §6 permite). Explícito: Claude Code sólo recuerda,
no corre la auditoría por su cuenta ni decide por Gato — mismo principio ya
aplicado en `docs/proceso/JUICIO-CRUZADO-CODEX-v1.md` §2 para el
señalamiento de riesgo alto.

## Auditoría Codex (unidad: el cambio a AGENTS.md) — APROBAR_CON_CAMBIOS → APROBAR

Primera pasada, `mcp__codex__codex` read-only: `APROBAR_CON_CAMBIOS`.

- **MAJOR confirmado** — el disparador 3 decía "documento **nuevo**" que se
  vuelve normativo, excluyendo modificaciones a documentos normativos ya
  existentes. La propia unidad auditada (una edición a `AGENTS.md`, no un
  documento nuevo) es la prueba directa del hueco: no activaba ninguno de
  los 6 disparadores propios. Corregido a "documento nuevo... o un cambio
  sustantivo (no editorial) a uno ya existente".
- **MINOR confirmado** — "una unidad que ya se auditó" era ambiguo entre la
  auditoría previa (rol de ChatGPT) y la revisión posterior (rol de Codex,
  regla 4). Corregido a "ya recibió la revisión posterior de Codex (§6
  regla 4)".

Reparación acotada aplicada (una sola ronda, `AGENTS.md` §9). Re-juicio del
delta con el mismo Codex: `APROBAR`, sin hallazgos nuevos. Verificado
también por lectura directa del diff antes de comitear.

## Memoria

Dos memorias `feedback` guardadas para sesiones futuras:
`feedback_senalamiento_proactivo_riesgo_alto.md` (avisar con razones ante
`R2`/`R1` alto y sugerir juicio cruzado sólo si está justificado) y
`feedback_recordar_auditorias_codex.md` (recordar la auditoría de Codex
según los 6 disparadores de este commit, actualizada para apuntar a
`AGENTS.md` §6 en vez de a un criterio ad hoc).

## Sin ADR

Documento de proceso, sin contrato arquitectónico nuevo.

## Commit

Un commit `docs:` en `sesion/42-dt1-slice2-caracterizacion`, con los
trailers de atribución. Sin push (DoD #6).
