"""Fixture deliberadamente rota para PR-broken (sesión 35).

Propósito: disparar `pytest -m "not integration and not integration_gui and
not integration_gui_slow"` (assertion falla) sin afectar los otros tres
checks. `mypy src/` no ve tests/. Ruff no revisa la semántica del assert.

Nota respecto al draft original: se usa `assert 1 == 2` en vez de
`assert False` porque `assert False` dispara `B011` de ruff (`flake8-bugbear`,
parte del `select` activo en `pyproject.toml`) y contaminaría también el job
de lint — el objetivo es que esta fixture falle *sólo* pytest.

Sin marcador de integración: el filtro del CI lo debe descubrir y correr.
Si el CI reporta este test como *deselected* en lugar de *failed*, es señal
de que el filtro es demasiado estricto — refuta el criterio de éxito #3.

Este archivo NO debe mergearse. Vive sólo en la rama `sesion/35-pr-broken-canary`
(draft).
"""


def test_ci_broken_canary() -> None:
    assert 1 == 2, "PR-broken canary; este test falla a propósito para validar H1"
