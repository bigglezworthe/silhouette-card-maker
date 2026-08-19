# ==============================================================================
# layouts.py
#     Handles the card/page layout system for all card/paper types.
# ==============================================================================
from __future__ import annotations

import json
import os

from src.layout_models import (
    CardLayoutDef,
    CardSizeDef,
    CardSizeDefs,
    DefaultSettings,
    LayoutConfig,
    LayoutDef,
    LayoutDefs,
    PaperLayoutDef,
    PaperLayoutDefs,
    PaperSizeDef,
    PaperSizeDefs,
    ResolvedLayout,
    SpecialtyCardSizeDef,
    SpecialtyLayoutDefs,
    SpecialtyPaperSizeDef
)
from src.paths import Paths
from src.enums import Orientation, Variant

from typing import TypeVar
from pathlib import Path
from pydantic import BaseModel

from src.pdf import create_template_name

T = TypeVar("T", bound=BaseModel)

LAYOUTS_PATH = Paths.assets / "layouts"
CARD_SIZE_DEF_PATH = Paths.assets / "card_sizes.json"
PAPER_SIZE_DEF_PATH = Paths.assets / "paper_sizes.json"
SPECIALTY_LAYOUTS_DEF_PATH = LAYOUTS_PATH / "specialty.json"
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
USER_PAPER_LAYOUTS_PATH = USER_LAYOUTS_PATH / "layout"
USER_SPECIALTY_LAYOUTS_PATH = USER_LAYOUTS_PATH / "specialty"

USER_LAYOUTS_ENV = "SCM_USER_LAYOUTS"

# Optional override for where cutting templates get written/read (default: SCRIPT_DIR-relative
# cutting_templates/ directories in generate_dxf.py and dxf_to_studio3.py).
CUTTING_TEMPLATES_DIR_ENV = "SCM_CUTTING_TEMPLATES_DIR"

# Priorty to use when sorting available paper sizes
PAPER_SIZE_PRIORITY = ["letter", "tabloid", "a4", "a3", "arch_b"]
CARD_SIZE_PRIORITY = ["standard", "poker", "bridge"]

DEFAULT_ORIENTATION = Orientation.LANDSCAPE

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
