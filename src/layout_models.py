#==================================================================================================
# src/layouts/models.py
#  Houses pydantic model classes which allow for easy ports from JSON. 
#
#  Supports several different levels of robustness and redundancy: 
#    Ex: layouts.paper_layouts["letter"]["standard"]["borderless"]    
#    Ex: layouts.paper_layouts.paper["letter"].card["standard"].variant["borderless"]
#==================================================================================================

from typing import Annotated, Self, Generic, TypeVar

from pydantic import BaseModel, BeforeValidator, RootModel, model_validator

from src.measurements import Measurement
from src.enums import Orientation

T = TypeVar("T", bound=BaseModel)
#============================
# Type Validator
#============================
def validate_measurement(value: Measurement | str) -> Measurement:
    if isinstance(value, Measurement):
        return value
    return Measurement.parse(value)

MeasurementField = Annotated[
    Measurement,
    BeforeValidator(validate_measurement)
]

#============================
# Settings
#============================
# [!] Asserting that this must exist. 
class RegistrationSettings(BaseModel):
    inset: Measurement
    thickness: Measurement
    length: Measurement

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
    width: Measurement
    height: Measurement
    radius: Measurement | None = None
    aliases: list[str] | None = []

class PaperSizeDef(BaseModel):
    width: Measurement
    height: Measurement
    aliases: list[str] | None = []

    @model_validator(mode="after")
    def validate_orientation(self) -> Self:
        if self.width.value < self.height.value:
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
    width: Measurement | None = None
    height: Measurement | None = None
    radius: Measurement | None = None     

class SpecialtyPaperSizeDef(BaseModel):
    name: str | None = None
    width: Measurement | None = None
    height: Measurement | None = None

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

class Defs(RootModel[dict[str, T]], Generic[T]):
    def names(self) -> list[str]:
        return list(self.root.keys())
    def __getitem__(self, name: str) -> T:
        return self.root[name]
    def __setitem__(self, name: str, value: T) -> None:
        self.root[name] = value 

class CardLayoutDefs(Defs[CardLayoutDef]):
    def variants(self) -> dict[str, CardLayoutDef]:
        return self.root
    def variant(self, name: str) -> CardLayoutDef:
        return self.root[name]

class PaperLayoutDef(Defs[CardLayoutDefs]):
    def cards(self) -> dict[str, CardLayoutDefs]:
        return self.root
    def card(self, name: str) -> CardLayoutDefs:
        return self.root[name]

class PaperLayoutDefs(Defs[PaperLayoutDef]):
    def papers(self) -> dict[str, PaperLayoutDef]:
        return self.root
    def paper(self, name: str) -> PaperLayoutDef:
        return self.root[name]

class CardSizeDefs(Defs[CardSizeDef]):
    def cards(self) -> dict[str, CardSizeDef]:
        return self.root
    def card(self, name: str) -> CardSizeDef:
        return self.root[name]

class PaperSizeDefs(Defs[PaperSizeDef]):
    def papers(self) -> dict[str, PaperSizeDef]:
        return self.root
    def paper(self, name: str) -> PaperSizeDef:
        return self.root[name]

class SpecialtyLayoutDefs(Defs[SpecialtyLayoutDef]):
    def layouts(self) -> dict[str, SpecialtyLayoutDef]:
        return self.root
    def layout(self, name: str) -> SpecialtyLayoutDef:
        return self.root[name]

class LayoutDefs(BaseModel):
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
class LayoutDef(BaseModel):
    card_size: CardSizeDef
    paper_size: PaperSizeDef
    orientation: Orientation | None
    registration_orientation: Orientation | None
    version: int
    num_rows: int | None
    num_cols: int | None 
    registration: RegistrationSettings | None
