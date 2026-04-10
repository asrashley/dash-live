from abc import abstractmethod
import struct
from typing import Any, BinaryIO, ClassVar

from dashlive.utils.fio.field_reader import FieldReader
from dashlive.utils.fio.field_writer import FieldWriter

from ..atom import Mp4Atom
from ..atom_factory import AtomFactory
from ..options import Options

class FullBox(Mp4Atom):
    FB_HEADER_SIZE: ClassVar[int] = 4  # number of bytes used for the version and flags fields

    version: int
    flags: int

    def encode_fields(self, dest: BinaryIO) -> None:
        d = FieldWriter(self, dest)
        d.write('B', 'version')
        d.write(3, 'flags', value=struct.pack('>I', self.flags)[1:])
        self.encode_box_fields(dest)

    @abstractmethod
    def encode_box_fields(self, dest: BinaryIO) -> None:
        pass


class FullBoxFactory[T](AtomFactory[T]):
    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv, debug=options.debug)
        r.read("B", "version")
        r.read('3I', "flags")
        return rv
