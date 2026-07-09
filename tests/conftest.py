"""Utilidades compartidas de tests.

Regla de la sesión 03: los fixtures en ``tests/fixtures/`` NUNCA se
mutan in place. Todo test que dispare kicad-cli u operaciones que
escriban en la carpeta del proyecto debe operar sobre una copia en
``tmp_path``. ``mirror_fixture`` implementa esa copia.
"""

from __future__ import annotations

from pathlib import Path


def mirror_fixture(src: Path, dst: Path) -> Path:
    """Copia recursivamente el fixture ``src`` al destino ``dst``.

    Devuelve ``dst`` para permitir uso encadenado. Copia archivos y
    subdirectorios; los enlaces simbólicos se resuelven a su contenido.
    """
    dst.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        target = dst / entry.name
        if entry.is_dir():
            mirror_fixture(entry, target)
        elif entry.is_file():
            target.write_bytes(entry.read_bytes())
    return dst
