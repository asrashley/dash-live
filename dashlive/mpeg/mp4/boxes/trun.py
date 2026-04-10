#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import struct
from typing import AbstractSet, Any, BinaryIO, cast, ClassVar, override

from dashlive.mpeg.nal import Nal
from dashlive.utils.fio import FieldWriter
from dashlive.utils.json_object import JsonObject
from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from ..atom import MODULE_PREFIX_RE, Mp4Atom
from ..options import Options

from .full import FullBox, FullBoxFactory
from .tfhd import TrackFragmentHeaderBox

# See section 8.8.8 of ISO/IEC 14496-12
class TrackSample(ObjectWithFields):
    REQUIRED_FIELDS = {
        'index': int,
        'offset': int,
    }
    composition_time_offset: int
    duration: int | None
    flags: int
    index: int
    offset: int
    size: int

    @classmethod
    def parse(
            cls, src: BinaryIO, index: int, offset: int,
            trun: dict[str, Any], tfhd: TrackFragmentHeaderBox) -> dict[str, Any]:
        rv = {
            'index': index,
            'offset': offset,
            'duration': None
        }
        flags = trun["flags"]
        if flags & TrackFragmentRunBox.sample_duration_present:
            rv['duration'] = struct.unpack('>I', src.read(4))[0]
        elif tfhd.default_sample_duration:
            rv['duration'] = tfhd.default_sample_duration
        if flags & TrackFragmentRunBox.sample_size_present:
            rv['size'] = struct.unpack('>I', src.read(4))[0]
        else:
            rv['size'] = tfhd.default_sample_size
        if flags & TrackFragmentRunBox.sample_flags_present:
            rv['flags'] = struct.unpack('>I', src.read(4))[0]
        else:
            rv['flags'] = tfhd.default_sample_flags
        if index == 0 and (flags & TrackFragmentRunBox.first_sample_flags_present):
            rv['flags'] = trun["first_sample_flags"]
        if flags & TrackFragmentRunBox.sample_composition_time_offsets_present:
            if trun['version']:
                rv["composition_time_offset"] = struct.unpack('>i', src.read(4))[0]
            else:
                rv["composition_time_offset"] = struct.unpack('>I', src.read(4))[0]
        return rv

    def encode(self, dest: BinaryIO, version: int, flags: int) -> None:
        d = FieldWriter(self, dest)
        if flags & TrackFragmentRunBox.sample_duration_present:
            d.write('I', 'duration')
        if flags & TrackFragmentRunBox.sample_size_present:
            d.write('I', 'size')
        if flags & TrackFragmentRunBox.sample_flags_present:
            d.write('I', 'flags')
        if flags & TrackFragmentRunBox.sample_composition_time_offsets_present:
            if version:
                d.write('i', 'composition_time_offset')
            else:
                d.write('I', 'composition_time_offset')

    @override
    def _to_json(self, exclude: AbstractSet) -> JsonObject:
        rv = super()._to_json(exclude)
        if '_type' in rv:
            rv['_type'] = MODULE_PREFIX_RE.sub(r'\g<box_name>', rv['_type'])
        return rv


class TrackFragmentRunBox(FullBox):
    ATOM_FOURCC = 'trun'
    data_offset_present: ClassVar[int] = 0x000001
    first_sample_flags_present: ClassVar[int] = 0x000004  # overrides default flags for the first sample only
    sample_duration_present: ClassVar[int] = 0x000100  # sample has its own duration?
    sample_size_present: ClassVar[int] = 0x000200  # sample has its own size
    sample_flags_present: ClassVar[int] = 0x000400  # sample has its own flags
    sample_composition_time_offsets_present: ClassVar[int] = 0x000800  # sample has a composition time offset

    samples: list[TrackSample]

    OBJECT_FIELDS = {
        'samples': ListOf(TrackSample),
        **FullBox.OBJECT_FIELDS,
    }

    def parse_samples(self, src: BinaryIO, nal_length_field_length: int) -> None:
        tfhd: Mp4Atom | None = self.find_peer("tfhd")
        assert tfhd is not None, "Failed to find tfhd box for trun box"
        for sample in self.samples:
            pos = sample.offset + tfhd.base_data_offset
            end = pos + sample.size
            sample.nals = []
            while pos < end:
                src.seek(pos)
                nal = Nal(src, nal_length_field_length)
                pos += nal.size + nal_length_field_length
                sample.nals.append(nal)

    @override
    def encode_box_fields(self, dest: BinaryIO) -> None:
        pos = self.position + self.header_size + FullBox.FB_HEADER_SIZE
        assert pos == dest.tell()
        self.output_box_fields(dest)
        for sample in self.samples:
            self.options.log.debug(f"Encoding sample {sample.index} at offset {dest.tell()} with size {sample.size}")
            sample.encode(dest, self.version, self.flags)

    def output_box_fields(self, dest: BinaryIO) -> None:
        w = FieldWriter(self, dest)
        self.sample_count = len(self.samples)
        self.options.log.debug(f"Encoding trun box with {self.sample_count} samples")
        w.write('I', 'sample_count')
        if self.flags & self.data_offset_present:
            w.write('I', 'data_offset')
        if self.flags & self.first_sample_flags_present:
            w.write('I', 'first_sample_flags')

    def post_encode(self, dest: BinaryIO) -> None:
        moof = self.find_atom(
            'moof', check_parent=True, recurse_children=False,
            no_exception=True)
        if moof is None:
            self.options.log.info('%s: Failed to find moof box', self._fullname)
            return
        mdat = moof.find_peer('mdat')
        if mdat is None:
            self.options.log.info('%s: Failed to find mdat box', self._fullname)
            return
        mdat_sample_start = moof.position + moof.size + mdat.header_size

        tfhd: TrackFragmentHeaderBox = moof['traf.tfhd']
        first_sample_pos: int = tfhd.base_data_offset
        if (self.flags & self.data_offset_present) != 0:
            first_sample_pos += self.data_offset
        if first_sample_pos != mdat_sample_start:
            self.options.log.debug(
                'rewriting trun data_offset from %d to %d',
                self.data_offset,
                mdat_sample_start - tfhd.base_data_offset)
            self.data_offset = mdat_sample_start - tfhd.base_data_offset
            assert self.data_offset >= 0
            cur = dest.tell()
            if (self.flags & self.data_offset_present) == 0:
                self.flags |= self.data_offset_present
                dest.seek(self.position + self.header_size)
                self.encode_fields(dest)
            else:
                pos: int = self.position + self.header_size + FullBox.FB_HEADER_SIZE
                dest.seek(pos)
                self.output_box_fields(dest)
            dest.seek(cur)


class TrackFragmentRunBoxFactory(FullBoxFactory[TrackFragmentRunBox]):
    def atom_type(self) -> type[TrackFragmentRunBox]:
        return TrackFragmentRunBox

    @override
    def depends_upon(self):
        return {'moof', 'traf', 'mdat', 'tfhd'}

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        tfhd: TrackFragmentHeaderBox = cast(TrackFragmentHeaderBox, parent.get('tfhd'))
        sample_count = struct.unpack('>I', src.read(4))[0]
        rv["sample_count"] = sample_count
        if rv["flags"] & TrackFragmentRunBox.data_offset_present:
            rv["data_offset"] = struct.unpack('>i', src.read(4))[0]
        else:
            rv["data_offset"] = 0
        if rv["flags"] & TrackFragmentRunBox.first_sample_flags_present:
            rv["first_sample_flags"] = struct.unpack('>I', src.read(4))[0]
        else:
            rv["first_sample_flags"] = 0
        rv["samples"] = []
        offset: int = rv["data_offset"]
        samples: list[TrackSample] = []
        for i in range(sample_count):
            ts = TrackSample.parse(src, i, offset, rv, tfhd)
            ts = TrackSample(**ts)
            samples.append(ts)
            offset += ts.size
        rv["samples"] = samples
        return rv
