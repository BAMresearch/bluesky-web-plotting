from __future__ import annotations

from datetime import datetime, timezone

from bluesky_web_plots.timeline.predicates import parse_predicate


SAMPLE_RUN_MD = {
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

SAMPLE_CTX = {
    "uid": SAMPLE_RUN_MD["start"]["uid"],
    "start": SAMPLE_RUN_MD["start"],
    "stop": SAMPLE_RUN_MD["stop"],
    "streams": ["primary"],  # in Tiled you’d typically fill this from run.keys()
}


def test_eq_plan_name() -> None:
    p = parse_predicate({"field": "start.plan_name", "op": "eq", "value": "scan"}, path="p")
    assert p.evaluate(SAMPLE_CTX)


def test_not_exit_status_failure() -> None:
    p = parse_predicate({"not": {"field": "stop.exit_status", "op": "eq", "value": "success"}}, path="p")
    assert p.evaluate(SAMPLE_CTX) is False


def test_exists_missing() -> None:
    p = parse_predicate({"field": "start.proposal_id", "op": "exists"}, path="p")
    assert p.evaluate(SAMPLE_CTX) is False


def test_relative_time_window() -> None:
    # Pretend "now" is shortly after the run
    now = datetime.fromtimestamp(1772276595.0, tz=timezone.utc)

    p = parse_predicate({"field": "start.time", "op": "gte", "value": {"relative": "-24h"}}, path="p")
    assert p.evaluate(SAMPLE_CTX, now=now) is True

    p2 = parse_predicate({"field": "start.time", "op": "gte", "value": {"relative": "-1s"}}, path="p2")
    assert p2.evaluate(SAMPLE_CTX, now=now) is False