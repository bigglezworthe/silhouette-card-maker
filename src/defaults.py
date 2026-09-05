from src.layout_models import ResolvedRegistrationSettings

DEFAULT_PPI = 300
DEFAULT_CARD_RADIUS = "3mm"

DEFAULT_REG_SETTINGS = ResolvedRegistrationSettings(
    inset = "10mm",
    thickness = "1mm",
    length = "5mm",
)
DEFAULT_BORDERLESS_REG_SETTINGS = ResolvedRegistrationSettings(
    inset = "3.5mm",
    thickness = "1mm",
    length = "5mm",
)

# Approximately 1.25mm of bleed in px assuming 300ppi: ceil(1.25mm * 1in/25.4mm * 300px/1in)
MINIMUM_PRINT_BLEED = 15

# Registration mark constraints (in mm)
MAX_REG_LENGTH_MM = 20.0
MAX_REG_THICKNESS_MM = 1.0
MAX_REG_INSET_MM = 86.36
MIN_REG_LENGTH_MM = 5.0
MIN_REG_THICKNESS_MM = 0.5
MIN_REG_INSET_MM = 10.0
REG_PADDING_MM = 1.5  # Extra clearance around registration marks

# [!] Previously loaded from defaults.json
BORDERLESS_INSET_MM = 10
BORDERLESS_EXPANSION_MM = (MIN_REG_INSET_MM - BORDERLESS_INSET_MM) * 2
