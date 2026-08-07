# Sesión 36 — Sanitización de los 3 encoders ad-hoc + un golden por formato

**Rama:** `sesion/36-sanitizacion-encoders-ad-hoc` desde `master`.
**Tipo:** deuda técnica dirigida (P1-1 del backlog) + arranque incremental
de DT4 (formatos ad-hoc que erosionan el espíritu de F1).

## Objetivo

Los tres encoders ad-hoc de `tools/pcb.py` — `_encode_tracks`,
`_encode_zones`, `_encode_component_detail` — deben (a) sanitizar
explícitamente cualquier valor string que emiten como cuerpo del formato,
en el mismo punto donde lo emiten, y (b) quedar respaldados por un golden
propio que congele su superficie actual como contrato.

## Motivación (breve)

Los tres formatos ad-hoc (`TRACKS|v1`, `ZONES|v1`, `DETAIL|…`) nacieron para
no tocar F1 desde una sesión que necesitaba emitir datos que el spec TOON
canónico no cubría cómodamente. Cumplen la letra de F1 (spec TOON
inmutable) pero erosionan el espíritu — son formatos de serialización sin
las salvaguardas del canónico (golden, versión rígida, escape probado). El
backlog los registra como P1-1 (falta sanitización, esfuerzo S) y el
CONTEXTO los agrupa bajo DT4. Esta sesión paga la parte inmediata: no
inventa otro formato ni migra a TOON canónico, cierra el hueco de higiene
que hoy tienen los tres.

## Hipótesis (con criterio de refutación explícito)

**H1 — Los 3 encoders no sanitizan hoy caracteres que romperían su propio
parser.** Concretamente: al menos uno de los tres, ante un valor de dominio
que contenga el delimitador del formato ad-hoc (`|`, u otro), un salto de
línea, o una comilla, produce salida ambigua o directamente inválida para
el consumidor esperado.
**Refutación:** al inspeccionar los tres, el agente encuentra que la
sanitización ya está aplicada (in-line o vía helper), o que el input está
garantizado libre de esos caracteres por el modelo de dominio de KiCad y
existe una assertion/validador que lo respalda antes del encoder. En ese
caso H1 se refuta y el alcance se acorta a "solo goldens + un test
adversarial que confirma que el dominio no puede meter esos caracteres"; se
registra por qué la sanitización explícita es innecesaria y qué evidencia
lo prueba.

**H2 — Los tres formatos son estructuralmente distintos entre sí lo
suficiente como para que un golden por formato sea la unidad correcta.**
Un golden por encoder, no un golden compuesto ni tres goldens que en
realidad prueban lo mismo.
**Refutación:** dos de los tres comparten estructura (mismo prefijo, misma
gramática de campos, misma forma de escape) al punto que un golden
compuesto capturaría ambos sin pérdida de fidelidad. En ese caso se decide
explícitamente cuántos goldens produce esta sesión (uno, dos o tres) y por
qué; se documenta la decisión en el reporte para que sesiones futuras que
toquen estos formatos sepan qué contrato se congeló.

**H3 — Estos son los únicos tres formatos ad-hoc de DT4; no hay un cuarto
oculto.**
**Refutación:** al buscar en `tools/` (`grep`-style, no exhaustivo — el
agente elige heurística razonable, ej. cadenas del estilo `|v1`, `|` como
delimitador de nivel superior, u otros patrones ad-hoc que emerjan) el
agente encuentra un cuarto candidato. Si aparece, se anota como
subelemento del backlog (P1-1b o similar, con la ubicación exacta) para
sesión futura; **no se amplía el alcance de ésta**. Esta sesión sigue
cerrando los tres declarados y solo los tres.

## Verificación de premisa (P3)

Antes de tocar nada, el agente confirma:

1. `master` contiene el workflow `.github/workflows/ci.yml` (sesión 35
   mergeada) y los 4 checks de DoD corren en cualquier PR nuevo. Si no está
   mergeada, **parar y escalar** — esta sesión asume que el gate de CI
   protege el trabajo.
2. Los tres encoders siguen existiendo con esos nombres exactos en
   `src/kicad_mcp/tools/pcb.py`. El CONTEXTO cita líneas 809, 3263, 3314
   como referencia — si el archivo se movió, el agente localiza las nuevas
   posiciones y las registra en el reporte.
3. Existe un directorio de goldens de TOON canónico con los 3 goldens
   preexistentes (F1 los protege). El agente localiza la ruta real (el
   prompt no la fija) y agrega los nuevos goldens **en esa misma
   convención** — mismo formato de nombre, mismo estilo de fixture, mismo
   patrón de comparación en el test. No se inventa infraestructura
   paralela.
4. `pyproject.toml` no lista dependencias nuevas respecto a sesión 35. Si
   sí, escalar (F5).

## Alcance

### Dentro

- Sanitización explícita en los 3 encoders, en la función misma, contra al
  menos: delimitador del propio formato, saltos de línea, y comillas. La
  implementación concreta (escape con `\`, cuoting, reemplazo, o `repr`)
  la decide el agente según lo que menos rompa el contrato actual del
  parser del consumidor — la que introduzca menos cambios en la salida
  para inputs "limpios" (los que hoy ya se emiten).
- Un archivo golden por formato (o menos si H2 se refuta), en el
  directorio de goldens que ya existe, con al menos un caso "limpio" y un
  caso "adversarial" (string con delimitador, string con newline,
  string con comilla — todos los que apliquen).
- Un test parametrizado que, por cada formato, compara la salida del
  encoder contra el golden. Si algún cambio futuro altera la salida, el
  test rompe con diff legible.
- Docstring de cada encoder actualizada: qué caracteres escapa, qué
  garantiza, qué golden lo respalda.
- Reporte de sesión con la propuesta concreta para sesión 37.

### Fuera

- **Migrar cualquiera de los tres formatos ad-hoc al TOON canónico.** Eso
  es cambio de F1 vía ADR, no una sesión de higiene. Si el agente ve un
  camino "obvio" para hacerlo — anotarlo como candidata explícita en el
  reporte y **parar**.
- **Refactorizar `tools/pcb.py`.** DT1 tiene su propia sesión (40 en el
  roadmap). Se toca solo lo mínimo dentro de los 3 encoders. Si un encoder
  tienta a "extraer helper compartido" y ese helper cae fuera de los 3,
  parar y anotar.
- **Cualquier cambio en los goldens preexistentes** (los 3 de TOON
  canónico). Son contrato F1 y esta sesión no los altera. Si el agente
  descubre que uno está desactualizado por drift previo, lo anota — no lo
  arregla acá.
- **Sanitización en encoders del TOON canónico.** Están protegidos por
  golden. Si al pasar por ahí el agente ve un caso, lo registra en el
  reporte, no lo toca.

## Fronteras aplicables

- **F1.** El punto delicado. Estos tres formatos "cumplen la letra" de F1
  pero son ad-hoc — los goldens de esta sesión los congelan tal cual son
  hoy. La sanitización debe ser **aditiva sobre inputs sucios**: para
  inputs que hoy ya salen "limpios" (los del uso normal), la salida no
  cambia. Si al agregar sanitización cambian las salidas emitidas hoy en
  algún caso del suite, es una regresión del contrato — parar y escalar,
  no ajustar el golden a la nueva salida.
- **F5.** No se agregan dependencias. Escape con stdlib (`str.translate`,
  `re`, o lo que ya use el proyecto). Si el agente ve necesidad de una
  librería de escape "profesional", escalar.

F2, F3, F4 no aplican directamente a esta sesión.

## Criterio de éxito (falsable)

Todos los siguientes se pueden efectivamente no cumplir:

1. Los 3 encoders emiten sanitización explícita en el mismo cuerpo de la
   función, no delegada río arriba (o H1 refutada con evidencia por qué la
   sanitización explícita es innecesaria).
2. Existen 1, 2 o 3 archivos golden nuevos según el resultado de H2, cada
   uno con caso limpio y caso adversarial. La decisión sobre la cantidad
   está en el reporte con su justificación.
3. Un test parametrizado corre bajo `pytest -m "not integration and not
   integration_gui and not integration_gui_slow"` y pasa contra los
   goldens nuevos.
4. Los 4 checks locales de DoD verdes en la rama (ruff, ruff format,
   mypy, pytest offline). Como CI de sesión 35 está activo, esos 4 checks
   también corren en el PR y **deben ser verdes ahí** — no solo local.
5. Ningún cambio fuera de los 3 encoders y su nuevo test/goldens (salvo
   docstrings). Si hubo un cambio adicional, está justificado en el
   reporte.
6. `docs/BACKLOG.md` marca P1-1 como cerrado (o parcialmente cerrado con
   nota, según lo que efectivamente se hizo).

## Riesgos a priori

- **Formato "DETAIL" sin versión rígida.** El backlog lo llama
  `DETAIL|…` (con puntos suspensivos), sugiriendo que la superficie es
  menos fija que `TRACKS|v1` / `ZONES|v1`. Si el agente termina teniendo
  que decidir qué versión declarar o si declarar una — registrar en el
  reporte como decisión persistente P9, no tomar la decisión en silencio.
- **El input "adversarial" del test golden podría ser irrepresentable en
  el dominio real de KiCad.** Ej.: un net name no puede contener `|` por
  reglas del propio KiCad. Si es así, H1 se refuta parcialmente (el escape
  es defensivo, no correctivo), y el golden adversarial documenta un
  contrato hipotético útil para regresión, no un bug real. Está bien —
  registrar la asimetría en el reporte.
- **`tools/pcb.py` es god module (3402 LOC, complejidad 146).** Alto
  riesgo de conflicto de merge si en paralelo alguien toca esas áreas. En
  este proyecto no hay paralelismo humano, así que el riesgo es bajo, pero
  el agente debe minimizar el área tocada por si alguna vez se vuelve
  relevante (ej. cherry-pick a un branch de curación).
- **Descubrir que un encoder ya sanitizaba pero mal.** Distinto de H1: si
  ya hay escape pero es incompleto (escapa `|` pero no `\n`, por
  ejemplo), la sanitización nueva no es aditiva pura — cambia lo que ya
  existía. Se registra explícitamente en el reporte con la nota de qué
  cambió y por qué la nueva versión es correcta.

## Entregables

- `src/kicad_mcp/tools/pcb.py` con los 3 encoders sanitizados y docstrings
  actualizadas.
- Archivos golden nuevos en la ruta que ya usa el proyecto (cantidad según
  H2).
- Un test parametrizado (o archivo de tests con casos por formato) que
  compara salida contra golden.
- Reporte `docs/historico/sesiones/36-reporte.md` siguiendo la convención
  vigente (número + guión + palabra "reporte", como 35).
- Actualización de `docs/BACKLOG.md` cerrando P1-1 (o dejando P1-1b si
  H3 lo pide).

## Nota preventiva — variantes de "aflojá X" que se escalan

- **"Ya que estoy en `pcb.py`, extraigo N helpers":** no. Alcance son 3
  encoders + goldens. DT1 tiene su sesión, y sin DT2 antes ni siquiera se
  puede empezar bien. Escalar.
- **"Los 3 formatos ad-hoc son fea idea — los migro a TOON canónico":**
  cambio de F1 vía ADR, no una sesión de higiene. Escalar como propuesta
  de ADR aparte.
- **"El escape más limpio es agregar `python-slugify` / `markupsafe` /
  librería X":** F5. Escape con stdlib. Escalar si de veras hace falta,
  con justificación.
- **"Aprovecho para arreglar drift en CLAUDE.md que vi al pasar":** no.
  P1-4 tiene su sesión (~39 en el roadmap). Anotar y seguir.
- **"El test integration_gui_slow que arreglamos en 35 me tienta tocar
  otro test que también parece mal marcado":** no. Si aparece candidato,
  al backlog. Alcance de esta sesión son los 3 encoders.

Si algo en el reporte de esta sesión tiene forma de "expandimos porque
convenía", el arquitecto va a preguntar por qué no se escaló. El respeto
al alcance es parte del criterio de éxito, no un adorno.
