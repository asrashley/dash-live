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

from bitio import BitsFieldReader, BitsFieldWriter

from objects import ObjectWithFields
from break_duration import BreakDuration
from splice_time import SpliceTime

class SpliceInsert(ObjectWithFields):
    OBJECT_FIELDS = {
        'break_duration': BreakDuration,
        'splice_time': SpliceTime,
    }
    DEFAULT_VALUES = {
        "splice_event_cancel_indicator": False,
        "splice_immediate_flag": False,
        "out_of_network_indicator": True,
    }

    @classmethod
    def parse(cls, src):
        kwargs = {}
        r = BitsFieldReader(cls, src, kwargs)
        r.read(32, 'splice_event_id')
        r.read(1, 'splice_event_cancel_indicator')
        r.get(7, 'reserved')
        if kwargs['splice_event_cancel_indicator']:
            return
        r.read(1, 'out_of_network_indicator')
        r.read(1, 'program_splice_flag')
        r.read(1, 'duration_flag')
        r.read(1, 'splice_immediate_flag')
        r.get(4, 'reserved')
        if kwargs['program_splice_flag'] and not kwargs['splice_immediate_flag']:
            kwargs['splice_time'] = SpliceTime.parse(r)
        if not kwargs['program_splice_flag']:
            r.read(8, 'component_count')
            kwargs['components'] = []
            for j in range(kwargs['component_count']):
                kwargs['components'].append({
                    'tag': r.get(8, 'tag'),
                    'splice_time': SpliceTime.parse(r)
                })
        if kwargs['duration_flag']:
            kwargs['break_duration'] = BreakDuration.parse(r)
        else:
            kwargs['break_duration'] = None
        r.read(16, 'unique_program_id')
        r.read(8, 'avail_num')
        r.read(8, 'avails_expected')
        return kwargs

    def encode(self, dest):
        w = BitsFieldWriter(self, dest)
        w.write(32, 'splice_event_id')
        w.write(1, 'splice_event_cancel_indicator')
        w.write(7, 'reserved', value=0x7F)
        if self.splice_event_cancel_indicator:
            return
        self.duration_flag = self.break_duration is not None
        w.write(1, 'out_of_network_indicator')
        w.write(1, 'program_splice_flag')
        w.write(1, 'duration_flag')
        w.write(1, 'splice_immediate_flag')
        w.write(4, 'reserved', value=0x0F)
        if self.program_splice_flag and not self.splice_immediate_flag:
            self.splice_time.encode(w)
        if not self.program_splice_flag:
            self.component_count = len(self.components)
            w.write(8, 'component_count')
            for comp in self.components:
                w.write(8, 'tag', value=comp.tag)
                comp.splice_time.encode(w)
        if self.break_duration:
            self.break_duration.encode(w)
        w.write(16, 'unique_program_id')
        w.write(8, 'avail_num')
        w.write(8, 'avails_expected')
