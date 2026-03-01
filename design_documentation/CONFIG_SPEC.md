# CONFIG_SPEC.md — Bluesky Run Timeline & Plot Panels Configuration (v1)

This document defines the **configuration contract** for a Bluesky + Tiled + ZMQ timeline UI (Dash/Plotly), intended to be used with a fork/extension of **bluesky-web-plotting**.

The configuration is **JSON** (or JSON5 if you later decide to allow comments—this spec assumes **strict JSON**).

---

## 1. Goals and scope

The configuration must support:

1. **Two data sources**
   - **Live**: Bluesky documents delivered via **ZMQ** (`start`, `descriptor`, `event_page`, `stop`).
   - **Tiled**: persisted runs queried from a Tiled server.

2. A **unified timeline** that can show:
   - historical runs (Tiled), and
   - currently running / very recent runs (Live overlay).

3. **Tracks**:
   - “Virtual tracks” = group clips by run metadata (e.g. `start.plan_name`, `start.proposal_id`).
   - “Stream-aware tracks” = optionally require that a run contains a given stream (e.g. `"primary"`, `"baseline"`).

4. **Preconfigured filters** per track, expressed as a small “predicate language”.

5. **Selection actions**:
   - Clicking a clip populates the two top panes (left/right) with configurable content (plots, metadata, tables, etc.).

---

## 2. File format

- **Encoding:** UTF-8
- **Format:** JSON
- **Top-level key required:** `"version": 1`

---

## 3. Top-level schema

### 3.1. Root object

```json
{
  "version": 1,
  "app": { ... },
  "sources": { ... },
  "timeline": { ... },
  "tracks": [ ... ],
  "panels": { ... }
}
```

### 3.2. Required keys

- `version` (number): must be `1`
- `sources` (object)
- `timeline` (object)
- `tracks` (array; may be empty but not recommended)

### 3.3. Optional keys

- `app` (object)
- `panels` (object)

---

## 4. `app` section

```json
{
  "title": "Bluesky Run Browser",
  "timezone": "UTC"
}
```

- `title` (string, optional): UI title.
- `timezone` (string, optional): IANA timezone name or `"UTC"`.
  - **Recommendation:** use `"UTC"` for storage and convert in UI if desired.

---

## 5. `sources` section

### 5.1. `sources.live` (ZMQ)

```json
{
  "enabled": true,
  "zmq_address": "tcp://localhost:5568",
  "max_live_runs": 50,
  "max_live_event_pages_per_stream": 200
}
```

- `enabled` (bool, optional; default `true`)
- `zmq_address` (string, required if enabled): ZMQ SUB endpoint.
- `max_live_runs` (int, optional; default `50`): cap the in-memory set of live-tracked runs.
- `max_live_event_pages_per_stream` (int, optional; default `200`): cap cached event pages per stream (only relevant if you keep live data for selection plotting).

**Notes**
- Live is **fast** but may be **lossy** (pub/sub can drop messages). The UI must tolerate missing docs.

### 5.2. `sources.tiled`

```json
{
  "enabled": true,
  "uri": "http://localhost:8000",
  "root": "runs",
  "poll_interval_ms": 2000,
  "lookback_hours": 48,
  "include_incomplete": true
}
```

- `enabled` (bool, optional; default `true`)
- `uri` (string, required if enabled): base URI of the Tiled server.
- `root` (string, optional): path/key of the run catalog root within the Tiled client.
- `poll_interval_ms` (int, optional; default `2000`): refresh cadence for fetching run index updates.
- `lookback_hours` (number, optional; default `48`): only index runs with `start.time >= now - lookback_hours`.
- `include_incomplete` (bool, optional; default `true`): include runs without a stop doc (if present in Tiled).

**Notes**
- Tiled is the **eventual source of truth** for completed runs.

---

## 6. `timeline` section

```json
{
  "default_window_hours": 12,
  "show": { "live": true, "tiled": true },
  "track_order": ["primary", "baseline", "proposal"],
  "clip": {
    "min_duration_ms": 5,
    "running_update_ms": 500
  }
}
```

- `default_window_hours` (number, optional; default `12`): initial time window shown.
- `show.live` / `show.tiled` (bool, optional; default `true`): default state of top-bar toggles.
- `track_order` (array of strings, optional): ordering of track IDs in the UI. Tracks not listed appear after those listed.
- `clip.min_duration_ms` (int, optional; default `5`): minimum bar duration for visibility (clips shorter than this are expanded visually).
- `clip.running_update_ms` (int, optional; default `500`): how often running clips should visually extend to “now”.

---

## 7. `tracks` section

### 7.1. TrackDefinition schema

```json
{
  "id": "primary",
  "name": "Primary (by plan)",
  "include_sources": ["tiled", "live"],
  "require_streams": ["primary"],
  "where": [ ... ],
  "group_by": { ... },
  "label": { ... },
  "on_select": { ... }
}
```

#### Required keys
- `id` (string): unique identifier (stable; used in `track_order`).
- `name` (string): display name.

#### Optional keys
- `include_sources` (array of `"tiled"`/`"live"`; default `["tiled","live"]`)
- `require_streams` (array of strings; default `[]`)
- `where` (Predicate; default empty = include all)
- `group_by` (GroupBy; required for meaningful tracks; if omitted, all clips share a single group)
- `label` (LabelSpec; optional)
- `on_select` (SelectionSpec; optional)
- `streams_hint` (array of strings; optional): advisory list of streams to prefer for plots in this track.

---

## 8. Grouping (`group_by`)

### 8.1. GroupBy schema

```json
{
  "field": "start.plan_name",
  "fallback": "unknown_plan"
}
```

- `field` (string): a **field path** (see section 10).
- `fallback` (string, optional): used if the field is missing or null/empty.

**Semantics**
- The resolved value becomes the **track row label** (y-axis category) for that clip.
- If the resolved value is not a string, it is converted to string.

---

## 9. Clip labeling (`label`)

### 9.1. LabelSpec schema

```json
{
  "title": { "template": "{start.plan_name} (scan_id={start.scan_id})" },
  "subtitle": { "template": "{uid}" }
}
```

- `title.template` (string, optional)
- `subtitle.template` (string, optional)

Templates use `{...}` placeholders where `...` is a field path (section 10).

**Template rules**
- Missing fields render as empty string.
- Values are stringified.
- No conditionals/loops in v1 (keep it simple).

---

## 10. Field paths and evaluation context

### 10.1. Evaluation context object

Predicates and templates are evaluated against a context with these roots:

- `uid` (string)
- `start` (object) — start document
- `stop` (object or null) — stop document if known
- `streams` (array of strings) — known streams for the run (may be partial for live/incomplete data)

### 10.2. Field path syntax

- Dot-separated: `start.plan_name`, `stop.exit_status`, `uid`, `start.time`
- Root must be one of: `uid`, `start`, `stop`, `streams`

### 10.3. Missing data

- If any segment is missing, the result is `null` (missing).
- Predicates must handle missing values according to operator semantics.

---

## 11. Predicates (`where`)

### 11.1. Predicate forms

A predicate is either:

1) a **leaf predicate**:
```json
{ "field": "start.plan_name", "op": "eq", "value": "count" }
```

2) a **boolean composition**:
```json
{ "all": [ ... ] }
{ "any": [ ... ] }
{ "not": { ... } }
```

### 11.2. Leaf predicate schema

- `field` (string, required): field path (section 10)
- `op` (string, required): operator (section 11.3)
- `value` (any, optional/required depending on op)

### 11.3. Supported operators (v1)

| Operator    | Value required | Meaning |
|------------|----------------|---------|
| `eq`       | yes            | field equals value |
| `neq`      | yes            | field not equals value |
| `in`       | yes (array)    | field is in array |
| `nin`      | yes (array)    | field is not in array |
| `gt`       | yes            | field > value (numeric or time) |
| `gte`      | yes            | field >= value |
| `lt`       | yes            | field < value |
| `lte`      | yes            | field <= value |
| `exists`   | no             | field is present and not null |
| `missing`  | no             | field is missing or null |
| `not_empty`| no             | field is a non-empty string/list |
| `contains` | yes (string)   | field (string) contains substring |
| `regex`    | yes (string)   | field (string) matches regex |
| `starts_with` | yes (string)| field starts with substring |
| `ends_with`   | yes (string)| field ends with substring |

### 11.4. Type rules

- `contains`, `regex`, `starts_with`, `ends_with`:
  - if field is not a string, the predicate is **false**.
- `not_empty`:
  - true for strings with length > 0
  - true for arrays/lists with length > 0
  - false otherwise
- `exists`:
  - true if field resolves and value is not null
- `missing`:
  - true if field is null or missing

### 11.5. Time comparisons

Fields such as `start.time` and `stop.time` are expected to be epoch seconds (float/int) in Bluesky docs.

For time comparisons (`gt/gte/lt/lte`) you may use either:

- absolute epoch seconds:
```json
{ "field": "start.time", "op": "gte", "value": 1730000000 }
```

- relative time spec:
```json
{ "field": "start.time", "op": "gte", "value": { "relative": "-24h" } }
```

Relative spec format:
- `{ "relative": "-24h" }`, `{ "relative": "-30m" }`, `{ "relative": "-7d" }`
- Units: `s`, `m`, `h`, `d`
- Evaluated relative to “now” at predicate evaluation time.

### 11.6. Boolean composition semantics

- `{ "all": [...] }` is true if all sub-predicates are true.
- `{ "any": [...] }` is true if any sub-predicate is true.
- `{ "not": P }` negates predicate `P`.
- Empty `all` => true; empty `any` => false.

---

## 12. Stream requirements (`require_streams`)

A track may require that certain streams exist for a run:

```json
"require_streams": ["primary", "baseline"]
```

Semantics:
- A run is included only if **all** required stream names are present in the run’s known stream set.

**Important**
- For live data, stream knowledge may lag until descriptors arrive.
- Implementations should treat “unknown streams” consistently. Two acceptable approaches:
  1. **Strict**: exclude until streams are confirmed.
  2. **Optimistic**: include but mark as “pending streams” until confirmed.

This spec allows either; choose one and document it in your implementation.

---

## 13. Selection behavior (`on_select`) and `panels`

  - `on_select` determines what appears in the top panes when a clip becomes selected.
  - It does not control the selection/cursor mechanics themselves.
  - the UI expects the timeline figure to embed the run UID in a click-retrievable field (e.g. Plotly `customdata`)

### 13.1. `panels.defaults`

```json
{
  "defaults": {
    "left": { "kind": "summary" },
    "right": { "kind": "stream_plot", "stream": "primary" }
  }
}
```

### 13.2. Track-level `on_select` overrides

```json
"on_select": {
  "left_panel": { "kind": "run_metadata" },
  "right_panel": { "kind": "stream_plot", "stream": "baseline" }
}
```

If omitted:
- fall back to `panels.defaults`.
If `panels.defaults` is also missing:
- UI chooses reasonable built-ins (implementation-defined).

### 13.3. PanelSpec schema

A panel spec always has:
- `kind` (string): one of the supported panel kinds below.
- Additional keys depend on `kind`.

#### Supported panel kinds (v1)

1) `summary`
- Shows compact run summary: uid, plan_name, times, duration, status, streams.

2) `run_metadata`
- Shows prettified start/stop JSON.

3) `stream_plot`
- Plots a selected stream using the plotting framework.
- Keys:
  - `stream` (string, required): e.g. `"primary"`, `"baseline"`
  - `fields` (string, optional): `"hinted"` (default) or `"all"` (implementation-defined)

4) `table_preview`
- Shows a table preview for the selected stream (head/tail).
- Keys:
  - `stream` (string, required)
  - `rows` (int, optional; default `50`)

5) `json_editor`
- Shows an editor for the loaded JSON config (read/write UI is optional; may be read-only).
- Keys:
  - `target` (string, optional): `"config"` (default)

### 13.4 Runtime UI State (not configured)

  - Selection is runtime state: selected_uid: `Optional[str]`
  - Cursor/playhead is runtime state: cursor_time: `Optional[datetime]`
  - Clicking a clip updates both:
    - selected_uid becomes the clicked run UID
    - cursor_time becomes the click x-position (fallback to `t0` if not available)
  - The timeline figure will visually reflect:
    - selection via a clip outline overlay
    - cursor via a vertical line across all lanes + optional timestamp label
  - These are stored/managed in the UI layer (Dash callbacks / `dcc.Store`), *not* in JSON config.

---

## 14. Examples

### 14.1. Minimal working config

```json
{
  "version": 1,
  "sources": {
    "live": { "enabled": true, "zmq_address": "tcp://localhost:5568" },
    "tiled": { "enabled": true, "uri": "http://localhost:8000", "root": "runs" }
  },
  "timeline": {
    "default_window_hours": 12,
    "show": { "live": true, "tiled": true }
  },
  "tracks": [
    {
      "id": "primary",
      "name": "Primary (by plan)",
      "require_streams": ["primary"],
      "where": [],
      "group_by": { "field": "start.plan_name", "fallback": "unknown_plan" }
    },
    {
      "id": "baseline",
      "name": "Baseline (by plan)",
      "require_streams": ["baseline"],
      "where": [],
      "group_by": { "field": "start.plan_name", "fallback": "unknown_plan" }
    },
    {
      "id": "proposal",
      "name": "By proposal",
      "where": [{ "field": "start.proposal_id", "op": "exists" }],
      "group_by": { "field": "start.proposal_id", "fallback": "no_proposal" }
    }
  ]
}
```

### 14.2. Track filtering by plan name

```json
{
  "id": "grid_scans",
  "name": "Grid scans only",
  "where": [
    { "field": "start.plan_name", "op": "regex", "value": "^grid_.*" }
  ],
  "group_by": { "field": "start.plan_name", "fallback": "grid" },
  "on_select": {
    "left_panel": { "kind": "run_metadata" },
    "right_panel": { "kind": "stream_plot", "stream": "primary" }
  }
}
```

### 14.3. Only show unsuccessful runs

```json
{
  "id": "failures",
  "name": "Non-success runs",
  "where": {
    "not": { "field": "stop.exit_status", "op": "eq", "value": "success" }
  },
  "group_by": { "field": "start.plan_name", "fallback": "unknown_plan" }
}
```

---

## 15. Compatibility and extension rules

1. Unknown top-level keys should be ignored (forward compatibility).
2. Unknown operators must produce a **configuration validation error**.
3. Missing required keys must produce a **configuration validation error**.
4. The configuration version must be validated:
   - `version != 1` => reject with a clear error.

---

## 16. Validation checklist

An implementation should validate:

- Root contains `version`, `sources`, `timeline`, `tracks`.
- Each track has unique `id`.
- `include_sources` contains only `"tiled"` and/or `"live"`.
- `require_streams` are strings.
- Predicates reference supported operators.
- Templates reference valid field roots (`uid`, `start`, `stop`, `streams`).

---

## 17. Open decisions (explicitly left to implementation)

These are intentionally not fixed by v1:

- Whether live runs missing descriptors/streams are temporarily hidden when `require_streams` is used.
- How many plot types are supported by `stream_plot` (depends on available plotting callbacks).
- Whether `json_editor` is read-only or can persist changes.

---

## 18. Change log

- v1: initial spec covering sources, timeline, tracks, predicate language, and panel actions.
