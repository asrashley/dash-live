#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from pathlib import Path

def generate_new_filename(in_directory: Path, name: str, suffix: str) -> Path:
    index: int = 1
    new_name: Path = in_directory / f'{name}{suffix}'
    while new_name.exists():
        new_name = in_directory / f'{name}_{index:02d}{suffix}'
        index += 1
    return new_name
