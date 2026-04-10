#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO

from dashlive.utils.binary import Binary
from dashlive.utils.fio import FieldReader, FieldWriter

from ..atom import Mp4Atom
from .full import FullBox, FullBoxFactory
from ..options import Options


class EventMessageBox(FullBox):
    ATOM_FOURCC = 'emsg'
    OBJECT_FIELDS = {
        'data': Binary,
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def encode_box_fields(self, dest):
        d = FieldWriter(self, dest)
        if self.version == 0:
            d.write('S0', 'scheme_id_uri')
            d.write('S0', 'value')
            d.write('I', 'timescale')
            d.write('I', 'presentation_time_delta')
            d.write('I', 'event_duration')
            d.write('I', 'event_id')
        elif self.version == 1:
            d.write('I', 'timescale')
            d.write('Q', 'presentation_time')
            d.write('I', 'event_duration')
            d.write('I', 'event_id')
            d.write('S0', 'scheme_id_uri')
            d.write('S0', 'value')
        if self.data is not None:
            d.write(None, 'data')


class EventMessageBoxFactory(FullBoxFactory[EventMessageBox]):
    def atom_type(self) -> type[EventMessageBox]:
        return EventMessageBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        if rv['version'] == 0:
            r.read('S0', 'scheme_id_uri')
            r.read('S0', 'value')
            r.read('I', 'timescale')
            r.read('I', 'presentation_time_delta')
            r.read('I', 'event_duration')
            r.read('I', 'event_id')
        elif rv['version'] == 1:
            r.read('I', 'timescale')
            r.read('Q', 'presentation_time')
            r.read('I', 'event_duration')
            r.read('I', 'event_id')
            r.read('S0', 'scheme_id_uri')
            r.read('S0', 'value')
        rv["data"] = None
        end = rv["position"] + rv["size"]
        if src.tell() < end:
            r.read(end - src.tell(), 'data')
        return rv
