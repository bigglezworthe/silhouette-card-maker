from pathlib import Path

import numpy as np
from PIL import Image


MAIN = Path("game/output/steve_doran/page1.png")
REFACTOR = Path("game/output/steve_doran_rf/page1.png")
OUTPUT = Path("game/output/directional_diff.png")


main = np.asarray(Image.open(MAIN).convert("RGB"), dtype=np.int16)
refactor = np.asarray(Image.open(REFACTOR).convert("RGB"), dtype=np.int16)

if main.shape != refactor.shape:
    raise ValueError(
        f"Image dimensions differ: "
        f"main={main.shape}, refactor={refactor.shape}"
    )

main_brightness = main.mean(axis=2)
refactor_brightness = refactor.mean(axis=2)

different = np.any(main != refactor, axis=2)

main_darker = different & (main_brightness < refactor_brightness)
refactor_darker = different & (refactor_brightness < main_brightness)
ambiguous = different & ~(main_darker | refactor_darker)

diff = np.full(main.shape, 255, dtype=np.uint8)

diff[main_darker] = (255, 80, 80)
diff[refactor_darker] = (80, 120, 255)
diff[ambiguous] = (255, 210, 50)

Image.fromarray(diff).save(OUTPUT)

print(f"Different pixels: {different.sum():,}")
print(f"Saved: {OUTPUT}")
