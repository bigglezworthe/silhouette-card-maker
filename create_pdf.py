import os
import re

from pathlib import Path
# from enum import Enum

import click
import fitz

from utilities import Paths, CardSize, PaperSize, generate_pdf, get_cards

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
@click.option("--name", help="Label each page of the PDF with a name.")

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
    load_offset,
    name
):

    image_paths = {}
    image_paths['front'] = Path(front_dir_path)
    image_paths['back'] = Path(back_dir_path)
    image_paths['double'] = Path(double_sided_dir_path)
    output_path = Path(output_path)

    crop = crop.strip().lower()

    cards = get_cards(image_paths)
    num_digits = len(str(len(cards)-1))
    for i, card in enumerate(cards):
        print(f"[{i:0{num_digits}}] {card.name}")
        print(f'    front: {card.front}')
        print(f'    back: {card.back}')
        #card.front.save(output_path / f'{card.name}.{card.front.format}')
        #card.back.save(output_path / f'{card.name}_back.{card.back.format}')
        

    # pdf = generate_pdf(
    #     front_dir_path,
    #     back_dir_path,
    #     double_sided_dir_path,
    #     output_path,
    #     output_images,
    #     card_size,
    #     paper_size,
    #     only_fronts,
    #     crop,
    #     extend_corners,
    #     ppi,
    #     quality,
    #     load_offset,
    #     name
    # )

    print("Success")

if __name__ == '__main__':
    cli()