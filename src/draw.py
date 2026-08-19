# ==============================================================================
# draw.py
#     Drawing onto the page.
# ==============================================================================
from dataclasses import dataclass
import math

from PIL import Image, ImageDraw
from enum import Enum

from src.cards import Cards, ProcessedCardSide, ProcessedCards
from src.enums import FitMode, Orientation, CardSide
from src.images import MINIMUM_BLEED, calculate_max_print_bleed, fill_rounded_corners, crop_and_scale_image
from src.page_manager import PageLayout, RegistrationParams

#============================
# Options
#============================
# Measurement strings to be parsed

@dataclass(frozen=True)
class SideRenderOptions:
    crop: str | None
    fit: FitMode
    extend_edges: str | None 
    extend_corners_radius: str | None
    extend_bleed: str | None

# [!] Might be able to freeze this? Looks like orientation is the holdup. 
@dataclass(frozen=False) 
class CardRenderOptions:
    front: SideRenderOptions
    back: SideRenderOptions
    orientation: Orientation
    
#============================
# Params
#============================
# Numerical values to be used 

@dataclass(frozen=True)
class SideRenderParams:
    crop: tuple[float, float]
    fit: FitMode
    extend_edges: int 
    extend_corners_radius: int
    extend_bleed: int

# [!] Might be able to freeze this? Looks like orientation is the holdup. 
@dataclass(frozen=False) 
class CardRenderParams:
    front: SideRenderParams
    back: SideRenderParams
    orientation: Orientation

#============================
# Geometry
#============================

# [!] Need to figure out the appropriate bleed to use here
@dataclass(frozen=True)
class RenderGeometry:
    page_layout: PageLayout
    max_print_bleed_width: int
    max_print_bleed_height: int
    radius: int
    label_margin: int

def build_render_geometry(
    page_layout: PageLayout,
    reg_params: RegistrationParams,
    radius: int,
    borderless: bool,
) -> RenderGeometry:
    if borderless:
        label_margin_px = reg_params.inset
    else:
        label_margin_px = reg_params.inset - (2 * reg_params.thickness)

    max_print_bleed = calculate_max_print_bleed(
        page_layout.x_pos, page_layout.y_pos, 
        page_layout.card_width_px, page_layout.card_height_px, 
        MINIMUM_BLEED,
    )



    return RenderGeometry(
        page_layout = page_layout,
        max_print_bleed_width = max_print_bleed[0],
        max_print_bleed_height = max_print_bleed[1],
        radius = radius,
        label_margin = label_margin_px,
    )

#============================
# Page
#============================
@dataclass(frozen=True)
class DuplexPage:
    front: Image.Image
    back:  Image.Image

def get_card_positions(
    page_layout: PageLayout,
    skip_indices: set[int],
) -> list[tuple[int, int]]:
    card_positions = (page_layout.y_pos, page_layout.x_pos)
    return [
        (row, col)
        for i, (row, col) in enumerate(card_positions)
        if i not in skip_indices
    ]


def render_duplex_page(
    bg_image: Image.Image,
    processed_cards: ProcessedCards,
    page_layout: PageLayout,
    skip_indices_set: set[int]
) -> DuplexPage:

    x_pos = page_layout.x_pos
    y_pos = page_layout.y_pos

    front_pos = 

    

#============================
# Render
#============================

def draw_card_with_bleed(
    card_image: Image.Image,
    base_image: Image.Image,
    x: int,
    y: int,
    print_bleed: tuple[int, int],
    extra_bleed: tuple[int, int, int, int] = (0, 0, 0, 0),  # top, right, bottom, left
) -> None:
    bleed_width, bleed_height = print_bleed
    extra_top, extra_right, extra_bottom, extra_left = extra_bleed

    bleed_top = bleed_height + extra_top
    bleed_bottom = bleed_height + extra_bottom
    bleed_left = bleed_width + extra_left
    bleed_right = bleed_width + extra_right

    width, height = card_image.size
    base_image.paste(card_image, (x, y))

    class Axis(int, Enum):
        X = 0
        Y = 1

    def extend_edge(
        crop_box: tuple[int, int, int, int],
        start: tuple[int, int],
        bleed: int,
        axis: Axis,
    ) -> None:
        for bleed_i in range(bleed):
            pos = (
                start[0] + (bleed_i if axis == Axis.X else 0),
                start[1] + (bleed_i if axis == Axis.Y else 0),
            )
            base_image.paste(card_image.crop(crop_box), pos)

    def fill_corner(
        corner_pixel_x: int,
        corner_pixel_y: int,
        corner_x: int,
        corner_y: int,
        width: int,
        height: int,
    ) -> None:
        pixel = card_image.crop(
            (corner_pixel_x, corner_pixel_y, corner_pixel_x + 1, corner_pixel_y + 1)
        )
        for dx in range(width):
            for dy in range(height):
                base_image.paste(pixel, (corner_x + dx, corner_y + dy))

    extend_edge((0, 0, width, 1), (x, y - bleed_top), bleed_top, Axis.Y)
    extend_edge((0, height - 1, width, height), (x, y + height), bleed_bottom, Axis.Y)
    extend_edge((0, 0, 1, height), (x - bleed_left, y), bleed_left, Axis.X)
    extend_edge((width - 1, 0, width, height), (x + width, y), bleed_right, Axis.X)

    fill_corner(0, 0, x - bleed_left, y - bleed_top, bleed_left, bleed_top)
    fill_corner(width - 1, 0, x + width, y - bleed_top, bleed_right, bleed_top)
    fill_corner(0, height - 1, x - bleed_left, y + height, bleed_left, bleed_bottom)
    fill_corner(width - 1, height - 1, x + width, y + height, bleed_right, bleed_bottom)

    # [!] Why not just paste a rectangle beneath the card? Seems easier than filling space 1px at a time

def draw_card_layout(
    card_images: list[Image.Image | None],
    single_back_image: Image.Image | None,
    base_image: Image.Image,
    num_rows: int,
    num_cols: int,
    x_pos: list[int],
    y_pos: list[int],
    width: int,
    height: int,
    print_bleed: tuple[int, int],
    render_params: CardRenderParams,
    ppi_ratio: float,
    side: CardSide,
    orientation: Orientation,
) -> None:
    num_cards = num_rows * num_cols
    front_params = render_params.front
    back_params = render_params.back 
    crop_percent_x, crop_percent_y = front_params.crop
    crop_backs_percent_x, crop_backs_percent_y = back_params.crop
    print_bleed_x, print_bleed_y = print_bleed

    extend_edges_thickness = math.floor(front_params.extend_edges * ppi_ratio)
    extend_edges_backs_thickness = math.floor(back_params.extend_edges * ppi_ratio)
    extend_corners_thickness = math.floor(front_params.extend_corners_radius * ppi_ratio)
    extend_corners_backs_thickness = math.floor(back_params.extend_corners_radius * ppi_ratio)
    extend_bleed_thickness = math.floor(front_params.extend_bleed * ppi_ratio)

    scaled_width = math.floor(width * ppi_ratio)
    scaled_height = math.floor(height * ppi_ratio)

    scaled_bleed_width = math.ceil(print_bleed_x * ppi_ratio)
    scaled_bleed_height = math.ceil(print_bleed_y * ppi_ratio)

    # Fill spaces with card back
    for i, card_image in enumerate(card_images):
        if card_image is None:
            continue

        col = i % num_cards % num_cols
        row = (i % num_cards) // num_cols

        if side == CardSide.BACK:
            if orientation == Orientation.PORTRAIT:
                col = num_cols - col - 1
            else:
                row = num_rows - row - 1

        base_x = math.floor(x_pos[col] * ppi_ratio)
        base_y = math.floor(y_pos[row] * ppi_ratio)

        # Default: use synthetic bleed, no position offset needed
        bleed_offset_x = 0
        bleed_offset_y = 0
        synthetic_bleed = (scaled_bleed_width, scaled_bleed_height)

        
        if card_image is single_back_image:
            active_crop_x, active_crop_y = crop_backs_percent_x, crop_backs_percent_y
            active_fit = back_opts.fit
            active_extend_edges_thickness = extend_edges_backs_thickness
            active_extend_corners_thickness = extend_corners_backs_thickness
        else:
            active_crop_x, active_crop_y = crop_percent_x, crop_percent_y
            active_fit = front_opts.fit
            active_extend_edges_thickness = extend_edges_thickness
            active_extend_corners_thickness = extend_corners_thickness

        if active_crop_x > 0 or active_crop_y > 0 or active_fit == FitMode.CROP:
            card_image, bleed_offset_x, bleed_offset_y, synthetic_bleed = (
                crop_and_scale_image(
                    card_image,
                    active_crop_x,
                    active_crop_y,
                    scaled_width,
                    scaled_height,
                    scaled_bleed_width,
                    scaled_bleed_height,
                    active_fit,
                )
            )
        else:
            card_image = card_image.resize((scaled_width, scaled_height))

        if active_extend_edges_thickness > 0:
            card_image = card_image.crop(
                (
                    active_extend_edges_thickness,
                    active_extend_edges_thickness,
                    card_image.width - active_extend_edges_thickness,
                   card_image.height - active_extend_edges_thickness,
                )
            )

        if active_extend_corners_thickness > 0:
            card_image = fill_rounded_corners(
                card_image, active_extend_corners_thickness
            )

        if side == CardSide.BACK and orientation == Orientation.LANDSCAPE:
            card_image = card_image.rotate(180)

        # Calculate final position
        x = base_x + bleed_offset_x + active_extend_edges_thickness
        y = base_y + bleed_offset_y + active_extend_edges_thickness

        # Calculate total bleed
        edge_bleed_width = synthetic_bleed[0] + active_extend_edges_thickness
        edge_bleed_height = synthetic_bleed[1] + active_extend_edges_thickness

        # Handle edges
        # [!] Changed notation to bool arithmetic instead of if/else
        extra_bleed_top = extend_bleed_thickness * (row == 0)
        extra_bleed_bottom = extend_bleed_thickness * (row == num_rows - 1)
        extra_bleed_left = extend_bleed_thickness * (col == 0)
        extra_bleed_right = extend_bleed_thickness * (col == num_cols - 1)

        draw_card_with_bleed(
            card_image,
            base_image,
            x,
            y,
            (edge_bleed_width, edge_bleed_height),
            (extra_bleed_top, extra_bleed_right, extra_bleed_bottom, extra_bleed_left),
        )


# Doesn't save any lines of code but cleans up the call
def draw_card_layouts(
    cards: Cards,
    page: DuplexPage,

    x_pos: list[int],
    y_pos: list[int],
    width: int,
    height: int,
    print_bleed: tuple[int, int],
    render_params: CardRenderParams,
    ppi_ratio: float,
    orientation: Orientation,
) -> None:
    draw_card_layout(
        front_card_images,
        single_back_image,
        base_front_image,
        num_rows,
        num_cols,
        x_pos,
        y_pos,
        width,
        height,
        print_bleed,
        render_params,
        ppi_ratio,
        side=CardSide.FRONT,
        orientation=orientation,
    )

    draw_card_layout(
        back_card_images,
        single_back_image,
        base_back_image,
        num_rows,
        num_cols,
        x_pos,
        y_pos,
        width,
        height,
        print_bleed,
        render_params,
        ppi_ratio,
        side=CardSide.BACK,
        orientation=orientation,
    )


def draw_outline(
    page: Image.Image,
    x_pos: list[int],
    y_pos: list[int],
    card_width_px: int,
    card_height_px: int,
    radius_px: int,
    ppi_ratio: float,
) -> None:
    draw = ImageDraw.Draw(page)
    scaled_w = math.floor(card_width_px * ppi_ratio)
    scaled_h = math.floor(card_height_px * ppi_ratio)
    scaled_r = math.floor(radius_px * ppi_ratio)

    for x in x_pos:
        for y in y_pos:
            sx = math.floor(x * ppi_ratio)
            sy = math.floor(y * ppi_ratio)
            draw.rounded_rectangle(
                [sx, sy, sx + scaled_w, sy + scaled_h],
                radius=scaled_r,
                outline="white",
                width=1,
            )


def draw_outlines(
    pages: list[Image.Image],
    x_pos: list[int],
    y_pos: list[int],
    card_width_px: int,
    card_height_px: int,
    radius_px: int,
    ppi_ratio: float,
) -> None:
    for page in pages:
        draw_outline(
            page,
            x_pos,
            y_pos,
            card_width_px,
            card_height_px,
            radius_px,
            ppi_ratio,
        )
