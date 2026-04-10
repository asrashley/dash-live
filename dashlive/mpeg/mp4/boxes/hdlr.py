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


class HandlerBox(FullBox):
    ATOM_FOURCC = 'hdlr'

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'pre_defined', value=0)
        w.write('S4', 'handler_type')
        w.write(None, 'reserved', value=(b'\0' * 12))  # reserved = 0
        w.write('S0', 'name')


class HandlerBoxFactory(FullBoxFactory[HandlerBox]):
    def atom_type(self) -> type[HandlerBox]:
        return HandlerBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        src.read(4)
        rv["handler_type"] = str(src.read(4), 'utf-8')
        src.read(12)
        name_len = rv["position"] + rv["size"] - src.tell()
        name_bytes = src.read(name_len)
        while name_len and name_bytes[-1] == 0:
            name_bytes = name_bytes[:-1]
            name_len -= 1
        rv["name"] = str(name_bytes, 'utf-8')
        return rv
