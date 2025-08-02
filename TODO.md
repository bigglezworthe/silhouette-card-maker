* Streamlit UI
* Add pictures to tutorial
* Film video for tutorial
* Should the tutorial also mention A4 and template sizes?

----
[-] `create_pdf.py` 
    [?] Place functionality into `create_pdf.py`
    [+] Properly notate constants
    [-] Convert to use 'pathlib'
    [+] Add per-folder card back image selection
    [-] Add per-slot card back to PDF
    [ ] Now outputs 2 separate PDFs, `-single` and `-double`
        [ ] Option to enable/disable
[ ] `fetch,py`
    [ ] Centralized file that takes `plugin` as argument
    [ ] Pulls from `utils` to standardize work
    [ ] Ouputs to appropriate `{game}/{decklist_filename}/` folders for uniformity
    [ ]

[ ] Add error logging
[ ] Add configs
[ ] Link file cleanup to autorun with flag after PDF creation
[ ] Link PDF creation to autorun after image fetch
[ ] create `tools` folder housing `utils` for better hierarchy
[ ] replace `requirements.txt` with `.toml`





IMPORTANT NOTES
1) Removed warnings for unmatched double-sided backs. Card backs are now matched to fronts, so having unmatched backs in double-sided isn't a big deal. If this is important, it can be added back, although it would require a refactor.
2) Error opening `offset.json` now results in intentional crash instead of ignoring offset.
3) `create_pdf.py --load_offset now defaults to True. Why is this even an option? 
4) PDF creation units are now in pt. All units remain in px until pushed to PDF. Would save a bit of time/effort to convert all these values to px and work in that the whole time.





