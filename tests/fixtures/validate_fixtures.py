#!/usr/bin/env python3
"""Valida los fixtures contra el motor de conectividad REAL de KiCad.

Para cada fixture: exporta la netlist con kicad-cli, la parsea, y compara
componentes, valores, membresía exacta de nets y pines sin conectar contra
ground_truth.json. Cualquier divergencia es fallo.

Uso: python3 validate_fixtures.py [dir_fixtures]
Requiere kicad-cli en PATH (KiCad 7+).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def netlist(sch: Path) -> ET.Element:
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        out = Path(tmp.name)
    res = subprocess.run(
        ["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml",
         "-o", str(out), str(sch)],
        capture_output=True, text=True, timeout=60,
    )
    if res.returncode != 0:
        raise RuntimeError(f"kicad-cli falló: {res.stderr[:400]}")
    return ET.parse(out).getroot()


def parse(root: ET.Element) -> tuple[dict, dict]:
    comps = {
        c.get("ref"): {
            "value": c.findtext("value") or "",
            "lib": (c.find("libsource").get("lib") + ":" + c.find("libsource").get("part"))
            if c.find("libsource") is not None else "",
        }
        for c in root.iter("comp")
    }
    nets: dict[str, list[str]] = {}
    for n in root.iter("net"):
        members = [f'{node.get("ref")}.{node.get("pin")}' for node in n.iter("node")]
        if len(members) >= 2:  # nets de 1 solo nodo = pin sin conectar
            nets[n.get("name")] = sorted(members)
    return comps, nets


def validate(fixture_dir: Path) -> list[str]:
    gt = json.loads((fixture_dir / "ground_truth.json").read_text())
    comps, nets = parse(netlist(fixture_dir / "fixture.kicad_sch"))
    errs: list[str] = []

    gt_refs = set(gt["components"])
    if set(comps) != gt_refs:
        errs.append(f"refs: netlist={sorted(set(comps) - gt_refs)} extra, "
                    f"faltan={sorted(gt_refs - set(comps))}")
    for ref, meta in gt["components"].items():
        if ref in comps and comps[ref]["value"] != meta["value"]:
            errs.append(f"{ref}: value netlist='{comps[ref]['value']}' gt='{meta['value']}'")
        if ref in comps and comps[ref]["lib"] != meta["lib"]:
            errs.append(f"{ref}: lib netlist='{comps[ref]['lib']}' gt='{meta['lib']}'")

    gt_nets = {k: v for k, v in gt["nets"].items() if len(v) >= 2}
    if set(nets) != set(gt_nets):
        errs.append(f"nets: extra={sorted(set(nets) - set(gt_nets))}, "
                    f"faltan={sorted(set(gt_nets) - set(nets))}")
    for name in set(nets) & set(gt_nets):
        if nets[name] != gt_nets[name]:
            errs.append(f"net {name}: netlist={nets[name]} gt={gt_nets[name]}")

    # pines sin conectar: los del gt no deben aparecer en ninguna net real
    in_nets = {m for ms in nets.values() for m in ms}
    for pin in gt["unconnected_pins"]:
        if pin in in_nets:
            errs.append(f"pin {pin} debía estar sin conectar pero está en una net")
    return errs


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    dirs = sorted(d for d in root.iterdir()
                  if d.is_dir() and (d / "ground_truth.json").exists())
    if not dirs:
        print("No hay fixtures con ground_truth.json en", root)
        return 2
    failed = False
    for d in dirs:
        errs = validate(d)
        status = "OK ✓" if not errs else "FALLO ✗"
        print(f"{d.name}: {status}")
        for e in errs[:10]:
            print("   -", e)
        failed |= bool(errs)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
