# ==============================================================================
# draw.py
#     Drawing onto the page.
# ==============================================================================

from PIL import Image, ImageDraw, ImageFont

from src.enums import Orientation
from src.images import calculate_max_print_bleed
from src.render_models import (
    DuplexPage, 
    RenderGeometry, 
    PageLayout, 
    RegistrationParams, 
    ProcessedCard
)

#============================
# Options
#============================
# Measurement strings to be parsed

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

    x_bleed, y_bleed = calculate_max_print_bleed(
        page_layout.card_positions, 
        page_layout.card_width_px, 
        page_layout.card_height_px, 
    )

    return RenderGeometry(
        page_layout = page_layout,
        x_fill = x_bleed,
        y_fill = y_bleed,
        radius = radius,
        label_margin = label_margin_px,
    )

#============================
# Page
#============================

def build_label_text(sheet_number: int, template: str | None, label: str | None) -> str:
    text = f'sheet: {sheet_number}, template: {template or ""}'
    if label:
        text = f"label: {label}, {text}"
    return text

def normalize_pages(
    duplex_page: DuplexPage,
    orientation: Orientation,
) -> DuplexPage:
    if orientation != Orientation.PORTRAIT:
        return duplex_page

    return DuplexPage(
        front=duplex_page.front.rotate(90, expand=True),
        back=duplex_page.back.rotate(90, expand=True),
    )

def render_duplex_page(
    bg_image: Image.Image,
    card_batch: list[ProcessedCard],
    geometry: RenderGeometry,
) -> DuplexPage:
    
    front_page = bg_image.copy()
    back_page = bg_image.copy()

    page_layout = geometry.page_layout

    # [!] Does this properly account for all cases? If padding = 0?
    first_y, first_x = page_layout.card_positions[0]
    print(f"    Grid origins: {first_x}, {first_y}")

    positions = (i for i, valid in enumerate(page_layout.card_placements) if valid) 
    for card in card_batch:
        pos = next(positions)

        # Positions are stored as (row, col) -> (y, x)
        front_y, front_x = page_layout.card_positions[pos]
        back_y, back_x = page_layout.back_positions[pos]
        
        grid_x = front_x - first_x
        grid_y = front_y - first_y
        print(f"      Placing card in position {pos} at: {grid_x}, {grid_y}")

        front_page.paste(
            card.front.image,
            (front_x - first_x, front_y - first_y),
        )

        if card.back is None:
            continue

        back_page.paste(
            card.back.image,
            (back_x - first_x, back_y - first_y),
        )
    
    print(f"      Grid Size: {front_page.size}")
    return DuplexPage(front_page, back_page)

#============================
# Render
#============================
# [!] Some functions return things, others don't. Need to standardize.

def draw_outline(
    page: Image.Image,
    positions: list[tuple[int, int]],
    card_width: int,
    card_height: int,
    radius: int,
    color: str = "white",
) -> None:
    draw = ImageDraw.Draw(page)
    for y, x in positions:
        draw.rounded_rectangle(
            (x, y, x + card_width, y + card_height),
            radius=radius,
            outline=color,
            width=1,
        )

def draw_outlines(
    pages: list[DuplexPage],
    page_layout: PageLayout,
    radius: int,
    outline_color: str = "white"
) -> None:
    for duplex_page in pages:
        draw_outline(
            duplex_page.front, 
            page_layout.card_positions,
            page_layout.card_width_px,
            page_layout.card_height_px,
            radius,
            outline_color,
        )
        draw_outline(
            duplex_page.back, 
            page_layout.back_positions,
            page_layout.card_width_px,
            page_layout.card_height_px,
            radius,
            outline_color,
        )

#============================
# Label
#============================
def draw_rotated_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    angle: float,
    fill: str = "black",
) -> Image.Image:
    bbox = font.getbbox(text)
    width = int(bbox[2] - bbox[0])
    height = int(bbox[3] - bbox[1])

    text_image = Image.new("RGBA", (width, height), (0,0,0,0))
    ImageDraw.Draw(text_image).text(
        (-bbox[0], -bbox[1]), 
        text, 
        fill=fill, 
        font=font,
    )

    return text_image.rotate(
        angle,
        expand=True,
        resample=Image.Resampling.BICUBIC,
    )


def draw_front_label(
    page: Image.Image,
    text: str, 
    position: tuple[int, int],
    angle: int,
    font: ImageFont.FreeTypeFont,
) -> None:
    draw = ImageDraw.Draw(page)

    if angle:
        text_image = draw_rotated_text(text, font, angle)

        page.paste(
            text_image,
            (
                position[0] - text_image.width // 2,
                position[1] - text_image.height // 2,
            ),
            text_image,
        )

    else:
        draw.text(
            position,
            text,
            fill="black",
            anchor="mm",
            font=font,
        )

#============================
# Label
#============================
 
def add_label(
    duplex_page: DuplexPage,
    page_layout: PageLayout,
    label_text: str,
    label_font: ImageFont.FreeTypeFont,
) -> DuplexPage:
    front_page = duplex_page.front
    draw_front_label(
        page=front_page,
        text=label_text,
        position=page_layout.label_position,
        angle=page_layout.label_angle,
        font=label_font,
    )
    return DuplexPage(front_page, duplex_page.back) 

def build_canvas(bounds: tuple[int, int, int, int]) -> Image.Image: 
    canvas_width = bounds[2] - bounds[0]
    canvas_height = bounds[3] - bounds[1]

    return Image.new("RGB", (canvas_width, canvas_height), "white")

def add_reg(
    duplex_page: DuplexPage,
    reg_image: Image.Image,
    bounds: tuple[int, int, int, int],
) -> DuplexPage:
    front_reg = reg_image.copy()
    back_reg = reg_image.copy()
    front_reg.paste(duplex_page.front, (bounds[0], bounds[1]))
    back_reg.paste(duplex_page.back, (bounds[0], bounds[1]))

    return DuplexPage(
        front = front_reg,
        back = back_reg,
    )



