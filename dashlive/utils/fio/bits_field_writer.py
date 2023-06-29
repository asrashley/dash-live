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

from builtins import object
import logging
import os
import sys

try:
    import bitstring
except ImportError:
    sys.path.append(
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "lib")))
    import bitstring


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
            self.log = logging.getLogger('fio')
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
                self.obj.classname(), field, size, self.bits.len, value)
        self.bits.append(bitstring.Bits(uint=value, length=size))

    def write_bytes(self, field, length=None, value=None):
        if value is None:
            value = getattr(self.obj, field)
        if length is None:
            length = len(value)
        if self.log:
            self.log.debug(
                '%s: write_bytes %s size=%d pos=%d',
                self.obj.classname(), field, length, self.bits.len)
        self.bits.append(bitstring.Bits(bytes=value, length=(8 * length)))

    def append_writer(self, field_writer):
        self.bits.append(field_writer.bits)

    def overwrite(self, position, size, field, value=None):
        if value is None:
            value = getattr(self.obj, field)
        if self.log:
            self.log.debug(
                '%s: overwrite %s size=%d pos=%d value=0x%x',
                self.obj.classname(), field, size, position, value)
        data = bitstring.Bits(uint=value, length=size)
        self.bits.overwrite(data, position)

    def bitpos(self):
        return self.bits.len

    def bytepos(self):
        bitpos = self.bitpos()
        assert ((bitpos & 8) == 0)
        return bitpos // 8

    def toBytes(self):
        return self.bits.bytes

    def __len__(self):
        return self.bits.len
