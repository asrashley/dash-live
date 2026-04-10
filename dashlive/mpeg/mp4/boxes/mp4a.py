#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO

from dashlive.utils.fio import FieldReader, FieldWriter

from ..atom import Mp4Atom
from ..atom_factory import AtomFactory
from ..options import Options


# see table 6.3 of 3GPP TS 26.244 V12.3.0
class MP4AudioSampleEntry(Mp4Atom):
    ATOM_FOURCC = 'mp4a'

    def encode_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write(6, 'reserved', b'')
        w.write('H', 'data_reference_index')
        w.write(8, 'reserved_8', b'')
        w.write('H', 'reserved_2', 2)
        w.write('H', 'reserved_2', 16)
        w.write(4, 'reserved_4', b'')
        w.write('H', 'timescale')
        w.write(2, 'reserved', b'')


class MP4AudioSampleEntryFactory(AtomFactory[MP4AudioSampleEntry]):
    parse_children = True

    def atom_type(self) -> type[MP4AudioSampleEntry]:
        return MP4AudioSampleEntry

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.get(6, 'reserved')  # (8)[6] reserved
        r.read('H', "data_reference_index")
        r.get(16, 'reserved')  # reserved 8,2,2,4
        r.read('H', "timescale")
        r.get(2, 'reserved')  # (16) reserved
        return rv
