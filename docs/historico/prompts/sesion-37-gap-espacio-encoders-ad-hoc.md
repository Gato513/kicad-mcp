# Sesión 37 — Cerrar el gap del espacio en los tres formatos ad-hoc

**Rama:** `sesion/37-gap-espacio-encoders-ad-hoc` desde `master`.
**Tipo:** hardening — completa P1-1 del backlog (que sesión 36 dejó
parcialmente cerrado por el descubrimiento de H36.1 refutada).

## Objetivo

Los tres encoders ad-hoc de `tools/pcb.py` deben neutralizar el espacio
como delimitador estructural en los campos space-delimited (líneas de
ítem), preservando la tolerancia actual al espacio en el header
`|`-delimited de `_encode_component_detail`. La señal de que el fix es
correcto son los goldens 004/005/006 actualizados **solo** en las líneas
que la sesión 36 marcó como "caracterización" (T4, Z4, pads 4-5). Otras
líneas cambiando serían regresión.

## Motivación (breve)

Sesión 36 aplicó `_sanitize` en los tres encoders y descubrió, por
evaluación activa de H36.1, que `_sanitize` neutraliza `\n`, `|`, `:`, `>`
y control-chars pero **no el espacio** — y el espacio es el delimitador
posicional real de las gramáticas de tracks/zones/pad-detail (a diferencia
de TOON canónico, que es `|`-delimited y por eso tolera espacios). Un
`net_name` como `"GND EN"` sobrevive intacto a `_sanitize` y corrompe el
parsing posicional río abajo (evidencia bit-exacta en `36-reporte.md §H36.1`,
línea `T4`). Sesión 36 documentó el gap como golden de caracterización y
lo escaló a esta sesión. P1-1 queda completado cuando este gap se cierra.

## Ruta elegida por el arquitecto: (a), local

De las dos rutas que 36 propuso, esta sesión implementa la (a) — un
mini-sanitizador local en `tools/pcb.py` que compone `_sanitize` + neutralización
del espacio, aplicado solo en campos space-delimited. La ruta (b) (extender
`_sanitize` con un parámetro opcional) queda descartada por default porque
invertiría la dirección natural de dependencia — `toon/` es núcleo y los
ad-hoc son la deuda, cambiar la API interna de `toon/` para servir a los
ad-hoc es la solución equivocada aunque técnicamente funcione. Si durante
P3 el agente encuentra una razón dura que haga (a) inviable (ej.
descubrir que `_sanitize` no puede componerse sin duplicar lógica no
trivial), **parar y escalar antes de escribir código**, no cambiar a (b)
en silencio.

## Hipótesis (con criterio de refutación explícito)

**H1 — La composición `_sanitize(x)` + `.replace(" ", "_")` (o
`.replace(" ", "-")`, u otra sustitución que el agente proponga) neutraliza
todo caso de espacio estructural en los campos space-delimited afectados
(`net_name` de tracks/zones, `number` de pads).**
**Refutación:** existen espacios "sutiles" que este pipeline no cubre —
tabulaciones, `\u00A0` (non-breaking space), otros separadores unicode. Si
el agente encuentra que `_sanitize` no los toca y son alcanzables desde el
dominio de KiCad, la sustitución debe ampliarse (por ej. a
`re.sub(r"\s", "_", _sanitize(x))`). Se registra como decisión P9 con
justificación.

**H2 — El header `|`-delimited de `_encode_component_detail` (`DETAIL|<ref>|pcb|...`)
**no** requiere neutralización del espacio, porque `|` es el delimitador ahí
y un espacio dentro de `<ref>` no rompe el parser.**
**Refutación:** el agente inspecciona la gramática del header y encuentra
que sí hay algún punto donde el espacio importa (por ej. un consumer
posicional que aún opera sobre el header antes del primer `|`, o un `ref`
que también aparece luego en una línea space-delimited y debería ser
consistente entre header y cuerpo). Si es así, ampliar el fix; caso
contrario, mantener el header como está y documentarlo en el reporte con
la evidencia de que revisar y decidir no-actuar es un resultado válido.

**H3 — El cambio se manifiesta en los goldens exactamente en las líneas T4
(004), Z4 (005) y pads 4-5 (006), y en ninguna otra.**
**Refutación:** al regenerar los goldens el diff toca más líneas que las
esperadas. Si eso pasa: parar, entender por qué (¿existe un caso "limpio"
que también contiene espacio y no fue reconocido como adversarial en 36?
¿el sanitizador nuevo está siendo demasiado agresivo y neutraliza algo que
antes salía intacto?), y **no aceptar el nuevo golden hasta entenderlo**.
Un golden que cambia por razones no anticipadas es señal de regresión, no
de éxito del fix.

## Verificación de premisa (P3)

Antes de tocar nada, el agente confirma:

1. `master` contiene el merge de sesión 36 — es decir, los tres encoders
   ya llaman a `_sanitize` sobre `net_name`/`ref`/`pad.number`, y los
   goldens 004/005/006 existen en `tests/golden/`. Si no, **parar** —
   esta sesión asume el estado de post-36.
2. `docs/BACKLOG.md` refleja P1-1 como parcialmente cerrado por 36, con
   remisión a esta sesión. Si el BACKLOG quedó desactualizado por la
   fricción de aplicación de diffs de 36, es un dato del contexto pero no
   bloquea; se anota y se sigue.
3. `toon.encoder._sanitize` conserva la misma firma que en 36. Si cambió
   (por ejemplo, si alguien la modificó al margen y ya acepta parámetro
   opcional para espacio), la ruta (a) probablemente sigue siendo la
   correcta de todos modos — pero el agente debe confirmar que su
   composición sigue produciendo el efecto esperado. Anota la desviación.
4. **Búsqueda proactiva de un 4to campo space-delimited** en los tres
   encoders (fuera de los tres cerrados en 36: `net_name` de tracks,
   `net_name` de zones, `pad.number`). Si aparece un candidato (ej. otro
   campo interpolado en la misma línea que también podría contener
   espacio en teoría), anotarlo — si es alcanzable desde el dominio,
   incluirlo en el alcance; si no lo es, dejarlo para futuro con
   justificación.

## Alcance

### Dentro

- Mini-sanitizador local en `tools/pcb.py`, en el sitio que el agente
  juzgue más cohesivo (probablemente arriba de los tres encoders, como
  helper privado del módulo). La forma exacta la decide el agente:
  wrapper con nombre explicativo (ej. `_sanitize_for_space_delimited`), o
  inlineado si es una sola línea. Docstring que explique **por qué** existe
  (referencia a sesión 37 y al gap del espacio) — no solo qué hace.
- Aplicación del mini-sanitizador **solo** en los campos space-delimited
  ya identificados: `net_name` en `_encode_tracks` y `_encode_zones`,
  `pad.number` en `_encode_component_detail`. El header
  `DETAIL|<ref>|pcb|...` sigue usando `_sanitize` sin la neutralización de
  espacio (H2 lo confirma).
- Actualización de los 3 goldens en las líneas de caracterización marcadas
  por sesión 36 (T4 en 004, Z4 en 005, pads 4-5 en 006). Si H3 se refuta
  y hay más líneas cambiando, **parar y entender antes de aceptar**.
- Actualización de docstrings de los tres encoders para reflejar el
  contrato ampliado (qué caracteres neutralizan ahora, no solo qué
  neutralizaba `_sanitize`).
- `docs/BACKLOG.md` cierra P1-1 completamente.
- Reporte `docs/historico/sesiones/37-reporte.md` con la propuesta para
  sesión 38.

### Fuera

- **Ruta (b).** Si tenta, parar y consultar.
- **Cualquier cambio en `toon/`.** Ni una línea. Si el fix pide tocar
  `toon/`, es señal de que la solución quiere ser (b) — escalar.
- **Otros gaps documentados en sesión 36 decisión #4**: `filter_desc`,
  `kiid`, `layer`, `bbox_source`, `via_layers`, `CopperItem.net_name`
  vacío sin fallback `or "-"`. Todos van al backlog como candidatos
  futuros con su ubicación exacta. Ninguno se toca acá.
- **Migrar los ad-hoc a TOON canónico.** Cambio de F1 vía ADR aparte.
- **Formalizar los tres formatos ad-hoc con spec propia.** Fuera de esta
  sesión.
- **Refactorización de `tools/pcb.py`.** DT1 tiene su propia sesión (40 en
  el roadmap). No aprovechar el paso por ahí para "arreglar de yapa".

## Fronteras aplicables

- **F1.** La ruta (a) explícitamente **no** toca `toon/` — F1 no está
  en juego. Si el agente encuentra que necesita tocarlo, escala. Los
  goldens de F1 (los tres del canónico, protegidos desde sesiones
  previas) siguen intactos; los que cambian son los 004/005/006, que son
  ad-hoc y protegen el contrato ad-hoc, no el TOON canónico.
- **F4.** `tools → bridge → externo`. Esta sesión trabaja dentro de
  `tools/` sin dependencias nuevas hacia afuera; F4 se respeta.
- **F5.** Sin dependencias nuevas. Sanitización con stdlib
  (`str.replace`, `re.sub` si hace falta). Si algo pide una librería,
  escalar.

F2 y F3 no aplican directamente.

## Criterio de éxito (falsable)

1. Los tres encoders neutralizan el espacio en los campos
   space-delimited (o H1 refutada y ampliada al pipeline correcto, con
   evidencia).
2. El header `DETAIL|<ref>|...` de `_encode_component_detail` **no**
   sufre neutralización del espacio (o H2 refutada con evidencia).
3. Los 3 goldens 004/005/006 se actualizan **solo** en las líneas de
   caracterización marcadas en sesión 36. Si otras líneas cambian, se
   documenta por qué antes de aceptar el diff — de lo contrario es
   regresión.
4. `pytest tests/test_pcb_encoders_golden.py` verde 3/3 con los goldens
   actualizados.
5. Los 4 checks locales de DoD verdes (ruff, ruff format, mypy, pytest
   offline) — 388 passed como en 36 (o el nuevo baseline que emerja).
6. CI verde en el PR (el gate de sesión 35 no se rompe).
7. `docs/BACKLOG.md` marca **P1-1 cerrado** (no parcialmente cerrado —
   la sesión 36 lo dejó parcial, esta lo completa).
8. Cero cambios fuera de `tools/pcb.py`, los 3 goldens, `BACKLOG.md`, el
   reporte y (opcionalmente) docstrings tocados.

## Riesgos a priori

- **Que el espacio "estructural" no sea el único carácter de whitespace
  problemático.** Si un `net_name` de dominio real puede contener tabs
  (poco probable pero no imposible dado que KiCad importa nombres de
  netlists externas), el fix debería ser `re.sub(r"\s", "_", ...)` no
  `replace(" ", "_")`. El agente decide con evidencia; H1 lo captura.
- **Que exista un caso limpio actual que contenga espacio y salga
  correcto por convención implícita** (ej. un `bbox_source` con
  descripción tipo `"from KiCad IPC"`). Si el mini-sanitizador lo
  toca de yapa, es scope creep — verificar que el sanitizador está
  aplicado solo en los campos declarados en Dentro.
- **Que `_encode_component_detail` tenga más campos afectados** de los
  identificados en 36 (el reporte menciona `pad.number` explícito, pero
  hay que confirmar que no hay otro campo space-delimited en la línea de
  pad). P3 punto 4 lo cubre.
- **Que la elección de carácter sustituto (`_` vs `-` vs otro) importe
  para el consumidor.** `_sanitize` usa `_`, así que por consistencia el
  mini-sanitizador debería usar `_` también. Si el agente propone otro,
  registrar como P9 con justificación.

## Entregables

1. `src/kicad_mcp/tools/pcb.py` con mini-sanitizador local + 3 sitios de
   aplicación ajustados + docstrings actualizados en los tres encoders.
2. `tests/golden/004_pcb_tracks_canarios/expected.txt`,
   `005_pcb_zones_canarios/expected.txt`,
   `006_pcb_component_detail_canarios/expected.txt` actualizados **solo**
   en las líneas de caracterización.
3. `docs/BACKLOG.md` con P1-1 cerrado.
4. `docs/historico/sesiones/37-reporte.md`.
5. Si algún archivo bloqueado por `.claude/settings.json` necesita
   actualización (ej. `CLAUDE.md` no debería en esta sesión — pero si
   emerge algo, patrón usual: diff en `docs/historico/drafts/` y aplicación
   manual del arquitecto).

## Nota preventiva — variantes de "aflojá X" que se escalan

- **"Ampliar `_sanitize` para que el sanitizador local no duplique
  código":** eso es la ruta (b) disfrazada. Parar y consultar. La
  ligera duplicación de "aplicar `_sanitize` y luego neutralizar
  espacio" en un helper local es exactamente el precio de mantener
  `toon/` intacto — no es un problema a resolver.
- **"Ya que estoy tocando pcb.py, arreglo `layer` que renderiza `None`
  literal / `CopperItem.net_name` vacío sin `or '-'`":** no. Al
  backlog. Cada gap tiene su sesión.
- **"Migrar los ad-hoc a TOON canónico ya es hora":** no. ADR aparte,
  no esta sesión.
- **"Los goldens 004/005/006 son ad-hoc, no importa si cambian líneas
  no anticipadas":** sí importa. Un golden que cambia por razones que
  no entiende el que lo aprueba es un contrato roto. Si el diff no
  coincide con lo esperado, se investiga primero, no se acepta.
- **"Ampliar el mini-sanitizador para que también neutralice mayúsculas
  / normalice unicode / haga X":** no. Alcance es el espacio. Todo
  lo demás emerge en futuras sesiones si hay motivo.

Si algo en el reporte de 37 tiene forma de "expandimos porque
convenía" o "cambiamos ruta porque parecía más limpio", el arquitecto
va a preguntar por qué no se escaló. La disciplina del alcance es
parte del criterio de éxito, no un adorno — sesión 36 lo hizo bien
(H36.1 refutada → escalar en vez de fixear en el momento), 37 debe
mantener el mismo estándar.
