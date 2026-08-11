# Ficha 17 — `get_component_detail`

```
K = {get_component_detail}   (LOC=21, L1975-1995, @mcp.tool closure, no mutante)
```

**Nota de divergencia LOC (H-S47EXT-01):** `enumeracion.md §6`/contrato §2
anotan LOC=30. Re-derivación de esta sesión: LOC=21. Ver
`04-hallazgos-fuera-de-scope-ext.md`. No altera el veredicto.

```python
@mcp.tool(name="get_component_detail", ...)
def get_component_detail(ref: str, kind: str = "pcb") -> str:
    with tool_call_timer() as timer:
        if kind != "pcb":
            raise KicadMcpError(code=ErrorCode.INVALID_PARAMS, ...)
        board = _resolve_board(bridge)
        detail = bridge.get_component_detail(board, ref)
        out = _encode_component_detail(detail)
    ...
    return out
```

## M1 — Volumen

LOC actual = 21. 1 closure eliminada de `register()`. Reducción de `pcb.py`
= 21 LOC.

## M2 — Acoplamiento

```
M2_actual_vector = (d1=1, d2=1, d3=3, d4=0, d5=0)
d1_simbolos: ['bridge']
d2_aristas: [['get_component_detail','_resolve_board','CALL']]
d3_modulos: ['..errors', '..logging_config', '.pcb_encoders']
d4_simbolos: []
d5_detalle: entrante_interna=[], entrante_src=[], entrante_tests=[]
```

Dependencia hacia `_resolve_board` (ficha 11 del paquete original,
NO_APTO, permanece en `pcb.py`). Mismo dilema estructural latente que las
fichas closure-bearing: import-back viola S1; inyectar `_resolve_board`
como parámetro sube `d1` 1→2, activa R11. No determinante — S7 falla
primero.

## M3 — Superficie observable

`@mcp.tool(name="get_component_detail")`, no mutante (sin
`@mutating_tool`). Código de error [F3]: `INVALID_PARAMS` (para
`kind != "pcb"`). Usa `_encode_component_detail` de `pcb_encoders.py`
(sesión 41, ya sanitiza `ref`/campos según `docs/specs/toon-v1.md §5` —
regla de código 6 de CLAUDE.md).

## M4 — Cobertura

`COBERTURA_DEMOSTRADA`: 3 tests offline con assert
(`tests/test_pcb_session11.py::test_get_component_detail_encodes_pads`,
`test_get_component_detail_unknown_ref`,
`test_get_component_detail_sch_not_supported`) + 5 tests `integration_gui`/
`integration_gui_slow` que lo ejercitan como parte de flujos de zona/
vecindad (no exclusivos de esta tool, pero corroboran la ruta feliz en
GUI real).

## Gates S1–S8

**S1:** no determinante — el estado actual cumple, pero el gate se evalúa
sobre la **extracción proyectada**, que aquí no se evalúa completamente
porque S7 rechaza primero (ver M2 y S7). No se afirma cumplimiento de S1
bajo extracción (corrección C-EXT-03).
**S2:** cumple. **S3:** simple.
**S4:** cumple, `COBERTURA_DEMOSTRADA`.
**S5:** cumple. **S6:** `REFERENCIA_EXISTENTE` — aparece en tests GUI de
zonas (`test_pcb_session21_hole_clearance_gui.py`,
`test_zones_e2e_gui.py`) solo como consumidor incidental (verifica
geometría de un footprint durante un flujo de zona), no implementa
geometría de zona; no es `CAMBIO_INCIDENTAL` ni `PRERREQUISITO` de DT3.
**S7:** NO cumple ninguna cuantitativa (21 < 80; 1 closure < 3; 21 < 100).
S7.d no demostrable — función de una responsabilidad (resolver + delegar a
bridge + encodear), ya cohesiva.
**S8:** no determinante (S7 ya falla).

**R activado:** R11 (beneficio marginal, S7 no se satisface).

## Veredicto individual: **NO_APTO** (S7 sin dispensa E1 defendible)
