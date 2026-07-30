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
| [0013](adr/0013-refs-duplicados-por-anotacion-no-borrado.md) | Refs duplicados se resuelven por anotación, no borrado | Sesión 31b (F-V1-02): `set_footprint_ref` + pre-check `DUPLICATE_REFS` en `route_board`. ADR-0010 queda intacta (sin narrowing) — no se abre `delete_footprint`. |

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
- **D-30.5** (sesión 30, `docs/investigacion/30-solder-mask-ant1.md`): el fill de KiCad, al recortar contra un keepout circular aproximado por un polígono de N vértices, respeta el **apotema** (`r·cos(π/N)`) del polígono, no un círculo ideal al radio pedido. Con N=16 (default de `_circle_vertices_mm` en sesión 21-29) el déficit de apotema a radios ~1.8mm superaba el margen de seguridad de 0.02mm — causa raíz del P1 `solder_mask_bridge` en ANT1 y de por qué el fix de sesión 26 no tuvo efecto. Fix: N=16→64. Aplica a cualquier keepout circular auto-generado por `enforce_hole_clearance`, no solo al caso ANT1.
- **D-19c.1**: nunca aplicar `add_keepout_zone` antes de un `route_board` autorruteado desde cero — bloquea nets sistemáticamente. Aplicar keepouts *después* del ruteo.
- **D-19c.2 / D-19d.1**: KiCad reasigna el net de una vía/track nueva al net del cobre físico bajo/cruzado (comportamiento de dominio, no bug). Cerrado en tool con verificación post-creación + `NET_ASSIGNMENT_MISMATCH`.
- **D-23.3** (sesión 23, ver `docs/historico/sesiones/23-reporte.md`): el
  loop de vías de `enforce_hole_clearance` (`ipc.py`, bloque de creación de
  keepouts `via_*`, hoy ~líneas 2037-2073 — antes 1996-2032, desplazado por
  el fix de sesión 30) nunca creó un keepout `via_*` en 3 corridas de
  investigación de sesión 23. Puede ser código muerto. **Deuda técnica
  identificada pero NO se toca** salvo evidencia nueva de que importa —
  investigación independiente, riesgo alto de regresión si se elimina sin
  certeza. Ratificado sin intervención en sesión 30: el fix quirúrgico en
  `enforce_hole_clearance` deliberadamente dejó el loop de vías fuera de
  alcance, conservando solo el término de agujero (ver
  `docs/investigacion/30-solder-mask-ant1.md` §"Fix implementado").
  Referenciado como R16 en `docs/BACKLOG.md` y `docs/CONTEXT.md`.
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

  **Ratificación empírica (sesión 29 D7):** V4.a=6 violaciones no-triviales
  (3× hole_clearance J1 NPTH, 1× hole_clearance ANT1, 1× clearance ANT1,
  1× solder_mask_bridge ANT1) vs V4.b=0 tras `fill_zones()` explícito.
  Bit-exacto al patrón que D5 registró — confirma que el fenómeno depende
  del orden de fases y del footprint set, no del layout específico. D7
  ejecutó con coordenadas distintas de D5/D6 y ratificó el mismo patrón.
  Con este resultado D-26.1 pasa de "ratificado con matiz metodológico"
  (estado post-D6) a "ratificado sin confusor". Aplicable a cualquier
  flujo con `add_zone(fill=true) → move_footprint × N → run_drc()`.

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

### D-30.1 — Estrategia de validación explícita para sesiones con hipótesis técnica

**Contexto:** durante Fase 3, la disciplina "verificar contra la realidad
del sistema, no contra la aritmética propia" emergió como aprendizaje
recurrente (sesión 24: fix Opción X verificado en vivo contra KiCad real;
sesión 26: fix acordado refutado por verificación empírica antes del merge).
Ese instinto operacional se convirtió en factor determinante de la calidad
alcanzada en el cierre de Fase 3. Formalizarlo como regla lo convierte de
instinto en criterio replicable.

**Decisión:** toda sesión que tenga como objetivo **modificar el
comportamiento del sistema o validar una hipótesis técnica** debe incluir
en su prompt, ANTES de cualquier implementación, un bloque explícito con
los siguientes 4 puntos:

1. **Hipótesis** que se pretende validar.
2. **Evidencia que confirmaría** la hipótesis.
3. **Evidencia que refutaría** la hipótesis.
4. **Estrategia para proteger** el cambio frente a regresiones.

**Criterio de aplicabilidad:** el criterio NO es el tipo de sesión sino si
existe un comportamiento del sistema cuya validez queremos demostrar.

**Aplica a:**
- Sesiones de nuevas capacidades.
- Sesiones de corrección de bugs.
- Sesiones de refactor con impacto funcional.
- Sesiones de investigación técnica.
- Dogfoodings.

**NO aplica a:**
- Consolidación documental.
- Reorganización del repositorio.
- Limpieza de documentación.
- Trabajo administrativo (releases, versionado, etc.).

**Consecuencia operacional (arquitecto):** si al redactar un prompt de sesión
no puedo llenar claramente los 4 puntos, el prompt no está listo. Vuelve a
fase de diseño hasta que el problema esté suficientemente entendido para
formular hipótesis y criterios de refutación. Un prompt que arranca sin
D-30.1 completo es un prompt que va a producir código sin criterio de
validación — exactamente lo que Fase 3 nos enseñó a evitar.

**Consecuencia operacional (ejecutor):** el bloque D-30.1 del prompt es
lectura obligatoria antes de tocar código. Si el ejecutor encuentra que la
hipótesis no encaja con lo que observa en el estado real del sistema,
`AskUserQuestion` obligatoria antes de proceder.

### D-30.2 — Criterio de éxito de Fase 4: aumento de confianza

**Contexto:** en Fase 3 el criterio dominante era convergencia técnica
(¿está estable la arquitectura?). Fase 4 tiene ambición distinta: proyecto
de referencia Open Source, no expansión de capabilities. El criterio de
éxito de cada sesión cambia en consecuencia.

**Decisión:** durante Fase 4, el éxito de una sesión se mide principalmente
por el aumento de confianza que aporta al proyecto, no por el volumen de
código escrito. Esto orienta las decisiones tácticas:

- Una sesión de investigación que cierra sin fix pero con causa raíz
  identificada aumenta confianza (patrón sesión 23, sesión 26).
- Una sesión de dogfooding sin fricciones aumenta confianza (patrón
  D5/D6/D7).
- Una sesión que agrega feature sin evidencia clara de necesidad, sin
  hipótesis D-30.1, o sin protección contra regresiones NO aumenta
  confianza — incluso si el código funciona.

**Aplicación:** cuando surja tensión entre "escribir más código" y
"consolidar evidencia sobre el código que ya existe", elegir consolidar.

### D-30.3 — Definición operacional de "igualmente válido" en Validation Suite

**Contexto:** la Validation Suite compara el flujo automatizado del proyecto
contra placas fabricadas por sus autores originales (ground truth). Sin
definición operacional de "igualmente válido", la comparación degrada a
juicio subjetivo.

**Decisión (versión mínima, sujeta a revisión post-3 validaciones):**

Una PCB producida por el flujo automatizado se considera "igualmente
válida" respecto al ground truth si cumple los 4 criterios simultáneamente:

1. **DRC** (booleano, obligatorio): 0 errores, 0 warnings — o warnings
   documentados y compartidos con el ground truth.
2. **Longitud total de tracks** (cuantitativo): dentro de ±30% del ground
   truth.
3. **Número de vías** (cuantitativo): dentro de ±20% del ground truth.
4. **Área ocupada por cobre** (cuantitativo): dentro de ±25% del ground
   truth (proxy de densidad).

**Métricas de referencia registradas para cada validación:** además de los
4 criterios de aceptación, el report de validación incluye la comparación
completa (con y sin cumplimiento) para permitir revisión posterior de los
umbrales.

**Revisión de umbrales:** tras las primeras 3 validaciones cerradas
(nivel A/B/C), evaluar si los ±30/±20/±25% son apropiados. Ajustar según
evidencia. Si aparecen métricas útiles nuevas (tiempo de ruteo, jerarquía
de nets ejercitada, etc.), agregarlas.

**Fuera del criterio (deliberadamente):**
- Estética del ruteo (subjetiva, imposible de operacionalizar).
- Preferencias de colocación específicas (dominio del diseñador, no del
  flujo).
- Coincidencia exacta de decisiones — la comparación no es de igualdad,
  es de validez equivalente.

### D-30.4 — Criterio de diversidad para admisión a Validation Suite

**Contexto:** sin criterio explícito de diversidad, es fácil terminar con
N validaciones que ejercitan los mismos features. Eso infla el número de
"placas probadas" sin ampliar cobertura real.

**Decisión:** un proyecto candidato para entrar a la Validation Suite
posterior al primero de cada nivel (A/B/C/D) debe agregar **al menos una
feature no cubierta** en la matriz de cobertura vigente al momento de la
admisión.

**Features de interés (lista viva, no exhaustiva):**
- Capas: 2, 4, 6+.
- Planos: single, múltiples, mixto (potencia/GND separados).
- Protocolos: USB, USB-C, ESP32, RF, I²C, SPI, CAN.
- Familias: switching, lineal, digital, analógico, RF.
- Estructura sch: jerárquico, plano, con símbolos custom.
- Footprints: SMD estándar, THT, personalizados, BGA, QFN, flex.
- Densidad: baja (<30%), media (30-50%), alta (>50%).

**Consecuencia operacional:** cada proyecto candidato viene con una
justificación de qué feature nueva aporta. Sin esa justificación, se
rechaza y se busca otro.

**Excepción:** el **primer proyecto de cada nivel** (A/B/C/D) puede
seleccionarse por criterios distintos (simplicidad para nivel A, dificultad
para nivel C, etc.) sin requisito de diversidad — es la ancla del nivel.

**Aplicación de la matriz de cobertura:** vive en
`validation-suite/reports/coverage-matrix.md` (a crear cuando se cierre
la primera validación de nivel A). Se actualiza tras cada validación
cerrada.

### D-31.1 — Convenciones estructurales de la Validation Suite

**Contexto:** sesión 31 fue la primera validación de Nivel A y tenía rol
dual explícito: validar Y establecer el template que sesiones 32-33
reutilizan. Las decisiones de proceso tomadas ahí se convierten
automáticamente en estándar — se formalizan acá para que no dependan de
releerse el reporte completo de sesión 31.

**Decisión (procedimientos que sesiones 32-33 heredan sin re-derivar):**

1. **Estructura de directorios por proyecto**:
   `validation-suite/level-{a,b,c}/<proyecto>/{ground-truth-original,
   ground-truth-kicad10,working,metrics.md,validation-report.md,README.md}`.
   `ground-truth-original/` nunca se sobrescribe (ni siquiera si la
   migración de formato resulta ser un no-op); `ground-truth-kicad10/` es
   la referencia de comparación D-30.3; `working/` es la copia mutable
   del flujo canónico.
2. **Estado inicial de `working/`**: todos los footprints movidos a
   `(0,0)` (no una grilla prolija) — decisión explícita del arquitecto en
   sesión 31, literal del prompt original. Ejercita `get_footprint_neighbors`
   y la colocación asistida contra el caso adversarial máximo (courtyards
   100% solapados). Generado con `validation-suite/tools/prepare_working.py`.
3. **Scripts de la Suite corren con el Python del SISTEMA**
   (`/usr/bin/python3`, el que trae `pcbnew`), nunca con el venv de `uv`
   — documentado en el docstring de cada script, con detección de
   `ImportError` y mensaje explícito (no traceback crudo).
4. **`copper_area_mm2` se mide por unión geométrica por capa**, no suma
   aditiva — evita doble conteo de pads bajo un plano. Ver
   `validation-suite/tools/measure_ground_truth.py` para el procedimiento
   completo y los chequeos de cordura (`union ≤ aditivo`).
5. **`board_area_mm2` se calcula del bbox de Edge.Cuts explícito**, nunca
   de `pcbnew.BOARD.GetBoardEdgesBoundingBox()` — esa API de pcbnew NO se
   limita a Edge.Cuts pese al nombre (incluye otros ítems del board),
   hallazgo de sesión 31 verificado empíricamente.
6. **Gate GUI del DoD se corre PRIMERO, antes del Bloque 0**, no al final
   como sugería el prompt original — minimiza los cambios de proyecto
   abierto en KiCad. Válido cuando la sesión no toca `src/`; si termina
   tocando `src/`, se re-corre al cierre.
7. **Reubicación del entorno vivo**: cuando `KICAD_MCP_PROJECT` apunta a
   una ruta fija (`/tmp/gui-test-project`, vía `~/.claude.json`), el
   proyecto anterior se respalda no-destructivamente (patrón D-27.1,
   `<ruta>.{nombre-anterior}-bak/`) y se reemplaza en el mismo path — no
   se edita la config del server ni se reinicia la sesión.
8. **3 handoffs humanos mínimos** por candidato nuevo: (a) cerrar el
   proyecto anterior en KiCad, (b) abrir el proyecto nuevo, (c) abrir
   específicamente el **PCB Editor** (no sólo el Project Manager —
   `health()` distingue `pcb_editor_abierto` y sesión 31 encontró que el
   paso (b) por sí solo no garantiza (c)).

**Precedente:** sesión 31, primera Validation Suite Nivel A (ANAVI Dev
Mic). Ver `validation-suite/level-a/anavi-dev-mic/validation-report.md`
para el detalle completo de cada hallazgo que originó estas convenciones.

### D-31c.1 — Cross-check obligatorio contra ADRs vigentes antes de fijar el marco de un prompt

**Contexto:** al cerrar decisiones de diseño no re-abribles en el marco
del prompt de una sesión (patrón D1-DN), el arquitecto puede fijar una
decisión que choca con un ADR vigente sin saberlo — el marco cerrado del
prompt no incluye automáticamente un cross-check contra la superficie de
ADRs que toca.

**Decisión:** cross-check obligatorio contra ADRs vigentes que tocan el
área operada antes de fijar el marco (patrón D1-DN) en el prompt de una
sesión. Origen: sesión 31b reveló que D1-D4 del prompt de 31b (semántica
de `delete_footprint`) chocaba con ADR-0010 (asimetría deliberada
`delete_track`/`delete_footprint`) — decisión que el arquitecto había
cerrado sin verificar el ADR vigente. Salvado por rigor investigativo del
ejecutor (2 agentes Explore + 1 Plan, verificado contra el código real)
más `AskUserQuestion` antes de comprometerse con el fix original. La
convención hace explícita la disciplina para prompts futuros: el marco
cerrado del prompt es autoritativo pero no dispensa del cross-check con
ADRs de la superficie tocada.

**Aplicación:** decisión del arquitecto sobre el proceso de generación de
prompts, no sobre código — análoga a D-30.1 pero un nivel arriba (D-30.1
exige hipótesis/evidencia/refutación/protección dentro de una sesión;
D-31c.1 exige cross-check de ADRs vigentes al diseñar el prompt mismo,
antes de que la sesión arranque).

### D-32.1 — Criterio DRC separado por severidad (eléctrico / estructural / cosmético)

**Contexto:** sesión 31c descubrió que "0 errores DRC nuevos" (el
criterio literal de D-30.3) no distingue severidad — un delta de
conteo idéntico puede ocultar una composición completamente distinta
(tipos nuevos graves vs. tipos nuevos cosméticos). Sesión 32 aplicó la
descomposición por primera vez de forma sistemática y confirmó su valor:
el ground truth y el output de ANAVI Macro Pad 12 mostraron un delta de
conteo total casi idéntico (175→179, +4), pero la tabla separada reveló
que el 100% del delta neto era eléctrico (2 `unconnected_items` + 2
`track_dangling`) mientras estructural y cosmético permanecían casi
intactos — exactamente el tipo de distinción que un conteo total oculta.

**Decisión:** formalizar la taxonomía de 3 buckets para el criterio DRC
de D-30.3 en toda validación futura de la Suite:

- **Eléctricos** (estricto — 0 nuevos): `unconnected_items`,
  `shorting_items`, `clearance`, `hole_clearance`, `hole_to_hole`,
  `track_dangling`, `via_dangling`, `copper_edge_clearance`,
  `starved_thermal`.
- **Estructurales** (moderado — registrar deltas, no falla automática):
  `solder_mask_bridge`, `courtyards_overlap`, `malformed_courtyard`,
  `footprint_type_mismatch`, `lib_footprint_mismatch`,
  `lib_footprint_issues`, `invalid_outline`, `zones_intersect`.
- **Cosméticos** (informativo): `silk_over_copper`, `silk_overlap`,
  `silk_edge_clearance`, `silk_mask_clearance`, `text_height`,
  `text_thickness`.

Un rule id de KiCad no catalogado se clasifica como **estructural** por
defecto (conservador) y se anota explícitamente. El pass/fail del
criterio DRC de D-30.3 se evalúa sobre **eléctricos + estructurales**,
no sobre el total; el conteo total se sigue reportando para
comparabilidad histórica.

**Fuente de datos:** `validation-suite/tools/measure_ground_truth.py`
(schema 1.1, sesión 32) ya expone `drc_by_rule` (conteo por tipo,
fusionando `violations`+`unconnected_items` igual que `_run_drc`
original) — la clasificación en buckets es una interpretación sobre esa
salida, no requiere cambios adicionales al script.

**Aplicación:** vigente para sesión 33 en adelante. No reabre el
criterio DRC "0 errores/warnings o compartidos con el ground truth" de
D-30.3 en sí — lo refina operacionalmente, mismo espíritu que D-30.5
refinó el mecanismo de `enforce_hole_clearance` sin reabrir D-23.2.

### D-32b.1 — `POST_ROUTE_REFILL_SKIPPED`: error explícito sin retry, raise al final del pipeline

**Contexto:** F-V2-REFILL-SILENCIOSO (hallazgo P0/P1 de sesión 32,
reproducido también en sesión 31c): el bloque de refill de seguridad de
`route_board(refill=true)` sólo corre si `reload_board_from_disk()` tuvo
éxito; hasta sesión 32b, si esa recarga (mutación sin reintento, D-07.1)
lanzaba una excepción, se descartaba en silencio y `route_board` completaba
como éxito normal sin el refill prometido — sin ninguna señal de error,
rompiendo D-23.2/ADR-0012 exactamente en el caso que ese contrato existe
para prevenir.

**Decisión:** cuando `refill=true`, había ≥1 zona existente, y la recarga
falló por una excepción real (no por "otro proyecto abierto" ni "editor
cerrado" — ambos legítimos), `route_board` levanta
`POST_ROUTE_REFILL_SKIPPED` (adición pura al `StrEnum ErrorCode`, F1/F3
intacta). **Sin retry**: `reload_board_from_disk` se sigue llamando una sola
vez — el fix respeta D-07.1 en vez de reabrirlo. El raise se pospone hasta
DESPUÉS del DRC post-route, el registro del snapshot y
`store.mark_live_stale` (no en el guard de arriba): abortar antes dejaría el
flag `live_stale` en `False` con el disco adelante del vivo, y un
`fill_zones()` posterior pasaría `_guard_live_stale()` y pisaría el ruteo con
su propio `save_board()`. El `audit_record` se escribe siempre (con o sin
error), conservando el `result` forense completo más el `error_code`.

**Fuente:** sesión 32b. Ver `docs/adr/0012-route-board-persist-contract.md`
§"Extensión F-V2 (sesión 32b)" para el detalle completo (incluye por qué el
guard `reloaded is True` no se relaja: refillear el vivo tras una recarga
fallida pisaría el ruteo, porque el vivo todavía refleja el estado
pre-ruteo).

### D-32b.2 — Alcance del fix F-V2-REFILL-SILENCIOSO: sólo `route_board`

**Contexto:** el prompt de sesión 32b hipotetizaba (H2) que el mismo bug
podía afectar `fill_zones()` y `add_zone(fill=true)` — las tres tools
comparten el contrato D-23.2/ADR-0012 desde la extensión de sesión 27, y la
cobertura simétrica era la lectura por defecto antes de inspeccionar el
código.

**Decisión:** H2 queda refutada por inspección, no se aplica fix a
`fill_zones`/`add_zone`. Ninguna de las dos llama `reload_board_from_disk`
en absoluto — abren con `_guard_live_stale()` y su único modo de falla
(`save_board()`) ya levanta `POST_ZONE_PERSIST_FAILED` desde sesión 27. No
existe la llamada cuya excepción se pudiera descartar en silencio: el cierre
del contrato para estas dos tools es por evidencia de que no tienen el
camino silencioso, no por código simétrico nuevo (D-30.2: éxito por
confianza, no por volumen). Registrado también: `delete_tracks_bulk` llama
`refill_zones()` sin `enforce_hole_clearance()` ni `save_board()` — una
asimetría real con el contrato, pero fuera del alcance acordado de esta
sesión; anotada en `docs/BACKLOG.md` para evaluación futura.

**Fuente:** sesión 32b, cross-check D-31c.1 aplicado antes de escribir el
plan de ejecución.

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
