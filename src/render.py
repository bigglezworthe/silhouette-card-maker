# ==============================================================================
# draw.py
#     Drawing onto the page.
# ==============================================================================

import math

from PIL import Image, ImageDraw, ImageFont

from src.defaults import MAX_REG_INSET_MM, MAX_REG_LENGTH_MM, MAX_REG_THICKNESS_MM, MIN_REG_LENGTH_MM, MIN_REG_THICKNESS_MM
from src.enums import CornerMatrix, Orientation, Registration
from src.calcs import calculate_max_print_bleed
from src.layout_models import ResolvedLayout, ResolvedRegistrationSettings
from src.measurements import parse_to_px
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

#============================
# Registration
#============================

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

def draw_reg_corner_lines(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    length: int,
    thickness: int,
    x_dir: int,
    y_dir: int,
) -> None:

    offset = thickness // 2
    effective_length = length + offset

    x += x_dir * offset
    y -= y_dir * offset 

    points = [
        (x, y),
        (x - x_dir * effective_length, y),
        (x - x_dir * effective_length, y + y_dir * thickness),
        (x - x_dir * thickness, y + y_dir * thickness),
        (x - x_dir * thickness, y + y_dir * effective_length),
        (x, y + y_dir * effective_length),
    ]

    draw.polygon(points, fill="black")

def generate_reg_mark(
    paper_width: str,
    paper_height: str,
    reg_opts: ResolvedRegistrationSettings,
    dpi_scale: float,
    layout_def: ResolvedLayout,
    registration: Registration,
) -> Image.Image:

    # Refactor: matplotlib -> PIL
    # Pillow measures in px, MPL in mm.

    is_portrait = layout_def.registration_orientation == Orientation.PORTRAIT
    if is_portrait:
        paper_width, paper_height = paper_height, paper_width

    # Normalize units to pixel
    paper_width_px = parse_to_px(paper_width, dpi_scale)
    paper_height_px = parse_to_px(paper_height, dpi_scale)
    inset_px = parse_to_px(reg_opts.inset, dpi_scale)
    thickness_px = parse_to_px(reg_opts.thickness, dpi_scale)
    length_px = parse_to_px(reg_opts.length, dpi_scale)
    
    min_reg_length_px = parse_to_px(f"{MIN_REG_LENGTH_MM}mm", dpi_scale)
    max_reg_length_px = parse_to_px(f"{MAX_REG_LENGTH_MM}mm", dpi_scale)
    min_reg_thickness_px = parse_to_px(f"{MIN_REG_THICKNESS_MM}mm", dpi_scale)
    max_reg_thickness_px = parse_to_px(f"{MAX_REG_THICKNESS_MM}mm", dpi_scale)
    max_reg_inset_px = parse_to_px(f"{MAX_REG_INSET_MM}mm", dpi_scale)

    # Constrain registration mark parameters within valid ranges.
    length_px = max(min_reg_length_px, min(length_px, max_reg_length_px))
    thickness_px = max(min_reg_thickness_px, min(thickness_px, max_reg_thickness_px))
    inset_px = min(inset_px, max_reg_inset_px)

    # Create image sized to the paper dimensions
    img = Image.new("RGB", (paper_width_px, paper_height_px), "white")
    draw = ImageDraw.Draw(img)

    # Corners to draw L's on.
    render_corners = [CornerMatrix.BOTTOM_LEFT, CornerMatrix.TOP_RIGHT]

    if registration == Registration.THREE:
        five = parse_to_px("5mm", dpi_scale)
        pil_offset = thickness_px // 2
        coords = [ 
            (inset_px - pil_offset, inset_px - pil_offset), 
            (inset_px + five + pil_offset, inset_px + five + pil_offset) 
        ]
        draw.rectangle(
            coords,
            fill="black"
        )

    else:  # Registration.FOUR
        render_corners.append(CornerMatrix.TOP_LEFT)
        render_corners.append(CornerMatrix.BOTTOM_RIGHT)

    for corner in render_corners:
        x_dir, y_dir = corner.value
        x = inset_px if x_dir < 0 else paper_width_px - inset_px
        y = inset_px if y_dir > 0 else paper_height_px - inset_px

        draw_reg_corner_lines(
            draw,
            x=x,
            y=y,
            length=length_px,
            thickness=thickness_px,
            x_dir=x_dir,
            y_dir=y_dir,
        )
    
    img = img.resize([math.floor(img.width * dpi_scale), math.floor(img.height * dpi_scale)])

    if layout_def.orientation != layout_def.registration_orientation:
        img = img.rotate(90 if is_portrait else -90, expand=True)
    return img



