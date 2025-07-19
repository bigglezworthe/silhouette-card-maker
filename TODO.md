* Streamlit UI
* Add pictures to tutorial
* Film video for tutorial
* Should the tutorial also mention A4 and template sizes?

----

[ ] Restructure folders
    [ ] Merge `assets` and `calibration` into `paper`
    [ ] Merge `hugo` and `images` into `tutorials`
    [ ] Split `utilities.py` into folder `utils`
    [ ] Move image folders to `root`
[ ] Refactor files
    [ ] Replace use of `os.path` with `pathlib` Paths
    [ ] Replace `pypdfium` dependency with `pymupdf`
    [ ] Adopt dot notation for local imports
    [ ] Make proper constants
    [ ] Standalone tools should have CLI interface
[ ] Create `json` config for common CLI settings
[ ] Scale down tutorial images by ~50% to save disk space


