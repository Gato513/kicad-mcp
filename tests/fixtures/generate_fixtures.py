#!/usr/bin/env python3
"""Generador determinista de fixtures KiCad para kicad-mcp.

Estrategia:
- Símbolos embebidos en lib_symbols (FIXLIB): sin dependencia de librerías
  instaladas, control total de posiciones de pines.
- Conectividad por global labels colocados EXACTAMENTE en el endpoint de cada
  pin (un label sobre un pin conecta sin necesidad de wires ni junctions).
- UUIDs deterministas (uuid5) → los fixtures son reproducibles byte a byte.
- Cada fixture emite su ground_truth.json calculado independientemente del
  archivo: el validador compara la netlist real de kicad-cli contra él.

Transformación librería→esquemático (rotación 0, sin mirror, la única usada):
    endpoint = (sym_x + pin_x, sym_y - pin_y)   # eje Y invertido
Toda posición es múltiplo de 1.27 mm (grilla de esquemático).

Formato: KiCad 7 (version 20230121) — legible por KiCad 9/10 sin pérdida.
"""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

NS = uuid.UUID("a5b1c2d3-0000-4000-8000-kicadfixture".replace("kicadfixture", "0123456789ab"))
FMT_VERSION = 20230121  # KiCad 7


def uid(name: str) -> str:
    return str(uuid.uuid5(NS, name))


def f2s(v: float) -> str:
    """Formato numérico estilo KiCad: sin decimales superfluos."""
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


# ---------------------------------------------------------------- símbolos
# Cada símbolo: lista de pines (numero, nombre, tipo, x_lib, y_lib, angulo)


@dataclass
class SymDef:
    name: str  # nombre dentro de FIXLIB
    ref_prefix: str
    pins: list[tuple[str, str, str, float, float, int]]
    body: tuple[float, float, float, float]  # rectángulo x1 y1 x2 y2

    def pin_endpoint(self, sym_x: float, sym_y: float, number: str) -> tuple[float, float]:
        for n, _, _, px, py, _ in self.pins:
            if n == number:
                return (sym_x + px, sym_y - py)
        raise KeyError(number)


def two_pin(name: str, prefix: str, ptype: str = "passive") -> SymDef:
    return SymDef(
        name,
        prefix,
        [
            ("1", "~", ptype, 0.0, 5.08, 270),
            ("2", "~", ptype, 0.0, -5.08, 90),
        ],
        (-1.016, 3.81, 1.016, -3.81),
    )


def conn4() -> SymDef:
    pins = [(str(i + 1), "~", "passive", -7.62, 3.81 - i * 2.54, 0) for i in range(4)]
    return SymDef("CONN4", "J", pins, (-5.08, 5.08, 5.08, -5.08))


def mcu8() -> SymDef:
    left = [(str(i + 1), f"P{i}", "bidirectional", -10.16, 3.81 - i * 2.54, 0) for i in range(4)]
    right = [
        (str(i + 5), f"P{i + 4}", "bidirectional", 10.16, -3.81 + i * 2.54, 180) for i in range(4)
    ]
    return SymDef("MCU8", "U", left + right, (-7.62, 6.35, 7.62, -6.35))


def mcu48() -> SymDef:
    left = [(str(i + 1), f"PA{i}", "bidirectional", -15.24, 29.21 - i * 2.54, 0) for i in range(24)]
    right = [
        (str(i + 25), f"PB{i}", "bidirectional", 15.24, -29.21 + i * 2.54, 180) for i in range(24)
    ]
    return SymDef("MCU48", "U", left + right, (-12.7, 31.75, 12.7, -31.75))


SYMBOLS = {
    s.name: s
    for s in [
        two_pin("R2", "R"),
        two_pin("C2", "C"),
        two_pin("LED2", "D"),
        conn4(),
        mcu8(),
        mcu48(),
    ]
}


def emit_lib_symbol(s: SymDef) -> str:
    pins = []
    for num, pname, ptype, px, py, ang in s.pins:
        pins.append(
            f"      (pin {ptype} line (at {f2s(px)} {f2s(py)} {ang}) (length 1.27)\n"
            f'        (name "{pname}" (effects (font (size 1.27 1.27))))\n'
            f'        (number "{num}" (effects (font (size 1.27 1.27)))))'
        )
    x1, y1, x2, y2 = s.body
    ref_line = (
        f'      (property "Reference" "{s.ref_prefix}" (at 0 {f2s(y1 + 2.54)} 0) '
        f"(effects (font (size 1.27 1.27))))\n"
    )
    val_line = (
        f'      (property "Value" "{s.name}" (at 0 {f2s(y2 - 2.54)} 0) '
        f"(effects (font (size 1.27 1.27))))\n"
    )
    return (
        f'    (symbol "FIXLIB:{s.name}" (pin_names (offset 0.254)) (in_bom yes) (on_board yes)\n'
        f"{ref_line}"
        f"{val_line}"
        f'      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
        f'      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
        f'      (symbol "{s.name}_0_1"\n'
        f"        (rectangle (start {f2s(x1)} {f2s(y1)}) (end {f2s(x2)} {f2s(y2)})\n"
        f"          (stroke (width 0.254) (type default)) (fill (type none))))\n"
        f'      (symbol "{s.name}_1_1"\n' + "\n".join(pins) + "))"
    )


# ---------------------------------------------------------------- fixture


@dataclass
class Component:
    ref: str
    sym: str
    value: str
    x: float
    y: float
    nets: dict[str, str]  # numero de pin -> net ("" = sin conectar)


@dataclass
class Fixture:
    name: str
    project: str
    components: list[Component] = field(default_factory=list)

    def add(self, ref: str, sym: str, value: str, x: float, y: float, **nets: str) -> None:
        assert abs(x / 1.27 - round(x / 1.27)) < 1e-9, f"{ref}: x fuera de grilla"
        assert abs(y / 1.27 - round(y / 1.27)) < 1e-9, f"{ref}: y fuera de grilla"
        self.components.append(
            Component(ref, sym, value, x, y, {k.lstrip("p"): v for k, v in nets.items()})
        )

    def ground_truth(self) -> dict:
        nets: dict[str, list[str]] = {}
        unconnected: list[str] = []
        for c in self.components:
            sdef = SYMBOLS[c.sym]
            for num, *_rest in sdef.pins:
                net = c.nets.get(num, "")
                if net:
                    nets.setdefault(net, []).append(f"{c.ref}.{num}")
                else:
                    unconnected.append(f"{c.ref}.{num}")
        return {
            "components": {
                c.ref: {"value": c.value, "lib": f"FIXLIB:{c.sym}", "x": c.x, "y": c.y}
                for c in self.components
            },
            "nets": {k: sorted(v) for k, v in sorted(nets.items())},
            "unconnected_pins": sorted(unconnected),
            "counts": {
                "components": len(self.components),
                "nets": len(nets),
                "unconnected": len(unconnected),
            },
        }

    def emit(self) -> str:
        root = uid(f"{self.name}/root")
        used = sorted({c.sym for c in self.components})
        parts = [
            f"(kicad_sch (version {FMT_VERSION}) (generator fixgen)",
            f"  (uuid {root})",
            '  (paper "A3")',
            "  (lib_symbols",
            *[emit_lib_symbol(SYMBOLS[s]) for s in used],
            "  )",
        ]
        # global labels en endpoints de pines conectados
        for c in self.components:
            sdef = SYMBOLS[c.sym]
            for num, net in sorted(c.nets.items()):
                if not net:
                    continue
                ex, ey = sdef.pin_endpoint(c.x, c.y, num)
                parts.append(
                    f'  (global_label "{net}" (shape input) (at {f2s(ex)} {f2s(ey)} 0)\n'
                    f"    (effects (font (size 1.27 1.27)) (justify left))\n"
                    f"    (uuid {uid(f'{self.name}/{c.ref}/{num}/label')}))"
                )
        # instancias de símbolos
        for c in self.components:
            sdef = SYMBOLS[c.sym]
            pin_uuids = "\n".join(
                f'    (pin "{num}" (uuid {uid(f"{self.name}/{c.ref}/{num}")}))'
                for (num, *_r) in sdef.pins
            )
            parts.append(
                f'  (symbol (lib_id "FIXLIB:{c.sym}") (at {f2s(c.x)} {f2s(c.y)} 0) (unit 1)\n'
                f"    (in_bom yes) (on_board yes) (dnp no)\n"
                f"    (uuid {uid(f'{self.name}/{c.ref}')})\n"
                f'    (property "Reference" "{c.ref}" (at {f2s(c.x + 2.54)} {f2s(c.y - 2.54)} 0)'
                f" (effects (font (size 1.27 1.27))))\n"
                f'    (property "Value" "{c.value}" (at {f2s(c.x + 2.54)} {f2s(c.y + 2.54)} 0)'
                f" (effects (font (size 1.27 1.27))))\n"
                f'    (property "Footprint" "" (at {f2s(c.x)} {f2s(c.y)} 0)'
                f" (effects (font (size 1.27 1.27)) hide))\n"
                f'    (property "Datasheet" "" (at {f2s(c.x)} {f2s(c.y)} 0)'
                f" (effects (font (size 1.27 1.27)) hide))\n" + pin_uuids + "\n"
                f'    (instances (project "{self.project}"\n'
                f'      (path "/{root}" (reference "{c.ref}") (unit 1)))))'
            )
        parts.append('  (sheet_instances (path "/" (page "1")))')
        parts.append(")")
        return "\n".join(parts) + "\n"


# ---------------------------------------------------------------- fixtures


def build_001() -> Fixture:
    """5 componentes: MCU8 + 2 pullups I2C + desacoplo + conector.
    Rasgo plantado: U1.5 (P4) deliberadamente sin conectar."""
    f = Fixture("001_basico", "fixture001")
    f.add(
        "U1",
        "MCU8",
        "MCU-8P",
        127.0,
        63.5,
        p1="3V3",
        p2="GND",
        p3="SDA",
        p4="SCL",
        p5="",
        p6="LED_A",
        p7="GND2X",
        p8="GND2X",
    )
    f.add("R1", "R2", "10k", 152.4, 50.8, p1="3V3", p2="SDA")
    f.add("R2", "R2", "10k", 162.56, 50.8, p1="3V3", p2="SCL")
    f.add("C1", "C2", "100nF", 101.6, 63.5, p1="3V3", p2="GND")
    f.add("J1", "CONN4", "I2C-HDR", 190.5, 63.5, p1="3V3", p2="GND", p3="SDA", p4="SCL")
    return f


def build_002() -> Fixture:
    """~30 componentes. Rasgos plantados: GND con >8 miembros (degradación
    TOON), exactamente 2 pines sin conectar, bus I2C con pullups."""
    f = Fixture("002_medio", "fixture002")
    mcu_nets = {}
    # 24 pines izquierdos del MCU48: alimentación + señales
    mcu_nets["p1"] = "3V3"
    mcu_nets["p2"] = "GND"
    for i in range(3, 13):
        mcu_nets[f"p{i}"] = f"IO{i - 2}"
    mcu_nets["p13"] = "SDA"
    mcu_nets["p14"] = "SCL"
    for i in range(15, 25):
        mcu_nets[f"p{i}"] = "GND"  # muchos GND → colapso
    # 24 derechos: LEDs y sin conectar plantados
    for i in range(25, 33):
        mcu_nets[f"p{i}"] = f"LED{i - 24}"
    mcu_nets["p33"] = ""  # plantado: sin conectar #1
    mcu_nets["p34"] = ""  # plantado: sin conectar #2
    for i in range(35, 49):
        mcu_nets[f"p{i}"] = "GND"
    f.add("U1", "MCU48", "MCU-48P", 127.0, 127.0, **mcu_nets)
    for i in range(1, 9):  # 8 caps de desacoplo
        f.add(f"C{i}", "C2", "100nF", 63.5 + i * 10.16, 63.5, p1="3V3", p2="GND")
    f.add("R1", "R2", "4k7", 63.5, 101.6, p1="3V3", p2="SDA")
    f.add("R2", "R2", "4k7", 73.66, 101.6, p1="3V3", p2="SCL")
    for i in range(1, 9):  # 8 resistencias serie + 8 LEDs
        f.add(f"R{i + 2}", "R2", "330", 190.5 + i * 10.16, 101.6, p1=f"LED{i}", p2=f"LEDK{i}")
        f.add(f"D{i}", "LED2", "LED", 190.5 + i * 10.16, 127.0, p1=f"LEDK{i}", p2="GND")
    f.add("J1", "CONN4", "PWR-I2C", 63.5, 152.4, p1="3V3", p2="GND", p3="SDA", p4="SCL")
    f.add("J2", "CONN4", "GPIO-A", 76.2, 152.4, p1="IO1", p2="IO2", p3="IO3", p4="IO4")
    f.add("J3", "CONN4", "GPIO-B", 88.9, 152.4, p1="IO5", p2="IO6", p3="IO7", p4="IO8")
    return f


def build_003() -> Fixture:
    """150 componentes: 10 bloques de conector + 14 resistencias. Prueba de
    escala para presupuesto TOON, índice espacial y área local. Bloques
    separados 76.2 mm: un radio de 30 mm alrededor de un bloque no toca a
    los vecinos (ground truth espacial)."""
    f = Fixture("003_grande", "fixture003")
    for b in range(10):
        bx = 63.5 + (b % 5) * 76.2
        by = 63.5 + (b // 5) * 127.0
        f.add(
            f"J{b + 1}",
            "CONN4",
            f"BLK{b + 1}",
            bx,
            by,
            p1=f"B{b + 1}_A",
            p2=f"B{b + 1}_B",
            p3=f"B{b + 1}_C",
            p4="GND",
        )
        for r in range(14):
            rx = bx + 5.08 + (r % 7) * 2.54
            ry = by - 12.7 + (r // 7) * 25.4
            net_in = [f"B{b + 1}_A", f"B{b + 1}_B", f"B{b + 1}_C"][r % 3]
            f.add(f"R{b * 14 + r + 1}", "R2", "1k", rx, ry, p1=net_in, p2="GND")
    return f


def main(out_root: Path) -> None:
    for fx in (build_001(), build_002(), build_003()):
        d = out_root / fx.name
        d.mkdir(parents=True, exist_ok=True)
        (d / "fixture.kicad_sch").write_text(fx.emit())
        gt = fx.ground_truth()
        # Preservar campos aportados fuera del generador (p. ej. erc_expected,
        # observado con kicad-cli; no computable desde la spec de la fixture).
        existing_path = d / "ground_truth.json"
        if existing_path.is_file():
            existing = json.loads(existing_path.read_text())
            for key, value in existing.items():
                if key not in gt:
                    gt[key] = value
        existing_path.write_text(json.dumps(gt, indent=2) + "\n")
        print(
            f"{fx.name}: {gt['counts']['components']} comp, "
            f"{gt['counts']['nets']} nets, "
            f"{gt['counts']['unconnected']} sin conectar"
        )


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
