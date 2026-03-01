from __future__ import annotations

from datetime import datetime, timezone

import pytest

from bluesky_web_plots.timeline.config import TrackConfig
from bluesky_web_plots.timeline.dataframe import DF_COLUMNS, build_timeline_df
from bluesky_web_plots.timeline.models import RunEnvelope, RunStatus, TimelineModel


def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


SAMPLE_MD = {
    "start": {
        "plan_name": "scan",
        "scan_id": 6,
        "time": 1772276582.521329,
        "uid": "77adb8cc-d8e1-41bc-92ec-60691a822f48",
    },
    "stop": {
        "exit_status": "success",
        "time": 1772276589.9414232,
        "run_start": "77adb8cc-d8e1-41bc-92ec-60691a822f48",
    },
}


def _make_track(**overrides):
    base = {
        "id": "primary",
        "name": "Primary",
        "where": [],
        "group_by": {"field": "start.plan_name", "fallback": "unknown_plan"},
    }
    base.update(overrides)
    return TrackConfig.from_dict(base, path="track")


def test_build_df_empty_model():
    model = TimelineModel()
    track = _make_track()
    now = _dt(1772276600.0)
    df = build_timeline_df(model=model, track=track, now=now, window_hours=24, show_sources={"tiled", "live"})
    assert tuple(df.columns) == DF_COLUMNS
    assert len(df) == 0


def test_build_df_basic_grouping_and_duration():
    uid = "77adb8cc-d8e1-41bc-92ec-60691a822f48"  # container key
    env = RunEnvelope(
        uid=uid,
        t_start=_dt(SAMPLE_MD["start"]["time"]),
        t_stop=_dt(SAMPLE_MD["stop"]["time"]),
        status=RunStatus.SUCCESS,
        streams_present={"primary"},
        start_doc=SAMPLE_MD["start"],
        stop_doc=SAMPLE_MD["stop"],
    )
    model = TimelineModel(runs={uid: env})
    track = _make_track()
    now = _dt(1772276600.0)

    df = build_timeline_df(model=model, track=track, now=now, window_hours=24, show_sources={"tiled"})
    assert len(df) == 1
    row = df.iloc[0]
    assert row["lane"] == "scan"
    assert row["status"] == "success"
    assert row["streams"] == "primary"
    assert bool(row["uid_mismatch"]) is False
    assert pytest.approx(row["duration_s"], rel=1e-6) == (SAMPLE_MD["stop"]["time"] - SAMPLE_MD["start"]["time"])


def test_build_df_running_uses_now_for_t1():
    uid = "u1"
    env = RunEnvelope(
        uid=uid,
        t_start=_dt(1772276582.0),
        t_stop=None,
        status=RunStatus.RUNNING,
        streams_present={"primary"},
        start_doc={"plan_name": "count", "time": 1772276582.0, "uid": uid},
        stop_doc=None,
    )
    model = TimelineModel(runs={uid: env})
    track = _make_track(group_by={"field": "start.plan_name", "fallback": "x"})
    now = _dt(1772276600.0)

    df = build_timeline_df(model=model, track=track, now=now, window_hours=24, show_sources={"tiled", "live"})
    assert len(df) == 1
    row = df.iloc[0]
    assert row["t1"].to_pydatetime() == now
    assert pytest.approx(row["duration_s"], rel=1e-12) == (now.timestamp() - 1772276582.0)


def test_where_filter_excludes():
    uid = "u2"
    env = RunEnvelope(
        uid=uid,
        t_start=_dt(SAMPLE_MD["start"]["time"]),
        t_stop=_dt(SAMPLE_MD["stop"]["time"]),
        status=RunStatus.SUCCESS,
        streams_present={"primary"},
        start_doc=SAMPLE_MD["start"],
        stop_doc=SAMPLE_MD["stop"],
    )
    model = TimelineModel(runs={uid: env})

    track = _make_track(where={"field": "start.plan_name", "op": "eq", "value": "count"})
    now = _dt(1772276600.0)

    df = build_timeline_df(model=model, track=track, now=now, window_hours=24, show_sources={"tiled", "live"})
    assert len(df) == 0


def test_require_streams_excludes():
    uid = "u3"
    env = RunEnvelope(
        uid=uid,
        t_start=_dt(SAMPLE_MD["start"]["time"]),
        t_stop=_dt(SAMPLE_MD["stop"]["time"]),
        status=RunStatus.SUCCESS,
        streams_present={"primary"},
        start_doc=SAMPLE_MD["start"],
        stop_doc=SAMPLE_MD["stop"],
    )
    model = TimelineModel(runs={uid: env})

    track = _make_track(require_streams=["baseline"])
    now = _dt(1772276600.0)

    df = build_timeline_df(model=model, track=track, now=now, window_hours=24, show_sources={"tiled", "live"})
    assert len(df) == 0


def test_uid_mismatch_recorded():
    uid = "container-uid"
    env = RunEnvelope(
        uid=uid,
        t_start=_dt(1772276582.0),
        t_stop=_dt(1772276583.0),
        status=RunStatus.SUCCESS,
        streams_present={"primary"},
        start_doc={"plan_name": "scan", "time": 1772276582.0, "uid": "start-uid"},
        stop_doc={"exit_status": "success", "time": 1772276583.0},
    )
    model = TimelineModel(runs={uid: env})
    track = _make_track()
    now = _dt(1772276600.0)

    df = build_timeline_df(model=model, track=track, now=now, window_hours=24, show_sources={"tiled", "live"})
    assert len(df) == 1
    row = df.iloc[0]
    assert row["start_uid"] == "start-uid"
    assert bool(row["uid_mismatch"]) is True
