# Sesión 34c — `docs/architecture-for-contributors.md`

**Rama:** `sesion/34c-architecture-for-contributors` (desde `master` @
`cd41338`). **Tipo:** ciclo documental — onboarding en inglés para
colaboradores externos, con topología y taxonomía de tools verificadas
contra código en HEAD, sin tocar código, tests, specs ni ADRs.
**Mergeada:** PR [#20](https://github.com/Gato513/kicad-mcp/pull/20),
2026-08-12T16:20:00Z, merge commit `2a4b0d3`.

## Resumen ejecutivo

Se publicó `docs/architecture-for-contributors.md` (487 líneas): mapa de
sistema, taxonomía de tools (R/W-IPC/W-COMPOSITE/W-SKIP/Infra), flujos de
datos representativos, tour del repo, guía de los 15 ADR, distinción
sesión/investigación/ADR y cross-references — todo verificado contra el
código en HEAD `cd41338`, no contra el drift Rust de `docs/arquitectura.md`
§3.1 (deferido por ADR-0009, ya adjudicado en el propio repo). Más 3
inserciones mínimas (`README.md`, `CONTRIBUTING.md`, `docs/INDEX.md`).

El ciclo pasó por **4 rondas de revisión independiente de Codex** sobre el
mismo hallazgo (MAJOR-1: la definición de W-COMPOSITE prometía persistencia
incondicional también para `route_board`, que en realidad la condiciona a
`refill=True` + zonas existentes + recarga exitosa del editor). Cada
corrección fue dirigida, acotada a una oración del mismo callout, y
autorizada explícitamente por el arquitecto antes de ejecutarse — sin
reabrir el commit inicial ni tocar código/tests. Cerrado: **APROBAR**,
`OBJETIVO_CUMPLIDO_CON_DEUDA_NO_BLOQUEANTE`.

## Auditoría previa y ajustes

`auditoria-previa-34c.md`, veredicto `EJECUTABLE_CON_AJUSTES`, 10 ajustes
obligatorios ya integrados en la orden de ejecución (allowlist exacta de 4
archivos, contenido obligatorio de 8 secciones, criterios de aceptación
A1-A12 reconciliados, rama única R-A con R-C como aborto controlado). Sin
reconsulta a ChatGPT en este ciclo. Sin gap que requiriera escalar a
decisión de Gato durante la ejecución inicial — sí las hubo después, en la
revisión (ver más abajo).

## Rama elegida: R-A

Abort branch R-C **no se activó**. La contradicción aparente entre
`docs/arquitectura.md` §3.1 (Rust core + bridge separado) y el código
(Python single-process) ya está adjudicada dentro del repo por ADR-0009
(`aceptado`, ratificado 2026-07-11, con tabla de latencia medida: 89% de
una mutación es espera IPC/UI de KiCad, un core Rust atacaría <0.3% de
eso). `docs/arquitectura.md` §10 ya prescribe el MVP Python/FastMCP que
efectivamente se construyó. El nuevo documento cita ambas fuentes con su
alcance temporal y no toma partido.

## Contenido implementado (8 secciones, orden mandatado)

1. Executive summary.
2. System map — Mermaid, dos fronteras de proceso reales (cliente↔servidor
   stdio; bridge↔KiCad IPC), `kicad-cli`/Freerouting como subprocesos,
   escritura de esquemático vía `kicad-skip` (sin IPC).
3. Tool taxonomy — R/W-IPC/W-COMPOSITE/W-SKIP + **Infra** (quinta etiqueta
   de la auditoría, agregada porque sin ella `save_board`/
   `reload_board_from_disk` no clasifican; deviation declarada y
   confirmada con el arquitecto). Override de `delete_tracks_bulk` trazado
   a `pcb.py:1947` (`any(z.kind == "copper" for z in ...)`, guard de
   tablero completo, no geométrico) + `D-34a-fix-1.1`. Callout dedicado
   para `route_board` (agregado en la revisión, ver abajo).
4. Data flow — lectura, mutación PCB Familia A vía `@mutating_tool`
   (ADR-0014), excepción de `delete_tracks_bulk` (preámbulo después del
   early-return de `dry_run`), escritura de esquemático.
5. Repo layout — un directorio por línea, componentes internos a rutas de
   código reales, externos (KiCad, `kicad-cli`, `kipy`, `kicad-skip`,
   Freerouting) a interfaz/dependencia.
6. ADR guide — tabla de los 15 ADR (0000-0013 desde `DECISIONES.md`, 0014
   desde su propio archivo — ausente del índice formal, hallazgo
   pre-declarado #2, no corregido).
7. Sesión vs investigación vs ADR, alineado con `docs/INDEX.md`.
8. Cross-references con precedencia sin absolutismos.

## Revisión de Codex — 4 rondas sobre MAJOR-1

| Ronda | Commit revisado | Veredicto | Hallazgo |
|---|---|---|---|
| 1 | `50befb2` | APROBAR_CON_CAMBIOS | La tabla de taxonomía y el resumen de ADR-0012 prometían refill+enforce+save "unconditionally"/"always" para toda la categoría W-COMPOSITE, incluyendo `route_board` — que en el código sólo corre ese bloque bajo `refill and zones_existentes > 0 and reloaded is True` (`pcb.py`). |
| 2 | `ef347eb` | OBJETIVO_NO_CUMPLIDO_POR_EVIDENCIA / BLOQUEAR | La reparación agrupó el caso de fallo de `reload_board_from_disk` junto a los casos de éxito silencioso (`refill=False`, editor cerrado, proyecto cruzado). En realidad esa falla puntual **no** retorna éxito: eleva `POST_ROUTE_REFILL_SKIPPED` vía la rama `refill_broke_contract` (`pcb.py:3087-3098`). |
| 3 | `4a7c950` | OBJETIVO_NO_CUMPLIDO_POR_EVIDENCIA / BLOQUEAR | La reformulación seguía sin las dos precondiciones reales: `refill_skipped_reason` sólo se asigna dentro de `elif refill and zones_existentes > 0:` (`pcb.py:2894`) — fuera de esas dos condiciones, una recarga fallida deja `refill_skipped_reason=None`, `refill_broke_contract=False`, y la llamada retorna éxito sin el raise. |
| 4 | `fe55cae` | APROBAR — `OBJETIVO_CUMPLIDO_CON_DEUDA_NO_BLOQUEANTE` | Cerrado. El documento ahora limita `POST_ROUTE_REFILL_SKIPPED` exactamente al caso `refill=True` + `zones_existentes>0` + recarga fallida sobre el target correcto. |

Cada ronda 2-4 fue una **corrección dirigida y excepcional**, autorizada
explícitamente por el arquitecto (2026-08-12) antes de ejecutarse, con
alcance declarado de antemano (una oración del mismo callout, sin código,
sin tests, sin archivo adicional) — no un loop de auto-corrección abierto.
Entre la ronda 1 y la 2, Claude Code verificó cada hallazgo directamente
contra `pcb.py` antes de aceptar la corrección; en ningún caso se aplicó
un fix sin confirmación mecánica previa.

## Hallazgo nuevo, registrado y explícitamente NO investigado

Durante la verificación de la ronda 4, se observó que las ramas
`"editor_closed"`/`"cross_project"` de `refill_skipped_reason`
(`pcb.py:2902`, `:2904`) parecen código inalcanzable: `zones_existentes >
0` (`:2778`) ya implica `is_target_open`, por lo que dentro del `elif` que
las asigna (`:2894`), `reloaded` distinto de `True` implica siempre
`reload_error is not None` (`:2900`, `"reload_failed"`). No afecta el
comportamiento observable que el documento describe ni el fix de la ronda
4. Por instrucción explícita del arquitecto, **queda fuera de 34c**: no se
investigó la causa, no se propuso fix, no se mezcló en el PR. Registrado
como posible deuda de código para decisión de un ciclo futuro.

## Tests y gates

- `uv run pytest -m "not integration and not integration_gui and not
  integration_gui_slow"`: **408 passed, 78 deselected** — repetido después
  de cada corrección (rondas 1 y 2), sin cambios; no repetido en las
  rondas 3-4 por ser delta exclusivamente documental sobre evidencia ya
  verde.
- `uv run ruff format --check`: verde, 90 files already formatted.
- `git diff --check`: limpio en cada commit y en el rango acumulado
  `cd41338..HEAD`.
- Sin gate GUI: el ciclo no toca el pipeline de zonas/keepouts en código,
  sólo lo describe.

## Disciplina de alcance

`git diff cd41338..HEAD --stat` confirmado en cada ronda: exactamente los
4 archivos de la allowlist original en las 5 commits del ciclo —
`docs/architecture-for-contributors.md` (nuevo), `README.md`,
`CONTRIBUTING.md`, `docs/INDEX.md`. Sin código, sin tests, sin specs, sin
ADRs, sin `docs/BACKLOG.md`/`docs/DECISIONES.md`/`docs/CONTEXT.md`/
`docs/arquitectura.md` tocados en ningún commit — todos explícitamente
prohibidos por la orden de ejecución. Push, PR y merge quedaron reservados
al arquitecto en todo momento; se ejecutaron sólo tras autorización
explícita (2026-08-12) y con el SHA exacto (`fe55cae`) fijado de antemano
para el PR, sin agregar commits después de esa autorización.

## Commits (5, sobre `cd41338`)

- `50befb2` — docs: agrega architecture-for-contributors.md (ciclo 34c)
- `ef347eb` — docs: corrige garantía incondicional de W-COMPOSITE para
  route_board (34c, revisión Codex)
- `4a7c950` — docs: separa el fallo de reload_board_from_disk del éxito
  silencioso en route_board (34c, corrección dirigida autorizada)
- `fe55cae` — docs: agrega las dos precondiciones de
  POST_ROUTE_REFILL_SKIPPED (34c, corrección dirigida autorizada)
- `2a4b0d3` — Merge pull request #20 (mergeado por el arquitecto)

## Publicación

PR #20 (`https://github.com/Gato513/kicad-mcp/pull/20`), base `master`,
head `fe55cae` exacto — sin commits agregados entre la autorización de
publicación y la apertura del PR. Mergeado por el arquitecto. Local
`master` sincronizado por fast-forward `cd41338..2a4b0d3` sin conflictos;
rama de trabajo `sesion/34c-architecture-for-contributors` borrada
localmente tras confirmar el merge.

## Próxima sesión

Sin bloqueantes. Candidatos abiertos para un ciclo futuro, a decisión del
arquitecto: la posible rama inalcanzable de `refill_skipped_reason`
(arriba); los 3 hallazgos fuera de alcance pre-declarados en la orden de
34c (`auditoria-contratos-bridge.md` §6 obsoleto, ADR-0014 ausente del
índice de `DECISIONES.md`, drift Rust de `docs/arquitectura.md` §3.1); y
los 6 hallazgos nuevos registrados en el commit `50befb2` (docstrings de
paquete que aún describen un MVP solo-lectura, conteo de sesiones
desactualizado en `docs/INDEX.md`, etc.) — ninguno bloqueante, ninguno
corregido en este ciclo.
