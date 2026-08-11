# Ficha 6 — `_copper_in_bbox`

```
K = {_copper_in_bbox}   (LOC=12, L418-429)
```

Semilla S3 (2 consumidores: `delete_tracks_bulk` [excluido institucional],
`get_tracks` [no materializado, ficha #18 de la lista sin ficha]).

**M2:** d1=0, d2=1 (`_copper_in_bbox -> _segment_intersects_bbox`, ficha 12,
fuera de K), d3=1 (`..bridge.ipc`), d4=1, d5=2
(`entrante_interna={delete_tracks_bulk, get_tracks}`).
`M2_actual_vector=(0,1,1,1,2)`.

**S1: NO CUMPLE.** El único destino de d2 (`_segment_intersects_bbox`) no
forma parte de K:

```
Opción A: importar _segment_intersects_bbox desde pcb.py -> arista módulo
  nuevo -> pcb.py, PROHIBIDA. S1 no cumple.
Opción B: inyectarlo como parámetro -> d1 pasa de 0 a 1, EMPEORA esa
  dimensión (de 0 a 1 es un aumento estricto). S8 no cumple.
```

Mismo patrón que fichas 1/3, a escala menor.

**S7:** NO cumple ninguna cuantitativa (0<80, 0<3, 12<100).

**Veredicto individual: NO_APTO** — doble motivo: S1/S8 (arriba) y S7 sin
dispensa E1 (función de una línea de lógica, sin mezcla que eliminar).
