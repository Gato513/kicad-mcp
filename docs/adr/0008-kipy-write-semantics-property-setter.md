# ADR-0008 — Semántica de escritura vía kipy: setter de property, no mutación de campo

**Fecha:** 2026-07-10 · **Estado:** aceptado · **Fuente:** sesión 06 T1

## Contexto

`IpcBridge.move_footprint` (sesión 03) mutaba la posición de un footprint
así:

```python
fp.position.x = int(mm_to_nm(x_mm))
fp.position.y = int(mm_to_nm(y_mm))
raw_board.update_items(fp)
```

En sesión 06 el humano observó, contra KiCad 10.0.4 real, que la mutación
NO persistía: `test_move_footprint_round_trip_against_open_board` fallaba
con `x1 == x0` exacto (la re-lectura devolvía la posición inicial), y una
verificación manual en la GUI mostraba U19 en su coordenada original.

Se plantearon dos hipótesis:

- **H1 histórica**: kipy 0.7.1 exige un paso de `commit`/`push` explícito
  (`begin_commit()` + `push_commit()`) para persistir mutaciones.
- **H2**: `get_footprint_position` lee de una lista cacheada localmente.

Ambas quedaron descartadas por la lectura del código fuente de kipy 0.7.1
instalado en el venv:

- kipy explícitamente documenta lo contrario de H1 (`kipy/board.py:315-316`):
  > *"If you do not call begin_commit, any changes made to the board will be
  > committed immediately, which will result in multiple steps being added
  > to the undo history."*
  Sin `begin_commit` la escritura es inmediata; el batching es solo para
  atomicidad de undo.
- H2 se descarta viendo `Board.get_footprints()` (kipy `board.py:501-506`):
  cada llamada envía un `GetItems` fresco al server IPC, sin cache local.

La causa real es más sutil y vive en el patrón de acceso a propiedades:

- **`kipy.geometry.Vector2.__init__`** (`geometry.py:38-42`) crea un proto
  NUEVO y hace `CopyFrom` del proto que recibe:

  ```python
  def __init__(self, proto: Optional[types.Vector2] = None):
      self._proto = types.Vector2()
      if proto is not None:
          self._proto.CopyFrom(proto)
  ```

- **`kipy.board_types.FootprintInstance.position`** (`board_types.py:1935-1937`)
  como GETTER retorna un `Vector2` recién construido:

  ```python
  @property
  def position(self) -> Vector2:
      return Vector2(self._proto.position)
  ```

Escribir `fp.position.x = valor` invoca el getter (crea Vector2 con COPIA
del proto interno), muta `.x_nm` de esa COPIA, y descarta el objeto: el
proto interno del `FootprintInstance` NUNCA cambia. `update_items(fp)`
envía el proto original sin cambios; KiCad recibe "update: la posición
sigue siendo la misma que ya tenía" — un no-op silencioso.

El SETTER de la property (`board_types.py:1939-1964`) sí escribe sobre
`self._proto.position` (via `CopyFrom(position.proto)`) y adicionalmente
arrastra los `field.text.position` (reference, value, datasheet, description)
y los ítems de la definición (pads, zones, shapes) por un delta calculado
desde la posición anterior.

## Decisión

Todas las escrituras a properties de kipy que expongan un wrapper (Vector2,
Angle, Field, otras propiedades derivadas del proto) usan el **setter de
property**, nunca el patrón `getter().campo = valor`.

Regla concreta para el bridge:

```python
# CORRECTO — setter de property
fp.position = Vector2.from_xy(int(mm_to_nm(x_mm)), int(mm_to_nm(y_mm)))
raw_board.update_items(fp)

# INCORRECTO — muta una copia local, la escritura se pierde
fp.position.x = int(mm_to_nm(x_mm))
fp.position.y = int(mm_to_nm(y_mm))
raw_board.update_items(fp)  # envía el proto sin cambios
```

Adicionalmente:

- `add_track` construye `Track()` vacío y asigna vía setters (`track.start`,
  `track.end`, `track.width`, `track.layer`, `track.net`) — no cae en el
  bug porque el patrón siempre fue setter directo.
- `snapshot_footprints` sólo LEE (`fp.position`, `fp.value_field`) sobre la
  copia local; la copia refleja el estado del proto interno al momento
  del getter, por lo que la lectura es correcta.

## Consecuencias aceptadas

- **Un fix contenido a `bridge/ipc.py:move_footprint`** cierra el gap. La
  arquitectura del bridge (frontera de proceso, tipos de kipy no salen del
  bridge) queda intacta.
- **La cobertura debe verificar el efecto, no sólo el retorno.** Un test
  que sólo asserta "no hubo excepción" o "el snap_id > 0" no atrapa este
  bug (T2/D-06.3). Post-mutación se re-lee vía bridge y se contrasta la
  posición con la solicitada.
- **Los fakes del bridge en unit deben simular la SEMÁNTICA REAL.** El
  `_FakeBridge` de sesión 03 registraba llamadas a `move_footprint` pero
  `snapshot_footprints` devolvía posiciones fijas en (0, 0); un test que
  pasara con ese fake no atrapaba el bug. En sesión 06 el fake mantiene
  un `_positions[ref] -> (x, y)` y `move_footprint` lo actualiza —
  cómplice de la spec, no del bug.
- **Patrón validado para mutaciones futuras.** Cualquier mutación IPC
  nueva (rotación, cambio de valor, edición de field, etc.) debe usar
  siempre el setter de property. Auditar por grep `= .*\.[a-z_]+$` sobre
  wrappers de kipy antes de emitir mutaciones.

## Alternativas descartadas

- **Envolver en `begin_commit()` / `push_commit()`.** No corresponde al bug
  real (sin commit las escrituras SÍ persisten inmediatamente); habría
  añadido complejidad sin resolver el gap. Reservado para mutaciones
  múltiples cuando queramos una entrada única en el undo (v0.5+).
- **Hashing del board para detectar mutaciones no persistidas.** Diferido
  en ADR-0007 §Alternativas; no es la solución mínima al bug T1.
- **Mockeo del bridge en integration_gui.** Rompe la regla explícita de
  CLAUDE.md ("si un test integration falla y KiCad no está corriendo, ese
  es el motivo — no lo arregles mockeando el bridge en tests de integración").
