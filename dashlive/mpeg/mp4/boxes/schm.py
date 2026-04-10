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
from ..options import Options

from .full import FullBox, FullBoxFactory

class ProtectionSchemeTypeBox(FullBox):
    ATOM_FOURCC = 'schm'

    def encode_fields(self, dest):
        if self.scheme_uri is not None:
            self.flags |= 0x000001
        return super().encode_fields(dest)

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('S4', "scheme_type")
        w.write('I', "scheme_version")
        if self.scheme_uri is not None:
            w.write('S0', "scheme_uri")


class ProtectionSchemeTypeBoxFactory(FullBoxFactory[ProtectionSchemeTypeBox]):
    def atom_type(self) -> type[ProtectionSchemeTypeBox]:
        return ProtectionSchemeTypeBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.read('S4', 'scheme_type')
        r.read('I', 'scheme_version')
        if rv['flags'] & 0x000001:
            r.read('S0', 'scheme_uri')
        else:
            rv['scheme_uri'] = None
        return rv
