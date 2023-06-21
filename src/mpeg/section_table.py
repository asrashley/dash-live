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
from abc import abstractmethod

from crccheck.crc import Crc32Mpeg2

from dashlive.utils.fio import BitsFieldReader, BitsFieldWriter
from dashlive.utils.object_with_fields import ObjectWithFields

class MpegSectionTable(ObjectWithFields):
    @classmethod
    def parse(cls, src, size=None):
        kwargs = {
            'position': src.tell()
        }
        r = BitsFieldReader(cls, src, kwargs, size=size)
        r.read(8, 'table_id')
        r.read(1, 'section_syntax_indicator')
        r.read(1, 'private_indicator')
        r.read(2, 'sap_type')
        r.read(12, 'section_length')
        kwargs['header_size'] = r.bytepos() - kwargs['position']
        cls.parse_payload(r, kwargs)
        r.read(32, 'crc')
        crc = Crc32Mpeg2()
        crc.process(memoryview(r.data[kwargs['position']:r.bytepos()]).tolist())
        kwargs['crc_valid'] = crc.final() == 0
        return kwargs

    def encode(self, dest=None):
        w = BitsFieldWriter(self, dest)
        w.write(8, 'table_id')
        w.write(1, 'section_syntax_indicator')
        w.write(1, 'private_indicator')
        w.write(2, 'sap_type')
        pos = w.bitpos()
        w.write(12, 'section_length', value=0)
        self.encode_fields(w)
        # NOTE: section_length includes the CRC field
        self.section_length = 4 + ((w.bitpos() - pos - 12) // 8)
        w.overwrite(pos, 12, 'section_length')
        data = w.toBytes()
        crc = Crc32Mpeg2()
        crc.process(memoryview(data).tolist())
        w.write(32, 'crc32', value=crc.final())
        if dest is None:
            return w.toBytes()
        return w

    @abstractmethod
    def encode_fields(self, dest):
        pass
