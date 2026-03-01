from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from bluesky_web_plots.timeline.models import TimelineModel, RunStatus
from bluesky_web_plots.timeline.tiled_source import TiledSource
from bluesky_tiled_plugins.queries import TimeRange

class FakeRun:
    def __init__(self, metadata: dict, streams: list[str]):
        self.metadata = metadata
        self._streams = streams

    def keys(self):
        return list(self._streams)


class FakeCatalog:
    def __init__(self, runs: dict[str, FakeRun]):
        self._runs = runs
        self.last_query = None

    def search(self, query: Any):
        self.last_query = query
        # For unit tests we don't implement filtering logic; assume server did it.
        return self

    def keys(self):
        return list(self._runs.keys())

    def __getitem__(self, uid: str):
        return self._runs[uid]


def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def test_tiled_source_sync_populates_model_and_health():
    uid = "container-uid"
    md = {
        "start": {"time": 1000.0, "uid": uid, "plan_name": "scan"},
        "stop": {"time": 1010.0, "exit_status": "success"},
    }
    cat = FakeCatalog({uid: FakeRun(md, streams=["primary", "baseline"])})
    model = TimelineModel()

    src = TiledSource(client=cat, lookback_hours=48, include_incomplete=True)
    now = _dt(2000.0)
    src.sync(model, now=now)

    assert model.health_tiled.connected is True
    assert model.health_tiled.last_error is None
    assert uid in model.runs

    env = model.runs[uid]
    assert env.status == RunStatus.SUCCESS
    assert env.t_stop is not None
    assert env.streams_present == {"primary", "baseline"}


def test_tiled_source_respects_include_incomplete_false():
    uid = "u1"
    md = {"start": {"time": 1000.0, "uid": uid, "plan_name": "scan"}}
    cat = FakeCatalog({uid: FakeRun(md, streams=["primary"])})
    model = TimelineModel()

    src = TiledSource(client=cat, lookback_hours=48, include_incomplete=False)
    src.sync(model, now=_dt(2000.0))

    assert uid not in model.runs


def test_tiled_source_calls_search_with_timerange():
    uid = "u1"
    md = {
        "start": {"time": 1000.0, "uid": uid, "plan_name": "scan"},
        "stop": {"time": 1010.0, "exit_status": "success"},
    }
    cat = FakeCatalog({uid: FakeRun(md, streams=["primary"])})
    model = TimelineModel()

    src = TiledSource(client=cat, lookback_hours=48, include_incomplete=True)
    src.sync(model, now=_dt(2000.0))

    assert cat.last_query is not None
    q = cat.last_query
    assert isinstance(q, TimeRange)
    # Optional: only assert if attributes exist
    if hasattr(q, "since") and hasattr(q, "until"):
        assert q.since == pytest.approx(_dt(2000.0).timestamp() - 48 * 3600)
        assert q.until == pytest.approx(_dt(2000.0).timestamp())


def test_tiled_source_sync_handles_missing_stop_time_as_incomplete():
    uid = "u1"
    md = {"start": {"time": 1000.0, "uid": uid, "plan_name": "scan"}}
    cat = FakeCatalog({uid: FakeRun(md, streams=["primary"])})
    model = TimelineModel()

    src = TiledSource(client=cat, lookback_hours=48, include_incomplete=True)
    src.sync(model, now=_dt(2000.0))

    assert uid in model.runs
    env = model.runs[uid]
    assert env.status == RunStatus.INCOMPLETE
    assert env.t_stop is None
    assert env.streams_present == {"primary"}


def test_tiled_source_sync_handles_empty_streams_as_empty_set():
    uid = "u1"
    md = {
        "start": {"time": 1000.0, "uid": uid, "plan_name": "scan"},
        "stop": {"time": 1010.0, "exit_status": "success"},
    }
    cat = FakeCatalog({uid: FakeRun(md, streams=[])})
    model = TimelineModel()

    src = TiledSource(client=cat, lookback_hours=48, include_incomplete=True)
    src.sync(model, now=_dt(2000.0))

    assert uid in model.runs
    env = model.runs[uid]
    assert env.streams_present == set()