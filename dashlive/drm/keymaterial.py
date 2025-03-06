#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import base64
import binascii
from collections.abc import Set
import re
from typing import ClassVar, NotRequired, Optional, TypedDict

class KeyMaterialJson(TypedDict):
    _type: NotRequired[str]
    hex: NotRequired[str]

class KeyMaterial:
    length: ClassVar[int] = 16

    raw: bytes

    def __init__(self,
                 value: bytes | str | None = None,
                 hex: Optional[str] = None,
                 b64: Optional[str] = None,
                 raw: Optional[bytes] = None) -> None:
        if value is not None:
            if isinstance(value, bytes) and len(value) == 16:
                self.raw = value
            else:
                if isinstance(value, bytes):
                    value = str(value, 'ascii')
                if re.match(r'^(0x)?[0-9a-f-]+$', value, re.IGNORECASE):
                    if value.startswith('0x'):
                        value = value[2:]
                    self.raw = binascii.unhexlify(value.replace('-', ''))
                else:
                    self.raw = base64.b64decode(value)
        elif raw is not None:
            self.raw = raw
        elif hex is not None:
            if hex.startswith('0x'):
                hex = hex[2:]
            self.raw = binascii.unhexlify(hex.replace('-', ''))
        elif b64 is not None:
            self.raw = binascii.a2b_base64(b64)
        else:
            raise ValueError("One of value, hex, b64 or raw must be provided")
        if len(self.raw) != self.__class__.length:
            raise ValueError(f"KeyMaterial size {len(self.raw)} is invalid")

    def to_hex(self) -> str:
        return str(binascii.b2a_hex(self.raw), 'ascii')

    def from_hex(self, value: str) -> None:
        self.raw = binascii.a2b_hex(value.replace('-', ''))

    hex = property(to_hex, from_hex)

    def to_base64(self) -> str:
        return str(base64.b64encode(self.raw), 'ascii')

    def from_base64(self, value: str) -> None:
        self.raw = base64.b64decode(value)

    b64 = property(to_base64, from_base64)

    def hex_to_le_guid(self, raw: bool) -> bytes | str:
        guid: str = self.hex
        if len(guid) != 32:
            raise ValueError("GUID should be 32 hex characters")
        dword: str = ''.join([guid[6:8], guid[4:6], guid[2:4], guid[0:2]])
        word1: str = ''.join([guid[10:12], guid[8:10]])
        word2: str = ''.join([guid[14:16], guid[12:14]])
        # looking at example streams, word 3 appears to be in big endian
        # format!
        word3: str = ''.join([guid[16:18], guid[18:20]])
        result: str = '-'.join([dword, word1, word2, word3, guid[20:]])
        assert len(result) == 36
        if raw is True:
            return binascii.a2b_hex(result.replace('-', ''))
        return result

    def toJSON(self, pure=True, exclude: Set[str] | None = None) -> KeyMaterialJson | str:
        if pure:
            return self.to_hex()
        rv: KeyMaterialJson = {}
        if exclude is None or '_type' not in exclude:
            rv['_type'] = KeyMaterial.__name__
        if exclude is None or 'hex' not in exclude:
            rv['hex'] = self.to_hex()
        return rv

    def __len__(self):
        return self.length
