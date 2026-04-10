#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO, ClassVar

from dashlive.utils.fio import BitsFieldReader, BitsFieldWriter

from ..atom import Mp4Atom
from ..atom_factory import AtomFactory
from ..options import Options


class AC3SpecificBox(Mp4Atom):
    ATOM_FOURCC = 'dac3'
    SAMPLE_RATES: ClassVar[list[int]] = [48000, 44100, 32000, 0]
    CHANNEL_CONFIGURATIONS: ClassVar[list[tuple[int, str]]] = [
        (2, "1 + 1 (Ch1, Ch2)"),
        (1, "1/0 (C)"),
        (2, "2/0 (L, R)"),
        (3, "3/0 (L, C, R)"),
        (3, "2/1 (L, R, S)"),
        (4, "3/1 (L, C, R, S)"),
        (4, "2/2 (L, R, SL, SR)"),
        (5, "3/2 (L, C, R, SL, SR)"),
    ]

    def encode_fields(self, dest):
        w = BitsFieldWriter(self)
        w.write(2, 'fscod')
        w.write(5, 'bsid')
        w.write(3, 'bsmod')
        w.write(3, 'acmod')
        w.write(1, 'lfe')
        w.write(5, 'bitrate_code')
        w.write(5, 'reserved', value=0x00)
        dest.write(w.toBytes())


class AC3SpecificBoxFactory(AtomFactory[AC3SpecificBox]):
    def atom_type(self) -> type[AC3SpecificBox]:
        return AC3SpecificBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = BitsFieldReader(self.classname(), src, rv, rv["size"] - rv["header_size"])
        r.read(2, 'fscod')
        r.read(5, 'bsid')
        r.read(3, 'bsmod')
        r.read(3, 'acmod')
        r.read(1, 'lfe')
        r.read(5, 'bitrate_code')
        r.get(5, 'reserved')
        rv['sampling_frequency'] = AC3SpecificBox.SAMPLE_RATES[rv["fscod"]]
        rv['channel_count'], rv['channel_configuration'] = AC3SpecificBox.CHANNEL_CONFIGURATIONS[rv['acmod']]
        if rv['lfe']:
            rv['channel_count'] += 1
        return rv
