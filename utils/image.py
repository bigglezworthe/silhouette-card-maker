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
        
        if card.front.image and not card.front.processed:
            card.front.image = self._process_face(card.front,image)
            card.front.processed = True
        if card.back.image and not card.back.processed:
            card.back.image = self._process_face(card.back.image)
            card.back.processed = True
        
        self.card = card
        return card

    def _process_face_image(self, img:Image.Image)->Image.Image:
        cropped = crop_image(img, self.crop_amount, self.crop_unit)
        resized = cropped.resize((self.card_width, self.card_height))
        extend_rect=(
            -self.extend_corners, 
            -self.extend_corners,
            resized.width+self.extend_corners,
            resized.height+self.extend_corners
        )
        return resized.crop(extend_rect)

        # After Debugging, best to log errors instead of crash
        # try:
        #     self._process_card(card_image):
        # except Exception as {e}:
        #     self.errors.append(f'Error: {e}')

def crop_image(img:Image.Image, crop_amount:float, crop_unit:str|None)->Image.Image:
    ppi = img.info.get('dpi')
    if not ppi:
        print(f'Could not extract PPI from image. Defaulting to 300.')
        ppi = 300
    else:
        ppi = ppi[0]

    x, y = img.size
    valid_units = [None, '%', 'mm', 'in', 'px']
    match crop_unit:
        case None | '%':
            x_crop = crop_amount * x
            y_crop = crop_amount * y
        case 'px':
            x_crop = y_crop = crop_amount
        case 'in':
            x_crop = y_crop = crop_amount * ppi 
        case 'mm':
            MM_PER_INCH = 25.4
            x_crop = y_crop = crop_amount * ppi / MM_PER_INCH
        case _:
            raise ValueError(f'Invalid crop unit: {crop_unit}. Valid units: {valid_units]}')
    x_crop, y_crop = math.floor(x_crop), math.floor(y_crop)    
    return img.crop((x_crop,y_crop,x-x_crop,y-y_crop))


def get_image(path:Path)->Image.Image
    return Image.open(Path)

    