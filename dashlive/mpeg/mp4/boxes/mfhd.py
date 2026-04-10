#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import struct
from typing import Any, BinaryIO

from dashlive.utils.fio import FieldWriter

from ..atom import Mp4Atom
from ..options import Options

from .full import FullBox, FullBoxFactory

class MovieFragmentHeaderBox(FullBox):
    ATOM_FOURCC = 'mfhd'

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'sequence_number')


class MovieFragmentHeaderBoxFactory(FullBoxFactory[MovieFragmentHeaderBox]):
    def atom_type(self) -> type[MovieFragmentHeaderBox]:
        return MovieFragmentHeaderBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        rv["sequence_number"] = struct.unpack('>I', src.read(4))[0]
        return rv
