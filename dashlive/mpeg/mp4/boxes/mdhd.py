#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import struct
from typing import Any, BinaryIO

from dashlive.utils.date_time import DateTimeField, from_iso_epoch, to_iso_epoch
from dashlive.utils.fio import FieldWriter

from ..atom import Mp4Atom
from ..options import Options

from .full import FullBox, FullBoxFactory

class MediaHeaderBox(FullBox):
    ATOM_FOURCC = 'mdhd'
    OBJECT_FIELDS = {
        "creation_time": DateTimeField,
        "modification_time": DateTimeField,
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        if self.version == 1:
            sz = 'Q'
        else:
            sz = 'I'
        w.write(sz, 'creation_time', value=to_iso_epoch(self.creation_time))
        w.write(sz, 'modification_time', value=to_iso_epoch(self.modification_time))
        w.write('I', 'timescale')
        w.write(sz, 'duration')
        chars: list[int] = [ord(c) - 0x60 for c in list(self.language)] + [0, 0, 0]
        lang: int = (chars[0] << 10) + (chars[1] << 5) + chars[2]
        w.write('H', 'lang', value=lang)
        w.write('H', 'pre_defined', value=0)


class MediaHeaderBoxFactory(FullBoxFactory[MediaHeaderBox]):
    def atom_type(self) -> type[MediaHeaderBox]:
        return MediaHeaderBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        if rv["version"] == 1:
            rv["creation_time"] = struct.unpack('>Q', src.read(8))[0]
            rv["modification_time"] = struct.unpack('>Q', src.read(8))[0]
            rv["timescale"] = struct.unpack('>I', src.read(4))[0]
            rv["duration"] = struct.unpack('>Q', src.read(8))[0]
        else:
            rv["creation_time"] = struct.unpack('>I', src.read(4))[0]
            rv["modification_time"] = struct.unpack('>I', src.read(4))[0]
            rv["timescale"] = struct.unpack('>I', src.read(4))[0]
            rv["duration"] = struct.unpack('>I', src.read(4))[0]
        rv["creation_time"] = from_iso_epoch(rv["creation_time"])
        rv["modification_time"] = from_iso_epoch(rv["modification_time"])
        tmp = struct.unpack('>H', src.read(2))[0]
        rv["language"] = ''.join([
            chr(0x60 + ((tmp >> 10) & 0x1F)),
            chr(0x60 + ((tmp >> 5) & 0x1F)),
            chr(0x60 + (tmp & 0x1F))
        ])
        src.read(2)
        return rv
