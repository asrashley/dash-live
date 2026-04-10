#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO

from ..atom import Mp4Atom
from ..atom_factory import AtomFactory
from ..options import Options


class OriginalFormatBox(Mp4Atom):
    ATOM_FOURCC = 'frma'
    data_format: str

    def encode_fields(self, dest):
        dest.write(bytes(self.data_format, 'ascii'))


class OriginalFormatBoxFactory(AtomFactory[OriginalFormatBox]):
    def atom_type(self) -> type[OriginalFormatBox]:
        return OriginalFormatBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        rv["data_format"] = str(src.read(4), 'ascii')
        return rv
