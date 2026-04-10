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
from ..atom_factory import AtomFactory
from ..options import Options


class PixelAspectRatioBox(Mp4Atom):
    ATOM_FOURCC = 'pasp'
    h_spacing: int
    v_spacing: int

    def encode_fields(self, dest):
        d = FieldWriter(self, dest)
        d.write('I', 'h_spacing')
        d.write('I', 'v_spacing')


class PixelAspectRatioBoxFactory(AtomFactory[PixelAspectRatioBox]):
    def atom_type(self) -> type[PixelAspectRatioBox]:
        return PixelAspectRatioBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.read('I', 'h_spacing')
        r.read('I', 'v_spacing')
        return rv
