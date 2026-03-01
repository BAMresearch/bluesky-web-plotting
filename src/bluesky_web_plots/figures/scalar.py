from datetime import datetime

from event_model.documents import Event, EventDescriptor, EventPage, RunStart
from plotly import graph_objs as go
from plotly.subplots import make_subplots

from bluesky_web_plots.structures.scalar import PlotAgainst, Scalar

from .base_figure import BaseFigureCallback


class ScalarFigureCallback(BaseFigureCallback[Scalar]):
    structure: Scalar

    def __init__(self, structure: Scalar):
        self.structure = structure
        self.figure = make_subplots(shared_xaxes=True)
        self.figure.update_layout({"uirevision": "constant"})

    def run_start(self, document: RunStart):
        self._scan_id = document.get("scan_id", document["uid"][4:])

    def descriptor(self, document: EventDescriptor):
        if self.structure["names"][0] not in document["data_keys"].keys():
            return
        data_key = document["data_keys"].get(self.structure["names"][0], {})

        self.figure.update_layout(
            dict(
                xaxis_title="Sequence Number"
                if self.structure["plot_against"] == PlotAgainst.SEQ_NUM
                else "Time",
                yaxis_title=data_key.get("units", "value"),
            )
        )

        self.figure.add_trace(
            go.Scatter(x=[], y=[], mode="lines+markers", name=f"plan {self._scan_id}")
        )

    def event(self, document: Event):
        if self.structure["names"][0] not in document["data"].keys():
            return
        if self.structure["plot_against"] == PlotAgainst.TIME:
            x = datetime.fromtimestamp(document["time"])
        else:
            x = document["seq_num"]

        y = document["data"][self.structure["names"][0]]
        trace = self.figure.data[-1]
        trace.x += (x,)  # type: ignore
        trace.y += (y,)  # type: ignore

    def event_page(self, document: EventPage):
        if self.structure["names"][0] not in document["data"].keys():
            return
        if self.structure["plot_against"] == PlotAgainst.TIME:
            x = [datetime.fromtimestamp(time) for time in document["time"]]
        else:
            x = document["seq_num"]

        y = document["data"][self.structure["names"][0]]
        trace = self.figure.data[-1]
        trace.x += tuple(x)  # type: ignore
        trace.y += tuple(y)  # type: ignore
