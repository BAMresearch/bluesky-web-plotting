import itertools
import logging
import threading
from queue import Queue

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, callback_context, dcc, html, no_update
from dash.dependencies import ALL
from flask import Flask

from bluesky_web_plots import __version__
from bluesky_web_plots.logger import logger


class PlotServer:
    def __init__(self, host: str = "0.0.0.0", port=8080, columns=2) -> None:
        self.HOST = host
        self.PORT = port
        self._columns = columns
        self.updated_plot_queue: Queue[tuple[tuple[str, ...], go.Figure]] = Queue()
        self._plots: dict[tuple[str, ...], go.Figure] = {}
        self._lock = threading.Lock()
        self.deleted_plot_queue = Queue()

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

    def add_widget(self, names: tuple[str, ...], figure: go.Figure):
        with self._lock:
            self._plots[names] = figure

    def _setup_layout(self):
        app = self._app

        def make_card(name, figure):
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

        app.layout = html.Div(
            [
                html.Div(
                    [
                        html.H1("Bluesky Web Plots"),
                        html.Div(
                            f"https://github.com/evvaaaa/bluesky-web-plotting version {__version__}",
                            style={
                                "opacity": 0.5,
                            },
                        ),
                    ],
                    style={
                        "display": "flex",
                        "flexDirection": "column",
                        "alignItems": "center",
                    },
                ),
                dcc.Interval(id="interval", interval=250, n_intervals=0),
                html.Div(id="plots-container"),
            ]
        )

        @app.callback(
            Output("plots-container", "children"),
            Input("interval", "n_intervals"),
            State("plots-container", "children"),
            prevent_initial_call=True,
        )
        def update_plots(n, children):
            logger.debug(f"Updated plots for the {n}th time.")
            with self._lock:
                while not self.updated_plot_queue.empty():
                    names, figure = self.updated_plot_queue.get()
                    self._plots[names] = figure

                columns = [[] for _ in range(self._columns)]
                columns_iter = itertools.cycle(columns)
                for names, fig in self._plots.items():
                    next(columns_iter).append(make_card(", ".join(names), fig))
                return dbc.Row(
                    [dbc.Col(column, width=12 // self._columns) for column in columns]
                )

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
            triggered_index = eval(triggered_id)["index"]
            with self._lock:
                plot_name = tuple(triggered_index.split(", "))
                self._plots.pop(plot_name, None)
                self.deleted_plot_queue.put(plot_name)
            # Rebuild the cards after deletion
            columns = [[] for _ in range(self._columns)]
            columns_iter = itertools.cycle(columns)
            for names, fig in self._plots.items():
                next(columns_iter).append(make_card(", ".join(names), fig))
            return dbc.Row(
                [dbc.Col(column, width=12 // self._columns) for column in columns]
            )
