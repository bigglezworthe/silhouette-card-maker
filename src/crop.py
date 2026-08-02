#==============================================================================
# crop.py 
#     Logic associated with cropping images. 
#==============================================================================
# [!] Might merge with images.py 

import math 

from .measurements import parse_unit_string
from .enums import FitMode 

from PIL import Image

def convert_inch_to_crop(crop_in: float, card_width_px: int, card_height_px: int) -> tuple[float, float]:
    # Card dimensions are based on 300 ppi
    card_width_in = card_width_px / 300
    card_height_in = card_height_px / 300

    crop_x_percent = 2 * crop_in / card_width_in * 100
    crop_y_percent = 2 * crop_in / card_height_in * 100

    return (crop_x_percent, crop_y_percent)

def parse_crop_string(crop_string: str | None, card_width: int, card_height: int) -> tuple[float, float]:
    if crop_string is None:
        return 0, 0

    valid_units = ["", "mm", "in", "%"]
    amount, unit = parse_unit_string(crop_string, valid_units)
    
    if unit == "mm":
        return convert_inch_to_crop(amount / 25.4, card_width, card_height)
    if unit == "in":
        return convert_inch_to_crop(amount, card_width, card_height)
    # Default unit is %
    return amount, amount

# [!] X/Ys should be consolidated for args and return 
def crop_and_scale_image(
    card_image: Image.Image,
    crop_percent_x: float,
    crop_percent_y: float,
    scaled_width: int,
    scaled_height: int, 
    scaled_bleed_width: int,
    scaled_bleed_height: int, 
    fit: FitMode = FitMode.STRETCH,
) -> tuple[Image.Image, int, int, tuple[int, int]]:
    # Returns processed image, bleed_offset_x, bleed_offset_y, synthetic_bleed (w,h)

    card_width, card_height = card_image.size

    cropped_width = math.floor(card_width * (1-(crop_percent_x / 100)))
    cropped_height = math.floor(card_height * (1-(crop_percent_y / 100)))

    if fit == FitMode.CROP:
        uniform_ratio = min(cropped_width / scaled_width, cropped_height / scaled_height)
        cropped_scaled_ratio_x = uniform_ratio 
        cropped_scaled_ratio_y = uniform_ratio
    else:
        cropped_scaled_ratio_x = cropped_width / scaled_width
        cropped_scaled_ratio_y = cropped_height / scaled_height

    scaled_width_with_bleed = scaled_width + (2 * scaled_bleed_width) 
    scaled_height_with_bleed = scaled_height + (2 * scaled_bleed_height) 
    
    unscaled_width_with_bleed = math.floor(scaled_width_with_bleed * cropped_scaled_ratio_x)
    unscaled_height_with_bleed = math.floor(scaled_height_with_bleed * cropped_scaled_ratio_y)

    can_bleed_x = unscaled_width_with_bleed <= card_width 
    can_bleed_y = unscaled_height_with_bleed <= card_height 

    # [!] Definitely some duplication happening here. Can set vars and perform ops after. 
    if can_bleed_x and can_bleed_y:
        crop_x = (card_width - unscaled_width_with_bleed) // 2 
        crop_y = (card_height - unscaled_height_with_bleed) // 2 
        card_image = card_image.crop((crop_x, crop_y, card_width - crop_x, card_height - crop_y))
        card_image = card_image.resize((scaled_width_with_bleed, scaled_height_with_bleed))

        return card_image, -scaled_bleed_width, -scaled_bleed_height, (0,0)

    if fit == FitMode.CROP:
        if can_bleed_x:
            content_height = min(math.floor(scaled_height * cropped_scaled_ratio_y), card_height)
            crop_x = (card_width - unscaled_width_with_bleed) // 2
            crop_y = (card_height - content_height) // 2
            card_image = card_image.crop((crop_x, crop_y, card_width - crop_x, card_height - crop_y))
            card_image = card_image.resize((scaled_width_with_bleed, scaled_height))
            return card_image, -scaled_bleed_width, 0, (0, scaled_bleed_height)
        if can_bleed_y:
            content_width = min(math.floor(scaled_width * cropped_scaled_ratio_x), card_width)
            crop_x = (card_width - content_width) // 2
            crop_y = (card_height - unscaled_height_with_bleed) // 2
            card_image = card_image.crop((crop_x, crop_y, card_width - crop_x, card_height - crop_y))
            card_image = card_image.resize((scaled_width, scaled_height_with_bleed))
            return card_image, 0, -scaled_bleed_height, (scaled_bleed_width, 0)

        content_width = min(math.floor(scaled_width * cropped_scaled_ratio_x), card_width)
        content_height = min(math.floor(scaled_height * cropped_scaled_ratio_y), card_height)
        crop_x = (card_width - content_width) // 2 
        crop_y = (card_height - content_height) // 2
        card_image = card_image.crop((crop_x, crop_y, card_width - crop_x, card_height - crop_y))
        card_image = card_image.resize((scaled_width, scaled_height))
        return card_image, 0, 0, (scaled_bleed_width, scaled_bleed_height)

    # STRETCH fallback 
    crop_x = card_width * (crop_percent_x / 100) // 2 
    crop_y = card_height * (crop_percent_y / 100) // 2 
    card_image = card_image.crop((crop_x, crop_y, card_width - crop_x, card_height - crop_y))
    card_image = card_image.resize((scaled_width, scaled_height))
    return card_image, 0, 0, (scaled_bleed_width, scaled_bleed_height)
