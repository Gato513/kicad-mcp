# kicad-mcp architecture, for contributors

This document exists to shorten the time between "I want to fix or add a
tool" and "I understand where it lives and what it must do." It is a map,
not a specification — the specifications (`docs/specs/`), the architectural
decision records (`docs/adr/`), and the write-tool contract in
[`CONTRIBUTING.md`](../CONTRIBUTING.md) are what actually govern behavior.
When this document and one of those disagree, the spec/ADR/code wins.

**Scope.** This covers: what process(es) exist and how they talk to each
other; how the ~30 MCP tools are categorized by what they touch and how they
persist it; where things live in the repo; and how to read the project's
decision history. It does **not** repeat the write-tool contract itself (see
CONTRIBUTING), the TOON wire format (see `docs/specs/toon-v1.md`), or EDA
domain vocabulary (see `docs/glosario.md`).

**Audience.** Someone who knows Python and roughly what an MCP server is,
but has never opened this repo. Project-specific jargon (TOON, snapshot,
gate, the W-* labels below, `D-NN.N`-style decision IDs) is explained
inline the first time it's used; EDA domain jargon (net, zone, DRC, pad...)
is linked to the glossary instead.

**A note on drift.** An earlier design document,
[`docs/arquitectura.md`](arquitectura.md) (v0.2, July 2026), specifies a
different stack: a Rust core (`rmcp`) talking to a *separate* persistent
Python bridge process. That stack was never built, and it isn't planned to
be — [ADR-0009](adr/0009-port-rust-diferido-con-condiciones.md) formally
deferred it with measured evidence (a mutation's latency is ~89% KiCad
IPC/UI wait; a Rust core would attack under 0.3% of that). `arquitectura.md`
§10 itself prescribes the single-process Python/FastMCP path as the MVP,
which is what actually shipped and is what this document describes. Treat
`arquitectura.md` §3–§4 as a **deferred target**, not the current system;
its §0, §10, and §11 (decisions log) are still accurate context for *why*
things are shaped the way they are.

---

## 1. System map

The server is **one OS process**. There is no separate bridge process, no
message queue between "server" and "bridge" — that split exists only in the
deferred design. What the deferred design called the "bridge" is an
in-process Python module (`src/kicad_mcp/bridge/ipc.py`) that the tool
functions call directly, in the same interpreter, same call stack.

There are exactly **two genuine process boundaries**:

1. **Client ↔ server**, over MCP's stdio transport. This is the only
   transport implemented ([ADR-0001](adr/0001-transporte-y-alcance-mono-usuario.md)
   — mono-user, local, no remote transport).
2. **Bridge ↔ KiCad**, over a Unix domain socket, using KiCad's IPC API
   (`kipy`/`pynng`, protobuf request-reply). KiCad runs the socket server
   inside its own GUI process, on its UI thread.

Everything else that looks like a "process boundary" in the deferred design
is, today, either an in-process function call or a short-lived subprocess
spawned and waited on synchronously:

- **`kicad-cli`** (validation, exports) — spawned as a subprocess per call,
  reads whatever is currently saved on disk. It never talks to the live,
  possibly-unsaved board in KiCad's memory.
- **Freerouting** (autorouting) — spawned as a `java -jar` subprocess by
  `bridge/autoroute.py`, alongside two calls to a *system* Python
  interpreter that imports KiCad's SWIG `pcbnew` bindings to export/import
  the routing job. This path does not use the IPC API at all.
- **Schematic writes** — direct file I/O via the `kicad-skip` library, not
  IPC. KiCad 10 does not expose a schematic IPC API, so this is the only
  way to mutate a `.kicad_sch` file (also why `docs/arquitectura.md` §3.2
  and §11 D6-adjacent notes call this out as the schematic write path).

```
┌──────────────────────────┐   MCP / stdio    ┌───────────────────────────────────────┐
│  MCP client (e.g. Claude │ ───────────────▶ │  kicad-mcp server (single Python       │
│  Code) — outside our     │ ◀─────────────── │  process, FastMCP)                     │
│  control                 │                   │                                        │
└──────────────────────────┘                   │  tools/world.py, tools/pcb.py, ...     │
                                                │        │            │           │      │
                                                │        │            │           │      │
                                                │   (in-process call, no IPC)     │      │
                                                │        ▼            ▼           ▼      │
                                                │  bridge/ipc.py  bridge/rules.py  ...   │
                                                │  (kipy client)  bridge/netlist.py      │
                                                │        │        bridge/kicad_cli.py    │
                                                │        │        bridge/autoroute.py    │
                                                │        │        tools/sch.py (kicad-   │
                                                │        │         skip, direct write)   │
                                                └────────┼────────────┼──────────┬───────┘
                                                          │            │          │
                                          IPC socket       │  subprocess│  subprocess
                                     (protobuf, 2s timeout,│  (spawn,   │  (spawn,
                                      depth-1 queue)       │   wait)    │   wait)
                                                          ▼            ▼          ▼
                                                ┌──────────────┐ ┌──────────┐ ┌─────────────┐
                                                │ KiCad GUI    │ │kicad-cli │ │ Freerouting  │
                                                │ (UI thread,  │ │(exports, │ │ + system     │
                                                │ live board)  │ │ ERC/DRC) │ │ pcbnew (SWIG)│
                                                └──────┬───────┘ └────┬─────┘ └──────┬──────┘
                                                       │              │              │
                                                       ▼              ▼              ▼
                                                ┌───────────────────────────────────────┐
                                                │   .kicad_pcb / .kicad_sch on disk      │
                                                │   (also written directly by kicad-skip,│
                                                │   and by tools/sch.py, no IPC)         │
                                                └───────────────────────────────────────┘
```

Two properties of the IPC channel matter more than the diagram can show:

- **Hard 2-second timeout, depth-1 queue.** Every IPC call is wrapped in a
  single process-wide lock (`threading.Lock`, non-reentrant). KiCad
  processes each request on its UI thread, so there is never more than one
  in-flight request, and nothing in this codebase should be written to
  expect concurrency against that socket or to expect asynchronous
  notifications from KiCad — the API is strictly request-reply.
- **Live vs. disk can diverge.** Most PCB mutation tools change the board
  *in KiCad's memory* and do not save automatically (`docs/adr/0007`,
  "snapshots vivos" — the read that follows registers `mtimes=None` because
  there is no fresh disk state to hash). `kicad-cli` and disk-based reads
  only see what was last saved. A handful of tools (see §3) always save as
  part of their contract instead.

Disk is the one artifact all three channels agree on eventually:
`.kicad_pcb` and `.kicad_sch` are what `kicad-cli`, a reopened GUI session,
and version control all see.

---

## 2. Tool taxonomy

Every MCP tool that mutates something falls into one of four categories
first defined by `docs/analisis/auditoria-contratos-bridge.md` §1 (cited
here as the *origin* of the vocabulary — that audit is a point-in-time
document about which tools satisfied which contract axes as of its date,
not a live source for any individual tool's current behavior; see the
callout on `delete_tracks_bulk` below for why that distinction matters).
The audit is scoped to *write* tools only — it does not define a category
for reads, so **R** below is this document's label for "everything else,"
not a term from the audit.

| Label | Meaning | Persists to disk? |
|---|---|---|
| **R** | Read-only. Reads the live board (IPC), a saved file, or runs `kicad-cli` for validation/export. Never mutates a design. | N/A |
| **W-IPC** | Mutates the live board via IPC. Registers a snapshot with `mtimes=None` (deliberately — see ADR-0007) and does **not** call `save_board()` itself. | No, by design — caller must call `save_board` explicitly. |
| **W-COMPOSITE** | Mutates via IPC, then — under the tool's own trigger condition — refills zones, enforces hole clearance, and saves, per the D-23.2 contract ([ADR-0012](adr/0012-route-board-persist-contract.md)). For `fill_zones` and `add_zone(fill=True)` that trigger condition is "every call, no exceptions." For `route_board` it is not — see the callout below. | When the pipeline runs, always — and if the save fails, the tool reports a typed error rather than silently leaving disk stale. |
| **W-SKIP** | Writes a `.kicad_sch` file directly via `kicad-skip`. No IPC involved — KiCad 10 has no schematic IPC API. | Yes, immediately (it's a file write). |

`docs/analisis/auditoria-contratos-bridge.md` §1 also names a fifth,
non-mutating label, **Infra**, for the two tools that exist to *support*
the other four rather than change a design: `save_board` (the explicit
persistence mechanism W-IPC tools rely on) and `reload_board_from_disk`
(resyncs the live board from what's on disk, e.g. after `route_board`
writes a new file). This document keeps that label — without it, those two
tools don't fit any of the other four categories.

A tool's category is about **what it does to the design and how it
persists**, not about which Python file it lives in. `tools/pcb.py` alone
hosts R, W-IPC, W-COMPOSITE, and Infra tools side by side.

### `route_board`'s refill+enforce+save pipeline is conditional, not guaranteed

`route_board` is classified W-COMPOSITE, and its docstring and
[ADR-0012](adr/0012-route-board-persist-contract.md) do commit to the
D-23.2 contract — but unlike `fill_zones` and `add_zone(fill=True)`, it
does not run the refill+enforce+save block on every call. Verified against
`src/kicad_mcp/tools/pcb.py` (`route_board`): that block
(`_refill_enforce_and_save`) only runs when **all three** hold: `refill`
is `True` (the default, but callers can pass `False`); the board has at
least one existing zone (`zones_existentes > 0`); and the live editor was
successfully reloaded to reflect the freshly-routed file
(`reloaded is True` — which itself requires the target board to be the one
open in KiCad's editor at call time).

When the block is skipped, `route_board` treats the reason differently
depending on *why*. If `refill=False` was passed, the editor is closed, or
a different project is open in KiCad — three cases where skipping is the
documented, expected behavior — the call still returns success; the
newly-routed copper was written to disk (via an atomic file replace, not
through this pipeline), but hole-clearance and zone-fill enforcement
against it were not, and the reported `err_post` was measured without
them. But if the editor *was* the right target and reload was attempted
and failed, that's the one case the tool treats as a broken promise rather
than an expected skip: it raises `POST_ROUTE_REFILL_SKIPPED` instead of
returning success (`src/kicad_mcp/tools/pcb.py`, the
`refill_broke_contract` branch) — the routing itself is still valid and on
disk, but the tool does not claim the D-23.2 contract was honored.
`route_board`'s own response/error payload reports which case applied —
this document doesn't restate that shape, just the branching it depends
on. Treat "W-COMPOSITE" as route_board's *category*, not as a promise that
every successful call ends with a refill.

### `add_zone` and `delete_tracks_bulk` are dual-mode

Two tools don't have a single fixed category — which branch they take
depends on their arguments or on board state at call time. The audit lists
each as two separate rows for this reason.

- **`add_zone`** is W-IPC when called with `fill=False`, W-COMPOSITE when
  called with `fill=True`. This is a straightforward parameter switch.

- **`delete_tracks_bulk`** is more interesting, and is the one place where
  this document deliberately diverges from how the audit and
  `docs/DECISIONES.md` phrase the rule, in favor of what the code actually
  checks (verified against `src/kicad_mcp/tools/pcb.py` at this repo's HEAD,
  and against `docs/DECISIONES.md` §D-34a-fix-1.1). The tool takes the
  W-COMPOSITE branch — refill, enforce clearance, save, with
  `POST_ZONE_PERSIST_FAILED` on save failure — when **the board contains
  at least one copper zone**, checked with a board-wide
  `any(zone.kind == "copper" for zone in ...)`. That is *not* a geometric
  test of whether the deleted tracks/vias actually overlapped a zone; it's
  a coarser, deliberately conservative guard that refills whenever a zone
  could plausibly be affected. `docs/DECISIONES.md` D-34a-fix-1.1 (and the
  brief for this document) describe the condition as "when the deletion
  touches a copper zone," which is accurate in the common case but implies
  more precision than the check performs. Both descriptions lead to the
  same practical advice for a caller: **if the board has copper zones and
  you bulk-delete copper, expect the W-COMPOSITE contract to apply.**

  Structurally, `delete_tracks_bulk` is also the one W-IPC-family tool that
  does **not** carry the `@mutating_tool` decorator described in §4 below —
  not because it's exempt from the guards, but because of a `dry_run`
  early-return ordering problem, explained there.

  **Do not treat `docs/analisis/auditoria-contratos-bridge.md` §6 as
  current for this tool.** That section predates the fix
  (`docs/historico/sesiones/34a-fix-1-reporte.md`) that made the
  W-COMPOSITE branch above exist at all; it describes an earlier state
  where copper-zone deletions were never persisted.

### Where each category's tools live

- **R:** `health`; both of `world.py` (`get_world_context`,
  `get_context_delta`); both of `validate.py` (`run_erc`, `run_drc`); all
  four of `export.py`; the four pure-read PCB tools (`get_tracks`,
  `get_component_detail`, `get_footprint_neighbors`, `get_zones`).
- **W-IPC:** most of `tools/pcb.py`'s mutating surface — `move_footprint`,
  `set_footprint_ref`, `add_track`, `add_via`, `delete_track`, `delete_via`,
  `draw_board_outline`, `add_keepout_zone`, `delete_zone`, plus `add_zone`
  and `delete_tracks_bulk` in their W-IPC branch.
- **W-COMPOSITE:** `route_board` (conditionally — see the callout above),
  `fill_zones`, plus `add_zone` and `delete_tracks_bulk` in their
  W-COMPOSITE branch.
- **W-SKIP:** all four of `tools/sch.py` — `add_symbol`, `set_value`,
  `set_footprint`, `connect_pins`.
- **Infra:** `save_board`, `reload_board_from_disk`.

---

## 3. Data flow

There is no single universal request pipeline — the shape of a call depends
on its category. These four flows are representative, not exhaustive.

**Read (R).** Client calls a tool like `get_world_context`. The tool reads
either the live board over IPC or a file from disk (schematic reads always
go through disk + `kicad-cli`'s netlist export, since there's no schematic
IPC). The result is normalized, encoded to TOON (see
`docs/specs/toon-v1.md`), and a snapshot is registered so a later
`get_context_delta` call can diff against it.

**PCB mutation, W-IPC family A, via `@mutating_tool`.** Most W-IPC and
W-COMPOSITE PCB tools share a standardized entry preamble, implemented as
the `@mutating_tool` decorator
([ADR-0014](adr/0014-mutating-tool-decorator.md)). In order: guard against
a live board that's gone stale relative to disk; guard against an external
edit to disk since the last read; if a `base_snap` argument was given,
validate it against the snapshot store. Only after all three pass does the
tool's own body run. The decorator deliberately does **not** cover the
*epilogue* (timing, the Gate G1 session backup, the audit log entry, the
post-mutation snapshot registration) — those still happen at the end of
each tool body, because their shape differs enough between tools (compare
a W-IPC tool's snapshot-with-`mtimes=None` to a W-COMPOSITE tool's
snapshot-with-fresh-mtimes) that a shared epilogue wasn't worth forcing.

**The `delete_tracks_bulk` exception.** This tool's guards run the same
checks as `@mutating_tool`, but written inline rather than via the
decorator, and — critically — **after** an early return for
`dry_run=True`. `dry_run` is meant to answer "what would this delete?"
without requiring the caller to already hold a fresh, non-stale board; if
the guards ran first (as the decorator would), a `dry_run=True` preview
call against a slightly stale board would fail with
`EXTERNAL_EDIT_DETECTED` instead of returning the preview. So the ordering
here is deliberate, not an oversight — see ADR-0014's exclusions section
for the full reasoning.

**Schematic write (W-SKIP).** Client calls e.g. `add_symbol`. The tool
loads the target `.kicad_sch` with `kicad-skip`, mutates the in-memory
representation, and overwrites the file. No IPC, no live/disk split — the
write *is* the persistence. The post-write state is then rebuilt by
re-reading the file from disk with fresh mtimes, in contrast to the
`mtimes=None` live-snapshot pattern that's exclusive to IPC mutations
([ADR-0007](adr/0007-snapshots-vivos-mtimes-none.md)).

Two more ADRs worth knowing before touching this code: **ADR-0008**
documents that `kipy` mutations must go through a property *setter*, not
direct field assignment — assigning a field silently does nothing.
**ADR-0012** is the D-23.2 persistence contract that defines what
"W-COMPOSITE" means above (refill → enforce hole clearance → save, with a
typed error on save failure) and is mandatory reading before touching
`route_board`, `fill_zones`, or `add_zone` — `route_board`'s version of
that pipeline is conditional (see §2's callout), the other two run it on
every call.

---

## 4. Repo layout

**`src/kicad_mcp/`** — the server.

- `server.py` — entry point. Builds a `FastMCP` instance, registers every
  tool module, runs over stdio.
- `tools/` — one file per tool category: `world.py` (context reads),
  `pcb.py` (the bulk of the mutating surface), `sch.py` (schematic writes),
  `validate.py` (ERC/DRC), `export.py` (BOM/netlist/render/manufacturing),
  `meta.py` (`health`). `_mutating.py` holds the `@mutating_tool`
  decorator and its shared guard helpers. `pcb_encoders.py` holds three
  ad-hoc, non-TOON encoders for tracks/zones/component-detail responses.
- `bridge/` — everything that talks to something outside this process:
  `ipc.py` (the `kipy` client — reads and mutates the live board),
  `kicad_cli.py` (subprocess version probe), `rules.py` (ERC/DRC via
  `kicad-cli`), `netlist.py` (netlist export via `kicad-cli`),
  `sch_positions.py` (parses symbol positions out of a `.kicad_sch`),
  `state_builder.py` (assembles the normalized state the TOON encoder
  consumes), `rules_reader.py` (reads netclass/clearance rules that
  `kipy` doesn't expose), `autoroute.py` (the Freerouting + SWIG `pcbnew`
  pipeline behind `route_board`).
- `toon/` — the TOON encoder and delta/diff engine; pure, deterministic,
  no I/O. The contract it implements is `docs/specs/toon-v1.md`.
- `snapshots/` — the in-memory snapshot store (cache + mtime bookkeeping)
  that backs `get_context_delta` and the staleness guards above.
- `gates/` — the G1/G3 gates (see below).
- `audit/` — the JSONL mutation audit log.
- `errors.py` — the `ErrorCode` `StrEnum`; this is public API (frontier
  F3) consumed by the calling LLM, and existing codes are never renamed.
- `paths.py` — path canonicalization (`canonicalize_within_project_root`),
  the project's path-traversal mitigation.

One gap worth flagging so it doesn't mislead you: several package-level
docstrings in this tree (`__init__.py` at the top level, and in `gates/`
and `audit/`) still describe a "read-only MVP, no mutations" phase. That
phase is long past — the mutating surface described in §2 above is real
and exercised by the test suite — the docstrings are simply stale.

**Gates**, concretely: `docs/adr/0003` defines a five-gate system
(G1–G5) for destructive or high-impact operations. As implemented today,
only two exist in code: **G1** (`gates/g1.py`) takes a one-time backup —
copying `.kicad_sch`/`.kicad_pcb` and, in a git repo, committing (never
pushing) — the first time a project is mutated in a server session; **G3**
(`gates/g3.py`) blocks fabrication exports when DRC isn't clean. G2 (an
interactive confirmation gate for destructive operations) does not exist
yet in code — [ADR-0010](adr/0010-borrado-de-cobre-sin-gate-g2.md) is the
explicit decision that copper deletion (`delete_track`/`delete_via`) does
not wait for it.

**`tests/`** — `golden/` holds encoder input→output pairs that are
contract-frozen (frontier F1: a failing golden is reported, not "fixed" by
editing the golden). `fixtures/` holds KiCad project fixtures for
integration tests — process these with code, never read them into an LLM
context directly. `data/` holds smaller structured test inputs. Everything
else follows a `test_<area>.py` / `test_<area>_session<N>...py` naming
split between contract/unit tests and session-scoped regression tests, with
`_gui` / `_gui_slow` suffixes marking tests that require a live KiCad GUI
(these are excluded from CI; see the pytest markers in
[`CONTRIBUTING.md`](../CONTRIBUTING.md)).

**`docs/`** — `adr/` (architectural decisions, one file per decision, see
§6); `specs/` (frozen contracts: `tool-catalog.md`, `toon-v1.md`,
`restricciones-kicad.md`, `fixtures.md`); `investigacion/` (root-cause
investigation reports — read before re-hypothesizing about a bug that may
already have been diagnosed); `historico/` (session reports and other
process archaeology — evidence, not a live source, see §7); `analisis/`
and `proceso/` (point-in-time audits and the multi-agent workflow
description; treat dated analysis documents the same way as `historico/` —
useful for "why," superseded by code and the ADRs for "what's true now").

**External dependencies**, for orientation rather than as code paths:
**KiCad** (the application this project drives, via its GUI process and
IPC socket); **`kicad-cli`** (KiCad's official command-line tool, invoked
as a subprocess for validation/exports); **`kipy`** (`kicad-python`, the
official IPC client library, imported inside `bridge/ipc.py`);
**`kicad-skip`** (a third-party library for reading/writing `.kicad_sch`
files directly, imported inside `tools/sch.py`); **Freerouting** (a
third-party headless autorouter, invoked as a subprocess by
`bridge/autoroute.py`, [ADR-0011](adr/0011-autorouting-route-board.md)).
None of these are modules inside this repository — don't go looking for
`src/kicad_mcp/kipy/`.

---

## 5. How to read an ADR here

Every file in `docs/adr/` follows the same shape: a title naming the
decision, a header line with `Fecha` / `Estado` / `Fuente` (date / status /
originating session or analysis), a `Contexto` section explaining the
problem, and a `Decisión` section stating what was chosen and why
alternatives were rejected. All 15 ADRs in this repo, as of this document,
carry `Estado: aceptado` (accepted) — there is no "proposed" or
"superseded" status in use here yet, so don't infer a lifecycle stage that
isn't in the source file.

ADRs are governed by frontier **F1**
([ADR-0000](adr/0000-fronteras-inviolables.md)): they are append-only and
never edited retroactively to change a past decision. If a later session
changes course, it adds a new ADR (or a dated addendum inside the existing
one, as ADR-0012 does for its several extensions) rather than rewriting
history.

| ADR | Title | One-line summary |
|---|---|---|
| [0000](adr/0000-fronteras-inviolables.md) | Fronteras inviolables (inviolable frontiers) | F1–F5: specs/goldens, gates, error codes, target KiCad version, dependencies — none change without explicit human approval. |
| [0001](adr/0001-transporte-y-alcance-mono-usuario.md) | Mono-user, stdio transport | No multi-tenancy or remote transport in the MVP. |
| [0002](adr/0002-versiones-de-kicad.md) | KiCad 10 target, 9.0 minimum | No KiCad 11 / nightlies (reinforces F4). |
| [0003](adr/0003-gates-de-autonomia.md) | Autonomy gates (G1–G5) | Backups, destructive-operation confirmation, session budget — deterministic, not prompted (reinforces F2). |
| [0004](adr/0004-economia-de-tokens.md) | Context calibration | Defaults for graduated refresh, TOON token budget, re-sync policy. |
| [0005](adr/0005-linux-como-plataforma.md) | Linux as the sole platform | No official macOS/Windows support in the MVP. |
| [0006](adr/0006-sin-base-de-datos.md) | No database | JSONL + backups under `.kicad-mcp/`, no SQL/structured persistence. |
| [0007](adr/0007-snapshots-vivos-mtimes-none.md) | Live snapshots, `mtimes=None` | A post-mutation in-memory snapshot deliberately carries no disk mtimes. |
| [0008](adr/0008-kipy-write-semantics-property-setter.md) | `kipy` write semantics | Mutate via a property setter, never by direct field assignment. |
| [0009](adr/0009-port-rust-diferido-con-condiciones.md) | Rust port deferred | A v0.4 Rust core is conditional on real evidence of a bottleneck; measured, the bottleneck is KiCad/IPC wait, not Python. |
| [0010](adr/0010-borrado-de-cobre-sin-gate-g2.md) | Copper deletion without Gate G2 | `delete_track`/`delete_via` don't trigger destructive-operation confirmation. |
| [0011](adr/0011-autorouting-route-board.md) | Autorouting via Freerouting | `route_board` delegates routing to headless Freerouting, not to the LLM. |
| [0012](adr/0012-route-board-persist-contract.md) | disk==memory==`err_post` contract (D-23.2) | `route_board` measures DRC and persists *after* refill+enforce; extended to `fill_zones`, `add_zone(fill=True)`, and (per this document, informally) `delete_tracks_bulk`. |
| [0013](adr/0013-refs-duplicados-por-anotacion-no-borrado.md) | Duplicate refs resolved by annotation, not deletion | `set_footprint_ref` plus a `DUPLICATE_REFS` pre-check in `route_board`; ADR-0010 stays untouched. |
| [0014](adr/0014-mutating-tool-decorator.md) | `@mutating_tool` decorator | Standardizes the entry-guard preamble for Family-A W-IPC PCB tools; deliberately excludes the epilogue and three named exceptions (see §3 above). |

Titles and summaries for 0000–0013 are taken from
[`docs/DECISIONES.md`](DECISIONES.md) §1, which is the maintained index for
those. **ADR-0014 is not yet listed in that index** — its table stops at
0013, even though the ADR file itself exists and is accepted. That's a
known gap, out of scope for this document to fix; the row above comes
directly from `docs/adr/0014-mutating-tool-decorator.md`.

---

## 6. Session report, investigation, or ADR — how to tell them apart

Three kinds of document accumulate in `docs/`, and they carry different
authority. This mirrors how [`docs/INDEX.md`](INDEX.md) organizes them:

- **ADR** (`docs/adr/`) — an active, binding architectural decision.
  One file per decision, append-only, never retroactively edited. If
  you're deciding whether some past design choice still holds, this is
  the first place to check.
- **Investigation** (`docs/investigacion/`) — a root-cause report for a
  specific bug, written once the cause is understood (P4.0-style: what was
  observed, what was ruled out, what the actual mechanism was). These stay
  *active* rather than being archived to `historico/`, because ADRs and
  specs cite them as mandatory reading before re-investigating a
  previously-diagnosed failure mode. Treat "we already looked into this"
  as a real possibility and check here first.
- **Session report** (`docs/historico/sesiones/`) — a per-session log:
  what was attempted, what happened, what was decided in the moment. These
  are archived, not operative — useful for archaeology ("why did we choose
  this," "what did we already try and reject") but not a source to cite
  for current behavior. If something from a session report needs to govern
  future work, the convention is to promote its conclusion into
  `DECISIONES.md`, `ROADMAP.md`, or `BACKLOG.md` and leave only a pointer
  behind — not to keep citing the session report directly.

---

## 7. Cross-references

- **[`docs/INDEX.md`](INDEX.md)** — the canonical map of what to read for
  a given task, including a "minimum context to start a session" list.
  This document doesn't replace it; if the two ever disagree about what's
  active vs. archived, INDEX.md governs.
- **[`docs/CONTEXT.md`](CONTEXT.md)** — a snapshot of technical context;
  check its date/SHA before treating it as current operative state, since
  by nature it ages between cycles.
- **[`docs/DECISIONES.md`](DECISIONES.md)** — indexes both formal ADRs and
  informal-but-current decisions that were never promoted to an ADR. Use
  it as the entry point before assuming a design question is unanswered.
- **[`docs/BACKLOG.md`](BACKLOG.md)** — prioritized debt, risks, and
  planned work; check before treating an issue you noticed as new.

None of these fully subordinates the others. As a rough rule for where
authority sits on a given question: specs and ADRs govern the specific
object they define; `docs/DECISIONES.md` is the index into both formal and
informal decisions; the code at the current HEAD is what verifies actual
runtime mechanics (this document included — if the code has moved on,
trust the code); `docs/INDEX.md` governs the documentation map itself; and
`docs/historico/` is evidence of process, not standing authority, unless
one of its conclusions has been explicitly promoted into a document above.
