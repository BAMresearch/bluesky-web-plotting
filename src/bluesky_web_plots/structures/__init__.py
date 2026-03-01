from plotly import graph_objs as go

from .array import Array as Array
from .base_structure import Base as Base
from .sample_map import SampleMap as SampleMap
from .scalar import Scalar as Scalar


def unpack_structures(
    *structures: Base, static_figures: dict[str, go.Figure] | None = None
):
    static_figures = static_figures or {}
    serialzed_static_figures = {n: v.to_json() for n, v in static_figures.items()}
    return {
        "BLUESKY_LIVE_PLOTS": {
            "STRUCTURES": structures,
            "SERIALISED_PLOT": serialzed_static_figures,
        }
    }
