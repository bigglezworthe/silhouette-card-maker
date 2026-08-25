from dataclasses import dataclass
from pathlib import Path
from PIL import Image

from src.enums import FitMode, Orientation

#==========================================================
# page_manager.py
#==========================================================
# [!] Might need renaming to avoid confusion with Layout_Models
@dataclass(frozen=True)
class PageLayout:
    card_width_px: int
    card_height_px: int
    paper_width_px: int
    paper_height_px: int
    card_positions: list[tuple[int, int]]
    back_positions: list[tuple[int, int]]
    label_position: tuple[int, int]
    label_angle: int
    num_rows: int
    num_cols: int
    max_length_mm: float 

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

#==========================================================
# draw.py
#==========================================================

#============================
# Options
#============================
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

# [!] Need to figure out the appropriate bleed to use here
@dataclass(frozen=True)
class RenderGeometry:
    page_layout: PageLayout
    max_print_bleed_width: int
    max_print_bleed_height: int
    radius: int
    label_margin: int

#==========================================================
# cards.py
#==========================================================
# Processed = Images, Unprocessed = Paths 

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

@dataclass(frozen=True)
class ProcessedCardSide:
    image: Image.Image
    offset_x: int
    offset_y: int
    synthetic_bleed_width: int
    synthetic_bleed_height: int

@dataclass
class ProcessedCard:
    front: ProcessedCardSide
    back: ProcessedCardSide | None

@dataclass
class ProcessedCards:
    cards: list[ProcessedCard]

#==========================================================
# images.py
#==========================================================
@dataclass(frozen=True)
class CardRenderGeometry:
    width: int
    height: int
    print_bleed_x: int
    print_bleed_y: int
    ppi_scale: float


