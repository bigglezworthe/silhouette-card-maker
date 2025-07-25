from pathlib import Path

class Paths():
    BASE = Path()
    GAME = BASE / 'game'
    FRONT = GAME / 'front'
    BACK = GAME / 'back'
    DOUBLE = GAME / 'double_sided'
    OUTPUT = GAME / 'output'
    ASSETS = BASE / 'assets'