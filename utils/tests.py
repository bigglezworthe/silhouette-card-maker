from utils.layouts import Layout

def layout(layout:Layout, perform:bool)->bool:
    if perform:
        print(f'Skip: {skip}')
        print(f'CCP: {layout.cards_per_page}')
        print(f'Layout Card Positions:')
        print_list(layout.card_positions)
        print(f'CardSize: {layout.card_layout_size}')
        print(f'PaperSize: {layout.paper_layout}')
        print('Layout scale test: x2')
        layout.scale(2)
        print_list(layout.card_positions)
        print(f'CardSize: {layout.card_layout_size}')
        print(f'PaperSize: {layout.paper_layout}')

    return True