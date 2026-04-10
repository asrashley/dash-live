from typing import BinaryIO, override

from .atom import Mp4Atom

class WrapperIterator:
    _wrapper: "Wrapper"
    _current: int
    _end: int

    def __init__(self, wrapper: "Wrapper"):
        self._wrapper = wrapper
        self._current = 0
        if wrapper._children is None:
            self._end = 0
        else:
            self._end = len(wrapper._children)

    def __next__(self):
        if self._current >= self._end:
            raise StopIteration
        rv = self._wrapper.children[self._current]
        self._current += 1
        return rv


class Wrapper(Mp4Atom):
    ATOM_FOURCC = 'wrap'
    DEFAULT_VALUES = {
        'atom_type': 'wrap',
        'position': 0,
        'parent': None,
        '_children': [],
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if self._children is None:
            self._children = []

    @override
    def encode(self, dest: BinaryIO, depth: int = 0) -> BinaryIO:
        assert depth == 0
        here: int = dest.tell()
        if self._children:
            for child in self._children:
                child.encode(dest=dest, depth=(depth + 1))
            self.post_encode_all(dest=dest)
        self.size = dest.tell() - here
        return dest

    def encode_fields(self, dest: BinaryIO) -> None:
        pass

    def __iter__(self):
        return WrapperIterator(self)
