from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from event_model.documents import Event, EventDescriptor, EventPage, RunStart
from plotly import graph_objs as go

from bluesky_web_plots.structures.base_structure import Base

T = TypeVar("T", bound=(Base | None))


class BaseFigureCallback(ABC, Generic[T]):
    structure: T
    figure: go.Figure

    def __init__(self, structure: T):
        self.structure = structure

    @abstractmethod
    def run_start(self, document: RunStart):
        pass

    @abstractmethod
    def descriptor(self, document: EventDescriptor):
        pass

    @abstractmethod
    def event(self, document: Event):
        pass

    @abstractmethod
    def event_page(self, document: EventPage):
        pass
