# ADR-0012 — `route_board`: contrato disco==memoria==`err_post` (D-23.2)

**Fecha:** 2026-07-24 · **Estado:** aceptado · **Fuente:** sesión 24
(fix de F-D4-02, investigación previa en sesión 23)

## Contexto

La investigación de sesión 23 (`docs/investigacion/23-fd4-02.md`) reprodujo
3/3 veces, con evidencia bit-exacta, que `route_board` sobreestimaba
sistemáticamente sus propios errores DRC reportados y dejaba el `.kicad_pcb`
en disco roto de forma indefinida. La causa raíz **no** era protección
ausente ni un handle IPC obsoleto — ambas hipótesis originales del
arquitecto se descartaron con evidencia — sino un **bug de orden de
medición + falta de persistencia**:

1. `route_board` medía `post_report = run_drc(pcb_path)` sobre la salida
   **cruda** de Freerouting, antes de que corriera su propio bloque de
   protección (`refill_zones()` + `enforce_hole_clearance()`, workaround
   F-D3-01/F-D3-03 de sesión 21 para un bug de `kipy` 0.7.1).
2. Ese bloque **sí** arreglaba el clearance contra la zona GND en el board
   *vivo*, pero `route_board` nunca lo persistía a disco — no había ningún
   `save_board()` posterior. El disco quedaba con la salida cruda (rota)
   hasta que el llamador invocaba `save_board()` manualmente, paso no
   documentado como obligatorio.

Sesión 23 Bloque 3 confirmó además, con un board sintético, **por qué** el
refill es necesario y no cosmético: Freerouting no respeta el `(plane)` de
una zona de cobre como exclusión de ruteo para nets ajenos al dueño de la
zona — lo trata como área libre. El clearance contra la zona solo se logra
por post-procesamiento (refill+enforce) o inyectando un keepout real al DSN
(opción descartada por costo, ver investigación §Bloque 4 Opción Y).

## Decisión — D-23.2

**Cuando `route_board` termina OK, disco == memoria == `err_post`
reportado.**

Implementación (Opción X de la investigación, recomendada por el agente y
confirmada por el arquitecto): reordenar el pipeline de `route_board` para
que la medición de `post_report`/`por_tipo`/`err_introducidos` ocurra
**después** del bloque `refill_zones()` + `enforce_hole_clearance()`, y
agregar un `save_board()` explícito al final de ese mismo bloque (solo
cuando `refill and zones_existentes > 0 and reloaded is True` — mismo guard
condicional que ya existía para el refill; si el llamador desactivó
`refill` o no hay zonas, el disco sigue siendo la salida cruda de
Freerouting por diseño, sin autoguardado sorpresa).

Efecto: el JSON que `route_board` devuelve dejó de mentir. Un `run_drc()`
independiente inmediato, sin que el llamador tenga que saber que debe
invocar `save_board()` aparte, coincide con lo reportado.

### Código de error `POST_ROUTE_PERSIST_FAILED`

Si el `save_board()` nuevo falla (KiCad ocupado, IPC caído), `route_board`
levanta `POST_ROUTE_PERSIST_FAILED`. Semántica: el board **vivo** ya tiene
el clearance arreglado por refill+enforce, pero no se pudo escribir a
disco — es un fallo de la propia escritura del proceso, **distinto** de
`EXTERNAL_EDIT_DETECTED` (que indica que algo *externo* modificó el
archivo). El llamador puede reintentar `save_board()` manual o descartar
los cambios; el board vivo no se toca ni se fuerza un reload que lo
revertiría al estado crudo. No es un código renombrado (F3 intacta) — es
adición pura, documentada en `docs/specs/tool-catalog.md` en el mismo
commit (DoD #2).

## Alcance — solo `route_board`

`fill_zones` y `add_zone(fill=True)` invocan internamente la misma
combinación `refill_zones()` + `enforce_hole_clearance()` y sufren, en
teoría, el mismo patrón conceptual de "el vivo se arregla pero el reporte
inmediato/disco puede no reflejarlo". **No se tocan en este ADR ni en la
sesión que lo origina.** El arquitecto fue explícito: causa raíz → cambio
mínimo → test de regresión → dogfooding, sin ampliar superficie. Extender
el contrato D-23.2 a esas dos tools queda diferido a una sesión de
generalización posterior — este ADR no debe leerse como que el alcance
limitado es una decisión permanente, sino como la aplicación disciplinada
del cambio mínimo que cierra la evidencia disponible hoy.

## Consecuencias

- El contrato observable de `route_board` cambia: el disco queda escrito
  con el estado **final** (post-refill), no solo con la salida cruda de
  Freerouting. Cualquier flujo que dependiera implícitamente del guardado
  "sin refinar" queda desactualizado — no se detectó ninguno en el código
  existente (el `post_report` viejo solo alimentaba el payload/audit/log,
  ningún control de flujo).
- El snapshot de disco que `route_board` registra (mtimes para
  `EXTERNAL_EDIT_DETECTED`) se recolecta **después** del nuevo
  `save_board()`, no antes — de lo contrario quedaría stale y el propio
  guardado de `route_board` dispararía un `EXTERNAL_EDIT_DETECTED` espurio
  en la siguiente lectura.
- Costo de rendimiento: un `save_board()` adicional es barato (ya se hacía
  uno equivalente al inicio del pipeline, D-14.3).

## Riesgos / diferidos

- El mecanismo de `enforce_hole_clearance` específico para vías (crear
  keepout `via_*` por vía de net ajeno) no se activó en ninguna de las 3
  reproducciones de sesión 23 — el arreglo observado proviene enteramente
  del `refill_zones()` plano. Deuda técnica D-23.3 (issue R16), diferida a
  P3/P4; no se toca en este ADR.
- Si dogfooding futuro (D5+) revela que el refill+enforce no alcanza a
  arreglar el 100% de los casos (el propio docstring de
  `enforce_hole_clearance` dice "A VECES"), la Opción Z de la investigación
  (extender el loop de vías) queda como refuerzo de robustez a evaluar con
  evidencia real de intermitencia — no antes.

## Extensión de alcance (sesión 27)

Con D-23.2 ratificado 5/5 en producción (2/2 regresión sesión 24 + 3/3
dogfooding D5 sesión 25), la generalización que la sección anterior dejó
diferida procedió en sesión 27.

**Tools cubiertas por el contrato D-23.2, actualizado:** `route_board`,
`fill_zones`, `add_zone(fill=true)`. `add_zone(fill=false)` queda fuera por
diseño — sin fill no hay refill+enforce que persistir, ni bug conceptual que
cerrar.

**Hallazgo de la lectura previa a implementar:** la sospecha inicial de que
`fill_zones`/`add_zone` no llamaban a `enforce_hole_clearance()` era
incorrecta — ambas ya lo hacían desde sesión 21 (F-D3-01,
`src/kicad_mcp/tools/pcb.py`, dentro de `fill_zones` y del `if fill:` de
`add_zone`). Lo único que faltaba, en las dos, era la mitad "persistencia" del
contrato: `save_board()` explícito tras el refill+enforce, con manejo de
fallo visible y mtimes de snapshot recolectados **después** del save (mismo
hallazgo #31 de sesión 24: recolectarlos antes deja `latest_disk_mtimes`
stale y el propio guardado dispara un `EXTERNAL_EDIT_DETECTED` espurio en la
siguiente lectura). El cambio quirúrgico resultó más chico que lo
anticipado.

**Código de error `POST_ZONE_PERSIST_FAILED`.** Compartido entre las dos
tools nuevas (no uno por tool) — misma semántica en ambas: el pipeline de
zona (refill + enforce si aplica) completó en el vivo, pero `save_board()`
falló al persistirlo. `POST_ROUTE_PERSIST_FAILED` (existente, `route_board`)
y `POST_ZONE_PERSIST_FAILED` (nuevo) son **semánticamente equivalentes** —
se discriminan por origen del llamador (el agente ya sabe qué tool invocó),
no por semántica de código. Unificarlos en un solo código queda como deuda
de bajo impacto, diferida a después de que Fase 3 cierre.

**Diferencia deliberada respecto a `route_board`: sin campo `drc` en el
payload.** `route_board` ya reportaba `drc.err_post` en su contrato JSON
desde sesión 17 (P2.2) — extender esa medición a él fue continuidad de
contrato. `fill_zones`/`add_zone` nunca tuvieron un campo `drc`; agregarlo
habría sido un cambio de contrato JSON en dos tools baratas y de uso
frecuente (`fill_zones` se llama de forma idempotente en flujos existentes,
ver `tests/test_zones_e2e_gui.py`), sumando un `run_drc()` (subprocess
`kicad-cli`, del orden de segundos) a cada llamada. Para estas dos tools el
contrato D-23.2 se reduce a su núcleo — **disco == vivo** — sin medir ni
reportar DRC. El `run_drc()` que el agente ya puede invocar por su cuenta es
lo que pasa a ser fiel al estado persistido, que es el objetivo real del
contrato.

**`add_zone(fill=true)`, detalle de implementación:** el `store.register()`
de mtimes de disco vive dentro del mismo `if fill:` que dispara el
refill+enforce+save; la rama `fill=false` conserva `register(state,
mtimes=None)` (snapshot vivo, sin persistencia) — comportamiento sin cambios
respecto a antes de sesión 27.

## Alternativas descartadas

- **Opción Y — inyectar keepout real al DSN por-net vs zona:** previene el
  problema en el origen (confirmado viable en sesión 23, Bloque 3) pero
  costo alto (módulo nuevo de post-procesamiento del DSN, riesgo de
  sobre-restringir ruteo cerca de pads propios). Descartada por el
  arquitecto para esta ronda; el post-procesamiento existente ya demostró
  funcionar 100% de las veces en las reproducciones disponibles.
- **Generalizar a `fill_zones`/`add_zone(fill=True)` en la misma sesión:**
  descartado explícitamente para mantener el cambio mínimo y el test de
  regresión enfocado en la causa raíz confirmada.

## Extensión F-V2 (sesión 32b)

Sesión 32 (Validation Suite Nivel B-01) descubrió, y sesión 32b cerró, un
modo de falla del contrato D-23.2 no cubierto por la extensión de sesión 27:
el bloque de refill+enforce+save de `route_board` está condicionado a
`reloaded is True` (`reload_board_from_disk()` tuvo éxito). Esa recarga es
una **mutación sin reintento** (D-07.1): un `AS_BUSY` transitorio de KiCad
basta para que falle una sola vez, y hasta sesión 32b la excepción se
descartaba en silencio (`except KicadMcpError: reloaded = False`) — sin
`POST_ROUTE_PERSIST_FAILED`, sin ningún error visible, `route_board` devolvía
éxito normal con el refill de seguridad contra D-19.1 sin correr. Reproducido
de forma independiente en el audit log de sesiones 31c y 32
(`docs/BACKLOG.md` entrada `F-V2-REFILL-SILENCIOSO`).

**Por qué el guard `reloaded is True` NO se relaja.** La opción obvia —
desacoplar el refill de la recarga, refillear igual aunque la recarga haya
fallado — es incorrecta: si la recarga falló, el board vivo sigue
reflejando el estado **pre-ruteo** (el `save_board` implícito de D-14.3 bajó
live→disco *antes* de que Freerouting escribiera el ruteo). Refillear y
guardar ese vivo desactualizado pisaría el ruteo recién persistido en disco.
El guard existente es correcto y se mantiene sin cambios.

**Código de error `POST_ROUTE_REFILL_SKIPPED`** (adición pura al `StrEnum`,
F1/F3 intacta — mismo estándar que `POST_ROUTE_PERSIST_FAILED` de sesión 24
y `DUPLICATE_REFS` de sesión 31b). Se levanta únicamente cuando: `refill=true`
(el llamador pidió el refill), `zones_existentes > 0` (había algo que
refillear) y la recarga fue intentada y lanzó una excepción real
(`reload_error is not None`). Los otros dos motivos de que `reloaded` no sea
`True` — editor cerrado (`"skipped_editor_closed"`), board de otro proyecto
abierto (el reload ni se intenta) — son caminos de diseño ya documentados en
`tool-catalog.md` vía el campo `reloaded`: no rompen ningún contrato y NO
levantan error, sólo se exponen como `zones.refill_skipped_reason` para
diagnóstico honesto (sin ambigüedad para el llamador sobre por qué
`zones.refilladas` es `0`).

Nombre elegido sobre la alternativa `POST_ROUTE_REFILL_FAILED`: el refill
**nunca se intentó** (se saltó porque la recarga previa falló) — "FAILED"
sugeriría que `refill_zones()` corrió y no pudo completar, que es exactamente
la semántica que ya tiene `POST_ROUTE_PERSIST_FAILED` (el refill+enforce SÍ
corrieron; falló el `save_board()` posterior). "SKIPPED" distingue los dos
modos de falla sin ambigüedad.

**Punto del pipeline donde se levanta: al final, no en el guard.** Levantar
el error inmediatamente en el guard (antes de DRC post-route, snapshot y
`store.mark_live_stale`) abriría una ventana de corrupción: el flag
`live_stale` quedaría en `False` (nunca llega a marcarse) con el disco
adelante del vivo, y un `fill_zones()` posterior pasaría
`_guard_live_stale()` sin ser rechazado — su propio `save_board()` pisaría el
ruteo recién escrito. El raise se pospone hasta después de que el DRC
post-route corra, el snapshot de disco se registre y
`store.mark_live_stale(snap_id)` se aplique; el `audit_record` se escribe
siempre (con o sin error), conservando el `result` forense
(`reloaded`, `zones_existentes`, `zones_refilladas`,
`refill_skipped_reason`) que fue precisamente lo que permitió detectar este
bug en sesión 32 — más el `error_code` cuando corresponde.

**Alcance: `route_board` únicamente — H2 refutada por inspección.** El
prompt de sesión 32b hipotetizaba que el mismo bug podía afectar
`fill_zones()` y `add_zone(fill=true)` (D2, cobertura simétrica). Inspección
del código lo refuta: ninguna de las dos llama `reload_board_from_disk` en
absoluto — abren con `_guard_live_stale()` (rechazan si el disco ya está
adelante del vivo) y su único modo de falla, `save_board()`, ya levanta
`POST_ZONE_PERSIST_FAILED` (sesión 27, mismo ADR). No existe la llamada cuya
excepción se pudiera descartar en silencio — el cierre del contrato para
estas dos tools es por evidencia (no tienen el camino silencioso), no por
código simétrico nuevo.

**Observación registrada, no accionada esta sesión:** `delete_tracks_bulk`
(`src/kicad_mcp/tools/pcb.py`) llama `refill_zones()` cuando borra tracks de
zonas de cobre, pero sin `enforce_hole_clearance()` ni `save_board()`
posterior — asimetría real con el contrato D-23.2 tal como se aplica a las
otras tres tools. Fuera del alcance acordado de sesión 32b (fix quirúrgico
sobre F-V2-REFILL-SILENCIOSO); anotado en `docs/BACKLOG.md` para evaluación
futura.
