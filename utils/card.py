from pathlib import Path     # Import for typing
from PIL import Image

from utils.enums import ImageType
from utils.filesys import FileSearcher
from utils.misc import select_item

class CardFace:
    def __init__(self, path:Path=None, image:Image.Image=None, stream:bytes=None):
        self.path = path
        self.image = image
        self.stream = stream

    def open_image(self, path:Path=None):
        if not self.image:
            path = path or self.path
            self.image = Image.open(path) if path else None

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
    
    def load(self):
        self.front.open_image()
        self.back.open_image()
    
    def info(self)->dict:
        return {
            'name': self.name,
            'front': self.front.path,
            'front_image': bool(self.front.image),
            'back': self.back.path,
            'back_image': bool(self.back.image),
            'mdfc': self.mdfc,
        }

    def as_string(self)->str:
        return f'Name: {self.name} Front: {self.front} Back: {self.back}'

    def __str__(self):
        return self.as_string()

class CardFetcher:
    def __init__(self, game_paths:dict, only_fronts:bool=False):
        self.game_paths=game_paths
        self.only_fronts = only_fronts

        self.card=None
        self.cached_backs = {}
        self.cached_paths = {}
        self.ignored = []
        self.totals={
            'single':0,
            'double':0,
            'ignored':0,
        }

        self.image_types = [x.value for x in ImageType]

        self.double_searcher = FileSearcher(self.game_paths['double'],recursive=False)
        self.back_searcher = FileSearcher(self.game_paths['back'], recursive=False)
    
    def _check_cached_path(self, path:Path)->Path:
        if path not in self.cached_paths:
            self.back_searcher.path = self.game_paths['back'] / path
            back_path_search = self.back_searcher.bottom_up(self.game_paths['back'], self.image_types)
            card_back_select_header = f'Back Images available for {path}'
            self.cached_paths[path]= select_item(back_path_search, header=card_back_select_header)
        
        return self.cached_paths[path]

    def _check_cached_face(self, face:CardFace)->CardFace:
        if face.path in self.cached_backs:
            face = self.cached_backs[face.path]
        else:
            self.cached_backs[face.path] = face
        return face

    def _is_valid(self, card:Card):
        if self.only_fronts and card.mdfc:
            self.ignored.append(card.name)
            self.totals['ignored']+=1
            return False
        elif card.back.path:
            self.totals['double']+=1
            return True
        else:
            self.totals['single']+=1
            return True
    
    def fetch(self, front_path:Path)->Card:
        card = Card()
        card.front.path = front_path
        card.name = front_path.stem
        # print(f'{i} {card.name}')
        rel_path = front_path.relative_to(self.game_paths['front'])

        double_path = self.double_searcher.by_name(rel_path)
        if double_path:
            card.back.path = double_path[0]
            card.mdfc = True
        elif not self.only_fronts: 
            card.back.path = self._check_cached_path(rel_path.parent)
            if card.back.path:
                card.back = self._check_cached_face(card.back)
        
        if not self._is_valid(card):
            card = None

        return card 

def print_card(card:Card):
    for k, v in card.info().items():
        print(f'{k}: {v}')
