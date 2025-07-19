import os
import shutil

# These should really be declared globally in a constant.py file
FRONT_IMAGE_PATH = os.path.join('game', 'front')
BACK_IMAGE_PATH = os.path.join('game', 'back')
DOUBLE_IMAGE_PATH = os.path.join('game', 'double_sided')

# Default ignore list
IGNORE_FILE_LIST = ['EMPTY.md']
IGNORE_TYPE_LIST = ['md']
DEFAULT_IGNORE = {'files':IGNORE_FILE_LIST, 'types':IGNORE_TYPE_LIST}

def create_ignore_dict(
    ignore_filenames_list:[str], 
    ignore_extensions_list:[str]
    ) -> {str:[str],str:[str]}:

    return {'files':ignore_filenames_list, 'types':ignore_extensions_list}

def empty_folder(folder_path:str, ignore:{str:[str]}=DEFAULT_IGNORE) -> int:
    i = 0

    for item in os.listdir(folder_path):
        full_path = os.path.join(folder_path, item)

        if item in ignore['files']:
            continue
        elif os.path.splitext(item) in ignore['types']:
            continue

        if os.path.isfile(full_path):
            os.remove(full_path)
            print(f'Deleted file {full_path}')
            i += 1
        elif os.path.isdir(full_path):
            shutil.rmtree(full_path)
            print(f'Deleted directory {full_path}')
            i += 1

    return i

def empty_folders(folder_paths:[str], ignore:{str:[str]}=DEFAULT_IGNORE):
    i = 0
    for fldr in folder_paths:
        i = i + empty_folder(fldr, ignore)
    
    print(f'Deleted {i} item{"s"*bool(i-1)}') 

if __name__ == '__main__':
    empty_folders([FRONT_IMAGE_PATH, BACK_IMAGE_PATH, DOUBLE_IMAGE_PATH], DEFAULT_IGNORE)  