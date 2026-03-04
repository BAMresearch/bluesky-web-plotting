from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


ColorBy = Literal["status", "lane"]


def _ensure_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_ts(dt: datetime) -> str:
    dt = _ensure_aware_utc(dt)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def make_timeline_figure(
    df: pd.DataFrame,
    *,
    selected_uid: Optional[str] = None,
    cursor_time: Optional[datetime] = None,
    color_by: ColorBy = "status",
    title: str = "Bluesky runs timeline",
    show_legend: bool = False,
) -> go.Figure:
    """
    NLE-like timeline using numeric lane indices for robust overlays.

    Expects at least: uid, lane, t0, t1, status, streams, duration_s.
    """
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(
            title=title,
            xaxis_title="Time (UTC)",
            yaxis_title="",
            height=400,
            uirevision="timeline",
        )
        return fig

    d = df.copy()
    d["t0"] = pd.to_datetime(d["t0"], utc=True)
    d["t1"] = pd.to_datetime(d["t1"], utc=True)
    d["lane"] = d["lane"].astype(str)

    # Stable lane order
    lane_order = list(dict.fromkeys(d["lane"].tolist()))
    if not lane_order:
        lane_order = sorted(d["lane"].unique().tolist())

    lane_to_idx = {lane: i for i, lane in enumerate(lane_order)}
    d["lane_idx"] = d["lane"].map(lane_to_idx).astype(int)

    color_col = "status" if color_by == "status" else "lane"

    # hover_data must only reference existing columns
    hover_data: dict[str, object] = {
        "uid": True,
        "status": True,
        "streams": True,
        "duration_s": ":.3f",
        "t0": True,
        "t1": True,
    }
    for optional in ("track_id", "source"):
        if optional in d.columns:
            hover_data[optional] = True

    fig = px.timeline(
        d,
        x_start="t0",
        x_end="t1",
        y="lane_idx",
        color=color_col,
        hover_data=hover_data,
        custom_data=["uid", "lane", "t0", "t1"],  # makes Dash click handling robust
    )

    # Y-axis tick labels are the lane names
    fig.update_yaxes(
        title="",
        autorange="reversed",
        tickmode="array",
        tickvals=list(range(len(lane_order))),
        ticktext=lane_order,
        range=[len(lane_order) - 0.5, -0.5],
    )

    fig.update_xaxes(
        title="Time (UTC)",
        showgrid=True,
        rangeslider=dict(visible=True),
    )

    fig.update_layout(
        title=title,
        showlegend=show_legend,
        bargap=0.25,
        hoverlabel=dict(namelength=-1),
        margin=dict(l=20, r=20, t=40, b=20),
        height=max(420, 140 + 35 * len(lane_order)),
        # Preserve zoom and range-slider window across periodic refresh callbacks.
        uirevision="timeline",
    )

    # Selection overlay: rectangle band around selected clip on its lane
    if selected_uid:
        sel = d.loc[d["uid"].astype(str) == str(selected_uid)]
        if not sel.empty:
            r = sel.iloc[0]
            x0 = r["t0"].to_pydatetime()
            x1 = r["t1"].to_pydatetime()
            y = int(r["lane_idx"])
            y0 = y - 0.4
            y1 = y + 0.4

            fig.add_shape(
                type="rect",
                x0=x0,
                x1=x1,
                y0=y0,
                y1=y1,
                xref="x",
                yref="y",
                line=dict(width=3),
                fillcolor="rgba(0,0,0,0)",  # transparent fill
                layer="above",
            )

    # Cursor / playhead overlay: vertical line across all lanes + marker label
    if cursor_time is not None:
        ct = _ensure_aware_utc(cursor_time)

        fig.add_shape(
            type="line",
            x0=ct,
            x1=ct,
            y0=-0.5,
            y1=len(lane_order) - 0.5,
            xref="x",
            yref="y",
            line=dict(width=2),
            layer="above",
        )

        fig.add_annotation(
            x=ct,
            y=-0.5,
            xref="x",
            yref="y",
            text=_format_ts(ct),
            showarrow=True,
            arrowhead=2,
            ax=0,
            ay=25,
        )

    return fig
