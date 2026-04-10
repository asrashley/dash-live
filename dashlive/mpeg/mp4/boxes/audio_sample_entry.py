
import struct
from typing import Any, BinaryIO

from ..atom import Mp4Atom
from ..options import Options

from .sample_entry import SampleEntry, SampleEntryFactory

class AudioSampleEntry(SampleEntry):
    def encode_fields(self, dest: BinaryIO) -> None:
        super().encode_fields(dest)
        dest.write(b'\0' * 8)  # reserved
        dest.write(struct.pack('>H', self.channel_count))
        dest.write(struct.pack('>H', self.sample_size))
        dest.write(b'\0' * 4)  # reserved
        dest.write(struct.pack('>H', self.sampling_frequency))
        dest.write(b'\0' * 2)  # reserved


class AudioSampleEntryFactory[T](SampleEntryFactory[T]):
    parse_children = True

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        src.read(8)  # reserved
        rv["channel_count"] = struct.unpack('>H', src.read(2))[0]
        rv["sample_size"] = struct.unpack('>H', src.read(2))[0]
        src.read(4)  # reserved
        rv["sampling_frequency"] = struct.unpack('>H', src.read(2))[0]
        src.read(2)  # reserved
        return rv
