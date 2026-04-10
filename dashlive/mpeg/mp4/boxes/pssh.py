#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import binascii
import re
from typing import Any, BinaryIO

from dashlive.utils.binary import Binary, HexBinary
from dashlive.utils.fio import FieldReader, FieldWriter
from dashlive.utils.list_of import ListOf

from ..atom import Mp4Atom
from ..options import Options

from .full import FullBox, FullBoxFactory

class ContentProtectionSpecificBox(FullBox):
    ATOM_FOURCC = 'pssh'
    OBJECT_FIELDS = {
        "data": Binary,
        "key_ids": ListOf(HexBinary),
        "system_id": HexBinary,
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.system_id = self._fixup_binary_field(self.system_id)
        kids = []
        for kid in self.key_ids:
            kids.append(self._fixup_binary_field(kid))
        self.key_ids = kids
        if self.data and not isinstance(self.data, Binary):
            self.data = Binary(self.data, encoding=Binary.BASE64)

    @staticmethod
    def _fixup_binary_field(value: Binary | str | bytes) -> Binary:
        if value is None:
            return None
        if isinstance(value, Binary):
            return value
        if len(value) != 16:
            if re.match(r'^(0x)?[0-9a-f-]+$', value, re.IGNORECASE):
                if value.startswith('0x'):
                    value = value[2:]
                value = binascii.unhexlify(value.replace('-', ''))
        if len(value) != 16:
            raise ValueError(fr"Invalid length: {len(value)}")
        return HexBinary(value, encoding=Binary.HEX)

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write(16, 'system_id')
        if self.version > 0:
            w.write('I', 'num_keys', len(self.key_ids))
            for kid in self.key_ids:
                w.write(16, 'kid', kid)
        if self.data is None:
            w.write('I', 'data_len', 0)
        else:
            w.write('I', 'data_len', len(self.data))
            w.write(None, 'data')


class ContentProtectionSpecificBoxFactory(FullBoxFactory[ContentProtectionSpecificBox]):
    def atom_type(self) -> type[ContentProtectionSpecificBox]:
        return ContentProtectionSpecificBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.read(16, "system_id")
        rv["key_ids"] = []
        if rv["version"] > 0:
            kid_count = r.get('I', 'kid_count')
            for _ in range(kid_count):
                rv["key_ids"].append(r.read(16, 'kid'))
        data_size = r.get('I', 'data_size')
        if data_size > 0:
            r.read(data_size, "data")
        else:
            rv["data"] = None
        return rv
