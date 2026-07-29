Generado con pcbnew (KiCad 10.0.4, `/usr/bin/python3`), partiendo de
`tests/fixtures/005_pcb_limpio/clean_board.kicad_pcb` (Edge.Cuts 50x50mm)
como base: se agregaron 2 footprints `R_0805_2012Metric` más (`R1`/`R2`,
en (15,35)mm y (35,35)mm) conectados por un net real (`NET1`).

Estado final: 4 footprints —
- 2× `REF**` (heredados de 005, en (15,15)mm y (35,15)mm — **reference
  designator idéntico, posiciones distintas**, sin net).
- `R1`/`R2` (refs únicos, conectados por `NET1`).

DRC verificado: 0 violations, 3 unconnected items (ratsnest normal de
`NET1` sin rutear — no es una violación).

**Propósito: reproducir el fallo de `pcbnew.ExportSpecctraDSN` con refs
duplicados (F-V1-02, sesión 31/31b).** Contorno Edge.Cuts presente a
propósito: sin él, `_EXPORT_DSN_SCRIPT` (`src/kicad_mcp/bridge/
autoroute.py`) sale por `NO_OUTLINE` (exit 4) antes de llegar al bug real.
Los refs únicos + net sirven de control: tras renombrar los `REF**`
duplicados, un export sobre la misma topología (con conectividad real,
no sólo footprints sueltos) debe ser significativo.

Verificado manualmente antes de comitear el fixture:
- Con los 2 `REF**` intactos: `pcbnew.ExportSpecctraDSN(board, out)` →
  `ok=False`, `size=0`.
- Renombrando ambos a refs únicos (`MH1`/`MH2`): → `ok=True`,
  `size=2356` bytes.

Nunca se muta in-place — todo test que lo use debe copiarlo primero
(`tests/conftest.mirror_fixture`, regla de sesión 03).
