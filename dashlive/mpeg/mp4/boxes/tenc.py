#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO

from dashlive.utils.binary import HexBinary
from dashlive.utils.fio import FieldReader, FieldWriter

from ..atom import Mp4Atom
from ..options import Options

from .full import FullBox, FullBoxFactory

class TrackEncryptionBox(FullBox):
    ATOM_FOURCC = 'tenc'
    OBJECT_FIELDS = {
        "default_kid": HexBinary,
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('3I', "is_encrypted")
        w.write('B', "iv_size")
        w.write(16, "default_kid")


class TrackEncryptionBoxFactory(FullBoxFactory[TrackEncryptionBox]):
    def atom_type(self) -> type[TrackEncryptionBox]:
        return TrackEncryptionBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.read('3I', "is_encrypted")
        r.read('B', "iv_size")
        r.read(16, "default_kid")
        return rv
