from enum import StrEnum

from .base_structure import Base


class ColorScale(StrEnum):
    """Look at me using american spelling and everything..."""

    VIRIDIS = "Viridis"
    CIVIDIS = "Cividis"
    PLASMA = "Plasma"
    INFERNO = "Inferno"
    MAGMA = "Magma"
    JET = "Jet"
    HOT = "Hot"
    COOL = "Cool"
    RAINBOW = "Rainbow"
    PORTLAND = "Portland"
    ELECTRIC = "Electric"
    EARTH = "Earth"
    BLACKBODY = "Blackbody"
    YLGNBU = "YlGnBu"
    YLORRD = "YlOrRd"
    BLUERED = "Bluered"
    RDBU = "RdBu"
    PICNIC = "Picnic"
    GREYS = "Greys"
    GREENS = "Greens"
    BLUES = "Blues"
    REDS = "Reds"
    PURPLES = "Purples"
    ORANGES = "Oranges"


class SampleMap(Base):
    """Simply takes names, it will do the rest :)"""

    intensity_data_key: str
    """Of the names given to the strucutre, which is the intensity datakey for the heatmap?"""

    color_scale: ColorScale
