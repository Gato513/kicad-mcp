# Sesión 39 — DT2: decorador `@mutating_tool` para unificar el preámbulo transversal

**Rama:** `sesion/39-mutating-tool-decorator` desde `master` remoto en
`989c505` (o su sucesor legítimo, avanzado por PR mergeado con CI verde —
con branch protection activa, avances de `master` son información legítima;
el agente confirma el estado real en P3).
**Tipo:** deuda técnica estructural (DT2 del backlog). Prerrequisito
declarado de DT1 (sesión 40, partición de `tools/pcb.py`). Primera sesión
del ciclo que sale del frente de encoders ad-hoc y ataca el modo de fallo
transversal del proyecto: preámbulo repetido literal ×19 sin lugar único
donde vivan las políticas.

## Objetivo

Existe un decorador (o, si el análisis lo pide, un context manager /
pequeña jerarquía de decoradores; ver H1) que captura el preámbulo
transversal repetido hoy en las ~19 tools mutantes de `tools/*.py`, y todas
esas tools están aplicándolo, con reducción medible del boilerplate
transversal y **cero cambio observable** en la API pública, la taxonomía
de errores (F3), o el comportamiento de la suite completa.

## Motivación (breve)

DT2 del backlog: boilerplate transversal ×19 sin decorador. El costo real
no es el LOC — es que sin un lugar único, cada política transversal (por
ejemplo cambios de auditoría, budget-check, manejo estructural de
excepciones IPC) se aplica o se olvida a mano en cada mutante. Sesión 40
(DT1) va a partir `tools/pcb.py` en varios archivos; si el preámbulo sigue
siendo repetido literal, DT1 fija la deuda en más archivos en vez de
reducirla. DT2 antes de DT1 es la secuencia correcta declarada en el
CONTEXTO §8 y en el roadmap del §9. Esta sesión ejecuta esa secuencia.

## Hipótesis (con criterio de refutación explícito)

**H1 — Las ~19 tools mutantes comparten un preámbulo lo suficientemente
uniforme como para caber en un decorador único, posiblemente
parametrizable con 1–3 parámetros simples (categoría de mutación, si
persiste a disco según el catálogo, etc.).**
**Refutación:** al inspeccionar los 19 preámbulos reales, aparecen dos o
más variantes estructurales que no caben en parámetros triviales — por
ejemplo, algunas mutantes hacen validación cruzada con estado que otras
no tocan, o el manejo del snapshot difiere de forma esencial entre
familias. En ese caso hay dos opciones válidas: (a) proponer una pequeña
jerarquía de decoradores (2–3 variantes especializadas, no un solo
decorador con 6 parámetros ocultando complejidad), o (b) **escalar
partición de sesión** — 39a analiza y diseña con ADR-0014, 39b implementa.
El agente decide con evidencia y consulta al arquitecto antes de tomar
cualquiera de las dos opciones; el default "un solo decorador
parametrizado" no se fuerza.

**H2 — Son efectivamente ~19 mutantes hoy; ni crecieron ni se
consolidaron desde la última auditoría.**
**Refutación:** el conteo real difiere. Si son más (20–25), el trabajo
sigue cabiendo pero se registra la deriva. Si son menos (crecieron por
consolidación previa), es señal positiva y se registra. Si son muchas
más (30+) o muchas menos (<10), es señal de que el catálogo de tools
está desactualizado — se anota como candidato de higiene documental y se
continúa con el número real. Fuente cruzada: `docs/specs/tool-catalog.md`
+ `ADR-0012` + código real en `tools/*.py`; discrepancias entre las tres
son un dato en sí mismo.

**H3 — Aplicar el decorador es refactor puro: la suite completa
(ofline + integration + integration_gui, hasta donde el agente pueda
correrla localmente) pasa sin ningún cambio de test, código de error o
comportamiento observable.**
**Refutación:** algún test cambia, alguna excepción se emite distinto,
algún consumidor externo (LLM cliente vía tool-catalog) percibe algo
distinto. Cualquiera de esas señales requiere análisis antes de aceptar:
o el cambio es una consolidación beneficiosa (algún preámbulo estaba
divergiendo por accidente y el decorador lo normaliza correctamente,
resultado válido con nota en P9), o es una regresión (el decorador
tomó una decisión que no cabía a alguna mutante en particular; investigar
qué mutante, por qué, y decidir si excluirla o ajustar el decorador).

## Verificación de premisa (P3)

Antes de tocar código:

1. **`master` remoto en `989c505`** o su sucesor por PR con CI verde. Si
   avanzó por push directo (branch protection no aplicada o
   bypasseada): parar y escalar.
2. **Branch protection sigue activa** sobre `master` con los cuatro
   checks obligatorios. Verificar con `gh api` o delegar la verificación
   al arquitecto.
3. **Estado de `docs/BACKLOG.md`:** `P1-1` cerrado (sesión 37+38),
   `P1-2` (`kiid`) abierto sin sesión asignada, `DT2` sigue registrado
   como pendiente. Si el BACKLOG ya lo cerró alguien al margen o le
   asignó otra sesión, escalar.
4. **Conteo real de mutantes.** Fuente triple:
   `docs/specs/tool-catalog.md` (persistencia declarada por tool),
   `docs/ADR/0012-*.md` (asimetría persistencia), y código real (grep de
   registros en `tools/*.py`). Reportar los tres números; si difieren,
   registrar como P9 y usar el del código real como verdad para esta
   sesión.
5. **Anatomía real del preámbulo transversal.** Antes de tocar nada,
   listar las líneas del preámbulo típico y hacer una tabla mutante-por-
   mutante indicando cuáles líneas están presentes, cuáles no, y cuáles
   varían. Ese análisis es el insumo directo de H1 — no se salta.
6. Confirmar que `errors.py` conserva los 27 códigos de F3 y su
   estructura (ninguna reorganización pendiente). El decorador va a
   tocar cómo se emiten errores; si la taxonomía está en flujo,
   escalar.

## Alcance

### Dentro

- Análisis estructural del preámbulo (P3 punto 5) que fundamenta H1.
- Diseño del decorador o pequeña jerarquía, con las decisiones de
  arquitectura que emergen documentadas: dónde inyecta el estado,
  cómo maneja las excepciones (passthrough vs wrap), cómo interactúa
  con el snapshot, cómo se testea aisladamente.
- **ADR-0014 (o siguiente número libre)** describiendo el patrón,
  las decisiones de diseño y por qué se descartaron alternativas. La
  API interna del decorador es superficie de gobernanza: cualquier
  tool nueva escrita después de esta sesión va a decidir si aplica el
  decorador leyendo este ADR.
- Implementación del decorador en el módulo apropiado (probablemente
  `tools/_mutating.py` o `tools/_common.py` — el agente decide con
  justificación en P9).
- Aplicación del decorador a las ~N tools mutantes reales (el número
  emerge de P3). Cambio quirúrgico: sólo remover las líneas del
  preámbulo repetido y aplicar el decorador; nada más.
- Test unitario del decorador aislado — al menos: caminos normales,
  manejo de excepciones IPC, manejo de excepciones inesperadas, y
  cualquier rama parametrizada del decorador.
- Reducción medida del boilerplate: LOC antes/después, tanto por tool
  individual como agregado, en el reporte.
- Actualización del `BACKLOG.md`: DT2 cerrado.
- Reporte con propuesta para sesión 40 (DT1).

### Fuera

- **Cualquier cambio a la lógica interna de las tools mutantes** más
  allá de reemplazar el preámbulo por el decorador. Si al pasar por
  ahí el agente ve un bug, oportunidad de simplificación o
  refactorización — al backlog, no se toca acá.
- **Refactor de `tools/pcb.py` más allá de aplicar el decorador.**
  DT1 es sesión 40.
- **Cambios a `errors.py` o a la taxonomía F3.** El decorador debe
  emitir los mismos códigos que hoy en los mismos casos; si necesita
  emitir uno nuevo, es ADR de F3 aparte.
- **Cambios a `bridge/` o `toon/`.** Ni una línea.
- **Sanitización de `kiid` (P1-2 abierto).** Aunque el paso por
  encoders sea inevitable, `kiid` requiere decisión de diseño propia
  y su fix vive naturalmente dentro de DT1 (sesión 40) según la nota
  del reporte de sesión 38. No se toca acá.
- **Aplicar el decorador a tools no mutantes** (queries, meta,
  export puros). La superficie de esta sesión son las mutantes.
- **Actualización del `tool-catalog.md` o `ADR-0012`** salvo que P3
  punto 4 revele que están estrictamente desactualizados y la
  actualización sea de una línea. Si es cambio mayor, sesión aparte.

## Fronteras aplicables

- **F1.** No se toca `toon/`.
- **F3.** Taxonomía de errores es API pública. El decorador debe
  preservar exactamente qué códigos se emiten y en qué casos. Si algún
  patrón actual emitía código A y el decorador va a emitir código B
  por consistencia, aunque "sea mejor", es cambio de F3 y se escala.
- **F4.** Cambios dentro de `tools/`. Si el decorador vive en
  `tools/_mutating.py`, es transversal dentro de `tools/`, no
  atraviesa capas.
- **F5.** Sin dependencias nuevas. `functools`, `contextlib` y stdlib
  son suficientes.

F2 no aplica directamente.

## Criterio de éxito (falsable)

1. **`@mutating_tool` (o el nombre que el agente elija con
   justificación) existe** con su ADR-0014 asociado y test unitario
   propio.
2. **Aplicado a las N mutantes reales** (N emerge de P3). Ninguna
   mutante quedó sin aplicar salvo justificación registrada en P9 con
   traza al código de por qué esa mutante particular no cabía. Si N
   quedan sin aplicar es H1 refutada — resultado válido con partición
   de sesión declarada.
3. **Reducción medible del boilerplate.** El reporte incluye:
   LOC del preámbulo removido por tool, agregado, y qué % del archivo
   `tools/*.py` representa. Sin número duro es criterio no cumplido.
4. **Suite completa verde offline** — `pytest -m "not integration and
   not integration_gui and not integration_gui_slow"` reporta
   `N passed` con `N == 392` (el baseline post-38) más los tests
   nuevos del decorador aislado (`M`). Diferencia justificada línea
   por línea: cualquier test viejo que necesitó ajuste es señal de
   que H3 se refutó — investigar antes de aceptar.
5. **Suite integration verde** hasta donde el agente pueda correrla
   localmente (con `kicad-cli` disponible). Si no puede correr algún
   subconjunto por infraestructura, lo declara. La suite completa se
   valida por CI en el PR.
6. **CI verde en el PR** contra `master`, con los 4 checks corriendo
   sobre este cambio no trivial. Este es el primer PR post-branch-
   protection sobre un refactor transversal grande — el gate importa
   más que nunca acá.
7. **API observable por el LLM cliente inalterada:** las 19 tools
   siguen apareciendo en el catálogo con la misma firma, mismos
   códigos de error, mismos mensajes. Verificable con
   `tools_catalog_view` o el mecanismo equivalente que el proyecto
   use para exponer el catálogo.
8. **Cero cambios a la lógica interna** de las mutantes más allá del
   preámbulo. Auditoría del diff: cada tool tocada debe tener la
   forma `borrado del preámbulo repetido + aplicación del
   decorador`, nada más. Cualquier cambio adicional debe estar
   justificado en el reporte.

## Riesgos a priori

- **El "preámbulo" no es tan uniforme como la auditoría lo describía.**
  La auditoría probablemente lo generalizó; la realidad muestra
  variaciones. H1 lo captura, pero preparate para que la sesión
  pueda partirse (39a/39b) si el análisis revela suficiente varianza.
- **El decorador oculta el flujo y hace debug futuro más difícil.**
  Mitigación: docstrings detalladas del decorador, ADR con ejemplos
  del "antes/después" para cada patrón cubierto, test unitario que
  ejerce las ramas explícitas.
- **Overhead de rendimiento del decorador.** El CONTEXTO §1 registra
  techo de 63 footprints; si el decorador introduce overhead
  significativo por mutación, podría bajar ese techo. Riesgo bajo
  (functools.wraps es prácticamente gratis) pero verificable con al
  menos una tool integration_gui_slow corrida antes y después. Si el
  agente no puede correrla local, lo declara para que lo verifique
  el CI o el arquitecto.
- **Alguna mutante actualmente maneja excepciones de forma única y
  el decorador la normaliza.** Si es fix accidental (mutante estaba
  emitiendo el código equivocado), es P9 con nota; si es regresión
  (mutante necesitaba ese manejo por razón concreta), escalar antes
  de mergear.
- **`tools/pcb.py` es el god module** — 19 mutantes es agregado, pero
  varias viven en `pcb.py`. Aplicar el decorador ahí sin
  comprometerse a partir el archivo puede dejar un `pcb.py` con
  decoradores + estructura god module intacta. Es aceptable —
  DT1 es sesión 40 — pero el reporte lo debe anotar como estado
  intermedio, no como cierre estructural de `pcb.py`.
- **`kiid` en P1-2 abre la posibilidad** de que sesión 40 tenga que
  tocar cosas que esta sesión toca. Riesgo de conflicto de merge
  bajo (no hay paralelismo humano) pero el orden importa: primero
  DT2 mergea, después DT1 arranca.

## Entregables

1. `src/kicad_mcp/tools/_mutating.py` (o ubicación decidida por el
   agente con justificación P9) con el decorador y su docstring de
   arquitectura.
2. Las N `tools/*.py` refactorizadas para aplicar el decorador, cada
   una con diff quirúrgico (borrado del preámbulo + aplicación).
3. `docs/ADR/0014-mutating-tool-decorator.md` (o el nombre decidido
   por el agente) siguiendo el estilo de los 14 ADRs existentes.
4. `tests/test_mutating_tool.py` (o el nombre convencional del
   proyecto) con cobertura del decorador aislado.
5. `docs/BACKLOG.md` con DT2 cerrado.
6. `docs/historico/sesiones/39-reporte.md` con:
   - Números duros (N mutantes reales, LOC antes/después, tests
     antes/después).
   - Anatomía del preámbulo (P3 punto 5) documentada.
   - Decisiones de arquitectura del decorador y por qué se
     descartaron alternativas (referenciando el ADR).
   - Propuesta para sesión 40 (DT1), preferentemente con la nota de
     integrar el fix de `P1-2 (kiid)` en el mismo alcance dado que
     los mismos encoders se refactorizan.
7. Todo en `sesion/39-...`. Ningún commit directo a `master` —
   regla operativa post-branch-protection.

## Nota preventiva — variantes de "aflojá X" que se escalan

- **"Ya que estoy en las mutantes, arreglo bug X que vi al pasar":**
  no. Al backlog. Alcance quirúrgico.
- **"El decorador podría también manejar Y (cache, retry,
  logging)":** no. Reemplazar el preámbulo actual, nada más. La
  vez que empezó a crecer un helper "de yapa" es como se creó el
  preámbulo repetido en primer lugar.
- **"Un solo decorador con 6 parámetros cubre todo":** parar y
  consultar. Si el análisis pide varias variantes, mejor jerarquía
  pequeña que decorador todopoderoso. Si pide partición de sesión,
  proponer 39a/39b.
- **"Aprovecho para arrancar DT1 (partir `pcb.py`) en la misma
  sesión":** no. Sesión 40. Cada sesión es una unidad.
- **"El decorador se ve mejor si cambia cómo se emiten los errores
  para hacerlos más consistentes":** F3. ADR aparte.
- **"Aplico también a las tools no mutantes por consistencia":** no.
  Alcance son las mutantes.
- **"Aprovecho para resolver `P1-2 (kiid)` de una vez":** no. Sesión
  40 lo va a tocar naturalmente al partir los encoders. Acá sólo
  DT2.
- **"Actualizo el `CONTEXTO_CHAT.md` que sé que tiene drift":** no.
  Eso es acción del arquitecto.

Sesión 38 cerró el frente de encoders sin residuo — este ciclo
empieza uno nuevo y más grande. El estándar de disciplina se hereda:
alcance quirúrgico, hallazgos escalados en P3 antes de improvisar,
diff anticipado antes de regenerar goldens (si aparecen), veredicto
explícito por decisión que no se toma sola. Si en P3 el análisis
revela que DT2 es más grande que M y no cabe en una sesión, la
partición 39a/39b es respuesta válida — mejor eso que forzar todo
en un commit gigante que nadie va a poder auditar bien.
