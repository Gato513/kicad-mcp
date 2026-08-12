# Sesión 34d — corrección Known Limitations: contrato dual de `delete_tracks_bulk`

**Rama:** `sesion/readme-known-limitations-delete-tracks-bulk-v2` (desde
`master` @ `2a4b0d3`). **Tipo:** ciclo documental de corrección dirigida —
solo `README.md` + `README.es.md`, sin código, tests, specs ni ADRs.
**Estado: no publicado.** El commit revisado (`06fa30b`) está aprobado por
Codex pero push/PR/merge quedan reservados al arquitecto; nada de eso se
ejecutó en este ciclo.

## Resumen ejecutivo

Desde `34a-fix-1` (D-34a-fix-1.1), `delete_tracks_bulk` dejó de ser una
tool puramente W-IPC: cuando el board contiene al menos una zona de cobre,
corre `refill_zones` → `enforce_hole_clearance` → `save_board`, con error
tipado `POST_ZONE_PERSIST_FAILED` si el save falla en vez de fallar en
silencio. Ambos README seguían describiendo el comportamiento pre-fix
("refills copper zones in memory but doesn't persist") y anunciaban un fix
"already scheduled" que ya está cerrado. Además, el bullet de
disco==memoria seguía diciendo "Only `route_board`, `fill_zones`, and
`add_zone(fill=true)`", lista que dejó de ser exhaustiva.

Cerrado en `06fa30b`: 4 ediciones (2 bullets × 2 idiomas), 2 archivos,
1 commit. `delete_zone`/`add_keepout_zone` (A2/A3) siguen abiertos y sin
cambios de contenido. **Revisión independiente de Codex: APROBAR, 0
hallazgos** (BLOCKER/MAJOR/MINOR), 1 NOTE informativa.

## Auditoría previa y ampliación de alcance

`auditoria-previa-readme-known-limitations-fix.md` dio veredicto
**BLOQUEADO** sobre el alcance original (1 archivo, 1 bullet: solo el
bullet de `delete_tracks_bulk` en `README.md`) — activó correctamente la
condición de aborto 3b del brief al encontrar drift material adicional: el
bullet vecino de disco==memoria y el equivalente en `README.es.md` también
estaban desactualizados por la misma causa raíz. Gato resolvió la decisión
que la auditoría planteó, ampliando el alcance de forma acotada y final
(2026-08-12) a los 2 archivos y las 2 correcciones descritas arriba. Sin
segunda ronda de ChatGPT — la ampliación responde exactamente a la
pregunta que la auditoría formuló, dentro de la forma que ella misma
propuso (flujo híbrido multiagente v2 §5: sin reconciliación repetida
salvo contradicción material nueva; esta no lo era).

## Verificación contra código (read-only, previa a cada edición)

- `src/kicad_mcp/tools/pcb.py:1946-1994` — guard board-wide
  `touched_copper_zone = any(z.kind == "copper" for z in bridge.list_zones(board))`
  (línea 1947; nombre de variable engañoso, **no** es un test geométrico
  de si el borrado tocó esa zona específica). Bajo esa condición:
  `refill_zones` → `enforce_hole_clearance` → `save_board` dentro de un
  `try/except` que levanta `POST_ZONE_PERSIST_FAILED` con
  `live_has_fix=True` si el save falla (líneas 1966-1983). Sin la
  condición: solo mutación en memoria, mismo patrón que el resto de la
  familia W-IPC.
- `src/kicad_mcp/errors.py:48` y `docs/specs/tool-catalog.md:238,1005` —
  código de error vigente y ya catalogado desde `34a-fix-1`. No se
  tocaron (F1/F3 intactas).
- `docs/architecture-for-contributors.md:195-231` (§"`add_zone` and
  `delete_tracks_bulk` are dual-mode") — usado como fuente de precisión
  técnica para el matiz del disparador ("board-wide check, not a
  geometric test"), sin copiar su prosa literalmente. Ese documento
  también advierte (líneas 227-231) que
  `docs/analisis/auditoria-contratos-bridge.md` §6 quedó obsoleta para
  esta tool tras el fix — razón por la que el enlace a esa auditoría en
  los README quedó anclado solo a la frase de A2/A3, no a la nueva
  descripción de `delete_tracks_bulk`.

## Las 4 ediciones

**`README.md`** (líneas originales 102-114):
- Bullet "Most write tools don't save to disk by themselves" — reemplazó
  "Only `route_board`, `fill_zones`, and `add_zone(fill=true)` guarantee…"
  por una lista que incluye `delete_tracks_bulk` bajo su precondición
  ("when the board has copper zones"), sin abrir la condicionalidad propia
  de `route_board` (explícitamente fuera de alcance de este ciclo).
- Bullet `delete_tracks_bulk` — reescrito para describir la conducta dual
  real (disparador board-wide → refill+enforce+save con
  `POST_ZONE_PERSIST_FAILED`; sin zona de cobre → in-memory, W-IPC), sin
  la frase "has a fix already scheduled". `delete_zone`/`add_keepout_zone`
  conservados; lista de tracking pasó de `A1`/`A2`/`A3` a `A2`/`A3`.

**`README.es.md`** (líneas originales 65-73), por aplicación directa de
D-34b.2 (afecta "limitaciones conocidas"): mismas dos correcciones,
semánticamente equivalentes al inglés — mismo disparador preciso, mismo
alcance de la corrección, mismo tratamiento de A2/A3 intacto — en el
registro resumido que D-34b.2 ya fija para ese archivo (sin expandirlo a
traducción completa, sin enlaces nuevos que el bullet original no tenía).

## Desviaciones respecto de la orden (2, ambas declaradas antes de commitear)

1. **Base de la rama.** El `master` local estaba en `a29b151`
   (`2a4b0d3` + `34c-reporte.md`, commit sin push). La orden fijaba la
   base en `2a4b0d3`. Se preguntó al arquitecto y se decidió crear la
   rama de trabajo directamente en `2a4b0d3` (no en `a29b151`), para que
   el criterio de aceptación A5 (`git diff --stat` contra `2a4b0d3` =
   exactamente 2 archivos) se cumpliera literalmente sin necesidad de
   verificación path-scoped.
2. **Lista de tracking `A1`/`A2`/`A3` → `A2`/`A3`.** Dejar `A1` en una
   lista de ítems "abiertos" habría vuelto a afirmar lo que este ciclo
   corrige (A1/`delete_tracks_bulk` está cerrado desde `34a-fix-1`). Es el
   "ajuste mínimo de conexión gramatical" que la orden autorizaba
   explícitamente si el bullet se reestructuraba; la descripción de A2/A3
   no cambió de significado.

## Revisión de Codex

Independiente, read-only, contra el commit exacto `06fa30b`:

- Padre directo confirmado: `06fa30b^ == 2a4b0d3`.
- Diff completo inspeccionado: únicamente los 4 cambios declarados.
- Redacción contrastada con `pcb.py`, `architecture-for-contributors.md` y
  `tool-catalog.md`.
- Guard board-wide, modos W-COMPOSITE/W-IPC, `POST_ZONE_PERSIST_FAILED` y
  persistencia condicional correctamente documentados.
- A1 retirado; A2/A3 conservan su significado. Frases obsoletas
  eliminadas. `git diff --check` limpio.
- **Veredicto: APROBAR.**
- **NOTE** (única observación): los criterios A1–A8 no aparecen definidos
  textualmente como contrato versionado en el repo, solo en la orden de
  ejecución de Gato; el revisor los reconstruyó desde el alcance y
  criterios descritos ahí. No bloqueante — registrado aquí como
  observación de proceso, sin acción en este ciclo.

## Disciplina de alcance

- `git diff --stat 2a4b0d3` (sobre `06fa30b`) → exactamente `README.md` +
  `README.es.md`, 2 archivos.
- `git log --oneline 2a4b0d3..06fa30b` → 1 commit.
- `grep -n "already scheduled\|Only \`route_board\`\|Solo \`route_board\`"
  README.md README.es.md` → sin resultados en ambos.
- Contenido de `delete_zone`/`add_keepout_zone` verificado intacto en
  significado, en ambos idiomas.
- Sin pruebas automatizadas aplicables: cambio exclusivamente documental,
  sin código ni tests tocados (`pytest`/`ruff`/`mypy` no corresponden a
  este ciclo).

## Commits (2, sobre `2a4b0d3`)

- `06fa30b` — docs: corrige el contrato dual de delete_tracks_bulk en
  Known Limitations (34a-fix-1). **Aprobado por Codex, no se modifica.**
- Este reporte — `docs(sesion-34d): reporte de cierre — Known Limitations
  delete_tracks_bulk`. Commit posterior y separado, autorizado aparte por
  el arquitecto; **no** está cubierto por la revisión de Codex sobre
  `06fa30b`.

## Publicación

Ninguna en este ciclo. Push, PR, merge y tag quedan reservados al
arquitecto — desbloqueados por la aprobación de Codex sobre `06fa30b`,
pero no ejecutados. Rama de trabajo
`sesion/readme-known-limitations-delete-tracks-bulk-v2` queda local.

## Hallazgos fuera de alcance / próxima sesión

- Ningún drift nuevo encontrado en los README durante la ejecución más
  allá de los 2 bullets ya autorizados.
- `docs/INDEX.md:80` ("24 reportes de sesión (01–24…)") tiene el conteo de
  reportes desactualizado — preexistente a este ciclo, ya señalado entre
  los hallazgos de `34c-reporte.md`; no se corrigió acá (fuera de la
  allowlist cerrada de este ciclo).
- La condicionalidad de la propia garantía disco==memoria de
  `route_board` sigue documentada solo en
  `docs/architecture-for-contributors.md` — explícitamente fuera de
  alcance de este ciclo, sin cambios.
- `a29b151` (`docs(sesion-34c): reporte de cierre`) sigue sin push en
  `master` local — pendiente, ajeno a este ciclo.
