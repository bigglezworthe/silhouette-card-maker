import json

from pydantic import BaseModel

from utils.enums import Paths, CardSize, PaperSize
from utils.misc import split_by_value

class OffsetData(BaseModel):
    x_offset: int = None
    y_offset: int = None

class CardLayout(BaseModel):
    x_pos: list[int]
    y_pos: list[int]
    template: str

    def xy_pairs(self)->list[tuple[int,int]]:
        return [(x, y) for y in self.y_pos for x in self.x_pos]

class CardLayoutSize(BaseModel):
    width: int
    height: int

class PaperLayout(BaseModel):
    width: int
    height: int
    card_layouts: dict[CardSize, CardLayout]

class Layout:
    def __init__(self, paper_size:PaperSize=None, card_size:CardSize=None, paper_layout:PaperLayout=None, card_layout_size:CardLayoutSize=None, card_layout:CardLayout=None):
        self.paper_size = paper_size
        self.card_size = card_size
        self.paper_layout = paper_layout
        self.card_layout_size = card_layout_size
        self.template = card_layout.template

        self.card_pos = card_layout.xy_pairs()

    def ignore_positions(self, position_indices:list[int]):
        cards_per_page = len(self.card_pos)
        valid_pos, invalid_pos = split_by_value(position_indices, cards_per_page)
        if invalid_pos:
            print(f'Ignoring indices that are outside range 0-{cards_per_page-1}: {invalid_pos}')

        if len(valid_pos) >= cards_per_page:
            raise ValueError(f'You cannot skip all cards per page')

        for idx in position_indices:
            self.card_pos[idx] = None

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

    


        


