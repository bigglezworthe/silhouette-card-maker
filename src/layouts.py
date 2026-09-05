# ==============================================================================
# layouts.py
#     Handles the card/page layout system for all card/paper types.
# ==============================================================================
from __future__ import annotations

from collections.abc import Collection
import json
import math
import os

from src.defaults import DEFAULT_PPI
from src.layout_models import (
    CardLayoutDef,
    CardSizeDef,
    CardSizeDefs,
    DefaultSettings,
    LayoutConfig,
    PaperLayoutDef,
    PaperLayoutDefs,
    PaperSizeDef,
    PaperSizeDefs,
    RegistrationSettings,
    ResolvedLayout,
    ResolvedRegistrationSettings,
    SpecialtyCardSizeDef,
    SpecialtyLayoutDefs,
    SpecialtyPaperSizeDef,
)
from src.measurements import parse_to_px
from src.paths import Paths
from src.enums import Orientation, Variant

from typing import TypeVar
from pathlib import Path
from pydantic import BaseModel

from src.render_models import PageLayout


T = TypeVar("T", bound=BaseModel)

LAYOUTS_PATH = Paths.assets / "layouts"
CARD_SIZE_DEF_PATH = Paths.assets / "card_sizes.json"
PAPER_SIZE_DEF_PATH = Paths.assets / "paper_sizes.json"
SPECIALTY_LAYOUTS_DEF_PATH = LAYOUTS_PATH / "specialty" / "specialty.json"
DEFAULT_SETTINGS_PATH = Paths.assets / "defaults.json" 


# Optional extra layout definitions to merge on top of layouts.json. Lets a layout-consuming
# project layer its own card sizes, paper sizes, and layouts on top of this repo's without
# modifying it. Opt-in: both are empty/unset by default, so load_layout_config() behaves
# exactly as if this didn't exist. Two ways to supply extra files, merged in this order:
#   1. Drop any number of *.json files into USER_LAYOUTS_DIR (merged in filename order) -
#      no configuration needed, just copy a file in.
#   2. Point USER_LAYOUTS_ENV at one or more file paths (os.pathsep-separated, merged in
#      order) - for files that live outside USER_LAYOUTS_DIR.
USER_LAYOUTS_PATH = LAYOUTS_PATH / "user"

USER_CARD_SIZES_PATH = USER_LAYOUTS_PATH / "card_size"
USER_PAPER_SIZES_PATH = USER_LAYOUTS_PATH / "paper_size"
USER_PAPER_LAYOUTS_PATH = USER_LAYOUTS_PATH / "layouts"
USER_SPECIALTY_LAYOUTS_PATH = USER_LAYOUTS_PATH / "specialty"

USER_LAYOUTS_ENV = "SCM_USER_LAYOUTS"

# Optional override for where cutting templates get written/read (default: SCRIPT_DIR-relative
# cutting_templates/ directories in generate_dxf.py and dxf_to_studio3.py).
CUTTING_TEMPLATES_DIR_ENV = "SCM_CUTTING_TEMPLATES_DIR"

# Priorty to use when sorting available paper sizes
PAPER_SIZE_PRIORITY = ["letter", "tabloid", "a4", "a3", "arch_b"]
CARD_SIZE_PRIORITY = ["standard", "poker", "bridge"]

DEFAULT_ORIENTATION = Orientation.LANDSCAPE

def create_template_name(
    paper_size: str, card_size: str, variant: Variant, version: int
) -> str:
    var_string = f"{variant.value}-" if variant != Variant.DEFAULT else ""
    return f"{paper_size}-{card_size}-{var_string}v{version}"

# ============================
# User Layouts
# ============================
def merge_unique_definitions(
    base: dict[str, T],
    extra: dict[str, T],
    path: Path,
) -> None:
    for key, value in extra.items():
        if key in base:
            raise ValueError(f"'{key}' already defined by {path}.")
        base[key] = value 

def merge_user_card_sizes(card_sizes: CardSizeDefs) -> None:
    for path in USER_CARD_SIZES_PATH.glob("*.json"):
        extra = load_from_json(path, CardSizeDefs)
        merge_unique_definitions(card_sizes.cards, extra.cards, path)

def merge_user_paper_sizes(paper_sizes: PaperSizeDefs) -> None: 
    for path in USER_PAPER_SIZES_PATH.glob("*.json"):
        extra = load_from_json(path, PaperSizeDefs)
        merge_unique_definitions(paper_sizes.papers, extra.papers, path)

def merge_user_paper_layouts(paper_layouts: PaperLayoutDefs) -> None:
    for path in USER_PAPER_LAYOUTS_PATH.glob("*.json"):
        extra = load_from_json(path, PaperLayoutDef)
        paper_size = path.stem.lower().strip()
        if paper_size not in paper_layouts.papers:
            paper_layouts[paper_size] = extra
            continue
        existing_paper = paper_layouts[paper_size]
        for card_size, card_layouts in extra.cards.items():
            if card_size not in existing_paper.cards:
                existing_paper.cards[card_size] = card_layouts
                continue

            existing_card = existing_paper.cards[card_size]
            for variant, layout in card_layouts.variants.items():
                # [!] Why crash on collision? Let users override defaults. 
                if variant in existing_card.root:
                    raise ValueError(
                        f"Collision in user layout '{path}': " 
                        + f"{paper_size}/{card_size}/{variant}"
                    )
                existing_card.variants[variant] = layout

def merge_user_specialty_layouts(specialty_layouts: SpecialtyLayoutDefs) -> None:
    for path in USER_SPECIALTY_LAYOUTS_PATH.glob("*.json"):
        extra = load_from_json(path, SpecialtyLayoutDefs)
        merge_unique_definitions(specialty_layouts.layouts, extra.layouts, path)

# ============================
# Resolvers
# ============================
def resolve_specialty_card_size(
    spec_card: SpecialtyCardSizeDef,
    card_sizes: CardSizeDefs,
) -> CardSizeDef:
    if spec_card.name:
        try:
            base = card_sizes[spec_card.name]
        except KeyError:
            raise ValueError(f"Card size not found: {spec_card.name}")
        base = card_sizes[spec_card.name]
        return CardSizeDef(
            width=spec_card.width or base.width,
            height=spec_card.height or base.height,
            radius=spec_card.radius or base.radius,
        )
    if (
        spec_card.width is None
        or spec_card.height is None
        or spec_card.radius is None
    ):
        raise ValueError(
            "Specialty card size must specify either a "
            + "card size name or width, height, and radius."
        )

    return CardSizeDef(
        width=spec_card.width,
        height=spec_card.height,
        radius=spec_card.radius,
    )

def resolve_specialty_paper_size(
    spec_paper: SpecialtyPaperSizeDef,
    paper_sizes: PaperSizeDefs,
) -> PaperSizeDef:
    if spec_paper.name:
        try:
            base = paper_sizes[spec_paper.name]
        except KeyError:
            raise ValueError(f"paper size not found: {spec_paper.name}")
        base = paper_sizes[spec_paper.name]
        return PaperSizeDef(
            width=spec_paper.width or base.width,
            height=spec_paper.height or base.height,
        )
    if spec_paper.width is None or spec_paper.height is None:
        raise ValueError("Specialty paper size must specify either a paper size name or width and height.")

    return PaperSizeDef(
        width=spec_paper.width,
        height=spec_paper.height,
    ) 

def resolve_specialty_layout(
    spec_name: str,
    layout_defs: LayoutConfig,
) -> ResolvedLayout:
    try:
        spec_def = layout_defs.specialty_layouts[spec_name]
    except KeyError:
        raise ValueError(f"Specialty Layout does not exist: {spec_name}")
    
    card_size = resolve_specialty_card_size(spec_def.card_size, layout_defs.card_sizes)
    paper_size = resolve_specialty_paper_size(spec_def.paper_size, layout_defs.paper_sizes)
    
    paper_name = spec_def.paper_size.name 

    num_rows = spec_def.num_rows
    num_cols = spec_def.num_cols
    orientation = spec_def.orientation or DEFAULT_ORIENTATION
    reg_orientation = spec_def.orientation or orientation
    
    if paper_name and paper_name in layout_defs.paper_layouts.papers:
        paper_layout = layout_defs.paper_layouts[paper_name]
        card_name = spec_def.paper_size.name 
        if card_name and card_name in paper_layout.cards:
            card_layouts = paper_layout.cards[card_name]
            if "default" in card_layouts.variants:
                card_layout = card_layouts["default"]
                num_rows = num_rows or card_layout.num_rows
                num_cols = num_cols or card_layout.num_cols
                reg_orientation = reg_orientation or card_layout.orientation

    return ResolvedLayout(
        card_size = card_size,
        paper_size = paper_size,
        orientation = orientation, 
        registration_orientation = reg_orientation,
        version = spec_def.version,
        num_rows = num_rows,
        num_cols = num_cols,
        registration = spec_def.registration,
        template = None,
    )

def resolve_layout( 
    card_name: str, 
    paper_name: str,
    variant: Variant,
    layouts: LayoutConfig,
) -> ResolvedLayout:

    card_layout = load_card_layout(card_name, paper_name, variant)
    template = create_template_name(card_name, paper_name, variant, card_layout.version)
    return ResolvedLayout(
        card_size = layouts.card_sizes[card_name],
        paper_size = layouts.paper_sizes[paper_name],
        orientation = card_layout.orientation,
        registration_orientation=card_layout.registration_orientation,
        version = card_layout.version,
        num_rows = card_layout.num_rows,
        num_cols = card_layout.num_cols,
        registration = card_layout.registration,
        template = template,
    )

def resolve_cutting_templates_dir(default: Path) -> Path:
    override = os.getenv(CUTTING_TEMPLATES_DIR_ENV)
    return Path(override) if override else default

def resolve_card_size_alias(card_sizes: CardSizeDefs, card_size: str) -> str:
    for name, card_def in card_sizes.cards.items():
        if card_def.aliases and (card_size in card_def.aliases):
            print(
                f"Card size '{card_size}' is an alias of '{name}'. Using '{name}' card size and cutting template."
            )
    return card_size

def resolve_paper_size_alias(paper_sizes: PaperSizeDefs, paper_size: str) -> str:
    for name, paper_def in paper_sizes.papers.items():
        if paper_def.aliases and (paper_size in paper_def.aliases):
            print(
                f"Paper size '{paper_size}' is an alias of '{name}'. Using '{name}' paper size and cutting template."
            )
            return name
    return paper_size

# ============================
# Get All's
# ============================
def get_all_card_size_names() -> list[str]:
    card_sizes = load_card_sizes()
    names = card_sizes.names()
    for card_size in card_sizes.cards.values():
        if card_size.aliases:
            names.extend(card_size.aliases)
    return biased_sort(names, ["standard", "poker", "bridge"])

def get_all_paper_size_names() -> list[str]:
    paper_sizes = load_paper_sizes()
    names = paper_sizes.names()

    for paper_size in paper_sizes.papers.values():
        if paper_size.aliases:
            names.extend(paper_size.aliases)
    return biased_sort(names, PAPER_SIZE_PRIORITY)

def get_all_specialty_layout_names() -> list[str]:
    specialty_layouts = load_specialty_layouts()
    if specialty_layouts: 
        return sorted(specialty_layouts.names())
    return []

# ============================
# Load Config
# ============================
# [!] Why are we loading everything? Just load the requested types. 
def load_from_json(path: Path, model: type[T]) -> T:
    with open(path, 'r') as f:
        data: object = json.load(f)
    return model.model_validate(data)

def load_card_sizes() -> CardSizeDefs:
    card_sizes = load_from_json(CARD_SIZE_DEF_PATH, CardSizeDefs)
    merge_user_card_sizes(card_sizes)
    return card_sizes

def load_paper_sizes() -> PaperSizeDefs:
    paper_sizes = load_from_json(PAPER_SIZE_DEF_PATH, PaperSizeDefs)
    merge_user_paper_sizes(paper_sizes)
    return paper_sizes

def load_paper_layout(paper_size: str) -> PaperLayoutDef:
    layout_path = LAYOUTS_PATH / (paper_size + ".json")
    return load_from_json(layout_path, PaperLayoutDef)

def load_card_layout(card_size: str, paper_size: str, reg_variant: Variant = Variant.DEFAULT) -> CardLayoutDef:
    return load_paper_layout(paper_size).cards[card_size].variants[reg_variant]

def load_paper_layouts() -> PaperLayoutDefs:
    paper_layouts: dict[str, PaperLayoutDef] = {}
    for path in LAYOUTS_PATH.glob("*.json"):
        paper_layouts[path.stem.lower().strip()] = load_from_json(path, PaperLayoutDef)

    paper_layout_defs = PaperLayoutDefs(paper_layouts)
    merge_user_paper_layouts(paper_layout_defs)
    return paper_layout_defs

def load_specialty_layouts() -> SpecialtyLayoutDefs: 
    specialty_layouts = load_from_json(SPECIALTY_LAYOUTS_DEF_PATH, SpecialtyLayoutDefs)
    merge_user_specialty_layouts(specialty_layouts)
    return specialty_layouts

def load_defaults() -> DefaultSettings:
    return load_from_json(DEFAULT_SETTINGS_PATH, DefaultSettings)    

def load_layouts() -> LayoutConfig:
    return LayoutConfig(
        card_sizes=load_card_sizes(), 
        paper_sizes=load_paper_sizes(), 
        paper_layouts=load_paper_layouts(), 
        specialty_layouts=load_specialty_layouts(),
    )

#=============================
# Prepare Layout Def
#=============================
def prepare_layout(
    layout_defs: LayoutConfig,
    card_size_name: str,
    paper_size_name: str,
    borderless: bool = False,
    specialty_name: str | None = None,
    registration_orientation_override: str | None = None,
) -> ResolvedLayout:

    variant = Variant.BORDERLESS if borderless else Variant.DEFAULT
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
        layout_def = resolve_layout(card_size_name, paper_size_name, variant, layout_defs)

    if registration_orientation_override:
        layout_def.registration_orientation = registration_orientation_override
    
    layout_def.orientation = layout_def.orientation or DEFAULT_ORIENTATION
    layout_def.registration_orientation = layout_def.registration_orientation or layout_def.orientation

    return layout_def

# ============================
# Misc
# ============================
# [!] Don't have a good place to put this and it's only used in this file
def biased_sort(items: list[str], priority: list[str]) -> list[str]:
    priority_items = [s for s in priority if s in items]
    rest = sorted(
        (s for s in items if s not in priority), key=lambda s: (s[0].isdigit(), s)
    )
    return priority_items + rest

#============================
# Page
#============================

def resolve_reg_opts(
    default_reg: ResolvedRegistrationSettings,
    layout_reg: RegistrationSettings | None,
) -> ResolvedRegistrationSettings:

    if layout_reg is None:
        return default_reg

    # These will never be blank.
    return ResolvedRegistrationSettings(
        thickness = (
            layout_reg.thickness
            if layout_reg.thickness is not None
            else default_reg.thickness
        ),
        length = (
            layout_reg.length
            if layout_reg.length is not None
            else default_reg.length
        ),
        inset = (
            layout_reg.inset
            if layout_reg.inset is not None
            else default_reg.inset
        ),
    )


"""
Card layout computation with strict registration-mark corner exclusion.

This module computes card positions on a page while respecting:
- paper orientation
- bleed spacing between cards
- Silhouette registration mark inset
- square corner exclusion zones where NOTHING may appear
  (neither cards nor bleed)

If no valid layout fits without intruding into corner zones,
layout generation FAILS explicitly.

────────────────────────────────────────────────────────────────────────────
TERMINOLOGY

paper edge
┌─────────────────────────────────────┐
│ inset                               │
│   ┌──────────────┐                  │
│   │ corner zone  │ ← corner_len     │
│   └──────────────┘                  │
│                                     │
│        usable area                  │
│   ┌─────────────────────────────┐   │
│   │   bleed | card | bleed      │   │
│   │   bleed | card | bleed      │   │
│   └─────────────────────────────┘   │
└─────────────────────────────────────┘

Definitions:
- inset: distance from paper edge to registration marks
- corner_len: how far registration marks extend inward
- corner zone: square (corner_len × corner_len) at each corner
- usable area: page minus margins
- grid: cards PLUS surrounding bleed (entire grid must avoid corner zones)
"""

# ─────────────────────────────────────────────────────────────────────────────
# 1. Normalize page size for orientation
# ─────────────────────────────────────────────────────────────────────────────


def normalize_page_size(
    orientation: Orientation,
    paper_width: int,
    paper_height: int,
) -> tuple[int, int]:
    """
    layouts.json stores paper sizes as landscape (width > height).
    Portrait swaps width and height; card dimensions are never swapped.
    """
    if orientation == Orientation.PORTRAIT:
        return paper_height, paper_width
    return paper_width, paper_height

# ─────────────────────────────────────────────────────────────────────────────
# 2. Compute how many cards fit along one axis
# ─────────────────────────────────────────────────────────────────────────────

def compute_grid_fit(
    usable: int,
    card: int,
    bleed: int,
) -> int:
    """
    Compute how many cards fit along a single dimension.

    | bleed | card | bleed | card | bleed |
      ^---------------------------------^ usable

    But bleed can extend beyond the usable area. Only cards must be in the usable area.

    n cards require:
        n * card + (n - 1) * bleed

    so:
        n <= (usable + bleed) / (card + bleed)
    """
    if usable <= 0:
        return 0
    return max(0, math.floor((usable + bleed) / (card + bleed)))

# ─────────────────────────────────────────────────────────────────────────────
# 3. Select margins that avoid corner exclusion zones
# ─────────────────────────────────────────────────────────────────────────────

def select_best_margins(
    page_width: int,
    page_height: int,
    card_width: int,
    card_height: int,
    bleed: int,
    inset: int,
    corner_len: int,
) -> tuple[int, int, int, int, int, int]:
    """
    Try margin strategies and select the one that:
    - keeps the ENTIRE grid (cards + bleed) out of corner zones
    - fits the maximum number of cards

    Returns:
        (cols, rows, margin_x, margin_y, usable_width, usable_height)

    Failure:
        Raises ValueError if no valid layout exists.

    Corner rule:
    A layout overlaps a corner zone if the grid intrudes within corner_len
    of the inset boundary on BOTH axes simultaneously.

    For each margin strategy, three candidate (cols, rows) counts are tried:
      1. (max_cols, max_rows) — maximum cards.
      2. (cols_clear, max_rows) — reduce cols until x gap clears the corner zone.
      3. (max_cols, rows_clear) — reduce rows until y gap clears the corner zone.
    Candidates 2 and 3 are symmetric: each shrinks one axis just enough to
    guarantee clearance on that axis, leaving the other axis at its maximum.
    """

    strategies = [
        (inset, inset),  # minimal margins
        (inset + corner_len, inset),  # clear corners horizontally
        (inset, inset + corner_len),  # clear corners vertically
    ]

    best = None
    best_count = 0

    def record_if_valid(
        cols: int,
        rows: int,
        margin_x: int, 
        margin_y: int, 
        usable_width: int,
        usable_height: int,
    ) -> None:

        nonlocal best, best_count
        if cols <= 0 or rows <= 0:
            return
        grid_width = cols * card_width + (cols + 1) * bleed
        grid_height = rows * card_height + (rows + 1) * bleed
        gap_x = margin_x + (usable_width - grid_width) / 2 - inset
        gap_y = margin_y + (usable_height - grid_height) / 2 - inset
        if gap_x < corner_len and gap_y < corner_len:
            return
        count = cols * rows
        if count > best_count:
            best_count = count
            best = (cols, rows, margin_x, margin_y, usable_width, usable_height)

    for margin_x, margin_y in strategies:
        usable_width = page_width - 2 * margin_x
        usable_height = page_height - 2 * margin_y

        max_cols = compute_grid_fit(usable_width, card_width, bleed)
        max_rows = compute_grid_fit(usable_height, card_height, bleed)

        if max_cols == 0 or max_rows == 0:
            continue

        # Candidate 1: (max_cols, max_rows)
        record_if_valid(
            max_cols, max_rows, margin_x, margin_y, usable_width, usable_height
        )

        # Candidates 2 and 3: shrink one axis until that axis clears the corner zone.
        # Derived from gap >= corner_len:
        #   gap_x = margin_x + (usable_w - cols*(cw+b) - b)/2 - inset >= corner_len
        #   → cols <= (usable_w - b - 2*(corner_len - margin_x + inset)) / (cw+b)
        # (same formula for rows/y by symmetry)
        cols_clear = max(
            0,
            math.floor(
                (usable_width - bleed - 2 * (corner_len - margin_x + inset))
                / (card_width + bleed)
            ),
        )
        rows_clear = max(
            0,
            math.floor(
                (usable_height - bleed - 2 * (corner_len - margin_y + inset))
                / (card_height + bleed)
            ),
        )
        record_if_valid(
            cols_clear, max_rows, margin_x, margin_y, usable_width, usable_height
        )  # candidate 2
        record_if_valid(
            max_cols, rows_clear, margin_x, margin_y, usable_width, usable_height
        )  # candidate 3

    if best is None:
        raise ValueError(
            "No valid layout fits without intruding into corner exclusion zones."
        )

    return best


# ─────────────────────────────────────────────────────────────────────────────
# 4. Compute centered card positions
# ─────────────────────────────────────────────────────────────────────────────

def compute_card_positions(
    cols: int,
    rows: int,
    card_width: int,
    card_height: int,
    bleed: int,
    margin_x: int,
    margin_y: int,
    usable_width: int,
    usable_height: int,
) -> tuple[list[int], list[int], int, int]:
    """
    Center the card grid within the usable area and return positions.
    """

    grid_width = cols * card_width + (cols + 1) * bleed
    grid_height = rows * card_height + (rows + 1) * bleed

    start_x = round(margin_x + (usable_width - grid_width) / 2 + bleed)
    start_y = round(margin_y + (usable_height - grid_height) / 2 + bleed)

    x_pos = [start_x + i * (card_width + bleed) for i in range(cols)]
    y_pos = [start_y + j * (card_height + bleed) for j in range(rows)]

    return x_pos, y_pos, start_x, start_y

def build_card_positions(
    rows: list[int],
    cols: list[int],
) -> list[tuple[int, int]]:
    return [(row, col) for row in rows for col in cols]

def mirror_card_positions(
    rows: list[int],
    cols: list[int],
    mirror_rows: bool = True,
    mirror_cols: bool = True,
) -> list[tuple[int, int]]:
    row_sum = min(rows) + max(rows)
    col_sum = min(cols) + max(cols)
    return[
        (
            row_sum - row if mirror_rows else row, 
            col_sum - col if mirror_cols else col,
        ) 
        for row in rows for col in cols
    ]

def calculate_label_position(
    inset: int,
    thickness: int,
    page_width: int,
    page_height: int,
    borderless: bool,
    orientation: Orientation,
) -> tuple[tuple[int, int], int]: 
    if borderless:
        label_margin = inset
    else:
        label_margin = inset - (thickness * 2)

    if orientation == Orientation.LANDSCAPE:
        label_position = (
            page_width - label_margin,
            page_height // 2,
        )
        label_angle = 90
    else:
        label_position = (
            page_width // 2,
            page_height - label_margin, 
        )
        label_angle = 0

    return label_position, label_angle

def resolve_card_placements(
    skip_indices: Collection[int],
    num_cards: int,
) -> list[bool]:
    valid_indices = {n for n in skip_indices if n < num_cards}
    invalid_indices = set(skip_indices) - valid_indices 

    if len(invalid_indices) > 0:
        print(
            "Ignoring skip indices that are outside range "
            + f"0-{num_cards - 1}: {invalid_indices}"
        )

    if len(valid_indices) == num_cards:
        raise ValueError("You cannot skip all cards per page!")

    return [index not in valid_indices for index in range(num_cards)]  

def generate_layout(
    orientation: Orientation,
    card_width: str,
    card_height: str,
    paper_width: str,
    paper_height: str,
    inset: str,
    thickness: str,
    length: str,
    ppi_scale: float,
    skip_indices: list[int],
    borderless: bool,
) -> PageLayout:
    """
    Compute card positions on a page, accounting for margins, bleed,
    orientation, and strict registration mark corner exclusion zones.

    Raises:
        ValueError if no valid layout exists.
    """

    # Equivalent to double the bleed
    CARD_DISTANCE = "1.25mm"

    # Convert all dimensions to pixels
    card_distance_px = parse_to_px(CARD_DISTANCE, ppi_scale)
    page_width_px = parse_to_px(paper_width, ppi_scale)
    page_height_px = parse_to_px(paper_height, ppi_scale)
    card_width_px = parse_to_px(card_width, ppi_scale)
    card_height_px = parse_to_px(card_height, ppi_scale)
    inset_px = parse_to_px(inset, ppi_scale)
    thickness_px = parse_to_px(thickness, ppi_scale)
    length_px = parse_to_px(length, ppi_scale)

    # Normalize orientation
    page_width_px, page_height_px = normalize_page_size(orientation, page_width_px, page_height_px)

    # Select margins and grid size (strict — no fallback)
    cols, rows, margin_x, margin_y, usable_w, usable_h = select_best_margins(
        page_width_px,
        page_height_px,
        card_width_px,
        card_height_px,
        card_distance_px,
        inset_px,
        length_px,
    )

    # Compute card positions
    x_pos, y_pos, start_x, start_y = compute_card_positions(
        cols,
        rows,
        card_width_px,
        card_height_px,
        card_distance_px,
        margin_x,
        margin_y,
        usable_w,
        usable_h,
    )

    # Maximum registration mark length that fits with a bleed safety buffer
    max_length_px = max(
        0, max(start_x - inset_px, start_y - inset_px) - card_distance_px
    )
    # [!] Need to find a better conversion.
    max_length_mm = round(max_length_px * 25.4 / (ppi_scale * DEFAULT_PPI), 2)
    
    card_positions = build_card_positions(y_pos, x_pos)
    back_positions = mirror_card_positions(y_pos, x_pos, mirror_cols=False)

    card_placements = resolve_card_placements(
        skip_indices = skip_indices,
        num_cards = len(card_positions),
    )

    label_position, label_angle = calculate_label_position(
        inset=inset_px,
        thickness=thickness_px,
        page_width=page_width_px,
        page_height=page_height_px,
        borderless=borderless,
        orientation=orientation,
    )

    return PageLayout(
        card_width_px = card_width_px,
        card_height_px = card_height_px,
        paper_width_px = page_width_px,
        paper_height_px = page_height_px,
        card_positions = card_positions,
        back_positions = back_positions,
        card_placements = card_placements,
        label_position = label_position,
        label_angle = label_angle,
        num_rows = len(y_pos),
        num_cols = len(x_pos),
        max_length_mm = max_length_mm,
    )
