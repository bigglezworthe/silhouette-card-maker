import json
import math

from pydantic import BaseModel

from utils.enums import Paths, CardSize, PaperSize
from utils.misc import split_by_value

class OffsetData(BaseModel):
    x_offset: int
    y_offset: int

class CardLayout(BaseModel):
    x_pos: list[int]
    y_pos: list[int]
    template: str

    def xy_pairs(self)->list[tuple[int,int]]:
        return [(x, y) for y in self.y_pos for x in self.x_pos]

    def scale(self, factor:float):
        self.x_pos = [n * factor for n in self.x_pos]
        self.y_pos = [n * factor for n in self.y_pos]

class CardLayoutSize(BaseModel):
    width: int
    height: int

    def scale(self, factor):
        self.width *= factor
        self.height *= factor

class PaperLayout(BaseModel):
    width: int
    height: int
    card_layouts: dict[CardSize, CardLayout]

    def scale(self, factor):
        self.width *= factor
        self.height *= factor
        self.card_layouts = {k: v.scale(f) for k, v in self.card_layouts.items()}

class Layout:
    def __init__(self, paper_size:PaperSize, card_size:CardSize, paper_layout:PaperLayout, card_layout_size:CardLayoutSize, card_layout:CardLayout):
        self.paper_size = paper_size
        self.card_size = card_size
        self.paper_layout = (paper_layout.width, paper_layout.height)
        self.card_layout_size = card_layout_size
        self.template = card_layout.template
        self.card_positions = card_layout.xy_pairs()
        
        self.cards_per_page = self._update_cpp()
        self.max_border = self._calc_max_border(card_layout)

    def _update_cpp(self):
        self.cards_per_page = len(self.card_positions)
    
    def _calc_max_border(self, card_layout:CardLayout) -> tuple[int,int]:
        x_pos = card_layout.x_pos
        y_pos = card_layout.y_pos
        w = self.card_layout_size.width
        h = self.card_layout_size.height

        x_pos.sort()
        y_pos.sort()

        def get_max_border(pos_list, obj_size) -> float:
            default = 100000
            if len(pos_list) < 2:
                return default
            
            max_border = math.ceil((pos_list[1] - pos_list[0] - obj_size) / 2)
            return default if max_border < 0 else max_border 
        
        return get_max_border(x_pos, w), get_max_border(y_pos, h)

    def ignore_positions(self, remove_indices:list[int]):
        self.card_positions = [pos for i, pos in enumerate(self.card_positions) if i not in set(remove_indices)]
        self._update_cpp()

    def scale(self, factor:float):
        self.paper_layout = tuple(n * factor for n in self.paper_layout)
        self.card_layout_size.scale(factor)
        self.max_border = tuple(n * factor for n in self.max_border)
        self.card_positions = [tuple(n * factor for n in pos) for pos in self.card_positions]


class Layouts(BaseModel):
    card_sizes: dict[CardSize, CardLayoutSize]
    paper_layouts: dict[PaperSize, PaperLayout]

def load_layouts() -> Layouts:
    layouts_path = Paths.ASSETS / 'layouts.json'
    with open(layouts_path, 'r') as layouts_file:
        try:
            layouts_data = json.load(layouts_file)
            layouts = Layouts(**layouts_data)
        except ValidationErr as e:
            raise Exception(f'Cannot parse layouts.json: {e}.')
    return layouts 

def make_layout(paper_size:PaperSize, card_size:CardSize, layouts:Layouts, skip_positions:list[int]) -> Layout:
    paper_size_enum = PaperSize(paper_size)
    card_size_enum = CardSize(card_size)

    if paper_size_enum not in layouts.paper_layouts:
        raise Exception(f'Unsupported paper size "{paper_size}". Try paper sizes: {layouts.paper_layouts.keys()}')
    paper_layout = layouts.paper_layouts[paper_size]

    if card_size_enum not in layouts.card_sizes:
        raise Exception(f'Unsupported card size "{card_size}". Try card sizes: {layouts.card_layouts.keys()}.')
    card_layout_size = layouts.card_sizes[card_size]

    if card_size_enum not in paper_layout.card_layouts:
        raise Exception(f'Unsupported card size "{card_size}" with paper size "{paper_size}". Try card sizes: {paper_layout.card_layouts.keys()}.')
    card_layout = paper_layout.card_layouts[card_size]

    layout = Layout(paper_size, card_size, paper_layout, card_layout_size, card_layout)
    layout.ignore_positions(skip_positions)
    return layout


#==============================================================================
# Offset (Maybe deserves its own file?)
#------------------------------------------------------------------------------
def save_offset(x_offset:int, y_offset:int):
    data_json = OffsetData(x_offset, y_offset).model_dump_json(indent=4)

    data_path = Paths.DATA / 'offset_data.json'
    data_path.mkdir(parents=True,exist_ok=True)
    with open(data_path,'w') as offset_file:
        offset_file.write(data_json)

def load_offset() -> OffsetData:
    data_path = Paths.DATA / 'offset_data.json'
    if not data_path.exists():
        return OffsetData()
    
    with open(data_path, 'r') as offset_file:
        return OffsetData(**json.load(offset_file))
        # why not halt with error?
        # except json.JSONDecodeError as e:
        #     print(f'Cannot decode offset JSON: {e}')
        # except ValidationErr as e:
        #     print(f'Cannot validate offset data: {e}')


#==============================================================================

    


        


