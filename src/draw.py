# ==============================================================================
# draw.py
#     Drawing onto the page.
# ==============================================================================
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from src.enums import Orientation
from src.images import MINIMUM_BLEED, calculate_max_print_bleed
from src.render_models import CardRenderParams, RenderGeometry, PageLayout, RegistrationParams, ProcessedCard, ProcessedCardSide


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

    max_print_bleed = calculate_max_print_bleed(
        page_layout.card_positions, 
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


def build_label_text(sheet_number: int, template: str | None, label: str | None) -> str:
    text = f"sheet: {sheet_number}, template: {template or ""}"
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
    processed_cards: list[ProcessedCard],
    page_layout: PageLayout,
    label_text: str | None, 
    label_font: ImageFont.FreeTypeFont,
) -> DuplexPage:

    
    front_page = bg_image.copy()
    back_page = bg_image.copy()

    if label_text is not None: 
        draw_front_label(
            page=front_page,
            text=label_text,
            position=page_layout.label_position,
            angle=page_layout.label_angle,
            font=label_font,
        )

    for i, card in enumerate(processed_cards):
        # Positions are stored as (row, col) -> (y, x)
        front_y, front_x = page_layout.card_positions[i]
        back_y, back_x = page_layout.back_positions[i]

        front_page.paste(
            card.front.image, 
            (front_x + card.front.offset_x, front_y + card.front.offset_y)
        )

        if card.back is None:
            continue

        back_page.paste(
            card.back.image, 
            (back_x + card.back.offset_x, back_y + card.back.offset_y)
        )

    return DuplexPage(front_page, back_page)


#============================
# Bleed
#============================
def extend_edge(
    source: Image.Image,
    destination: Image.Image,
    source_box: tuple[int, int, int, int],
    destination_box: tuple[int, int, int, int],
) -> None:
    width = destination_box[2] - destination_box[0]
    height = destination_box[3] - destination_box[1]

    edge = source.crop(source_box).resize(
        (width, height),
        resample=Image.Resampling.NEAREST,
    )

    destination.paste(
        edge,
        destination_box[:2],
    )

# Card Bleed
def extend_image_edges(
    image: Image.Image,
    bleed_width: int,
    bleed_height: int,
) -> Image.Image:
    width, height = image.size

    extended = Image.new(image.mode, (width + 2 * bleed_width, height + 2 * bleed_height))
    extended.paste(image, (bleed_width, bleed_height))

    edges = (
        (
            (0, 0, width, 1), 
            (bleed_width, 0, bleed_width + width, bleed_height)
        ),
        (
            (0, height - 1, width, height),
            (bleed_width, bleed_height + height, bleed_width + width, extended.height),
        ),
        (
            (0, 0, 1, height),
            (0, bleed_height, bleed_width, bleed_height + height),
        ),
        (
            (width - 1, 0, width, height),
            (bleed_width + width, bleed_height, extended.width, bleed_height + height),
        ),
    )

    for source_box, destination_box in edges:
        extend_edge(
            image,
            extended,
            source_box,
            destination_box,
        )

    return extended

def add_print_bleed_to_page(
    page: Image.Image,
    edges: tuple[int, int, int, int],
    bleed: tuple[int, int],
) -> Image.Image:
    top, bottom, left, right = edges
    bleed_width, bleed_height = bleed

    if bleed_height == 0 and bleed_width == 0:
        return page

    if bleed_height > 0: 
        extend_edge(
            page,
            page,
            (left, top, right, top + 1),
            (left, top - bleed_height, right, top),
        )

        extend_edge(
            page,
            page,
            (left, bottom - 1, right, bottom),
            (left, bottom, right, bottom + bleed_height),
        )

    if bleed_width > 0:
        extend_edge(
            page,
            page,
            (left, top, left + 1, bottom),
            (left - bleed_width, top, left, bottom),
        )

        extend_edge(
            page,
            page,
            (right - 1, top, right, bottom),
            (right, top, right + bleed_width, bottom),
        )

    return page

# Print Bleed
def add_print_bleed(
    duplex_page: DuplexPage,
    page_layout: PageLayout,
    render_geometry: RenderGeometry,
    render_params: CardRenderParams,
    
) -> DuplexPage:

    x_pos = sorted({col for _, col in page_layout.card_positions})
    y_pos = sorted({row for row, _ in page_layout.card_positions})

    edges = (
        min(y_pos),
        max(y_pos) + page_layout.card_height_px,
        min(x_pos),
        max(x_pos) + page_layout.card_width_px,
    )

    bleed_front = (
        min(render_params.front.extend_bleed, render_geometry.max_print_bleed_width),
        min(render_params.front.extend_bleed, render_geometry.max_print_bleed_height),
    )
    
    bleed_back = (
        min(render_params.back.extend_bleed, render_geometry.max_print_bleed_width),
        min(render_params.back.extend_bleed, render_geometry.max_print_bleed_height),
    )

    return DuplexPage(
        front = add_print_bleed_to_page(duplex_page.front, edges, bleed_front),
        back = add_print_bleed_to_page(duplex_page.back, edges, bleed_back) 
    )


#============================
# Render
#============================
# [!] Some functions return things, others don't. Need to standardize.
def render_card_side(
    page: Image.Image,
    card_side: ProcessedCardSide,
    x: int,
    y: int,
) -> None:
    card_image = card_side.image

    card_image = extend_image_edges(
        card_image,
        card_side.synthetic_bleed_width,
        card_side.synthetic_bleed_height,
    )

    page.paste(
        card_image,
        (
            x + card_side.offset_x - card_side.synthetic_bleed_width,
            y + card_side.offset_y - card_side.synthetic_bleed_height
        ),
    )

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
