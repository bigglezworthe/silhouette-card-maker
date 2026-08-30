from dataclasses import dataclass
import math

from PIL import Image

from src.render_models import CardRenderOptions, CardRenderParams, SideRenderParams, RegistrationParams
from src.enums import FitMode
from src.layout_models import CardSizeDef, ResolvedRegistrationSettings
from src.measurements import parse_measurement, parse_to_in, parse_to_mm, parse_to_px

#============================
# Unit Conversion
#============================
# Converts strings and things to numbers
def calculate_render_params(
    render_opts: CardRenderOptions,
    card_size_def: CardSizeDef,
    ppi_scale: float,
) -> CardRenderParams: 

    # Percents are in decimal (0<=%<=1)
    crop_x_percent = calculate_crop_percent(render_opts.front.crop, card_size_def.width)
    crop_y_percent = calculate_crop_percent(render_opts.front.crop, card_size_def.height)
    crop_back_x_percent = calculate_crop_percent(render_opts.back.crop, card_size_def.width)
    crop_back_y_percent = calculate_crop_percent(render_opts.back.crop, card_size_def.height)

    extend_edges_px = parse_to_px(render_opts.front.extend_edges, ppi_scale)
    extend_edges_backs_px = parse_to_px(render_opts.back.extend_edges, ppi_scale)
    extend_corners_px = parse_to_px(render_opts.front.extend_corners_radius, ppi_scale)
    extend_corners_backs_px = parse_to_px(render_opts.back.extend_corners_radius, ppi_scale)
    extend_bleed_px = parse_to_px(render_opts.front.extend_bleed, ppi_scale)
    extend_bleed_backs_px = parse_to_px(render_opts.back.extend_bleed, ppi_scale)

    fit_backs = render_opts.back.fit or render_opts.front.fit

    return CardRenderParams(
        front = SideRenderParams(
            crop = (crop_x_percent, crop_y_percent),
            fit = render_opts.front.fit,
            extend_edges = extend_edges_px,
            extend_corners_radius = extend_corners_px,
            extend_bleed = extend_bleed_px
        ),
        back = SideRenderParams(
            crop = (crop_back_x_percent, crop_back_y_percent),
            fit = fit_backs,
            extend_edges = extend_edges_backs_px,
            extend_corners_radius = extend_corners_backs_px,
            extend_bleed = extend_bleed_backs_px
        ),
        orientation= render_opts.orientation
    ) 

#============================
# Crop
#============================
# [!] Doesn't really belong here...
def parse_crop_string(crop_string: str | None) -> tuple[float, str]:
    if crop_string is None:
        return 0, ""

    valid_units = ["", "mm", "in", "%"]
    try: 
        return parse_measurement(crop_string, valid_units)
    except ValueError as e:
        raise ValueError(f"Invalid Crop Format: {crop_string}") from e

def calculate_crop_percent(crop_str: str | None, dimension_str: str) -> float:
    value, unit = parse_crop_string(crop_str) 
    match unit:
        case "mm":
            return 2 * (value / parse_to_mm(dimension_str))
        case "in":
            return 2 * (value / parse_to_in(dimension_str))
        case _:
            return value / 100

@dataclass(frozen=True)
class CropGeometry:
    crop_box: tuple[int, int, int, int]
    resize_size: tuple[int, int]
    offset: tuple[int, int]
    synthetic_bleed: tuple[int ,int]

def centered_crop(
    source_width: int,
    source_height: int,
    crop_width: int,
    crop_height: int, 
) -> tuple[int, int, int, int]:
    x = (source_width - crop_width) // 2
    y = (source_height - crop_height) // 2

    return (x, y, source_width - x, source_height - y)

@dataclass(frozen=True)
class CropResult:
    image: Image.Image
    offset: tuple[int, int]
    synthetic_bleed: tuple[int, int]

def calculate_crop_geometry(
    card_width: int,
    card_height: int,
    crop_percent_x: float,
    crop_percent_y: float,
    scaled_width: int,
    scaled_height: int,
    scaled_bleed_width: int,
    scaled_bleed_height: int,
    fit: FitMode,
) -> CropGeometry:
    cropped_width = math.floor(card_width * (1 - crop_percent_x))    
    cropped_height = math.floor(card_height * (1 - crop_percent_y))    

    if fit == FitMode.CROP:
        ratio = min(
            cropped_width / scaled_width,
            cropped_height / scaled_height,
        )
        ratio_x = ratio_y = ratio
    else:
        ratio_x = cropped_width / scaled_width
        ratio_y = cropped_height / scaled_height

    requested_width = scaled_width + (2 * scaled_bleed_width)
    requested_height = scaled_height + (2 * scaled_bleed_height)

    source_width = math.floor(requested_width * ratio_x)
    source_height = math.floor(requested_height * ratio_y)

    can_bleed_x = source_width <= card_width
    can_bleed_y = source_height <= card_height

    if can_bleed_x and can_bleed_y:
        crop_box = centered_crop(card_width, card_height, source_width, source_height)
        return CropGeometry(
            crop_box=crop_box,
            resize_size=(requested_width, requested_height),
            offset=(-scaled_bleed_width, -scaled_bleed_height),
            synthetic_bleed=(0,0),
        )

    if fit == FitMode.CROP:
        content_width = min(math.floor(scaled_width * ratio_x), card_width)
        content_height = min(math.floor(scaled_height * ratio_y), card_height)

        if can_bleed_x:
            crop_box = centered_crop(card_width, card_height, source_width, content_height)
            return CropGeometry(
                crop_box=crop_box,
                resize_size=(requested_width, scaled_height),
                offset=(-scaled_bleed_width, 0),
                synthetic_bleed=(0,scaled_bleed_height),
            )
        if can_bleed_y:
            crop_box = centered_crop(card_width, card_height, content_width, source_height)
            return CropGeometry(
                crop_box=crop_box,
                resize_size=(scaled_width, requested_height),
                offset=(0, -scaled_bleed_height),
                synthetic_bleed=(scaled_bleed_height,0),
            )
        crop_box = centered_crop(card_width, card_height, content_width, content_height)
        return CropGeometry(
            crop_box=crop_box,
            resize_size=(scaled_width, scaled_height),
            offset=(0,0),
            synthetic_bleed=(scaled_bleed_width, scaled_bleed_height)
        )

    # STRETCH
    crop_width = math.floor(card_width * crop_percent_x / 2)
    crop_height = math.floor(card_height * crop_percent_y / 2)

    crop_box = (crop_width, crop_height, card_width - crop_width, card_height - card_height)
    return CropGeometry(
        crop_box=crop_box,
        resize_size=(scaled_width, scaled_height),
        offset=(0, 0),
        synthetic_bleed=(scaled_bleed_width, scaled_bleed_height)
    )

def crop_and_scale_image(
    card_image: Image.Image,
    crop_percent_x: float,
    crop_percent_y: float,
    scaled_width: int,
    scaled_height: int,
    scaled_bleed_width: int,
    scaled_bleed_height: int,
    fit: FitMode = FitMode.STRETCH,
) -> CropResult:
    card_width, card_height = card_image.size

    geometry = calculate_crop_geometry(
        card_width=card_width,
        card_height = card_height,
        crop_percent_x = crop_percent_x,
        crop_percent_y = crop_percent_y,
        scaled_width = scaled_width,
        scaled_height = scaled_height,
        scaled_bleed_width = scaled_bleed_width,
        scaled_bleed_height = scaled_bleed_height,
        fit = fit,
    )

    card_image = card_image.crop(geometry.crop_box)
    card_image = card_image.resize(geometry.resize_size)

    return CropResult(card_image, geometry.offset, geometry.synthetic_bleed)

#============================
# Reg Params
#============================

def calculate_reg_params(
    reg_opts: ResolvedRegistrationSettings,
    ppi_scale: float,
) -> RegistrationParams:
    return RegistrationParams(
        thickness = parse_to_px(reg_opts.thickness, ppi_scale),
        length = parse_to_px(reg_opts.length, ppi_scale),
        inset = parse_to_px(reg_opts.inset, ppi_scale),
    )

