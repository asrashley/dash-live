#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO

from dashlive.utils.binary import Binary
from dashlive.utils.fio import BitsFieldReader, BitsFieldWriter
from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from ..atom import Mp4Atom
from ..atom_factory import AtomFactory
from ..options import Options


class HevcNalArray(ObjectWithFields):
    OBJECT_FIELDS = {
        'nal_units': ListOf(Binary),
    }

    @classmethod
    def parse(cls, reader: BitsFieldReader) -> dict[str, Any]:
        rv = {}
        r = reader.duplicate('HEVC NAL array', rv)
        r.read(1, 'array_completeness')
        r.get(1, 'reserved')
        r.read(6, 'nal_unit_type')
        num_nalus = r.get(16, 'num_nalus')
        rv['nal_units'] = []
        for i in range(num_nalus):
            unit_length = r.get(16, 'nalUnitLength')
            nal_unit = r.get_bytes(unit_length, f'NAL unit {i}')
            rv['nal_units'].append(Binary(nal_unit, encoding=Binary.BASE64))
        return rv

    def encode(self, dest):
        w = BitsFieldWriter(self, dest)
        w.write(1, 'array_completeness')
        w.write(1, 'reserved', value=0)
        w.write(6, 'nal_unit_type')
        w.write(16, 'num_nalus', value=len(self.nal_units))
        for nalu in self.nal_units:
            w.write(16, 'nalUnitLength', value=len(nalu.data))
            w.write_bytes('NAL unit', value=nalu.data)


# see FFMPEG libavformat/hevc.c for HEVCDecoderConfigurationRecord
class HEVCConfigurationBox(Mp4Atom):
    ATOM_FOURCC = 'hvcC'
    VPS_NAL_UNIT_TYPE = 32
    SPS_NAL_UNIT_TYPE = 33
    PPS_NAL_UNIT_TYPE = 34

    # general_profile_compatibility_flags
    HEVCPROFILE_MAIN = 0x0002
    HEVCPROFILE_MAIN10 = 0x0004
    HEVCPROFILE_MAIN_STILL_PICTURE = 0x0008
    HEVCPROFILE_REXT = 0x0010
    HEVCPROFILE_HIGH_THROUGHPUT = 0x0020
    HEVCPROFILE_MULTIVIEW_MAIN = 0x0040
    HEVCPROFILE_SCALABLE_MAIN = 0x0080
    HEVCPROFILE_3D_MAIN = 0x0100
    HEVCPROFILE_SCREEN_EXTENDED = 0x0200
    HEVCPROFILE_SCALABLE_REXT = 0x0400
    HEVCPROFILE_HIGH_THROUGHPUT_SCREEN_EXTENDED = 0x0800

    OBJECT_FIELDS = {
        'arrays': ListOf(HevcNalArray),
    }
    OBJECT_FIELDS.update(Mp4Atom.OBJECT_FIELDS)

    def encode_fields(self, dest):
        w = BitsFieldWriter(self)
        w.write(8, 'configuration_version')
        w.write(2, 'general_profile_space')
        w.write(1, 'general_tier_flag')
        w.write(5, 'general_profile_idc')
        w.write(32, 'general_profile_compatibility_flags')
        w.write(48, 'general_constraint_indicator_flags')
        w.write(8, 'general_level_idc')
        w.write(4, 'reserved', value=0x0F)
        w.write(12, 'min_spatial_segmentation_idc')
        w.write(6, 'reserved', value=0x3F)
        w.write(2, 'parallelismType')
        w.write(6, 'reserved', value=0x3F)
        w.write(2, 'chroma_format_idc')
        w.write(5, 'reserved', value=0x1F)
        w.write(3, 'luma_bit_depth', value=(self.luma_bit_depth - 8))
        w.write(5, 'reserved', value=0x1F)
        w.write(3, 'chroma_bit_depth', value=(self.chroma_bit_depth - 8))
        w.write(16, 'avg_framerate')
        w.write(2, 'constant_framerate')
        w.write(3, 'num_temporal_layers')
        w.write(1, 'temporal_id_nested')
        w.write(2, 'length_size_minus_one')
        w.write(8, 'num_arrays', value=len(self.arrays))
        for nal_arr in self.arrays:
            nal_arr.encode(w)
        dest.write(w.toBytes())

    def get_vps(self):
        """
        Returns the VPS NAL units in this configuration box
        """
        return self._get_nal_unit(self.VPS_NAL_UNIT_TYPE)

    def get_sps(self):
        """
        Returns the SPS NAL units in this configuration box
        """
        return self._get_nal_unit(self.SPS_NAL_UNIT_TYPE)

    def _get_nal_unit(self, nal_type):
        for nal_arr in self.arrays:
            if nal_arr.nal_unit_type == nal_type:
                return nal_arr.nal_units
        return []


class HEVCConfigurationBoxFactory(AtomFactory[HEVCConfigurationBox]):
    def atom_type(self) -> type[HEVCConfigurationBox]:
        return HEVCConfigurationBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r: BitsFieldReader = BitsFieldReader(self.classname(), src, rv, rv["size"] - rv["header_size"])
        r.read(8, 'configuration_version')
        if rv['configuration_version'] != 1:
            return rv
        r.read(2, 'general_profile_space')
        r.read(1, 'general_tier_flag')
        r.read(5, 'general_profile_idc')
        r.read(32, 'general_profile_compatibility_flags')
        r.read(48, 'general_constraint_indicator_flags')
        r.read(8, 'general_level_idc')
        r.get(4, 'reserved')
        r.read(12, 'min_spatial_segmentation_idc')
        r.get(6, 'reserved')
        r.read(2, 'parallelismType')
        r.get(6, 'reserved')
        r.read(2, 'chroma_format_idc')
        r.get(5, 'reserved')
        rv['luma_bit_depth'] = 8 + r.get(3, 'luma_bit_depth_minus8')
        r.get(5, 'reserved')
        rv['chroma_bit_depth'] = 8 + r.get(3, 'chroma_bit_depth_minus8')
        r.read(16, 'avg_framerate')
        r.read(2, 'constant_framerate')
        r.read(3, 'num_temporal_layers')
        r.read(1, 'temporal_id_nested')
        r.read(2, 'length_size_minus_one')
        num_arrays = r.get(8, 'num_arrays')
        rv['arrays'] = []
        # the 'arrays' list should contain the VPS, SPS and PPS
        for i in range(num_arrays):
            rv['arrays'].append(HevcNalArray.parse(r))
        return rv
