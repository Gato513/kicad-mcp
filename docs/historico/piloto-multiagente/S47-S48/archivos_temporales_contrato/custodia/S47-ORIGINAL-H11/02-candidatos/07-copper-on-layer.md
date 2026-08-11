# Ficha 7 — `_copper_on_layer`

```
K = {_copper_on_layer}   (LOC=6, L432-437)
```

Semilla S3 (3 consumidores: `_opposite_layer_blocked` [stitching,
institucional], `delete_tracks_bulk` [institucional], `get_tracks` [no
materializado]).

**M2:** d1=0, d2=0 (hoja — predicado de comparación de string de capa, sin
llamadas salientes), d3=1 (`..bridge.ipc`), d4=1, d5=3
(`entrante_interna={_opposite_layer_blocked, delete_tracks_bulk,
get_tracks}`). `M2_actual_vector=(0,0,1,1,3)`.

**S1:** cumple (d2=0, sin riesgo de ciclo).
**S2:** cumple, 1 reexport.
**S3:** simple (6 líneas, predicado puro).
**S4:** sin test focal; `COBERTURA_INFERIDA` transitiva.
**S5:** cumple. **S6:** `REFERENCIA_EXISTENTE` — no es geometría de
coordenadas, es comparación de nombre de capa; sin adyacencia siquiera
temática con DT3.

**S7:** NO cumple ninguna cuantitativa (0<80, 0<3, 6<100) — el candidato
más pequeño del universo materializado. S7.d no demostrable (predicado de 6
líneas, ya de responsabilidad mínima posible).

**S8:** M2_proyectado = M2_actual (igualdad).

**R activado:** R11.

**Veredicto individual: NO_APTO.**
