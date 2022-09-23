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
from binascii import unhexlify

class Binary(object):
    BASE64 = 1
    HEX = 2

    def __init__(self, data, encoding=BASE64, _type=None):
        if data is not None:
            if _type is not None:
                if encoding == self.BASE64:
                    data = base64.b64decode(data)
                elif encoding == self.HEX:
                    data = unhexlify(data)
        self.data = data
        self.encoding = encoding

    @classmethod
    def from_kwargs(clz, data, encoding=None, _type=None):
        if data is not None:
            if isinstance(data, Binary):
                return data
            if encoding == clz.BASE64:
                data = base64.b64decode(data)
            elif encoding == clz.HEX or data[:2] == '0x':
                if data[:2] == '0x':
                    data = data[2:]
                data = unhexlify(data)
        if encoding is None:
            encoding = clz.BASE64
        return Binary(data=data, encoding=encoding)

    @property
    def classname(self):
        clz = type(self)
        if clz.__module__.startswith('__'):
            return clz.__name__
        return clz.__module__ + '.' + clz.__name__

    def toJSON(self, pure=False):
        if self.data is None:
            return None
        rv = {
            '_type': self.classname,
            'encoding': self.encoding,
        }
        if self.encoding == self.BASE64:
            rv['data'] = base64.b64encode(self.data)
        else:
            rv['data'] = self.data.encode('hex')
        return rv

    def encode(self, encoding):
        if encoding == self.HEX or encoding == 'hex':
            return self.data.encode('hex')
        if encoding == self.BASE64 or encoding == 'base64':
            return base64.b64encode(self.data)
        raise ValueError(r'Unknown encoding format: "{0}"'.format(encoding))

    def __len__(self):
        if self.data is None:
            return 0
        return len(self.data)

    def __repr__(self):
        if self.data is None:
            encoded_data = 'None'
        elif self.encoding == self.BASE64:
            encoded_data = base64.b64encode(self.data)
        else:
            encoded_data = '0x' + self.data.encode('hex')
        return r'{0}(encoding={1}, data={2})'.format(
            self.classname,
            self.encoding,
            encoded_data)

class HexBinary(Binary):
    def __init__(self, data, encoding=None, _type=None):
        super(HexBinary, self).__init__(data, encoding, _type)
        self.encoding = Binary.HEX

    @classmethod
    def from_kwargs(clz, data, encoding=None, _type=None):
        assert encoding != Binary.BASE64
        if data is not None:
            if isinstance(data, HexBinary):
                return data
            if encoding is None and (len(data) % 2) == 0 and data[:2] == '0x':
                encoding = Binary.HEX
            if encoding == Binary.HEX:
                data = unhexlify(data)
        if encoding is None:
            encoding = Binary.HEX
        return HexBinary(data=data, encoding=encoding)
