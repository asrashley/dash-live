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

import bitstring

class BitsFieldReader:
    __slots__ = ('name', 'debug', 'data', 'src', 'kwargs', 'bitsize', 'log')

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
            self.log = logging.getLogger('fio')
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
        data = self.src.read(f'bytes:{length}')
        self.kwargs[field] = data

    def get(self, size, field):
        if self.log:
            self.log.debug(
                '%s: read %s size=%d pos=%s', self.name, field, size,
                self.src.bitpos)
        if size == 1:
            return self.src.read('bool')
        return self.src.read('uint:%d' % size)

    def get_bytes(self, length, field):
        if self.log:
            self.log.debug(
                '%s: read_bytes %s size=%d pos=%s', self.name, field, length,
                self.src.pos)
        data = self.src.read(f'bytes:{length}')
        return data

    def bitpos(self):
        return self.src.bitpos

    def bytepos(self):
        return self.src.bytepos
