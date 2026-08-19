#==================================================================================================
# src/layouts/models.py
#  Houses pydantic model classes which allow for easy ports from JSON. 
#
#  Supports several different access routes: 
#    dict: layouts.paper_layouts["letter"]["standard"]["borderless"]    
#    item: layouts.paper_layouts.papers["letter"].cards["standard"].variants["borderless"]
#    root: layouts.paper_layouts.root["letter"].root["standard"].root["borderless"]
#==================================================================================================

from typing import Self, Generic, TypeVar
from pydantic import BaseModel, RootModel, model_validator

from src.enums import Orientation

T = TypeVar("T", bound=BaseModel)

#============================
# Settings
#============================
# [!] Asserting that this must exist. 
class RegistrationSettings(BaseModel):
    inset: str 
    thickness: str
    length: str

class VariantRegistrationSettings(BaseModel):
    default: RegistrationSettings
    borderless: RegistrationSettings

class DefaultSettings(BaseModel):
    ppi: int
    card_radius: str
    registration: VariantRegistrationSettings

#============================
# Layout
#============================

class CardSizeDef(BaseModel):
    width: str
    height: str
    radius: str | None = None
    aliases: list[str] | None = []

class PaperSizeDef(BaseModel):
    width: str
    height: str
    aliases: list[str] | None = []

    @model_validator(mode="after")
    def validate_orientation(self) -> Self:
        if self.width < self.height:
            # [!] Why not just swap them?
            raise ValueError(
                f"Paper width ({self.width}) must be >= height ({self.height})." 
                + "Paper sizes are stored as landscape."
            )
        return self

class CardLayoutDef(BaseModel):
    orientation: Orientation
    registration_orientation: Orientation | None = None
    version: int
    num_rows: int | None = None
    num_cols: int | None = None
    registration: RegistrationSettings | None = None

#============================
# Specialty Layouts
#============================

class SpecialtyCardSizeDef(BaseModel):
    name: str | None = None
    width: str | None = None
    height: str | None = None
    radius: str | None = None     

class SpecialtyPaperSizeDef(BaseModel):
    name: str | None = None
    width: str | None = None
    height: str | None = None

class SpecialtyLayoutDef(BaseModel):
    card_size: SpecialtyCardSizeDef
    paper_size: SpecialtyPaperSizeDef
    orientation: Orientation = Orientation.LANDSCAPE
    registration_orientation: Orientation | None = None
    version: int = 1
    num_rows: int | None = None
    num_cols: int | None = None
    registration: RegistrationSettings | None = None

#============================
# Collection Classes
#============================
# These could all be identical and access elements via `defs.root[item]`
# but the specificity is nice for autocomplete. 

class Defs(RootModel[dict[str, T]], Generic[T]):
    def names(self) -> list[str]:
        return list(self.root.keys())
    def __getitem__(self, name: str) -> T:
        return self.root[name]
    def __setitem__(self, name: str, value: T) -> None:
        self.root[name] = value 

class CardLayoutDefs(Defs[CardLayoutDef]):
    @property
    def variants(self) -> dict[str, CardLayoutDef]:
        return self.root

class PaperLayoutDef(Defs[CardLayoutDefs]):
    @property
    def cards(self) -> dict[str, CardLayoutDefs]:
        return self.root

class PaperLayoutDefs(Defs[PaperLayoutDef]):
    @property
    def papers(self) -> dict[str, PaperLayoutDef]:
        return self.root

class CardSizeDefs(Defs[CardSizeDef]):
    @property
    def cards(self) -> dict[str, CardSizeDef]:
        return self.root

class PaperSizeDefs(Defs[PaperSizeDef]):
    @property
    def papers(self) -> dict[str, PaperSizeDef]:
        return self.root

class SpecialtyLayoutDefs(Defs[SpecialtyLayoutDef]):
    @property
    def layouts(self) -> dict[str, SpecialtyLayoutDef]:
        return self.root
    def layout(self, name: str) -> SpecialtyLayoutDef:
        return self.root[name]

class LayoutConfig(BaseModel):
    card_sizes: CardSizeDefs
    paper_sizes: PaperSizeDefs
    paper_layouts: PaperLayoutDefs
    specialty_layouts: SpecialtyLayoutDefs

# [!] Slightly misleading name given the rest of the classes
# [!] this is essentially the actual layout object the program uses
# [!] whereas the other classes deal with JSON import structure
#============================
# Output
#============================
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
