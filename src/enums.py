# ==============================================================================
# enums.py
#     Enums live here.
# ==============================================================================
from enum import Enum


class Registration(str, Enum):
    THREE = "3"
    FOUR = "4"


# Paper orientation: portrait keeps cards upright, landscape rotates them 90 degrees.
class Orientation(str, Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class OrientationMode(str, Enum):
    """CLI orientation selection. OPTIMIZE tries both and picks the best."""

    OPTIMIZE = "optimize"
    LANDSCAPE = Orientation.LANDSCAPE.value
    PORTRAIT = Orientation.PORTRAIT.value


class Variant(str, Enum):
    DEFAULT = "default"
    BORDERLESS = "borderless"


class Unit(str, Enum):
    MM = "mm"
    IN = "in"


class FitMode(str, Enum):
    STRETCH = "stretch"
    CROP = "crop"


class CardSide(Enum):
    FRONT = "front"
    BACK = "back"

class CornerMatrix(Enum):
    TOP_LEFT = (-1, 1)
    TOP_RIGHT = (1, 1)
    BOTTOM_LEFT = (-1, -1)
    BOTTOM_RIGHT = (1, -1)

