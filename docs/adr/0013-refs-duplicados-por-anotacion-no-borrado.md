# ADR-0013 — Refs de footprint duplicados/sin anotar se resuelven por anotación, no por borrado

**Fecha:** 2026-07-29 · **Estado:** aceptado · **Fuente:** sesión 31
(hallazgo F-V1-02) + sesión 31b (fix)

## Contexto

Sesión 31 (primera Validation Suite Nivel A, ANAVI Dev Mic) encontró que
`route_board` fallaba enteramente contra un board real: 4 mounting holes
del diseño del autor comparten el reference designator literal `REF**`
(footprints sólo-mecánicos, sin símbolo de esquemático — nunca fueron
anotados, patrón real y no infrecuente en proyectos KiCad externos).

Aislado con un experimento controlado: `pcbnew.ExportSpecctraDSN()`
—invocada por `_run_export_dsn`, paso 1 de `route_board`— devuelve
`ok=False, size=0` cuando el board tiene refs de footprint duplicados,
**sin importar la posición** de esos footprints. Quitando 3 de las 4
instancias `REF**` en una copia de prueba, la exportación pasó de fallar
a `ok=True, size=2.4MB`. Es comportamiento de `pcbnew` (upstream), no
arreglable desde `src/`.

El diseño obvio para desbloquear esto — un `delete_footprint(ref, kiid)`
general — choca con [ADR-0010](0010-borrado-de-cobre-sin-gate-g2.md):
borrar footprints/componentes/zonas sigue siendo territorio de Gate G2
(interactivo, no existe en código). Esa asimetría con `delete_track`/
`delete_via` es **deliberada**: "la re-agregabilidad barata [de cobre] es
la propiedad que habilita la excepción, y no la tienen los footprints...
recrearlo no es un call, es un problema de re-instanciación (hoy ni
siquiera existe `place_footprint`)."

Acotar el trigger de borrado a "sólo cuando el ref está duplicado" **no
cambia ese argumento**: un footprint con ref duplicado es exactamente
igual de caro de reinstanciar que uno con ref único si el borrado
resulta equivocado. Y en el caso real que motivó esta investigación, las
4 `REF**` de ANAVI Dev Mic son mounting holes **legítimas**, no basura
duplicada — borrar 3 habría destruido el ground truth de 13 footprints
que sesión 31 ya midió y admitió en `validation-suite/level-a/
anavi-dev-mic/`, invalidando la validación en curso.

## Decisión

Refs duplicados/sin anotar se resuelven por **anotación**, no por
borrado. Tool nueva: `set_footprint_ref(ref: str, new_ref: str, kiid:
str | None = None, base_snap: int | None = None) -> str`.

**Semántica:**
- Sólo opera cuando `ref` está compartido por 2+ footprints actualmente
  en el board. Con un `ref` único, rechaza con `INVALID_PARAMS` — **no
  puede usarse como `delete_footprint` disfrazado** sobre un footprint
  válido con ref único; el tipo de la precondición excluye ese caso
  estructuralmente, no por convención.
- Sin `kiid`, o con un `kiid` que no corresponde a ninguna instancia
  actual de `ref`, rechaza con el código nuevo `DUPLICATE_REFS` y
  `data.candidates` (kiid + posición + value de cada instancia). Nunca
  resuelve a ciegas — mismo espíritu que la ambigüedad ya establecida en
  `_delete_copper` ("2+ candidatos... NUNCA borramos 'el más cercano'").
- Con `kiid` válido: renombra esa única instancia. **Sin cascada** —
  tracks/zonas conectados quedan intactos, mismo criterio que
  `delete_track`/`delete_via`.

**Companion de diagnóstico** (mismo commit, sin implicancias de gate —
es lectura, no mutación): `route_board` corre un pre-check
`_find_duplicate_refs` sobre `pre_footprints` (ya en memoria, cero IPC
extra) ANTES del DRC pre-route y del round-trip DSN/Freerouting. Si
encuentra refs duplicados, falla con `DUPLICATE_REFS` y `data.duplicates`
(lista de `{ref, kiids}`) — reemplaza el `KICAD_CLI_FAILED` opaco con
stderr crudo de pcbnew por un error legible que apunta a
`set_footprint_ref`.

**Nuevo código de error:** `DUPLICATE_REFS` — adición pura al `ErrorCode`
StrEnum (F1, excepción sancionada; no renombra nada existente).

## Hallazgo arquitectónico: semántica de escritura de `reference_field`

Verificado con un spike contra KiCad 10.0.4 real (sesión 31b, Paso 0)
antes de implementar: `fp.reference_field.text.value = nuevo_ref` seguido
de `board.update_items(fp)` persiste correctamente, confirmado con una
relectura fresca vía `get_footprints()`.

Esto es la **contraparte** del hallazgo de
[ADR-0008](0008-kipy-write-semantics-property-setter.md). Ahí,
`fp.position` es un getter que devuelve `Vector2(self._proto.position)`
—una copia (`CopyFrom`)— y escribir sobre esa copia se pierde en
silencio; hace falta el setter completo (`fp.position = Vector2(...)`).
Acá, en cambio, la cadena `FootprintInstance.reference_field` →
`Field.text` → `BoardText.value` usa `proto_ref=` **sin** `CopyFrom` en
toda la cadena (kipy 0.7.1, `board_types.py` líneas 2037-2038, 1056-1058,
735-737) — escribir `fp.reference_field.text.value = ...` muta el proto
interno del `FootprintInstance` directamente, sin necesidad de un setter
de nivel superior.

**Consecuencia para mutaciones futuras:** la lección de ADR-0008 ("auditar
por grep `= .*\.[a-z_]+$` sobre wrappers de kipy antes de emitir
mutaciones, usar siempre el setter de property") sigue vigente como
regla general — pero no toda propiedad de kipy tiene la trampa de copia.
Cada mutación IPC nueva debe verificarse individualmente contra el motor
real (spike GUI, D-30.1) antes de asumir cuál de los dos patrones aplica.

## Consecuencias

- El loop de sesión 31 (Validation Suite ANAVI Dev Mic) queda
  desbloqueado: `route_board` puede completar sobre el `working/` ya
  preparado, sin re-medir el ground truth (las 4 mounting holes se
  conservan, sólo se renombran).
- `ADR-0010` queda **intacta, sin narrowing**: no se abrió ninguna forma
  de borrado de footprints sin G2. La asimetría `delete_track` sí /
  `delete_footprint` no sigue siendo deliberada (`docs/BACKLOG.md` §P2).
- `set_footprint_ref` es la primera tool de escritura de PCB que muta un
  campo de texto (no geometría ni cobre) — precedente para futuras tools
  de anotación (ej. renombrar `value_field`) si aparece evidencia de
  necesidad.
- Limitación conocida, documentada, no resuelta: un rename por esta tool
  vive sólo en el PCB — si el footprint tiene backing de esquemático (a
  diferencia de mounting holes/logos sólo-mecánicos), un "Update PCB from
  Schematic" posterior puede desincronizarlo. Irrelevante para el caso
  que motivó esta ADR (`REF**` mecánicos sin backing de netlist),
  relevante en el caso general.
- El pre-check de `route_board` tiene una degradación conocida y
  aceptada: sólo corre si el board está abierto en vivo y no `stale`
  (mismo criterio best-effort que `zones_existentes`, ya existente en
  `route_board`). Sin board vivo, el pre-check no tiene nada que revisar
  y `route_board` procede como antes (fallaría más tarde, en el
  subprocess, con el error opaco original — no hay regresión, sólo
  ausencia de la mejora de diagnóstico en ese caso).

## Alternativas descartadas

- **`delete_footprint`/`resolve_duplicate_ref` general o acotado a refs
  duplicados.** Rechazado — ver Contexto. No escapa al argumento de
  costo de re-instanciación de ADR-0010, y en el caso real habría
  destruido datos de diseño legítimos.
- **Implementar Gate G2 (elicitation interactiva) para desbloquear un
  `delete_footprint` gateado correctamente.** El SDK MCP vendored trae
  `mcp.server.elicitation` disponible, así que es técnicamente posible —
  pero es alcance mayor (diseño de UX de confirmación, tests de un flujo
  humano-en-el-loop) que no corresponde a una sesión de fix quirúrgico.
  Queda como opción futura si aparece evidencia de que el borrado real de
  footprints (más allá del caso de refs duplicados, ya resuelto acá) es
  necesario.
- **Pre-check de `route_board` sin la tool de resolución** (sólo mejorar
  el mensaje de error). Insuficiente — deja al agente sin manera de
  actuar sobre el hallazgo dentro del flujo canónico.
