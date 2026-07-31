# Sesión 34b — LICENSE + NOTICE + README público + CONTRIBUTING.md

**Rama:** `sesion/34b-license-readme-contributing` (desde `master` — el
rename `master`→`main` que el prompt asumía tampoco estaba hecho en esta
sesión, igual que en 34a; `sesion-01` sigue viva y `origin/HEAD` la sigue
apuntando). Ambas quedan como operación directa del arquitecto, sin
bloquear el merge. Secuencia 32b→32c→32d→33→34a ya estaba en `master`
(`dcf1d7c`).

**Tipo:** escritura estructurada de documentación OSS, sin código de
`src/`. Segunda de la trilogía de preparación de release (34a → **34b** →
34a-fix-1 → 34c).

## Resumen ejecutivo

Primera exposición pública consciente del proyecto: `LICENSE` (Apache
2.0), `NOTICE`, `README.md` público en inglés (reemplaza el README
interno en español), `README.es.md` (traducción resumida), y
`CONTRIBUTING.md`. Input principal: `docs/analisis/auditoria-contratos-bridge.md`
§6 (sesión 34a) y `docs/analisis/validation-suite-sintesis-A-B-C.md`.

Cada afirmación pública se formuló como hipótesis refutable (D-33.1)
antes de aceptarla — registro auditable en
`docs/analisis/readme-honestidad-check.md`: 16/16 afirmaciones revisadas
sostenidas, 2 con matiz explícito ya incorporado al texto (no oculto).

**2 correcciones a premisas del prompt original**, encontradas al
verificar en vez de asumir: `kicad-skip` es LGPL-2.1-or-later, no MIT
(metadata del paquete instalado); `pcbnew` se invoca por subprocess
contra el Python del sistema, nunca importado en el venv del proyecto
(`bridge/autoroute.py`). Ambas corregidas en `NOTICE` y en la
justificación de D-34b.1.

**Conteo de tools verificado por comando, no copiado del prompt**: 32
tools únicas (`grep -rA2 "@mcp.tool" src/kicad_mcp/tools/*.py`), no "20+"
ni "31" como decían distintas fuentes internas.

## Bloque 0 — Setup y precondiciones

Igual que en 34a: rename no hecho, `sesion-01` viva. Se ramificó desde
`master` sin bloquear la sesión (decisión ya tomada explícitamente al
inicio, sin necesidad de reconsultar — mismo patrón que 34a). Baseline
`pytest -m "not integration"`: **394 passed, 39 skipped**, igual al
esperado.

## Bloque 1 — LICENSE + NOTICE

`LICENSE`: texto completo de Apache License 2.0, apéndice con
`Copyright 2026 The kicad-mcp contributors` (decisión del arquitecto vía
`AskUserQuestion`).

`NOTICE`: tabla de 7 dependencias con licencia distinta de Apache 2.0
(KiCad, `pcbnew`, Freerouting — GPL-3.0-or-later; `kicad-skip` —
LGPL-2.1-or-later, corregido; `kicad-python`/`mcp`/`pydantic` — MIT;
`protobuf` transitiva — BSD-3-Clause), cada una con su modelo de
invocación exacto (subprocess/IPC vs. import), y nota descriptiva de por
qué ese modelo no crea conflicto de licencia con el código propio.
Reconocimientos a ANAVI Technology y Great Scott Gadgets (proyectos de
la Validation Suite).

## Bloque 2 — README.md público

195 líneas, en inglés, reemplaza el README interno (su contenido de
navegación ya está cubierto por `docs/INDEX.md`, y estaba desactualizado
a sesión 24).

Elevator pitch elegido tras descartar explícitamente 3 frases refutables
por evidencia propia del proyecto ("end-to-end", "automates full PCB
design", "works on any board" — las tres refutadas por Nivel C/HackRF
One). Sección "What it does" declara la escala validada sin ambigüedad
(63 fp/2 capas completo; 437 fp/4 capas como frontera refutatoria, no
como éxito matizado).

**"Known limitations" — 10 ítems**, cada uno con link a su fuente:
escala, crash-loop de Freerouting (upstream), `add_zone(fill=true)`
crash no concluyente, persistencia W-IPC no automática, asimetrías
`delete_tracks_bulk`/`delete_zone`/`add_keepout_zone`, variante
same-layer de F-D5-01 no cubierta, esquemático sin CRUD/sin IPC,
idle-timeout del cliente MCP, tests GUI no automatizados, Linux-only.

Quickstart con comandos y env vars reales del repo (`verificar_entorno.py`,
`KICAD_MCP_PROJECT`, `KICAD_MCP_FREEROUTING_JAR`, `KICAD_API_SOCKET`,
`npx @modelcontextprotocol/inspector`) — verificados contra
`scripts/verificar_entorno.py`, no inventados.

## Bloque 3 — CONTRIBUTING.md

235 líneas. "How the project makes decisions" traduce D-30.1/D-31c.1/
D-33.1 a lenguaje accesible con ejemplos concretos y links a los
reportes de sesión que los ejercitaron (30, 31b, 33). "Bridge write
contracts" usa los 4 ejes de D-34a.1 con ejemplos reales del código,
incluyendo un snippet antes/después del patrón de
F-V2-REFILL-SILENCIOSO (marcado "roughly" — no es el diff literal,
es una reconstrucción fiel al mecanismo documentado en D-32b.1).
Checklist de "How to add a new write tool" tomado directo de auditoría
34a §6. Nota honesta de "maintenance status" (mantenimiento hoy es
mayormente de un solo maintainer) — aplicación de D-30.2/D-33.1 a las
expectativas de contribución, no sólo a afirmaciones técnicas.

## Bloque 4 — README.es.md

Creado (no diferido): traducción resumida — pitch, qué hace, escala
validada, las 10 limitaciones (versión condensada), link al README
principal. No traduce quickstart completo ni CONTRIBUTING (D-34b.2).

## Bloque 5 — Consolidación

- **`docs/analisis/readme-honestidad-check.md`**: 16 afirmaciones
  públicas verificadas una por una (evidencia / qué la refutaría /
  veredicto), más 2 frases descartadas explícitamente antes de publicar.
  16/16 sostenidas.
- **Verificación de links**: los 20 paths únicos referenciados desde
  README/README.es/CONTRIBUTING existen, verificado con chequeo directo
  de filesystem (no sólo `find` visual).
- **Lectura como externo**: `grep` de jerga interna sin explicar
  ("sesión NN", códigos `D-XX.X`) en los 3 documentos públicos — 0
  apariciones. Los identificadores de tracking (`F-V3-...`, `A1`/`A2`/`A3`,
  `F-D5-01-B`) sólo aparecen como tags parentéticos después de la
  oración que ya explica el comportamiento, nunca como sustituto de la
  explicación.
- **`docs/CONTEXT.md`**: entrada 6 de "Estado de la secuencia de Fase 4"
  (cierre de 34b), próxima sesión actualizada a `34a-fix-1` (precede a
  34c).
- **`docs/DECISIONES.md`**: `D-34b.1` (Apache 2.0, con el razonamiento de
  compatibilidad GPL/LGPL verificado, no asumido) y `D-34b.2` (inglés
  principal / español secundario, con el alcance exacto de qué se
  traduce y qué no).
- **`docs/BACKLOG.md` no tocado** (cierre por arquitectura, no cambio de
  backlog, tal como pedía el prompt).

## Gates

- `pytest -m "not integration"`: **394 passed, 39 skipped, 0 failed**
  (sin cambios respecto al baseline — sesión puramente documental).
- `git diff --stat` contra `master`: solo `README.md`, `docs/CONTEXT.md`,
  `docs/DECISIONES.md` modificados + los archivos nuevos esperados.
  `src/`, `tests/`, `docs/specs/`, `docs/adr/`, `docs/BACKLOG.md`
  intocados.
- Los 7 `PROMPT-SESION-3*.md` preexistentes sin trackear siguen `??`,
  no se agregaron a esta sesión.

## Disciplina de alcance

Sin scope creep: no se tocó `src/` en ninguna forma, no se rediseñó
ningún contrato (LICENSE/NOTICE documentan el modelo existente, no
proponen uno nuevo), no se agregó `CODE_OF_CONDUCT.md` separado (fuera
de entregables — referencia breve dentro de CONTRIBUTING sí),
`docs/BACKLOG.md` no se tocó pese a la tentación de anotar "cerrar 34b"
en él. `README.es.md` se completó dentro del timebox (no quedó diferido).

## Próxima sesión

**34a-fix-1** — fix de `delete_tracks_bulk` (asimetría A1, P1): reemplazar
la llamada inline a `refill_zones()` por `_refill_enforce_and_save(...)`,
con manejo de `POST_ROUTE_PERSIST_FAILED` o código nuevo equivalente,
test de regresión con zona de cobre real + verificación de disco
post-save, gate GUI del DoD (toca pipeline de zonas). Hipótesis completa
ya en `docs/analisis/auditoria-contratos-bridge.md` §5.3. Precede a
**34c** (docs de arquitectura para colaboradores externos), para que 34c
documente la asimetría A1 ya resuelta.

**Sin bloqueantes pendientes para mergear a `master`** (rename a `main` y
resolución de `sesion-01` siguen siendo operación directa del arquitecto,
no bloquean este merge).
