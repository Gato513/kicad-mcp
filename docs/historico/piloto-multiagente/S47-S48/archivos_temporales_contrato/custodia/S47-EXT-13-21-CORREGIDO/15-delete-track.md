# Ficha 15 — `delete_track`

```
K = {delete_track}   (LOC=18, L1702-1719, @mcp.tool closure)
```

**Nota de divergencia LOC (H-S47EXT-01):** `enumeracion.md §6`/contrato §2
anotan LOC=51. Re-derivación de esta sesión: LOC=18, confirmado por lectura
directa (L1702-1719, 18 líneas). Ver
`04-hallazgos-fuera-de-scope-ext.md`. No altera el veredicto: 18 y 51 son
ambos << `UMBRAL_S7_LOC=80`.

`delete_track` es un wrapper delgado sobre `_delete_copper` (ficha 1 del
paquete original, cluster propio, NO_APTO, permanece en `pcb.py`):

```python
@mutating_tool("delete_track", base_snap_check=False)
def delete_track(id=None, net=None, near_x_mm=None, near_y_mm=None, base_snap=None) -> str:
    with tool_call_timer() as timer:
        return _delete_copper(tool_name="delete_track", track_id=id, net=net,
                               x_mm=near_x_mm, y_mm=near_y_mm,
                               kinds=("track", "arc"), base_snap=base_snap, timer=timer)
```

## M1 — Volumen

LOC actual = 18. 1 closure eliminada de `register()`. Reducción de `pcb.py`
= 18 LOC.

## M2 — Acoplamiento

```
M2_actual_vector = (d1=0, d2=1, d3=2, d4=0, d5=0)
d1_simbolos: []
d2_aristas: [['delete_track','_delete_copper','CALL']]
d3_modulos: ['..logging_config', '._mutating']
d4_simbolos: []
d5_detalle: entrante_interna=[], entrante_src=[], entrante_tests=[]
```

Sin capturas de scope (`d1=0`) — es un pasamanos puro hacia `_delete_copper`.
Bajo extracción mínima, el único corte es la llamada a `_delete_copper`
(permanece en `pcb.py`, ficha 1). Mismo dilema estructural que ficha 14:
importar de vuelta viola S1; inyectar `_delete_copper` como parámetro
preserva S1 pero sube `d1` de 0 a 1 (empeora), activando R11. No se
profundiza más porque S7 ya falla primero (ver abajo) — el gate de tamaño
detiene la evaluación antes de que S1/S8 sean determinantes para el
veredicto, aunque ambas rutas se documentan para completar M2.

## M3 — Superficie observable

`@mcp.tool(name="delete_track")`, `@mutating_tool("delete_track",
base_snap_check=False)` — la excepción de `base_snap_check` está documentada
en el propio decorador (`_mutating.py`): `delete_track`/`delete_via` validan
`base_snap` dentro de `_delete_copper`, después de resolver `id` vs.
`net`+coordenadas. Sin códigos de error [F3] propios (delega en
`_delete_copper`).

## M4 — Cobertura

`COBERTURA_DEMOSTRADA`: 9 tests offline con assert (`tests/test_pcb_session11.py`
×4: happy/ambigüedad/net-not-found/nothing-in-tolerance;
`tests/test_pcb_session16.py` ×5 adicionales: by-id, ambigüedad con ids,
id-stale, by-id-wrong-kind→track-id-stale, mixing-id-and-coords) + 5 tests
`integration_gui`/`integration_gui_slow`.

**Corrección C-EXT-01 (hallazgo MINOR de revisión independiente):** la
versión original de esta ficha declaraba "6 tests offline" y enumeraba
"×4 + ×6". El conteo verificado contra el código es 4 + 5 = 9, y faltaba
`test_delete_track_by_id_wrong_kind_is_track_id_stale`. M4 sigue siendo
`COBERTURA_DEMOSTRADA` con cualquiera de los dos conteos; el veredicto no
cambia.

## Gates S1–S8

**S1:** no determinante — el estado actual cumple, pero el gate se evalúa
sobre la **extracción proyectada**, que aquí no se evalúa completamente
porque S7 rechaza primero (ver M2 y S7). No se afirma cumplimiento de S1
bajo extracción (corrección C-EXT-03).
**S2:** cumple. **S3:** simple (wrapper de una función).
**S4:** cumple, `COBERTURA_DEMOSTRADA` amplia.
**S5:** cumple. **S6:** `REFERENCIA_EXISTENTE`.
**S7:** NO cumple ninguna cuantitativa (18 < 80; 1 closure < 3; 18 < 100).
S7.d no demostrable: `delete_track` ya es de responsabilidad única (delegar
en `_delete_copper`), no hay mezcla que eliminar.
**S8:** no determinante (S7 ya falla).

**R activado:** R11 (beneficio marginal — S7 no se satisface, sin base para
E1).

## Veredicto individual: **NO_APTO** (S7 sin dispensa E1 defendible)

Con el LOC correcto (18) el fallo de S7 es aún más claro que con el valor
erróneo de `enumeracion.md` (51) — ambos están muy por debajo del umbral, la
divergencia no cambia el resultado.
