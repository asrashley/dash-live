#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO

from dashlive.utils.fio import FieldReader, FieldWriter

from ..atom import Mp4Atom
from ..options import Options

from .full import FullBox, FullBoxFactory

class TrackExtendsBox(FullBox):
    ATOM_FOURCC = 'trex'

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'track_id')
        w.write('I', 'default_sample_description_index')
        w.write('I', 'default_sample_duration')
        w.write('I', 'default_sample_size')
        w.write('I', 'default_sample_flags')


class TrackExtendsBoxFactory(FullBoxFactory[TrackExtendsBox]):
    def atom_type(self) -> type[TrackExtendsBox]:
        return TrackExtendsBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.read('I', "track_id")
        r.read('I', "default_sample_description_index")
        r.read('I', "default_sample_duration")
        r.read('I', "default_sample_size")
        r.read('I', "default_sample_flags")
        return rv
