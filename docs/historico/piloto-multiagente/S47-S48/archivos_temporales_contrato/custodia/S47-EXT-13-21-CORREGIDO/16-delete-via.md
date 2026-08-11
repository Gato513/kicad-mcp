# Ficha 16 — `delete_via`

```
K = {delete_via}   (LOC=18, L1726-1743, @mcp.tool closure)
```

**Nota de divergencia LOC (H-S47EXT-01):** `enumeracion.md §6`/contrato §2
anotan LOC=24. Re-derivación de esta sesión: LOC=18 (idéntico a
`delete_track`, mismo patrón de wrapper). Ver
`04-hallazgos-fuera-de-scope-ext.md`. No altera el veredicto.

```python
@mutating_tool("delete_via", base_snap_check=False)
def delete_via(id=None, net=None, x_mm=None, y_mm=None, base_snap=None) -> str:
    with tool_call_timer() as timer:
        return _delete_copper(tool_name="delete_via", track_id=id, net=net,
                               x_mm=x_mm, y_mm=y_mm,
                               kinds=("via",), base_snap=base_snap, timer=timer)
```

## M1 — Volumen

LOC actual = 18. 1 closure eliminada de `register()`. Reducción de `pcb.py`
= 18 LOC.

## M2 — Acoplamiento

```
M2_actual_vector = (d1=0, d2=1, d3=2, d4=0, d5=0)
d1_simbolos: []
d2_aristas: [['delete_via','_delete_copper','CALL']]
d3_modulos: ['..logging_config', '._mutating']
d4_simbolos: []
d5_detalle: entrante_interna=[], entrante_src=[], entrante_tests=[]
```

Estructuralmente idéntico a `delete_track` (ficha 15): pasamanos puro hacia
`_delete_copper`. Mismo dilema S1-vs-S8 latente (import-back viola S1;
inyección de `_delete_copper` como parámetro sube `d1` 0→1, activa R11), no
determinante porque S7 ya falla primero.

## M3 — Superficie observable

`@mcp.tool(name="delete_via")`, `@mutating_tool("delete_via",
base_snap_check=False)` (misma justificación documentada que
`delete_track`). Sin códigos de error [F3] propios.

## M4 — Cobertura

`COBERTURA_DEMOSTRADA` pero delgada: 1 solo test offline con assert
(`tests/test_pcb_session11.py::test_delete_via_happy`) + 1 test
`integration_gui` (`test_delete_via_round_trip`). Cobertura offline
significativamente más delgada que `delete_track` (1 vs. 6 tests) — se
declara la limitación explícitamente: no hay evidencia offline de los casos
de ambigüedad/net-not-found/nothing-in-tolerance para `delete_via`
específicamente (aunque el núcleo compartido `_delete_copper` sí los cubre
vía los tests de `delete_track`, que ejercitan el mismo código).

## Gates S1–S8

**S1:** no determinante — el estado actual cumple, pero el gate se evalúa
sobre la **extracción proyectada**, que aquí no se evalúa completamente
porque S7 rechaza primero (ver M2 y S7). No se afirma cumplimiento de S1
bajo extracción (corrección C-EXT-03).
**S2:** cumple. **S3:** simple.
**S4:** cumple con reserva — `COBERTURA_DEMOSTRADA` mínima (1 test propio),
el resto de la cobertura de `_delete_copper` es compartida con
`delete_track`, no exclusiva de `delete_via`. No es gate bloqueante por sí
solo (S7 ya falla).
**S5:** cumple. **S6:** `REFERENCIA_EXISTENTE`.
**S7:** NO cumple ninguna cuantitativa (18 < 80; 1 closure < 3; 18 < 100).
S7.d no demostrable — responsabilidad única, sin mezcla que eliminar.
**S8:** no determinante (S7 ya falla).

**R activado:** R11 (beneficio marginal, S7 no se satisface).

## Veredicto individual: **NO_APTO** (S7 sin dispensa E1 defendible)
