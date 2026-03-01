from __future__ import annotations

import json
from pathlib import Path

from bluesky_web_plots.timeline.io import load_config
from bluesky_web_plots.timeline.bootstrap import create_timeline_model


def test_create_timeline_model_from_config(tmp_path: Path) -> None:
    cfg = {
        "version": 1,
        "sources": {
            "live": {"enabled": True, "zmq_address": "tcp://localhost:5568"},
            "tiled": {"enabled": True, "uri": "http://localhost:8000", "root": "runs"},
        },
        "timeline": {"default_window_hours": 6, "show": {"live": True, "tiled": False}},
        "tracks": [
            {"id": "primary", "name": "Primary", "where": [], "group_by": {"field": "start.plan_name", "fallback": "x"}}
        ],
    }
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")

    loaded = load_config(p)
    model = create_timeline_model(loaded)

    assert model.view.window_hours == 6
    assert model.view.show_live is True
    assert model.view.show_tiled is False

    assert model.health_live.details["zmq_address"] == "tcp://localhost:5568"
    assert model.health_tiled.details["uri"] == "http://localhost:8000"