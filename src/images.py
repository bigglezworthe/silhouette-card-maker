# ==============================================================================
# images.py
#     Place images on the page and perform non-crop manipulations
# ==============================================================================
from dataclasses import dataclass
import math

from PIL import Image

from src.calcs import crop_and_scale_image
from src.cards import Card, CardSide, ProcessedCard, ProcessedCardSide
from src.draw import CardRenderParams, RenderGeometry, SideRenderParams
from src.enums import FitMode
from src.measurements import parse_measurement

# Approximately 1.25mm of bleed in px assuming 300ppi: ceil(1.25mm * 1in/25.4mm * 300px/1in)
MINIMUM_BLEED = 15

@dataclass(frozen=True)
class CardRenderGeometry:
    width: int
    height: int
    print_bleed_x: int
    print_bleed_y: int
    ppi_scale: float


def calculate_max_print_bleed(
    x_pos: list[int],
    y_pos: list[int],
    width: int,
    height: int,
    min_bleed: int = 0
) -> tuple[int, int]:

    def max_bleed(positions: list[int], size: int) -> int:
        if len(positions) < 2:
            return min_bleed

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

def convert_inch_to_crop(
    crop_in: float, card_width_px: int, card_height_px: int
) -> tuple[float, float]:
    # Card dimensions are based on 300 ppi
    card_width_in = card_width_px / 300
    card_height_in = card_height_px / 300

    crop_x_percent = 2 * crop_in / card_width_in * 100
    crop_y_percent = 2 * crop_in / card_height_in * 100

    return (crop_x_percent, crop_y_percent)


def parse_crop_string(crop_string: str | None) -> tuple[float, str]:
    if crop_string is None:
        return 0, ""

    valid_units = ["", "mm", "in", "%"]
    try: 
        return parse_measurement(crop_string, valid_units)
    except ValueError as e:
        raise ValueError(f"Invalid Crop Format: {crop_string}") from e

def process_card_side(
    card_side: CardSide,
    render_params: SideRenderParams,
    geometry: RenderGeometry,
) -> ProcessedCardSide:
    image = card_side.image

    if image is None:
        raise ValueError("Card side must have an image to process. ")

    crop_percent_x, crop_percent_y = render_params.crop


    if crop_percent_x > 0 or crop_percent_y > 0 or render_params.fit == FitMode.CROP:
        crop_result = crop_and_scale_image(
            image,
            crop_percent_x,
            crop_percent_y,
            geometry.scaled_card_width,
            geometry.scaled_card_height,
            geometry.scaled_bleed_width,
            geometry.scaled_bleed_height,
            render_params.fit,
        )
    
        image = crop_result.image
        offset_x, offset_y = crop_result.offset
        synthetic_bleed_width, synthetic_bleed_height = crop_result.synthetic_bleed

    else:
        image = image.resize((geometry.scaled_card_width, geometry.scaled_card_height))
        offset_x = 0
        offset_y = 0
        synthetic_bleed_width = geometry.scaled_bleed_width
        synthetic_bleed_height = geometry.scaled_bleed_height

    extend_edges = render_params.extend_edges
    if extend_edges > 0:
        image = image.crop((
            extend_edges, extend_edges, 
            image.width - extend_edges, image.height - extend_edges
        ))

    extend_corners = render_params.extend_corners_radius
    if extend_corners > 0:
        image = fill_rounded_corners(image, render_params.extend_corners_radius)

    return ProcessedCardSide(
        image = image,
        offset_x = offset_x,
        offset_y = offset_y,
        synthetic_bleed_width = synthetic_bleed_width,
        synthetic_bleed_height = synthetic_bleed_height, 
    )

def process_cards(
    card_batch: list[Card],
    default_back: ProcessedCardSide | None,
    render_params: CardRenderParams,
    render_geometry: RenderGeometry,
) -> list[ProcessedCard]:
    processed: list[ProcessedCard] = []
    for card in card_batch:
        front = process_card_side(card.front, render_params.front, render_geometry)
        if card.back is None:
            back = default_back
        else: 
            back = process_card_side(card.back, render_params.back, render_geometry)
        processed.append(ProcessedCard(front, back))

    return processed

