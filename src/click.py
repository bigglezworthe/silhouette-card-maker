#==============================================================================
# src/click.py
#     Custom options for click
#==============================================================================

from collections.abc import Collection
from typing import override

import click
from src.measurements import DEFAULT_UNIT, MeasureUnits, Measurement

class MeasureType(click.ParamType):
    name: str = "measurement"

    def __init__(
        self, 
        default_unit: MeasureUnits | str = DEFAULT_UNIT, 
        invalid_units: Collection[MeasureUnits | str] = ()
    ) -> None:
        self.default_unit: MeasureUnits | str = default_unit
        self.invalid_units: Collection[MeasureUnits | str] = invalid_units

    @override
    def convert(
        self,
        value: str | Measurement, 
        param: click.Parameter | None, 
        ctx: click.Context | None
    ) -> Measurement:
        if isinstance(value, Measurement):
            return value

        try:
            return Measurement.parse(
                value,
                default_unit=self.default_unit,
                invalid_units=self.invalid_units,
            )
        except ValueError as exc:
            self.fail(str(exc), param, ctx)
