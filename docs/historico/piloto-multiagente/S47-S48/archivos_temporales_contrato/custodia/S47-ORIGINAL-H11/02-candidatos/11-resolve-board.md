# Ficha 11 — `_resolve_board`

```
K = {_resolve_board}   (LOC=9, L242-250)
```

Semilla S3 — el helper con **mayor fan-in de todo pcb.py**: 17
consumidores (`docs/analisis/40-dt1-caracterizacion.md §5` lo confirma
independientemente: "`_resolve_board` (17 tools — utilidad transversal, no
señal de acoplamiento entre familias)").

**M2:** d1=0 (función pura, `bridge` es su propio parámetro explícito —
`def _resolve_board(bridge: IpcBridge) -> BoardHandle`), d2=0 (hoja, solo
llama a `bridge.get_board()` externo), d3=2 (`..bridge.ipc`, `..errors`),
d4=1, d5=17 (`entrante_interna` = los 17 closures listados en
`raw/m2.json`, incluye `_delete_copper`, todos los 12 `@mcp.tool` restantes
que resuelven tablero, `add_via`, `add_zone`/`add_keepout_zone`, etc.).
`M2_actual_vector=(0,0,2,1,17)`.

**S1:** cumple (d2=0, dependencia solo hacia `bridge/` estable).
**S2:** cumple, 1 reexport (por debajo de `UMBRAL_R7_REEXPORTS=3` pese al
fan-in de 17 — el umbral R7 mide reexports NECESARIOS, no consumidores;
aquí basta 1 reexport para servir a los 17).
**S3:** simple (9 líneas, patrón idéntico a un helper de `pcb_encoders.py`).
**S4:** sin test focal directo; `COBERTURA_INFERIDA` fuerte por
transitividad extrema (17 caminos independientes lo ejercen, muchos con
`assert` — ver `raw/coverage.json` de sus consumidores), pero ningún test
asigna una aserción a `_resolve_board` en sí (p. ej. sobre el manejo de
`BOARD_NOT_FOUND`).

**S5:** cumple. **S6:** `REFERENCIA_EXISTENTE` (resolución de handle IPC,
no geometría de dominio, sin relación con DT3/P1-2).

**S7:** NO cumple ninguna cuantitativa (0<80, 0<3, 9<100). S7.d no
demostrable: función de una expresión (`return bridge.get_board(...)` con
manejo de error), responsabilidad ya mínima y única.

**S8:** M2_proyectado = M2_actual bajo diseño mínimo (1 reexport preserva
los 17 accesos sin cambio de conteo) — cumple por igualdad, no domina.

**R activado:** R11.

**Veredicto individual: NO_APTO** (S7 sin dispensa E1 defendible). Nota
para H11: pese a ser NO_APTO por tamaño, este es el helper con la señal de
"utilidad transversal genuina" más fuerte de todo el archivo (17
consumidores, 0 aristas salientes propias) — un candidato natural si
alguna vez se autoriza consolidar la familia `{_resolve_board, _audit_error,
_similars}` en un módulo `pcb_utils.py` compartido (fuera del alcance de
S47, que solo caracteriza el universo enumerado por el algoritmo §7.1).
