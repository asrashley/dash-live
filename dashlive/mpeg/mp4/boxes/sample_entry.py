import struct
from typing import Any, BinaryIO

from ..atom import Mp4Atom
from ..atom_factory import AtomFactory
from ..options import Options
from dashlive.utils.fio.field_reader import FieldReader

class SampleEntry(Mp4Atom):
    def encode_fields(self, dest: BinaryIO) -> None:
        dest.write(b'\0' * 6)  # reserved
        dest.write(struct.pack('>H', self.data_reference_index))


class SampleEntryFactory[T](AtomFactory[T]):
    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv, debug=options.debug)
        r.skip(6)  # reserved
        r.read('H', 'data_reference_index')
        return rv
