# ==============================================================================
# pdf.py
#     PDF generation
# ==============================================================================
import math

from pathlib import Path

from PIL import ImageFont

from src.paths import Paths
from src.calcs import calculate_reg_params, calculate_render_params
from src.cards import batch_cards, load_card_side, load_cards
from src.defaults import DEFAULT_PPI
from src.draw import (
    DuplexPage,
    add_print_bleed,
    build_label_text,
    build_render_geometry,
    draw_outlines,
    normalize_pages,
    render_duplex_page,
)
from src.enums import Orientation, OrientationMode, Registration, Variant
from src.images import (
    process_card_side,
    process_cards,
)
from src.layout_models import ResolvedLayout
from src.layouts import (
    DEFAULT_ORIENTATION,
    load_defaults,
)
from src.measurements import parse_to_mm, parse_to_px
from src.offset import load_saved_offset
from src.page_manager import (
    REG_PADDING_MM,
    generate_layout,
    generate_reg_mark,
    resolve_reg_opts,
)
from src.paths import ImagePaths
from src.render_models import CardRenderOptions, Cards, PageLayout

LABEL_FONT = Paths.assets / "arial.ttf"



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
        return orientation, generate_layout(orientation=orientation, **kwargs)

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
    # ========================
    # The Goal
    # ------------------------
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
    # ========================

    # ==============================
    # Image modification
    # ==============================
    defaults = load_defaults()
    default_reg = (
        defaults.registration.borderless
        if borderless
        else defaults.registration.default
    )

    # Uses default length rather than effective length?
    total_exclusion_mm = parse_to_mm(default_reg.length) + REG_PADDING_MM
    total_exclusion = f"{total_exclusion_mm}mm"

    reg_opts = resolve_reg_opts(
        default_reg,
        layout_def.registration,
    )

    reg_params = calculate_reg_params(reg_opts=reg_opts, ppi_scale=ppi_scale)

    card_size_def = layout_def.card_size
    paper_size_def = layout_def.paper_size

    orientation = layout_def.orientation or DEFAULT_ORIENTATION

    # [!] skip_indices can be immediately validated as set
    page_layout = generate_layout(
        orientation=orientation,
        card_width=card_size_def.width,
        card_height=card_size_def.height,
        paper_width=paper_size_def.width,
        paper_height=paper_size_def.height,
        inset=reg_opts.inset,
        thickness=reg_opts.thickness,
        length=total_exclusion,
        ppi_scale=ppi_scale,
        skip_indices=skip_indices,
        borderless=borderless,
    )

    render_params = calculate_render_params(
        render_opts=render_opts,
        card_size_def=card_size_def,
        ppi_scale=ppi_scale,
    )


    num_cards = len(page_layout.card_positions)
    if num_cards == 0:
        raise ValueError(
            f'Card size "{card_size_name}" does not fit on paper size "{paper_size_name}".'
        ) 

    # ==============================
    # Registration
    # ==============================
    reg_image = generate_reg_mark(
        paper_width=paper_size_def.width,
        paper_height=paper_size_def.height,
        reg_opts=reg_opts,
        dpi_scale=ppi_scale,
        layout_def=layout_def,
        registration=registration,
    )

    # ==============================
    # Page Manager
    # ==============================
    pages: list[DuplexPage] = []

    radius_px = parse_to_px(card_size_def.radius or defaults.card_radius, ppi_scale)

    render_geometry = build_render_geometry(
        page_layout=page_layout,
        reg_params=reg_params,
        radius=radius_px,
        borderless=borderless,
    )

    # [!] Load and process cards by page to minimize RAM usage
    # [!] but keep cards.default_back loaded
    processed_card_back = None

    if not only_fronts:
        if cards.default_back:
            loaded_card_back = load_card_side(cards.default_back)
            processed_card_back = process_card_side(
                loaded_card_back, render_params.back, render_geometry
            )

    print("registration:", reg_image.size)
    for sheet_number, card_batch in enumerate(
        batch_cards(cards.cards, len(page_layout.card_positions)), 
        start=1,
    ):
        loaded_cards = load_cards(card_batch)
        processed_cards = process_cards(
            loaded_cards,
            processed_card_back,
            render_params,
            render_geometry,
        )

        front_sheet_num = sheet_number if only_fronts else sheet_number * 2 - 1
        label_text = build_label_text(front_sheet_num, layout_def.template, label)

        duplex_page = render_duplex_page(
            bg_image=reg_image.copy(),
            processed_cards=processed_cards,
            page_layout=page_layout,
            label_text=label_text,
            label_font=ImageFont.truetype(LABEL_FONT, 40 * ppi_scale),
        )
        if sheet_number == 1:
            print("duplex_front_page:", duplex_page.front.size)

        processed_duplex_page = add_print_bleed(
            duplex_page,
            page_layout,
            render_geometry,
            render_params,
        )
        if sheet_number == 1:
            print("processed:", processed_duplex_page.front.size)

        normalized_duplex_page = normalize_pages(processed_duplex_page, orientation)
        if sheet_number == 1:
            print("normalized:", normalized_duplex_page.front.size)


        pages.append(normalized_duplex_page)

    if len(pages) == 0:
        print("No pages were generated.")
        return

    if show_outline:
        # [!] Consolidated calls
        draw_outlines(
            pages,
            page_layout,
            render_geometry.radius,
        )
    print("outline:", pages[0].front.size)

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

    images = [image for page in pages for image in (page.front, page.back)]

    print("output_res:", int(DEFAULT_PPI * ppi_scale))
    if output_images:
        for i, image in enumerate(images):
            image.save(
                output_path / f"page{i + 1}.png",
                resolution=math.floor(DEFAULT_PPI * ppi_scale),
                speed=0,
                subsampling=0,
                quality=quality,
            )
    else:
        images[0].save(
            output_path,
            format="PDF",
            save_all=True,
            append_images=images[1:],
            resolution=math.floor(DEFAULT_PPI * ppi_scale),
            speed=0,
            subsampling=0,
            quality=quality,
        )
    print(f"Generated PDF: {output_path}")
