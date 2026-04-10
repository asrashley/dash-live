#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from datetime import datetime
from typing import Any, BinaryIO

from dashlive.utils.date_time import DateTimeField, from_iso_epoch, to_iso_epoch
from dashlive.utils.fio import FieldReader, FieldWriter
from dashlive.utils.list_of import ListOf

from .full import FullBox, FullBoxFactory
from ..atom import Mp4Atom
from ..options import Options


class MovieHeaderBox(FullBox):
    ATOM_FOURCC = 'mvhd'
    OBJECT_FIELDS = {
        "creation_time": DateTimeField,
        "modification_time": DateTimeField,
        "matrix": ListOf(int),
    }
    duration: int
    creation_time: datetime
    modification_time: datetime
    rate: float
    volume: float
    timescale: int
    matrix: list[int]
    next_track_id: int

    def __setattr__(self, name, value):
        if name == 'duration':
            if self.version == 0 and self.duration.bit_length() > 32:
                self.version = 1
                self.update_size(4)
        elif name == 'version':
            if value == 0 and self.duration.bit_length() > 32:
                raise ValueError('Duration is too large to use version 0 header')
        super().__setattr__(name, value)

    def encode_box_fields(self, dest):
        d = FieldWriter(self, dest)
        if self.version == 1:
            sz = 'Q'
        else:
            sz = 'I'
        d.write(sz, 'creation_time',
                value=to_iso_epoch(self.creation_time))
        d.write(sz, 'modification_time',
                value=to_iso_epoch(self.modification_time))
        d.write('I', 'timescale')
        d.write(sz, 'duration')
        d.write('D16.16', 'rate')
        d.write('D8.8', 'volume')
        d.write(10, 'reserved', value=(b'\0' * 10))  # reserved
        for value in self.matrix:
            d.write('I', 'matrix', value=value)
        d.write(6 * 4, 'reserved', value=(b'\0' * 6 * 4))  # reserved
        d.write('I', 'next_track_id')


class MovieHeaderBoxFactory(FullBoxFactory[MovieHeaderBox]):
    def atom_type(self) -> type[MovieHeaderBox]:
        return MovieHeaderBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv, debug=options.debug)
        if rv['version'] == 1:
            sz = 'Q'
        else:
            sz = 'I'
        r.read(sz, 'creation_time')
        r.read(sz, 'modification_time')
        r.read('I', 'timescale')
        r.read(sz, 'duration')
        rv["creation_time"] = from_iso_epoch(rv["creation_time"])
        rv["modification_time"] = from_iso_epoch(rv["modification_time"])
        r.read('D16.16', 'rate')
        r.read('D8.8', 'volume')
        r.skip(10)  # reserved
        rv["matrix"] = []
        for _i in range(9):
            rv["matrix"].append(r.get('I', 'matrix'))
        r.skip(6 * 4)  # pre_defined = 0
        r.read('I', 'next_track_id')
        return rv
