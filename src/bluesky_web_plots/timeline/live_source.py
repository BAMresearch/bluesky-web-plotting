from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

import attrs

from .models import RunEnvelope, RunStatus, TimelineModel


def _ensure_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _dt_from_epoch(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except Exception:
        return None


def _status_from_stop(stop: Mapping[str, Any]) -> RunStatus:
    s = stop.get("exit_status")
    if s == "success":
        return RunStatus.SUCCESS
    if s == "abort":
        return RunStatus.ABORTED
    if s == "fail":
        return RunStatus.FAILED
    return RunStatus.UNKNOWN


@attrs.define(slots=True)
class LiveSourceEngine:
    """
    Maintain timeline state from live Bluesky documents.

    This class is transport-agnostic: ZMQ or in-process RE callbacks can feed it.
    """
    model: TimelineModel

    def on_doc(self, name: str, doc: Mapping[str, Any], *, received_at: Optional[datetime] = None) -> None:
        now = _ensure_aware_utc(received_at or datetime.now(timezone.utc))

        # health badge bookkeeping
        self.model.health_live.connected = True
        self.model.health_live.last_update_time = now
        self.model.health_live.last_error = None

        if name == "start":
            self._on_start(doc, now=now)
        elif name == "descriptor":
            self._on_descriptor(doc, now=now)
        elif name == "stop":
            self._on_stop(doc, now=now)
        else:
            # For timeline purposes, ignore everything else (event, event_page, datum, etc.)
            return

    def _on_start(self, doc: Mapping[str, Any], *, now: datetime) -> None:
        uid = doc.get("uid")
        if not uid:
            return

        t0 = _dt_from_epoch(doc.get("time")) or now

        env = RunEnvelope(
            uid=str(uid),
            t_start=t0,
            t_stop=None,
            status=RunStatus.RUNNING,
            streams_present=set(),
            start_doc=dict(doc),
            stop_doc=None,
            updated_at=now,
        )
        # live creates/overwrites — later tiled may override
        self.model.runs[str(uid)] = env

    def _on_descriptor(self, doc: Mapping[str, Any], *, now: datetime) -> None:
        run_start = doc.get("run_start")
        if not run_start:
            return
        uid = str(run_start)

        env = self.model.runs.get(uid)
        if env is None:
            # Descriptor arrived but we didn't see the start (possible if we subscribed late).
            # Create a minimal envelope so the run can still be displayed.
            env = RunEnvelope(
                uid=uid,
                t_start=now,
                t_stop=None,
                status=RunStatus.RUNNING,
                streams_present=set(),
                start_doc=None,
                stop_doc=None,
                updated_at=now,
            )
            self.model.runs[uid] = env

        stream_name = doc.get("name")
        if isinstance(stream_name, str) and stream_name:
            env.streams_present.add(stream_name)

        env.updated_at = now

    def _on_stop(self, doc: Mapping[str, Any], *, now: datetime) -> None:
        run_start = doc.get("run_start")
        if not run_start:
            return
        uid = str(run_start)

        env = self.model.runs.get(uid)
        if env is None:
            # stop arrived but we didn't see start; create best-effort envelope
            t1 = _dt_from_epoch(doc.get("time")) or now
            env = RunEnvelope(
                uid=uid,
                t_start=t1,  # unknown start; use stop time
                t_stop=t1,
                status=_status_from_stop(doc),
                streams_present=set(),
                start_doc=None,
                stop_doc=dict(doc),
                updated_at=now,
            )
            self.model.runs[uid] = env
            return

        t1 = _dt_from_epoch(doc.get("time")) or now
        env.t_stop = t1
        env.status = _status_from_stop(doc)
        env.stop_doc = dict(doc)
        env.updated_at = now
