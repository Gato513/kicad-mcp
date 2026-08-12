# kicad-mcp

An MCP (Model Context Protocol) server that lets an LLM agent operate
[KiCad](https://www.kicad.org/) directly — read schematics and PCBs in a
token-efficient format, place footprints, draw copper, run an autorouter,
validate with ERC/DRC, and export manufacturing files — through 32
purpose-built tools instead of raw file editing.

**Status:** past MVP. The full PCB write loop (placement → outline →
zones/GND plane → autorouting → DRC → export) has been closed and
re-validated against real KiCad 10.0.4 for months. It is now in a
pre-release consolidation phase: a structured [Validation
Suite](validation-suite/) exercises the flow against real open-hardware
projects to find where it actually breaks, on purpose, before anyone else
does. See [Known limitations](#known-limitations) below — this README
leads with them rather than burying them.

## What it does

kicad-mcp automates the canonical KiCad PCB flow: place footprints → draw
board outline → add copper zones/GND plane → route with
[Freerouting](https://github.com/freerouting/freerouting) (headless
autorouter) → refill zones and re-run DRC → export gerbers/BOM/renders.
State is exposed to the LLM agent as [TOON](docs/specs/toon-v1.md), a
compact encoding designed to keep token usage low across many small tool
calls rather than re-serializing the whole board every time.

It talks to a **running KiCad instance** over KiCad's own local IPC API
(`kicad-python`) for live edits, and shells out to `kicad-cli` for
DRC/ERC/export — it does not parse or hand-edit `.kicad_pcb`/`.kicad_sch`
files itself for PCB work (schematic editing is the one exception, see
limitation 7 below).

**Validated scale, stated plainly:** the flow has completed end-to-end,
with results within the project's own acceptance thresholds, on boards up
to **63 footprints / 48 nets / 2 layers**. It was also run against a
**437-footprint / 380-net / 4-layer** board (HackRF One) specifically to
find the scaling ceiling — the autorouter did not complete on that board
(see limitation 2). Treat "small-to-medium 2-layer board" as the
demonstrated sweet spot today, not "any KiCad project."

## Quickstart

```bash
git clone https://github.com/Gato513/kicad-mcp.git
cd kicad-mcp
uv sync                                   # install dependencies (uv, https://docs.astral.sh/uv/)
python3 scripts/verificar_entorno.py      # environment check — run this before anything else
uv run pytest -m "not integration"        # offline unit + golden tests (394 passing today)
```

`verificar_entorno.py` tells you exactly what's missing for the mode
you're in (plain unit tests vs. tests that need a running KiCad) and
prints the fix, so start there rather than guessing at env vars.

To actually drive KiCad you need:
- KiCad ≥ 9.0 installed, 10.0.4 is the validated target (see
  [ADR-0002](docs/adr/0002-versiones-de-kicad.md)), with **Preferences →
  Plugins → Enable API server** turned on and KiCad restarted.
- `KICAD_MCP_PROJECT` set to the `.kicad_pro` you want the server to
  operate on.
- `KICAD_MCP_FREEROUTING_JAR` set to a local `freerouting-*.jar` if you
  want `route_board` to actually autoroute (Java ≥ 17 required).
- `KICAD_API_SOCKET` only if your KiCad API socket isn't at the default
  `ipc:///tmp/kicad/api.sock`.

Then register the server with an MCP client (`uv run kicad-mcp` runs it
over stdio) or probe it by hand with the official inspector:

```bash
npx @modelcontextprotocol/inspector uv run kicad-mcp
```

A minimal first call once connected: `health()` to confirm the bridge can
see your KiCad instance, then `run_drc()` against a project you don't
mind DRC-checking.

## Known limitations

This section exists because a colleague who tries this on their own board
deserves to know where it stops working *before* they hit it, not after.
Each item links to the session or document where it was found and
verified — nothing here is a guess.

- **Validated up to 63 footprints / 2 layers; a 437-footprint / 4-layer
  board found the scaling ceiling, not a routed result.** See
  [`docs/analisis/validation-suite-sintesis-A-B-C.md`](docs/analisis/validation-suite-sintesis-A-B-C.md)
  for the full three-point comparison (13 fp → 63 fp → 437 fp).
- **Freerouting 2.1.0 can enter an internal crash-loop on large/complex
  boards** (observed on the 437-footprint board: repeated internal
  `NullPointerException`s, no routing progress for a full hour). This is
  an upstream Freerouting issue, not a kicad-mcp bug — `route_board`
  itself behaved correctly on the timeout (no corrupted state). See
  [`docs/BACKLOG.md`](docs/BACKLOG.md) (`F-V3-ROUTER-TIMEOUT-HARD`).
- **`add_zone(fill=true)` can crash KiCad after 3-4 consecutive calls on
  large boards.** Root cause is not conclusively identified — code
  analysis found no bridge-side cause, and the failure signature (zone
  fragmentation) looks like a pcbnew fill behavior at scale, but this
  wasn't confirmed by reproduction this cycle. Workaround: call
  `fill_zones()` once at the end instead of `fill=true` per zone. Full
  writeup: [`docs/analisis/auditoria-contratos-bridge.md`](docs/analisis/auditoria-contratos-bridge.md) §4.
- **Most write tools don't save to disk by themselves.** Tools like
  `add_track`, `add_via`, `move_footprint` mutate the live, in-memory
  board and expect the caller to invoke `save_board()` explicitly.
  Only `route_board`, `fill_zones`, and `add_zone(fill=true)` guarantee
  disk == memory when they return successfully — see
  [ADR-0012](docs/adr/0012-route-board-persist-contract.md).
- **`delete_tracks_bulk` refills copper zones in memory but doesn't
  persist or re-check hole clearance afterward** — call `fill_zones()`
  yourself if the deletion touched a zone. `delete_zone` and
  `add_keepout_zone` similarly don't recompute neighboring zone fills on
  their own. Tracked as `A1`/`A2`/`A3` in
  [`docs/analisis/auditoria-contratos-bridge.md`](docs/analisis/auditoria-contratos-bridge.md) §5.2;
  `A1` (`delete_tracks_bulk`) has a fix already scheduled.
- **Freerouting doesn't treat a GND copper plane as an exclusion zone for
  nets it doesn't own** — it only routes to the plane's own net, not
  around it. A specific same-layer variant of the resulting orphaned-via
  pattern isn't fixed by the existing post-route stitching yet. See
  `F-D5-01-B` in [`docs/BACKLOG.md`](docs/BACKLOG.md).
- **Schematic editing is direct file mutation (`kicad-skip`), not IPC** —
  KiCad 10 doesn't expose a schematic API. This also means the schematic
  write tools (`add_symbol`, `set_value`, `set_footprint`,
  `connect_pins`) are purely additive today: there's no `delete_wire` or
  similar, so an agent can build a schematic but not clean one up. See
  [`docs/guias/guia-paleta.md`](docs/guias/guia-paleta.md) for the one
  real hazard this creates (never edit a schematic file while KiCad's
  own editor has it open).
- **Long-running tool calls (e.g. a full autoroute) can exceed an MCP
  client's idle timeout** (~1818s observed) before KiCad/Freerouting
  finishes. This is a client-side limitation, not a kicad-mcp bug —
  driving the call from a detached process (`nohup` + `disown`) works
  around it. See `docs/historico/sesiones/33-reporte.md`.
- **GUI-dependent tests require a human with KiCad open and are not
  automated** — this is a constraint of KiCad's IPC API on this version,
  not a project shortcut. See
  [`docs/guias/pruebas-gui.md`](docs/guias/pruebas-gui.md) for the manual
  protocol.
- **Practically Linux-only** ([ADR-0005](docs/adr/0005-linux-como-plataforma.md)).
  KiCad 10.0.4 is the validated target; 9.0 is the documented minimum
  ([ADR-0002](docs/adr/0002-versiones-de-kicad.md)).

## Documentation

- [`docs/analisis/validation-suite-sintesis-A-B-C.md`](docs/analisis/validation-suite-sintesis-A-B-C.md) — the
  cross-board evidence behind the scale claims above.
- [`docs/analisis/auditoria-contratos-bridge.md`](docs/analisis/auditoria-contratos-bridge.md) — full audit of
  every write tool's persistence/error/sync/reload contract.
- [`docs/adr/`](docs/adr/) — one architectural decision record per file
  (why KiCad 10, why stdio-only, why no database, the `route_board`
  persistence contract, etc.).
- [`docs/architecture-for-contributors.md`](docs/architecture-for-contributors.md)
  — start here if you're new: real process topology, tool taxonomy, and
  how to navigate the ADRs/specs/session-report layers below.
- [`docs/DECISIONES.md`](docs/DECISIONES.md) — index of ADRs plus
  informal decisions not yet promoted to one.
- [`docs/investigacion/`](docs/investigacion/) — root-cause
  investigation reports for specific bugs.
- [`docs/glosario.md`](docs/glosario.md) — EDA/KiCad domain glossary.
- [`docs/guias/guia-paleta.md`](docs/guias/guia-paleta.md) — protocol for
  populating a schematic with `add_symbol`.
- [`docs/guias/pruebas-gui.md`](docs/guias/pruebas-gui.md) — manual test
  protocol for the GUI-dependent test suite.
- [`docs/INDEX.md`](docs/INDEX.md) — full documentation map, if you need
  something not linked above.

## Contributing

Contributions are welcome. [`CONTRIBUTING.md`](CONTRIBUTING.md) covers
setup, the project's write-tool contract (the 4 axes every write tool is
checked against), and the review conventions that shaped the codebase —
read it before opening a PR that touches anything under `src/kicad_mcp/tools/`
or `src/kicad_mcp/bridge/`.

## License

Apache License 2.0 — see [`LICENSE`](LICENSE). Runtime dependencies with
other licenses (KiCad and Freerouting are GPL-3.0, invoked as external
processes rather than linked; `kicad-skip` is LGPL-2.1) are listed in
[`NOTICE`](NOTICE).

## Acknowledgments

- [KiCad](https://www.kicad.org/) — the EDA platform this project
  automates, not replaces.
- [Freerouting](https://github.com/freerouting/freerouting) — the
  headless autorouter `route_board` drives. Its 2.1.0 crash-loop on large
  boards is a real, documented limitation (see above) — it's still the
  best open autorouter available for this integration.
- [ANAVI Technology](https://anavi.technology/) and [Great Scott
  Gadgets](https://greatscottgadgets.com/) — authors of the real
  open-hardware designs (`anavi-dev-mic`, `anavi-macro-pad-12`,
  `hackrf-one`) used as ground truth in the Validation Suite.
- Built with heavy use of Claude (Anthropic) as the agentic development
  environment throughout this project's write-tool implementation and
  validation cycles — noted here for transparency about how the codebase
  was produced, not as an endorsement of any particular workflow.

*(También disponible en [español](README.es.md).)*
