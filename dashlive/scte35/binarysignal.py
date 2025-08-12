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


from dashlive.mpeg.section_table import MpegSectionTable
from dashlive.utils.list_of import ListOf
from .descriptors import SpliceDescriptor
from .splice_time import SpliceTime
from .splice_insert import SpliceInsert
from .splice_schedule import SpliceSchedule

class SapType:
    CLOSED_GOP_NO_LEADING_PICTURES = 0
    CLOSED_GOP_LEADING_PICTURES = 1
    OPEN_GOP = 2
    UNSPECIFIED = 3

class BinarySignal(MpegSectionTable):
    TABLE_ID = 0xFC
    DEFAULT_VALUES = {
        'cw_index': 0xFF,
        'descriptors': [],
        'encryption_algorithm': 0,
        'encrypted_packet': False,
        'private_indicator': False,
        'protocol_version': 0,
        'pts_adjustment': 0,
        'sap_type': SapType.UNSPECIFIED,
        'section_syntax_indicator': False,
        'splice_insert': None,
        'splice_schedule': None,
        'table_id': TABLE_ID,
        'tier': 0xfff,
        'time_signal': None,
    }
    OBJECT_FIELDS = {
        'splice_insert': SpliceInsert,
        'splice_schedule': SpliceSchedule,
        'descriptors': ListOf(SpliceDescriptor),
        'time_signal': SpliceTime,
    }

    @classmethod
    def parse_payload(cls, r, kwargs):
        r.read(8, 'protocol_version')
        r.read(1, 'encrypted_packet')
        r.read(6, 'encryption_algorithm')
        r.read(33, 'pts_adjustment')
        r.read(8, 'cw_index')
        r.read(12, 'tier')
        r.read(12, 'splice_command_length')
        r.read(8, 'splice_command_type')
        for field in {'splice_schedule', 'splice_insert', 'time_signal'}:
            kwargs[field] = None
        if kwargs['splice_command_type'] == 0:
            # splice_null() - nothing to do
            pass
        elif kwargs['splice_command_type'] == 4:
            kwargs['splice_schedule'] = SpliceSchedule.parse(r)
        elif kwargs['splice_command_type'] == 5:
            kwargs['splice_insert'] = SpliceInsert.parse(r)
        elif kwargs['splice_command_type'] == 6:
            kwargs['time_signal'] = SpliceTime.parse(r)
        elif kwargs['splice_command_type'] == 7:
            # bandwidth_reservation() - nothing to do
            pass
        elif kwargs['splice_command_type'] == 0xFF:
            cls._parse_private_command(r, kwargs)
            # as no private commands are supported, parsing must stop
            # at this point
            return kwargs
        descriptor_loop_length = r.get(16, 'descriptor_loop_length')
        endpos = r.bytepos() + descriptor_loop_length
        kwargs['descriptors'] = []
        while r.bytepos() < endpos:
            kwargs['descriptors'].append(SpliceDescriptor.parse(r))
        if kwargs['encrypted_packet']:
            r.read(32, 'e_crc_32')
        return kwargs

    def encode_fields(self, w):
        if self.splice_schedule is not None:
            self.splice_command_type = 4
        elif self.splice_insert is not None:
            self.splice_command_type = 5
        elif self.time_signal is not None:
            self.splice_command_type = 6
        else:
            self.splice_command_type = 0
        w.write(8, 'protocol_version')
        w.write(1, 'encrypted_packet')
        w.write(6, 'encryption_algorithm')
        w.write(33, 'pts_adjustment')
        w.write(8, 'cw_index')
        w.write(12, 'tier')
        pos = w.bitpos()
        w.write(12, 'splice_command_length', value=0)
        w.write(8, 'splice_command_type')
        if self.splice_command_type == 4:
            self.splice_schedule.encode(w)
        elif self.splice_command_type == 5:
            self.splice_insert.encode(w)
        elif self.splice_command_type == 6:
            self.time_signal.encode(w)
        # command_length excludes the splice_command_length and splice_command_type fields
        self.splice_command_length = (w.bitpos() - pos - 20) // 8
        w.overwrite(pos, 12, 'splice_command_length')
        pos = w.bitpos()
        w.write(16, 'descriptor_loop_length', value=0)
        for desc in self.descriptors:
            desc.encode(dest=w)
        self.descriptor_loop_length = (w.bitpos() - pos - 16) // 8
        w.overwrite(pos, 16, 'descriptor_loop_length')

    @classmethod
    def _parse_private_command(cls, r, kwargs):
        r.read(32, 'private_identifier')


if __name__ == "__main__":
    import base64
    import io
    import sys

    for arg in sys.argv[1:]:
        data: bytes = base64.b64decode(arg)
        src = io.BufferedReader(io.BytesIO(data))
        print('====')
        print(BinarySignal.parse(src, size=len(data)))
        print('====')
