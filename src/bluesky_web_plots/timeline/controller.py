from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

import pandas as pd

from .bootstrap import create_timeline_model
from .config import RootConfig, TrackConfig
from .dataframe import build_timeline_df
from .live_source import LiveSourceEngine
from .models import TimelineModel
from .tiled_source import TiledSource


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TimelineUIState:
    selected_uid: Optional[str] = None
    cursor_time: Optional[datetime] = None


class TimelineController:
    """
    Owns the TimelineModel and coordinates sources + projections.

    Dash callbacks should interact with this controller, not with sources directly.
    """

    def __init__(self, *, cfg: RootConfig, tiled_catalog: Any):
        self.cfg = cfg
        self.model: TimelineModel = create_timeline_model(cfg)

        # Sources
        self.tiled = TiledSource(
            client=tiled_catalog,
            lookback_hours=cfg.sources.tiled.lookback_hours,
            include_incomplete=cfg.sources.tiled.include_incomplete,
        )
        self.live_engine = LiveSourceEngine(model=self.model)

        # Provenance: uid -> "tiled"|"live"
        # (tiled overrides live once seen)
        self.source_for_uid: dict[str, str] = {}

        # Poll cadence bookkeeping
        self._last_tiled_poll: Optional[datetime] = None

        # Track display cap
        self.max_tracks_shown: int = 6

    def tick(self, *, now: Optional[datetime] = None) -> None:
        """
        Periodic housekeeping:
          - Poll Tiled according to poll_interval_ms
        """
        now = now or _utc_now()

        if not self.cfg.sources.tiled.enabled:
            return

        poll_ms = self.cfg.sources.tiled.poll_interval_ms
        poll_s = poll_ms / 1000.0

        if self._last_tiled_poll is None or (now - self._last_tiled_poll).total_seconds() >= poll_s:
            before = set(self.model.runs.keys())
            self.tiled.sync(self.model, now=now)
            after = set(self.model.runs.keys())
            new_or_updated = after | before  # conservative

            # Mark anything present after sync as tiled
            for uid in after:
                self.source_for_uid[uid] = "tiled"

            self._last_tiled_poll = now

    def tracks_to_show(self) -> list[TrackConfig]:
        tracks = list(self.cfg.tracks)

        # Respect config ordering if provided
        order = list(self.cfg.timeline.track_order)
        if order:
            order_index = {tid: i for i, tid in enumerate(order)}
            tracks.sort(key=lambda t: order_index.get(t.id, 10_000))

        return tracks[: self.max_tracks_shown]

    def build_combined_df(
        self,
        *,
        now: datetime,
        show_sources: set[str],
        window_hours: float,
    ) -> pd.DataFrame:
        """
        Build a combined DF for up to N tracks stacked in one graph.
        """
        parts: list[pd.DataFrame] = []
        for track in self.tracks_to_show():
            df = build_timeline_df(
                model=self.model,
                track=track,
                now=now,
                window_hours=window_hours,
                show_sources=show_sources,
                source_for_uid=self.source_for_uid,
            )
            if df.empty:
                continue

            # Make lanes unique across tracks
            df = df.copy()
            df["lane"] = df["lane"].astype(str).map(lambda s: f"[{track.id}] {s}")
            parts.append(df)

        if not parts:
            # Return empty DF with correct columns inferred from build_timeline_df’s schema
            return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

        out = pd.concat(parts, ignore_index=True)
        return out
