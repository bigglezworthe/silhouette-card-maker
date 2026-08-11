# ==============================================================================
# paths.py
#     Contains relevant relative paths and file system ops
# ==============================================================================
from dataclasses import dataclass, field
import os
import filetype

from pathlib import Path

# Static root directory from THIS file
RELATIVE_ROOT = Path(__file__).parent.parent

@dataclass
class ImagePaths:
    front: Path
    back: Path
    double: Path
    output: Path
    front_image_paths: list[Path] = field(default_factory=list)
    double_image_paths: list[Path] = field(default_factory=list)
    back_image_path: Path | None = None


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


def check_paths_subset(subset: set[Path], mainset: set[Path]) -> set[Path]:
    subset_stems = {p.stem: p for p in subset}
    mainset_stems = {p.stem for p in mainset}

    return {orig for stem, orig in subset_stems.items() if stem not in mainset_stems}


# ============================
# Functions below this point been Pathified.
# ============================

# [!] Only used once. Can be removed.
def get_directory(path: Path) -> Path:
    return path.resolve() if path.is_dir() else path.parent.resolve()


# [!] Used by plugins (keeping str | Path for now)
def ensure_directory(path: str | Path) -> str | Path:
    """Create directory and any missing parent directories. Returns the path."""
    os.makedirs(path, exist_ok=True)
    return path


# [!] Only used once. Can be removed.
# Function renamed: added _exists
def ensure_output_directory_exists(output_path: Path) -> None:
    parent = output_path.parent
    if parent:
        os.makedirs(parent, exist_ok=True)


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


def get_image_file_paths(dir_path: Path) -> list[Path]:
    result: list[Path] = []

    for current_folder, _, files in os.walk(dir_path):
        for filename in files:
            full_path = os.path.join(current_folder, filename)

            # [!] Why are we using filetype.guess_mime() instead of checking extension?
            if filetype.guess_mime(full_path) in VALID_MIMETYPES:
                relative_path = os.path.relpath(full_path, dir_path)
                result.append(Path(relative_path))

    return result


# [!] Probably should be renamed. Not very similar to get_image_file_paths.
# Allows user to select when multiple card back options exist
def select_back_card_image_path(back_dir_path: Path) -> Path | None:
    files = [
        f
        for f in Path(back_dir_path).glob("*")
        if f.is_file() and filetype.guess_mime(f) in VALID_MIMETYPES
    ]

    if len(files) == 0:
        return None

    if len(files) == 1:
        return files[0]

    print("[0] No back image")
    for i, f in enumerate(files):
        print(f"[{i + 1}] {f}")

    while True:
        choice = input("Select a back image(enter the number): ")
        if not choice.isdigit():
            continue

        index = int(choice) - 1
        if index == -1:
            return None
        if index >= 0 and index < len(files):
            break

    return files[index]


def resolve_image_with_any_extension(path: str) -> str:
    p = Path(path)

    if p.is_file():
        return str(p)

    pattern = f"{p.stem}.*"
    matches = list(p.parent.glob(pattern))

    if len(matches) == 0:
        raise FileNotFoundError(f"Missing image: {pattern}")
    if len(matches) > 1:
        raise ValueError(f"Ambiguous image match: {matches}")

    return str(matches[0])
