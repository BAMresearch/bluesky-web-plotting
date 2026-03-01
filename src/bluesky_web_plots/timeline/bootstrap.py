from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import RootConfig
from .models import SourceHealth, TimelineModel, TimelineViewSettings


def create_timeline_model(cfg: RootConfig) -> TimelineModel:
    """
    Create the initial TimelineModel from validated config.

    This does not start background tasks (pollers / ZMQ dispatcher).
    It only produces a consistent initial in-memory state.
    """
    view = TimelineViewSettings(
        show_live=cfg.timeline.show.live,
        show_tiled=cfg.timeline.show.tiled,
        window_hours=cfg.timeline.default_window_hours,
    )

    health_live = SourceHealth(
        connected=False,
        last_update_time=None,
        last_error=None,
        details={
            "enabled": cfg.sources.live.enabled,
            "zmq_address": cfg.sources.live.zmq_address,
            "max_live_runs": cfg.sources.live.max_live_runs,
        },
    )

    health_tiled = SourceHealth(
        connected=False,
        last_update_time=None,
        last_error=None,
        details={
            "enabled": cfg.sources.tiled.enabled,
            "uri": cfg.sources.tiled.uri,
            "root": cfg.sources.tiled.root,
            "poll_interval_ms": cfg.sources.tiled.poll_interval_ms,
            "lookback_hours": cfg.sources.tiled.lookback_hours,
            "include_incomplete": cfg.sources.tiled.include_incomplete,
        },
    )

    return TimelineModel(
        runs={},
        selected_uid=None,
        view=view,
        health_live=health_live,
        health_tiled=health_tiled,
    )