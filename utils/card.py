from pathlib import Path

from utils.enums import ImageType
from utils.filesys import FileSearcher
from utils.misc import select_item
    

class Card:
    def __init__(self, name:str=None, front:Path=None, back:Path=None, mdfc:bool=False):
        self.name = name
        self.front = front
        self.back = back
        self.mdfc = mdfc

    def as_string(self):
        return f'name: {self.name}\n front: {self.front}\n back: {self.back} | mdfc: {self.mdfc}'
    
    def __str__(self):
        return self.as_string()

class Cards:
    def __init__(self, single_sided:list[Card]=None, double_sided:list[Card]=None):
        self.single_sided = single_sided or []
        self.double_sided = double_sided or []

    def add(self, card:Card, single_sided:bool=None):
        if single_sided and card.mdfc:
            print(f'Cannot add double-sided card to single-sided list. {card.name}')

        if card.back:
            self.double_sided.append(card)
        else:
            self.single_sided.append(card)

    def get(self, single_sided:bool)->list[Card]:
        return self.single_sided if single_sided else self.double_sided
    
    def total(self, single_sided:bool=None)->int:
        if single_sided == None:
            return len(self.single_sided) + len(self.double_sided)
        if single_sided:
            return len(self.single_sided)
        else:
            return len(self.double_sided)
    
def get_cards(image_paths, only_fronts:bool) -> Cards:
    image_types = [x.value for x in ImageType]
    front_paths = FileSearcher(image_paths['front'], recursive=True).by_types(image_types)
    back_paths = {}
    cards = Cards()

    for front_path in front_paths:
        card = Card()
        
        card.front = front_path
        card.name = front_path.stem
        rel_path = front_path.relative_to(image_paths['front'])

        double_path = FileSearcher(image_paths['double'],recursive=False).by_name(rel_path)
        if double_path:
            card.back = double_path
            card.mdfc = True
            cards.add(card, only_fronts)
            continue
        
        if only_fronts:
            cards.add(card, only_fronts)
            continue
        
        rel_dir = rel_path.parent
        if rel_dir in back_paths:
            card.back = back_paths[rel_dir]
        else:
            back_searcher = FileSearcher(image_paths['back'] / rel_dir, recursive=False)
            back_path_search = back_searcher.bottom_up(image_paths['back'], image_types)
            card_back_select_header = f'Back Images available for {rel_dir}'
            card.back = select_item(back_path_search, header=card_back_select_header)
            back_paths[rel_dir] = card.back
        
        cards.add(card)
    
    return cards