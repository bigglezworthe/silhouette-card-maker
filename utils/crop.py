import re

def split_float_unit(s:str, valid_units:[str]):
    s = s.strip().lower()

    float_unit_pattern = r'\s*([+-]?\d*\.?\d+)\s*([a-zA-Z]*)\s*'
    match = re.fullmatch(float_unit_pattern, s)

    if not match:
        raise ValueError(f'Invalid format: {s}')
    
    num = float(match.group(1))
    unit = match.group(2) or None  # None if unit is missing
    
    if unit not in valid_units:
        raise ValueError(f'Invalid unit: {unit}')
    
    return num, unit

def get_crop_ratio(crop_string:str, width:int, height:int, ppi:int): 
    valid_units = [None, '%', 'mm', 'in', 'px']
    amount, unit = split_float_unit(crop_string, valid_units)

    if amount < 0:
        raise ValueError(f'Crop value cannot be negative. Got {crop_string}')

    match unit:
        case None | '%':
            x_percent = amount / 100
            y_percent = amount / 100
        case 'in':
            x_percent = 2 * amount / width * ppi
            y_percent = 2 * amount / height * ppi
        case 'mm':
            MM_TO_INCH = 1/25.4
            x_percent = 2 * amount / width * ppi * MM_TO_INCH
            y_percent = 2 * amount / height * ppi * MM_TO_INCH
        case  'px':
            x_percent = 2 * amount / width
            y_percent = 2 * amount / height
    
    return 1-x_percent, 1-y_percent

def crop_image(crop_string:str, pic:Image.Image):
    ppi = pic.info.get('dpi')[0]
    x, y = pic.size

    x_ratio, y_ratio = get_crop_ratio(crop_string, x, y, ppi)

    return pic.crop(
        x_crop,
        y_crop,
        int(x*x_ratio),
        int(y*y_ratio)
    )

