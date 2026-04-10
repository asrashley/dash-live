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


class BitRateBox(Mp4Atom):
    ATOM_FOURCC = 'btrt'
    bufferSizeDB: int
    maxBitrate: int
    avgBitrate: int

    def encode_fields(self, dest):
        d = FieldWriter(self, dest, debug=self.options.debug)
        d.write('I', 'bufferSizeDB')
        d.write('I', 'maxBitrate')
        d.write('I', 'avgBitrate')


class BitRateBoxFactory(AtomFactory[BitRateBox]):
    def atom_type(self) -> type[BitRateBox]:
        return BitRateBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv, debug=options.debug)
        r.read('I', 'bufferSizeDB')
        r.read('I', 'maxBitrate')
        r.read('I', 'avgBitrate')
        return rv
