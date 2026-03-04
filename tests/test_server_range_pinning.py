from __future__ import annotations

from datetime import datetime, timezone

from bluesky_web_plots.web_plots.server import (
    _should_pin_right_edge_to_now,
    _parse_xaxis_range,
)


def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def test_parse_xaxis_range_from_split_keys():
    x0, x1 = _parse_xaxis_range(
        {
            "xaxis.range[0]": "1970-01-01T00:00:00+00:00",
            "xaxis.range[1]": "1970-01-01T00:00:10+00:00",
        }
    )
    assert x0 == _dt(0.0)
    assert x1 == _dt(10.0)


def test_parse_xaxis_range_from_list_key():
    x0, x1 = _parse_xaxis_range(
        {
            "xaxis.range": [
                "1970-01-01T00:00:00+00:00",
                "1970-01-01T00:00:20+00:00",
            ]
        }
    )
    assert x0 == _dt(0.0)
    assert x1 == _dt(20.0)


def test_parse_xaxis_range_autorange():
    x0, x1 = _parse_xaxis_range({"xaxis.autorange": True})
    assert x0 is None
    assert x1 is None


def test_should_pin_right_edge_true_when_near_now():
    now = _dt(1000.0)
    x0 = _dt(900.0)
    x1 = _dt(995.0)
    assert _should_pin_right_edge_to_now(x0, x1, now=now) is True


def test_should_pin_right_edge_false_when_far_from_now():
    now = _dt(1000.0)
    x0 = _dt(900.0)
    x1 = _dt(700.0)
    assert _should_pin_right_edge_to_now(x0, x1, now=now) is False
