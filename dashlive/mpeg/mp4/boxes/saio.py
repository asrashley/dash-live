#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import struct
from typing import Any, BinaryIO, override

from dashlive.utils.fio import FieldWriter

from ..atom import Mp4Atom
from .full import FullBox, FullBoxFactory
from ..options import Options


class SampleAuxiliaryInformationOffsetsBox(FullBox):
    ATOM_FOURCC = 'saio'

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        if self.flags & 0x01:
            w.write('I', 'aux_info_type')
            w.write('I', 'aux_info_type_parameter')
        if self.offsets is None:
            pos = self.find_first_cenc_sample()
            if pos < 0:
                pos = 0
            if pos is not None:
                self.offsets = [pos]
            else:
                self.offsets = []
        w.write('I', 'entry_count', value=len(self.offsets))
        for off in self.offsets:
            if self.version == 0:
                w.write('I', 'offset', value=off)
            else:
                w.write('Q', 'offset', value=off)

    def find_first_cenc_sample(self) -> int | None:
        if self._parent is None:
            return None
        parent = self._parent()
        if not parent:
            return None
        senc = parent.find_child('senc')
        if senc is None:
            return None
        if len(senc.samples) == 0:
            return None
        tfhd = parent.find_child('tfhd')
        base_data_offset: int | None = None
        if tfhd is not None:
            base_data_offset = tfhd.base_data_offset
        if base_data_offset is None:
            moof = self.find_atom('moof')
            base_data_offset = moof.position
        assert base_data_offset is not None
        senc_sample_pos: int = senc.position + senc.samples[0].offset
        return senc_sample_pos - base_data_offset

    def post_encode(self, dest):
        if self.offsets is not None and len(self.offsets) != 1:
            return
        if self._parent is None:
            return
        parent = self._parent()
        if not parent:
            return
        senc = parent.find_child('senc')
        if senc is None:
            return
        pos = self.find_first_cenc_sample()
        if self.offsets is None or pos != self.offsets[0]:
            if self.options.has_bug('saio'):
                return
            self.options.log.debug('%s: SENC sample offset has changed', self._fullname)
            self.offsets = [pos]
            pos = dest.tell()
            dest.seek(self.position)
            self.encode(dest)
            dest.seek(pos)

    def _to_json(self, exclude):
        exclude.add('aux_info_type')
        fields = super(FullBox, self)._to_json(exclude)
        if "aux_info_type" in self._fields:
            fields['aux_info_type'] = '0x%x' % self.aux_info_type
        return fields


class SampleAuxiliaryInformationOffsetsBoxFactory(FullBoxFactory[SampleAuxiliaryInformationOffsetsBox]):
    def atom_type(self) -> type[SampleAuxiliaryInformationOffsetsBox]:
        return SampleAuxiliaryInformationOffsetsBox

    @override
    def depends_upon(self) -> set[str]:
        return {'moof', 'senc', 'tfhd'}

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        if rv["flags"] & 0x01:
            rv["aux_info_type"] = struct.unpack('>I', src.read(4))[0]
            rv["aux_info_type_parameter"] = struct.unpack('>I', src.read(4))[0]
        entry_count = struct.unpack('>I', src.read(4))[0]
        rv["offsets"] = []
        for _ in range(entry_count):
            if rv["version"] == 0:
                o = struct.unpack('>I', src.read(4))[0]
            else:
                o = struct.unpack('>Q', src.read(8))[0]
            rv["offsets"].append(o)
        return rv
