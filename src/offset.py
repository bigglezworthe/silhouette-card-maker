#==============================================================================
# offset.py 
#     Duplex printing alignment. Feeds offset_pdf.py.
#==============================================================================

import os
import json 

from pydantic import BaseModel
from .paths import Paths

from xml.dom import ValidationErr

DATA_PATH = Paths.root / "data"
OFFSET_DATA_PATH = DATA_PATH / "offset_data.json"

class OffsetData(BaseModel):
    x_offset: int = 0 
    y_offset: int = 0
    angle_offset: float = 0.0

def save_offset(x_offset: int, y_offset: int, angle_offset: float = 0.0) -> None:
    os.makedirs(DATA_PATH, exist_ok=True)
    
    with open(OFFSET_DATA_PATH, 'w') as offset_file:
        offset_data = OffsetData(x_offset=x_offset, y_offset=y_offset,angle_offset=angle_offset)
        _ = offset_file.write(offset_data.model_dump_json(indent=4))
    print("Offset data saved!")

# [!] Method of OffsetData?
def load_saved_offset() -> OffsetData | None:
    if not OFFSET_DATA_PATH.is_file():
        return None 
    
    with open(OFFSET_DATA_PATH, 'r') as offset_file:
        try:
            data = json.load(offset_file)
            return OffsetData(**data)
        except json.JSONDecodeError as e:
            print(f"Cannot decode offset JSON: {e}")
        except ValidationErr as e:
            print(f"Cannot validate offset data: {e}")

    return None



        
