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
from .full import FullBox, FullBoxFactory
from ..options import Options


class SampleAuxiliaryInformationSizesBox(FullBox):
    ATOM_FOURCC = 'saiz'

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        if self.flags & 1:
            w.write('I', 'aux_info_type')
            w.write('I', 'aux_info_type_parameter')
        w.write('B', 'default_sample_info_size')
        if self.default_sample_info_size == 0:
            self.sample_count = len(self.sample_info_sizes)
        w.write('I', 'sample_count')
        if self.default_sample_info_size == 0:
            for sz in self.sample_info_sizes:
                w.write('B', 'size', value=sz)

    def _to_json(self, exclude):
        exclude.add('aux_info_type')
        fields = super(FullBox, self)._to_json(exclude)
        if "aux_info_type" in self._fields:
            fields['aux_info_type'] = '0x%x' % self.aux_info_type
        return fields


class SampleAuxiliaryInformationSizesBoxFactory(FullBoxFactory[SampleAuxiliaryInformationSizesBox]):
    def atom_type(self) -> type[SampleAuxiliaryInformationSizesBox]:
        return SampleAuxiliaryInformationSizesBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        if rv["flags"] & 1:
            rv["aux_info_type"] = struct.unpack('>I', src.read(4))[0]
            rv["aux_info_type_parameter"] = struct.unpack('>I', src.read(4))[0]
        rv["default_sample_info_size"] = struct.unpack('B', src.read(1))[0]
        rv["sample_info_sizes"] = []
        rv["sample_count"] = struct.unpack('>I', src.read(4))[0]
        if rv["default_sample_info_size"] == 0:
            for _ in range(rv["sample_count"]):
                rv["sample_info_sizes"].append(struct.unpack('B', src.read(1))[0])
        return rv
