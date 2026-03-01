from __future__ import annotations

import json
from pathlib import Path

import pytest

from bluesky_web_plots.timeline.io import load_config
from bluesky_web_plots.timeline.predicates import ConfigError


def test_load_config_ok(tmp_path: Path) -> None:
    cfg = {
        "version": 1,
        "sources": {
            "live": {"enabled": True, "zmq_address": "tcp://localhost:5568"},
            "tiled": {"enabled": True, "uri": "http://localhost:8000", "root": "runs"},
        },
        "timeline": {"default_window_hours": 12, "show": {"live": True, "tiled": True}},
        "tracks": [
            {"id": "primary", "name": "Primary", "where": [], "group_by": {"field": "start.plan_name", "fallback": "x"}}
        ],
    }
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")

    loaded = load_config(p)
    assert loaded.version == 1
    assert loaded.sources.live.zmq_address == "tcp://localhost:5568"
    assert loaded.tracks[0].id == "primary"


def test_load_config_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{ not valid json", encoding="utf-8")

    with pytest.raises(ConfigError) as e:
        load_config(p)
    assert "invalid JSON" in str(e.value)


def test_duplicate_track_ids_rejected(tmp_path: Path) -> None:
    cfg = {
        "version": 1,
        "sources": {
            "live": {"enabled": True, "zmq_address": "tcp://localhost:5568"},
            "tiled": {"enabled": True, "uri": "http://localhost:8000", "root": "runs"},
        },
        "timeline": {"default_window_hours": 12, "show": {"live": True, "tiled": True}},
        "tracks": [
            {"id": "x", "name": "X", "where": [], "group_by": {"field": "start.plan_name", "fallback": "x"}},
            {"id": "x", "name": "X2", "where": [], "group_by": {"field": "start.plan_name", "fallback": "x"}},
        ],
    }
    p = tmp_path / "dup.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")

    with pytest.raises(ConfigError) as e:
        load_config(p)
    assert "duplicate track id" in str(e.value)


def test_unknown_operator_rejected(tmp_path: Path) -> None:
    cfg = {
        "version": 1,
        "sources": {
            "live": {"enabled": True, "zmq_address": "tcp://localhost:5568"},
            "tiled": {"enabled": True, "uri": "http://localhost:8000", "root": "runs"},
        },
        "timeline": {"default_window_hours": 12, "show": {"live": True, "tiled": True}},
        "tracks": [
            {
                "id": "primary",
                "name": "Primary",
                "where": {"field": "start.plan_name", "op": "nope", "value": "scan"},
                "group_by": {"field": "start.plan_name", "fallback": "x"},
            }
        ],
    }
    p = tmp_path / "op.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")

    with pytest.raises(ConfigError) as e:
        load_config(p)
    assert "unknown operator" in str(e.value)