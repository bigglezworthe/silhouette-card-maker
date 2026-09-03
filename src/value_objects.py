from typing import Any, NamedTuple, Self

Pixel = int
Millimeter = float
Inch = float
Point = float

class PPI(int):
    def __new__(cls, value: Any) -> Self:
        val = int(value)
        if val <= 0:
            raise ValueError("PPI must be positive")
        return super().__new__(cls, val)

class Percent(int):
    def __new__(cls, value: Any) -> Self:
        val = float(value)
        if not 0<=val<=100:
            raise ValueError("Percent must be between 0 and 100")
        return super().__new__(cls, val)

class GridPosition(NamedTuple):
    row: int
    col: int

    def __post_init__(self):
        if self.row < 0:
            raise ValueError("Row must be positive")
        if self.col < 0:
            raise ValueError("Column must e positive")

class PixelCoord(NamedTuple):
    x: Pixel
    y: Pixel

class PixelSize(NamedTuple):
    width: Pixel
    height: Pixel

    def __post_init__(self):
        if self.width < 0:
            raise ValueError("Width must be positive")
        if self.height < 0:
            raise ValueError("Height must e positive")

class PixelBox(NamedTuple):
    left: Pixel
    top: Pixel
    right: Pixel
    bottom: Pixel

    @property
    def size(self) -> PixelSize:
        return PixelSize(
            width = self.right - self.left,
            height = self.bottom - self.top,
        )
