#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO, ClassVar

import bitstring

from dashlive.utils.fio import BitsFieldReader
from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from ..atom import Mp4Atom
from ..atom_factory import AtomFactory
from ..options import Options


class EAC3SubStream(ObjectWithFields):
    DEFAULT_EXCLUDE = {'src'}

    @classmethod
    def parse(cls, r):
        r.read(2, 'fscod')
        r.read(5, 'bsid')
        r.read(5, 'bsmod')
        r.read(3, 'acmod')
        r.kwargs['channel_count'] = EAC3SpecificBox.ACMOD_NUM_CHANS[r.kwargs['acmod']]
        r.kwargs['sampling_frequency'] = EAC3SpecificBox.FSCOD_SAMPLE_RATE[r.kwargs['fscod']]
        r.read(1, 'lfeon')
        r.get(3, 'reserved')
        r.read(4, 'num_dep_sub')
        if r.kwargs["num_dep_sub"] > 0:
            r.read(9, 'chan_loc')
        else:
            r.get(1, 'reserved')

    def encode_fields(self, ba):
        ba.append(bitstring.pack('uint:2, uint:5, uint:5, uint:3, bool',
                                 self.fscod, self.bsid, self.bsmod, self.acmod,
                                 self.lfeon))
        ba.append(bitstring.Bits(uint=0, length=3))  # reserved
        ba.append(bitstring.Bits(uint=self.num_dep_sub, length=4))
        if self.num_dep_sub > 0:
            ba.append(bitstring.Bits(uint=self.chan_loc, length=9))
        else:
            ba.append(bitstring.Bits(uint=0, length=1))  # reserved


# See section C.3.1 of ETSI TS 103 420 V1.2.1
class EAC3SpecificBox(Mp4Atom):
    ATOM_FOURCC = 'dec3'
    ACMOD_NUM_CHANS: ClassVar[list[int]] = [2, 1, 2, 3, 3, 4, 4, 5]
    FSCOD_SAMPLE_RATE: ClassVar[list[int]] = [48000, 44100, 32000, 0]

    OBJECT_FIELDS = {
        "substreams": ListOf(EAC3SubStream),
    }
    OBJECT_FIELDS.update(Mp4Atom.OBJECT_FIELDS)

    substreams: list[EAC3SubStream]
    data_rate: int
    flag_ec3_extension_type_a: bool = False
    complexity_index_type_a: int | None = None

    def encode_fields(self, dest) -> None:
        ba = bitstring.BitArray()
        num_ind_sub: int = len(self.substreams)
        ba.append(bitstring.pack('uint:13, uint:3', self.data_rate,
                                 num_ind_sub - 1))
        for s in self.substreams:
            s.encode_fields(ba)
        if 'flag_ec3_extension_type_a' in self._fields:
            ba.append(bitstring.pack('uint:7, bool, uint:8', 0,
                                     self.flag_ec3_extension_type_a,
                                     self.complexity_index_type_a))
        dest.write(ba.bytes)


class EAC3SpecificBoxFactory(AtomFactory[EAC3SpecificBox]):
    def atom_type(self) -> type[EAC3SpecificBox]:
        return EAC3SpecificBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r: BitsFieldReader = BitsFieldReader(self.classname(), src, rv, size=None)
        r.read(13, "data_rate")
        num_ind_sub: int = r.get(3, "num_ind_sub") + 1
        rv["substreams"] = []
        for _ in range(num_ind_sub):
            r2 = r.duplicate("EAC3SubStream", {})
            EAC3SubStream.parse(r2)
            rv["substreams"].append(EAC3SubStream(**r2.kwargs))
        if (r.bitpos() + 16) <= r.bitsize:
            r.get(7, 'reserved')
            r.read(1, 'flag_ec3_extension_type_a')
            r.read(8, 'complexity_index_type_a')
        return rv
