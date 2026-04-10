#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO

from dashlive.utils.fio import FieldWriter

from ..atom import Mp4Atom
from ..options import Options

from .full import FullBox, FullBoxFactory

class MimeBox(FullBox):
    ATOM_FOURCC = 'mime'
    content_type: str

    def encode_box_fields(self, dest):
        d = FieldWriter(self, dest, debug=self.options.debug)
        d.write('S0', 'content_type')


class MimeBoxFactory(FullBoxFactory[MimeBox]):
    def atom_type(self) -> type[MimeBox]:
        return MimeBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        rv['content_type'] = src.read(rv['size'] - rv['header_size'] - 4)
        while rv['content_type'][-1] == 0:
            rv['content_type'] = rv['content_type'][:-1]
        rv['content_type'] = str(rv['content_type'], 'ascii')
        return rv
