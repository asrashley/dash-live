#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO, override

from dashlive.utils.fio import FieldReader, FieldWriter

from ..atom import Mp4Atom
from ..options import Options

from .full import FullBox, FullBoxFactory


class TrackFragmentHeaderBox(FullBox):
    ATOM_FOURCC = 'tfhd'
    base_data_offset_present = 0x000001
    sample_description_index_present = 0x000002
    default_sample_duration_present = 0x000008
    default_sample_size_present = 0x000010
    default_sample_flags_present = 0x000020
    duration_is_empty = 0x010000
    default_base_is_moof = 0x020000

    def encode_box_fields(self, dest):
        if self.base_data_offset is None:
            self.base_data_offset = self.find_atom('moof').position
        w = FieldWriter(self, dest)
        w.write('I', 'track_id')
        if self.flags & self.base_data_offset_present:
            w.write('Q', 'base_data_offset')
        if self.flags & self.sample_description_index_present:
            w.write('I', 'sample_description_index')
        if self.flags & self.default_sample_duration_present:
            w.write('I', 'default_sample_duration')
        if self.flags & self.default_sample_size_present:
            w.write('I', 'default_sample_size')
        if self.flags & self.default_sample_flags_present:
            w.write('I', 'default_sample_flags')


class TrackFragmentHeaderBoxFactory(FullBoxFactory[TrackFragmentHeaderBox]):
    def atom_type(self) -> type[TrackFragmentHeaderBox]:
        return TrackFragmentHeaderBox

    @override
    def depends_upon(self):
        return {'moof'}

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        rv["base_data_offset"] = None
        rv["sample_description_index"] = 0
        rv["default_sample_duration"] = 0
        rv["default_sample_size"] = 0
        rv["default_sample_flags"] = 0
        r = FieldReader(self.classname(), src, rv)
        r.read('I', 'track_id')
        if rv["flags"] & TrackFragmentHeaderBox.base_data_offset_present:
            r.read('Q', 'base_data_offset')
        elif rv["flags"] & TrackFragmentHeaderBox.default_base_is_moof:
            rv["base_data_offset"] = parent.find_atom('moof').position
        if rv["flags"] & TrackFragmentHeaderBox.sample_description_index_present:
            r.read('I', 'sample_description_index')
        if rv["flags"] & TrackFragmentHeaderBox.default_sample_duration_present:
            r.read('I', 'default_sample_duration')
        if rv["flags"] & TrackFragmentHeaderBox.default_sample_size_present:
            r.read('I', 'default_sample_size')
        if rv["flags"] & TrackFragmentHeaderBox.default_sample_flags_present:
            r.read('I', 'default_sample_flags')
        if rv["base_data_offset"] is None:
            rv["base_data_offset"] = parent.find_atom('moof').position
        return rv
