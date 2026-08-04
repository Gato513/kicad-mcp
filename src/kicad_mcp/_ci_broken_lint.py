"""Fixture deliberadamente rota para PR-broken (sesión 35).

Propósito: disparar `ruff check` (F401: import no usado) sin afectar los
otros tres checks. mypy strict no se queja de imports no usados, ruff format
acepta el estilo, y pytest no descubre este archivo.

Este archivo NO debe mergearse. Vive sólo en la rama `sesion/35-pr-broken-canary`
(draft), que se cierra sin merge una vez validado H1.
"""

import os
