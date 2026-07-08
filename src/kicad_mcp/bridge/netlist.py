"""Lectura de conectividad vía ``kicad-cli sch export netlist --format kicadxml``.

La netlist es la fuente de verdad de conectividad
(``docs/specs/restricciones-kicad.md``): NO se reimplementa desde el archivo
``.kicad_sch``. Los pines sin conectar quedan expuestos por KiCad como una
net cuyo nombre matchea ``unconnected-*``; aquí se normalizan a ``net=None``.
"""

from __future__ import annotations

import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from ..errors import ErrorCode, KicadMcpError

_TIMEOUT_S: Final = 60.0
_UNCONNECTED_PREFIX: Final = "unconnected-"


@dataclass(frozen=True)
class NetlistComponent:
    """Un ``<comp>`` del netlist normalizado."""

    ref: str
    value: str
    lib: str
    pin_ids: tuple[str, ...]


@dataclass(frozen=True)
class Netlist:
    """Resultado de parsear el netlist ``kicadxml``."""

    components: tuple[NetlistComponent, ...]
    nets: dict[str, tuple[tuple[str, str], ...]] = field(default_factory=dict)
    unconnected_pins: tuple[tuple[str, str], ...] = ()


def _run_kicad_cli_netlist(schematic: Path, output: Path) -> None:
    """Invoca ``kicad-cli sch export netlist``. Lanza ``KicadMcpError`` tipado."""
    args = [
        "kicad-cli",
        "sch",
        "export",
        "netlist",
        "--format",
        "kicadxml",
        "-o",
        str(output),
        str(schematic),
    ]
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_MISSING,
            message="kicad-cli no está en PATH.",
            hint="Instala KiCad ≥ 9.0 o exporta PATH con kicad-cli.",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message=f"kicad-cli tardó más de {_TIMEOUT_S:.0f}s exportando netlist.",
            hint="Reintentar; si persiste, reducir el alcance del esquemático.",
        ) from exc
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()[:200]
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message="kicad-cli devolvió error al exportar el netlist.",
            hint=stderr or f"returncode={completed.returncode}",
        )


def _parse_netlist_xml(xml_path: Path) -> Netlist:
    """Parsea el XML de ``kicadxml`` a la estructura tipada."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    components: list[NetlistComponent] = []
    for comp in root.findall("./components/comp"):
        ref = comp.attrib.get("ref", "")
        value_el = comp.find("value")
        value = (value_el.text or "") if value_el is not None else ""
        libsrc = comp.find("libsource")
        lib_lib = libsrc.attrib.get("lib", "") if libsrc is not None else ""
        lib_part = libsrc.attrib.get("part", "") if libsrc is not None else ""
        lib = f"{lib_lib}:{lib_part}" if lib_lib or lib_part else ""
        pin_ids = tuple(pin.attrib.get("num", "") for pin in comp.findall("./units/unit/pins/pin"))
        components.append(NetlistComponent(ref=ref, value=value, lib=lib, pin_ids=pin_ids))

    nets: dict[str, tuple[tuple[str, str], ...]] = {}
    unconnected: list[tuple[str, str]] = []
    for net in root.findall("./nets/net"):
        name = net.attrib.get("name", "")
        members = tuple(
            (node.attrib.get("ref", ""), node.attrib.get("pin", "")) for node in net.findall("node")
        )
        if name.startswith(_UNCONNECTED_PREFIX):
            unconnected.extend(members)
        else:
            nets[name] = members

    return Netlist(
        components=tuple(components),
        nets=nets,
        unconnected_pins=tuple(unconnected),
    )


def load_netlist(schematic: Path) -> Netlist:
    """Exporta y parsea el netlist del esquemático dado.

    ``schematic`` debe ser una ruta absoluta ya canonicalizada por el
    llamador (regla de código #4). Escribe el XML a un temporal y lo
    borra al terminar.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".xml", delete=False, dir=str(schematic.parent)
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        _run_kicad_cli_netlist(schematic, tmp_path)
        return _parse_netlist_xml(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
