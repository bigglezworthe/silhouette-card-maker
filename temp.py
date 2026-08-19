
def generate_pdf(
    image_paths: ImagePaths,
    layout_def: LayoutDef,
    output_path: Path, 
    output_images: bool,
    card_size_name: str,
    paper_size_name: str,
    registration: Registration,
    only_fronts: bool,
    render_opts: CardRenderOptions,
    ppi: int,
    quality: int,
    skip_indices: list[int],
    load_offset: bool,
    label: str,
    show_outline: bool = False,
    borderless: bool = False,
) -> None:

    # ==============================
    # Image modification
    # ==============================
    defaults = load_defaults()
    default_reg = defaults.registration.borderless if borderless else defaults.registration.default
    effective_thickness = default_reg.thickness
    effective_length = default_reg.length
    effective_inset = default_reg.inset

    if layout_def.registration is not None: 
        effective_thickness = layout_def.registration.thickness
        effective_length = layout_def.registration.length
        effective_inset = layout_def.registration.inset

    # [!] This value is extremely suspicious. Why is it default_reg.length instead of effective_length?
    total_exclusion_mm = (
        parse_to_mm(default_reg.length) + page_manager.REG_PADDING_MM
    )
    total_exclusion = f"{total_exclusion_mm}mm"

    card_size_def = layout_defs.card_sizes[card_size_name]
    paper_size_def = layout_defs.paper_sizes[paper_size_name]

    page_layout = page_manager.generate_layout(
        orientation = layout_def.orientation,
        card_width = card_size_def.width,
        card_height = card_size_def.height,
        paper_width = paper_size_def.width, 
        paper_height = paper_size_def.height,
        inset = effective_inset,
        length = total_exclusion,
        ppi = ppi
    )

    card_width_px = page_layout.card_width_px
    card_height_px = page_layout.card_height_px
    page_width_px = page_layout.paper_width_px
    page_height_px = page_layout.paper_height_px
    x_pos = page_layout.x_pos
    y_pos = page_layout.y_pos

    
    crop_size = calculate_crop_size(render_opts.front.crop, page_layout.card_size)
    crop_backs = parse_crop_string(crop_backs_string, card_width_px, card_height_px)

    extend_edges_px = parse_dimension_string(extend_edges, ppi)
    extend_edges_backs_px = parse_dimension_string(
        extend_edges_backs, ppi
    )

    extend_corners_px = parse_dimension_string(extend_corners, ppi)
    extend_corners_backs_px = parse_dimension_string(
        extend_corners_backs, ppi
    )

    extend_bleed_px = parse_dimension_string(extend_bleed, ppi)
    extend_bleed_backs_px = parse_dimension_string(
        extend_bleed_backs, ppi
    )

    fit_backs_mode = FitMode(fit_backs) if fit_backs is not None else fit

    effective_card_radius = card_size_def.radius or defaults.card_radius
    radius_px = measurements.size_to_pixel(effective_card_radius, ppi)

    # ==============================
    # PDF
    # ==============================
    num_rows = len(y_pos)
    num_cols = len(x_pos)
    num_cards = num_rows * num_cols

    if num_cards == 0:
        raise Exception(
            f'Card size "{card_size}" does not fit on paper size "{paper_size}".'
        )

    clean_skip_indices = [n for n in skip_indices if n < num_cards]
    ignore_skip_indices = [n for n in skip_indices if n >= num_cards]

    if len(ignore_skip_indices) > 0:
        print(
            f"Ignoring skip indices that are outside range 0-{num_cards - 1}: {ignore_skip_indices}"
        )

    if len(clean_skip_indices) == num_cards:
        raise ValueError("You cannot skip all cards per page!")

    ppi_ratio = ppi / 300
    inset_px = measurements.size_to_pixel(effective_inset, ppi)
    thickness_px = measurements.size_to_pixel(effective_thickness, ppi)
    if borderless:
        label_margin_px = math.floor(inset_px * ppi_ratio)
    else:
        label_margin_px = math.floor((inset_px - thickness_px * 2) * ppi_ratio)

    reg_is_portrait = registration_orientation == Orientation.PORTRAIT
    reg_width = paper_size_def.height if reg_is_portrait else paper_size_def.width
    reg_height = paper_size_def.width if reg_is_portrait else paper_size_def.height

    # ==============================
    # Page Manager
    # ==============================
    with page_manager.generate_reg_mark(
        reg_width,
        reg_height,
        effective_inset or "",
        effective_thickness or "",
        effective_length or "",
        ppi,
        registration,
    ) as reg_im:
        reg_im = reg_im.resize(
            [
                math.floor(reg_im.width * ppi_ratio),
                math.floor(reg_im.height * ppi_ratio),
            ]
        )

        if registration_orientation != orientation:
            reg_im = reg_im.rotate(90 if reg_is_portrait else -90, expand=True)

        pages: list[Image.Image] = []

        max_print_bleed = calculate_max_print_bleed(
            x_pos, y_pos, card_width_px, card_height_px, MINIMUM_BLEED
        )

        # Cache back
        single_back_image = None
        if not only_fronts and not use_default_back_page:
            if back_card_image_path is not None:
                # [!] Created load_card_image() to remove duplicated code
                single_back_image = load_card_image(back_card_image_path, "back")

        # Create card layout
        num_image = 1
        # [!] Does it really matter that it's natsorted?
        it = iter(
            natsorted(list(check_paths_subset(front_set, ds_set)))
            + natsorted(list(ds_set))
        )
        while True:
            file_group = list(itertools.islice(it, num_cards - len(clean_skip_indices)))
            if not file_group:
                break

            # Get cards in batches
            front_card_images: list[Image.Image | None] = []
            back_card_images: list[Image.Image | None] = []
            file_group_iterator = iter(file_group)
            for i in range(num_cards):
                if i in clean_skip_indices:
                    front_card_images.append(None)
                    back_card_images.append(None)
                    continue
                try:
                    file = next(file_group_iterator)
                except StopIteration:
                    break

                print(f"Image {num_image}: {file}")
                num_image += 1

                front_card_image_path = os.path.join(front_dir_path, file)
                front_card_image_path = resolve_image_with_any_extension(
                    front_card_image_path
                )

                front_card_image = load_card_image(front_card_image_path, "front")
                front_card_images.append(front_card_image)

                if only_fronts:
                    back_card_images.append(None)
                    continue

                if file in ds_set:
                    ds_card_image_path = os.path.join(ds_dir_path, file)

                    # Backside image might have different extension
                    ds_card_image_path = resolve_image_with_any_extension(
                        ds_card_image_path
                    )
                    ds_card_image = load_card_image(ds_card_image_path, "double-sided")
                    back_card_images.append(ds_card_image)
                    continue

                back_card_images.append(single_back_image)

            front_page = reg_im.copy()
            back_page = reg_im.copy()

            # [!] Consolidated calls
            draw_card_layouts(
                front_card_images,
                back_card_images,
                single_back_image,
                front_page,
                back_page,
                num_rows,
                num_cols,
                x_pos,
                y_pos,
                card_width_px,
                card_height_px,
                max_print_bleed,
                crop,
                crop_backs,
                ppi_ratio,
                extend_edges_px,
                extend_edges_backs_px,
                extend_corners_px,
                extend_corners_backs_px,
                extend_bleed_px,
                extend_bleed_backs_px,
                fit=fit,
                fit_backs=fit_backs_mode,
                orientation=orientation,
            )

            if show_outline:
                # [!] Consolidated calls
                draw_outlines(
                    [front_page, back_page],
                    x_pos,
                    y_pos,
                    card_width_px,
                    card_height_px,
                    radius_px,
                    ppi_ratio,
                )

            add_front_back_pages(
                front_page,
                back_page,
                pages,
                page_width_px,
                page_height_px,
                ppi_ratio,
                template,
                only_fronts,
                label,
                orientation,
                label_margin_px,
            )

        if len(pages) == 0:
            print("No pages were generated.")
            return

        if load_offset:
            saved_offset = load_saved_offset()

            if saved_offset is None:
                print("Offset cannot be applied")
            else:
                print(
                    "Loaded offsets:"
                    + f"x={saved_offset.x_offset},"
                    + f"y={saved_offset.y_offset},"
                    + f"angle={saved_offset.angle_offset}"
                )

        if output_images:
            for index, page in enumerate(pages):
                page.save(
                    os.path.join(output_path, f"page{index + 1}.png"),
                    resolution=math.floor(300 * ppi_ratio),
                    speed=0,
                    subsampling=0,
                    quality=quality,
                )
            print(f"Generated images: {output_path}")
        else:
            pages[0].save(
                output_path,
                format="PDF",
                save_all=True,
                append_images=pages[1:],
                resolution=math.floor(300 * ppi_ratio),
                speed=0,
                subsampling=0,
                quality=quality,
            )
            print(f"Generated PDF: {output_path}")
