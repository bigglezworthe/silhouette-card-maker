from pathlib import Path

from PIL import Image, ImageDraw


INPUT_DIR = Path("game/front")
OUTPUT_DIR = Path("game/front")

BORDER_WIDTH = 10

# 2 x 4 card layout, row-major.
COLORS = [
    "#e6194b",  # red
    "#3cb44b",  # green
    "#4363d8",  # blue
    "#f58231",  # orange
    "#911eb4",  # purple
    "#42d4f4",  # cyan
    "#f032e6",  # magenta
    "#bfef45",  # lime
]


def add_outline(
    image: Image.Image,
    color: str,
    width: int,
) -> Image.Image:
    draw = ImageDraw.Draw(image)

    draw.rectangle(
        (
            0,
            0,
            image.width - 1,
            image.height - 1,
        ),
        outline=color,
        width=width,
    )

    return image


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(
        path
        for path in INPUT_DIR.iterdir()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )

    for index, path in enumerate(images):
        color = COLORS[index % len(COLORS)]

        with Image.open(path) as image:
            image = image.convert("RGB")
            add_outline(image, color, BORDER_WIDTH)
            image.save(OUTPUT_DIR / path.name)

        print(f"{path.name}: {color}")


if __name__ == "__main__":
    main()
