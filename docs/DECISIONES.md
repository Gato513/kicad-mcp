# Decisiones — kicad-mcp

Generado en la reorganización documental (2026-07-24), consolidado desde
`docs/historico/CONTEXT-v7.md` (post-sesión 24). Este documento indexa las
decisiones de arquitectura **vigentes**. No duplica el contenido de los ADR
ni del histórico — apunta a la fuente y resume el veredicto actual. Las
decisiones superadas por evidencia posterior se marcan como tales; su
razonamiento completo queda en `docs/historico/`.

---

## 1. ADR formales (`docs/adr/`)

Todas con estado **aceptado**, salvo que se indique lo contrario. Orden
cronológico; cada una es la fuente autoritativa de su tema.

| ADR | Título | Resumen de una línea |
|---|---|---|
| [0000](adr/0000-fronteras-inviolables.md) | Fronteras inviolables | F1–F5: specs/goldens, gates, códigos de error, versión KiCad, dependencias — no se tocan sin aprobación humana explícita. |
| [0001](adr/0001-transporte-y-alcance-mono-usuario.md) | Mono-usuario, transporte stdio | Sin multi-tenancy ni transporte remoto en el MVP. |
| [0002](adr/0002-versiones-de-kicad.md) | KiCad 10 objetivo, 9.0 mínimo | Sin KiCad 11/nightlies (refuerza F4). |
| [0003](adr/0003-gates-de-autonomia.md) | Gates de autonomía (G1–G5) | Backups, confirmación destructiva, budget de sesión — deterministas, no prompteados (refuerza F2). |
| [0004](adr/0004-economia-de-tokens.md) | Calibración de contexto | Defaults de refresh graduado, presupuesto TOON, política de re-sync. |
| [0005](adr/0005-linux-como-plataforma.md) | Linux como única plataforma | Sin soporte oficial macOS/Windows en el MVP. |
| [0006](adr/0006-sin-base-de-datos.md) | Sin base de datos | JSONL + backups en `.kicad-mcp/`, sin SQL/persistencia estructurada. |
| [0007](adr/0007-snapshots-vivos-mtimes-none.md) | Snapshots vivos, `mtimes=None` | Snapshot post-mutación in-memory no lleva mtimes de disco. |
| [0008](adr/0008-kipy-write-semantics-property-setter.md) | Semántica de escritura kipy | Mutar vía setter de property, nunca por asignación directa de campo. |
| [0009](adr/0009-port-rust-diferido-con-condiciones.md) | Port a Rust diferido | v0.4 condicional a evidencia de cuello de botella real (ver `historico/analisis/ANALISIS-ESTADO-Y-BACKLOG.md` §1.4 — el cuello es KiCad/IPC, no Python). |
| [0010](adr/0010-borrado-de-cobre-sin-gate-g2.md) | Borrado de cobre sin Gate G2 | `delete_track`/`delete_via` no disparan elicitation destructiva. |
| [0011](adr/0011-autorouting-route-board.md) | Autorouting con Freerouting | `route_board` delega ruteo a Freerouting headless, no al LLM. |
| [0012](adr/0012-route-board-persist-contract.md) | Contrato disco==memoria==`err_post` | Sesión 24: `route_board` mide DRC y persiste **después** de refill+enforce; fix de F-D4-02. Ver D-23.2 abajo. **Extendido en sesión 27** a `fill_zones` y `add_zone(fill=True)` — ADR-0012 sección "Extensión de alcance (sesión 27)". |

## 2. Decisiones informales vigentes (no formalizadas como ADR)

Origen: `docs/historico/CONTEXT-v7.md` y reportes de sesión. Se listan solo
las que siguen vigentes hoy; el detalle completo y su evolución cronológica
está en `docs/historico/CONTEXT-v7.md` §"Decisiones de arquitectura vigentes"
y en los reportes de sesión referenciados.

### Sobre lectura/escritura de PCB
- **D-V3.2**: TOON no crece con tracks/vías. Vista dedicada: `get_tracks(net=|bbox=|layer=)` con IDs estables.
- **D-V3.3**: selección de cobre por KIID (no por radio/coordenadas) en `delete_track`/`delete_via`.
- **D-V3.4 / D-V3.5**: `route_board` con contrato JSON enriquecido (route_ms, causas de nets bloqueadas, DRC pre/post); reglas del board (netclasses, edge clearance) viajan al DSN de Freerouting.
- **D-19.1**: Freerouting respeta `(plane)` del DSN como conectividad para el net dueño de la zona, **no** como exclusión para el resto de los nets. Contexto necesario para entender por qué el refill+enforce de ADR-0012 es imprescindible (sin él, otros nets podían enrutarse ignorando la zona GND).
- **D-19c.1**: nunca aplicar `add_keepout_zone` antes de un `route_board` autorruteado desde cero — bloquea nets sistemáticamente. Aplicar keepouts *después* del ruteo.
- **D-19c.2 / D-19d.1**: KiCad reasigna el net de una vía/track nueva al net del cobre físico bajo/cruzado (comportamiento de dominio, no bug). Cerrado en tool con verificación post-creación + `NET_ASSIGNMENT_MISMATCH`.
- **D-23.2 (ADR-0012)**: `route_board`, al terminar OK, garantiza disco == memoria == `err_post` reportado — ver ADR-0012 para el contrato completo.

**D-23.2 extendido (sesión 27):** contrato disco==memoria aplicado a
las tres tools:
- `route_board` (sesión 24, `POST_ROUTE_PERSIST_FAILED`).
- `fill_zones` (sesión 27, `POST_ZONE_PERSIST_FAILED`).
- `add_zone(fill=True)` (sesión 27, `POST_ZONE_PERSIST_FAILED`).

El campo `drc` del payload NO se agrega a `fill_zones`/`add_zone` — el
contrato aplica al núcleo (disco==vivo), no a la ergonomía. Estas dos
tools son baratas y frecuentes; agregar un `kicad-cli` post-operación
las encarece varios segundos por llamada. El llamador que quiera DRC
puede invocar `run_drc()` por su cuenta con contrato ahora fiel — que
es el efecto real del fix.

Códigos `POST_ROUTE_PERSIST_FAILED` y `POST_ZONE_PERSIST_FAILED`
coexisten temporalmente. Semánticamente equivalentes; el llamador ya
sabe qué tool invocó. Unificación en código compartido queda como
deuda diferida P4 post-Fase 3 (ver `BACKLOG.md`).

Documentación autoritativa: ADR-0012 sección "Extensión de alcance
(sesión 27)".

### Sobre testing / verificación
- **D-24.1 (patrón fixture helper runtime)**: preferir helpers que deriven
  bboxes/coordenadas en runtime desde el estado real del board
  (`bridge.list_zones()`, `get_world_context()`, etc.) sobre directorios
  estáticos con coordenadas hardcodeadas. Nace de que la copia de trabajo
  `/tmp/gui-test-project` puede tener origen absoluto distinto del fixture
  crudo (mismo tamaño, desplazado) — hardcodear generaría tests flakey a
  mediano plazo. Ejemplo vivo: `tests/test_pcb_session24_route_board_persist_gui.py`.
- **D-24.2 (baseline dinámico + delta)**: para verificar que un cambio no
  introduce errores nuevos en placas con errores DRC preexistentes (ej.
  courtyards, edge clearance del outline), preferir "baseline dinámico +
  delta" sobre "allowlist estática escrita a mano". Metodología: `run_drc()`
  inicial registra `por_tipo` + violaciones individuales; mediciones
  posteriores comparan solo los deltas contra ese baseline. Convertir a
  allowlist estática solo cuando N corridas consecutivas ratifican
  estabilidad del residual.
- **D-26.1 (refill obligatorio post-colocación masiva antes de leer
  baseline DRC)**: `move_footprint` NO dispara refill de zonas — solo
  `add_zone(fill=True)`, `fill_zones`, `route_board` (con refill) y
  `delete_tracks_bulk` lo hacen (sesión 26,
  `docs/investigacion/26-solder-mask-ant1.md` §2). Un baseline DRC leído
  inmediatamente después de una colocación masiva sobre una zona ya
  filleada mide fill rancio (geometría previa a los moves), no el estado
  real de la zona contra los footprints en su posición final. Todo flujo
  (dogfooding o test) que combine `move_footprint` masivo con lectura de
  baseline DRC según D-24.2 debe invocar `fill_zones()` explícito entre la
  colocación y esa lectura. **Consecuencia sobre el baseline V4 de D5**:
  las 6 violaciones que registró (3× `hole_clearance` J1, 1×
  `hole_clearance`/1× `clearance`/1× `solder_mask_bridge` ANT1) no
  representan la geometría real post-colocación — no se re-audita
  retroactivamente, el hallazgo aplica de D6 en adelante. **Pendiente de
  ratificación**: si `fill_zones()` post-colocación en D6 cambia el
  conteo/composición del baseline respecto a lo que D5 midió sin ese paso,
  es evidencia dura de la validez de D-26.1.

### Sobre esquemático
- **D-19b.1**: `lib_symbol_mismatch` NO se resuelve con "Update Symbols from Library" — es destructivo cuando el símbolo local diverge intencionalmente (rompió 6 pines en sesión 19b).
- **D-19b.2**: el neteo de esquemático es por coincidencia de texto de label, no por proximidad geométrica ni wire físico. No-Connect no severa una red si el pin conserva su label. Cualquier tool de mutación de sch debe respetar esto.
- **R12 (vigente, sin cerrar)**: las tools de escritura de sch (`add_symbol`, `set_value`, `set_footprint`, `connect_pins`, `clone_symbols`) son puramente aditivas. No existe CRUD (`delete_wire`, `delete_label`, etc.). Cualquier defecto de sch requiere intervención GUI humana. Ver `docs/BACKLOG.md`.

### Sobre proceso (vinculantes para quien redacta briefs de sesión)
- **D-V3.6**: los briefs de dogfooding se generan ejecutando las tools del propio server, nunca redactando desde memoria/texto — regla nacida de fricciones repetidas (Riesgo 8, ocurrió 3 veces) donde el brief mismo era la fuente del error.
- **Regla arquitectónica reforzada** (tras D-12.4 y hallazgo de sesión 19): antes de aceptar "X escala mal" o "X no funciona", exigir prueba de que X aislado también falla. Dos veces una conclusión de "no escala" resultó ser causada por un factor externo combinado (keepout + autorouter), no por X en sí.

### D-27.1 — Restore no destructivo del entorno GUI vivo

**Contexto:** cuando el entorno vivo (`/tmp/gui-test-project`) no
coincide con la precondición esperada de una sesión (mtime más viejo,
contenido residual de sesión anterior, fixture drift, etc.), se
necesita un procedimiento estándar que no invalide el estado de KiCad
abierto ni pierda información sobre lo que había antes.

**Decisión (procedimiento estándar):**

1. Respaldar los archivos del proyecto vivo a un directorio temporal
   (backup no destructivo — permite forense si algo sale mal).
2. Sobrescribir archivos en el mismo path desde el fixture requerido.
   **NO usar `rm -rf` del directorio** — invalidaría el lock de KiCad
   sobre el proyecto abierto.
3. Sincronizar el editor vivo con `reload_board_from_disk()` sin
   reiniciar la GUI.
4. Confirmar el estado post-restore con `get_component_detail` +
   `get_zones` (o equivalentes) coincidiendo con el README del fixture.

**Requisito de proceso:** `AskUserQuestion` obligatoria al arquitecto
ANTES de cualquier mutación del proyecto abierto — nunca decisión
unilateral, aun cuando el patrón esté formalizado.

**Precedentes que validaron el procedimiento:** sesión 24 (test de
regresión F-D4-02) y sesión 27 (test de regresión generalización
D-23.2). Ambas resolvieron el desvío sin reiniciar la GUI y sin
pérdida de información.

**No aplica a:** sesiones donde el arquitecto autoriza reinicio de
KiCad de entrada, o sesiones sin KiCad abierto (unit tests, docs).

### D-28.1 — Cambios de orden de fases del brief requieren AskUserQuestion

**Contexto:** en dogfoodings y sesiones de fix, el brief define un orden
específico de fases (ej. contorno → plano → colocación → refill →
baseline). El agente ejecutor puede tener razones para desviarse del
orden (por ejemplo, réplica exacta de un estado histórico, o
conveniencia operacional). Esos desvíos son legítimos como
implementación, pero el orden de fases suele estar diseñado para aislar
variables metodológicas — cambiar el orden puede contaminar el
experimento sin que se note hasta el análisis.

**Precedente:** D6 (sesión 28) invirtió el orden plano-vs-colocación
respecto al brief (que prescribía plano ANTES de colocar, orden de D5).
El agente colocó primero y creó el plano después, con intención
legítima (réplica exacta del layout D5 vía coordenadas heredadas). Pero
ese orden por sí solo evitó el fill rancio que D-26.1 pretendía
mitigar, contaminando la ratificación empírica de D-26.1. El agente lo
detectó honestamente en el análisis y lo documentó, pero el confusor
quedó en la evidencia.

**Decisión:** cualquier cambio de orden de fases respecto al brief
requiere **`AskUserQuestion` obligatoria al arquitecto ANTES de
ejecutar**, con explicación del cambio propuesto y el motivo. El
arquitecto evalúa si el cambio es metodológicamente aceptable, si
requiere ajustes al brief, o si conviene mantener el orden original.

**No aplica a:** cambios de implementación dentro de una fase (ej.
qué footprint mover primero dentro de "Fase 3: colocación"). El
criterio de discriminación es: ¿cambia el estado observable entre
mediciones? Si sí, es cambio de orden de fases y requiere consulta.

**Antecedente relacionado:** D-27.1 (restore no destructivo del entorno
GUI vivo) también exige AskUserQuestion antes de mutar el proyecto
abierto. D-28.1 extiende el principio de "cambios metodológicos
requieren consulta" al orden de fases del propio brief.

### D-28.2 — Barrido completo de sitios al generar diffs de decisiones (deuda del arquitecto)

**Contexto:** el arquitecto genera diffs de consolidación tras cada
sesión relevante. Una decisión arquitectónica puede aparecer en
múltiples documentos (CONTEXT.md secciones "Estado", "Decisiones
vigentes"; DECISIONES.md; ADR; BACKLOG; ROADMAP; hoja-de-ruta; docstrings
de código). Actualizar solo el sitio más obvio genera drift documental
que puede persistir varias sesiones sin ser detectado.

**Precedente:** consolidación post-sesión 27 actualizó D-23.2 en
`docs/DECISIONES.md §2` y "estado en una línea" del `docs/CONTEXT.md`,
pero omitió `docs/CONTEXT.md §"Decisiones vigentes"` que seguía
diciendo que D-23.2 solo cubría `route_board`. El drift fue detectado
en D6 sesión 28 por el agente ejecutor del dogfooding — no debería
haber sido tarea de un dogfooding detectar drift documental.

**Decisión:** cuando el arquitecto genera diffs de consolidación sobre
una decisión, hacer barrido mental completo de dónde puede aparecer
esa decisión antes de commitear:

- `docs/CONTEXT.md` — secciones "Estado", "Decisiones vigentes",
  "Fases del proyecto", riesgos, hallazgos, backlog resumido.
- `docs/DECISIONES.md` — entrada de la decisión + entradas relacionadas
  que puedan referenciarla.
- `docs/adr/*.md` — ADR de la decisión + ADRs que la citen.
- `docs/BACKLOG.md` — items que la mencionen (cerrados o vigentes).
- `docs/ROADMAP.md` — historial de sesiones que la cite.
- `hoja-de-ruta-v4.md` (o versión vigente) — secuencia + estado técnico.
- Docstrings en código que la referencien.

**No aplica a:** decisiones marginales o triviales que aparecen en
un solo sitio. Aplica a cualquier decisión con `D-N.M` asignado o con
ADR dedicado.

**Consecuencia operacional:** los diffs de consolidación pueden ser
más largos de lo que parecía inicialmente. Es preferible un diff largo
correcto a uno corto con drift.

## 3. Decisiones superadas (referencia histórica, no vigentes)

- **D-V3.1** (revert humano post-route): superada por recarga programática (`Board.revert()`, sesión 18) — ya no hay contacto humano por route.
- **D-R2/D-14.1** (revert + F8 como costo tolerable): revocada por D-V3.1 — el ruteo real es iterativo, el costo por iteración era inaceptable.
- Detalle completo de la cronología de revocaciones: `docs/historico/CONTEXT-v7.md` §"Decisiones de arquitectura vigentes" (sección "Ratificadas por evidencia").

---

## Cómo mantener este documento

Al agregar un ADR nuevo, añadir una fila a §1. Al fijar una decisión informal
que se espera dure más de una sesión, añadirla a §2 con la fuente. Cuando una
decisión de §2 queda superada, moverla a §3 con una frase de una línea sobre
qué la reemplazó — el detalle completo queda en el reporte de sesión que la
originó, no se re-narra aquí.
