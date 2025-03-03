from typing import Union, List
import os

from colorama import Fore



def green(s:str) -> str:
    return Fore.GREEN + s + Fore.RESET

def yellow(s:str) -> str:
    return Fore.YELLOW + s + Fore.RESET

def red(s:str) -> str:
    return Fore.RED + s + Fore.RESET



def sec2hms(seconds):
    """ Return a string of hours, minutes, seconds from a given number of seconds """
    minutes, seconds = divmod(round(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}' {seconds}''"



def list_files_with_extension(ext: Union[str, tuple, list], rep, recursive=True) -> List[str]:
    """
        Recursively list all files of the given extension(s) in a folder

        Parameters
        ----------
            ext : str|list
                file extension, including the extension separator (dot)
    """
    extensions = (ext) if isinstance(ext, str) else ext
    file_list = []
    if os.path.isdir(rep):
        for filename in os.listdir(rep):
            filename = os.path.join(rep, filename)
            if os.path.isdir(filename) and recursive:
                file_list.extend(list_files_with_extension(extensions, filename))
            else:
                file_ext = os.path.splitext(filename)[1]
                if file_ext and file_ext in extensions:
                    file_list.append(filename)
    return file_list



def read_file_drop_comments(path: str) -> List[str]:
    lines = []
    with open(path, 'r', encoding='utf-8') as f:
        for l in f.readlines():
            l = l.strip()
            if l and not l.startswith('#'):
                lines.append(l)
    return lines