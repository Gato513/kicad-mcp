"""Fixture deliberadamente rota para PR-broken (sesión 35).

Propósito: disparar `mypy src/` (return type incompatible: retorna int donde
declaró str) sin afectar los otros tres checks. Ruff (check y format) no hace
inferencia de tipos; pytest no descubre este archivo.

Este archivo NO debe mergearse. Vive sólo en la rama `sesion/35-pr-broken-canary`
(draft).
"""


def double(x: int) -> str:
    # mypy strict marca esto como "Incompatible return value type
    # (got 'int', expected 'str')".
    return x * 2
