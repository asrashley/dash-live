#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO

from dashlive.utils.date_time import DateTimeField, from_iso_epoch, to_iso_epoch
from dashlive.utils.fio import FieldReader, FieldWriter
from dashlive.utils.list_of import ListOf

from .full import FullBox, FullBoxFactory
from ..atom import Mp4Atom
from ..options import Options


class TrackHeaderBox(FullBox):
    ATOM_FOURCC = 'tkhd'
    Track_enabled = 0x000001
    Track_in_movie = 0x000002
    Track_in_preview = 0x000004
    Track_size_is_aspect_ratio = 0x000008

    OBJECT_FIELDS = {
        "creation_time": DateTimeField,
        "modification_time": DateTimeField,
        "matrix": ListOf(int),
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def encode_fields(self, dest):
        self.flags = 0
        if self.is_enabled:
            self.flags |= self.Track_enabled
        if self.in_movie:
            self.flags |= self.Track_in_movie
        if self.in_preview:
            self.flags |= self.Track_in_preview
        if self.size_is_aspect_ratio:
            self.flags |= self.Track_size_is_aspect_ratio
        super().encode_fields(dest)

    def encode_box_fields(self, dest):
        d = FieldWriter(self, dest)
        if self.version == 1:
            sz = 'Q'
        else:
            sz = 'I'
        d.write(sz, 'creation_time', to_iso_epoch(self.creation_time))
        d.write(sz, 'modification_time', to_iso_epoch(self.modification_time))
        d.write('I', 'track_id')
        d.write(4, 'reserved', b'\0' * 4)  # reserved
        d.write(sz, 'duration')
        d.write(8, 'reserved', b'\0' * 8)  # reserved
        d.write('H', 'layer')
        d.write('H', 'alternate_group')
        d.write('D8.8', 'volume')  # int(self.volume * 256.0))
        d.write(2, 'reserved', b'\0' * 2)  # reserved
        for m in self.matrix:
            d.write('I', 'matrix', m)
        d.write('D16.16', 'width')  # long(self.width * 65536.0))
        d.write('D16.16', 'height')  # long(self.height * 65536.0))


class TrackHeaderBoxFactory(FullBoxFactory[TrackHeaderBox]):
    def atom_type(self) -> type[TrackHeaderBox]:
        return TrackHeaderBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        rv["is_enabled"] = (rv["flags"] & TrackHeaderBox.Track_enabled) == TrackHeaderBox.Track_enabled
        rv["in_movie"] = (rv["flags"] & TrackHeaderBox.Track_in_movie) == TrackHeaderBox.Track_in_movie
        rv["in_preview"] = (rv["flags"] & TrackHeaderBox.Track_in_preview) == TrackHeaderBox.Track_in_preview
        rv["size_is_aspect_ratio"] = (
            (rv["flags"] & TrackHeaderBox.Track_size_is_aspect_ratio) == TrackHeaderBox.Track_size_is_aspect_ratio)
        sz = 'Q' if rv["version"] == 1 else 'I'
        r.read(sz, "creation_time")
        r.read(sz, "modification_time")
        r.read('I', "track_id")
        r.skip(4)  # reserved
        r.read(sz, "duration")
        rv["creation_time"] = from_iso_epoch(rv["creation_time"])
        rv["modification_time"] = from_iso_epoch(rv["modification_time"])
        r.get(8, 'reserved')  # 2 x 32 bits reserved
        r.read('H', "layer")
        r.read('H', "alternate_group")
        rv["volume"] = r.get('D8.8', 'volume')  # value is fixed point 8.8
        r.get(2, 'reserved')  # reserved
        rv["matrix"] = []
        for _ in range(9):
            rv["matrix"].append(r.get('I', 'matrix'))
        rv["width"] = r.get('D16.16', 'width')
        rv["height"] = r.get('D16.16', 'height')
        return rv
