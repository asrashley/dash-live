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
from ..options import Options

from .full import FullBox, FullBoxFactory

class TrackFragmentDecodeTimeBox(FullBox):
    ATOM_FOURCC = 'tfdt'
    base_media_decode_time: int

    def __setattr__(self, name: str, value: Any) -> None:
        if name == 'base_media_decode_time':
            if self.version == 0 and value.bit_length() > 32:
                object.__setattr__(self, 'version', 1)
                self.update_size(4)
        elif name == 'version':
            if value == 0 and self.base_media_decode_time.bit_length() > 32:
                raise ValueError(
                    'base media decode time is too large to use version 0 header')
        super().__setattr__(name, value)

    def encode_box_fields(self, dest: BinaryIO) -> None:
        assert self.base_media_decode_time >= 0
        d = FieldWriter(self, dest)
        if self.version == 1:
            d.write('Q', 'base_media_decode_time')
        else:
            assert self.base_media_decode_time < (2 << 32)
            d.write('I', 'base_media_decode_time')


class TrackFragmentDecodeTimeBoxFactory(FullBoxFactory[TrackFragmentDecodeTimeBox]):
    def atom_type(self) -> type[TrackFragmentDecodeTimeBox]:
        return TrackFragmentDecodeTimeBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        if rv["version"] == 1:
            rv["base_media_decode_time"] = struct.unpack('>Q', src.read(8))[0]
        else:
            rv["base_media_decode_time"] = struct.unpack('>I', src.read(4))[0]
        return rv
