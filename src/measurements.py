#==============================================================================
# measurements.py 
#     Value + Unit string parsing and unit conversion. 
#==============================================================================

from collections.abc import Collection
import re


MM_PER_INCH = 25.4
PT_PER_INCH = 72
DEFAULT_PPI = 300 

_UNIT_PATTERN = re.compile(
    r"^(?P<amount>\d+(?:\.\d*)?|\.\d+)(?P<unit>[a-zA-Z%]+)?$"
)

def parse_measurement(measurement: str | None, valid_units: Collection[str]) -> tuple[float, str]:
    if not measurement: 
        return 0, "" 

    match = _UNIT_PATTERN.fullmatch(measurement.strip().lower())
 
    if not match:
        raise ValueError(f"Invalid unit format: {measurement}")

    amount = match["amount"]
    unit = match["unit"] or ""

    if valid_units and (unit not in valid_units):
        raise ValueError(f"Invalid unit: {measurement}. Valid units are {valid_units}")

    return float(amount), unit

def parse_to_mm(measurement: str | None) -> float:
    valid_units = ["","in","mm"]
    amount, unit = parse_measurement(measurement, valid_units)

    if unit == "in":
        return amount * MM_PER_INCH

    # mm or no unit
    return amount

def parse_to_in(measurement: str | None) -> float:
    return parse_to_mm(measurement) / MM_PER_INCH

def parse_to_pt(measurement: str) -> float:
    return parse_to_in(measurement) * PT_PER_INCH

def parse_to_px(measurement: str | None, ppi_scale: float = 1.0) -> int:
    return round(parse_to_in(measurement) * ppi_scale * DEFAULT_PPI)

