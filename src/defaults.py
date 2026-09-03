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




