from enum import Enum
import itertools
import math
import os
from pathlib import Path
from typing import List, Optional

from natsort import natsorted
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

import page_manager
from src import measurements
from src.enums import FitMode, Registration, Orientation, OrientationMode, Variant
from src.layouts import load_layout_config, RegistrationSettings, CardSizeDef
from src.crop import crop_and_scale_image 
from src.paths import (
        get_directory, 
        ensure_output_directory_exists,
        delete_hidden_files_in_directory,
        get_image_file_paths,
        get_back_card_image_path,
        check_paths_subset,
        resolve_image_with_any_extension,
)
from src.offset import load_saved_offset

# Approximately 1.25mm of bleed assuming 300 PPI: ceil(1.25mm * 1in/25.4mm * 300ppi)
MINIMUM_BLEED = 15


# Borderless mode tricks Silhouette Studio into using a smaller effective inset than its
# 10mm minimum (MIN_REG_INSET_MM) by inflating the declared paper size. The software
# still places registration marks at 10mm from the declared edge, but since the declared
# paper is larger than the real sheet, the marks land closer to the actual paper edge.
#
# BORDERLESS_INSET_MM: the effective inset on the real paper (from layouts.json defaults).
# BORDERLESS_EXPANSION_MM: how much to add to each paper dimension in Silhouette Studio
#   so that the 10mm studio inset becomes BORDERLESS_INSET_MM on the real sheet.
#   Formula: each side gains (MIN_REG_INSET_MM - BORDERLESS_INSET_MM), times 2 for both sides.
_layout_config = load_layout_config()
BORDERLESS_INSET_MM = measurements.size_to_mm(_layout_config.defaults.registration.borderless.inset)
BORDERLESS_EXPANSION_MM = (page_manager.MIN_REG_INSET_MM - BORDERLESS_INSET_MM) * 2


def create_template_name(paper_size: str, card_size: str, variant: Variant, version: int) -> str:
    if variant == Variant.DEFAULT:
        return f"{paper_size}-{card_size}-v{version}"
    else:
        return f"{paper_size}-{card_size}-{variant.value}-v{version}"

def parse_dimension_string(dimension_string: str | None, ppi: int) -> int:
    if dimension_string is None:
        return 0

    valid_units = ["","mm","in","px"]
    amount, unit = measurements.parse_unit_string(dimension_string, valid_units)

    if unit == "mm":
        return math.floor(amount / 25.4 * ppi)
    if unit == "in":
        return math.floor(amount * ppi)
    # Default unit is px
    return int(amount)

def fill_rounded_corners(card_image: Image.Image, corner_radius: int) -> Image.Image:
    """
    Fill the rounded corner regions of a card image with bleed.

    Assumes the card has rounded corners with the specified radius.
    Pixels in the "cut zone" (outside the corner radius arc) are filled
    by extending from the nearest pixel on the arc.

    Args:
        card_image: The card image to modify
        corner_radius: The radius of the rounded corners in pixels

    Returns:
        A new image with filled corners
    """
    import math

    # Create a copy so we don't modify the original
    result = card_image.copy()
    width, height = result.size

    # Define the four corners: (corner_point, center_of_arc)
    corners = [
        ((0, 0), (corner_radius, corner_radius)),  # top-left
        ((width, 0), (width - corner_radius, corner_radius)),  # top-right
        ((0, height), (corner_radius, height - corner_radius)),  # bottom-left
        ((width, height), (width - corner_radius, height - corner_radius)),  # bottom-right
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
                # Calculate distance from this pixel to the arc's center point
                dist = math.sqrt((local_x - arc_cx) ** 2 + (local_y - arc_cy) ** 2)

                # Pixels beyond the corner_radius are in the "cut zone" - the area that
                # will be removed when the card is die-cut with rounded corners
                if dist > corner_radius:
                    # Use polar coordinates to find the nearest point on the arc:
                    # 1. Calculate the angle from the arc center to this cut-zone pixel
                    angle = math.atan2(local_y - arc_cy, local_x - arc_cx)

                    # 2. Project that angle onto the arc at exactly corner_radius distance
                    # This gives us the nearest "good" pixel on the rounded corner edge
                    src_x = int(arc_cx + corner_radius * math.cos(angle))
                    src_y = int(arc_cy + corner_radius * math.sin(angle))

                    # Clamp to image bounds for safety
                    src_x = max(0, min(width - 1, src_x))
                    src_y = max(0, min(height - 1, src_y))

                    # Copy the arc pixel into the cut zone, extending the card image
                    # radially outward to fill what would otherwise be white corners
                    try:
                        pixel = result.getpixel((src_x, src_y))
                        result.putpixel((local_x, local_y), pixel)
                    except (IndexError, ValueError):
                        pass

    return result


def draw_card_with_bleed(
    card_image: Image.Image,
    base_image: Image.Image,
    x: int,
    y: int,
    print_bleed: tuple[int, int],
    extra_bleed: tuple[int, int, int, int] = (0, 0, 0, 0)
):
    """
    Draw a card with bleed on all edges.

    Args:
        card_image: The card image to draw
        base_image: The base image to draw on
        x, y: Position to place the card
        print_bleed: Tuple of (bleed_width, bleed_height) in pixels
        extra_bleed: Additional bleed for outer edges (top, right, bottom, left) in pixels
    """
    bleed_width, bleed_height = print_bleed
    extra_top, extra_right, extra_bottom, extra_left = extra_bleed

    # Calculate total bleed for each edge
    bleed_top = bleed_height + extra_top
    bleed_bottom = bleed_height + extra_bottom
    bleed_left = bleed_width + extra_left
    bleed_right = bleed_width + extra_right

    width, height = card_image.size
    base_image.paste(card_image, (x, y))

    class Axis(int, Enum):
        X = 0
        Y = 1

    def extend_edge(crop_box: tuple[int, int, int, int], start: tuple[int, int], bleed: int, axis: Axis):
        for bleed_i in range(bleed):
            pos = (
                start[0] + (bleed_i if axis == Axis.X else 0),
                start[1] + (bleed_i if axis == Axis.Y else 0)
            )
            base_image.paste(card_image.crop(crop_box), pos)

    def fill_corner(corner_pixel_x: int, corner_pixel_y: int,
                    corner_x: int, corner_y: int,
                    width: int, height: int):
        """Fill a corner bleed region by tiling a single pixel."""
        pixel = card_image.crop((corner_pixel_x, corner_pixel_y, corner_pixel_x + 1, corner_pixel_y + 1))
        for dx in range(width):
            for dy in range(height):
                base_image.paste(pixel, (corner_x + dx, corner_y + dy))

    # Extend the edges of the cards to create print bleed
    # Top and bottom
    extend_edge((0, 0, width, 1), (x, y - bleed_top), bleed_top, Axis.Y)
    extend_edge((0, height - 1, width, height), (x, y + height), bleed_bottom, Axis.Y)

    # Left and right
    extend_edge((0, 0, 1, height), (x - bleed_left, y), bleed_left, Axis.X)
    extend_edge((width - 1, 0, width, height), (x + width, y), bleed_right, Axis.X)

    # Fill four corners with tiled pixels from card corners
    fill_corner(0, 0, x - bleed_left, y - bleed_top, bleed_left, bleed_top)  # Top-left
    fill_corner(width - 1, 0, x + width, y - bleed_top, bleed_right, bleed_top)  # Top-right
    fill_corner(0, height - 1, x - bleed_left, y + height, bleed_left, bleed_bottom)  # Bottom-left
    fill_corner(width - 1, height - 1, x + width, y + height, bleed_right, bleed_bottom)  # Bottom-right

    return base_image

def draw_card_layout(
    card_images: List[Image.Image | None],
    single_back_image: Image.Image,
    base_image: Image.Image,
    num_rows: int,
    num_cols: int,
    x_pos: List[int],
    y_pos: List[int],
    width: int,
    height: int,
    print_bleed: tuple[int, int],
    crop: tuple[float, float],
    crop_backs: tuple[float, float],
    ppi_ratio: float,
    extend_edges: int,
    extend_edges_backs: int,
    extend_corners_radius: int,
    extend_corners_backs_radius: int,
    extend_bleed: int,
    flip: bool,
    fit: FitMode,
    fit_backs: FitMode,
    orientation: Orientation
):
    num_cards = num_rows * num_cols
    crop_percent_x, crop_percent_y = crop
    crop_backs_percent_x, crop_backs_percent_y = crop_backs

    extend_edges_thickness = math.floor(extend_edges * ppi_ratio)
    extend_edges_backs_thickness = math.floor(extend_edges_backs * ppi_ratio)
    extend_corners_thickness = math.floor(extend_corners_radius * ppi_ratio)
    extend_corners_backs_thickness = math.floor(extend_corners_backs_radius * ppi_ratio)
    extend_bleed_thickness = math.floor(extend_bleed * ppi_ratio)

    # Calculate the size of the card after scaling: "scaled size"
    scaled_width = math.floor(width * ppi_ratio)
    scaled_height = math.floor(height * ppi_ratio)

    scaled_bleed_width = math.ceil(print_bleed[0] * ppi_ratio)
    scaled_bleed_height = math.ceil(print_bleed[1] * ppi_ratio)

    # Fill all the spaces with the card back
    for i, card_image in enumerate(card_images):
        if card_image is None:
            continue

        # Calculate base position from layout
        col = i % num_cards % num_cols
        row = (i % num_cards) // num_cols
        # Long-side flip: landscape flips rows, portrait flips columns
        if flip:
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

        # Select parameters based on card type (front vs back).
        # Renaming to active_* allows us to use a single processing path below
        # instead of duplicating the entire image processing logic for fronts and backs.
        if card_image is single_back_image:
            active_crop_x, active_crop_y = crop_backs_percent_x, crop_backs_percent_y
            active_fit = fit_backs
            active_extend_edges_thickness = extend_edges_backs_thickness
            active_extend_corners_thickness = extend_corners_backs_thickness
        else:
            active_crop_x, active_crop_y = crop_percent_x, crop_percent_y
            active_fit = fit
            active_extend_edges_thickness = extend_edges_thickness
            active_extend_corners_thickness = extend_corners_thickness

        # Apply cropping, scaling, and fit mode
        if active_crop_x > 0 or active_crop_y > 0 or active_fit == FitMode.CROP:
            card_image, bleed_offset_x, bleed_offset_y, synthetic_bleed = crop_and_scale_image(
                card_image,
                active_crop_x,
                active_crop_y,
                scaled_width,
                scaled_height,
                scaled_bleed_width,
                scaled_bleed_height,
                active_fit
            )
        else:
            # No percentage crop and STRETCH mode: just scale to target size
            card_image = card_image.resize((scaled_width, scaled_height))

        # Apply extend_edges: simple crop that affects all edges uniformly
        if active_extend_edges_thickness > 0:
            card_image = card_image.crop((
                active_extend_edges_thickness,
                active_extend_edges_thickness,
                card_image.width - active_extend_edges_thickness,
                card_image.height - active_extend_edges_thickness
            ))

        # If extend_corners is specified, fill the corner regions FIRST
        # This modifies the card image so the bleed will be generated from the filled corners
        if active_extend_corners_thickness > 0:
            card_image = fill_rounded_corners(card_image, active_extend_corners_thickness)

        if flip and orientation == Orientation.LANDSCAPE:
            card_image = card_image.rotate(180)

        # Calculate final position
        x = base_x + bleed_offset_x + active_extend_edges_thickness
        y = base_y + bleed_offset_y + active_extend_edges_thickness

        # Calculate total bleed including synthetic bleed and edge extension
        edge_bleed_width = synthetic_bleed[0] + active_extend_edges_thickness
        edge_bleed_height = synthetic_bleed[1] + active_extend_edges_thickness

        # Determine if this card is on an outer edge and should have extended bleed
        # extra_bleed format: (top, right, bottom, left)
        extra_bleed_top = extend_bleed_thickness if row == 0 else 0
        extra_bleed_bottom = extend_bleed_thickness if row == num_rows - 1 else 0
        extra_bleed_left = extend_bleed_thickness if col == 0 else 0
        extra_bleed_right = extend_bleed_thickness if col == num_cols - 1 else 0

        # Generate edge bleed (from the modified card if corners were filled)
        draw_card_with_bleed(
            card_image,
            base_image,
            x,
            y,
            (edge_bleed_width, edge_bleed_height),
            (extra_bleed_top, extra_bleed_right, extra_bleed_bottom, extra_bleed_left)
        )

def draw_outline(
    page: Image.Image,
    x_pos: List[int],
    y_pos: List[int],
    card_width_px: int,
    card_height_px: int,
    radius_px: int,
    ppi_ratio: float,
):
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
                outline='white',
                width=1,
            )

def add_front_back_pages(front_page: Image.Image, back_page: Image.Image, pages: List[Image.Image], page_width: int, page_height: int, ppi_ratio: float, template: str, only_fronts: bool, label: str, orientation: Orientation, label_margin_px: int, borderless: bool):
    font = ImageFont.truetype(os.path.join(asset_directory, 'arial.ttf'), 40 * ppi_ratio)

    num_sheet = len(pages) + 1
    if not only_fronts:
        num_sheet = int(len(pages) / 2) + 1

    label_text = f'sheet: {num_sheet}, template: {template}'
    if label is not None:
        label_text = f'label: {label}, {label_text}'

    # Label goes on the short side of the paper, opposite the top-left black square.
    # Landscape: short sides are left/right; black square top-left → label on RIGHT.
    # Portrait: short sides are top/bottom; black square top-left → label on BOTTOM.
    if orientation == Orientation.LANDSCAPE:
        # Right side: rotate page, draw horizontal text, rotate back
        front_page = front_page.rotate(-90, expand=True)
        draw = ImageDraw.Draw(front_page)
        label_x = math.floor((page_height / 2) * ppi_ratio)
        label_y = math.floor(page_width * ppi_ratio) - label_margin_px
        draw.text((label_x, label_y), label_text, fill=(0, 0, 0), anchor="mm", font=font)
        front_page = front_page.rotate(90, expand=True)
    else:
        # Bottom side: horizontal text
        draw = ImageDraw.Draw(front_page)
        label_x = math.floor((page_width / 2) * ppi_ratio)
        label_y = math.floor(page_height * ppi_ratio) - label_margin_px
        draw.text((label_x, label_y), label_text, fill=(0, 0, 0), anchor="mm", font=font)

    # Rotate portrait pages to landscape so the generated PDF is always landscape.
    # This ensures offset_pdf.py works regardless of card orientation detection.
    if orientation == Orientation.PORTRAIT:
        front_page = front_page.rotate(90, expand=True)
        back_page = back_page.rotate(90, expand=True)

    # Add a back page for every front page template
    pages.append(front_page)
    if not only_fronts:
        pages.append(back_page)

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
    """Resolve an OrientationMode to a concrete Orientation and compute the layout.

    OrientationMode represents user intent:
      - LANDSCAPE or PORTRAIT: Force a specific orientation (manual control)
      - OPTIMIZE: Try both orientations and automatically pick whichever fits more cards

    Orientation is the concrete result (LANDSCAPE or PORTRAIT).

    Args:
        orientation_mode: User's orientation preference (manual or optimize).
        card_width, card_height: Card dimensions as unit strings (e.g., "2.5in").
        paper_width, paper_height: Paper dimensions as unit strings.
        inset, length: Registration mark parameters as unit strings.
        ppi: Pixels per inch for layout computation.
        preferred: Tiebreaker orientation when OPTIMIZE finds equal card counts.

    Returns:
        (chosen_orientation, computed_layout)

    Raises:
        ValueError if no valid layout exists in any tried card orientation.
    """
    kwargs = dict(
        card_width=card_width,
        card_height=card_height,
        paper_width=paper_width,
        paper_height=paper_height,
        inset=inset,
        length=length,
        ppi=ppi,
    )

    # Manual mode: user specified exact card orientation (LANDSCAPE or PORTRAIT)
    if orientation_mode != OrientationMode.OPTIMIZE:
        orientation = Orientation(orientation_mode.value)
        return orientation, page_manager.generate_layout(orientation=orientation, **kwargs)

    # Optimize mode: try both card orientations and pick the one that fits more cards
    best_count = 0
    best_orientation = preferred
    best_computed = None

    for orient in Orientation:
        try:
            computed = page_manager.generate_layout(orientation=orient, **kwargs)
        except ValueError:
            # This card orientation doesn't produce a valid layout, skip it
            continue
        # Count total cards: rows × columns
        count = len(computed.x_pos) * len(computed.y_pos)
        # Keep this card orientation if it fits more cards, or if it's a tie and matches preferred
        if count > best_count or (count == best_count and orient == preferred):
            best_count = count
            best_orientation = orient
            best_computed = computed

    if best_computed is None:
        raise ValueError("No valid layout in either card orientation.")

    return best_orientation, best_computed


def generate_pdf(
    front_dir_path: str,
    back_dir_path: str,
    ds_dir_path: str,
    output_path: str,
    output_images: bool,
    card_size: str,
    paper_size: str,
    registration: Registration,
    only_fronts: bool,
    fit: FitMode,
    fit_backs: str | None,
    crop_string: str | None,
    crop_backs_string: str | None,
    extend_edges: str | None,
    extend_edges_backs: str | None,
    extend_corners: str | None,
    extend_corners_backs: str | None,
    extend_bleed: str | None,
    extend_bleed_backs: str | None,
    ppi: int,
    quality: int,
    skip_indices: List[int],
    load_offset: bool,
    label: str,
    show_outline: bool = False,
    specialty: Optional[str] = None,
    borderless: bool = False,
    registration_orientation_override: Optional[str] = None,
):
    # Sanity checks for the different directories
    f_path = Path(front_dir_path)
    if not f_path.exists() or not f_path.is_dir():
        raise Exception(f'Front image directory path "{f_path}" is invalid.')

    b_path = Path(back_dir_path)
    if not b_path.exists() or not b_path.is_dir():
        raise Exception(f'Back image directory path "{b_path}" is invalid.')

    ds_path = Path(ds_dir_path)
    if not ds_path.exists() or not ds_path.is_dir():
        raise Exception(f'Double-sided image directory path "{ds_path}" is invalid.')

    o_path = Path(output_path)

    # Delete hidden files that may affect image fetching
    delete_hidden_files_in_directory(f_path)
    delete_hidden_files_in_directory(b_path)
    delete_hidden_files_in_directory(ds_path)

    # Sanity check for output images
    if output_images:
        o_path = get_directory(o_path)
    else:
        if not o_path.name.lower().endswith(".pdf"):
            raise Exception(f'Cannot save PDF to output path "{o_path}" because it is not a valid PDF file path.')
        ensure_output_directory_exists(o_path)

    # Get the back image, if it exists
    back_card_image_path = None
    use_default_back_page = True
    if not only_fronts:
        back_card_image_path = get_back_card_image_path(back_dir_path)
        use_default_back_page = back_card_image_path is None
        if use_default_back_page:
            print(f'No back image provided in back image directory \"{back_dir_path}\".')

    front_image_filenames = get_image_file_paths(front_dir_path)
    ds_image_filenames = get_image_file_paths(ds_dir_path)

    # Check if double-sided back images has matching front images
    front_set = set(front_image_filenames)
    ds_set = set(ds_image_filenames)
    diff = check_paths_subset(ds_set, front_set)
    if len(diff) > 0:
        raise Exception(f'Double-sided backs "{ds_set - front_set}" do not have matching fronts. Add the missing fronts to front image directory "{front_dir_path}".')

    if only_fronts:
        if len(ds_set) > 0:
            raise Exception(f'Cannot use "--only_fronts" with double-sided cards. Remove cards from double-side image directory "{ds_dir_path}".')

    layout_config = load_layout_config()
    default_reg = layout_config.defaults.registration.default
    registration_orientation_override = (
        Orientation(registration_orientation_override)
        if registration_orientation_override is not None
        else None
    )

    if borderless and specialty:
        raise Exception('Cannot use --borderless with --specialty. Specialty layouts define their own geometry.')

    if specialty:
        if not layout_config.specialty_layouts or specialty not in layout_config.specialty_layouts:
            raise Exception(f'Specialty layout "{specialty}" not found.')
        spec = layout_config.specialty_layouts[specialty]

        # Resolve card size
        if spec.card_size.name:
            if spec.card_size.name not in layout_config.card_sizes:
                raise Exception(f'Card size "{spec.card_size.name}" not found in card_sizes.')
            base = layout_config.card_sizes[spec.card_size.name]
            card_size_def = CardSizeDef(
                width=base.width,
                height=base.height,
                radius=spec.card_size.radius or base.radius,
            )
        else:
            card_size_def = CardSizeDef(
                width=spec.card_size.width,
                height=spec.card_size.height,
                radius=spec.card_size.radius,
            )

        # Resolve paper size
        if spec.paper_size.name:
            if spec.paper_size.name not in layout_config.paper_sizes:
                raise Exception(f'Paper size "{spec.paper_size.name}" not found in paper_sizes.')
            paper_size_def = layout_config.paper_sizes[spec.paper_size.name]
        else:
            paper_size_def = PaperSizeDef(
                width=spec.paper_size.width,
                height=spec.paper_size.height,
            )

        orientation = spec.orientation
        registration_orientation = spec.registration_orientation or orientation
        if registration_orientation_override is not None:
            registration_orientation = registration_orientation_override
        template = f"{specialty}-v{spec.version}"

        lr = spec.registration or RegistrationSettings()
        effective_inset = lr.inset or default_reg.inset

    else:
        # Resolve aliases
        card_size = resolve_card_size_alias(layout_config, card_size)
        paper_size = resolve_paper_size_alias(layout_config, paper_size)

        # Validate card size
        if card_size not in layout_config.card_sizes:
            raise Exception(f'Unsupported card size "{card_size}". Try card sizes: {list(layout_config.card_sizes.keys())}.')
        card_size_def = layout_config.card_sizes[card_size]

        # Validate paper size
        if paper_size not in layout_config.paper_sizes:
            raise Exception(f'Unsupported paper size "{paper_size}". Try paper sizes: {list(layout_config.paper_sizes.keys())}.')
        paper_size_def = layout_config.paper_sizes[paper_size]

        # Select variant based on borderless flag
        variant = Variant.BORDERLESS if borderless else Variant.DEFAULT

        # Look up layout from nested structure: layouts[paper][card][variant]
        if paper_size not in layout_config.layouts or card_size not in layout_config.layouts[paper_size]:
            raise Exception(f'No layout defined for paper "{paper_size}" with card "{card_size}". Add it to layouts.json.')

        card_layouts = layout_config.layouts[paper_size][card_size]
        if variant.value not in card_layouts:
            raise Exception(f'No {variant.value} layout defined for paper "{paper_size}" with card "{card_size}". Add it to layouts.json.')

        layout_def = card_layouts[variant.value]
        orientation = layout_def.orientation
        registration_orientation = layout_def.registration_orientation or orientation
        if registration_orientation_override is not None:
            registration_orientation = registration_orientation_override
        version = layout_def.version

        # Effective registration: merge per-layout overrides on top of variant defaults
        layout_reg = layout_def.registration
        lr = layout_reg or RegistrationSettings()

        if borderless:
            effective_inset = lr.inset or layout_config.defaults.registration.borderless.inset
        else:
            effective_inset = lr.inset or layout_config.defaults.registration.default.inset

        template = create_template_name(paper_size, card_size, variant, version)

    effective_thickness = lr.thickness or default_reg.thickness
    effective_length = lr.length or default_reg.length

    # Corner exclusion zone = configured mark length + padding constant
    total_exclusion_mm = measurements.size_to_mm(default_reg.length) + page_manager.REG_PADDING_MM
    computed = page_manager.generate_layout(
        orientation=orientation,
        card_width=card_size_def.width,
        card_height=card_size_def.height,
        paper_width=paper_size_def.width,
        paper_height=paper_size_def.height,
        inset=effective_inset,
        length=f"{total_exclusion_mm}mm",
        ppi=layout_config.ppi,
    )

    card_width_px = computed.card_width_px
    card_height_px = computed.card_height_px
    page_width_px = computed.paper_width_px
    page_height_px = computed.paper_height_px
    x_pos = computed.x_pos
    y_pos = computed.y_pos

    # Determine the amount of x and y crop
    crop = parse_crop_string(crop_string, card_width_px, card_height_px)
    crop_backs = parse_crop_string(crop_backs_string, card_width_px, card_height_px)

    # Parse extend_edges, extend_corners, and extend_bleed parameters
    extend_edges_px = parse_dimension_string(extend_edges, layout_config.ppi)
    extend_edges_backs_px = parse_dimension_string(extend_edges_backs, layout_config.ppi)
    extend_corners_px = parse_dimension_string(extend_corners, layout_config.ppi)
    extend_corners_backs_px = parse_dimension_string(extend_corners_backs, layout_config.ppi)
    extend_bleed_px = parse_dimension_string(extend_bleed, layout_config.ppi)
    extend_bleed_backs_px = parse_dimension_string(extend_bleed_backs, layout_config.ppi)

    # Parse fit_backs parameter - if not specified, use the same fit mode as fronts
    fit_backs_mode = FitMode(fit_backs) if fit_backs is not None else fit

    # Convert corner radius to pixels for outline drawing
    effective_card_radius = card_size_def.radius or layout_config.defaults.card_radius
    radius_px = measurements.size_to_pixel(effective_card_radius, layout_config.ppi)

    num_rows = len(y_pos)
    num_cols = len(x_pos)
    num_cards = num_rows * num_cols

    if num_cards == 0:
        raise Exception(f'Card size "{card_size}" does not fit on paper size "{paper_size}".')

    # Check skip indices
    # You can only skip valid indices (within the max card count per page)
    clean_skip_indices = [n for n in skip_indices if n < num_cards]
    ignore_skip_indices = [n for n in skip_indices if n >= num_cards]

    if len(ignore_skip_indices) > 0:
        print(f'Ignoring skip indices that are outside range 0-{num_cards - 1}: {ignore_skip_indices}')

    # If all possible cards are skipped, this may result in an infinite loop
    if len(clean_skip_indices) == num_cards:
        raise Exception('You cannot skip all cards per page')

    # The baseline PPI is 300
    ppi_ratio = ppi / 300

    inset_px = measurements.size_to_pixel(effective_inset, layout_config.ppi)
    thickness_px = measurements.size_to_pixel(effective_thickness, layout_config.ppi)
    if borderless:
        # Different margin for borderless because of space constraints
        label_margin_px = math.floor(inset_px * ppi_ratio)
    else:
        label_margin_px = math.floor((inset_px - thickness_px * 2) * ppi_ratio)

    # Paper sizes are stored as landscape; portrait registration marks need swapped dimensions.
    # When the registration orientation differs from the card layout, rotate the canvas back
    # to match the layout so cards are placed correctly.
    reg_is_portrait = registration_orientation == Orientation.PORTRAIT
    reg_width  = paper_size_def.height if reg_is_portrait else paper_size_def.width
    reg_height = paper_size_def.width  if reg_is_portrait else paper_size_def.height

    # Load an image with the registration marks
    with page_manager.generate_reg_mark(
        reg_width,
        reg_height,
        effective_inset,
        effective_thickness,
        effective_length,
        layout_config.ppi,
        registration,
    ) as reg_im:
        reg_im = reg_im.resize([math.floor(reg_im.width * ppi_ratio), math.floor(reg_im.height * ppi_ratio)])

        if registration_orientation != orientation:
            reg_im = reg_im.rotate(90 if reg_is_portrait else -90, expand=True)

        # Create the array that will store the filled templates
        pages: List[Image.Image] = []

        max_print_bleed = calculate_max_print_bleed(x_pos, y_pos, card_width_px, card_height_px, MINIMUM_BLEED)

        # Load and cache the single back image for reuse
        # Do this if we expect both front and back pages and if we have a back image
        # use_default_back_page indicates no back image was found
        single_back_image = None
        if not only_fronts and not use_default_back_page:
            try:
                # We know the exact image path so we do not need resolve_image_with_any_extension()
                single_back_image = Image.open(back_card_image_path)
                single_back_image = ImageOps.exif_transpose(single_back_image)
            except FileNotFoundError:
                print(f'Cannot get back image "{back_card_image_path}".')
                single_back_image = None
            except OSError as e:
                raise OSError(f'Failed to load back image "{back_card_image_path}": {e}') from e

        # Create card layout
        num_image = 1
        # First iterate on single-sided cards, then iterate on double-sided cards
        it = iter(natsorted(list(check_paths_subset(front_set, ds_set))) + natsorted(list(ds_set)))
        while True:
            file_group = list(itertools.islice(it, num_cards - len(clean_skip_indices)))
            if not file_group:
                break

            # Fetch card art in batches
            # Batch size is based on cards per page
            front_card_images = []
            back_card_images = []
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

                print(f'Image {num_image}: {file}')
                num_image += 1

                front_card_image_path = os.path.join(front_dir_path, file)
                # Allow differing extensions for double-sided images
                # Iteration is a combination of front and double-sided image paths
                front_card_image_path = resolve_image_with_any_extension(front_card_image_path)
                try:
                    front_card_image = Image.open(front_card_image_path)
                    front_card_image = ImageOps.exif_transpose(front_card_image)
                except OSError as e:
                    raise OSError(f'Failed to load front image "{front_card_image_path}": {e}') from e
                front_card_images.append(front_card_image)

                if only_fronts:
                    back_card_images.append(None)
                    continue

                # Add double-sided back image
                if file in ds_set:
                    ds_card_image_path = os.path.join(ds_dir_path, file)
                    # Allow differing extensions for double-sided images
                    # Iteration is a combination of front and double-sided image paths
                    ds_card_image_path = resolve_image_with_any_extension(ds_card_image_path)
                    try:
                        ds_card_image = Image.open(ds_card_image_path)
                        ds_card_image = ImageOps.exif_transpose(ds_card_image)
                    except OSError as e:
                        raise OSError(f'Failed to load double-sided image "{ds_card_image_path}": {e}') from e
                    back_card_images.append(ds_card_image)
                    continue

                back_card_images.append(single_back_image)

            front_page = reg_im.copy()
            back_page = reg_im.copy()

            # Create front layout
            draw_card_layout(
                front_card_images,
                single_back_image,
                front_page,
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
                flip=False,
                fit=fit,
                fit_backs=fit_backs_mode,
                orientation=orientation,
            )

            # Create back layout
            draw_card_layout(
                back_card_images,
                single_back_image,
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
                extend_bleed_backs_px,
                flip=True, # Flip the back sides
                fit=fit,
                fit_backs=fit_backs_mode,
                orientation=orientation,
            )

            # Draw cutting path outlines on top of the card images
            if show_outline:
                draw_outline(front_page, x_pos, y_pos, card_width_px, card_height_px, radius_px, ppi_ratio)
                draw_outline(back_page, x_pos, y_pos, card_width_px, card_height_px, radius_px, ppi_ratio)

            # Add the front and back layouts (also handles portrait→landscape rotation)
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
                borderless
            )

        if len(pages) == 0:
            print('No pages were generated')
            return

        # Load saved offset if available
        if load_offset:
            saved_offset = load_saved_offset()

            if saved_offset is None:
                print('Offset cannot be applied')
            else:
                print(f'Loaded x offset: {saved_offset.x_offset}, y offset: {saved_offset.y_offset}, angle offset: {saved_offset.angle_offset}')
                pages = offset_images(pages, saved_offset.x_offset, saved_offset.y_offset, ppi, saved_offset.angle_offset)

        # Save the pages array as a PDF
        if output_images:
            for index, page in enumerate(pages):
                page.save(os.path.join(output_path, f'page{index + 1}.png'), resolution=math.floor(300 * ppi_ratio), speed=0, subsampling=0, quality=quality)

            print(f'Generated images: {output_path}')

        else:
            pages[0].save(output_path, format='PDF', save_all=True, append_images=pages[1:], resolution=math.floor(300 * ppi_ratio), speed=0, subsampling=0, quality=quality)
            print(f'Generated PDF: {output_path}')


def offset_images(images: List[Image.Image], x_offset: int, y_offset: int, ppi: int, angle_offset: float = 0.0) -> List[Image.Image]:
    result_images = []

    add_offset = False
    for image in images:
        if add_offset:
            # The back page is rotated 180° in the PDF (long-side flip).
            # In orientation-relative terms: +X = right, -X = left, +Y = up, -Y = down.
            # Negating x_offset compensates for the 180° x-axis flip.
            result = ImageChops.offset(image, math.floor(-x_offset * ppi / 300), math.floor(y_offset * ppi / 300))
            # Apply angle rotation if specified
            # Negative angle because PIL rotates counter-clockwise, but we want positive = clockwise
            if angle_offset != 0.0:
                result = result.rotate(-angle_offset, center=(image.width / 2, image.height / 2), fillcolor='white')
            result_images.append(result)
        else:
            result_images.append(image)

        add_offset = not add_offset

    return result_images

def calculate_max_print_bleed(x_pos: List[int], y_pos: List[int], width: int, height: int, min_bleed: int = 0) -> tuple[int, int]:
    if len(x_pos) == 1 and len(y_pos) == 1:
        return (min_bleed, min_bleed)

    x_border_max = min_bleed
    if len(x_pos) >= 2:
        x_pos.sort()

        x_pos_0 = x_pos[0]
        x_pos_1 = x_pos[1]

        x_border_max = max(0, math.ceil((x_pos_1 - x_pos_0 - width) / 2))

    y_border_max = min_bleed
    if len(y_pos) >= 2:
        y_pos.sort()

        y_pos_0 = y_pos[0]
        y_pos_1 = y_pos[1]

        y_border_max = max(0, math.ceil((y_pos_1 - y_pos_0 - height) / 2))

    return (x_border_max, y_border_max)
