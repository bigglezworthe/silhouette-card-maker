from pathlib import Path     # Import for typing
from PIL import Image

from utils.enums import ImageType
from utils.filesys import FileSearcher
from utils.misc import select_item
# from utils.image import CardImage


class CardFace:
    def __init__(self, path:Path=None, image:Image.Image=None, cached:bool=False, processed:bool=False):
        self.path = path
        self.image = image
        self.cached = cached
        self.processed = processed

    def open_image(self, path:Path=None):
        path = path or self.path
        self.image = Image.open(path) if path else None

    def status(self)->dict[str:bool]:
        return {'cached':self.cached, 'processed':self.processed}

    def as_string(self) -> str:
        return str(self.path)
    
    def __str__(self):
        return self.as_string()


class Card:
    _sentinel = object()

    def __init__(self, name:str=None, front_face:CardFace=None, back_face:CardFace=None, mdfc:bool=False):
        self.name = name
        self.front = front_face or CardFace()
        self.back = back_face or CardFace()
        self.mdfc = mdfc
    
    def paths(self, front_path:Path|None=_sentinel, back_path:Path|None=_sentinel) -> tuple[Path, Path]:
        if font_path is not _sentinel:
            self.front.path = front_path
        if back_path is not sentinel:
            self.back.path = back_path

        return self.front.path, self.back.path
    
    def images(self, front_image:Image.Image|None=_sentinel, back_image:Image.Image|None=_sentinel) -> tuple[Image.Image, Image.Image]:
        if font_image is not _sentinel:
            self.front.image = front_image
        if back_image is not sentinel:
            self.back.image = back_image

        return self.front.image, self.back.image
    
    def load_images(self):
        self.front.open_image(front_path)
        self.back.open_image(back_path)
    
    def status(self)->dict:
        return {
            'front': self.front.status(),
            'back': self.back.status()
        }

    def cached(self)->bool:
        return self.back.cached
    
    def info(self)->dict[str:str]:
        return {
            'name': self.name,
            'front': str(self.front),
            'back': str(self.back)
        }

    def as_string(self)->str:
        return f'Name: {self.name} Front: {self.front} Back: {self.back}'

    def __str__(self):
        return self.as_string()

class Cards:
    def __init__(self, single_sided:list[Card]=None, double_sided:list[Card]=None):
        self.single_sided = single_sided or []
        self.double_sided = double_sided or []
        
        self.ignored = []
        self.cache_back = {}

    def add(self, card:Card, single_sided:bool):
        if single_sided and card.mdfc:
            self.ignored.append(card.name)
        elif card.back.path:
            self.double_sided.append(card)
            if card.back.path not in self.cache_back:
                self.cache_back[card.back.path] = None
        else:
            self.single_sided.append(card)

    def get(self, single_sided:bool)->list[Card]:
        return self.single_sided if single_sided else self.double_sided
    
    def total(self)->dict[str,int]:
        single = len(self.single_sided)
        double = len(self.double_sided)
        ignored = len(self.ignored)
        return {'single':single,'double':double,'ignored':ignored,'total':single+double}
    
def get_cards(image_paths, only_fronts:bool) -> Cards:
    image_types = [x.value for x in ImageType]
    front_paths = FileSearcher(image_paths['front'], recursive=True).by_types(image_types)
    cards = Cards()
    cached_paths = {}

    for front_path in front_paths:
        card = Card()
        
        card.front.path = front_path
        card.name = front_path.stem
        rel_path = front_path.relative_to(image_paths['front'])

        double_path = FileSearcher(image_paths['double'],recursive=False).by_name(rel_path)
        if double_path:
            card.back.path = double_path[0]
            card.mdfc = True
            cards.add(card, only_fronts)
            continue
        
        if only_fronts:
            cards.add(card, only_fronts)
            continue
        
        rel_dir = rel_path.parent
        if rel_dir in cached_paths:
            card.back.path = cached_paths[rel_dir]
        else:
            back_searcher = FileSearcher(image_paths['back'] / rel_dir, recursive=False)
            back_path_search = back_searcher.bottom_up(image_paths['back'], image_types)
            card_back_select_header = f'Back Images available for {rel_dir}'
            card.back.path = select_item(back_path_search, header=card_back_select_header)
            if card.back.path:
                cached_paths[rel_dir]=card.back.path
        cards.add(card, only_fronts)
    
    return cards