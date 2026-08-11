# ==============================================================================
# REFACTOR NOTES:
# There's a lot of potential here with the CardLayout class, which definitely
# doesn't need to be a NamedTuple. Need to figure out what matplotlib is
# actually doing, because it's a huge performance hit.
#
# GOALS:
# [X] update type hints
# [X] assess external dependencies
# [ ] compact code
# ================================================
from dataclasses import dataclass
import math
from typing import NamedTuple 

from PIL import Image, ImageDraw
from enum import Enum

from src.measurements import Measurement, PixelMeasurement
from src.enums import Orientation, Registration

# [!] Enum? Dataclass?
# Registration mark constraints (in mm)
MAX_REG_LENGTH_MM = 20.0
MAX_REG_THICKNESS_MM = 1.0
MAX_REG_INSET_MM = 86.36
MIN_REG_LENGTH_MM = 5.0
MIN_REG_THICKNESS_MM = 0.5
MIN_REG_INSET_MM = 10.0
REG_PADDING_MM = 1.5  # Extra clearance around registration marks

# [!] Previously loaded from defaults.json
BORDERLESS_INSET_MM = 10
BORDERLESS_EXPANSION_MM = (MIN_REG_INSET_MM - BORDERLESS_INSET_MM) * 2

class PixelSize(NamedTuple):
    width: PixelMeasurement
    height: PixelMeasurement

# [!] Not currently used
@dataclass(frozen=True)
class Point:
    x: Measurement
    y: Measurement

    @property
    def values(self) -> tuple[float, float]:
        return (self.x.value, self.y.value)

@dataclass(frozen=True)
class PixelPoint:
    x: PixelMeasurement
    y: PixelMeasurement

    @property
    def values(self) -> tuple[int, int]:
        return (self.x.value, self.y.value)

# [!] Might need renaming to avoid confusion with Layout_Models
class PageLayout(NamedTuple):
    card_size: tuple[PixelMeasurement, PixelMeasurement]
    paper_size: tuple[PixelMeasurement, PixelMeasurement]
    x_pos: list[int]
    y_pos: list[int]
    max_length_mm: float 

class CornerMatrix(Enum):
    TOP_LEFT = (-1, 1)
    TOP_RIGHT = (1, 1)
    BOTTOM_LEFT = (-1, -1)
    BOTTOM_RIGHT = (1, -1)

def draw_reg_corner_lines(
    draw: ImageDraw.ImageDraw,
    x: PixelMeasurement,
    y: PixelMeasurement,
    length: PixelMeasurement,
    thickness: PixelMeasurement,
    x_dir: int,
    y_dir: int,
) -> None:
    points = [
        PixelPoint(x, y).values,
        PixelPoint(x - x_dir * length, y).values,
        PixelPoint(x - x_dir * length, y + y_dir * thickness).values,
        PixelPoint(x - x_dir * thickness, y + y_dir * thickness).values,
        PixelPoint(x - x_dir * thickness, y + y_dir * length).values,
        PixelPoint(x, y + y_dir * length).values,
    ]
    print(f"Drawing registration polygon: {points}")
    draw.polygon(points, fill="black")

def generate_reg_mark(
    paper_width: Measurement,
    paper_height: Measurement,
    inset: Measurement,
    thickness: Measurement,
    length: Measurement,
    dpi: int,
    registration: Registration,
) -> Image.Image:

    # [!] Refactor: matplotlib -> PIL
    # [!] Pillow measures in px, MPL in mm.
    print("Generating Registration Marks")

    # Normalize units to pixel
    paper_width = paper_width.px(dpi)
    paper_height = paper_height.px(dpi)
    inset = inset.px(dpi)
    thickness = thickness.px(dpi)
    length = length.px(dpi)

    min_reg_length = Measurement.from_value(MIN_REG_LENGTH_MM, "mm").px(dpi)
    max_reg_length = Measurement.from_value(MAX_REG_LENGTH_MM, "mm").px(dpi)
    min_reg_thickness = Measurement.from_value(MIN_REG_THICKNESS_MM, "mm").px(dpi)
    max_reg_thickness = Measurement.from_value(MAX_REG_THICKNESS_MM, "mm").px(dpi)
    max_reg_inset = Measurement.from_value(MAX_REG_INSET_MM, "mm").px(dpi)

    # Constrain registration mark parameters within valid ranges.
    length = max(min_reg_length, min(length, max_reg_length))
    thickness = max(min_reg_thickness, min(thickness, max_reg_thickness))
    inset = min(inset, max_reg_inset)

    # Create image sized to the paper dimensions
    img = Image.new("RGB", (int(paper_width.value), int(paper_height.value)), "white")
    draw = ImageDraw.Draw(img)

    # Corners to draw L's on.
    render_corners = [CornerMatrix.BOTTOM_LEFT, CornerMatrix.TOP_RIGHT]

    if registration == Registration.THREE:
        five = Measurement.parse("5mm").px(dpi)
        coords = [ 
            PixelPoint(inset, inset).values, 
            PixelPoint(inset + five, inset + five).values 
        ]
        print(f"Reg.THREE detected. Drawing rectangle at {coords}")
        draw.rectangle(
            coords,
            fill="black",
            outline=None,
            width=thickness.value,
        )

    else:  # Registration.FOUR
        render_corners.append(CornerMatrix.TOP_LEFT)
        render_corners.append(CornerMatrix.BOTTOM_RIGHT)

    for corner in render_corners:
        print(f"Drawing corner: {corner.value}")
        x_dir, y_dir = corner.value
        x = inset if x_dir < 0 else paper_width - inset
        y = inset if y_dir > 0 else paper_height - inset

        draw_reg_corner_lines(
            draw,
            x=x,
            y=y,
            length=length,
            thickness=thickness,
            x_dir=x_dir,
            y_dir=y_dir,
        )
    return img


"""
Card layout computation with strict registration-mark corner exclusion.

This module computes card positions on a page while respecting:
- paper orientation
- bleed spacing between cards
- Silhouette registration mark inset
- square corner exclusion zones where NOTHING may appear
  (neither cards nor bleed)

If no valid layout fits without intruding into corner zones,
layout generation FAILS explicitly.

────────────────────────────────────────────────────────────────────────────
TERMINOLOGY

paper edge
┌─────────────────────────────────────┐
│ inset                               │
│   ┌──────────────┐                  │
│   │ corner zone  │ ← corner_len     │
│   └──────────────┘                  │
│                                     │
│        usable area                  │
│   ┌─────────────────────────────┐   │
│   │   bleed | card | bleed      │   │
│   │   bleed | card | bleed      │   │
│   └─────────────────────────────┘   │
└─────────────────────────────────────┘

Definitions:
- inset: distance from paper edge to registration marks
- corner_len: how far registration marks extend inward
- corner zone: square (corner_len × corner_len) at each corner
- usable area: page minus margins
- grid: cards PLUS surrounding bleed (entire grid must avoid corner zones)
"""

# ─────────────────────────────────────────────────────────────────────────────
# 1. Normalize page size for orientation
# ─────────────────────────────────────────────────────────────────────────────


def normalize_page_size(
    orientation: Orientation,
    paper_size: tuple[PixelMeasurement, PixelMeasurement],
) -> tuple[PixelMeasurement, PixelMeasurement]:
    """
    layouts.json stores paper sizes as landscape (width > height).
    Portrait swaps width and height; card dimensions are never swapped.
    """
    if orientation == Orientation.PORTRAIT:
        return paper_size[1], paper_size[0]
    return paper_size


# ─────────────────────────────────────────────────────────────────────────────
# 2. Compute how many cards fit along one axis
# ─────────────────────────────────────────────────────────────────────────────


def compute_grid_fit(
    usable: PixelMeasurement,
    card: PixelMeasurement,
    bleed: PixelMeasurement,
) -> int:
    """
    Compute how many cards fit along a single dimension.

    | bleed | card | bleed | card | bleed |
      ^---------------------------------^ usable

    But bleed can extend beyond the usable area. Only cards must be in the usable area.

    n cards require:
        n * card + (n - 1) * bleed

    so:
        n <= (usable + bleed) / (card + bleed)
    """
    if usable <= 0:
        return 0
    return max(0, math.floor((usable + bleed) / (card + bleed)))



# ─────────────────────────────────────────────────────────────────────────────
# 3. Select margins that avoid corner exclusion zones
# ─────────────────────────────────────────────────────────────────────────────


def select_best_margins(
    page_size: tuple[PixelMeasurement, PixelMeasurement],
    card_size: tuple[PixelMeasurement, PixelMeasurement],
    bleed: PixelMeasurement,
    inset: PixelMeasurement,
    corner_len: PixelMeasurement,
) -> tuple[int, int, tuple[PixelMeVasurement, PixelMeasurement],tuple[PixelMeasurement, PixelMeasurement]]:
    """
    Try margin strategies and select the one that:
    - keeps the ENTIRE grid (cards + bleed) out of corner zones
    - fits the maximum number of cards

    Returns:
        (cols, rows, margin_x, margin_y, usable_width, usable_height)

    Failure:
        Raises ValueError if no valid layout exists.

    Corner rule:
    A layout overlaps a corner zone if the grid intrudes within corner_len
    of the inset boundary on BOTH axes simultaneously.

    For each margin strategy, three candidate (cols, rows) counts are tried:
      1. (max_cols, max_rows) — maximum cards.
      2. (cols_clear, max_rows) — reduce cols until x gap clears the corner zone.
      3. (max_cols, rows_clear) — reduce rows until y gap clears the corner zone.
    Candidates 2 and 3 are symmetric: each shrinks one axis just enough to
    guarantee clearance on that axis, leaving the other axis at its maximum.
    """

    strategies = [
        (inset, inset),  # minimal margins
        (inset + corner_len, inset),  # clear corners horizontally
        (inset, inset + corner_len),  # clear corners vertically
    ]

    best = None
    best_count = 0

    def record_if_valid(
        cols: int,
        rows: int,
        margins: tuple[PixelMeasurement, PixelMeasurement], 
        usable_size: tuple[PixelMeasurement, PixelMeasurement],
    ) -> None:

        nonlocal best, best_count
        if cols <= 0 or rows <= 0:
            return
        grid_width = cols * card_size[0] + (cols + 1) * bleed
        grid_height = rows * card_size[1] + (rows + 1) * bleed
        gap_x = margins[0] + (usable_size[0] - grid_width) / 2 - inset
        gap_y = margins[1] + (usable_size[1] - grid_height) / 2 - inset
        if gap_x < corner_len and gap_y < corner_len:
            return
        count = cols * rows
        if count > best_count:
            best_count = count
            best = (cols, rows, margins, usable_size)

    for margin_x, margin_y in strategies:
        usable_width = page_width - 2 * margin_x
        usable_height = page_height - 2 * margin_y

        max_cols = compute_grid_fit(usable_width, card_width, bleed)
        max_rows = compute_grid_fit(usable_height, card_height, bleed)

        if max_cols == 0 or max_rows == 0:
            continue

        # Candidate 1: (max_cols, max_rows)
        record_if_valid(
            max_cols, max_rows, margin_x, margin_y, usable_width, usable_height
        )

        # Candidates 2 and 3: shrink one axis until that axis clears the corner zone.
        # Derived from gap >= corner_len:
        #   gap_x = margin_x + (usable_w - cols*(cw+b) - b)/2 - inset >= corner_len
        #   → cols <= (usable_w - b - 2*(corner_len - margin_x + inset)) / (cw+b)
        # (same formula for rows/y by symmetry)
        cols_clear = max(
            0,
            math.floor(
                (usable_width - bleed - 2 * (corner_len - margin_x + inset))
                / (card_width + bleed)
            ),
        )
        rows_clear = max(
            0,
            math.floor(
                (usable_height - bleed - 2 * (corner_len - margin_y + inset))
                / (card_height + bleed)
            ),
        )
        record_if_valid(
            cols_clear, max_rows, margin_x, margin_y, usable_width, usable_height
        )  # candidate 2
        record_if_valid(
            max_cols, rows_clear, margin_x, margin_y, usable_width, usable_height
        )  # candidate 3

    if best is None:
        raise ValueError(
            "No valid layout fits without intruding into corner exclusion zones."
        )

    return best


# ─────────────────────────────────────────────────────────────────────────────
# 4. Compute centered card positions
# ─────────────────────────────────────────────────────────────────────────────

def compute_card_positions(
    cols: int,
    rows: int,
    card_width: int,
    card_height: int,
    bleed: int,
    margin_x: int,
    margin_y: int,
    usable_width: int,
    usable_height: int,
) -> tuple[list[int], list[int], int, int]:
    """
    Center the card grid within the usable area and return positions.
    """

    grid_width = cols * card_width + (cols + 1) * bleed
    grid_height = rows * card_height + (rows + 1) * bleed

    start_x = round(margin_x + (usable_width - grid_width) / 2 + bleed)
    start_y = round(margin_y + (usable_height - grid_height) / 2 + bleed)

    x_pos = [start_x + i * (card_width + bleed) for i in range(cols)]
    y_pos = [start_y + j * (card_height + bleed) for j in range(rows)]

    return x_pos, y_pos, start_x, start_y


def generate_layout(
    orientation: Orientation,
    card_size: tuple[PixelMeasurement, PixelMeasurement],
    paper_size: tuple[PixelMeasurement, PixelMeasurement],
    inset: PixelMeasurement,
    length: PixelMeasurement,
):
    """
    Compute card positions on a page, accounting for margins, bleed,
    orientation, and strict registration mark corner exclusion zones.

    Raises:
        ValueError if no valid layout exists.
    """

    # Equivalent to double the bleed
    CARD_DISTANCE = "1.25mm"

    # Convert all dimensions to pixels
    ppi = paper_size[0].ppi
    card_distance = Measurement.parse(CARD_DISTANCE).px(ppi)

    # Normalize orientation
    page_size = normalize_page_size(orientation, paper_size)

    # Select margins and grid size (strict — no fallback)
    cols, rows, margins, usable_area = select_best_margins(
        page_size,
        card_size,
        card_distance,
        inset,
        length,
    )

    # Compute card positions
    x_pos, y_pos, start_x, start_y = compute_card_positions(
        cols,
        rows,
        card_width_px,
        card_height_px,
        card_distance_px,
        margin_x,
        margin_y,
        usable_w,
        usable_h,
    )

    # Maximum registration mark length that fits with a bleed safety buffer
    max_length_px = max(
        0, max(start_x - inset_px, start_y - inset_px) - card_distance_px
    )
    max_length_mm = round(max_length_px * 25.4 / ppi, 2)

    return PageLayout(
        card_width = card_width,
        card_height = card_height,
        paper_width = page_width,
        paper_height = page_height,
        x_pos = x_pos,
        y_pos = y_pos,
        max_length = max_length,
    )

    
