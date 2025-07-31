from pathlib import Path
from enum import Enum

class Paths():
    BASE = Path()
    GAME = BASE / 'game'
    FRONT = GAME / 'front'
    BACK = GAME / 'back'
    DOUBLE = GAME / 'double_sided'
    OUTPUT = GAME / 'output'
    ASSETS = BASE / 'assets'
    DATA = BASE / 'data'

class ImageType(str, Enum):
    JPG = ".jpg"
    JPEG = ".jpeg"
    PNG = ".png"
    GIF = ".gif"
    BMP = ".bmp"
    TIFF = ".tiff"
    WEBP = ".webp"
    AVIF = ".avif"

class CardSize(str, Enum):
    STANDARD = "standard"
    JAPANESE = "japanese"
    POKER = "poker"
    POKER_HALF = "poker_half"
    BRIDGE = "bridge"
    BRIDGE_SQUARE = "bridge_square"
    DOMINO = "domino"
    DOMINO_SQUARE = "domino_square"

class PaperSize(str, Enum):
    LETTER = "letter"
    TABLOID = "tabloid"
    A4 = "a4"
    A3 = "a3"
    ARCHB = "archb"