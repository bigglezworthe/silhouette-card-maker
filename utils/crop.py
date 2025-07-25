import re

def split_float_unit(s:str):
    s = s.strip().lower()

    float_unit_pattern = r'\s*([+-]?\d*\.?\d+)\s*([a-zA-Z]*)\s*'
    match = re.fullmatch(float_unit_pattern, s)

    if not match:
        raise ValueError(f'Invalid format: {s}')
    
    num = float(match.group(1))
    unit = match.group(2) or None  # None if unit is missing
    
    return num, unit

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

def crop_image(pic:Image.Imag, crop_string:str):
    ppi = pic.info.get('dpi', (300,300))[0]
    x, y = pic.size

    crop_amount, crop_unit = split_float_unit(crop_string)
    x_scale, y_scale = get_crop_ratio(x, y, crop_amount, crop_unit, ppi)

    return pic.crop(
        x_crop,
        y_crop,
        int(x*x_scale),
        int(y*y_scale)
    )

