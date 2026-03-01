from __future__ import annotations
import pytest


def test_run_envelope_running_invariant():
    from datetime import datetime, timezone
    from bluesky_web_plots.timeline.models import RunEnvelope, RunStatus

    t0 = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        RunEnvelope(uid="x", t_start=t0, t_stop=t0, status=RunStatus.RUNNING)