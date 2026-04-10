#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO, cast

from dashlive.utils.fio import FieldReader, FieldWriter
from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from ..atom import Mp4Atom
from ..atom_factory import AtomFactory
from ..options import Options


class FontRecord(ObjectWithFields):
    font_id: int
    font: str

    @classmethod
    def parse(cls, src: BinaryIO, parent: dict[str, Any]) -> dict[str, Any]:
        offset: int = src.tell() - parent['position']
        rv: dict[str, Any] = {
            "offset": offset,
        }
        r: FieldReader = FieldReader(cls.classname(), src, rv)
        r.read('H', 'font_id')
        name_len: int = cast(int, r.get('B', 'font-name-length'))
        r.read(f'S{name_len}', 'font')
        rv['size'] = 3 + name_len
        return rv

    def encode(self, dest: BinaryIO) -> BinaryIO:
        w = FieldWriter(self, dest)
        w.write('H', 'font_id')
        w.write('B', 'font-name-length', value=len(self.font))
        w.write('S', 'font')
        return dest


class FontTableBox(Mp4Atom):
    ATOM_FOURCC = 'ftab'
    OBJECT_FIELDS = {
        "font_table": ListOf(FontRecord),
    }
    font_table: list[FontRecord]

    def encode_fields(self, dest: BinaryIO) -> None:
        d: FieldWriter = FieldWriter(self, dest)
        d.write('H', 'entry-count', value=len(self.font_table))
        for font in self.font_table:
            font.encode(dest)


class FontTableBoxFactory(AtomFactory[FontTableBox]):
    def atom_type(self) -> type[FontTableBox]:
        return FontTableBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv: dict[str, Any] | None = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r: FieldReader = FieldReader(self.classname(), src, rv, debug=options.debug)
        entry_count: int = cast(int, r.get('H', 'entry-count'))
        rv['font_table'] = []
        for _idx in range(entry_count):
            rv['font_table'].append(FontRecord.parse(src, rv))
        return rv
