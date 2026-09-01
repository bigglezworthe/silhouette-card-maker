#==============================================================================
# cards.py
#     Card objects and accessories.
#==============================================================================

from collections.abc import Collection, Iterator
from itertools import islice
from pathlib import Path

from PIL import Image, ImageOps

from src.paths import ImagePaths, get_relative_stem, index_image_paths, select_back_image_path
from src.render_models import Card, CardSide, Cards

#============================
# Find Cards
#============================
def find_cards(image_dirs: ImagePaths, only_front_images: bool = False) -> Cards:
    # [!] Can't we just ignore the 2 errors instead of crashing? 
    # [!] Maybe a y/n warn with CLI --ignore flag?
    cards: list[Card] = []

    front_image_paths = index_image_paths(image_dirs.front_dir)
    double_image_paths = index_image_paths(image_dirs.double_dir)

    if only_front_images and double_image_paths:
        raise ValueError(
            'Cannot use "--only_fronts" with double-sided cards.' 
            + f'Remove cards from double_side image directory: {image_dirs.double_dir}'
        )

    unmatched_backs: list[Path] = []
    for key, back_path in double_image_paths.items():
        front_path = front_image_paths.pop(key, None)
        if front_path is None:
            unmatched_backs.append(back_path)
            continue

        cards.append(
            Card(
                front = CardSide(name=key, path=front_path),
                back = CardSide(name=key, path=back_path),
            )
        )

    if double_image_paths:
        raise ValueError(
            f'Double-sided backs "{unmatched_backs}" do not have matching fronts.'
            + f'Add the missing fronts to front image directory: {image_dirs.front_dir}'
        )

    for key, path in front_image_paths.items():
        cards.append(Card(front=CardSide(name=key, path=path), back=None))
    
    card_back = find_default_back(image_dirs.back_dir) if not only_front_images else None

    return Cards(cards=cards, default_back=card_back)

def find_default_back(back_dir: Path) -> CardSide | None:
    back_image_path = select_back_image_path(back_dir) 

    if back_image_path is None:
        print(f"No back image provided from back image directory: {back_dir}")
        return None
    back_name = get_relative_stem(back_image_path, back_dir)
    return CardSide(name=back_name, path=back_image_path)

def load_card_side(card_side: CardSide) -> CardSide:
    try:
        image = Image.open(card_side.path)
        return CardSide(
            name = card_side.name,
            path = card_side.path,
            image = ImageOps.exif_transpose(image),
        )
    except FileNotFoundError:
        # [!] This shouldn't ever happen
        print(f'Cannot find image: {card_side.path}.')
        return card_side
    except OSError as e:
        raise OSError(f'Failed to load image "{card_side.path}": {e}') from e

def load_cards(cards: Collection[Card]) -> list[Card]:
    loaded_cards: list[Card] = []

    for card in cards:
        front = load_card_side(card.front)
        back = load_card_side(card.back) if card.back is not None else None

        loaded_cards.append(Card(front, back))

    return loaded_cards

def batch_cards(cards: Collection[Card], size: int) -> Iterator[list[Card]]:
    card_iter = iter(cards)

    while batch := list(islice(card_iter, size)):
        yield batch


