import math
import re

from PIL import Image

from utils.misc import split_float_unit


def calc_max_bleed(card:CardLayout)-> tuple(int,int):
    x_pos = card.x_pos
    y_pos = card.y_pos
    w = card.width
    h = card.height

    x_pos.sort()
    y_pos.sort()

    big_number = 100000

    if len(x_pos) <= 1 and len(y_pos) <= 1:
        return (0,0)
    
    def get_max_border(pos_list, obj_size) -> float:
        default = 100000
        if len(pos_list) < 2:
            return default
        
        max_border = math.ceil((pos_list[1] - pos_list[0] - obj_size) / 2)
        return default if max_border < 0 else max_border 
    
    return (get_max_border(x_pos, width), get_max_border(y_pos, height))

def get_crop_ratio(image_width:int, image_height:int, crop_amount:float, crop_unit:str, ppi:int): 
    valid_units = [None, '%', 'mm', 'in', 'px']

    if crop_unit not in valid_units:
        raise ValueError(f'Invalid unit: {crop_unit}')

    if crop_amount < 0:
        raise ValueError(f'Crop value cannot be negative. Got {crop_amount}')

    match crop_unit:
        case None | '%':
            x_percent = crop_amount / 100
            y_percent = crop_amount / 100
        case 'in':
            x_percent = 2 * crop_amount / image_width * ppi
            y_percent = 2 * crop_amount / image_height * ppi
        case 'mm':
            MM_TO_INCH = 1/25.4
            x_percent = 2 * crop_amount / image_width * ppi * MM_TO_INCH
            y_percent = 2 * crop_amount / image_height * ppi * MM_TO_INCH
        case 'px':
            x_percent = 2 * crop_amount / image_width
            y_percent = 2 * crop_amount / image_height
    
    return 1-x_percent, 1-y_percent

def crop_image(pic:Image, crop_string:str):
    ppi = pic.info.get('dpi')
    if not ppi:
        print(f'Could not extract PPI from image. Defaulting to 300.')
        ppi = 300
    else:
        ppi = ppi[0]

    x, y = pic.size

    crop_amount, crop_unit = split_float_unit(crop_string)
    x_scale, y_scale = get_crop_ratio(x, y, crop_amount, crop_unit, ppi)

    return pic.crop(x_crop,y_crop,int(x*x_scale),int(y*y_scale))
