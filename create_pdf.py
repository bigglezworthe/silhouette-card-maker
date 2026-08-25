import click

from pathlib import Path

from src.cards import find_cards
from src.enums import Orientation, Registration, FitMode 
from src.measurements import DEFAULT_PPI 
from src.paths import ImagePaths, Paths, prepare_output_path
from src.pdf import generate_pdf
from src.layouts import (
    get_all_card_size_names,
    get_all_paper_size_names,
    get_all_specialty_layout_names,
    load_layouts,
    prepare_layout,
)

from src.render_models import CardRenderOptions, SideRenderOptions

#============================
# Initialize Defaults
#============================
OUTPUT_DIRECTORY = Paths.output
DEFAULT_OUTPUT_PATH = OUTPUT_DIRECTORY / "game.pdf"

CARD_SIZE_CHOICES = get_all_card_size_names()
PAPER_SIZE_CHOICES = get_all_paper_size_names()
SPECIALTY_CHOICES = get_all_specialty_layout_names()

# ============================
# CLI Args
# ============================
@click.command()
@click.option("--front_dir_path", default=Paths.fronts, type=click.Path(path_type=Path, file_okay=False, exists=True), show_default=True, help="The path to the directory containing the card fronts.")
@click.option("--back_dir_path", default=Paths.backs, type=click.Path(path_type=Path, file_okay=False, exists=True), show_default=True, help="The path to the directory containing one or more card backs.")
@click.option("--double_sided_dir_path", default=Paths.doubles, type=click.Path(path_type=Path, file_okay=False, exists=True), show_default=True, help="The path to the directory containing card backs for double-sided cards.")
@click.option("--output_path", default=DEFAULT_OUTPUT_PATH, type=click.Path(path_type=Path), show_default=True, help="The desired path to the output PDF.")
@click.option("--output_images", default=False, is_flag=True, help="Create images instead of a PDF.")
@click.option("--card_size", default="standard", type=click.Choice(CARD_SIZE_CHOICES, case_sensitive=False), show_default=True, help="The desired card size.")
@click.option("--paper_size", default="letter", type=click.Choice(PAPER_SIZE_CHOICES, case_sensitive=False), show_default=True, help="The desired paper size.")
@click.option("--registration", default=Registration.THREE.value, type=click.Choice([t.value for t in Registration], case_sensitive=False), show_default=True, help="The desired registration pattern.")
@click.option("--registration_orientation", default=None, type=click.Choice([t.value for t in Orientation], case_sensitive=False), help="Override the registration mark orientation without changing the card layout.")
@click.option("--specialty", default=None, type=click.Choice(SPECIALTY_CHOICES, case_sensitive=False), help="Use a specialty layout. Overrides card_size, paper_size, and registration settings.")
@click.option("--only_fronts", default=False, is_flag=True, help="Only generate front pages.")
@click.option("--fit", default=FitMode.STRETCH.value, type=click.Choice([t.value for t in FitMode], case_sensitive=False), show_default=True, help="How to fit front and double-sided images to card size. 'stretch' allows distortion, 'crop' preserves aspect ratio by center-cropping.")
@click.option("--fit_backs", type=click.Choice([t.value for t in FitMode], case_sensitive=False), help="How to fit back images to card size. 'stretch' allows distortion, 'crop' preserves aspect ratio by center-cropping.")
@click.option("--crop", help="Crop card edges of front and double-sided images (removes edges). Examples: 3mm, 0.125in, 6.5.")
@click.option("--crop_backs", help="Crop card edges of back images (removes edges). Examples: 3mm, 0.125in, 6.5.")
@click.option("--extend_edges", help="Crop card edges and extend them for front and double-sided images. Examples: 3mm, 0.125in.")
@click.option("--extend_edges_backs", help="Crop card edges and extend them for back images only. Examples: 3mm, 0.125in.")
@click.option("--extend_corners", help="Extend rounded corner regions to reduce corner artifacts for front and double-sided images. Examples: 3mm, 0.125in.")
@click.option("--extend_corners_backs", help="Extend rounded corner regions to reduce corner artifacts for back images only. Examples: 3mm, 0.125in.")
@click.option("--extend_bleed", help="Extend the outer bleed of outer cards on front pages (odd-numbered pages). Examples: 3mm, 0.125in.")
@click.option("--extend_bleed_backs", help="Extend the outer bleed of outer cards on back pages (even-numbered pages). Examples: 3mm, 0.125in.")
@click.option("--ppi", default=DEFAULT_PPI, type=click.IntRange(min=0), show_default=True, help="Pixels per inch (PPI) when creating PDF.")
@click.option("--quality", default=100, type=click.IntRange(min=0, max=100), show_default=True, help="File compression quality.")
@click.option("--load_offset", default=False, is_flag=True, help="Apply saved offsets. See `offset_pdf.py` for more information.")
@click.option("--skip", default=[], type=click.IntRange(min=0), multiple=True, help="Skip a card based on its index. Useful for registration issues. Examples: 0, 4.")
@click.option("--label", default="", help="Apply a custom label to each page.")
@click.option("--show_outline", default=False, is_flag=True, help="Show a white outline for cutting paths.")
@click.option("--borderless", default=False, is_flag=True, help="Use tighter inset to fit more cards per page.")
@click.version_option("2.2.0")
# ============================

def cli(
    front_dir_path: Path,
    back_dir_path: Path,
    double_sided_dir_path: Path,
    output_path: Path,
    output_images: bool,
    card_size: str,
    paper_size: str,
    registration: Registration,
    registration_orientation: Orientation | None,
    specialty: str | None,
    only_fronts: bool,
    fit: FitMode,
    fit_backs: FitMode,
    crop: str | None,
    crop_backs: str | None,
    extend_edges: str | None,
    extend_edges_backs: str | None,
    extend_corners: str | None,
    extend_corners_backs: str | None,
    extend_bleed: str | None,
    extend_bleed_backs: str | None,
    ppi: int,
    quality: int,
    skip: list[int],
    load_offset: bool,
    label: str,
    show_outline: bool,
    borderless: bool,
) -> None:

    image_paths = ImagePaths(
        front_dir_path.resolve(), 
        back_dir_path.resolve(), 
        double_sided_dir_path.resolve(),
    )
    output_path = prepare_output_path(output_path, output_images)

    cards = find_cards(image_paths, only_fronts)
    
    ppi_scale = ppi / DEFAULT_PPI

    # [!] Need to track down what ACTUALLY happens when None is supplied
    registration_orientation = registration_orientation or Orientation.LANDSCAPE

    #========================
    # Layout
    #========================
    layout_defs = load_layouts()
    layout_def = prepare_layout(
        layout_defs = layout_defs,
        card_size_name = card_size,
        paper_size_name = paper_size,
        borderless = borderless,
        specialty_name = specialty,
        registration_orientation_override = registration_orientation,
    )

    #========================
    # Structure Init
    #========================
    render_opts = CardRenderOptions(
        front = SideRenderOptions(
            crop = crop,
            extend_edges = extend_edges,
            extend_corners_radius = extend_corners,
            extend_bleed = extend_bleed,
            fit = fit,
        ),
        back = SideRenderOptions(
            crop = crop_backs,
            extend_edges = extend_edges_backs,
            extend_corners_radius = extend_corners_backs,
            extend_bleed = extend_bleed_backs,
            fit = fit_backs,
        ),
        orientation = registration_orientation,
    )

    
    generate_pdf(
        image_paths = image_paths,
        cards = cards,
        layout_def = layout_def,
        output_path = output_path,
        output_images = output_images,
        card_size_name = card_size,
        paper_size_name = paper_size,
        registration = registration,
        only_fronts = only_fronts,
        render_opts = render_opts,
        ppi_scale = ppi_scale,
        quality = quality,
        skip_indices = skip,
        load_offset = load_offset,
        label = label,
        show_outline = show_outline,
        borderless = borderless,
    )


if __name__ == "__main__":
    cli()
