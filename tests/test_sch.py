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
import re
import shutil
import subprocess
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


def _prop_in(sheet_path: Path, ref: str, prop_name: str) -> str:
    """Valor de una propiedad de un símbolo (por ref) leído de disco."""
    from skip import Schematic

    sch = Schematic(str(sheet_path))
    for sym in sch.symbol:
        if str(sym.Reference.value) == ref:
            for prop in sym.property:
                if str(prop.name) == prop_name:
                    return str(prop.value)
    raise AssertionError(f"prop {prop_name} de {ref} no hallada en {sheet_path.name}")


def _strip_global_labels(sheet_path: Path) -> None:
    """Borra todos los global_labels de la hoja (deja pines flotantes).

    Necesario para el golden de ``connect_pins``: 001_basico ancla casi
    todos los pines a global labels; sin quitarlos, el net resultante
    heredaría el nombre global (prioridad) en vez del pedido.
    """
    from skip import Schematic

    sch = Schematic(str(sheet_path))
    for gl in list(sch.global_label):
        gl.delete()
    sch.write(str(sheet_path))


def _make_palette_project(tmp_path: Path) -> Path:
    """Proyecto con un root de diseño + ``paleta.kicad_sch`` separada (D-12.3).

    El ``.kicad_pro`` desambigua el root cuando coexisten dos ``.kicad_sch``.
    Ambos parten del fixture 001 (tiene los templates FIXLIB:*).
    """
    src = Path(__file__).parent / "fixtures" / "001_basico" / "fixture.kicad_sch"
    proj = tmp_path / "pal_proj"
    proj.mkdir()
    shutil.copy(src, proj / "design.kicad_sch")
    (proj / "design.kicad_pro").write_text("{}")
    shutil.copy(src, proj / "paleta.kicad_sch")
    return proj


def _netlist_comps(sheet_path: Path, tmp_path: Path) -> list[str]:
    """Exporta netlist (kicadxml) y devuelve la lista de refs de componentes."""
    out = tmp_path / "comps.net"
    r = subprocess.run(
        [
            "kicad-cli",
            "sch",
            "export",
            "netlist",
            "--format",
            "kicadxml",
            "-o",
            str(out),
            str(sheet_path),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    return re.findall(r'<comp ref="([^"]+)">', out.read_text())


def _netlist_nodes_by_net(sheet_path: Path, tmp_path: Path) -> dict[str, list[tuple[str, str]]]:
    """Exporta netlist (kicadxml) y devuelve ``{net_name: [(ref, pin), ...]}``."""
    out = tmp_path / "verify.net"
    r = subprocess.run(
        [
            "kicad-cli",
            "sch",
            "export",
            "netlist",
            "--format",
            "kicadxml",
            "-o",
            str(out),
            str(sheet_path),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    text = out.read_text()
    result: dict[str, list[tuple[str, str]]] = {}
    for netm in re.finditer(r'<net code="[^"]*" name="([^"]*)"[^>]*>(.*?)</net>', text, re.S):
        name = netm.group(1)
        nodes = re.findall(r'<node ref="([^"]+)" pin="([^"]+)"', netm.group(2))
        result[name] = nodes
    return result


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


# --- set_value / set_footprint (D-12.1) --------------------------------------


@pytest.mark.unit
async def test_set_value_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """set_value R1 -> 22k: efecto verificado en disco + confirm ≤50 + snap + audit."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("set_value", {"ref": "R1", "value": "22k"})
    assert not result.isError, _text(result)
    confirm = _text(result)
    assert estimate_tokens(confirm) <= 50, f"confirm largo: {confirm!r}"
    assert confirm.startswith("OK set_value R1")
    assert "[snap:" in confirm
    # Efecto real en disco (D-06.3).
    assert _prop_in(project / "fixture.kicad_sch", "R1", "Value") == "22k"

    audit_file = project / ".kicad-mcp" / "audit.jsonl"
    entries = [json.loads(line) for line in audit_file.read_text().splitlines()]
    accepted = [e for e in entries if e["tool"] == "set_value" and "result" in e]
    assert len(accepted) == 1
    assert accepted[0]["result"]["snap"] >= 1
    assert accepted[0]["result"]["old"] == "10k"


@pytest.mark.unit
async def test_set_value_disk_snapshot_has_mtimes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-08.5 #4: el snapshot post-write es de disco (mtimes no None)."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("set_value", {"ref": "C1", "value": "220nF"})
    assert not result.isError, _text(result)

    import re

    from kicad_mcp.snapshots import get_default_store

    snap_id = int(re.search(r"\[snap:(\d+)\]", _text(result)).group(1))  # type: ignore[union-attr]
    entry = get_default_store().get(snap_id)
    assert entry is not None
    assert entry.mtimes is not None
    # El value derivado quedó reflejado en el estado normalizado.
    c1 = next(c for c in entry.state.components if c.ref == "C1")
    assert c1.value == "220nF"


@pytest.mark.unit
async def test_set_value_rejects_missing_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ref inexistente → COMPONENT_NOT_FOUND con similares."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("set_value", {"ref": "R9", "value": "1k"})
    assert result.isError
    text = _text(result)
    assert "COMPONENT_NOT_FOUND" in text
    # No debe haberse creado backup (validación previa a G1).
    assert not (project / ".kicad-mcp" / "backups").exists()


@pytest.mark.unit
async def test_set_value_rejects_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Value vacío → INVALID_PARAMS."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("set_value", {"ref": "R1", "value": "   "})
    assert result.isError
    assert "INVALID_PARAMS" in _text(result)


@pytest.mark.unit
async def test_set_value_rejects_control_chars(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regla 6: value con salto de línea → INVALID_PARAMS antes de tocar disco."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("set_value", {"ref": "R1", "value": "10k\ninject"})
    assert result.isError
    assert "INVALID_PARAMS" in _text(result)
    # R1 sigue en 10k (no se tocó disco).
    assert _prop_in(project / "fixture.kicad_sch", "R1", "Value") == "10k"


@pytest.mark.unit
async def test_set_footprint_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """set_footprint R1 -> lib:name: efecto verificado en disco + confirm ≤50."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    fp = "Resistor_SMD:R_0805_2012Metric"
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("set_footprint", {"ref": "R1", "footprint_id": fp})
    assert not result.isError, _text(result)
    confirm = _text(result)
    assert estimate_tokens(confirm) <= 50, f"confirm largo: {confirm!r}"
    assert confirm.startswith("OK set_footprint R1")
    assert _prop_in(project / "fixture.kicad_sch", "R1", "Footprint") == fp


@pytest.mark.unit
async def test_set_footprint_rejects_bad_format(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """footprint_id sin ':' → INVALID_PARAMS (formato lib:name)."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("set_footprint", {"ref": "R1", "footprint_id": "R_0805"})
    assert result.isError
    text = _text(result)
    assert "INVALID_PARAMS" in text
    assert "lib:name" in text
    # No se tocó disco (Footprint sigue vacío).
    assert _prop_in(project / "fixture.kicad_sch", "R1", "Footprint") == ""


@pytest.mark.unit
async def test_set_footprint_rejects_missing_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ref inexistente → COMPONENT_NOT_FOUND."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("set_footprint", {"ref": "ZZ9", "footprint_id": "Lib:Foot"})
    assert result.isError
    assert "COMPONENT_NOT_FOUND" in _text(result)


# --- connect_pins (D-12.2) ---------------------------------------------------


@pytest.mark.unit
async def test_connect_pins_golden_netlist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """GOLDEN (D-12.2): dos pines → connect_pins → netlist → misma net con el nombre pedido."""
    project = _copy_fixture("001_basico", tmp_path)
    sheet = project / "fixture.kicad_sch"
    _strip_global_labels(sheet)  # deja R1.2 y R2.2 flotantes
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "connect_pins",
            {"pin_a": "R1.2", "pin_b": "R2.2", "net_name": "I2C_SDA"},
        )
    assert not result.isError, _text(result)
    confirm = _text(result)
    assert estimate_tokens(confirm) <= 50, f"confirm largo: {confirm!r}"
    assert confirm.startswith("OK connect_pins R1.2<->R2.2 net=I2C_SDA")

    # Prueba de oro: el netlist netea ambos pines en la net con el nombre pedido.
    nets = _netlist_nodes_by_net(sheet, tmp_path)
    # Los labels locales llevan prefijo de sheet-path ('/').
    match = [n for n, nodes in nets.items() if n.endswith("I2C_SDA")]
    assert match, f"net I2C_SDA ausente; nets: {list(nets)}"
    nodes = nets[match[0]]
    assert ("R1", "2") in nodes and ("R2", "2") in nodes, nodes


@pytest.mark.unit
async def test_connect_pins_snapshot_and_audit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """El snapshot de disco lleva mtimes y refleja el net derivado; audit registrado."""
    project = _copy_fixture("001_basico", tmp_path)
    _strip_global_labels(project / "fixture.kicad_sch")
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "connect_pins",
            {"pin_a": "R1.2", "pin_b": "R2.2", "net_name": "I2C_SDA"},
        )
    assert not result.isError, _text(result)

    from kicad_mcp.snapshots import get_default_store

    snap_id = int(re.search(r"\[snap:(\d+)\]", _text(result)).group(1))  # type: ignore[union-attr]
    entry = get_default_store().get(snap_id)
    assert entry is not None
    assert entry.mtimes is not None
    r1 = next(c for c in entry.state.components if c.ref == "R1")
    assert any(p.net == "I2C_SDA" for p in r1.pins), r1.pins

    audit_file = project / ".kicad-mcp" / "audit.jsonl"
    entries = [json.loads(line) for line in audit_file.read_text().splitlines()]
    accepted = [e for e in entries if e["tool"] == "connect_pins" and "result" in e]
    assert len(accepted) == 1
    assert accepted[0]["result"]["labels"] >= 2


@pytest.mark.unit
async def test_connect_pins_rejects_missing_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ref inexistente → COMPONENT_NOT_FOUND, sin backup."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "connect_pins", {"pin_a": "R1.2", "pin_b": "R9.1", "net_name": "N1"}
        )
    assert result.isError
    assert "COMPONENT_NOT_FOUND" in _text(result)
    assert not (project / ".kicad-mcp" / "backups").exists()


@pytest.mark.unit
async def test_connect_pins_rejects_same_pin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """El mismo pin dos veces → INVALID_PARAMS."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "connect_pins", {"pin_a": "R1.2", "pin_b": "R1.2", "net_name": "N1"}
        )
    assert result.isError
    assert "INVALID_PARAMS" in _text(result)


@pytest.mark.unit
async def test_connect_pins_rejects_empty_net(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """net_name vacío → INVALID_PARAMS."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "connect_pins", {"pin_a": "R1.2", "pin_b": "R2.2", "net_name": "  "}
        )
    assert result.isError
    assert "INVALID_PARAMS" in _text(result)


@pytest.mark.unit
async def test_connect_pins_rejects_missing_pin_number(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Número de pin inexistente en el símbolo → INVALID_PARAMS con pines disponibles."""
    project = _copy_fixture("001_basico", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "connect_pins", {"pin_a": "R1.9", "pin_b": "R2.2", "net_name": "N1"}
        )
    assert result.isError
    text = _text(result)
    assert "INVALID_PARAMS" in text
    assert "Pines de R1" in text


@pytest.mark.unit
async def test_connect_pins_rejects_cross_sheet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """004 multi-hoja: refs en hojas distintas → INVALID_PARAMS (labels locales)."""
    project = _copy_fixture("004_real", tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    # U11 vive en bus_pci; U20 en modul (hojas distintas).
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "connect_pins", {"pin_a": "U11.1", "pin_b": "U20.1", "net_name": "X"}
        )
    assert result.isError
    text = _text(result)
    assert "INVALID_PARAMS" in text
    assert "hojas distintas" in text


# --- add_symbol cross-file desde paleta (D-12.3) -----------------------------


@pytest.mark.unit
async def test_add_symbol_cross_file_from_explicit_palette(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """source=paleta.kicad_sch clona cross-file; el netlist reconoce el símbolo."""
    project = _make_palette_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_symbol",
            {
                "sheet": "design.kicad_sch",
                "lib_id": "FIXLIB:R2",
                "ref": "R50",
                "x_mm": 175.0,
                "y_mm": 60.0,
                "source": "paleta.kicad_sch",
            },
        )
    assert not result.isError, _text(result)
    confirm = _text(result)
    assert estimate_tokens(confirm) <= 50
    assert confirm.startswith("OK add_symbol R50 FIXLIB:R2")
    # Efecto en disco + netlist (la prueba de que el clon cross-file es válido).
    assert "R50" in _refs_in(project / "design.kicad_sch")
    assert "R50" in _netlist_comps(project / "design.kicad_sch", tmp_path)


@pytest.mark.unit
async def test_add_symbol_default_palette_lookup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sin source: si existe paleta.kicad_sch en la raíz, se usa por default (D-12.3)."""
    project = _make_palette_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_symbol",
            {
                "sheet": "design.kicad_sch",
                "lib_id": "FIXLIB:C2",
                "ref": "C50",
                "x_mm": 175.0,
                "y_mm": 60.0,
            },
        )
    assert not result.isError, _text(result)
    assert "C50" in _refs_in(project / "design.kicad_sch")
    assert "C50" in _netlist_comps(project / "design.kicad_sch", tmp_path)


@pytest.mark.unit
async def test_add_symbol_source_missing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """source apuntando a un archivo inexistente → PROJECT_NOT_FOUND."""
    project = _make_palette_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_symbol",
            {
                "sheet": "design.kicad_sch",
                "lib_id": "FIXLIB:R2",
                "ref": "R51",
                "x_mm": 175.0,
                "y_mm": 60.0,
                "source": "noexiste.kicad_sch",
            },
        )
    assert result.isError
    assert "PROJECT_NOT_FOUND" in _text(result)


@pytest.mark.unit
async def test_add_symbol_cross_file_lib_id_not_in_palette(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """lib_id ausente en la paleta → INVALID_PARAMS con los lib_ids disponibles."""
    project = _make_palette_project(tmp_path)
    monkeypatch.setenv("KICAD_MCP_PROJECT", str(project))
    mcp = _make_server()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "add_symbol",
            {
                "sheet": "design.kicad_sch",
                "lib_id": "Device:LED",
                "ref": "D50",
                "x_mm": 175.0,
                "y_mm": 60.0,
                "source": "paleta.kicad_sch",
            },
        )
    assert result.isError
    text = _text(result)
    assert "INVALID_PARAMS" in text
    assert "FIXLIB:" in text
