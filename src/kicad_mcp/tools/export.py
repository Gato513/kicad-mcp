"""Tools de la categoría ``export``.

Ver `docs/specs/tool-catalog.md §export`. Sesión 03: ``export_bom``,
``export_netlist``, ``export_render``, ``export_manufacturing`` (nueva,
detrás del gate G3 — DRC clean).

Toda ruta de salida pasa por ``canonicalize_within_project_root`` (regla #4).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from ..errors import ErrorCode, KicadMcpError
from ..gates.g3 import check_drc_clean
from ..logging_config import estimate_tokens, log_tool_call, tool_call_timer
from ..paths import canonicalize_within_project_root
from ..tools.world import _resolve_root_schematic

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_TIMEOUT_S: Final = 120.0
_RENDER_KINDS: Final = frozenset({"sch_pdf", "pcb_png", "pcb_pdf"})


def _project_root() -> Path:
    """Raíz del proyecto activo (para canonicalización de rutas de salida)."""
    sch = _resolve_root_schematic()
    return sch.parent


def _run_cli(args: list[str], *, action: str) -> None:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_MISSING,
            message="kicad-cli no está en PATH.",
            hint="Instala KiCad ≥ 9.0 o exporta PATH con kicad-cli.",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message=f"kicad-cli {action} excedió {_TIMEOUT_S:.0f}s.",
            hint="Reintentar o reducir alcance del proyecto.",
        ) from exc
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()[:200]
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message=f"kicad-cli {action} falló.",
            hint=stderr or f"returncode={completed.returncode}",
        )


def _resolve_output(candidate: str | None, default: str) -> Path:
    """Canonicaliza la ruta de salida contra la raíz del proyecto."""
    root = _project_root()
    path = candidate if candidate else default
    return canonicalize_within_project_root(path, root)


def register(mcp: FastMCP) -> None:
    """Registra las tools ``export`` del MVP en la instancia FastMCP."""

    @mcp.tool(name="export_bom", description="BOM en CSV")
    def export_bom(output_path: str | None = None) -> dict[str, Any]:
        with tool_call_timer() as timer:
            sch = _resolve_root_schematic()
            out = _resolve_output(output_path, "bom.csv")
            out.parent.mkdir(parents=True, exist_ok=True)
            _run_cli(
                [
                    "kicad-cli",
                    "sch",
                    "export",
                    "bom",
                    "-o",
                    str(out),
                    str(sch),
                ],
                action="BOM",
            )
            payload = {"output_path": out.name, "bytes": out.stat().st_size}
        log_tool_call(
            tool_name="export_bom",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
        )
        return payload

    @mcp.tool(name="export_netlist", description="Netlist del esquemático")
    def export_netlist(output_path: str | None = None) -> dict[str, Any]:
        with tool_call_timer() as timer:
            sch = _resolve_root_schematic()
            out = _resolve_output(output_path, "netlist.net")
            out.parent.mkdir(parents=True, exist_ok=True)
            _run_cli(
                [
                    "kicad-cli",
                    "sch",
                    "export",
                    "netlist",
                    "-o",
                    str(out),
                    str(sch),
                ],
                action="netlist",
            )
            payload = {"output_path": out.name, "bytes": out.stat().st_size}
        log_tool_call(
            tool_name="export_netlist",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
        )
        return payload

    @mcp.tool(
        name="export_render",
        description="PDF del esquemático (sch_pdf) o PDF del PCB (pcb_pdf)",
    )
    def export_render(kind: str, output_path: str | None = None) -> dict[str, Any]:
        if kind not in _RENDER_KINDS:
            raise KicadMcpError(
                code=ErrorCode.INVALID_PARAMS,
                message=f"``kind`` inválido: {kind!r}",
                hint=f"Valores válidos: {sorted(_RENDER_KINDS)}",
            )
        if kind == "pcb_png":
            raise KicadMcpError(
                code=ErrorCode.INVALID_PARAMS,
                message="pcb_png no está soportado por kicad-cli 10.",
                hint="Usar pcb_pdf (single-mode); PNG llegará cuando kicad-cli lo exponga.",
            )
        with tool_call_timer() as timer:
            sch = _resolve_root_schematic()
            if kind == "sch_pdf":
                out = _resolve_output(output_path, "schematic.pdf")
                out.parent.mkdir(parents=True, exist_ok=True)
                _run_cli(
                    ["kicad-cli", "sch", "export", "pdf", "-o", str(out), str(sch)],
                    action="sch PDF",
                )
            else:  # pcb_pdf
                pcb = sch.with_suffix(".kicad_pcb")
                if not pcb.is_file():
                    raise KicadMcpError(
                        code=ErrorCode.PROJECT_NOT_FOUND,
                        message="No se encontró el .kicad_pcb del proyecto activo.",
                        hint=f"Se buscaba {pcb.name} junto al esquemático.",
                    )
                out = _resolve_output(output_path, "pcb.pdf")
                out.parent.mkdir(parents=True, exist_ok=True)
                _run_cli(
                    [
                        "kicad-cli",
                        "pcb",
                        "export",
                        "pdf",
                        "--mode-single",
                        "-l",
                        "F.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts",
                        "-o",
                        str(out),
                        str(pcb),
                    ],
                    action="pcb PDF",
                )
            payload = {"kind": kind, "output_path": out.name, "bytes": out.stat().st_size}
        log_tool_call(
            tool_name="export_render",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
            extra={"kind": kind},
        )
        return payload

    @mcp.tool(
        name="export_manufacturing",
        description="Gerbers + drill (Gate G3: bloquea si DRC tiene errores)",
    )
    def export_manufacturing(output_dir: str | None = None) -> dict[str, Any]:
        with tool_call_timer() as timer:
            sch = _resolve_root_schematic()
            pcb = sch.with_suffix(".kicad_pcb")
            if not pcb.is_file():
                raise KicadMcpError(
                    code=ErrorCode.PROJECT_NOT_FOUND,
                    message="No se encontró el .kicad_pcb del proyecto activo.",
                    hint=f"Se buscaba {pcb.name} junto al esquemático.",
                )
            check_drc_clean(pcb)  # Gate G3: EXPORT_BLOCKED_BY_DRC si sucio.
            fab_dir = _resolve_output(output_dir, "fab")
            fab_dir.mkdir(parents=True, exist_ok=True)
            _run_cli(
                ["kicad-cli", "pcb", "export", "gerbers", "-o", str(fab_dir), str(pcb)],
                action="gerbers",
            )
            _run_cli(
                ["kicad-cli", "pcb", "export", "drill", "-o", str(fab_dir), str(pcb)],
                action="drill",
            )
            files = sorted(p.name for p in fab_dir.iterdir() if p.is_file())
            payload = {"output_dir": fab_dir.name, "files": files, "count": len(files)}
        log_tool_call(
            tool_name="export_manufacturing",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(json.dumps(payload, ensure_ascii=False)),
            extra={"files_count": len(files)},
        )
        return payload
