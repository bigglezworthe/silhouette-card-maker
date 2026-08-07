This is a full refactor of the `create_pdf` side of the codebase. It will not touch the `plugins` beyond ensuring compatibility. 

## Goals: 

- Increase codebase maintability and readabilty
- Convert existing string-based paths to `pathlib.Path` objects 
- Keep code organized into intuitive modules
- Remove unnecessary dependencies when possible

## Outside of Scope:

- Performance. Most of the execution time is spent opening and processing images. It's unlikely that any major performance gains will occur. 
- Adding features. With a cleaner codebase and proper hooks, adding features should be simpler. Features will be in a separate branch. 

## Future Goals: 

- Config system
- Layout overhaul
- Additional tooling and organized `tools/` 
