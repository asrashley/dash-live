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

from ..atom import Mp4Atom
from ..atom_factory import AtomFactory
from ..options import Options


class FileTypeBox(Mp4Atom):
    ATOM_FOURCC = 'ftyp'
    OBJECT_FIELDS = {
        "compatible_brands": ListOf(str),
    }
    compatible_brands: list[str]
    major_brand: str
    minor_version: int

    def encode_fields(self, dest: BinaryIO) -> None:
        d = FieldWriter(self, dest)
        d.write(4, 'major_brand')
        d.write('I', 'minor_version')
        for cb in self.compatible_brands:
            d.write(4, 'compatible_brand', value=bytes(cb, 'ascii'))


class FileTypeBoxFactory(AtomFactory[FileTypeBox]):
    def atom_type(self) -> type[FileTypeBox]:
        return FileTypeBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        r = FieldReader("FileTypeBox", src, rv)
        rv['major_brand'] = str(r.get(4, 'major_brand'), 'ascii')
        r.read('I', 'minor_version')
        size = rv["size"] - rv["header_size"] - 8
        rv['compatible_brands'] = []
        while size > 3:
            cb: bytes = cast(bytes, r.get(4, 'compatible_brand'))
            if len(cb) != 4:
                break
            rv['compatible_brands'].append(str(cb, 'ascii'))
            size -= 4
        return rv
