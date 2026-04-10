#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO, ClassVar

from dashlive.utils.binary import HexBinary
from dashlive.utils.fio import FieldReader, FieldWriter
from dashlive.utils.object_with_fields import ObjectWithFields

from ..atom import Mp4Atom
from ..options import Options

from .sample_entry import SampleEntry, SampleEntryFactory

class BoxRecord(ObjectWithFields):
    @classmethod
    def parse(cls, src: BinaryIO, parent: dict[str, Any]) -> dict[str, Any]:
        rv: dict[str, Any] = {
            "offset": src.tell() - parent['position'],
            "size": 8,
        }
        r: FieldReader = FieldReader(cls.classname(), src, rv)
        r.read('H', 'top')
        r.read('H', 'left')
        r.read('H', 'bottom')
        r.read('H', 'right')
        return rv

    def encode(self, dest: BinaryIO) -> BinaryIO:
        w: FieldWriter = FieldWriter(self, dest)
        w.write('H', 'top')
        w.write('H', 'left')
        w.write('H', 'bottom')
        w.write('H', 'right')
        return dest


class StyleRecord(ObjectWithFields):
    @classmethod
    def parse(cls, src: BinaryIO, parent: dict[str, Any]) -> dict[str, Any]:
        rv: dict[str, Any] = {
            "offset": src.tell() - parent['position'],
            "size": 8,
        }
        r: FieldReader = FieldReader(cls.classname(), src, rv)
        r.read('H', 'start_char')
        r.read('H', 'end_char')
        r.read('H', 'font_id')
        r.read('B', 'face_style_flags')
        r.read('B', 'font_size')
        r.read(4, 'text_colour')
        return rv

    def encode(self, dest: BinaryIO) -> BinaryIO:
        w: FieldWriter = FieldWriter(self, dest)
        w.write('H', 'start_char')
        w.write('H', 'end_char')
        w.write('H', 'font_id')
        w.write('B', 'face_style_flags')
        w.write('B', 'font_size')
        w.write(4, 'text_colour')
        return dest


class TextSampleEntry(SampleEntry):
    ATOM_FOURCC = 'tx3g'
    OBJECT_FIELDS: ClassVar[dict[str, Any]] = {
        "default_text_box": BoxRecord,
        "default_style": StyleRecord,
        "background_colour": HexBinary,
    }
    default_text_box: BoxRecord
    default_style: StyleRecord
    display_flags: int
    horizontal_justification: int
    vertical_justification: int
    background_colour: HexBinary

    def encode_fields(self, dest: BinaryIO) -> None:
        super().encode_fields(dest)
        w: FieldWriter = FieldWriter(self, dest)
        w.write('I', 'display_flags')
        w.write('B', 'horizontal_justification')  # should be signed 8 bit
        w.write('B', 'vertical_justification')  # should be signed 8 bit
        w.write(4, 'background_colour')
        self.default_text_box.encode(dest)
        self.default_style.encode(dest)


class TextSampleEntryFactory(SampleEntryFactory[TextSampleEntry]):
    parse_children = True

    def atom_type(self) -> type[TextSampleEntry]:
        return TextSampleEntry

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        r: FieldReader = FieldReader(self.classname(), src, rv, debug=options.debug)
        r.read('I', 'display_flags')
        r.read('B', 'horizontal_justification')  # should be signed 8 bit
        r.read('B', 'vertical_justification')  # should be signed 8 bit
        r.read(4, 'background_colour')
        rv['default_text_box'] = BoxRecord.parse(r.src, rv)
        rv['default_style'] = StyleRecord.parse(r.src, rv)
        return rv
