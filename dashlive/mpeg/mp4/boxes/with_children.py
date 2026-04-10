from typing import BinaryIO

from ..atom import Mp4Atom
from ..atom_factory import AtomFactory

class BoxWithChildren(Mp4Atom):
    include_atom_type = True

    def encode_fields(self, dest: BinaryIO) -> None:
        pass


class BoxWithChildrenFactory[T](AtomFactory[T]):
    parse_children = True
