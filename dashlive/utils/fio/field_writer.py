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

import logging
import struct

import bitstring

from dashlive.utils.binary import Binary

from .sizes import format_bit_sizes

class FieldWriter:
    __slots__ = ['obj', 'dest', 'bits', 'log']

    def __init__(self, obj, dest, debug=False):
        self.obj = obj
        if isinstance(dest, FieldWriter):
            dest = dest.dest
        self.dest = dest
        self.bits = None
        if debug or getattr(self.obj, 'debug', False):
            self.log = logging.getLogger('fio')
        elif hasattr(self.obj, 'options') and getattr(self.obj.options, 'debug', False):
            self.log = logging.getLogger('fio')
        else:
            self.log = None

    def write(self, size, field, value=None):
        if value is None:
            value = getattr(self.obj, field)
        if isinstance(value, Binary):
            value = value.data
        if isinstance(size, str):
            if size == '3I':
                value = struct.pack('>I', value)[1:]
            elif size == 'S':
                value = bytes(value, 'utf-8')
            elif size == 'S0':
                value = bytes(value, 'utf-8') + b'\0'
            elif size[0] == 'S':
                leng = int(size[1:])
                value = bytes(value, 'utf-8')
                padding = leng - len(value)
                if padding > 0:
                    value += b'\0' * padding
            elif size[0] == 'D':
                bsz, asz = list(map(int, size[1:].split('.')))
                value = value * (1 << asz)
                fbs = format_bit_sizes[bsz + asz]
                value = struct.pack(f'>{fbs}', int(value))
            else:
                value = struct.pack(f'>{size}', value)
        elif isinstance(size, int):
            if isinstance(value, str):
                value = bytes(value, 'utf-8')
            padding = size - len(value)
            if padding > 0:
                value += b'\0' * padding
            elif padding < 0:
                value = value[:size]
        elif size is None and isinstance(value, str):
            value = bytes(value, 'utf-8')
        if self.log and self.log.isEnabledFor(logging.DEBUG):
            if isinstance(value, int):
                v = '0x' + hex(value)
            elif isinstance(value, str):
                v = '0x' + value.encode('hex')
            else:
                v = str(value)
            self.log.debug(
                '%s: Write %s size=%s (%d) pos=%d value=%s',
                self.obj.classname(), field, size, len(value),
                self.dest.tell(), v)
        return self.dest.write(value)

    def overwrite(self, position, size, field, value=None):
        if self.log:
            self.log.debug(
                '%s: overwrite %s size=%d pos=%d',
                self.obj.classname(), field, size, position)
        pos = self.dest.tell()
        self.dest.seek(position)
        self.write(size, field, value)
        self.dest.seek(pos)

    def writebits(self, size, field, value=None):
        if self.bits is None:
            self.bits = bitstring.BitArray()
        if value is None:
            value = getattr(self.obj, field)
        if isinstance(value, bool):
            value = 1 if value else 0
        if self.log:
            self.log.debug(
                '%s: WriteBits %s size=%d value=0x%x',
                self.obj.classname(), field, size,
                value)
        self.bits.append(bitstring.Bits(uint=value, length=size))

    def done(self):
        if self.bits is not None:
            self.dest.write(self.bits.bytes)
