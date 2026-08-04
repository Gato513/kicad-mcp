"""Fixture deliberadamente rota para PR-broken (sesión 35).

Propósito: disparar `ruff format --check` (espaciado incorrecto en la firma)
sin afectar los otros tres checks. Los tipos son válidos, no hay imports no
usados, el archivo no es un test.

Este archivo NO debe mergearse. Vive sólo en la rama `sesion/35-pr-broken-canary`
(draft).
"""


def add(x:int, y:int)->int:
    return x + y
