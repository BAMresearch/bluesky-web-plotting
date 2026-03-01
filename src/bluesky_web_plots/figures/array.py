from datetime import datetime

from event_model.documents import Event, EventDescriptor, EventPage, RunStart
from plotly import graph_objs as go

from bluesky_web_plots.structures.array import Array, View

from .base_figure import BaseFigureCallback


class ArrayFigureCallback(BaseFigureCallback[Array]):
    def __init__(self, structure: Array):
        self.structure = structure

        self.figure = go.Figure()
        self.figure.update_layout({"uirevision": "constant"})
        self._scan_id = 0

    def run_start(self, document: RunStart):
        self._scan_id = document.get("scan_id", document["uid"][4:])

    def descriptor(self, document: EventDescriptor):
        if self.structure["names"][0] not in document["data_keys"].keys():
            return
        data_key = document["data_keys"].get(self.structure["names"][0], {})
        shape = data_key.get("shape")
        if shape and self.structure["view"] == View.SLICE:
            self.figure.add_trace(go.Scatter(x=[], y=[], name=f"plan {self._scan_id}"))
        else:
            self.figure.add_trace(
                go.Surface(x=[], y=[], z=[], name=f"plan {self._scan_id}")
            )

    def event(self, document: Event):
        if self.structure["names"][0] not in document["data"].keys():
            return
        trace = self.figure.data[-1]
        received = document["data"][self.structure["names"][0]]
        if self.structure["view"] == View.SLICE:
            trace.x = tuple(range(len(received)))  # type: ignore
            trace.y = tuple(received)  # type: ignore
        else:
            trace.x += (datetime.fromtimestamp(document["time"]),)  # type: ignore
            for i, n in enumerate(received):
                trace.y += (i,)  # type: ignore
                trace.z += (n,)  # type: ignore

    def event_page(self, document: EventPage): ...
