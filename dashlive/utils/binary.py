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
import base64
from binascii import unhexlify, b2a_hex
from typing import Union

class Binary(object):
    BASE64 = 1
    HEX = 2

    def __init__(self, data, encoding=BASE64, _type=None):
        if data is not None and _type is not None:
            if encoding == self.BASE64:
                data = base64.b64decode(data)
            elif encoding == self.HEX:
                data = unhexlify(data)
        self.data = data
        self.encoding = encoding

    @classmethod
    def from_kwargs(clz, data=None, encoding=None, _type=None, b64=None, hx=None):
        if data is not None:
            if isinstance(data, Binary):
                return data
            if encoding is None and (len(data) % 2) == 0 and data[:2] == '0x':
                encoding = clz.HEX
            if encoding == clz.BASE64:
                data = base64.b64decode(data)
            elif encoding == clz.HEX:
                if data[:2] == '0x':
                    data = data[2:]
                data = unhexlify(data)
        if b64 is not None:
            encoding = clz.BASE64
            data = base64.b64decode(b64)
        elif hx is not None:
            encoding = clz.HEX
            if hx[:2] == '0x':
                hx = hx[2:]
            data = unhexlify(hx)
        if encoding is None:
            encoding = clz.BASE64
        return clz(data=data, encoding=encoding)

    @classmethod
    def classname(clz):
        if clz.__module__.startswith('__'):
            return clz.__name__
        return clz.__module__ + '.' + clz.__name__

    def toJSON(self, pure=False):
        if self.data is None:
            return None
        rv = {
            '_type': self.classname(),
        }
        if self.encoding == self.BASE64:
            rv['b64'] = str(base64.b64encode(self.data), 'ascii')
        else:
            rv['hx'] = str(b2a_hex(self.data), 'ascii')
        return rv

    def encode(self, encoding):
        if encoding == self.HEX or encoding == 'hex':
            return str(b2a_hex(self.data), 'ascii')
        if encoding == self.BASE64 or encoding == 'base64':
            return str(base64.b64encode(self.data), 'ascii')
        raise ValueError(r'Unknown encoding format: "{0}"'.format(encoding))

    def __len__(self):
        if self.data is None:
            return 0
        return len(self.data)

    def __repr__(self):
        encoding = ''
        if self.data is None:
            encoded_data = 'None'
        elif self.encoding == self.BASE64:
            encoded_data = str(base64.b64encode(self.data), 'ascii')
            encoding = 'b64='
        else:
            encoded_data = '0x' + str(self.data.encode('hex'), 'ascii')
            encoding = 'hx='
        return f'{self.classname()}({encoding}{encoded_data})'

    def __eq__(self, other: Union["Binary", bytes]) -> bool:
        if isinstance(other, bytes):
            return self.data == other
        return (
            self.encoding == other.encoding and
            self.data == other.data)


class HexBinary(Binary):
    def __init__(self, data, encoding=None, _type=None):
        super(HexBinary, self).__init__(data, encoding=Binary.HEX, _type=_type)
        self.encoding = Binary.HEX
