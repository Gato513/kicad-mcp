# Sesión 44 — cierre de P1-2: `kiid` sin sanitizar en los encoders ad hoc

## Resumen ejecutivo

`docs/BACKLOG.md` tenía abierto, sin sesión asignada, el candidato P1-2:
`it.kiid`/`z.kiid` en `tools/pcb_encoders.py` (`_encode_tracks`,
`_encode_zones`) no pasan por `_sanitize`/`_sanitize_space_delimited` como
sí lo hacen `net_name`/`ref`/`pad.number` (regla 6 de `CLAUDE.md`). La
entrada original explicaba por qué sanitizar mecánicamente sería
contraproducente (`kiid` es un identificador de round-trip; mutilarlo rompe
`delete_track(id=...)`) y proponía dos caminos de cierre: sanear de otra
forma, o refutar con evidencia de que KiCad garantiza que un KIID nunca
contiene los caracteres estructurales que las tres gramáticas ad hoc usan
como delimitador (espacio, `|`).

Esta sesión reunió esa evidencia y **cierra P1-2 como refutado, sin ningún
cambio de código.**

## Investigación

**Evidencia 1 — contrato de kipy (upstream).** El tipo protobuf `KIID`
(`kipy/proto/common/types/base_types_pb2.pyi:276-290`, dependencia del
venv del proyecto) declara:

> "The KIID's value in standard UUID format, stored as a string for easy
> portability"

Es el mismo tipo `KIID` que usan tracks, vías, zonas, footprints y pads —
no una garantía puntual de una sola superficie. Un UUID estándar usa
exclusivamente `[0-9a-fA-F-]`; ninguno de esos caracteres es un delimitador
de `_encode_tracks`/`_encode_zones`/`_encode_component_detail`.

Una garantía documental de una librería de terceros no es evidencia
suficiente por sí sola cuando el dato en cuestión puede originarse en un
archivo editable a mano (los fixtures de este mismo repo lo son). Hacía
falta confirmar qué pasa si el archivo miente.

**Evidencia 2 — verificación empírica (offline, `pcbnew`).** Se copió
`tests/fixtures/007_pcb_multicapa/multicapa.kicad_pcb` a un scratch fuera
del repo (el fixture commiteado nunca se tocó) y se reemplazó el campo
`(uuid ...)` de la vía por una cadena adversarial:

```
(uuid "evil kiid|injection\ttab")
```

Cargado con `pcbnew.LoadBoard()` (mismo motor de parseo que usa el server
IPC — no un stub ni una re-implementación propia):

```
uuid string: 'cc200f04-593b-4f1c-a25e-c62b244a64f8'
```

El string inyectado **no sobrevive** — KiCad lo descarta al detectar que no
es un UUID válido y genera uno nuevo al azar. Control (para descartar que
KiCad simplemente reemplaza *todo* uuid al cargar, lo que invalidaría el
experimento): se repitió con el uuid original, bien formado, del mismo
fixture (`5e4b1000-0000-4000-8000-000000000004`) — se preserva exacto. El
comportamiento es específicamente rechazo de formato inválido, no
regeneración incondicional.

**Conclusión:** ni siquiera un `.kicad_pcb` adversarial hecho a mano puede
lograr que un `kiid` con espacio, `|` u otro delimitador llegue al object
model en memoria que expone el IPC — el parser de KiCad lo intercepta antes
de que `kicad-mcp` tenga oportunidad de leerlo. Para ítems creados por las
tools de escritura del propio proyecto (`add_via`, `add_track`, `add_zone`)
el argumento es más directo todavía: el KIID lo asigna KiCad internamente al
construir el objeto, nunca se deriva de texto de archivo.

## Decisión

P1-2 se cierra **sin tocar código**. La ausencia de sanitización en
`it.kiid`/`z.kiid` era la decisión correcta desde sesión 36/38; esta sesión
la confirma con evidencia verificable en vez de dejarla como candidato
abierto indefinidamente. Detalle completo en `docs/BACKLOG.md` §P1-2.

## Verificación

Sesión documental + experimento offline en `/tmp` (no en `tests/fixtures/`,
no en `tests/golden/`, no en `docs/specs/` — F1 intacta). Sin cambios en
`src/`; no aplica re-correr la suite offline ni `ruff`/`mypy` porque no hubo
edición de código de producción ni de tests.

## Commit

Un commit `docs:` en `sesion/42-dt1-slice2-caracterizacion`, con los
trailers de atribución. Sin push (DoD #6).
