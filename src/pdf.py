# ==============================================================================
# pdf.py
#     PDF generation
# ==============================================================================
import math
import os

from pathlib import Path
from pydoc import resolve

from PIL import Image, ImageFont, ImageDraw

from create_pdf import DEFAULT_OUTPUT_PATH
from src.calcs import calculate_reg_params, calculate_render_params
from src.cards import Cards, batch_cards, load_card_side, load_cards
from src.defaults import DEFAULT_PPI
from src.draw import CardRenderOptions, build_render_geometry, draw_card_layouts, draw_outlines, render_duplex_page
from src.enums import Orientation, OrientationMode, Registration, Variant
from src.images import (
    MINIMUM_BLEED,
    calculate_max_print_bleed,
    process_card_side,
    process_cards,
)
from src.layout_models import  ResolvedLayout
from src.layouts import (
    DEFAULT_ORIENTATION,
    load_defaults,
)
from src.measurements import parse_to_mm, parse_to_px
from src.offset import load_saved_offset
from src.page_manager import REG_PADDING_MM, PageLayout, generate_layout, generate_reg_mark, resolve_reg_opts, resolve_skipped_indices
from src.paths import (
    ImagePaths,
    Paths,
)

def create_template_name(
    paper_size: str, card_size: str, variant: Variant, version: int
) -> str:
    var_string = f"{variant.value}-" if variant != Variant.DEFAULT else ""
    return f"{paper_size}-{card_size}-{var_string}v{version}"


def add_front_back_pages(
    front_page: Image.Image,
    back_page: Image.Image,
    pages: list[Image.Image],
    page_width: int,
    page_height: int,
    ppi_ratio: float,
    template: str,
    only_fronts: bool,
    label: str,
    orientation: Orientation,
    label_margin_px: int,
) -> None:
    font = ImageFont.truetype(Paths.assets / "arial.ttf", 40 * ppi_ratio)
    num_sheet = len(pages) + 1
    if not only_fronts:
        num_sheet = int(len(pages) / 2) + 1

    label_text = f"sheet: {num_sheet}, template: {template}"
    if len(label):
        label_text = f"{label}, {label_text}"

    # Label goes on short side of paper opposite top-left black square
    if orientation == Orientation.LANDSCAPE:
        # [!] This feels expensive for placing text.
        front_page = front_page.rotate(-90, expand=True)
        draw = ImageDraw.Draw(front_page)
        label_x = math.floor((page_height / 2) * ppi_ratio)
        label_y = math.floor(page_width * ppi_ratio) - label_margin_px
        draw.text(
            (label_x, label_y), label_text, fill=(0, 0, 0), anchor="mm", font=font
        )
        front_page = front_page.rotate(90, expand=True)
    else:
        draw = ImageDraw.Draw(front_page)
        label_x = math.floor((page_width / 2) * ppi_ratio)
        label_y = math.floor(page_height * ppi_ratio) - label_margin_px
        draw.text(
            (label_x, label_y), label_text, fill=(0, 0, 0), anchor="mm", font=font
        )

    # [!] Can be included in ELSE above
    if orientation == Orientation.PORTRAIT:
        front_page = front_page.rotate(90, expand=True)
        back_page = back_page.rotate(90, expand=True)

    pages.append(front_page)
    if not only_fronts:
        pages.append(back_page)


# [!] Might belong in layout.py?
def find_best_orientation(
    orientation_mode: OrientationMode,
    card_width: str,
    card_height: str,
    paper_width: str,
    paper_height: str,
    inset: str,
    length: str,
    ppi: int,
    preferred: Orientation = Orientation.LANDSCAPE,
) -> tuple[Orientation, PageLayout]:
    # [!] Need to package this more reasonably
    kwargs = dict(
        card_width=card_width,
        card_height=card_height,
        paper_width=paper_width,
        paper_height=paper_height,
        inset=inset,
        length=length,
        ppi=ppi,
    )

    if orientation_mode != OrientationMode.OPTIMIZE:
        orientation = Orientation(orientation_mode.value)
        return orientation, generate_layout(
            orientation=orientation, **kwargs
        )

    # try both orientations and pick the one that fits more cards
    best_count = 0
    best_orientation = preferred
    best_computed = None

    for orient in Orientation:
        try:
            computed = generate_layout(orientation=orient, **kwargs)
        except ValueError:
            continue

        count = len(computed.x_pos) * len(computed.y_pos)
        if count > best_count or (count == best_count and orient == preferred):
            best_count = count
            best_orientation = orient
            best_computed = computed

    if best_computed is None:
        raise ValueError("No valid layout in either card orientation.")

    return best_orientation, best_computed


def generate_pdf(
    image_paths: ImagePaths,
    cards: Cards,
    layout_def: ResolvedLayout,
    output_path: Path, 
    output_images: bool,
    card_size_name: str,
    paper_size_name: str,
    registration: Registration,
    only_fronts: bool,
    render_opts: CardRenderOptions,
    ppi_scale: float,
    quality: int,
    skip_indices: list[int],
    load_offset: bool,
    label: str,
    show_outline: bool = False,
    borderless: bool = False,
) -> None:
    #========================
    # The Goal
    #------------------------
    # defaults = load_defaults()
    # layout = prepare_layout(...)
    # geometry = prepare_geometry(layout, defaults, ppi)
    # render_params = prepare_render_params(render_opts, geometry, ppi)
    # cards = load_cards(image_paths, ...)
    # cards = process_cards(cards, ...)
    # pages = render_pages(
    #     cards = cards,
    #     layout=layout,
    #     geometry=geometry,
    #     render_params=render_params,
    #     ...
    # )
    # save_output(pages, ...) load_defaults()
    #========================

    # ==============================
    # Image modification
    # ==============================
    defaults = load_defaults()
    default_reg = defaults.registration.borderless if borderless else defaults.registration.default

    # Uses default length rather than effective length? 
    total_exclusion_mm = (parse_to_mm(default_reg.length) + REG_PADDING_MM)
    total_exclusion = f"{total_exclusion_mm}mm"

    reg_opts = resolve_reg_opts(
        default_reg,
        layout_def.registration,
    )

    card_size_def = layout_def.card_size
    paper_size_def = layout_def.paper_size

    # [!] skip_indices can be immediately validated as set
    page_layout = generate_layout(
        orientation = layout_def.orientation or DEFAULT_ORIENTATION,
        card_width = card_size_def.width,
        card_height = card_size_def.height,
        paper_width = paper_size_def.width, 
        paper_height = paper_size_def.height,
        inset = reg_opts.inset,
        length = total_exclusion,
        ppi_scale = ppi_scale,
        skip_indices = skip_indices
    )

    render_params = calculate_render_params(
        render_opts = render_opts,
        card_size_def = card_size_def,
        ppi_scale = ppi_scale,
    )

    reg_params = calculate_reg_params(reg_opts = reg_opts, ppi_scale = ppi_scale )
    
    radius_px = parse_to_px(
        card_size_def.radius or defaults.card_radius, 
        ppi_scale
    )


    # ==============================
    # PDF
    # ==============================

    num_cards = len(page_layout.card_positions)
    if num_cards == 0:
        raise ValueError(
            f'Card size "{card_size_name}" does not fit on paper size "{paper_size_name}".'
        )

    # ==============================
    # Skip Indices
    # ==============================
    if borderless:
        label_margin_px = math.floor(reg_params.inset)
    else:
        label_margin_px = math.floor(reg_params.inset - reg_params.thickness* 2)

    # ==============================
    # Registration
    # ==============================
    reg_image = generate_reg_mark(
        paper_width = paper_size_def.width,
        paper_height = paper_size_def.height,
        reg_opts = reg_opts,
        dpi_scale = ppi_scale,
        layout_def = layout_def,
        registration = registration,
    )

    # ==============================
    # Page Manager
    # ==============================
    pages: list[Image.Image] = []

    render_geometry = build_render_geometry(
        page_layout = page_layout,
        reg_params = reg_params,
        radius = radius_px,
        borderless = borderless,
    )
    
    # [!] Load and process cards by page to minimize RAM usage
    # [!] but keep cards.default_back loaded
    processed_card_back = None

    if not only_fronts:
        if cards.default_back:
            loaded_card_back = load_card_side(cards.default_back)
            processed_card_back = process_card_side(loaded_card_back, render_params, render_geometry)

    for card_batch in batch_cards(cards.cards, len(page_layout.card_positions)):
        loaded_cards = load_cards(card_batch)
        processed_cards = process_cards(
            loaded_cards, 
            processed_card_back,
            render_params, 
            render_geometry,
        )

        duplex_page = render_duplex_page(
            bg_image = reg_image,
            processed_cards = processed_cards,
            page_layout = page_layout,
        )




        front_page = reg_img.copy()
        back_page = reg_img.copy()

        # [!] Consolidated calls
        draw_card_layouts(
            front_card_images,
            back_card_images,
            single_back_image,
            front_page,
            back_page,
            num_rows,
            num_cols,
            x_pos,
            y_pos,
            card_width_px,
            card_height_px,
            max_print_bleed,
            crop,
            crop_backs,
            ppi_ratio,
            extend_edges_px,
            extend_edges_backs_px,
            extend_corners_px,
            extend_corners_backs_px,
            extend_bleed_px,
            extend_bleed_backs_px,
            fit=fit,
            fit_backs=fit_backs_mode,
            orientation=orientation,
        )

        if show_outline:
            # [!] Consolidated calls
            draw_outlines(
                [front_page, back_page],
                x_pos,
                y_pos,
                card_width_px,
                card_height_px,
                radius_px,
                ppi_ratio,
            )

        add_front_back_pages(
            front_page,
            back_page,
            pages,
            page_width_px,
            page_height_px,
            ppi_ratio,
            template,
            only_fronts,
            label,
            orientation,
            label_margin_px,
        )

    if len(pages) == 0:
        print("No pages were generated.")
        return

    if load_offset:
        saved_offset = load_saved_offset()

        if saved_offset is None:
            print("Offset cannot be applied")
        else:
            print(
                "Loaded offsets:"
                + f"x={saved_offset.x_offset},"
                + f"y={saved_offset.y_offset},"
                + f"angle={saved_offset.angle_offset}"
            )

    if output_images:
        for index, page in enumerate(pages):
            page.save(
                os.path.join(output_path, f"page{index + 1}.png"),
                resolution=math.floor(300 * ppi_ratio),
                speed=0,
                subsampling=0,
                quality=quality,
            )
        print(f"Generated images: {output_path}")
    else:
        pages[0].save(
            output_path,
            format="PDF",
            save_all=True,
            append_images=pages[1:],
            resolution=math.floor(300 * ppi_ratio),
            speed=0,
            subsampling=0,
            quality=quality,
        )
        print(f"Generated PDF: {output_path}")
