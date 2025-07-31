def select_item(items:list, include_none:bool=True, header:str=None, footer:str="Select #:"):
    if not items:
        return None
    elif len(items) == 1:
        return items[0]

    print(header)
    for i, item in enumerate(items):
        print(f'[{i + 1}] {item}')
    
    if include_none:
        print(f'[0] None')

    while True:
        choice = input(footer)
        if not choice.isdigit():
            continue

        idx = int(choice) - 1
        if idx == -1 and include_none:
            return None 
        elif idx >= 0 and idx < len(items):
            return items[idx]

def print_list(list:list):
    num_digits = len(str(len(list)-1))
    for i, item in enumerate(list):
        print(f'[{i:0{num_digits}}] {item}')

def print_dict(dict:dict):
    for k, v in dict.items():
        print(f'{k}: {v}')

def px2pt(px:int, ppi:int)->float:
    POINT_PER_INCH = 72
    return px / ppi * POINT_PER_INCH

def split_float_unit(s:str) -> tuple[float,str]:
    s = s.strip().lower()

    float_unit_pattern = r'\s*([+-]?\d*\.?\d+)\s*([a-zA-Z]*)\s*'
    match = re.fullmatch(float_unit_pattern, s)

    if not match:
        raise ValueError(f'Invalid format: {s}')
    
    num = float(match.group(1))
    unit = match.group(2) or None  # None if unit is missing
    
    return num, unit

def split_by_value(l:list[int], n:int) -> tuple[list[int], list[int]]:
    meet = [x for x in l if x < n]
    exceed = [x for x in l if x >= n]

    return meet, exceed

    