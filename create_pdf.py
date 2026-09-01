from PIL import ImageFont
import click

from pathlib import Path

from src.calcs import calculate_reg_params, calculate_render_params
from src.cards import batch_cards, find_cards, load_card_side, load_cards
from src.draw import (
    DuplexPage, 
    build_label_text, 
    build_render_geometry,
    draw_front_label, 
    draw_outlines, 
    normalize_pages, 
    render_duplex_page,
)
from src.enums import Orientation, Registration, FitMode 
from src.images import pad_duplex_page, process_card_side, process_cards
from src.measurements import DEFAULT_PPI, parse_to_mm, parse_to_px 
from src.offset import load_saved_offset
from src.page_manager import (
    REG_PADDING_MM,
    add_reg,
    build_canvas, 
    generate_layout, 
    generate_reg_mark,
    get_canvas_bounds, 
    resolve_reg_opts,
)
from src.paths import ImagePaths, Paths, prepare_output_path
from src.pdf import generate_pdf
from src.layouts import (
    DEFAULT_ORIENTATION,
    get_all_card_size_names,
    get_all_paper_size_names,
    get_all_specialty_layout_names,
    load_defaults,
    load_layouts,
    prepare_layout,
)

from src.render_models import CardRenderOptions, SideRenderOptions

#============================
# Initialize Defaults
#============================
OUTPUT_DIRECTORY = Paths.output
DEFAULT_OUTPUT_PATH = OUTPUT_DIRECTORY / "game.pdf"

CARD_SIZE_CHOICES = get_all_card_size_names()
PAPER_SIZE_CHOICES = get_all_paper_size_names()
SPECIALTY_CHOICES = get_all_specialty_layout_names()

LABEL_FONT = Paths.assets / "arial.ttf"

# ============================
# CLI Args
# ============================
@click.command()
@click.option("--front_dir_path", default=Paths.fronts, type=click.Path(path_type=Path, file_okay=False, exists=True), show_default=True, help="The path to the directory containing the card fronts.")
@click.option("--back_dir_path", default=Paths.backs, type=click.Path(path_type=Path, file_okay=False, exists=True), show_default=True, help="The path to the directory containing one or more card backs.")
@click.option("--double_sided_dir_path", default=Paths.doubles, type=click.Path(path_type=Path, file_okay=False, exists=True), show_default=True, help="The path to the directory containing card backs for double-sided cards.")
@click.option("--output_path", default=DEFAULT_OUTPUT_PATH, type=click.Path(path_type=Path), show_default=True, help="The desired path to the output PDF.")
@click.option("--output_images", default=False, is_flag=True, help="Create images instead of a PDF.")
@click.option("--card_size", default="standard", type=click.Choice(CARD_SIZE_CHOICES, case_sensitive=False), show_default=True, help="The desired card size.")
@click.option("--paper_size", default="letter", type=click.Choice(PAPER_SIZE_CHOICES, case_sensitive=False), show_default=True, help="The desired paper size.")
@click.option("--registration", default=Registration.THREE.value, type=click.Choice([t.value for t in Registration], case_sensitive=False), show_default=True, help="The desired registration pattern.")
@click.option("--registration_orientation", default=None, type=click.Choice([t.value for t in Orientation], case_sensitive=False), help="Override the registration mark orientation without changing the card layout.")
@click.option("--specialty", default=None, type=click.Choice(SPECIALTY_CHOICES, case_sensitive=False), help="Use a specialty layout. Overrides card_size, paper_size, and registration settings.")
@click.option("--only_fronts", default=False, is_flag=True, help="Only generate front pages.")
@click.option("--fit", default=FitMode.STRETCH.value, type=click.Choice([t.value for t in FitMode], case_sensitive=False), show_default=True, help="How to fit front and double-sided images to card size. 'stretch' allows distortion, 'crop' preserves aspect ratio by center-cropping.")
@click.option("--fit_backs", type=click.Choice([t.value for t in FitMode], case_sensitive=False), help="How to fit back images to card size. 'stretch' allows distortion, 'crop' preserves aspect ratio by center-cropping.")
@click.option("--crop", help="Crop card edges of front and double-sided images (removes edges). Examples: 3mm, 0.125in, 6.5.")
@click.option("--crop_backs", help="Crop card edges of back images (removes edges). Examples: 3mm, 0.125in, 6.5.")
@click.option("--extend_edges", help="Crop card edges and extend them for front and double-sided images. Examples: 3mm, 0.125in.")
@click.option("--extend_edges_backs", help="Crop card edges and extend them for back images only. Examples: 3mm, 0.125in.")
@click.option("--extend_corners", help="Extend rounded corner regions to reduce corner artifacts for front and double-sided images. Examples: 3mm, 0.125in.")
@click.option("--extend_corners_backs", help="Extend rounded corner regions to reduce corner artifacts for back images only. Examples: 3mm, 0.125in.")
@click.option("--extend_bleed", help="Extend the outer bleed of outer cards on front pages (odd-numbered pages). Examples: 3mm, 0.125in.")
@click.option("--extend_bleed_backs", help="Extend the outer bleed of outer cards on back pages (even-numbered pages). Examples: 3mm, 0.125in.")
@click.option("--ppi", default=DEFAULT_PPI, type=click.IntRange(min=0), show_default=True, help="Pixels per inch (PPI) when creating PDF.")
@click.option("--quality", default=100, type=click.IntRange(min=0, max=100), show_default=True, help="File compression quality.")
@click.option("--load_offset", default=False, is_flag=True, help="Apply saved offsets. See `offset_pdf.py` for more information.")
@click.option("--skip", default=[], type=click.IntRange(min=0), multiple=True, help="Skip a card based on its index. Useful for registration issues. Examples: 0, 4.")
@click.option("--label", default="", help="Apply a custom label to each page.")
@click.option("--show_outline", default=False, is_flag=True, help="Show a white outline for cutting paths.")
@click.option("--borderless", default=False, is_flag=True, help="Use tighter inset to fit more cards per page.")
@click.version_option("2.2.0")
# ============================

def cli(
    front_dir_path: Path,
    back_dir_path: Path,
    double_sided_dir_path: Path,
    output_path: Path,
    output_images: bool,
    card_size: str,
    paper_size: str,
    registration: Registration,
    registration_orientation: Orientation | None,
    specialty: str | None,
    only_fronts: bool,
    fit: FitMode,
    fit_backs: FitMode,
    crop: str | None,
    crop_backs: str | None,
    extend_edges: str | None,
    extend_edges_backs: str | None,
    extend_corners: str | None,
    extend_corners_backs: str | None,
    extend_bleed: str | None,
    extend_bleed_backs: str | None,
    ppi: int,
    quality: int,
    skip: list[int],
    load_offset: bool,
    label: str,
    show_outline: bool,
    borderless: bool,
) -> None:

    image_paths = ImagePaths(
        front_dir_path.resolve(), 
        back_dir_path.resolve(), 
        double_sided_dir_path.resolve(),
    )
    output_path = prepare_output_path(output_path, output_images)

    cards = find_cards(image_paths, only_fronts)
    
    ppi_scale = ppi / DEFAULT_PPI

    # [!] Need to track down what ACTUALLY happens when None is supplied
    registration_orientation = registration_orientation or Orientation.LANDSCAPE

    #========================
    # Layout
    #========================
    layout_defs = load_layouts()
    layout_def = prepare_layout(
        layout_defs = layout_defs,
        card_size_name = card_size,
        paper_size_name = paper_size,
        borderless = borderless,
        specialty_name = specialty,
        registration_orientation_override = registration_orientation,
    )

    #========================
    # Structure Init
    #========================
    render_opts = CardRenderOptions(
        front = SideRenderOptions(
            crop = crop,
            extend_edges = extend_edges,
            extend_corners_radius = extend_corners,
            extend_bleed = extend_bleed,
            fit = fit,
        ),
        back = SideRenderOptions(
            crop = crop_backs,
            extend_edges = extend_edges_backs,
            extend_corners_radius = extend_corners_backs,
            extend_bleed = extend_bleed_backs,
            fit = fit_backs,
        ),
        orientation = registration_orientation,
    )

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
        skip_indices=skip,
        borderless=borderless,
    )

    render_params = calculate_render_params(
        render_opts=render_opts,
        card_size_def=card_size_def,
        ppi_scale=ppi_scale,
    )

    reg_params = calculate_reg_params(reg_opts=reg_opts, ppi_scale=ppi_scale)

    num_cards = sum(page_layout.card_placements)
    if num_cards == 0:
        raise ValueError(
            f'Card size "{card_size}" does not fit on paper size "{paper_size}".'
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
    # Render Pages
    # ==============================
    pages: list[DuplexPage] = []

    radius_px = parse_to_px(card_size_def.radius or defaults.card_radius, ppi_scale)

    render_geometry = build_render_geometry(
        page_layout=page_layout,
        reg_params=reg_params,
        radius=radius_px,
        borderless=borderless,
    )

    # [!] Card positions is nice for placement, but x_pos and y_pos are useful elsewhere
    canvas_bounds = get_canvas_bounds(render_geometry)
    print("Canvas Bounds:", canvas_bounds)
    blank_canvas = build_canvas(canvas_bounds)
    print("Canvas Size:", blank_canvas.size)

    # [!] Load and process cards by page to minimize RAM usage
    # [!] but keep cards.default_back loaded
    processed_card_back = None

    if not only_fronts:
        if cards.default_back:
            loaded_card_back = load_card_side(cards.default_back)
            processed_card_back = process_card_side(
                loaded_card_back, render_params.back, render_geometry
            )

    for sheet_number, card_batch in enumerate(
        batch_cards(cards.cards, num_cards), 
        start=1,
    ):
        print(f"Processing page {sheet_number}")
        print("  Loading cards...")
        loaded_cards = load_cards(card_batch)
        print("  Processing cards...")
        processed_cards = process_cards(
            loaded_cards,
            processed_card_back,
            render_params,
            render_geometry,
        )

        front_sheet_num = sheet_number if only_fronts else sheet_number * 2 - 1
        label_text = build_label_text(front_sheet_num, layout_def.template, label)

        print("  Placing cards...")
        duplex_page = render_duplex_page(
            bg_image=blank_canvas.copy(),
            card_batch=processed_cards,
            geometry=render_geometry,
        )

        # [!] Placing this here to avoid cyclic imports: draw <-> images
        print("  Adding print bleed...")
        duplex_page = pad_duplex_page(
            duplex_page,
            render_geometry.x_fill,
            render_geometry.y_fill,
        )

        print("  Adding registration...")
        print("  Reg Image size:", reg_image.size)
        duplex_page = add_reg(
            duplex_page,
            reg_image,
            canvas_bounds,
        )

        print("  Adding label...")
        draw_front_label(
            page=duplex_page.front,
            text=label_text,
            position=page_layout.label_position,
            angle=page_layout.label_angle,
            font=ImageFont.truetype(LABEL_FONT, 40 * ppi_scale),
        )


        #print("  Filling gaps...")
        #duplex_page = add_borders(
        #    duplex_page, 
        #    page_layout, 
        #)
        
        #processed_duplex_page = add_print_bleed(
        #    duplex_page,
        #    page_layout,
        #    render_geometry,
        #    render_params,
        #)

        print("  Normalizing page...")
        duplex_page = normalize_pages(duplex_page, orientation)

        print("  Page complete.")
        pages.append(duplex_page)

    if len(pages) == 0:
        print("No pages were generated.")
        return

    print("Drawing outlines...")
    if show_outline:
        # [!] Consolidated calls
        draw_outlines(
            pages,
            page_layout,
            render_geometry.radius,
        )

    print("Offsetting pages...")
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
    
    generate_pdf(
        duplex_pages = pages,
        output_path = output_path,
        output_images = output_images,
        ppi_scale = ppi_scale,
        quality = quality,
    )


if __name__ == "__main__":
    cli()
