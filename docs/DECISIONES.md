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
| [0012](adr/0012-route-board-persist-contract.md) | Contrato disco==memoria==`err_post` | Sesión 24: `route_board` mide DRC y persiste **después** de refill+enforce; fix de F-D4-02. Ver D-23.2 abajo. **Vigente hoy solo en `route_board`** — `fill_zones`/`add_zone(fill=True)` sufren el mismo patrón sin corregir (R14 residual, generalización pendiente — paso 3 de `hoja-de-ruta-v4.md`). |

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
- **D-23.2 (ADR-0012)**: `route_board`, al terminar OK, garantiza disco == memoria == `err_post` reportado — ver ADR-0012 para el contrato completo. Generalización a `fill_zones`/`add_zone(fill=True)` pendiente (ver `hoja-de-ruta-v4.md` paso 3, `docs/BACKLOG.md`).

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

### Sobre esquemático
- **D-19b.1**: `lib_symbol_mismatch` NO se resuelve con "Update Symbols from Library" — es destructivo cuando el símbolo local diverge intencionalmente (rompió 6 pines en sesión 19b).
- **D-19b.2**: el neteo de esquemático es por coincidencia de texto de label, no por proximidad geométrica ni wire físico. No-Connect no severa una red si el pin conserva su label. Cualquier tool de mutación de sch debe respetar esto.
- **R12 (vigente, sin cerrar)**: las tools de escritura de sch (`add_symbol`, `set_value`, `set_footprint`, `connect_pins`, `clone_symbols`) son puramente aditivas. No existe CRUD (`delete_wire`, `delete_label`, etc.). Cualquier defecto de sch requiere intervención GUI humana. Ver `docs/BACKLOG.md`.

### Sobre proceso (vinculantes para quien redacta briefs de sesión)
- **D-V3.6**: los briefs de dogfooding se generan ejecutando las tools del propio server, nunca redactando desde memoria/texto — regla nacida de fricciones repetidas (Riesgo 8, ocurrió 3 veces) donde el brief mismo era la fuente del error.
- **Regla arquitectónica reforzada** (tras D-12.4 y hallazgo de sesión 19): antes de aceptar "X escala mal" o "X no funciona", exigir prueba de que X aislado también falla. Dos veces una conclusión de "no escala" resultó ser causada por un factor externo combinado (keepout + autorouter), no por X en sí.

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
