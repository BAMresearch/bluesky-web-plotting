from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional

import attrs


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    ABORTED = "aborted"
    FAILED = "failed"
    UNKNOWN = "unknown"
    INCOMPLETE = "incomplete"


def _details_default() -> dict[str, Any]:
    return {}


@attrs.define(slots=True)
class RunEnvelope:
    """
    Minimal run information needed for the timeline ("clip") and selection.

    Invariants:
      - If status == RUNNING: t_stop must be None
      - If t_stop is None: status should usually be RUNNING or INCOMPLETE/UNKNOWN
        (we enforce the first invariant strictly; the second is guidance)
    """
    uid: str
    t_start: datetime
    t_stop: Optional[datetime]
    status: RunStatus
    streams_present: set[str] = attrs.field(factory=set)

    start_doc: Optional[Mapping[str, Any]] = None
    stop_doc: Optional[Mapping[str, Any]] = None
    updated_at: Optional[datetime] = None

    def __attrs_post_init__(self) -> None:
        # Cross-field invariant
        if self.status == RunStatus.RUNNING and self.t_stop is not None:
            raise ValueError("RunEnvelope invariant violated: RUNNING run must have t_stop=None")



@attrs.define(slots=True)
class SourceHealth:
    """
    Used to drive top-bar status badges.
    """
    connected: bool
    last_update_time: Optional[datetime] = None
    last_error: Optional[str] = None
    details: dict[str, Any] = attrs.field(factory=_details_default)


@attrs.define(slots=True)
class TimelineViewSettings:
    show_live: bool = True
    show_tiled: bool = True
    window_hours: float = 12.0


@attrs.define(slots=True)
class TimelineModel:
    """
    Merged state consumed by the UI.

    - runs: union of Live + Tiled envelopes, keyed by run uid
    - selected_uid: which clip is currently selected
    - view: toggle states / window
    - health_*: status for badges
    """
    runs: dict[str, RunEnvelope] = attrs.field(factory=dict)
    selected_uid: Optional[str] = None
    view: TimelineViewSettings = attrs.field(factory=TimelineViewSettings)

    health_live: SourceHealth = attrs.field(factory=lambda: SourceHealth(connected=False))
    health_tiled: SourceHealth = attrs.field(factory=lambda: SourceHealth(connected=False))

    def get_selected(self) -> Optional[RunEnvelope]:
        if self.selected_uid is None:
            return None
        return self.runs.get(self.selected_uid)