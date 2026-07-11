"""Tests unit de ``tools.sch`` (add_symbol) — sesión 08 T4.

Estrategia: se copia el fixture 001_basico (o 004_real) a ``tmp_path``
(regla 7 — nunca mutar el fixture original) y se ejecuta ``add_symbol``
vía cliente MCP en proceso. Se verifica:

- Sanitización de ``ref`` (regla 6): refs con caracteres inválidos → INVALID_PARAMS.
- Colisión de ``ref`` en la MISMA hoja o en OTRA hoja → INVALID_PARAMS.
- ``lib_id`` no instanciado en la hoja → INVALID_PARAMS con hint del catálogo.
- Coordenadas fuera del área de la hoja → INVALID_PARAMS.
- Éxito con verificación de efecto: el archivo escrito contiene el
  símbolo nuevo con la posición pedida (D-06.3).
- Snapshot post-write registrado con mtimes frescos (D-06.2 / D-08.5 #4).
- G1 backup disparado.
- Confirm ≤ 50 tokens (ADR-0004).

El archivo mutado queda en ``tmp_path``; no toca el repo. Nada de KiCad
IPC — la superficie es 100 % ``.kicad_sch`` sobre disco (D-08.5 #3).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.gates import g1
from kicad_mcp.logging_config import estimate_tokens
from kicad_mcp.tools.sch import register as register_sch


def _copy_fixture(name: str, tmp_path: Path) -> Path:
    """Copia recursiva de ``tests/fixtures/<name>`` a ``tmp_path/proj``.

    Regla 7: los fixtures no se mutan. Todos los tests que muten disco
    (add_symbol es el único hoy) reciben una copia fresca.
    """
    src = Path(__file__).parent / "fixtures" / name
    dst = tmp_path / "proj"
    shutil.copytree(src, dst)
    return dst


def _make_server() -> FastMCP:
    mcp = FastMCP(name="test-sch", instructions="test")
    register_sch(mcp)
    return mcp


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


@pytest.fixture(autouse=True)
def _reset_g1() -> Any:
    g1.reset_session_state()
    yield
    g1.reset_session_state()


def _refs_in(sheet_path: Path) -> list[str]:
    """Lista de refs presentes en un ``.kicad_sch`` según kicad-skip."""
    from skip import Schematic

    sch = Schematic(str(sheet_path))
    return [str(sym.Reference.value) for sym in sch.symbol]


# --- éxito -------------------------------------------------------------------


@pytest.mark.unit
async def test_add_symbol_happy_path_on_001_basico(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """001_basico + clone de FIXLIB:R2 con ref R99 → sale con snap>0 y efecto verificado."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    # 001_basico usa "fixture.kicad_sch" como raíz — resuelve el .kicad_sch
    # único del proyecto (no hay .kicad_pro).
    sheet_name = "fixture.kicad_sch"
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_symbol",
            {
                "sheet": sheet_name,
                "lib_id": "FIXLIB:R2",
                "ref": "R99",
                "x_mm": 175.0,
                "y_mm": 60.0,
            },
        )
    assert not result.isError, _text(result)
    confirm = _text(result)
    # ADR-0004 / D-08.5: confirm ≤ 50 tokens.
    assert estimate_tokens(confirm) <= 50, f"confirm demasiado largo: {confirm!r}"
    assert confirm.startswith("OK add_symbol R99 FIXLIB:R2")
    assert "[snap:" in confirm

    # Efecto verificado sobre el archivo escrito.
    live_refs = _refs_in(project / sheet_name)
    assert "R99" in live_refs, f"R99 debe estar en el sch tras write; refs: {live_refs}"
    # Backup G1 creado.
    backup_dir = project / ".kicad-mcp" / "backups"
    assert backup_dir.is_dir()

    # Audit escribió la mutación con snap positivo.
    audit_file = project / ".kicad-mcp" / "audit.jsonl"
    entries = [json.loads(line) for line in audit_file.read_text().splitlines()]
    accepted = [e for e in entries if e["tool"] == "add_symbol" and "result" in e]
    assert len(accepted) == 1
    assert accepted[0]["result"]["snap"] >= 1


@pytest.mark.unit
async def test_add_symbol_registers_disk_snapshot_with_fresh_mtimes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-06.2 / D-08.5 #4: el snapshot post-write NO es vivo — tiene mtimes.

    Anti-regresión: si se registra ``mtimes=None`` (patrón vivo), el
    próximo delta contra este base saltearía el chequeo de edición
    externa. Para mutaciones de disco (kicad-skip), el snapshot debe
    portar los mtimes reales de los archivos del proyecto.
    """
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_symbol",
            {
                "sheet": "fixture.kicad_sch",
                "lib_id": "FIXLIB:C2",
                "ref": "C42",
                "x_mm": 110.0,
                "y_mm": 60.0,
            },
        )
    assert not result.isError, _text(result)

    import re

    from kicad_mcp.snapshots import get_default_store

    snap_id = int(re.search(r"\[snap:(\d+)\]", _text(result)).group(1))  # type: ignore[union-attr]
    entry = get_default_store().get(snap_id)
    assert entry is not None
    assert entry.mtimes is not None, "snapshot de disco DEBE portar mtimes (D-08.5 #4)"
    assert entry.state.kind == "sch"


# --- validaciones ------------------------------------------------------------


@pytest.mark.unit
async def test_add_symbol_rejects_colliding_ref_in_same_sheet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ref ya presente en la MISMA hoja → INVALID_PARAMS + audit."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_symbol",
            {
                "sheet": "fixture.kicad_sch",
                "lib_id": "FIXLIB:R2",
                "ref": "R1",  # ya existe
                "x_mm": 170.0,
                "y_mm": 60.0,
            },
        )
    assert result.isError
    text = _text(result)
    assert "INVALID_PARAMS" in text
    assert "R1" in text and "ya existe" in text


@pytest.mark.unit
async def test_add_symbol_rejects_ref_colliding_across_sheets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """004_real es multi-hoja: una ref ya usada en cualquier hoja bloquea.

    D-08.5: la validación de colisión NO es por hoja, es por proyecto —
    la re-anotación de KiCad exige unicidad global.
    """
    project = _copy_fixture("004_real", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    # U1 vive en muxdata.kicad_sch (por ejemplo); intentamos ponerlo en
    # rams.kicad_sch — colisión aunque no sea la misma hoja.
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_symbol",
            {
                "sheet": "rams.kicad_sch",
                "lib_id": "Device:C",  # no existe en rams; validaremos que primero pega la colisión
                "ref": "U1",  # ref del board de prueba (docs/componentes-pcb.md)
                "x_mm": 300.0,
                "y_mm": 200.0,
            },
        )
    # La sanitización de ref pasa; la colisión global se detecta antes del lib_id lookup.
    assert result.isError
    text = _text(result)
    assert "INVALID_PARAMS" in text
    assert "ya existe" in text


@pytest.mark.unit
async def test_add_symbol_rejects_missing_lib_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """lib_id no instanciado en la hoja → INVALID_PARAMS con hint de disponibles."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_symbol",
            {
                "sheet": "fixture.kicad_sch",
                "lib_id": "Device:LED",  # no está en la hoja
                "ref": "D42",
                "x_mm": 175.0,
                "y_mm": 60.0,
            },
        )
    assert result.isError
    text = _text(result)
    assert "INVALID_PARAMS" in text
    assert "Device:LED" in text
    # Hint lista al menos uno de los lib_ids disponibles.
    assert "FIXLIB:" in text


@pytest.mark.unit
async def test_add_symbol_rejects_out_of_area(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Coordenadas absurdas → INVALID_PARAMS con rango permitido en el hint."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_symbol",
            {
                "sheet": "fixture.kicad_sch",
                "lib_id": "FIXLIB:R2",
                "ref": "R55",
                "x_mm": 999999.0,
                "y_mm": 999999.0,
            },
        )
    assert result.isError
    text = _text(result)
    assert "INVALID_PARAMS" in text
    assert "fuera del área" in text


@pytest.mark.unit
async def test_add_symbol_rejects_unsanitized_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regla 6: refs con chars inválidos rechazadas antes de tocar disco."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_symbol",
            {
                "sheet": "fixture.kicad_sch",
                "lib_id": "FIXLIB:R2",
                "ref": "R;drop-table",  # inyección
                "x_mm": 175.0,
                "y_mm": 60.0,
            },
        )
    assert result.isError
    text = _text(result)
    assert "INVALID_PARAMS" in text


@pytest.mark.unit
async def test_add_symbol_rejects_path_outside_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regla 4: el sheet no puede escapar del project root."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_symbol",
            {
                "sheet": "../evil.kicad_sch",
                "lib_id": "FIXLIB:R2",
                "ref": "R55",
                "x_mm": 175.0,
                "y_mm": 60.0,
            },
        )
    assert result.isError
    text = _text(result)
    assert "PATH_OUTSIDE_PROJECT" in text
