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
import os
import struct
import sys

try:
    import bitstring
except ImportError:
    sys.path.append(
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "lib")))
    import bitstring

from utils.binary import Binary

format_sizes = {
    'B': 1,
    'H': 2,
    'I': 4,
    'Q': 8,
}

format_bit_sizes = {
    8: 'B',
    16: 'H',
    32: 'I',
    64: 'Q',
}

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

class BitsFieldReader(object):
    def __init__(self, name, src, kwargs, size=None, data=None, debug=False):
        self.name = name
        self.debug = debug
        bitsize = None
        if isinstance(src, BitsFieldReader):
            if size is None:
                bitsize = src.bitsize - src.bitpos()
                size = bitsize // 8
            if data is None:
                data = src.data
            src = src.src
        if size is None:
            if data is None:
                try:
                    size = kwargs["size"] - kwargs["header_size"]
                except KeyError:
                    pos = src.tell()
                    src.seek(0, 2)  # seek to end
                    size = src.tell() - pos
                    src.seek(pos)
            else:
                size = len(data)
        if data is None:
            self.data = src.read(size)
            self.src = bitstring.ConstBitStream(bytes=self.data)
        else:
            self.data = data
            self.src = src
        self.kwargs = kwargs
        if bitsize is None:
            bitsize = 8 * size
        self.bitsize = bitsize
        if debug:
            self.log = logging.getLogger('bitio')
        else:
            self.log = None

    def duplicate(self, name, kwargs):
        return BitsFieldReader(name, self.src, kwargs, debug=self.debug,
                               size=len(self.data), data=self.data)

    def read(self, size, field):
        self.kwargs[field] = self.get(size, field)

    def read_bytes(self, length, field):
        if self.log:
            self.log.debug(
                '%s: read_bytes %s size=%d pos=%s', self.name, field, length,
                self.src.pos)
        data = self.src.read('bytes:{0}'.format(length))
        self.kwargs[field] = data

    def get(self, size, field):
        if self.log:
            self.log.debug(
                '%s: read %s size=%d pos=%s', self.name, field, size,
                self.src.bitpos)
        if size == 1:
            return self.src.read('bool')
        return self.src.read('uint:%d' % size)

    def bitpos(self):
        return self.src.bitpos

    def bytepos(self):
        return self.src.bytepos

class FieldWriter(object):
    def __init__(self, obj, dest, debug=False):
        self.obj = obj
        if isinstance(dest, FieldWriter):
            dest = dest.dest
        self.dest = dest
        self.bits = None
        if debug or getattr(self.obj, 'debug', False):
            self.log = logging.getLogger('bitio')
        elif hasattr(self.obj, 'options') and getattr(self.obj.options, 'debug', False):
            self.log = logging.getLogger('bitio')
        else:
            self.log = None

    def write(self, size, field, value=None):
        if value is None:
            value = getattr(self.obj, field)
        if isinstance(value, Binary):
            value = value.data
        if isinstance(size, basestring):
            if size == '0I':
                value = struct.pack('>I', value)[1:]
            elif size == 'S0':
                value += '\0'
            elif size[0] == 'D':
                bsz, asz = map(int, size[1:].split('.'))
                value = value * (1 << asz)
                value = struct.pack('>' + format_bit_sizes[bsz + asz],
                                    int(value))
            else:
                value = struct.pack('>' + size, value)
        elif isinstance(size, (int, long)):
            padding = size - len(value)
            if padding > 0:
                value += '\0' * padding
            elif padding < 0:
                value = value[:size]
        if self.log and self.log.isEnabledFor(logging.DEBUG):
            if isinstance(value, (int, long)):
                v = '0x' + hex(value)
            elif isinstance(value, basestring):
                v = '0x' + value.encode('hex')
            else:
                v = str(value)
            self.log.debug(
                '%s: Write %s size=%s (%d) pos=%d value=%s',
                self.obj.classname, field, str(size), len(value),
                self.dest.tell(), v)
        return self.dest.write(value)

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
                self.obj.classname, field, size,
                value)
        self.bits.append(bitstring.Bits(uint=value, length=size))

    def done(self):
        if self.bits is not None:
            self.dest.write(self.bits.bytes)


class BitsFieldWriter(object):
    def __init__(self, obj, dest=None):
        self.obj = obj
        if dest is None:
            self.bits = bitstring.BitArray()
        elif isinstance(dest, BitsFieldWriter):
            self.bits = dest.bits
        else:
            self.bits = dest
        if getattr(obj, 'debug', False):
            self.log = logging.getLogger('bitio')
        else:
            self.log = None

    def duplicate(self, new_obj):
        return BitsFieldWriter(obj=new_obj, dest=self.bits)

    def write(self, size, field, value=None):
        if value is None:
            value = getattr(self.obj, field)
        if self.log:
            self.log.debug(
                '%s: write %s size=%d pos=%d value=0x%x',
                self.obj.classname, field, size, self.bits.len, value)
        self.bits.append(bitstring.Bits(uint=value, length=size))

    def write_bytes(self, field, length=None, value=None):
        if value is None:
            value = getattr(self.obj, field)
        if length is None:
            length = len(value)
        if self.log:
            self.log.debug(
                '%s: write_bytes %s size=%d pos=%d',
                self.obj.classname, field, length, self.bits.len)
        self.bits.append(bitstring.Bits(bytes=value, length=(8 * length)))

    def append_writer(self, field_writer):
        self.bits.append(field_writer.bits)

    def overwrite(self, position, size, field, value=None):
        if value is None:
            value = getattr(self.obj, field)
        if self.log:
            self.log.debug(
                '%s: overwrite %s size=%d pos=%d value=0x%x',
                self.obj.classname, field, size, position, value)
        data = bitstring.Bits(uint=value, length=size)
        self.bits.overwrite(data, position)

    def bitpos(self):
        return self.bits.len

    def bytepos(self):
        bitpos = self.bitpos()
        assert((bitpos & 8) == 0)
        return bitpos // 8

    def toBytes(self):
        return self.bits.bytes

    def __len__(self):
        return self.bits.len
