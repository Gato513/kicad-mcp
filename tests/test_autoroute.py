"""Tests unit del runner de autorouting (T1, D-14.4).

Estrategia: se inyecta un ``SubprocessRunner`` fake que enruta por los args
(python del sistema vs java) y simula éxito, cada fallo tipado de D-14.4, y el
timeout. No toca pcbnew, ni java, ni el socket IPC.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kicad_mcp.bridge import autoroute
from kicad_mcp.errors import ErrorCode, KicadMcpError


def _completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class _FakeRunner:
    """Runner enrutado por args. Cada fase puede forzar un resultado/excepción.

    - fase python (``-c``) se distingue por ``args[1] == "-c"``; el 3er arg
      (script) desambigua export (contiene ``ExportSpecctraDSN``) de import
      (contiene ``ImportSpecctraSES``).
    - fase java se distingue por ``args[0] == "java"`` (o el exe pasado).
    - ``ses_path`` se materializa (archivo no vacío) en la fase java salvo que
      ``produce_ses=False`` — así ``_run_freerouting`` ve el SES real.
    """

    def __init__(
        self,
        *,
        export: object = "ok",
        java: object = "ok",
        import_: object = "ok",
        produce_ses: bool = True,
        import_counts: tuple[int, int, int, int] = (0, 318, 0, 26),
    ) -> None:
        self.export = export
        self.java = java
        self.import_ = import_
        self.produce_ses = produce_ses
        self.import_counts = import_counts
        self.calls: list[str] = []

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        if args[0] == "java" or "-jar" in args:
            self.calls.append("java")
            return self._resolve_java(args)
        # python -c <script> ...
        script = args[2]
        if "ExportSpecctraDSN" in script:
            self.calls.append("export")
            return self._resolve("export", self.export)
        if "ImportSpecctraSES" in script:
            self.calls.append("import")
            return self._resolve_import()
        raise AssertionError(f"args inesperados: {args}")

    def _resolve(self, stage: str, spec: object) -> subprocess.CompletedProcess[str]:
        if isinstance(spec, BaseException):
            raise spec
        if isinstance(spec, subprocess.CompletedProcess):
            return spec
        return _completed(0, stdout=f"{stage.upper()}_OK\n")

    def _resolve_java(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        if isinstance(self.java, BaseException):
            raise self.java
        if isinstance(self.java, subprocess.CompletedProcess):
            result = self.java
        else:
            result = _completed(0, stdout="routed\n")
        if self.produce_ses:
            ses = Path(args[args.index("-do") + 1])
            ses.write_text("(session)\n")
        return result

    def _resolve_import(self) -> subprocess.CompletedProcess[str]:
        if isinstance(self.import_, BaseException):
            raise self.import_
        if isinstance(self.import_, subprocess.CompletedProcess):
            return self.import_
        tb, ta, vb, va = self.import_counts
        line = f"IMPORT_OK tracks_before={tb} tracks_after={ta} vias_before={vb} vias_after={va}\n"
        return _completed(0, stdout=line)


@pytest.fixture
def jar(tmp_path: Path) -> str:
    p = tmp_path / "freerouting.jar"
    p.write_bytes(b"fake-jar")
    return str(p)


def _src(tmp_path: Path) -> Path:
    src = tmp_path / "board.kicad_pcb"
    src.write_text("(kicad_pcb)")
    return src


@pytest.mark.unit
def test_autoroute_success(tmp_path: Path, jar: str) -> None:
    runner = _FakeRunner()
    result = autoroute.run_autoroute(_src(tmp_path), tmp_path / "work", runner=runner, jar_path=jar)
    assert (result.tracks_before, result.tracks_after) == (0, 318)
    assert (result.vias_before, result.vias_after) == (0, 26)
    assert result.export_ms >= 0 and result.route_ms >= 0 and result.import_ms >= 0
    assert Path(result.routed_pcb).name == "routed.kicad_pcb"
    assert runner.calls == ["export", "java", "import"]


@pytest.mark.unit
def test_autoroute_jar_missing_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KICAD_MCP_FREEROUTING_JAR", raising=False)
    with pytest.raises(KicadMcpError) as exc:
        autoroute.run_autoroute(
            _src(tmp_path), tmp_path / "work", runner=_FakeRunner(), jar_path=None
        )
    assert exc.value.code is ErrorCode.KICAD_CLI_MISSING
    assert exc.value.data == {"requirement": "freerouting_jar", "env": "KICAD_MCP_FREEROUTING_JAR"}


@pytest.mark.unit
def test_autoroute_jar_path_inexistente(tmp_path: Path) -> None:
    with pytest.raises(KicadMcpError) as exc:
        autoroute.run_autoroute(
            _src(tmp_path), tmp_path / "work", runner=_FakeRunner(), jar_path="/no/existe.jar"
        )
    assert exc.value.code is ErrorCode.KICAD_CLI_MISSING
    assert exc.value.data is not None and exc.value.data["path"] == "/no/existe.jar"


@pytest.mark.unit
def test_autoroute_java_missing(tmp_path: Path, jar: str) -> None:
    runner = _FakeRunner(java=FileNotFoundError("java"))
    with pytest.raises(KicadMcpError) as exc:
        autoroute.run_autoroute(_src(tmp_path), tmp_path / "work", runner=runner, jar_path=jar)
    assert exc.value.code is ErrorCode.KICAD_CLI_MISSING
    assert exc.value.data == {"requirement": "java"}


@pytest.mark.unit
def test_autoroute_pcbnew_missing_on_export(tmp_path: Path, jar: str) -> None:
    runner = _FakeRunner(export=_completed(autoroute._EXIT_NO_PCBNEW, stderr="NO_PCBNEW: boom"))
    with pytest.raises(KicadMcpError) as exc:
        autoroute.run_autoroute(_src(tmp_path), tmp_path / "work", runner=runner, jar_path=jar)
    assert exc.value.code is ErrorCode.KICAD_CLI_MISSING
    assert exc.value.data is not None and exc.value.data["requirement"] == "pcbnew"


@pytest.mark.unit
def test_autoroute_no_edge_cuts(tmp_path: Path, jar: str) -> None:
    runner = _FakeRunner(export=_completed(autoroute._EXIT_NO_OUTLINE, stderr="NO_OUTLINE"))
    with pytest.raises(KicadMcpError) as exc:
        autoroute.run_autoroute(_src(tmp_path), tmp_path / "work", runner=runner, jar_path=jar)
    assert exc.value.code is ErrorCode.KICAD_CLI_FAILED
    assert "draw_board_outline" in exc.value.hint
    assert exc.value.data is not None and exc.value.data["reason"] == "no_edge_cuts"


@pytest.mark.unit
def test_autoroute_export_generic_failure(tmp_path: Path, jar: str) -> None:
    runner = _FakeRunner(export=_completed(1, stderr="EXPORT_FAILED ok=False size=0"))
    with pytest.raises(KicadMcpError) as exc:
        autoroute.run_autoroute(_src(tmp_path), tmp_path / "work", runner=runner, jar_path=jar)
    assert exc.value.code is ErrorCode.KICAD_CLI_FAILED
    assert exc.value.data is not None and exc.value.data["stage"] == "export_dsn"


@pytest.mark.unit
def test_autoroute_freerouting_no_ses(tmp_path: Path, jar: str) -> None:
    runner = _FakeRunner(produce_ses=False, java=_completed(1, stderr="fatal: could not route"))
    with pytest.raises(KicadMcpError) as exc:
        autoroute.run_autoroute(_src(tmp_path), tmp_path / "work", runner=runner, jar_path=jar)
    assert exc.value.code is ErrorCode.KICAD_CLI_FAILED
    assert exc.value.data is not None and exc.value.data["stage"] == "freerouting"


@pytest.mark.unit
def test_autoroute_freerouting_timeout(tmp_path: Path, jar: str) -> None:
    runner = _FakeRunner(java=subprocess.TimeoutExpired(cmd="java", timeout=600))
    with pytest.raises(KicadMcpError) as exc:
        autoroute.run_autoroute(
            _src(tmp_path), tmp_path / "work", runner=runner, jar_path=jar, timeout_s=600
        )
    assert exc.value.code is ErrorCode.KICAD_TIMEOUT
    assert exc.value.data is not None and exc.value.data["timeout_s"] == 600


@pytest.mark.unit
def test_autoroute_import_failure(tmp_path: Path, jar: str) -> None:
    runner = _FakeRunner(import_=_completed(1, stderr="IMPORT_FAILED"))
    with pytest.raises(KicadMcpError) as exc:
        autoroute.run_autoroute(_src(tmp_path), tmp_path / "work", runner=runner, jar_path=jar)
    assert exc.value.code is ErrorCode.KICAD_CLI_FAILED
    assert exc.value.data is not None and exc.value.data["stage"] == "import_ses"


@pytest.mark.unit
def test_autoroute_passes_max_passes_flag(tmp_path: Path, jar: str) -> None:
    seen: list[list[str]] = []

    class _Capture(_FakeRunner):
        def __call__(self, args: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
            seen.append(args)
            return super().__call__(args, **kw)  # type: ignore[arg-type]

    autoroute.run_autoroute(
        _src(tmp_path), tmp_path / "work", runner=_Capture(), jar_path=jar, max_passes=100
    )
    java_args = next(a for a in seen if a[0] == "java")
    assert "-mp" in java_args and java_args[java_args.index("-mp") + 1] == "100"
