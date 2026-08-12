# Contributing to kicad-mcp

Thanks for considering it. This project welcomes bug reports, small
fixes, and discussion of the documented limitations just as much as new
tools — see [Reporting bugs vs. limitations](#reporting-bugs-vs-limitations)
below for the distinction that matters most here.

Expected commitment level: this is a young project coming out of a long
solo consolidation phase (see [`README.md`](README.md#known-limitations)
for what that phase found). A PR that adds a small, well-tested fix is
easier to review and merge than a large new capability — start small if
you're new here.

**Maintenance status, said plainly:** review today is mostly a single
maintainer, not a team — response time on issues/PRs will vary, and that's
worth knowing before you invest a lot of time in a large change without
discussing it first. This is exactly the kind of thing this document tries
not to leave you to discover the hard way.

## Development setup

```bash
git clone https://github.com/Gato513/kicad-mcp.git
cd kicad-mcp
uv sync
python3 scripts/verificar_entorno.py      # tells you what's missing for your mode
uv run pytest -m "not integration"        # offline unit + golden tests
uv run ruff check --fix && uv run ruff format
uv run mypy src/
```

`verificar_entorno.py` detects which test mode you're in (no KiCad
running, KiCad running headless, or KiCad running with its GUI open) and
reports exactly what to fix — run it before anything else in a session,
not just once at clone time.

## How the project makes decisions

The project went through an extended consolidation phase before this
release, and three habits from that phase are baked into how PRs get
reviewed here. They're not process for its own sake — each one traces
back to a specific bug that shipping without it would have missed.

**Explicit hypothesis validation.** A change to system behavior — a bug
fix, a new tool, a refactor with functional impact — should state, before
any code is written: (1) the hypothesis being tested, (2) what evidence
would confirm it, (3) what evidence would refute it, (4) how the change
is protected against regressions. This isn't paperwork: it's the
difference between "I think this is why it breaks" and "I checked, and
here's what would have proven me wrong." See the isolation of a
solder-mask bridging defect down to sub-millimeter precision in
`docs/historico/sesiones/30-reporte.md` for what this looks like in
practice.

**Cross-check against current ADRs before finalizing a design.** Before
committing to an approach for a write-tool change, check whether an
existing [ADR](docs/adr/) already governs adjacent behavior — and if
you're not yet sure how the ADRs, `docs/DECISIONES.md`, and
`docs/INDEX.md` relate to each other, start with
[`docs/architecture-for-contributors.md`](docs/architecture-for-contributors.md),
which maps that out. A rejected
`delete_footprint` design (see
[ADR-0013](docs/adr/0013-refs-duplicados-por-anotacion-no-borrado.md))
pivoted to annotating duplicate references instead of deleting footprints
specifically because deleting them would have conflicted with an existing
ADR about copper deletion gates.

**The refutation principle.** For any explanation you're about to accept
— "this is why the crash happens," "this fix addresses the root cause" —
ask first: *what result would prove this wrong, and did I actually check
for it?* Only accept the explanation if it survives that check. This
caught a real near-miss during the project's own Validation Suite: an
initial hypothesis about a KiCad crash (overlapping copper zones causing
a fill conflict) looked plausible enough to write down — but asking what
would refute it led to a follow-up test with non-overlapping zones, which
crashed identically and disproved the original theory before it was
recorded as fact. Full account: `docs/historico/sesiones/33-reporte.md`.

## How to contribute

1. Fork the repo, branch from `main`.
2. Keep PRs focused — one fix or one tool per PR is easier to review than
   a bundle.
3. Run the full offline suite (`pytest -m "not integration"`), `ruff`,
   and `mypy` before opening the PR; all three are expected clean.
4. If your change touches a write tool (anything in
   `src/kicad_mcp/tools/pcb.py` or `sch.py` that mutates the board), read
   [Bridge write contracts](#bridge-write-contracts) and check it against
   the [checklist](#how-to-add-a-new-write-tool) below in the PR
   description.
5. Open the PR against `main` with a description of what changed and,
   for anything behavior-affecting, the hypothesis/evidence/refutation
   reasoning from above — even a couple of sentences is enough.
6. Expect review to ask "what would prove this doesn't work?" — it's not
   personal, it's the project's one consistent review question.

### Boundaries that require maintainer sign-off first

A handful of things are treated as frozen contracts and won't be merged
without an explicit maintainer decision beforehand — open an issue to
discuss before investing time in a PR that touches:

- `docs/specs/**` and `tests/golden/**` — these are contracts consumed by
  the LLM agent at runtime and by the golden-file encoder tests; a
  failing golden test is never "fixed" by editing the golden.
- The gate system (`G1`–`G5`, [ADR-0003](docs/adr/0003-gates-de-autonomia.md)) —
  autonomy safety thresholds are deliberately not prompt-tunable.
- Existing error codes in `docs/specs/tool-catalog.md` — they're public
  API. New codes are always welcome; renaming or removing existing ones
  isn't.
- The KiCad version target (10.0.4, 9.0 minimum,
  [ADR-0002](docs/adr/0002-versiones-de-kicad.md)) — no nightly-only
  features.
- New entries in `pyproject.toml` dependencies — propose with a
  one-line justification for why it's needed.

## Bridge write contracts

Every tool that mutates a live KiCad board or a schematic file is checked
against four axes, adopted after auditing all 32 tools against them (full
results: [`docs/analisis/auditoria-contratos-bridge.md`](docs/analisis/auditoria-contratos-bridge.md)):

1. **Persistence** — does the tool save to disk, always or
   conditionally? Strict-contract example: `fill_zones()` always calls
   `save_board()` before returning
   ([ADR-0012](docs/adr/0012-route-board-persist-contract.md)). Valid
   design *without* persistence: `add_track()` mutates the live,
   in-memory board only and documents that the caller must call
   `save_board()` explicitly — that's a deliberate choice (`mtimes=None`
   snapshots), not an oversight.
2. **Error propagation** — every write failure surfaces as a typed
   `{code, message, hint}`, never silently. The example of what *not* to
   do is the project's own history: before a fix in one release,
   `route_board(refill=true)` discarded a failed disk reload inside a
   bare `except` and reported success anyway, skipping the safety refill
   it had promised without any visible error — roughly:

   ```python
   # Don't: swallows the failure, caller has no idea the refill was skipped.
   try:
       reloaded = reload_board_from_disk(...)
   except KicadMcpError:
       reloaded = False  # silently degrades the guarantee route_board promised

   # Do: report it as a distinct, typed error instead of pretending success.
   try:
       reload_board_from_disk(...)
   except KicadMcpError as exc:
       raise KicadMcpError(
           code=ErrorCode.POST_ROUTE_REFILL_SKIPPED,
           message="Refill after routing was skipped because the disk reload failed.",
           hint=str(exc),
       ) from exc
   ```

   `POST_ROUTE_REFILL_SKIPPED` is a pure addition to the `ErrorCode`
   `StrEnum` — existing codes are never renamed (they're public API, see
   `docs/specs/tool-catalog.md`), but adding a new one to report a
   previously-silent failure is always welcome.
3. **Disk↔memory synchronization** — a mutating tool should start with
   `_guard_live_stale()` and `check_no_external_disk_edit()` unless
   there's a documented reason it's exempt. The one legitimate exception
   is `reload_board_from_disk` itself — it's the mechanism that clears
   the guard, so it can't also be gated by it.
4. **Reload handling** — if a tool calls `reload_board_from_disk`
   internally, a failure there must propagate with a diagnosis, never be
   dropped. No automatic retry (a KiCad IPC call is not idempotent to
   retry blindly against) — but always a reported failure.

## How to add a new write tool

Checklist for any PR that adds or changes a tool touching the live board
or a schematic file:

- [ ] Does it mutate zones/keepouts, directly or indirectly? If so, does
      it run `refill_zones()` + `enforce_hole_clearance()` +
      `save_board()` together (reuse `_refill_enforce_and_save` if
      possible), or is there a documented reason it doesn't need to?
- [ ] Does it start with `_guard_live_stale()` +
      `check_no_external_disk_edit()`? If not, why is this tool a
      legitimate exception?
- [ ] Does the tool's response make clear whether the change landed on
      disk or only in memory?
- [ ] Is every new error code a pure addition to the `ErrorCode` StrEnum
      (never a rename), documented in `docs/specs/tool-catalog.md` in the
      same commit?
- [ ] If the tool touches the zone/keepout/routing pipeline, is the
      corresponding GUI regression test updated? This is a merge gate,
      not optional, for that category of change.
- [ ] Unit tests cover all four axes above, with the bridge mocked.
- [ ] If the tool needs real KiCad behavior to verify, an
      `integration`-marked test exists for it.

## Test conventions

Three layers, in increasing order of cost:

1. **Offline (`pytest -m "not integration"`)** — pure logic, encoder/golden
   comparisons, mocked bridge. Fast, runs on every commit, currently 394
   tests. This is the gate for any PR.
2. **Integration (`pytest -m integration`)** — needs a real, running
   KiCad instance (`kicad-cli` or the IPC API), no GUI required. Slower;
   run before merging anything that touches the bridge.
3. **GUI (`pytest -m integration_gui` / `integration_gui_slow`)** — needs
   a human with KiCad's GUI open and its API server enabled, following
   the manual protocol in
   [`docs/guias/pruebas-gui.md`](docs/guias/pruebas-gui.md). These are
   **not automated**, and that's a limitation of KiCad's current IPC API
   (there's no way to script "open this project in the GUI" without
   nightly-only features this project has chosen not to depend on — see
   [ADR-0002](docs/adr/0002-versiones-de-kicad.md)), not a corner the
   project cut. A PR that touches `route_board`, `fill_zones`,
   `add_zone`, or the zones/keepouts pipeline needs its corresponding
   `_gui_slow` test run manually before merge.

## Reporting bugs vs. limitations

- **Bug report:** behavior you didn't expect and that isn't already
  listed in [`README.md` §Known limitations](README.md#known-limitations).
  Open a GitHub issue with clear reproduction steps (KiCad version,
  board/project shape, the exact tool call and its response).
- **Known limitation:** already documented in the README, each with a
  link to the session or analysis that found it. If you have an idea for
  fixing one, open an issue framed the way the project frames its own
  investigations: state the hypothesis, and say what would refute it —
  see [The refutation principle](#how-the-project-makes-decisions) above.
  This is a genuine invitation, not a formality — several of today's
  documented limitations are open precisely because nobody has done that
  work yet.

Issues: <https://github.com/Gato513/kicad-mcp/issues>.

## Code of conduct

This project follows the spirit of the [Contributor
Covenant](https://www.contributor-covenant.org/): be respectful, assume
good faith, focus disagreement on the work rather than the person. No
separate enforcement document exists yet; raise any concern directly with
a maintainer via a GitHub issue in the meantime.
