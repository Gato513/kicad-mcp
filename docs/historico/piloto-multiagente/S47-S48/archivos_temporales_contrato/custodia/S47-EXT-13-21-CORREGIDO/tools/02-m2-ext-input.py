#!/usr/bin/env python3
"""
Derivador mecánico de input para tools/m2.py anclado (S47-CORREGIDO-2),
que solo lee `fichas` de su segundo argumento (clusters.json). El script
m2.py anclado NO se modifica; este derivador solo recorta el campo `fichas`
de un clusters.json existente a un subconjunto contiguo de `survivors`, sin
tocar ningún otro campo.

Uso:
  02-m2-ext-input.py <clusters-in.json> <clusters-out.json> <lo:hi>

<lo:hi> son índices 0-based, extremo hi exclusivo, sobre el array
`survivors` -- p.ej. "12:21" para los 9 supervivientes 13-21 (posiciones
1-indexed 13..21).
"""

import json
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
lo_s, hi_s = sys.argv[3].split(":")
lo, hi = int(lo_s), int(hi_s)

data = json.loads(src.read_text())
survivors = data["survivors"]
subset = survivors[lo:hi]

out = dict(data)
out["fichas"] = subset
dst.write_text(json.dumps(out, indent=2, sort_keys=True))

print(f"OK -> {dst}  fichas={subset}")
