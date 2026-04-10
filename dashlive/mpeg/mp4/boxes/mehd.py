#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import struct
from typing import Any, BinaryIO

from dashlive.utils.fio import FieldWriter

from ..atom import Mp4Atom
from ..options import Options

from .full import FullBox, FullBoxFactory


class MovieExtendsHeaderBox(FullBox):
    ATOM_FOURCC = 'mehd'

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        if self.version == 1:
            w.write('Q', 'fragment_duration')
        else:
            w.write('I', 'fragment_duration')


class MovieExtendsHeaderBoxFactory(FullBoxFactory[MovieExtendsHeaderBox]):
    def atom_type(self) -> type[MovieExtendsHeaderBox]:
        return MovieExtendsHeaderBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        if rv["version"] == 1:
            rv["fragment_duration"] = struct.unpack('>Q', src.read(8))[0]
        else:
            rv["fragment_duration"] = struct.unpack('>I', src.read(4))[0]
        return rv
