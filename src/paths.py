# Contains relevant paths.

from pathlib import Path

# Root directory from THIS file
RELATIVE_ROOT = Path(__file__).parent.parent 

# [!] How exhaustive should this be? 
class Paths:
    root: Path = RELATIVE_ROOT 
    assets: Path = root / 'assets'
    game: Path = root / 'game'
    fronts: Path = game / 'fronts'
    backs: Path = game / 'backs'
    doubles: Path = game / 'double-sided'
