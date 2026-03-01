from event_model.documents import Event, EventDescriptor, EventPage, RunStart
from plotly import graph_objs as go
from plotly.subplots import make_subplots

from bluesky_web_plots.structures.sample_map import SampleMap

from ..logger import logger
from .base_figure import BaseFigureCallback


class SampleMapFigureCallback(BaseFigureCallback[SampleMap]):
    structure: SampleMap

    def __init__(self, structure: SampleMap):
        self.structure = structure
        self._z_data_key = structure["intensity_data_key"]
        x_y_data_keys = tuple(
            set(structure["names"])
            - {
                self._z_data_key,
            }
        )  # type: ignore
        if len(x_y_data_keys) != 2:
            logger.warning(
                "Received a request for a sample map with more than two x, y dimensions: "
                f"{x_y_data_keys}. Only the first two will be used."
            )
        self._x_data_key, self._y_data_key, *_ = list(x_y_data_keys)
        self.figure = make_subplots(x_title=self._x_data_key, y_title=self._y_data_key)
        self.figure.update_layout({"uirevision": "constant"})

    def _get_axis_template(self, name: str, min: float, max: float) -> dict:
        return dict(
            range=[min, max],
        )

    def run_start(self, document: RunStart):
        self._scan_id = document.get("scan_id", document["uid"][4:])
        self.figure.add_trace(
            go.Heatmap(
                x=[],
                y=[],
                z=[],
                colorscale=self.structure["color_scale"],
                name=f"plan {self._scan_id}",
            )
        )

    def descriptor(self, document: EventDescriptor):
        if (
            not set(self.structure["names"]) <= document["data_keys"].keys()
            or self.structure["intensity_data_key"] in document["data_keys"]
        ):
            return

        # We don't add the trace here since empty data would mean that the trace wouldn't
        # be accessible.

    def event(self, document: Event):
        if not set(self.structure["names"]) <= document["data"].keys():
            return

        new_x = document["data"][self._x_data_key]
        new_y = document["data"][self._y_data_key]
        new_z = document["data"][self._z_data_key]

        if self.figure.data:
            x = self.figure.data[-1].x + (new_x,)  # type: ignore
            y = self.figure.data[-1].y + (new_y,)  # type: ignore
            z = self.figure.data[-1].z + (new_z,)  # type: ignore
            self.figure.update_layout(
                xaxis=self._get_axis_template(self._x_data_key, min(x), max(x)),
                yaxis=self._get_axis_template(self._y_data_key, min(y), max(y)),
            )
            self.figure.data[-1].x = x  # type: ignore
            self.figure.data[-1].y = y  # type: ignore
            self.figure.data[-1].z = z  # type: ignore
        else:
            self.figure.add_trace(
                go.Heatmap(
                    x=[
                        new_x,
                    ],
                    y=[
                        new_y,
                    ],
                    z=[
                        new_z,
                    ],
                    colorscale=self.structure["color_scale"],
                    name=f"plan {self._scan_id}",
                )
            )
            self.figure.update_layout(
                xaxis=self._get_axis_template(
                    self._x_data_key, min(new_x, 0), max(new_x, 0)
                ),
                yaxis=self._get_axis_template(
                    self._y_data_key, min(new_y, 0), max(new_y, 0)
                ),
            )

        # trace = self.figure.data[-1]
        # trace.x += (x,)  # type: ignore
        # trace.y += (y,)  # type: ignore
        # trace.z += (z,)  # type: ignore

    def event_page(self, document: EventPage):
        if not set(self.structure["names"]) <= document["data"].keys():
            return

        x = document["data"][self._x_data_key]
        y = document["data"][self._y_data_key]
        z = document["data"][self._z_data_key]
        trace = self.figure.data[-1]
        trace.x += tuple(x)  # type: ignore
        trace.y += tuple(y)  # type: ignore
        trace.z += tuple(z)  # type: ignore
