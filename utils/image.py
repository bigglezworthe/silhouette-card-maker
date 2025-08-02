import math
import re

from PIL import Image

from utils.misc import split_float_unit
from utils.card import Card, Cards
from utils.layout import Layout

class CardImageProcessor:
    def __init__(self, 
            card:Card=None,
            card_width:int,
            card_height:int,
            ppi_scale:float,
            crop_amount:float=None,
            crop_unit:str|None=None,
            max_card_bleed:tuple[int,int],
            extend_corners:int,
    ):
        self.card = card
        self.scale = ppi_scale

        self.width = card_width
        self.height = card_height

        self.crop = crop_amount
        self.crop_unit = crop_unit
        self.max_bleed = max_card_bleed
        self.extend_corners = extend_corners

        self.errors = []
    
    def load_card(self,card:Card):
        self.card = card

    def process(self, card:Card=None)->Card:
        card = card or self.card
        if not card:
            raise ValueError(f'No card supplied')
        
        if card.front.image:
            card.front.image = self._process_face(card.front,image)
            card.front.processed = True
        if card.back.image:
            card.back.image = self._process_face(card.back.image)
            card.back.processed = True
        
        self.card = card
        return card

    def _process_face(self, img:Image.Image)->Image.Image:
        cropped = crop_image(img, self.crop_amount, self.crop_unit)
        resized = cropped.resize((self.card_width, self.card_height))

        extend_rect=(
            self.extend_corners, 
            self.extend_corners,
            resized.width-self.extend_corners,
            resized.height-self.extend_corners
        )

        return resized.crop(extend_rect)

        # After Debugging, best to log errors instead of crash
        # try:
        #     self._process_card(card_image):
        # except Exception as {e}:
        #     self.errors.append(f'Error: {e}')

def calc_card_bleed(self,card_layout:CardLayout) -> tuple(int,int):
    x_pos = card_layout.x_pos
    y_pos = card_layout.y_pos
    w = card_layout.width
    h = card_layout.height

    x_pos.sort()
    y_pos.sort()

    if len(x_pos) <= 1 and len(y_pos) <= 1:
        return (0,0)

    def get_max_border(pos_list, obj_size) -> float:
        default = 100000
        if len(pos_list) < 2:
            return default
        
        max_border = math.ceil((pos_list[1] - pos_list[0] - obj_size) / 2)
        return default if max_border < 0 else max_border 
    
    return (get_max_border(x_pos, width), get_max_border(y_pos, height))

def calc_crop_scale(image_size:tuple[int,int], crop_amount:float, crop_unit:str, ppi:int)->tuple[float,float]: 
    valid_units = [None, '%', 'mm', 'in', 'px']

    if crop_unit not in valid_units:
        raise ValueError(f'Invalid unit: {crop_unit}')

    if crop_amount < 0:
        raise ValueError(f'Crop value cannot be negative. Got {crop_amount}')

    x_percent_px = 2 * crop_amount / image_width
    y_percent_px = 2 * crop_amount / image_height

    match crop_unit:
        case None | '%':
            x_percent = y_percent = crop_amount / 100
        case 'in':
            x_percent, y_percent = scale_factor(2 * crop_amount * ppi)
            y_percent = 2 * crop_amount / image_height * ppi
        case 'mm':
            INCH_PER_MM = 1/25.4
            x_percent = 2 * crop_amount / image_width * ppi * INCH_PER_MM
            y_percent = 2 * crop_amount / image_height * ppi * INCH_PER_MM
        case 'px':
            x_percent = 2 * crop_amount / image_width
            y_percent = 2 * crop_amount / image_height
    
    return 1-x_percent, 1-y_percent

def crop_image(img:Image.Image, crop_amount:float, crop_unit:str|None)->Image.Image:
    ppi = img.info.get('dpi')
    if not ppi:
        print(f'Could not extract PPI from image. Defaulting to 300.')
        ppi = 300
    else:
        ppi = ppi[0]

    x, y = img.size
    x_scale, y_scale = calc_crop_scale(x, y, crop_amount, crop_unit, ppi)

    return img.crop((x,y,int(x*x_scale),int(y*y_scale)))

def process_card_image(
            card_image:Image.Image,
            card_width:int,
            card_height:int,
            ppi_scale:float,
            crop_amount:float,
            crop_unit:str|None,
            max_card_bleed:tuple[int,int],
            extend_corners:int
) -> Image.Image:
    card_image_cropped = crop_image(card_image, crop_amount, crop_unit)
    card_image_normalized = card_image_cropped.resize((card_width,card_height))

    extend_corners_rect=(
        extend_corners, 
        extend_corners,
        card_image.width-extend_corners,
        card_image.height-extend_corners
    )

    return card_image_normalized.crop(extend_corners_rect)

def get_image(path:Path)->Image.Image
    return Image.open(Path)

    