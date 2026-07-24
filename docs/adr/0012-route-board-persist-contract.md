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
