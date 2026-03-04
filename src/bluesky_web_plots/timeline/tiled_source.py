from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Mapping, Optional

import attrs

from tiled.queries import Key

from .models import RunEnvelope, RunStatus, TimelineModel


def _ensure_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _status_from_stop(stop: Mapping[str, Any] | None) -> RunStatus:
    if not stop:
        return RunStatus.INCOMPLETE
    s = stop.get("exit_status")
    if s == "success":
        return RunStatus.SUCCESS
    if s == "abort":
        return RunStatus.ABORTED
    if s == "fail":
        return RunStatus.FAILED
    return RunStatus.UNKNOWN


@attrs.define(slots=True)
class TiledSource:
    """
    Polls a Tiled Runs catalog (client) and updates TimelineModel.

    'client' is the runs catalog directly in your setup.
    """
    client: Any
    lookback_hours: float
    include_incomplete: bool = True

    def sync(self, model: TimelineModel, *, now: datetime) -> None:
        now = _ensure_aware_utc(now)
        since = now - timedelta(hours=self.lookback_hours)

        try:
            # Server-side query for time window using generic key predicates.
            filtered = self.client.search(Key("start.time") >= since.timestamp()).search(
                Key("start.time") <= now.timestamp()
            )
            uids = list(filtered.keys())
        except Exception as e:
            model.health_tiled.connected = False
            model.health_tiled.last_error = str(e)
            model.health_tiled.last_update_time = now
            return

        model.health_tiled.connected = True
        model.health_tiled.last_error = None
        model.health_tiled.last_update_time = now

        for uid in uids:
            run = filtered[uid]
            md = getattr(run, "metadata", {}) or {}
            start = md.get("start", {}) or {}
            stop = md.get("stop", {}) or {}

            if "time" not in start:
                continue

            # Incomplete handling
            if (not self.include_incomplete) and ("time" not in stop):
                continue

            t_start = datetime.fromtimestamp(float(start["time"]), tz=timezone.utc)
            t_stop = None
            if "time" in stop:
                t_stop = datetime.fromtimestamp(float(stop["time"]), tz=timezone.utc)

            status = _status_from_stop(stop if "time" in stop else None)

            # Streams present (server-side read of run keys)
            try:
                streams_present = set(run.keys())
            except Exception:
                streams_present = set()

            env = RunEnvelope(
                uid=str(uid),
                t_start=t_start,
                t_stop=t_stop,
                status=status if t_stop is not None else (RunStatus.INCOMPLETE if status != RunStatus.SUCCESS else status),
                streams_present=streams_present,
                start_doc=start,
                stop_doc=stop if stop else None,
                updated_at=now,
            )

            # Tiled is canonical if present
            model.runs[str(uid)] = env
