from enum import StrEnum

from .base_structure import Base


class PlotAgainst(StrEnum):
    TIME = "TIME"
    SEQ_NUM = "SEQ_NUM"


class Scalar(Base):
    plot_against: PlotAgainst
