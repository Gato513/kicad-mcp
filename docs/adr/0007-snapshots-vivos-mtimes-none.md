# ADR-0007 — Snapshots vivos: `mtimes=None` tras mutaciones in-memory

**Fecha:** 2026-07-09 · **Estado:** aceptado · **Fuente:** sesión 05 D-05.2

## Contexto

`SnapshotStore` (sesión 04, ADR referenciada en `arquitectura.md §4.3-4.4`)
guarda cada snapshot junto con el conjunto de `mtime_ns` de los archivos
del proyecto (`.kicad_sch`, `.kicad_pcb`) que lo generaron. Esto habilita
detectar ediciones externas (`EXTERNAL_EDIT_DETECTED`): si entre dos
llamadas del agente el usuario modifica el `.kicad_pcb` en KiCad, el
`mtime` cambia y la próxima mutación con `base_snap` viejo se rechaza.

Con la sesión 05 T5 aparece un caso nuevo: tras `move_footprint` /
`add_track` exitosas se registra un snapshot post-mutación reconstruido
desde el board de kipy (in-memory), no desde el `.kicad_pcb` en disco —
el archivo todavía no refleja la mutación (KiCad guarda solo cuando el
usuario lo hace). Si a ese snapshot le ponemos los `mtimes` actuales del
disco, en el momento en que el usuario apriete `Save` los `mtimes` de
disco cambian y la siguiente mutación del agente encadenada contra ese
snap detectaría un `EXTERNAL_EDIT_DETECTED` **falso positivo**: no hubo
edición externa, es el propio `Save` del agente.

## Decisión

`SnapshotEntry.mtimes` pasa de `dict[str, int]` a `dict[str, int] | None`.

- `mtimes: dict[str, int]` → snapshot de disco (comportamiento actual).
  Se compara con el disco actual: mismatch ⇒ `EXTERNAL_EDIT_DETECTED`.
- `mtimes: None` → **snapshot vivo**. Se registra así cuando el estado
  proviene de una fuente in-memory (kipy) y por lo tanto no hay un
  `mtime` de disco al que anclarlo. La validación de mtime **se omite**
  para snapshots vivos: sólo se chequea presencia en el store
  (`SNAPSHOT_STALE`).

El sentinel es explícito y aparece en el sitio de registro; no hay
detección "automática" ni fallback a `mtimes` recientes de disco. El
llamador declara la naturaleza del snap con el parámetro.

## Consecuencias aceptadas

- Un snapshot vivo **no detecta** ediciones externas concurrentes: si
  entre dos mutaciones encadenadas del agente el usuario modifica el
  `.kicad_pcb` en disco (edición externa real), la siguiente mutación
  pasará porque el store no está monitoreando el disco para ese snap.
  Aceptamos el hueco: el flujo real es que el agente encadene mutaciones
  cortas y el usuario mire, no que corrijan a mano en paralelo. El
  próximo `get_world_context` reconstruye la verdad de todos modos.
- La alternativa evaluada — **hashear el board de kipy** para detectar
  cambios sobre snapshots vivos — se difiere hasta que se mida que el
  hueco importa. Motivos: (a) exige ingerir todo el board por request de
  validación (contra el objetivo del store, que es evitar precisamente
  ese trabajo), (b) el hash no distingue entre "el usuario editó" y "otra
  operación del agente movió cosas", con lo cual el error se degrada a
  `SNAPSHOT_STALE` sin más información, (c) fue rechazada por D-05.2 como
  scope creep de esta sesión.
- El código de error `SNAPSHOT_STALE` gana un campo estructurado
  `data.base_snap` y `data.retention` para que el agente correlacione el
  fallo con su plan sin parsear el mensaje. F3 intacta: el código no se
  renombra, sólo se enriquece el payload.

## No decidido aquí

- Cómo detectar ediciones externas sobre un snapshot vivo si el hueco
  llega a importar (aparecería como sesión 07+). Los candidatos son
  hashing incremental del board y polling del socket IPC; ambos requieren
  medición previa de frecuencia real del falso negativo.
- Si `get_context_delta` sobre un snapshot vivo debe declararlo en la
  cabecera del delta (p. ej. `snap:… |base:… |live`). Hoy no: la
  cabecera se mantiene según spec TOON v1 §3 (F1).
