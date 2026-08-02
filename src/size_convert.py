import re

MM_PER_INCH = 25.4
PT_PER_INCH = 72

_SIZE_PATTERN = re.compile(
    r"^(?P<value>(?:\d+\.\d*|\.\d+|\d+))(?P<unit>mm|in)?$"
)


def size_to_mm(size_string: str) -> float:
    match = _SIZE_PATTERN.fullmatch(size_string)

    if not match:
        raise ValueError(f"Invalid size format: {size_string}")

    value = float(match.group("value"))
    unit = match.group("unit")

    if unit == "in":
        return value * MM_PER_INCH

    # mm or no unit
    return value


def size_to_in(size_string: str) -> float:
    return size_to_mm(size_string) / MM_PER_INCH


def size_to_pt(size_string: str) -> float:
    return size_to_in(size_string) * PT_PER_INCH


def size_to_pixel(size_string: str, ppi: int) -> int:
    return round(size_to_in(size_string) * ppi)
