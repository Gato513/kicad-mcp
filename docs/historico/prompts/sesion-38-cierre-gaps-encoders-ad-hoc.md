# Sesión 38 — Cierre de gaps de fallback y sanitización de headers en encoders ad-hoc

**Rama:** `sesion/38-cierre-gaps-encoders-ad-hoc` desde `master` remoto en
`4958760` (o su sucesor si un merge posterior por PR quedó registrado antes
de que arranques — con branch protection activa, cualquier avance de
`master` es información legítima; el agente confirma el estado real en P3).
**Tipo:** hardening — última pieza de DT4 sobre los encoders ad-hoc.
Consolida la familia de gaps derivados de la decisión #4 de sesión 36, con
veredicto explícito por cada candidato para que el frente cierre
definitivamente en vez de dejar residuo para sesiones futuras.

## Objetivo

Los encoders ad-hoc de `tools/pcb.py` deben cerrar tres gaps ya
identificados: `CopperItem.layer: str | None` renderizando el literal
`None`, `CopperItem.net_name` vacío sin fallback consistente con lo que ya
hacen `ZoneItem` y `PadDetail`, y `filter_desc` de los headers
`TRACKS|v1|...`/`ZONES|v1|...` sin pasar por sanitización estructural. Los
cuatro candidatos que quedaron sin veredicto en la decisión #4 de sesión 36
(`kiid`, `bbox_source`, `kind`, `via_layers`) deben recibir uno explícito
en el reporte: entran si caen en el mismo patrón defensivo y son
resolubles sin ampliar el contrato, o quedan registrados como items P1-x
nuevos en `BACKLOG.md` si son de otra categoría o requieren discusión de
diseño. El frente de encoders ad-hoc queda cerrado o formalmente delegado
al terminar esta sesión — no queda una tercera categoría "gap conocido sin
sesión asignada".

## Motivación (breve)

Sesión 36 sanitizó los tres encoders y descubrió por evaluación activa que
`_sanitize` no cubría el espacio. Sesión 37 cerró ese gap con
`_sanitize_space_delimited` y en el proceso dejó marcados en la decisión
#4 los otros hallazgos "vi al pasar pero fuera de alcance": tres gaps
concretos (los del Dentro de esta sesión) y cuatro candidatos que
requieren verificación (`kiid`, `bbox_source`, `kind`, `via_layers`). El
principio del ritmo (§Metodología P10 del CONTEXTO) pide cerrar la deuda
antes de que el momentum se pierda; el principio de disciplina de alcance
pide no mezclar categorías. Esta sesión resuelve las dos cosas a la vez:
cierra los tres gaps concretos, y sobre los cuatro candidatos hace la
única cosa que la sesión 36 no pudo hacer (verificar caso por caso contra
código y consumidores reales) para clasificarlos.

## Ruta y decisiones ya tomadas por el arquitecto

Se documentan acá para que el reporte pueda apuntar de vuelta con
trazabilidad, no para que el agente las re-decida:

- **Fallback para `CopperItem.layer` y `CopperItem.net_name`: `"-"`** por
  consistencia con lo que `ZoneItem`/`PadDetail` ya usan (el agente
  confirma el sustituto exacto que esos usan en P3 y replica; si no es
  `"-"` sino otra cosa, replicar lo que sea consistente). Si algún caller
  real puede tener `layer == "-"` como valor legítimo (improbable pero
  verificable), es una razón para escalar.
- **Sanitización de `filter_desc`: `_sanitize` puro**, no
  `_sanitize_space_delimited`, porque los headers son `|`-delimited y el
  espacio no es estructural ahí — el paralelo exacto al header
  `DETAIL|<ref>|pcb|...` que sesión 37 dejó sin neutralización del
  espacio (H2 de 37).
- **Ubicación de los cambios:** los sitios de emisión ya conocidos por
  sesiones 36/37 (`_encode_tracks`, `_encode_zones`,
  `_encode_component_detail`). Sin extraer helpers compartidos; si un
  fallback es `f"{x or '-'}"` inline, se queda inline — mantener el
  estilo del código existente. Si el patrón se repite tres o cuatro
  veces y realmente pide un helper local, es material para sesión 40
  (DT1), no para acá.

## Hipótesis (con criterio de refutación explícito)

**H1 — Los tres gaps declarados en Dentro caen en el mismo patrón
defensivo puro: fallback textual consistente donde ya existe uno análogo
(dos primeros), y sanitización estructural estándar donde el header es
`|`-delimited (`filter_desc`). Ninguno requiere lógica nueva ni cambio de
contrato observable para inputs que hoy salen "limpios".**
**Refutación:** al inspeccionar los tres, alguno tiene razón concreta para
no llevar fallback / no sanitizar — por ejemplo, `CopperItem.layer` es
`None` por diseño en un caso legítimo donde algún consumer distingue
`None` de `"-"` semánticamente, o `filter_desc` está garantizado libre de
`|` por el punto donde nace (típicamente hard-coded en el propio código
que emite el header, no user-controlled). En cualquiera de esos casos:
parar antes de forzar el fix, escalar, y si la conclusión es que el fix
no aporta valor, registrar como "gap aparente refutado por evidencia" con
la traza al consumer/origen. La sanitización defensiva de `filter_desc`
sigue siendo válida como defensa en profundidad aunque sea input interno
controlado — se aplica igual, se documenta que es defensa, no correctivo.

**H2 — De los cuatro candidatos (`kiid`, `bbox_source`, `kind`,
`via_layers`), al menos dos son de la misma categoría defensiva y se
pueden cerrar en esta sesión sin ampliar el contrato; los demás son de
categoría distinta y quedan registrados como P1-x nuevos en `BACKLOG.md`
con su ubicación exacta.**
**Refutación:** los cuatro son de la misma categoría (todos entran) o
ninguno lo es (todos van al backlog). Cualquiera de esos dos extremos es
resultado válido — lo que **no** es válido es tratar a algunos "de yapa"
sin veredicto explícito. Cada uno de los cuatro tiene una fila en el
reporte: nombre + veredicto (`entra`/`queda P1-x`/`refutado`) + una frase
de justificación con traza al código.

**H3 — Los goldens 004/005/006 tienen canario para los tres gaps
declarados (T4/Z4/pads 4-5 ya incluyen strings vacíos, campos ausentes o
caracteres estructurales representativos) o requieren canarios nuevos
mínimos para probar los fallbacks.**
**Refutación:** algún gap declarado no tiene canario y agregarlo cambia
líneas del golden más allá de la anticipada. En ese caso, se anticipa
línea por línea qué debería cambiar antes de regenerar el golden (mismo
patrón de sesión 37 con H3), y solo se acepta el diff si coincide. Un
golden que cambia por razones no explicadas es regresión, no éxito del
fix — parar y entender.

## Verificación de premisa (P3)

Antes de tocar nada, el agente confirma:

1. **`master` remoto en `4958760`** o su sucesor legítimo (avanzado por
   PR mergeado con CI verde). Si el remoto está en otro commit por push
   directo (branch protection ausente o bypasseada), **parar y escalar**:
   la premisa del acuerdo operativo con el arquitecto no se cumplió.
2. **Branch protection activa sobre `master`** con los cuatro checks
   obligatorios de sesión 35 (`ruff-check`, `ruff-format`, `mypy`,
   `pytest-offline`). Si no lo está: parar y escalar. El agente puede
   verificarlo con `gh api repos/OWNER/REPO/branches/master/protection`
   (si `gh` no está disponible, delega la verificación al arquitecto
   antes de continuar).
3. Sesión 37 mergeada: `_sanitize_space_delimited` existe en
   `tools/pcb.py`, los goldens 004/005/006 están en su estado post-37,
   `docs/BACKLOG.md` tiene `P1-1` como cerrado. Si algo de eso no está,
   la propuesta original de sesión 38 se apoya en aire — parar.
4. Los tres gaps declarados siguen presentes en el código actual.
   Concretamente: `CopperItem.layer` sigue siendo `str | None`,
   `CopperItem.net_name` sigue emitiéndose sin fallback, `filter_desc`
   sigue interpolado en los headers sin pasar por `_sanitize`. Si alguno
   ya fue arreglado al margen (poco probable pero verificable), anota la
   desviación y ajusta el alcance.
5. Confirmá el fallback exacto que usan `ZoneItem.net_name`,
   `PadDetail.net_name` y `PadDetail.number` hoy — es lo que hay que
   replicar en `CopperItem`. Si son inconsistentes entre sí (uno usa
   `"-"`, otro usa `"?"`, otro usa `""`), documentar y elegir el que
   más aparezca, registrando la elección como P9.
6. **Búsqueda proactiva sobre los cuatro candidatos**: para cada uno,
   localizar (a) dónde vive el campo en el modelo, (b) dónde y cómo se
   emite en los encoders, (c) si tiene consumer conocido en tests o en
   documentación de tools. Esa evidencia alimenta el veredicto de H2.

## Alcance

### Dentro

- **Fallback en `CopperItem.layer`** para que no renderice el literal
  `None`. Aplicado en el sitio de emisión, consistente con el patrón de
  las otras dataclasses del mismo módulo.
- **Fallback en `CopperItem.net_name`** para vacío, consistente con
  `ZoneItem.net_name` y `PadDetail.net_name`.
- **`_sanitize` sobre `filter_desc`** en los headers `TRACKS|v1|...` y
  `ZONES|v1|...`.
- **Veredicto explícito por candidato** (`kiid`, `bbox_source`, `kind`,
  `via_layers`) en el reporte, con traza al código:
  - Si entra: fix aplicado en la misma sesión, siguiendo el patrón
    apropiado (fallback defensivo o sanitización).
  - Si queda como P1-x: entrada nueva en `BACKLOG.md` con ID, ubicación
    exacta, categoría, y por qué no cabe en esta sesión (típicamente:
    requiere discusión de diseño, o vive en zona que sesión 40 va a
    refactorizar).
  - Si resulta refutado: nota en el reporte con la evidencia de por qué
    no era un gap real.
- **Canarios nuevos en los goldens 004/005/006** si algún gap
  declarado o candidato que entra no tenía cobertura. Cada canario
  nuevo se justifica en el reporte contra qué gap prueba.
- **Docstrings de los encoders afectados** ajustadas para reflejar los
  fallbacks/sanitización nuevos.
- **Cierre en `BACKLOG.md`** de las entradas que aplique, apertura de
  las P1-x nuevas si algún candidato quedó afuera.
- **Reporte** `docs/historico/sesiones/38-reporte.md` con propuesta para
  sesión 39.

### Fuera

- **Extraer un helper `_fallback(x)` compartido** o similar. Si el
  patrón `x or "-"` aparece 6 veces, se queda inline seis veces. DT2 y
  DT1 son las sesiones para consolidar patrones repetidos.
- **Reformular `_sanitize_space_delimited`** de sesión 37. Se usa como
  está.
- **Cualquier cambio a `toon/`.** Ni una línea.
- **Refactorización de `tools/pcb.py` fuera de las líneas necesarias.**
  DT1 tiene su sesión.
- **Migrar los ad-hoc a TOON canónico.** ADR aparte.
- **Gaps de otra naturaleza que puedan aparecer en el paso por el
  código** (por ej. otra dataclass con `Optional` renderizando `None`):
  se anotan como candidatos nuevos en el reporte, no se tocan.
- **Actualización del `CONTEXTO_CHAT.md`.** Esa es tarea del arquitecto,
  no del agente.

## Fronteras aplicables

- **F1.** No se toca `toon/`. La sanitización de `filter_desc` usa
  `_sanitize` importado, como ya lo hacen los tres encoders desde sesión
  36 — es consumo del canónico, no modificación.
- **F4.** Cambios dentro de `tools/`, sin nuevas dependencias hacia
  `bridge/` o externo.
- **F5.** Sin dependencias nuevas. Fallbacks con expresiones triviales
  (`x or "-"`); sanitización con la función ya usada.

F2 y F3 no aplican.

## Criterio de éxito (falsable)

1. Los tres gaps declarados en Dentro cerrados en `tools/pcb.py`, con el
   fallback exacto identificado por P3 punto 5, o justificadamente no
   cerrados (H1 refutada con evidencia de por qué el fix no aporta).
2. `filter_desc` pasa por `_sanitize` en ambos headers, aunque el input
   sea internamente controlado (defensa en profundidad).
3. Los cuatro candidatos (`kiid`, `bbox_source`, `kind`, `via_layers`)
   tienen veredicto explícito en el reporte, con evidencia. Ninguno queda
   "sin decidir".
4. Los goldens 004/005/006 se actualizan **solo** en las líneas
   afectadas por los gaps declarados y los candidatos que hayan entrado
   (más canarios nuevos que se hayan agregado, con línea propia
   justificada). Otras líneas cambiando = regresión, se investiga antes
   de aceptar (mismo estándar que H3 de sesión 37).
5. Los cuatro checks locales de DoD verdes; test suite pasa con
   `N passed`, `N ≥ 388` — la diferencia sobre 388 corresponde
   exactamente a los canarios nuevos agregados. Si `N < 388` es
   regresión y no cierra la sesión.
6. **CI verde en el PR contra `master`.** Con branch protection activa,
   este es el primer criterio duro que no depende de disciplina — o los
   cuatro checks pasan o no se puede mergear.
7. `docs/BACKLOG.md` refleja el resultado: entradas cerradas para
   `CopperItem.layer`, `CopperItem.net_name`, `filter_desc`; entradas
   P1-x nuevas para los candidatos que no entraron.
8. Cero cambios fuera de `tools/pcb.py`, los tres goldens, `BACKLOG.md`,
   docstrings tocados en (1) y el reporte. Si hubo un cambio adicional,
   está justificado en el reporte con su razón.

## Riesgos a priori

- **`"-"` como valor legítimo colisionando con el fallback.** Si algún
  layer/net_name real puede ser literalmente `"-"`, un consumer
  posicional no puede distinguir "no hay valor" de "hay valor `-`". Es
  improbable en el dominio de KiCad pero verificable; P3 punto 5 lo
  cubre parcialmente. Si aparece, escalar antes de forzar el fallback.
- **`filter_desc` como input interno controlado.** Alta probabilidad de
  que nazca hard-coded en el propio código que emite el header
  (constantes tipo `"all"`, `"user"`). La sanitización defensiva sigue
  siendo válida (costo cero, cierra el flanco) pero se documenta como
  defensiva pura, no correctiva. El canario adversarial en el golden
  prueba una capacidad, no un bug.
- **Uno o más candidatos vive en zona que sesión 40 (DT1) va a
  refactorizar.** Fixear ahí ahora significa que el fix probablemente se
  reescribe o se mueve en 40. Es aceptable — mejor pagar la deuda dos
  veces que dejarla abierta — pero se anota como advertencia en el
  reporte para 40.
- **Canario nuevo que arrastra otros cambios.** Agregar un caso al
  `input.json` de un golden puede rebalancear columnas ancho variable,
  reordenar salida, etc. Si el diff no es la línea única esperada, H3
  se refuta y se investiga antes de aceptar.
- **Que los cuatro candidatos, al mirar el código real, sean todos de
  categoría distinta y ninguno entre en alcance.** Resultado válido —
  la sesión cierra igual con los tres gaps declarados, y los cuatro
  van al backlog con veredicto documentado. No es "sesión desperdiciada":
  el veredicto documentado es el entregable.

## Entregables

1. `src/kicad_mcp/tools/pcb.py` con los tres gaps cerrados, la
   sanitización de `filter_desc` en ambos headers, los candidatos que
   hayan entrado, y las docstrings ajustadas de los encoders tocados.
2. `tests/golden/004_pcb_tracks_canarios/`,
   `005_pcb_zones_canarios/`, `006_pcb_component_detail_canarios/` con
   goldens actualizados y canarios nuevos si los hubo, ambos con
   justificación por línea en el reporte.
3. `docs/BACKLOG.md` con entradas cerradas y/o P1-x nuevas según los
   veredictos.
4. `docs/historico/sesiones/38-reporte.md`, incluyendo:
   - Tabla o lista con los veredictos por candidato.
   - Anticipación línea a línea del diff de golden antes de la
     regeneración (para trazabilidad de H3).
   - Propuesta para sesión 39 (que por decisión del arquitecto es DT2
     salvo que 38 revele bloqueante).
5. Todo entregado en la rama `sesion/38-...`; ningún commit directo a
   `master` bajo ninguna circunstancia (regla operativa post-branch
   protection).

## Nota preventiva — variantes de "aflojá X" que se escalan

- **"Ya que hay repetición, extraigo helper `_fallback(x, sub="-")`
  compartido":** no. Estilo inline, consistente con la base actual.
  Consolidar patrones repetidos es DT2 (sesión 39) o DT1 (sesión 40).
- **"Los cuatro candidatos me parecen todos del mismo patrón,
  los meto de una":** no. Cada uno tiene veredicto explícito con
  justificación individual. "Parece" no es evidencia — la evidencia es
  el traceo al código y al consumer.
- **"Ya que estoy tocando `_encode_tracks`, arreglo tal cosa que vi al
  pasar":** anotar como candidato nuevo en el reporte y seguir. Se
  vuelve a decidir en otra sesión.
- **"El fallback `"-"` es feo, `"—"` (em dash) queda más legible":** no.
  Consistencia con lo que ya está en `ZoneItem`/`PadDetail`. Estética
  no es criterio en esta sesión.
- **"`filter_desc` es interno controlado, sanitizarlo es paranoia
  gratis":** documentar que es defensa en profundidad, aplicar igual.
  El costo es una llamada a función; el beneficio es cerrar el flanco
  antes de que futuros cambios en cómo se construye `filter_desc`
  reintroduzcan el riesgo.
- **"Aprovecho el momentum para arrancar DT2 acá mismo":** no.
  Sesión 39 según decisión del arquitecto. Terminar DT4 primero,
  entrar a DT2 con el terreno de encoders ya cerrado.
- **"Actualizo el docstring de `test_pcb_encoders_golden.py` que 37
  dejó marcado":** ese ya se resolvió en el micro-commit `4958760`
  incorporado a master; verificar en P3 que efectivamente está y no
  volver a tocar.
- **"Aprovecho para actualizar el CONTEXTO_CHAT.md que sé que tiene
  drift":** no. Eso es acción del arquitecto.

Sesión 36 y 37 mantuvieron disciplina estricta de alcance con
consecuencias muy visibles: hallazgo real correctamente escalado (36),
implementación quirúrgica sin residuos (37). La sesión 38 hereda ese
estándar. Cierra el frente de encoders ad-hoc o lo delega formalmente
al backlog — cualquier tercera opción ("gap conocido, sin dueño, para
después") es exactamente el patrón que produce la deuda que este
proyecto viene pagando.
