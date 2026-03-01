# API_REFERENCE.md — Timeline modules (light)

This is a lightweight reference of key entry points under `src/bluesky_web_plots/timeline/`.
It is intentionally short and not a substitute for docstrings or code reading.

---

## Configuration

### `bluesky_web_plots.timeline.io.load_config(path: Path) -> RootConfig`
Load strict JSON config and return validated config object.

### `bluesky_web_plots.timeline.bootstrap.create_timeline_model(cfg: RootConfig) -> TimelineModel`
Create initial runtime state from config (does not start polling or ZMQ).

---

## Predicates and filtering

### `bluesky_web_plots.timeline.predicates.parse_predicate(obj, *, path) -> Predicate`
Parse a predicate from config JSON.

### `Predicate.evaluate(ctx, *, now=None) -> bool`
Evaluate against an evaluation context `{uid,start,stop,streams}`.

---

## Timeline projection & visualization

### `bluesky_web_plots.timeline.dataframe.build_timeline_df(...) -> pandas.DataFrame`
Project runtime state into a stable DataFrame schema for plotting.

### `bluesky_web_plots.timeline.figures.make_timeline_figure(df, *, selected_uid=None, cursor_time=None, ...) -> go.Figure`
Build the Plotly timeline figure, including selection and playhead overlays.

---

## Sources

### `bluesky_web_plots.timeline.tiled_source.TiledSource.sync(model: TimelineModel, *, now: datetime) -> None`
Poll Tiled (server-side time window query) and update `model.runs` and `model.health_tiled`.

### `bluesky_web_plots.timeline.live_source.LiveSourceEngine.on_doc(name: str, doc: Mapping, *, received_at=None) -> None`
Ingest a single Bluesky document and update `model.runs` and `model.health_live`.

---

## Runtime models

### `bluesky_web_plots.timeline.models.RunEnvelope`
Canonical “clip” state for a run.

### `bluesky_web_plots.timeline.models.TimelineModel`
Merged state for the UI (runs, selection, view toggles, health).

