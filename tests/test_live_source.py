from __future__ import annotations

from datetime import datetime, timezone

from bluesky_web_plots.timeline.live_source import LiveSourceEngine
from bluesky_web_plots.timeline.models import RunStatus, TimelineModel


def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def test_live_start_creates_running_envelope():
    model = TimelineModel()
    engine = LiveSourceEngine(model=model)

    engine.on_doc("start", {"uid": "u1", "time": 1000.0, "plan_name": "scan"}, received_at=_dt(1001.0))

    env = model.runs["u1"]
    assert env.status == RunStatus.RUNNING
    assert env.t_stop is None
    assert env.start_doc is not None
    assert env.start_doc["plan_name"] == "scan"


def test_live_descriptor_adds_stream():
    model = TimelineModel()
    engine = LiveSourceEngine(model=model)

    engine.on_doc("start", {"uid": "u1", "time": 1000.0}, received_at=_dt(1000.0))
    engine.on_doc("descriptor", {"run_start": "u1", "name": "primary"}, received_at=_dt(1000.5))

    env = model.runs["u1"]
    assert "primary" in env.streams_present


def test_live_stop_finalizes_status_and_time():
    model = TimelineModel()
    engine = LiveSourceEngine(model=model)

    engine.on_doc("start", {"uid": "u1", "time": 1000.0}, received_at=_dt(1000.0))
    engine.on_doc("stop", {"run_start": "u1", "time": 1010.0, "exit_status": "success"}, received_at=_dt(1010.1))

    env = model.runs["u1"]
    assert env.status == RunStatus.SUCCESS
    assert env.t_stop == _dt(1010.0)
    assert env.stop_doc is not None
    assert env.stop_doc["exit_status"] == "success"


def test_live_descriptor_before_start_creates_minimal_envelope():
    model = TimelineModel()
    engine = LiveSourceEngine(model=model)

    engine.on_doc("descriptor", {"run_start": "u1", "name": "baseline"}, received_at=_dt(1000.0))

    env = model.runs["u1"]
    assert env.status == RunStatus.RUNNING
    assert "baseline" in env.streams_present


def test_live_stop_before_start_creates_completed_envelope():
    model = TimelineModel()
    engine = LiveSourceEngine(model=model)

    engine.on_doc("stop", {"run_start": "u1", "time": 1010.0, "exit_status": "fail"}, received_at=_dt(1010.0))

    env = model.runs["u1"]
    assert env.status == RunStatus.FAILED
    assert env.t_stop == _dt(1010.0)