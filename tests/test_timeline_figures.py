from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from bluesky_web_plots.timeline.figures import make_timeline_figure


def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _df_one(uid: str = "u1") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "uid": uid,
                "lane": "scan",
                "t0": _dt(1000.0),
                "t1": _dt(1010.0),
                "status": "success",
                "streams": "primary",
                "duration_s": 10.0,
                "title": "scan",
                "subtitle": "",
            }
        ]
    )


def test_make_timeline_figure_empty():
    fig = make_timeline_figure(pd.DataFrame(), title="X")
    assert fig is not None
    assert hasattr(fig, "to_dict")


def test_make_timeline_figure_selection_adds_shape():
    df = _df_one("u1")
    fig = make_timeline_figure(df, selected_uid="u1")
    assert fig.layout.shapes is not None
    assert len(fig.layout.shapes) >= 1


def test_make_timeline_figure_cursor_adds_shape_and_annotation():
    df = _df_one("u1")
    ct = _dt(1005.0)
    fig = make_timeline_figure(df, cursor_time=ct)
    assert fig.layout.shapes is not None
    assert len(fig.layout.shapes) >= 1
    assert fig.layout.annotations is not None
    assert len(fig.layout.annotations) >= 1
