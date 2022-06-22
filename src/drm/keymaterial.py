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
import re


class KeyMaterial(object):
    length = 16

    def __init__(self, value=None, hex=None, b64=None, raw=None):
        if value is not None:
            if len(value) == 16:
                self.raw = value
            elif re.match(r'^(0x)?[0-9a-f-]+$', value, re.IGNORECASE):
                if value.startswith('0x'):
                    value = value[2:]
                self.raw = binascii.unhexlify(value.replace('-', ''))
            else:
                self.raw = base64.b64decode(value)
        elif raw is not None:
            self.raw = raw
        elif hex is not None:
            self.raw = binascii.unhexlify(hex.replace('-', ''))
        elif b64 is not None:
            self.raw = binascii.a2b_base64(b64)
        else:
            raise ValueError("One of value, hex, b64 or raw must be provided")
        if len(self.raw) != self.length:
            raise ValueError("Size {} is invalid".format(len(self.raw)))

    def to_hex(self):
        return binascii.b2a_hex(self.raw)

    def from_hex(self, value):
        self.raw = value.replace('-', '').decode('hex')

    hex = property(to_hex, from_hex)

    def to_base64(self):
        return base64.b64encode(self.raw)

    def from_base64(self, value):
        self.raw = base64.b64decode(value)

    b64 = property(to_base64, from_base64)

    def __len__(self):
        return self.length
