import math
import io 

from PIL import Image

from utils.card import Card

class CardImageProcessor:
    def __init__(self, 
            card:Card=None,
            card_width:int,
            card_height:int,
            scale:float,
            crop_amount:float,
            crop_unit:str|None,
            borders:tuple[int,int]
    ):
        self.card = card

        self.width = card_width
        self.height = card_height
        self.scale = scale

        self.crop = crop_amount
        self.crop_unit = crop_unit
        self.borders = borders

        self.errors = []
    
    def load_card(self,card:Card):
        self.card = card

    def process(self, card:Card=None)->Card:
        card = card or self.card
        if not card:
            raise ValueError(f'No card supplied')

        card.load()
        
        if card.front.image and not card.front.stream:
            card.front.stream = self._process_face(card.front,image, False)
            card.front.image = None
        if card.back.image and not card.back.stream:
            card.back.stream = self._process_face(card.back.image, True)
            card.back.image = None
        
        self.card = card
        return card

    def _process_face(self, img:Image.Image, flip:bool)->bytes:
        cropped = crop_image(img, self.crop_amount, self.crop_unit)
        resized = cropped.resize((self.card_width, self.card_height))
        extended = resized.crop(
            -self.borders[0], 
            -self.borders[1],
            resized.width+self.borders[0],
            resized.height+self.borders[1]
        )

        scaled = extended.resize(self.scale)

        if flip:
            final = scaled.transpose(Image.FLIP_TOP_BOTTOM)
        else:
            final = scaled
        
        return image_to_bytes(final)

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


def get_image(path:Path)->Image.Image:
    return Image.open(Path)

def image_to_bytes(img:Image.Image) -> bytes:
        buf = io.BytesIO()
        img.save(buf, format=None)
        return buf.getvalue()