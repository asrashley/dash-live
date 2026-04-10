import struct
from typing import Any, BinaryIO

from dashlive.utils.fio.field_reader import FieldReader

from ..atom import Mp4Atom
from ..options import Options

from .sample_entry import SampleEntry, SampleEntryFactory

class VisualSampleEntry(SampleEntry):
    version: int
    revision: int
    vendor: int
    temporal_quality: int
    spatial_quality: int
    width: int
    height: int
    compressorname: str
    horizresolution: float
    vertresolution: float

    def encode_fields(self, dest: BinaryIO) -> None:
        super().encode_fields(dest)
        dest.write(struct.pack('>H', self.version))
        dest.write(struct.pack('>H', self.revision))
        dest.write(struct.pack('>I', self.vendor))
        dest.write(struct.pack('>I', self.temporal_quality))
        dest.write(struct.pack('>I', self.spatial_quality))
        dest.write(struct.pack('>H', self.width))
        dest.write(struct.pack('>H', self.height))
        dest.write(struct.pack('>I', int(self.horizresolution * 65536.0)))
        dest.write(struct.pack('>I', int(self.vertresolution * 65536.0)))
        dest.write(struct.pack('>I', self.entry_data_size))
        dest.write(struct.pack('>H', self.frame_count))
        c = self.compressorname + '\0' * 32
        dest.write(c[:32].encode('ascii'))
        dest.write(struct.pack('>H', self.bit_depth))
        dest.write(struct.pack('>H', self.colour_table))


class VisualSampleEntryFactory[T](SampleEntryFactory[T]):
    parse_children = True

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv, debug=options.debug)
        r.read('H', "version")
        r.read('H', "revision")
        r.read('I', "vendor")
        r.read('I', "temporal_quality")
        r.read('I', "spatial_quality")
        r.read('H', "width")
        r.read('H', "height")
        r.read('I', "horizresolution")
        rv["horizresolution"] /= 65536.0
        r.read('I', "vertresolution")
        rv["vertresolution"] /= 65536.0
        r.read('I', "entry_data_size")
        r.read('H', "frame_count")
        r.read('S32', "compressorname")
        r.read('H', "bit_depth")
        r.read('H', "colour_table")
        return rv
