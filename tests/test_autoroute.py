"""Tests unit del runner de autorouting (T1, D-14.4).

Estrategia: se inyecta un ``SubprocessRunner`` fake que enruta por los args
(python del sistema vs java) y simula éxito, cada fallo tipado de D-14.4, y el
timeout. No toca pcbnew, ni java, ni el socket IPC.
"""

from __future__ import annotations

import json
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


# --- inyección de edge clearance al DSN (F-11, sesión 17 P2.1) ----------------
#
# Grammar confirmada por bytecode (javap) del jar de Freerouting 2.1.0:
# ``Structure.read_boundary_scope`` lee un sub-scope ``(clearance_class
# "nombre")`` dentro de ``(boundary ...)`` y lo pasa a
# ``BoardManager.create_board``; ``NetClass.read_scope`` acepta una
# ``(class "nombre" (rule (clearance V)))`` sin nets asignados. Validado
# empíricamente corriendo Freerouting real sobre un DSN inyectado (sesión 17):
# parsea sin error y rutea normalmente.

_MINIMAL_DSN = """(pcb "x.dsn"
  (parser
    (string_quote ")
    (host_cad "KiCad's Pcbnew")
  )
  (resolution um 10)
  (unit um)
  (structure
    (layer F.Cu
      (type signal)
    )
    (boundary
      (path pcb 0  20000 -20000  0 -20000  0 0  20000 0  20000 -20000)
    )
    (rule
      (width 200)
      (clearance 200)
    )
  )
  (placement
  )
  (library
  )
  (network
    (net NET1
      (pins U1-1 U2-1)
    )
    (class kicad_default NET1
      (rule
        (width 200)
        (clearance 200)
      )
    )
  )
  (wiring
  )
)
"""


def _write_dsn(tmp_path: Path, text: str = _MINIMAL_DSN) -> Path:
    dsn = tmp_path / "route.dsn"
    dsn.write_text(text, encoding="utf-8")
    return dsn


@pytest.mark.unit
def test_inject_edge_clearance_adds_clearance_class_to_boundary(tmp_path: Path) -> None:
    dsn = _write_dsn(tmp_path)
    autoroute._inject_edge_clearance(dsn, 0.5)
    text = dsn.read_text(encoding="utf-8")
    assert '(clearance_class "board_edge")' in text
    # Debe quedar DENTRO del scope boundary, antes de su cierre.
    boundary_start = text.index("(boundary")
    class_pos = text.index('(clearance_class "board_edge")')
    assert boundary_start < class_pos


@pytest.mark.unit
def test_inject_edge_clearance_adds_class_to_network(tmp_path: Path) -> None:
    dsn = _write_dsn(tmp_path)
    autoroute._inject_edge_clearance(dsn, 0.5)
    text = dsn.read_text(encoding="utf-8")
    assert '(class "board_edge"' in text
    assert "(clearance 500)" in text  # 0.5mm -> 500um


@pytest.mark.unit
def test_inject_edge_clearance_converts_mm_to_um_correctly(tmp_path: Path) -> None:
    dsn = _write_dsn(tmp_path)
    autoroute._inject_edge_clearance(dsn, 0.35)
    text = dsn.read_text(encoding="utf-8")
    assert "(clearance 350)" in text


@pytest.mark.unit
def test_inject_edge_clearance_result_is_balanced_and_well_formed(tmp_path: Path) -> None:
    """El .dsn modificado sigue teniendo scopes boundary/network parseables
    (mismo balanceo consciente de strings que usa el propio inyector)."""
    dsn = _write_dsn(tmp_path)
    autoroute._inject_edge_clearance(dsn, 0.5)
    text = dsn.read_text(encoding="utf-8")
    # Ambos scopes siguen siendo encontrables y balanceados tras la inyección.
    b_start, b_end = autoroute._find_dsn_scope_span(text, "boundary")
    n_start, n_end = autoroute._find_dsn_scope_span(text, "network")
    assert text[b_start] == "(" and text[b_end - 1] == ")"
    assert text[n_start] == "(" and text[n_end - 1] == ")"


@pytest.mark.unit
def test_inject_edge_clearance_missing_dsn_is_noop_not_crash(tmp_path: Path) -> None:
    """El arnés de tests con runner fake nunca materializa el .dsn — no debe romper."""
    autoroute._inject_edge_clearance(tmp_path / "does_not_exist.dsn", 0.5)  # no debe lanzar


@pytest.mark.unit
def test_inject_edge_clearance_unexpected_dsn_shape_is_noop_not_crash(tmp_path: Path) -> None:
    dsn = tmp_path / "route.dsn"
    dsn.write_text("(pcb (parser))", encoding="utf-8")  # sin boundary/network
    original = dsn.read_text(encoding="utf-8")
    autoroute._inject_edge_clearance(dsn, 0.5)
    assert dsn.read_text(encoding="utf-8") == original  # intacto, no corrompido


@pytest.mark.unit
def test_find_dsn_scope_span_does_not_confuse_prefix_keywords(tmp_path: Path) -> None:
    """``(boundary_extra ...)`` no debe matchear al buscar el scope ``boundary``."""
    text = "(structure (boundary_extra (foo 1)) (boundary (path pcb 0 0 0)))"
    start, end = autoroute._find_dsn_scope_span(text, "boundary")
    assert text[start:end] == "(boundary (path pcb 0 0 0))"


@pytest.mark.unit
def test_run_autoroute_injects_edge_clearance_when_kicad_pro_present(
    tmp_path: Path, jar: str
) -> None:
    """Round-trip completo: si hay un .kicad_pro hermano con edge clearance,
    el .dsn que ve Freerouting ya lo trae inyectado (verificado vía el spy
    del runner, que puede leer el archivo en el momento de la fase java)."""
    src = _src(tmp_path)
    (tmp_path / "board.kicad_pro").write_text(
        '{"design_settings": {"rules": {"min_copper_edge_clearance": 0.5}}}',
        encoding="utf-8",
    )

    captured: dict[str, str] = {}

    class _SpyRunner(_FakeRunner):
        def __call__(self, args: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
            if args[0] == "java" or "-jar" in args:
                dsn_path = Path(args[args.index("-de") + 1])
                captured["dsn_text"] = dsn_path.read_text(encoding="utf-8")
            elif "-c" in args and "ExportSpecctraDSN" in args[2]:
                # El runner fake no materializa el .dsn (no es real pcbnew) —
                # para este test necesitamos contenido real para inyectar.
                Path(args[4]).write_text(_MINIMAL_DSN, encoding="utf-8")
            return super().__call__(args, **kw)  # type: ignore[arg-type]

    autoroute.run_autoroute(src, tmp_path / "work", runner=_SpyRunner(), jar_path=jar)
    assert '(clearance_class "board_edge")' in captured["dsn_text"]
    assert "(clearance 500)" in captured["dsn_text"]


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


# --- parsers de .dsn/.ses: denominador correcto + estado por net (P2.2) -------
#
# Fragmentos reales (recortados) capturados exportando/ruteando boards reales
# en sesión 17 — no sintéticos inventados. El ``.dsn`` grande (208 nets, con
# nombres con "/" que KiCad quotea) viene de exportar
# ``tests/fixtures/004_real/video.kicad_pcb``; el resto son boards mínimos de
# 2 pads construidos con pcbnew para aislar el caso.

_DSN_NETWORK_FRAGMENT = """(pcb "x.dsn"
  (network
    (net NET1
      (pins U1-1 U2-1)
    )
    (net "unconnected-(U3-NC-Pad5)"
      (pins U3-5)
    )
    (net "/ESVIDEO-RVB/OE_RVB-"
      (pins U8-3 U9-1)
    )
    (class kicad_default NET1 "/ESVIDEO-RVB/OE_RVB-"
      (rule
        (width 200)
        (clearance 200)
      )
    )
  )
)
"""

_SES_NETWORK_OUT_FRAGMENT = """(session route
  (routes
    (network_out
      (net NET1
        (wire
          (path F.Cu 200
            0 0
            1000 0
          )
        )
      )
      (net "/ESVIDEO-RVB/OE_RVB-"
        (wire
          (path F.Cu 200
            0 0
            500 0
          )
        )
        (wire
          (path F.Cu 200
            500 0
            1000 0
          )
        )
      )
    )
  )
)
"""


@pytest.mark.unit
def test_parse_dsn_net_pin_counts_excludes_nothing_but_reports_raw_counts() -> None:
    """Denominador correcto (F-09): 1-pin y multi-pin nets se reportan tal
    cual — el filtro >=2 lo aplica el llamador (route_board), no el parser."""
    counts = autoroute.parse_dsn_net_pin_counts(_DSN_NETWORK_FRAGMENT)
    assert counts == {
        "NET1": 2,
        "unconnected-(U3-NC-Pad5)": 1,
        "/ESVIDEO-RVB/OE_RVB-": 2,
    }


@pytest.mark.unit
def test_parse_dsn_net_pin_counts_handles_quoted_slash_net_names() -> None:
    counts = autoroute.parse_dsn_net_pin_counts(_DSN_NETWORK_FRAGMENT)
    assert "/ESVIDEO-RVB/OE_RVB-" in counts


@pytest.mark.unit
def test_parse_dsn_net_pin_counts_missing_network_scope_returns_empty() -> None:
    assert autoroute.parse_dsn_net_pin_counts("(pcb (parser))") == {}


@pytest.mark.unit
def test_parse_ses_net_wire_counts_counts_wires_per_net() -> None:
    counts = autoroute.parse_ses_net_wire_counts(_SES_NETWORK_OUT_FRAGMENT)
    assert counts == {"NET1": 1, "/ESVIDEO-RVB/OE_RVB-": 2}


@pytest.mark.unit
def test_parse_ses_net_wire_counts_missing_network_out_returns_empty() -> None:
    assert autoroute.parse_ses_net_wire_counts("(session route (routes))") == {}


@pytest.mark.unit
def test_classify_net_routing_routed_partial_blocked() -> None:
    # NET1: 2 pines, 1 wire -> necesita 1, tiene 1 -> ruteada.
    # NETA: 3 pines, 1 wire -> necesita 2, tiene 1 -> parcial (faltan 1).
    # NETB: 2 pines, 0 wires -> bloqueada.
    # NETC: 1 pin -> ni ruteable, se ignora.
    pins = {"NET1": 2, "NETA": 3, "NETB": 2, "NETC": 1}
    wires = {"NET1": 1, "NETA": 1}
    routed, partial, blocked = autoroute.classify_net_routing(pins, wires)
    assert routed == ["NET1"]
    assert partial == [{"net": "NETA", "faltan": 1}]
    assert blocked == ["NETB"]


@pytest.mark.unit
def test_classify_net_routing_net_absent_from_wire_counts_is_blocked() -> None:
    """Net que Freerouting nunca tocó (ausente del .ses) = bloqueada, no crash."""
    routed, _partial, blocked = autoroute.classify_net_routing({"NET1": 2}, {})
    assert routed == []
    assert blocked == ["NET1"]


@pytest.mark.unit
def test_end_to_end_parsers_against_real_captured_dsn_and_ses(tmp_path: Path) -> None:
    """Round-trip completo de los parsers sobre un DSN+SES reales (no
    fragmentos recortados a mano) — construidos acá con pcbnew-style
    contenido mínimo para no depender de un archivo externo al repo."""
    dsn = _MINIMAL_DSN  # definido arriba: red NET1 con 2 pines (U1-1, U2-1)
    ses = """(session route
  (routes
    (network_out
      (net NET1
        (wire
          (path F.Cu 200 0 0 1000 0)
        )
      )
    )
  )
)
"""
    pins = autoroute.parse_dsn_net_pin_counts(dsn)
    wires = autoroute.parse_ses_net_wire_counts(ses)
    routed, partial, blocked = autoroute.classify_net_routing(pins, wires)
    assert routed == ["NET1"]
    assert partial == []
    assert blocked == []


# --- config headless de Freerouting (hallazgo empírico, sesión 17) -----------
#
# Con ``gui.enabled=true`` (default de la instalación), el batch mode de
# Freerouting ("-de/-do -host KiCad") completaba el ruteo (logueaba "Auto-
# routing was completed"/"Optimization was completed") pero el proceso JVM
# quedaba colgado sin escribir el .ses, reventando por KICAD_TIMEOUT aunque
# el router ya hubiera terminado — reproducido corriendo el round-trip real
# contra el despertador (24 fp) en sesión 17. Con ``gui.enabled=false`` corre
# limpio de punta a punta.


@pytest.mark.unit
def test_ensure_freerouting_headless_config_flips_enabled_true_to_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = tmp_path / "freerouting.json"
    settings.write_text(json.dumps({"gui": {"enabled": True, "other": "x"}}), encoding="utf-8")
    monkeypatch.setattr(autoroute, "_FREEROUTING_SETTINGS_CANDIDATES", (settings,))

    autoroute._ensure_freerouting_headless_config()

    written = json.loads(settings.read_text(encoding="utf-8"))
    assert written["gui"]["enabled"] is False
    assert written["gui"]["other"] == "x"  # preserva el resto de la config


@pytest.mark.unit
def test_ensure_freerouting_headless_config_already_false_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = tmp_path / "freerouting.json"
    settings.write_text(json.dumps({"gui": {"enabled": False}}), encoding="utf-8")
    monkeypatch.setattr(autoroute, "_FREEROUTING_SETTINGS_CANDIDATES", (settings,))
    before = settings.stat().st_mtime_ns

    autoroute._ensure_freerouting_headless_config()

    assert settings.stat().st_mtime_ns == before  # no reescribe si ya está bien


@pytest.mark.unit
def test_ensure_freerouting_headless_config_missing_file_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        autoroute, "_FREEROUTING_SETTINGS_CANDIDATES", (tmp_path / "does-not-exist.json",)
    )
    autoroute._ensure_freerouting_headless_config()  # no debe lanzar


@pytest.mark.unit
def test_ensure_freerouting_headless_config_malformed_json_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = tmp_path / "freerouting.json"
    settings.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(autoroute, "_FREEROUTING_SETTINGS_CANDIDATES", (settings,))
    autoroute._ensure_freerouting_headless_config()  # no debe lanzar


@pytest.mark.unit
def test_ensure_freerouting_headless_config_no_gui_key_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin la clave ``gui`` (schema distinto de freerouting) no inventa nada."""
    settings = tmp_path / "freerouting.json"
    settings.write_text(json.dumps({"router": {}}), encoding="utf-8")
    monkeypatch.setattr(autoroute, "_FREEROUTING_SETTINGS_CANDIDATES", (settings,))
    autoroute._ensure_freerouting_headless_config()
    assert json.loads(settings.read_text(encoding="utf-8")) == {"router": {}}


@pytest.mark.unit
def test_run_autoroute_calls_ensure_headless_config(
    tmp_path: Path, jar: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = tmp_path / "freerouting.json"
    settings.write_text(json.dumps({"gui": {"enabled": True}}), encoding="utf-8")
    monkeypatch.setattr(autoroute, "_FREEROUTING_SETTINGS_CANDIDATES", (settings,))

    autoroute.run_autoroute(_src(tmp_path), tmp_path / "work", runner=_FakeRunner(), jar_path=jar)

    assert json.loads(settings.read_text(encoding="utf-8"))["gui"]["enabled"] is False
