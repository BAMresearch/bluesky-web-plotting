from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

import pandas as pd

from .config import TrackConfig
from .models import RunEnvelope, RunStatus, TimelineModel
from .predicates import resolve_field_path


DF_COLUMNS: tuple[str, ...] = (
    "uid",
    "start_uid",
    "uid_mismatch",
    "source",
    "track_id",
    "track_name",
    "lane",
    "t0",
    "t1",
    "duration_s",
    "status",
    "streams",
    "plan_name",
    "scan_id",
    "proposal_id",
    "title",
    "subtitle",
)


def _ensure_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        # Treat naive as UTC (choose consistency over ambiguity)
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _within_window(t0: datetime, *, now: datetime, window_hours: float) -> bool:
    window_start = now - timedelta(hours=window_hours)
    return t0 >= window_start


def _streams_to_str(streams: Iterable[str]) -> str:
    s = sorted(set(streams))
    return ",".join(s)


def _get_start_doc(env: RunEnvelope) -> Mapping[str, Any]:
    return env.start_doc or {}


def _get_stop_doc(env: RunEnvelope) -> Mapping[str, Any]:
    return env.stop_doc or {}


def _build_eval_ctx(uid: str, env: RunEnvelope) -> dict[str, Any]:
    return {
        "uid": uid,
        "start": dict(_get_start_doc(env)),
        "stop": dict(_get_stop_doc(env)) if env.stop_doc is not None else None,
        "streams": sorted(env.streams_present),
    }


def _lane_for_track(track: TrackConfig, ctx: Mapping[str, Any]) -> str:
    if track.group_by is None:
        return track.id  # fallback: all clips on one lane

    value = resolve_field_path(ctx, track.group_by.field)
    if value is None:
        return track.group_by.fallback or "unknown"
    if isinstance(value, str) and value == "":
        return track.group_by.fallback or "unknown"
    return str(value)


def _render_template(template: str, ctx: Mapping[str, Any]) -> str:
    # Safe-ish templating: replace {field.path} with resolved value.
    # Missing fields => "".
    out = ""
    i = 0
    while i < len(template):
        if template[i] == "{":
            j = template.find("}", i + 1)
            if j == -1:
                # no closing brace: treat rest literally
                out += template[i:]
                break
            key = template[i + 1 : j].strip()
            val = resolve_field_path(ctx, key)
            out += "" if val is None else str(val)
            i = j + 1
        else:
            out += template[i]
            i += 1
    return out


def _titles_for_track(track: TrackConfig, ctx: Mapping[str, Any]) -> tuple[str, str]:
    title = ""
    subtitle = ""
    if track.label and track.label.title:
        title = _render_template(track.label.title.template, ctx)
    if track.label and track.label.subtitle:
        subtitle = _render_template(track.label.subtitle.template, ctx)
    return title, subtitle


def build_timeline_df(
    *,
    model: TimelineModel,
    track: TrackConfig,
    now: datetime,
    window_hours: float,
    show_sources: set[str],
    source_for_uid: Optional[Mapping[str, str]] = None,
) -> pd.DataFrame:
    """
    Build a stable DataFrame for ONE track.

    Parameters
    ----------
    model:
      TimelineModel containing merged RunEnvelopes.
    track:
      TrackConfig defining filtering/grouping.
    now:
      Reference time (UTC-aware recommended). Used for running clips and window filtering.
    window_hours:
      Only include runs with t_start within [now-window_hours, now].
    show_sources:
      Which sources to include: {"live","tiled"}.
      (Interpretation depends on how you label envelopes; see source_for_uid.)
    source_for_uid:
      Optional mapping uid -> "live"/"tiled". If omitted, defaults to "tiled".

    Returns
    -------
    pandas.DataFrame with columns DF_COLUMNS.
    """
    now = _ensure_aware_utc(now)
    rows: list[dict[str, Any]] = []

    for uid, env in model.runs.items():
        # Source filter (default: assume tiled unless caller tells us otherwise)
        source = (source_for_uid or {}).get(uid, "tiled")
        if source not in show_sources:
            continue

        # include_sources filter
        if source not in {s.value for s in track.include_sources}:
            continue

        t0 = _ensure_aware_utc(env.t_start)
        if not _within_window(t0, now=now, window_hours=window_hours):
            continue

        # require_streams filter
        if track.require_streams:
            if not set(track.require_streams).issubset(env.streams_present):
                continue

        ctx = _build_eval_ctx(uid, env)

        # where filter
        if track.where is not None and not track.where.evaluate(ctx, now=now):
            continue

        lane = _lane_for_track(track, ctx)

        # stop time for running clips is "now"
        t1 = _ensure_aware_utc(env.t_stop) if env.t_stop is not None else now
        duration_s = max(0.0, (t1 - t0).total_seconds())

        start_doc = _get_start_doc(env)
        stop_doc = _get_stop_doc(env)

        start_uid = start_doc.get("uid")
        uid_mismatch = bool(start_uid) and (str(start_uid) != str(uid))

        plan_name = start_doc.get("plan_name")
        scan_id = start_doc.get("scan_id")
        proposal_id = start_doc.get("proposal_id")

        title, subtitle = _titles_for_track(track, ctx)
        if not title:
            # sensible fallback
            title = str(plan_name) if plan_name is not None else lane

        rows.append(
            {
                "uid": str(uid),
                "start_uid": None if start_uid is None else str(start_uid),
                "uid_mismatch": uid_mismatch,
                "source": source,
                "track_id": track.id,
                "track_name": track.name,
                "lane": lane,
                "t0": t0,
                "t1": t1,
                "duration_s": duration_s,
                "status": env.status.value if isinstance(env.status, RunStatus) else str(env.status),
                "streams": _streams_to_str(env.streams_present),
                "plan_name": None if plan_name is None else str(plan_name),
                "scan_id": scan_id,
                "proposal_id": None if proposal_id is None else str(proposal_id),
                "title": title,
                "subtitle": subtitle,
            }
        )

    df = pd.DataFrame(rows, columns=list(DF_COLUMNS))
    if df.empty:
        # Ensure dtypes are predictable enough for Plotly and tests
        for c in ("t0", "t1"):
            df[c] = pd.to_datetime(df[c])
        return df

    df = df.sort_values(["lane", "t0", "uid"], ascending=[True, True, True]).reset_index(drop=True)
    df["uid_mismatch"] = df["uid_mismatch"].astype(bool)
    return df
