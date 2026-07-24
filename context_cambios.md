# Contexto de cambios — reorganización documental (2026-07-24)

Documento de briefing para que el arquitecto se actualice antes de retomar el
rol. Cubre dos sesiones de trabajo documental encadenadas, ejecutadas por el
agente sobre el repo entre la entrega de `CONTEXT-v7.md` y este momento.
**No reemplaza a `hoja-de-ruta-v4.md` ni a `docs/CONTEXT.md`** — es el relato
de qué cambió y por qué, para que el próximo `CONTEXT-v8` (si corresponde)
parta del estado real y no de supuestos.

---

## 1. Punto de partida

Existía una reorganización documental previa (commit `b876090`) que había
partido un `CONTEXT.md` monolítico (basado en `CONTEXT-v3.md`, congelado en
sesión 19e) en cuatro documentos: `docs/CONTEXT.md` (dejado como andamiaje
vacío), `docs/DECISIONES.md`, `docs/ROADMAP.md`, `docs/BACKLOG.md`, más un
`docs/INDEX.md` como mapa de navegación.

El humano entregó **`docs/historico/CONTEXT-v7.md`** (post-sesión 24, mucho
más reciente que v3) y **borró `CONTEXT-v3.md`**, dejando 5 documentos con
referencias rotas a un archivo que ya no existía.

## 2. Primera pasada — consolidar v7 en la estructura de 4 documentos

Objetivo: hacer de v7 la fuente de verdad, sin convertir `docs/CONTEXT.md` en
una copia de v7 (debía ser síntesis para un arquitecto externo, no
cronología).

**Cambios:**
- `docs/CONTEXT.md` reescrito desde cero: qué es el sistema (ya no "MVP
  solo-lectura", sino loop de escritura de PCB cerrado con 20+ tools),
  arquitectura/principios, estado Fase 3 (modelo de fases 1-4, criterio de
  convergencia, interpretación verde/amarillo/rojo), decisiones vigentes
  (resumen + puntero), riesgos abiertos, conocimiento de dominio para
  decisiones futuras.
- `docs/DECISIONES.md`: agregadas D-24.1 (fixture helper runtime), D-24.2
  (baseline dinámico + delta), D-19.1 (Freerouting no respeta plano GND como
  exclusión); matizada la fila de ADR-0012 (el contrato disco==memoria==
  reportado rige hoy **solo** en `route_board`, no en `fill_zones`/`add_zone`).
- `docs/ROADMAP.md`: reescrita la sección post-D5 con la secuencia estricta
  de Fase 3 completa (D5 → fix P1 → generalización D-23.2 → D6 →
  convergencia); release explícitamente diferido a post-convergencia (antes
  el borrador sugería "considerar open source" apenas tras D5).
- `docs/BACKLOG.md`: repriorizado — nuevo P1 (solder mask ANT1), nuevo P2
  (generalización D-23.2), CRUD-sch bajado de P1 a P3 (v7 lo excluye del
  alcance de Fase 3), agregado R16/D-23.3.
- `docs/INDEX.md`: puntero histórico actualizado, descripción de
  `docs/CONTEXT.md` corregida.

**Inconsistencia detectada y reportada (no corregida en esta pasada):**
`CLAUDE.md` seguía describiendo el proyecto como "MVP solo-lectura (sin
mutaciones aún)", contradiciendo el estado real documentado en v7. Se dejó
una nota en `docs/CONTEXT.md` señalándolo, sin editar `CLAUDE.md` (fuera del
alcance de esa tarea).

## 3. Cambios del humano entre pasadas

El humano, independientemente:
1. **Actualizó `CLAUDE.md`** — corrigió la inconsistencia "MVP solo-lectura"
   (ahora describe correctamente 20+ tools con escritura de PCB), agregó
   referencias a `CONTEXT.md`/ADR-0012, nuevo marcador de test
   `integration_gui_slow`, nuevas reglas de código (contrato D-23.2, F1
   con excepción sancionada para adiciones a `ErrorCode`).
2. **Creó `hoja-de-ruta-v4.md`** en la raíz del repo — documento operacional
   detallado de la secuencia de Fase 3 (tabla sesión-por-sesión con gates de
   salida explícitos, criterio de cierre de Fase 3, qué NO se prioriza).

## 4. Segunda pasada — reconciliar la estructura con los cambios del humano

Estos dos cambios del humano introdujeron nuevas referencias y un documento
nuevo que entraban en tensión con la estructura de la primera pasada.
Verificación contra el repo real (no asunciones) reveló:

### 4.1 Bug real (no solo desalineación): rutas rotas en documentos protegidos

La primera pasada había movido `investigacion/` a `docs/historico/
investigacion/`. Pero **`docs/specs/tool-catalog.md` (F1) y
`docs/adr/0012-route-board-persist-contract.md`** (nunca editado
retroactivamente) **ya referenciaban `docs/investigacion/`** desde antes de
esa reorg — la primera pasada rompió esos links sin verificarlo.

**Fix:** `git mv docs/historico/investigacion docs/investigacion` — mueve
archivos, no toca contenido protegido. Resuelve los links en
`tool-catalog.md`, ADR-0012, `CLAUDE.md` y `hoja-de-ruta-v4.md` (los dos
últimos ya asumían esa ruta, correctamente).

### 4.2 Reclamo prematuro en `CLAUDE.md`

`CLAUDE.md` decía "F4: KiCad 10.0.4 (validado en dogfoodings D3-D5)". **D5
todavía no había corrido** (sin reporte de sesión 25 en el repo,
`git log` sin merge posterior a sesión 24). Contradecía al propio
`hoja-de-ruta-v4.md` ("D5 lo evalúa por primera vez"). Reportado al humano,
quien lo corrigió a mano: `D3-D4 (D5 pendiente)`.

### 4.3 Decisión estructural: `hoja-de-ruta-v4.md` vs `docs/ROADMAP.md`

Ambos documentos cubrían la secuencia de Fase 3 con contenido casi idéntico
pero no igual. `CLAUDE.md` ya apuntaba a `hoja-de-ruta-v4.md` como "la ruta
vigente" para el flujo de trabajo. **Se le preguntó al humano** cómo resolver
la duplicación; eligió: **`hoja-de-ruta-v4.md` es la única fuente de la
secuencia estratégica.**

**Fix:** `docs/ROADMAP.md` se redujo a estado-en-una-línea + historial de
dogfooding (tabla D1-D4, valor que `hoja-de-ruta-v4.md` no repite). Ya no
duplica la secuencia estricta.

### 4.4 Referencias internas rotas en `hoja-de-ruta-v4.md`

- Ruta a la hoja anterior: decía `docs/historico/hoja-de-ruta-v3.md`, la
  real es `docs/historico/roadmaps/hoja-de-ruta-v3.md`.
- 3 referencias a `CONTEXT.md § "Backlog priorizado v7"` — esa sección no
  existe en el `docs/CONTEXT.md` consolidado de la primera pasada (el
  backlog se separó a `docs/BACKLOG.md`). Corregidas para apuntar ahí.
- Menciones ambiguas de "CONTEXT.md v7" (el nombre de archivo real es
  `docs/historico/CONTEXT-v7.md`, ya que "CONTEXT.md" ahora es el documento
  consolidado). Desambiguadas.

### 4.5 Ítems de backlog de v7 que se habían perdido en la primera pasada

La primera pasada, al repriorizar `docs/BACKLOG.md`, omitió por descuido una
sección completa del backlog de v7 ("P2 release polish") y varios ítems P4.
Violaba la propia regla de "no eliminar información existente". Se
agregaron en esta pasada:

- **P2 release polish** (diferido hasta convergencia de Fase 3): ADR-0013+
  (edge clearance Freerouting), docs para colaboradores externos, test
  canario Freerouting, licencia + README + CONTRIBUTING, limpieza de código
  muerto.
- **P4 adicionales**: timeout adaptativo, limpieza de tracks huérfanos,
  guard cross-proceso, `add_zone` con hueco interior, Opción Y de F-D4-02
  (descartada, solo reconsiderar con evidencia de intermitencia real).

### 4.6 `docs/INDEX.md`

Actualizado: `hoja-de-ruta-v4.md` y `docs/investigacion/*.md` agregados como
documentos activos; mapa de `historico/` corregido (ya no lista
`investigacion/` ahí); regla de promoción de resúmenes actualizada para
incluir `hoja-de-ruta-v4.md`.

---

## 5. Estado actual de la documentación (mapa rápido)

| Documento | Rol |
|---|---|
| `CLAUDE.md` (raíz) | Contrato del agente ejecutor — superficie estable |
| `hoja-de-ruta-v4.md` (raíz) | **Única fuente de la secuencia estratégica de Fase 3** — gates de salida, criterio de convergencia |
| `docs/CONTEXT.md` | Síntesis para arquitecto externo — no cronología, no backlog detallado |
| `docs/historico/CONTEXT-v7.md` | Handoff monolítico original, sesión-por-sesión, congelado post-sesión 24 |
| `docs/DECISIONES.md` | Índice de ADR + decisiones informales vigentes |
| `docs/ROADMAP.md` | Estado en una línea + historial de dogfooding (D1-D4). Ya no repite la secuencia |
| `docs/BACKLOG.md` | Backlog priorizado completo (única fuente, ya no vive en `docs/CONTEXT.md`) |
| `docs/INDEX.md` | Mapa de navegación de toda la documentación |
| `docs/investigacion/*.md` | Investigaciones de causa raíz — **activo, no histórico** (referenciado por ADR-0012 y `tool-catalog.md`) |
| `docs/historico/**` | Evidencia de proceso: sesiones, prompts, auditorías, roadmaps v2/v3, dogfooding — no operativo |

## 6. Hechos clave para no perder de vista

- **D5 (sesión 25) todavía no corrió.** Ninguna fila nueva en el historial
  de dogfooding, ningún reporte de sesión 25 en el repo. La próxima acción
  real del proyecto es ejecutar D5, no una sesión de docs.
- El backlog de Fase 3 vigente es: **P1 solder mask ANT1 → P2 generalización
  D-23.2 → convergencia** (2-3 verdes consecutivos). Ver `docs/BACKLOG.md`
  para el detalle completo, `hoja-de-ruta-v4.md` para la secuencia y gates.
- `docs/investigacion/` cambió de ruta (ya no bajo `historico/`) — si algún
  documento nuevo cita esos reportes, usar la ruta sin `historico/`.

## 7. Recomendación para cuando se redacte `CONTEXT-v8`

Si `CONTEXT-v8` se escribe como monolito nuevo (al estilo v3→v7), considerar
si sigue teniendo sentido mantenerlo así o si conviene que el "handoff para
nuevo chat de arquitecto" apunte directamente a `docs/CONTEXT.md` +
`hoja-de-ruta-v4.md`/`v5` + `docs/BACKLOG.md`, evitando la duplicación que
motivó esta reorganización. En cualquier caso: si v8 reintroduce una sección
de backlog propia, hay que decidir explícitamente si reemplaza o convive con
`docs/BACKLOG.md` — la ambigüedad de ese punto fue la causa de la mayoría de
los fixes de la sección 4.
