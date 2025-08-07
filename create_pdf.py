import os
import re

from pathlib import Path
# from enum import Enum

import click
import fitz

from utilities import generate_pdf

import utils.tests
from utils.enums import Paths, CardSize, PaperSize
from utils.filesys import GamePathMaker, FileSearcher
from utils.misc import print_list
from utils.card import CardFetcher
from utils.layouts import load_layouts, make_layout
from utils.image import CardImageProcessor

VERSION = 'v1.0.0 | dev'
DEFAULT_OUTPUT_FILE = Paths.OUTPUT / 'game.pdf'

@click.command()
@click.option("--output_path", default=DEFAULT_OUTPUT_FILE, show_default=True, help="The desired path to the output PDF.")
@click.option("--output_images", default=False, is_flag=True, help="Create images instead of a PDF.")
@click.option("--card_size", default=CardSize.STANDARD.value, type=click.Choice([t.value for t in CardSize], case_sensitive=False), show_default=True, help="The desired card size.")
@click.option("--paper_size", default=PaperSize.LETTER.value, type=click.Choice([t.value for t in PaperSize], case_sensitive=False), show_default=True, help="The desired paper size.")
@click.option("--only_fronts", default=False, is_flag=True, help="Only use the card fronts, exclude the card backs.")
@click.option("--crop", default='0', show_default=True, help="Crop the outer portion of front and double-sided images. Examples: 3mm, 0.125in, 6.5.")
@click.option("--extend_corners", default=0, type=click.IntRange(min=0), show_default=True, help="Reduce artifacts produced by rounded corners in card images.")
@click.option("--ppi", default=300, type=click.IntRange(min=0), show_default=True, help="Pixels per inch (PPI) when creating PDF.")
@click.option("--quality", default=75, type=click.IntRange(min=0, max=100), show_default=True, help="File compression. A higher value corresponds to better quality and larger file size.")
@click.option("--load_offset", default=True, is_flag=True, help="Apply saved offsets. See `offset_pdf.py` for more information.")
@click.option("--skip", type=click.IntRange(min=0), multiple=True, help="Skip a card based on its index. Useful for registration issues. Examples: 0, 4.")
@click.option("--name", help="Label each page of the PDF with a name.")

@click.option("--game_dir_path", default = Paths.GAME, show_default=True, help="The path to the directory containing front, back, and double-sided card images.")
@click.option("--relative_dir_path", default = None, show_default=True, help="A common relative path to search for cards within the front, back, and double-sided folders.")
@click.option("--save_config", default=False, is_flag=True, help="Save all options to user.json")
@click.option("--load_config", default=False, is_flag=True, help="Apply saved settings (supplied settings will take precedence).")

@click.version_option(VERSION)

def cli(
    game_dir_path,
    relative_dir_path,
    output_path,
    output_images,
    card_size,
    paper_size,
    only_fronts,
    crop,
    extend_corners,
    ppi,
    quality,
    skip,
    load_offset,
    save_config,
    load_config,
    name
):
    #================================================================
    # Input grooming
    #----------------------------------------------------------------
    crop_amount, crop_unit = split_float_unit(crop.strip().lower())
    #================================================================

    game_paths = GamePathMaker(game_dir_path, relative_dir_path, output_path, output_images).dict()
    output_path = game_paths['output']

    layout = make_layout(paper_size, card_size, load_layouts(), list(skip))
    utils.tests.layout(layout, False)

    scale = ppi / layout.ppi
    borders = tuple(min(extend_corners, border) for border in layout.max_borders)

    #================================================================
    # Main Loop
    #----------------------------------------------------------------
 
    fetcher = CardFetcher(game_paths, only_fronts = only_fronts)
    img_pro = CardImageProcessor(
        card_width = layout.card_layout_size.width,
        card_height = layout.card_layout_size.height,
        scale = scale
        crop_amount = crop_amount,
        crop_unit = crop_unit,
        borders = borders
    )

    pdf_gen = CardPDFGenerator(
        path = game_paths['output'], 
        page_width = layout.paper_layout[0],
        page_height = layout.paper_layout[1], 
        ppi = ppi,
        ppi_scale = ppi / layout.ppi
        page_name = name,
        template = layout.template,
    )

    card_paths = FileSearcher(game_paths['front'], recursive=True).by_types(fetcher.image_types)
    for i, path in enumerate(card_paths):
        print(f'[{i}]')

        card = fetcher.fetch(path)
        print(f'Fetched card: {card.name}')
        if not card:
            continue

        card = img_pro.process(card)
        print(f'Processed card.')

        pdf_gen.place(card)
        print(f'Added to PDF.')
    
    print(fetcher.totals)
    #================================================================

    # pdf = generate_pdf(
    #     cards,
    #     output_path,
    #     output_images,
    #     layout,
    #     crop,
    #     extend_corners,
    #     ppi,
    #     quality,
    #     load_offset,
    #     skip,
    #     name
    # )

    print("Success")

if __name__ == '__main__':
    cli()