"""Tests de las tools de export.

- ``unit``: ``PATH_OUTSIDE_PROJECT``, ``INVALID_PARAMS`` y Gate G3 con DRC
  mockeado (caso limpio y sucio de ``export_manufacturing``).
- ``integration``: exporta contra fixture 001; verifica que el archivo se
  crea dentro de la raíz del proyecto. ``export_manufacturing`` contra
  004_real: debe responder ``EXPORT_BLOCKED_BY_DRC`` (violaciones reales).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from kicad_mcp.bridge.rules import RulesReport, Violation
from kicad_mcp.errors import ErrorCode, KicadMcpError
from kicad_mcp.server import create_server
from tests.conftest import mirror_fixture

FIXTURES = Path(__file__).parent / "fixtures"


def _parse(result: CallToolResult) -> dict[str, Any]:
    return json.loads(result.content[0].text) if not result.isError else {"error": result}


def _error_text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


@pytest.mark.unit
async def test_export_render_rejects_invalid_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(FIXTURES / "001_basico"))
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_render", {"kind": "dxf"})
    assert result.isError
    assert "INVALID_PARAMS" in _error_text(result)


@pytest.mark.unit
async def test_export_render_pcb_png_returns_invalid_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(FIXTURES / "001_basico"))
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_render", {"kind": "pcb_png"})
    assert result.isError
    text = _error_text(result)
    assert "INVALID_PARAMS" in text
    assert "pcb_pdf" in text


@pytest.mark.unit
async def test_export_bom_rejects_output_outside_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(FIXTURES / "001_basico"))
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_bom", {"output_path": "/etc/passwd_bom.csv"})
    assert result.isError
    assert "PATH_OUTSIDE_PROJECT" in _error_text(result)


@pytest.mark.integration
async def test_export_bom_writes_csv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_copy = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project_copy))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_bom", {"output_path": "out/bom.csv"})
    payload = _parse(result)
    assert not result.isError, payload
    bom = project_copy / "out" / "bom.csv"
    assert bom.is_file()
    assert bom.stat().st_size > 0
    assert payload["bytes"] == bom.stat().st_size


@pytest.mark.integration
async def test_export_netlist_writes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_copy = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project_copy))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_netlist", {"output_path": "out/net.net"})
    payload = _parse(result)
    assert not result.isError, payload
    assert (project_copy / "out" / "net.net").is_file()
    assert payload["bytes"] > 0


@pytest.mark.integration
async def test_export_render_sch_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_copy = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project_copy))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "export_render", {"kind": "sch_pdf", "output_path": "renders/sch.pdf"}
        )
    payload = _parse(result)
    assert not result.isError, payload
    pdf = project_copy / "renders" / "sch.pdf"
    assert pdf.is_file()
    with pdf.open("rb") as f:
        assert f.read(4) == b"%PDF"


# ---- export_manufacturing (Gate G3) -----------------------------------------


@pytest.mark.unit
async def test_export_manufacturing_blocks_when_drc_dirty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """DRC con severidad ``error`` ⇒ ``EXPORT_BLOCKED_BY_DRC``."""
    # Fixture 001 no tiene .kicad_pcb; creamos uno vacío para pasar el
    # chequeo previo. El gate se dispara antes de tocarlo.
    project = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    pcb_stub = project / "fixture.kicad_pcb"
    pcb_stub.write_text("(kicad_pcb (version 20240108))")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    dirty_report = RulesReport(
        violations=(
            Violation(rule="clearance", severity="error", message="Track too close", items=()),
            Violation(rule="silk", severity="warning", message="Silk clipped", items=()),
        ),
        counts={"error": 1, "warning": 1},
        coordinate_units="mm",
        kicad_version="10.0.4",
    )

    def fake_drc(_: Path) -> RulesReport:
        return dirty_report

    monkeypatch.setattr("kicad_mcp.tools.export.check_drc_clean", lambda pcb: _wrap(fake_drc, pcb))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_manufacturing", {})
    assert result.isError
    text = _error_text(result)
    assert "EXPORT_BLOCKED_BY_DRC" in text
    assert "1 errores DRC" in text
    assert "clearance" in text


def _wrap(runner: Any, pcb: Path) -> None:
    """Aplica ``check_drc_clean`` real usando un runner inyectado (sin tocar kicad-cli)."""
    from kicad_mcp.gates.g3 import check_drc_clean as real_check

    real_check(pcb, drc_runner=runner)


@pytest.mark.unit
async def test_export_manufacturing_runs_when_drc_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """DRC limpio ⇒ ejecuta gerbers + drill y devuelve la lista."""
    project = mirror_fixture(FIXTURES / "001_basico", tmp_path / "001")
    pcb_stub = project / "fixture.kicad_pcb"
    pcb_stub.write_text("(kicad_pcb (version 20240108))")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    # Gate G3 pasa (report limpio).
    monkeypatch.setattr("kicad_mcp.tools.export.check_drc_clean", lambda _pcb: None)

    calls: list[str] = []

    def fake_run_cli(args: list[str], *, action: str) -> None:
        calls.append(action)
        # Simulamos los archivos que kicad-cli hubiera generado.
        out_dir = Path(args[args.index("-o") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        if action == "gerbers":
            for name in ["F_Cu.gbr", "B_Cu.gbr", "Edge_Cuts.gbr"]:
                (out_dir / name).write_bytes(b"G04 test*\n")
        elif action == "drill":
            (out_dir / "drill_PTH.drl").write_bytes(b"M48\n")

    monkeypatch.setattr("kicad_mcp.tools.export._run_cli", fake_run_cli)

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_manufacturing", {})
    payload = _parse(result)
    assert not result.isError, payload
    assert calls == ["gerbers", "drill"]
    assert payload["output_dir"] == "fab"
    assert payload["count"] == 4
    assert "F_Cu.gbr" in payload["files"]
    assert "drill_PTH.drl" in payload["files"]
    assert (project / "fab").is_dir()


@pytest.mark.integration
async def test_export_manufacturing_blocks_on_real_dirty_pcb(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Contra 004_real (copia parcial a tmp): DRC real tiene violaciones ``error``.

    Se copian solo ``video.kicad_sch`` y ``video.kicad_pcb`` (sin ``.kicad_pro``)
    para que kicad-cli aplique las constraints de DRC por defecto. Con el
    ``.kicad_pro`` original, las violaciones de board-edge-clearance quedan
    clasificadas como ``warning`` (setting del proyecto original) y el gate
    no dispara. El proyecto MVP prioriza probar la RUTA del gate contra un
    reporte DRC real; la matriz de configuraciones alternativas (varios
    ``.kicad_pro``, un fixture PCB limpio) queda para v0.3+ (03-reporte.md).
    """
    src = FIXTURES / "004_real"
    if not (src / "video.kicad_pcb").is_file():
        pytest.skip("fixture 004_real no disponible")
    project = tmp_path / "004-drc-defaults"
    project.mkdir()
    for name in ("video.kicad_sch", "video.kicad_pcb"):
        (project / name).write_bytes((src / name).read_bytes())
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))

    mcp = create_server()
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_manufacturing", {})
    assert result.isError, "el gate debe bloquear con DRC por defecto"
    text = _error_text(result)
    assert "EXPORT_BLOCKED_BY_DRC" in text
    assert "errores DRC" in text
    # No debe haber creado la carpeta fab/ (el gate se dispara antes).
    assert not (project / "fab").is_dir()
    # Consumo defensivo del código (evita "no usado" del import).
    assert ErrorCode.EXPORT_BLOCKED_BY_DRC.value in text
    _ = KicadMcpError  # symbol referenciado por type-check
