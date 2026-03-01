# DESIGN_DECISIONS.md — Timeline & Sources (v1)

This document records key design decisions for the timeline functionality under `src/bluesky_web_plots/timeline/`.

It is intentionally short and actionable: **what we decided, why, and what it implies**.

---

## DD-001 — Keep a strict JSON config contract

**Decision:** Use a strict JSON configuration validated into attrs classes (`CONFIG_SPEC.md`).

**Why:**
- Config is edited by humans and shared across beamlines.
- Strict validation yields fast feedback and stable behavior.

**Implications:**
- Unknown keys may be ignored for forward compatibility, but unknown operators / missing required fields must error clearly.
- Config parsing remains deterministic and testable.

---

## DD-002 — Separate concerns: Model → DataFrame → Figure

**Decision:** The rendering pipeline is split into three layers:

1. `TimelineModel` (runtime state)
2. `build_timeline_df(...)` (projection into a stable table)
3. `make_timeline_figure(...)` (Plotly visualization + overlays)

**Why:**
- Keeps logic testable (TDD) without depending on Dash/Plotly internals.
- Makes sources (Tiled/Live) swappable without refactoring visualization.

**Implications:**
- DataFrame schema becomes a stable internal contract.
- Plotly tests remain light (presence checks, not brittle snapshots).

---

## DD-003 — Use numeric lanes in the timeline figure

**Decision:** Timeline `y` axis uses numeric lane indices (`lane_idx`) with tick labels showing lane names.

**Why:**
- Robust overlays: selection outline and playhead line are exact and simple.
- Future features (fold/unfold groups, vertical zoom) are much easier with numeric coordinates.

**Implications:**
- DataFrame keeps `lane` as a string; mapping to `lane_idx` happens in `make_timeline_figure(...)`.
- Any lane grouping changes require only remapping indices + tick labels.

---

## DD-004 — Two sources with different guarantees (Tiled vs Live)

**Decision:** Support both:
- **TiledSource**: durable, canonical for completed runs
- **LiveSourceEngine**: low-latency, document-driven and potentially lossy (pub/sub)

**Why:**
- Beamline operators want immediate visibility while acquiring.
- Tiled provides the reliable historical record and final run outcome.

**Implications:**
- UI defaults to a unified timeline showing both; users can toggle visibility.
- Live may miss docs; the system must be resilient and reconcile with Tiled.

---

## DD-005 — Merge precedence: Tiled overrides Live for the same UID

**Decision:** When a run exists in both live and tiled sources, the tiled record is considered canonical (especially `t_stop` and exit status).

**Why:**
- Tiled is durable and replayable; live transport may drop messages.

**Implications:**
- A run may appear as running via live, then later become “completed” once polled from Tiled.
- The timeline must handle this transition smoothly.

---

## DD-006 — UID policy: container key is primary; record start.uid mismatch

**Decision:** Use the Tiled container key (`client[uid]`) as the run UID used by the UI.
Record `start.uid` for diagnostics, and flag mismatches.

**Why:**
- The container key is how runs are addressed in Tiled.
- `start.uid` should match; mismatch indicates corruption or unexpected ingestion.

**Implications:**
- DataFrame includes `start_uid` and `uid_mismatch`.
- Selection uses the container key UID consistently.

---

## DD-007 — Predicate convenience semantics

**Decision:** Predicate parsing supports:
- `where: []` means “match all”
- `where: [P1, P2, ...]` means implicit AND (`all`)

**Why:**
- Keeps config concise and readable.
- Matches user expectations in hand-edited config.

**Implications:**
- Predicate logic remains centralized in `predicates.py`.
- Future refactor to an operator registry is allowed without changing schema.

