#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO

from dashlive.utils.fio import BitsFieldReader, FieldReader, FieldWriter
from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from ..atom import Mp4Atom
from ..options import Options

from .full import FullBox, FullBoxFactory


class SegmentReference(ObjectWithFields):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            assert "src" != key
            if key not in self.__dict__:
                setattr(self, key, value)

    @classmethod
    def parse(cls, src, parent, **kwargs):
        rv = {}
        r = BitsFieldReader(cls.classname(), src, rv, size=12)
        r.read(1, 'ref_type')
        r.read(31, 'ref_size')
        r.read(32, 'duration')
        r.read(1, 'starts_with_SAP')
        r.read(3, 'SAP_type')
        r.read(28, 'SAP_delta_time')
        return rv

    def _to_json(self, exclude):
        fields = {
            '_type': self.classname()
        }
        if exclude is None:
            exclude = set()
        exclude.add('parent')
        for k, v in self.__dict__.items():
            if k not in exclude:
                fields[k] = v
        return fields

    def encode(self, dest):
        w = FieldWriter(self, dest)
        w.writebits(1, 'ref_type')
        w.writebits(31, 'ref_size')
        w.writebits(32, 'duration')
        w.writebits(1, 'starts_with_SAP')
        w.writebits(3, 'SAP_type')
        w.writebits(28, 'SAP_delta_time')
        w.done()


class SegmentIndexBox(FullBox):
    ATOM_FOURCC = 'sidx'
    OBJECT_FIELDS = {
        'references': ListOf(SegmentReference),
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'reference_id')
        w.write('I', 'timescale')
        sz = 'I' if self.version == 0 else 'Q'
        w.write(sz, 'earliest_presentation_time')
        w.write(sz, 'first_offset')
        w.write('H', 'reserved', 0)
        w.write('H', 'reference_count', len(self.references))
        for segment_ref in self.references:
            segment_ref.encode(w)


class SegmentIndexBoxFactory(FullBoxFactory[SegmentIndexBox]):
    def atom_type(self) -> type[SegmentIndexBox]:
        return SegmentIndexBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.read('I', 'reference_id')
        r.read('I', 'timescale')
        sz = 'I' if rv['version'] == 0 else 'Q'
        r.read(sz, 'earliest_presentation_time')
        r.read(sz, 'first_offset')
        r.skip(2)
        ref_count = r.get('H', 'reference_count')
        rv["references"] = []
        for _ in range(ref_count):
            rv["references"].append(
                SegmentReference(**SegmentReference.parse(src, parent)))
        return rv
