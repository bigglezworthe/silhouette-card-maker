from enum import Enum
import itertools
import json
import math
import os
from pathlib import Path
import re
from typing import Dict, List
from xml.dom import ValidationErr


from natsort import natsorted
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel

from utils.filesys import FileSearcher
from utils.misc import select_item
from utils.enums import CardSize, PaperSize
from utils.layouts import CardLayoutSize, CardLayout, PaperLayout, Layout, Layouts

#=================================================================
# BLEED
#-----------------------------------------------------------------
def draw_card_with_bleed(card_image: Image, base_image: Image, box: tuple[int, int, int, int], print_bleed: tuple[int, int]):
    origin_x, origin_y, _, _ = box

    x_bleed = print_bleed[0]
    y_bleed = print_bleed[1]

    width, height = card_image.size
    base_image.paste(card_image, (origin_x, origin_y))

    class Axis(int, Enum):
        X = 0
        Y = 1

    def extend_edge(crop_box: tuple[int, int, int, int], start: tuple[int, int], bleed: int, axis: Axis):
        for bleed_i in range(bleed):
            pos = (
                start[0] + (bleed_i if axis == Axis.X else 0),
                start[1] + (bleed_i if axis == Axis.Y else 0)
            )

            base_image.paste(card_image.crop(crop_box), pos)

    # Extend the edges of the cards to create print bleed
    # Top and bottom
    extend_edge((0, 0, width, 1), (origin_x, origin_y - y_bleed), y_bleed, Axis.Y)
    extend_edge((0, height - 1, width, height), (origin_x, origin_y + height), y_bleed, Axis.Y)

    # Left and right
    extend_edge((0, 0, 1, height), (origin_x - x_bleed, origin_y), x_bleed, Axis.X)
    extend_edge((width - 1, 0, width, height), (origin_x + width, origin_y), x_bleed, Axis.X)

    # Corners
    for x_bleed, crop_x, pos_x in [(x_bleed, 0, origin_x - x_bleed), (x_bleed, width - 1, origin_x + width)]:
        for y_bleed, crop_y, pos_y in [(y_bleed, 0, origin_y - y_bleed), (y_bleed, height - 1, origin_y + height)]:
            for x_bleed_i in range(x_bleed):
                for y_bleed_i in range(y_bleed):
                    base_image.paste(card_image.crop((crop_x, crop_y, crop_x + 1, crop_y + 1)), (pos_x + x_bleed_i, pos_y + y_bleed_i))

    return base_image

def calculate_max_print_bleed(x_pos: List[int], y_pos: List[int], width: int, height: int) -> tuple[int, int]:
    if len(x_pos) == 1 & len(y_pos) == 1:
        return (0, 0)

    x_border_max = 100000
    if len(x_pos) >= 2:
        x_pos.sort()

        x_pos_0 = x_pos[0]
        x_pos_1 = x_pos[1]

        x_border_max = math.ceil((x_pos_1 - x_pos_0 - width) / 2)

        if x_border_max < 0:
            x_border_max = 100000

    y_border_max = 100000
    if len(y_pos) >= 2:
        y_pos.sort()

        y_pos_0 = y_pos[0]
        y_pos_1 = y_pos[1]

        y_border_max = math.ceil((y_pos_1 - y_pos_0 - height) / 2)

        if y_border_max < 0:
            y_border_max = 100000

    return (x_border_max, y_border_max)
#-----------------------------------------------------------------

#=================================================================
# LAYOUT
#-----------------------------------------------------------------

def draw_card_layout(card_images: List[Image.Image], base_image: Image.Image, num_rows: int, num_cols: int, x_pos: List[int], y_pos: List[int], width: int, height: int, print_bleed: tuple[int, int], crop: tuple[float, float], ppi_ratio: float, extend_corners: int, flip: bool):
    num_cards = num_rows * num_cols

    # Fill all the spaces with the card back
    for i, card_image in enumerate(card_images):

        # Calculate the location of the new card based on what number the card is
        new_origin_x = math.floor(x_pos[i % num_cards % num_cols] * ppi_ratio)
        new_origin_y = math.floor(y_pos[(i % num_cards) // num_cols] * ppi_ratio)

        if flip:
            new_origin_y = math.floor(y_pos[num_rows - ((i % num_cards) // num_cols) - 1] * ppi_ratio)

            # Rotate the back image to account for orientation
            card_image = card_image.rotate(180)

        # Crop the outer portion of a card to remove preexisting print bleed
        crop_x_percent, crop_y_percent = crop
        if crop_x_percent > 0 or crop_y_percent > 0:
            card_width, card_height = card_image.size
            card_width_crop = math.floor(card_width / 2 * (crop_x_percent / 100))
            card_height_crop = math.floor(card_height / 2 * (crop_y_percent / 100))

            card_image = card_image.crop((
                card_width_crop,
                card_height_crop,
                card_width - card_width_crop,
                card_height - card_height_crop
            ))

        # Resize the image to normalize extend_corners
        card_image = card_image.resize((math.floor(width * ppi_ratio), math.floor(height * ppi_ratio)))

        extend_corners_ppi = math.floor(extend_corners * ppi_ratio)
        card_image = card_image.crop((extend_corners_ppi, extend_corners_ppi, card_image.width - extend_corners_ppi, card_image.height - extend_corners_ppi))

        draw_card_with_bleed(
            card_image,
            base_image,
            (new_origin_x + extend_corners_ppi, new_origin_y + extend_corners_ppi, math.floor(width * ppi_ratio) - (2 * extend_corners_ppi), math.floor(height * ppi_ratio) - (2 * extend_corners_ppi)),
            tuple(math.ceil(bleed * ppi_ratio) + extend_corners_ppi for bleed in print_bleed)
        )

def add_front_back_pages(front_page: Image.Image, back_page: Image.Image, pages: List[Image.Image], page_width: int, page_height: int, ppi_ratio: float, template: str, only_fronts: bool, name: str):
    # Add template version number to the back
    draw = ImageDraw.Draw(front_page)
    font = ImageFont.truetype(os.path.join(asset_directory, 'arial.ttf'), 40 * ppi_ratio)

    # "Raw" specified location
    num_sheet = len(pages) + 1
    if not only_fronts:
        num_sheet = int(len(pages) / 2) + 1

    label = f'sheet: {num_sheet}, template: {template}'
    if name is not None:
        label = f'name: {name}, {label}'

    draw.text((math.floor((page_width - 180) * ppi_ratio), math.floor((page_height - 140) * ppi_ratio)), label, fill = (0, 0, 0), anchor="ra", font=font)

    # Add a back page for every front page template
    pages.append(front_page)
    if not only_fronts:
        pages.append(back_page)

#=================================================================
# MAIN
#-----------------------------------------------------------------

def generate_pdf(
    output_path: Path,
    output_images: bool,
    card_size: CardSize,
    paper_size: PaperSize,
    only_fronts: bool,
    crop_string: str,
    extend_corners: int,
    ppi: int,
    quality: int,
    skip_positions: List[int],
    load_offset: bool,
    name: str
):
    #====================================================================
    # DISABLED CHECKS FOR UNMATCHED DOUBLE-SIDED BACKS
    #--------------------------------------------------------------------
    # Check if double-sided back images has matching front images
    # front_set = set(front_image_filenames)
    # ds_set = set(ds_image_filenames)
    # if not ds_set.issubset(front_set):
    #     raise Exception(f'Double-sided backs "{ds_set - front_set}" do not have matching fronts. Add the missing fronts to front image directory "{front_dir_path}".')

    # if only_fronts:
    #     if len(ds_set) > 0:
    #         raise Exception(f'Cannot use "--only_fronts" with double-sided cards. Remove cards from double-side image directory "{double_sided_dir_path}".')
    #--------------------------------------------------------------------

        # Not sure why this happens now. Do this later.
        # crop = parse_crop_string(crop_string, card_layout.width, card_layout.height)

        # Load an image with the registration marks
        with Image.open(registration_path) as reg_im:
            reg_im = reg_im.resize([math.floor(reg_im.width * ppi_ratio), math.floor(reg_im.height * ppi_ratio)])
            # Create the array that will store the filled templates
            pages: List[Image.Image] = []

            max_print_bleed = calculate_max_print_bleed(card_layout.x_pos, card_layout.y_pos, card_layout.width, card_layout.height)

            # Create reusable back page for single-sided cards
            single_sided_back_page = reg_im.copy()
            if not use_default_back_page:

                # Load the card back image
                with Image.open(back_card_image_path) as back_im:
                    back_im = ImageOps.exif_transpose(back_im)

                    draw_card_layout(
                        [back_im] * num_cards,
                        single_sided_back_page,
                        num_rows,
                        num_cols,
                        card_layout.x_pos,
                        card_layout.y_pos,
                        card_layout.width,
                        card_layout.height,
                        max_print_bleed,
                        (0, 0),
                        ppi_ratio,
                        extend_corners,
                        flip=True
                    )

            # Create single-sided card layout
            num_image = 1
            it = iter(natsorted(list(front_set - ds_set)))
            while True:
                file_group = list(itertools.islice(it, num_cards))
                if not file_group:
                    break

                # Fetch card art
                front_card_images = []
                for file in file_group:
                    print(f'Image {num_image}: {file}')
                    num_image = num_image + 1

                    front_image_path = os.path.join(front_dir_path, file)
                    front_image = Image.open(front_image_path)
                    front_image = ImageOps.exif_transpose(front_image)
                    front_card_images.append(front_image)

                single_sided_front_page = reg_im.copy()

                # Create front layout for single-sided cards
                draw_card_layout(
                    front_card_images,
                    single_sided_front_page,
                    num_rows,
                    num_cols,
                    card_layout.x_pos,
                    card_layout.y_pos,
                    card_layout.width,
                    card_layout.height,
                    max_print_bleed,
                    crop,
                    ppi_ratio,
                    extend_corners,
                    flip=False
                )

                add_front_back_pages(
                    single_sided_front_page,
                    single_sided_back_page,
                    pages,
                    paper_layout.width,
                    paper_layout.height,
                    ppi_ratio,
                    card_layout.template,
                    only_fronts,
                    name
                )

            # Create double-sided card layout
            it = iter(natsorted(list(ds_set)))
            while True:
                file_group = list(itertools.islice(it, num_cards))
                if not file_group:
                    break

                # Fetch card art
                front_card_images = []
                back_card_images = []
                for file in file_group:
                    print(f'Image {num_image} (double-sided): {file}')
                    num_image = num_image + 1

                    front_image_path = os.path.join(front_dir_path, file)
                    front_image = Image.open(front_image_path)
                    front_image = ImageOps.exif_transpose(front_image)
                    front_card_images.append(front_image)

                    ds_image_path = os.path.join(double_sided_dir_path, file)
                    ds_image = Image.open(ds_image_path)
                    ds_image = ImageOps.exif_transpose(ds_image)
                    back_card_images.append(ds_image)

                double_sided_front_page = reg_im.copy()
                double_sided_back_page = reg_im.copy()

                # Create front layout for double-sided cards
                draw_card_layout(
                    front_card_images,
                    double_sided_front_page,
                    num_rows,
                    num_cols,
                    card_layout.x_pos,
                    card_layout.y_pos,
                    card_layout.width,
                    card_layout.height,
                    max_print_bleed,
                    crop,
                    ppi_ratio,
                    extend_corners,
                    flip=False
                )

                # Create back layout for double-sided cards
                draw_card_layout(
                    back_card_images,
                    double_sided_back_page,
                    num_rows,
                    num_cols,
                    card_layout.x_pos,
                    card_layout.y_pos,
                    card_layout.width,
                    card_layout.height,
                    max_print_bleed,
                    crop,
                    ppi_ratio,
                    extend_corners,
                    flip=True
                )

                # Add the front and back layouts
                add_front_back_pages(
                    double_sided_front_page,
                    double_sided_back_page,
                    pages,
                    paper_layout.width,
                    paper_layout.height,
                    ppi_ratio,
                    card_layout.template,
                    False,
                    name
                )

            if len(pages) == 0:
                print('No pages were generated')
                return

            # Load saved offset if available
            if load_offset:
                saved_offset = load_saved_offset()

                if saved_offset is None:
                    print('Offset cannot be applied')
                else:
                    print(f'Loaded x offset: {saved_offset.x_offset}, y offset: {saved_offset.y_offset}')
                    pages = offset_images(pages, saved_offset.x_offset, saved_offset.y_offset, ppi)

            # Save the pages array as a PDF
            if output_images:
                for index, page in enumerate(pages):
                    page.save(os.path.join(output_path, f'page{index + 1}.png'), resolution=math.floor(300 * ppi_ratio), speed=0, subsampling=0, quality=quality)

                print(f'Generated images: {output_path}')

            else:
                pages[0].save(output_path, format='PDF', save_all=True, append_images=pages[1:], resolution=math.floor(300 * ppi_ratio), speed=0, subsampling=0, quality=quality)
                print(f'Generated PDF: {output_path}')


#==============================================================================
# OFFSET 
#------------------------------------------------------------------------------
class OffsetData(BaseModel):
    x_offset: int
    y_offset: int

def save_offset(x_offset, y_offset) -> None:
    # Create the directory if it doesn't exist
    os.makedirs('data', exist_ok=True)

    # Save the offset data to a JSON file
    with open('data/offset_data.json', 'w') as offset_file:
        offset_file.write(OffsetData(x_offset=x_offset, y_offset=y_offset).model_dump_json(indent=4))

    print('Offset data saved!')

def load_saved_offset() -> OffsetData:
    if os.path.exists('data/offset_data.json'):
        with open('data/offset_data.json', 'r') as offset_file:
            try:
                data = json.load(offset_file)
                return OffsetData(**data)

            except json.JSONDecodeError as e:
                print(f'Cannot decode offset JSON: {e}')

            except ValidationErr as e:
                print(f'Cannot validate offset data: {e}.')

    return None

def offset_images(images: List[Image.Image], x_offset: int, y_offset: int, ppi: int) -> List[Image.Image]:
    offset_images = []

    add_offset = False
    for image in images:
        if add_offset:
            offset_images.append(ImageChops.offset(image, math.floor(x_offset * ppi / 300), math.floor(y_offset * ppi / 300)))
        else:
            offset_images.append(image)

        add_offset = not add_offset

    return offset_images
#------------------------------------------------------------------------------