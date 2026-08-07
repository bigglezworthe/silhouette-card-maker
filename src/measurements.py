# ==============================================================================
# measurements.py
#     Value + Unit string parsing and unit conversion.
# ==============================================================================

import re
from enum import Enum
from typing import Self
from dataclasses import dataclass

_UNIT_PATTERN = re.compile(r"^(?P<amount>\d+(?:\.\d*)?|\.\d+)(?P<unit>[a-zA-Z%]+)?$")

# Available units for conversion 
class ConvertUnits(str, Enum):
    NONE = ""
    MM = "mm"
    IN = "in"
    PX = "px"
    PT = "pt"

# Physical units for input 
class InputUnits(str, Enum):
    NONE = ConvertUnits.NONE.value
    MM = ConvertUnits.MM.value
    IN = ConvertUnits.IN.value
    PT = ConvertUnits.PT.value

DEFAULT_UNIT = ConvertUnits.MM
MM_PER_INCH = 25.4
PT_PER_INCH = 72

@dataclass(frozen=True, order=True)
class Measurement:
    mm: float

    @classmethod
    def parse(cls, measurement_str: str | None) -> Self:
        if measurement_str is None:
            return cls(0)

        match = _UNIT_PATTERN.fullmatch(measurement_str.strip().lower())

        if not match:
            raise ValueError(f"Invalid measurement format: {measurement_str}")

        amount = float(match["amount"])
        unit_string = match["unit"]

        if unit_string == "":
            unit = InputUnits.MM
        else:
            try:
                unit = InputUnits(unit_string)
            except ValueError:
                raise ValueError(f"Invalid unit: {unit_string}") from None

        return cls.from_value(amount, unit)

    @classmethod
    def from_value(cls, value: float, unit: InputUnits) -> Self:
        match unit:
            case InputUnits.MM:
                return cls(value)
            case InputUnits.IN:
                return cls(value * MM_PER_INCH)
            case InputUnits.PT:
                return cls(value / PT_PER_INCH * MM_PER_INCH)
            case _:
                raise ValueError(f"Unsupported unit: {unit}")

    @property
    def inches(self) -> float:
        return self.mm / MM_PER_INCH

    @property
    def points(self) -> float:
        return self.inches * PT_PER_INCH

    def pixels(self, ppi: int = 300) -> int:
        return round(self.inches * ppi)

def parse_unit_string(
    unit_string: str | None, valid_units: list[str]
) -> tuple[float, str]:
    if unit_string is None:
        return 0, ""

    match = _UNIT_PATTERN.fullmatch(unit_string.strip().lower())

    if not match:
        raise ValueError(f"Invalid unit format: {unit_string}")

    amount = match["amount"]
    unit = match["unit"] or ""

    if valid_units and (unit not in valid_units):
        raise ValueError(f"Invalid unit: {unit_string}. Valid units are {valid_units}")

    return float(amount), unit


def size_to_mm(size_string: str | None) -> float:
    valid_units = ["", "in", "mm"]
    amount, unit = parse_unit_string(size_string, valid_units)

    if unit == "in":
        return amount * MM_PER_INCH

    # mm or no unit
    return amount


def size_to_in(size_string: str | None) -> float:
    return size_to_mm(size_string) / MM_PER_INCH


def size_to_pt(size_string: str | None) -> float:
    return size_to_in(size_string) * PT_PER_INCH


def size_to_pixel(size_string: str | None, ppi: int) -> int:
    return round(size_to_in(size_string) * ppi)
