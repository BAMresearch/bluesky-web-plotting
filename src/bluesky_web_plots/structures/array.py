from enum import StrEnum

from .base_structure import Base


class View(StrEnum):
    SURFACE = "SURFACE"
    SLICE = "SLICE"


class Array(Base):
    view: View
