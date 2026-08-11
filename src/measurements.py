# ==============================================================================
# measurements.py
#     Value + Unit string parsing and unit conversion.
# 
# [!] NOTES: 
# This got a bit out of hand. It started as a simple unit conversion tool that
# carried magnitude but also retained unit. No more length_mm and length_px 
# being passed around. No more convert_to(<unit>) blocks at the top of 
# functions. Just nice, simple Measurements that could be passed around and 
# converted on the fly as needed. 
#
# Then came the initialization of JSON-loaded units and CLI args as Measurements,
# which vastly simplified a lot of existing code. Fantastic! But the shortcomings 
# of a sequential refactor came shortly after when reality struck that these 
# units aren't just sitting around looking pretty, they're here for math. 
#
# Measurements are completely unwieldy when it comes to basic arithmetic since 
# you can't add 2 classes. The answer seemed simple: z = x.value + y.value, done! 
# But z isn't a Measurement, so now that needs to be wrapped. Args were getting
# unpacked when entering a function, then repacked back into their Measurement-
# based structs on exiting. The return of length_px was back in full force.
#
# A fork in the road arrived where Measurements needed to be abandoned entirely 
# or Measurements need to natively support basic arithmetic. The current form 
# has decided to overload arithmetic operators. Hopefully it works out... (if
# you're reading this, it did!)
# ==============================================================================
# [!] CURRENTLY ASSUMES 300ppi FOR ALL ARITHMETIC OPS CONVERTING TO PIXEL
from __future__ import annotations
from collections.abc import Collection
import re
from enum import Enum
from typing import Self, override
from dataclasses import dataclass


_MEASUREMENT_PATTERN = re.compile(r"^(?P<quant>\d+(?:\.\d*)?|\.\d+)(?P<unit>[a-zA-Z%]+)?$")

DEFAULT_PPI = 300
MM_PER_INCH = 25.4
PT_PER_INCH = 72

# Physical units for input 
class MeasureUnits(str, Enum):
    MM = "mm"
    IN = "in"
    PT = "pt"
    PX = "px"
    PERCENT = "%"

DEFAULT_UNIT = MeasureUnits.MM 

@dataclass(frozen=True)
class Measurement:
    value: float = 0
    unit: MeasureUnits = DEFAULT_UNIT

    @staticmethod
    def _coerce_unit(unit: MeasureUnits | str, invalid_units: Collection[MeasureUnits] = ()) -> MeasureUnits:
        try: 
            if unit in invalid_units:
                raise ValueError
            return MeasureUnits(unit)
        except ValueError:
            units = ", ".join(u.value for u in MeasureUnits if u not in invalid_units)
            raise ValueError(f"Invalid unit: {unit}. Supported units: {units}") from None 


    @classmethod
    def parse(
        cls, 
        measurement_str: str,
        *,
        default_unit: MeasureUnits | str = DEFAULT_UNIT,
        invalid_units: Collection[MeasureUnits | str] = (),
    ) -> Self:

        invalid_units = {cls._coerce_unit(unit) for unit in invalid_units}
        default_unit = cls._coerce_unit(default_unit, invalid_units)

        match = _MEASUREMENT_PATTERN.fullmatch(measurement_str.strip().lower())

        if not match:
            raise ValueError(f"Invalid measurement format: {measurement_str}")

        amount = float(match["quant"])
        unit_string = match["unit"] or default_unit.value
        unit = cls._coerce_unit(unit_string, invalid_units)

        return cls(amount, unit)

    @classmethod
    def from_value(cls, value: float, unit: MeasureUnits | str) -> Self: 
        unit = cls._coerce_unit(unit)
        return cls(value, unit)

    def to(self, unit: MeasureUnits | str, ppi: int = DEFAULT_PPI) -> Self:
        unit = self._coerce_unit(unit)

        if self.unit == unit:
            return self

        value = self.value

        # convert to mm, then to whatever else 
        match self.unit:
            case MeasureUnits.MM:
                value = value * 1
            case MeasureUnits.IN:
                value = value * MM_PER_INCH
            case MeasureUnits.PT:
                value = value * MM_PER_INCH / PT_PER_INCH
            case MeasureUnits.PX:
                value = value * MM_PER_INCH / ppi
            case MeasureUnits.PERCENT:
                raise ValueError("Percentage measurements cannot be converted.")

        match unit:
            case MeasureUnits.MM:
                value = value / 1
            case MeasureUnits.IN: 
                value = value / MM_PER_INCH
            case MeasureUnits.PT:
                value = value / MM_PER_INCH * PT_PER_INCH
            case MeasureUnits.PX:
                value = value / MM_PER_INCH * ppi
            case MeasureUnits.PERCENT: 
                raise ValueError("Measurements cannot be converted to percentage.")

        return self.from_value(value, unit)

    def px(self, ppi: int = DEFAULT_PPI) -> Self:
        return round(self.to(MeasureUnits.PX, ppi))

    @override
    def __str__(self) -> str:
        return f"{self.value:g}{self.unit.value}"

    #==========================================================
    # MATH
    #==========================================================
    
    #============================
    # Arithmetic
    #============================
    
    def _coerce_other(self, other: object) -> Measurement | None:
        if not isinstance(other, Measurement):
            return None
        return other.to(self.unit)

    def __add__(self, other: object) -> Self:
        other = self._coerce_other(other)
        if other is None:
            return NotImplemented
        return self.from_value(self.value + other.value, self.unit)

    def __sub__(self, other: object) -> Self:
        other = self._coerce_other(other)
        if other is None:
            return NotImplemented
        return self.from_value(self.value - other.value, self.unit)

    def __mul__(self, other: object) -> Self:
        if not isinstance(other, (int, float)):
            return NotImplemented
        return self.from_value(self.value * other, self.unit)

    def __rmul__(self, other: object) -> Self:
        return self.__mul__(other)

    def __truediv__(self, other: object) -> Self | float:
        if isinstance(other, Measurement):
            return self.value / other.to(self.unit).value
        if isinstance(other, (int, float)):
            return self.from_value(self.value / other, self.unit)
        return NotImplemented

    #============================
    # Comparisons
    #============================

    def __lt__(self, other: object) -> bool:
        other = self._coerce_other(other)
        if other is None:
            return NotImplemented
        return self.value < other.value

    def __le__(self, other: object) -> bool:
        other = self._coerce_other(other)
        if other is None:
            return NotImplemented
        return self.value <= other.value

    def __gt__(self, other: object) -> bool:
        other = self._coerce_other(other)
        if other is None:
            return NotImplemented
        return self.value > other.value

    def __ge__(self, other: object) -> bool:
        other = self._coerce_other(other)
        if other is None:
            return NotImplemented
        return self.value >= other.value

    @override
    def __eq__(self, other: object) -> bool:
        try:
            other = self._coerce_other(other)
        except ValueError:
            return False

        if other is None:
            return False
        return self.value == other.value

    #============================
    # Rounding
    #============================

    def __round__(self, ndigits: int | None = None) -> Self:
        return self.from_value(round(self.value, ndigits), self.unit)

    
# [!] Not sure if this is useful. Might delete later.
def percent_of(part: str | Measurement, total: str | Measurement) -> Measurement:
    part = part if isinstance(part, Measurement) else Measurement.parse(part)
    total = total if isinstance(total, Measurement) else Measurement.parse(total)

    part_mm = part.to(MeasureUnits.MM).value
    total_mm = total.to(MeasureUnits.MM).value

    return Measurement.from_value(part_mm / total_mm * 100, MeasureUnits.PERCENT)





