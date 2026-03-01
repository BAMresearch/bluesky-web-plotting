# src/bluesky_web_plots/web_plots/server.py
from __future__ import annotations

import itertools
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from typing import Any, Optional

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, callback_context, dcc, html, no_update
from dash.dependencies import ALL
from flask import Flask

from bluesky_web_plots import __version__
from bluesky_web_plots.logger import logger

from bluesky_web_plots.timeline.controller import TimelineController
from bluesky_web_plots.timeline.dash_layout import make_timeline_layout
from bluesky_web_plots.timeline.figures import make_timeline_figure
from bluesky_web_plots.timeline.io import load_config


def _parse_cursor_time(x: Any) -> Optional[datetime]:
    """
    Plotly clickData x is usually an ISO string; convert to UTC datetime.
    """
    if x is None:
        return None
    if isinstance(x, datetime):
        dt = x
    else:
        try:
            dt = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class PlotServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8080, columns: int = 2) -> None:
        self.HOST = host
        self.PORT = port
        self._columns = columns

        self.updated_plot_queue: Queue[tuple[tuple[str, ...], go.Figure]] = Queue()
        self._plots: dict[tuple[str, ...], go.Figure] = {}
        self._lock = threading.Lock()
        self.deleted_plot_queue: Queue[tuple[str, ...]] = Queue()

        # Timeline bits (optional)
        self._timeline_controller: TimelineController | None = None
        self._timeline_lock = threading.Lock()

    def enable_timeline(self, *, config_path: str, tiled_catalog: Any) -> None:
        """
        Enable the Timeline tab.

        Parameters
        ----------
        config_path:
            Path to JSON config file.
        tiled_catalog:
            A Tiled 'runs catalog' object (in your setup: the client itself).
        """
        cfg = load_config(Path(config_path))
        self._timeline_controller = TimelineController(cfg=cfg, tiled_catalog=tiled_catalog)

    def add_widget(self, names: tuple[str, ...], figure: go.Figure) -> None:
        with self._lock:
            self._plots[names] = figure

    def run(self) -> None:
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.ERROR)

        server = Flask(__name__)
        self._app = Dash(
            title="Bluesky Web Plots",
            server=server,
            external_stylesheets=[dbc.themes.BOOTSTRAP],
            update_title=None,  # type: ignore
        )

        self._setup_layout()

        app_thread = threading.Thread(
            target=lambda: self._app.run(
                host=self.HOST,
                port=self.PORT,
                debug=False,
                use_reloader=False,
            ),
            daemon=True,
        )
        app_thread.start()

    def _setup_layout(self) -> None:
        app = self._app

        def make_card(name: str, figure: go.Figure) -> dbc.Card:
            return dbc.Card(
                [
                    dbc.CardHeader(
                        dbc.Row(
                            [
                                dbc.Col(html.H5(name)),
                                dbc.Col(
                                    dbc.Button(
                                        "Delete",
                                        id={"type": "delete-btn", "index": name},
                                        color="danger",
                                        size="sm",
                                        n_clicks=0,
                                    ),
                                    width="auto",
                                ),
                            ],
                            justify="between",
                        ),
                    ),
                    dbc.Collapse(
                        dcc.Graph(id={"type": "plot", "index": name}, figure=figure),
                        id={"type": "collapse", "index": name},
                        is_open=True,
                    ),
                ],
                style={"margin": "10px"},
            )

        header = html.Div(
            [
                html.H1("Bluesky Web Plots"),
                html.Div(
                    f"https://github.com/evvaaaa/bluesky-web-plotting version {__version__}",
                    style={"opacity": 0.5},
                ),
            ],
            style={
                "display": "flex",
                "flexDirection": "column",
                "alignItems": "center",
            },
        )

        plots_tab = dbc.Tab(
            label="Plots",
            tab_id="tab-plots",
            children=[
                dcc.Interval(id="interval", interval=250, n_intervals=0),
                html.Div(id="plots-container"),
            ],
        )

        timeline_children = (
            make_timeline_layout()
            if self._timeline_controller is not None
            else html.Div("Timeline not enabled.", style={"opacity": 0.7, "padding": "10px"})
        )
        timeline_tab = dbc.Tab(
            label="Timeline",
            tab_id="tab-timeline",
            children=[timeline_children],
        )

        tabs = dbc.Tabs(
            id="main-tabs",
            active_tab="tab-plots",
            children=[plots_tab, timeline_tab],
        )

        app.layout = html.Div([header, tabs])

        # -----------------------------
        # Plots tab callbacks (existing)
        # -----------------------------
        @app.callback(
            Output("plots-container", "children"),
            Input("interval", "n_intervals"),
            State("plots-container", "children"),
            prevent_initial_call=True,
        )
        def update_plots(n: int, children):
            logger.debug(f"Updated plots for the {n}th time.")
            with self._lock:
                while not self.updated_plot_queue.empty():
                    names, figure = self.updated_plot_queue.get()
                    self._plots[names] = figure

                columns = [[] for _ in range(self._columns)]
                columns_iter = itertools.cycle(columns)
                for names, fig in self._plots.items():
                    next(columns_iter).append(make_card(", ".join(names), fig))

                return dbc.Row([dbc.Col(column, width=12 // self._columns) for column in columns])

        @app.callback(
            Output("plots-container", "children", allow_duplicate=True),
            Input({"type": "delete-btn", "index": ALL}, "n_clicks"),
            State("plots-container", "children"),
            prevent_initial_call=True,
        )
        def delete_plot(n_clicks_list, children):
            ctx = callback_context
            if not ctx.triggered or all(n is None or n == 0 for n in n_clicks_list):
                return no_update

            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
            triggered_index = json.loads(triggered_id)["index"]

            with self._lock:
                plot_name = tuple(triggered_index.split(", "))
                self._plots.pop(plot_name, None)
                self.deleted_plot_queue.put(plot_name)

            # Rebuild the cards after deletion
            columns = [[] for _ in range(self._columns)]
            columns_iter = itertools.cycle(columns)
            for names, fig in self._plots.items():
                next(columns_iter).append(make_card(", ".join(names), fig))

            return dbc.Row([dbc.Col(column, width=12 // self._columns) for column in columns])

        # -----------------------------
        # Timeline tab callbacks (new)
        # -----------------------------
        if self._timeline_controller is None:
            return

        controller = self._timeline_controller

        @app.callback(
            Output("timeline-badges", "children"),
            Input("timeline-refresh", "n_intervals"),
        )
        def _update_badges(_: int):
            with self._timeline_lock:
                hl = controller.model.health_live
                ht = controller.model.health_tiled

            def badge(label: str, ok: bool, extra: str):
                color = "success" if ok else "secondary"
                return dbc.Badge(f"{label}: {extra}", color=color, className="me-2")

            return [
                badge("Live", hl.connected, "connected" if hl.connected else "disconnected"),
                badge("Tiled", ht.connected, "connected" if ht.connected else "disconnected"),
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

            show_sources = set(toggles or [])
            selected_uid = (ui_state or {}).get("selected_uid")

            cursor_time = _parse_cursor_time((ui_state or {}).get("cursor_time"))

            with self._timeline_lock:
                controller.tick(now=now)
                df = controller.build_combined_df(
                    now=now,
                    show_sources=show_sources,
                    window_hours=controller.model.view.window_hours,
                )

            return make_timeline_figure(
                df,
                selected_uid=selected_uid,
                cursor_time=cursor_time,
                color_by="status",
                title="Beamline timeline",
                show_legend=False,
            )
