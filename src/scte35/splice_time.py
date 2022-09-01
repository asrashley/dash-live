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

class SpliceTime(ObjectWithFields):
    @classmethod
    def parse(cls, src):
        kwargs = {}
        r = BitsFieldReader(cls, src, kwargs)
        time_specified_flag = r.get(1, 'time_specified_flag')
        if time_specified_flag:
            r.get(6, 'reserved')
            r.read(33, 'pts')
        else:
            kwargs['pts'] = None
        return kwargs

    def encode(self, dest):
        w = BitsFieldWriter(self, dest)
        if self.pts is None:
            w.write(1, 'time_specified_flag', value=0)
        else:
            w.write(1, 'time_specified_flag', value=1)
            w.write(6, 'reserved', 0x3F)
            w.write(33, 'pts')
