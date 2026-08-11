# ==============================================================================
# pdf.py
#     PDF generation
# ==============================================================================
import itertools
import math
import os

from natsort import natsorted

from src import page_manager

from PIL import Image, ImageFont, ImageDraw

from src.measurements import Measurement, MeasureUnits
from src.draw import CardRenderOptions, draw_card_layouts, draw_outlines
from src.enums import FitMode, Orientation, OrientationMode, Registration, Variant
from src.images import (
    MINIMUM_BLEED,
    calculate_max_print_bleed,
    load_card_image,
    parse_crop_string,
    parse_dimension_string,
)
from src.layouts import (
    DEFAULT_ORIENTATION,
    load_defaults,
    load_layouts,
    resolve_layout,
    resolve_specialty_layout,
)
from src.offset import load_saved_offset
from src.paths import (
    ImagePaths,
    Paths,
    check_paths_subset,
    get_directory,
    get_image_file_paths,
    resolve_image_with_any_extension,
    select_back_card_image_path,
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
) -> tuple[Orientation, page_manager.CardLayout]:
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
        return orientation, page_manager.generate_layout(
            orientation=orientation, **kwargs
        )

    # try both orientations and pick the one that fits more cards
    best_count = 0
    best_orientation = preferred
    best_computed = None

    for orient in Orientation:
        try:
            computed = page_manager.generate_layout(orientation=orient, **kwargs)
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
    output_images: bool,
    card_name: str,
    paper_name: str,
    registration: Registration,
    only_fronts: bool,
    render_opts: CardRenderOptions,
    ppi: int,
    quality: int,
    skip_indices: list[int],
    load_offset: bool,
    label: str,
    specialty_name: str | None,
    show_outline: bool = False,
    borderless: bool = False,
    registration_orientation_override: str | None = None,
) -> None:

    # ==============================
    # File ops
    # ==============================
    if output_images:
        image_paths.output = get_directory(image_paths.output)
    else:
        if not image_paths.output.name.lower().endswith(".pdf"):
            raise FileNotFoundError(f"Invalid PDF output path: {image_paths.output}")
        if image_paths.output.parent:
            image_paths.output.parent.mkdir(parents=True, exist_ok=True)

    use_default_back_page = True
    if not only_fronts:
        image_paths.back_image_path = select_back_card_image_path(image_paths.back)
        use_default_back_page = image_paths.back_image_path is None
        if use_default_back_page:
            print(f"No back image provided in back image directory: {image_paths.back}")

    image_paths.front_image_paths = get_image_file_paths(image_paths.front)
    image_paths.double_image_paths = get_image_file_paths(image_paths.double)

    front_set = set(image_paths.front_image_paths)
    ds_set = set(image_paths.double_image_paths)
    diff = check_paths_subset(ds_set, front_set)
    if len(diff) > 0:
        raise Exception(
            f'Double-sided backs "{ds_set - front_set}" do not have matching fronts.'
            + f'Add the missing fronts to front image directory: {image_paths.front}'
        )

    if only_fronts:
        if len(ds_set) > 0:
            raise Exception(
                'Cannot use "--only_fronts" with double-sided cards.' 
                + f'Remove cards from double_side image directory: {image_paths.double}'
            )

    # ==============================
    # Layout
    # ==============================
    layout_defs = load_layouts()
    defaults = load_defaults()

    variant = Variant.BORDERLESS if borderless else Variant.DEFAULT
    default_reg = defaults.registration.borderless if borderless else defaults.registration.default
    registration_orientation_override = (
        Orientation(registration_orientation_override)
        if registration_orientation_override is not None
        else None
    )

    if borderless and specialty_name:
        raise Exception(
            "Cannot use --borderless with --specialty."
            + "Specialty layouts define their own geometry."
        )

    if specialty_name:
        layout_def = resolve_specialty_layout(specialty_name, layout_defs)
    else:
        layout_def = resolve_layout(card_name, paper_name, variant, layout_defs)
        template = create_template_name(paper_name, card_name, variant, layout_def.version)

    if registration_orientation_override:
        layout_def.registration_orientation = registration_orientation_override
    
    layout_def.orientation = layout_def.orientation or DEFAULT_ORIENTATION
    layout_def.registration_orientation = layout_def.registration_orientation or layout_def.orientation
    # ==============================
    # Image modification
    # ==============================
    effective_thickness = default_reg.thickness
    effective_length = default_reg.length
    effective_inset = default_reg.inset

    if layout_def.registration is not None: 
        effective_thickness = layout_def.registration.thickness
        effective_length = layout_def.registration.length
        effective_inset = layout_def.registration.inset

    # [!] This value is extremely suspicious. Why is it default_reg.length instead of effective_length?
    total_exclusion_mm = (
        default_reg.length.to(MeasureUnits.MM).value + page_manager.REG_PADDING_MM
    )
    total_exclusion = Measurement.from_value(total_exclusion_mm, MeasureUnits.MM)

    card_size_def = layout_defs.card_sizes[card_name]
    paper_size_def = layout_defs.paper_sizes[paper_name]

    page_layout = page_manager.generate_layout(
        orientation=layout_def.orientation,
        card_size=(card_size_def.width.px(ppi), card_size_def.height.px(ppi)),
        paper_size=(paper_size_def.width.px(ppi), paper_size_def.height.px(ppi)),
        inset=effective_inset.px(ppi),
        length=total_exclusion.px(ppi),
    )

    card_width_px = page_layout.card_width_px
    card_height_px = page_layout.card_height_px
    page_width_px = page_layout.paper_width_px
    page_height_px = page_layout.paper_height_px
    x_pos = page_layout.x_pos
    y_pos = page_layout.y_pos

    
    crop_size = calculate_crop_size(render_opts.front.crop, page_layout.card_size)
    crop_backs = parse_crop_string(crop_backs_string, card_width_px, card_height_px)

    extend_edges_px = parse_dimension_string(extend_edges, ppi)
    extend_edges_backs_px = parse_dimension_string(
        extend_edges_backs, ppi
    )

    extend_corners_px = parse_dimension_string(extend_corners, ppi)
    extend_corners_backs_px = parse_dimension_string(
        extend_corners_backs, ppi
    )

    extend_bleed_px = parse_dimension_string(extend_bleed, ppi)
    extend_bleed_backs_px = parse_dimension_string(
        extend_bleed_backs, ppi
    )

    fit_backs_mode = FitMode(fit_backs) if fit_backs is not None else fit

    effective_card_radius = card_size_def.radius or defaults.card_radius
    radius_px = measurements.size_to_pixel(effective_card_radius, ppi)

    # ==============================
    # PDF
    # ==============================
    num_rows = len(y_pos)
    num_cols = len(x_pos)
    num_cards = num_rows * num_cols

    if num_cards == 0:
        raise Exception(
            f'Card size "{card_size}" does not fit on paper size "{paper_size}".'
        )

    clean_skip_indices = [n for n in skip_indices if n < num_cards]
    ignore_skip_indices = [n for n in skip_indices if n >= num_cards]

    if len(ignore_skip_indices) > 0:
        print(
            f"Ignoring skip indices that are outside range 0-{num_cards - 1}: {ignore_skip_indices}"
        )

    if len(clean_skip_indices) == num_cards:
        raise ValueError("You cannot skip all cards per page!")

    ppi_ratio = ppi / 300
    inset_px = measurements.size_to_pixel(effective_inset, ppi)
    thickness_px = measurements.size_to_pixel(effective_thickness, ppi)
    if borderless:
        label_margin_px = math.floor(inset_px * ppi_ratio)
    else:
        label_margin_px = math.floor((inset_px - thickness_px * 2) * ppi_ratio)

    reg_is_portrait = registration_orientation == Orientation.PORTRAIT
    reg_width = paper_size_def.height if reg_is_portrait else paper_size_def.width
    reg_height = paper_size_def.width if reg_is_portrait else paper_size_def.height

    # ==============================
    # Page Manager
    # ==============================
    with page_manager.generate_reg_mark(
        reg_width,
        reg_height,
        effective_inset or "",
        effective_thickness or "",
        effective_length or "",
        ppi,
        registration,
    ) as reg_im:
        reg_im = reg_im.resize(
            [
                math.floor(reg_im.width * ppi_ratio),
                math.floor(reg_im.height * ppi_ratio),
            ]
        )

        if registration_orientation != orientation:
            reg_im = reg_im.rotate(90 if reg_is_portrait else -90, expand=True)

        pages: list[Image.Image] = []

        max_print_bleed = calculate_max_print_bleed(
            x_pos, y_pos, card_width_px, card_height_px, MINIMUM_BLEED
        )

        # Cache back
        single_back_image = None
        if not only_fronts and not use_default_back_page:
            if back_card_image_path is not None:
                # [!] Created load_card_image() to remove duplicated code
                single_back_image = load_card_image(back_card_image_path, "back")

        # Create card layout
        num_image = 1
        # [!] Does it really matter that it's natsorted?
        it = iter(
            natsorted(list(check_paths_subset(front_set, ds_set)))
            + natsorted(list(ds_set))
        )
        while True:
            file_group = list(itertools.islice(it, num_cards - len(clean_skip_indices)))
            if not file_group:
                break

            # Get cards in batches
            front_card_images: list[Image.Image | None] = []
            back_card_images: list[Image.Image | None] = []
            file_group_iterator = iter(file_group)
            for i in range(num_cards):
                if i in clean_skip_indices:
                    front_card_images.append(None)
                    back_card_images.append(None)
                    continue
                try:
                    file = next(file_group_iterator)
                except StopIteration:
                    break

                print(f"Image {num_image}: {file}")
                num_image += 1

                front_card_image_path = os.path.join(front_dir_path, file)
                front_card_image_path = resolve_image_with_any_extension(
                    front_card_image_path
                )

                front_card_image = load_card_image(front_card_image_path, "front")
                front_card_images.append(front_card_image)

                if only_fronts:
                    back_card_images.append(None)
                    continue

                if file in ds_set:
                    ds_card_image_path = os.path.join(ds_dir_path, file)

                    # Backside image might have different extension
                    ds_card_image_path = resolve_image_with_any_extension(
                        ds_card_image_path
                    )
                    ds_card_image = load_card_image(ds_card_image_path, "double-sided")
                    back_card_images.append(ds_card_image)
                    continue

                back_card_images.append(single_back_image)

            front_page = reg_im.copy()
            back_page = reg_im.copy()

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
