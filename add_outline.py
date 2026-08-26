from pathlib import Path

from PIL import Image, ImageDraw


INPUT_DIR = Path("game/front")
OUTPUT_DIR = Path("game/front")
BORDER_WIDTH = 10


def add_border(image: Image.Image, width: int) -> Image.Image:
    draw = ImageDraw.Draw(image)

    draw.rectangle(
        (
            0,
            0,
            image.width - 1,
            image.height - 1,
        ),
        outline="black",
        width=width,
    )

    return image


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    for path in INPUT_DIR.iterdir():
        if not path.is_file():
            continue

        try:
            with Image.open(path) as image:
                image = image.convert("RGB")
                add_border(image, BORDER_WIDTH)
                image.save(OUTPUT_DIR / path.name)

        except (OSError, ValueError):
            print(f"Skipping {path}")


if __name__ == "__main__":
    main()
