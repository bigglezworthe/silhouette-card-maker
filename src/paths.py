#==============================================================================
# paths.py 
#     Contains relevant relative paths and file system ops 
#==============================================================================
import os
import filetype

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
    output: Path = game / 'output'

#============================
# Functions below this point been Pathified. 
#============================

# [!] Unnecessary function. These files tend to repopulate. 
def delete_hidden_files_in_directory(path: Path) -> None:
    if not path.is_dir():
        return
    
    # Was global 
    extraneous_files = {".DS_Store", "Thumbs.db", "desktop.ini", "Icon\r"}

    for item in path.iterdir():
        if item.is_file() and (item in extraneous_files or item.name.startswith("._")):
            try:
                os.remove(item)
                print(f"Removed hidden file: {item}")
            except OSError as e:
                print(f"Could not remove {item}: {e}")

# [!] Only used once. Can be removed.
def get_directory(path: Path) -> Path:
    return path if path.is_dir() else path.parent

# [!] Only used once. Can be removed. 
# Function renamed: added _exists
def ensure_output_directory_exists(output_path: Path) -> None:
    parent = output_path.parent
    if parent:
        os.makedirs(parent, exist_ok=True)

#============================
# Image paths 
#============================
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

def get_image_file_paths(dir_path: str) -> list[str]:
    result: list[str] = []

    for current_folder, _, files in os.walk(dir_path):
        for filename in files:
            full_path = os.path.join(current_folder, filename)
           
           # [!] Why are we using filetype.guess_mime() instead of checking extension?
            if filetype.guess_mime(full_path) in VALID_MIMETYPES:
                relative_path = os.path.relpath(full_path, dir_path)
                result.append(relative_path)

    return result 

# [!] Probably should be renamed. Not very similar to get_image_file_paths.
# Allows user to select when multiple card back options exist
def get_back_card_image_path(back_dir_path: str | Path) -> Path | None:
    files = [f 
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
