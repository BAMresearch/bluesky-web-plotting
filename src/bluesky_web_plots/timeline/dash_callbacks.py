from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import dash
from dash import Input, Output, State, no_update
import dash_bootstrap_components as dbc

from .controller import TimelineController
from .figures import make_timeline_figure


def _parse_cursor_time(x: Any) -> Optional[datetime]:
    """
    Plotly clickData x is usually an ISO string; convert to UTC datetime.
    """
    if x is None:
        return None
    if isinstance(x, datetime):
        dt = x
    else:
        # plotly tends to pass ISO strings
        try:
            dt = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def register_timeline_callbacks(app: dash.Dash, *, controller: TimelineController) -> None:
    @app.callback(
        Output("timeline-badges", "children"),
        Input("timeline-refresh", "n_intervals"),
    )
    def _update_badges(_: int):
        hl = controller.model.health_live
        ht = controller.model.health_tiled

        def badge(label: str, ok: bool, extra: str):
            color = "success" if ok else "secondary"
            return dbc.Badge(f"{label}: {extra}", color=color, className="me-2")

        live_extra = "connected" if hl.connected else "disconnected"
        tiled_extra = "connected" if ht.connected else "disconnected"
        return [
            badge("Live", hl.connected, live_extra),
            badge("Tiled", ht.connected, tiled_extra),
        ]

    @app.callback(
        Output("timeline-ui-state", "data"),
        Input("timeline-graph", "clickData"),
        State("timeline-ui-state", "data"),
        prevent_initial_call=True,
    )
    def _on_timeline_click(click_data: Any, ui_state: dict):
        if not click_data or "points" not in click_data or not click_data["points"]:
            return no_update

        p0 = click_data["points"][0]
        # We set custom_data=["uid","lane","t0","t1"] in make_timeline_figure
        custom = p0.get("customdata") or []
        uid = custom[0] if len(custom) > 0 else None

        cursor_time = _parse_cursor_time(p0.get("x"))
        if cursor_time is None and len(custom) >= 3:
            cursor_time = _parse_cursor_time(custom[2])

        ui_state = dict(ui_state or {})
        ui_state["selected_uid"] = uid
        ui_state["cursor_time"] = cursor_time.isoformat() if cursor_time else None
        return ui_state

    @app.callback(
        Output("timeline-graph", "figure"),
        Input("timeline-refresh", "n_intervals"),
        Input("timeline-source-toggles", "value"),
        State("timeline-ui-state", "data"),
    )
    def _refresh_timeline(_: int, toggles: list[str], ui_state: dict):
        now = datetime.now(timezone.utc)

        # Poll Tiled on its cadence
        controller.tick(now=now)

        show_sources = set(toggles or [])
        window_hours = controller.model.view.window_hours  # from config bootstrap

        df = controller.build_combined_df(
            now=now,
            show_sources=show_sources,
            window_hours=window_hours,
        )

        selected_uid = (ui_state or {}).get("selected_uid")
        cursor_time_raw = (ui_state or {}).get("cursor_time")
        cursor_time = _parse_cursor_time(cursor_time_raw)

        fig = make_timeline_figure(
            df,
            selected_uid=selected_uid,
            cursor_time=cursor_time,
            color_by="status",
            title="Beamline timeline",
            show_legend=False,
        )
        return fig
