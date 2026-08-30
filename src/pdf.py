# ==============================================================================
# pdf.py
#     PDF generation
# ==============================================================================
import math

from pathlib import Path

from src.defaults import DEFAULT_PPI
from src.draw import (DuplexPage)
from src.enums import Orientation, OrientationMode
from src.page_manager import (generate_layout)
from src.render_models import PageLayout

# [!] Might belong in layout.py?
def find_best_orientation(
    orientation_mode: OrientationMode,
    card_width: str,
    card_height: str,
    paper_width: str,
    paper_height: str,
    inset: str,
    length: str,
    ppi: int,
    preferred: Orientation = Orientation.LANDSCAPE,
) -> tuple[Orientation, PageLayout]:
    # [!] Need to package this more reasonably
    kwargs = dict(
        card_width=card_width,
        card_height=card_height,
        paper_width=paper_width,
        paper_height=paper_height,
        inset=inset,
        length=length,
        ppi=ppi,
    )

    if orientation_mode != OrientationMode.OPTIMIZE:
        orientation = Orientation(orientation_mode.value)
        return orientation, generate_layout(orientation=orientation, **kwargs)

    # try both orientations and pick the one that fits more cards
    best_count = 0
    best_orientation = preferred
    best_computed = None

    for orient in Orientation:
        try:
            computed = generate_layout(orientation=orient, **kwargs)
        except ValueError:
            continue

        count = len(computed.x_pos) * len(computed.y_pos)
        if count > best_count or (count == best_count and orient == preferred):
            best_count = count
            best_orientation = orient
            best_computed = computed

    if best_computed is None:
        raise ValueError("No valid layout in either card orientation.")

    return best_orientation, best_computed


def generate_pdf(
    duplex_pages: list[DuplexPage],
    output_path: Path,
    output_images: bool,
    ppi_scale: float,
    quality: int,
) -> None:

    images = [image for page in duplex_pages for image in (page.front, page.back)]

    print("Saving...")
    if output_images:
        for i, image in enumerate(images):
            image.save(
                output_path / f"page{i + 1}.png",
                resolution=math.floor(DEFAULT_PPI * ppi_scale),
                speed=0,
                subsampling=0,
                quality=quality,
            )
    else:
        images[0].save(
            output_path,
            format="PDF",
            save_all=True,
            append_images=images[1:],
            resolution=math.floor(DEFAULT_PPI * ppi_scale),
            speed=0,
            subsampling=0,
            quality=quality,
        )
    print(f"Generated PDF: {output_path}")
