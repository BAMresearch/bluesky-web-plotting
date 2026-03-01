from __future__ import annotations

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc


def make_timeline_layout() -> html.Div:
    """
    Layout only. No controller access here.
    """
    return html.Div(
        [
            # Top bar
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Checklist(
                            id="timeline-source-toggles",
                            options=[
                                {"label": "Tiled", "value": "tiled"},
                                {"label": "Live", "value": "live"},
                            ],
                            value=["tiled", "live"],
                            inline=True,
                            switch=True,
                        ),
                        width="auto",
                    ),
                    dbc.Col(html.Div(id="timeline-badges"), width=True),
                ],
                align="center",
                className="mb-2",
            ),
            # Stores for UI state
            dcc.Store(
                id="timeline-ui-state",
                data={"selected_uid": None, "cursor_time": None},
            ),
            # Refresh timer
            dcc.Interval(id="timeline-refresh", interval=500, n_intervals=0),
            # Timeline graph
            dcc.Graph(
                id="timeline-graph",
                figure={},
                config={
                    "displayModeBar": True,
                    "scrollZoom": True,
                },
                style={"height": "70vh"},
            ),
        ],
        style={"padding": "10px"},
    )
