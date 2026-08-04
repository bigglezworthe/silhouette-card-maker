# ==============================================================================
# images.py
#     Place images on the page and perform non-crop manipulations
# ==============================================================================
import math

from pathlib import Path
from PIL import Image, ImageOps

from src import measurements

# Approximately 1.25mm of bleed in px assuming 300ppi: ceil(1.25mm * 1in/25.4mm * 300px/1in)
MINIMUM_BLEED = 15


def calculate_max_print_bleed(
    x_pos: list[int],
    y_pos: list[int],
    width: int,
    height: int,
) -> tuple[int, int]:

    def max_bleed(positions: list[int], size: int) -> int:
        if len(positions) < 2:
            return MINIMUM_BLEED

        positions = sorted(positions)
        return max(0, math.ceil((positions[1] - positions[0] - size) / 2))

    return max_bleed(x_pos, width), max_bleed(y_pos, height)


def fill_rounded_corners(card_image: Image.Image, corner_radius: int) -> Image.Image:
    result = card_image.copy()
    width, height = result.size

    # [top-left, top-right, bottom-left, bottom-right]
    corners = [
        ((0, 0), (corner_radius, corner_radius)),
        ((width, 0), (width - corner_radius, corner_radius)),
        ((0, height), (corner_radius, height - corner_radius)),
        ((width, height), (width - corner_radius, height - corner_radius)),
    ]

    for (corner_x, corner_y), (arc_cx, arc_cy) in corners:
        # Each rounded corner has a square region of size (corner_radius x corner_radius)
        # that contains both the rounded arc and the "cut zone" beyond it
        square_x_start = 0 if corner_x == 0 else width - corner_radius
        square_y_start = 0 if corner_y == 0 else height - corner_radius
        square_x_end = corner_radius if corner_x == 0 else width
        square_y_end = corner_radius if corner_y == 0 else height

        # Process each pixel in this corner's square
        for local_x in range(square_x_start, square_x_end):
            for local_y in range(square_y_start, square_y_end):
                dist = math.sqrt((local_x - arc_cx) ** 2 + (local_y - arc_cy) ** 2)

                if dist > corner_radius:
                    # Angle from arc center to this pixel
                    angle = math.atan2(local_y - arc_cy, local_x - arc_cx)

                    # Project angle onto arc
                    src_x = int(arc_cx + corner_radius * math.cos(angle))
                    src_y = int(arc_cy + corner_radius * math.sin(angle))

                    # Copy the arc pixel outward
                    try:
                        # [!] There's a type warning here that's internal to Pillow.
                        pixel = result.getpixel((src_x, src_y))
                        result.putpixel((local_x, local_y), pixel)
                    except (IndexError, ValueError):
                        pass
    return result


def load_card_image(image_path: str | Path, path_label: str = "") -> Image.Image | None:

    path_label = f"{path_label.strip()} " if path_label else ""

    try:
        image = Image.open(image_path)
        return ImageOps.exif_transpose(image)
    except FileNotFoundError:
        print(f'Cannot get {path_label} image "{image_path}".')
    except OSError as e:
        raise OSError(f'Failed to load {path_label} image "{image_path}": {e}') from e

    return None


def parse_dimension_string(dimension_string: str | None, ppi: int) -> int:
    if dimension_string is None:
        return 0

    valid_units = ["", "mm", "in", "px"]
    amount, unit = measurements.parse_unit_string(dimension_string, valid_units)

    if unit == "mm":
        return math.floor(amount / 25.4 * ppi)
    if unit == "in":
        return math.floor(amount * ppi)
    return int(amount)
