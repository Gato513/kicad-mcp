# Sesión 19d — Fixes puntuales pre-Dogfooding 3

**Rama:** `sesion/19d-fixes-preD3` (desde `sesion/19-zonas`) · **Fecha:** 2026-07-22.

## Resumen

Los 4 caveats operacionales que dejó la sesión 19c (investigación pura, sin
código) pasan de "documentar en el prompt del D3" a **resueltos en las
tools**, con verificación en vivo contra KiCad 10.0.4 real (fixture
`despertador-routed`) para cada uno. Se encontraron y corrigieron 2 bugs
reales durante las verificaciones en vivo (ver más abajo) — ninguno hubiera
aparecido con sólo tests unit/fake-bridge.

## 19d.0 — ¿`add_track` tiene el mismo bug de net-hijacking que `add_via`?

**Sí, confirmado en vivo.** Metodología idéntica a 19c Bloque 1, contra el
board despertador-routed real:

1. **Baseline vacío:** `add_track(net="GND", (150,30)->(152,30))` sobre zona
   sin cobre ajeno → releído con `get_tracks` → net GND preservado.
2. **Setup:** `add_track(net="/MOSI", (160,35)->(162,35))` — segmento
   ad-hoc.
3. **Cruce:** `add_track(net="GND", (161,34)->(161,36))`, perpendicular,
   cruzando el segmento de `/MOSI` en su punto medio. Releído con
   `get_tracks`: el track pedido como GND **quedó asignado a `/MOSI`
   completo** (no sólo el punto de cruce — el segmento entero cambió de
   net).

Confirma H2 de 19c (KiCad reasigna al net del cobre físico que se
pisa/cruza) para `add_track`, con una variante: a diferencia de una vía
(punto), un track reasignado cambia el net de **todo el segmento**, no sólo
el punto de intersección.

**Hallazgo adicional (no trivial, verificado con varios experimentos en
vivo):** la reasignación de net de una **vía** requiere que el cobre ajeno
esté **indexado en el grafo de conectividad** de KiCad — un segmento
flotante ad-hoc entre dos puntos vacíos (sin pad) **no** dispara el
hijacking de una vía que lo cruce, aunque sí dispara el de un track que lo
cruce. Sólo un stub **anclado a un pad real** (con conectividad genuina)
reproduce el hijacking de vía de forma confiable. Esto no cambia la
conclusión (ambos tienen el bug) pero sí el diseño de los tests
`integration_gui` (ver 19d.1).

## 19d.1 — Fix `add_via`/`add_track`: verificación post-creación

**Diseño:** helper module-level `_verify_created_net_or_revert` en
`bridge/ipc.py` (kipy-agnóstico — no importa kipy, recibe `raw_board` y los
KIID proto ya construidos). Tras `create_items`, releé el net real del ítem
recién creado vía `get_items_by_id` (no confía en el objeto en memoria, que
sigue mostrando el net pedido pese al hijacking). Si difiere del pedido:
`raw_board.remove_items(...)` (revert) + `NET_ASSIGNMENT_MISMATCH` con
`data.requested_net`/`data.actual_net`/`data.at`.

**Restricción de diseño clave:** `self._lock` del bridge es un
`threading.Lock` **no reentrante** — el helper NO puede llamar a
`get_copper_by_kiid` (que retoma el lock) desde dentro del bloque
`with self._lock` de `add_via`/`add_track`; debe releer inline con
`_get_items_by_id_or_empty` (ya module-level, sin lock).

`add_track` pasó de `-> None` a `-> str` (devuelve el KIID creado, simétrico
a `add_via` — antes descartaba el retorno de `create_items`).

Nuevo código `NET_ASSIGNMENT_MISMATCH` en `errors.py` + fila en la taxonomía
y en las filas per-tool de `add_via`/`add_track` de `tool-catalog.md` (F3:
se agrega, no se renombra nada existente).

**Tests:**
- Unit (`tests/test_ipc.py`): `_verify_created_net_or_revert` con
  `raw_board` fake — caso feliz (net coincide, no revierte), mismatch
  (revierte + lanza con `data` correcto), ítem desaparecido (borrado
  concurrente, no-op), net releído sin nombre (no-op). 4 tests.
- `integration_gui` (`tests/test_pcb_session19d_gui.py`, nuevo): reproduce
  el hijacking real vía un stub anclado a pad de un net "ajeno" (net_b),
  luego intenta `add_via`/`add_track` con net_a sobre/cruzando ese stub →
  confirma `NET_ASSIGNMENT_MISMATCH` + verifica contra `board.raw` que NO
  quedó ningún ítem nuevo (revert real). Caso feliz en zona vacía (sin falso
  positivo). 3 tests, todos corridos en vivo — **pasan**.

## 19d.2 — `delete_tracks_bulk` (nueva tool)

Borra tracks/vías por filtro (`net`/`bbox`/`layer`, al menos uno
obligatorio — mismo patrón de validación que `get_tracks`), en un solo
round-trip IPC vía la nueva `bridge.remove_many_by_kiid` (un
`get_items_by_id` batch + un `remove_items` en bloque). `dry_run=True`
lista sin mutar. Refill de zonas de cobre post-bulk si corresponde (una sola
vez, no por ítem). Retorna
`{tracks_deleted, vias_deleted, snap_id, zones_refilled}`.

**Tests:**
- Unit (`tests/test_pcb_delete_bulk.py`, nuevo, fake bridge): filtro
  obligatorio, `NET_NOT_FOUND`, `dry_run` no muta, borrado real +
  snapshot, `include_vias=False`, filtro por `bbox`, refill condicional a
  zonas de cobre presentes. 8 tests.
- `integration_gui` (`tests/test_pcb_session19d_gui.py`): siembra un stub
  propio anclado a pad (garantiza cobertura no trivial), `dry_run` no muta,
  borrado real deja 0 ítems del net. Corrido en vivo — **pasa**.

## 19d.3 — `test_zones_e2e_gui.py` reescrito al escenario Bloque 3

Reemplaza el escenario P4.5 original (plano + keepout **antes** de rutear —
el escenario ROJO de 19c Bloque 4 que bloqueaba 9/10 nets) por el escenario
VERDE de 19c Bloque 3: vaciar TODO el cobre (`delete_tracks_bulk`, dogfood de
19d.2) → plano GND (`add_zone`+`fill_zones`) → `route_board` **desde cero,
sin keepout**. `timeout_s=900`.

Aserciones: `tracks_final < tracks_inicial` (el plano absorbe cobre),
área del plano ≥60% del board, DRC sin errores nuevos, zona GND con KIID
estable. **Sin cota dura de vías** (decisión explícita: el ruteo desde cero
produce un conteo de vías determinado por Freerouting, no comparable al
board hand-routed original — 19c Bloque 3 dio 30 vías > 21 originales; acotar
`vias_final <= vias_inicial` habría hecho fallar el propio escenario que
19c validó como VERDE).

**Corrida en vivo (dos intentos, ver bugs abajo):** la corrida final
convergió en **522.2s (8.7 min)** — 172 tracks + 18 vías agregadas, DRC
`err_post` (29) ≤ `err_preexistentes` (route_board lo midió internamente,
≥29 para que la aserción pasara), zona GND con KIID estable. **Test verde.**
Consistente con el 512.9s de 19c Bloque 3 sobre el mismo fixture.

## Bugs reales encontrados durante los fixes

Ninguno de los dos hubiera aparecido con sólo tests unit (fake bridge) — los
dos requirieron la corrida en vivo contra KiCad real.

1. **`remove_many_by_kiid` llamaba mal la API de kipy.** Implementación
   inicial: `raw_board.remove_items(*items)` (desempaquetado). La firma real
   de `kipy.Board.remove_items` es
   `(self, items: BoardItem | Sequence[BoardItem])` — **un solo parámetro**,
   no variádico. Con 335 ítems a borrar, kipy lanzó
   `TypeError: remove_items() takes 2 positional arguments but 335 were
   given`, envuelto por el bridge como `KICAD_CLI_FAILED`. Fix: pasar la
   lista directo (`remove_items(items)`). Se agregó un test de regresión en
   `test_ipc.py` con un `raw_board` fake cuya firma de `remove_items` replica
   la real (un solo parámetro) — sin esa forma exacta, un fake más laxo no
   lo hubiera atrapado.
2. **Baseline de DRC del E2E medía el archivo viejo, no el board real.** El
   diseño inicial de `test_zones_e2e_gui.py` llamaba `run_drc()` (la tool)
   **antes** de `route_board` para armar un "baseline" — pero `run_drc`
   lee de **disco** (`_resolve_pcb()`), mientras que `add_zone`/
   `fill_zones`/`delete_tracks_bulk` mutan sólo el board **vivo** por IPC
   (esto ya está documentado como constraint general en
   `docs/specs/tool-catalog.md` y `docs/pruebas-gui.md`, pero no se aplicó
   al diseñar este test). El baseline resultante (1 error) reflejaba el
   `.kicad_pcb` pristino recién restaurado en disco, no el board
   vaciado+con plano recién armado — comparado contra el DRC post-route real
   (32 errores en la corrida con el bug), producía un falso "route_board
   introdujo violaciones" que no era comparable. Fix: usar
   `route_payload["drc"]["err_preexistentes"]`/`["err_post"]` — que
   `route_board` mide correctamente porque hace su propio `save_board`
   (live→disco) ANTES de su DRC pre-route interno — exactamente lo que
   midió 19c Bloque 3. Con el fix, la misma corrida (con más margen) convergió
   limpia y el test pasó.

## Estado de los 4 caveats de 19c

| # | Caveat | Estado post-19d |
|---|---|---|
| 1 | `add_via` no verifica el net resultante contra lo pedido | **Cerrado en tool.** `NET_ASSIGNMENT_MISMATCH` — verificado en vivo. |
| 2 | Workaround manual (`get_tracks` antes de cada `add_via`) | **Ya no es obligatorio** — el fix lo hace innecesario (la tool ahora falla honesto en vez de aceptar silenciosamente). Sigue siendo una buena práctica defensiva, ya no un requisito de seguridad. |
| 3 | Sin tool de borrado masivo (266 llamadas en 19c Bloque 3) | **Cerrado.** `delete_tracks_bulk`, dogfood exitoso en el E2E reescrito. |
| 4 | `test_zones_e2e_gui.py` prueba el escenario equivocado (plano+keepout pre-route) | **Cerrado.** Reescrito al escenario Bloque 3 (sin keepout), verde en vivo. |

**Adicional, no listado como caveat pero confirmado esta sesión:** el bug de
net-hijacking es simétrico entre `add_via` y `add_track` (19d.0) — ambos
comparten el mismo fix.

## Contrato final de las tools modificadas/nuevas

- `add_via` — sin cambio de firma. Nuevo error posible:
  `NET_ASSIGNMENT_MISMATCH`.
- `add_track` — **cambio de tipo de retorno interno del bridge** (`None` →
  `str`, KIID). La tool MCP no cambia de firma (sigue devolviendo el
  confirm de texto); el KIID ahora se usa internamente para la
  verificación. Nuevo error posible: `NET_ASSIGNMENT_MISMATCH`.
- `delete_tracks_bulk` (nueva) —
  `(net?, bbox?, layer?, include_vias?=true, dry_run?=false, base_snap?) ->
  JSON {tracks_deleted, vias_deleted, snap_id, zones_refilled}`. Errores:
  `NET_NOT_FOUND`, `INVALID_PARAMS`, `PROJECT_NOT_FOUND`, `KICAD_NOT_RUNNING`,
  `KICAD_TIMEOUT`, `KICAD_RESTARTED`, `SNAPSHOT_STALE`,
  `EXTERNAL_EDIT_DETECTED`.
- `errors.py` — nuevo `NET_ASSIGNMENT_MISMATCH`.
- `bridge/ipc.py` — nuevo `remove_many_by_kiid(board, kiids) -> int`; nuevo
  helper module-level `_verify_created_net_or_revert`.

`docs/specs/tool-catalog.md` actualizado en el mismo commit (taxonomía +
filas per-tool de `add_via`/`add_track`/`delete_tracks_bulk`).

## Diff-resumen

```
docs/specs/tool-catalog.md    |   6 +-   (taxonomía + filas per-tool)
src/kicad_mcp/bridge/ipc.py   | 132 ++-  (verify+revert, remove_many_by_kiid)
src/kicad_mcp/errors.py       |   1 +    (NET_ASSIGNMENT_MISMATCH)
src/kicad_mcp/tools/pcb.py    | 135 ++   (delete_tracks_bulk)
tests/test_ipc.py             | 140 ++   (6 tests: verify+revert ×4, remove_many ×2)
tests/test_pcb.py             |   6 +-   (fake bridge: add_track -> str)
tests/test_pcb_session11.py   |   6 +-   (idem)
tests/test_pcb_session16.py   |   6 +-   (idem)
tests/test_pcb_delete_bulk.py | nuevo    (8 tests unit delete_tracks_bulk)
tests/test_pcb_session19d_gui.py | nuevo (4 tests integration_gui, todos verdes en vivo)
tests/test_zones_e2e_gui.py   | 250 ~~~  (reescrito a escenario Bloque 3, verde en vivo)
```

## Suites

`uv run pytest -m "not integration and not integration_gui and not
integration_gui_slow"`: **315 passed** (301 heredados de sesión 19 + 14
nuevos: 4 en `test_ipc.py` de verify+revert + 2 de `remove_many_by_kiid` + 8
en `test_pcb_delete_bulk.py`). `ruff check`/`ruff format --check` limpios.
`mypy src/` limpio (33 módulos).

`integration_gui`/`integration_gui_slow` corridos en vivo contra KiCad
10.0.4 real (fixture despertador-routed, restaurado desde
`tests/fixtures/despertador-routed/` a `/tmp/gui-test-project/` +
`reload_board_from_disk` cuando la copia de trabajo quedó sin cobre por
corridas de sesiones previas): 3 tests de `test_pcb_session19d_gui.py`
(mismatch add_via/add_track + caso feliz) + 1 de borrado masivo + 1 E2E de
`test_zones_e2e_gui.py` — **todos verdes**.

## Notas operacionales

- Durante 19d.0 KiCad se cerró de forma forzosa (crash) por una razón no
  determinada — no se pudo aislar si alguna de las mutaciones rápidas en
  cadena (add_track/add_via/delete en loop) lo disparó, o fue inestabilidad
  del proceso en sí. El humano reinició KiCad manualmente; el board no
  perdió datos (no se había guardado nada nuevo en disco todavía). Se
  documenta como riesgo operacional para el D3: si el agente hace mutaciones
  IPC muy rápidas en cadena, considerar guardar (`save_board`) con más
  frecuencia como red de seguridad adicional a los backups de G1.
- La copia de trabajo en `/tmp/gui-test-project/` había quedado con sólo 2-3
  ítems de cobre residual (debris de sesiones 18/19c anteriores, nunca
  restaurada). Se restauró desde el fixture versionado (`tests/fixtures/
  despertador-routed/`, intacto — nunca mutado in-place) dos veces durante
  esta sesión, con confirmación explícita del humano antes de sobrescribir
  la copia de trabajo. Se recomienda restaurar la copia de trabajo antes de
  arrancar el D3 (protocolo ya documentado en `docs/pruebas-gui.md`).
- No se tocó `docs/specs/**` salvo `tool-catalog.md` (excepción explícita de
  F1/DoD #2), ni `tests/golden/**` (F1). No se tocó lógica de gates (F2). No
  se renombró ningún código de error existente (F3). No se agregaron
  dependencias (F5). Todo el trabajo fue contra KiCad 10.0.4 (F4).
- `KICAD_MCP_GUI_REF` (env var listada en el prompt de esta sesión) **sí
  existe** en el repo — se usa como default de ref en varios tests
  `integration_gui` más antiguos (sesiones 6/7/8/11) y en `test_ipc.py`; no
  la usa `test_zones_e2e_gui.py` ni `test_pcb_session19d_gui.py` (ambos
  resuelven el board/nets dinámicamente). Corrección a una nota preliminar
  de esta misma sesión que había concluido erróneamente que no existía.

## Cierre

Los 4 caveats de 19c quedan resueltos en las tools (no sólo documentados),
con verificación en vivo de cada uno. El Dogfooding 3 puede arrancar sin los
workarounds operacionales que 19c había dejado como precondición — quedan
como buenas prácticas defensivas, no como requisitos de seguridad.
