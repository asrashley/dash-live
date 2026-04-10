#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import struct
from typing import Any, BinaryIO

from dashlive.utils.binary import Binary
from dashlive.utils.fio import FieldReader, FieldWriter
from dashlive.utils.list_of import ListOf

from ..atom import Mp4Atom
from ..atom_factory import AtomFactory
from ..options import Options


class AVCConfigurationBox(Mp4Atom):
    ATOM_FOURCC = 'avcC'
    OBJECT_FIELDS = {
        'sps': ListOf(Binary),
        'sps_ext': ListOf(Binary),
        'pps': ListOf(Binary),
    }
    configurationVersion: int
    AVCProfileIndication: int
    profile_compatibility: int
    AVCLevelIndication: int
    lengthSizeMinusOne: int
    sps: list[bytes]
    pps: list[bytes]
    chroma_format: int
    luma_bit_depth: int
    chroma_bit_depth: int
    sps_ext: list[bytes]

    def encode_fields(self, dest):
        d = FieldWriter(self, dest, debug=self.options.debug)
        d.write('B', 'configurationVersion')
        d.write('B', 'AVCProfileIndication')
        d.write('B', 'profile_compatibility')
        d.write('B', 'AVCLevelIndication')
        d.write('B', 'lengthSizeMinusOne',
                0xFC + (self.lengthSizeMinusOne & 0x03))
        d.write('B', 'sps_count', 0xE0 + (len(self.sps) & 0x1F))
        for sps in self.sps:
            d.write('H', 'sps_size', len(sps))
            d.write(None, 'sps', sps)
        d.write('B', 'pps_count', len(self.pps) & 0x1F)
        for pps in self.pps:
            d.write('H', 'pps_size', len(pps))
            d.write(None, 'pps', pps)
        if AVCConfigurationBox.is_ext_profile(self.AVCProfileIndication) and 'chroma_format' in self._fields:
            d.write('B', 'chroma_format', self.chroma_format + 0xFC)
            d.write('B', 'luma_bit_depth', self.luma_bit_depth - 8 + 0xF8)
            d.write('B', 'chroma_bit_depth', self.chroma_bit_depth - 8 + 0xF8)
            d.write('B', 'sps_ext_count', len(self.sps_ext))
            for s in self.sps_ext:
                d.write('H', 'sps_ext_size', len(s))
                d.write(None, 'sps_ext', s)

    @classmethod
    def is_ext_profile(clz, profile_idc):
        return profile_idc in [100, 110, 122, 244, 44, 83, 86, 118,
                               128, 134, 135, 138, 139]


class AVCConfigurationBoxFactory(AtomFactory[AVCConfigurationBox]):
    def atom_type(self) -> type[AVCConfigurationBox]:
        return AVCConfigurationBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv, debug=options.debug)
        r.read('B', "configurationVersion")
        r.read('B', "AVCProfileIndication")
        r.read('B', "profile_compatibility")
        r.read('B', "AVCLevelIndication")
        r.read('B', "lengthSizeMinusOne", mask=0x03)
        numOfSequenceParameterSets: int = r.get('B', "numOfSequenceParameterSets", mask=0x1F)
        rv["sps"] = []
        for _i in range(numOfSequenceParameterSets):
            sequenceParameterSetLength: int = struct.unpack('>H', src.read(2))[0]
            sequenceParameterSetNALUnit: bytes = src.read(sequenceParameterSetLength)
            rv["sps"].append(sequenceParameterSetNALUnit)
        numOfPictureParameterSets: int = r.get('B', 'numOfPictureParameterSets')
        rv["pps"] = []
        for _i in range(numOfPictureParameterSets):
            pictureParameterSetLength: int = struct.unpack('>H', src.read(2))[0]
            pictureParameterSetNALUnit: bytes = src.read(pictureParameterSetLength)
            rv["pps"].append(pictureParameterSetNALUnit)
        end = rv["position"] + rv["size"]
        if AVCConfigurationBox.is_ext_profile(rv["AVCProfileIndication"]) and (end - src.tell()) > 3:
            r.read('B', 'chroma_format', mask=0x03)
            r.read('B', 'luma_bit_depth', mask=0x03)
            rv["luma_bit_depth"] += 8
            r.read('B', 'chroma_bit_depth', mask=0x03)
            rv["chroma_bit_depth"] += 8
            numOfSequenceParameterSetExtensions = r.get(
                'B', 'numOfSequenceParameterSetExtensions')
            rv["sps_ext"] = []
            for _i in range(numOfSequenceParameterSetExtensions):
                length: int = r.get('H', 'sps_ext_length')
                nal_unit: bytes = src.read(length)
                rv["sps_ext"].append(nal_unit)
        return rv
