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

class SampleDescriptionBox(FullBox):
    ATOM_FOURCC = 'stsd'

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'entry_count')


class SampleDescriptionBoxFactory(FullBoxFactory[SampleDescriptionBox]):
    parse_children = True

    def atom_type(self) -> type[SampleDescriptionBox]:
        return SampleDescriptionBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        rv["entry_count"] = struct.unpack('>I', src.read(4))[0]
        return rv
