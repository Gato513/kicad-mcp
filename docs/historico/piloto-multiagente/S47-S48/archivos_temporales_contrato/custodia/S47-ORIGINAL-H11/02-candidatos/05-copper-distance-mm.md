# Ficha 5 — `_copper_distance_mm` + `_dist_point_segment`

```
K = {_copper_distance_mm, _dist_point_segment}   (LOC=18+12=30)
```

Semilla S3 (`_copper_distance_mm`, 2 consumidores: `_match_copper` [ficha 1],
`_opposite_layer_blocked` [excluido institucional, familia stitching]).
Expandido con `_dist_point_segment` (único consumidor: `_copper_distance_mm`,
absorbido por C2).

**M2:** d1=0, d2=0 (`_dist_point_segment` está dentro de K, sin más
llamadas salientes a V), d3=1 (`..bridge.ipc`, tipo `CopperItem`), d4=1
(`_copper_distance_mm` mismo), d5=2 (`entrante_interna={_match_copper,
_opposite_layer_blocked}`). `M2_actual_vector=(0,0,1,1,2)`.

**S1:** cumple (d2=0). **S2:** cumple, 1 reexport necesario. **S3:** simple.
**S4:** sin test focal directo; `COBERTURA_INFERIDA` (vía `_match_copper`,
que a su vez solo se ejerce transitivamente por `delete_track`/`delete_via`
— cadena de inferencia larga, sin aserción directa sobre la distancia
calculada).

**S5:** cumple. **S6:** `REFERENCIA_EXISTENTE` (mismo razonamiento
geométrico que fichas 3/4; `_opposite_layer_blocked`, uno de los 2
consumidores, sí pertenece a la familia stitching institucionalmente
segregada — pero eso no convierte a `_copper_distance_mm` en zona
institucional per se: no cae en la regla (b) de `enumeracion.md` porque
tiene OTRO consumidor, `_match_copper`, fuera de la familia zonas/stitching
— se documenta la adyacencia como hallazgo §14 sin escalar a exclusión).

**S7:** NO cumple ninguna cuantitativa (0<80, 0<3, 30<100). S7.d no
demostrable (matemática de distancia pura, responsabilidad ya única).

**S8:** M2_proyectado = M2_actual bajo diseño mínimo (1 reexport) — cumple
por igualdad, no domina.

**R activado:** R11.

**Veredicto individual: NO_APTO** (S7 sin dispensa E1 defendible).
