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

import decimal
import logging
import struct

from .sizes import format_bit_sizes

class FieldReader(object):
    def __init__(self, name, src, kwargs, debug=False):
        self.name = name
        self.src = src
        self.kwargs = kwargs
        if debug:
            self.log = logging.getLogger('bitio')
        else:
            self.log = None

    def read(self, size, field, mask=None):
        self.kwargs[field] = self.get(size, field, mask)

    def get(self, size, field, mask=None):
        if isinstance(size, (int, long)):
            value = self.src.read(size)
            if self.log and self.log.isEnabledFor(logging.DEBUG):
                self.log.debug('%s: read %s size=%d pos=%d value=0x%s', self.name, field,
                               size, self.src.tell(), value.encode('hex'))
            return value
        if size == 'B':
            value = ord(self.src.read(1))
        elif size == 'H':
            d = self.src.read(2)
            value = (ord(d[0]) << 8) + ord(d[1])
        elif size == 'I':
            d = self.src.read(4)
            value = (ord(d[0]) << 24) + (ord(d[1]) << 16) + (ord(d[2]) << 8) + ord(d[3])
        elif size == 'Q':
            value = struct.unpack('>Q', self.src.read(8))[0]
        elif size == '0I':
            d = self.src.read(3)
            value = (ord(d[0]) << 16) + (ord(d[1]) << 8) + ord(d[2])
        elif size == 'S0':
            value = ''
            d = self.src.read(1)
            while ord(d) != 0:
                value += d
                d = self.src.read(1)
            if self.log and self.log.isEnabledFor(logging.DEBUG):
                self.log.debug('%s: read %s size=%d pos=%d value="%s"',
                               self.name, field,
                               len(value), self.src.tell(), value)
            return value
        elif size[0] == 'S':
            value = self.src.read(int(size[1:]))
            value = value.split('\0')[0]
        elif size[0] == 'D':
            bsz, asz = map(int, size[1:].split('.'))
            shift = 1 << asz
            value = decimal.Decimal(
                self.get(format_bit_sizes[bsz + asz], field)) / shift
        else:
            raise ValueError("unsupported size: " + size)
        if mask is not None:
            value &= mask
        if self.log:
            self.log.debug(
                '%s: read %s size=%s pos=%d value=0x%x',
                self.name, field,
                str(size), self.src.tell(), value)
        return value

    def skip(self, size):
        self.get(size, 'skip')
