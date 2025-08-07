from pathlib import Path 

class GamePathMaker:
    def __init__(self, game_path:str, rel_path: str|None, output_path:str, output_is_folder:bool=False):
        self.rel = rel_path or ''
        self.game = self._require_item_wrapper(Path(game_path), 'Game')
        self.front = self._require_item_wrapper(self.game / 'front' / self.rel, 'Front')
        self.back = self._require_item_wrapper(self.game / 'back' / self.rel, 'Back')
        self.double = self._require_item_wrapper(self.game / 'double_sided' / self.rel, 'Double-Sided')

        if output_is_folder:
            self.output = self._require_item_wrapper(self.game / output_path, 'Output') 
        else:
            self.output = self.game / output_path
        
    def _require_item_wrapper(self,path:Path, name:str)->Path:
        return require_item(
            path=path,
            is_file=False,
            error_msg=f'{name} Folder not found: {path}'
        )

    def dict(self):
        return {
            'game': self.game,
            'front': self.front,
            'back': self.back,
            'double': self.double,
            'output': self.output
        }
    
class FileSearcher:
    def __init__(self, path: Path, recursive: bool = True, ignore_hidden: bool = False):
        self.path = path
        self.recursive = recursive
        self.ignore_hidden = ignore_hidden
        self._update_glob_func()

    def _update_glob_func(self):
        self.glob_func = self.path.rglob if self.recursive else self.path.glob

    def _is_visible(self, f: Path) -> bool:
        return not self.ignore_hidden or not f.name.startswith('.')

    def _glob_from(self, path: Path, pattern: str, recursive: bool):
        func = path.rglob if recursive else path.glob
        return func(pattern)

    def by_name(self, name:str, path:Path=None, recursive:bool=None) -> list[Path]:
        path = path or self.path
        recursive = self.recursive if recursive is None else recursive
        return [f for f in self._glob_from(path, name, recursive) if self._is_visible(f)]

    def by_types(self, types:list[str]=None, path:Path=None, recursive:bool=None) -> list[Path]:
        types = types or ['']
        path = path or self.path
        recursive = self.recursive if recursive is None else recursive

        results = []
        for ext in types:
            pattern = f'*{ext.lower()}'
            results.extend(
                f for f in self._glob_from(path, pattern, recursive) if self._is_visible(f)
            )
        return results            

    def bottom_up(self, root_path:Path=None, types:list[str]=None) -> list[Path]:
        root_path = root_path or Path()
        search_dir = self.path

        while True:
            files = self.by_types(types, path=search_dir, recursive=False)
            if files:
                return files

            if search_dir == root_path:
                break

            search_dir = search_dir.parent

        return None

def require_item(path:str|Path, is_file:bool=True, error_msg:str=None) -> Path:
    error_msg = error_msg or f'Invalid path: {path}'
    path = Path(path)

    file_check = is_file and not path.is_file()
    dir_check = not is_file and not path.is_dir()

    if file_check or dir_check:
        raise FileNotFoundError(f'{error_msg}')

    return path


