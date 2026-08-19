# ==============================================================================
# paths.py
#     Contains relevant relative paths and file system ops
# ==============================================================================
from collections.abc import Collection
from dataclasses import dataclass, field
import os
import filetype

from pathlib import Path

# Static root directory from THIS file
RELATIVE_ROOT = Path(__file__).parent.parent

@dataclass
class ImagePaths:
    front_dir: Path
    back_dir: Path
    double_dir: Path
    front_images: list[Path] = field(default_factory=list)
    double_images: list[Path] = field(default_factory=list)
    back_image: Path | None = None


# [!] How exhaustive should this be?
class Paths:
    root: Path = RELATIVE_ROOT
    assets: Path = root / "assets"
    game: Path = root / "game"
    fronts: Path = game / "front"
    backs: Path = game / "back"
    doubles: Path = game / "double_sided"
    # [!] Should this be the output file or just the directory?
    output: Path = game / "output"


def match_stems(paths: Collection[Path], reference: Collection[Path]) -> tuple[set[Path], set[Path]]:
    ref_stems = {path.stem for path in reference}
    return {path for path in paths if path.stem in ref_stems}, {path for path in paths if path.stem not in ref_stems}

# [!] Used by plugins (keeping str | Path for now)
def ensure_directory(path: str | Path) -> str | Path:
    """Create directory and any missing parent directories. Returns the path."""
    os.makedirs(path, exist_ok=True)
    return path

def prepare_output_path(output_path: Path, is_dir: bool) -> Path:
    if is_dir: 
        output_path.mkdir(parents=True, exist_ok=True)

    if output_path.suffix.lower() == ".pdf":
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        raise ValueError(f"Invalid PDF output file path: {output_path}")

    return output_path

# ============================
# Image paths
# ============================
# [!] Might get moved to images.py

# List can be found here: https://github.com/h2non/filetype.py?tab=readme-ov-file#image
# Pillow suported formats: https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html
VALID_MIMETYPES = (
    # "image/vnd.dwg",
    # "image/x-xcf",
    "image/jpeg",
    "image/jpx",
    # "image/jxl",
    "image/png",
    "image/apng",
    "image/gif",
    "image/webp",
    # "image/x-canon-cr2",
    "image/tiff",
    "image/bmp",
    # "image/vnd.ms-photo",
    # "image/vnd.adobe.photoshop",
    # "image/x-icon",
    # "image/heic",
    "image/avif",
    "image/qoi",
    "image/dds",
)

def resolve_image_with_any_extension(path: Path) -> str:

    if path.is_file():
        return str(path)

    pattern = f"{path.stem}.*"
    matches = list(path.parent.glob(pattern))

    if len(matches) == 0:
        raise FileNotFoundError(f"Missing image: {pattern}")
    if len(matches) > 1:
        raise ValueError(f"Ambiguous image match: {matches}")

    return str(matches[0])
def get_relative_stem(path: Path, relative: Path) -> Path:
    return path.relative_to(relative).with_suffix("")

def index_image_paths(dir_path: Path, recursive: bool = True) -> dict[Path, Path]:
    result: dict[Path, Path] = {}

    paths = dir_path.rglob("*") if recursive else dir_path.glob("*")
    for path in paths: 
        if path.is_file() and filetype.guess_mime(path) in VALID_MIMETYPES:
            relative_stem = get_relative_stem(path, dir_path)
            if relative_stem in result:
                raise ValueError(
                    "Images cannot have the same path with different extension:"
                    + f"{result[relative_stem]} and {path}"
                )
            result[relative_stem] = path

    return result

# Allows user to select when multiple card back options exist
def select_back_image_path(back_dir_path: Path) -> Path | None:
    file_dict = index_image_paths(back_dir_path, recursive=False)

    if len(file_dict) == 0:
        return None

    files = list(file_dict.values()) 

    if len(files) == 1:
        return files[0]

    print("[0] No back image")
    for i, f in enumerate(files, start=1):
        print(f"[{i}] {f}")

    while True:
        choice = input("Select a back image(enter the number): ")
        if not choice.isdigit():
            continue

        index = int(choice)
        if index == 0:
            return None
        if 1 <= index <= len(files):
            return files[index-1]
