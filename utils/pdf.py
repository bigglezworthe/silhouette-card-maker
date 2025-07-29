#===========================================================
# Layout is in pixels assuming 300ppi
# PDF uses pt 72pt/in 

import fitz   #PyMuPDF
import math

from pathlib import Path
# from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from utils.enums import Paths
from utils.misc import px2pt, split_by_values
from utils.image import process_card_image, get_image

class CardPDF:
    def __init__(self, 
        path:Path, 
        page_height:float, 
        page_width:float, 
        bg:fitz.Pixmap, 
        ppi:int,
        ppi_scale:int,
        cards_per_page:int,
        font_path:Path,
        font_size:float,
        page_name:str|None,
        template:str
    ):
        self.path = path
        self.bg = bg
        self.ppi = ppi
        self.scale = ppi_scale
        self.cpp = cards_per_page
        self.font = fitz.Font(fontfile=str(font_path))
        self.page_name = page_name
        self.template = template

        self.pdf = fitz.open()
        self.current_page = None
        self.current_position = 0

        self.width = self.to_scale(width)
        self.height = self.to_scale(height)
        self.font_size = self.to_scale(font_size)

    def to_scale(f:float)->float:
        return f * self.scale

    def unscale(f:float)->float:
        return f / self.scale

    def new_page(self, 
        page_height:float=None, 
        page_width:float=None, 
        bg:fitz.Pixmap=None, 
        cards_per_page:int=None,
        template:str=None
    )->fitz.Page:
        height = self.to_scale(page_height) or self.height
        width = self.to_scale(page_width) or self.width
        bg = bg or self.bg
        cpp = cards_per_page or self.cpp
        template = template or self.template

        rect = fitz.Rect(0,0,,width, height)

        page = self.pdf.new_page(height=height, width=width)
        page.insert_image(rect, pixmap=bg)
        self.current_page = page

        label = f'sheet: {page.number}, template: {template}'
        if self.name:
            label = f'name: {self.name}, {label}'
        
        label_pos_x = math.floor((width - px2pt(180) * self.scale))
        label_pos_y = math.floor((height - px2pt(140) * self.scale))
        label_pos = fitz.Point(label_pos_x, label_pos_y)
        self.insert_text(label, pos)

        return page

    def insert_text(self, 
        txt:str,
        pos:fitz.Point,  
        page:fitz.Page=None, 
        font:fitz.Font=None, 
        font_size:float=None, 
        fill:tuple[float,float,float]=(0,0,0)
    )->None:
        page = page or self.current_page
        font = font or self.font
        size = self.to_scale(font_size) or self.font_size

        page.insert_text(pos, txt, fontsize=size, fill=fill)
    
    def change_page(self, page_index:int) -> fitz.Page:
        return self.pdf[page_index]

    def render(self, path:Path=None, ppi:int=None):
        path = path or self.path
        ppi = ppi or self.ppi

        for i, page in enumerate(doc,1):
            pix = page.get_pixmap(dpi=ppi)
            pix.save(f'game{i}.png')
    
    def save(self, path:Path=None):
        path = path or self.Path
        self.pdf.save(path or self.Path)
    
    def close(self):
       self. pdf.close()

def generate_pdf(
    cards:Cards,
    output_path:Path,
    output_images: bool,
    layout: Layout,
    crop_string: str,
    extend_corners: int,
    ppi: int,
    quality: int,
    load_offset: bool,
    skip:[int],
    name: str
) -> CardPDF:

    DEFAULT_PPI = 300
    ppi_scale = ppi / DEFAULT_PPI
    
    card_row = [px2pt(y) for y in layout.card_layout.y_pos]
    card_col = [px2pt(x) for x in layout.card_layout.x_pos]
    cards_per_page = len(card_rows) * len(card_cols)
    
    valid_pos, invalid_pos = split_by_value(skip_position, cards_per_page)
    if invalid_pos:
        print(f'Ignoring skip indices that are outside range 0-{cards_per_page-1}: {invalid_pos}')

    if len(valid_pos) >= cards_per_page:
        raise ValueError(f'You cannot skip all cards per page')

    bg_path = Paths.ASSETS / f'{layout.paper_size}_registration.jpg'
    bg_pix = fitz.Pixmap(str(bg_path))

    page_width = px2pt(layout.paper_layout.width)
    page_height = px2pt(layout.paper_layout.height)

    pdf = CardPDF(
        output_path = output_path,
        page_height = page_width, 
        page_width = page_width,
        bg = pg_pix, 
        ppi = ppi,
        ppi_scale = ppi_scale,
        cards_per_page=cards_per_page,
        font_path = Paths.ASSETS / f'arial.ttf',
        font_size = 40,
        template = layout.card_layout.template,
        name = name
    )
    
    page = pdf.new_page()

    max_card_bleed = calc_max_bleed(layout.card_layout)
    extend_corners_scale = math.floor(extend_corners*ppi_scale)
    crop_amount, crop_unit = split_float_unit(crop_string)
    card_width_scaled = math.floor(layout.card_layout_size.width*ppi_scale)
    card_height_scaled= math.floor(layout.card_layout_size.height*ppi_scale)

    def process_card_image_wrapper(card_path:Path) -> Image.Image:
        return process_card_image(
            card_path,
            card_width_scaled,
            card_height_scaled,
            ppi_scale,
            crop_amount,
            crop_unit,
            max_card_bleed,
            extend_corners_scale
        )

    for i, card in enumerate(cards.get(single_sided=True)):
        card_front_image = process_card_image_wrapper(get_image(card.front))

    
    cached_images = {}
    for i, card in enumerate(cards.get(single_sided=False)):
        card_front_image = process_card_image_wrapper(get_image(card.front))
        
        if cached_images[card.back]:
            card_back_image = cached_images[card.back]
        else
            card_back_image = process_card_image_wrapper(get_image(card.back))
            cached_images[card.back] = card_back_image
    
        






    pdf.save(output_path)
    pdf.close()







