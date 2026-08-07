# Sesión 31b — Fix intermedio: `delete_footprint` + `board_bbox_mm`

**Tipo:** sesión de fix intermedia post-sesión 31. Resuelve los dos
hallazgos de la primera validación externa para desbloquear el reintento
de sesión 31 sobre el `working/` de ANAVI Dev Mic ya preparado.

**Rama:** `sesion/31b-fix-delete-footprint-y-bbox` desde `master`
post-merge de sesión 31.

**Origen:** F-V1-02 (P0, bloqueante) y F-V1-01 (P1, agrupable) — ambos
identificados y con causa raíz aislada en sesión 31. Ver
`docs/historico/sesiones/31-reporte.md` y `docs/BACKLOG.md`.

**Precedente metodológico:** patrón sesiones 30 (fix quirúrgico + D-30.1
estricta) y sesiones intermedias de Fase 3. La disciplina es la misma:
fix acotado, no expansión.

## Contexto de Fase 4

- **D-30.1 estricta.** Bloque explícito de hipótesis / evidencia
  confirmatoria / evidencia refutatoria / protección contra regresiones
  ANTES de tocar código. Ver §"Estrategia de validación".
- **D-30.2 aplica:** éxito = aumento de confianza. Un fix correcto con
  evidencia sólida vale más que dos fixes apurados.
- **Interpretación Fase 4:** los dos hallazgos NO son regresión (fricciones
  preexistentes nunca ejercitadas por el despertador). Son gaps
  legítimos expuestos por la Validation Suite.

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4.

**Regla operacional específica:** sesión 31b es fix quirúrgico. Si aparece
tentación de "aprovechar y arreglar también X", `AskUserQuestion` antes
de expandir alcance. Precedente sesión 30: 35 líneas efectivas, no 350.

---

## Estrategia de validación (D-30.1)

### Hipótesis principales

**H1 — Fix F-V1-02 con tool nueva.** Una tool `delete_footprint(ref,
kiid=None)` permite al agente resolver refs duplicados desde el flujo
canónico, sin intervención manual fuera. Con la tool disponible, ANAVI
Dev Mic puede completar `route_board` porque el agente puede eliminar
las 3 instancias sobrantes de `REF**` antes del ruteo.

**H1a — Protección proactiva.** Un pre-check en `route_board` que valide
unicidad de refs antes de invocar `ExportSpecctraDSN` falla-fast con
error legible (`F-V1-DUPLICATE-REFS` o equivalente), evitando que un
proyecto Nivel A/B/C futuro dispare el mismo bug de pcbnew sin
diagnóstico prolijo.

**H2 — Fix F-V1-01.** `board_bbox_mm` puede leer Edge.Cuts como su
docstring promete. En un board con footprints apilados en el origen
(convención del `working/` adoptada en sesión 31 y ratificada en D-31.2)
y Edge.Cuts definido, la tool devuelve la bbox del Edge.Cuts real, no
la del enjambre de footprints ±100mm.

### Evidencia confirmatoria

- **H1:** en un fixture con refs duplicados (replicado del bug de ANAVI
  Dev Mic o minimalizado), aplicar `delete_footprint` → footprint
  eliminado + `ExportSpecctraDSN` pasa a exportar sin error (verificable
  por tamaño > 0 y parseo mínimo del DSN).
- **H1a:** en el mismo fixture SIN aplicar delete, invocar `route_board`
  → error legible con nombre `DUPLICATE_REFS` (o el código que se
  acuerde), NO segfault ni error opaco de pcbnew. Sobre el fixture
  post-delete, `route_board` procede sin el pre-check disparándose.
- **H2:** en un board con footprints en `(0,0)` y Edge.Cuts en, por
  ejemplo, `(50, 50)-(150, 130)`, `board_bbox_mm` devuelve
  aproximadamente `(50, 50, 100, 80)`, NO `(-100, -100, 200, 200)` que
  daría el fallback de enjambre.

### Evidencia refutatoria

- **H1:** eliminar el footprint duplicado NO desbloquea
  `ExportSpecctraDSN` → hay otra causa en pcbnew además del ref. Requiere
  investigación adicional antes de mergear.
- **H1a:** el pre-check dispara falsos positivos sobre proyectos válidos
  (ej. despertador) → refutación. El fix del pre-check requiere
  refinamiento.
- **H2:** leer Edge.Cuts requiere un mecanismo IPC no disponible en
  KiCad 10.0.4 → refutación. Fix se difiere o requiere workaround
  distinto.

### Protección contra regresiones

- **Suite offline** (`pytest -m "not integration"`) → verde antes del
  merge.
- **Suite integration** (`pytest -m integration`) → verde antes del
  merge.
- **Gate GUI del DoD** contra despertador:
  - `tests/test_pcb_session21_hole_clearance_gui.py` → 2/2.
  - `tests/test_pcb_session27_zone_persist_gui.py` → 2/2.
  - Contra `/tmp/kicad-mcp-sesion31b-gui/` (copia fresca del fixture).
- **Test canario nuevo obligatorio:** un test que reproduzca el bug de
  refs duplicados desde un fixture minimal (2 footprints con mismo ref),
  verificando (a) que `delete_footprint` los elimina, (b) que el
  pre-check de `route_board` los detecta antes de que exploten. Este
  test es el gate de regresión permanente contra F-V1-02.

---

## Decisiones de diseño cerradas (no re-abrir en ejecución)

Las 4 preguntas de diseño acordadas con el arquitecto quedan
operacionalizadas así:

### D1 — Semántica de `delete_footprint` ante refs duplicados

**Decisión:** parámetro extra `strict=True` (default), que hace fallar
con error legible si `ref` es ambiguo sin `kiid`. Con `strict=False`,
borra todos los footprints con ese ref.

Firma de la tool:
```python
delete_footprint(ref: str, kiid: str | None = None, strict: bool = True)
```

Casos:
- `delete_footprint("R1")` → si "R1" es único, borra. Si hay múltiples,
  error `AMBIGUOUS_REF` listando los `kiid` disponibles.
- `delete_footprint("R1", kiid="abc123")` → borra exactamente ese.
- `delete_footprint("REF**", strict=False)` → borra los 4 mounting holes
  de una sola llamada.

Razonamiento: `strict=True` default protege contra borrados masivos
accidentales. `strict=False` permite resolver el caso ANAVI Dev Mic con
1 llamada explícita. `kiid` permite operar sobre uno específico cuando
el resto se quiere conservar.

### D2 — Efectos colaterales de `delete_footprint`

**Decisión:** solo elimina el footprint. NO borra tracks huérfanos, NO
borra vías huérfanas, NO borra zonas afectadas.

Precedente: `delete_track` sí / `delete_footprint` no (asimetría D-R3,
D-R8, BACKLOG P2 histórico) — ahora resolvemos parcialmente la asimetría
pero mantenemos consistencia con `delete_track` en no cascada.

Nota metodológica: si el usuario quiere limpiar tracks huérfanos, tiene
`delete_tracks_bulk` disponible. Lo agrupamos en otra decisión post-sesión
31b si aparece evidencia de que es necesario.

### D3 — Protección proactiva en `route_board`

**Decisión:** SÍ incluir pre-check.

`route_board` debe validar unicidad de refs de footprints ANTES de
invocar `ExportSpecctraDSN`. Si hay duplicados, fallar con error legible
listando los refs duplicados y sus `kiid`. El código del error es
`DUPLICATE_REFS` (nombre a validar contra convenciones del proyecto).

Justificación: cuesta ~5-10 líneas y evita que sesión 32 con un candidato
Nivel B que también tenga refs duplicados dispare el mismo bug opaco de
pcbnew sin diagnóstico. Es defensa en profundidad + observabilidad.

Nota: el pre-check NO llama a `delete_footprint`. Solo detecta y reporta.
La resolución queda al agente.

### D4 — Reintento de sesión 31 post-fix

**Decisión:** reutilizar el `working/` de ANAVI Dev Mic ya preparado.

El Bloque 0/1 de sesión 31 (ground truth medido, DRC baseline
documentado, working/ construido, tooling reutilizable) queda íntegro.
Sesión 31-reintento arranca desde Bloque 2 con el estado que sesión 31
dejó pre-`route_board`.

**Consecuencia para sesión 31b:** NO tocar `validation-suite/level-a/anavi-dev-mic/`.
Es el estado que reintento de 31 va a consumir.

---

## Preparación

1. Verificar que `master` incluye sesión 31 mergeada (commit `a930db0`
   pusheado si aplica, o preguntar al arquitecto si el push ya se hizo).
2. `git checkout master && git pull` (si aplica).
3. `git checkout -b sesion/31b-fix-delete-footprint-y-bbox`.
4. `/tmp/gui-test-project/` NO se toca.
5. `/tmp/kicad-mcp-sesion31b-gui/` = copia fresca del fixture despertador
   para el gate GUI del DoD.
6. **Lectura obligatoria** antes de arrancar:
   - `docs/historico/sesiones/31-reporte.md`.
   - `docs/BACKLOG.md` entradas F-V1-01 y F-V1-02 completas.
   - `docs/DECISIONES.md` D-31.1 y D-31.2 si están.
   - `validation-suite/level-a/anavi-dev-mic/validation-report.md` para
     entender el contexto del hallazgo.

---

## Bloque 0 — Reproducción controlada de ambos bugs (30 min)

**Objetivo:** confirmar que reproducimos ambos bugs en fixtures acotados
antes de tocar código. Este bloque es un **gate**: si no reproducimos,
algo no entendemos.

### F-V1-02 — reproducción

1. Crear fixture minimal `tests/fixtures/duplicate-refs-minimal/`:
   - Board vacío con 2 footprints simples (dos mounting holes o dos
     resistencias) con el mismo `ref` — replica minimalizada del bug de
     ANAVI Dev Mic.
   - Edge.Cuts básico.
2. Invocar `pcbnew.ExportSpecctraDSN()` (u homologable IPC) sobre este
   fixture → confirmar que falla del mismo modo que en sesión 31 (DSN
   vacío, error, o cualquier síntoma equivalente).
3. Aplicar quirúrgicamente (edición del `.kicad_pcb` a mano) el
   renombrado de uno de los dos refs → confirmar que `ExportSpecctraDSN`
   pasa a funcionar. Esto ratifica que el fixture reproduce el bug
   correcto.

### F-V1-01 — reproducción

1. Crear fixture minimal `tests/fixtures/footprints-at-origin-with-edge/`:
   - Board con Edge.Cuts definido en una región `(50, 50)-(150, 130)`.
   - Todos los footprints (o al menos 3) apilados en `(0, 0)`.
2. Invocar `board_bbox_mm` sobre este fixture → confirmar que devuelve
   la bbox del enjambre de footprints ±100mm (aprox. `(-100, -100, 200,
   200)`), NO la del Edge.Cuts.

### Gate del Bloque 0

Si CUALQUIERA de los dos bugs no reproduce como se espera, `AskUserQuestion`
antes de continuar. La reproducción es evidencia previa al fix — sin ella,
el fix va a ciegas.

### Salida esperada

Dos fixtures minimales versionados en `tests/fixtures/`, ambos bugs
confirmados reproducibles.

---

## Bloque 1 — Fix F-V1-02: `delete_footprint` + pre-check (60-90 min)

**Objetivo:** implementar la tool nueva y el pre-check, ambos con
evidencia contra el motor real.

### Sub-bloque 1.1 — Implementación de `delete_footprint`

Firma:
```python
delete_footprint(ref: str, kiid: str | None = None, strict: bool = True)
```

Semántica según D1 (arriba). Ubicación: donde vivan `delete_track` y
tools de escritura de PCB en `src/kicad_mcp/`.

Consideraciones específicas:
- No cascade (D2): solo elimina el footprint. Documentar explícito en
  docstring.
- Códigos de error nuevos: `AMBIGUOUS_REF` (con lista de kiids
  disponibles), `FOOTPRINT_NOT_FOUND` (si `ref` o `kiid` no existen).
- Manejar el segfault documentado en sesión 31 (combinar remove+move en
  el mismo proceso pcbnew): si aplica, usar el mismo patrón de
  subprocesos separados que documentó sesión 31 en los docstrings de
  `prepare_working.py`.

### Sub-bloque 1.2 — Pre-check en `route_board`

Antes de invocar `ExportSpecctraDSN` (o su homologable IPC), validar que
todos los footprints tienen `ref` único.

Si hay duplicados:
- No invocar `ExportSpecctraDSN`.
- Retornar error con código `DUPLICATE_REFS`, listando los refs
  duplicados con sus `kiid` correspondientes.
- Formato: mensaje legible sugiriendo la resolución (`delete_footprint`
  con `kiid`, o `strict=False` para borrar todos los que compartan el
  ref).

### Sub-bloque 1.3 — Tests

Unit tests para `delete_footprint`:
- `test_delete_footprint_unique_ref` → borra exactamente uno.
- `test_delete_footprint_ambiguous_strict_true` → error `AMBIGUOUS_REF`
  con lista de kiids.
- `test_delete_footprint_ambiguous_strict_false` → borra todos.
- `test_delete_footprint_with_kiid` → borra el kiid exacto.
- `test_delete_footprint_not_found` → error `FOOTPRINT_NOT_FOUND`.
- `test_delete_footprint_no_cascade_on_tracks` → tracks conectados
  permanecen tras la eliminación.

Integration test para pre-check:
- `test_route_board_rejects_duplicate_refs` (nuevo, marca `integration`)
  → sobre el fixture minimal del Bloque 0, verifica que `route_board`
  devuelve `DUPLICATE_REFS` antes de tocar `ExportSpecctraDSN`.
- `test_route_board_accepts_after_delete` → misma fixture, aplicar
  `delete_footprint` con `strict=False` → `route_board` procede.

**Test canario permanente** (gate de regresión contra F-V1-02):
- `tests/test_pcb_session31b_duplicate_refs_canary.py` → verifica que la
  combinación pre-check + `delete_footprint` cierra el ciclo. Este test
  queda como canario permanente. Si en el futuro alguien remueve el
  pre-check o rompe `delete_footprint`, este test lo detecta.

---

## Bloque 2 — Fix F-V1-01: `board_bbox_mm` lee Edge.Cuts (30 min)

**Objetivo:** implementar lo que la docstring ya promete.

### Pasos

1. Ubicar `board_bbox_mm` (o la función interna equivalente).
2. Implementar la lectura de Edge.Cuts como fuente primaria.
3. Mantener el fallback de enjambre de footprints ±100mm SOLO si
   Edge.Cuts está vacío (no hay líneas en la capa) — casos borde
   legítimos como un board recién creado.
4. Documentar el orden de resolución explícito en la docstring:
   ```
   1. Bbox de Edge.Cuts si tiene contenido.
   2. Bbox de enjambre de footprints ±100mm si Edge.Cuts vacío.
   3. Error si ninguna de las dos aplica (board completamente vacío).
   ```

### Tests

Unit tests:
- `test_bbox_reads_edge_cuts_when_present` → sobre el fixture del
  Bloque 0.
- `test_bbox_falls_back_to_footprints_when_edge_cuts_empty` → asegurar
  que el fallback sigue funcionando cuando corresponde.
- `test_bbox_errors_when_board_empty` → si aplica.

---

## Bloque 3 — Gate de regresión y validación integral (45 min)

**Objetivo:** confirmar que los fixes no rompen nada existente y que el
gate GUI del DoD sigue verde.

### Pasos

1. **Suite offline:** `pytest -m "not integration"` → verde.
2. **Suite integration:** `pytest -m integration` → verde. Incluye los
   nuevos tests del pre-check y `delete_footprint`.
3. **Gate GUI del DoD contra `/tmp/kicad-mcp-sesion31b-gui/`:**
   - `test_pcb_session21_hole_clearance_gui.py` → 2/2 verde.
   - `test_pcb_session27_zone_persist_gui.py` → 2/2 verde.
4. **`ruff` + `mypy`** limpios.
5. **Ejercicio de humo sobre despertador:** correr `board_bbox_mm` sobre
   una copia del despertador con footprints reales (no en `0,0`) →
   verificar que devuelve la bbox de Edge.Cuts del despertador, no un
   valor inesperado. Este es un chequeo mínimo de que el fix no
   regresiona el caso "posiciones reales de footprints" que Fase 1-3
   siempre tuvo.

Si CUALQUIER gate falla, `AskUserQuestion` antes de mergear. No forzar
merge con violaciones nuevas.

---

## Bloque 4 — Consolidación documental (30 min)

**Objetivo:** dejar el registro claro para que reintento de sesión 31
tenga contexto completo.

### Actualizaciones

1. **`docs/BACKLOG.md`:**
   - F-V1-02: mover a "cerrado en sesión 31b" con detalle del fix
     (`delete_footprint` + pre-check `DUPLICATE_REFS`).
   - F-V1-01: mover a "cerrado en sesión 31b".
   - Deuda técnica derivada (si aplica): pregunta abierta sobre si el
     pre-check debería expandirse a otras validaciones estructurales
     (ej. footprints sin ref, footprints con `net` inválido). Nueva
     entrada P3/P4 si corresponde.

2. **`docs/DECISIONES.md`:**
   - D-31b.1 (candidato): semántica de `delete_footprint` (D1, D2 de
     arriba) formalizada.
   - D-31b.2 (candidato): pre-check `DUPLICATE_REFS` en `route_board`
     como patrón para futuras validaciones estructurales.

3. **`docs/CONTEXT.md`:** estado post-sesión 31b, fixes aplicados,
   próximo paso = reintento de sesión 31 sobre `working/` reutilizado.

4. **`docs/historico/sesiones/31b-reporte.md`:** reporte de la sesión con
   formato heredado. Bloques ejecutados, evidencia por hipótesis, tests
   agregados, decisión sobre D4 (reintento sobre working/ reutilizado)
   confirmada.

### Pre-merge

- Diff completo revisado.
- Todos los gates verdes.
- `AskUserQuestion` al arquitecto antes de mergear con: diff, resumen
  ejecutivo, confirmación de D4 (reintento de sesión 31 arranca desde
  Bloque 2 sobre `working/` intacto).

---

## Criterios de éxito

1. **Éxito pleno:** H1, H1a, H2 confirmadas con evidencia contra motor
   real. Todos los gates verdes. Merge limpio. Fixes acotados (<100
   líneas efectivas totales, esperable dado el precedente sesión 30).
   Reintento de sesión 31 desbloqueado.

2. **Éxito parcial con matiz:** una de las tres hipótesis se refuta,
   pero las otras dos avanzan. `AskUserQuestion` sobre cómo cerrar.
   Ejemplo: H1a (pre-check) refutada por falso positivo, pero H1
   (`delete_footprint`) y H2 (`board_bbox`) sí. Se puede mergear H1+H2 y
   agendar H1a como sesión separada.

3. **Aprendizaje por nueva refutación:** el fix diseñado no resuelve el
   bug (patrón sesión 26). Reportar honestamente, revertir cambios,
   escalar. No mergear un fix no verificado.

4. **Aprendizaje por scope creep detectado:** durante la ejecución
   aparece tentación de expandir alcance. Registrar y no expandir.
   `AskUserQuestion` antes de tocar algo fuera de F-V1-01/F-V1-02.

---

## Entregables

1. **Rama** `sesion/31b-fix-delete-footprint-y-bbox` mergeable a
   `master`.
2. **Tool nueva** `delete_footprint(ref, kiid=None, strict=True)` en
   `src/kicad_mcp/`.
3. **Pre-check** `DUPLICATE_REFS` en `route_board`.
4. **Fix** de `board_bbox_mm` leyendo Edge.Cuts.
5. **Tests nuevos:** unit + integration + canario permanente.
6. **Fixtures nuevos** en `tests/fixtures/` (duplicate-refs-minimal,
   footprints-at-origin-with-edge).
7. **Reporte** `docs/historico/sesiones/31b-reporte.md`.
8. **Actualizaciones** en `docs/BACKLOG.md`, `docs/CONTEXT.md`,
   `docs/DECISIONES.md`.

---

## Fuera de alcance

- Modificar `validation-suite/level-a/anavi-dev-mic/` — se preserva
  intacto para reintento de sesión 31.
- Expandir `delete_footprint` con cascade a tracks huérfanos (D2:
  explícitamente diferido).
- Expandir el pre-check a otras validaciones estructurales — se registra
  como pregunta abierta en BACKLOG, no se implementa acá.
- Arrancar el reintento de sesión 31 durante esta sesión.
- Features nuevas al MCP.
- Cualquier deuda de BACKLOG no relacionada con F-V1-01/F-V1-02.

---

## Env vars

Sin cambios respecto a sesiones anteriores.

---

## Cierre esperado

Sesión 31b cerrada con:

- Rama mergeada a master.
- F-V1-02 (P0) cerrado con fix verificado contra motor real + canario.
- F-V1-01 (P1) cerrado con fix verificado.
- Reintento de sesión 31 desbloqueado — arrancará desde Bloque 2 sobre
  el `working/` de ANAVI Dev Mic ya preparado en sesión 31.
- Regla de disciplina cumplida: fix quirúrgico, no expansión.

**Próxima sesión: reintento de sesión 31 (llamémosle 31c o 32-pre según
convención que uses)** — arranca sólo cuando sesión 31b esté cerrada
con todos los gates verdes y mergeada.

**Recordatorio operacional:** el ejecutor debe respetar la regla de
alcance. Si aparece durante la ejecución cualquier decisión de diseño
no cubierta por D1-D4, `AskUserQuestion` en vez de improvisar. Las 4
decisiones cerradas arriba son el marco — todo lo demás es consulta.
