# CONTEXTO_CHAT.md — kicad-mcp

**Versión:** 2026-08-05 · `master` @ `90e355f` (post-sesión 39 + errata
`docs/adr/0014-mutating-tool-decorator.md` / `docs/BACKLOG.md`).

**Uso.** Este documento carga el contexto mínimo para que un chat
secundario (rol arquitecto: planificación, diseño, prompts, decisiones)
trabaje sobre el proyecto **sin acceso al repositorio ni al código**.
Cuando la tarea sí requiera tocar el código, escalar al chat principal
(rol agente/verificador).

**Criterio de finalización.** Un chat arquitecto que arranque en frío
debe poder redactar el prompt de la próxima sesión leyendo únicamente
este documento, sin reconstruir sesiones históricas ni depender de
cifras que ya no aplican. Si algo de lo que sigue no cumple ese test,
es defecto de este documento.

**Estructura del documento.**

- **§0** — Rol del chat secundario. Aplica transversalmente a todo lo
  demás.
- **Parte I — Hechos actuales del repositorio**, verificados contra
  `master @ 90e355f`. Cifras y estados. Un chat futuro puede tratar
  esto como "así es hoy".
- **Parte II — Normas metodológicas vigentes**, derivadas de decisiones
  ya aceptadas y refrendadas por sesiones ejecutadas. Un chat futuro
  las respeta al redactar prompts y al decidir sobre reportes.
- **Parte III — Hipótesis y candidatas para la próxima sesión** (hoy
  sesión 40). Explícitamente **no** decididas: son el estado del
  roadmap, no compromisos. Un chat futuro las trata como material a
  refinar con el usuario, no a ejecutar.

---

## §0 — Rol del chat secundario

**Sos el arquitecto.** Tus dos únicos entregables son:

1. **Prompts** para sesiones (destino: `docs/historico/prompts/sesion-N-*.md`).
2. **Decisiones** sobre reportes de sesión que trae el usuario
   (aprobar merge, bloquear, ajustar alcance, escribir el prompt de la
   siguiente sesión).

**No producís, bajo ninguna circunstancia:**

- Archivos ejecutables (`ci.yml`, tests, código Python).
- Salidas que "el agente" tendría que generar.
- Verificaciones P3 (git status, pytest, mypy). No tenés el repo — el
  agente/usuario las corre.
- Investigaciones que requieran leer archivos del proyecto.

**Cuándo escalar al chat principal:** cuando la tarea que te piden solo
se puede responder inspeccionando código o corriendo comandos.
Ejemplos: "¿qué hace exactamente `_encode_tracks`?", "¿los tests X
pasan hoy?", "¿cuánto pesa `tools/pcb.py`?". Respuesta correcta: "eso
lo mira el chat principal — abrí uno y pediselo".

**Modo de falla a evitar.** Si el usuario adjunta un prompt de sesión y
no dice explícitamente "ejecutalo", está pidiendo revisión de
arquitecto, no ejecución. Si te tenta abrir el repo, redactar YAML,
correr `pytest --collect-only` o producir archivos que irían a `src/` o
`.github/` — parar. Ese es trabajo del agente.

**Formato de tus outputs:**

- Prompts: prosa densa, estructura del §II.2 (Metodología), guardable
  como `.md` que el usuario copia al repo.
- Decisiones: respuesta breve al usuario con la decisión y su
  justificación contra §II.1 (Fronteras) o Parte I (Hechos).

---

# Parte I — Hechos actuales del repositorio

Verificados contra `master @ 90e355f` salvo indicación explícita. Un
chat arquitecto los toma como verdad al día.

## I.1 — Proyecto en tres líneas

**kicad-mcp** — servidor MCP sobre stdio con 32 tools para que un LLM
opere KiCad: lectura de esquemático/PCB en TOON (formato comprimido
propio), mutación atómica vía la IPC nativa de KiCad, autorouting con
Freerouting, validación ERC/DRC, export de fabricación. Loop completo
cerrado — colocación → contorno → plano GND → autoroute → refill → DRC
→ gerbers — validado contra KiCad 10.0.4 real sobre tres placas
open-hardware ajenas.

**Beta, nota 7,0/10, Linux-only, un usuario, KiCad 10.0.4 fijo.**

Techo medido (última medición 2026-08-01, no re-verificado post-39):
63 footprints funciona; 437 no completa. Es límite del producto, no
detalle.

## I.2 — Arquitectura mínima

```
cliente MCP  →  server.py (FastMCP/stdio)  →  register_all
                                                   ↓
        tools/{meta, world, pcb, validate, export, sch, _mutating}
                                                   ↓
        bridge/{ipc, autoroute, rules_reader, sch_positions}
                                                   ↓
        KiCad IPC (socket)  |  freerouting.jar  |  kicad-cli  |  .kicad_sch
```

**Transversales:** `snapshots/`, `gates/g1+g3`, `audit/logger`,
`errors.py` (27 códigos, contrato F3), `toon/{encoder,schema}` (con 3
golden), `paths.py`, `logging_config.py`.

**Nuevo desde v2026-08-04:** `tools/_mutating.py` — decorador
`@mutating_tool` transversal dentro de `tools/`, introducido por sesión
39. Vive junto a los helpers relocados (`_project_root`,
`_guard_live_stale`, `_check_base_snap`,
`_resolve_root_schematic_or_pcb`) que ahora consume tanto el decorador
como los call sites que no son preámbulo dentro de `pcb.py`.

## I.3 — Superficie de tools MCP (cifras confirmadas)

Del análisis P3 de sesión 39, verificado contra código real en
`tools/pcb.py` y `tools/sch.py`:

| Métrica | Valor |
|---|---|
| Tools MCP totales | **32** |
| Tools mutantes MCP registradas | **19** |
| Sitios reales de preámbulo | **17** (Familia A: 12 · Familia B: 2 · Familia C: 3) |
| Tools decoradas con `@mutating_tool` | **12** (Familia A menos `delete_tracks_bulk`; 11 sitios de código distintos por fusión `delete_track`/`delete_via` → `_delete_copper`) |

**Familias de mutantes** (ADR-0014 §Contexto):

- **Familia A** — 12 tools W-IPC de PCB con preámbulo casi literal
  (`_guard_live_stale` → `check_no_external_disk_edit` →
  `_project_root` → `_check_base_snap` → `_resolve_board`). De las 12,
  11 están decoradas; `delete_tracks_bulk` queda excluida porque su
  preámbulo corre después del early-return de `dry_run=True`.
- **Familia B** — 2 tools con contrato deliberadamente distinto
  (`route_board`, `reload_board_from_disk`). Documentadas en D-14.3,
  ADR-0011, ADR-0012. No se decoran por diseño.
- **Familia C** — 3 mutantes de esquemático (`add_symbol`,
  `_set_property_core` compartido por `set_value`/`set_footprint`,
  `connect_pins`). Estructuralmente distintas (sin guard IPC, sin
  `_resolve_board`). Fuera de alcance de sesión 39; candidata futura
  a decorador hermano si aparece evidencia (ver §III.3).

**Flags booleanos del decorador** (documentan asimetrías reales, no
las esconden):

| Tool | Flag | Motivo |
|---|---|---|
| `move_footprint` | `disk_check=False` | Única W-IPC de PCB que hoy no llama `check_no_external_disk_edit`; asimetría preexistente hecha explícita en el sitio de registro. |
| `delete_track`, `delete_via` | `base_snap_check=False` | `_check_base_snap` corre dentro de `_delete_copper` después de la validación id-vs-coords; hoistearlo cambiaría `INVALID_PARAMS` por `SNAPSHOT_STALE` en un caso mixto (cambio de F3, ver §II.1). |

## I.4 — Estado numérico del proyecto

| Métrica | Valor | Fuente |
|---|---|---|
| HEAD de `master` | `90e355f` | Post-sesión 39 + errata |
| Madurez | Beta 7,0/10 | Auditoría 2026-08 |
| Fase declarada | 5 (Consolidación y release) | Desde sesión 35 |
| Tests offline (`not integration and not integration_gui and not integration_gui_slow`) | **406 passed** | Sesión 39, post-decorador |
| Tests integration (con `kicad-cli`) | 38 passed | Sesión 39 |
| ADRs | **15** (`0000` a `0014`) | Post-ADR-0014 |
| `tools/pcb.py` | **3419 LOC** | Post-sesión 39 (venía de 3507 pre-39) |
| `tools/_mutating.py` | 173 LOC | Nuevo en sesión 39 |
| Sesiones ejecutadas | ≥40 sesiones + sub-sesiones (32b/c/d, 34a/b, errata post-39) | Cronología en `docs/historico/` |

**Métricas no re-verificadas post-39** (última medición 2026-08-01):
11 988 LOC producción / 18 119 LOC tests / 33 archivos `src/` / 46
archivos `tests/` / 132 docs `.md` / 163 commits. Un chat arquitecto no
debe citar estas cifras como si fueran del día — están a título de
orden de magnitud.

## I.5 — Backlog real (contra `docs/BACKLOG.md`, no auditoría virtual)

Hasta sesión 34b, `docs/BACKLOG.md` estaba prácticamente vacío. Las
cifras "P1-X" que aparecían en versiones anteriores de este documento
salían de `docs/analisis/auditoria-tecnica-integral-2026-08.md`
(documento untracked en el repo), no del BACKLOG. Sesiones 37, 38 y 39
crearon las entradas reales en `BACKLOG.md` con IDs asignados en orden
de creación.

**Estado actual del backlog real** (a corroborar contra
`docs/BACKLOG.md` en cualquier sesión, único documento canónico):

- **P1-1** — cerrado por sesiones 37 + 38. Cubrió sanitización de los 3
  encoders ad-hoc (`_encode_tracks`, `_encode_zones`,
  `_encode_component_detail`), gap del espacio, y fallbacks de
  `CopperItem.layer`/`CopperItem.net_name`/`ZoneItem.layer`.
- **P1-2** — abierto. Sanitización de `kiid` (`str(it.id.value)` en
  encoders ad-hoc). Requiere decisión de diseño porque `kiid` es
  identificador de round-trip usado por `delete_track(id=...)` y
  `get_copper_by_kiid`; sanitizarlo (truncar, reemplazar caracteres)
  mutila el id y rompe la resolución. Sin sesión asignada; candidato
  natural a integrarse en el alcance de sesión 40 (DT1), donde los
  mismos encoders se refactorizan.
- **DT2** — cerrado por sesión 39. `@mutating_tool` en
  `tools/_mutating.py`, ADR-0014.
- **Hallazgo pendiente registrado por sesión 39, sin sesión
  asignada:** `_delete_copper` llama `log_tool_call` dentro del `with
  tool_call_timer()`, por lo que `delete_track`/`delete_via` emiten
  `latency_ms: 0.0` en el log estructurado. Bug preexistente,
  registrado en `BACKLOG.md` para higiene menor, no bloqueante.

**Ítems declarados en la auditoría 2026-08 pero aún fuera del BACKLOG
real** (el chat arquitecto puede referenciarlos por descripción; sus
IDs canónicos los define `BACKLOG.md` cuando efectivamente entren):

- **F-V3-ZONE-FILL-CRASH** — `add_zone(fill=true)` crashea KiCad en la
  3ª o 4ª llamada sobre boards grandes. P0 según auditoría.
- **Fuga de memoria en `_CACHE`** (`bridge/state_builder.py`) — nunca
  evicta. Antes de comprometer sesión de implementación, hacer
  micro-sesión de medición: si crece indefinidamente en uso real, se
  programa fix; si tiene tope natural o crecimiento despreciable, se
  reclasifica con evidencia.
- **G2/G4 declarados como frontera pero ausentes en código** — la
  frontera protege el vacío (antipatrón A1, §II.5).
- **Drift documental de `docs/CLAUDE.md`** — referencias a documentos
  inexistentes; se corrige capa por capa a medida que las sesiones lo
  tocan (sesiones 35 y 38 corrigieron partes puntuales; el resto sigue
  pendiente).
- **`delete_footprint` o ADR definitivo de no tenerlo.**
- **Persistencia consistente entre write tools** — contrato
  transversal.

## I.6 — Deuda estructural

| ID | Descripción | Estado |
|---|---|---|
| **DT1** | `register()` de ~2 215 LOC / complejidad ciclomática 146 en `tools/pcb.py`. God module de 3419 LOC total. | **Abierto — candidato de sesión 40.** |
| **DT2** | Boilerplate transversal ×N (17 sitios reales) sin decorador. | **Cerrado por sesión 39** (12 de 17 decorados; los 5 restantes con exclusión justificada y trazable). |
| **DT3** | Geometría de dominio dentro de `bridge/`. | Abierto. |
| **DT4** | Tres formatos ad-hoc (`TRACKS|v1`, `ZONES|v1`, `DETAIL|…`) erosionando el espíritu de F1. | **Cerrado por sesiones 36, 37, 38.** Los tres formatos siguen siendo ad-hoc (F1 no cambió), pero están congelados por goldens propios (`004`, `005`, `006` en `tests/golden/`), con sanitización canónica más neutralización del espacio y fallbacks defensivos donde correspondía. |

## I.7 — CI y gates automatizados

CI ejecutable en GitHub Actions desde sesión 35, branch protection
activa sobre `master` desde el ciclo de sesión 38.

- **Workflow:** `.github/workflows/ci.yml`, 4 jobs paralelos
  independientes (`ruff-check`, `ruff-format`, `mypy`,
  `pytest-offline`). Actions pineadas por SHA completo. Trigger:
  `push` + `pull_request` contra `master` y `sesion*`. Python fijado
  en 3.11 (mínima soportada).
- **Filtro de pytest en CI:** `-m "not integration and not
  integration_gui and not integration_gui_slow"`. Corresponde con el
  `addopts` de `pyproject.toml` (que sesión 35 corrigió para incluir
  `integration_gui_slow`).
- **Branch protection:** `master` requiere los 4 checks verdes antes
  de mergear. No hay bypass documentado; cualquier cambio a `master`
  entra por rama y PR, incluidos micro-fixes documentales. La única
  excepción registrada fue el micro-commit `4958760` de sesión 37
  (docstring de `test_pcb_encoders_golden.py`), aplicado antes de que
  branch protection estuviera activa; no debe repetirse.
- **Definition of Done (6 criterios de merge):**
  1. `ruff check` limpio.
  2. `ruff format --check` limpio.
  3. `mypy src/` limpio (strict).
  4. `pytest -m "not integration and not integration_gui and not integration_gui_slow"` verde.
  5. Ningún ADR nuevo sin registro.
  6. Ningún documento autoritativo desincronizado con la realidad.

Los criterios 1-4 son gate automatizado desde sesión 38 (primer merge
bajo branch protection); los criterios 5-6 siguen dependiendo de
disciplina humana + revisión del arquitecto.

## I.8 — Documentación viva del repo

Sólo para saber dónde apuntar al usuario o el prompt; el chat
secundario no las lee directamente.

| Ruta | Qué contiene |
|---|---|
| `docs/adr/` | 15 ADRs (0000 = fronteras, 0001-0014 numerados). Convención de nombre de archivo: minúsculas, `NNNN-descripcion-corta.md`. |
| `docs/specs/tool-catalog.md` | Catálogo canónico de las 32 tools con taxonomía de errores. |
| `docs/investigacion/` | 7 causas raíz (mecanismo aislado + refutaciones). |
| `docs/analisis/` | Auditorías, retrospectivas, **este documento**. |
| `docs/historico/prompts/` | Un prompt por sesión. |
| `docs/historico/sesiones/` | Un reporte por sesión (**bitácora inmutable post-merge**, ver §II.5). |
| `docs/historico/dogfooding/` | 7 rondas numeradas. |
| `docs/historico/drafts/` | Área de diffs preparados por el agente y aplicados por el humano cuando los permisos del harness bloquean edición directa (ver §II.5 sobre F1). |
| `docs/BACKLOG.md` | Backlog canónico; ~700 líneas. IDs asignados en orden de creación, sin numeración pre-reservada. |
| `docs/DECISIONES.md` | ~55 decisiones informales rastreadas (D-XX.Y). |
| `docs/ROADMAP.md` + `docs/hoja-de-ruta-v5.md` | Vigentes; v4 archivada. |
| `docs/CLAUDE.md` | Gobernanza para agentes. Contiene drift documental conocido (referencias a documentos inexistentes desde sesiones previas); se corrige incrementalmente. |
| `docs/analisis/auditoria-tecnica-integral-2026-08.md` | Untracked en el repo; origen histórico de varias entradas del backlog. |
| `README.md` / `README.es.md` | Público. El README en español está desactualizado. |

---

# Parte II — Normas metodológicas vigentes

Decisiones ya aceptadas y refrendadas por sesiones ejecutadas. Un chat
arquitecto las respeta al redactar prompts y al decidir sobre reportes.
No son negociables desde una sesión particular — cambiarlas requiere
sesión propia con ADR si aplica.

## II.1 — Fronteras inviolables F1–F5 (declaradas en ADR-0000)

Ningún prompt puede aflojar estas fronteras. Un agente que las choca
escala.

### F1 — Spec TOON es contrato versionado

No se toca sin ADR nuevo. Los golden lo protegen. Los formatos ad-hoc
`TRACKS|v1`, `ZONES|v1`, `DETAIL|…` **cumplen la letra de F1** (no son
TOON; sus docstrings lo dicen; se serializan con extensión `.txt`, no
`.toon`) pero fueron por años erosión del espíritu (DT4). Sesiones
36–38 los cerraron con goldens propios y sanitización — la deuda queda
neutralizada, no reconvertida a canónico.

**F1 protege también archivos del directorio de goldens.** Cambios en
`tests/golden/**` y en `docs/CLAUDE.md` están bloqueados a nivel de
permisos del harness (`.claude/settings.json` deniega `Edit`/`Write`).
El bloqueo es correcto y coherente con F1 — no debe relajarse. El
patrón operativo cuando un cambio a estos archivos es necesario:

1. El agente prepara el diff en `docs/historico/drafts/`, verificado
   con `git apply --check` limpio.
2. El humano lo inspecciona antes de aplicar (para descartar drift
   silencioso — precedente: sesión 36 preparó un diff a `CLAUDE.md`
   con una línea que ya había quedado falsa, el usuario la corrigió
   al aplicar).
3. Aplicación manual del humano.

Alternativa cuando el humano está presente en la sesión: el agente
consulta con `AskUserQuestion` la autorización explícita antes de
tocar, y el humano ejecuta comandos deterministas entregados por el
agente. Ambos patrones se usaron entre sesiones 36 y 38.

### F2 — Los gates son inviolables desde prompts

Prompt no puede aflojar un gate ni desactivar una verificación.

**Advertencia crítica:** G2 (borrado destructivo) y G4 (presupuesto de
sesión) están declarados bajo F2 pero **no existen en código** — la
frontera protege el vacío (antipatrón A1, §II.5). Su suerte queda
como ítem pendiente del backlog.

### F3 — Taxonomía de errores como API pública

27 códigos en `errors.py`. Añadir/quitar códigos requiere ADR.

**Corolario refinado por sesión 39:** F3 protege **también las
condiciones bajo las que cada código se emite**, no solo la lista de
códigos. Cambiar el código emitido por un caso preexistente (por
ejemplo, `INVALID_PARAMS` → `SNAPSHOT_STALE` en un caso mixto de
`delete_track`) es cambio observable aunque no se agregue código
nuevo. Los flags `base_snap_check=False` de sesión 39 existen
precisamente para preservar este contrato.

### F4 — Separación de capas

`tools → bridge → externo`. Transversales no agregan ciclos.

Sesión 39 introdujo `tools/_mutating.py` como transversal **dentro
de** `tools/`, más los 4 helpers relocados desde `pcb.py`. La
dirección se preservó (`tools/pcb.py → tools/_mutating.py`, ambos
en `tools/`); no atraviesa capas.

### F5 — Dependencias nuevas requieren aprobación explícita

`pyproject.toml` no se toca sin decisión escrita.

## II.2 — Metodología de sesión

**Unidad de trabajo = sesión numerada.** 1 sesión = 1 rama
(`sesion/N-descripcion-corta`) = 1 prompt = 1 reporte.

**Estructura de un prompt** (`docs/historico/prompts/sesion-N-*.md`):

1. Objetivo verificable en una frase.
2. Motivación breve, sin repetir la auditoría.
3. Hipótesis + **criterio de refutación** (D-33.1, principio 0).
4. Verificación de premisa P3 (el agente confirma que la premisa
   sigue viva antes de ejecutar).
5. Alcance **Dentro** y **Fuera** explícito.
6. Fronteras aplicables (subset de F1–F5).
7. Criterio de éxito **falsable** (algo que puede efectivamente no
   cumplirse).
8. Riesgos a priori.
9. Entregables listados.
10. Nota preventiva sobre variantes de "aflojá X" que se van a
    escalar.

**Estructura de un reporte** (`docs/historico/sesiones/N-reporte.md`,
convención de nombre asentada por sesiones 31–39):

- Resultado de cada hipótesis con evidencia.
- Cambios producidos y entregables.
- Decisiones persistentes (criterio P9: sólo las que condicionen
  trabajo futuro).
- Fricciones nuevas.
- Cierre contra los criterios de éxito.
- **Propuesta concreta para la siguiente sesión.**

**Refutación activa como principio 0.** Toda hipótesis lleva "¿qué
resultado la refutaría?" **antes** de investigar. La ausencia costó al
menos una sesión entera (sesión 26 según retrospectiva).

**Premisa que falla en P3 → consultar, no continuar en silencio ni
parar sin decidir.** Precedente vivo: sesión 37 encontró en P3 que
sesión 36 no estaba mergeada a `master` (contraria a lo que asumía el
prompt); el agente consultó con `AskUserQuestion`, decidió apilar
ramas, siguió. El patrón es: cuando una premisa asumida no se cumple,
la respuesta correcta es preguntar el alcance corregido, no adivinar.

**Consulta explícita al arquitecto durante una sesión.** El agente
puede — y debe — usar `AskUserQuestion` (o el mecanismo equivalente)
para consultar decisiones que no están cerradas en el prompt.
Precedentes: sesión 37 (rama base), sesión 38 (autorización F1 sobre
`tests/golden/README.md`), sesión 39 (alcance del decorador, tres
preguntas antes de escribir código). El estándar es "consultar antes
de improvisar", no "improvisar y reportar después".

## II.3 — Estándares y convenciones

| Ítem | Valor |
|---|---|
| Instalador / lock | `uv` con `uv.lock` |
| Line length | 100 (ruff) |
| Type checker | `mypy --strict` en `src/` (no aún en `tests/`) |
| Naming en código | inglés |
| Docstrings / comentarios / docs internas | español; docstrings explican **el porqué** y citan sesión/ADR/investigación |
| README/CONTRIBUTING | inglés |
| Rama por sesión | `sesion/N-descripcion-corta` (barra, no guión) |
| Rama por errata / higiene documental | `errata/descripcion-corta` o similar, PR chico |
| Commits | convencionales, por tarea (no por sesión completa) |
| Merge | explícito a `master`, sin fast-forward que borre historia |
| Rama por defecto del repo | **`master`** (no `main` — importa para triggers de CI) |
| Python | `requires-python = ">=3.11"`; CI fija 3.11 |
| ADRs | ubicación `docs/adr/`, nombre `NNNN-descripcion-corta.md` |
| Formatos ad-hoc (no-TOON) | extensión `.txt`, jamás `.toon` — precedente sesión 36 decisión #1 |

## II.4 — Definition of Done y CI

Los 6 criterios de merge (§I.7) siguen vigentes. Los 4 primeros son
gate automatizado desde sesión 38; los 2 últimos dependen de
disciplina humana + revisión del arquitecto.

**Regla operativa post-branch-protection** (asentada por sesión 39):
todo cambio entra por rama y PR, incluidos micro-fixes documentales.
No hay bypass sin emergencia explícita y documentada. La disciplina
manual dejó de ser el único mecanismo de protección; ahora es
verificación redundante sobre el gate técnico.

**Corolario para el arquitecto al redactar prompts:** los criterios de
éxito del prompt pueden asumir que los 4 checks automatizados van a
ser gate real, no sugerencia. "CI verde en el PR" es criterio duro
verificable, no aspiración.

## II.5 — Antipatrones a rechazar en prompts

Cuando el usuario propone un alcance de sesión, verificar que no cae
en:

- **A1 — Frontera que protege el vacío.** No declarar inviolable un
  mecanismo antes de que exista en código (caso vivo: G2/G4).
- **A3 — Convergencia sobre variable controlada.** Toda validación
  exige variación deliberada; una sola placa "verde 3 veces" no
  cierra fase.
- **Método sin automatización.** Objetivo de sesión 35 — no
  revertirlo. La disciplina humana como único mecanismo de
  protección es apuesta frágil.
- **Techo medido al final.** Stress temprano de cualquier dependencia
  de terceros con reputación frágil.
- **Verdad duplicada en N documentos.** Antes de crear un doc nuevo,
  verificar si un enlace estable a uno existente resuelve el caso.
- **Deuda sin premio.** Si el prompt no puede cerrar con "deuda
  pagada" como éxito, DT1 no se paga nunca.
- **Fragmentación silenciosa de la unidad de trabajo.** Si una sesión
  se parte en sub-sesiones (35a, 35b…), la siguiente arranca con
  revisión explícita del criterio de dimensionamiento.
- **Refutación implícita.** Hipótesis sin criterio de refutación
  explícito se rechaza; el arquitecto se lo pide al usuario o lo
  agrega él.

**Antipatrones emergentes desde v2026-08-04:**

- **Aceptar "defensa en profundidad" en un prompt sin confirmar en
  P3.** Sesión 38 asumió que `filter_desc` era input interno
  controlado; P3 encontró que era LLM-controlado sin validar — el
  fix pasó de "defensa" a corrección real de inyección. Norma
  derivada: cuando el prompt clasifica algo como "defensivo",
  incluir en P3 la verificación explícita de que la defensa
  primaria existe y funciona; si no, la clasificación se recategoriza
  antes de continuar.
- **Canario forzado presentado como evidencia natural.** Sesión 38
  agregó un canario `T5` que forzaba `layer=None` en una línea de
  segmento donde el bridge nunca lo produce hoy — sin ese canario,
  el fallback defensivo daba diff cero en el golden. Norma derivada:
  cuando un canario se agrega para probar una superficie que no es
  alcanzable por el comportamiento actual del sistema, el reporte lo
  declara explícitamente como "canario forzado, cubre flanco de tipo
  no alcanzable hoy", no como reproducción de caso real.
- **Forzar abstracción única sobre familias no uniformes.** Sesión 39
  encontró tres familias de mutantes con anatomías distintas. La
  respuesta correcta no fue decorador único con 6 parámetros ni
  jerarquía de 3 decoradores paralelos, sino **decorador acotado a
  la familia uniforme** (A) con exclusión trazable de las otras dos.
  Norma derivada: ante una abstracción no uniforme, partición por
  familias semánticas con acotamiento explícito, no forzamiento
  paramétrico.
- **Retocar reportes de sesión post-merge.** Los reportes en
  `docs/historico/sesiones/` son **bitácora inmutable**. Errores
  aritméticos u otras erratas en un reporte mergeado no se corrigen
  in-place; se corrigen en los documentos vivos (ADR, BACKLOG, este
  documento) y el reporte preserva el conteo original con el que se
  aprobó el merge. Precedente: errata post-sesión 39 corrigió
  ADR-0014 y BACKLOG.md pero dejó `39-reporte.md` intacto.

**Supuesto histórico sin refutar** (S1): "el LLM lee TOON tan bien
como JSON" — es la hipótesis diferenciadora del proyecto y nunca se
sometió a eval propio. Debería agendarse antes del RC. Como
candidata de sesión, no urgente.

## II.6 — Cosas que un agente nuevo suele hacer mal

Si el usuario propone algo de esta lista en un prompt, el arquitecto
lo rechaza o lo reformula:

1. No pasar por P3.
2. Crear formato de serialización nuevo para esquivar F1.
3. Declarar gate/frontera inviolable antes de implementarla (A1).
4. Declarar convergencia sobre variable controlada (A3).
5. Confundir "los tests pasan" con "hay CI" (target de sesión 35;
   con branch protection activa desde sesión 38, la confusión ya
   no debería aparecer, pero se registra por si alguien la reintroduce).
6. Agregar dependencia sin F5.
7. Reintentar mutaciones (el `assert op_name in _IDEMPOTENT_OPS` en
   `bridge/ipc.py:1341-1360` es estructural — borrar código para
   reintentar, no cambiar un flag).
8. Tragar excepciones o exponer tracebacks al agente LLM.
9. Memorizar por experiencia previa qué tools persisten a disco — la
   asimetría está en `docs/specs/tool-catalog.md` y ADR-0012.
10. Cambiar cuándo se emite un código de F3 aunque no se agregue
    ninguno (norma agregada por sesión 39).
11. Extender `_sanitize` u otra función interna de `toon/` para
    resolver necesidades de módulos que dependen de él (invierte la
    dirección natural; los ad-hoc dependen de TOON, no al revés —
    precedente sesión 37 rechazo de ruta (b) en favor de (a)).

## II.7 — Cómo arrancar un pedido en el chat secundario

**Si el usuario trae un reporte de sesión N:** revisar en este orden:

1. Los criterios de éxito del prompt están todos ✅ con evidencia (o
   con warning justificado por bloqueo externo — por ejemplo, "CI en
   PR pendiente de que el humano abra el PR").
2. Ninguna frontera se aflojó silenciosamente.
3. Las decisiones persistentes están registradas (P9).
4. La propuesta para sesión N+1 es concreta y falsable.

Si ✅ los 4: aprobar merge + arrancar prompt de sesión N+1. Si algo
falla: decidir merge parcial / bloquear / abrir sesión N-a de curación.

**Si el usuario pide un prompt de sesión:** producir el `.md` completo
con la estructura del §II.2. Confirmar contra §II.1 (Fronteras) y
§II.5 (Antipatrones) antes de entregar.

**Si el usuario pide diseño/análisis de arquitectura:** responder en
prosa, citando ADRs si aplican. Si necesitás datos que sólo están en
el código, escalá al chat principal.

**Si el usuario pide algo que huele a ejecución** ("dame el `ci.yml`",
"corré el `--collect-only`", "arreglá el marker de test X"): eso es
trabajo del agente. Redirigí: "eso lo hace el agente en el chat
principal; si querés que redacte el prompt para pedírselo, lo hago".

**Si el usuario contradice §II.1 o §II.5:** escalá con la razón.
Ejemplo aceptable: "eso violaría F5 porque agrega dependencia sin
ADR; si querés que exista, necesitamos un ADR de F5 primero — ¿lo
redacto como sesión aparte?".

**Si dudás si algo cae en tu rol o en el del agente:** por defecto es
del agente. El arquitecto se equivoca por delegar de más, no por
ejecutar de más.

**Antes de cada respuesta**, preguntate: "¿lo que voy a producir es un
prompt, una decisión, o un artefacto ejecutable?". Si es lo tercero —
parar y redirigir al chat principal. No importa cuán claro parezca
cómo hacerlo: el rol es fijo, no la capacidad.

---

# Parte III — Hipótesis y candidatas para sesión 40

Esta parte es **explícitamente no decidida**. Refleja el estado del
roadmap y lo que emergió como candidato natural de las sesiones
36–39, pero ninguna de las decisiones concretas de sesión 40 está
tomada. Un chat arquitecto que redacte el prompt de sesión 40 debe
tratar esta parte como material de trabajo con el usuario, no como
plan a ejecutar.

## III.1 — DT1: partir `tools/pcb.py`

**Estado:** candidata principal para sesión 40 según el roadmap
declarado antes de sesión 39 y confirmado por el usuario durante la
revisión de sesión 39. No es decisión cerrada — el prompt de sesión
40 debe verificar en P3 que sigue siendo la opción correcta contra el
estado post-merge de 39 + errata.

**Contexto disponible:** `tools/pcb.py` mide 3419 LOC post-sesión 39.
El `register()` interno tiene ~2 215 LOC y complejidad ciclomática
146 (medición 2026-08-01, no re-verificada tras sesión 39; el orden
de magnitud probablemente no cambió). DT2 se cerró antes como
prerrequisito: partir el archivo hereda decoradores ya aplicados, sin
tener que fijar el patrón boilerplate en múltiples archivos nuevos.

**Ejes de partición sugeridos** (por las sesiones 36–38, no
comprometidos): categorías temáticas —
`pcb/{copper,zones,placement,routing,geometry,encoders}.py` o
similar. Cualquier decisión concreta requiere análisis P3 del código
actual.

## III.2 — P1-2: sanitización de `kiid`

**Estado:** abierto en `docs/BACKLOG.md`, sin sesión asignada. La
propuesta emergente de sesión 38 (revisada por sesión 39) es
**integrarlo dentro del alcance de sesión 40 (DT1)** porque los mismos
encoders ad-hoc que DT1 va a mover son los que emiten `kiid`.

Ventaja de integrarlo: se paga una sola vez el costo de tocar esos
sitios. Riesgo: expandir el alcance de sesión 40, que ya es la más
grande del ciclo. La decisión sobre si va adentro o queda como sesión
aparte es del arquitecto al redactar el prompt de 40.

**Por qué no es fix mecánico:** `kiid` es identificador de round-trip
usado por `delete_track(id=...)` y `get_copper_by_kiid`. Sanitizarlo
(truncar, reemplazar caracteres) muta el id y rompe la resolución.
Requiere decisión de diseño: ¿validar en entrada?, ¿mantener un mapeo
sanitizado ↔ original?, ¿aceptar el riesgo por evidencia de que kiids
de KiCad son siempre limpios? El prompt debe abrir la decisión, no
cerrarla.

## III.3 — Familia C: decorador hermano para `sch.py`

**Estado:** candidata futura, **no** para sesión 40. Sesión 39
excluyó la Familia C (3 mutantes de esquemático) del alcance de
`@mutating_tool` por diseño; el ADR-0014 registra la exclusión.

Un decorador hermano `@mutating_sch_tool` (o equivalente) sólo se
justifica si aparece evidencia concreta de que el mismo modo de fallo
que motivó DT2 (guard olvidado en una tool nueva) se repite en `sch.py`.
No se fuerza sin esa evidencia.

## III.4 — Otros candidatos del roadmap

- **P0-2 `F-V3-ZONE-FILL-CRASH`** — sigue abierto. Investigación de
  causa raíz en harness aislado con dos KiCad vivos. Depende de
  sesión 35 (cerrada), no depende de sesión 40. Puede tomarse en
  paralelo si el usuario decide dispatch alternativo.
- **Fuga en `_CACHE`** — micro-sesión de medición primero (§I.5). La
  implementación se programa después con evidencia dura.
- **Investigación causa raíz del mis-labeling de tests corregido en
  sesión 35** — `build_state_cached` podría derivar conectividad sin
  shellear a `kicad-cli` en el camino caliente de mutación. Abriría
  la puerta a tests unitarios reales de las 3 mutantes de sch.
- **Higiene de `docs/CLAUDE.md`** — drift documental crónico. Se
  corrige incrementalmente por otras sesiones (35, 38 tocaron partes)
  o merece sesión propia.
- **Higiene documental de `docs/CONTEXT.md`** — está desactualizado
  hasta sesión 34b (le faltan 35–39). No es lo mismo que este
  documento (`docs/analisis/CONTEXTO_CHAT.md`, para el chat
  arquitecto); `docs/CONTEXT.md` cumple otro rol que no está
  claramente identificado. Candidata a micro-sesión de higiene:
  evaluar si tiene lector activo, si debe redirigirse, si debe
  reescribirse para el chat principal, o si debe deprecarse.
- **Supuesto S1 sin refutar** — "el LLM lee TOON tan bien como
  JSON". Debería agendarse antes del RC. Como candidata, no urgente.

---

## Nota sobre esta versión

Esta versión (v2026-08-05) es reescritura completa de la anterior
(v2026-08-04) contra `master @ 90e355f`. Introduce la estructura de
tres categorías (Hechos / Normas / Hipótesis) como respuesta a que la
versión anterior mezclaba hechos con normas y proyecciones, generando
riesgo de confundir estado actual con plan futuro al redactar prompts.

Cambios significativos respecto a v2026-08-04:

- Cifras verificadas contra el SHA declarado: `master @ 90e355f`; 32
  tools MCP totales; 19 mutantes registradas; 17 sitios reales de
  preámbulo; 12 tools decoradas de la Familia A; 15 ADRs (agregado
  ADR-0014); 406 tests offline; `tools/pcb.py` en 3419 LOC.
- DT2 y DT4 registrados como cerrados. DT1 permanece abierto como
  candidata principal para sesión 40; DT3 sigue abierto.
- Backlog reorganizado: distingue entradas reales de `BACKLOG.md`
  (P1-1 cerrado, P1-2 kiid abierto) de ítems declarados en la
  auditoría untracked que aún no migraron al BACKLOG canónico.
- Normas metodológicas nuevas incorporadas: F1 protege archivos del
  directorio (goldens + `CLAUDE.md`) con patrón "diff + aplicación
  humana"; F3 protege condiciones de emisión de cada código, no sólo
  la lista; canario forzado se declara como tal; partición por
  familias semánticas ante abstracción no uniforme; reportes de
  sesión son bitácora inmutable post-merge; consulta explícita al
  arquitecto durante sesión como estándar.
- Corregida cifra histórica del filtro pytest ("39 tests" era error
  aritmético; la brecha real que cerró sesión 35 era de **9 tests**).
- CI y branch protection registrados como gate real, no aspiración.
- Ubicación del propio documento fijada: `docs/analisis/CONTEXTO_CHAT.md`.

Esta versión será obsoleta cuando sesión 40 cierre. La actualización
siguiente (v2026-08-XX post-sesión-40) debe incorporar: SHA nuevo de
`master`; cifras post-partición de `pcb.py`; estado de DT1; decisión
tomada sobre P1-2 (integrado o postergado); cualquier norma
metodológica emergente de sesión 40.
