import json
# Mostly handles JSON interfacing
from utils.enums import Paths, CardSize, PaperSize
from pydantic import BaseModel

class CardLayout(BaseModel):
    x_pos: list[int]
    y_pos: list[int]
    template: str

class CardLayoutSize(BaseModel):
    width: int
    height: int

class PaperLayout(BaseModel):
    width: int
    height: int
    card_layouts: dict[CardSize, CardLayout]

class Layout(BaseModel):
    paper_size: PaperSize = None
    card_size: CardSize = None
    paper_layout: PaperLayout = None
    card_layout_size: CardLayoutSize = None
    card_layout: CardLayout = None

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

def get_layout(paper_size:PaperSize, card_size:CardSize, layouts:Layouts) -> Layout:
    layout = Layout()
    paper_size_enum = PaperSize(paper_size)
    card_size_enum = CardSize(card_size)

    if paper_size_enum not in layouts.paper_layouts:
        raise Exception(f'Unsupported paper size "{paper_size}". Try paper sizes: {layouts.paper_layouts.keys()}')
    layout.paper_layout = layouts.paper_layouts[paper_size]

    if card_size_enum not in layouts.card_sizes:
        raise Exception(f'Unsupported card size "{card_size}". Try card sizes: {layouts.card_layouts.keys()}.')
    layout.card_layout_size = layouts.card_sizes[card_size]

    if card_size_enum not in layout.paper_layout.card_layouts:
        raise Exception(f'Unsupported card size "{card_size}" with paper size "{paper_size}". Try card sizes: {paper_layout.card_layouts.keys()}.')
    layout.card_layout = layout.paper_layout.card_layouts[card_size]

    layout.paper_size = paper_size
    layout.card_size = card_size

    return layout

        


