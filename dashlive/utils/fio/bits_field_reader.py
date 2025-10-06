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
from typing import BinaryIO, Union, cast

import bitstring

class BitsFieldReader:
    __slots__ = ('name', 'debug', 'data', 'src', 'kwargs', 'bitsize', 'log')

    debug: bool
    name: str
    data: bytes
    bitsize: int
    src: bitstring.ConstBitStream
    log: logging.Logger | None

    def __init__(self, name: str, src: Union["BitsFieldReader", BinaryIO], kwargs,
                 size: int | None = None, data: bytes | None = None, debug: bool = False) -> None:
        self.name = name
        self.debug = debug
        bitsize: int | None = None
        if isinstance(src, BitsFieldReader):
            if size is None:
                bitsize = src.bitsize - src.bitpos()
                size = cast(int, bitsize) // 8
            if data is None:
                data = src.data
            src = cast(BinaryIO, src.src)
        elif size is None:
            if data is None:
                try:
                    size = kwargs["size"] - kwargs["header_size"]
                except KeyError:
                    pos: int = src.tell()
                    src.seek(0, 2)  # seek to end
                    size = src.tell() - pos
                    src.seek(pos)
            else:
                size = len(data)
        if data is None:
            assert size is not None
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

    def duplicate(self, name, kwargs) -> "BitsFieldReader":
        return BitsFieldReader(name, self.src, kwargs, debug=self.debug,
                               size=len(self.data), data=self.data)

    def read(self, size, field) -> None:
        self.kwargs[field] = self.get(size, field)

    def read_bytes(self, length, field) -> None:
        if self.log:
            self.log.debug(
                '%s: read_bytes %s size=%d pos=%s', self.name, field, length,
                self.src.pos)
        data = self.src.read(f'bytes:{length}')
        self.kwargs[field] = data

    def get(self, size: int, field: str) -> bool | int:
        if self.log:
            self.log.debug(
                '%s: read %s size=%d pos=%s', self.name, field, size,
                self.src.bitpos)
        if size == 1:
            return cast(bool, self.src.read('bool'))
        return cast(int, self.src.read('uint:%d' % size))

    def get_bytes(self, length, field) -> bytes:
        if self.log:
            self.log.debug(
                '%s: read_bytes %s size=%d pos=%s', self.name, field, length,
                self.src.pos)
        data: bytes = cast(bytes, self.src.read(f'bytes:{length}'))
        return data

    def bitpos(self) -> int:
        return self.src.bitpos

    def bytepos(self) -> int:
        return self.src.bytepos
