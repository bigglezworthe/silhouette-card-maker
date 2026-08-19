#==============================================================================
# classes.py
#    Index of all major classes for reference.
#==============================================================================

#================================================
# draw.py
#================================================
#============================
# Options
#============================
# Measurement strings to be parsed

from dataclasses import dataclass


@dataclass(frozen=True)
class SideRenderOptions:
    crop: str | None
    fit: FitMode
    extend_edges: str | None 
    extend_corners_radius: str | None
    extend_bleed: str | None

# [!] Might be able to freeze this? Looks like orientation is the holdup. 
@dataclass(frozen=False) 
class CardRenderOptions:
    front: SideRenderOptions
    back: SideRenderOptions
    orientation: Orientation
    
#============================
# Params
#============================
# Numerical values to be used 

@dataclass(frozen=True)
class SideRenderParams:
    crop: tuple[float, float]
    fit: FitMode
    extend_edges: int 
    extend_corners_radius: int
    extend_bleed: int

# [!] Might be able to freeze this? Looks like orientation is the holdup. 
@dataclass(frozen=False) 
class CardRenderParams:
    front: SideRenderParams
    back: SideRenderParams
    orientation: Orientation

#============================
# Geometry
#============================
@dataclass(frozen=True)
class RenderGeometry:
    page_layout: PageLayout
    max_print_bleed: tuple[int, int]
    radius: int
    label_margin: int
    ppi_ratio: float

#================================================
# page_manager.py
#================================================

# [!] Does max_length need to be in mm? 
@dataclass(frozen=True)
class PageLayout:
    card_width_px: int
    card_height_px: int
    paper_width_px: int
    paper_height_px: int
    x_pos: list[int]
    y_pos: list[int]
    max_length_mm: float 

# [!] UNUSED. layouts.RegistrationSettings is the same
@dataclass(frozen=True)
class RegistrationOptions:
    thickness: str
    inset: str
    length: str

@dataclass(frozen=True)
class RegistrationParams:
    thickness: int
    inset: int
    length: int
    
#================================================
# cards.py
#================================================

@dataclass 
class CardSide:
    name: Path
    path: Path
    image: Image.Image | None = None

@dataclass
class Card:
    front: CardSide
    back: CardSide | None

@dataclass
class Cards:
    cards: list[Card]
    default_back: CardSide | None

#================================================
# layout_models.py
#================================================

class ResolvedLayout(BaseModel):
    card_size: CardSizeDef
    paper_size: PaperSizeDef
    orientation: Orientation | None
    registration_orientation: Orientation | None
    version: int
    num_rows: int | None
    num_cols: int | None 
    registration: RegistrationSettings | None
    template: str | None
