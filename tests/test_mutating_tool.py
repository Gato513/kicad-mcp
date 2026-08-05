"""Tests unit del decorador ``@mutating_tool`` (DT2, sesión 39).

Dos niveles:
1. **Aislado** — ejercita ``mutating_tool`` directamente contra spies que
   reemplazan las tres guardas reales (``_guard_live_stale``,
   ``check_no_external_disk_edit``, ``_check_base_snap``), sin tocar el
   store real, IPC ni disco. Cubre orden, gating por flag, propagación de
   excepciones con su ``code`` intacto (F3) y preservación de metadata
   (``functools.wraps``).
2. **Canario de registro** — registra ``tools/pcb.py`` completo contra un
   ``FastMCP`` real y verifica que las 12 tools de la superficie decidida
   en sesión 39 llevan la marca ``__mutating_tool__``. Una mutante nueva
   que se agregue a la Familia A sin el decorador rompe este test.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP

import kicad_mcp.tools._mutating as mutating_mod
from kicad_mcp.errors import ErrorCode, KicadMcpError
from kicad_mcp.tools._mutating import mutating_tool
from kicad_mcp.tools.pcb import register as register_pcb

# ---------------------------------------------------------------------------
# 1. Decorador aislado — spies sobre las tres guardas reales del módulo.
# ---------------------------------------------------------------------------


@pytest.fixture
def _calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Reemplaza las tres guardas de ``_mutating`` por spies mudos.

    Cada spy sólo registra su nombre en ``calls`` — no toca el store real
    ni el filesystem. Los tests de excepción sobreescriben un spy puntual
    para que lance en vez de sólo registrar. ``_resolve_root_schematic_or_pcb``
    también se reemplaza: es un argumento posicional evaluado ANTES de llamar
    a ``check_no_external_disk_edit`` (real o patcheado), y sin proyecto
    configurado (no hay ``KICAD_MCP_PROJECT`` en el entorno de test) lanzaría
    ``PROJECT_NOT_FOUND`` antes de llegar al spy — ruido ajeno a lo que este
    archivo ejercita.
    """
    calls: list[str] = []
    monkeypatch.setattr(mutating_mod, "_guard_live_stale", lambda: calls.append("live_guard"))
    monkeypatch.setattr(
        mutating_mod, "_resolve_root_schematic_or_pcb", lambda: Path("/dummy/project")
    )
    monkeypatch.setattr(
        mutating_mod,
        "check_no_external_disk_edit",
        lambda store, schematic: calls.append("disk_check"),
    )
    monkeypatch.setattr(
        mutating_mod, "_check_base_snap", lambda base_snap: calls.append(f"base_snap:{base_snap}")
    )
    return calls


def test_orden_de_guardas_y_cuerpo(_calls: list[str]) -> None:
    """Con todos los flags en default (True), el orden es idéntico al preámbulo
    inline que reemplaza: live-guard → disk-check → base_snap → cuerpo."""

    @mutating_tool("dummy_tool")
    def dummy(base_snap: int | None = None) -> str:
        _calls.append("body")
        return "OK"

    result = dummy(base_snap=7)
    assert result == "OK"
    assert _calls == ["live_guard", "disk_check", "base_snap:7", "body"]


def test_base_snap_none_no_dispara_check(_calls: list[str]) -> None:
    @mutating_tool("dummy_tool")
    def dummy(base_snap: int | None = None) -> str:
        _calls.append("body")
        return "OK"

    dummy()  # base_snap por default es None
    assert _calls == ["live_guard", "disk_check", "body"]


def test_base_snap_posicional_se_detecta(_calls: list[str]) -> None:
    """``base_snap`` no siempre es el único kwarg — el bind_partial debe
    localizarlo por NOMBRE sin asumir posición fija en la firma."""

    @mutating_tool("dummy_tool")
    def dummy(x_mm: float, y_mm: float, base_snap: int | None = None) -> str:
        _calls.append("body")
        return "OK"

    dummy(1.0, 2.0, 9)  # posicional
    assert _calls == ["live_guard", "disk_check", "base_snap:9", "body"]


def test_base_snap_por_keyword_se_detecta(_calls: list[str]) -> None:
    @mutating_tool("dummy_tool")
    def dummy(x_mm: float, base_snap: int | None = None) -> str:
        _calls.append("body")
        return "OK"

    dummy(x_mm=1.0, base_snap=3)
    assert _calls == ["live_guard", "disk_check", "base_snap:3", "body"]


@pytest.mark.parametrize(
    ("flag", "skipped"),
    [
        ("live_guard", "live_guard"),
        ("disk_check", "disk_check"),
    ],
)
def test_flag_false_saltea_su_guarda(_calls: list[str], flag: str, skipped: str) -> None:
    kwargs: dict[str, Any] = {flag: False}

    @mutating_tool("dummy_tool", **kwargs)
    def dummy(base_snap: int | None = None) -> str:
        _calls.append("body")
        return "OK"

    dummy(base_snap=1)
    assert skipped not in _calls
    assert "body" in _calls


def test_base_snap_check_false_saltea_aunque_se_pase_base_snap(_calls: list[str]) -> None:
    @mutating_tool("dummy_tool", base_snap_check=False)
    def dummy(base_snap: int | None = None) -> str:
        _calls.append("body")
        return "OK"

    dummy(base_snap=42)
    assert _calls == ["live_guard", "disk_check", "body"]


def test_excepcion_de_live_guard_propaga_con_mismo_code(
    _calls: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise() -> None:
        raise KicadMcpError(
            code=ErrorCode.EXTERNAL_EDIT_DETECTED, message="disco adelante", hint="recargá"
        )

    monkeypatch.setattr(mutating_mod, "_guard_live_stale", _raise)

    @mutating_tool("dummy_tool")
    def dummy(base_snap: int | None = None) -> str:
        _calls.append("body")
        return "OK"

    with pytest.raises(KicadMcpError) as exc_info:
        dummy()
    assert exc_info.value.code is ErrorCode.EXTERNAL_EDIT_DETECTED
    # El cuerpo NUNCA corre si una guarda lanza — mismo comportamiento que
    # el preámbulo inline (la excepción cortaba antes de abrir el `with`).
    assert "body" not in _calls
    assert "disk_check" not in _calls


def test_excepcion_de_disk_check_propaga_con_mismo_code(
    _calls: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(store: Any, schematic: Any) -> None:
        raise KicadMcpError(
            code=ErrorCode.EXTERNAL_EDIT_DETECTED, message="edición externa", hint="reintentá"
        )

    monkeypatch.setattr(mutating_mod, "check_no_external_disk_edit", _raise)

    @mutating_tool("dummy_tool")
    def dummy(base_snap: int | None = None) -> str:
        _calls.append("body")
        return "OK"

    with pytest.raises(KicadMcpError) as exc_info:
        dummy()
    assert exc_info.value.code is ErrorCode.EXTERNAL_EDIT_DETECTED
    assert _calls == ["live_guard"]  # corrió el live-guard, no el cuerpo


def test_excepcion_de_base_snap_propaga_con_mismo_code(
    _calls: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(base_snap: int) -> None:
        raise KicadMcpError(
            code=ErrorCode.SNAPSHOT_STALE, message="snap vencido", hint="releé el contexto"
        )

    monkeypatch.setattr(mutating_mod, "_check_base_snap", _raise)

    @mutating_tool("dummy_tool")
    def dummy(base_snap: int | None = None) -> str:
        _calls.append("body")
        return "OK"

    with pytest.raises(KicadMcpError) as exc_info:
        dummy(base_snap=1)
    assert exc_info.value.code is ErrorCode.SNAPSHOT_STALE
    assert _calls == ["live_guard", "disk_check"]


def test_wraps_preserva_metadata_y_firma(_calls: list[str]) -> None:
    @mutating_tool("dummy_tool")
    def dummy(x_mm: float, base_snap: int | None = None) -> str:
        """Docstring original."""
        _calls.append("body")
        return "OK"

    assert dummy.__name__ == "dummy"
    assert dummy.__doc__ == "Docstring original."
    sig = inspect.signature(dummy)
    assert list(sig.parameters) == ["x_mm", "base_snap"]


def test_marca_mutating_tool_presente_con_el_nombre_pasado(_calls: list[str]) -> None:
    @mutating_tool("mi_tool_de_prueba")
    def dummy(base_snap: int | None = None) -> str:
        return "OK"

    assert dummy.__mutating_tool__ == "mi_tool_de_prueba"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 2. Canario de registro — las 12 tools reales de pcb.py llevan la marca.
# ---------------------------------------------------------------------------

# Superficie decidida en sesión 39 (ver ADR-0014 y docstring de _mutating.py):
# las 11 tools W-IPC de PCB "Familia A" + set_footprint_ref, MENOS
# delete_tracks_bulk (preámbulo post early-return de dry_run) y la Familia B
# (route_board, reload_board_from_disk).
_DECORATED_TOOLS = frozenset(
    {
        "move_footprint",
        "set_footprint_ref",
        "add_track",
        "add_via",
        "save_board",
        "delete_track",
        "delete_via",
        "draw_board_outline",
        "add_zone",
        "add_keepout_zone",
        "fill_zones",
        "delete_zone",
    }
)

# Tools mutantes de pcb.py deliberadamente EXCLUIDAS del decorador (ver
# docstring de _mutating.py) — el canario también las verifica para dejar
# la exclusión explícita, no accidental.
_EXCLUDED_MUTATING_TOOLS = frozenset(
    {"delete_tracks_bulk", "route_board", "reload_board_from_disk"}
)


class _UnusedBridge:
    """Standin para ``ipc_bridge``: el registro de tools no invoca ningún
    método del bridge (sólo define closures) — el canario nunca llama una
    tool, sólo inspecciona el callable registrado."""


def test_tools_decoradas_llevan_la_marca_mutating_tool() -> None:
    mcp = FastMCP(name="test-dt2-canary", instructions="test")
    register_pcb(mcp, ipc_bridge=_UnusedBridge())  # type: ignore[arg-type]

    for name in sorted(_DECORATED_TOOLS):
        tool = mcp._tool_manager.get_tool(name)
        assert tool is not None, f"tool {name!r} no está registrada"
        marker = getattr(tool.fn, "__mutating_tool__", None)
        assert marker == name, (
            f"{name!r} no lleva @mutating_tool (o el nombre pasado no coincide) — "
            "una mutante nueva sin decorador debe fallar acá, no en silencio"
        )


def test_tools_excluidas_no_llevan_la_marca() -> None:
    """Documenta la exclusión: si alguna de estas empieza a llevar la marca
    sin que el ADR-0014 se haya actualizado, es una señal de scope creep."""
    mcp = FastMCP(name="test-dt2-canary-exclusions", instructions="test")
    register_pcb(mcp, ipc_bridge=_UnusedBridge())  # type: ignore[arg-type]

    for name in sorted(_EXCLUDED_MUTATING_TOOLS):
        tool = mcp._tool_manager.get_tool(name)
        assert tool is not None, f"tool {name!r} no está registrada"
        marker = getattr(tool.fn, "__mutating_tool__", None)
        assert marker is None, (
            f"{name!r} ahora lleva @mutating_tool — actualizá ADR-0014 y "
            "este test si la exclusión dejó de aplicar"
        )
