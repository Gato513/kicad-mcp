"""Bridge a KiCad: IPC (kicad-python) y kicad-cli (subprocess).

MVP: solo el wrapper de ``kicad-cli`` (`kicad_cli.py`). El bridge IPC
persistente en Python se introduce en v0.2 con las mutaciones de PCB.

Regla de código #1: los subprocesses se invocan con **lista de argumentos**,
timeout obligatorio, ``shell=False`` siempre. Nunca interpolar entrada del
agente ni del proyecto en un comando.
"""
