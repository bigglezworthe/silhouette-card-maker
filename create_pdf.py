import os
import re

from pathlib import Path
# from enum import Enum

import click
import fitz

from utilities import generate_pdf

from utils.enums import Paths, CardSize, PaperSize
from utils.filesys import require_item
from utils.misc import print_list
from utils.card import get_cards
from utils.layouts import load_layouts, make_layout

VERSION = 'v1.0.0 | dev'
DEFAULT_OUTPUT_FILE = Paths.OUTPUT / 'game.pdf'

@click.command()
@click.option("--front_dir_path", default=Paths.FRONT, show_default=True, help="The path to the directory containing the card fronts.")
@click.option("--back_dir_path", default=Paths.BACK, show_default=True, help="The path to the directory containing one or more card backs.")
@click.option("--double_sided_dir_path", default=Paths.DOUBLE, show_default=True, help="The path to the directory containing card backs for double-sided cards.")
@click.option("--output_path", default=DEFAULT_OUTPUT_FILE, show_default=True, help="The desired path to the output PDF.")
@click.option("--output_images", default=False, is_flag=True, help="Create images instead of a PDF.")
@click.option("--card_size", default=CardSize.STANDARD.value, type=click.Choice([t.value for t in CardSize], case_sensitive=False), show_default=True, help="The desired card size.")
@click.option("--paper_size", default=PaperSize.LETTER.value, type=click.Choice([t.value for t in PaperSize], case_sensitive=False), show_default=True, help="The desired paper size.")
@click.option("--only_fronts", default=False, is_flag=True, help="Only use the card fronts, exclude the card backs.")
@click.option("--crop", default='0', show_default=True, help="Crop the outer portion of front and double-sided images. Examples: 3mm, 0.125in, 6.5.")
@click.option("--extend_corners", default=0, type=click.IntRange(min=0), show_default=True, help="Reduce artifacts produced by rounded corners in card images.")
@click.option("--ppi", default=300, type=click.IntRange(min=0), show_default=True, help="Pixels per inch (PPI) when creating PDF.")
@click.option("--quality", default=75, type=click.IntRange(min=0, max=100), show_default=True, help="File compression. A higher value corresponds to better quality and larger file size.")
@click.option("--load_offset", default=False, is_flag=True, help="Apply saved offsets. See `offset_pdf.py` for more information.")
@click.option("--skip", type=click.IntRange(min=0), multiple=True, help="Skip a card based on its index. Useful for registration issues. Examples: 0, 4.")
@click.option("--name", help="Label each page of the PDF with a name.")
@click.version_option(VERSION)

def cli(
    front_dir_path,
    back_dir_path,
    double_sided_dir_path,
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
    name
):

    #================================================================
    # Input grooming
    #----------------------------------------------------------------
    image_paths = {
        'front': require_item(front_dir_path, False, f'Front Image Folder not found: {front_dir_path}'),
        'back': require_item(back_dir_path, False, f'Back Image Folder not found: {back_dir_path}'),
        'double': require_item(double_sided_dir_path, False, f'Double-Sided Image Folder not found: {double_sided_dir_path}')
    }

    if output_images: 
        output_path = require_item(output_path, False, f'Invalid output path. Must be a folder if using --output_images: {output_path}')
    
    crop = crop.strip().lower()
    skip = list(skip)

    #================================================================

    layout = make_layout(paper_size, card_size, load_layouts(), skip)
    print(f'Skip: {skip}')
    print(f'CCP: {len(layout.card_pos)}')
    print(f'Layout Card Positions:')
    print_list(layout.card_pos)

    cards = get_cards(image_paths, only_fronts)

    # print_list(cards.single_sided)
    # print_list(cards.double_sided)

    card_stats = cards.total()  
    for k, v in cards.total().items():
        print(f'{k}: {v}')

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