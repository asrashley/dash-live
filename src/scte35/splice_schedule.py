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

from scte35.break_duration import BreakDuration
from utils.bitio import BitsFieldReader, BitsFieldWriter
from utils.object_with_fields import ObjectWithFields
from utils.list_of import ListOf

class SpliceItem(ObjectWithFields):
    OBJECT_FIELDS = {
        'break_duration': BreakDuration
    }

    @classmethod
    def parse(cls, bit_reader):
        kwargs = {}
        spr = bit_reader.duplicate(kwargs)
        spr.read(32, 'event_id')
        spr.read(1, 'event_cancel_indicator')
        spr.get(7, 'reserved')
        if kwargs['event_cancel_indicator']:
            return kwargs
        spr.read(1, 'out_of_network_indicator')
        spr.read(1, 'program_splice_flag')
        spr.read(1, 'duration_flag')
        spr.get(5, 'reserved')
        if kwargs['program_splice_flag']:
            spr.read(32, 'utc_splice_time')
            kwargs['components'] = None
        else:
            kwargs['utc_splice_time'] = None
            component_count = spr.get(8, 'component_count')
            kwargs['components'] = []
            for j in range(component_count):
                kwargs['components'].append({
                    'tag': spr.get(8, 'tag'),
                    'utc_splice_time': spr.get(32, 'utc_splice_time'),
                })
        if kwargs['duration_flag']:
            kwargs['break_duration'] = BreakDuration.parse(spr)
        else:
            kwargs['break_duration'] = None
        spr.read(16, 'unique_program_id')
        spr.read(8, 'avail_num')
        spr.read(8, 'avails_expected')
        return kwargs

    def encode(self, dest):
        w = BitsFieldWriter(self, dest)
        w.write(32, 'event_id')
        w.write(1, 'event_cancel_indicator')
        w.write(7, 'reserved', value=0x7F)
        if self.event_cancel_indicator:
            return
        self.program_splice_flag = self.utc_splice_time is not None
        self.duration_flag = self.break_duration is not None
        w.write(1, 'out_of_network_indicator')
        w.write(1, 'program_splice_flag')
        w.write(1, 'duration_flag')
        w.write(5, 'reserved', value=0x1F)
        if self.program_splice_flag:
            w.write(32, 'utc_splice_time')
        else:
            w.write(8, 'component_count', value=len(self.components))
            for comp in self.components:
                w.write(8, 'tag', value=comp['tag'])
                w.write(32, 'utc_splice_time', value=comp['utc_splice_time'])
        if self.break_duration:
            self.break_duration.encode(w)
        w.write(16, 'unique_program_id')
        w.write(8, 'avail_num')
        w.write(8, 'avails_expected')


class SpliceSchedule(ObjectWithFields):
    OBJECT_FIELDS = {
        'splices': ListOf(SpliceItem),
    }

    @classmethod
    def parse(cls, src):
        kwargs = {}
        r = BitsFieldReader(cls, src, kwargs)
        splice_count = r.get(8, 'splice_count')
        kwargs['splices'] = []
        for idx in range(splice_count):
            splice = SpliceItem.parse(r)
            kwargs['splices'].append(splice)

    def encode(self, dest):
        w = BitsFieldWriter(self, dest)
        w.write(8, 'splice_count', value=len(self.splices))
        for splice in self.splices:
            splice.encode(w)
